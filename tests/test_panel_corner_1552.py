"""INBOX 1552: a panel's corner resizes from the corner.

The card's rounded corner clips hit testing, so a press in the last pixels of
a corner landed on the backdrop and played its click, moving every edge. The
corner zone is 16px each way (inside the curve), and a backdrop press inside
a panel's box resizes from the edge it names, with the closing click eaten.
Driven by scratchpad/ui-sweeps/rim1536.js (all six cases ok).
"""
from tests._app_js import frontend_text

JS = frontend_text("panel-movable.js")


def _block(start: str) -> str:
    return JS.split(start, 1)[1].split("\n};\n", 1)[0]


def test_one_edge_reader_with_a_wider_corner() -> None:
    body = _block("panelAdopt.rimEdge = (r, x, y) => {")
    assert "a < 16 && b < 16" in body
    assert 'return corner || v + h;' in body
    assert "panelAdopt.rimEdge(st.rim, e.clientX, e.clientY)" in _block("panelAdopt.rimHover = (e) => {")


def test_a_backdrop_press_inside_the_box_resizes_and_eats_its_click() -> None:
    down = JS.split('document.addEventListener("pointerdown", (e) => {', 1)[1].split("}, true);", 1)[0]
    assert '!e.target.closest(".panel-movable-on")' in down
    assert "panelAdopt.rimEdge(r, e.clientX, e.clientY)" in down
    assert "panelGripDown(e, p);" in down
    assert 'document.addEventListener("click", eat, { capture: true, once: true });' in down
