"""Source text: the worker message shape is browser code with no runner here, so it is read as text.

Review 6008801452 (2): the worker sends a lint of a `DOC_GRAMMAR_SKIP_KINDS` kind as its span and kind only (L342,
`bare`), so nothing may read its message or suggestions. Every reader of `docGrammarAsk`'s lints goes through
`docGrammarFindings`, which drops those kinds before reading anything else, or through LanguageTool's merge, which
reads spans only. Run under node: a bare lint that throws on any other field is skipped without a throw."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")
WORKER = (JS / "harper-worker.js").read_text(encoding="utf-8")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_a_bare_lint_is_dropped_before_any_field_but_its_kind_is_read():
    script = (
        'const DOC_GRAMMAR_SKIP_KINDS = new Set(["Spelling"]);\n'
        "const docGrammarOutside = () => () => true, docProseSkipMask = () => [], docStructuralMask = () => [];\n"
        "const docGrammarKeeps = () => true, docGrammarMessage = (m) => String(m);\n"
        + _function(PROSE, "function docGrammarFindings(")
        + """
const text = "Teh dogs runs.";
const bare = new Proxy({ start: 0, end: 3, kind: "Spelling" }, { get(t, k) {
  if (!["start", "end", "kind"].includes(k)) throw new Error("read " + String(k)); return t[k]; } });
const full = { start: 4, end: 13, kind: "Agreement", message: "Use run.", suggestions: [{ kind: "Replace", text: "dogs run" }] };
console.log(JSON.stringify(docGrammarFindings([bare, full], text).map((f) => [f.harperKind, f.message, f.alternatives])));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [["Agreement", "Use run.", ["dogs run"]]]


def test_the_kind_is_the_first_thing_read_and_the_page_sends_exactly_its_skip_kinds():
    body = _function(PROSE, "function docGrammarFindings(")
    loop = body[body.index("for (const lint of lints || []) {") :]
    assert loop.split("\n")[1].strip() == "if (DOC_GRAMMAR_SKIP_KINDS.has(lint.kind)) continue;"
    assert "bare: [...DOC_GRAMMAR_SKIP_KINDS]" in PROSE
    assert (
        "bare.has(kept.kind) ? { start: kept.start, end: kept.end, kind: kept.kind } : kept"
        in WORKER
    )


def test_every_reader_of_the_asked_lints_goes_through_findings_or_the_span_only_merge():
    readers = {p.name: p.read_text(encoding="utf-8") for p in JS.glob("*.js")}
    callers = {
        name for name, text in readers.items() if re.search(r"(?<!function )docGrammarAsk\(", text)
    }
    assert callers == {"documents-prose.js", "whiteboard-map-more.js"}, callers
    merge = readers["documents-languagetool.js"]
    body = merge[
        merge.index("async function merge(") : merge.index("window.docSpell.languageTool = merge;")
    ]
    assert ".message" not in body and ".suggestions" not in body
