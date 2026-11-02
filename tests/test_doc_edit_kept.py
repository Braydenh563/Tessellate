"""Words typed in a document just before a reload survive it (INBOX 648;
found by the e2e flow pass, tests-e2e/specs/documents.spec.js).

A document saves itself 1.2 s after the typing stops. A Leave inside that
pause, a closed desktop window (which asks nothing), or a save the server
refused lost the newest words for good. Now the text is kept on this device
at that moment, the next save that lands drops it, and the next open of that
document offers it back once.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def test_kept_at_unload_and_on_a_refused_save_and_dropped_by_a_landed_one():
    source = DOCS.read_text(encoding="utf-8")
    assert 'window.addEventListener("pagehide", keepDocEditLocally);' in source
    # The save body moved into docSaveOnce when saves were serialised.
    save = _function(source, "async function docSaveOnce(")
    landed = save[save.index("currentDoc = saved;") : save.index('$("doc-saved").textContent = "Saved";')]
    assert "forgetDocEditLocally(saved.id)" in landed
    refused = save[save.index('$("doc-saved").textContent = "Not saved";') :]
    assert "keepDocEditLocally()" in refused[:200]
    assert "offerKeptDocEdit(doc);" in _function(source, "async function openDocument(id) {")


def _run(kept: dict | None, doc: dict, *, dirty: bool = True, extra: str = "") -> dict:
    source = DOCS.read_text(encoding="utf-8")
    parts = [
        _function(source, "function docKeptDrafts() {"),
        _function(source, "function keepDocEditLocally() {"),
        _function(source, "function forgetDocEditLocally(id) {"),
        _function(source, "function offerKeptDocEdit(doc) {"),
    ]
    script = (
        """
const DOC_EDIT_KEPT = "doc-edit-drafts";
const DOC_KEPT_MAX = 5;
const DOC_KEPT_DAYS = 14;
const store = {};
const prefs = {
  setJSON: (k, v) => { store[k] = JSON.stringify(v); },
  remove: (k) => { delete store[k]; },
  json: (k, fallback) => { try { const v = JSON.parse(store[k]); return v && typeof v === "object" ? v : fallback; } catch { return fallback; } },
};
const toasts = [];
function toastAction(message, label) { toasts.push([message, label]); }
function clipText(t) { return t; }
const title = { value: "Packing list" };
function $(id) { return title; }
function docText() { return "Passport. Charger."; }
"""
        + f"let currentDoc = {json.dumps(doc)};\nlet docDirty = {json.dumps(dirty)};\n"
        # Kept copies are one per document, stamped now unless the test says.
        + (f"const k = {json.dumps(kept)}; store[DOC_EDIT_KEPT] = JSON.stringify({{[k.id]: {{at: Date.now(), ...k}}}});\n" if kept else "")
        + "\n".join(parts)
        + """
const before = DOC_EDIT_KEPT in store;
offerKeptDocEdit(currentDoc);
keepDocEditLocally();
"""
        + extra
        + """
const all = store[DOC_EDIT_KEPT] ? JSON.parse(store[DOC_EDIT_KEPT]) : {};
console.log(JSON.stringify({ before, toasts, all, kept: all[currentDoc.id] || Object.values(all)[0] || null }));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@needs_node
def test_a_kept_copy_that_differs_is_offered_back():
    doc = {"id": 7, "title": "Packing list", "content": "Passport."}
    got = _run({"id": 7, "title": "Packing list", "content": "Passport. Charger."}, doc, dirty=False)
    assert got["toasts"] == [["Your unsaved changes to “Packing list” were kept.", "Put them back"]]


@needs_node
def test_a_kept_copy_already_saved_is_dropped_without_a_word():
    doc = {"id": 7, "title": "Packing list", "content": "Passport. Charger."}
    got = _run({"id": 7, "title": "Packing list", "content": "Passport. Charger."}, doc, dirty=False)
    assert got["toasts"] == []
    assert got["kept"] is None


@needs_node
def test_another_documents_copy_is_left_for_that_document():
    doc = {"id": 8, "title": "Other", "content": "x"}
    got = _run({"id": 7, "title": "Packing list", "content": "kept"}, doc, dirty=False)
    assert got["toasts"] == []
    assert got["kept"]["id"] == 7


@needs_node
def test_unload_with_unsaved_words_keeps_them():
    got = _run(None, {"id": 7, "title": "Packing list", "content": "Passport."}, dirty=True)
    assert got["kept"]["id"] == 7
    assert got["kept"]["content"] == "Passport. Charger."


@needs_node
def test_a_second_documents_unsaved_words_do_not_replace_the_first():
    """Audit 1028 D5: one slot per document, not one for all."""
    got = _run({"id": 7, "title": "Packing list", "content": "kept"}, {"id": 8, "title": "Other", "content": "x"})
    assert set(got["all"]) == {"7", "8"}
    assert got["all"]["7"]["content"] == "kept"


@needs_node
def test_a_kept_copy_older_than_two_weeks_is_not_offered():
    """Audit 1028 D4: kept text does not sit on the device for ever."""
    old = {"id": 7, "title": "Packing list", "content": "old words", "at": 1}
    got = _run(old, {"id": 7, "title": "Packing list", "content": "Passport."}, dirty=False)
    assert got["toasts"] == []
    assert got["all"] == {}
