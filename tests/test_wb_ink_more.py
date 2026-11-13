"""Ink beyond the plain pen (WHITEBOARD_PLAN section 3). `whiteboard-ink-more.js` is run in node for its pure parts;
the browser half is `scratchpad/ui-sweeps/wbink3.js`."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

#: The board's own helpers, lifted from whiteboard.js so the test uses the shipped inset, not a copy.
_HELPERS = (
    "const WB_HOLLOW_INSET = { diamond: (h) => h * 1.1, \"triangle-open\": (h) => h, circle: (h) => (h * 2) / 3, square: (h) => (h * 2) / 2.6 };\n"
    "const WB_CAP_SIZE_SCALE = { s: 0.7, l: 1.45 };\n"
)


def _node(body: str, files=("whiteboard-ink-more.js",)):
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
    script = "const wbFmtState = {};\n" + _HELPERS + helpers + "\n" + "\n".join(frontend_text(f) for f in files) + "\n" + body
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
