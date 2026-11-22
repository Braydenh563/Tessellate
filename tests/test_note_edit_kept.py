"""An edit left in the note form survives a reload (INBOX 648; found by the
e2e flow pass, tests-e2e/specs/notes.spec.js).

The Capture box kept its draft on this device and the note edit form did
not: the browser asked before a reload, and a Leave, or the desktop window
closing (which asks nothing), lost the edit for good. Now each change is kept
in localStorage until Save or Cancel, and the next start offers it back once.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
PANELS = JS / "note-edit-panels.js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def test_every_change_is_kept_and_save_or_cancel_forgets_it():
    source = PANELS.read_text(encoding="utf-8")
    keep = source[source.index("const keepDraft = () => {") :]
    keep = keep[: keep.index("\n  };")]
    assert "keepNoteEditLocally(noteFormDraft)" in keep
    save = source[source.index('toast("Note saved.");') - 300 : source.index('toast("Note saved.");')]
    assert "forgetNoteEditLocally()" in save
    assert "forgetNoteEditLocally()" in _function(source, "function closeNoteForm() {")
    # Opening another note's form drops the other note's kept edit.
    opener = _function((JS / "notes-list.js").read_text(encoding="utf-8"), "async function openNoteEditor(")
    assert "forgetNoteEditLocally" in opener
    # And the offer runs when the file arrives.
    assert "\nofferKeptNoteEdit();" in source


def _offer(kept: dict | None, note_content: str, api_error: str | None = None) -> dict:
    source = PANELS.read_text(encoding="utf-8")
    parts = [
        _function(source, "function keepNoteEditLocally(draft) {"),
        _function(source, "function forgetNoteEditLocally() {"),
        _function(source, "async function offerKeptNoteEdit() {"),
    ]
    script = (
        """
const NOTE_EDIT_KEPT = "note-edit-draft";
const store = {};
const prefs = {
  setJSON: (k, v) => { store[k] = JSON.stringify(v); },
  set: (k, v) => { store[k] = String(v); return true; },
  remove: (k) => { delete store[k]; },
  json: (k, fallback) => { try { const v = JSON.parse(store[k]); return v && typeof v === "object" ? v : fallback; } catch { return fallback; } },
};
let editingId = null; const appState = { get: () => editingId }; const setEditingNote = (id) => { editingId = id; };
const toasts = [];
function toastAction(message, label) { toasts.push([message, label]); }
const keptEdit = { awaitsUnlock: false };
async function apiJson() {
  if (API_ERROR) throw Object.assign(new Error("x"), JSON.parse(API_ERROR));
  return { id: 4, content: NOTE_CONTENT };
}
function withTitle(content, title) { return title ? `# ${title}\\n\\n${content}` : content; }
function clipText(t) { return t; }
function notePreviewText(t) { return t; }
"""
        + f"const NOTE_CONTENT = {json.dumps(note_content)};\n"
        + f"const API_ERROR = {json.dumps(api_error)};\n"
        + (f"store[NOTE_EDIT_KEPT] = {json.dumps(json.dumps(kept))};\n" if kept else "")
        + "\n".join(parts)
        + """
offerKeptNoteEdit().then(() => console.log(JSON.stringify({ toasts, kept: NOTE_EDIT_KEPT in store, waiting: keptEdit.awaitsUnlock })));
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_kept_edit_is_offered_back():
    out = _offer({"id": 4, "title": "Bike", "content": "the lock code is 2210"}, "# Bike\n\nthe lock code is 2201")
    assert out["toasts"] == [["Your unsaved changes to “Bike” were kept.", "Open them"]], out
    assert out["kept"] is True


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_kept_edit_already_saved_is_dropped_quietly():
    out = _offer({"id": 4, "title": "Bike", "content": "the lock code is 2210"}, "# Bike\n\nthe lock code is 2210")
    assert out == {"toasts": [], "kept": False, "waiting": False}, out


KEPT = {"id": 4, "title": "Bike", "content": "the lock code is 2210"}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_locked_server_keeps_the_edit_and_waits_for_the_unlock():
    # A restarted server answers 401 until sign-in; reading that as "the note
    # is gone" threw the kept edit away (tests-e2e/specs/draft-recovery.spec.js).
    out = _offer(KEPT, "x", api_error=json.dumps({"isLockout": True}))
    assert out == {"toasts": [], "kept": True, "waiting": True}, out


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_unreachable_server_keeps_the_edit_too():
    out = _offer(KEPT, "x", api_error=json.dumps({}))
    assert out == {"toasts": [], "kept": True, "waiting": False}, out


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_note_that_is_gone_lets_the_edit_go():
    out = _offer(KEPT, "x", api_error=json.dumps({"status": 404}))
    assert out == {"toasts": [], "kept": False, "waiting": False}, out
