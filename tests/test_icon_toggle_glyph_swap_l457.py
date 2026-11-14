"""Source text: LEDGER L457, "Give icon toggles (map toggles, ask-time-travel,
ocr-zoom-fit) a glyph swap, not just pressed fill" (owner B58: "clicking an icon
button to toggle smth doesn't change the icon's look so it is hard to tell if it
worked or not")."""

import re

from tests._app_js import frontend_text


def _near(name: str, anchor: str, span: int = 1600) -> str:
    js = frontend_text(name)
    i = js.index(anchor)
    return js[i : i + span]


def test_the_map_core_toggle_swaps_its_crown():
    body = _near("whiteboard-map.js", '["wb-map-core", data.core')
    assert "ph-crown" in body and "ph-crown-simple" in body


def test_the_map_line_toggles_swap_their_glyph():
    dash = _near("whiteboard-map.js", 'getElementById("wb-map-edge-dashed")')
    assert re.search(r'on \? "ph ph-rectangle-dashed" : "ph ph-line-segment"', dash)
    arrow = _near("whiteboard-map.js", 'getElementById("wb-map-edge-arrow")', 1600)
    assert re.search(r'on \? "ph ph-arrow-right" : "ph ph-minus"', arrow)


def test_ask_time_travel_swaps_to_a_calendar_while_open():
    body = _near("capture-ask.js", "function showAskAsOf(on)")
    assert re.search(r'on \? "ph ph-calendar-check" : "ph ph-clock-counter-clockwise"', body)


def test_ocr_fit_swaps_between_in_and_out():
    body = _near("library.js", "function ocrSyncZoomButtons()")
    assert re.search(r'ocrZoom === null \? "ph ph-arrows-in" : "ph ph-arrows-out"', body)
