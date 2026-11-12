"""The "/" menu's "Remind me about this" (DOCUMENTS_PLAN gap row 7).

Notion's `@date` mention makes a reminder; here the "/" menu in a document has
a row that opens the app's one reminder prompt (`remindAbout`, the same one a
document's Library menu uses) with the document as the target, so the reminder
lists "Open its document". Nothing new is drawn: the prompt, the presets and
the reminder route are the existing ones. Measured in the running app: see
CHANGELOG.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _editor() -> str:
    return (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")


def test_the_row_is_a_document_only_slash_item_that_reuses_the_reminder_prompt() -> None:
    src = _editor()
    start = src.index('id: "remind"')
    row = src[start : src.index("\n", start)]
    assert 'label: "Remind me about this"' in row
    assert 'ensureModule("library")' in row and "remindAbout(" in row and "documentId:" in row
    # inside the `if (inDocument)` block, not offered in a note
    before = src[: start]
    assert before.rindex("if (inDocument) {") > before.rindex("\n  }\n")


def test_the_prompt_is_the_librarys_own() -> None:
    lib = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert "async function remindAbout({ title, entryId = null, documentId = null })" in lib
    assert "documentId" in lib[lib.index("async function remindAbout(") :][:1200]
