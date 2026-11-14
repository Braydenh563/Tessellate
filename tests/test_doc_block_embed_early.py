"""L-documents-74: a `![[Doc#^id]]` drawn before the document list lands redraws when it does.

Seen in a second window: docEmbedTarget resolves a block through `docs`, which is empty until the list loads,
so the widget stayed a chip. Runs documents-embeds.js in node against a stand-in page.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """
const calls = [];
const heard = [];
class El {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this.isConnected = true; this.className = ""; this.classList = { add() {} }; }
  append(...kids) { this.children.push(...kids); }
  replaceChildren(...kids) { this.children = kids; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
}
const document = { createElement: (t) => new El(t), addEventListener: (name, fn, opts) => { if (name === "docs-landed") heard.push({ name, fn, once: !!opts?.once }); } };
const window = {};
let docs = [];
const currentDoc = null;
const wikiLinkTarget = (n) => n;
const docBlockRefSplit = (n) => { const i = String(n).indexOf("#^"); return i < 0 ? { name: n, blockId: null } : { name: n.slice(0, i), blockId: n.slice(i + 2) }; };
const resolveWikiTarget = () => null;
const docBlockTextCache = new Map();
const docBlockFind = () => null;
const chipWords = () => {};
const docBlockDocumentText = () => null;
const apiJson = async (url) => { calls.push(url); return { content: "x ^abc123" }; };
"""


def _run(body: str) -> object:
    text = (JS / "documents-embeds.js").read_text(encoding="utf-8")
    script = HARNESS + text + "\n;(async () => {\n" + body + "\n})();\n"
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_an_early_block_embed_redraws_when_the_list_lands() -> None:
    got = _run(
        "const host = new El('div');"
        "window.docEmbedFill(host, 'Src#^abc123');"
        "const before = { calls: [...calls], waiting: heard.map((h) => [h.name, h.once]) };"
        "docs = [{ id: 3, title: 'Src' }];"
        "heard.forEach((h) => h.fn());"
        "await new Promise((r) => setTimeout(r, 20));"
        "console.log(JSON.stringify({ before, after: calls }));"
    )
    assert got["before"]["waiting"] == [["docs-landed", True]]
    assert "/documents/3" not in got["before"]["calls"]
    assert "/documents/3" in got["after"]


@node
def test_a_plain_missing_name_or_a_loaded_list_waits_for_nothing() -> None:
    got = _run(
        "const host = new El('div');"
        "window.docEmbedFill(host, 'nothing here', { keep: true });"
        "docs = [{ id: 3, title: 'Src' }];"
        "window.docEmbedFill(host, 'Other#^abc123', { keep: true });"
        "console.log(JSON.stringify(heard.map((h) => h.name)));"
    )
    assert got == []


def test_the_list_loader_announces_itself() -> None:
    text = (JS / "documents.js").read_text(encoding="utf-8")
    assert text.count('document.dispatchEvent(new Event("docs-landed"))') == 1
