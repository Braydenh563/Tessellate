"""L-documents-26 / L342: what one typed key costs in a long document.

Measured before (doctype-style sweep, 20k-word document, 4x CPU, invalidation
tracking): every key read the whole 130,000-character text five times over in
the decorations that look for markers it does not hold (columns, four fence
languages, mermaid, suggestions), wrote the caret readout inside the key's own
frame (a status-bar layout and restyle on each key), and the outline pass after
a pause appended 1,176 rows one at a time to the live list, 2 `:has()`
invalidations a row.
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
