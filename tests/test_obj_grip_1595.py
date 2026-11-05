"""INBOX 1595 (the owner: dragging is "hard"): two ways round the 250 ms hold.

1. A grip on each draggable card, shown on hover and keyboard focus, starts the
   drag at once. One floating element (`.obj-grip`, `data-obj-grip`) follows the
   card the pointer is over, so no card renderer changed; a press on it names
   the card through the element's `objCard`.
2. A press-and-move inside the hold makes a text selection (the failed try).
   A press on that selection used to be the browser's, so the retry did nothing;
   it now clears the selection and starts the hold, but only in the card the
   failed try began on (a selection made on purpose elsewhere is still left alone).

The real mouse drags are measured in `scratchpad/ui-sweeps/objgrip.js`."""

from __future__ import annotations

import re
from pathlib import Path

from tests._objmove_node import needs_node, run

ROOT = Path(__file__).resolve().parent.parent
FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js"]
STUBS = """
globalThis.Event = class { constructor(type) { this.type = type; } };
const cardEl = { classList: { add() {}, remove() {} } };
const other = { classList: { add() {}, remove() {} } };
OBJ_MODES.reorder = { grab: () => ({}) };
objCardAt = (target) => (target && target.inCard ? { card: target.inCard, ref: { kind: "note", id: 1, title: "t" } } : null);
let cleared = 0;
const box = { left: 90, right: 200, top: 90, bottom: 120 };
window.getSelection = () => ({ isCollapsed: false, rangeCount: 1, getRangeAt: () => ({ getClientRects: () => [box] }), removeAllRanges: () => { cleared += 1; } });
const press = (target) => ({ button: 0, pointerType: "mouse", clientX: 100, clientY: 100, target });
const words = (card) => ({ tagName: "P", inCard: card, closest: () => null });
"""


@needs_node
def test_a_press_on_the_grip_names_its_card_and_starts_at_once() -> None:
    out = run(FILES, STUBS + """
    const grip = { tagName: "SPAN", objCard: cardEl };
    const target = { tagName: "SPAN", closest: (sel) => (sel === OBJ_GRIP ? grip : null) };
    objCardAt = (t) => (t === cardEl ? { card: cardEl, ref: { kind: "note", id: 1, title: "t" } } : null);
    const seed = objDragSeed(press(target));
    __out({ card: seed.card === cardEl, grip: seed.grip, mode: seed.mode });
    """)
    assert out == {"card": True, "grip": True, "mode": "reorder"}


@needs_node
def test_a_press_in_words_selected_by_a_failed_try_clears_them_and_arms() -> None:
    out = run(FILES, STUBS + """
    const fail = (card) => {
      objDragNow = { id: 1, x0: 100, y0: 100, t0: 1000, card, mode: "reorder", touch: false, live: false };
      objDragMove({ pointerId: 1, clientX: 112, clientY: 100, timeStamp: 1100 });
    };
    //: A selection nobody failed a try on: the press stays the browser's.
    const untouched = objDragSeed(press(words(cardEl)));
    //: Press and move inside the hold on cardEl, then press the words again.
    fail(cardEl);
    const elsewhere = objDragSeed(press(words(other)));
    const retry = objDragSeed(press(words(cardEl)));
    const clearedByRetry = cleared;
    //: The failed try is spent: the next press in a selection is the browser's again.
    const again = objDragSeed(press(words(cardEl)));
    __out({ untouched, elsewhere, retry: Boolean(retry && retry.card === cardEl && !retry.grip), clearedByRetry, again });
    """)
    assert out == {"untouched": None, "elsewhere": None, "retry": True, "clearedByRetry": 1, "again": None}


@needs_node
def test_a_touch_scroll_is_not_a_failed_try() -> None:
    out = run(FILES, STUBS + """
    objDragNow = { id: 1, x0: 100, y0: 100, t0: 1000, card: cardEl, mode: "reorder", touch: true, live: false };
    objDragMove({ pointerId: 1, clientX: 140, clientY: 100, timeStamp: 1100 });
    __out(objDragSeed(press(words(cardEl))));
    """)
    assert out is None


def test_the_grip_is_one_floating_element_drawn_from_tokens() -> None:
    js = (ROOT / "frontend" / "js" / "obj-drag.js").read_text(encoding="utf-8")
    assert 'dataset.objGrip = ""' in js and "objCard" in js, "the grip carries data-obj-grip and its card"
    assert "focusin" in js and "pointerover" in js, "shown on hover and on keyboard focus"
    css = (ROOT / "frontend" / "css" / "objmove-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.obj-grip\s*\{([^}]*)\}", css, re.M)
    assert rule, "the .obj-grip rule is missing"
    body = rule.group(1)
    assert "position: fixed" in body and "cursor: grab" in body
    assert not re.search(r"\d+px", re.sub(r"1px", "", body)), "sizes are tokens, not pixels"
    assert "(hover: none)" in css and "display: none" in css.split("(hover: none)", 1)[1][:200], "a finger has its own hold"


def test_help_and_design_say_where_the_grip_is() -> None:
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "grip" in help_text.split('"id": "object-move"', 1)[1].split('"badge"', 1)[0]
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "A drag grip on a card" in design
