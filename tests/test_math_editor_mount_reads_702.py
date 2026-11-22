"""L702: the equation editor's mount reads no layout, and its jump strip hears the pane that scrolls.

Measured at 4x on the chat box (1093x614): the mount's `mark` forced 675ms of layout and 571ms
of style, reading 21 group headings before the pane had ever been laid out; afterwards 0.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text


def _draw() -> str:
    text = frontend_text("math-editor.js")
    start = text.index("const draw = (")
    return text[start:text.index("\n  };\n", start)]


def test_the_mount_draw_marks_the_first_chip_and_reads_rects_after_the_frame():
    text = frontend_text("math-editor.js")
    draw = _draw()
    first = draw[draw.index("if (first) {"):]
    first = first[:first.index("return;")]
    assert "getBoundingClientRect" not in first and "scrollHeight" not in first
    assert "afterFrames(() => host.isConnected && mark())" in first
    assert "const before = first ? 0 :" in draw
    assert "draw({ first: true });" in text


def test_the_jump_strip_listens_on_the_equation_pane_that_scrolls():
    text = frontend_text("math-editor.js")
    assert 'const scroller = host.closest(".calc-equation, .calc-panes");' in text
    css = (Path(__file__).resolve().parents[1] / "frontend/css/reply-kit-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"\.calc-pane\.calc-equation \{[^}]*\}", css).group(0)
    assert "overflow-y: auto" in rule
