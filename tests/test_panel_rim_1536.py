"""Every edge and corner of a movable panel resizes it (INBOX 1536).

The owner: "can you make the edges and corners of popups resizable??". The
outer 6px of a panel name the edge (`data-rim`, with its resize cursor), and a
press there resizes from that side with the opposite edge held still.
Measured on Settings at 1440 by 900 (`scratchpad/ui-sweeps/rim1536.js`): left
208 to 148 with the right at 1232; right 1232 to 1182 with the left held;
top 54 to 94 and bottom 846 to 806 the same way; the top left corner both."""

from __future__ import annotations

import re

from tests._app_js import frontend_text

JS = frontend_text("panel-movable.js")
CSS = (__import__("pathlib").Path(__file__).resolve().parents[1] / "frontend/css/panel-movable-lazy.css").read_text()


def test_an_adopted_panel_watches_its_rim_without_reading_layout_per_move():
    assert 'panel.addEventListener("pointermove", panelAdopt.rimHover)' in JS
    hover = JS[JS.index("panelAdopt.rimHover = (e) => {"):]
    hover = hover[:hover.index("\n};\n")]
    #: One box read, only when none is kept; the save drops it.
    assert hover.count("getBoundingClientRect") == 1 and "if (!st.rim)" in hover
    assert re.search(r"function panelSave\(panel\) \{\n  const st = panelSt\(panel\);\n  st\.rim = null;", JS)


def test_a_press_on_the_rim_resizes_from_that_edge():
    down = JS[JS.index("function panelGripDown(e, rimmed)"):]
    down = down[:down.index("\nfunction ")]
    assert 'const dx = edge.includes("e") ? 1 : edge.includes("w") ? -1 : 0;' in down
    #: Grown left or up, the far edge holds: the translate takes the growth back.
    assert "- (dx < 0 ? sw : 0)" in down and "- (dy < 0 ? sh : 0)" in down
    assert 'e.target.closest(".panel-movable-on[data-rim]")' in JS


def test_each_rim_has_its_resize_cursor():
    for edge, cursor in (("n", "ns-resize"), ("e", "ew-resize"), ("ne", "nesw-resize"), ("nw", "nwse-resize")):
        assert re.search(rf'\[data-rim="{edge}"\][^{{]*\{{\s*cursor: {cursor};', CSS), edge
