"""At phone width the board's context bar never covers the selection it edits
(uipolish-0924 item C, `#wb-context`).

Pinned to the top of the canvas, it sat over 3 of the sweep's 10 selections,
the ones high on the board (6080, 6719 and 319px2, measured by
`scratchpad/ui-sweeps/wbcontextphone.js` at 390x844). Such a selection gets
the bar at the foot of the canvas, above the rail: 0px2 on all ten, two
fixed places, never on the rail or the top bar; 1440 keeps the floating bar.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_a_selection_under_the_top_band_gets_the_foot() -> None:
    js = frontend_text("whiteboard.js")
    start = js.index("const pinned = active === bar && WB_PHONE.matches;")
    block = js[start : js.index("} else {", start)]
    assert 'getElementById("wb-tool-group")' in block, "the foot is measured against the rail"
    assert 'bar.dataset.wbAnchor = "bottom";' in block
    assert "!under(foot)" in block, "a selection that meets both bands keeps the top"
