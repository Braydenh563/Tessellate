"""A map's tree: node kinds, references, styling and the tree built from a board's objects.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json

from pydantic import BaseModel
from tessellate.core.database import Entry, WhiteboardObject, WhiteboardSketch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from tessellate.api.wb_model import MAP_REFERENCE_KINDS, MAP_TOPIC_KIND
from tessellate.api.wb_board import _board_filter, _require_entry

# --- maps: the same board, with a tree on it --------------------------------
#
# MINDMAP_PLAN.md §4 chose option B, a mindmap is a board with `type: "map"`,
# not a second entity with its own tables. Everything below therefore reads
# and writes the rows that already exist (`WhiteboardObject`, and link
# sketches for cross-branch connections); the only genuinely new endpoints are
# the ones that would otherwise force a client to invent a tree out of a flat
# list, and to invent coordinates for it.


#: How far a map's own tree walks will go before deciding the tree is not
#: one. `parent_id` has no database constraint behind it (see the column's
#: comment), so a cycle is possible in principle; every walk here is
#: iterative and seen-set guarded, and this is the second belt, a map 200
#: levels deep is a bug, not a map.
MAX_MAP_DEPTH = 200

#: Where a node lands when the caller does not say. Mirrored from
#: `ai/tools/whiteboard.py`'s `_DIAGRAM_ROW`/`_DIAGRAM_COL`, which are
#: themselves mirrored from the whiteboard's own `wbArrangeMindMap`, so a
#: node added by the AI, by an import, and by a person's own Tab key all land
#: on the same spacing convention instead of three different ones.
MAP_ROW = 170.0
MAP_COL = 320.0

#: An imported outline's ceiling, in characters and in nodes. An import is
#: the one door in this app that takes a document written somewhere else, so
#: it is the one that needs a size the parser cannot be argued out of.
MAX_IMPORT_CHARS = 400_000
MAX_IMPORT_NODES = 2_000

#: How deep an imported outline may nest. Deeper than any real map, shallow
#: enough that a file of nothing but indentation cannot build a stack.
MAX_IMPORT_DEPTH = 40


def _map_kind_ok(kind: str) -> None:
    if kind != MAP_TOPIC_KIND and kind not in MAP_REFERENCE_KINDS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Pick one of these node kinds: "
                + ", ".join(sorted({MAP_TOPIC_KIND} | MAP_REFERENCE_KINDS))
                + "."
            ),
        )


def _require_reference(db: Session, kind: str, ref_id: int | None) -> None:
    """A reference node has to point at something that exists.

    The same rule, and the same reason, as `_require_entry` at the top of
    this file: an unvalidated id is a node that stores fine, draws as an
    empty box, and cannot be identified or removed from the UI afterwards,
    because the thing you would click is the item that isn't there.

    Privacy is deliberately *not* checked here, and that is not an oversight.
    Putting your own private note on your own map is the same act as dropping
    it on a board (`create_node` does not refuse it either), the app is
    behind the lock either way. The refusal that matters is the AI's, and it
    lives where the AI is: `_require_note` in `ai/tools/_common.py`, which
    every map tool in `ai/tools/whiteboard.py` calls before it writes, and
    `read_mindmap`, which will not read a private note's text back out.
    """
    if ref_id is None:
        raise HTTPException(status_code=422, detail=f"A {kind} node needs to point at an existing {kind}.")
    if kind == "note":
        _require_entry(db, ref_id)
        return
    label = {"document": "document", "file": "file", "link": "bookmark"}[kind]
    if _referenced(db, kind, ref_id) is None:
        raise HTTPException(status_code=404, detail=f"That {label} could not be found.")


def _referenced(db: Session, kind: str, ref_id: int):
    """The document, file or bookmark a reference node points at, or None."""
    from tessellate.core.database import Attachment
    from tessellate.repo import bookmarks, documents

    if kind == "link":
        return bookmarks.find(db, ref_id)
    if kind == "document":
        return documents.find(db, ref_id)
    return db.get(Attachment, ref_id)


def _reference_label(db: Session, kind: str, ref_id: int | None, fallback: str) -> str:
    """What a reference node is *called*, resolved from the thing it points
    at rather than copied into the map when the node was made.

    Copied text goes stale the moment the note is renamed, and a map full of
    names that no longer match the notes is worse than one with no names at
    all. A private note contributes the fact of the reference and nothing
    else: the same rule the board preview and the Connections block follow.
    """
    if ref_id is None:
        return fallback
    if kind == "note":
        return _note_reference_label(db, ref_id, fallback)
    return _other_reference_label(db, kind, ref_id) or fallback


def _note_reference_label(db: Session, ref_id: int, fallback: str) -> str:
    """A note reference's name: its title, "Private note" for a private one."""
    from tessellate.entry import manager_text

    entry = db.get(Entry, ref_id)
    if entry is None or entry.is_deleted:
        return fallback or "(note missing)"
    if entry.is_private:
        return "Private note"
    text = manager_text.readable_content(entry)
    return manager_text.extract_title(text) or text.strip().split("\n")[0][:80] or fallback


def _other_reference_label(db: Session, kind: str, ref_id: int) -> str:
    """A document, file or link reference's name, "" when it has none."""
    if kind not in ("document", "file", "link"):
        return ""
    row = _referenced(db, kind, ref_id)
    if row is None:
        return ""
    if kind == "document":
        return row.title
    if kind == "file":
        return row.filename
    return row.title or row.url


def _reference_facets(db: Session, kind: str, ref_id: int | None) -> dict:
    """What the *notebook* knows about the note behind a node: its category
    and when it was last edited.

    MINDMAP_PLAN.md §5 item 19, and the sentence in it that is the reason
    this is here at all: colouring a map by category or by age is "the thing
    a general mindmapper cannot do", because a general mindmapper has only
    the tree. Resolved on the server for the same reason the label is
    (`_reference_label`): a copy on the client goes stale the moment a note is
    refiled, and the client has no way to know it did.

    Only for `note` nodes. A document, file or link has no filing of its own
    in this notebook, and a private note contributes nothing at all, which is
    the same boundary its title is behind one function above.
    """
    from tessellate.repo import categories as categories_repo

    if kind != "note" or ref_id is None:
        return {}
    entry = db.get(Entry, ref_id)
    if entry is None or entry.is_deleted or entry.is_private:
        return {}
    return {
        "ref_category": categories_repo.name_of(db, entry.category_id) or "Unfiled",
        # Naive UTC, as every timestamp in this database is: the client reads
        # it as UTC explicitly rather than letting the browser guess a zone.
        "ref_updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def _object_data(obj: WhiteboardObject) -> dict:
    """An object's JSON blob, never raising. A row edited by hand, or written
    by an older version, must not take a whole board's tree down with it."""
    try:
        parsed = json.loads(obj.data or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


#: What the node edit strip and the two radials write on a node, beyond its
#: text and its colour (MINDMAP_PLAN.md §12.1 items 2 to 4). Named in one
#: place because three things have to agree about them: the tree endpoint
#: hands them to the canvas, the two XML exports carry them out, and the two
#: XML imports read them back. The seven that arrived with the strip and the
#: rings were invisible to the exports for exactly as long as this list did
#: not exist, and §12.0 says a feature that cannot round-trip is not shipped.
#: `color` is not here because a node dict has carried it as a key of its own
#: since long before the strip existed; the exports read both.
MAP_STYLE_FIELDS = (
    "bold",
    "italic",
    "font_size",
    "align",
    "shape",
    "core",
    "spine",
    "fill",
    "effect",
    "icon",
    "link",
    "edge_label",
    "edge_style",
    "edge_dashed",
    "edge_width",
    "edge_arrow",
    "edge_bend",
    "edge_slide",
    "edge_from",
    "edge_to",
    "image",
    "task",
    "note",
    "boundary",
    "boundary_label",
    "summary",
    "summary_span",
    "branch_layout",
    "callout",
    "labels",
    "stamps",
    "priority",
    "progress",
    "flag",
    "markers",
    "due",
    "due_time",
    "start",
    "recording",
)


def _map_node_style(data: dict) -> dict:
    """The style fields a node actually carries, in a fixed order, with the
    unset ones left out: an export writes an attribute only for what somebody
    chose, so a plain map exports as the same file it did before any of this
    existed."""
    style: dict = {}
    for field in MAP_STYLE_FIELDS:
        value = data.get(field)
        if value is None or value is False or value == "":
            continue
        style[field] = value
    return style


def _map_node_dict(db: Session, obj: WhiteboardObject) -> dict:
    """One node, flat: `_build_tree` fills in `children`."""
    data = _object_data(obj)
    content = str(data.get("content") or "")
    raw_ref = data.get("ref_id")
    ref_id = int(raw_ref) if isinstance(raw_ref, int) else None
    text = (
        content
        if obj.kind in (MAP_TOPIC_KIND, "text")
        else _reference_label(db, obj.kind, ref_id, content)
    )
    node = {
        "id": obj.id,
        "kind": obj.kind,
        "text": text,
        "ref_id": ref_id,
        "x": obj.x,
        "y": obj.y,
        "color": data.get("color"),
        "collapsed": bool(data.get("collapsed")),
        "pinned": bool(data.get("pinned")),
        "style": _map_node_style(data),
        "children": [],
    }
    node.update(_reference_facets(db, obj.kind, ref_id))
    return node


def _build_tree(db: Session, objects: list[WhiteboardObject]) -> list[dict]:
    """The board's objects as nested roots.

    **A node whose parent is not on this board is a root**, and that is the
    reason this is not a two-line recursion down from `parent_id IS NULL`.
    `parent_id` is a plain integer (see the column's comment), so a pointer
    can go stale: and a walk that starts only from NULL silently drops every
    node under a broken pointer. The board still holds them; the map just
    stops showing them, which is the worst way to lose something.
    """
    nodes = {obj.id: _map_node_dict(db, obj) for obj in objects}
    roots: list[dict] = []
    for obj in objects:
        parent = nodes.get(obj.parent_id) if obj.parent_id is not None else None
        if parent is None:
            roots.append(nodes[obj.id])
        else:
            parent["children"].append(nodes[obj.id])

    # A ring (a → b → a) leaves both nodes attached to each other and neither
    # in `roots`, so the outline would simply not mention them. They are
    # still on the board, so the lowest id of each unreachable ring is
    # re-rooted and the rest follows it, rather than pretending the rows are
    # not there.
    reachable: set[int] = set()

    def claim(start: dict) -> None:
        frontier = [start]
        while frontier:
            node = frontier.pop()
            if node["id"] in reachable:
                continue
            reachable.add(node["id"])
            frontier.extend(node["children"])

    for root in roots:
        claim(root)
    for obj in objects:
        if obj.id not in reachable:
            roots.append(nodes[obj.id])
            claim(nodes[obj.id])
    return roots


def _map_objects(db: Session, board_id: int | None) -> list[WhiteboardObject]:
    """Every object on a board, oldest first, creation order, which is the
    order a person built the map in and the only one an outline can be read
    in without surprises. Position decides where a node is *drawn*; it does
    not decide what the map says.

    **Unless a topic was moved among its siblings** (INBOX 445): then its
    `data.order` is its key instead of its id, which is what `wbMapIndex`
    sorts by on the canvas, so the tree, every export and the agent's outline
    read the siblings in the order the person put them. Only siblings are
    ever compared, because `_build_tree` appends children in this list's
    order."""
    objects = list(
        db.scalars(
            select(WhiteboardObject)
            .where(_board_filter(WhiteboardObject, board_id))
            .order_by(WhiteboardObject.id)
        )
    )
    return sorted(objects, key=_sibling_key)


def _sibling_key(obj: WhiteboardObject) -> tuple[float, int]:
    try:
        order = json.loads(obj.data or "{}").get("order")
    except (TypeError, ValueError, AttributeError):
        order = None
    is_number = isinstance(order, (int, float)) and not isinstance(order, bool)
    return (float(order) if is_number else float(obj.id), obj.id)


def _cross_links(db: Session, board_id: int | None, node_ids: set[int]) -> list[dict]:
    """The non-tree edges: link sketches whose two ends are both map nodes.

    Kept as link sketches rather than given a table of their own, because
    that is what a link between two things on a board already is, the
    frontend draws them and `_forget_links_to` cleans them up, and a second
    representation would need both written again.
    """
    out: list[dict] = []
    for sketch in db.scalars(
        select(WhiteboardSketch)
        .where(_board_filter(WhiteboardSketch, board_id))
        .order_by(WhiteboardSketch.id)
    ):
        try:
            data = json.loads(sketch.data or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or not str(data.get("type", "")).startswith("link-"):
            continue
        source_kind = data.get("sourceKind") or "node"
        target_kind = data.get("targetKind") or "node"
        if source_kind != "object" or target_kind != "object":
            continue
        source, target = data.get("sourceId"), data.get("targetId")
        if source in node_ids and target in node_ids:
            out.append(
                {"from_id": source, "to_id": target, "label": str(data.get("label") or "")}
            )
    return out


class MapTreeOut(BaseModel):
    board_id: int
    title: str
    type: str
    layout: str
    #: Nested `{id, kind, text, ref_id, x, y, color, collapsed, pinned,
    #: style, children}`, where `style` holds whichever of
    #: `MAP_STYLE_FIELDS` the node actually carries. Typed as `list[dict]`
    #: rather than as a self-referencing
    #: model: OpenAPI's handling of recursive schemas buys nothing here, and
    #: the shape is documented above and asserted in `tests/test_mindmap.py`.
    roots: list[dict]
    cross_links: list[dict]
    #: The map's own theme, `MAP_THEME_FIELDS` filtered to what this map set
    #: (MINDMAP_PLAN.md §13e). Empty for every map that has never been
    #: themed, which is every map that existed before this. It rides on the
    #: tree rather than on `BoardOut` because the tree is the one call the
    #: canvas makes before it draws, and a theme that arrived one request
    #: later would paint the map twice.
    theme: dict = {}
    #: Whether the map numbers its branches (decision 17), for the same
    #: reason the theme rides here: the canvas draws the numbers on its first
    #: paint or it draws the map twice.
    numbered: bool = False
    #: The branch colours this map draws, resolved from the theme's `palette`
    #: (decision 8): the canvas reads these rather than keeping its own list,
    #: so it and the thumbnail are drawn from one copy.
    palette: list[str] = []
