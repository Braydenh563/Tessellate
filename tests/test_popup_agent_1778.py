"""INBOX 1778 (a) and (c): the popup Agent's footer is never cut, and the turn's
own steps card goes before the answer, not under it.

Measured in the running app (1440, 360, 720 wide; a 75-character note title and
a 56-character status): before, the status was 0px wide at every width, the
toggle's caption ellipsised (scrollWidth 578 against clientWidth 372), and Stop
was 4px short at 360. After, scrollWidth equals clientWidth on every item and
the plan card sits between the steps fold and the answer."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def _rules(selector: str) -> str:
    return "".join(m.group(0) for m in re.finditer(re.escape(selector) + r"[^{]*\{[^}]*\}", CSS))


def test_no_foot_item_ellipsises() -> None:
    for selector in ("#command-palette-use-note-text", "#command-palette-status"):
        body = _rules(f".command-palette-foot > {selector}") + _rules(f"> {selector}")
        assert "text-overflow" not in body and "white-space: nowrap" not in body, selector


def test_the_foot_wraps_and_the_buttons_keep_their_size() -> None:
    assert "flex-wrap: wrap;" in _rules(".command-palette-foot")
    buttons = _rules(".command-palette-foot > :is(#command-palette-stop, #command-palette-menu)")
    assert "flex: none;" in buttons and "white-space: nowrap;" in buttons


def test_the_plan_card_is_placed_before_an_empty_answer_box() -> None:
    js = (ROOT / "frontend" / "js" / "palette.js").read_text(encoding="utf-8")
    start = js.index("onPlan: (event) => {")
    body = js[start : js.index("onStep:", start)]
    assert "placeStep(card)" in body and 'classList.contains("step-plan")' in body
