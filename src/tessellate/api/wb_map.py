"""A map's node routes: the tree, create, paste an outline, move and clear a node's style.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from tessellate.core.database import WhiteboardObject
from tessellate.core import events
from tessellate.entry.manager_text import extract_title
from sqlalchemy import func, select
from tessellate.core.deps import get_session
from tessellate.api.wb_model import Coord, MAP_REFERENCE_KINDS, MAP_TOPIC_KIND, MAX_OBJECT_TEXT_CHARS, WhiteboardObjectData, WhiteboardObjectOut, _object_to_out
from tessellate.core.events import object_state as _object_state
from tessellate.api.wb_tree import MAP_COL, MAP_ROW, MAP_STYLE_FIELDS, MAX_IMPORT_CHARS, MAX_MAP_DEPTH, MapTreeOut, _build_tree, _cross_links, _map_kind_ok, _map_objects, _object_data, _require_reference
from tessellate.api.wb_board import _board_entry, _board_filter, _board_numbered, _board_settings, _board_theme, _require_board
from tessellate.api.wb_preview import _board_palette
from tessellate.api.wb_import import _parse_markdown_outline, _place_map_nodes

router = APIRouter()


@router.get("/boards/{board_id}/tree", response_model=MapTreeOut)
def board_tree(board_id: int, db: Session = Depends(get_session)) -> MapTreeOut:
    """The board as a nested tree, plus its cross-links.

    The one endpoint a map client cannot do without: `GET /whiteboard/` hands
    back a flat list of objects, and rebuilding the tree from it client-side
    means every reader (the canvas, the Library thumbnail, an export, the
    agent) writes the same walk again, including the dangling-parent and
    ring cases, which is exactly the sort of thing four copies get subtly
    differently.
    """
    entry = _board_entry(db, board_id)
    board_type, layout = _board_settings(entry)
    objects = _map_objects(db, board_id)
    return MapTreeOut(
        board_id=board_id,
        title=extract_title(entry.content) or entry.content.strip()[:40] or f"Note {board_id}",
        type=board_type,
        layout=layout,
        roots=_build_tree(db, objects),
        cross_links=_cross_links(db, board_id, {obj.id for obj in objects}),
        theme=_board_theme(entry),
        numbered=_board_numbered(entry),
        palette=_board_palette(_board_theme(entry)),
    )


class MapNodeCreate(BaseModel):
    kind: str = MAP_TOPIC_KIND
    #: The parent this node hangs off, or None for a root topic.
    parent_id: int | None = None
    text: str = Field(default="", max_length=MAX_OBJECT_TEXT_CHARS)
    #: For a `note`/`document`/`file`/`link` node: what it stands for.
    ref_id: int | None = Field(default=None, ge=1)
    #: Omitted means "put it somewhere sensible", see `_next_position`. A
    #: caller that has to invent coordinates gets them wrong, which is the
    #: whole reason `generate_diagram` computes them server-side too.
    x: Coord | None = None
    y: Coord | None = None
    color: str | None = Field(default=None, max_length=20)


def _next_position(
    db: Session, board_id: int, parent: WhiteboardObject | None
) -> tuple[float, float]:
    """Where a new node goes when the caller did not say.

    One column right of its parent, one row below the last sibling, the same
    row/column convention `wbArrangeMindMap` and `generate_diagram` already
    use, so a map built by hand, by import and by the agent does not read as
    three different tools' opinions. Roots stack down the left edge.
    """
    siblings = db.scalars(
        select(func.count())
        .select_from(WhiteboardObject)
        .where(
            _board_filter(WhiteboardObject, board_id),
            WhiteboardObject.parent_id == parent.id
            if parent is not None
            else WhiteboardObject.parent_id.is_(None),
        )
    ).one()
    if parent is None:
        return 0.0, float(siblings) * MAP_ROW
    return float(parent.x) + MAP_COL, float(parent.y) + float(siblings) * MAP_ROW


@router.post(
    "/boards/{board_id}/nodes", response_model=WhiteboardObjectOut, status_code=201
)
@events.writes("whiteboard_object", "created")
def create_map_node(
    board_id: int, body: MapNodeCreate, db: Session = Depends(get_session)
) -> WhiteboardObjectOut:
    """Add a node under a parent, or as a new root.

    Not a second CRUD for `whiteboard_objects`, `PUT`/`DELETE /objects/{id}`
    still own the rest of a node's life. This exists for the two things the
    generic create cannot do without a client that already knows the whole
    tree: attach the node to a parent (with the board scoping that implies)
    and work out where it goes.
    """
    _require_board(db, board_id)
    _map_kind_ok(body.kind)
    if body.kind in MAP_REFERENCE_KINDS:
        _require_reference(db, body.kind, body.ref_id)

    parent = None
    if body.parent_id is not None:
        parent = db.get(WhiteboardObject, body.parent_id)
        # Scoped to the board it claims, the rule this module opens with. A
        # parent on another board would build a tree spanning two boards,
        # which renders on neither.
        if parent is None or parent.board_id != board_id:
            raise HTTPException(
                status_code=404,
                detail="That node is not on this board.",
            )

    if body.x is not None and body.y is not None:
        x, y = body.x, body.y
    else:
        x, y = _next_position(db, board_id, parent)
    data = WhiteboardObjectData(
        content=body.text,
        ref_id=body.ref_id if body.kind in MAP_REFERENCE_KINDS else None,
        color=body.color,
    )
    obj = WhiteboardObject(
        board_id=board_id,
        kind=body.kind,
        data=data.model_dump_json(exclude_none=True),
        x=x,
        y=y,
        z=1,
        parent_id=parent.id if parent is not None else None,
    )
    db.add(obj)
    db.flush()  # so the event can name the node's id
    events.record(
        db,
        "created",
        "whiteboard_object",
        obj.id,
        f"{obj.kind} on map {board_id}",
        payload={"after": _object_state(obj)},
    )
    db.commit()
    db.refresh(obj)
    return _object_to_out(obj)


class MapOutlinePaste(BaseModel):
    #: The topic the outline goes under, or None for new trunks.
    parent_id: int | None = None
    text: str = Field(min_length=1, max_length=MAX_IMPORT_CHARS)


#: A numbered line's number, taken off so it reads as a bullet.
_PASTE_NUMBERED = re.compile(r"^(\s*)\d+[.)]\s+")


def _outline_from_paste(text: str) -> str:
    """Plain pasted text as the bullet outline `_parse_markdown_outline`
    reads: a line keeps its indentation and becomes a bullet, a numbered
    line loses its number, and a heading line becomes a bullet too (pasted
    text names no map, so a heading is a topic like any other)."""
    out = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if not raw.strip():
            continue
        line = _PASTE_NUMBERED.sub(r"\1- ", raw.rstrip())
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("#"):
            stripped = "- " + stripped.lstrip("#").strip()
        elif stripped[0] not in "-*+" or not stripped[1:2].isspace():
            stripped = "- " + stripped
        out.append(indent + stripped)
    return "\n".join(out)


@router.post(
    "/boards/{board_id}/nodes/outline",
    response_model=list[WhiteboardObjectOut],
    status_code=201,
)
def paste_map_outline(
    board_id: int, body: MapOutlinePaste, db: Session = Depends(get_session)
) -> list[WhiteboardObjectOut]:
    """**Text pasted onto a map becomes a branch** (audit FEAT-09,
    2026-10-05). An indented list from anywhere (a note, a document, another
    mind mapper's outline) comes in under the selected topic as topics, one
    per line and nested by indentation, in one transaction, so the client
    records it as one Undo step. The same outline reader the Markdown import
    uses, so a paste and an import cannot disagree about what a line means.
    """
    _require_board(db, board_id)
    parent = None
    if body.parent_id is not None:
        parent = db.get(WhiteboardObject, body.parent_id)
        if parent is None or parent.board_id != board_id:
            raise HTTPException(status_code=404, detail="That node is not on this board.")
    _, parsed = _parse_markdown_outline(_outline_from_paste(body.text))
    if not parsed:
        raise HTTPException(status_code=422, detail="There is nothing to add: the text has no lines.")
    # The top lines hang off the topic they were pasted onto (`under`).
    created = _place_map_nodes(db, board_id, parsed, under=parent)
    for obj in created:
        events.record(
            db,
            "created",
            "whiteboard_object",
            obj.id,
            f"{obj.kind} on map {board_id}",
            payload={"after": _object_state(obj)},
        )
    db.commit()
    for obj in created:
        db.refresh(obj)
    return [_object_to_out(obj) for obj in created]


class MapNodeMove(BaseModel):
    #: The new parent, or None to promote the node to a root. The node keeps
    #: its own children either way, moving a node moves its branch.
    parent_id: int | None = None


def _is_descendant(
    db: Session, node_id: int, candidate_id: int, board_id: int | None
) -> bool:
    """Is `candidate_id` somewhere under `node_id`?

    Walks down rather than up, and iteratively: walking up from the candidate
    follows `parent_id` pointers that may already be broken, and a recursive
    walk of a tree that is not one is a stack overflow rather than a refusal.
    """
    seen = {node_id}
    frontier = [node_id]
    depth = 0
    while frontier and depth < MAX_MAP_DEPTH:
        children = list(
            db.scalars(
                select(WhiteboardObject.id).where(
                    WhiteboardObject.parent_id.in_(frontier),
                    _board_filter(WhiteboardObject, board_id),
                )
            )
        )
        if candidate_id in children:
            return True
        frontier = [child for child in children if child not in seen]
        seen.update(frontier)
        depth += 1
    return False


@router.put(
    "/boards/{board_id}/nodes/{node_id}/move", response_model=WhiteboardObjectOut
)
@events.writes("whiteboard_object", "edited")
def move_map_node(
    board_id: int, node_id: int, body: MapNodeMove, db: Session = Depends(get_session)
) -> WhiteboardObjectOut:
    """Re-parent a node, and with it its whole branch.

    **The cycle check is why this endpoint exists at all**, and why `PUT
    /objects/{id}` deliberately does not touch `parent_id`: a node made its
    own descendant produces a ring no tree walk can leave, so the map becomes
    unreadable: and the only UI that could undo it is the one that has just
    stopped rendering.
    """
    _require_board(db, board_id)
    node = db.get(WhiteboardObject, node_id)
    if node is None or node.board_id != board_id:
        raise HTTPException(
            status_code=404, detail="That node is not on this board."
        )

    before = _object_state(node)
    if body.parent_id is None:
        node.parent_id = None
    else:
        if body.parent_id == node.id:
            raise HTTPException(
                status_code=422,
                detail="A node can't be its own parent.",
            )
        parent = db.get(WhiteboardObject, body.parent_id)
        if parent is None or parent.board_id != board_id:
            raise HTTPException(
                status_code=404,
                detail="That node is not on this board.",
            )
        if _is_descendant(db, node.id, parent.id, board_id):
            raise HTTPException(
                status_code=422,
                detail="That would make the node a descendant of itself. Move the branch out first.",
            )
        node.parent_id = parent.id
    events.record(
        db,
        "edited",
        "whiteboard_object",
        node.id,
        f"moved under {node.parent_id}" if node.parent_id else "moved to a root",
        payload={"after": _object_state(node), "before": before},
    )
    db.commit()
    db.refresh(node)
    return _object_to_out(node)


class MapNodeMoveOne(BaseModel):
    """One node's new place: whose child it is, and where it sits."""

    id: int
    #: Absent means "leave the parent alone", which is what a tidy wants: a
    #: tidy moves every node's box and re-parents none of them. `None` is a
    #: real value here and means "promote this node to a root", so the two
    #: cannot share one sentinel and the field is a string-tagged optional
    #: rather than a bare `int | None`.
    reparent: bool = False
    parent_id: int | None = None
    x: Coord | None = None
    y: Coord | None = None


class MapNodesMove(BaseModel):
    #: 400 rather than no cap: a tidy of the largest map anyone has built here
    #: is a few hundred nodes, and an unbounded list is a request body that can
    #: be made to hold anything.
    moves: list[MapNodeMoveOne] = Field(default_factory=list, max_length=400)


def _parent_map(db: Session, board_id: int) -> dict[int, int | None]:
    """Every node on the board as `id -> parent_id`, in one query."""
    rows = db.execute(
        select(WhiteboardObject.id, WhiteboardObject.parent_id).where(
            _board_filter(WhiteboardObject, board_id)
        )
    ).all()
    return {row[0]: row[1] for row in rows}


def _first_cycle(parents: dict[int, int | None], changed: set[int]) -> int | None:
    """The first node in `changed` that can reach itself by walking up.

    Walking up is safe here, unlike in `_is_descendant`, precisely because the
    walk is over a dict this function owns rather than over rows another
    request may be editing: the whole batch is checked against the shape it
    *would* produce, before a single row is written. A seen set rather than a
    depth cap alone, because a ring that does not contain the node it was
    entered from is still a ring, and the walk would otherwise spin until the
    cap and report the wrong node.
    """
    for node_id in changed:
        seen = {node_id}
        current = parents.get(node_id)
        steps = 0
        while current is not None and steps <= MAX_MAP_DEPTH:
            if current in seen:
                return node_id
            seen.add(current)
            current = parents.get(current)
            steps += 1
        if current is not None:
            # Deeper than any tree this app draws: treated as a ring rather
            # than walked further, which is the same refusal for the same
            # reason.
            return node_id
    return None


@router.put("/boards/{board_id}/nodes/move-many", response_model=list[WhiteboardObjectOut])
@events.writes("whiteboard_object", "edited")
def move_map_nodes(
    board_id: int, body: MapNodesMove, db: Session = Depends(get_session)
) -> list[WhiteboardObjectOut]:
    """Move a set of nodes in one request, one transaction, one cycle check.

    **Why this exists.** Tidy persists one node at a time, transplanting a
    branch is one `/move` per child, and opening every folded branch is one PUT
    per folded node: a tidy of two hundred nodes is two hundred round trips,
    two hundred transactions, and a map that is half arranged for as long as
    they take. Any one of them failing leaves the map in a shape nobody asked
    for, because there is nothing to roll back to.

    The batch is all or nothing. Every id is checked against the board, every
    new parent is checked against the board, and the cycle check runs once
    against the shape the whole batch *would* produce rather than per move:
    checking each move against the map as it stands would pass a pair of moves
    that are each innocent and together make a ring.
    """
    _require_board(db, board_id)
    if not body.moves:
        return []
    seen_ids: set[int] = set()
    for move in body.moves:
        if move.id in seen_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Node {move.id} is in this batch twice; each node moves once.",
            )
        seen_ids.add(move.id)

    nodes = {
        node.id: node
        for node in db.scalars(
            select(WhiteboardObject).where(
                WhiteboardObject.id.in_(seen_ids),
                _board_filter(WhiteboardObject, board_id),
            )
        )
    }
    missing = sorted(seen_ids - set(nodes))
    if missing:
        raise HTTPException(
            status_code=404, detail="That node is not on this board."
        )

    parents = _parent_map(db, board_id)
    reparented: set[int] = set()
    for move in body.moves:
        if not move.reparent:
            continue
        if move.parent_id is not None:
            if move.parent_id == move.id:
                raise HTTPException(
                    status_code=422,
                    detail="A node can't be its own parent.",
                )
            if move.parent_id not in parents:
                raise HTTPException(
                    status_code=404,
                    detail="That node is not on this board.",
                )
        parents[move.id] = move.parent_id
        reparented.add(move.id)

    offender = _first_cycle(parents, reparented)
    if offender is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"That would make node {offender} a descendant of itself. "
                "Move the branch out first."
            ),
        )

    out: list[WhiteboardObjectOut] = []
    before_states: list[dict] = []
    for move in body.moves:
        node = nodes[move.id]
        before_states.append(_object_state(node))
        if move.reparent:
            node.parent_id = move.parent_id
        if move.x is not None:
            node.x = move.x
        if move.y is not None:
            node.y = move.y
        out.append(node)
    #: **One event, not one per node**, which is what `events.writes` on this
    #: function means and why the decorator's own docstring warns against
    #: decorating a loop: a tidy is one thing the person did, and twelve
    #: `edited` rows for one press of Tidy is a history nobody can read. The
    #: whole batch's before and after ride in the payload, so nothing is lost;
    #: the single-node `/move` above still records per node, because there it
    #: really is one node the person moved.
    events.record(
        db,
        "edited",
        "whiteboard_object",
        out[0].id,
        f"moved {len(out)} nodes on map {board_id}"
        if len(out) > 1
        else (f"moved under {out[0].parent_id}" if out[0].parent_id else "moved to a root"),
        payload={
            "after": [_object_state(node) for node in out],
            "before": before_states,
        },
    )
    db.commit()
    for node in out:
        db.refresh(node)
    return [_object_to_out(node) for node in out]


class MapClearStyleOut(BaseModel):
    """How many topics changed, so the toast can say it rather than guess."""

    cleared: int


#: What "back to the map" drops from a topic, which is exactly what "back to
#: the branch" drops from one node (`WB_MAP_STYLE_KEYS`, whiteboard.js): the
#: same list, at the other scope. `color` is in it because a hand-painted
#: topic is a look somebody gave one topic, and `image` is not, because a
#: picture is content: the reset's whole promise is that it is the safe way
#: out of a topic you over-decorated, and one that also threw away an upload
#: would be the one control on this map you cannot press to find out what it
#: does. `MAP_STYLE_FIELDS` minus the content ones, plus the colour it does
#: not list because a node has carried `color` as a key of its own since
#: before any of this existed.
MAP_CONTENT_FIELDS = frozenset({
    "image", "task", "note", "boundary", "boundary_label", "boundary_set", "summary", "summary_span", "branch_layout", "callout", "labels", "stamps",
    "priority", "progress", "flag", "markers", "due", "due_time", "start", "recording",
})
MAP_CLEARABLE_FIELDS = frozenset(MAP_STYLE_FIELDS) - MAP_CONTENT_FIELDS | {"color"}


@router.post("/boards/{board_id}/nodes/clear-style", response_model=MapClearStyleOut)
@events.writes("whiteboard_object", "edited")
def clear_map_node_styles(
    board_id: int, db: Session = Depends(get_session)
) -> MapClearStyleOut:
    """Drop every per-topic look on this map in one request, one transaction.

    **This is "Reset to branch" at the map's scope, not a second idea**
    (MINDMAP_PLAN.md §13e). The ring's own reset drops this exact list from
    one topic so that it goes back to following what it inherits; with a map
    theme, what a topic inherits is the map, so the same sentence said about
    the whole map is the bulk operation §13.4 measured missing. One button
    that means two things at two scopes is one thing to learn; two buttons
    that mean nearly the same would be two.

    One request for the same reason `move-many` is one: a reset that is one
    PUT per topic is two hundred round trips on a two-hundred-topic map, and
    any one of them failing leaves the map half reset with nothing to roll
    back to.
    """
    _require_board(db, board_id)
    objects = _map_objects(db, board_id)
    cleared = 0
    for obj in objects:
        data = _object_data(obj)
        dropped = {key: value for key, value in data.items() if key in MAP_CLEARABLE_FIELDS}
        if not dropped:
            continue
        for key in dropped:
            data.pop(key, None)
        obj.data = json.dumps(data)
        cleared += 1
    if cleared:
        #: One event for the whole press, the reason `move-many` gives: a
        #: person pressed one thing once, and a row per topic is a history
        #: nobody can read.
        events.record(
            db,
            "edited",
            "whiteboard_object",
            objects[0].id,
            f"cleared the look of {cleared} topic" + ("" if cleared == 1 else "s")
            + f" on map {board_id}",
            payload={"after": {"cleared": cleared}, "before": {"board_id": board_id}},
        )
        db.commit()
    return MapClearStyleOut(cleared=cleared)
