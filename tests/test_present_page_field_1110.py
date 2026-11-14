"""INBOX 1694 b3 (s9b-1110): the present bar's page number is typeable with a list of every page, on a board and a map.

Driven at 1440 and 390 on a three-frame board and a four-topic map (steps 3 and 4): type 3 and Enter goes to page 3, 99
clamps to the last, the picker lists "1. First", "2. Second", "3. Third" (a map: Root, Alpha, Beta, Gamma) and a pick goes
there. The one fault found was the phone's field, 37 x 28 beside 44 px buttons; it is the touch token (40 px at the default density) square now.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WB = frontend_text("whiteboard.js")
MAP = frontend_text("whiteboard-map.js")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_a_board_and_a_map_share_one_typeable_page_field_and_one_page_list() -> None:
    assert "wbPresent.pageField = valueField(host" in WB
    assert "onCommit: (n) => wbPresentShow(n - 1)" in WB
    assert 'kebabMenu(items, "Go to a page")' in WB
    assert "label: `${i + 1}. ${step.title()}`" in WB
    # A map's presentation goes through the same step walker, so it has the same field and list.
    assert "wbPresentShow(" in MAP


def test_the_phones_page_field_is_a_touch_height_target() -> None:
    phone = CSS[CSS.index("@media (max-width: 599.98px) {\n  .wb-present-bar {") :][:900]
    rule = phone[phone.index(".wb-present-bar .wb-present-page .value-field .value-field-input {") :]
    rule = rule[: rule.index("}")]
    assert "min-height: var(--control-h-touch)" in rule and "min-width: var(--control-h-touch)" in rule and "box-sizing: border-box" in rule
