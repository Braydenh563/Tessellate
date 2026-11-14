"""Source text: at 390 under touch, a note row's menu and the document's Edit and Read reach 44px (L425).

Measured at 390x844 with touch emulation: every note row's "More actions" was
44x32 (drawn at the meta line's height on the owner's word) and Edit and Read
were 37x36 each. After: the menu keeps its 32px box and a 44px-tall ::after
answers the finger (a press 5px above or below it lands on it), and each half of
the pair is 44px across, the dock still one row at 360 and 390.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR


def test_the_note_rows_menu_answers_a_44px_finger():
    css = (CSS_DIR / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    after = re.search(r"#entry-list > li \.menu-wrap > button::after \{(.*?)\}", css, re.S)
    assert after, "the row menu's hit area is missing"
    assert "inset: calc((var(--control-h) - var(--target-min)) / 2) 0" in after.group(1)


def test_edit_and_read_are_44px_across_under_a_finger():
    css = (CSS_DIR / "library-lazy.css").read_text(encoding="utf-8")
    block = re.search(r"@media \(pointer: coarse\) \{\s*#tab-documents #doc-view-seg > button \{(.*?)\}", css, re.S)
    assert block and "min-width: var(--target-min)" in block.group(1)
