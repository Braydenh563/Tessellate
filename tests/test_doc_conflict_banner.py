"""An autosave's edit conflict is a status line, not a dialog (audit 1028 D9).

The real saveDocument, docSaveOnce and docResolveConflict run under node with a
server that answers 409 until told otherwise. The modal stole the focus in the
middle of a sentence; now only a save asked for by hand (or Resolve) opens it.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def _run(steps: str) -> dict:
    source = frontend_text("documents.js")
    body = "\n".join(
        _function(source, head)
        for head in ("async function saveDocument(", "async function docSaveOnce(", "async function docResolveConflict(")
    )
    script = (
        """
let currentDoc = { id: 1, title: "T", content: "a", content_hash: "h0", threads_hash: "p0", file_type: "md" };
let docs = [currentDoc];
let docDirty = true, docEditSeq = 0, docConflictOpen = false, docSaveTimer = null, docConflictPending = null;
const docSaveQueue = { inFlight: null, again: null };
const docsMadeThisSession = new Set(); // documents.js state docSaveOnce reads since audit 1028 U38
function renderDocComments() {} // the comments panel (documents-comments.js): what a save sends beside the text
const reloads = [], sentThreads = [{ id: "t1" }];
renderDocComments.threads = () => sentThreads;
renderDocComments.reload = () => { reloads.push(1); };
const surface = { text: "" };
function docSurface() { return surface; }
function renderDocPreview() {}
let text = "mine", conflict = true;
const puts = [], prompts = [], kept = [];
const saved = { textContent: "", children: [], append(n) { this.children.push(n); } };
const el = { value: "T", textContent: "", classList: { add() {} } };
function $(id) { return id === "doc-saved" ? saved : el; }
function docText() { return text; }
function docNextName() { return "Untitled document 1"; }
function docFillBlankTitle() { return false; }
let docSaveFailedSaid = false;
function docSetStatusText(node, t) { node.textContent = t; }
function toast() {}
function docRunAfterSave() {}
function renderDocList() {}
function keepDocEditLocally() { kept.push(text); }
function forgetDocEditLocally() {}
function isEditConflict(e) { return e && e.conflict; }
function smallButton(label, title, onClick) { return { label, onClick }; }
let answer = null;
function editConflictPrompt(o) { prompts.push(o); return Promise.resolve(answer); }
async function apiJson(url, opts) {
  const sent = JSON.parse(opts.body);
  puts.push(sent);
  if (conflict) { const e = new Error("conflict"); e.conflict = true; e.detail = { current: { id: 1, content: "theirs", content_hash: "h9", threads_hash: "p9", title: "T" } }; throw e; }
  return { ...currentDoc, content: sent.content, content_hash: "h10" };
}
const tick = () => new Promise((r) => setTimeout(r, 0));
"""
        + body
        + "\n(async () => {\n"
        + steps
        + "\nconsole.log(JSON.stringify({ puts: puts.length, prompts: prompts.length, pending: !!docConflictPending, status: saved.textContent, buttons: saved.children.map((c) => c.label), kept: kept.length, dirty: docDirty }));\n})();\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_an_autosave_conflict_opens_no_dialog_and_offers_resolve():
    got = _run("await saveDocument({ silent: true });")
    assert got["prompts"] == 0
    assert got["pending"] is True
    assert got["status"].startswith("Changed in another window")
    assert got["buttons"] == ["Resolve"]
    assert got["kept"] == 1  # the draft is safe on this device while it waits


@needs_node
def test_autosave_stays_quiet_while_the_conflict_waits():
    got = _run("await saveDocument({ silent: true }); await saveDocument({ silent: true }); await saveDocument({ silent: true });")
    assert got["puts"] == 1 and got["prompts"] == 0


@needs_node
def test_a_save_asked_for_by_hand_opens_the_dialog():
    got = _run("await saveDocument({ silent: true }); await saveDocument({ silent: false });")
    assert got["prompts"] == 1 and got["pending"] is False


@needs_node
def test_resolve_keep_mine_saves_with_the_other_windows_hash():
    got = _run(
        """
await saveDocument({ silent: true });
answer = "mine"; conflict = false;
await saveDocument({ silent: false });
if (puts[puts.length - 1].base_hash !== "h9") throw new Error("base_hash " + puts[puts.length - 1].base_hash);
"""
    )
    assert got["prompts"] == 1 and got["pending"] is False and got["dirty"] is False


@needs_node
def test_a_save_sends_the_panels_threads_and_the_threads_hash_it_started_from():
    got = _run(
        """
conflict = false;
await saveDocument({ silent: false });
const sent = puts[0];
if (JSON.stringify(sent.threads) !== JSON.stringify(sentThreads)) throw new Error("threads " + JSON.stringify(sent.threads));
if (sent.base_threads_hash !== "p0") throw new Error("base_threads_hash " + sent.base_threads_hash);
"""
    )
    assert got["puts"] == 1


@needs_node
def test_keep_mine_sends_the_other_windows_threads_hash_and_take_theirs_reloads_the_panel():
    mine = _run(
        """
await saveDocument({ silent: true });
answer = "mine"; conflict = false;
await saveDocument({ silent: false });
if (puts[puts.length - 1].base_threads_hash !== "p9") throw new Error("base_threads_hash " + puts[puts.length - 1].base_threads_hash);
if (reloads.length) throw new Error("keep mine must not reload the panel");
"""
    )
    assert mine["dirty"] is False
    theirs = _run(
        """
await saveDocument({ silent: true });
answer = "theirs";
await saveDocument({ silent: false });
if (reloads.length !== 1) throw new Error("reloads " + reloads.length);
if (currentDoc.threads_hash !== "p9") throw new Error("threads_hash " + currentDoc.threads_hash);
if (surface.text !== "theirs") throw new Error("text " + surface.text);
"""
    )
    assert theirs["dirty"] is False


@needs_node
def test_a_save_by_hand_with_no_conflict_still_goes_straight_through():
    got = _run("conflict = false; await saveDocument({ silent: false });")
    assert got["prompts"] == 0 and got["puts"] == 1


def test_leaving_a_conflicted_document_asks_and_typing_keeps_the_banner():
    source = frontend_text("documents.js")
    assert "saveDocument({ silent: !docConflictPending })" in _function(source, "async function openDocument(")
    assert "if (docConflictPending?.id === currentDoc.id) return;" in _function(source, "function markDocDirty(")
