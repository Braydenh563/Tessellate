"""INBOX 887 to 889 (the owner, on an iPhone in Safari): the keyboard covering the
chat input, the no-model notice, a pinch on the whiteboard that moved a note, and
the OCR workspace on a phone. Source ratchets; the measured numbers are in the
sweeps named in each docstring (`scratchpad/ui-sweeps/`)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"


def _read(rel: str) -> str:
    return (FRONT / rel).read_text(encoding="utf-8")


def test_viewport_meta_asks_for_resizes_content_as_an_addition():
    """Chrome on Android resizes the layout with the keyboard; Safari ignores it, so
    the visualViewport code stays the mechanism that serves the iPhone."""
    html = _read("index.html")
    meta = re.search(r'<meta name="viewport" content="([^"]*)"', html)
    assert meta
    assert "width=device-width" in meta.group(1)
    assert "interactive-widget=resizes-content" in meta.group(1)
    assert "visualViewport" in _read("js/phone-shell.js")


def test_keyboard_inset_is_reread_on_focus_and_ignores_pinch_zoom():
    """kbinset.js: a keyboard that arrives with no resize event left the inset at 0
    (input 706 against 508 visible); a 2x pinch zoom wrote 422px as a keyboard."""
    js = _read("js/phone-shell.js")
    body = js[js.index("function initKeyboardInset()"):js.index("initKeyboardInset();\n")]
    assert "focusin" in body and "focusout" in body
    assert "viewport.scale" in body
    assert 'classList.toggle("keyboard-open"' in body


def test_no_model_notice_steps_aside_for_the_keyboard_and_aligns_its_action():
    css = _read("css/03-dashboard-widgets.css")
    block = css[css.index("/* A phone: the words and the close"):]
    block = block[:block.index("/* The Ask tab's answer foot")]
    assert "html.keyboard-open .chat-dock .ai-offline-note" in block
    assert "grid-area: 1 / 3 / 3 / 4" in block
    assert "margin-inline-start" in block


# --- 888: a pinch on the whiteboard must not carry a note ----------------------

WB = (FRONT / "js" / "whiteboard.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def _slop(script: str) -> dict:
    body = (
        "const WB_TOUCH_SLOP = 8;\nconst WB_CLICK_SLOP = 3;\n"
        + _function(WB, "function wbTouchSlopStep(")
        + _function(WB, "function wbIsSecondTouch(")
        + script
    )
    result = subprocess.run(["node", "-e", body], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@needs_node
def test_a_touch_drag_waits_for_the_slop_then_carries_the_whole_distance():
    out = _slop(
        """
const touch = (dx, dy) => ({ dx, dy, sourceEvent: { type: "touchmove" } });
const mouse = (dx, dy) => ({ dx, dy, sourceEvent: { type: "mousemove" } });
const g = {};
const steps = [touch(2, 1), touch(3, 2), touch(3, 3), touch(1, 1)].map((e) => wbTouchSlopStep(g, e));
const mg = {};
console.log(JSON.stringify({
  steps,
  mouseInstant: [wbTouchSlopStep(mg, mouse(1, 0)), wbTouchSlopStep(mg, mouse(1, 1)), wbTouchSlopStep(mg, mouse(2, 0))],
  noGesture: wbTouchSlopStep(null, touch(1, 1)),
  zoomedShape: [wbTouchSlopStep({}, touch(5, 0), 0.5), wbTouchSlopStep({}, touch(20, 0), 0.5)],
}));
"""
    )
    # 2,1 and 5,3 are inside 8px; 8,6 (10px) crosses and releases the whole run so far; then live
    assert out["steps"][:2] == [None, None]
    assert out["steps"][2] == {"dx": 8, "dy": 6}
    assert out["steps"][3] == {"dx": 1, "dy": 1}
    # INBOX 1354: a mouse gets a 3px slop, so a click that slips 2px is a
    # click; past it the whole run so far is released, as a finger's is
    assert out["mouseInstant"] == [None, None, {"dx": 4, "dy": 1}], "a mouse waits 3px, then carries it all"
    assert out["noGesture"] == {"dx": 1, "dy": 1}
    # a shape measures in board units: 5 units at 0.5 scale is 2.5 screen px, 20 is 10
    assert out["zoomedShape"] == [None, {"dx": 20, "dy": 0}]


@needs_node
def test_only_a_two_finger_touch_start_is_a_second_touch():
    out = _slop(
        """
console.log(JSON.stringify([
  wbIsSecondTouch({ type: "touchstart", touches: [{}] }),
  wbIsSecondTouch({ type: "touchstart", touches: [{}, {}] }),
  wbIsSecondTouch({ type: "mousedown" }),
]));
"""
    )
    assert out == [False, True, False]


def test_every_item_drag_refuses_a_second_finger_and_a_second_finger_cancels_the_gesture():
    """wbpinch.js: before, a pinch from a note moved the note 12px and 61px and a text
    box 206px and 373px, and a pinch from the item itself never zoomed (scale 1 to 1)."""
    assert WB.count("wbIsSecondTouch(event)") >= 4, "card, shape, text box and grip drags"
    assert "wbTouchSlopStep(d._gesture, event" in WB
    for used in ("step.dx / transform.k", "d._dragRawDX += step.dx"):
        assert used in WB
    listener = WB[WB.index("let wbPinching = false;"):]
    listener = listener[: listener.index("const midPanClass")]
    assert "wbCancelGesture()" in listener
    assert "stopImmediatePropagation" in listener, "d3-drag's per-touch listeners would starve the zoom"


# --- 889: the OCR reading on a phone -------------------------------------------


def test_files_reading_actions_wrap_instead_of_running_off_the_row():
    """ocrphone.js at 390, Files tab with a reading open: Copy text and Open reading
    were told neither to wrap nor shrink, ran to x=427 and the library view scrolled
    50px sideways (scrollWidth 414 against 364). After: 364 against 364."""
    css = _read("css/library-lazy.css")
    rule = re.search(r"\n\.library-file-reading-actions \{(.*?)\n\}", css, re.S)
    assert rule
    body = rule.group(1)
    assert "flex-wrap: wrap" in body and "min-width: 0" in body
    assert "flex: 0 0 auto" not in body


def test_ocr_source_chip_ellipsises_on_a_phone():
    """Before: the chip's words wrapped to three lines inside a 32px box (scrollHeight
    43 in 32); the ellipsis has to sit on the text span of an inline flex chip."""
    css = _read("css/library-lazy.css")
    assert re.search(r"\.sheet-card-page \.ocr-source \{[^}]*white-space: nowrap", css)
    assert re.search(r"\.sheet-card-page \.ocr-source > \.ph-text \{[^}]*text-overflow: ellipsis", css)
