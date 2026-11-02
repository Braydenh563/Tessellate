"""A titled blank document swapped for a template is not left behind (audit 1028 U34).

New document, type a name, then pick a template: the empty document the first
keystroke made stayed in the list beside the template's. It is dropped now and
its title is the template document's name. Real functions under node.
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


def _run(steps: str) -> dict:
    source = DOCS.read_text(encoding="utf-8")
    body = "\n".join(
        _function(source, head)
        for head in ("function docIsUntouched(", "async function docDropIfUntouched(", "function docTemplateFill(", "async function createDocument(")
    )
    script = (
        """
let currentDoc = { id: 7, title: "Weekly plan" };
let docs = [currentDoc], text = "", titleValue = "Weekly plan", creatingDocument = null;
const docsMadeThisSession = new Set([7]);
const deleted = [], posted = [];
function $() { return { value: titleValue, focus() {}, select() {} }; }
function docText() { return text; }
const docNextName = () => "Untitled document";
function renderDocList() {}
function startBlankDocument() { throw new Error("not a blank start"); }
function loadCaptureDocuments() {}
async function loadDocuments() {}
function offerCreateUndo() {}
async function apiJson(url, opts) {
  if (opts.method === "DELETE") { deleted.push(url); return {}; }
  posted.push(JSON.parse(opts.body)); return { id: 8 };
}
"""
        + body
        + "\n(async () => {\n"
        + steps
        + "\nconsole.log(JSON.stringify({ deleted, posted }));\n})();\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


TEMPLATE = '{ id: "meeting", title: "Meeting notes", content: "# {{title}}\\n" }'


@needs_node
def test_the_empty_titled_document_is_dropped_and_its_title_carries_over():
    got = _run(f"await createDocument({TEMPLATE});")
    assert got["deleted"] == ["/documents/7"]
    assert got["posted"][0]["title"] == "Weekly plan"
    assert got["posted"][0]["content"].startswith("# Weekly plan")


@needs_node
def test_a_document_with_words_in_it_stays():
    got = _run(f'text = "some words";\nawait createDocument({TEMPLATE});')
    assert got["deleted"] == []
    assert got["posted"][0]["title"] == "Meeting notes"


@needs_node
def test_an_untitled_start_takes_the_templates_own_title():
    got = _run(f'titleValue = "";\nawait createDocument({TEMPLATE});')
    assert got["posted"][0]["title"] == "Meeting notes"
