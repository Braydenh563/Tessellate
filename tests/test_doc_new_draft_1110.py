"""A document started by typing, whose first save fails, keeps its words (audit 1028 D3, D36).

Typing into the blank editor makes the row on the first key (`ensureDocumentExists`).
Offline or on a 500 that POST said "Not saved" but kept nothing (a draft needs a
`currentDoc`), and every further key posted again. Now the words are kept on this
device under the id "new", retries wait out a pause, and the next open offers them back.
Runs the real functions under node.
"""

import json
import shutil
import subprocess

import pytest
from tests._app_js import documents_text

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def _run(steps: str) -> dict:
    source = documents_text()
    heads = (
        "function docKeptDrafts() {",
        "function keepDocEditLocally() {",
        "function forgetDocEditLocally(id) {",
        "function markDocDirty() {",
        "function offerKeptDocEdit(doc) {",
    )
    body = "\n".join(_function(source, h) for h in heads)
    script = (
        """
const DOC_EDIT_KEPT = "doc-edit-drafts", DOC_KEPT_MAX = 5, DOC_KEPT_DAYS = 14;
const store = {};
const prefs = {
  setJSON: (k, v) => { store[k] = JSON.stringify(v); },
  remove: (k) => { delete store[k]; },
  json: (k, f) => { try { return JSON.parse(store[k]) || f; } catch { return f; } },
};
let currentDoc = null, docDirty = false, docEditSeq = 0, docConflictPending = null, docSaveTimer = null;
let creatingDocument = null;
const docSaveQueue = { inFlight: null, again: null, newRetry: null, newOffered: false };
function startBlankDocument() {}
function docSurface() { return null; }
const docTypeState = { pending: null };
const els = { "doc-title": { value: "" }, "doc-saved": { textContent: "" }, "doc-status": { textContent: "", classList: { add() {} } } };
function $(id) { return els[id]; }
let text = "";
function docText() { return text; }
function scheduleDocFacts() {}
function docSetStatusText(n, t) { n.textContent = t; }
function saveDocument() {}
function toast() {}
const offers = [];
function toastAction(m, l) { offers.push([m, l]); }
function clipText(t) { return t; }
let posts = 0, failing = true;
function ensureDocumentExists() {
  posts += 1;
  if (failing) return Promise.reject(new Error("Failed to fetch"));
  currentDoc = { id: 7, content_hash: "h" };
  return Promise.resolve(currentDoc);
}
const tick = () => new Promise((r) => setTimeout(r, 0));
"""
        + body
        + "\n(async () => {\n"
        + steps
        + "\nconsole.log(JSON.stringify({ posts, status: els['doc-saved'].textContent, detail: els['doc-status'].textContent, kept: store[DOC_EDIT_KEPT] ? JSON.parse(store[DOC_EDIT_KEPT]) : null, offers }));\nclearTimeout(docSaveQueue.newRetry);\n})();\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_a_failed_first_save_says_not_saved_and_keeps_a_draft():
    got = _run('text = "My trip"; els["doc-title"].value = "Trip"; markDocDirty(); await tick(); await tick();')
    assert got["status"] == "Not saved"
    assert got["kept"]["new"]["content"] == "My trip"
    assert got["kept"]["new"]["title"] == "Trip"


@needs_node
def test_the_status_line_says_the_save_will_be_tried_again():
    """gap5-1111 (w4-1110): the 8 s retry was silent; the line now says so."""
    got = _run('text = "My trip"; markDocDirty(); await tick(); await tick();')
    assert got["detail"] == "Failed to fetch. It will try again in 8 seconds."


@needs_node
def test_keys_after_a_failed_first_save_do_not_post_again():
    got = _run(
        'text = "a"; markDocDirty(); await tick(); await tick();'
        ' text = "ab"; markDocDirty(); text = "abc"; markDocDirty(); await tick(); await tick();'
    )
    assert got["posts"] == 1
    assert got["kept"]["new"]["content"] == "abc"


@needs_node
def test_a_new_draft_is_kept_at_unload_before_any_post_and_offered_back():
    got = _run(
        'text = "typed"; keepDocEditLocally();'
        ' if (!store[DOC_EDIT_KEPT]) throw new Error("not kept"); offerKeptDocEdit(null);'
    )
    assert got["kept"]["new"]["content"] == "typed"
    assert got["offers"] and got["offers"][0][1] == "Put it back"


@needs_node
def test_nothing_is_kept_for_a_blank_new_page():
    got = _run('text = ""; keepDocEditLocally(); offerKeptDocEdit(null);')
    assert got["kept"] is None
    assert got["offers"] == []
