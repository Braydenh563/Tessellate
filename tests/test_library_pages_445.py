"""INBOX 445 (1): the Bookmarks, Contents and AI skills sub-tabs.

The DOM is not visible to this suite, so these pin the shapes the measured
sweeps depend on (`scratchpad` drivers in the session notes): the ARIA tree on
Contents, every page of the bookmark list, Undo on both deletes, and the
skills kind segment. A failure here means one of those was rebuilt away.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
INDEX = index_html_text()


def test_contents_is_an_aria_tree():
    assert 'id="contents-outline" class="contents-outline" role="tree"' in INDEX
    for needle in ('"treeitem"', '"aria-level"', '"group"', "contentsTreeKeys", "ArrowRight", "ArrowLeft"):
        assert needle in LIBRARY, needle
    # Exactly one door into the tab order, roving from there.
    assert 'tabindex", "0"' in LIBRARY


def test_contents_has_expand_and_collapse_all():
    assert 'id="contents-expand"' in INDEX and 'id="contents-collapse"' in INDEX
    assert "contentsSetAll(true)" in LIBRARY and "contentsSetAll(false)" in LIBRARY


def test_contents_asks_for_document_headings():
    assert "/documents/outline" in LIBRARY


def test_bookmarks_ask_for_every_page():
    assert "fetchAllBookmarks" in LIBRARY
    assert 'apiJson("/bookmarks")' not in LIBRARY


def test_deletes_offer_undo():
    assert "deleteBookmarksWithUndo" in LIBRARY and "deleteSkillWithUndo" in LIBRARY
    assert LIBRARY.count("settleUndoFromToast") >= 2


def test_skills_page_has_a_kind_segment_and_a_sort():
    assert 'id="skills-kind"' in INDEX and 'id="skills-sort"' in INDEX
    assert "chip item-label skill-badge" in LIBRARY


def test_library_subtabs_have_no_width_floor():
    css = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
    block = css[css.index(".tabs-line > button {") :]
    block = block[: block.index("}")]
    assert "min-width: 6.5rem" not in block
