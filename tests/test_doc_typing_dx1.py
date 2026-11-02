"""Audit 1102 DX1: typing in a long, rich document keeps up on a slow CPU.

Measured before (scratchpad sweep p9b.js, a 3,120-line document of 60 rich
sections, 60 keys at 60 ms, 4x CPU): keydown-to-paint p50 1,738 ms and p95
2,473 ms here (the audit measured 7.0 s and 12.5 s), 69 long tasks summing
8.7 s. Per key the work is now the edit and what is on screen: the outline
waits for an edit that can change it, the facts and the prose pass wait for a
real pause that the next key withdraws, and a diagram is not drawn again
because a key moved it down the page.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str, indent: str = "") -> str:
    start = source.index(head)
    end = source.index(f"\n{indent}}}\n", start) + len(indent) + 3
    return source[start:end]


def _node(script: str) -> dict:
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def _facts_harness(body: str) -> str:
    fns = "\n".join(_function(DOCS, h) for h in ("function runDocFacts(", "function docFactsDelay(", "function scheduleDocFacts("))
    return (
        """
let docFactsTimer = null, docFactsStale = false, docFactsIdle = 0, docCmView = null;
const calls = [];
for (const n of ["Stats", "Outline", "Counts", "Comments", "Properties"]) globalThis["renderDoc" + n] = () => calls.push(n);
function $() { return { classList: { contains: () => false } }; }
const queue = [], options = [];
globalThis.requestIdleCallback = (fn, opts) => { options.push(opts); return queue.push(fn); };
globalThis.cancelIdleCallback = (id) => { queue[id - 1] = null; };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
"""
        + fns
        + body
    )


@needs_node
def test_a_key_withdraws_a_facts_pass_still_waiting_for_idle():
    got = _node(
        _facts_harness(
            """
(async () => {
  scheduleDocFacts();
  await wait(160);
  const waiting = queue.filter(Boolean).length;
  scheduleDocFacts();
  const afterKey = queue.filter(Boolean).length;
  await wait(160);
  for (const fn of queue) if (fn) fn();
  console.log(JSON.stringify({ waiting, afterKey, calls: calls.length, timeouts: options.filter((o) => o && o.timeout).length }));
})();
"""
        )
    )
    assert got["waiting"] == 1 and got["afterKey"] == 0
    assert got["calls"] == 5
    assert got["timeouts"] == 0, "an idle callback with a ceiling runs between two keys of one burst"


@needs_node
def test_the_pause_after_typing_skips_an_outline_no_edit_could_change():
    got = _node(
        _facts_harness(
            """
runDocFacts.outlineSame = true;
runDocFacts(true);
const typedSame = calls.slice();
calls.length = 0;
runDocFacts.outlineSame = false;
runDocFacts(true);
const typedChanged = calls.slice();
calls.length = 0;
runDocFacts.outlineSame = true;
runDocFacts();
console.log(JSON.stringify({ typedSame, typedChanged, direct: calls, reset: runDocFacts.outlineSame === undefined }));
"""
        )
    )
    assert "Outline" not in got["typedSame"] and len(got["typedSame"]) == 4
    assert "Outline" in got["typedChanged"]
    assert "Outline" in got["direct"], "an open, a restore or a view switch draws everything"
    assert got["reset"] is True


@needs_node
def test_the_pause_is_counted_in_the_typists_own_rhythm():
    got = _node(
        _facts_harness(
            """
const delays = [];
const realTimeout = setTimeout;
globalThis.setTimeout = (fn, ms) => { delays.push(ms); return 0; };
scheduleDocFacts();
scheduleDocFacts.gap = 160;
scheduleDocFacts();
scheduleDocFacts.gap = 5000;
scheduleDocFacts();
globalThis.setTimeout = realTimeout;
console.log(JSON.stringify({ delays }));
"""
        )
    )
    assert got["delays"] == [120, 240, 600]


_FAKE_DOC = """
function fakeDoc(text) {
  const lines = text.split("\\n");
  const starts = []; let at = 0;
  for (const l of lines) { starts.push(at); at += l.length + 1; }
  const line = (n) => ({ number: n, from: starts[n - 1], to: starts[n - 1] + lines[n - 1].length, text: lines[n - 1] });
  return {
    lines: lines.length, line,
    lineAt(pos) { let n = 1; while (n < lines.length && starts[n] <= pos) n++; return line(n); },
    sliceString: (a, b) => text.slice(a, b),
  };
}
function edit(before, from, to, insert) {
  const after = before.slice(0, from) + insert + before.slice(to);
  return {
    startState: { doc: fakeDoc(before) }, state: { doc: fakeDoc(after) },
    changes: { iterChanges(fn) { fn(from, to, from, from + insert.length, { lines: insert.split("\\n").length }); } },
  };
}
"""


@needs_node
def test_an_edit_is_outline_neutral_only_away_from_headings_fences_and_tasks():
    nested = _function(DOCS, "  function outlineNeutral() {", "  ")
    text = "# Title\\n\\nA paragraph here.\\n- [ ] task\\nSetext\\n---\\n```\\ncode\\n```\\n"
    got = _node(
        _FAKE_DOC
        + "const docFileType = () => ({ previewable: true });\n"
        + "const neutral = (update) => {\n"
        + nested
        + "\n  return outlineNeutral();\n};\n"
        + f"const T = \"{text}\";\n"
        + """
const at = (s) => T.indexOf(s);
console.log(JSON.stringify({
  paragraph: neutral(edit(T, at("here") , at("here"), "x")),
  heading: neutral(edit(T, at("Title"), at("Title"), "x")),
  task: neutral(edit(T, at("task"), at("task"), "x")),
  aboveUnderline: neutral(edit(T, at("Setext"), at("Setext"), "x")),
  insideFence: neutral(edit(T, at("code"), at("code"), "x")),
  fence: neutral(edit(T, at("```\\ncode") + 3, at("```\\ncode") + 3, "js")),
  newline: neutral(edit(T, at("here"), at("here"), "\\n")),
  joinLines: neutral(edit(T, at("here.") + 5, at("here.") + 6, "")),
}));
"""
    )
    assert got["paragraph"] is True and got["insideFence"] is True
    assert not any(got[k] for k in ("heading", "task", "aboveUnderline", "fence", "newline", "joinLines")), got


def test_the_caret_spy_waits_for_a_line_change_and_reads_in_the_engines_measure():
    update = _function(DOCS, "function docCmUpdate(")
    assert "if (line !== docCmUpdate.spyLine)" in update
    assert "runDocFacts.outlineSame = runDocFacts.outlineSame !== false && outlineNeutral();" in update
    spy = _function(DOCS, "function scheduleDocOutlineSpy(")
    assert "docCmView.requestMeasure({ key: scheduleDocOutlineSpy, read: docWhereLine" in spy


def test_a_document_key_redraws_no_note_gutter():
    body = _function(DOCS, "function docSurfaceInput(")
    assert "if (!docCmView) renderDocGutter(docBoxEl());" in body
    assert "renderDocGutter();" not in body


def test_the_prose_pass_waits_for_idle_and_the_next_key_withdraws_it():
    body = _function(DOCS, "function docToolsOnInput(")
    assert "cancelIdleCallback(docToolsOnInput.idle)" in body
    assert "requestIdleCallback(check)" in body
    assert "Math.max(DOC_PROSE_DEBOUNCE_MS, Math.min(600, 1.5 * docToolsOnInput.gap))" in body
    ask = _function(PROSE, "function docGrammarRequest(")
    assert "(docProse.typedAt || 0) > asked" in ask and "if (!typed) renderDocProse(true);" in ask


def test_the_suggestion_chip_is_not_rebuilt_by_a_key_that_changes_nothing():
    body = _function(PROSE, "function renderDocSuggestState(")
    assert "if (typed === true && key === renderDocSuggestState.key) return;" in body
    assert "renderDocSuggestState(true);" in PROSE


def test_a_diagram_moved_by_a_key_is_the_same_diagram():
    eq = re.search(r"class DocMermaidWidget[\s\S]*?eq\(other\) \{\s*return ([^;]+);", MERMAID)
    assert eq and eq.group(1) == "other.source === this.source"
    assert "view.posAtDOM(figure) + 4" in MERMAID
    assert "blocksOf.get(state.doc)" in MERMAID


def test_a_key_does_not_rewrite_the_root_class():
    """`classList.remove` writes the attribute even when the class is absent:
    every key woke the observers of `<html>` (measured 60 class records in 60
    keys, 13 diagram theme redraws); now 0."""
    avatars = (JS / "avatars.js").read_text(encoding="utf-8")
    assert 'if (root.classList.contains("is-idle")) root.classList.remove("is-idle");' in avatars
    assert 'document.documentElement.classList.remove("is-idle");' not in avatars


def test_the_caret_readout_is_drawn_once_per_key_in_the_engine():
    listener = DOCS.split('docListen("selectionchange", () => {', 1)[1].split("\n});", 1)[0]
    assert "if (docEventFromCm(document.activeElement)) return;" in listener
    update = _function(DOCS, "function docCmUpdate(")
    assert "if (!update.docChanged) renderDocCaret();" in update
