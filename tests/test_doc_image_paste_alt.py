"""A picture pasted into a markdown document asks what it shows (audit 1028 D27).

The upload and insert were already there (settings-wiring.js), with the file's
own name as the alt text ("image.png"). This asks first, through the app's
prompt, and writes what was said. Real functions under node.
"""

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


def _run(said: str, steps: str = "") -> dict:
    source = DOCS.read_text(encoding="utf-8")
    body = "\n".join(_function(source, head) for head in ("async function docImagePasteAsk(", "async function docImageUpload("))
    script = (
        """
const box = { selectionStart: 3, selectionEnd: 3, value: "abc", setSelectionRange() {} };
const prompts = [], wrote = [];
async function promptDialog(message, initial, opts) { prompts.push([message, opts && opts.confirmLabel]); return SAID; }
function docSurface() { return box; }
function docUndoBreak() {}
function finishMarkdownEdit() { wrote.push(box.value); }
function authHeaders() { return {}; }
function toast() {}
async function apiJson() { return { url: "/media/x.png" }; }
globalThis.FormData = class { append() {} };
"""
        .replace("SAID", json.dumps(said))
        + body
        + """
(async () => {
  await docImagePasteAsk({ name: "image.png", type: "image/png" });
  console.log(JSON.stringify({ prompts, value: box.value }));
})();
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_the_words_typed_become_the_alt_text():
    got = _run("A chart of weekly sales")
    assert got["prompts"] == [["Describe this picture (optional)", "Add picture"]]
    assert got["value"] == "abc![A chart of weekly sales](/media/x.png)"


@needs_node
def test_an_empty_answer_still_adds_the_picture_with_the_default_alt():
    got = _run("")
    assert got["value"] == "abc![image](/media/x.png)"


def test_the_paste_is_taken_ahead_of_the_note_upload_only_inside_a_markdown_document():
    source = DOCS.read_text(encoding="utf-8")
    listener = source[source.index('window.addEventListener("paste"'):]
    listener = listener[: listener.index("}, true);")]
    assert "docCmView" in listener and "doc-content-code" in listener
    assert 'getData("text/plain")' in listener  # a copy with words in it is the words' paste
    assert "event.stopPropagation()" in listener
