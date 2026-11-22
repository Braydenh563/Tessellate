"""Source text: the word list's ARIA wiring is browser code with no runner here, so it is read as text.

Review 6008801452 (1): the word list is announced. Focus stays in the editor while Up and Down light a row, so the
lit row is the editor's `aria-activedescendant` (each row has a stable id), with `aria-controls` and `aria-expanded`;
closing the list clears it. Checked in the app (2026-11-22, an md document, "lorem"): `aria-activedescendant` names
`doc-complete-opt-0`, whose `aria-selected` is true, with `aria-expanded` true; after Escape it is gone and
`aria-expanded` is false."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "frontend" / "js" / "documents-prose-check.js").read_text(encoding="utf-8")


def _function(head: str) -> str:
    start = SRC.index(head)
    return SRC[start : SRC.index("\n  }\n", start) + 4]


def test_each_row_has_a_stable_id_and_the_editor_points_at_the_lit_one():
    render = _function("  function renderDocComplete(")
    assert "li.id = `doc-complete-opt-${index}`;" in render
    assert (
        "docCompleteAria(view ? view.contentDOM : box.el, `doc-complete-opt-${docCompleteIndex}`);"
        in render
    )
    aria = _function("  function docCompleteAria(")
    for attr in (
        "aria-activedescendant",
        'aria-controls", "doc-complete-list"',
        'aria-expanded", "true"',
    ):
        assert attr in aria, attr
    assert 'getAttribute("aria-activedescendant") === id) return;' in aria, (
        "a key that keeps the lit row writes nothing"
    )


def test_closing_the_list_clears_the_pointer():
    assert 'docCompleteAria(docCompleteAria.host, "");' in _function("  function hideDocComplete(")
    aria = _function("  function docCompleteAria(")
    assert aria.count('removeAttribute("aria-activedescendant")') == 2
