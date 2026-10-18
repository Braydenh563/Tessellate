"""AI tool handlers for the whiteboard: read/search/add-card/add-link and
the server-side `generate_diagram` layout engine.

Split out of `ai/tools.py`'s "documents, past chats, and skills" section
(ROADMAP.md §0/§4): the whiteboard quarter of it, self-contained apart
from the shared helpers in `_common.py`.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import deps, events
from tessellate.core.database import Entry
from tessellate.entry import manager
from tessellate.entry.properties import strip as strip_properties

from ._common import DEFAULT_LIST_LIMIT, PREVIEW_CHARS, ToolError, _clip, _limit_arg, _require_note, mark_outside

def _whiteboard_board_filter(model, board_id: int | None):
    """Same rule `routes_whiteboard.py`'s own `_board_filter` uses: `== None`
    renders as SQL `= NULL`, never true for any row, so the default board
    would read as empty however much was actually on it."""
    return model.board_id.is_(None) if board_id is None else model.board_id == board_id


# --- the event log for the AI's own board writes (Brief 7, item 4) ----------
#
# The whiteboard routes record one event per write with whole field values,
# which is what lets `events.replay` rebuild a card, a sketch or a map node
# from its own events. These tools recorded a detail and no payload, so a
# board the model built was in the log and did not replay, while the same
# board built by hand did: the AI is the writer whose work a person is most
# likely to want to read back or put back, so it was the wrong half to leave
# out.
#
# The four helpers below *are* the write, rather than a `record` call each
# tool site has to remember: each is wrapped in `@events.writes`, so a tool
# that grows a second write inside it folds into one event instead of
# quietly recording twice, and every payload is built by the same
# `events.*_state` the routes use, so one entity has one idea of its state
# whoever wrote it.
#
# They are helpers rather than decorators on the tool handlers because two of
# the handlers are batches: `generate_diagram` places up to sixty cards and
# their links, and `create_mindmap` makes a board and its root. Decorating a
# function that loops over several writes folds the whole batch into a single
# event (`events.writes`' own docstring says so), which is exactly the shape
# that lost the replay here in the first place. A board's replayable entity
# is the item, not the board (Brief 7 decision 4), so a batch records one
# event per item.


@events.writes("whiteboard_node", "placed")
def _place_card(
    session: Session,
    entry: Entry,
    board_id: int | None,
    x: float,
    y: float,
    existing=None,
):
    """Put one note on one board at one position, and say so.

    "placed" rather than "created", the verb the route uses and for its
    reason: the same note dropped on the same board twice moves the card that
    is already there, so one verb has to be honest about both.
    """
    from tessellate.core.database import WhiteboardNode

    node = existing if existing is not None else WhiteboardNode(
        board_id=board_id, entry_id=entry.id, z=1
    )
    node.x, node.y = float(x), float(y)
    if existing is None:
        session.add(node)
    session.flush()  # so the event can name the card's id
    events.record(
        session,
        "placed",
        "whiteboard_node",
        node.id,
        f"note {entry.id} on board {board_id}",
        payload={"after": events.node_state(node), "existing": existing is not None},
    )
    return node


@events.writes("whiteboard_sketch", "created")
def _draw_link(session: Session, board_id: int | None, data: dict):
    """A link between two things on a board, which is a sketch row like any
    other drawing: the same entity type the route records, so a link the AI
    drew and one a person dragged replay through the same events."""
    from tessellate.core.database import WhiteboardSketch

    sketch = WhiteboardSketch(board_id=board_id, data=json.dumps(data), x=0, y=0, z=1)
    session.add(sketch)
    session.flush()  # so the event can name the link's id
    events.record(
        session,
        "created",
        "whiteboard_sketch",
        sketch.id,
        f"link on board {board_id}",
        payload={"after": events.sketch_state(sketch)},
    )
    return sketch


@events.writes("whiteboard_object", "created")
def _place_object(session: Session, obj):
    """One map node or text box, already built by the caller, recorded."""
    session.add(obj)
    session.flush()  # so the event can name the node's id
    events.record(
        session,
        "created",
        "whiteboard_object",
        obj.id,
        f"{obj.kind} on map {obj.board_id}",
        payload={"after": events.object_state(obj)},
    )
    return obj


@events.writes("board", "created")
def _new_board(session: Session, entry: Entry, name: str, board_type: str, layout: str):
    """A new board, built here rather than through `manager.create_entry`.

    Same reason the `POST /boards` route records its own event: the note is
    constructed directly, so without this line a board the AI made would be
    the one thing in the app that appears with nothing anywhere saying it
    had.
    """
    session.add(entry)
    session.flush()  # so the event, and the nodes, can name the board's id
    events.record(
        session,
        "created",
        "board",
        entry.id,
        name[:80],
        payload={"after": events.board_state(name, board_type, layout)},
    )
    return entry


def _inside(item, frame) -> bool:
    """Whether a card's corner lies in a frame's region (decision 14): the
    board moves what lies wholly inside, and a card's stored corner is the
    part of it the server knows."""
    x, y = item.x or 0, item.y or 0
    return frame.x <= x <= frame.x + (frame.width or 0) and frame.y <= y <= frame.y + (frame.height or 0)


def board_outline(title: str, cards: list[dict], frames: list[dict], text_boxes: list[dict], shapes: list[dict], links: list[dict]) -> str:
    """A board as flat indented text: the form a small model reads best and a
    person can paste anywhere (OPEN row 1379, the "outline-text export"). Cards
    sit under the frame that covers them, then the loose ones; every link is a
    line naming both ends by card id, so a later call can act on them."""
    lines = [f"Board: {title}"]
    in_frame: set[int] = set()
    by_card = {card["card_id"]: card for card in cards}

    def card_line(card: dict, indent: str) -> str:
        first = (card["preview"].strip().splitlines() or [""])[0]
        return f"{indent}- card {card['card_id']} (note {card['note_id']}): {first}"

    for frame in frames:
        lines.append(f"Frame: {frame['title'] or '(untitled)'}")
        for card_id in frame["card_ids"]:
            if card_id in by_card:
                in_frame.add(card_id)
                lines.append(card_line(by_card[card_id], "  "))
    loose = [card for card in cards if card["card_id"] not in in_frame]
    if loose:
        lines.append("Cards:" if frames else "Cards")
        lines.extend(card_line(card, "  ") for card in loose)
    lines.extend(_outline_extras(text_boxes, shapes, links))
    return "\n".join(lines)


def _outline_extras(text_boxes: list[dict], shapes: list[dict], links: list[dict]) -> list[str]:
    """The text boxes, shapes and links of a board outline, each under its heading."""
    lines: list[str] = []
    if text_boxes:
        lines.append("Text boxes")
        lines.extend(f"  - {box['text']}" for box in text_boxes)
    if shapes:
        lines.append("Shapes")
        lines.extend(f"  - {shape['shape']} {shape['shape_id']}: {shape['text']}" for shape in shapes)
    if links:
        lines.append("Links")
        lines.extend(f"  - card {link['from_card_id']} -> card {link['to_card_id']}" for link in links)
    return lines


def _read_whiteboard(session: Session, args: dict) -> dict:
    """The read half of ROADMAP item 11's AI+whiteboard integration: lets the
    agent answer "what's on my project-planning board?" without a human
    describing it first. Nothing under `ai/` mentioned the whiteboard at all
    before this: `autonomous.py`'s orphaned-card cleanup is a background
    job, not agent context.
    """
    from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch

    raw_board_id = args.get("board_id")
    board_id = int(raw_board_id) if raw_board_id not in (None, "") else None

    nodes = list(session.scalars(select(WhiteboardNode).where(_whiteboard_board_filter(WhiteboardNode, board_id))))
    sketches = list(
        session.scalars(select(WhiteboardSketch).where(_whiteboard_board_filter(WhiteboardSketch, board_id)))
    )
    objects = list(
        session.scalars(select(WhiteboardObject).where(_whiteboard_board_filter(WhiteboardObject, board_id)))
    )

    entry_ids = [n.entry_id for n in nodes]
    entries = (
        {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(entry_ids)))} if entry_ids else {}
    )

    def _card_preview(n) -> str:
        entry = entries.get(n.entry_id)
        if entry is None:
            return "(note missing)"
        # A card's note can be marked private *after* it was placed on the
        # board: `_add_whiteboard_card` refuses a private note going in via
        # `_require_note`, but that only guards the write. `entry.content` is
        # ciphertext at rest for a private note, and this tool result becomes
        # part of the agent's own context, so it needs the same refusal
        # `_require_note` gives every other read.
        if entry.is_private:
            return "(private note: not available to the AI)"
        if manager.came_from_outside(entry):
            mark_outside()  # SEC-02: a clipped or imported note's words
        return _clip(strip_properties(entry.content).lstrip(), PREVIEW_CHARS)

    cards = [
        {"card_id": n.id, "note_id": n.entry_id, "preview": _card_preview(n)}
        for n in nodes
    ]

    from .board_edit import _path_corner

    links = []
    #: The drawn shapes with words in them, by id and corner (FEAT-12): what
    #: `move_board_item`, `edit_board_item` and `delete_board_item` act on.
    #: Pen strokes without words are left out; they are many and say nothing.
    shapes = []
    for sketch in sketches:
        try:
            parsed = json.loads(sketch.data)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and str(parsed.get("type", "")).startswith("link-"):
            links.append({"from_card_id": parsed.get("sourceId"), "to_card_id": parsed.get("targetId")})
        elif isinstance(parsed, dict) and parsed.get("label") and isinstance(parsed.get("d"), str):
            x, y = _path_corner(parsed["d"])
            shapes.append({
                "shape_id": sketch.id, "shape": parsed.get("shape") or "shape",
                "text": _clip(str(parsed["label"]), PREVIEW_CHARS), "x": round(x), "y": round(y),
            })

    text_boxes = []
    frames = []
    image_count = 0
    for obj in objects:
        try:
            data = json.loads(obj.data)
        except (TypeError, ValueError):
            data = {}
        if obj.kind == "text":
            text_boxes.append({"object_id": obj.id, "text": _clip(str(data.get("content") or ""), PREVIEW_CHARS)})
        elif obj.kind == "image":
            image_count += 1
        elif obj.kind == "frame":
            #: A frame's title is how a board is divided up ("Ideas", "Done"),
            #: and the region it covers says which cards sit under it.
            frames.append({
                "object_id": obj.id,
                "title": _clip(str(data.get("content") or ""), PREVIEW_CHARS),
                "card_ids": [n.id for n in nodes if _inside(n, obj)],
            })

    board_title = "Default board"
    if board_id is not None:
        board_entry = session.get(Entry, board_id)
        # Same rule as a card's own note above: a board is itself an Entry,
        # and it can be marked private after being used as one.
        if board_entry is not None and not board_entry.is_private:
            board_title = manager.extract_title(board_entry.content) or _clip(board_entry.content, 40)

    return {
        "board_id": board_id,
        "board_title": board_title,
        "cards": cards,
        "text_boxes": text_boxes,
        "shapes": shapes,
        "frames": frames,
        "image_count": image_count,
        "links": links,
        "outline": board_outline(board_title, cards, frames, text_boxes, shapes, links),
        "label": f"ph:folders Read whiteboard board “{board_title}”",
    }


def _search_whiteboard(session: Session, args: dict) -> dict:
    """The search half of ROADMAP item 11's AI+whiteboard integration:
    "whiteboard content becomes searchable the same way notes are." Words,
    not meaning: an embedding index over text-box content needs a table, a
    backfill and a place in the embedding-refresh cycle, and nothing measured
    asks for it (data-1011 decision: not built; the notes the cards stand for
    are already searched by meaning). A keyword scan across every board's card
    previews and text boxes answers "which board did I put that on?".
    """
    from tessellate.core.database import WhiteboardNode, WhiteboardObject

    term = str(args.get("query") or "").strip().lower()
    if not term:
        raise ToolError("query is required")
    #: Every word, anywhere in the text, in any order: "budget meeting" finds a
    #: card that says "meeting about the budget". A one-word query is unchanged.
    words = term.split()

    def hit(text: str) -> bool:
        lowered = text.lower()
        return all(word in lowered for word in words)
    limit = _limit_arg(args, default=DEFAULT_LIST_LIMIT)

    matches = []
    node_rows = list(session.scalars(select(WhiteboardNode)))
    entry_ids = [n.entry_id for n in node_rows]
    entries = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(entry_ids)))} if entry_ids else {}
    for node in node_rows:
        entry = entries.get(node.entry_id)
        # Skip a card whose note is private, its `content` is ciphertext at
        # rest, so `term in entry.content.lower()` would only ever match by
        # accident, and a match on the raw column is not one this tool may
        # report back to the model regardless. Same guard as `_read_whiteboard`'s
        # `_card_preview` above.
        if entry is not None and not entry.is_private and hit(entry.content):
            if manager.came_from_outside(entry):
                mark_outside()  # SEC-02
            matches.append({
                "board_id": node.board_id,
                "card_id": node.id,
                "note_id": node.entry_id,
                "preview": _clip(strip_properties(entry.content).lstrip(), PREVIEW_CHARS),
            })

    for obj in session.scalars(select(WhiteboardObject).where(WhiteboardObject.kind == "text")):
        try:
            data = json.loads(obj.data)
        except (TypeError, ValueError):
            continue
        text = str(data.get("content") or "")
        if hit(text):
            matches.append({
                "board_id": obj.board_id,
                "object_id": obj.id,
                "text": _clip(text, PREVIEW_CHARS),
            })

    return {
        "matches": matches[:limit],
        "total_matching": len(matches),
        "label": f"ph:magnifying-glass Searched whiteboards for “{_clip(term, 30)}”",
    }


def _add_whiteboard_card(session: Session, args: dict) -> dict:
    """The write half's simplest step: place an existing note as a card on a
    board: what "AI-guided diagram generation" reduces to for one note at a
    time. Reuses `_require_note` (not a bare `session.get`) so a private note
    gets the same refusal every other tool already gives it.
    """
    from tessellate.core.database import WhiteboardNode

    entry = _require_note(session, args, "note_id")
    raw_board_id = args.get("board_id")
    board_id = int(raw_board_id) if raw_board_id not in (None, "") else None
    x = float(args["x"]) if args.get("x") is not None else 100.0
    y = float(args["y"]) if args.get("y") is not None else 100.0

    existing = session.scalar(
        select(WhiteboardNode).where(
            WhiteboardNode.entry_id == entry.id,
            _whiteboard_board_filter(WhiteboardNode, board_id),
        )
    )
    if existing is not None:
        return {
            "card_id": existing.id,
            "note_id": entry.id,
            "already_there": True,
            "label": f"ph:folders “{_clip(entry.content, 40)}” is already on that board",
        }

    node = _place_card(session, entry, board_id, x, y)
    session.commit()
    session.refresh(node)
    return {
        "card_id": node.id,
        "note_id": entry.id,
        "x": node.x,
        "y": node.y,
        "label": f"ph:folders Placed “{_clip(entry.content, 40)}” on the whiteboard",
    }


def _add_whiteboard_link(session: Session, args: dict) -> dict:
    """The other write step: connect two cards already on a board. No anchor
    picking here (that's a live-drag interaction, ROADMAP item 11), a
    generated link is a floating one, which still terminates correctly on
    each card's own border via `wbLinkEndpoints` on the client side.
    """
    from tessellate.core.database import WhiteboardNode

    source = session.get(WhiteboardNode, int(args.get("from_card_id") or 0))
    target = session.get(WhiteboardNode, int(args.get("to_card_id") or 0))
    if source is None:
        raise ToolError(f"No whiteboard card with id {args.get('from_card_id')}")
    if target is None:
        raise ToolError(f"No whiteboard card with id {args.get('to_card_id')}")
    if source.id == target.id:
        raise ToolError("Can't link a card to itself.")
    if source.board_id != target.board_id:
        raise ToolError("Both cards must be on the same board to link them.")

    data = {
        "type": "link-curved" if args.get("curved") else "link-straight",
        "sourceId": source.id,
        "targetId": target.id,
        "color": "#8899ff",
    }
    sketch = _draw_link(session, source.board_id, data)
    session.commit()
    session.refresh(sketch)
    return {
        "link_id": sketch.id,
        "from_card_id": source.id,
        "to_card_id": target.id,
        "label": "ph:link Linked the two cards",
    }


#: A runaway model asking for a diagram of hundreds of notes is a real
#: failure mode a bulk tool has to bound, the same reason every list tool
#: here clamps its own `limit`, one call shouldn't be able to flood a
#: board.
MAX_DIAGRAM_NODES = 60

#: Layout constants mirrored from the whiteboard's own client-side
#: `wbArrangeMindMap` (`WB_MINDMAP_TREE_ROW`/`_COL`/`_RADIAL_STEP` in
#: app.js) so a diagram this tool places and one arranged by hand afterward
#: read as the same spacing convention, not two different tools' opinions.
_DIAGRAM_ROW = 170.0
_DIAGRAM_COL = 320.0
_DIAGRAM_RADIAL_STEP = 260.0


def _diagram_tree_positions(root_ref: str, children_of: dict[str, list[str]], layout: str) -> dict[str, tuple[float, float]]:
    """Board (x, y) for every node reachable from `root_ref`, laid out as a
    tree (depth → column, siblings spread along a row) or radially (depth →
    ring, siblings spread around it).

    Not a port of d3.tree()'s own tidy-tree (Reingold-Tilford/Buchheim)
    algorithm: that optimises for the *tightest* non-overlapping packing,
    which this doesn't need to match exactly, only to produce. A leaf gets
    the next free row slot in visitation order; an internal node's slot is
    the mean of its children's, which is the simplest arrangement that is
    still guaranteed non-overlapping and reads as a sensible tree. Depth is
    plain BFS distance from the root.
    """
    import math

    depth: dict[str, int] = {root_ref: 0}
    queue = [root_ref]
    while queue:
        current = queue.pop(0)
        for child in children_of.get(current, []):
            if child in depth:
                # Reached via two different paths, not a simple tree.
                raise ToolError(f"'{child}' has more than one path back to the root, check parent_ref for a cycle or a duplicate.")
            depth[child] = depth[current] + 1
            queue.append(child)

    slot: dict[str, float] = {}
    next_leaf_slot = [0]

    def assign(node: str) -> float:
        kids = children_of.get(node, [])
        if not kids:
            value = float(next_leaf_slot[0])
            next_leaf_slot[0] += 1
        else:
            value = sum(assign(k) for k in kids) / len(kids)
        slot[node] = value
        return value

    assign(root_ref)

    positions: dict[str, tuple[float, float]] = {}
    if layout == "radial":
        leaf_count = max(next_leaf_slot[0], 1)
        for node, d in depth.items():
            angle = (slot[node] / leaf_count) * 2 * math.pi - math.pi / 2
            radius = d * _DIAGRAM_RADIAL_STEP
            positions[node] = (radius * math.cos(angle), radius * math.sin(angle))
    else:
        for node, d in depth.items():
            positions[node] = (d * _DIAGRAM_COL, slot[node] * _DIAGRAM_ROW)
    return positions


def _diagram_nodes(args: dict) -> dict[str, dict]:
    """The declared nodes keyed by ref, each checked to name exactly one of a
    title (a new note) or a note id (an existing one)."""
    raw_nodes = args.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ToolError("'nodes' must be a non-empty list.")
    if len(raw_nodes) > MAX_DIAGRAM_NODES:
        raise ToolError(f"That's {len(raw_nodes)} nodes: {MAX_DIAGRAM_NODES} is the most this can place in one call.")
    by_ref: dict[str, dict] = {}
    for i, raw in enumerate(raw_nodes):
        ref = str(raw.get("ref") or "").strip()
        if not ref:
            raise ToolError(f"nodes[{i}] has no 'ref', every node needs a short local id to reference as a parent.")
        if ref in by_ref:
            raise ToolError(f"'{ref}' is used as 'ref' on more than one node, refs must be unique.")
        title = str(raw.get("title") or "").strip()
        note_id = raw.get("note_id")
        if bool(title) == bool(note_id):
            raise ToolError(f"Node '{ref}' needs exactly one of 'title' (new note) or 'note_id' (existing note).")
        by_ref[ref] = {"title": title, "note_id": note_id, "parent_ref": raw.get("parent_ref") or None}
    return by_ref


def _diagram_attach(by_ref: dict[str, dict]) -> dict[str, int]:
    """The nodes that hang from a card already on the board."""
    #: A parent can be a card already on the board, written `card:<card_id>`
    #: (the ids `read_whiteboard` lists): the new nodes then grow out of it
    #: instead of starting a diagram of their own (OPEN row 1379).
    attach: dict[str, int] = {}
    for ref, node in by_ref.items():
        parent_ref = node["parent_ref"]
        if isinstance(parent_ref, str) and parent_ref.startswith("card:"):
            try:
                attach[ref] = int(parent_ref[5:])
            except ValueError as exc:
                raise ToolError(f"Node '{ref}' has parent_ref '{parent_ref}': after card: put the card's number.") from exc
    return attach


def _diagram_shape(by_ref: dict[str, dict]) -> tuple[dict[str, int], str, dict[str, list[str]]]:
    """The cards the new nodes hang from, the root, and each node's children."""
    attach = _diagram_attach(by_ref)
    roots = [ref for ref, node in by_ref.items() if not node["parent_ref"]]
    if attach and roots:
        raise ToolError("Either one node has no 'parent_ref' (a new diagram) or every top node hangs from a card:<id>, not both.")
    if not attach and len(roots) != 1:
        raise ToolError(
            "Exactly one node must have no 'parent_ref' (the diagram's root): "
            f"found {len(roots)}."
        )
    root_ref = roots[0] if roots else next(iter(attach))

    children_of: dict[str, list[str]] = {}
    for ref, node in by_ref.items():
        parent_ref = node["parent_ref"]
        if parent_ref is None:
            continue
        if ref in attach:
            children_of.setdefault(f"__card:{attach[ref]}", []).append(ref)
            continue
        if parent_ref not in by_ref:
            raise ToolError(f"Node '{ref}' has parent_ref '{parent_ref}', which isn't in this call's own nodes.")
        children_of.setdefault(parent_ref, []).append(ref)
    return attach, root_ref, children_of


def _diagram_positions(
    session: Session,
    board_id: int | None,
    by_ref: dict[str, dict],
    shape: tuple[dict[str, int], str, dict[str, list[str]]],
    layout: str,
) -> tuple[dict, dict, str]:
    """Every node's position, the board cards a diagram extends, and the
    layout actually used (extending a card is always a tree)."""
    from tessellate.core.database import WhiteboardNode

    attach, root_ref, children_of = shape
    anchors: dict[int, WhiteboardNode] = {}
    if attach:
        layout = "tree"
        positions = {}
        for card_id in dict.fromkeys(attach.values()):
            anchor = session.scalar(
                select(WhiteboardNode).where(WhiteboardNode.id == card_id, _whiteboard_board_filter(WhiteboardNode, board_id))
            )
            if anchor is None:
                raise ToolError(f"There is no card {card_id} on that board. read_whiteboard lists the card ids.")
            anchors[card_id] = anchor
            virtual = f"__card:{card_id}"
            laid = _diagram_tree_positions(virtual, children_of, "tree")
            shift = (anchor.y or 0.0) - laid[virtual][1]
            for ref, (px, py) in laid.items():
                if ref != virtual:
                    positions[ref] = ((anchor.x or 0.0) + px, py + shift)
    else:
        positions = _diagram_tree_positions(root_ref, children_of, layout)
    unreached = [ref for ref in by_ref if ref not in positions]
    if unreached:
        raise ToolError(f"Node '{unreached[0]}' cannot be reached from the root: check parent_ref for a cycle.")
    return positions, anchors, layout


def _diagram_entries(session: Session, by_ref: dict[str, dict]) -> dict[str, Entry]:
    """Resolve every ref to a real Entry, creating one for a bare title,
    reusing (and permission-checking, same as any other tool) one already
    given as note_id. Two passes on purpose: entries have to exist before
    any card/link touches them, and failing on node 40 of 60 after
    already writing 39 cards would be a worse outcome than failing before
    anything is written at all."""
    entries: dict[str, Entry] = {}
    for ref, node in by_ref.items():
        if node["note_id"] is not None:
            entries[ref] = _require_note(session, {"note_id": node["note_id"]})
        else:
            entries[ref] = manager.create_entry(
                session, node["title"], category_name=manager.UNCATEGORISED, tags=[], ai_confidence=0
            )
    for entry in entries.values():
        deps.store_quietly(session, entry)
    return entries


def _diagram_cards(session: Session, board_id: int | None, entries: dict[str, Entry], positions: dict) -> dict:
    from tessellate.core.database import WhiteboardNode

    cards = {}
    for ref, entry in entries.items():
        x, y = positions[ref]
        existing = session.scalar(
            select(WhiteboardNode).where(
                WhiteboardNode.entry_id == entry.id,
                _whiteboard_board_filter(WhiteboardNode, board_id),
            )
        )
        cards[ref] = _place_card(session, entry, board_id, x, y, existing)
    session.commit()
    for card in cards.values():
        session.refresh(card)
    return cards


def _diagram_links(session: Session, board_id: int | None, by_ref: dict[str, dict], attach: dict, anchors: dict, cards: dict) -> int:
    link_count = 0
    for ref, node in by_ref.items():
        parent_ref = node["parent_ref"]
        if parent_ref is None:
            continue
        data = {
            "type": "link-straight",
            "sourceId": anchors[attach[ref]].id if ref in attach else cards[parent_ref].id,
            "targetId": cards[ref].id,
            "color": "#8899ff",
        }
        _draw_link(session, board_id, data)
        link_count += 1
    return link_count


def _generate_diagram(session: Session, args: dict) -> dict:
    """Place a whole tree of notes on a whiteboard in one call, the gap
    named directly (BACKLOG.md §29d, HANDOVER.md): `add_whiteboard_card`/
    `add_whiteboard_link` already exist, but x/y are free-form numbers the
    model has to invent itself across many chained calls, exactly the
    bookkeeping a small (2-8B) tool-calling model gets wrong. Here the
    model only ever declares *structure* (a title or an existing note, and
    which other node is its parent); this function creates whatever notes
    need creating, computes every position server-side, and wires the
    links: the same job `wbArrangeMindMap` already does client-side for a
    board someone arranges by hand, now reachable in one round trip.
    """
    raw_board_id = args.get("board_id")
    board_id = int(raw_board_id) if raw_board_id not in (None, "") else None
    layout = "radial" if args.get("layout") == "radial" else "tree"

    by_ref = _diagram_nodes(args)
    shape = _diagram_shape(by_ref)
    attach, root_ref, _children = shape
    positions, anchors, layout = _diagram_positions(session, board_id, by_ref, shape, layout)
    entries = _diagram_entries(session, by_ref)
    cards = _diagram_cards(session, board_id, entries, positions)
    link_count = _diagram_links(session, board_id, by_ref, attach, anchors, cards)
    # One event more than the items' own, and on the board rather than on any
    # of them: that this was one diagram generation, rather than sixty cards
    # that happened to arrive together, is a fact no item's own history can
    # hold (Brief 7 decision 4 keeps the board's own events on `board`). It
    # carries no `after`, because nothing about the board itself changed:
    # what it says is what ran, which is what a feed reading this wants.
    events.record(
        session,
        "generated",
        "board",
        board_id,
        f"{len(cards)} cards, root '{root_ref}'",
        payload={
            "cards": len(cards),
            "links": link_count,
            "layout": layout,
            "root_ref": root_ref,
        },
    )
    session.commit()

    return {
        "board_id": board_id,
        "root_card_id": cards[root_ref].id,
        "extended_cards": sorted(anchors),
        "cards": [
            {"ref": ref, "card_id": card.id, "note_id": entries[ref].id, "x": card.x, "y": card.y}
            for ref, card in cards.items()
        ],
        "links_created": link_count,
        "label": f"ph:map-trifold Placed {len(cards)} cards as a {layout} diagram",
    }




# --- mindmaps (MINDMAP_PLAN.md §5 item 14) ----------------------------------
#
# Four tools, one job each, because that is the shape a small model can
# actually use: AGENT_SKILLS_REFORM.md's Phase A/B contract is "one tool per
# step", and the failure it is written against is a 4B model handed a
# compound instruction that narrates instead of calling anything. So
# `read_mindmap` reads and never writes, `add_map_node` adds exactly one node
# per call and never invents coordinates, and every description below names
# the tool that comes before it.
#
# The tree itself is read through `routes_whiteboard`'s own helpers rather
# than walked again here. Imported inside the functions, not at module scope:
# the API layer sits on top of this one, and the walk has three edge cases
# (a dangling parent, a ring, board scoping) that must have exactly one
# implementation: a second copy is how two readers of the same map come to
# disagree about what is on it.

#: The most nodes one `read_mindmap` will spell out. A map is meant to fit in
#: the model's window beside the question; past this the outline stops being
#: context and becomes the whole window, the same reason every list tool here
#: has a limit.
MAX_OUTLINE_NODES = 200


def _outline_lines(nodes: list[dict], depth: int, out: list[str], budget: list[int]) -> None:
    """The tree as indented text, the form the plan asks for by name, and
    the one a small model handles best: an id per line, so the next call can
    name a node instead of describing it."""
    for node in nodes:
        if budget[0] <= 0:
            return
        budget[0] -= 1
        marks = [f"id {node['id']}"]
        if node["kind"] != "topic":
            # The kind and what it stands for, so "which of these is a real
            # note?" is answerable from the outline without a second call.
            marks.append(
                f"{node['kind']} {node['ref_id']}" if node["ref_id"] is not None else node["kind"]
            )
        if node["collapsed"]:
            marks.append("collapsed")
        out.append(f"{'  ' * depth}- {node['text'] or '(untitled)'} [{', '.join(marks)}]")
        _outline_lines(node["children"], depth + 1, out, budget)


def _read_mindmap(session: Session, args: dict) -> dict:
    """A whole map as an indented outline (MINDMAP_PLAN.md §5 item 14).

    Deliberately *not* `read_whiteboard` with a flag. That tool answers
    "what is on this board" as three flat lists, cards, text boxes, links , 
    which is the right answer for a canvas and the wrong one for a map, where
    the structure is the content. A model handed a flat list of twenty topics
    and a separate list of parent ids will reconstruct the tree wrongly, or
    not at all.
    """
    from tessellate.api.routes_whiteboard import _board_settings, _build_tree, _map_objects

    raw_board_id = args.get("board_id")
    if raw_board_id in (None, ""):
        raise ToolError(
            "board_id is required: call search_whiteboard or read_whiteboard first to find the map's id."
        )
    board_id = int(raw_board_id)
    board = session.get(Entry, board_id)
    if board is None or board.is_deleted:
        raise ToolError(f"No board with id {board_id}")
    # A board is an Entry and can be marked private after being used as one, 
    # same rule, and the same reason, as `_read_whiteboard`'s own board title
    # check: this result becomes part of the agent's context.
    if board.is_private:
        raise ToolError(f"Board {board_id} is a private note and can't be read by the AI.")

    board_type, layout = _board_settings(board)
    objects = _map_objects(session, board_id)
    roots = _build_tree(session, objects)
    budget = [MAX_OUTLINE_NODES]
    lines: list[str] = []
    _outline_lines(roots, 0, lines, budget)
    title = manager.extract_title(board.content) or _clip(board.content, 40)
    outline = "\n".join([title, *lines]) if lines else f"{title}\n(empty: no nodes yet)"

    result = {
        "board_id": board_id,
        "board_title": title,
        "type": board_type,
        "layout": layout,
        "node_count": len(objects),
        "outline": outline,
        "label": f"ph:tree-structure Read the mindmap “{title}”",
    }
    if budget[0] <= 0 and len(objects) > MAX_OUTLINE_NODES:
        result["truncated"] = (
            f"Only the first {MAX_OUTLINE_NODES} of {len(objects)} nodes are shown."
        )
    return result


def _create_mindmap(session: Session, args: dict) -> dict:
    """A new, empty map with one root topic on it.

    A map *is* a board, which is itself a note (`routes_whiteboard.py`'s own
    opening line), so this creates one note and one object, not a new kind
    of thing. The root is created here rather than left to a second
    `add_map_node` call because a map with no root has nothing to hang the
    next node off, and a small model handed an empty map reliably stalls
    there.
    """
    from tessellate.api.routes_whiteboard import (
        MAP_TOPIC_KIND,
        _store_board_settings,
    )
    from tessellate.core.database import WhiteboardObject

    title = str(args.get("title") or "").strip()
    if not title:
        raise ToolError("title is required: what is this map about?")
    root_text = str(args.get("root_text") or "").strip() or title

    entry = Entry(content=f"# {title}", is_board=True)
    # "tree-right", not the API's own "free" default: every position this
    # module computes is a tree-right ladder (`_next_position`), so telling
    # the client anything else would be describing a map it isn't.
    _store_board_settings(entry, "map", "tree-right")
    # Two events, on two entities, the same pair a person creating this map
    # by hand records (`POST /boards` then `POST /boards/{id}/nodes`): the
    # board is one thing and the root topic on it is another, and folding
    # them into one would leave the root with no event of its own to replay
    # from.
    _new_board(session, entry, title, "map", "tree-right")
    root = _place_object(
        session,
        WhiteboardObject(
            board_id=entry.id,
            kind=MAP_TOPIC_KIND,
            data=json.dumps({"content": root_text}),
            x=0.0,
            y=0.0,
            z=1,
        ),
    )
    session.commit()
    session.refresh(entry)
    session.refresh(root)
    return {
        "board_id": entry.id,
        "root_id": root.id,
        "title": title,
        "next": "Add nodes with add_map_node, passing this board_id and parent_id.",
        "label": f"ph:tree-structure Created the mindmap “{_clip(title, 40)}”",
    }


def _map_from_note(session: Session, args: dict) -> dict:
    """A mind map made from one note in one call: its title the centre topic
    (which opens the note), its headings and lists the branches.

    One tool rather than `create_mindmap` and a call per node, because a
    small model asked for "a map of this note" stalls after the third node
    (WHITEBOARD_PLAN row 9). The same build as the note menu's Make a mind
    map (`routes_map_from_notes.map_from_note_entry`), so it is the same map
    with or without a model."""
    from tessellate.api.routes_map_from_notes import map_from_note_entry

    if args.get("note_id") is None:
        raise ToolError("note_id is required: which note should the map be made from?")
    entry = _require_note(session, args)
    if entry.is_board:
        raise ToolError(f"#{entry.id} is already a board; read it with read_whiteboard or read_mindmap.")
    try:
        board, count = map_from_note_entry(session, entry, str(args.get("title") or ""))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    name = board.content[2:]
    return {
        "board_id": board.id,
        "title": name,
        "nodes": count,
        "label": f"ph:tree-structure Made the mind map “{_clip(name, 40)}” from the note",
    }


def _add_map_node(session: Session, args: dict) -> dict:
    """One node, under one parent, per call.

    The single-step shape on purpose (AGENT_SKILLS_REFORM Phase B): a bulk
    "here is my whole tree" call already exists as `generate_diagram`, and
    it exists precisely because the *card* version of this needed the model
    to invent x/y across many chained calls. Here the model never sees a
    coordinate at all, the server places the node beside its parent, so
    the only thing it has to get right is which node is the parent.
    """
    from tessellate.api.routes_whiteboard import (
        MAP_REFERENCE_KINDS,
        MAP_TOPIC_KIND,
        _next_position,
    )
    from tessellate.core.database import WhiteboardObject

    raw_board_id = args.get("board_id")
    if raw_board_id in (None, ""):
        raise ToolError("board_id is required: call create_mindmap or read_mindmap first.")
    board_id = int(raw_board_id)
    board = session.get(Entry, board_id)
    if board is None or board.is_deleted:
        raise ToolError(f"No board with id {board_id}")

    kind = str(args.get("kind") or MAP_TOPIC_KIND).strip() or MAP_TOPIC_KIND
    if kind != MAP_TOPIC_KIND and kind not in MAP_REFERENCE_KINDS:
        raise ToolError(
            f"Unknown node kind '{kind}', use 'topic' for text, or 'note' to put an existing note on the map."
        )

    text = str(args.get("text") or "").strip()
    ref_id = None
    if kind == "note":
        # **`_require_note`, not `session.get`.** It is the one lookup that
        # refuses a private note, and a map is a place a note's title would
        # otherwise be copied into and read straight back out through
        # `read_mindmap`. (CLAUDE.md's "a guard removed while the shape
        # around it was kept" is exactly this line going missing.)
        entry = _require_note(session, args, "note_id")
        ref_id = entry.id
        text = text or _clip(manager.readable_content(entry), 80)
    elif kind in MAP_REFERENCE_KINDS:
        raw_ref = args.get("ref_id")
        if raw_ref in (None, ""):
            raise ToolError(f"A '{kind}' node needs ref_id: the id of the {kind} it stands for.")
        ref_id = int(raw_ref)
    elif not text:
        raise ToolError("text is required for a topic node.")

    parent = None
    raw_parent = args.get("parent_id")
    if raw_parent not in (None, ""):
        parent = session.get(WhiteboardObject, int(raw_parent))
        if parent is None or parent.board_id != board_id:
            raise ToolError(
                f"No node with id {raw_parent} on board {board_id}: call read_mindmap for the ids."
            )

    x, y = _next_position(session, board_id, parent)
    data = {"content": text}
    if ref_id is not None:
        data["ref_id"] = ref_id
    node = _place_object(
        session,
        WhiteboardObject(
            board_id=board_id,
            kind=kind,
            data=json.dumps(data),
            x=x,
            y=y,
            z=1,
            parent_id=parent.id if parent is not None else None,
        ),
    )
    session.commit()
    session.refresh(node)
    return {
        "node_id": node.id,
        "board_id": board_id,
        "parent_id": node.parent_id,
        "kind": kind,
        "text": text,
        "label": f"ph:tree-structure Added “{_clip(text, 40)}” to the map",
    }


def _link_map_nodes(session: Session, args: dict) -> dict:
    """A cross-link: an edge between two nodes that are *not* parent and
    child.

    Every serious mindmapper has this and calls it a relationship or a
    cross-link, and it is the one edge a tree cannot express. Stored as a
    link sketch, the same row a link between two cards already is, so the
    canvas draws it, `_forget_links_to` cleans it up when either end goes,
    and there is no second kind of edge to maintain.
    """
    from tessellate.core.database import WhiteboardObject

    source = session.get(WhiteboardObject, int(args.get("from_id") or 0))
    target = session.get(WhiteboardObject, int(args.get("to_id") or 0))
    if source is None:
        raise ToolError(f"No map node with id {args.get('from_id')}")
    if target is None:
        raise ToolError(f"No map node with id {args.get('to_id')}")
    if source.id == target.id:
        raise ToolError("Can't link a node to itself.")
    if source.board_id != target.board_id:
        raise ToolError("Both nodes must be on the same map to link them.")
    raw_board_id = args.get("board_id")
    if raw_board_id not in (None, "") and int(raw_board_id) != (source.board_id or 0):
        raise ToolError(
            f"Those nodes are on board {source.board_id}, not board {raw_board_id}."
        )

    label = _clip(str(args.get("label") or "").strip(), 80)
    data = {
        "type": "link-curved",
        "sourceId": source.id,
        "sourceKind": "object",
        "targetId": target.id,
        "targetKind": "object",
        "color": "#8899ff",
        "label": label,
    }
    sketch = _draw_link(session, source.board_id, data)
    session.commit()
    session.refresh(sketch)
    return {
        "link_id": sketch.id,
        "board_id": source.board_id,
        "from_id": source.id,
        "to_id": target.id,
        "label_text": label,
        "label": "ph:link Linked two nodes on the map",
    }
