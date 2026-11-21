"""L-documents-26 / L342: what one typed key costs in a long document.

Measured before (doctype-style sweep, 20k-word document, 4x CPU, invalidation
tracking): every key read the whole 130,000-character text five times over in
the decorations that look for markers it does not hold (columns, four fence
languages, mermaid, suggestions), wrote the caret readout inside the key's own
frame (a status-bar layout and restyle on each key), and the outline pass after
a pause appended 1,176 rows one at a time to the live list (23.6 ms a pass;
16 ms through one fragment).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
DOCS = documents_text()
SURFACE = (JS / "documents-surface.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str, indent: str = "") -> str:
    start = source.index(head)
    end = source.index(f"\n{indent}}}\n", start) + len(indent) + 3
    return source[start:end]


def test_the_caret_readout_is_not_written_inside_a_typed_key():
    body = _function(DOCS, "function docToolsOnInput(", "")
    assert "docToolsOnInput.caret = setTimeout(renderDocCaret," in body
    assert "clearTimeout(docToolsOnInput.caret);" in body
    assert "\n  renderDocCaret();" not in body
    # A caret move with no edit still draws it at once.
    assert "if (!update.docChanged) renderDocCaret();" in _function(DOCS, "function docCmUpdate(", "")


def test_the_marker_decorations_ask_only_the_edited_lines():
    cols = (JS / "documents-columns.js").read_text(encoding="utf-8")
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    mermaid = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    prose = (JS / "documents-prose.js").read_text(encoding="utf-8")
    assert "docStr.lacks(state, /:::/, tr)" in cols and "build(tr.state, tr)" in cols
    assert "!docStr(state.doc).includes(\":::\")) return" in cols, "only the fallback reads the whole text"
    assert "window.docStr?.lacks?.(state, opener, tr)" in math and "build(tr.state, tr)" in math
    assert "docStr.lacks(state, /```[ \\t]*mermaid/, tr)" in mermaid and "build(tr.state, tr)" in mermaid
    assert "docStr.lacks(view.state, docSuggestParse.opener, update)" in prose
    assert "build(update.view, update)" in prose
    assert "!docStr.lacks(docCmView.state, docSuggestParse.opener)" in prose


def test_the_outline_rows_go_in_once():
    body = _function(DOCS, "function renderDocOutline(", "")
    assert "const rows = document.createDocumentFragment();" in body
    assert "rows.appendChild(li);" in body and "list.appendChild(li);" not in body
    assert body.count("list.appendChild(rows);") == 1


@needs_node
def test_lacks_carried_across_edits_matches_a_whole_text_scan():
    """A seeded run of 400 edits, many of them colons, backticks and braces next
    to each other and across line breaks: the carried answer equals a fresh scan
    of the whole text every time, and the whole text is read only for the first
    state."""
    start = SURFACE.index("  const docStrCache = new WeakMap();")
    end = SURFACE.index("  //: The document's text: the single most-read thing in this file.")
    lacks_src = SURFACE[start:end]
    script = f"""
const fs = require("fs"), vm = require("vm");
const ctx = {{ console }};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"))}, "utf8") + ";globalThis.CM6 = CM6;", ctx);
vm.runInContext({json.dumps(lacks_src)} + ";globalThis.docStr = docStr;", ctx);
const out = vm.runInContext(`(() => {{
  const patterns = [/:::/, /\\`\\`\\`[ \\\\t]*mermaid/, /\\\\{{\\\\+\\\\+|\\\\{{--/];
  let seed = 7;
  const rnd = (n) => {{ seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; }};
  const bits = [":", ":", "::", "\\\\n", "\\`", "\\`\\`\\`", " mermaid", "mermaid", "{{", "+", "-", "x", "word "];
  let state = CM6.state.EditorState.create({{ doc: "# Title\\\\n\\\\nsome words\\\\n" }});
  const toString = CM6.state.Text.prototype.toString;
  let wholeReads = 0, mayRead = 1;
  CM6.state.Text.prototype.toString = function () {{ wholeReads += 1; return toString.call(this); }};
  let wrong = 0, checks = 0;
  for (const p of patterns) docStr.lacks(state, p);
  for (let i = 0; i < 400; i += 1) {{
    const len = state.doc.length;
    const from = rnd(len + 1);
    const to = Math.min(len, from + (rnd(3) === 0 ? rnd(4) : 0));
    if (patterns.some((p) => p.test(state.doc.sliceString(0)))) mayRead += 1;
    const tr = state.update({{ changes: {{ from, to, insert: rnd(4) === 0 ? "" : bits[rnd(bits.length)] }} }});
    state = tr.state;
    const text = state.doc.sliceString(0);
    for (const p of patterns) {{
      checks += 1;
      if (docStr.lacks(state, p, tr) !== !p.test(text)) wrong += 1;
    }}
  }}
  return {{ wrong, checks, wholeReads, mayRead }};
}})()`, ctx);
console.log(JSON.stringify(out));
"""
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    got = json.loads(res.stdout)
    assert got["checks"] == 1200
    assert got["wrong"] == 0
    # The whole text is read only where the state before already held a match.
    assert got["wholeReads"] <= got["mayRead"] < 400, got


EDITOR = (JS / "editor.js").read_text(encoding="utf-8")

#: The scan as it was before the caret's line bounded it: the reference the
#: bounded one must agree with.
_TOKEN_AT_WHOLE_TEXT = """
function refTokenAt(textarea, trigger) {
  const upto = textarea.value.slice(0, textarea.selectionStart);
  const open = upto.lastIndexOf(trigger);
  if (open === -1) return null;
  const fragment = upto.slice(open + trigger.length);
  if (fragment.includes("\\n")) return null;
  if (trigger === "[[" && upto.slice(open).includes("]]")) return null;
  if (trigger === "/") {
    const before = open === 0 ? "\\n" : upto[open - 1];
    if (!/\\s/.test(before)) return null;
    if (/\\s/.test(fragment) && !editorTokenAt.phrase(textarea, fragment)) return null;
  }
  if (trigger === "```") {
    if (open > 0 && upto[open - 1] !== "\\n") return null;
    if (/\\s/.test(fragment)) return null;
  }
  return { start: open, fragment };
}
"""


def test_the_token_scan_reads_only_the_carets_line():
    body = _function(EDITOR, "function editorTokenAt(", "")
    assert "textarea.value.slice(0, textarea.selectionStart)" not in body
    assert 'lastIndexOf("\\n", caret - 1) + 1' in body
    # The engine's surface reads the caret's line from the document, never the joined text.
    assert "doc.lineAt(caret)" in body and body.index("doc.lineAt(caret)") < body.index("textarea.value")


@needs_node
def test_the_bounded_token_scan_matches_the_whole_text_scan():
    """The "/" menu, the `[[` picker and the fence finisher ask for the token
    before the caret on every typed key; a token never spans a line break, so
    the caret's line answers the same as the whole 130,000-character text. A
    seeded run of 3,000 texts and carets, three triggers each."""
    body = _function(EDITOR, "function editorTokenAt(", "")
    script = f"""
{body}
editorTokenAt.phrase = (t, fragment) => fragment.length % 2 === 0;
{_TOKEN_AT_WHOLE_TEXT}
let seed = 11;
const rnd = (n) => {{ seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; }};
const bits = ["/", "[[", "]]", "```", "\\n", " ", "a", "js", "x/y", "[", "]", "`"];
let wrong = 0, checks = 0, found = 0;
for (let i = 0; i < 3000; i += 1) {{
  let value = "";
  const n = 1 + rnd(12);
  for (let k = 0; k < n; k += 1) value += bits[rnd(bits.length)];
  const selectionStart = rnd(3) === 0 ? rnd(value.length + 1) : value.length;
  const textarea = {{ value, selectionStart }};
  //: The engine's surface: its value would join the text, so reading it is an error.
  const lineAt = (at) => {{
    const from = at > 0 ? value.lastIndexOf("\\n", at - 1) + 1 : 0;
    const end = value.indexOf("\\n", at);
    return {{ from, text: value.slice(from, end === -1 ? value.length : end) }};
  }};
  const engine = {{ get value() {{ throw new Error("joined the text"); }}, selectionStart, view: {{ state: {{ doc: {{ lineAt }} }} }} }};
  for (const trigger of ["/", "[[", "```"]) {{
    checks += 1;
    const b = JSON.stringify(refTokenAt(textarea, trigger));
    if (JSON.stringify(editorTokenAt(textarea, trigger)) !== b) wrong += 1;
    if (JSON.stringify(editorTokenAt(engine, trigger)) !== b) wrong += 1;
    if (b !== "null") found += 1;
  }}
}}
console.log(JSON.stringify({{ wrong, checks, found }}));
"""
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    got = json.loads(res.stdout)
    assert got["checks"] == 9000
    assert got["wrong"] == 0, got
    assert got["found"] > 300, got
