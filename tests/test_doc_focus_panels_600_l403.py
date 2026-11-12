"""Source text: in focus mode the document's side panels sit beside the page
from 720px wide, not over it (L403).

Measured at 700, 720, 760, 819 and 820: before, at 760 and 819 the sidebar and
the suggestions panel spanned the window (10 to 750 at 760) over the page;
after, from 720 the sidebar is 10 to 270 with the page from 279, and the
suggestions panel leaves the page 321px at 720 and 420px at 819. Below 720
each panel is still the window's width over the page.
"""

from __future__ import annotations

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_both_panels_give_up_room_from_720():
    assert "@media (min-width: 720px) {\n  #tab-documents.doc-focus:has(#doc-prose-panel:not(.hidden)) .doc-main {" in CSS
    assert "@media (min-width: 720px) {\n  #tab-documents.doc-focus.doc-focus-sidebar .doc-main {" in CSS


def test_both_panels_span_the_window_only_below_720():
    assert "@media (max-width: 719.98px) {\n  #tab-documents.doc-focus #doc-prose-panel:not(.hidden) {" in CSS
    assert "@media (max-width: 719.98px) {\n  #tab-documents.doc-focus.doc-focus-sidebar .doc-sidebar {" in CSS
    assert "@media (max-width: 819.98px) {\n  #tab-documents.doc-focus #doc-prose-panel" not in CSS
