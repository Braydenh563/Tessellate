"""DC10 (audit 1031 docs): one find UI. The hand-built find bar (`#doc-find-bar`
and its handlers) only ever showed for the textarea fallback; the editor's own
search panel is the find, so the bar, its handlers and its styles are gone."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
DOCS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")


def test_no_fallback_find_bar_markup_handlers_or_styles():
    for ident in ("doc-find-bar", "doc-find-input", "doc-find-count", "doc-replace-one", "doc-replace-all", "doc-find-help"):
        assert f'id="{ident}"' not in HTML, ident
    for name in ("docFindMatches", "docFindSelect", "docFindStep", "docReplaceOne", "docReplaceAll"):
        assert name not in DOCS, name
    css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend/css").glob("*.css"))
    assert ".doc-find-bar" not in css and ".doc-find-count" not in css


def test_the_toggle_reaches_the_editors_panel_or_the_page_find():
    start = DOCS.index("function toggleDocFindBar(")
    body = DOCS[start : DOCS.index("\n}\n", start)]
    assert "openSearchPanel" in body and "closeSearchPanel" in body
    assert "openGlobalFind()" in body, "with no engine the page find answers"
    assert re.search(r'id="doc-find-toggle"[^>]*', HTML), "the toolbar button stays"
    assert "aria-controls=\"doc-find-bar\"" not in HTML
