"""The board's object library (WHITEBOARD_PLAN decision 25; INBOX 557c, 558).

The owner: "an object or elements library would be really good like with what
draw.io has", and "the ability to save custom elements and stuff as well". A
library item is a reusable thing for a board or a map:

- `element`: a saved selection (shapes, text, stickies, frames, pictures and
  the links between them), positioned from its box's top left corner;
- `shape`: one drawn path kept as a shape, which scales and takes text;
- `style` and `palette`: a look to apply, and up to sixteen colours;
- `preset`: a sticky or text box with its look and words;
- `branch`: a mind map branch, `{text, data, children}` all the way down;
- `template`: a whole board or map, its settings and its content.

**Built-in sets are files, not rows** (`frontend/board-library/*.json`,
built by `scripts/build_board_library.py`): the client reads them as static
files and this module reads the same files to place one, so an upgrade can
improve a set without a migration. Built-ins are addressed `"<set>/<key>"`;
their favourite and recent marks are rows of `board_library_marks`.

**Placing makes independent copies** (decision 25): ordinary rows on the
board, each remembering `library_ref {id, version}` in its data, never
following a later edit. One placement is one transaction and one event.

Nothing here fetches anything: a picture in a payload is this notebook's own
`/media/` upload (`MEDIA_URL_RE`), and an import drops any it does not have.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.api.routes_whiteboard import (
    BOARD_BG_COLOR_RE,
    BOARD_LAYOUTS,
    MAP_REFERENCE_KINDS,
    MAP_TOPIC_KIND,
    MEDIA_URL_RE,
    WhiteboardObjectBase,
    WhiteboardObjectData,
    WhiteboardSketchBase,
    _require_board,
    _require_object_data,
    _board_settings,
    _object_state,
    _on_current_layer,
    _object_to_out,
    _sketch_state,
    _store_board_background,
    _store_board_settings,
    _store_board_theme,
    BoardBackground,
)
from tessellate.core import deps, events, undo_bin
from tessellate.core.database import (
    BoardLibrary,
    BoardLibraryItem,
    BoardLibraryMark,
    Entry,
    MediaUpload,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
    utcnow,
)
from tessellate.core.deps import get_session

router = APIRouter(tags=["board-library"])

if getattr(sys, "frozen", False):
    _BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    _BUNDLE_ROOT = Path(__file__).resolve().parents[3]
BUILTIN_DIR = _BUNDLE_ROOT / "frontend" / "board-library"

ITEM_KINDS = ("element", "shape", "style", "palette", "preset", "branch", "template")
LIBRARY_KINDS = ("yours", "custom", "imported")
#: The code editor's snippets (INBOX 788, `routes_code_snippets.py`) are rows
#: of this table too, but not a board's: kept out of `ITEM_KINDS`, out of the
#: board's listing unless asked by kind, and out of a library's export.
SNIPPET_KIND = "snippet"
#: The payload limits (features audit 8.5): a saved thing is a few shapes or a
#: board's worth, never a backup.
MAX_PAYLOAD_ITEMS = 500
MAX_PAYLOAD_BYTES = 512 * 1024
MAX_SKETCH_DATA_CHARS = 200_000
MAX_NAME = 120
MAX_TAGS = 20
#: Recent shows this many, newest first.
RECENT_LIMIT = 12
EXPORT_FORMAT = "memorymap-library"
OBJECT_TYPES = ("text", "image", "frame")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
STYLE_KEYS = frozenset(
    {"color", "width", "dash", "fill", "fillOpacity", "noStroke", "startCap", "endCap", "font_size",
     "bold", "italic", "align", "bg", "border_color", "shape"}
)
INK = "ink"

logger = logging.getLogger(__name__)


# --- payloads -----------------------------------------------------------------


def _fail(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _media_urls(value: Any) -> list[str]:
    """Every `/media/...` string anywhere in a payload."""
    text = json.dumps(value)
    return re.findall(r"/media/[A-Za-z0-9][A-Za-z0-9._-]{0,119}", text)


def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and abs(number) < 1e7 else default


def _clean_element(payload: dict) -> dict:
    """An element payload as stored: known kinds, bounded sizes, object data
    through the board's own validator, links only between items it holds."""
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise _fail("A saved selection needs at least one item.")
    if len(items) > MAX_PAYLOAD_ITEMS:
        raise _fail(f"A library item holds at most {MAX_PAYLOAD_ITEMS} things.")
    clean, keys = [], set()
    for raw in items:
        if not isinstance(raw, dict):
            raise _fail("Each item is an object.")
        key = str(raw.get("key") or f"k{len(clean)}")[:40]
        if key in keys:
            raise _fail("Two items share a key.")
        keys.add(key)
        group = raw.get("group")
        item: dict[str, Any] = {"key": key, "z": int(_clean_number(raw.get("z"), 0))}
        if isinstance(group, str) and group:
            item["group"] = group[:40]
        if raw.get("kind") == "sketch":
            data = raw.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except ValueError:
                    raise _fail("A drawing's data is not JSON.") from None
            if not isinstance(data, dict) or not isinstance(data.get("d", ""), str):
                raise _fail("A drawing needs its path.")
            data.pop("sourceId", None)
            data.pop("targetId", None)
            data.pop("library_ref", None)
            if len(json.dumps(data)) > MAX_SKETCH_DATA_CHARS:
                raise _fail("One drawing in this item is too large.")
            item.update(kind="sketch", data=data)
        elif raw.get("kind") == "object":
            kind = raw.get("type")
            if kind not in OBJECT_TYPES:
                raise _fail(f"A library item holds text, pictures and frames, not {kind}.")
            data = dict(raw.get("data") or {})
            data.pop("library_ref", None)
            data.pop("comments", None)
            try:
                checked = WhiteboardObjectData(**data).model_dump(exclude_none=True)
            except ValueError as err:
                logger.info("board library: an item did not validate: %s", err)
                raise _fail("An item's data is not valid.") from None
            if kind == "image" and not MEDIA_URL_RE.match(checked.get("url") or ""):
                raise _fail("A picture in the library is one of this notebook's uploads.")
            item.update(
                kind="object", type=kind, data=checked,
                x=_clean_number(raw.get("x")), y=_clean_number(raw.get("y")),
                w=max(20.0, min(4000.0, _clean_number(raw.get("w"), 200))),
                h=max(20.0, min(4000.0, _clean_number(raw.get("h"), 120))),
            )
            rotation = raw.get("rotation")
            if rotation is not None:
                item["rotation"] = max(-360.0, min(360.0, _clean_number(rotation)))
        else:
            raise _fail("An item is a drawing or an object.")
        clean.append(item)
    links = []
    for raw in payload.get("links") or []:
        if not isinstance(raw, dict) or raw.get("from") not in keys or raw.get("to") not in keys:
            continue
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        data = {k: v for k, v in data.items() if k not in ("sourceId", "targetId", "library_ref")}
        if not str(data.get("type", "")).startswith("link-"):
            data["type"] = "link-straight"
        links.append({"from": raw["from"], "to": raw["to"], "data": data})
    box = payload.get("box") if isinstance(payload.get("box"), dict) else {}
    return {
        "box": {"w": max(1.0, _clean_number(box.get("w"), 100)), "h": max(1.0, _clean_number(box.get("h"), 100))},
        "items": clean,
        "links": links,
    }


def _clean_branch(payload: dict) -> dict:
    count = 0

    def walk(node: Any, depth: int) -> dict:
        nonlocal count
        count += 1
        if count > MAX_PAYLOAD_ITEMS or depth > 30:
            raise _fail(f"A saved branch holds at most {MAX_PAYLOAD_ITEMS} topics, 30 deep.")
        if not isinstance(node, dict):
            raise _fail("A branch is topics.")
        data = dict(node.get("data") or {})
        for key in ("library_ref", "comments", "ref_id", "order", "pinned", "collapsed"):
            data.pop(key, None)
        data["content"] = str(node.get("text") or data.get("content") or "")[:5000]
        try:
            checked = WhiteboardObjectData(**data).model_dump(exclude_none=True)
        except ValueError as err:
            logger.info("board library: a topic did not validate: %s", err)
            raise _fail("A topic's data is not valid.") from None
        text = checked.pop("content", "")
        return {"text": text, "data": checked, "children": [walk(c, depth + 1) for c in node.get("children") or []]}

    roots = payload.get("nodes")
    if not isinstance(roots, list) or not roots:
        raise _fail("A saved branch needs at least one topic.")
    return {"nodes": [walk(n, 0) for n in roots]}


def _clean_payload(kind: str, payload: Any) -> dict:
    if kind not in ITEM_KINDS:
        raise _fail(f"A library item is one of: {', '.join(ITEM_KINDS)}.")
    if not isinstance(payload, dict):
        raise _fail("A library item's payload is an object.")
    if len(json.dumps(payload)) > MAX_PAYLOAD_BYTES:
        raise _fail("This is too large for the library (512 KB at most).")
    for url in _media_urls(payload):
        if not MEDIA_URL_RE.match(url):
            raise _fail("A picture in the library is one of this notebook's uploads.")
    if kind in ("element", "shape", "preset"):
        return _clean_element(payload)
    if kind == "branch":
        return _clean_branch(payload)
    if kind == "style":
        style = payload.get("style") if isinstance(payload.get("style"), dict) else {}
        clean = {k: v for k, v in style.items() if k in STYLE_KEYS and isinstance(v, (str, int, float, bool))}
        if not clean:
            raise _fail("A saved style needs at least one property.")
        target = payload.get("target") if payload.get("target") in ("shape", "line", "text", "link") else "shape"
        return {"target": target, "style": clean}
    if kind == "palette":
        colours = [c.lower() for c in payload.get("colours") or [] if isinstance(c, str) and HEX_RE.match(c)]
        if not colours:
            raise _fail("A palette needs at least one #rrggbb colour.")
        return {"colours": list(dict.fromkeys(colours))[:16]}
    # template
    board = payload.get("board") if isinstance(payload.get("board"), dict) else {}
    out: dict[str, Any] = {"board": {
        "type": board.get("type") if board.get("type") in ("board", "map") else "board",
        "layout": str(board.get("layout") or "")[:30] or None,
    }}
    if isinstance(board.get("theme"), dict):
        out["board"]["theme"] = board["theme"]
    background = board.get("background")
    if isinstance(background, dict):
        try:
            out["board"]["background"] = BoardBackground(**background).model_dump(exclude_none=True)
        except ValueError as err:
            logger.info("board library: a background did not validate: %s", err)
            raise _fail("A template's background is not valid.") from None
    if payload.get("element"):
        out["element"] = _clean_element(payload["element"])
    if payload.get("branch"):
        out["branch"] = _clean_branch(payload["branch"])
    if "element" not in out and "branch" not in out:
        raise _fail("A template needs something on it.")
    return out


def _clean_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    out = []
    for tag in tags:
        text = str(tag).strip().lower()[:40]
        if text and text not in out:
            out.append(text)
    return out[:MAX_TAGS]


# --- built-ins ---------------------------------------------------------------


#: The converted draw.io sets (WHITEBOARD_PLAN decision 4) sit one folder
#: down so the panel's first open does not fetch their 0.37 MB; the panel
#: lists them as closed groups and fetches one when it is opened or searched.
#: Names are the panel's words, not the converter's `mxgraph.*` source name.
SHAPE_SET_NAMES = {
    "drawio-basic": "Basic shapes", "drawio-flowchart": "Flowchart, more",
    "drawio-arrows": "Arrows, more", "drawio-bpmn": "BPMN", "drawio-networks": "Network and cloud",
}


@lru_cache(maxsize=1)
def _shape_sets() -> list[dict]:
    out = []
    for path in sorted((BUILTIN_DIR / "drawio").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        key = data.get("key", path.stem)
        out.append({"key": key, "name": SHAPE_SET_NAMES.get(key, data.get("name", key)),
                    "count": len(data.get("items") or []), "path": f"drawio/{path.name}"})
    order = list(SHAPE_SET_NAMES)
    return sorted(out, key=lambda s: order.index(s["key"]) if s["key"] in order else len(order))


@lru_cache(maxsize=1)
def _builtin_index() -> dict[str, dict]:
    """Every built-in entry by `"<set>/<key>"`, read once per process."""
    out: dict[str, dict] = {}
    if not BUILTIN_DIR.is_dir():
        return out
    for path in sorted([*BUILTIN_DIR.glob("*.json"), *(BUILTIN_DIR / "drawio").glob("*.json")]):
        if path.stem in ("index", "icons"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        key = data.get("key", path.stem)
        for entry in data.get("items") or []:
            if isinstance(entry.get("payload"), dict):
                entry = {**entry, "payload": {**entry["payload"], "items": drawings_under_cards(entry["payload"].get("items") or [])}}
            out[f"{key}/{entry['key']}"] = {**entry, "set": SHAPE_SET_NAMES.get(key, data.get("name", path.stem))}
    return out


def drawings_under_cards(items: list) -> list:
    """A stencil drawn when drawings were one layer under every card keeps
    that look (WHITEBOARD_PLAN decision 43, the owner 2026-10-27: "each
    stroke stacks"). The built-in sets give a drawing z 5 and a card z 1, so
    with one order a shape would now cover the words on it: its drawings
    move under its lowest card, their own order kept. A stencil with no card
    or no drawing, or drawings already under the cards, is unchanged."""
    zs = lambda rows: [int(i.get("z") or 0) for i in rows]  # noqa: E731
    drawings = [i for i in items if isinstance(i, dict) and i.get("kind") == "sketch"]
    cards = [i for i in items if isinstance(i, dict) and i.get("kind") != "sketch" and i.get("type") != "frame"]
    if not drawings or not cards or max(zs(drawings)) < min(zs(cards)):
        return items
    shift = max(zs(drawings)) - min(zs(cards)) + 1
    return [{**i, "z": int(i.get("z") or 0) - shift} if i in drawings else i for i in items]


@lru_cache(maxsize=1)
def _icons() -> dict[str, str]:
    path = BUILTIN_DIR / "icons.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("icons") or {}
    except (OSError, ValueError):
        return {}


def _builtin(key: str) -> dict | None:
    if key.startswith("icons/"):
        name = key.split("/", 1)[1]
        d = _icons().get(name)
        if not d:
            return None
        return {
            "key": name, "kind": "element", "name": name.replace("-", " ").capitalize(), "tags": ["icon"], "set": "Icons",
            "payload": {"box": {"w": 96, "h": 96}, "items": [{
                "key": "i", "kind": "sketch", "z": 5,
                "data": {"d": d, "shape": "custom", "icon": name, "color": INK, "width": 0, "fill": INK, "fillOpacity": 1, "noStroke": True},
            }], "links": []},
        }
    return _builtin_index().get(key)


# --- the routes ----------------------------------------------------------------


class LibraryItemOut(BaseModel):
    id: int
    library_id: int
    kind: str
    name: str
    tags: list[str] = []
    payload: dict = {}
    favourite: bool = False
    use_count: int = 0
    last_used_at: datetime | None = None
    version: int = 1
    updated_at: datetime | None = None


def _item_out(row: BoardLibraryItem) -> LibraryItemOut:
    return LibraryItemOut(
        id=row.id, library_id=row.library_id, kind=row.kind, name=row.name, tags=row.tags or [],
        payload=row.payload or {}, favourite=bool(row.favourite), use_count=row.use_count or 0,
        last_used_at=row.last_used_at, version=row.version or 1, updated_at=row.updated_at,
    )


def _yours(db: Session) -> BoardLibrary:
    """The default library, made the first time anything asks for it."""
    row = db.scalar(select(BoardLibrary).where(BoardLibrary.kind == "yours").order_by(BoardLibrary.id))
    if row is None:
        row = BoardLibrary(name="Yours", kind="yours", sort=0)
        db.add(row)
        db.flush()
    return row


def _library_out(row: BoardLibrary) -> dict:
    return {"id": row.id, "name": row.name, "kind": row.kind, "sort": row.sort}


@router.get("/board-library")
def list_library(
    response: Response,
    kind: str | None = None,
    q: str | None = None,
    library_id: int | None = None,
    favourites: bool = False,
    recent: bool = False,
    deleted: bool = False,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_session),
) -> dict:
    """The library: the person's libraries and items, the built-in sets'
    names (their entries are static files), and favourite and recent across
    both. With `q` or `kind`, built-in entries that match are listed too
    (the AI's `list_library` reads this; the panel filters on the client)."""
    yours = _yours(db)
    db.commit()
    libraries = db.scalars(select(BoardLibrary).order_by(BoardLibrary.sort, BoardLibrary.id)).all()
    query = select(BoardLibraryItem)
    query = query.where(BoardLibraryItem.deleted_at.is_not(None) if deleted else BoardLibraryItem.deleted_at.is_(None))
    query = query.where(BoardLibraryItem.kind == kind if kind else BoardLibraryItem.kind != SNIPPET_KIND)
    if library_id:
        query = query.where(BoardLibraryItem.library_id == library_id)
    if favourites:
        query = query.where(BoardLibraryItem.favourite.is_(True))
    rows = db.scalars(query.order_by(BoardLibraryItem.updated_at.desc(), BoardLibraryItem.id.desc())).all()
    words = (q or "").lower().split()

    def matches(name: str, tags: list[str]) -> bool:
        text = " ".join([name.lower(), *tags])
        return all(w in text for w in words)

    items = [_item_out(r) for r in rows if matches(r.name, r.tags or [])]
    #: A library grows with what the person saves: the newest `limit`, and
    #: the whole count in a header so a caller can tell it was cut.
    response.headers["X-Total-Count"] = str(len(items))
    items = items[:limit]
    marks = {m.key: {"favourite": bool(m.favourite), "use_count": m.use_count or 0,
                     "last_used_at": m.last_used_at.isoformat() if m.last_used_at else None}
             for m in db.scalars(select(BoardLibraryMark)).all()}
    used = [(r.last_used_at, f"item:{r.id}") for r in rows if r.last_used_at]
    used += [(m.last_used_at, f"builtin:{m.key}") for m in db.scalars(select(BoardLibraryMark)).all() if m.last_used_at]
    out: dict[str, Any] = {
        "yours_id": yours.id,
        "libraries": [_library_out(lib) for lib in libraries],
        "items": [i.model_dump(mode="json") for i in items],
        "marks": marks,
        "recent": [ref for _, ref in sorted(used, reverse=True)[:RECENT_LIMIT]],
    }
    try:
        out["sets"] = json.loads((BUILTIN_DIR / "index.json").read_text(encoding="utf-8")).get("sets", [])
    except (OSError, ValueError):
        out["sets"] = []
    out["shape_sets"] = _shape_sets()
    if words or kind:
        builtins = []
        for key, entry in _builtin_index().items():
            if kind and entry.get("kind", "element") != kind:
                continue
            if matches(entry.get("name", ""), entry.get("tags") or []):
                builtins.append({"key": key, "name": entry.get("name"), "set": entry.get("set"), "kind": entry.get("kind", "element")})
        if words and (not kind or kind == "element"):
            for name in _icons():
                if matches(name.replace("-", " "), ["icon"]):
                    builtins.append({"key": f"icons/{name}", "name": name.replace("-", " ").capitalize(), "set": "Icons", "kind": "element"})
                    if len(builtins) > 200:
                        break
        out["builtins"] = builtins[:200]
    return out


class LibraryItemCreate(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=MAX_NAME)
    tags: list[str] = []
    payload: dict
    library_id: int | None = None


def _library_or_404(db: Session, library_id: int | None) -> BoardLibrary:
    if library_id is None:
        return _yours(db)
    row = db.get(BoardLibrary, library_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That library could not be found.")
    return row


@router.post("/board-library", status_code=201)
@events.writes("library_item", "created")
def create_library_item(body: LibraryItemCreate, db: Session = Depends(get_session)) -> dict:
    library = _library_or_404(db, body.library_id)
    payload = _clean_payload(body.kind, body.payload)
    row = BoardLibraryItem(
        library_id=library.id, kind=body.kind, name=body.name.strip()[:MAX_NAME],
        tags=_clean_tags(body.tags), payload=payload, favourite=False, use_count=0, version=1,
    )
    db.add(row)
    db.flush()
    events.record(db, "created", "library_item", row.id, row.name[:80], payload={"after": {"name": row.name, "kind": row.kind}})
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")


class LibraryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    tags: list[str] | None = None
    payload: dict | None = None
    favourite: bool | None = None
    library_id: int | None = None


def _item_or_404(db: Session, item_id: int) -> BoardLibraryItem:
    row = db.get(BoardLibraryItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That library item could not be found.")
    return row


@router.put("/board-library/{item_id}")
@events.writes("library_item", "edited")
def update_library_item(item_id: int, body: LibraryItemUpdate, db: Session = Depends(get_session)) -> dict:
    row = _item_or_404(db, item_id)
    before = {"name": row.name, "tags": row.tags, "favourite": row.favourite, "version": row.version}
    if body.name is not None:
        row.name = body.name.strip()[:MAX_NAME]
    if body.tags is not None:
        row.tags = _clean_tags(body.tags)
    if body.favourite is not None:
        row.favourite = body.favourite
    if body.library_id is not None:
        row.library_id = _library_or_404(db, body.library_id).id
    if body.payload is not None:
        row.payload = _clean_payload(row.kind, body.payload)
        row.version = (row.version or 1) + 1
    row.updated_at = utcnow()
    events.record(db, "edited", "library_item", row.id, row.name[:80],
                  payload={"before": before, "after": {"name": row.name, "tags": row.tags, "favourite": row.favourite, "version": row.version}})
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")


@router.delete("/board-library/{item_id}")
@events.writes("library_item", "deleted")
def delete_library_item(item_id: int, db: Session = Depends(get_session)) -> dict:
    """Into the library's bin: `restore` brings it back (the toast's Undo)."""
    row = _item_or_404(db, item_id)
    row.deleted_at = utcnow()
    events.record(db, "deleted", "library_item", row.id, row.name[:80])
    db.commit()
    return {"id": row.id, "deleted": True}


#: Declared before `/{item_id}/restore`, which would take `libraries` for an id.
class LibraryRestoreBody(BaseModel):
    token: str = Field(min_length=1, max_length=64)


@router.post("/board-library/libraries/restore", status_code=201)
def restore_library(body: LibraryRestoreBody, db: Session = Depends(get_session)) -> dict:
    """Undo of `DELETE /board-library/libraries/{id}`: the library, and the items it held, back (INBOX 898)."""
    config = deps.get_config()
    saved, _ = undo_bin.take(config.data_dir, "board-library", body.token)
    data = saved["library"]
    library = undo_bin.row_from(BoardLibrary, data, keep_id=db.get(BoardLibrary, data["id"]) is None)
    db.add(library)
    db.flush()
    for item in saved["items"]:
        existing = db.get(BoardLibraryItem, item["id"])
        if existing is not None:
            existing.library_id = library.id
        elif saved["with_items"]:
            db.add(undo_bin.row_from(BoardLibraryItem, {**item, "library_id": library.id}))
    db.commit()
    db.refresh(library)
    undo_bin.finish(config.data_dir, body.token)
    return _library_out(library)


@router.post("/board-library/{item_id}/restore")
@events.writes("library_item", "restored")
def restore_library_item(item_id: int, db: Session = Depends(get_session)) -> dict:
    row = _item_or_404(db, item_id)
    row.deleted_at = None
    events.record(db, "restored", "library_item", row.id, row.name[:80])
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")


@router.post("/board-library/{item_id}/duplicate", status_code=201)
@events.writes("library_item", "created")
def duplicate_library_item(item_id: int, db: Session = Depends(get_session)) -> dict:
    src = _item_or_404(db, item_id)
    row = BoardLibraryItem(
        library_id=src.library_id, kind=src.kind, name=f"{src.name} (copy)"[:MAX_NAME], tags=list(src.tags or []),
        payload=json.loads(json.dumps(src.payload or {})), favourite=False, use_count=0, version=1,
    )
    db.add(row)
    db.flush()
    events.record(db, "created", "library_item", row.id, row.name[:80], payload={"after": {"name": row.name, "kind": row.kind}})
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")


class MarkBody(BaseModel):
    key: str = Field(min_length=3, max_length=120)
    favourite: bool


@router.post("/board-library/marks")
def mark_builtin(body: MarkBody, db: Session = Depends(get_session)) -> dict:
    """A built-in entry starred or unstarred."""
    if _builtin(body.key) is None:
        raise HTTPException(status_code=404, detail="That built-in shape could not be found.")
    mark = db.get(BoardLibraryMark, body.key) or BoardLibraryMark(key=body.key, favourite=False, use_count=0)
    mark.favourite = body.favourite
    db.add(mark)
    db.commit()
    return {"key": body.key, "favourite": mark.favourite}


class LibraryBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.post("/board-library/libraries", status_code=201)
def create_library(body: LibraryBody, db: Session = Depends(get_session)) -> dict:
    _yours(db)
    row = BoardLibrary(name=body.name.strip(), kind="custom", sort=1 + (db.scalar(select(BoardLibrary.sort).order_by(BoardLibrary.sort.desc())) or 0))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _library_out(row)


@router.put("/board-library/libraries/{library_id}")
def rename_library(library_id: int, body: LibraryBody, db: Session = Depends(get_session)) -> dict:
    row = _library_or_404(db, library_id)
    row.name = body.name.strip()
    db.commit()
    return _library_out(row)


@router.delete("/board-library/libraries/{library_id}")
def delete_library(library_id: int, with_items: bool = False, db: Session = Depends(get_session)) -> dict:
    """A library goes; what it held moves to Yours, so nothing saved is lost.

    `with_items` takes the items with it: Undo of an import (INBOX 898), whose
    library should not leave its contents behind in Yours. Either way the
    answer carries the token `POST /board-library/libraries/restore` takes.
    """
    row = _library_or_404(db, library_id)
    if row.kind == "yours":
        raise HTTPException(status_code=409, detail="Yours is where everything you save goes; it stays.")
    held = db.scalars(select(BoardLibraryItem).where(BoardLibraryItem.library_id == row.id)).all()
    saved = {"library": undo_bin.row_dict(row), "with_items": with_items, "items": [undo_bin.row_dict(i) for i in held]}
    moved = 0
    if with_items:
        for item in held:
            db.delete(item)
        db.flush()  # the items go before the library they point at
    else:
        yours = _yours(db)
        for item in held:
            item.library_id = yours.id
            moved += 1
    db.flush()
    db.delete(row)
    token = undo_bin.stash(deps.get_config().data_dir, "board-library", saved)
    db.commit()
    return {"deleted": library_id, "moved": moved, "undo_token": token}


@router.get("/board-library/export")
def export_library(library_id: int | None = None, db: Session = Depends(get_session)) -> Response:
    """`memorymap-library-1.json`: one library and its live items."""
    library = _library_or_404(db, library_id)
    db.commit()
    rows = db.scalars(
        select(BoardLibraryItem).where(
            BoardLibraryItem.library_id == library.id,
            BoardLibraryItem.deleted_at.is_(None),
            BoardLibraryItem.kind != SNIPPET_KIND,
        )
    ).all()
    body = {
        "format": EXPORT_FORMAT,
        "version": 1,
        "library": {"name": library.name},
        "items": [{"kind": r.kind, "name": r.name, "tags": r.tags or [], "payload": r.payload or {}} for r in rows],
    }
    safe = re.sub(r"[^A-Za-z0-9 _-]+", "", library.name).strip() or "Library"
    return Response(
        content=json.dumps(body, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe}.memorymap-library.json"'},
    )


class ImportBody(BaseModel):
    format: str
    version: int = 1
    library: dict = {}
    items: list[dict] = []


@router.post("/board-library/import", status_code=201)
@events.writes("library_item", "imported")
def import_library(body: ImportBody, db: Session = Depends(get_session)) -> dict:
    """A library file into a new library named from it. New ids throughout;
    a picture this notebook does not have is dropped and counted."""
    if body.format != EXPORT_FORMAT or body.version != 1:
        raise _fail("This is not a Tessellate library file.")
    if len(body.items) > 2000:
        raise _fail("A library file holds at most 2,000 items.")
    have = {f"/media/{name}" for name in db.scalars(select(MediaUpload.filename)).all()}
    name = str(body.library.get("name") or "Imported")[:80].strip() or "Imported"
    _yours(db)
    library = BoardLibrary(name=name, kind="imported", sort=1 + (db.scalar(select(BoardLibrary.sort).order_by(BoardLibrary.sort.desc())) or 0))
    db.add(library)
    db.flush()
    made, skipped, dropped_media = 0, 0, 0
    for raw in body.items:
        kind = raw.get("kind")
        payload = raw.get("payload")
        if not isinstance(payload, dict) or kind not in ITEM_KINDS:
            skipped += 1
            continue
        missing = [u for u in _media_urls(payload) if u not in have]
        if missing:
            dropped_media += len(missing)
            payload = _drop_media(payload, set(missing))
        try:
            clean = _clean_payload(kind, payload)
        except HTTPException:
            skipped += 1
            continue
        db.add(BoardLibraryItem(
            library_id=library.id, kind=kind, name=str(raw.get("name") or "Untitled")[:MAX_NAME],
            tags=_clean_tags(raw.get("tags")), payload=clean, favourite=False, use_count=0, version=1,
        ))
        made += 1
    events.record(db, "imported", "library_item", library.id, f"{made} into {name}"[:80],
                  payload={"after": {"library": name, "items": made, "skipped": skipped, "dropped_media": dropped_media}})
    db.commit()
    return {"library": _library_out(library), "items": made, "skipped": skipped, "dropped_media": dropped_media}


def _drop_media(payload: dict, missing: set[str]) -> dict:
    """The payload without the items whose picture is not in this notebook."""
    def keep(item: Any) -> bool:
        return not (isinstance(item, dict) and any(u in missing for u in _media_urls(item)))

    out = dict(payload)
    if isinstance(out.get("items"), list):
        out["items"] = [i for i in out["items"] if keep(i)]
        keys = {i.get("key") for i in out["items"] if isinstance(i, dict)}
        out["links"] = [lk for lk in out.get("links") or [] if isinstance(lk, dict) and lk.get("from") in keys and lk.get("to") in keys]
    return json.loads(re.sub(r"/media/[A-Za-z0-9][A-Za-z0-9._-]{0,119}", lambda m: "" if m.group(0) in missing else m.group(0), json.dumps(out)))


# --- placing --------------------------------------------------------------------

_PATH_TOKEN = re.compile(r"[MmLlCcQqTtSsHhVvAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "T": 2, "C": 6, "S": 4, "Q": 4, "H": 1, "V": 1, "A": 7, "Z": 0}


def transform_path(d: str, sx: float = 1.0, sy: float = 1.0, dx: float = 0.0, dy: float = 0.0) -> str:
    """A path scaled about the origin then moved: absolute points map, relative
    ones scale, arc radii scale. The board's grammar (whiteboard.js's
    `wbTransformPathD`) plus the rest of SVG's, so a saved path round-trips."""
    tokens = _PATH_TOKEN.findall(d or "")
    out: list[str] = []
    i = 0
    cmd = None

    def num(v: float) -> str:
        text = f"{v:.2f}".rstrip("0").rstrip(".")
        return text if text not in ("-0", "") else "0"

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
            out.append(cmd)
            if cmd in "Zz":
                continue
        elif cmd is None:
            break
        n = _ARGS[cmd.upper()]
        args = []
        for _ in range(n):
            if i >= len(tokens) or tokens[i].isalpha():
                break
            args.append(float(tokens[i]))
            i += 1
        if len(args) < n:
            break
        rel = cmd.islower()
        up = cmd.upper()
        if up == "A":
            rx, ry, rot, large, sweep, x, y = args
            px, py = (x * sx, y * sy) if rel else (x * sx + dx, y * sy + dy)
            out += [num(abs(rx * sx)), num(abs(ry * sy)), num(rot), str(int(large)), str(int(sweep)), num(px), num(py)]
        elif up == "H":
            out.append(num(args[0] * sx if rel else args[0] * sx + dx))
        elif up == "V":
            out.append(num(args[0] * sy if rel else args[0] * sy + dy))
        else:
            for k in range(0, n, 2):
                x, y = args[k], args[k + 1]
                out += [num(x * sx), num(y * sy)] if rel else [num(x * sx + dx), num(y * sy + dy)]
        # A repeated pair after M is an implicit L.
        if cmd == "M":
            cmd = "L"
        elif cmd == "m":
            cmd = "l"
    return " ".join(out)


class PlaceBody(BaseModel):
    item_id: int | None = None
    builtin: str | None = Field(default=None, max_length=120)
    #: The centre of the placed box, in board units.
    x: float = 0.0
    y: float = 0.0
    #: A size to scale the item to (a shape dragged out larger); its own box
    #: when absent.
    w: float | None = Field(default=None, gt=0, le=8000)
    h: float | None = Field(default=None, gt=0, le=8000)
    #: The colour an `"ink"` placeholder becomes: the pen the person holds.
    ink: str | None = Field(default=None, max_length=7)
    #: A branch goes under this topic; absent, it is a new trunk.
    parent_id: int | None = None


def _resolve(db: Session, body: PlaceBody) -> tuple[dict, dict]:
    """(entry, library_ref) for what is being placed."""
    if body.item_id is not None:
        row = db.get(BoardLibraryItem, body.item_id)
        if row is None or row.deleted_at is not None:
            raise HTTPException(status_code=404, detail="That library item could not be found.")
        row.use_count = (row.use_count or 0) + 1
        row.last_used_at = utcnow()
        return ({"kind": row.kind, "name": row.name, "payload": row.payload or {}},
                {"id": row.id, "version": row.version or 1})
    if body.builtin:
        entry = _builtin(body.builtin)
        if entry is None:
            raise HTTPException(status_code=404, detail="That built-in shape could not be found.")
        mark = db.get(BoardLibraryMark, body.builtin) or BoardLibraryMark(key=body.builtin, favourite=False, use_count=0)
        mark.use_count = (mark.use_count or 0) + 1
        mark.last_used_at = utcnow()
        db.add(mark)
        return entry, {"builtin": body.builtin}
    raise _fail("Say what to place: an item id or a built-in key.")


def _ink(value: Any, ink: str) -> Any:
    return ink if value == INK else value


def _place_sketch_part(db: Session, board_id: int | None, item: dict, geo: tuple, ink: str, ref: dict,
                       group_id: str | None) -> WhiteboardSketch:
    sx, sy, left, top = geo
    data = dict(item["data"])
    if "d" in data:
        data["d"] = transform_path(data["d"], sx, sy, left, top)
    for key in ("color", "fill"):
        if key in data:
            data[key] = _ink(data[key], ink)
    if isinstance(data.get("width"), (int, float)) and data["width"] and sx != 1:
        data["width"] = max(1, round(data["width"] * min(sx, sy) ** 0.5, 1))
    data["library_ref"] = ref
    row = WhiteboardSketch(board_id=board_id, data=json.dumps(data), x=0, y=0, z=int(item.get("z", 5)),
                           group_id=group_id)
    db.add(row)
    db.flush()
    return row


def _place_object_part(db: Session, board_id: int | None, item: dict, geo: tuple, ink: str, ref: dict,
                       group_id: str | None) -> WhiteboardObject:
    sx, sy, left, top = geo
    data = dict(item["data"])
    for key in ("color", "bg", "border_color"):
        if key in data:
            data[key] = _ink(data[key], ink)
    row = WhiteboardObject(
        board_id=board_id, kind=item["type"],
        data=json.dumps({**WhiteboardObjectData(**data).model_dump(exclude_none=True), "library_ref": ref}),
        x=left + item["x"] * sx, y=top + item["y"] * sy, z=int(item.get("z", 1)),
        width=max(20.0, item["w"] * sx), height=max(20.0, item["h"] * sy),
        rotation=item.get("rotation"), group_id=group_id,
    )
    db.add(row)
    db.flush()
    return row


def _place_link_part(db: Session, board_id: int | None, link: dict, ends: tuple, geo: tuple, ink: str,
                     ref: dict) -> WhiteboardSketch:
    a, b = ends
    sx, sy, left, top = geo
    data = dict(link["data"])
    for key in ("color",):
        if key in data:
            data[key] = _ink(data[key], ink)
    if isinstance(data.get("bend"), dict):
        data["bend"] = {"x": float(data["bend"].get("x", 0)) * sx, "y": float(data["bend"].get("y", 0)) * sy}
    # An elbow's bends (Phase B) were saved from the box's corner.
    if isinstance(data.get("points"), list):
        data["points"] = [
            {"x": left + float(p.get("x", 0)) * sx, "y": top + float(p.get("y", 0)) * sy}
            for p in data["points"][:50]
            if isinstance(p, dict)
        ]
    data.update(sourceId=a[1], sourceKind=a[0], targetId=b[1], targetKind=b[0], library_ref=ref)
    row = WhiteboardSketch(board_id=board_id, data=json.dumps(data), x=0, y=0, z=1)
    db.add(row)
    db.flush()
    return row


def _grouped_parts(payload: dict) -> list[dict]:
    """A multi-part element is one thing on the board: with no group named by
    the stencil itself, its parts share one, so a move or a resize takes
    them all (INBOX 1307). Ungroup still splits it."""
    parts = payload.get("items") or []
    if len(parts) > 1 and not any(p.get("group") for p in parts):
        parts = [{**p, "group": "_whole"} for p in parts]
    return parts


def _place_parts(db: Session, board_id: int | None, parts: list[dict], geo: tuple, ink: str, ref: dict,
                 ids: dict) -> tuple[list, list]:
    """Place each sketch and object part, sharing one fresh group id per named
    group; fills `ids` (stencil key to kind and row id) for the links."""
    groups: dict[str, str] = {}

    def group_for(raw: str | None) -> str | None:
        if not raw:
            return None
        groups.setdefault(raw, uuid.uuid4().hex[:24])
        return groups[raw]

    made_sketches, made_objects = [], []
    for item in parts:
        if item["kind"] == "sketch":
            row = _place_sketch_part(db, board_id, item, geo, ink, ref, group_for(item.get("group")))
            made_sketches.append(row)
            ids[item["key"]] = ("sketch", row.id)
        else:
            row = _place_object_part(db, board_id, item, geo, ink, ref, group_for(item.get("group")))
            made_objects.append(row)
            ids[item["key"]] = ("object", row.id)
    return made_sketches, made_objects


def _place_element(db: Session, board_id: int | None, payload: dict, body: PlaceBody, ref: dict) -> dict:
    box = payload.get("box") or {"w": 100, "h": 100}
    bw, bh = max(1.0, float(box.get("w", 100))), max(1.0, float(box.get("h", 100)))
    sx = (body.w / bw) if body.w else 1.0
    sy = (body.h / bh) if body.h else 1.0
    geo = (sx, sy, body.x - bw * sx / 2, body.y - bh * sy / 2)
    ink = body.ink if body.ink and BOARD_BG_COLOR_RE.match(body.ink) else "#3355ff"
    ids: dict = {}
    made_sketches, made_objects = _place_parts(db, board_id, _grouped_parts(payload), geo, ink, ref, ids)
    for link in payload.get("links") or []:
        a, b = ids.get(link["from"]), ids.get(link["to"])
        if a and b:
            made_sketches.append(_place_link_part(db, board_id, link, (a, b), geo, ink, ref))
    return {"sketches": made_sketches, "objects": made_objects}


def _map_has_no_centre(db: Session, board_id: int | None) -> bool:
    """True for a map board with no topic that is a root. A board that is not
    a map has no centre to want, and a map with one already has its trunk."""
    if board_id is None:
        return False
    entry = db.get(Entry, board_id)
    if entry is None or _board_settings(entry)[0] != "map":
        return False
    roots = db.scalar(
        select(WhiteboardObject.id)
        .where(WhiteboardObject.board_id == board_id, WhiteboardObject.parent_id.is_(None),
               WhiteboardObject.kind.in_(MAP_REFERENCE_KINDS | {MAP_TOPIC_KIND}))
        .limit(1)
    )
    return roots is None


def _place_branch(db: Session, board_id: int | None, payload: dict, body: PlaceBody, ref: dict,
                  name: str | None = None) -> dict:
    parent = None
    if body.parent_id is not None:
        parent = db.get(WhiteboardObject, body.parent_id)
        if parent is None or parent.board_id != board_id or parent.kind not in MAP_REFERENCE_KINDS | {MAP_TOPIC_KIND}:
            raise HTTPException(status_code=404, detail="That topic is not on this board.")
    made = []
    # A sideways tree: each leaf takes the next row, and a topic with children
    # sits on its first child's row. The row was `parent's row + i`, so the
    # second child of one topic and the first child of the next landed on the
    # same spot (the Decision template's "Option B" under "Cost"), which a map
    # with no layout to tidy it kept as one box on another (INBOX 664).
    rows = [0]

    def add(node: dict, parent_id: int | None, depth: int) -> int:
        data = {**node.get("data", {}), "content": node.get("text", ""), "library_ref": ref}
        row = WhiteboardObject(
            board_id=board_id, kind="topic", data=json.dumps(WhiteboardObjectData(**{k: v for k, v in data.items() if k != "library_ref"}).model_dump(exclude_none=True) | {"library_ref": ref}),
            x=body.x + depth * 220, y=body.y, z=1, width=180, height=48, parent_id=parent_id,
        )
        db.add(row)
        db.flush()
        made.append(row)
        kids = [add(child, row.id, depth + 1) for child in node.get("children") or []]
        if kids:
            at = kids[0]
        else:
            at = rows[0]
            rows[0] += 1
        row.y = body.y + at * 70
        return at

    nodes = list(payload.get("nodes") or [])
    #: A branch placed on a map with no central topic (INBOX 670) used to make
    #: one trunk per top-level topic. One top-level topic is already the centre
    #: (it has no parent); several go under a new centre named after the
    #: template, so a map has the one trunk it is built around.
    if parent is None and len(nodes) > 1 and _map_has_no_centre(db, board_id):
        #: A built-in template says how its centre is drawn (`payload.root`,
        #: K15): the preview shows a root box or an oval, so the map built
        #: from it does too.
        nodes = [{"text": (name or "Map").strip()[:200] or "Map", "data": dict(payload.get("root") or {}), "children": nodes}]
    for node in nodes:
        add(node, parent.id if parent is not None else None, 1 if parent is not None else 0)
    return {"sketches": [], "objects": made}


def _band_tops(db: Session, board_id: int | None, made: dict) -> tuple[int, list[int]]:
    """The highest z already on the board among the drawings and cards (one
    band since decision 43: notes, boxes, pictures, tables and strokes), and
    the frames' z values, leaving out the rows just placed."""
    here = (lambda col: col.is_(None)) if board_id is None else (lambda col: col == board_id)
    sketch_top = db.scalar(
        select(func.max(WhiteboardSketch.z)).where(here(WhiteboardSketch.board_id), WhiteboardSketch.id.not_in({r.id for r in made["sketches"]}))
    )
    note_top = db.scalar(select(func.max(WhiteboardNode.z)).where(here(WhiteboardNode.board_id)))
    others = db.scalars(
        select(WhiteboardObject).where(here(WhiteboardObject.board_id), WhiteboardObject.id.not_in({r.id for r in made["objects"]}))
    ).all()
    top = max([0, sketch_top or 0, note_top or 0, *[o.z or 0 for o in others if o.kind != "frame"]])
    return top, [o.z or 0 for o in others if o.kind == "frame"]


def _stack_on_top(db: Session, board_id: int | None, made: dict) -> None:
    """Put placed rows on top of what is already on the board, keeping the
    stencil's own order among them (wb5).

    A stencil carries small fixed z values (a drawing 5, a card 1, a link 1),
    so a placement landed under, or tied with, anything already drawn above
    them. The board's stacking (`wbStackOrder` in whiteboard.js) is two
    bands: frames, then drawings and cards together (decision 43); each
    placed row takes the next z of its band in the stencil's order (z, then
    drawings before cards, as a tie paints), frames under the frames already
    there, as one drawn by hand does (`wbStackNewZ`)."""
    top, frame_zs = _band_tops(db, board_id, made)
    rank = {"sketch": 0, "object": 2}
    by_stencil = lambda pair: (pair[1].z or 0, rank[pair[0]], pair[1].id)  # noqa: E731
    frames = sorted((("object", r) for r in made["objects"] if r.kind == "frame"), key=by_stencil)
    rest = sorted([*(("sketch", r) for r in made["sketches"]), *(("object", r) for r in made["objects"] if r.kind != "frame")], key=by_stencil)
    for rows, first in (
        (frames, (min(frame_zs) - len(frames)) if frame_zs else 0),
        (rest, top + 1),
    ):
        for i, (_, row) in enumerate(rows):
            row.z = first + i
    db.flush()


def _onto_current_layer(db: Session, board_id: int | None, made: dict) -> None:
    """Placed rows go on the board's current layer, as anything drawn by hand
    does (canvasdepth2, `_on_current_layer`)."""
    for row in made["sketches"] + made["objects"]:
        row.data = json.dumps(_on_current_layer(db, board_id, json.loads(row.data)))


@router.post("/whiteboard/boards/{board_id}/place", status_code=201)
def place_library_item(board_id: int, body: PlaceBody, db: Session = Depends(get_session)) -> dict:
    """Make a library item's rows on a board, in one transaction: one board
    event naming the placement and its rows, and each row's own `created`
    event, so every placed item replays like one drawn by hand (the board's
    time machine reads them; WHITEBOARD_PLAN decision 33). It was one
    `@events.writes` scope, which folded the rows' events into the board's
    with their values dropped, so a placed item had no log of its own.
    `board_id` 0 is the default scratch board. A template is not placed; it
    starts a board (`/board-library/new-board`)."""
    target = None if board_id == 0 else board_id
    if target is not None:
        entry = db.get(Entry, target)
        if entry is None or entry.is_deleted:
            raise HTTPException(status_code=404, detail="That board could not be found.")
        entry.is_board = True
    entry_data, ref = _resolve(db, body)
    kind = entry_data.get("kind", "element")
    payload = entry_data.get("payload") or {}
    if kind in ("element", "shape", "preset"):
        made = _place_element(db, target, payload, body, ref)
    elif kind == "branch":
        made = _place_branch(db, target, payload, body, ref, entry_data.get("name"))
    elif kind == "template":
        if payload.get("element"):
            made = _place_element(db, target, payload["element"], body, ref)
        elif payload.get("branch"):
            made = _place_branch(db, target, payload["branch"], body, ref, entry_data.get("name"))
        else:
            made = {"sketches": [], "objects": []}
    else:
        raise _fail("A style or a palette is applied to what is selected, not placed.")
    _stack_on_top(db, target, made)
    _onto_current_layer(db, target, made)
    events.record(
        db, "placed", "board", target, f"{entry_data.get('name', 'item')} placed"[:80],
        payload={"after": {"library_ref": ref, "sketches": [{"id": s.id, **_sketch_state(s)} for s in made["sketches"]],
                           "objects": [{"id": o.id, **_object_state(o)} for o in made["objects"]]}},
    )
    for s in made["sketches"]:
        events.record(db, "created", "whiteboard_sketch", s.id, f"drawing on board {target} (library)",
                      payload={"after": _sketch_state(s)})
    for o in made["objects"]:
        events.record(db, "created", "whiteboard_object", o.id, f"{o.kind} on board {target} (library)",
                      payload={"after": _object_state(o)})
    db.commit()
    for row in made["sketches"] + made["objects"]:
        db.refresh(row)
    return {
        "name": entry_data.get("name"),
        "sketches": [{"id": s.id, "board_id": s.board_id, "data": s.data, "x": s.x, "y": s.y, "z": s.z, "group_id": s.group_id} for s in made["sketches"]],
        "objects": [_object_to_out(o).model_dump(mode="json") for o in made["objects"]],
    }


MAX_PASTE_ITEMS = 500


class PasteItem(BaseModel):
    """One copied thing. `key` is the client's name for it, so a copied link
    can name the two ends (`src`, `dst`) without knowing their new ids."""

    key: str = Field(min_length=1, max_length=40)
    object: WhiteboardObjectBase | None = None
    sketch: WhiteboardSketchBase | None = None
    src: str | None = Field(default=None, max_length=40)
    dst: str | None = Field(default=None, max_length=40)


class PasteBody(BaseModel):
    items: list[PasteItem] = Field(min_length=1, max_length=MAX_PASTE_ITEMS)


def _point_link_ends(parsed: dict, item: PasteItem, keys: dict[str, tuple[str, int]]) -> None:
    """Point a copied link's ends at the rows its pasted ends became."""
    for end, key in (("source", item.src), ("target", item.dst)):
        if key and key in keys:
            parsed[f"{end}Kind"], parsed[f"{end}Id"] = keys[key]


def _paste_object(db: Session, target: int | None, item: PasteItem, keys: dict[str, tuple[str, int]]) -> WhiteboardObject:
    b = item.object
    _require_object_data(b)
    row = WhiteboardObject(
        kind=b.kind, board_id=target, x=b.x, y=b.y, z=b.z, width=b.width, height=b.height,
        rotation=b.rotation, group_id=b.group_id,
        data=json.dumps(_on_current_layer(db, target, b.data.model_dump(mode="json", exclude_none=True)), separators=(",", ":")),
    )
    db.add(row)
    db.flush()
    keys[item.key] = ("object", row.id)
    return row


def _paste_sketch(db: Session, target: int | None, item: PasteItem, keys: dict[str, tuple[str, int]]) -> WhiteboardSketch:
    b = item.sketch
    try:
        parsed = json.loads(b.data)
    except ValueError:
        parsed = None
    data = b.data
    if isinstance(parsed, dict):
        _point_link_ends(parsed, item, keys)
        data = json.dumps(_on_current_layer(db, target, parsed))
    row = WhiteboardSketch(board_id=target, data=data, x=b.x, y=b.y, z=b.z, group_id=b.group_id)
    db.add(row)
    db.flush()
    keys[item.key] = ("sketch", row.id)
    return row


def _process_pasted_images(db: Session, made_objects: list) -> None:
    from tessellate.core import media_process

    for o in made_objects:
        if o.kind == "image":
            media_process.process_referenced_uploads(db, deps.get_config().data_dir / "media", o.data)


def _record_paste(db: Session, board_id: int, made_sketches: list, made_objects: list) -> None:
    """One event for the paste, then one per row made, so each undoes alone."""
    events.record(db, "placed", "board", board_id, "pasted items",
                  payload={"after": {"sketches": [s.id for s in made_sketches], "objects": [o.id for o in made_objects]}})
    for s in made_sketches:
        events.record(db, "created", "whiteboard_sketch", s.id, f"drawing on board {board_id} (paste)",
                      payload={"after": _sketch_state(s)})
    for o in made_objects:
        events.record(db, "created", "whiteboard_object", o.id, f"{o.kind} on board {board_id} (paste)",
                      payload={"after": _object_state(o)})


@router.post("/whiteboard/boards/{board_id}/paste", status_code=201)
def paste_board_items(board_id: int, body: PasteBody, db: Session = Depends(get_session)) -> dict:
    """**A paste is one request** (WHITEBOARD_PLAN 1355): the copied objects
    and sketches are made in one transaction, then each copied link is made
    with its two ends pointed at the new rows, so a fifty-item paste is one
    round trip rather than fifty and a link between copies stays a link.
    `keys` maps each item's client key to its new kind and id."""
    target = None if board_id == 0 else board_id
    _require_board(db, target)
    keys: dict[str, tuple[str, int]] = {}
    made_objects, made_sketches = [], []

    # Links last: their ends have to exist before they can point at them.
    # An object has no ends: a stray src or dst is ignored, never a silent drop.
    made_objects.extend(_paste_object(db, target, item, keys) for item in body.items if item.object)
    for linked in (False, True):
        made_sketches.extend(
            _paste_sketch(db, target, item, keys)
            for item in body.items
            if item.sketch and bool(item.src or item.dst) == linked
        )
    _record_paste(db, board_id, made_sketches, made_objects)
    db.commit()
    for row in made_sketches + made_objects:
        db.refresh(row)
    _process_pasted_images(db, made_objects)
    return {
        "keys": {k: {"kind": v[0], "id": v[1]} for k, v in keys.items()},
        "sketches": [{"id": s.id, "board_id": s.board_id, "data": s.data, "x": s.x, "y": s.y, "z": s.z, "group_id": s.group_id} for s in made_sketches],
        "objects": [_object_to_out(o).model_dump(mode="json") for o in made_objects],
    }


class NewBoardBody(BaseModel):
    item_id: int | None = None
    builtin: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=100)
    ink: str | None = Field(default=None, max_length=7)


@router.post("/board-library/new-board", status_code=201)
@events.writes("board", "created")
def new_board_from_template(body: NewBoardBody, db: Session = Depends(get_session)) -> dict:
    """A board started from a template: its kind, layout, theme and look, then
    its content placed at the origin. A built-in element (a Kanban, a SWOT)
    is a template for a plain board."""
    probe = PlaceBody(item_id=body.item_id, builtin=body.builtin, x=0, y=0, ink=body.ink)
    entry_data, ref = _resolve(db, probe)
    payload = entry_data.get("payload") or {}
    kind = entry_data.get("kind", "element")
    settings = payload.get("board", {}) if kind == "template" else {"type": "branch" if kind == "branch" else "board"}
    #: A built-in map template names the layout it is drawn for (INBOX 715:
    #: a fishbone to the left, pros and cons on both sides, a brainstorm
    #: round its centre), so the map it starts is the shape its preview was.
    if kind == "branch" and entry_data.get("layout") in BOARD_LAYOUTS:
        settings["layout"] = entry_data["layout"]
    board_type = "map" if settings.get("type") in ("map", "branch") else "board"
    name = body.name.strip()
    entry = Entry(content=f"# {name}", is_board=True)
    _store_board_settings(entry, board_type, settings.get("layout") or ("tree-right" if board_type == "map" else None))
    if settings.get("theme"):
        _store_board_theme(entry, settings["theme"])
    if settings.get("background"):
        _store_board_background(entry, BoardBackground(**settings["background"]))
    db.add(entry)
    db.flush()
    events.record(db, "created", "board", entry.id, name[:80], payload={"after": {"title": name, "type": board_type, "from": ref}})
    if kind in ("element", "shape", "preset"):
        box = payload.get("box") or {}
        probe.x, probe.y = float(box.get("w", 0)) / 2, float(box.get("h", 0)) / 2
        _place_element(db, entry.id, payload, probe, ref)
    elif kind == "branch":
        #: The central topic is the map's own name, as a blank map's is.
        _place_branch(db, entry.id, payload, probe, ref, name)
    elif payload.get("element"):
        box = payload["element"].get("box") or {}
        probe.x, probe.y = float(box.get("w", 0)) / 2, float(box.get("h", 0)) / 2
        _place_element(db, entry.id, payload["element"], probe, ref)
    elif payload.get("branch"):
        _place_branch(db, entry.id, payload["branch"], probe, ref, entry_data.get("name"))
    db.commit()
    board_type, layout = _board_settings(entry)
    return {"id": entry.id, "title": name, "type": board_type, "layout": layout}
