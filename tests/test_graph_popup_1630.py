"""INBOX 1630, the graph's node popups: the hover card stays below the top bar,
the detail panel scrolls its body only with the dock flush at its foot, an edge
resize names the edge at the press and is not fought by the placement, and a map
that keeps asking for its own next frame has an end.
Measured in the app by Playwright sweeps (one-offs, not kept; the numbers are in CHANGELOG)."""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_the_hover_card_stands_below_the_top_bar_and_flips_below_its_dot():
    body = _fn(frontend_text("js/graph-canvas.js"), "gcHoverCardFrame")
    assert 'document.getElementById("top-bar")' in body
    assert "const floor = Math.max(gap, seen + gap);" in body
    assert "if (top < floor) {" in body and "top = sy + r + gap;" in body
    assert "top = Math.max(floor, Math.min(top, s.dims.h - h - gap));" in body


def test_the_popup_room_names_the_floor_under_the_top_bar():
    graph = frontend_text("js/graph.js")
    room = _fn(graph, "graphPanelRoom")
    assert 'getElementById("top-bar")' in room and "floor" in room
    place = _fn(graph, "placeGraphPopup")
    assert "const { box, room, floor } = graphPanelRoom();" in place
    assert "graphPopupFollowSpot(box, room, size, floor)" in place


def test_the_detail_panel_scrolls_its_body_only():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    popup = html[html.index('<div id="graph-popup"') : html.index('<div id="graph-new"')]
    body = popup.index('<div class="graph-popup-body">')
    assert popup.index("graph-popup-head") < body < popup.index('id="graph-popup-content"')
    assert popup.index('id="graph-popup-tags"') < popup.index("</div>", popup.index('id="graph-popup-tags"')) < popup.index('id="graph-popup-saverow"')
    css = _css("graph-lazy.css")
    panel = css[css.index("#graph-popup {") :]
    panel = panel[: panel.index("}")]
    assert "display: flex;" in panel and "flex-direction: column;" in panel
    assert "overflow: hidden;" in panel and "padding-bottom: 0;" in panel
    scroller = css[css.index(".graph-popup-body {") :]
    scroller = scroller[: scroller.index("}")]
    assert "overflow-y: auto;" in scroller and "min-height: 0;" in scroller
    base = _css("04-chat-dock-appearance.css")
    dock = base[base.index(".graph-popup-actions {") :]
    dock = dock[: dock.index("}")]
    assert "position: sticky" not in dock and "margin-bottom: 0;" in dock


def test_the_grip_is_not_a_strip_under_the_dock():
    css = _css("graph-lazy.css")
    grip = css[css.index("#graph-popup > button.panel-grip {") :]
    assert "margin-top: calc(-1 * var(--target-min));" in grip[: grip.index("}")]
    assert "#graph-popup > .graph-popup-actions {" in css


def test_the_placement_waits_out_an_edge_resize():
    place = _fn(frontend_text("js/graph.js"), "placeGraphPopup")
    wait = place.index('popup.classList.contains("panel-moving")')
    assert wait < place.index("graphPanelRoom()") and "graphLate.sizing = true;" in place
    assert "graphLate.popupDragged = true;" in place[place.index("if (graphLate.sizing)") :]


def test_an_edge_is_named_again_at_the_press():
    pm = frontend_text("js/panel-movable.js")
    fresh = pm[pm.index("panelAdopt.rimFresh = ") : pm.index("function panelGripDown(")]
    assert "getBoundingClientRect()" in fresh and "panelAdopt.rimEdge(" in fresh
    pick = pm.index('let rim = e.target.closest(".panel-movable-on[data-rim]");')
    assert "if (rim && !panelAdopt.rimFresh(rim, e)) rim = null;" in pm[pick : pick + 200]


def test_the_corner_is_a_square_and_an_edge_is_the_rest():
    pm = frontend_text("js/panel-movable.js")
    edge = pm[pm.index("panelAdopt.rimEdge = ") : pm.index("panelAdopt.rimHover = ")]
    assert "(a < 16 && b < 16)" in edge
    assert re.search(r'const corner = .*\? "nw" : .*"ne" : .*"sw" : .*"se" : "";', edge)
    assert "return corner || v + h;" in edge


def test_a_self_requested_frame_has_an_end():
    draw = frontend_text("js/graph-canvas.js")
    assert "if (s.selfFrames === GC_SELF_FRAMES) {" in draw and "s.fadeSnap = true;" in draw
    step = _fn(draw, "gcFadeStep")
    assert "s.fadeSnap" in step and "s.hoverEase = 1;" in step
    tail = draw[draw.index("s.selfFrames = (s.selfFrames || 0) + 1;") :]
    assert tail.index("s.selfFrames > GC_SELF_FRAMES") < tail.index("gcRequestDraw(s, true)")
