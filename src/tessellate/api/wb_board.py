"""A board as a whole: its lookups, state route, settings, theme, layers, background, and the models a board
is read and created with.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from tessellate.repo.content import BOARDS
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException
from tessellate.core.database import Entry, LIKE_ESCAPE, WhiteboardNode, WhiteboardObject, WhiteboardSketch
from sqlalchemy.orm import Session
from datetime import datetime
from tessellate.core.deps import get_session
from sqlalchemy import or_, select
from tessellate.api.wb_model import BOARD_LAYOUTS, BOARD_TYPES, DEFAULT_BOARD_LAYOUT, DEFAULT_BOARD_TYPE, MAP_APP_DEFAULT_PINS, MAP_LEVELS, MAP_LEVEL_FIELDS, MAP_LEVEL_THEME_FIELDS, MAP_THEME_FIELDS, MAP_THEME_FONT_RANGE, MEDIA_URL_RE, WhiteboardSketchOut, WhiteboardStateOut, _object_to_out

router = APIRouter()


def _board_filter(model, board_id: int | None):
    """`board_id = N`, or `IS NULL` for the unnamed scratch board.

    `== None` renders as `= NULL` in SQL, which is never true for any row, so
    the default board came back empty however much was on it. SQLAlchemy's
    `is_()` is the difference between a working board and a blank one.
    """
    return model.board_id.is_(None) if board_id is None else model.board_id == board_id


def _forget_links_to(
    db: Session,
    board_id: int | None,
    kind: str,
    item_id: int,
    into: list[dict] | None = None,
) -> int:
    """Delete the link sketches on a board whose either end was the item just
    deleted. Links live as sketch rows whose JSON `data` names their ends
    (`sourceId`/`targetId` plus a `sourceKind`/`targetKind` of "node",
    "object" or "sketch", "node" when absent); the frontend already skips a
    link whose end is gone, so without this a deleted card left an invisible
    orphan row behind forever. One linear pass over the board's sketches: 
    boards are hundreds of rows, not millions. Returns how many went.

    `into`, when given, collects each removed link as a sketch row
    (`WhiteboardSketchOut`) first. A branch deleted from a map hands those
    back with its topics, because a link to a topic is half of what a restore
    has to put back (INBOX 445, found by the second audit)."""
    rows = db.scalars(select(WhiteboardSketch).where(_board_filter(WhiteboardSketch, board_id))).all()
    gone = 0
    for row in rows:
        try:
            data = json.loads(row.data or "{}")
        except (TypeError, ValueError):
            continue
        # A sketch's `data` is whatever was stored in it, and only a link
        # sketch is an object with a `type`. A drawing saved as a bare JSON
        # array (which the API accepts and an import can produce) used to
        # reach `.get` on a list here and raise, turning a card's deletion
        # into a 500 because of an unrelated sketch on the same board.
        if not isinstance(data, dict) or not str(data.get("type", "")).startswith("link-"):
            continue
        ends = (
            (data.get("sourceId"), data.get("sourceKind") or "node"),
            (data.get("targetId"), data.get("targetKind") or "node"),
        )
        if any(end_id == item_id and end_kind == kind for end_id, end_kind in ends):
            if into is not None and all(link["id"] != row.id for link in into):
                into.append(WhiteboardSketchOut.model_validate(row).model_dump())
            db.delete(row)
            gone += 1
    return gone


def _require_entry(session: Session, entry_id: int) -> Entry:
    entry = session.get(Entry, entry_id)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    return entry


def _require_board(session: Session, board_id: int | None) -> None:
    """A board is a note too, and `board_id` is a real foreign key
    (`PRAGMA foreign_keys=ON`), writing one that doesn't exist doesn't fail
    quietly, it throws `IntegrityError` out of `db.commit()` as a raw 500. A
    board note purged (or hard-deleted) out from under a stale client-side
    `currentBoardId` is exactly how that happens: nothing here re-validates
    the id on write the way `_require_entry` already does for `entry_id`.
    Checked the same permissive way `_board_filter` reads it: `None` always
    means the default scratch board, never "board 0".

    Also where an ordinary note gets permanently remembered as a board the
    first time anything is drawn on it, every node/sketch/object write with
    a real `board_id` already funnels through here, so this is the one
    place that sees "this note just became a board" regardless of which of
    the three it was. See `Entry.is_board`'s own comment for why that has to
    survive the board being emptied again later, not just recognise it now.
    """
    if board_id is None:
        return
    entry = BOARDS.writable(session, board_id)
    if not entry.is_board:
        entry.is_board = True
        session.commit()


@router.get("/", response_model=WhiteboardStateOut)
def get_whiteboard_state(
    board_id: int | None = None, db: Session = Depends(get_session)
) -> WhiteboardStateOut:
    nodes = db.scalars(
        select(WhiteboardNode).where(_board_filter(WhiteboardNode, board_id))
    ).all()
    sketches = db.scalars(
        select(WhiteboardSketch).where(_board_filter(WhiteboardSketch, board_id))
    ).all()
    objects = db.scalars(
        select(WhiteboardObject).where(_board_filter(WhiteboardObject, board_id))
    ).all()
    dropped = _drop_orphan_links(db, sketches, nodes, objects)
    if dropped:
        db.commit()
        sketches = [row for row in sketches if row.id not in dropped]
    #: A card whose note is in the bin is not drawn (it opened a note nobody could see); Restore
    #: brings it back, so the row and its links stay (the orphan pass above sees every card) and
    #: only the read leaves it out (INBOX 1747, row 10).
    binned = set(db.scalars(select(Entry.id).where(Entry.id.in_([n.entry_id for n in nodes]), Entry.is_deleted.is_(True))))
    return WhiteboardStateOut(
        nodes=[n for n in nodes if n.entry_id not in binned],
        sketches=list(sketches),
        objects=[_object_to_out(o) for o in objects],
        background=_board_background(db.get(Entry, board_id)) if board_id else {},
        layers=_board_layers(db.get(Entry, board_id)) if board_id else [],
    )


def _drop_orphan_links(db: Session, sketches, nodes, objects) -> set[int]:
    """Delete every link on this board whose named end no longer exists, and
    return the ids that went.

    **An integrity pass, because the delete paths cannot be the only guard.**
    Reported with a screenshot: a node "had a dangling curved edge to nowhere
    (an edge whose other end is a deleted node or a point)". Every *delete*
    route does call `_forget_links_to`, but a link's ends are ids inside a
    JSON blob, not foreign keys, so nothing at the database level enforces
    them, and any path that removes a row without going through those routes
    leaves the link behind. One such path is live and was measured: purging a
    note deletes its `WhiteboardNode` rows in bulk (`entry/manager.py`), and
    the link sketch that pointed at the card survived with an id that resolves
    to nothing.

    Doing it on load rather than on write is deliberate. It is the one moment
    the whole board is already in memory, so the check costs no extra query;
    it catches an orphan whatever created it, including one already sitting in
    a notebook from before this existed; and it cannot be forgotten by the
    next route that deletes something.

    A *free* end (`sourcePoint`/`targetPoint`, a fixed board-space point with
    no item at all) is left alone: that is a real feature, asked for in those
    words, and only an end that names an id which is gone is an orphan.
    """
    node_ids = {row.id for row in nodes}
    object_ids = {row.id for row in objects}
    known = {"node": node_ids, "object": object_ids, "sketch": {row.id for row in sketches}}
    dropped: set[int] = set()
    for row in sketches:
        try:
            data = json.loads(row.data or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or not str(data.get("type", "")).startswith("link-"):
            continue
        ends = (
            (data.get("sourceId"), data.get("sourceKind") or "node"),
            (data.get("targetId"), data.get("targetKind") or "node"),
        )
        for end_id, end_kind in ends:
            if end_id is None:
                continue  # a free point, which is allowed
            if end_id not in known.get(end_kind, set()):
                dropped.add(row.id)
                db.delete(row)
                break
    return dropped


def _board_settings(entry: Entry | None) -> tuple[str, str]:
    """This board's `(type, layout)`, defaulted and validated on the way out.

    Everything here is defensive on purpose, because the column is JSON in a
    text field and this is the only place that reads it: NULL (every board
    that predates maps), a blob that isn't JSON, a blob that is JSON but not
    an object, and a value outside the known set all mean the same thing, 
    an ordinary free-layout whiteboard. A board is a note someone can still
    edit by other means; a bad value here must degrade to the default, never
    to a 500 on the Library's own board list.
    """
    if entry is None:
        return DEFAULT_BOARD_TYPE, DEFAULT_BOARD_LAYOUT
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    board_type = parsed.get("type")
    layout = parsed.get("layout")
    return (
        board_type if board_type in BOARD_TYPES else DEFAULT_BOARD_TYPE,
        layout if layout in BOARD_LAYOUTS else DEFAULT_BOARD_LAYOUT,
    )


def _store_board_settings(
    entry: Entry, board_type: str | None = None, layout: str | None = None
) -> tuple[str, str]:
    """Write `type`/`layout` back, leaving whatever this board already had
    for the one that wasn't given. Returns the pair as it now stands.

    Read-modify-write rather than replace, because a settings blob is a
    family that will keep growing (a default node colour, tidy-on-drop) and
    the failure mode of replacing is silent: changing the layout would clear
    every setting added after this function was written.
    """
    current_type, current_layout = _board_settings(entry)
    resolved_type = board_type or current_type
    resolved_layout = layout or current_layout
    try:
        existing = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing["type"] = resolved_type
    existing["layout"] = resolved_layout
    entry.board_settings = json.dumps(existing)
    return resolved_type, resolved_layout


def _clean_theme(raw: object) -> dict:
    """Whatever was handed in, reduced to the fields `MAP_THEME_FIELDS` knows
    and the values they allow. Everything unknown is dropped rather than
    refused, for the same reason `_board_settings` defaults instead of
    raising: this runs on the read path of every map, and a blob written by a
    newer client, or by hand, must degrade to a plainer map and never to a
    500 on somebody's notebook.

    `False` and `""` are dropped with `None`, because the absence of a value
    is how a theme says "the app's own default" and three ways of saying that
    would be three things to get wrong at the ten places that read one.
    """
    if not isinstance(raw, dict):
        return {}
    theme: dict = {}
    for field, allowed in MAP_THEME_FIELDS.items():
        value = raw.get(field)
        if value is None or value is False or value == "":
            continue
        if allowed is dict:
            levels = _clean_levels(value)
            if levels:
                theme[field] = levels
            continue
        if allowed is bool:
            theme[field] = True
            continue
        if allowed is int:
            try:
                number = int(value)
            #: OverflowError: JSON's `1e999` is infinity, which has no int.
            except (TypeError, ValueError, OverflowError):
                continue
            low, high = MAP_THEME_FONT_RANGE
            if low <= number <= high:
                theme[field] = number
            continue
        if isinstance(value, str) and value in allowed:
            theme[field] = value
    return theme


def _clean_levels(raw: object) -> dict:
    """A map's per-level looks, reduced to `MAP_LEVELS` and `MAP_LEVEL_FIELDS`.
    Dropped rather than refused, for `_clean_theme`'s reason; a level left
    with nothing is left out."""
    if not isinstance(raw, dict):
        return {}
    levels: dict = {}
    for level in MAP_LEVELS:
        look = raw.get(level)
        if not isinstance(look, dict):
            continue
        clean: dict = {}
        for field, allowed in MAP_LEVEL_FIELDS.items():
            value = look.get(field)
            if value is None or value == "":
                continue
            if allowed is bool:
                if isinstance(value, bool):
                    clean[field] = value
            elif allowed is int:
                try:
                    number = int(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                low, high = MAP_THEME_FONT_RANGE
                if low <= number <= high:
                    clean[field] = number
            elif isinstance(value, str) and value in allowed:
                clean[field] = value
        if clean:
            levels[level] = clean
    return levels


def _board_theme(entry: Entry | None) -> dict:
    """This map's theme, defaulted and validated on the way out."""
    if entry is None:
        return {}
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return _clean_theme(parsed.get("theme"))


def _store_board_theme(entry: Entry, theme: dict) -> dict:
    """Merge a theme patch in, and return the theme as it now stands.

    A patch, not a replacement, and a key whose value is `None` is a key
    removed: that is the only way the dialog has of saying "stop theming
    this field and go back to the app's default", and a replacing write would
    make every control in it depend on every other one being sent.

    `_store_board_settings`'s own read-modify-write, for its own reason: the
    settings blob is a family, and replacing it here would clear the board's
    type and layout every time somebody picked a font size.
    """
    current = _board_theme(entry)
    merged = dict(current)
    for field in MAP_THEME_FIELDS:
        if field not in theme:
            continue
        value = theme[field]
        if value is None or value is False or value == "":
            merged.pop(field, None)
        else:
            merged[field] = value
    resolved = _clean_theme(merged)
    try:
        existing = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing["theme"] = resolved
    entry.board_settings = json.dumps(existing)
    return resolved


def _themed_style(style: dict, theme: dict) -> dict:
    """One node's stored style with the map's theme filled in underneath it.

    **The node always wins.** A theme is what a topic follows when it was
    never told otherwise, so a field the node carries is left exactly as it
    is: this is the one rule that makes a map-wide change safe to press,
    because no deliberate per-topic choice can be overwritten by one.
    """
    if not theme:
        return style
    filled = dict(style)
    for field, value in theme.items():
        if field in MAP_LEVEL_THEME_FIELDS:
            continue
        filled.setdefault(field, value)
    return filled


def _without_pins(style: dict) -> dict:
    """A node's style with every app-default pin written as the absence it
    means. For the exports: a file has no word for "the app's own, against a
    theme", and `curve` alone of the pins was a value any reader knew, so it
    is the one left in."""
    out = dict(style)
    for field, value in MAP_APP_DEFAULT_PINS.items():
        if field != "edge_style" and field in out and out[field] == value:
            del out[field]
    return out


def _board_numbered(entry: Entry | None) -> bool:
    """Whether this map numbers its branches (MINDMAP_PLAN.md decision 17).

    A sibling of `type`, `layout` and `theme` in the settings blob, and not a
    field of the theme: the theme is what a topic follows when it says
    nothing, and a number is not something one topic can decline, it is the
    topic's place in the outline. Anything but a stored `true` is off, so
    every map made before this reads exactly as it did.
    """
    if entry is None:
        return False
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, dict) and parsed.get("numbered") is True


def _store_board_numbered(entry: Entry, numbered: bool) -> None:
    """`_store_board_theme`'s read-modify-write, for its reason: the blob is
    a family, and replacing it would clear the type, layout and theme."""
    try:
        existing = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    if numbered:
        existing["numbered"] = True
    else:
        existing.pop("numbered", None)
    entry.board_settings = json.dumps(existing)


#: A colour the board is drawn on: `#rrggbb` only, because it is written into
#: a CSS custom property, and anything wider would be a way to inject a rule.
BOARD_BG_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


#: At most this many named layers on a board; a layer is a few fields.
MAX_BOARD_LAYERS = 20


class BoardLayer(BaseModel):
    """One named layer (draw.io's LayersWindow; WHITEBOARD_PLAN section 6):
    items name it in `data.layer`; hidden hides them all, locked locks them."""

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,24}$")
    name: str = Field(min_length=1, max_length=60)
    hidden: bool = False
    locked: bool = False
    #: The layer new items land in (draw.io's current layer; canvasdepth2).
    #: At most one per board: `_store_board_layers` keeps the first.
    current: bool = False

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A layer needs a name.")
        return value


def _board_layers(entry: Entry | None) -> list[dict]:
    """The board's named layers as stored, each re-checked on the way out."""
    if entry is None:
        return []
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        return []
    stored = parsed.get("layers") if isinstance(parsed, dict) else None
    out = []
    for raw in stored if isinstance(stored, list) else []:
        try:
            out.append(BoardLayer(**raw).model_dump())
        except (TypeError, ValueError):
            continue
    return out[:MAX_BOARD_LAYERS]


def _store_board_layers(entry: Entry, layers: list[BoardLayer]) -> list[dict]:
    """Replace the whole list: a layer's order is the list's order, so a
    patch per layer would have to say where it goes."""
    try:
        existing = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    seen, out = set(), []
    for layer in layers[:MAX_BOARD_LAYERS]:
        if layer.id not in seen:
            seen.add(layer.id)
            out.append(layer.model_dump())
    current = next((layer for layer in out if layer["current"]), None)
    for layer in out:
        layer["current"] = layer is current
    if out:
        existing["layers"] = out
    else:
        existing.pop("layers", None)
    entry.board_settings = json.dumps(existing)
    return out


def current_layer(db: Session, board_id: int | None) -> str | None:
    """The layer a new item on this board lands in, if the board has a
    current one that is neither hidden nor locked: drawing onto a layer you
    cannot see or change would make the thing vanish as it is drawn."""
    if not board_id:
        return None
    for layer in _board_layers(db.get(Entry, board_id)):
        if layer["current"] and not layer["hidden"] and not layer["locked"]:
            return layer["id"]
    return None


def _on_current_layer(db: Session, board_id: int | None, data: dict) -> dict:
    """`data` with the current layer, unless it already names one (or says
    `""`, none on purpose): every way onto a board, hand, paste, import or
    the library, goes through a create here, so this is the one place."""
    if data.get("layer") == "":
        # None on purpose is stored as no key, the shape an item that never
        # had a layer has, so an undo that re-creates one restores the board
        # identically (wbtrash660: `"layer":""` appeared after Undo).
        return {k: v for k, v in data.items() if k != "layer"}
    if "layer" in data:
        return data
    layer = current_layer(db, board_id)
    return {**data, "layer": layer} if layer else data


DEFAULT_GROUPS = ("shape", "link", "text", "pen", "highlighter")
_DEFAULT_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")


def _default_value(value, *, nested: bool = True):
    """A style value: a short string, a number, a bool, or (once) a small dict of those (a gradient)."""
    if isinstance(value, bool) or (isinstance(value, (int, float)) and not isinstance(value, bool)):
        return value
    if isinstance(value, str) and len(value) <= 64:
        return value
    if nested and isinstance(value, dict) and len(value) <= 6:
        out = {k: _default_value(v, nested=False) for k, v in value.items() if _DEFAULT_KEY_RE.match(str(k))}
        if len(out) == len(value):
            return out
    raise ValueError("A default style value is a short word, a number, a switch or a small group of those")


def _clean_defaults(value, *, strict: bool = False) -> dict:
    """`{shape, link, text, pen, highlighter}` of style dicts; an unknown group is dropped, an empty one stores nothing,
    and anything that is not style raises when `strict` (the route) and is skipped when not (a read)."""
    if not isinstance(value, dict):
        if strict:
            raise ValueError("Default styles are a group per kind of item")
        return {}
    out: dict = {}
    for group in DEFAULT_GROUPS:
        style = value.get(group)
        if style in (None, {}):
            continue
        try:
            if not isinstance(style, dict) or len(style) > 40:
                raise ValueError("A default style is a small set of values")
            if not all(_DEFAULT_KEY_RE.match(str(k)) for k in style):
                raise ValueError("A default style names its values with plain words")
            out[group] = {k: _default_value(v) for k, v in style.items()}
        except ValueError:
            if strict:
                raise
    return out


#: The grid's spacing when a board sets none (the client's `WB_GRID_SPACING`).
BOARD_DEFAULT_GRID = 24
#: The switches a board's settings keep, each with the one value that is stored (the other is the default and is not).
BOARD_PAPERS = ("a4", "a3", "letter", "legal", "custom")
BOARD_ORIENTATIONS = ("portrait", "landscape")
BOARD_UNITS = ("px", "mm", "cm", "in", "pt")
#: Choices whose default is not stored (A4, portrait), with the client's table of sizes in `wbPdf`.
BOARD_CHOICE_DEFAULT = {"paper": "a4", "orientation": "portrait", "units": "px"}
BOARD_CUSTOM_MM = (50, 2000)
BOARD_SWITCH_STORED = {"sticky_fold": False, "rough": True, "guides": False, "page_view": True, "shadow_default": True}


class BoardBackground(BaseModel):
    """A board's look (WHITEBOARD_PLAN decision 24, FEAT-06): a colour, an
    image from this notebook's uploads, or both. A patch: a field sent as
    `null` is removed, a field not sent is kept."""

    color: str | None = Field(default=None, max_length=7)
    image: str | None = Field(default=None, max_length=300)
    #: Whether a sticky note's corner is drawn folded over (INBOX 792: "the
    #: option to hide the flap in the corner"). Folded is the default, so only
    #: `false` is ever stored; a note's own `fold` overrides it.
    sticky_fold: bool | None = None
    #: **The hand-drawn look** (Excalidraw's; canvasdepth2): every shape and
    #: line drawn with rough strokes. Plain is the default, so only `true` is
    #: stored; an item's own `rough` in its data overrides it.
    rough: bool | None = None
    #: **Set as default style** (draw.io's Ctrl+Shift+D): `{shape, link, text}`, each a small dict
    #: of the style values a new item of that kind starts with. A patch like the rest: `null` takes
    #: them all off. Kept opaque beyond its shape (see `_clean_defaults`), as a sketch's data is.
    defaults: dict | None = None
    #: **Board options** (wbformat2): the grid's spacing in board units (24 is the default and is not stored) and its
    #: colour. Snap, Shift+arrow nudging and the drawn grid all read the spacing.
    grid_size: int | None = Field(default=None, ge=4, le=200)
    grid_color: str | None = Field(default=None, max_length=7)
    #: **Board options, switches** (wbformat2). Each stores only its non-default value: alignment guides default on,
    #: page view (the page frames) and the shadow new shapes start with default off.
    guides: bool | None = None
    page_view: bool | None = None
    shadow_default: bool | None = None
    #: **Paper** (wbformat2): the page the page view draws and the PDF export starts from. A4 portrait is the default
    #: and is not stored; a custom size is in millimetres.
    paper: Literal["a4", "a3", "letter", "legal", "custom"] | None = None
    orientation: Literal["portrait", "landscape"] | None = None
    #: The unit the position and size fields and the rulers show lengths in (96 px to the inch); px is the default.
    units: Literal["px", "mm", "cm", "in", "pt"] | None = None
    paper_w: int | None = Field(default=None, ge=BOARD_CUSTOM_MM[0], le=BOARD_CUSTOM_MM[1])
    paper_h: int | None = Field(default=None, ge=BOARD_CUSTOM_MM[0], le=BOARD_CUSTOM_MM[1])

    @field_validator("grid_color")
    @classmethod
    def _grid_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not BOARD_BG_COLOR_RE.match(value):
            raise ValueError("A grid colour is #rrggbb")
        return value.lower()

    @field_validator("defaults")
    @classmethod
    def _style_defaults(cls, value: dict | None) -> dict | None:
        return None if value is None else _clean_defaults(value, strict=True)

    @field_validator("color")
    @classmethod
    def _hex_colour(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not BOARD_BG_COLOR_RE.match(value):
            raise ValueError("A background colour is #rrggbb")
        return value.lower()

    @field_validator("image")
    @classmethod
    def _own_upload(cls, value: str | None) -> str | None:
        """An upload of this notebook's or nothing, the topic picture's rule:
        an outside address would make a board call out of an offline app."""
        if value is None:
            return None
        text = value.strip()
        if not MEDIA_URL_RE.match(text):
            raise ValueError("A background image has to be a /media/... upload from this notebook")
        return text


def _background_flags_and_grid(stored: dict) -> dict:
    """The switches and the grid out of a stored background, only valid values."""
    out = {}
    if defaults := _clean_defaults(stored.get("defaults")):
        out["defaults"] = defaults
    size, grid = stored.get("grid_size"), stored.get("grid_color")
    if isinstance(size, int) and not isinstance(size, bool) and 4 <= size <= 200 and size != BOARD_DEFAULT_GRID:
        out["grid_size"] = size
    if isinstance(grid, str) and BOARD_BG_COLOR_RE.match(grid):
        out["grid_color"] = grid
    out.update({key: kept for key, kept in BOARD_SWITCH_STORED.items() if stored.get(key) is kept})
    out.update(_background_paper(stored))
    return out


def _background_paper(stored: dict) -> dict:
    """The paper fields out of a stored background: a known size or direction that is not the default, a custom
    size inside the bounds."""
    out = {}
    for key, choices in (("paper", BOARD_PAPERS), ("orientation", BOARD_ORIENTATIONS), ("units", BOARD_UNITS)):
        if stored.get(key) in choices and stored[key] != BOARD_CHOICE_DEFAULT[key]:
            out[key] = stored[key]
    for key in ("paper_w", "paper_h"):
        mm = stored.get(key)
        if isinstance(mm, int) and not isinstance(mm, bool) and BOARD_CUSTOM_MM[0] <= mm <= BOARD_CUSTOM_MM[1]:
            out[key] = mm
    return out


def _board_background(entry: Entry | None) -> dict:
    """The board's stored background, only the fields that hold a value."""
    if entry is None:
        return {}
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        return {}
    stored = parsed.get("background") if isinstance(parsed, dict) else None
    if not isinstance(stored, dict):
        return {}
    out = {}
    color, image = stored.get("color"), stored.get("image")
    if isinstance(color, str) and BOARD_BG_COLOR_RE.match(color):
        out["color"] = color
    if isinstance(image, str) and MEDIA_URL_RE.match(image):
        out["image"] = image
    out.update(_background_flags_and_grid(stored))
    return out


def _store_board_background(entry: Entry, patch: BoardBackground) -> dict:
    """Merge the fields sent into the stored background, the read-modify-write
    of the whole settings family (`_store_board_theme`'s reason)."""
    merged = _board_background(entry)
    for field in patch.model_fields_set:
        value = getattr(patch, field)
        if value is None or value == {} or (field in BOARD_SWITCH_STORED and value is not BOARD_SWITCH_STORED[field]) or (field == "grid_size" and value == BOARD_DEFAULT_GRID) or BOARD_CHOICE_DEFAULT.get(field) == value:
            merged.pop(field, None)
        else:
            merged[field] = value
    # A custom size means nothing on a named paper; kept, it would come back the day the paper is custom again.
    if merged.get("paper") != "custom":
        merged.pop("paper_w", None)
        merged.pop("paper_h", None)
    try:
        existing = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    if merged:
        existing["background"] = merged
    else:
        existing.pop("background", None)
    entry.board_settings = json.dumps(existing)
    return merged


def _is_link_sketch():
    """A connector, read off the sketch's stored JSON without parsing it: the
    client writes `{"type":"link-…"}` (`JSON.stringify`, no space) and the AI
    tools `json.dumps` (a space), so both spellings are matched."""
    return or_(
        WhiteboardSketch.data.like('%"type":"link-%', escape=LIKE_ESCAPE),
        WhiteboardSketch.data.like('%"type": "link-%', escape=LIKE_ESCAPE),
    )


class BoardOut(BaseModel):
    #: None is the one unnamed scratch board every notebook starts with.
    id: int | None
    title: str
    node_count: int
    sketch_count: int
    #: How many of `sketch_count` are connectors between items (a sketch whose
    #: data is a `link-*` type) rather than drawings. The dashboard and the
    #: Library said "3 cards · 2 sketches" for a map of three cards and two
    #: lines (audit 2026-10-05, UX-06): a person drew no sketches.
    link_count: int = 0
    object_count: int = 0
    #: When the board last changed: the later of its note's own edit and the
    #: last card, sketch or object written on it, since drawing on a board
    #: never touches the note. The Library's board card showed a count and
    #: no date, where every other kind of card has one (pass2.md, Remaining
    #: 2). None for an empty default board, which has neither.
    updated_at: datetime | None = None
    #: "board" (a free canvas) or "map" (tree semantics). See BOARD_TYPES.
    type: str = DEFAULT_BOARD_TYPE
    layout: str = DEFAULT_BOARD_LAYOUT
    #: The board's look, `{color, image}` (decision 24); `{}` is the theme's.
    background: dict = {}
    #: Its named layers (canvasdepth); `[]` for none.
    layers: list[dict] = []
    #: A miniature of where things actually sit on this board: up to
    #: Up to `PREVIEW_POINTS` items, `{x, y, kind, label}`, each position
    #: normalised into 0..1 against the board's own bounding box. The
    #: Library's board cards showed an icon, a title and a count, which is
    #: the same three facts for every board anyone has ever drawn (reported
    #: as the Boards & maps sub-tab being "boring" and wanting previews).
    #:
    #: **`kind` and `label` are why this replaced a bare list of points**,
    #: and both came out of looking at the result: reported again as "the
    #: whiteboard preview is poor", and the screenshot showed why. Every card
    #: drew as an identical blank grey rectangle, so three different boards
    #: called "Cloud computing" were indistinguishable: a preview whose only
    #: information is *how many* things there are and roughly where. And a
    #: board holding only sketches previewed as nothing at all, because
    #: sketches were not in the sample; "Default board · 2 sketches" showed
    #: an empty space where its picture should be.
    #:
    #: Normalised here rather than client-side because the client would then
    #: need every item's absolute coordinates to compute the bounds, which is
    #: the whole board: and a list of twenty boards would ship twenty whole
    #: boards to draw twenty thumbnails.
    preview_items: list[dict] = []
    #: A map's parent→child edges as line segments, `{x1, y1, x2, y2}`, in the
    #: same normalised 0..1 space as `preview_items` and sampled with it.
    #:
    #: Empty for an ordinary board, which has no tree to draw. It exists
    #: because a map whose thumbnail is a scatter of dots is indistinguishable
    #: from a board: and structure is the entire difference between the two,
    #: so the one thing the picture has to show is the one thing points alone
    #: cannot.
    preview_edges: list[dict] = []
    #: The board's own width/height, so a thumbnail can be drawn at the shape
    #: the board actually has instead of stretched to whatever box it lands
    #: in. Normalising into 0..1 threw this away: a tall map and a wide board
    #: both came back as the unit square, so every card drew the same
    #: rectangle and a tree that runs left to right looked identical to one
    #: that runs top to bottom.
    #:
    #: Clamped into `PREVIEW_ASPECT_RANGE`. Past that the letterboxed picture
    #: is a sliver a few pixels wide inside a card that is mostly empty, which
    #: says less about the board than a slightly wrong ratio does.
    preview_aspect: float = 1.0
    #: Fingerprint of the stored raster thumbnail when it is current for the
    #: board as it is now, else None (the client then draws the SVG preview).
    thumb_v: str | None = None


class BoardTypeMixin(BaseModel):
    """`type` and `layout` as a request field, validated once for every
    endpoint that takes them rather than three times slightly differently."""

    type: str | None = None
    layout: str | None = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str | None) -> str | None:
        if value is not None and value not in BOARD_TYPES:
            raise ValueError(
                f"Unknown board type {value!r}: expected " + " or ".join(sorted(BOARD_TYPES))
            )
        return value

    @field_validator("layout")
    @classmethod
    def _known_layout(cls, value: str | None) -> str | None:
        if value is not None and value not in BOARD_LAYOUTS:
            raise ValueError(
                f"Unknown layout {value!r}: expected one of " + ", ".join(sorted(BOARD_LAYOUTS))
            )
        return value


class BoardCreate(BoardTypeMixin):
    name: str = Field(min_length=1, max_length=100)


def _board_entry(db: Session, board_id: int) -> Entry:
    """The note behind a board, or the 404 `rename_board` already gives: 
    `board_id=0` and negative ids can't resolve to a real note either."""
    entry = db.get(Entry, board_id) if board_id > 0 else None
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That board could not be found.")
    return entry
