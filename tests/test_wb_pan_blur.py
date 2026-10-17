"""A board or mind map pan does not re-blur the panels over it (BACKLOG, the owner 2026-10-12).

"With a popup tool panel showing, a two-finger trackpad pan is slow and
laggy." The panels over a board (top bar, tool rail, zoom card, map strip,
side bar) are glass: `backdrop-filter: blur(14px)` samples what is under it,
which moves on every pan frame, so each frame re-blurs five panels.

Measured (scratchpad sweep, 57-topic map, 1440x900, a wheel event every frame
for 2 s, medians of four runs): Glass on with a topic selected, 85 frames and
p95 50 ms (max 167 ms); Glass off, 117 frames and p95 16.7 ms. Fixed by
dropping the blur while the board moves and putting it back 180 ms after the
last pan or zoom step (`wbMarkMoving`), the same thing Glass off does for
good, so nothing blurs over moving pixels.
"""

from __future__ import annotations

import re

from tests._app_js import FRONTEND_DIR, JS_DIR

WB = (JS_DIR / "whiteboard.js").read_text(encoding="utf-8")
CSS = (FRONTEND_DIR / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_every_pan_and_zoom_step_marks_the_board_as_moving():
    start = WB.index("function handleWbZoom(")
    assert "wbMarkMoving();" in WB[start : WB.index("\n}\n", start)]
    helper = WB[WB.index("function wbMarkMoving(") :][:700]
    assert 'classList.add("wb-moving")' in helper and "WB_MOVING_MS" in helper
    assert int(re.search(r"const WB_MOVING_MS = (\d+);", WB).group(1)) >= 120


def test_the_marked_board_drops_the_blur_of_every_panel_over_it():
    rule = CSS[CSS.index("#wb-canvas-view.wb-moving") :][:900]
    for panel in (".wb-topbar", ".whiteboard-floating-panel", ".wb-map-strip", ".wb-sidebar"):
        assert panel in rule, panel
    assert "backdrop-filter: none" in rule and "-webkit-backdrop-filter: none" in rule
