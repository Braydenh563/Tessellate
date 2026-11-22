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

from tests._js_scope import unwrapped
from tests._app_js import documents_text

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
DOCS = documents_text()
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


# The three levers of the second pass (agent a29i): a key inside one paragraph
# patches the Live set instead of rebuilding the visible lines, a table is
# parsed from its own lines, and a fresh frame closure is known by its source.
ROOT = JS.parent.parent
CMJS = (JS / "documents-cm.js").read_text(encoding="utf-8")
_LOAD = f"""
const fs = require("fs"), vm = require("vm");
const read = (f) => fs.readFileSync({json.dumps(str(ROOT / "frontend"))} + "/" + f, "utf8");
const ctx = {{ console }};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(read("vendor/codemirror/codemirror.min.js") + ";globalThis.CM6 = CM6;", ctx);
vm.runInContext(read("js/documents-tables.js"), ctx);
"""


@needs_node
def test_a_table_parsed_from_its_own_lines_is_the_whole_text_parse():
    text = (
        "Prose with a | pipe\n| Name | Notes |\n| --- | --- |\n| One | Two |\n\nMore prose\n\n"
        "  | a | b |   \n  | --- | :---: |\n  | 1 | 2 |  \n| x | y |\n|---|---|\n| 3 | 4 |\n\n"
        "Name | Notes\n--- | ---\nOne | Two\n| no | delimiter |\n| at | all |\n"
    )
    got = _node(
        _LOAD
        + f"const T = {json.dumps(text)};\n"
        + """
const out = vm.runInContext(`(() => {
  const doc = CM6.state.Text.of(T.split("\\\\n"));
  let tables = 0, diff = [];
  for (let at = 0; at <= T.length; at += 1) {
    const whole = JSON.stringify(docTableParse(T, at));
    if (whole !== "null") tables += 1;
    if (JSON.stringify(docTableParse.at(doc, at)) !== whole) diff.push(at);
  }
  return { tables, diff };
})()`, Object.assign(ctx, { T }));
console.log(JSON.stringify(out));
"""
    )
    assert got["tables"] > 100 and got["diff"] == []
    assert "docTableParse.at(doc, line.from)" in CMJS and "docTableParse(source()" not in CMJS
    assert "docTableParse.at(doc, head)" in DOCS, "the grips plugin reads the caret's table the same way"


_STUBS = """
function docFenceGutterOn() { return false; }
function docStr(d) { return d.toString(); }
function mdTocEntries() { return []; }
function docCalloutFolded() { return false; }
function docMathLooksLikeMath() { return true; }
function mdDividerKind() { return null; }
function imageOptions(s) { return { name: s }; }
function mediaSrc(s) { return s; }
function wikiLinkTarget(n) { return n; }
function docImageLive() { return true; }
function docListGuides() { return []; }
function asSurface() { return null; }
function docSurface() { return null; }
const LIST_DEPTH_MAX = 6;
const docViewState = { tableFilter: { of: () => null, letters: () => "A" } };
const DOC_BLOCK_ID_AT_END = /(?:^|[ \\t])\\^([a-z0-9-]+)[ \\t]*$/;
"""

_PATCH_DOCS = [
    ("# Title\n\nIntro with **bold**, *em* and a [link](https://x.y) and $x$.\nSecond line of it %%a pin%% here.\n\n"
    "- one item\n- [ ] a task\n  - nested words\n1. first\n\n> [!note]- Kind\n> body words\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
    "After the table.\n\n```js\nconst a = 1;\n```\n\nLast paragraph ==mark== end.\n"),
    ("---\ntitle: x\n---\nfront para words\n\npara above table\n| a | b |\n|---|---|\n| 1 | 2 |\nafter table text\n\n"
    "before fence\n```\ncode\n```\nafter fence\n\nmath para\n$$\nx^2\n$$\nmore words\n\nA para\n===\n\n> quote para\n> more\n\n"
    "- item one\nlazy continuation\n- item two\n\n   indented para\n\n* a\n\n  b para in item\n"),
]


@needs_node
@pytest.mark.parametrize("text", _PATCH_DOCS, ids=["rich", "edges"])
def test_a_patched_live_set_is_the_set_a_full_rebuild_draws(text):
    """Keys typed and deleted at every few offsets: after each, the plugin's set
    (patched where `patchRegion` allows) equals a fresh plugin's on the new state."""
    helpers = "\n".join(_function(DOCS, h) for h in ("function docLiveSpanTouched(", "function docLiveRevealSame("))
    anchor = re.search(r"^docLiveSpanTouched\.anchorIn = .*$", DOCS, re.M).group(0)
    # The plugin reads the fence's language and title through docPairInput
    # (documents-prose.js, 5d37fc43e); the harness carries the real parser.
    fence = "function docPairInput() {}\n" + PROSE[PROSE.index("docPairInput.fenceParts = ") :].split("\n};\n")[0] + "\n};"
    helpers = fence + "\n" + _function((JS / "markdown.js").read_text(encoding="utf-8"), "function mdMathBlockFrom(") + "\n" + helpers
    got = _node(
        _LOAD
        + 'vm.runInContext(read("js/documents-props.js"), ctx);\n'
        + f"vm.runInContext({json.dumps(helpers + chr(10) + anchor + _STUBS)}, ctx);\n"
        + 'vm.runInContext(read("js/documents-cm.js"), ctx);\n'
        + f"ctx.DOC = {json.dumps(text)};\n"
        + """
const out = vm.runInContext(`(() => {
  const CM = CM6, P = docLivePlugin(CM);
  const md = CM.markdown.markdown({ base: CM.markdown.markdownLanguage });
  const dom = { closest: () => ({}), querySelector: () => null };
  const viewOf = (state) => ({ state, hasFocus: true, visibleRanges: [{ from: 0, to: state.doc.length }], viewport: { from: 0, to: state.doc.length }, dom, contentDOM: dom });
  const snap = (set) => { const o = []; for (const it = set.iter(); it.value; it.next()) o.push([it.from, it.to, it.value]); return o; };
  const same = (a, b) => a.length === b.length && a.every(([f, t, v]) => b.some(([f2, t2, v2]) => f2 === f && t2 === t && (v2 === v || v2.eq(v))));
  let state = CM.state.EditorState.create({ doc: DOC, extensions: [md] });
  const inst = P.create(viewOf(state));
  let patched = 0, bad = [];
  const pt = inst.patch;
  inst.patch = function (u) { const r = pt.call(this, u); if (r) patched += 1; return r; };
  for (let pos = 0; pos <= DOC.length; pos += 4) {
    state = CM.state.EditorState.create({ doc: DOC, extensions: [md], selection: { anchor: pos } });
    inst.rebuild(viewOf(state));
    let at = pos;
    for (const k of ["x", " ", "*", "y", "*", "|", "$", "=", "[", "]", "%", "#", "-", "\\\\n", "", "", "", ""]) {
      if (!k && !at) continue;
      const tr = k ? state.update({ changes: { from: at, insert: k }, selection: { anchor: at + k.length } })
        : state.update({ changes: { from: at - 1, to: at }, selection: { anchor: at - 1 } });
      at = tr.state.selection.main.head;
      inst.update({ startState: state, state: tr.state, changes: tr.changes, transactions: [tr], docChanged: true, selectionSet: true, viewportChanged: true, focusChanged: false, view: viewOf(tr.state) });
      state = tr.state;
      if (!same(snap(inst.decorations), snap(P.create(viewOf(state)).decorations))) bad.push(pos + ":" + JSON.stringify(k));
    }
  }
  return { patched, bad: bad.slice(0, 5) };
})()`, ctx);
console.log(JSON.stringify(out));
"""
    )
    assert got["bad"] == [], got
    assert got["patched"] > 100, "most keys inside a paragraph take the patch"


def test_a_widget_moved_by_a_key_reads_its_place_when_pressed():
    """A patched set keeps the widgets below a key as they were built, so none
    may act on a position it was built with: the pin and the callout's buttons
    ask the view (the task box already did)."""
    comment = CMJS.split("class DocCommentWidget", 1)[1].split("\n  }\n", 1)[0]
    assert "return other.body === this.body;" in comment
    assert "docShowComment(view ? view.posAtDOM(pin) : this.at)" in comment
    callout = CMJS.split("class DocCalloutWidget", 1)[1].split("\n  }\n", 1)[0]
    assert "other.at" not in callout and "fold.at ===" not in callout
    assert "view.state.doc.lineAt(view.posAtDOM(el)).from" in CMJS
    assert "docCalloutKindMenu(lineOf(kindButton" in CMJS and "docToggleCalloutFold(lineOf(fold" in CMJS


@needs_node
def test_a_fresh_frame_closure_is_known_by_its_source():
    lag = unwrapped((JS / "lag-watch.js").read_text(encoding="utf-8"))
    fns = "\n".join(_function(lag, h) for h in ("function lagStackOwner(", "function lagRafOwner("))
    const = re.search(r"^const LAG_RAF = .*$", lag, re.M).group(0)
    got = _node(
        const
        + "\n"
        + fns
        + """
let stacks = 0;
const real = lagStackOwner;
lagStackOwner = (s) => { stacks += 1; return real(s); };
const owners = new Set();
for (let i = 0; i < 64; i += 1) owners.add(lagRafOwner(() => i));
const one = stacks;
stacks = 0;
let flip = 0;
lagStackOwner = () => { stacks += 1; return flip++ % 2 ? "a.js tick" : "b.js tick"; };
for (let i = 0; i < 96; i += 1) lagRafOwner(() => i + 1);
console.log(JSON.stringify({ one, owners: owners.size, shared: stacks, mark: LAG_RAF.src.get("() => i + 1") }));
"""
    )
    assert got["owners"] == 1
    assert got["one"] <= 3, "64 fresh closures of one source take a stack at most once in 32"
    assert got["mark"] == "" and got["shared"] > 50, "a source two owners share takes the stack every time once seen"
