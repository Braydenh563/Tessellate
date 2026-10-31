"""Audit 1029 G30: a slow reload of a map already shown gave no sign it was
working. `renderGraphCanvas` marks `#graph-stats` busy from 400 ms until the
data is in, and a thin accent line runs under the count. Measured in Chromium
with `/graph` held 1.5 s: no line at 200 ms, `aria-busy="true"` and the
`graph-reloading` animation (background 40% x 2px) at 700 ms, both gone once
the map was in."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")


def test_a_slow_reload_marks_the_count_busy_and_clears_it():
    start = JS.index("const stats = s.shown ? document.getElementById(\"graph-stats\") : null;")
    block = JS[start : start + 400]
    assert 'setAttribute("aria-busy", "true"), 400)' in block
    assert "clearTimeout(slow);" in block and 'stats?.removeAttribute("aria-busy");' in block
    # Cleared before either outcome is handled, so a failed read clears it too.
    assert block.index('removeAttribute("aria-busy")') < block.index("if (!data)")


def test_the_line_is_thin_and_holds_still_for_less_motion():
    assert '#graph-stats[aria-busy="true"]' in CSS and "40% 2px" in CSS
    assert "@keyframes graph-reloading" in CSS
    reduced = CSS[CSS.index(':root[data-motion="reduced"] #graph-stats[aria-busy="true"]') :]
    assert "animation: none" in reduced[: reduced.index("}")]
