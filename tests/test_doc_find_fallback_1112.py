"""L341: the fallback find bar (no editor engine) keeps All documents and Replace in all."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _open_global_find() -> str:
    text = (JS / "wiring.js").read_text(encoding="utf-8")
    start = text.index("function openGlobalFind(")
    # The reach-outs' creation moved to documents-code.js (L624): only the Documents tab shows them.
    made = (JS / "documents-code.js").read_text(encoding="utf-8")
    return text[start : text.index("function closeGlobalFind", start)] + made[made.index("openGlobalFind.docsReach") :][:1400]


def test_the_fallback_bar_has_both_reach_outs_on_the_documents_tab_only():
    body = _open_global_find()
    assert 'className: "global-find-docs"' in body
    assert "docFindInDocuments(" in body and "openDocReplace({" in body
    assert 'name, textContent: label' in body or '"all-documents"' in body
    assert 'classList.contains("hidden")' in body.split("reach.hidden", 1)[1].split("\n", 1)[0]


def test_the_page_does_not_carry_them():
    assert "global-find-docs" not in (JS.parent / "index.html").read_text(encoding="utf-8")
