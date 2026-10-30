"""A control folded into a dock's ⋯ menu keeps its own short word (audit 1028 S21).

Select is one of the notes dock's folded actions (`data-fold-narrow`). Its
word ("Select", class `dock-word`) is clipped below 1400px, so the fold added
the control's title as a second word: "Select several notes to move, tag, or
delete together". Nowrap, that phrase made the phone menu 452px wide at 390
(left 8, right -70: clipped), and the view segment's two buttons 202px square
(`aspect-ratio: 1` at the menu's width). Measured after: the menu is 256px
wide inside the window, Select 241x44, the view buttons 104x44, and the sort
select, view segment and notes-per-page select are all the same width (216px at
390, 338 at 1280).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHONE = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8"), flags=re.S)


def _fold() -> str:
    start = PHONE.index("function foldDockActions(")
    return PHONE[start : PHONE.index("\n}\n", start)]


def test_the_fold_reuses_a_controls_own_word_and_gives_it_back():
    body = _fold()
    assert 'querySelector(".dock-word")' in body
    assert 'classList.replace("dock-word", "dock-folded-word")' in body
    assert 'classList.replace("dock-folded-word", "dock-word")' in body, "unfolding restores the word"
    #: The title is the second word only for a control with no word of its own.
    assert body.index('querySelector(".dock-word")') < body.index("control.title")


def test_the_notes_sort_select_is_capped_only_in_the_row_not_in_the_menu():
    assert '[data-dock-name="notes"] .dock-arrange:not(.dock-arrange-folded) .select-shell' in CSS
    assert '[data-dock-name="notes"] .dock-arrange .select-shell' not in CSS
