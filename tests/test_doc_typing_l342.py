"""L342: per-key main-thread time in a 20k-word document at 4x CPU.

The gate (scratchpad/ui-sweeps/typegate.js) asks for a per-key ThreadTime
p95 under 50 ms in both views. Each cut here keeps what the person sees
equal and moves work off the keys that do not need it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")
LT = (JS / "documents-languagetool.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def _node(script: str, *args: str) -> dict:
    out = subprocess.run(["node", "-e", script, *args], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_a_grammar_answer_landing_mid_typing_works_out_its_findings_only_when_read():
    script = (
        """
let docGrammarCache = { text: null, findings: [] };
const docGrammarWire = { asking: null };
const docProse = { typedAt: 0 };
let worked = 0, drawn = 0, answer;
const docGrammarEnabled = () => true, docCheckLinkText = () => "";
const docGrammarFindings = (lints, text) => { worked += 1; return lints.map((l) => ({ start: l.start, text })); };
const renderDocProse = () => { drawn += 1; void docGrammarCache.findings; };
const docGrammarAsk = (text, early) => new Promise((r) => { answer = r; });
"""
        + _function(PROSE, "function docGrammarRequest(")
        + """
(async () => {
  const out = {};
  docGrammarRequest("one two");
  docProse.typedAt = performance.now() + 1;
  answer([{ start: 0 }]);
  await new Promise((r) => setTimeout(r, 0));
  out.typed = { worked, drawn };
  out.first = docGrammarCache.findings.length;
  void docGrammarCache.findings;
  out.read = worked;
  docProse.typedAt = 0;
  docGrammarRequest("three");
  answer([{ start: 1 }, { start: 2 }]);
  await new Promise((r) => setTimeout(r, 0));
  out.paused = { worked, drawn, n: docGrammarCache.findings.length, text: docGrammarCache.text };
  console.log(JSON.stringify(out));
})();
"""
    )
    got = _node(script)
    assert got["typed"] == {"worked": 0, "drawn": 0}
    assert got["first"] == 1 and got["read"] == 1
    assert got["paused"] == {"worked": 2, "drawn": 1, "n": 2, "text": "three"}


@needs_node
def test_a_first_languagetool_check_maps_every_paragraph_once_without_a_quadratic_search():
    assert "paras.findIndex" not in LT and "touched.find(" not in LT
    script = r"""
    global.window = {docSpell: {}}; global.$ = () => null; global.docSpellingVariant = () => "us";
    const sent = [];
    global.apiJson = async (u, o) => { const b = JSON.parse(o.body); sent.push(b.text);
      return {available: true, matches: [...b.text.matchAll(/bad/g)].map((m) => ({start: m.index, end: m.index + 3, message: "m", suggestions: []}))}; };
    eval(require("fs").readFileSync(process.argv[1], "utf8"));
    const paras = [];
    for (let i = 0; i < 3000; i += 1) paras.push(i % 7 === 0 ? "bad same" : `line ${i} bad`);
    const text = paras.join("\n\n");
    const lt = window.docSpell.languageTool;
    (async () => {
      const a = await lt([], text);
      const edited = text.replace("line 1 bad", "line 1 bad bad");
      const b = await lt([], edited);
      const want = (t) => [...t.matchAll(/bad/g)].map((m) => m.index);
      console.log(JSON.stringify({ n: sent.length, second: sent[1], a: a.map((l) => l.start).join() === want(text).join(), b: b.map((l) => l.start).join() === want(edited).join() }));
    })();
    """
    got = _node(script, str(JS / "documents-languagetool.js"))
    assert got == {"n": 2, "second": "line 1 bad bad", "a": True, "b": True}


PREVIEW = (JS / "documents-preview.js").read_text(encoding="utf-8")


@needs_node
def test_moving_the_outline_mark_writes_only_the_rows_that_change():
    start = PREVIEW.index("  function markDocOutline(")
    body = PREVIEW[start : PREVIEW.index("\n  }\n", start) + 4]
    script = (
        """
let writes = 0;
const button = (on) => { const cls = new Set(on ? ["is-current"] : []), attrs = new Map(on ? [["aria-current", "location"]] : []);
  return { isConnected: true, classList: { contains: (c) => cls.has(c), add: (c) => { writes++; cls.add(c); }, remove: (c) => { writes++; cls.delete(c); } },
    hasAttribute: (a) => attrs.has(a), setAttribute: (a, v) => { writes++; attrs.set(a, v); }, removeAttribute: (a) => { writes++; attrs.delete(a); }, cls, attrs }; };
let docOutlineRows = [], docOutlineMarked = -1;
for (let i = 0; i < 500; i++) docOutlineRows.push({ line: i * 10, button: button(i === 3), row: { classList: { contains: () => false } } });
docOutlineMarked = 3;
const docSurface = () => ({ kind: "codemirror" }), renderDocCrumbs = () => {}, docCaretLine = () => 0;
const docCaretVisibleLine = () => null, docVisibleTopLine = () => 0, keepOutlineRowInView = () => {}, afterFrames = () => {};
"""
        + body
        + """
markDocOutline(255);
const marked = docOutlineRows.filter((r) => r.button.cls.has("is-current")).map((r) => r.line);
const aria = docOutlineRows.filter((r) => r.button.attrs.has("aria-current")).map((r) => r.line);
console.log(JSON.stringify({ writes, marked, aria, at: docOutlineMarked }));
"""
    )
    got = _node(script)
    assert got == {"writes": 4, "marked": [250], "aria": [250], "at": 25}


_FAKE_DOM = """
let made = 0, writes = 0;
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attrs = {}; this.cls = new Set(); this.textContent = "";
    this.classList = { add: (c) => this.cls.add(c), remove: (c) => this.cls.delete(c), contains: (c) => this.cls.has(c),
      toggle: (c, on) => { writes += 1; on ? this.cls.add(c) : this.cls.delete(c); } }; made += 1; }
  setAttribute(k, v) { writes += 1; this.attrs[k] = v; }
  appendChild(c) { this.children.push(c); return c; }
  append(...c) { this.children.push(...c); }
  replaceChildren() { this.children = []; }
  addEventListener(t, f) { this["on" + t] = f; }
}
const document = { createElement: (t) => new El(t) };
const list = new El("ul");
const $ = () => list;
let docCompleteMatches = [], docCompleteBox = null, docCompleteIndex = 0, rows = [], applied = [];
const hideDocComplete = () => { docCompleteMatches = []; };
const editorMenuState = { open: false };
const docCompleteRowsAt = () => rows;
const docFillAt = () => null;
const docLiftToViewport = () => {}, docPlaceFixed = () => {};
const docCompletePlace = () => ({ left: 0, top: 0 });
const applyDocComplete = (box, match) => applied.push([box.id, match.word]);
"""


@needs_node
def test_the_word_list_keeps_its_rows_when_the_words_are_the_same():
    from tests._app_js import documents_text

    src = documents_text()
    script = _FAKE_DOM + _function(src, "function renderDocComplete(") + """
const box = { kind: "textarea", id: 1 };
const out = {};
rows = [{ word: "quick", typed: 2 }, { word: "quiet", typed: 2 }, { word: "quill", typed: 2 }];
renderDocComplete(box);
const first = list.children.slice();
out.built = made;
docCompleteIndex = 1;
const box2 = { kind: "textarea", id: 2 };
renderDocComplete(box2);
out.same = list.children.every((li, i) => li === first[i]);
out.afterSame = made;
out.active = list.children.map((li) => li.cls.has("active"));
out.aria = list.children.map((li) => li.attrs["aria-selected"]);
list.children[2].onmousedown({ preventDefault() {} });
out.applied = applied;
rows = [{ word: "quick", typed: 3 }, { word: "quiet", typed: 3 }];
renderDocComplete(box2);
out.rebuilt = list.children[0] !== first[0];
out.texts = list.children.map((li) => li.children.map((c) => c.textContent).join("|"));
out.active2 = list.children.map((li) => li.cls.has("active"));
console.log(JSON.stringify(out));
"""
    out = _node(script)
    assert out["same"] and out["afterSame"] == out["built"]
    assert out["active"] == [False, True, False] and out["aria"] == ["false", "true", "false"]
    # A kept row offers what is shown now, in the box of the latest key.
    assert out["applied"] == [[2, "quill"]]
    assert out["rebuilt"] and out["texts"] == ["qui|ck", "qui|et"]
    assert out["active2"] == [False, True]


def _storage_listener() -> str:
    from tests._app_js import documents_text

    src = documents_text()
    start = src.index('window.addEventListener("storage", () => {\n  prefs.writes += 1;')
    return src[start:src.index("});", start) + 3] + "\n"


@needs_node
def test_the_gutter_preference_is_read_once_until_a_preference_is_written():
    from tests._app_js import documents_text

    prefs_js = (JS / "prefs.js").read_text(encoding="utf-8")
    script = """
const store = new Map(); let reads = 0; let onStorage = null;
const window = { localStorage: { getItem: (k) => { reads += 1; return store.has(k) ? store.get(k) : null; },
  setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) },
  addEventListener: (t, f) => { if (t === "storage") onStorage = f; } };
""" + prefs_js + "\nconst DOC_GUTTER_KEY = \"doc-gutter\";\n" + _function(documents_text(), "function docGutterPref(") + _storage_listener() + """
const out = {};
reads = 0; // prefs.js's own migration reads at load
out.a = docGutterPref(); docGutterPref(); docGutterPref();
out.readsCached = reads;
prefs.set("doc-gutter", "1");
out.b = docGutterPref(); docGutterPref();
out.readsAfterSet = reads;
store.set("doc-gutter", "0"); onStorage({ key: "doc-gutter" });
out.c = docGutterPref();
prefs.remove("doc-gutter");
out.d = docGutterPref();
console.log(JSON.stringify(out));
"""
    out = _node(script)
    assert out["readsCached"] == 1 and out["readsAfterSet"] == 2
    assert [out["a"], out["b"], out["c"], out["d"]] == [None, "1", "0", None]


@needs_node
def test_the_ghost_keeps_an_empty_slot_at_the_caret_while_typing_runs_on():
    """A ghost that comes or goes splits or joins the caret's text node, and CodeMirror then puts the
    DOM selection back with a forced layout (Selection.collapse, about 15 ms of a key at 4x CPU, 11
    of 44 keys in the gate's Source burst). While the person keeps typing, the ghost's place stays
    as an empty span, so only a new ghost's text changes; any other move drops it."""
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    start = code.index("docGhostPlugin.make = ")
    make = code[start:code.index("\n};\n", start) + 4]
    script = """
const document = { createElement: () => ({ setAttribute() {}, set textContent(t) { this.t = t; } }) };
class WidgetType {}
const Decoration = { none: [], set: (a) => a, widget: (spec) => ({ range: (pos) => ({ pos, text: spec.widget.text, side: spec.side }) }) };
const CM = { view: { Decoration, WidgetType, ViewPlugin: { fromClass: (cls, spec) => ({ cls, spec }) } } };
const docGhostPlugin = {};
""" + make + """
let want = null;
const P = docGhostPlugin.make(CM, (state, ghost) => (want ? ghost(want, state.selection.main.head) : null));
const st = (head, ranges) => ({ selection: { main: { head, empty: true }, ranges: ranges || [{}] } });
const typed = (head) => ({ state: st(head), docChanged: true, transactions: [{ isUserEvent: (e) => e === "input" }] });
const plugin = new P.cls({ state: st(0) });
const out = [];
const look = () => out.push(P.spec.decorations(plugin).map((d) => [d.pos, d.text]));
want = null; plugin.update(typed(1)); look();          // no ghost yet: nothing
want = "ck"; plugin.update(typed(3)); look();          // a ghost
want = null; plugin.update(typed(4)); look();          // the word ran past its rows: an empty slot
plugin.update(typed(5)); look();                       // still typing: the slot follows the caret
want = "wn"; plugin.update(typed(8)); look();          // a ghost again, in the slot
want = null; plugin.update({ state: st(2), docChanged: false, selectionSet: true, transactions: [{ isUserEvent: () => false }] }); look();  // a click: gone
plugin.update(typed(3)); look();                       // typing again without a ghost: nothing
console.log(JSON.stringify(out));
"""
    out = _node(script)
    assert out == [[], [[3, "ck"]], [[4, ""]], [[5, ""]], [[8, "wn"]], [], []]


@needs_node
def test_the_undo_pair_writes_disabled_only_when_it_changes():
    from tests._app_js import app_js_text

    text = app_js_text()
    start = text.index("function paintUndoDoor(button, verb, surface, stack) {")
    block = text[start : text.index("\n}\n", start) + 3]
    script = (
        "function paintStatusItem() {}\n"
        + block
        + """
let writes = 0, value = true;
const button = { id: "status-redo", get disabled() { return value; }, set disabled(v) { writes += 1; value = v; } };
const doc = (can) => ({ where: "document", canRedo: () => can });
for (let i = 0; i < 40; i += 1) paintUndoDoor(button, "redo", doc(false), []);
for (let i = 0; i < 40; i += 1) paintUndoDoor(button, "redo", null, []);
const idle = writes;
paintUndoDoor(button, "redo", doc(true), []);
paintUndoDoor(button, "redo", doc(true), []);
const lit = value;
paintUndoDoor(button, "redo", null, [{ label: "a step" }]);
paintUndoDoor(button, "redo", null, []);
console.log(JSON.stringify({ idle, writes, lit, after: value }));
"""
    )
    got = _node(script)
    assert got == {"idle": 0, "writes": 2, "lit": False, "after": True}


def test_the_document_card_is_not_a_has_subject_over_the_editor():
    """`.card:has(details.dock-menu[open])` walked the document card's whole subtree, the
    editor included, so each keystroke's write in the editor re-checked it and restyled the
    card and `.doc-layout`. The document's card takes the state from a class its one such
    menu sets, and the class covers the same cards: #doc-view-menu is the only
    `details.dock-menu` in `.doc-main`, and no documents script makes another."""
    import re

    from tests._app_js import documents_text

    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".card:has(details.dock-menu[open])" not in re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert ".card:not(.doc-main):has(details.dock-menu[open]),\n.card.doc-main.doc-view-menu-open {" in css
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    main = html[html.index('<section class="card doc-main">') :]
    depth, end = 0, 0
    for m in re.finditer(r"<(/?)section\b", main):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            end = m.end()
            break
    tags = re.findall(r"<details\b[^>]*>", main[:end])
    menus = [t for t in tags if "dock-menu" in (re.findall(r'class="([^"]*)"', t) or [""])[0].split()]
    assert len(menus) == 1 and 'id="doc-view-menu"' in menus[0]
    docs = documents_text()
    assert not re.search(r"""["'\s]dock-menu["'\s]""", docs.replace("doc-dock-menu", ""))
    assert 'viewMenu?.addEventListener("toggle", () => viewMenu.closest(".card")?.classList.toggle("doc-view-menu-open", viewMenu.open))' in docs


def test_the_grammar_worker_sends_spelling_lints_as_spans_only():
    # The page drops Harper's spelling lints and reads only their span (LanguageTool's overlap
    # test), so the worker sends nothing else of them: the whole lints were 359 kB per answer.
    import re

    worker = (ROOT / "frontend" / "js" / "harper-worker.js").read_text(encoding="utf-8")
    assert "bare.has(kept.kind) ? { start: kept.start, end: kept.end, kind: kept.kind } : kept" in worker
    assert "const bare = new Set(Array.isArray(event.data.bare) ? event.data.bare : []);" in worker
    text = (ROOT / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8")
    assert "bare: [...DOC_GRAMMAR_SKIP_KINDS] });" in text
    assert 'const DOC_GRAMMAR_SKIP_KINDS = new Set(["Spelling"]);' in text
    findings = text[text.index("function docGrammarFindings(") :]
    findings = findings[: findings.index("\n}\n")]
    assert re.search(r"if \(DOC_GRAMMAR_SKIP_KINDS\.has\(lint\.kind\)\) continue;", findings)
    # Nothing reads a spelling lint's words before that skip.
    assert findings.index("DOC_GRAMMAR_SKIP_KINDS") < findings.index("lint.message")


def _live_patch_harness(text: str, keys: list, at: int) -> dict:
    """Keys typed at `at` in Live: how many the plugin patched, and where the patched set
    differs from a fresh plugin's on the same state (the dx1 harness, one place)."""
    import re

    from tests import test_doc_typing_dx1 as dx1

    helpers = "\n".join(dx1._function(dx1.DOCS, h) for h in ("function docLiveSpanTouched(", "function docLiveRevealSame("))
    anchor = re.search(r"^docLiveSpanTouched\.anchorIn = .*$", dx1.DOCS, re.M).group(0)
    fence = "function docPairInput() {}\n" + PROSE[PROSE.index("docPairInput.fenceParts = ") :].split("\n};\n")[0] + "\n};"
    helpers = fence + "\n" + dx1._function((JS / "markdown.js").read_text(encoding="utf-8"), "function mdMathBlockFrom(") + "\n" + helpers
    stubs = dx1._STUBS.replace("function mdTocEntries() { return []; }", "function mdTocEntries(t) { return [...t.matchAll(/^#+ (.*)$/gm)].map((m) => ({ text: m[1], level: 1 })); }")
    return dx1._node(
        dx1._LOAD
        + 'vm.runInContext(read("js/documents-props.js"), ctx);\n'
        + f"vm.runInContext({json.dumps(helpers + chr(10) + anchor + stubs)}, ctx);\n"
        + 'vm.runInContext(read("js/documents-cm.js"), ctx);\n'
        + f"ctx.DOC = {json.dumps(text)}; ctx.KEYS = {json.dumps(keys)}; ctx.AT = {at};\n"
        + """
const out = vm.runInContext(`(() => {
  const CM = CM6, P = docLivePlugin(CM);
  const md = CM.markdown.markdown({ base: CM.markdown.markdownLanguage });
  const dom = { closest: () => ({}), querySelector: () => null };
  const viewOf = (state) => ({ state, hasFocus: true, visibleRanges: [{ from: 0, to: state.doc.length }], viewport: { from: 0, to: state.doc.length }, dom, contentDOM: dom });
  const snap = (set) => { const o = []; for (const it = set.iter(); it.value; it.next()) o.push([it.from, it.to, it.value]); return o; };
  const same = (a, b) => a.length === b.length && a.every(([f, t, v]) => b.some(([f2, t2, v2]) => f2 === f && t2 === t && (v2 === v || v2.eq(v))));
  let state = CM.state.EditorState.create({ doc: DOC, extensions: [md], selection: { anchor: AT } });
  const inst = P.create(viewOf(state));
  let patched = 0, at = AT;
  const bad = [];
  const pt = inst.patch;
  inst.patch = function (u) { const r = pt.call(this, u); if (r) patched += 1; return r; };
  for (const k of KEYS) {
    const tr = state.update({ changes: { from: at, insert: k }, selection: { anchor: at + k.length } });
    at += k.length;
    inst.update({ startState: state, state: tr.state, changes: tr.changes, transactions: [tr], docChanged: true, selectionSet: true, viewportChanged: true, focusChanged: false, view: viewOf(tr.state) });
    state = tr.state;
    if (!same(snap(inst.decorations), snap(P.create(viewOf(state)).decorations))) bad.push(k);
  }
  return { patched, bad };
})()`, ctx);
console.log(JSON.stringify(out));
"""
    )


_HEAD_DOC = "# Big document\n\n\n\n## Section 0\n\nword1 word2 word3\n\n\n# Other\n\nlast words\n"


@needs_node
def test_keys_at_a_headings_start_patch_the_live_set_and_match_a_rebuild():
    """The gate types at Ctrl+Home, before the H1's `#`: each of those keys rebuilt every visible
    line (the patch took paragraphs only). Now the heading's lines are patched, the line turning
    into a paragraph included, and the set equals a full rebuild after every key."""
    keys = list(" the quick")
    got = _live_patch_harness(_HEAD_DOC, keys, 0)
    assert got["bad"] == [], got
    assert got["patched"] == len(keys), got
    inside = _live_patch_harness(_HEAD_DOC, list("ab #"), _HEAD_DOC.index("Section"))
    assert inside["bad"] == [] and inside["patched"] == 4, inside
    level = _live_patch_harness(_HEAD_DOC, ["#", "x", " "], _HEAD_DOC.index("# Other"))
    assert level["bad"] == [], level


@needs_node
def test_a_heading_edit_with_a_contents_block_in_view_rebuilds():
    text = "[TOC]\n\n" + _HEAD_DOC
    got = _live_patch_harness(text, list("ab"), text.index("Section"))
    assert got["bad"] == [] and got["patched"] == 0, got
    para = _live_patch_harness(text, list("ab"), text.index("word2"))
    assert para["bad"] == [] and para["patched"] == 2, para
