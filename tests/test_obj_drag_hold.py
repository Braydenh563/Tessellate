"""Review 1031, finding 7: a drag arms only after a still hold of 250ms, or at
once from a grip, and never from a press inside selected text (obj-drag.js)."""

from __future__ import annotations

from tests._objmove_node import needs_node, run

FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js"]
STUBS = """
globalThis.Event = class { constructor(type) { this.type = type; } };
"""


@needs_node
def test_a_press_is_a_drag_only_after_a_still_hold() -> None:
    out = run(FILES, STUBS + """
    const g = { x0: 100, y0: 100, t0: 1000 };
    const move = (dx, dy, ms) => objDragVerdict(g, { clientX: 100 + dx, clientY: 100 + dy, timeStamp: 1000 + ms });
    __out({
      jitter: move(3, 0, 40),           // under 4px: still waiting, at any time
      slowSelect: move(5, 0, 150),      // moved before the hold completed: text selection
      fastSwipe: move(40, 0, 30),
      justShort: move(4, 0, 249),
      held: move(4, 0, 250),            // still hold, then a move
      heldFar: move(30, 12, 600),
    });
    """)
    assert out == {"jitter": "wait", "slowSelect": "swipe", "fastSwipe": "swipe", "justShort": "swipe", "held": "start", "heldFar": "start"}


@needs_node
def test_a_grip_arms_at_once_and_a_press_in_selected_text_never_arms() -> None:
    out = run(FILES, STUBS + """
    const grip = { closest: (sel) => (sel === OBJ_GRIP ? {} : null) };
    const plain = { closest: () => null };
    const down = (target) => ({ target, clientX: 100, clientY: 100, timeStamp: 1000 });
    const g = { x0: 100, y0: 100, t0: 1000, grip: true };
    const early = objDragVerdict(g, { clientX: 105, clientY: 100, timeStamp: 1010 });
    const box = { left: 90, right: 200, top: 90, bottom: 120 };
    const selection = (collapsed) => ({ isCollapsed: collapsed, rangeCount: 1, getRangeAt: () => ({ getClientRects: () => [box] }) });
    window.getSelection = () => selection(false);
    const inText = objPressInSelection({ clientX: 100, clientY: 100 });
    const beside = objPressInSelection({ clientX: 300, clientY: 100 });
    window.getSelection = () => selection(true);
    const collapsed = objPressInSelection({ clientX: 100, clientY: 100 });
    __out({ early, gripOn: objPressOnGrip(grip), gripOff: objPressOnGrip(plain), inText, beside, collapsed });
    """)
    assert out == {"early": "start", "gripOn": True, "gripOff": False, "inText": True, "beside": False, "collapsed": False}


@needs_node
def test_a_picture_is_grabbed_at_once_and_a_finger_lifts_after_its_hold() -> None:
    """INBOX 1470: a quick press-and-drag on a picture was the browser's own
    image drag; a finger on a card could not drag at all."""
    out = run(FILES, STUBS + """
    const card = { card: {}, ref: {} };
    OBJ_MODES.reorder = { grab: () => ({}) };
    window.getSelection = () => ({ isCollapsed: true, rangeCount: 0 });
    objCardAt = () => card;
    const down = (tagName, pointerType) => objDragSeed({ button: 0, pointerType, target: { tagName, closest: () => null }, clientX: 1, clientY: 1 });
    const g = { x0: 100, y0: 100, t0: 1000, grip: true, touch: true };
    __out({
      picture: down("IMG", "mouse").grip,
      words: down("SPAN", "mouse").grip,
      fingerOnPicture: down("IMG", "touch").grip,
      fingerSeeded: Boolean(down("SPAN", "touch")),
      fingerEarlyMove: objDragVerdict(g, { clientX: 130, clientY: 100, timeStamp: 1100 }),
      fingerJitter: objDragVerdict(g, { clientX: 108, clientY: 100, timeStamp: 1100 }),
    });
    """)
    assert out == {"picture": True, "words": False, "fingerOnPicture": False, "fingerSeeded": True, "fingerEarlyMove": "swipe", "fingerJitter": "wait"}
