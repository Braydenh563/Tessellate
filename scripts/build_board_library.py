"""Build the board library's built-in sets (WHITEBOARD_PLAN decision 25).

    python scripts/build_board_library.py

Writes `frontend/board-library/*.json`: the shape sets (General, Flowchart,
Arrows, Frames), drawn fresh here as paths in this file (draw.io is Apache-2.0:
its features are taken, none of its stencils), and `icons.json`, every glyph of
the vendored Phosphor font (MIT, `frontend/vendor/phosphor/LICENSE`) turned
into an SVG path. The font itself cannot be the icon: a `<text>` glyph does not
survive an SVG or PNG export, and a path does. Read with a small TrueType
`glyf` reader below, so no font library is needed.

The output is committed; this runs again only when a set changes. Each entry
is a library item of kind `element` (or `template`) whose payload is the board
library's own format (`routes_board_library.py`): items positioned from the
box's top left corner, the links between them by key.

Colour placeholders: a sketch whose `color` is `"ink"` takes the pen colour
the person is holding when it is placed, and a `fill` of `"ink"` the same at
the item's `fillOpacity`, so a shape matches whatever they were drawing with.
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "board-library"
PHOSPHOR = ROOT / "frontend" / "vendor" / "phosphor"


def _n(value: float) -> str:
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def path(*parts) -> str:
    """Join commands and numbers into a path string."""
    out = []
    for part in parts:
        out.append(part if isinstance(part, str) else _n(part))
    return " ".join(out)


def poly(points, close=True) -> str:
    d = ["M", points[0][0], points[0][1]]
    for x, y in points[1:]:
        d += ["L", x, y]
    if close:
        d.append("Z")
    return path(*d)


def ellipse_d(cx, cy, rx, ry) -> str:
    return path("M", cx - rx, cy, "A", rx, ry, 0, 1, 1, cx + rx, cy, "A", rx, ry, 0, 1, 1, cx - rx, cy, "Z")


def rounded_rect(w, h, r) -> str:
    return path(
        "M", r, 0, "L", w - r, 0, "A", r, r, 0, 0, 1, w, r, "L", w, h - r, "A", r, r, 0, 0, 1, w - r, h,
        "L", r, h, "A", r, r, 0, 0, 1, 0, h - r, "L", 0, r, "A", r, r, 0, 0, 1, r, 0, "Z",
    )


def shape_item(d, w, h, *, fill_opacity=0.12, label_area=None, filled=True, key="s"):
    data = {"d": d, "shape": "custom", "color": "ink", "width": 2}
    if filled:
        data["fill"] = "ink"
        data["fillOpacity"] = fill_opacity
    if label_area:
        data["label_area"] = label_area
    return {"key": key, "kind": "sketch", "data": data, "z": 5}


def element(key, name, tags, items, w, h, links=None, kind="element"):
    return {
        "key": key,
        "kind": kind,
        "name": name,
        "tags": tags,
        "payload": {"box": {"w": w, "h": h}, "items": items, "links": links or []},
    }


def shape(key, name, tags, d, w, h, **kw):
    return element(key, name, tags, [shape_item(d, w, h, **kw)], w, h)


# --- General -------------------------------------------------------------------

def general():
    w, h = 160, 100
    star = []
    for i in range(10):
        r = 60 if i % 2 == 0 else 26
        a = -math.pi / 2 + i * math.pi / 5
        star.append((60 + r * math.cos(a), 60 + r * math.sin(a)))
    cloud = path(
        "M", 40, 90, "C", 12, 90, 8, 58, 32, 52, "C", 30, 26, 66, 18, 80, 38,
        "C", 92, 14, 136, 20, 134, 50, "C", 160, 54, 158, 92, 128, 90, "Z",
    )
    callout = path("M", 0, 0, "L", w, 0, "L", w, 76, "L", 64, 76, "L", 36, 100, "L", 40, 76, "L", 0, 76, "Z")
    document = path("M", 0, 0, "L", w, 0, "L", w, 84, "C", 120, 64, 40, 108, 0, 88, "Z")
    cylinder = path(
        "M", 0, 16, "A", 80, 16, 0, 0, 1, w, 16, "L", w, 104, "A", 80, 16, 0, 0, 1, 0, 104, "Z",
        "M", 0, 16, "A", 80, 16, 0, 0, 0, w, 16,
    )
    sets = [
        shape("rect", "Rectangle", ["box", "square", "process"], poly([(0, 0), (w, 0), (w, h), (0, h)]), w, h),
        shape("rounded", "Rounded rectangle", ["box", "card"], rounded_rect(w, h, 16), w, h),
        shape("ellipse", "Ellipse", ["circle", "oval"], ellipse_d(80, 50, 80, 50), w, h,
              label_area={"x": 0.15, "y": 0.15, "w": 0.7, "h": 0.7}),
        shape("triangle", "Triangle", ["delta"], poly([(60, 0), (120, 104), (0, 104)]), 120, 104,
              label_area={"x": 0.25, "y": 0.5, "w": 0.5, "h": 0.45}),
        shape("diamond", "Diamond", ["rhombus", "decision"], poly([(80, 0), (160, 50), (80, 100), (0, 50)]), w, h,
              label_area={"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}),
        shape("parallelogram", "Parallelogram", ["slanted", "input", "output"], poly([(28, 0), (w, 0), (w - 28, h), (0, h)]), w, h,
              label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
        shape("hexagon", "Hexagon", ["six"], poly([(30, 0), (130, 0), (160, 50), (130, 100), (30, 100), (0, 50)]), w, h,
              label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
        shape("cylinder", "Cylinder", ["database", "storage", "drum"], cylinder, w, 120,
              label_area={"x": 0, "y": 0.25, "w": 1, "h": 0.65}),
        shape("cloud", "Cloud", ["internet", "weather"], cloud, w, h,
              label_area={"x": 0.2, "y": 0.35, "w": 0.6, "h": 0.5}),
        shape("callout", "Callout", ["speech", "bubble", "comment"], callout, w, h,
              label_area={"x": 0, "y": 0, "w": 1, "h": 0.76}),
        shape("document", "Document", ["page", "paper"], document, w, h,
              label_area={"x": 0, "y": 0, "w": 1, "h": 0.8}),
        shape("star", "Star", ["favourite", "rating"], poly(star), 120, 120,
              label_area={"x": 0.3, "y": 0.35, "w": 0.4, "h": 0.35}),
        element("text", "Text", ["words", "label", "type"], [
            {"key": "t", "kind": "object", "type": "text", "data": {"content": "Text"}, "x": 0, "y": 0, "w": 200, "h": 60, "z": 1},
        ], 200, 60),
    ]
    stickies = [
        ("yellow", "#fff4a3", "#e8d56a"), ("pink", "#ffd1dc", "#e8a3b4"), ("blue", "#cfe8ff", "#94bfe8"),
        ("green", "#d6f5c9", "#9dd18a"), ("orange", "#ffe0b8", "#e8b878"), ("purple", "#e6d9ff", "#b9a3e8"),
    ]
    for name, bg, edge in stickies:
        sets.append(element(f"sticky-{name}", f"Sticky note, {name}", ["sticky", "note", "post-it", name], [
            {"key": "t", "kind": "object", "type": "text",
             "data": {"content": "", "bg": bg, "border_color": edge, "color": "#2a2a1f", "font_size": 16},
             "x": 0, "y": 0, "w": 180, "h": 140, "z": 1},
        ], 180, 140))
    return {"key": "general", "name": "General", "items": sets}


# --- Flowchart -----------------------------------------------------------------

def flowchart():
    w, h = 160, 80
    terminator = path("M", 40, 0, "L", 120, 0, "A", 40, 40, 0, 0, 1, 120, 80, "L", 40, 80, "A", 40, 40, 0, 0, 1, 40, 0, "Z")
    predefined = path(
        "M", 0, 0, "L", w, 0, "L", w, h, "L", 0, h, "Z",
        "M", 16, 0, "L", 16, h, "M", w - 16, 0, "L", w - 16, h,
    )
    document = path("M", 0, 0, "L", w, 0, "L", w, 68, "C", 120, 52, 40, 88, 0, 72, "Z")
    multi = path(
        "M", 12, 0, "L", w, 0, "L", w, 60, "L", w - 6, 60,
        "M", 6, 6, "L", w - 6, 6, "L", w - 6, 66, "L", w - 12, 66,
        "M", 0, 12, "L", w - 12, 12, "L", w - 12, 74, "C", 110, 60, 36, 92, 0, 78, "Z",
    )
    database = path(
        "M", 0, 12, "A", 80, 12, 0, 0, 1, w, 12, "L", w, 88, "A", 80, 12, 0, 0, 1, 0, 88, "Z",
        "M", 0, 12, "A", 80, 12, 0, 0, 0, w, 12,
    )
    delay = path("M", 0, 0, "L", 110, 0, "A", 50, 40, 0, 0, 1, 110, 80, "L", 0, 80, "Z")
    offpage = poly([(0, 0), (100, 0), (100, 64), (50, 96), (0, 64)])
    items = [
        shape("process", "Process", ["step", "action", "box"], poly([(0, 0), (w, 0), (w, h), (0, h)]), w, h),
        shape("decision", "Decision", ["if", "branch", "question", "diamond"], poly([(80, 0), (160, 50), (80, 100), (0, 50)]), 160, 100,
              label_area={"x": 0.22, "y": 0.25, "w": 0.56, "h": 0.5}),
        shape("terminator", "Terminator", ["start", "end", "stop", "begin"], terminator, w, h,
              label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
        shape("data", "Data (input or output)", ["input", "output", "io", "parallelogram"], poly([(24, 0), (w, 0), (w - 24, h), (0, h)]), w, h,
              label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
        shape("predefined", "Predefined process", ["subroutine", "function", "call"], predefined, w, h,
              label_area={"x": 0.12, "y": 0, "w": 0.76, "h": 1}),
        shape("manual-input", "Manual input", ["keyboard", "enter"], poly([(0, 24), (w, 0), (w, h), (0, h)]), w, h,
              label_area={"x": 0, "y": 0.3, "w": 1, "h": 0.7}),
        shape("document", "Document", ["report", "page"], document, w, h,
              label_area={"x": 0, "y": 0, "w": 1, "h": 0.8}),
        shape("multi-document", "Multiple documents", ["reports", "pages"], multi, w, h,
              label_area={"x": 0, "y": 0.15, "w": 0.92, "h": 0.7}),
        shape("database", "Database", ["storage", "cylinder", "data store"], database, w, 100,
              label_area={"x": 0, "y": 0.25, "w": 1, "h": 0.65}),
        shape("delay", "Delay", ["wait", "pause"], delay, w, h,
              label_area={"x": 0, "y": 0, "w": 0.85, "h": 1}),
        shape("off-page", "Off-page reference", ["continue", "page"], offpage, 100, 96,
              label_area={"x": 0, "y": 0, "w": 1, "h": 0.66}),
        shape("connector", "On-page connector", ["circle", "join", "jump"], ellipse_d(30, 30, 30, 30), 60, 60,
              label_area={"x": 0.15, "y": 0.15, "w": 0.7, "h": 0.7}),
        shape("preparation", "Preparation", ["setup", "hexagon", "initialise"], poly([(28, 0), (132, 0), (160, 40), (132, 80), (28, 80), (0, 40)]), w, h,
              label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
    ]
    return {"key": "flowchart", "name": "Flowchart", "items": items}


# --- Arrows --------------------------------------------------------------------

def arrows():
    right = [(0, 25), (100, 25), (100, 0), (150, 50), (100, 100), (100, 75), (0, 75)]
    flip_x = lambda pts: [(150 - x, y) for x, y in pts]  # noqa: E731
    rot = lambda pts: [(y, x) for x, y in pts]  # noqa: E731 - right turned to down
    up = [(x, 150 - y) for x, y in rot(right)]
    both = [(0, 50), (40, 0), (40, 25), (110, 25), (110, 0), (150, 50), (110, 100), (110, 75), (40, 75), (40, 100)]
    chevron = [(0, 0), (100, 0), (150, 50), (100, 100), (0, 100), (50, 50)]
    notched = [(0, 25), (100, 25), (100, 0), (150, 50), (100, 100), (100, 75), (0, 75), (25, 50)]
    uturn = path(
        "M", 0, 140, "L", 0, 60, "A", 60, 60, 0, 0, 1, 120, 60, "L", 120, 90, "L", 150, 90, "L", 100, 140,
        "L", 50, 90, "L", 80, 90, "L", 80, 60, "A", 20, 20, 0, 0, 0, 40, 60, "L", 40, 140, "Z",
    )
    items = [
        shape("block-right", "Block arrow, right", ["arrow", "next", "forward"], poly(right), 150, 100, label_area={"x": 0, "y": 0.25, "w": 0.7, "h": 0.5}),
        shape("block-left", "Block arrow, left", ["arrow", "back", "previous"], poly(flip_x(right)), 150, 100, label_area={"x": 0.3, "y": 0.25, "w": 0.7, "h": 0.5}),
        shape("block-down", "Block arrow, down", ["arrow", "below"], poly(rot(right)), 100, 150, label_area={"x": 0.25, "y": 0, "w": 0.5, "h": 0.7}),
        shape("block-up", "Block arrow, up", ["arrow", "above"], poly(up), 100, 150, label_area={"x": 0.25, "y": 0.3, "w": 0.5, "h": 0.7}),
        shape("block-both", "Block arrow, both ways", ["arrow", "two-way", "exchange"], poly(both), 150, 100, label_area={"x": 0.27, "y": 0.25, "w": 0.46, "h": 0.5}),
        shape("chevron", "Chevron", ["step", "stage", "arrow"], poly(chevron), 150, 100, label_area={"x": 0.3, "y": 0.1, "w": 0.45, "h": 0.8}),
        shape("notched", "Notched arrow", ["arrow", "flow"], poly(notched), 150, 100, label_area={"x": 0.15, "y": 0.25, "w": 0.55, "h": 0.5}),
        shape("u-turn", "U-turn arrow", ["arrow", "return", "back"], uturn, 150, 140),
    ]
    return {"key": "arrows", "name": "Arrows", "items": items}


# --- Frames, which are templates too --------------------------------------------

def _frames(titles, cols, fw, fh, gap=40):
    items = []
    for i, title in enumerate(titles):
        x = (i % cols) * (fw + gap)
        y = (i // cols) * (fh + gap)
        items.append({"key": f"f{i}", "kind": "object", "type": "frame", "data": {"content": title},
                      "x": x, "y": y, "w": fw, "h": fh, "z": -1})
    rows = math.ceil(len(titles) / cols)
    return items, cols * fw + (cols - 1) * gap, rows * fh + (rows - 1) * gap


def frames():
    kanban, kw, kh = _frames(["To do", "Doing", "Done"], 3, 320, 520)
    retro, rw, rh = _frames(["Went well", "To improve", "Ideas", "Actions"], 4, 300, 440)
    swot, sw, sh = _frames(["Strengths", "Weaknesses", "Opportunities", "Threats"], 2, 420, 300)
    lane = [
        {"key": "f0", "kind": "object", "type": "frame", "data": {"content": "Timeline"}, "x": 0, "y": 0, "w": 960, "h": 240, "z": -1},
        {"key": "l", "kind": "sketch", "data": {"d": path("M", 40, 120, "L", 920, 120), "shape": "arrow", "color": "ink", "width": 3, "endCap": "arrow"}, "z": 5},
    ]
    for i in range(4):
        cx = 120 + i * 240
        lane.append({"key": f"m{i}", "kind": "sketch",
                     "data": {"d": ellipse_d(cx, 120, 10, 10), "shape": "custom", "color": "ink", "width": 2, "fill": "ink", "fillOpacity": 1}, "z": 6})
        lane.append({"key": f"t{i}", "kind": "object", "type": "text", "data": {"content": f"Step {i + 1}"},
                     "x": cx - 60, "y": 140, "w": 120, "h": 44, "z": 1})
    items = [
        element("frame", "Frame", ["region", "section", "slide", "page"], [
            {"key": "f0", "kind": "object", "type": "frame", "data": {"content": "Frame"}, "x": 0, "y": 0, "w": 480, "h": 320, "z": -1},
        ], 480, 320),
        element("kanban", "Kanban, three columns", ["board", "tasks", "to do", "doing", "done"], kanban, kw, kh),
        element("retro", "Retrospective, four columns", ["retro", "review", "went well"], retro, rw, rh),
        element("swot", "SWOT, two by two", ["strengths", "weaknesses", "opportunities", "threats", "analysis"], swot, sw, sh),
        element("timeline", "Timeline lane", ["timeline", "roadmap", "steps", "milestones"], lane, 960, 240),
        element("swimlanes-rows", "Swimlanes, three rows", SWIM_TAGS, _swimlanes(True), 1000, 520),
        element("swimlanes-columns", "Swimlanes, three columns", SWIM_TAGS, _swimlanes(False), 1000, 640),
    ]
    return {"key": "frames", "name": "Frames", "items": items}


SWIM_TAGS = ["swimlane", "pool", "lane", "process", "bpmn", "cross-functional"]


def _swimlanes(rows):
    """A pool (draw.io's swimlane container) as a frame round three lane
    frames, in rows or in columns (canvasdepth, INBOX 797)."""
    items = [{"key": "pool", "kind": "object", "type": "frame", "data": {"content": "Process"},
              "x": 0, "y": 0, "w": 1000, "h": 520 if rows else 640, "z": -2}]
    for i in range(3):
        x, y, w, h = (20, 56 + i * 160, 960, 130) if rows else (20 + i * 324, 56, 312, 564)
        items.append({"key": f"lane{i}", "kind": "object", "type": "frame", "data": {"content": f"Lane {i + 1}"},
                      "x": x, "y": y, "w": w, "h": h, "z": -1})
    return items


# --- Templates: a whole starting layout, dragged in from the Library -----------
#
# INBOX 596 (the owner: "can you add preset whiteboard and mind map templates
# that are draggable from the library??"). A board template is an element like
# any other (a click places it in the middle of the view, a drag where it is
# dropped), only larger and with words already in it; a map template is a
# branch, placed under the topic it is dropped on, or the selected topic, or
# the root. `template` says which kind of board the Library shows it on.

def _sticky(key, words, x, y, bg="#fff4a3", edge="#e8d56a"):
    return {"key": key, "kind": "object", "type": "text",
            "data": {"content": words, "bg": bg, "border_color": edge, "color": "#2a2a1f", "font_size": 16},
            "x": x, "y": y, "w": 200, "h": 120, "z": 1}


def _text(key, words, x, y, w=280, h=48):
    return {"key": key, "kind": "object", "type": "text", "data": {"content": words}, "x": x, "y": y, "w": w, "h": h, "z": 1}


def _box(key, d, x, y, label, **kw):
    item = shape_item(d, 0, 0, key=key, **kw)
    item["data"]["label"] = label
    item["data"]["d"] = _moved(item["data"]["d"], x, y)
    return item


def _moved(d, dx, dy):
    """A path from the build helpers, moved by (dx, dy): every number pair in
    an M, L or A command's end point. Only the commands those helpers write."""
    out, tokens, i = [], d.split(), 0
    while i < len(tokens):
        cmd = tokens[i]
        out.append(cmd)
        i += 1
        if cmd in ("M", "L"):
            out += [_n(float(tokens[i]) + dx), _n(float(tokens[i + 1]) + dy)]
            i += 2
        elif cmd == "A":
            out += tokens[i:i + 5] + [_n(float(tokens[i + 5]) + dx), _n(float(tokens[i + 6]) + dy)]
            i += 7
    return " ".join(out)


def templates():
    kanban, kw, kh = _frames(["To do", "Doing", "Done"], 3, 320, 520)
    kanban += [_sticky("s0", "First task", 60, 80), _sticky("s1", "Second task", 60, 230),
               _sticky("s2", "In progress", 420, 80, "#cfe8ff", "#94bfe8"), _sticky("s3", "Finished", 780, 80, "#d6f5c9", "#9dd18a")]
    retro, rw, rh = _frames(["Went well", "To improve", "Ideas", "Actions"], 4, 300, 440)
    for i, (bg, edge) in enumerate([("#d6f5c9", "#9dd18a"), ("#ffd1dc", "#e8a3b4"), ("#fff4a3", "#e8d56a"), ("#cfe8ff", "#94bfe8")]):
        retro.append(_sticky(f"s{i}", "Add a note", 50 + i * 340, 80, bg, edge))
    term = path("M", 40, 0, "L", 120, 0, "A", 40, 40, 0, 0, 1, 120, 80, "L", 40, 80, "A", 40, 40, 0, 0, 1, 40, 0, "Z")
    step = poly([(0, 0), (160, 0), (160, 80), (0, 80)])
    diamond = poly([(80, 0), (160, 50), (80, 100), (0, 50)])
    flow = [
        _box("start", term, 0, 0, "Start", label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
        _box("step", step, 0, 160, "Do the first step"),
        _box("ask", diamond, 0, 320, "Did it work?", label_area={"x": 0.22, "y": 0.25, "w": 0.56, "h": 0.5}),
        _box("fix", step, 280, 330, "Try again"),
        _box("end", term, 0, 500, "End", label_area={"x": 0.15, "y": 0, "w": 0.7, "h": 1}),
    ]
    arrow = {"type": "link-straight", "color": "ink", "width": 2, "endCap": "arrow"}
    flow_links = [{"from": a, "to": b, "data": dict(arrow)} for a, b in
                  [("start", "step"), ("step", "ask"), ("ask", "fix"), ("ask", "end"), ("fix", "step")]]
    meeting = [
        {"key": "f0", "kind": "object", "type": "frame", "data": {"content": "Meeting"}, "x": 0, "y": 0, "w": 960, "h": 460, "z": -1},
        _text("t0", "## Agenda", 40, 40), _text("t1", "## Notes", 340, 40), _text("t2", "## Actions", 640, 40),
        _sticky("s0", "First item", 40, 110), _sticky("s1", "What was said", 340, 110, "#cfe8ff", "#94bfe8"),
        _sticky("s2", "Who does what, by when", 640, 110, "#d6f5c9", "#9dd18a"),
    ]
    week, ww, wh = _frames(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], 5, 220, 380)
    items = [
        element("kanban", "Kanban with cards", ["template", "tasks", "to do", "doing", "done"], kanban, kw, kh),
        element("retro", "Retrospective", ["template", "retro", "review", "went well"], retro, rw, rh),
        element("flow", "Flowchart, a loop", ["template", "flowchart", "process", "decision"], flow, 440, 580, links=flow_links),
        element("meeting", "Meeting notes", ["template", "meeting", "agenda", "actions"], meeting, 960, 460),
        element("week", "Week plan", ["template", "week", "plan", "schedule"], week, ww, wh),
    ]
    for item in items:
        item["template"] = "board"
    return {"key": "templates", "name": "Templates", "items": items}


def _branch(key, name, tags, nodes):
    def walk(node):
        text, children = node if isinstance(node, tuple) else (node, [])
        return {"text": text, "children": [walk(c) for c in children]}

    return {"key": key, "kind": "branch", "name": name, "tags": ["template", *tags], "template": "map",
            "payload": {"nodes": [walk(n) for n in nodes]}}


def map_templates():
    """The four the empty map offers (`WB_MAP_TEMPLATES`, whiteboard-map.js),
    with the same words, and three more."""
    items = [
        _branch("brainstorm", "Brainstorm", ["ideas", "questions"], [
            ("Ideas", ["First idea"]), ("Questions", ["What do I not know yet?"]), "Themes", "Next steps"]),
        _branch("decision", "Decision", ["options", "choose"], [
            ("Options", ["Option A", "Option B"]), ("What matters", ["Cost", "Time"]), "Risks", "What would change my mind"]),
        _branch("project", "Project", ["plan", "milestones", "tasks"], [
            "Goal", ("Milestones", ["First milestone"]), "Tasks", "People", "Risks"]),
        _branch("causes", "Cause and effect", ["ishikawa", "fishbone", "why"], [
            "People", "Process", "Tools", "Surroundings", "What actually happened"]),
        _branch("pros-cons", "Pros and cons", ["compare", "weigh"], [
            ("Pros", ["A reason for"]), ("Cons", ["A reason against"]), "What I decided"]),
        _branch("book", "Book notes", ["reading", "summary"], [
            "The main idea", ("Key points", ["First point"]), "Quotes", "What I will do with it"]),
        _branch("meeting", "Meeting", ["agenda", "minutes", "actions"], [
            "Agenda", "Decisions", ("Actions", ["Who, what, by when"]), "Open questions"]),
    ]
    return {"key": "maps", "name": "Mind map templates", "items": items}


# --- Phosphor glyphs as paths ----------------------------------------------------

class _Font:
    """Just enough of a TrueType reader for simple and composite glyphs."""

    def __init__(self, data: bytes):
        self.data = data
        self.tables = {}
        count = struct.unpack(">H", data[4:6])[0]
        for i in range(count):
            tag, _, off, length = struct.unpack(">4sIII", data[12 + i * 16 : 28 + i * 16])
            self.tables[tag.decode("latin-1")] = (off, length)
        head = self.tables["head"][0]
        self.units = struct.unpack(">H", data[head + 18 : head + 20])[0]
        self.long_loca = struct.unpack(">h", data[head + 50 : head + 52])[0] == 1
        maxp = self.tables["maxp"][0]
        self.glyphs = struct.unpack(">H", data[maxp + 4 : maxp + 6])[0]
        hhea = self.tables["hhea"][0]
        self.ascender = struct.unpack(">h", data[hhea + 4 : hhea + 6])[0]
        self.descender = struct.unpack(">h", data[hhea + 6 : hhea + 8])[0]
        loca = self.tables["loca"][0]
        if self.long_loca:
            self.loca = list(struct.unpack(f">{self.glyphs + 1}I", data[loca : loca + 4 * (self.glyphs + 1)]))
        else:
            self.loca = [v * 2 for v in struct.unpack(f">{self.glyphs + 1}H", data[loca : loca + 2 * (self.glyphs + 1)])]
        self.cmap = self._cmap()

    def _cmap(self) -> dict[int, int]:
        data = self.data
        base = self.tables["cmap"][0]
        count = struct.unpack(">H", data[base + 2 : base + 4])[0]
        out: dict[int, int] = {}
        for i in range(count):
            _, _, off = struct.unpack(">HHI", data[base + 4 + i * 8 : base + 12 + i * 8])
            sub = base + off
            fmt = struct.unpack(">H", data[sub : sub + 2])[0]
            if fmt == 12:
                groups = struct.unpack(">I", data[sub + 12 : sub + 16])[0]
                for g in range(groups):
                    start, end, gid = struct.unpack(">III", data[sub + 16 + g * 12 : sub + 28 + g * 12])
                    for c in range(start, end + 1):
                        out[c] = gid + (c - start)
            elif fmt == 4:
                segs = struct.unpack(">H", data[sub + 6 : sub + 8])[0] // 2
                ends = struct.unpack(f">{segs}H", data[sub + 14 : sub + 14 + segs * 2])
                p = sub + 16 + segs * 2
                starts = struct.unpack(f">{segs}H", data[p : p + segs * 2])
                deltas = struct.unpack(f">{segs}h", data[p + segs * 2 : p + segs * 4])
                ro_at = p + segs * 4
                offsets = struct.unpack(f">{segs}H", data[ro_at : ro_at + segs * 2])
                for s in range(segs):
                    for c in range(starts[s], ends[s] + 1):
                        if c == 0xFFFF:
                            continue
                        if offsets[s] == 0:
                            gid = (c + deltas[s]) & 0xFFFF
                        else:
                            at = ro_at + s * 2 + offsets[s] + (c - starts[s]) * 2
                            gid = struct.unpack(">H", data[at : at + 2])[0]
                            if gid:
                                gid = (gid + deltas[s]) & 0xFFFF
                        out.setdefault(c, gid)
        return out

    def contours(self, gid: int, dx=0.0, dy=0.0) -> list[list[tuple[float, float, bool]]]:
        data = self.data
        glyf = self.tables["glyf"][0]
        start, end = self.loca[gid], self.loca[gid + 1]
        if start == end:
            return []
        g = glyf + start
        n = struct.unpack(">h", data[g : g + 2])[0]
        if n < 0:
            return self._composite(g + 10, dx, dy)
        end_pts = struct.unpack(f">{n}H", data[g + 10 : g + 10 + 2 * n])
        ilen = struct.unpack(">H", data[g + 10 + 2 * n : g + 12 + 2 * n])[0]
        p = g + 12 + 2 * n + ilen
        total = end_pts[-1] + 1
        flags = []
        while len(flags) < total:
            f = data[p]
            p += 1
            flags.append(f)
            if f & 8:
                repeat = data[p]
                p += 1
                flags.extend([f] * repeat)
        xs, ys = [], []
        v = 0
        for f in flags:
            if f & 2:
                d = data[p]
                p += 1
                v += d if f & 16 else -d
            elif not f & 16:
                v += struct.unpack(">h", data[p : p + 2])[0]
                p += 2
            xs.append(v)
        v = 0
        for f in flags:
            if f & 4:
                d = data[p]
                p += 1
                v += d if f & 32 else -d
            elif not f & 32:
                v += struct.unpack(">h", data[p : p + 2])[0]
                p += 2
            ys.append(v)
        out, s = [], 0
        for e in end_pts:
            out.append([(xs[i] + dx, ys[i] + dy, bool(flags[i] & 1)) for i in range(s, e + 1)])
            s = e + 1
        return out

    def _composite(self, p, dx, dy):
        data = self.data
        out = []
        while True:
            flags, gid = struct.unpack(">HH", data[p : p + 4])
            p += 4
            if flags & 1:
                a, b = struct.unpack(">hh", data[p : p + 4])
                p += 4
            else:
                a, b = struct.unpack(">bb", data[p : p + 2])
                p += 2
            if flags & 8:
                p += 2
            elif flags & 0x40:
                p += 4
            elif flags & 0x80:
                p += 8
            out.extend(self.contours(gid, dx + a, dy + b))
            if not flags & 0x20:
                return out


def _glyph_path(contours, units, ascender, size=96.0) -> str:
    """Quadratic contours as M, L, C, Z (the board's path grammar has no Q)."""
    k = size / units
    tx = lambda x: x * k  # noqa: E731
    ty = lambda y: (ascender - y) * k  # noqa: E731
    parts = []
    for pts in contours:
        if not pts:
            continue
        # Start on an on-curve point; between two off-curve points the
        # midpoint is an implied on-curve point.
        expanded = []
        for i, (x, y, on) in enumerate(pts):
            expanded.append((x, y, on))
            nx, ny, non = pts[(i + 1) % len(pts)]
            if not on and not non:
                expanded.append(((x + nx) / 2, (y + ny) / 2, True))
        first = next((i for i, q in enumerate(expanded) if q[2]), None)
        if first is None:
            continue
        seq = expanded[first:] + expanded[:first]
        sx, sy, _ = seq[0]
        cmds = ["M", tx(sx), ty(sy)]
        cx, cy = sx, sy
        i = 1
        while i <= len(seq):
            x, y, on = seq[i % len(seq)]
            if on:
                cmds += ["L", tx(x), ty(y)]
                cx, cy = x, y
                i += 1
            else:
                ex, ey, _ = seq[(i + 1) % len(seq)]
                c1 = (cx + 2 / 3 * (x - cx), cy + 2 / 3 * (y - cy))
                c2 = (ex + 2 / 3 * (x - ex), ey + 2 / 3 * (y - ey))
                cmds += ["C", tx(c1[0]), ty(c1[1]), tx(c2[0]), ty(c2[1]), tx(ex), ty(ey)]
                cx, cy = ex, ey
                i += 2
        cmds.append("Z")
        parts.append(_compact(cmds))
    return "".join(parts)


def _compact(cmds) -> str:
    """`M87 39C87 36.1 ...`: a command letter needs no space around it, which
    takes a quarter off a file of 1,530 glyphs."""
    out = []
    for part in cmds:
        if isinstance(part, str):
            out.append(part)
        else:
            text = _n(part)
            if out and not isinstance(out[-1], str) or (out and out[-1] not in "MLCZ"):
                out.append(" ")
            out.append(text)
    return "".join(out)


def icons():
    font = _Font((PHOSPHOR / "Phosphor.ttf").read_bytes())
    css = (PHOSPHOR / "style.css").read_text(encoding="utf-8")
    names = re.findall(r'\.ph-([a-z0-9-]+):before\s*\{\s*content:\s*"\\([0-9a-f]+)"', css)
    out = {}
    for name, code in names:
        gid = font.cmap.get(int(code, 16))
        if not gid:
            continue
        d = _glyph_path(font.contours(gid), font.units, font.ascender)
        if d:
            out[name] = d
    return {
        "format": "memorymap-icons",
        "version": 1,
        "source": "Phosphor Icons (MIT), frontend/vendor/phosphor/LICENSE; glyphs converted to paths by scripts/build_board_library.py",
        "size": 96,
        "icons": dict(sorted(out.items())),
    }


# --- BPMN ----------------------------------------------------------------------
# Drawn fresh here (the draw.io BPMN stencils are a separate, converted set).

def _bpmn_item(key, name, tags, d, w, h, *, width=2, area=None, fill_opacity=0.12):
    item = shape_item(d, w, h, fill_opacity=fill_opacity, label_area=area)
    item["data"]["width"] = width
    return element(key, name, tags, [item], w, h)


def bpmn():
    circle = ellipse_d(24, 24, 24, 24)
    inner = ellipse_d(24, 24, 19, 19)
    diamond = poly([(30, 0), (60, 30), (30, 60), (0, 30)])
    cross = path("M", 18, 18, "L", 42, 42, "M", 42, 18, "L", 18, 42)
    plus = path("M", 30, 14, "L", 30, 46, "M", 14, 30, "L", 46, 30)
    envelope = path("M", 12, 16, "L", 36, 16, "L", 36, 32, "L", 12, 32, "Z", "M", 12, 16, "L", 24, 26, "L", 36, 16)
    clock = path(ellipse_d(24, 24, 11, 11), "M", 24, 24, "L", 24, 16, "M", 24, 24, "L", 30, 28)
    task = rounded_rect(120, 80, 10)
    subprocess = path(rounded_rect(120, 80, 10), "M", 52, 62, "L", 68, 62, "L", 68, 74, "L", 52, 74, "Z", "M", 60, 65, "L", 60, 71, "M", 57, 68, "L", 63, 68)
    data_object = path("M", 0, 0, "L", 30, 0, "L", 40, 10, "L", 40, 52, "L", 0, 52, "Z", "M", 30, 0, "L", 30, 10, "L", 40, 10)
    data_store = path("M", 0, 8, "A", 25, 8, 0, 0, 1, 50, 8, "L", 50, 44, "A", 25, 8, 0, 0, 1, 0, 44, "Z", "M", 0, 8, "A", 25, 8, 0, 0, 0, 50, 8)
    annotation = path("M", 20, 0, "L", 0, 0, "L", 0, 60, "L", 20, 60)
    pool = path("M", 0, 0, "L", 400, 0, "L", 400, 160, "L", 0, 160, "Z", "M", 32, 0, "L", 32, 160)
    lanes = path("M", 0, 0, "L", 400, 0, "L", 400, 240, "L", 0, 240, "Z", "M", 32, 0, "L", 32, 240, "M", 32, 120, "L", 400, 120)
    items = [
        _bpmn_item("start-event", "Start event", ["bpmn", "begin", "event", "circle"], circle, 48, 48, area={"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6}),
        _bpmn_item("intermediate-event", "Intermediate event", ["bpmn", "event", "catch", "double circle"], path(circle, inner), 48, 48),
        _bpmn_item("end-event", "End event", ["bpmn", "finish", "event", "terminate"], circle, 48, 48, width=5),
        _bpmn_item("message-start", "Message start event", ["bpmn", "event", "envelope", "receive"], path(circle, envelope), 48, 48),
        _bpmn_item("timer-event", "Timer intermediate event", ["bpmn", "event", "clock", "wait"], path(circle, inner, clock), 48, 48),
        _bpmn_item("task", "Task", ["bpmn", "activity", "step", "work"], task, 120, 80, area={"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.8}),
        _bpmn_item("sub-process", "Sub-process", ["bpmn", "activity", "collapsed", "group"], subprocess, 120, 80, area={"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.6}),
        _bpmn_item("gateway-exclusive", "Gateway, exclusive (XOR)", ["bpmn", "decision", "xor", "diamond"], path(diamond, cross), 60, 60),
        _bpmn_item("gateway-parallel", "Gateway, parallel (AND)", ["bpmn", "fork", "join", "and"], path(diamond, plus), 60, 60),
        _bpmn_item("gateway-inclusive", "Gateway, inclusive (OR)", ["bpmn", "or", "diamond"], path(diamond, ellipse_d(30, 30, 14, 14)), 60, 60),
        _bpmn_item("data-object", "Data object", ["bpmn", "document", "artifact"], data_object, 40, 52),
        _bpmn_item("data-store", "Data store", ["bpmn", "database", "artifact"], data_store, 50, 52),
        _bpmn_item("text-annotation", "Text annotation", ["bpmn", "note", "comment"], annotation, 80, 60, area={"x": 0.1, "y": 0, "w": 0.9, "h": 1}, fill_opacity=0),
        _bpmn_item("pool", "Pool", ["bpmn", "participant", "swimlane"], pool, 400, 160, area={"x": 0.09, "y": 0, "w": 0.91, "h": 1}),
        _bpmn_item("pool-two-lanes", "Pool with two lanes", ["bpmn", "lane", "swimlane", "participant"], lanes, 400, 240, area={"x": 0.09, "y": 0, "w": 0.91, "h": 0.5}),
    ]
    return {"key": "bpmn", "name": "BPMN", "items": items}


# --- Icon sets, picked from the Phosphor glyphs ----------------------------------

ICON_SETS = {
    "cloud-network": ("Cloud and network", (
        "cloud cloud-arrow-up cloud-arrow-down cloud-check cloud-lightning database hard-drives hard-drive globe "
        "globe-hemisphere-west wifi-high wifi-slash network lock-key shield-check cpu stack queue plugs-connected "
        "terminal-window git-branch package cube gear").split()),
    "devices-people": ("Devices and people", (
        "desktop desktop-tower laptop monitor device-mobile device-tablet printer robot user user-circle users "
        "users-three envelope-simple chat-circle bug code").split()),
}


def icon_sets(glyphs):
    out = []
    for key, (name, wanted) in ICON_SETS.items():
        items = []
        for icon in wanted:
            if icon not in glyphs:
                raise SystemExit(f"icon set {key}: no glyph {icon}")
            data = {"d": glyphs[icon], "fill": "ink", "noStroke": True, "icon": icon}
            items.append(element(icon, icon.replace("-", " ").capitalize(), ["icon", key.split("-")[0]],
                                 [{"key": "i", "kind": "sketch", "data": data}], 96, 96))
        out.append({"key": key, "name": name, "items": items})
    return out



def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = icons()
    # UML, ERD, wireframe and C4 were written by earlier runs and are kept: the index is read, then updated by key.
    # Only the sets this file still owns outright are rewritten; the others (templates, flowchart, frames, UML, ...)
    # were edited in the committed JSON since, and writing them again here would undo that.
    sets = [bpmn(), *icon_sets(data["icons"])]
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))["sets"] if index_path.exists() else []
    for s in sets:
        (OUT / f"{s['key']}.json").write_text(json.dumps({"format": "memorymap-library-set", "version": 1, **s}, indent=1) + "\n", encoding="utf-8")
        entry = {"key": s["key"], "name": s["name"], "count": len(s["items"])}
        at = next((i for i, e in enumerate(index) if e["key"] == s["key"]), None)
        if at is None:
            after = next((i for i, e in enumerate(index) if e["key"] == "wireframe"), None) if s["key"] == "bpmn" else None
            before_icons = next((i for i, e in enumerate(index) if e["key"] == "icons"), len(index))
            index.insert(after + 1 if after is not None else before_icons, entry)
        else:
            index[at] = entry
    count = next((i for i, e in enumerate(index) if e["key"] == "icons"), None)
    entry = {"key": "icons", "name": "Icons", "count": len(data["icons"])}
    if count is None:
        index.append(entry)
    else:
        index[count] = entry
    index_path.write_text(json.dumps({"format": "memorymap-library-index", "version": 1, "sets": index}, indent=1) + "\n", encoding="utf-8")
    print(", ".join(f"{e['name']} {e['count']}" for e in index))


if __name__ == "__main__":
    main()
