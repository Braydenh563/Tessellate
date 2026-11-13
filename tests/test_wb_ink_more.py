"""Ink beyond the plain pen (WHITEBOARD_PLAN section 3). `whiteboard-ink-more.js` is run in node for its pure parts;
the browser half is `scratchpad/ui-sweeps/wbink3.js`."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

VENDOR = Path(__file__).resolve().parent.parent / "frontend" / "vendor" / "perfect-freehand" / "perfect-freehand.min.js"

#: The board's own helpers, lifted from whiteboard.js so the test uses the shipped inset, not a copy.
_HELPERS = (
    "const WB_HOLLOW_INSET = { diamond: (h) => h * 1.1, \"triangle-open\": (h) => h, circle: (h) => (h * 2) / 3, square: (h) => (h * 2) / 2.6 };\n"
    "const WB_CAP_SIZE_SCALE = { s: 0.7, l: 1.45 };\n"
)


def _node(body: str, files=("whiteboard-ink-more.js",), vendor=False):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = frontend_text("whiteboard.js")
    start = src.index("function wbCapScale(")
    helpers = src[start : src.index("}", start) + 1]
    h0 = src.index("function wbHollowInset(")
    helpers += "\n" + src[h0 : src.index("}", h0) + 1]
    s0 = src.index("function wbShaftEnd(")
    helpers += "\n" + src[s0 : src.index("\n}\n", s0) + 3]
    lib = ("var window = {};\n" + VENDOR.read_text(encoding="utf-8") + "\n") if vendor else ""
    script = "const wbFmtState = {};\n" + lib + _HELPERS + helpers + "\n" + "\n".join(frontend_text(f) for f in files) + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_a_hollow_end_stops_the_shaft_at_its_edge():
    out = _node(
        "console.log(JSON.stringify(wbFmtState.inkMore.trimShaft('M 0 0 L 100 0 M 100 0 L 90 5', 'none', 'circle', 18, {}, wbShaftEnd)));"
    )
    #: circle inset is headLen * 2 / 3 = 12: the shaft ends 12 short of the tip, the cap path is untouched.
    assert out == "M 0 0 L 88 0 M 100 0 L 90 5"


def test_both_ends_are_trimmed_and_solid_or_open_ends_are_not():
    both = _node("console.log(JSON.stringify(wbFmtState.inkMore.trimShaft('M 0 0 L 100 0', 'diamond', 'diamond', 10, {}, wbShaftEnd)));")
    assert both == "M 11 0 L 89 0"
    solid = _node("console.log(JSON.stringify(wbFmtState.inkMore.trimShaft('M 0 0 L 100 0', 'arrow', 'triangle', 10, {}, wbShaftEnd)));")
    assert solid == "M 0 0 L 100 0"


def test_a_short_line_keeps_a_stub_and_a_curve_is_left_alone():
    short = _node("console.log(JSON.stringify(wbFmtState.inkMore.trimShaft('M 0 0 L 10 0', 'square', 'square', 40, {}, wbShaftEnd)));")
    assert short == "M 9 0 L 1 0"
    curve = _node("console.log(JSON.stringify(wbFmtState.inkMore.trimShaft('M 0 0 Q 5 5 10 0', 'circle', 'circle', 18, {}, wbShaftEnd)));")
    assert curve == "M 0 0 Q 5 5 10 0"


def test_the_board_trims_the_drawn_path_and_keeps_the_hit_band_whole():
    wb = frontend_text("whiteboard.js")
    assert "wbFmtState.inkMore?.trimShaft(parsed.d" in wb
    assert "hitboxData = parsed.d; pathData = trimmed;" in wb
    assert "wbFmtState.inkMore?.trimShaft(liveD" in wb
    assert "/js/whiteboard-ink-more.js" in frontend_text("lazy-entries.js")


# --- Smoothed, pressure-aware ink (L-whiteboard-1, L-whiteboard-5) ------------------------------------------------


def _thickness(pressure, pointer):
    """The outline's height for a straight horizontal run of 40 points at one synthetic pressure."""
    points = [[i * 4, 50, pressure] for i in range(40)]
    return _node(
        f"const d = wbFmtState.inkMore.outline({json.dumps(points)}, 'draw', 4, {json.dumps(pointer)}, true, window.perfectFreehand);"
        "const ys = [...d.matchAll(/[ML] [-\\d.]+ ([-\\d.]+)/g)].map((m) => +m[1]);"
        "console.log(JSON.stringify(Math.max(...ys) - Math.min(...ys)));",
        vendor=True,
    )


def test_a_pen_stroke_is_wider_where_the_pen_presses_harder():
    light, hard = _thickness(0.15, "pen"), _thickness(0.9, "pen")
    assert 0 < light < hard
    assert hard / light > 2


def test_a_mouse_stroke_ignores_the_reported_pressure_and_is_still_a_stroke():
    # A mouse reports a fixed 0.5 while pressed: simulated pressure (speed) decides, so the value barely moves the width
    # (the pen's is above 2 times).
    assert _thickness(0.9, "mouse") / _thickness(0.15, "mouse") < 1.5
    assert _thickness(0.5, "mouse") > 1


def test_the_outline_is_plain_move_and_line_points_with_no_close():
    d = _node(
        "console.log(JSON.stringify(wbFmtState.inkMore.outline([[0,0],[20,10],[40,0]], 'draw', 4, 'mouse', true, window.perfectFreehand)));",
        vendor=True,
    )
    assert d.startswith("M ") and " L " in d
    assert not set(d) - set("ML 0123456789.-")


def test_one_point_is_a_dot_and_nothing_without_the_library():
    dot = _node("console.log(JSON.stringify(wbFmtState.inkMore.outline([[5,5]], 'draw', 4, 'mouse', true, window.perfectFreehand)));", vendor=True)
    assert dot.startswith("M ")
    none = _node("console.log(JSON.stringify(wbFmtState.inkMore.outline([[5,5]], 'draw', 4, 'mouse', true, null)));")
    assert none == ""


def test_a_dashed_pen_keeps_the_plain_stroke_and_a_marker_does_not_thin():
    out = _node(
        "const m = wbFmtState.inkMore; console.log(JSON.stringify([m.takesInk('solid', {}), m.takesInk('dashed', {}), m.takesInk(undefined, {}), m.takesInk('solid', null), m.inkOptions('highlighter', 20, 'pen').thinning]));"
    )
    assert out == [True, False, True, False, 0]


def test_the_library_is_vendored_with_its_licence_and_version():
    folder = VENDOR.parent
    assert (folder / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    assert (folder / "VERSION.txt").read_text(encoding="utf-8").startswith("perfect-freehand 1.2.3")
    assert (folder / "build.sh").is_file()


def test_the_board_draws_pen_and_marker_through_it():
    wb = frontend_text("whiteboard.js")
    assert "wbFmtState.inkMore.liveStyle(" in wb and "Object.assign(blob, { ink: 1 }" in wb and "if (parsed.ink) {" in wb
    assert "[x, y, e.pressure]" in wb
    entries = frontend_text("lazy-entries.js")
    assert entries.index("/vendor/perfect-freehand/perfect-freehand.min.js") < entries.index("/js/whiteboard-ink-more.js")


_BBOX = (
    "const bbox = (d) => { const n = (d.match(/-?\\d*\\.?\\d+/g) || []).map(Number); const xs = n.filter((_, i) => i % 2 === 0), ys = n.filter((_, i) => i % 2); "
    "const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys); return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY }; };\n"
)
_STROKE = (
    "const m = wbFmtState.inkMore; const hand = []; for (let i = 0; i <= 30; i++) hand.push([100 + i * 8, 100 + Math.sin(i / 4) * 30]);\n"
    "const d0 = m.outline(hand, 'draw', 3, 'mouse', true, window.perfectFreehand);\n"
    "const parsed = { d: d0, ink: 1, width: 3, shape: 'draw', ...m.keepPoints(hand, bbox(d0)) };\n"
)


def test_a_new_width_draws_the_outline_again_from_the_kept_points_l_whiteboard_31():
    out = _node(
        _BBOX + _STROKE + "const r = m.rebuild(parsed, 12, bbox, window.perfectFreehand);\n"
        "console.log(JSON.stringify({ before: bbox(d0).height, after: bbox(r.d).height, pts: r.pts.length > 10, pbox: Array.isArray(r.pbox) }));",
        vendor=True,
    )
    assert out["after"] > out["before"] + 8  # a 12 wide pen is fatter than a 3 wide one
    assert out["pts"] and out["pbox"]


def test_a_stroke_without_kept_points_only_changes_its_number():
    out = _node(
        _BBOX + "const m = wbFmtState.inkMore; console.log(JSON.stringify([m.rebuild({ d: 'M 0 0 L 5 5', ink: 1 }, 9, bbox, window.perfectFreehand), m.rebuild({ d: 'M 0 0', shape: 'rect' }, 9, bbox, window.perfectFreehand)]));",
        vendor=True,
    )
    assert out == [{}, {}]


def test_a_quarter_turn_turns_the_kept_points_with_the_outline_l_whiteboard_31():
    out = _node(
        _BBOX + _STROKE +
        "const nums = d0.match(/-?\\d*\\.?\\d+/g).map(Number); let cx = 0, cy = 0;\n"
        "const b = bbox(d0); cx = (b.minX + b.maxX) / 2; cy = (b.minY + b.maxY) / 2;\n"
        "let k = 0; const d1 = d0.replace(/-?\\d*\\.?\\d+/g, () => { const i = k++; const x = nums[i - (i % 2)], y = nums[i - (i % 2) + 1]; return String(i % 2 ? Math.round((cy + (x - cx)) * 10) / 10 : Math.round((cx - (y - cy)) * 10) / 10); });\n"
        "const before = JSON.stringify(parsed.pts); m.follow(parsed, d1, bbox); parsed.d = d1;\n"
        "const placed = m.placePoints(parsed.pts, parsed.pbox, bbox(d1));\n"
        "const first = [cx - (hand[0][1] - cy), cy + (hand[0][0] - cx)];\n"
        "console.log(JSON.stringify({ changed: before !== JSON.stringify(parsed.pts), dx: Math.abs(placed[0][0] - first[0]), dy: Math.abs(placed[0][1] - first[1]) }));",
        vendor=True,
    )
    assert out["changed"] and out["dx"] < 1.5 and out["dy"] < 1.5


def test_a_move_or_a_stretch_leaves_the_kept_points_to_the_box_mapping():
    out = _node(
        _BBOX + _STROKE +
        "let k = 0; const moved = d0.replace(/-?\\d*\\.?\\d+/g, (t) => String(Number(t) + (k++ % 2 ? 0 : 50)));\n"
        "const before = JSON.stringify(parsed.pts); m.follow(parsed, moved, bbox);\n"
        "console.log(JSON.stringify(before === JSON.stringify(parsed.pts)));",
        vendor=True,
    )
    assert out is True


def test_the_width_control_and_every_path_change_reach_the_ink_helpers():
    board = frontend_text("whiteboard.js")
    fmt = frontend_text("whiteboard-format.js")
    assert "wbFmtState.inkMore.rebuild(" in fmt
    for name in ("function wbSketchSetD", "function wbSketchSetProps", "async function wbSaveSketchProps"):
        body = board[board.index(name) :][:900]
        assert "inkMore?.follow(" in body, name
