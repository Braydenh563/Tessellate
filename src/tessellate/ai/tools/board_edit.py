"""AI tools that change what is already on a board (FEAT-12; WHITEBOARD_PLAN
decision 29), and that draw shapes and place library items on one.

The features audit: the assistant could read a board and add cards, links and
map topics, and could not move, edit, restyle or delete anything, draw a
shape, or use the object library, so "tidy this board" or "make the risks
red" had no tool. Decision 29: move, edit and delete each go through the
confirm card the other destructive tools use (the board is the person's
work, and a model that misread an id moves the wrong thing), each is one
event, and each returns an `undo` the run summary offers beside it, the same
contract every other write here keeps.

What counts as an item: a card (a note on the board, `card`), a text box,
sticky or frame (`object`), and a drawn shape or line (`shape`). A connector
is not edited here: it follows its two ends.
"""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import events

from ._common import ToolError, _clip, board_top_z

ITEM_KINDS = ("card", "object", "shape")
SHAPES = ("rect", "ellipse", "diamond", "frame")
_HEX = "0123456789abcdefABCDEF"


def _colour(value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = "#" + text
    if len(text) not in (4, 7) or any(c not in _HEX for c in text[1:]):
        raise ToolError(f"{value!r} is not a colour: give one like #cc3333.")
    return text.lower()


def _load(session: Session, kind: str, item_id) -> object:
    from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch

    model = {"card": WhiteboardNode, "object": WhiteboardObject, "shape": WhiteboardSketch}.get(str(kind or ""))
    if model is None:
        raise ToolError(f"kind must be one of {', '.join(ITEM_KINDS)}; read_whiteboard lists each item's kind and id.")
    try:
        row = session.get(model, int(item_id))
    except (TypeError, ValueError):
        row = None
    if row is None:
        raise ToolError(f"No {kind} with id {item_id} on any board. Call read_whiteboard for the ids.")
    if kind == "shape":
        data = _data(row)
        if str(data.get("type", "")).startswith("link-"):
            raise ToolError("That is a connector; it follows the two things it joins, so move or edit those.")
    if kind == "object" and row.kind not in ("text", "frame", "image"):
        raise ToolError("That is a mind map topic: use the mind map tools for it.")
    return row


def _data(row) -> dict:
    try:
        raw = getattr(row, "data", None)
        data = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (TypeError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def _entity(kind: str) -> str:
    return {"card": "whiteboard_node", "object": "whiteboard_object", "shape": "whiteboard_sketch"}[kind]


def _state(kind: str, row) -> dict:
    if kind == "card":
        return events.node_state(row)
    if kind == "object":
        return events.object_state(row)
    return events.sketch_state(row)


def _record(session: Session, verb: str, kind: str, row, before: dict, words: str) -> None:
    events.record(session, verb, _entity(kind), row.id, words[:80], payload={"before": before, "after": _state(kind, row)})


_ARITY = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}


def _path_corner(d: str) -> tuple[float, float]:
    """The top-left of an absolute path's points (the ends of each command,
    and a curve's control points, which is close enough to place by): the
    board draws every shape with absolute commands."""
    import re

    xs: list[float] = []
    ys: list[float] = []
    tokens = re.findall(r"[MLHVCSQTAZmlhvcsqtaz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d or "")
    i, cmd, cx, cy = 0, "M", 0.0, 0.0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i].upper()
            i += 1
            if cmd == "Z":
                continue
        n = _ARITY.get(cmd, 2)
        nums = tokens[i : i + n]
        if len(nums) < n or any(t.isalpha() for t in nums):
            break
        v = [float(t) for t in nums]
        i += n
        if cmd == "H":
            cx = v[0]
        elif cmd == "V":
            cy = v[0]
        elif cmd == "A":
            cx, cy = v[5], v[6]
        else:
            for k in range(0, n - 2, 2):
                xs.append(v[k])
                ys.append(v[k + 1])
            cx, cy = v[n - 2], v[n - 1]
        xs.append(cx)
        ys.append(cy)
    return (min(xs), min(ys)) if xs else (0.0, 0.0)


def _box(kind: str, row) -> tuple[float, float]:
    """An item's top-left corner in board units."""
    if kind != "shape":
        return float(row.x or 0), float(row.y or 0)
    return _path_corner(_data(row).get("d", ""))


def _move_board_item(session: Session, args: dict) -> dict:
    """Move one item so its top-left corner is at (x, y)."""
    from tessellate.api.routes_board_library import transform_path

    kind = str(args.get("kind") or "")
    row = _load(session, kind, args.get("item_id"))
    try:
        x, y = float(args["x"]), float(args["y"])
    except (KeyError, TypeError, ValueError) as err:
        raise ToolError("Give x and y, the new top-left corner in board units.") from err
    if _data(row).get("locked") or getattr(row, "locked", False):
        raise ToolError("That item is locked on the board; the person unlocks it first.")
    before = _state(kind, row)
    old_x, old_y = _box(kind, row)
    if kind == "shape":
        data = _data(row)
        data["d"] = transform_path(data.get("d", ""), 1, 1, x - old_x, y - old_y)
        row.data = json.dumps(data)
    else:
        row.x, row.y = x, y
    _record(session, "moved", kind, row, before, f"{kind} {row.id} moved by the assistant")
    session.commit()
    return {
        "kind": kind, "item_id": row.id, "x": round(x), "y": round(y),
        "label": f"ph:arrows-out-cardinal Moved the {kind} to {round(x)}, {round(y)}",
        "undo": {"tool": "move_board_item", "arguments": {"kind": kind, "item_id": row.id, "x": old_x, "y": old_y}},
    }


def _edit_board_item(session: Session, args: dict) -> dict:
    """Change an item's words or colours. A card's words are its note's, so a
    card takes colours only here; edit the note to change what it says."""
    kind = str(args.get("kind") or "")
    row = _load(session, kind, args.get("item_id"))
    data = _data(row)
    before = _state(kind, row)
    old: dict = {}
    changed = []
    text = args.get("text")
    colour = _colour(args.get("color"))
    fill = _colour(args.get("fill"))
    if kind == "card":
        raise ToolError("A card shows its note: edit the note itself (update_note) to change what it says.")
    if text is not None:
        key = "label" if kind == "shape" else "content"
        old["text"] = data.get(key, "")
        data[key] = str(text)[:2000]
        changed.append("words")
    if colour:
        old["color"] = data.get("color") or ""
        data["color"] = colour
        changed.append("colour")
    if fill:
        key = "fill" if kind == "shape" else "bg"
        old["fill"] = data.get(key) or ""
        data[key] = fill
        changed.append("fill")
    fold = args.get("fold")
    if fold is not None:
        #: A sticky's folded corner (OPEN row 810): the Format panel's switch,
        #: which the assistant could keep but not set.
        sticky = data.get("sticky") or (data.get("border_color") == "#e8d56a" and data.get("bg"))
        if kind != "object" or not sticky or data.get("sticker"):
            raise ToolError("Only a sticky note has a folded corner.")
        #: With no corner stored the board's default showed, which is
        #: not read here: the undo turns back to the other state.
        old["fold"] = data.get("fold", not bool(fold))
        data["fold"] = bool(fold)
        changed.append("corner")
    if not changed:
        raise ToolError("Nothing to change: give text, color, fill or fold.")
    if kind == "object":
        from tessellate.api.routes_whiteboard import WhiteboardObjectData

        try:
            data = WhiteboardObjectData(**data).model_dump(exclude_none=True) | {k: v for k, v in data.items() if k in ("library_ref",)}
        except ValueError as err:
            raise ToolError(f"That change is not valid for this item: {err}") from err
    row.data = json.dumps(data)
    _record(session, "updated", kind, row, before, f"{kind} {row.id} edited by the assistant")
    session.commit()
    return {
        "kind": kind, "item_id": row.id, "changed": changed,
        "label": f"ph:pencil-simple Changed the {kind}'s {' and '.join(changed)}",
        "undo": {"tool": "edit_board_item", "arguments": {"kind": kind, "item_id": row.id, **{k: v for k, v in old.items() if v or k == "fold"}}},
    }


def _delete_board_item(session: Session, args: dict) -> dict:
    """Take one item off its board. A card's note stays in the notebook."""
    kind = str(args.get("kind") or "")
    row = _load(session, kind, args.get("item_id"))
    from tessellate.api.routes_whiteboard import _forget_links_to

    before = _state(kind, row)
    #: Its connectors go with it, as they do when a person deletes it, and
    #: come back with it on the undo.
    links: list = []
    end_kind = {"card": "node", "object": "object", "shape": "sketch"}[kind]
    _forget_links_to(session, row.board_id, end_kind, row.id, into=links)
    kept_links = [link.model_dump(mode="json") if hasattr(link, "model_dump") else dict(link) for link in links]
    keep = {"kind": kind, "old_id": row.id, "state": before, "links": kept_links}
    events.record(session, "deleted", _entity(kind), row.id, f"{kind} {row.id} deleted by the assistant", payload={"before": before})
    session.delete(row)
    session.commit()
    return {
        "kind": kind, "item_id": before.get("id", args.get("item_id")),
        "label": f"ph:trash Took the {kind} off the board",
        "undo": {"tool": "restore_board_item", "arguments": {"item": json.dumps(keep)}},
    }


def _restore_board_item(session: Session, args: dict) -> dict:
    """Put back an item `delete_board_item` took off (its undo), with a new id."""
    from tessellate.core.database import WhiteboardNode, WhiteboardObject, WhiteboardSketch

    try:
        keep = json.loads(args.get("item") or "{}")
        kind, state = keep["kind"], dict(keep["state"])
    except (TypeError, ValueError, KeyError) as err:
        raise ToolError("item is the text delete_board_item returned for its undo.") from err
    model = {"card": WhiteboardNode, "object": WhiteboardObject, "shape": WhiteboardSketch}.get(kind)
    if model is None:
        raise ToolError("That is not a board item delete_board_item made.")
    columns = {c.name for c in model.__table__.columns} - {"id"}
    row = model(**{k: v for k, v in state.items() if k in columns})
    session.add(row)
    session.flush()
    end_kind = {"card": "node", "object": "object", "shape": "sketch"}[kind]
    for link in keep.get("links") or []:
        try:
            data = json.loads(link.get("data") or "{}")
        except (TypeError, ValueError):
            continue
        for end in ("source", "target"):
            if data.get(f"{end}Id") == keep.get("old_id") and (data.get(f"{end}Kind") or "node") == end_kind:
                data[f"{end}Id"] = row.id
        session.add(WhiteboardSketch(board_id=row.board_id, data=json.dumps(data), x=0, y=0, z=link.get("z") or 1))
    events.record(session, "created", _entity(kind), row.id, f"{kind} put back by the assistant", payload={"after": _state(kind, row)})
    session.commit()
    return {"kind": kind, "item_id": row.id, "label": f"ph:arrow-counter-clockwise Put the {kind} back on the board"}


def _shape_path(shape: str, x: float, y: float, w: float, h: float) -> str:
    if shape == "ellipse":
        rx, ry = w / 2, h / 2
        return f"M {x} {y + ry} A {rx} {ry} 0 1 0 {x + w} {y + ry} A {rx} {ry} 0 1 0 {x} {y + ry} Z"
    if shape == "diamond":
        return f"M {x + w / 2} {y} L {x + w} {y + h / 2} L {x + w / 2} {y + h} L {x} {y + h / 2} Z"
    return f"M {x} {y} L {x + w} {y} L {x + w} {y + h} L {x} {y + h} Z"


def _add_board_shape(session: Session, args: dict) -> dict:
    """Draw a rectangle, ellipse or diamond with words in it, or a frame."""
    from tessellate.core.database import WhiteboardObject, WhiteboardSketch

    shape = str(args.get("shape") or "rect").lower()
    if shape not in SHAPES:
        raise ToolError(f"shape is one of {', '.join(SHAPES)}.")
    raw = args.get("board_id")
    board_id = int(raw) if raw not in (None, "", 0, "0") else None
    try:
        x, y = float(args.get("x", 100)), float(args.get("y", 100))
        w = max(20.0, min(4000.0, float(args.get("width", 400 if shape == "frame" else 160))))
        h = max(20.0, min(4000.0, float(args.get("height", 300 if shape == "frame" else 80))))
    except (TypeError, ValueError) as err:
        raise ToolError("x, y, width and height are numbers in board units.") from err
    text = str(args.get("text") or "")[:500]
    if shape == "frame":
        row = WhiteboardObject(board_id=board_id, kind="frame", data=json.dumps({"content": text or "Frame"}), x=x, y=y, width=w, height=h, z=0)
        kind = "object"
    else:
        data = {"d": _shape_path(shape, x, y, w, h), "shape": "circle" if shape == "ellipse" else shape,
                "color": _colour(args.get("color")) or "#335599", "width": 2}
        if args.get("fill"):
            data["fill"] = _colour(args.get("fill"))
        if text:
            data["label"] = text
        row = WhiteboardSketch(board_id=board_id, data=json.dumps(data), x=0, y=0, z=board_top_z(session, board_id))
        kind = "shape"
    session.add(row)
    session.flush()
    events.record(session, "created", _entity(kind), row.id, f"{shape} drawn by the assistant", payload={"after": _state(kind, row)})
    session.commit()
    return {
        "kind": kind, "item_id": row.id, "shape": shape,
        "label": f"ph:shapes Drew a {shape}{' “' + _clip(text, 30) + '”' if text else ''}",
        "undo": {"tool": "delete_board_item", "arguments": {"kind": kind, "item_id": row.id}},
    }


def _list_library(session: Session, args: dict) -> dict:
    """The object library: built-in shapes, flowchart symbols, arrows, frames
    and icons, and the person's own saved items, found by a word."""
    from tessellate.api.routes_board_library import _builtin_index
    from tessellate.core.database import BoardLibraryItem

    term = str(args.get("query") or "").strip().lower()
    limit = max(1, min(30, int(args.get("limit") or 12)))
    found = []
    for key, entry in _builtin_index().items():
        words = " ".join([entry.get("name", ""), *entry.get("tags", [])]).lower()
        if not term or term in words:
            found.append({"ref": f"builtin:{key}", "name": entry.get("name", key), "set": key.split("/")[0]})
    yours = session.scalars(select(BoardLibraryItem).where(BoardLibraryItem.deleted_at.is_(None)))
    for item in yours:
        words = " ".join([item.name or "", *(item.tags or [])]).lower()
        if item.kind in ("element", "shape", "preset", "branch") and (not term or term in words):
            found.insert(0, {"ref": f"item:{item.id}", "name": item.name, "set": "yours"})
    return {
        "items": found[:limit], "total": len(found),
        "label": f"ph:shapes Looked in the library{' for “' + _clip(term, 30) + '”' if term else ''}",
    }


def _place_library_item(session: Session, args: dict) -> dict:
    """Place a library item (from list_library) on a board, centred at x, y."""
    from tessellate.api.routes_board_library import PlaceBody, place_library_item

    ref = str(args.get("ref") or "")
    body = {"x": float(args.get("x") or 0), "y": float(args.get("y") or 0)}
    if ref.startswith("builtin:"):
        body["builtin"] = ref.split(":", 1)[1]
    elif ref.startswith("item:") and ref[5:].isdigit():
        body["item_id"] = int(ref[5:])
    else:
        raise ToolError("ref is one list_library returned, like builtin:flowchart/decision or item:12.")
    raw = args.get("board_id")
    board_id = int(raw) if raw not in (None, "") else 0
    try:
        made = place_library_item(board_id, PlaceBody(**body), session)
    except HTTPException as err:
        raise ToolError(str(err.detail)) from err
    steps = [{"tool": "delete_board_item", "arguments": {"kind": "shape", "item_id": s["id"]}} for s in made["sketches"]
             if not str(json.loads(s["data"]).get("type", "")).startswith("link-")]
    steps += [{"tool": "delete_board_item", "arguments": {"kind": "object", "item_id": o["id"]}} for o in made["objects"]]
    return {
        "placed": made.get("name"), "sketch_ids": [s["id"] for s in made["sketches"]], "object_ids": [o["id"] for o in made["objects"]],
        "label": f"ph:shapes Placed “{_clip(made.get('name') or 'item', 30)}” on the board",
        "undo": steps[0] if len(steps) == 1 else {"tool": "batch", "steps": steps},
    }
