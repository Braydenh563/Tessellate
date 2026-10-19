"""The middle button pans the board from anywhere, and only the drag moves it.

The owner (2026-09-24, from the desktop window): the middle-button pan
"jerks repeatedly to the left side of the screen until i let go". Two causes,
both measured by `scratchpad/ui-sweeps/midpanwheel.js`:

- a pressed wheel still sends wheel events (a rocked wheel is a horizontal
  tilt, repeated while held), and the board's plain-wheel pan moved the board
  for each one on top of d3-zoom's drag: 3300 to 3600px sideways over a 300px
  drag, whichever way the hand went;
- the item drags wrote their own d3-drag filter, which replaces d3's default
  `!event.button` rather than adding to it, so a middle press on a topic or a
  card dragged the item and the board never panned (0px of 200).

The browser half is the sweep; this pins the two guards in the source so a
later edit cannot drop either without a failing test.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def test_the_plain_wheel_stands_aside_while_the_middle_button_is_down() -> None:
    start = SOURCE.index('container.node().addEventListener("wheel"')
    body = SOURCE[start : SOURCE.index("{ passive: false }", start)]
    guard = body.find("(e.buttons & 4) === 4 || wbMidPanHeld")
    assert guard != -1, "the plain-wheel pan must ignore wheel events while the middle button pans"
    assert guard < body.index("translateBy"), "the guard must run before the wheel moves the board"


def test_the_middle_press_flag_is_set_by_the_autoscroll_guard() -> None:
    assert "let wbMidPanHeld = false;" in SOURCE
    toggle = SOURCE[SOURCE.index("const midPanClass = (on) =>") :][:200]
    assert "wbMidPanHeld = on;" in toggle, "the press and its release must drive the flag the wheel reads"


@pytest.mark.parametrize(
    ("event", "want"),
    [
        ({"type": "wheel", "ctrlKey": True, "buttons": 0}, True),
        ({"type": "wheel", "ctrlKey": True, "buttons": 4}, False),
        ({"type": "wheel", "ctrlKey": False, "buttons": 0, "deltaMode": 1, "deltaX": 0}, True),  # a plain wheel zooms
        ({"type": "wheel", "ctrlKey": False, "buttons": 0, "deltaMode": 0, "deltaX": 3}, False),  # trackpad: pans
        ({"type": "wheel", "ctrlKey": True, "buttons": 0, "deltaMode": 0, "deltaX": 3}, True),  # pinch zooms
        ({"type": "wheel", "ctrlKey": False, "shiftKey": True, "buttons": 0}, False),  # shifted: the pan listener's
        ({"type": "mousedown", "button": 1, "buttons": 4}, True),
    ],
)
def test_the_zoom_filter_never_zooms_mid_pan(event: dict, want: bool) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    import json

    script = (
        "let wbSpaceHeld = false; let wbMidPanHeld = false;"
        " const wbBoardState = { wheel: { at: -1e9, pad: false } }; globalThis.window = { currentTool: 'select' };\n"
        + _function("wbTrackpadPan")
        + _function("wbZoomFilter")
        + f"\nconsole.log(JSON.stringify(Boolean(wbZoomFilter({json.dumps(event)}))));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) is want


def test_every_item_drag_takes_the_primary_button_only() -> None:
    """A d3-drag filter written here replaces d3's `!event.button`."""
    offenders = []
    for match in re.finditer(r"d3\.drag\(\)", SOURCE):
        chain = SOURCE[match.end() : match.end() + 4000]
        # The behaviour's own chain ends at its first `.on("start"`.
        chain = chain[: chain.find('.on("start"')] if '.on("start"' in chain else chain[:600]
        if ".filter(" not in chain:
            continue  # d3's default filter already refuses the middle button
        if "event.button" not in chain:
            line = SOURCE.count("\n", 0, match.start()) + 1
            offenders.append(line)
    assert offenders == [], f"d3.drag() filters without a button check at whiteboard.js lines {offenders}"


def test_the_right_button_pans_from_bare_canvas_and_a_drag_eats_its_menu() -> None:
    """C03: draw.io's right-drag pan. Browser half: `wbrightpan.js` (150px, menu closed;
    a plain right-click opens the app menu; a card press does not pan)."""
    body = _function("wbZoomFilter")
    assert 'event.button === 2) return wbIsBareCanvas(event.target)' in body
    assert "const WB_RIGHT_SLOP = 4;" in SOURCE
    handler = SOURCE[SOURCE.index('containerEl.addEventListener("contextmenu", (e) => {\n    //: A topic'):][:600]
    assert "wbRightOwns()" in handler, "the native menu must stand aside while a right press owns the gesture"


def _gesture(events: list[dict]) -> list[bool]:
    """Run wheel events through the filter in order; True where the board zooms."""
    import json

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "let wbSpaceHeld = false; let wbMidPanHeld = false;"
        " const wbBoardState = { wheel: { at: -1e9, pad: false } }; globalThis.window = { currentTool: 'select' };\n"
        + _function("wbTrackpadPan")
        + _function("wbZoomFilter")
        + f"\nconsole.log(JSON.stringify({json.dumps(events)}.map((e) => Boolean(wbZoomFilter(e)))));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _w(t: float, dy: float, dx: float = 0, **extra: object) -> dict:
    return {"type": "wheel", "timeStamp": t, "deltaX": dx, "deltaY": dy, "deltaMode": 0, "buttons": 0, **extra}


def test_a_two_finger_scroll_pans_even_when_a_frame_has_no_sideways_part() -> None:
    """INBOX 1327: vertical-only frames used to zoom, so the board could not decide."""
    frames = [_w(1000, 3, 1), _w(1016, 5), _w(1032, 12), _w(1048, 30), _w(1064, 2), _w(1080, 80)]
    assert _gesture(frames) == [False] * 6


def test_a_vertical_only_trackpad_scroll_pans_from_its_first_small_frame() -> None:
    assert _gesture([_w(500, 4), _w(516, 9), _w(532, 7.5)]) == [False] * 3


def test_a_pinch_zooms_and_a_mouse_wheel_zooms() -> None:
    pinch = [_w(0, 4, ctrlKey=True), _w(16, 6, ctrlKey=True)]
    assert _gesture(pinch) == [True, True]
    wheel = [_w(0, 100), _w(400, 100), _w(800, 100)]
    assert _gesture(wheel) == [True, True, True]


def test_the_next_gesture_starts_fresh_after_a_pause() -> None:
    frames = [_w(0, 3, 1), _w(16, 4), _w(1000, 100), _w(1100, 100)]
    assert _gesture(frames) == [False, False, True, True]


def test_a_selected_connectors_end_grip_wins_over_an_items_port() -> None:
    """INBOX 1328: pressing a connector's end grip, which sits on the very edge point the
    item's port is, drew a second arrow (sketches 1 -> 2, measured). Browser half: the press
    must reach the grip's own drag (1 -> 1, the end moves)."""
    start = SOURCE.index('containerEl.addEventListener("pointerdown", (e) => {\n    if (e.button !== 0 || e.pointerType === "touch" || window.currentTool !== "select" || !port.item')
    body = SOURCE[start : SOURCE.index("portTarget(x, y)", start)]
    assert ".wb-link-endpoint-handle" in body, "the port press must yield to a connector's end grip"


def test_frames_turn_and_a_click_on_a_panel_selects_it() -> None:
    """INBOX 1327. Browser half (measured): a tinted panel's body, a plain frame's edge and a
    panel's title select (object ids returned), a plain frame's body and bare board do not,
    and dragging a frame's rotate handle stored rotation 90."""
    assert 'if (d.kind === "table") return;\n    el.append("div")\n      .attr("class", "wb-rotate-handle")' in SOURCE
    assert "function wbSelectFrameAt(" in SOURCE
    assert "wbSelectFrameAt(...getLogicalMouse(e)" in SOURCE


@pytest.mark.parametrize(
    ("pref", "shift", "pans"),
    [("pan", False, True), ("pan", True, False), ("select", False, False), ("select", True, True)],
)
def test_left_drag_on_empty_canvas_pans_or_selects_by_preference(pref: str, shift: bool, pans: bool) -> None:
    """INBOX 1332: the default is Pan with Shift drawing the rectangle; the preference swaps
    them, one pair for boards and maps. Browser half (measured at 1440x900): pan, no shift moved
    the view 100,50 and drew no marquee; Shift drew it and moved 0; Select swapped both."""
    import json

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    event = {"type": "mousedown", "button": 0, "buttons": 1, "shiftKey": shift, "target": None}
    script = (
        "let wbSpaceHeld = false; let wbMidPanHeld = false;"
        f" const prefs = {{ get: () => {json.dumps(pref)} }};"
        " const wbBoardState = { wheel: { at: -1e9, pad: false } }; globalThis.window = { currentTool: 'select' };\n"
        + _function("wbLeftDragSelects")
        + "function wbIsBareCanvas() { return true; }\n"
        + _function("wbTrackpadPan")
        + _function("wbZoomFilter")
        + f"\nconsole.log(JSON.stringify(Boolean(wbZoomFilter({json.dumps(event)}))));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout.strip()) is pans


def test_the_marquee_starts_when_shift_disagrees_with_the_preference() -> None:
    assert "if (!place && e.shiftKey === wbLeftDragSelects()) return;" in SOURCE
    assert 'id="wb-drag-select"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
