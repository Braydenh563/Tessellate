"""A board's card in the library: the preview drawn from its items, its cache and fingerprint, and the thumbnail routes.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from tessellate.repo import whiteboard as whiteboard_repo
from tessellate.repo.content import BOARDS
from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch
from collections import OrderedDict
from sqlalchemy.orm import Session
from tessellate.core import board_thumbs, deps
from sqlalchemy import func, select
from tessellate.core.deps import get_session
from starlette.concurrency import run_in_threadpool
from tessellate.api.wb_model import MAP_REFERENCE_KINDS, MAP_TOPIC_KIND
from tessellate.api.wb_board import _board_entry, _board_theme

router = APIRouter()


#: The most points a board's thumbnail carries. A minimap is a shape, not a
#: census: past a few dozen dots the picture stops distinguishing boards and
#: starts being noise, and the payload grows with every card anyone adds.
PREVIEW_POINTS = 40


def _preview_points(rows: list[tuple[float, float]]) -> list[list[float]]:
    """Normalise raw board coordinates into 0..1 for a thumbnail.

    Evenly sampled rather than truncated: `rows[:40]` of a 300-card board is
    whatever 40 cards were inserted first, which is not the board's shape.
    A stride keeps the sample spread across the whole board.

    A board whose content is a single point, or a perfectly straight row of
    cards, has zero extent on at least one axis, hence the guard, which
    centres that axis instead of dividing by zero.
    """
    if not rows:
        return []
    stride = max(1, len(rows) // PREVIEW_POINTS)
    sampled = rows[::stride][:PREVIEW_POINTS]
    xs = [x for x, _ in sampled]
    ys = [y for _, y in sampled]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x
    span_y = max_y - min_y
    return [
        [
            round((x - min_x) / span_x, 3) if span_x else 0.5,
            round((y - min_y) / span_y, 3) if span_y else 0.5,
        ]
        for x, y in sampled
    ]


#: How much of a card's own text the thumbnail carries. Enough to tell two
#: boards apart at a glance and no more, the label is drawn at a few pixels
#: high, so a longer string is only bytes.
PREVIEW_LABEL_CHARS = 28

#: What a thing is drawn at on the canvas when it has no size of its own,
#: so a thumbnail draws the same picture the board does. These mirror
#: `WB_CARD_DEFAULT_SIZE`, `WB_MAP_NODE_W/H` and the sketch's own box in
#: frontend/js/whiteboard.js; a card's width and height are nullable columns and
#: a sketch has none at all, so without a figure here every one of them would
#: have to be drawn as a point.
PREVIEW_DEFAULT_SIZES = {
    "card": (250.0, 150.0),
    "sketch": (200.0, 150.0),
    MAP_TOPIC_KIND: (200.0, 56.0),
}
PREVIEW_FALLBACK_SIZE = (200.0, 120.0)


#: The branch colours a map's thumbnail draws, in the order a first-level
#: branch claims them.
#:
#: **This is `d3.schemeTableau10`, copied.** The canvas takes that scale from
#: d3 at runtime (`wbMapColors`, whiteboard.js), and the thumbnail has to
#: agree with the canvas or the same map is two different pictures depending
#: on where you look at it. The server has no d3, and shipping a *branch
#: index* instead would only move the same duplication into app.js, where the
#: preview is drawn and d3 is not guaranteed to have loaded. Copied here, once,
#: with `tests/test_board_preview.py` asserting a preview's colours come from
#: this list.
MAP_BRANCH_PALETTE = [
    "#4e79a7",
    "#f28e2c",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc949",
    "#af7aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ab",
]

#: **Every palette a map can pick, and the only copy of any of them**
#: (MINDMAP_PLAN.md decision 8). The canvas used to take its colours from
#: d3 at runtime while this file kept a copy for the thumbnail, so a second
#: palette would have been two more lists to keep in step. Now `/tree` hands
#: the canvas the resolved list (`MapTreeOut.palette`) and the thumbnail reads
#: the same name, so the two drawings cannot disagree. `classic` is the one
#: every map had (Tableau 10); the other three are d3's own categorical
#: schemes, copied: Dark2, Set2 and Category10.
MAP_BRANCH_PALETTES: dict[str, list[str]] = {
    "classic": MAP_BRANCH_PALETTE,
    "deep": ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666"],
    "soft": ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3"],
    "vivid": [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ],
    #: The four added 2026-10-05 (§12.2 item 7: eight curated palettes).
    #: Set1 without its yellow, Paired without its pale green, d3's
    #: Observable10, and the dark ends of ColorBrewer's BrBG, PRGn and PiYG:
    #: each colour at least 1.6:1 on white, so a 3px branch never vanishes
    #: (`test_every_palette_colour_is_a_line_on_the_light_paper`).
    "bold": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#999999"],
    "paired": [
        "#1f78b4", "#33a02c", "#e31a1c", "#ff7f00", "#6a3d9a",
        "#b15928", "#a6cee3", "#fb9a99", "#fdbf6f", "#cab2d6",
    ],
    "bright": [
        "#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951",
        "#ff8ab7", "#a463f2", "#97bbf5", "#9c6b4e", "#9498a0",
    ],
    "earth": [
        "#8c510a", "#35978f", "#762a83", "#c51b7d", "#4d9221",
        "#bf812d", "#01665e", "#9970ab", "#b35806", "#542788",
    ],
}


def _board_palette(theme: dict) -> list[str]:
    """The branch colours a themed map draws, `classic` when it picked none."""
    return MAP_BRANCH_PALETTES.get(theme.get("palette") or "classic", MAP_BRANCH_PALETTE)


def _branch_children(parents: dict[int, int | None]) -> dict[int | None, list[int]]:
    """Each node's children by parent, a missing parent read as a root, and a
    root's children ordered by the oldest id in each branch.

    **A branch is as old as its oldest topic** (the owner, 2026-10-10: "when
    I added a mindmap node in between, it changed the colour of the other
    nodes in the branch"). A topic put between a root and its child is the
    newest id on the map, so ordering a root's children by their own id sent
    the moved branch to the end of the palette and shifted every branch after
    it. Ordered by the oldest id in each branch, it takes the place (and the
    colour) of the branch it now holds. A map nobody re-parented orders as
    before: a branch's own topic is its oldest. `canvas.wbMapColors` agrees.
    """
    children: dict[int | None, list[int]] = {}
    for node_id, parent_id in parents.items():
        key = parent_id if parent_id in parents else None
        children.setdefault(key, []).append(node_id)
    walk_order: list[int] = []
    visited: set[int] = set()
    pending = list(children.get(None, []))
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        walk_order.append(node_id)
        pending.extend(children.get(node_id, []))
    oldest: dict[int, int] = {}
    for node_id in reversed(walk_order):
        oldest[node_id] = min([node_id, *(oldest[c] for c in children.get(node_id, []) if c in oldest)])
    #: Every list, not only a root's: rainbow colours a topic by its place among its siblings at any depth.
    for siblings in children.values():
        siblings.sort(key=lambda c: oldest.get(c, c))
    return children


def _rainbow_pick(palette: list[str], slot: int, inherited: str | None) -> str:
    """The `slot`th colour of the palette that is not the parent's, so a child
    never wears its parent's colour (`wbMapRainbowPick` is the canvas copy)."""
    choices = [c for c in palette if c != inherited] or palette
    return choices[slot % len(choices)]


def _map_branch_colors(
    parents: dict[int, int | None],
    own: dict[int, str | None],
    palette: list[str] | None = None,
    rainbow: bool = False,
) -> dict[int, str]:
    """Every map node's branch colour, by object id: Coggle's rule, which the
    canvas already follows.

    A first-level topic (a *child of a root*, not a root) takes the next
    palette entry, and every descendant inherits it unless it sets its own
    `data.color`. Starting at the roots instead would paint a whole map one
    colour, which is the one thing branch colour exists not to do.

    Iterative rather than recursive: a map imported from a deep OPML file is
    still a tree, but nothing here should be able to turn a 1,000-deep import
    into a `RecursionError` in a *thumbnail*. `seen` also makes a cycle (a
    dangling or corrupt `parent_id`) terminate rather than hang, and any node
    whose parent is missing is treated as a root, which is what every other
    reader of `parent_id` does.
    """
    palette = palette or MAP_BRANCH_PALETTE
    children = _branch_children(parents)
    colors: dict[int, str] = {}
    seen: set[int] = set()
    branch = 0
    # (id, the colour inherited from above, depth from its root, place among siblings)
    stack: list[tuple[int, str | None, int, int]] = [
        (node_id, None, 0, 0) for node_id in reversed(children.get(None, []))
    ]
    while stack:
        node_id, inherited, depth, slot = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        colour = own.get(node_id)
        if colour is None and depth == 1:
            # Depth 1 *is* the branch, and it is the only depth that ever
            # takes a new colour: the client decides this by asking whether
            # the colour handed down was null, which is true for exactly one
            # generation, a root's own children.
            colour = palette[branch % len(palette)]
            branch += 1
        if colour is None and rainbow and depth > 1:
            colour = _rainbow_pick(palette, slot, inherited)
        if colour is None:
            colour = inherited
        if colour:
            colors[node_id] = colour
        kids = children.get(node_id, [])
        stack.extend(
            (child_id, colour, depth + 1, slot_of) for slot_of, child_id in reversed(list(enumerate(kids)))
        )
    return colors


def _preview_size(
    kind: str, width: float | None, height: float | None
) -> tuple[float, float]:
    """How big this thing is on the board, falling back to what the canvas
    would draw it at.

    A card's `width`/`height` are nullable columns and a sketch has neither,
    so "no size stored" is the common case rather than the odd one, and it
    means "the default", not "zero".
    """
    default = PREVIEW_DEFAULT_SIZES.get(kind, PREVIEW_FALLBACK_SIZE)
    w = float(width) if width else default[0]
    h = float(height) if height else default[1]
    return (max(1.0, w), max(1.0, h))


#: **A drawn stroke's own box, from its path data.** The server's copy of
#: `wbPathBBox` (whiteboard.js), and it is a copy on purpose: the thumbnail has
#: to be the same picture as the canvas, and the canvas measures a sketch by its
#: path because a sketch has no width or height columns to measure instead.
#:
#: Why the preview needs it at all, which is the whole of INBOX 164's "one
#: squiggle": a sketch is stored with `x = 0, y = 0` and its strokes written in
#: absolute board coordinates (see the save in whiteboard.js: `x: 0, y: 0`), so
#: a preview that reads `sketch.x`/`sketch.y` puts **every** sketch on a board
#: at the board's origin, at one default size. Measured on a board with eight of
#: them: eight marks at one position (8.8, 45.5) and one size (29.4x14.7), which
#: paints as a single squiggle in the corner however much was drawn.
#:
#: The same command set the canvas handles, and no more: `M`/`L` absolute
#: points, `C` through its control points (a bound, not the true curve extent,
#: which is what the canvas settles for too), relative `h`/`v`, and the `a`
#: half-arc pair the ellipse tool draws, whose own note in whiteboard.js
#: explains why reading the chord's midpoint is exact for that one shape. An
#: unparseable or empty path returns None and the caller falls back to the
#: stored position and the default size, which is what every sketch got before.
_PATH_TOKENS = re.compile(r"[MLCHVAZmlchvaz]|-?\d*\.?\d+(?:[eE]-?\d+)?")


def _path_bbox(d: str) -> tuple[float, float, float, float] | None:
    """`(min_x, min_y, width, height)` of an SVG path, or None."""
    tokens = _PATH_TOKENS.findall(d or "")
    if not tokens:
        return None
    i = 0
    px = py = 0.0
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def visit(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x), max(max_y, y)

    def number() -> float:
        nonlocal i
        try:
            value = float(tokens[i])
        except (IndexError, ValueError):
            raise _PathEnd from None
        i += 1
        return value

    try:
        while i < len(tokens):
            cmd = tokens[i]
            i += 1
            if cmd in ("M", "L"):
                px, py = number(), number()
                visit(px, py)
            elif cmd == "C":
                points = [number() for _ in range(6)]
                visit(points[0], points[1])
                visit(points[2], points[3])
                visit(points[4], points[5])
                px, py = points[4], points[5]
            elif cmd == "h":
                px += number()
                visit(px, py)
            elif cmd == "v":
                py += number()
                visit(px, py)
            elif cmd == "a":
                rx, ry = number(), number()
                for _ in range(3):  # rotation and the two flags: not a bound
                    number()
                ex, ey = number(), number()
                mid_x, mid_y = px + ex / 2, py + ey / 2
                visit(mid_x - rx, mid_y - ry)
                visit(mid_x + rx, mid_y + ry)
                px, py = px + ex, py + ey
            # Z/z closes back to the last M and moves nothing.
    except _PathEnd:
        # Path data ended mid-command; keep the bounds accumulated so far.
        # This function is intentionally tolerant of truncated stroke paths.
        pass
    if min_x == float("inf"):
        return None
    return (min_x, min_y, max_x - min_x, max_y - min_y)


class _PathEnd(Exception):
    """A path that ran out of numbers mid-command: take what was read."""


#: The floor on a drawn stroke's own extent, in board pixels. A single dot or a
#: perfectly straight horizontal line has a zero-height box, and a zero-height
#: box normalises to nothing and draws nothing at all: the one thing a preview
#: of a drawing must not do is leave the drawing out.
PREVIEW_SKETCH_MIN = 8.0


def _sketch_preview(
    sketch: WhiteboardSketch,
) -> tuple[float, float, float, float, str | None, str | None]:
    """`(x, y, w, h, shape, colour)` for one drawn stroke.

    The position is the stroke's own top-left corner in board coordinates, plus
    whatever `x`/`y` the row carries: a freshly drawn sketch has 0, 0 there and
    a moved one has the offset a drag applied, and the canvas adds the two the
    same way (`wbItemBBox` reads the path, the group carries the translate).

    `shape` is the tool it was drawn with, which is what lets the thumbnail draw
    a rectangle as a rectangle and a pen stroke as a scribble rather than
    drawing one generic wave for all of them; `colour` is its own ink, so a
    board drawn in three colours previews in three colours.
    """
    data: dict = {}
    try:
        parsed = json.loads(sketch.data or "{}")
        data = parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        data = {}
    shape = data.get("shape")
    shape = shape if isinstance(shape, str) and shape else None
    colour = data.get("color")
    colour = colour if isinstance(colour, str) and colour else None
    box = _path_bbox(str(data.get("d") or ""))
    ox, oy = float(sketch.x), float(sketch.y)
    if box is None:
        w, h = _preview_size("sketch", None, None)
        return (ox, oy, w, h, shape, colour)
    return (
        ox + box[0],
        oy + box[1],
        max(PREVIEW_SKETCH_MIN, box[2]),
        max(PREVIEW_SKETCH_MIN, box[3]),
        shape,
        colour,
    )


def _preview_items(
    rows: list[tuple[float, float, str, str, str | None, float, float, str | None]],
) -> list[dict]:
    """The same normalisation as `_preview_points`, carrying what each item
    *is*, what it says, what colour it is and **how big it is**.

    Sampling happens before normalising and both use one stride, so the
    labels can never end up attached to the wrong positions, which is the
    obvious way to break this while every number still looks plausible.

    `color` is omitted rather than sent as null for the items that have none
    (every card, every sketch, every object on an ordinary board): a
    twenty-board list ships eight hundred of these.

    **`w` and `h` are why a board stopped previewing as identical grey
    blobs** (INBOX 68, the owner twice: "Boards & maps preview looks so bad,
    especially in the dashboard"). Positions alone cannot say that the banner
    across the top of a board is six times the width of the sticky under it,
    so every item was drawn as the same rectangle and the picture was of the
    renderer rather than of the board. They are fractions of the same span
    the positions were normalised into, so the client multiplies them by
    exactly what it multiplies `x` and `y` by, and a span of zero (one item,
    or a straight line of them) leaves them out rather than shipping an
    infinity.
    """
    if not rows:
        return []
    stride = max(1, len(rows) // PREVIEW_POINTS)
    sampled = rows[::stride][:PREVIEW_POINTS]
    points = _preview_points([(x, y) for x, y, _, _, _, _, _, _ in sampled])
    xs = [x for x, _, _, _, _, _, _, _ in sampled]
    ys = [y for _, y, _, _, _, _, _, _ in sampled]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    items = []
    for (nx, ny), (_, _, kind, label, colour, w, h, shape) in zip(points, sampled, strict=True):
        item = {"x": nx, "y": ny, "kind": kind, "label": label}
        if colour:
            item["color"] = colour
        #: Only where there is one, for the reason `color` is omitted: a
        #: twenty-board list would otherwise ship eight hundred nulls.
        if shape:
            item["shape"] = shape
        if span_x > 0 and span_y > 0:
            item["w"] = round(w / span_x, 4)
            item["h"] = round(h / span_y, 4)
        items.append(item)
    return items


#: How far a thumbnail's shape is allowed to depart from a square, as
#: width/height. A board 30 times wider than it is tall is a real board, and
#: letterboxed honestly into a Library card it is a two-pixel band of grey:
#: past this the ratio stops being information and starts being an empty card.
PREVIEW_ASPECT_RANGE = (0.5, 3.0)


def _card_label(entry: Entry | None) -> str:
    """What is written on a card in a thumbnail: its note's title."""
    from tessellate.entry import manager

    if entry is None or entry.is_private:
        return ""
    # A card *is* a note, so its own title (or first words) is what is written
    # on it. A private note contributes its position and nothing else: the
    # same rule the Connections block and the Library's file-usage chips follow.
    text = manager.readable_content(entry)
    return (manager.extract_title(text) or text.strip().split("\n")[0])[:PREVIEW_LABEL_CHARS]


def _card_preview_rows(db: Session, on) -> list[tuple]:  # noqa: ANN001
    """One preview row per card on the board."""
    rows: list[tuple] = []
    for node in db.scalars(select(WhiteboardNode).where(on(WhiteboardNode))):
        label = _card_label(db.get(Entry, node.entry_id))
        rows.append(
            (
                float(node.x),
                float(node.y),
                "card",
                label,
                None,
                *_preview_size("card", node.width, node.height),
                None,
            )
        )
    return rows


def _link_preview(data: dict, boxes: dict) -> tuple | None:
    """A connector's preview row, from the centres of what it joins.

    A link has no path of its own (the canvas computes it from its two ends
    every render), so it fell through to the default box at the origin and
    drew as a pen scribble (dog2 item 14: "a straight link draws as a wavy
    squiggle"). Each end is the joined item's centre, or the free point it
    stops at; an end that cannot be found leaves the link out rather than
    drawing it somewhere it is not. `line-rise` is a line that climbs left to
    right, since a box alone cannot say which diagonal it runs along, and
    `line-flat` a level one (within 1 in 12), which the thumbnail's minimum
    block height would otherwise tilt. An upright one is narrow as it is.
    """
    ends = []
    for side in ("source", "target"):
        point = data.get(f"{side}Point")
        if isinstance(point, dict) and "x" in point and "y" in point:
            try:
                ends.append((float(point["x"]), float(point["y"])))
                continue
            except (TypeError, ValueError):
                return None
        box = boxes.get((data.get(f"{side}Kind") or "node", data.get(f"{side}Id")))
        if box is None:
            return None
        ends.append((box[0] + box[2] / 2, box[1] + box[3] / 2))
    (x1, y1), (x2, y2) = ends
    colour = data.get("color")
    colour = colour if isinstance(colour, str) and colour else None
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    if dy < PREVIEW_SKETCH_MIN or dy * 12 < dx:
        shape = "line-flat"
    else:
        shape = "line-rise" if (x2 - x1) * (y2 - y1) < 0 else "line"
    return (
        min(x1, x2),
        min(y1, y2),
        max(PREVIEW_SKETCH_MIN, abs(x2 - x1)),
        max(PREVIEW_SKETCH_MIN, abs(y2 - y1)),
        shape,
        colour,
    )


def _sketch_preview_rows(db: Session, on) -> list[tuple]:  # noqa: ANN001
    """One preview row per drawn stroke on the board."""
    rows: list[tuple] = []
    links: list[dict] = []
    #: What a connector's ends can be joined to, by (kind, id): a card is
    #: "node", as the canvas stores it.
    boxes: dict = {}
    for node in db.scalars(select(WhiteboardNode).where(on(WhiteboardNode))):
        boxes[("node", node.id)] = (float(node.x), float(node.y), *_preview_size("card", node.width, node.height))
    for obj in db.scalars(select(WhiteboardObject).where(on(WhiteboardObject))):
        boxes[("object", obj.id)] = (
            float(obj.x),
            float(obj.y),
            *_preview_size(obj.kind or "object", obj.width, obj.height),
        )
    for sketch in db.scalars(select(WhiteboardSketch).where(on(WhiteboardSketch))):
        try:
            parsed = json.loads(sketch.data or "{}")
        except (TypeError, ValueError):
            parsed = {}
        if isinstance(parsed, dict) and str(parsed.get("type") or "").startswith("link-"):
            links.append(parsed)
            continue
        #: **From the strokes, not from the row.** A sketch's `x`/`y` are 0 for
        #: every stroke the drawing tools make, with the path in absolute board
        #: coordinates, so reading them put every sketch on a board at the
        #: origin at one default size: eight of them measured as eight marks at
        #: one position and one size, which is INBOX 164's single squiggle.
        sx, sy, sw, sh, shape, colour = _sketch_preview(sketch)
        boxes[("sketch", sketch.id)] = (sx, sy, sw, sh)
        rows.append((sx, sy, "sketch", "", colour, sw, sh, shape))
    for data in links:
        row = _link_preview(data, boxes)
        if row is not None:
            sx, sy, sw, sh, shape, colour = row
            rows.append((sx, sy, "sketch", "", colour, sw, sh, shape))
    return rows


def _object_data(obj) -> dict:  # noqa: ANN001
    """An object's `data` as a dict, whatever was stored."""
    try:
        parsed = json.loads(obj.data)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _object_preview_rows(db: Session, on) -> tuple[list[tuple], list[int | None], dict, dict, dict]:  # noqa: ANN001
    """The board's objects as preview rows, with the tree the branch colours need:
    `(rows, owners, parent_of, tree_parents, own_colors)`.

    `parent_of` carries only real parents and is what the edges are drawn
    from; `tree_parents` holds every map object's parent (roots at None) and
    `own_colors` its own `data.color`, which the branch-colour walk needs.
    """
    rows: list[tuple] = []
    owners: list[int | None] = []
    parent_of: dict[int, int] = {}
    tree_parents: dict[int, int | None] = {}
    own_colors: dict[int, str | None] = {}
    # Ordered by id so the branch colours fall in the same order the canvas
    # gives them: the client walks the objects in the order `GET /whiteboard`
    # returns them, which is this one.
    objects = db.scalars(select(WhiteboardObject).where(on(WhiteboardObject)).order_by(WhiteboardObject.id))
    for obj in list(objects):
        data = _object_data(obj)
        label = ""
        if obj.kind == MAP_TOPIC_KIND or obj.kind == "text":
            # A map's thumbnail is mostly topics, and a topic *is* its text,
            # a tree of unlabelled boxes tells two maps apart no better than
            # a scatter of dots did. A whiteboard's text boxes and sticky notes
            # are the same case (INBOX 68: "Boards & maps preview looks so
            # bad"). An image object still has no label: what it says is a
            # picture, and a thumbnail of a thumbnail is a different feature.
            label = str(data.get("content") or "")[:PREVIEW_LABEL_CHARS]
        rows.append(
            (
                float(obj.x),
                float(obj.y),
                obj.kind or "object",
                label,
                None,
                *_preview_size(obj.kind or "object", obj.width, obj.height),
                None,
            )
        )
        owners.append(obj.id)
        if obj.parent_id is not None:
            parent_of[obj.id] = obj.parent_id
        if obj.kind == MAP_TOPIC_KIND or obj.kind in MAP_REFERENCE_KINDS:
            tree_parents[obj.id] = obj.parent_id
            colour = data.get("color")
            own_colors[obj.id] = colour if isinstance(colour, str) and colour else None
    return rows, owners, parent_of, tree_parents, own_colors


def _preview_aspect(rows: list[tuple], kept: list[int]) -> float:
    """The sampled corner span, which is the box the items were normalised
    into and therefore the box the client draws. A single item, or a straight
    line of them, has no extent on an axis and keeps the square: the
    alternative is a divide by zero or a thumbnail whose shape is an artefact
    of a rounding error."""
    if not kept:
        return 1.0
    xs = [rows[i][0] for i in kept]
    ys = [rows[i][1] for i in kept]
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    if span_x > 0 and span_y > 0:
        low, high = PREVIEW_ASPECT_RANGE
        return round(min(max(span_x / span_y, low), high), 3)
    return 1.0


def _preview_edges(parent_of: dict, owners: list, kept: list[int], items: list[dict]) -> list[dict]:
    """A line from each kept child to its kept parent. An edge takes the
    *child's* colour, which is what the canvas does: a branch is one colour
    from where it leaves the trunk all the way out."""
    edges: list[dict] = []
    if not parent_of:
        return edges
    at = {owners[i]: n for n, i in enumerate(kept) if owners[i] is not None}
    for child_id, parent_id in parent_of.items():
        if child_id in at and parent_id in at:
            child, parent = items[at[child_id]], items[at[parent_id]]
            edge = {"x1": parent["x"], "y1": parent["y"], "x2": child["x"], "y2": child["y"]}
            if child.get("color"):
                edge["color"] = child["color"]
            edges.append(edge)
    return edges


def _board_preview(
    db: Session, board_id: int | None, palette: list[str] | None = None, rainbow: bool = False
) -> tuple[list[dict], list[dict], float]:
    """Everything placed on one board, as a thumbnail: `(items, edges, aspect)`.

    Cards, sketches *and* objects. Cards alone was the first version and it
    is why a sketch-only board previewed as an empty rectangle: the count
    line said "2 sketches" beside a picture of nothing.

    **Edges are computed from the sampled items, not from the board.** The
    sampler drops items on a large board (`PREVIEW_POINTS`), and an edge
    whose other end was dropped would be a line to nowhere, so an edge is
    emitted only when both of its ends survived sampling, and it reuses the
    normalised coordinates the items already got rather than normalising a
    second time against different bounds.

    **`aspect` is the shape the normalisation threw away.** Positions come
    back in 0..1 on both axes, so the client cannot tell a tall map from a
    wide board and drew both stretched into the card's box. It is measured
    over exactly the sampled corner span the items were normalised against,
    not over the board's true extent including each item's own width and
    height: the picture the client letterboxes *is* that span, so a ratio
    measured any other way would be a number that does not match the drawing.
    """
    def on(model):
        return (
            model.board_id.is_(None) if board_id is None else model.board_id == board_id
        )

    #: The eighth slot is a drawn stroke's own tool (`line`, `rect`,
    #: `ellipse`, `pen`, ...), `None` for everything that is not a sketch: a
    #: thumbnail that draws one generic wave for every shape on the board is
    #: the half of INBOX 164 the positions do not explain.
    rows = _card_preview_rows(db, on) + _sketch_preview_rows(db, on)
    #: Which object each row came from, positionally, `None` for a card or a
    #: sketch, which have no tree. Only map nodes ever claim a parent, so an
    #: ordinary board leaves `parent_of` empty and pays for nothing.
    owners: list[int | None] = [None] * len(rows)
    object_rows, object_owners, parent_of, tree_parents, own_colors = _object_preview_rows(db, on)
    rows += object_rows
    owners += object_owners

    # **The branch colours, computed here and not in the client.** Every node
    # drew in one grey before this, so a map's thumbnail showed its structure
    # and nothing about which branch was which, while the same map on the
    # canvas is colour-coded by branch. The rule is Coggle's and the canvas
    # already implements it; see `_map_branch_colors`.
    if tree_parents:
        branch_colors = _map_branch_colors(tree_parents, own_colors, palette, rainbow)
        rows = [
            (
                x,
                y,
                kind,
                label,
                branch_colors.get(owner) if owner is not None else colour,
                w,
                h,
                shape,
            )
            for (x, y, kind, label, colour, w, h, shape), owner in zip(
                rows, owners, strict=True
            )
        ]

    # Sample here rather than inside `_preview_items` so the edges can be
    # drawn against the *same* survivors: passing an already-sampled list
    # back through it is a no-op (its own stride is 1 for anything at or
    # under PREVIEW_POINTS), so nothing about the items changes.
    stride = max(1, len(rows) // PREVIEW_POINTS)
    kept = list(range(len(rows)))[::stride][:PREVIEW_POINTS]
    items = _preview_items([rows[i] for i in kept])
    return items, _preview_edges(parent_of, owners, kept, items), _preview_aspect(rows, kept)


#: How many boards' thumbnails are remembered at once. The Library lists every
#: board in the notebook, so this only has to cover one screenful of cards
#: plus the dashboard's widget; a notebook with more boards than this simply
#: recomputes the ones that fell off the end.
PREVIEW_CACHE_LIMIT = 128

#: `key -> (items, edges, aspect)`, where the key carries a fingerprint of
#: everything the picture is drawn from (see `_preview_fingerprint`), so a
#: stale entry cannot be served: a changed board has a different key, and the
#: old entry ages out rather than being invalidated by hand.
_PREVIEW_CACHE: "OrderedDict[tuple, tuple[list[dict], list[dict], float]]" = OrderedDict()

#: Hits and misses since the process started. Read by
#: `tests/test_board_preview.py`, which is the only way to assert a cache
#: works: the response is identical either way, which is the point of it.
PREVIEW_CACHE_STATS = {"hits": 0, "misses": 0}


_preview_stamps_bulk = whiteboard_repo.preview_stamps


def _preview_fingerprint(db: Session, board_id: int | None, stamps: list | None = None) -> tuple:
    """Everything a board's thumbnail depends on, as a cheap tuple.

    Three counts and three high-water marks, one per table, plus the same
    pair for the *notes* the board's cards stand for: a card's label is the
    note's title, so renaming a note has to change this key even though
    nothing on the board was touched. Six aggregates over indexed columns
    against a full scan of every row on the board plus one `Entry` fetch per
    card, which is what the miss path costs.

    The database's own identity is in the key as well. The cache is module
    state and the test suite builds a fresh database per test, so two
    databases whose board 1 is empty in the same way would otherwise share an
    entry: harmless today (both previews are empty) and exactly the sort of
    cross-test leak that is diagnosed at three in the morning.
    """
    def on(model):
        return model.board_id.is_(None) if board_id is None else model.board_id == board_id

    if stamps is None:
        stamps = []
        for model in (WhiteboardNode, WhiteboardSketch, WhiteboardObject):
            row = db.execute(
                select(func.count(), func.max(model.updated_at)).where(on(model))
            ).one()
            stamps.append((row[0], str(row[1])))
        cards = db.execute(
            select(func.count(), func.max(Entry.updated_at))
            .select_from(WhiteboardNode)
            .join(Entry, Entry.id == WhiteboardNode.entry_id)
            .where(on(WhiteboardNode))
        ).one()
        stamps.append((cards[0], str(cards[1])))
    bind = db.get_bind()
    return (
        str(getattr(bind, "url", bind)),
        db.info.get("workspace_id"),
        board_id,
        tuple(stamps),
    )


def _preview_fields(db: Session, board_id: int | None, stamps: list | None = None) -> dict:
    """A board's three preview fields, ready to splat into `BoardOut`, from
    the cache when the board has not moved since it was last drawn.

    **Why this is cached at all**: the Library rebuilds every board's
    thumbnail on every visit, and a thumbnail is a full scan of the board.
    Twenty boards of a few hundred items each is twenty of those, per visit,
    for a picture that changes only when the board does.
    """
    #: The map's palette is in the key (decision 8): picking one changes the
    #: board's settings and no row on it, so a key of the rows alone would
    #: serve the old colours until something else on the board moved.
    theme = _board_theme(db.get(Entry, board_id)) if board_id else {}
    palette_name = theme.get("palette") or "classic"
    rainbow = bool(theme.get("rainbow"))
    key = (*_preview_fingerprint(db, board_id, stamps), palette_name, rainbow)
    cached = _PREVIEW_CACHE.get(key)
    if cached is not None:
        PREVIEW_CACHE_STATS["hits"] += 1
        # Newest last: this is a plain LRU, and a board being looked at now is
        # the one least worth dropping.
        _PREVIEW_CACHE.move_to_end(key)
        items, edges, aspect = cached
    else:
        PREVIEW_CACHE_STATS["misses"] += 1
        items, edges, aspect = _board_preview(
            db, board_id, MAP_BRANCH_PALETTES.get(palette_name, MAP_BRANCH_PALETTE), rainbow
        )
        _PREVIEW_CACHE[key] = (items, edges, aspect)
        while len(_PREVIEW_CACHE) > PREVIEW_CACHE_LIMIT:
            _PREVIEW_CACHE.popitem(last=False)
    # Copied on the way out: the cached lists are shared with every later
    # caller, and a response model that a caller mutated in place would poison
    # every board list after it.
    #: The default board has no note behind it, so no id: its file is stored
    #: under 0 (`DEFAULT_BOARD_THUMB_ID`), the id the client sends for it.
    stored = board_thumbs.stored_fp(deps.get_config().data_dir, board_id or DEFAULT_BOARD_THUMB_ID)
    return {
        "preview_items": [dict(item) for item in items],
        "preview_edges": [dict(edge) for edge in edges],
        "preview_aspect": aspect,
        # Labels are read only for a board that has a stored picture to compare.
        "thumb_v": stored if stored is not None and stored == _thumb_fp(db, key) else None,
    }


def _thumb_fp(db: Session, key: tuple) -> str:
    """The fingerprint a raster thumbnail is stored against: the cache key
    without the database identity, so it survives a restart.

    The cards' note stamp (`max(Entry.updated_at)`) is swapped for the labels
    the picture actually shows. That stamp moves on any write to a note (a
    body edit, a pin, the janitor re-filing it, a tag), none of which changes
    a card's title, so every such write retired the stored picture and the
    card fell back to the drawn preview until the board was opened again (the
    owner, INBOX 1418: "the default board thumbnail keeps getting deleted";
    a board of drawings only has no such stamp, which is why only boards with
    note cards lost theirs). The preview cache key keeps the stamp: its miss
    path is what reads the notes.
    """
    scope = key[2]
    stamps = key[3][:3]
    node_scope = WhiteboardNode.board_id.is_(None) if scope is None else WhiteboardNode.board_id == scope
    labels = [
        _card_label(entry)
        for entry in db.scalars(
            select(Entry)
            .join(WhiteboardNode, WhiteboardNode.entry_id == Entry.id)
            .where(node_scope)
            .order_by(WhiteboardNode.id)
        )
    ]
    return board_thumbs.fingerprint_hash((key[1], scope, stamps, key[4], tuple(labels)))


#: The default board is the one board with no note, so no id to name it by in
#: a URL or a file: its thumbnail travels as board 0 (the owner, 2026-10-26:
#: "the default board doesnt get a thumbnail": the client skipped a falsy id).
DEFAULT_BOARD_THUMB_ID = 0


def _thumb_board(db: Session, board_id: int) -> None:
    if board_id != DEFAULT_BOARD_THUMB_ID:
        _board_entry(db, board_id)


def _thumb_writable(db: Session, board_id: int) -> None:
    """A thumbnail PUT is a write: a binned board answers the bin guard's 409
    (audit 1031 row 2a), where a read of it keeps its 404."""
    if board_id != DEFAULT_BOARD_THUMB_ID:
        BOARDS.writable(db, board_id)


def _current_thumb_fp(db: Session, board_id: int) -> str:
    entry = db.get(Entry, board_id) if board_id > 0 else None
    theme = _board_theme(entry)
    palette_name = theme.get("palette") or "classic"
    scope = board_id if board_id != DEFAULT_BOARD_THUMB_ID else None
    return _thumb_fp(db, (*_preview_fingerprint(db, scope), palette_name, bool(theme.get("rainbow"))))


@router.get("/boards/{board_id}/thumbnail/state")
def thumbnail_state(board_id: int, db: Session = Depends(get_session)) -> dict:
    """What the client needs to decide whether to draw a thumbnail: the
    board's fingerprint now and the one the stored thumbnail was drawn at."""
    _thumb_board(db, board_id)
    return {
        "fp": _current_thumb_fp(db, board_id),
        "stored": board_thumbs.stored_fp(deps.get_config().data_dir, board_id),
    }


@router.put("/boards/{board_id}/thumbnail")
async def put_thumbnail(
    board_id: int,
    request: Request,
    fp: str = Query(...),
    db: Session = Depends(get_session),
) -> dict:
    #: The lookup and the write go to the thread pool, and the body grows in a
    #: bytearray (audit 1028 K18): in the event loop they stalled every other
    #: request while a board list's thumbnails came in.
    await run_in_threadpool(_thumb_writable, db, board_id)
    if not board_thumbs.valid_fp(fp):
        raise HTTPException(status_code=422, detail="That thumbnail version is not valid.")
    declared = int(request.headers.get("content-length") or 0)
    if declared > board_thumbs.MAX_BYTES:
        raise HTTPException(status_code=413, detail="That thumbnail is too large.")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > board_thumbs.MAX_BYTES:
            raise HTTPException(status_code=413, detail="That thumbnail is too large.")
    body = bytes(data)
    mime = board_thumbs.sniff(body)
    if mime is None:
        raise HTTPException(status_code=415, detail="A thumbnail must be a WebP or JPEG image.")
    await run_in_threadpool(board_thumbs.save, deps.get_config().data_dir, board_id, fp, mime, body)
    return {"fp": fp, "bytes": len(body)}


#: Served under `/media` because an `<img src>` cannot send the auth header and
#: the media cookie is scoped to `/media` and `/files`; app.py includes this
#: router behind `require_unlock_media`, the same gate `/media/{filename}` has.
media_router = APIRouter(tags=["whiteboard"])


@media_router.get("/media/board-thumb/{board_id}")
def get_thumbnail(
    board_id: int, request: Request, v: str | None = None, db: Session = Depends(get_session)
):
    """The stored thumbnail. The `?v=` URL is immutable (a new fingerprint is a
    new URL), so it is cached for a year; without it the ETag still answers 304."""
    _thumb_board(db, board_id)
    found = board_thumbs.find(deps.get_config().data_dir, board_id)
    if found is None:
        raise HTTPException(status_code=404, detail="That board has no thumbnail yet.")
    path, fp, mime = found
    etag = f'"{fp}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable"
        if v == fp
        else "private, max-age=0, must-revalidate",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=path.read_bytes(), media_type=mime, headers=headers)
