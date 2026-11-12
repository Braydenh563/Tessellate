"""The whiteboard's vocabulary: limits, kinds, layouts and the map theme fields, and the models and state
helpers for a board's comments, nodes, sketches and objects.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata

from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_serializer
from fastapi import HTTPException
from tessellate.core.validation_copy import Said
from tessellate.core.database import WhiteboardObject

#: An image object's `data.url`, as an allowlist rather than a prefix check.
#:
#: **A `startswith("/media/")` test is not enough.** A purge removes an image
#: object's file, and `/media/../../../etc/passwd` passes a prefix check while
#: resolving well outside the media folder. Matching the exact shape
#: `upload_media` produces (a uuid4 hex plus a short suffix) closes it at the
#: door; the purge (`manager`) checks containment again.
MEDIA_URL_RE = re.compile(r"^/media/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_APP_ROUTE_LINK = re.compile(r"^#/[a-z][a-z-]{0,30}(?:/[A-Za-z0-9_.%-]{1,120}){0,4}$")

#: A sketch is a path list, not an image. Big enough for a page of scribble,
#: small enough that a runaway client can't fill the disk one PUT at a time.
MAX_SKETCH_CHARS = 400_000

#: A text box's own content. Generous: this is a whiteboard note, not a tweet
#:, but still bounded for the same reason every other free-text field here is.
MAX_OBJECT_TEXT_CHARS = 20_000
#: The longest note a topic can hold behind it (MINDMAP_PLAN.md decision 18).
#: A note is a paragraph or a few, not a document: a longer text belongs in a
#: notebook note the topic points at, which the map already does.
MAX_TOPIC_NOTE_CHARS = 10_000
#: A comment thread on an item (WHITEBOARD_PLAN decision 17): a remark, not a
#: note, and a thread a person reads in one popover.
MAX_COMMENT_CHARS = 2_000
MAX_COMMENTS_PER_ITEM = 100

#: What a board *is*. A map is a board with tree semantics turned on
#: (MINDMAP_PLAN.md §4, option B), the same rows, the same endpoints, one
#: extra edge per node. "board" is the default, and is what NULL settings
#: mean, so every board that existed before maps did stays exactly what it
#: was.
BOARD_TYPES = {"board", "map"}
DEFAULT_BOARD_TYPE = "board"

#: How a map arranges itself. "free" means "wherever you dragged it", which
#: is the only thing an ordinary whiteboard has ever done; the others are the
#: standard mindmap arrangements (MINDMAP_PLAN.md §3.1). Stored rather than
#: computed because it is a property of the map, not of the session looking
#: at it, the layout you chose has to be there tomorrow.
#:
#: "tree-left" and "tree-both" were added for MINDMAP_PLAN §13e: §12.0's own
#: decision list promised both and §13.4 measured them missing, and
#: both-sides is the layout Coggle is known for. A value this set does not
#: know is refused rather than stored, so an older client asking for one of
#: these is the only compatibility question, and it gets the default.
#: "logic-right", "timeline", "fishbone" and "tree-table" for MINDMAP_PLAN 15
#: row 6, XMind's structures beyond the tree; the client lays them out.
BOARD_LAYOUTS = {
    "free", "tree-right", "tree-left", "tree-both", "tree-down", "radial",
    "logic-right", "timeline", "fishbone", "tree-table",
}
DEFAULT_BOARD_LAYOUT = "free"
#: **A map made from text starts laid out** (audit FEAT-05, 2026-10-05). The
#: import and the accepted AI proposal used the board default, Free, while a
#: map made by hand (`createNewBoard`) and the AI's `create_mindmap` start in
#: tree-right: so the first Tab on an imported map piled new topics onto old
#: ones, 240 overlapping pairs over 101 topics. One default for every map
#: door.
DEFAULT_MAP_LAYOUT = "tree-right"

#: **The map's own theme** (MINDMAP_PLAN.md §13e, the owner: "the
#: customisation features are lacking severely"). §13.4 measured the gap
#: precisely: a topic has eleven fields and the map as a whole has none, so
#: every one of the eleven is set one topic at a time and the only bulk
#: operation of any kind is "Reset to branch" on a single node.
#:
#: **What is in here and what is not is one question asked eleven times**:
#: does this field describe *this topic*, or how *this map* draws topics? The
#: ten below are the second kind. Left out, deliberately: `icon`, `core`,
#: `image`, `link` and `edge_label`, each of which names which topic this is
#: rather than how it is drawn (a map whose every topic is a core idea with
#: the same picture is not a theme); `edge_bend` and `edge_slide`, which are
#: a position on one line; and `color`, which is not one value but a rule: it
#: seeds a whole subtree, and the map-level answer to it is a branch palette,
#: which is drawn in two places (the canvas from d3, the Library thumbnail
#: from `MAP_BRANCH_PALETTE` on this side) and would have to teach the
#: preview cache about itself before it could be picked. That is its own row
#: in §13e, not a corner of this one.
#:
#: The value `None` means "this map says nothing, use the app's default",
#: which is what every map has today: a theme that stores nothing draws
#: exactly the map that was drawn before this existed.
#:
#: **`palette` and `font` joined later, and they are the map's, not a
#: topic's** (§13e's remainder, decision 8). A branch palette is the answer
#: to `color` at map level: not one value but the list a first-level branch
#: claims its colour from, so it is a name here (`MAP_BRANCH_PALETTES`) and
#: the one list both drawings read. A font is the face every topic and line
#: label on the map is set in; no topic has a face of its own, so it never
#: resolves onto a topic (`MAP_LEVEL_THEME_FIELDS`).
MAP_THEME_FIELDS: dict[str, frozenset | type] = {
    "font_size": int,
    "align": frozenset({"left", "center", "right"}),
    "bold": bool,
    "italic": bool,
    "shape": frozenset({"pill", "rect", "ellipse", "none", "circle", "hexagon", "diamond", "cloud", "chevron", "underline"}),
    "spine": frozenset({"dashed", "none"}),
    "edge_style": frozenset({"curve", "elbow", "straight"}),
    "edge_dashed": bool,
    "edge_width": frozenset({"thin", "thick"}),
    "edge_arrow": frozenset({"on", "off"}),
    "palette": frozenset({"deep", "soft", "vivid", "bold", "paired", "bright", "earth"}),
    "font": frozenset({"serif", "mono", "wide"}),
    #: **How far apart the topics sit** (the owner, 2026-10-10: "the spacing
    #: is really close to the other things and bunched up", and "I want more
    #: mindmap appearance options"). The tidy's two gaps scaled; normal is no
    #: value. The map's, like the font: never resolved onto a topic.
    "spacing": frozenset({"compact", "roomy"}),
    #: **Rainbow every level** (MINDMAP_PLAN gap 10): each topic claims the next palette colour among its siblings at every depth, not only the first. The map's, never resolved onto a topic.
    "rainbow": bool,
    #: **A legend on the map** (MINDMAP_PLAN gap 11): the main branches' colours and the markers in use, drawn over the canvas. The map's, never resolved onto a topic.
    "legend": bool,
    #: **The hierarchy preset** (MINDMAP_PLAN.md decision 39): how the centre,
    #: the main branches and everything deeper draw. Classic is the default
    #: and is stored as no value; the frontend holds what each one draws
    #: (`WB_MAP_HIERARCHIES`), as it holds the fonts' stacks.
    "hierarchy": frozenset({"outline", "boxed", "flat"}),
    #: **A look per level** (decision 40): `{"0": {...}, "1": {...}, "2":
    #: {...}}`, each holding `MAP_LEVEL_FIELDS`. Cleaned by `_clean_levels`,
    #: and replaced whole by a patch, so Undo puts the whole set back.
    "levels": dict,
}

#: The fields one level of a map can set (decision 40), and their values.
#: `fill` is a level's own word set: `solid`, `tint` or `none`. A `False` is
#: kept: a level saying "not bold" against a preset that says bold is a choice.
MAP_LEVEL_FIELDS: dict[str, frozenset | type] = {
    "font_size": int,
    "bold": bool,
    "italic": bool,
    "shape": frozenset({"pill", "rect", "ellipse", "none", "rounded", "circle", "hexagon", "diamond", "cloud", "chevron", "underline"}),
    "spine": frozenset({"dashed", "none", "solid"}),
    "fill": frozenset({"solid", "tint", "none"}),
    "edge_width": frozenset({"thin", "thick", "normal"}),
    #: Topic effects (MINDMAP_PLAN §14.4, the owner 2026-10-10: "I want more
    #: mindmap appearance options"): a soft shadow or a glow in the branch
    #: colour, per level as per topic; `none` is a level saying "not here".
    "effect": frozenset({"shadow", "glow", "none"}),
}
MAP_LEVELS = ("0", "1", "2")

#: The theme fields that describe the map as a whole rather than how it draws
#: one topic: never filled in under a topic's style (`_themed_style`), so an
#: export never writes them onto a node and a re-import never reads them back
#: as a topic's own choice.
MAP_LEVEL_THEME_FIELDS = frozenset({"palette", "font", "hierarchy", "levels", "spacing", "rainbow", "legend"})

#: **A stored name for the app's own default, per themed select** (decision
#: 9's narrow case, built). Every select in the topic strip stores the app's
#: default as no value at all, which on a themed map means "follow the map":
#: so a topic could be pulled back to the map's look or to another named
#: value, never to the app's own. Each name here is a value a topic can carry
#: that draws exactly what no value draws on an unthemed map, and, being a
#: value, beats the theme the way any choice a topic carries does. `curve`
#: was already one; the other five are new words, which is why the exports
#: write them as the absence they mean (`_without_pins`) and the canvas
#: paints them as no attribute at all (`wbMapDrawn`, whiteboard-map.js).
#: `0` for the size because the field is a number: no text is drawn at 0px,
#: and every reader that writes a size already treats a falsy one as unset.
MAP_APP_DEFAULT_PINS: dict[str, object] = {
    "font_size": 0,
    "align": "auto",
    "shape": "rounded",
    "spine": "solid",
    "edge_width": "normal",
    "edge_style": "curve",
}

#: The bounds on a themed text size, the same two numbers the per-topic field
#: is drawn between. A size outside them is not a style, it is a map nobody
#: can read, and the strip itself only ever offers 12, 19 and 25.
MAP_THEME_FONT_RANGE = (8, 96)

#: A map node that stands for something that lives in the library. The node
#: is a *pointer*: deleting it removes the pointer and never the thing, which
#: is the half of containment that must not be got wrong (MINDMAP_PLAN.md
#: §5.4). `image` is deliberately not in here, an image object owns its file
#: and `delete_object` unlinks it, which is the opposite rule.
MAP_REFERENCE_KINDS = {"note", "document", "file", "link"}

#: A Phosphor glyph's name, the pattern `data.icon` had before it also took an
#: emoji (MINDMAP_PLAN.md decision 45).
ICON_NAME_RE = re.compile(r"^[a-z0-9-]{1,40}$")

#: The joiners and selectors an emoji sequence is made of beside its
#: pictographs: the zero-width joiner, the variation selectors and the keycap.
_EMOJI_JOINERS = {0x200D, 0xFE0E, 0xFE0F, 0x20E3}


def _is_one_emoji(value: str) -> bool:
    """Whether `value` is one emoji (pictographs and what joins them), not text.

    Short (16 code points covers the longest family or flag sequence), with no
    ASCII and no control, format or private character but the joiners an
    emoji uses: so a label, markup or an invisible run cannot ride in as an
    "icon". The glyph is drawn with `textContent`, so this guards meaning
    rather than being the only thing between a value and the page."""
    if not value or len(value) > 16:
        return False
    for char in value:
        point = ord(char)
        if point in _EMOJI_JOINERS or 0x1F3FB <= point <= 0x1F3FF or 0xE0020 <= point <= 0xE007F:
            continue
        pictograph = 0x2100 <= point <= 0x2BFF or 0x1F000 <= point <= 0x1FAFF or point in (0x203C, 0x2049, 0x3030, 0x303D, 0x3297, 0x3299)
        if not pictograph or unicodedata.category(char) in {"Cc", "Cf", "Co", "Cn"}:
            return False
    return True

#: A topic is text that exists only in the map. It is the one node kind with
#: nothing behind it, which is why deleting the map deletes it.
MAP_TOPIC_KIND = "topic"

#: A frame (WHITEBOARD_PLAN decision 14): a titled region of a board that
#: carries what lies inside it when it moves. Its title is `content`; it owns
#: nothing, so deleting it leaves what it held where it is.
FRAME_KIND = "frame"

#: A table (draw.io's; canvasdepth2): rows and columns of text cells.
TABLE_KIND = "table"
MAX_TABLE_ROWS = 50
MAX_TABLE_COLS = 20
#: A live Mermaid diagram (INBOX 1451): its source is `data.mermaid`, drawn
#: by the browser's diagram frame; nothing drawn is stored, so a theme
#: change or an edit redraws it.
DIAGRAM_KIND = "diagram"
MAX_MERMAID_CHARS = 20_000
VALID_OBJECT_KINDS = {"image", "text", FRAME_KIND, MAP_TOPIC_KIND, TABLE_KIND, DIAGRAM_KIND} | MAP_REFERENCE_KINDS


#: A card/sketch/object's own persisted group, asked for directly (Ctrl+G).
#: Opaque and client-generated (a `crypto.randomUUID()`), not a foreign key:
#: one group spans three different tables, so there's no single row for it
#: to reference. 40 chars is a UUID with room to spare.
GROUP_ID_MAX_LEN = 40


class WhiteboardComment(BaseModel):
    """One comment in an item's thread (WHITEBOARD_PLAN decision 17). The id
    and the time are the client's: a notebook has one author and one clock."""

    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=MAX_COMMENT_CHARS)
    at: str = Field(default="", max_length=40)
    #: The owner, 2026-10-10: "there's no way to edit a comment" and comments
    #: "need a lot of improvement". When it was last edited, whether it is
    #: resolved (folded away, out of the count), and the id of the comment
    #: it answers (a reply is drawn under its parent). Each is left out when
    #: it says nothing, so a thread written before them reads back unchanged.
    edited: str | None = Field(default=None, max_length=40)
    resolved: bool | None = None
    reply_to: str | None = Field(default=None, max_length=40)

    @model_serializer(mode="wrap")
    def _drop_unsaid(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}


#: A thread: `None` (or empty) is no thread.
CommentThread = Annotated[list[WhiteboardComment], Field(max_length=MAX_COMMENTS_PER_ITEM)]


#: Where an item may sit (audit 1031 BD1). `y: 1e308` was accepted and, with two
#: such items, put everything at y = -33 million: zoom to fit showed nothing and
#: the PNG export failed. A million board units is some 3,000 screens each way.
#: `allow_inf_nan=False` also refuses `"NaN"`, which SQLite stores as NULL and
#: which answered 500. `LAYER_LIMIT` is the same bound for the stacking number.
COORD_LIMIT = 1_000_000.0
LAYER_LIMIT = 10**12
Coord = Annotated[float, Field(ge=-COORD_LIMIT, le=COORD_LIMIT, allow_inf_nan=False)]
Layer = Annotated[int, Field(ge=-LAYER_LIMIT, le=LAYER_LIMIT)]


def _clamp(limit: float):
    def clamp(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(number) else max(-limit, min(limit, number))

    return clamp


#: What a row stored before the bound reads back as: pulled to the edge, so one
#: old row cannot blank the board and the response still validates.
StoredCoord = Annotated[float, BeforeValidator(_clamp(COORD_LIMIT))]
StoredLayer = Annotated[int, BeforeValidator(lambda v: int(_clamp(LAYER_LIMIT)(v)))]


class WhiteboardNodeBase(BaseModel):
    entry_id: int
    board_id: int | None = None
    x: Coord = 0.0
    y: Coord = 0.0
    z: Layer = 0
    #: Asked for directly ("resizing... cards"). `None` means auto-sized: 
    #: the same ~250×150 CSS default every card used before this existed.
    width: float | None = Field(default=None, ge=20, le=4000)
    height: float | None = Field(default=None, ge=20, le=4000)
    #: Degrees, clockwise, about the card's own centre. Asked for directly
    #: ("rotations"); `None` renders identically to 0.
    rotation: float | None = Field(default=None, ge=-360, le=360)
    group_id: str | None = Field(default=None, max_length=GROUP_ID_MAX_LEN)
    #: Decision 15: locked in place. False on every card made before it.
    locked: bool = False
    #: Decision 17: the card's thread. Left out of a PUT, the stored one stays
    #: (`_apply_node`), so a client that predates it cannot wipe it.
    comments: CommentThread | None = None
    #: Hidden by the Layers tab's eye (WHITEBOARD_PLAN decision 27).
    hidden: bool = False


class WhiteboardNodeOut(WhiteboardNodeBase):
    id: int
    x: StoredCoord = 0.0
    y: StoredCoord = 0.0
    z: StoredLayer = 0

    model_config = ConfigDict(from_attributes=True)


class WhiteboardSketchBase(BaseModel):
    data: str = Field(max_length=MAX_SKETCH_CHARS)
    board_id: int | None = None
    x: Coord = 0.0
    y: Coord = 0.0
    z: Layer = 0
    group_id: str | None = Field(default=None, max_length=GROUP_ID_MAX_LEN)


#: What a sketch's JSON may say about its look (audit 1031 BD14). The page
#: draws these into SVG attributes, so each is a short value of a known shape,
#: checked on the way in; a row stored before this is read as it is.
_PATH_RE = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]*$")
_COLOUR_RE = re.compile(r"^[#A-Za-z0-9(),.%\s/-]{0,60}$")
_SKETCH_NUMBERS = {"width": (0, 400), "opacity": (0, 1)}
_SKETCH_COLOURS = ("color", "fill", "label_color")
#: A tag is a word or two; an item holds a handful. Objects and sketches share the bounds.
MAX_TAG_CHARS = 40
MAX_TAGS_PER_ITEM = 20


def _bad_tags(tags: object) -> bool:
    return not (
        isinstance(tags, list) and len(tags) <= MAX_TAGS_PER_ITEM
        and all(isinstance(t, str) and 1 <= len(t) <= MAX_TAG_CHARS for t in tags)
    )


#: A shape's own connection points (draw.io's `points`): up to 64, each two fractions of the box (a little past the edge is
#: allowed), an optional pixel offset, the flag that holds it on the outline and a name.
_MAX_PORTS = 64
_PORT_FRACTION = 4
_PORT_OFFSET = 2000


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) < 1e9


def _bad_port(port: object) -> bool:
    """A port that is not `{x, y}` fractions with optional pixel offsets, a perimeter flag and a short name."""
    if not isinstance(port, dict) or "x" not in port or "y" not in port:
        return True
    if not all(_number(port[k]) and abs(port[k]) <= _PORT_FRACTION for k in ("x", "y")):
        return True
    if not all(_number(port[k]) and abs(port[k]) <= _PORT_OFFSET for k in ("dx", "dy") if k in port):
        return True
    if "perimeter" in port and not isinstance(port["perimeter"], bool):
        return True
    return "name" in port and not (isinstance(port["name"], str) and len(port["name"]) <= 80)


def _bad_ports(ports: object) -> bool:
    return not isinstance(ports, list) or len(ports) > _MAX_PORTS or any(_bad_port(p) for p in ports)


def _bad_sketch_field(parsed: dict) -> str | None:
    """The first field of a sketch's JSON that is not a value the page can draw."""
    path = parsed.get("d")
    if path is not None and not (isinstance(path, str) and _PATH_RE.match(path)):
        return "d"
    for key in _SKETCH_COLOURS:
        value = parsed.get(key)
        if value is not None and not (isinstance(value, str) and _COLOUR_RE.match(value) and "url(" not in value.lower()):
            return key
    for key, (low, high) in _SKETCH_NUMBERS.items():
        value = parsed.get(key)
        if value is not None and not (isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high):
            return key
    return None


def check_sketch_data(data: str) -> str:
    """`data` unchanged when it is safe to store: a bare path or list is left
    to the page's own parse, an object has its path, colours, width and
    opacity bounded, and a nest too deep to parse is refused."""
    try:
        parsed = json.loads(data)
    except RecursionError as exc:
        raise Said("This drawing is nested too deeply to save.") from exc
    except ValueError:
        return data
    bad = None
    if isinstance(parsed, dict):
        bad = "ports" if "ports" in parsed and _bad_ports(parsed["ports"]) else _bad_sketch_field(parsed)
        if not bad and "tags" in parsed and _bad_tags(parsed["tags"]):
            bad = "tags"
    if bad:
        raise Said(f"The drawing's {bad} is not something the board can draw.")
    return data


class WhiteboardSketchIn(WhiteboardSketchBase):
    """A sketch as a client sends it: checked. Reading one back
    (`WhiteboardSketchOut`) never refuses a row that is already stored."""

    @field_validator("data")
    @classmethod
    def _drawable(cls, value: str) -> str:
        return check_sketch_data(value)


class WhiteboardSketchOut(WhiteboardSketchBase):
    id: int
    x: StoredCoord = 0.0
    y: StoredCoord = 0.0
    z: StoredLayer = 0

    model_config = ConfigDict(from_attributes=True)


class TableMerge(BaseModel):
    """One merged table cell: the cell at (r, c) spanning rs rows and cs columns."""

    r: StrictInt = Field(ge=0, lt=MAX_TABLE_ROWS)
    c: StrictInt = Field(ge=0, lt=MAX_TABLE_COLS)
    rs: StrictInt = Field(ge=1, le=MAX_TABLE_ROWS)
    cs: StrictInt = Field(ge=1, le=MAX_TABLE_COLS)


class WhiteboardObjectData(BaseModel):
    """What `data` actually holds, validated by `kind` rather than left as an
    opaque string the way a sketch's own path data is, an image needs a real
    same-origin URL (never an arbitrary one a client could point anywhere),
    and a text box's content has its own length bound."""

    url: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=MAX_OBJECT_TEXT_CHARS)
    #: Locked in place (WHITEBOARD_PLAN decision 15). View state on a row that
    #: already carries a blob, like `pinned` below, so it earns no column.
    locked: bool | None = None
    #: The item's comment thread (WHITEBOARD_PLAN decision 17).
    comments: CommentThread | None = None
    #: Hidden by the Layers tab's eye, and its own name there (decision 27).
    hidden: bool | None = None
    name: str | None = Field(default=None, max_length=80)
    #: **A table's cells** (canvasdepth2), row by row, every row as long as
    #: the first (`_require_object_data`); and whether its first row is a
    #: header, drawn bold on a tint.
    cells: list[list[Annotated[str, StringConstraints(max_length=500)]]] | None = Field(default=None, max_length=50)
    header: bool | None = None
    #: A diagram's Mermaid source (`DIAGRAM_KIND`).
    mermaid: str | None = Field(default=None, max_length=MAX_MERMAID_CHARS)
    #: The Library diagram (a `documents` row of type mmd) this object shows, the mermaid above
    #: being its snapshot (1621 D3). Not `ref_id`, which is `MAP_REFERENCE_KINDS` only. Strict, so
    #: "7", 7.0 and true are refused; a deleted row is a valid state, so existence is not checked here.
    diagram_id: StrictInt | None = Field(default=None, ge=1)
    #: **A table's column widths** (wb5): one relative weight per column, so
    #: [2, 1, 1] is a first column twice the others and the box's width the
    #: sum. Absent means equal; a length other than the columns is refused.
    col_widths: list[Annotated[float, Field(ge=0.1, le=20)]] | None = Field(default=None, max_length=20)
    #: A table's row heights, the same kind of weights (one per row, mean 1).
    row_heights: list[Annotated[float, Field(ge=0.1, le=20)]] | None = Field(default=None, max_length=50)
    #: **Merged cells**: each `{r, c, rs, cs}` is the cell at row r, column c
    #: spanning rs rows and cs columns (`_require_table_merges` keeps them inside
    #: the grid and apart). `stripes` tints every other body row.
    merges: list[TableMerge] | None = Field(default=None, max_length=200)
    stripes: bool | None = None
    #: A frame marked as a lane keeps what it holds in a column (`stack`; whiteboard-layouts-more.js).
    stack: bool | None = None
    #: **Edit data** (draw.io's custom properties; canvasdepth2): up to 30
    #: named values on an item, edited in the Format panel's Data tab.
    props: dict[
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z][\w .-]{0,39}$")],
        Annotated[str, StringConstraints(max_length=200)],
    ] | None = Field(default=None, max_length=30)
    #: **Tags** (WHITEBOARD_PLAN structure rows): short words on an item, filtered by in the find bar
    #: (`wbFmtState.structure`). A sketch's own JSON carries the same list (`_bad_sketch_field`).
    tags: list[Annotated[str, StringConstraints(min_length=1, max_length=MAX_TAG_CHARS)]] | None = Field(default=None, max_length=MAX_TAGS_PER_ITEM)
    #: A folded frame (`collapsed`, below, also a map branch's flag) keeps its height from before the fold here, so
    #: Expand puts it back; the items wholly inside that full box are out of sight while it is folded.
    fold_h: int | None = Field(default=None, ge=20, le=4000)
    #: The named layer it is on (canvasdepth); the board's settings hold them.
    #: `""` is "on no layer, said on purpose": an item brought back by Undo
    #: says it so it does not land on the current layer (`_on_current_layer`).
    layer: str | None = Field(default=None, pattern=r"^([A-Za-z0-9_-]{1,24})?$")
    #: Where a placed library item came from (decision 25): `{id, version}`
    #: or `{builtin}`. Kept, never followed.
    library_ref: dict | None = None
    #: A frame's place in the presentation (decision 22, the Pages tab).
    page: int | None = Field(default=None, ge=1, le=100000)
    #: The Format panel's opacity and shadow (WHITEBOARD_PLAN decision 19).
    alpha: float | None = Field(default=None, ge=0.05, le=1)
    shadow: bool | None = None
    #: This item's own keep-proportions switch (INBOX 1313): a corner drag keeps
    #: the ratio without Shift. A schema that does not name it drops it.
    keep_ratio: bool | None = None
    #: A picture cropped to a shape (INBOX 1313): a name from this short list,
    #: never a path, so nothing a client sends reaches a style.
    crop: str | None = Field(default=None, pattern="^(ellipse|diamond|hexagon|triangle)$")
    #: A picture's rectangle crop: percent cut from the top, right, bottom and left
    #: (the Format panel's Trim edges). It shares the clip with `crop`.
    trim: list[Annotated[int, Field(ge=0, le=90)]] | None = Field(default=None, min_length=4, max_length=4)
    #: Edit image: a picture's quarter turn, flips and filters, drawn over the
    #: untouched file (non-destructive). Brightness and contrast are percent, 100 is as-is.
    turn: Literal[0, 90, 180, 270] | None = None
    flip_x: bool | None = None
    flip_y: bool | None = None
    grey: bool | None = None
    bright: int | None = Field(default=None, ge=20, le=200)
    contrast: int | None = Field(default=None, ge=20, le=200)
    #: Voting dots on a board item (Miro's; INBOX 1313): how many it holds.
    #: Content, not a look. Zero is "none", so it is not stored.
    votes: int | None = Field(default=None, ge=1, le=99)
    color: str | None = Field(default=None, max_length=20)
    #: 0 is a topic's pin to the app's own size against a map's theme
    #: (`MAP_APP_DEFAULT_PINS`); 1 to 7 stay refused (`_size_or_pin`).
    font_size: int | None = Field(default=None, ge=0, le=200)
    #: A text box's own fill/border: asked for directly (the properties
    #: panel). Images have no use for either; left `None` there.
    bg: str | None = Field(default=None, max_length=20)
    #: How solid that fill is, and for a diagram how solid its lines are (the
    #: Format panel's Fill opacity and Line opacity; INBOX 1486). 0 is a real
    #: answer (see-through), so absent, not zero, means "as it always was".
    bg_alpha: float | None = Field(default=None, ge=0, le=1)
    line_alpha: float | None = Field(default=None, ge=0, le=1)
    border_color: str | None = Field(default=None, max_length=20)
    #: A picture's border width in pixels (the Format panel's Border; its colour is `border_color`).
    #: Absent or 0 is no border.
    border_width: int | None = Field(default=None, ge=0, le=40)
    #: How the text sits in its box, and whether it is shown as rendered
    #: markdown: asked for directly ("text alignment, font size etc", "rendered
    #: md which is togglable in text boxes and sticky notes"). A field the
    #: schema does not name is dropped silently by Pydantic, which is exactly
    #: how the first attempt at this looked like a frontend bug: the toggle
    #: flipped, the PUT succeeded, and the value came back missing.
    align: str | None = Field(default=None, pattern="^(left|center|right|auto)$")
    #: Where the text sits up and down its box (the owner, 2026-10-10:
    #: "there's no way to vertically centre text"); absent is the top.
    valign: str | None = Field(default=None, pattern="^(middle|bottom)$")
    #: Line spacing (a multiple of the text size) and the space between
    #: letters in pixels (the Format panel's Text tab; WHITEBOARD_PLAN 1355).
    line_height: float | None = Field(default=None, ge=0.8, le=3)
    letter_spacing: float | None = Field(default=None, ge=-5, le=30)
    #: Right to left or vertical, and the words' own opacity (draw.io's Text
    #: tab; INBOX 1510(a)). Absent is left to right and solid.
    text_dir: str | None = Field(default=None, pattern="^(rtl|vertical)$")
    text_alpha: float | None = Field(default=None, ge=0.1, le=1)
    md: bool | None = None
    #: The Format panel's box rows (WHITEBOARD_PLAN 1355, wb5): each corner's
    #: radius in pixels as top-left, top-right, bottom-right, bottom-left; the
    #: space between a text box's edge and its words; and the shadow's offset
    #: and blur (the shadow switch itself is `shadow`). Absent is the default.
    radii: list[Annotated[int, Field(ge=0, le=200)]] | None = Field(default=None, min_length=4, max_length=4)
    pad: int | None = Field(default=None, ge=0, le=80)
    shadow_x: int | None = Field(default=None, ge=-60, le=60)
    shadow_y: int | None = Field(default=None, ge=-60, le=60)
    shadow_blur: int | None = Field(default=None, ge=0, le=60)
    #: A map reference node's target: the note / document / file / bookmark id
    #: this node stands for. Only meaningful for `MAP_REFERENCE_KINDS`; a
    #: topic has nothing to point at and leaves it None.
    ref_id: int | None = Field(default=None, ge=1)
    #: What a reference node says on the map in place of the item's own name
    #: (B38: "a node that I cant edit"). The tree still resolves the item's
    #: name, so renaming the note renames every node that has no caption; one
    #: that was captioned keeps the words its owner chose.
    caption: str | None = Field(default=None, max_length=120)
    #: A collapsed branch hides its children (Coggle's "tidy on demand"), and
    #: a pinned node keeps the position it was dragged to when the map is
    #: re-laid-out. Both are per-node view state on a node that already
    #: carries a JSON blob, so neither earns a column.
    collapsed: bool | None = None
    pinned: bool | None = None
    #: A topic whose `width`/`height` were chosen by hand rather than left at
    #: the creation defaults (MINDMAP_PLAN.md item 177, "resize a topic as a
    #: card resizes"). The flag is the whole point: every topic is created with
    #: both columns already filled, so the numbers cannot say by themselves
    #: whether anyone meant them, and the renderer applies the stored height as
    #: a floor only for a node that carries this. A field the schema does not
    #: name is dropped silently by Pydantic, which is how a toggle like this
    #: comes to look like a frontend bug: the PUT succeeds and the value never
    #: comes back.
    sized: bool | None = None
    #: The node edit strip's four (MINDMAP_PLAN.md §12.1 item 2, Coggle's
    #: text/link/image/icon). Weight and slant are stored here rather than
    #: written into the label as `**markdown**` because §12.0 says so
    #: ("styling is per node ... text size, weight, alignment") and because a
    #: label is already markdown-ish: a bold *marker* would then compose with
    #: whatever inline emphasis the text itself carries, and the two would
    #: fight over the same asterisks. Size and alignment reuse `font_size`
    #: and `align` above, which a text box already stores in exactly the same
    #: units, rather than adding a second way to say the same thing.
    bold: bool | None = None
    italic: bool | None = None
    #: The Format panel's Text tab, draw.io's other font styles (whiteboard-1018):
    #: underline and strikethrough, and a face by name. The names are the map
    #: fonts' (`WB_MAP_FONTS`) and a hand-written one; the stacks live in the
    #: frontend, so no CSS ever arrives from a client.
    underline: bool | None = None
    strike: bool | None = None
    font_family: str | None = Field(default=None, pattern="^(serif|mono|wide|hand)$")
    #: A Phosphor icon name without the `ph-` prefix, or one emoji
    #: (MINDMAP_PLAN.md decision 45). `_icon_name_or_emoji` is the whole
    #: guard: a name is written straight into a class attribute on the node,
    #: so anything but the character set Phosphor's own names use has no
    #: business arriving as one, and an emoji is drawn as text, never markup.
    icon: str | None = Field(default=None, max_length=40)
    #: **An emoji placed on the canvas as a sticker** (decision 44): a text
    #: object drawn as its glyph alone, sized to its box, with no card.
    sticker: bool | None = None
    #: **A sticky note** (the owner, 2026-10-10: "there's no real way to
    #: visually distinguish between a text box and a note"): a text object
    #: drawn as paper, lifted, with a folded corner. Its colour is `bg`.
    sticky: bool | None = None
    #: A sticky note's own say on its folded corner (INBOX 792), over the
    #: board's default (`background.sticky_fold`). `None` follows the board.
    fold: bool | None = None
    #: How a topic is drawn (MINDMAP_PLAN.md §12.1 item 3, decided in §12.0).
    #: Five values and not the plan's eight: `None` is the rounded card this
    #: map has always drawn, and `pill`, `rect`, `ellipse` and `none` are the
    #: four that can be had from a border-radius and a surface. Parallelogram,
    #: trapezoid, cloud and diamond want a clip-path that cuts into the box
    #: the label sits in, which at node size clips the label.
    #: K31 (the owner: "more shape designs for the core idea nodes") added
    #: `circle`, `hexagon`, `diamond` and `cloud` without that clip: the
    #: shape is drawn behind the label and the label is held to its inner
    #: box (library-lazy.css), so nothing is cut.
    #:
    #: `ellipse` arrived with the core node (item 177 names "rounded
    #: rectangle, pill, ellipse" as a core idea's own shape set) and is
    #: offered to every topic rather than only to a core one: a shape that
    #: appears and disappears from the picker depending on another toggle is
    #: a second rule to remember, and the three shapes are all just a radius.
    shape: str | None = Field(default=None, pattern="^(pill|rect|ellipse|none|rounded|circle|hexagon|diamond|cloud|chevron|underline)$")
    #: A topic's effect (MINDMAP_PLAN §14.4's topic effects): a soft shadow
    #: or a glow in its branch colour; `none` keeps one topic plain on a
    #: level that has one.
    effect: str | None = Field(default=None, pattern="^(shadow|glow|none)$")
    #: **A core idea** (MINDMAP_PLAN.md item 177: "a node marked as a core
    #: idea, with its own shape set and a heavier weight"). A mark on the
    #: node, not a third tier in the data model: §12.0 refused a "sub core"
    #: node *type* because `parent_id` and `kind` are all a node has and no
    #: export format this plan round-trips could carry a third one. This is
    #: the other thing that request wanted, which a style field can carry and
    #: both XML exports can write: the node draws heavier and says "start
    #: here", and a map that loses the flag still has every node it had.
    core: bool | None = None
    #: **A topic that is a task** (MINDMAP_PLAN.md §12.2 item 4's first
    #: slice, decision 15): `open` or `done`, absent for a topic that is not
    #: one. One field with two values rather than two flags, so "done but not
    #: a task" cannot be stored. Content, not a look: the map theme never sets
    #: it and the styling reset never clears it (`MAP_CONTENT_FIELDS`).
    task: str | None = Field(default=None, pattern="^(open|done)$")
    #: **A note behind a topic** (MINDMAP_PLAN.md §12.2 item 5, decision 18):
    #: plain text, shown on demand from a marker on the topic. Content, like
    #: `task`: no theme sets it and no reset clears it (`MAP_CONTENT_FIELDS`).
    note: str | None = Field(default=None, max_length=MAX_TOPIC_NOTE_CHARS)
    #: **A frame drawn as a panel** (INBOX 715): a named tint for its ground
    #: and edge, which turns the title inside its top, and one line under the
    #: title saying what goes in it. A name rather than a colour so the
    #: panel is drawn from the theme's own mix in light and dark alike.
    tint: str | None = Field(default=None, pattern="^(neutral|red|amber|green|teal|blue|violet|pink)$")
    hint: str | None = Field(default=None, max_length=120)
    #: **A boundary round this topic's branch** (MINDMAP_PLAN.md decision 19)
    #: and the words over it. Content, like `note`.
    boundary: str | None = Field(default=None, pattern="^(rounded|dashed|cloud)$")
    boundary_label: str | None = Field(default=None, max_length=80)
    #: **A summary of a run of siblings** starting here (decision 20): the
    #: words, and how many siblings the run takes, this topic first.
    summary: str | None = Field(default=None, max_length=80)
    summary_span: int | None = Field(default=None, ge=1, le=100)
    #: **A structure for this topic's branch** (XMind; MINDMAP_PLAN
    #: "canvasdepth, ranked" row 1): the branch under it is laid out as this
    #: layout whatever the map's own is. Content, like a boundary.
    branch_layout: str | None = Field(
        default=None,
        pattern="^(tree-right|tree-left|tree-both|tree-down|radial|logic-right|timeline|fishbone|tree-table)$",
    )
    #: **A callout on a topic** (XMind; canvasdepth2): a few words in a
    #: bubble over its own. Content, like a note.
    callout: str | None = Field(default=None, max_length=200)
    #: **Labels under a topic** (XMind; canvasdepth2): up to eight short tags
    #: drawn as a row under its words. No comma inside one, since the exports
    #: write the list as one comma-joined attribute, as markers are.
    labels: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30, pattern=r"^[^,]+$")]] | None = Field(
        default=None, max_length=8
    )
    #: **Reaction stamps and votes** (Miro; MINDMAP_PLAN 14.4): a count per
    #: stamp from a fixed set of six, each press one more. Content.
    stamps: dict[
        Annotated[str, StringConstraints(pattern=r"^(up|heart|star|question|check|fire)$")],
        Annotated[int, Field(ge=1, le=999)],
    ] | None = None
    #: **Which of those are yours** (INBOX 1493): a press on a stamp is a
    #: toggle per person, so the stamps this notebook's owner put on the topic
    #: are named here, each one counted in `stamps` too. Private to this
    #: install: the exports carry the counts, not whose they are.
    stamped: list[Annotated[str, StringConstraints(pattern=r"^(up|heart|star|question|check|fire)$")]] | None = Field(
        default=None, max_length=6
    )
    #: **Markers** (MINDMAP_PLAN decision 34): a priority 1 to 5, how far
    #: along it is (0 to 100, the menu offers quarters), a flag, and up to six
    #: Phosphor glyph names drawn before the label. Content, not a look: a
    #: reset of the map's looks keeps them.
    priority: int | None = Field(default=None, ge=1, le=5)
    progress: int | None = Field(default=None, ge=0, le=100)
    flag: bool | None = None
    markers: list[Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,40}$")]] | None = Field(
        default=None, max_length=6
    )
    #: **A due date** (§12.2 item 4, decision 37): a calendar day, no time,
    #: so a topic is due on a day wherever the map is opened. Content, like
    #: the markers; a reminder is made from it on request, never by itself.
    due: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
    #: **A start day**, beside `due` (the Gantt view draws a bar from one to the
    #: other for a topic that has both). The same shape and the same kind of
    #: field: content, so a look reset keeps it. Which comes first is not
    #: checked here; the view skips a topic whose start is after its due day.
    start: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
    #: **An audio note** (MINDMAP_PLAN gap 4, decided 2026-11-10): the id of a
    #: recording in the Library, never audio of its own (WORLD_CLASS_PLAN,
    #: "Audio in the notebook", decision 2: a recording is its own object).
    #: Content like `note`. A recording later put in the bin leaves the id
    #: dangling, which the topic's player says in words rather than failing.
    recording: int | None = Field(default=None, ge=1, strict=True)
    #: **The bar down a topic's leading edge** (MINDMAP_PLAN.md item 177:
    #: "per-node left edge: solid, dashed or none"). Two values, because the
    #: third is the absence of the field: a map drawn before this existed and
    #: one whose topic was set back to solid are the same map, and neither
    #: should carry the field into an export.
    spine: str | None = Field(default=None, pattern="^(dashed|none|solid)$")
    #: **A tint of the topic's colour across its whole card** (the owner:
    #: "the option to fill an individual node or have it cascade to its
    #: children as well"). `self` fills this topic, `branch` fills it and
    #: everything under it, `none` keeps one topic unfilled inside a filled
    #: branch; unfilled is the absence of the field. The cascade is worked out
    #: when the map is drawn (`wbMapFills`), the way branch colour is, so a
    #: topic added to a filled branch later is filled too.
    #: `solid` (MINDMAP_PLAN.md §14) is this topic filled in its branch
    #: colour with the ink that reads on it, the look a centre has by default.
    fill: str | None = Field(default=None, pattern="^(self|branch|none|solid)$")
    #: Where a topic points. Held to the three schemes a link on a page may
    #: safely have: `javascript:` and `data:` are the two this rejects by
    #: existing, and the frontend's own `wbMapOpenLink` refuses anything else
    #: again at the click (a stored value predating this validator, or one
    #: written by a tool, is still not a hole).
    link: str | None = Field(default=None, max_length=500)
    #: What the line *into* this node says (MINDMAP_PLAN.md §12.1 items 3 and
    #: 4, "label on the link"). Stored on the child rather than anywhere else
    #: because a tree edge has no row of its own: it is `parent_id`, so the
    #: only thing that can carry its label is one of its two ends, and the
    #: child is the end that has exactly one incoming edge.
    edge_label: str | None = Field(default=None, max_length=80)
    #: And how that line is drawn (§12.1 item 4, the link radial). Stored on
    #: the child for the same reason as its label. `curve` is the default and
    #: is what an unset value means, so a map made before these existed draws
    #: exactly as it did.
    edge_style: str | None = Field(default=None, pattern="^(curve|elbow|straight)$")
    edge_dashed: bool | None = None
    #: **How heavy that line is, and whether it ends in a head**
    #: (MINDMAP_PLAN.md item 177: "connection line styles: per-branch
    #: thickness, dash and arrowhead, managed from the map strip rather than
    #: by one global rule"). On the child with the rest of the edge's
    #: properties, for the reason `edge_label` gives above.
    #:
    #: Three thicknesses rather than a number of pixels: the value has to
    #: scale two drawings, the tapered ribbon the default curve is and the
    #: stroke the other shapes keep, so it is a step the frontend turns into
    #: each, and a map is read by one branch being heavier than its neighbour
    #: rather than by any absolute width.
    #:
    #: The arrowhead is three-valued on purpose, `on`, `off` and unset: a
    #: ribbon carries its direction in its taper and draws no head, a plain
    #: stroke has had one since the branch-direction report, so "unset" means
    #: "whatever this line shape does" and the two words are the override.
    edge_width: str | None = Field(default=None, pattern="^(thin|thick|normal)$")
    edge_arrow: str | None = Field(default=None, pattern="^(on|off)$")
    #: **Where the line into this topic bends** (MINDMAP_PLAN.md §12.1 item
    #: 5's third, "the control points on a curve drag to reshape it"). On the
    #: child, with the rest of the edge's properties, for the reason
    #: `edge_label` gives above: a tree edge is `parent_id` and has no row of
    #: its own, so the only thing that can carry a control point is one of its
    #: two ends, and the child is the end with exactly one incoming line.
    #:
    #: **Two fractions of the line's own length, not two board coordinates**,
    #: and that is the whole of why this is storable at all. The waypoint is
    #: written in the frame the line itself defines: `edge_slide` along it from
    #: the halfway mark, `edge_bend` across it. A pair of board coordinates
    #: would be correct until either end moved, which on a map that tidies
    #: itself is about one gesture later; a pair of fractions rides the tidy,
    #: the drag, the zoom and the layout switch unchanged, and the same numbers
    #: mean the same shape on a map exported and read back at another size.
    #:
    #: Unset is the line every map has always drawn, so a map made before this
    #: existed carries neither field and draws exactly as it did.
    edge_bend: float | None = Field(default=None, ge=-4, le=4)
    #: Held inside the ends rather than to the full -1..1 the frame allows: a
    #: waypoint dragged past an anchor turns the curve back on itself, which
    #: is a shape nobody asks for and a tangle nobody can undo by dragging.
    edge_slide: float | None = Field(default=None, ge=-0.45, le=0.45)
    #: **Which sides that line joins** (K31, the owner: "I want to be able to
    #: have more say in which sides the connections come from and to"):
    #: `edge_from` is the parent's side it leaves, `edge_to` this topic's side
    #: it enters. Unset is Auto, the side the layout picks, so a map made
    #: before these existed draws exactly as it did.
    edge_from: str | None = Field(default=None, pattern="^(top|right|bottom|left)$")
    edge_to: str | None = Field(default=None, pattern="^(top|right|bottom|left)$")
    #: **A picture in a topic** (MINDMAP_PLAN.md §12.1 item 2's fourth,
    #: Coggle's text/link/image/icon). The url of something already uploaded
    #: through `/media/upload`, which is the path a board image, a note
    #: attachment and a pasted picture all already take: a second upload route
    #: for the same bytes would be a second place for the captioning, the OCR
    #: and the orphan sweep to be forgotten.
    #:
    #: Held to the same allowlist an image *object* is (`MEDIA_URL_RE`), by
    #: the validator below rather than at the route, because this value also
    #: arrives from an imported file: the two XML imports write straight into
    #: `data` through `WhiteboardObjectData`, and a `_image` attribute in a
    #: file somebody was sent is exactly the door an off-origin url would come
    #: through.
    image: str | None = Field(default=None, max_length=300)
    #: A topic's place among its siblings (INBOX 445). Absent means the
    #: topic's own id, so creation order is still the order of every map made
    #: before this field existed; moving a topic up or down gives it a value
    #: between its neighbours' keys. A key, not a rank, so one move writes one
    #: or two rows rather than renumbering the whole branch.
    order: float | None = Field(default=None, ge=-1e12, le=1e12)

    @field_validator("markers", "labels", mode="before")
    @classmethod
    def _markers_from_attribute(cls, value):
        """An export writes the list as one comma-joined attribute
        (`_markers="star,warning"`); read back, it is a list again."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("stamps", mode="before")
    @classmethod
    def _stamps_from_attribute(cls, value):
        """An export writes the counts as one attribute (`up:3,star:1`)."""
        if isinstance(value, str):
            pairs = (part.split(":", 1) for part in value.split(",") if ":" in part)
            return {name.strip(): count.strip() for name, count in pairs}
        return value

    @field_validator("stamped")
    @classmethod
    def _stamped_have_a_count(cls, value, info):
        """A stamp with no count cannot be yours; the rest is kept in order."""
        if not value:
            return value
        counted = info.data.get("stamps") or {}
        kept = [name for name in dict.fromkeys(value) if name in counted]
        return kept or None

    @field_validator("icon")
    @classmethod
    def _icon_name_or_emoji(cls, value: str | None) -> str | None:
        if not value:
            return value
        if ICON_NAME_RE.match(value) or _is_one_emoji(value):
            return value
        raise ValueError("An icon is a Phosphor name or one emoji")

    @field_validator("font_size")
    @classmethod
    def _size_or_pin(cls, value: int | None) -> int | None:
        """8 to 200, or 0 for "the app's own size" (decision 9). Anything in
        between is a map nobody can read, refused as it always was."""
        if value is not None and 0 < value < 8:
            raise ValueError("A text size is 8 or more")
        return value

    @field_validator("image")
    @classmethod
    def _same_origin_picture(cls, value: str | None) -> str | None:
        """A picture in a topic is one of this install's own uploads or it is
        nothing. Same allowlist as an image object's `url`, and the same
        reasoning: a prefix test on `/media/` passes
        `/media/../../../etc/passwd`, and an arbitrary address would make a
        node a way to call out of an app whose whole promise is that it never
        does."""
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if not MEDIA_URL_RE.match(text):
            raise ValueError("A topic's picture has to be a /media/... upload from this notebook")
        return text

    @field_validator("link")
    @classmethod
    def _safe_link_scheme(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        lowered = text.lower()
        #: A note link from Link..., A note... is the app's own route hash
        #: ("#/notes/12", `wbItemLink`); it was refused with 422 (review, 2026-10-27).
        if not (lowered.startswith(("http://", "https://", "mailto:")) or _APP_ROUTE_LINK.match(text)):
            raise ValueError("A link must be an http, https or mailto address, or a link to something in this notebook")
        return text


class WhiteboardObjectBase(BaseModel):
    kind: str
    data: WhiteboardObjectData
    board_id: int | None = None
    x: Coord = 0.0
    y: Coord = 0.0
    z: Layer = 0
    width: float = Field(default=200.0, ge=20, le=4000)
    height: float = Field(default=120.0, ge=20, le=4000)
    rotation: float | None = Field(default=None, ge=-360, le=360)
    group_id: str | None = Field(default=None, max_length=GROUP_ID_MAX_LEN)

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in VALID_OBJECT_KINDS:
            raise ValueError(
                f"Unknown object kind {value!r}: expected one of "
                + ", ".join(sorted(VALID_OBJECT_KINDS))
            )
        return value


class WhiteboardObjectOut(BaseModel):
    id: int
    kind: str
    data: WhiteboardObjectData
    board_id: int | None
    x: StoredCoord
    y: StoredCoord
    z: StoredLayer
    width: float
    height: float
    rotation: float | None
    group_id: str | None
    #: A map node's parent, NULL for everything on an ordinary whiteboard.
    parent_id: int | None = None


# --- the event log for a board (WORLD_CLASS_PLAN B1, Brief 7) ---------------
#
# The entry managers record one event per write with whole-field values, which
# is what lets a note replay to its current state and a version be put back.
# A board recorded nothing at all, so the half of B1's own wording that says
# "and `routes_whiteboard.py`'s manager" was not true: a card could be moved,
# a text box rewritten and a branch deleted with no record of who did it or
# what it said before.
#
# **What a board's replayable entity is.** A note is one row and replays to
# one dict. A board is not: it is a note plus every card, sketch and object
# on it. So the entity here is the *item*, one of `whiteboard_node`,
# `whiteboard_sketch` and `whiteboard_object`, each replaying to its own
# current state through the same `events.replay`; the board's own events
# (`board` created, duplicated, its type or layout changed) are on the board.
# A board's whole state is the union of its items' replays, which is the only
# reading that keeps `replay` one function rather than one per surface.
#
# Every write below is wrapped in `@events.writes`, not left to remember a
# call: the decorator is what makes "one write, one event" true by
# construction, so a route that grows a second write inside it folds rather
# than quietly recording twice. The exception is any route that calls an
# entry manager (`rename_board` through `update_entry`): opening a scope
# there would fold the *note's* own edit into the board's event and take it
# out of that note's history, which is a worse loss than the tidier shape is
# worth. Those record beside the manager's event instead, and only for the
# fields the manager does not know about.




def _object_to_out(obj: WhiteboardObject) -> WhiteboardObjectOut:
    return WhiteboardObjectOut(
        id=obj.id,
        kind=obj.kind,
        data=WhiteboardObjectData(**json.loads(obj.data)),
        board_id=obj.board_id,
        x=obj.x,
        y=obj.y,
        z=obj.z,
        width=obj.width,
        height=obj.height,
        rotation=obj.rotation,
        group_id=obj.group_id,
        parent_id=obj.parent_id,
    )


def _require_table_cells(cells: list[list[str]] | None) -> None:
    """A table is a rectangle of cells: 1 to 50 rows of 1 to 20, all as long."""
    widths = {len(row) for row in cells or []}
    if not cells or len(widths) != 1 or not 1 <= widths.pop() <= MAX_TABLE_COLS:
        raise HTTPException(
            status_code=422,
            detail=f"A table is 1 to {MAX_TABLE_ROWS} rows of 1 to {MAX_TABLE_COLS} cells, every row as long as the first.",
        )


def _require_table_merges(data: WhiteboardObjectData) -> None:
    """Merges lie inside the grid, span more than one cell and never overlap; row heights are one per row."""
    rows, cols = len(data.cells), len(data.cells[0])
    if data.row_heights is not None and len(data.row_heights) != rows:
        raise HTTPException(status_code=422, detail="A table needs one height for each of its rows.")
    taken: set[tuple[int, int]] = set()
    for m in data.merges or []:
        spots = {(r, c) for r in range(m.r, m.r + m.rs) for c in range(m.c, m.c + m.cs)}
        if m.r + m.rs > rows or m.c + m.cs > cols or len(spots) < 2 or spots & taken:
            raise HTTPException(status_code=422, detail="A merged cell has to lie inside the table, cover two cells or more and not overlap another.")
        taken |= spots


def _require_object_data(body: WhiteboardObjectBase) -> None:
    if body.kind == "image":
        if not body.data.url or not MEDIA_URL_RE.match(body.data.url):
            raise HTTPException(
                status_code=422,
                detail="An image has to be one that was uploaded to Tessellate first.",
            )
    elif body.kind in ("text", FRAME_KIND, MAP_TOPIC_KIND) and body.data.content is None:
        raise HTTPException(
            status_code=422, detail=f"A {body.kind} item needs some content."
        )
    elif body.kind == DIAGRAM_KIND and not (body.data.mermaid or "").strip():
        raise HTTPException(status_code=422, detail="A diagram needs its Mermaid source.")
    elif body.kind == TABLE_KIND:
        _require_table_cells(body.data.cells)
        if body.data.col_widths is not None and len(body.data.col_widths) != len(body.data.cells[0]):
            raise HTTPException(status_code=422, detail="A table needs one width for each of its columns.")
        _require_table_merges(body.data)
    elif body.kind in MAP_REFERENCE_KINDS and body.data.ref_id is None:
        # A reference node with nothing to reference is the map equivalent of
        # a card pointing at note 9999 (this module's own opening comment): it
        # stores fine, draws as an empty box, and there is no way to tell from
        # the UI what it was ever meant to be.
        raise HTTPException(
            status_code=422,
            detail=f"A {body.kind} node needs to point at an existing {body.kind}.",
        )


class WhiteboardStateOut(BaseModel):
    nodes: list[WhiteboardNodeOut]
    sketches: list[WhiteboardSketchOut]
    objects: list[WhiteboardObjectOut] = []
    #: The board's look (decision 24), so opening a board draws it at once.
    background: dict = {}
    #: Its named layers, `[{id, name, hidden, locked}]` (canvasdepth).
    layers: list[dict] = []
