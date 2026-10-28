"""Document autosave runs one PUT at a time (audit 1028 D1, D2).

Two saves in flight both carried the old base_hash, so the second came back
409 and raised a false edit-conflict prompt; and a save that landed cleared
the dirty flag even when words were typed during the request, so closing
then lost them. These run the real saveDocument/docSaveOnce under node with
a PUT the test releases by hand.
"""

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


def _run(steps: str) -> dict:
    source = DOCS.read_text(encoding="utf-8")
    body = "\n".join(
        _function(source, head) for head in ("async function saveDocument(", "async function docSaveOnce(")
    )
    script = (
        """
let currentDoc = { id: 1, title: "T", content: "a", content_hash: "h0", file_type: "md" };
let docs = [currentDoc];
let docDirty = true, docEditSeq = 0, docConflictOpen = false, docSaveTimer = null;
let docSaveInFlight = null, docSaveAgain = null;
let text = "a";
const puts = [], pending = [], kept = [], forgot = [];
const el = { value: "T", textContent: "", classList: { add() {} } };
function $() { return el; }
function docText() { return text; }
function docNextName() { return "Untitled document 1"; }
function docSetStatusText(node, t) { node.textContent = t; }
function toast() {}
function docRunAfterSave() {}
function renderDocList() {}
function keepDocEditLocally() { kept.push(text); }
function forgetDocEditLocally(id) { forgot.push(id); }
function isEditConflict() { return false; }
function apiJson(url, opts) {
  const sent = JSON.parse(opts.body);
  puts.push(sent);
  return new Promise((resolve) => pending.push(() => {
    const n = puts.length;
    resolve({ ...currentDoc, content: sent.content, content_hash: "h" + n });
  }));
}
const tick = () => new Promise((r) => setTimeout(r, 0));
"""
        + body
        + "\n(async () => {\n"
        + steps
        + "\nconsole.log(JSON.stringify({ puts, docDirty, kept, forgot, status: el.textContent }));\n})();\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@needs_node
def test_a_second_save_waits_and_sends_the_new_hash():
    got = _run(
        """
const first = saveDocument({ silent: true });
await tick();
text = "ab"; docEditSeq += 1;
const second = saveDocument({ silent: true });
await tick();
if (puts.length !== 1) throw new Error("second PUT sent while the first was in flight");
pending.shift()();
await tick(); await tick();
pending.shift()();
await Promise.all([first, second]);
"""
    )
    assert [p["base_hash"] for p in got["puts"]] == ["h0", "h1"]
    assert got["puts"][1]["content"] == "ab"
    assert got["docDirty"] is False
    assert got["status"] == "Saved"


@needs_node
def test_words_typed_during_a_save_keep_the_document_dirty():
    got = _run(
        """
const first = saveDocument({ silent: true });
await tick();
text = "abc"; docEditSeq += 1;
pending.shift()();
await first;
"""
    )
    assert got["docDirty"] is True
    assert got["kept"] == ["abc"]
    assert got["forgot"] == []
    assert got["status"] == "Unsaved…"
