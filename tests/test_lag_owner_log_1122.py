"""Source text: forced layouts in the owner's lag log of 2026-11-22 (Windows, 46 notes). A forced layout is a read placed after a write, which no test without a browser can time; the order or shape that fixed each is pinned here, and the timing is scratchpad/lag/probe.js (AB=1, 4x CPU).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
LIB = (JS / "whiteboard-library.js").read_text(encoding="utf-8")


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(name)


def test_the_board_library_keeps_its_scroll_without_reading_it_on_a_redraw() -> None:
    # #wb-add-note: 274 ms, 258 of them forced layout. `wbRenderLibrary` read `list.scrollTop`
    # just after the sidebar was shown, laying the whole panel out before rebuilding it
    # (4x CPU, 4 runs each: the click 568 to 440 ms, its forced layout 331 to 238 ms).
    render = _fn(LIB, "wbRenderLibrary")
    assert "? list.scrollTop" not in render
    assert 'addEventListener("scroll"' in render and "wbLibState.libScroll = list.scrollTop" in render
    # The offset is written back only when it has to move.
    assert "if (top || was) list.scrollTop = top;" in render
