"""Chat and Graph keep their rows, their rings and their panels apart at every
zoom and resolution (the owner, 2026-11-11: "make sure the wrapping and ui
issues arent an issue anywhere else from zoom or resolution").

Measured by `scratchpad/ui-sweeps/wrapzoom-chat.js` over ten viewports
(1280x720 to 2560x1440 at 100 %, 125 %, 150 % and 200 %, and 768x1024).
These pin what the fixes rest on; the ring rooms are in
`tests/test_ring_room.py`, the chat strip's band in `tests/test_chat_dock.py`
and the panel observer in `tests/test_graph_popup_room.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import CSS_DIR

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
GRAPH_CSS = (CSS_DIR / "02-chat-graph.css").read_text(encoding="utf-8")
WIDGETS_CSS = (CSS_DIR / "03-dashboard-widgets.css").read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_the_selection_dock_is_in_the_column_not_over_its_panels():
    """Out of the flow it sat at the height of the topic's card and covered
    its name: 137px at 1280x720, all of it at 768x1024."""
    rule = _rule(GRAPH_CSS, ".graph-selection-dock")
    assert "position: absolute" not in rule and "top:" not in rule
    assert "align-self: center" in rule


def test_the_selection_dock_keeps_one_row_by_losing_its_words():
    """792px with its words: two rows and 114px tall at 768."""
    bar = re.search(r'id="graph-selection-dock".*?</div>', HTML, re.S).group(0)
    buttons = re.findall(r"<button [^>]*>.*?</button>", bar, re.S)
    worded = [b for b in buttons if "icon-only" not in b]
    assert len(worded) == 6
    assert all('<span class="dock-word">' in b for b in worded)
    band = GRAPH_CSS[GRAPH_CSS.index("@media (max-width: 1099.98px) {\n  .graph-selection-dock .dock-word") :]
    band = band[: band.index("\n}\n")]
    assert "clip-path: inset(50%)" in band and "display: none" not in band
    assert ".graph-selection-dock > button:has(> .ph-lead + .dock-word)" in band


def test_the_map_dock_keeps_one_row_with_a_highlight_on():
    """Clear highlight's 144px sent the actions to a second row at 768."""
    for word in ("Clear highlight", "Exit focus"):
        assert f'<span class="dock-word">{word}</span></button>' in HTML
    assert '.dock[data-dock-name="graph"] .dock-find .dock-word' in GRAPH_CSS
    band = GRAPH_CSS[GRAPH_CSS.index("@media (min-width: 600px) and (max-width: 1099.98px) {\n  .dock[data-dock-name=\"graph\"] > .dock-find") :]
    assert "flex-basis: 8rem" in band[: band.index("\n}\n")]


def test_an_option_rows_clip_skips_the_picker_shell():
    """The label clip matched `span.select-shell` too, and cut the opener's
    whole focus ring on four pickers at every viewport."""
    assert ".graph-option-row > span:not(.select-shell) {" in WIDGETS_CSS
    assert not re.search(r"\.graph-option-row > span \{", WIDGETS_CSS)
    assert not re.search(r"\.graph-option-row > span,", WIDGETS_CSS)
