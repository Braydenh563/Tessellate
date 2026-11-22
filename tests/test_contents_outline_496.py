"""The Library's Contents is an outline: one tool row, groups that fold, rows of
a mark, a title and one line of facts (INBOX 496).

The owner: "the contents library subtab could be redesigned soooo much
better", with a screenshot of a filter, four grouping buttons, a scrolling
strip of category chips and sections of three-column note rows. Driven in
Chromium by the session's `contents496.js` (1440 and 390, light and dark);
this is the half the suite can see.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")


def _view() -> str:
    start = INDEX.index('<div id="library-view-contents"')
    return INDEX[start : INDEX.index("</section>", start)]


def _body(signature: str) -> str:
    start = LIBRARY.index(signature)
    return LIBRARY[start : LIBRARY.index("\n}\n", start)]


def test_one_tool_row_with_a_group_by_select() -> None:
    view = _view()
    assert 'id="contents-filter"' in view
    select = re.search(r'<select id="contents-group"[^>]*>(.*?)</select>', view, re.S)
    assert select, "the grouping is one select"
    values = re.findall(r'<option value="(\w+)"', select.group(1))
    assert values == ["category", "tag", "topic", "date", "folder", "type"]  # By type added (L-world-class-8)
    # The four-way segment and the sideways strip of jump chips are gone.
    assert 'class="seg"' not in view and "contents-mode" not in view
    assert "contents-jump" not in view and "contents-jump" not in LIBRARY


def test_the_choice_is_kept_and_read_safely() -> None:
    assert 'const CONTENTS_GROUP_KEY = "contents-group";' in LIBRARY
    start = LIBRARY.index("let contentsMode = (() => {")
    init = LIBRARY[start : LIBRARY.index("})();", start)]
    assert "try {" in init and "CONTENTS_GROUPS.includes(stored)" in init


def test_a_row_is_a_mark_a_title_and_one_line_of_facts() -> None:
    body = _body("function contentsRowBody(link, mark, title, facts)")
    assert 'metaLine(facts, "contents-meta")' in body
    assert "link.append(mark, body)" in body
    note = _body("function contentsNoteRow(entry)")
    assert "contentsNoteMark(entry)" in note and "contentsNoteFacts(entry)" in note
    mark = _body("function contentsNoteMark(entry)")
    assert 'thumb.loading = "lazy"' in mark and "replaceWith(contentsGlyph(" in mark


def test_a_group_heading_says_what_the_group_is() -> None:
    build = _body("function contentsBuildSection(outline, { key, label, total, fill })")
    assert "contentsGroupMark(key)" in build
    mark = _body("function contentsGroupMark(key)")
    assert "paintCategoryDot(dot, key)" in mark


def test_one_column_not_a_grid_of_rows() -> None:
    rule = re.search(r"\n\.contents-list \{(.*?)\n\}", CSS, re.S).group(1)
    assert "grid-template-columns" not in rule
    assert "flex-direction: column" in rule
    assert "text-transform: none" in re.search(r"\n\.contents-heading \{(.*?)\n\}", CSS, re.S).group(1)
