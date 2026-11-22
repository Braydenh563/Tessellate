"""The editors' half of two windows, one note (WORLD_CLASS_PLAN 22.1 item 5).

The backend half, and why the check is on the text, is tests/test_edit_conflicts.py.
"""

from __future__ import annotations

from tests._app_js import app_js_text, documents_text


def test_the_editors_send_the_hash_they_started_from_and_ask_on_a_conflict():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    docs = documents_text()
    notes = (root / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    app = app_js_text()  # the whole boot code, not app.js alone (CLAUDE.md)
    assert "base_hash: currentDoc.content_hash" in docs
    assert "let base = entry.content_hash;" in notes and "base_hash: base" in notes
    # api() keeps the status and the structured detail on the error it throws.
    assert "error.status = response.status" in app and "error.detail = detail.detail" in app
    # One prompt, on the dialog recipe, for both editors.
    assert "function editConflictPrompt(" in app
    assert docs.count("editConflictPrompt(") >= 1 and notes.count("editConflictPrompt(") >= 1


def test_taking_their_document_takes_their_title_too():
    """Audit 1028 D10: "Take theirs" updated `currentDoc` but left the title
    box on the old text, so the next save sent the old title back."""

    docs = documents_text()
    start = docs.index("async function docResolveConflict(")
    theirs = docs[docs.index('answer === "theirs"', start): docs.index("\n}\n", start)]
    assert '$("doc-title").value = current.title' in theirs


def test_the_note_form_sends_only_the_fields_it_changed(client):
    """sm-1111 row 6: tags filed by the AI while the form was open were put back to the
    form's unchanged copy on Save. The form now sends tags and category only when the
    person changed them, and a PUT without them keeps what is there."""
    from pathlib import Path

    notes = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "note-edit-panels.js").read_text(encoding="utf-8")
    save = notes[notes.index("const before = { content: entry.content };"): notes.index("let base = entry.content_hash;")]
    assert "const after = { content: written };" in save
    assert "if (category !== entry.category)" in save and "!== (entry.tags || []).join(" in save
    made = client.post("/entries", json={"content": "form opened on this", "tags": ["old"]}).json()
    filed = client.put(f"/entries/{made['id']}", json={"tags": ["filed-by-ai"]})
    assert filed.status_code == 200
    saved = client.put(f"/entries/{made['id']}", json={"content": "typed in the form", "base_hash": made["content_hash"]})
    assert saved.status_code == 200 and saved.json()["tags"] == ["filed-by-ai"]
