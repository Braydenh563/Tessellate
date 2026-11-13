"""A board's items: the node, sketch and object routes, and the save-many and delete paths.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch
from tessellate.repo import documents as documents_repo
from tessellate.core import deps, events
from tessellate.core.deps import get_session
from tessellate.api import wb_binds
from sqlalchemy import select
from tessellate.api.wb_model import WhiteboardNodeBase, WhiteboardNodeOut, WhiteboardObjectBase, WhiteboardObjectOut, WhiteboardSketchIn, WhiteboardSketchOut, _object_to_out, _require_object_data
from tessellate.core.events import DELETED as _DELETED, node_state as _node_state, object_state as _object_state, sketch_state as _sketch_state
from tessellate.api.wb_board import _board_filter, _forget_links_to, _on_current_layer, _require_board, _require_entry

router = APIRouter()


def _apply_comments(node: WhiteboardNode, node_in: WhiteboardNodeBase) -> None:
    """A card's thread (decision 17), written only when the body names it: a
    PUT that leaves it out keeps what is stored, and an empty list is none."""
    if "comments" in node_in.model_fields_set:
        node.comments = [c.model_dump() for c in node_in.comments or []] or None


@router.post("/nodes", response_model=WhiteboardNodeOut)
@events.writes("whiteboard_node", "placed")
def create_node(
    node_in: WhiteboardNodeBase, db: Session = Depends(get_session)
) -> WhiteboardNode:
    _require_entry(db, node_in.entry_id)
    _require_board(db, node_in.board_id)
    # One card per note per board. Dropping the same note on a board twice is
    # a move, not a duplicate, the alternative is two cards stacked exactly
    # on top of each other, which reads as one card that won't drag properly.
    existing = db.scalar(
        select(WhiteboardNode).where(
            WhiteboardNode.entry_id == node_in.entry_id,
            _board_filter(WhiteboardNode, node_in.board_id),
        )
    )
    node = existing or WhiteboardNode(
        entry_id=node_in.entry_id, board_id=node_in.board_id
    )
    node.x, node.y, node.z = node_in.x, node_in.y, node_in.z
    node.width, node.height, node.group_id = node_in.width, node_in.height, node_in.group_id
    node.rotation = node_in.rotation
    node.locked = node_in.locked
    node.hidden = node_in.hidden
    _apply_comments(node, node_in)
    if existing is None:
        db.add(node)
        db.flush()  # so the event can name the card's id
    # "placed" rather than "created": dropping the same note on the same board
    # twice moves the card that is already there (see above), so one verb has
    # to be honest about both, and where the card ended up is the fact worth
    # keeping either way.
    events.record(
        db,
        "placed",
        "whiteboard_node",
        node.id,
        f"note {node.entry_id} on board {node.board_id}",
        payload={"after": _node_state(node), "existing": existing is not None},
    )
    db.commit()
    db.refresh(node)
    return node


@router.put("/nodes/{node_id}", response_model=WhiteboardNodeOut)
@events.writes("whiteboard_node", "edited")
def update_node(
    node_id: int, node_in: WhiteboardNodeBase, db: Session = Depends(get_session)
) -> WhiteboardNode:
    node = deps.get_or_404(db, WhiteboardNode, node_id, "That node could not be found.")
    _require_entry(db, node_in.entry_id)
    _require_board(db, node_in.board_id)
    _save_node(db, node, node_in)
    db.commit()
    wb_binds.apply_card_binding(db, node)
    db.refresh(node)
    return node


def _save_node(db: Session, node: WhiteboardNode, node_in: WhiteboardNodeBase) -> None:
    """What `PUT /nodes/{id}` writes, shared with `save-many`."""
    before = _node_state(node)
    node.entry_id = node_in.entry_id
    # `board_id` was read from the body and then never assigned, so moving a
    # card between boards returned 200 and changed nothing.
    node.board_id = node_in.board_id
    node.x, node.y, node.z = node_in.x, node_in.y, node_in.z
    node.width, node.height, node.group_id = node_in.width, node_in.height, node_in.group_id
    node.rotation = node_in.rotation
    node.locked = node_in.locked
    node.hidden = node_in.hidden
    _apply_comments(node, node_in)
    events.record(
        db,
        "edited",
        "whiteboard_node",
        node.id,
        f"card on board {node.board_id}",
        payload={"after": _node_state(node), "before": before},
    )


@router.delete("/nodes/{node_id}")
@events.writes("whiteboard_node", "deleted")
def delete_node(node_id: int, db: Session = Depends(get_session)) -> dict:
    # 404 rather than a cheerful "ok": deleting something that isn't there
    # is how a client finds out its board is stale, and swallowing it left
    # ghost cards on screen until a reload.
    node = deps.get_or_404(db, WhiteboardNode, node_id, "That node could not be found.")
    events.record(
        db,
        "deleted",
        "whiteboard_node",
        node.id,
        f"card off board {node.board_id}",
        payload={"before": _node_state(node), "after": dict(_DELETED)},
    )
    _forget_links_to(db, node.board_id, "node", node.id)
    db.delete(node)
    db.commit()
    return {"status": "ok"}


@router.post("/sketches", response_model=WhiteboardSketchOut)
@events.writes("whiteboard_sketch", "created")
def create_sketch(
    sketch_in: WhiteboardSketchIn, db: Session = Depends(get_session)
) -> WhiteboardSketch:
    _require_board(db, sketch_in.board_id)
    sketch = WhiteboardSketch(**sketch_in.model_dump())
    try:
        parsed = json.loads(sketch.data)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        layered = _on_current_layer(db, sketch_in.board_id, parsed)
        if layered is not parsed:
            sketch.data = json.dumps(layered)
    db.add(sketch)
    db.flush()  # so the event can name the sketch's id
    events.record(
        db,
        "created",
        "whiteboard_sketch",
        sketch.id,
        f"drawing on board {sketch.board_id}",
        payload={"after": _sketch_state(sketch)},
    )
    db.commit()
    db.refresh(sketch)
    return sketch


@router.put("/sketches/{sketch_id}", response_model=WhiteboardSketchOut)
@events.writes("whiteboard_sketch", "edited")
def update_sketch(
    sketch_id: int, sketch_in: WhiteboardSketchIn, db: Session = Depends(get_session)
) -> WhiteboardSketch:
    sketch = deps.get_or_404(db, WhiteboardSketch, sketch_id, "That sketch could not be found.")
    _require_board(db, sketch_in.board_id)
    _save_sketch(db, sketch, sketch_in)
    db.commit()
    db.refresh(sketch)
    return sketch


def _save_sketch(db: Session, sketch: WhiteboardSketch, sketch_in: WhiteboardSketchIn) -> None:
    """What `PUT /sketches/{id}` writes, shared with `save-many`."""
    before = _sketch_state(sketch)
    sketch.data = sketch_in.data
    sketch.board_id = sketch_in.board_id
    sketch.x, sketch.y, sketch.z = sketch_in.x, sketch_in.y, sketch_in.z
    sketch.group_id = sketch_in.group_id
    events.record(
        db,
        "edited",
        "whiteboard_sketch",
        sketch.id,
        f"drawing on board {sketch.board_id}",
        payload={"after": _sketch_state(sketch), "before": before},
    )


@router.delete("/sketches/{sketch_id}")
@events.writes("whiteboard_sketch", "deleted")
def delete_sketch(sketch_id: int, db: Session = Depends(get_session)) -> dict:
    sketch = deps.get_or_404(db, WhiteboardSketch, sketch_id, "That sketch could not be found.")
    events.record(
        db,
        "deleted",
        "whiteboard_sketch",
        sketch.id,
        f"drawing off board {sketch.board_id}",
        payload={"before": _sketch_state(sketch), "after": dict(_DELETED)},
    )
    _forget_links_to(db, sketch.board_id, "sketch", sketch.id)
    db.delete(sketch)
    db.commit()
    return {"status": "ok"}


# --- objects: images and text boxes, neither tied to a note -----------------
#
# Asked for directly: "images can also be attached by copy and pasting into
# the whiteboard as well though they wouldn't be shown in a note and would
# only be accessible from the library and the whiteboard", and separately,
# "I want the whiteboard to basically be like OneNote and Microsoft
# Whiteboard", which needs a real text box. A card always wraps an existing
# note; a sketch is a path, not a placeable rectangle. Neither fits an image
# or a text box, hence a third kind of thing on the canvas.


def _require_diagram_row(db: Session, body: WhiteboardObjectBase) -> None:
    """A link to a row that is gone is fine (the board draws its snapshot); one to a row that is not a diagram is not."""
    row_id = body.data.diagram_id
    if row_id is None:
        return
    if body.kind != "diagram":
        raise HTTPException(status_code=422, detail="Only a diagram can point at a Library diagram.")
    doc = documents_repo.find(db, row_id)
    if doc is not None and doc.file_type != "mmd":
        raise HTTPException(status_code=422, detail="That is not a diagram in the Library.")


@router.post("/objects", response_model=WhiteboardObjectOut, status_code=201)
@events.writes("whiteboard_object", "created")
def create_object(
    body: WhiteboardObjectBase, db: Session = Depends(get_session)
) -> WhiteboardObjectOut:
    _require_board(db, body.board_id)
    _require_object_data(body)
    _require_diagram_row(db, body)
    obj = WhiteboardObject(
        kind=body.kind,
        data=json.dumps(_on_current_layer(db, body.board_id, body.data.model_dump(mode="json", exclude_none=True)), separators=(",", ":")),
        board_id=body.board_id,
        x=body.x,
        y=body.y,
        z=body.z,
        width=body.width,
        height=body.height,
        rotation=body.rotation,
        group_id=body.group_id,
    )
    db.add(obj)
    db.flush()  # so the event can name the object's id
    events.record(
        db,
        "created",
        "whiteboard_object",
        obj.id,
        f"{obj.kind} on board {obj.board_id}",
        payload={"after": _object_state(obj)},
    )
    db.commit()
    db.refresh(obj)
    if obj.kind == "image":
        # Placing an image object on the board is itself the commit, a
        # whiteboard has no separate staging/save step the way a note or
        # chat draft does, so this fires immediately (core/media_process.py's
        # own docstring covers the other three commit points).
        from tessellate.core import media_process

        media_process.process_referenced_uploads(
            db, deps.get_config().data_dir / "media", obj.data
        )
    return _object_to_out(obj)


@router.put("/objects/{object_id}", response_model=WhiteboardObjectOut)
@events.writes("whiteboard_object", "edited")
def update_object(
    object_id: int, body: WhiteboardObjectBase, db: Session = Depends(get_session)
) -> WhiteboardObjectOut:
    obj = deps.get_or_404(db, WhiteboardObject, object_id, "That item could not be found.")
    _require_board(db, body.board_id)
    _require_object_data(body)
    _require_diagram_row(db, body)
    _save_object(db, obj, body)
    db.commit()
    db.refresh(obj)
    return _object_to_out(obj)


def _save_object(db: Session, obj: WhiteboardObject, body: WhiteboardObjectBase) -> None:
    """What `PUT /objects/{id}` writes, shared with `save-many`."""
    # The kind an object was created as doesn't change: an image resized or
    # moved is still an image; nothing in the UI offers "turn this into a
    # text box", so treating a mismatched kind here as a client bug rather
    # than silently reinterpreting the row is the safer failure.
    if body.kind != obj.kind:
        raise HTTPException(status_code=422, detail="You can't change what kind of item that is.")
    before = _object_state(obj)
    obj.data = body.data.model_dump_json(exclude_none=True)
    obj.board_id = body.board_id
    obj.x, obj.y, obj.z = body.x, body.y, body.z
    obj.width, obj.height = body.width, body.height
    obj.rotation = body.rotation
    obj.group_id = body.group_id
    events.record(
        db,
        "edited",
        "whiteboard_object",
        obj.id,
        f"{obj.kind} on board {obj.board_id}",
        payload={"after": _object_state(obj), "before": before},
    )


class SaveManyNode(WhiteboardNodeBase):
    id: int


class SaveManySketch(WhiteboardSketchIn):
    id: int


class SaveManyObject(WhiteboardObjectBase):
    id: int


class ItemsSaveMany(BaseModel):
    """Every item a gesture moved, each as its own `PUT` body plus its id."""

    nodes: list[SaveManyNode] = Field(default_factory=list, max_length=5000)
    sketches: list[SaveManySketch] = Field(default_factory=list, max_length=5000)
    objects: list[SaveManyObject] = Field(default_factory=list, max_length=5000)


def _rows_by_id(db: Session, model, ids: list[int], noun: str) -> dict[int, object]:
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Each item is saved once per batch.")
    rows = {row.id: row for row in db.scalars(select(model).where(model.id.in_(ids)))} if ids else {}
    if len(rows) != len(ids):
        raise HTTPException(status_code=404, detail=f"That {noun} could not be found.")
    return rows


@router.put("/items/save-many")
@events.writes("whiteboard_object", "edited")
def save_items(body: ItemsSaveMany, db: Session = Depends(get_session)) -> dict:
    """Save a whole selection's move in one request and one transaction.

    **Why this exists** (audit 1031 BD2: Ctrl+A on 362 items and two arrow
    presses sent 167 `PUT`s, three long tasks of 189 to 274 ms). A nudge, a
    multi-drag, a turn, a resize and an undo of any of them each wrote one
    request per item, each its own transaction, and a half-saved selection
    for as long as they took. This takes the same bodies the three `PUT`s take
    and applies them through the same helpers; the batch is all or nothing,
    every id and board and note checked before anything is written, and
    whatever it records folds into the one event `events.writes` opens.
    """
    nodes = _rows_by_id(db, WhiteboardNode, [n.id for n in body.nodes], "node")
    sketches = _rows_by_id(db, WhiteboardSketch, [n.id for n in body.sketches], "sketch")
    objects = _rows_by_id(db, WhiteboardObject, [n.id for n in body.objects], "item")
    for board_id in {item.board_id for item in (*body.nodes, *body.sketches, *body.objects)}:
        _require_board(db, board_id)
    for entry_id in {n.entry_id for n in body.nodes}:
        _require_entry(db, entry_id)
    for item in body.objects:
        _require_object_data(item)
        _require_diagram_row(db, item)
    for item in body.nodes:
        _save_node(db, nodes[item.id], item)
    for item in body.sketches:
        _save_sketch(db, sketches[item.id], item)
    for item in body.objects:
        _save_object(db, objects[item.id], item)
    db.commit()
    for node in nodes.values():
        wb_binds.apply_card_binding(db, node)
    return {"saved": len(nodes) + len(sketches) + len(objects)}


@router.delete("/objects/{object_id}")
@events.writes("whiteboard_object", "deleted")
def delete_object(object_id: int, db: Session = Depends(get_session)) -> dict:
    """Delete an object: and, on a map, everything hanging off it.

    **Coggle's rule, chosen deliberately over re-parenting** (MINDMAP_PLAN.md
    §5.4). The alternative, promoting a deleted node's children to its
    parent, reads as the gentler option and is worse: a branch you meant to
    remove reappears as loose children under a node that never had them, and
    there is no single action that puts it back. Deleting the subtree is one
    action, so it can be undone as one, which is why the whole subtree comes
    back in the response, rows and positions included, rather than a count.

    An ordinary object has no children, so this is exactly what it always
    was for a text box or an image.
    """
    obj = deps.get_or_404(db, WhiteboardObject, object_id, "That item could not be found.")
    doomed = _subtree(db, obj)
    deleted = [_object_to_out(row).model_dump() for row in doomed]
    # One event with the id list, the same shape a purge of notes records
    # (`manager_purge.purge_entries`): deleting a branch is one action a person took
    # and has to be undoable as one, so it is one event holding the state of
    # every row that went, not one event per row.
    events.record(
        db,
        "deleted",
        "whiteboard_object",
        obj.id,
        f"{obj.kind} on board {obj.board_id}"
        + (f" with {len(doomed) - 1} under it" if len(doomed) > 1 else ""),
        payload={
            "before": _object_state(obj),
            "after": dict(_DELETED),
            "ids": [row.id for row in doomed],
            "subtree": [_object_state(row) for row in doomed],
        },
    )
    #: The cross-links that went with them, as sketch rows, so Undo can draw
    #: them again between the restored topics (a link to a topic outside the
    #: branch keeps its far end, which still exists). Empty for a text box.
    links: list[dict] = []
    for row in doomed:
        _delete_one_object(db, row, links)
    db.commit()
    return {"status": "ok", "deleted": deleted, "links": links}


def _subtree(db: Session, root: WhiteboardObject) -> list[WhiteboardObject]:
    """`root` and every map node under it, deepest last.

    Breadth-first with a seen-set rather than recursion, because `parent_id`
    is a plain integer with no database-level constraint behind it (see the
    column's own comment): a cycle written by a bad client, or by a bug in
    something that has not been written yet, must end this walk rather than
    the process. Scoped to `root`'s own board for the same reason every other
    write here is: a child claiming a parent on another board is not part of
    this tree.
    """
    found = [root]
    seen = {root.id}
    frontier = [root.id]
    while frontier:
        children = db.scalars(
            select(WhiteboardObject).where(
                WhiteboardObject.parent_id.in_(frontier),
                _board_filter(WhiteboardObject, root.board_id),
            )
        ).all()
        frontier = []
        for child in children:
            if child.id in seen:
                continue
            seen.add(child.id)
            found.append(child)
            frontier.append(child.id)
    return found


def _delete_one_object(
    db: Session, obj: WhiteboardObject, links: list[dict] | None = None
) -> None:
    """The per-row half of `delete_object`: forget its links, remove the row.
    Does not commit: a subtree is one delete, so it is one transaction.

    **An image's file is kept** (INBOX 537): Undo re-makes the object from its
    row, and with the file unlinked it came back as a broken picture. The
    orphaned-media cleanup (`core.media_gc`, which reads every board object's
    data) reclaims it once nothing points at it; a purge still removes it."""
    _forget_links_to(db, obj.board_id, "object", obj.id, links)
    db.delete(obj)
