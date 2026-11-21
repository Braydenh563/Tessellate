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

