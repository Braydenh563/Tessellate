"""Source text: in focus mode the document's side panels sit beside the page
from 600px wide, not over it (L403).

Measured at 599, 600, 700, 760, 819 and 820: before, at 760 and 819 the
sidebar and the suggestions panel spanned the window (10 to 750 at 760) over
the page; after, from 600 the sidebar is 10 to 250 (270 from 700) with the
page beside it, and the suggestions panel, 40vw below 820, leaves the page
281px at 600 and 420px at 819. Below 600 each is still the window's width
over the page. 600 and 820 are the breakpoint set (`test_breakpoints`).
"""

from __future__ import annotations

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_both_panels_give_up_room_from_600():
    assert "@media (min-width: 600px) {\n  #tab-documents.doc-focus:has(#doc-prose-panel:not(.hidden)) .doc-main {" in CSS
    assert "@media (min-width: 600px) {\n  #tab-documents.doc-focus.doc-focus-sidebar .doc-main {" in CSS
    assert "@media (max-width: 819.98px) {\n  #tab-documents.doc-focus {\n    --doc-focus-prose-w: min(var(--doc-prose-w), 40vw);" in CSS


def test_both_panels_span_the_window_only_below_600():
    assert "@media (max-width: 599.98px) {\n  #tab-documents.doc-focus #doc-prose-panel:not(.hidden) {" in CSS
    assert "@media (max-width: 599.98px) {\n  #tab-documents.doc-focus.doc-focus-sidebar .doc-sidebar {" in CSS
    assert "@media (max-width: 819.98px) {\n  #tab-documents.doc-focus #doc-prose-panel" not in CSS
