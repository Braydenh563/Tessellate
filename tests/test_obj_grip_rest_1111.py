"""The hover grip (obj-drag.js) pays its popup hit test once, for the card the pointer rests on (INBOX 1716 lag log).

At 4x CPU on a page of 30,000 nodes `document.elementsFromPoint` is 8 to 54 ms a call and was run for every
card a pointer crossed (`look` 535 to 684 ms over 24 moves). The grip also no longer joins the body: a node
added under `<body>` re-asks every `:has()` subject of the page.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "js" / "obj-drag.js").read_text(encoding="utf-8")


def _look() -> str:
    return JS.split("const look = () => {", 1)[1].split("//: Nor for a card that scrolled", 1)[0]


def test_a_card_gets_its_grip_after_the_pointer_rests_on_it() -> None:
    look = _look()
    # One `show(` call per look (test_open_note_lag_1667): both paths go through `showNext`.
    assert "const showNext = () => show(next);" in look
    assert "rested = setTimeout(showNext, OBJ_GRIP_REST_MS)" in look, "a new card waits for the rest"
    assert "if (next === card) return showNext()" in look, "the card already holding the grip is kept at once"
    assert re.search(r"const OBJ_GRIP_REST_MS = \d+;", JS)


def test_every_way_out_clears_the_pending_show() -> None:
    hide = JS.split("const hide = () => {", 1)[1].split("};", 1)[0]
    assert "clearTimeout(rested)" in hide
    show = JS.split("function show(next) {", 1)[1].split("const box =", 1)[0]
    assert "clearTimeout(rested)" in show and "!next.isConnected" in show, "a card gone in the wait is not shown"
    over_grip = JS.split("if (event.target === grip || grip?.contains(event.target)) {", 1)[1].split("}", 1)[0]
    assert "clearTimeout(rested)" in over_grip, "a pointer on the grip must not have it moved away"


def test_the_grip_joins_html_not_body() -> None:
    show = JS.split("function show(next) {", 1)[1].split("const box =", 1)[0]
    assert "document.documentElement.append(grip)" in show
    assert "document.body.append(grip)" not in JS
