"""B37 (INBOX 904): the wheel pressed down pans the graph, from the first move.

The owner: "Pressing down the scroll wheel and dragging sometimes glitches a
little initially when starting to drag."

The board already pans on the middle button and refuses the browser's
autoscroll (`tests/test_wb_middle_pan.py`). The graph did neither:
`scratchpad/ui-sweeps/pan1017-b37graph.js` measured a 93px middle drag moving
the camera 1.8px (a left drag of the same length moved it 91px), and the
press arrived with its default un-prevented, which on Windows starts the
page's autoscroll circle under the pointer: the glitch at the start of a
drag. The browser half is the sweep; this pins the two guards.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _wiring() -> str:
    start = SOURCE.index("function gcWireInteraction(")
    return SOURCE[start : SOURCE.index("\n}\n", start)]


def test_the_zoom_filter_lets_the_middle_button_pan() -> None:
    wiring = _wiring()
    start = wiring.index(".filter((event) => {")
    body = wiring[start : wiring.index(".on(\"start\"", start)]
    assert "event.button === 1" in body, "a middle press must reach the pan"
    assert body.index("event.button === 1") < body.index("gcNodeAtWorld"), "over a node too"


def test_a_middle_press_on_the_canvas_never_starts_autoscroll() -> None:
    wiring = _wiring()
    assert 's.canvas.addEventListener("mousedown", (event) => {' in wiring
    assert "event.button === 1" in wiring[wiring.index('s.canvas.addEventListener("mousedown"') :][:200]
    assert "event.preventDefault()" in wiring[wiring.index('s.canvas.addEventListener("mousedown"') :][:260]
    # The release is also a command on Linux (primary-selection paste).
    assert 's.canvas.addEventListener("auxclick"' in wiring
