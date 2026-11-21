"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Selection to a note (INBOX 1728): the owner asked to highlight a section of a document and turn it into,
or append it to, a new or existing note. Text-level checks (the suite cannot see the DOM); the Playwright run
measured the menu rows and the saved note."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROSE = (ROOT / "frontend/js/documents-prose.js").read_text(encoding="utf-8")
DOCUMENTS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")
EDITOR = (ROOT / "frontend/js/editor.js").read_text(encoding="utf-8")


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def test_the_two_rows_are_in_the_editor_menu():
    items = _fn(PROSE, "docSelectionNoteItems")
    assert "New note from selection" in items and "Add to note\\u2026" in items
    assert "docSelectionNoteItems(docSurface())" in _fn(PROSE, "docEditorMenuItems")
    assert "Object.assign(window, { docSelectionNoteItems, docSelectionNoteMenu })" in PROSE


def test_the_selection_bar_opens_the_same_rows_for_documents_only():
    assert "Selection to a note" in EDITOR and "docSelectionNoteMenu(textarea, button)" in EDITOR
    shown = _fn(EDITOR, "selectionBarShow")
    assert 'editorSurfaceKind(textarea) !== "document"' in shown and "[data-note]" in shown


def test_code_files_get_the_rows_only_over_a_selection():
    body = _fn(DOCUMENTS, "docEditorMenuAtPoint")
    assert "code && sel.empty" in body and "docSelectionNoteItems(surface)" in body


def test_new_note_links_back_and_is_one_undo_step():
    body = _fn(PROSE, "docSelectionToNote")
    assert '"/entries"' in body and "pushEntryCreateUndo(" in body
    assert "pickLibraryItemDialog(" in body and 'sources: ["note"]' in body
    assert 'method: "PUT"' in body and "pushUndo(" in body
    assert body.count('"Undo"') == 2, "both ends offer Undo on the notice"
    block = _fn(PROSE, "docSelectionNoteBlock")
    assert "From [[${title}]]" in block, "the back link is a wiki link the resolver reads"


def test_guide_topic_exists():
    from tests._help_text import help_chat_text, help_more_text

    assert "documents-to-note" in help_chat_text() + help_more_text()
