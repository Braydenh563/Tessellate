"""L-world-class-8: the Library's Contents groups notes by their note type (Meeting, Book, your own)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(signature: str) -> str:
    start = LIBRARY.index(signature)
    return LIBRARY[start : LIBRARY.index("\n}\n", start)]


def test_by_type_is_a_group_by_choice_everywhere_the_modes_are_listed():
    assert re.search(r'const CONTENTS_GROUPS = \[[^\]]*"type"', LIBRARY)
    select = re.search(r'<select id="contents-group"[^>]*>(.*?)</select>', INDEX, re.S).group(1)
    assert '<option value="type">By type</option>' in select
    assert "type: new Set()" in LIBRARY[LIBRARY.index("const contentsCollapsed") :][:300]


def test_notes_group_under_their_note_type_and_untyped_ones_come_last():
    groups = _body("function contentsGroups(")
    assert 'contentsMode === "type"' in groups and "entry.note_type" in groups
    order = _body("function contentsOrderedKeys(")
    assert 'contentsMode === "type"' in order and '"No type"' in order


def test_the_group_wears_a_glyph_and_the_guide_names_the_mode():
    mark = _body("function contentsGroupMark(")
    assert "ph-shapes" in mark
    from tessellate.ai import help_topics_more_mid as mid

    assert "By type" in repr(mid.__dict__)
