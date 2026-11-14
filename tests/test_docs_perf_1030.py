"""Documents perf, audit 1028 D19 and D20, run on the real functions under node.

D19: the document text is read once per version (a `Text` is immutable, so the
string is keyed by the object); D20: the facts pass does nothing while the
Documents tab is hidden and runs once on the way back in.
"""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def _node(script: str) -> dict:
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_doc_text_is_joined_once_per_version():
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    body = "const docStrCache = new WeakMap();\n" + _function(source, "function docStr(")
    got = _node(
        body
        + """
let joins = 0;
const make = (text) => ({ toString() { joins += 1; return text; } });
const a = make("one"), b = make("two");
const reads = [docStr(a), docStr(a), docStr(a), docStr(b), docStr(a), docStr(b)];
console.log(JSON.stringify({ reads, joins }));
"""
    )
    assert got["reads"] == ["one", "one", "one", "two", "one", "two"]
    assert got["joins"] == 2


def test_no_editor_state_is_joined_directly_in_the_documents_files():
    for path in sorted(JS.glob("documents*.js")):
        text = path.read_text(encoding="utf-8")
        direct = re.findall(r"\b(?:state|startState)\.doc\.toString\(\)", text)
        assert not direct, f"{path.name}: read a state's text through docStr"


def _facts_script(hidden: bool) -> str:
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    body = "\n".join(_function(source, head) for head in ("function runDocFacts(", "function docFactsDelay(", "function scheduleDocFacts("))
    return (
        f"""
let docFactsTimer = null, docFactsStale = false, docFactsIdle = 0, docCmView = null;
const docIsCodeFile = () => false;
const calls = [];
for (const n of ["Stats", "Outline", "Counts", "Comments", "Properties"]) globalThis["renderDoc" + n] = () => calls.push(n);
let hidden = {str(hidden).lower()};
function $() {{ return {{ classList: {{ contains: () => hidden }} }}; }}
const queue = [];
globalThis.requestIdleCallback = (fn) => queue.push(fn);
globalThis.cancelIdleCallback = (id) => {{ queue[id - 1] = null; }};
"""
        + body
        + """
(async () => {
  scheduleDocFacts(); scheduleDocFacts();
  await new Promise((r) => setTimeout(r, 200));
  for (const fn of queue) if (fn) fn();
  const during = calls.length, staleDuring = docFactsStale;
  hidden = false;
  if (docFactsStale) runDocFacts();
  console.log(JSON.stringify({ during, staleDuring, after: calls.length, stale: docFactsStale, queued: queue.filter(Boolean).length }));
})();
"""
    )


@needs_node
def test_hidden_tab_skips_the_facts_pass_and_runs_it_on_return():
    got = _node(_facts_script(True))
    assert got["during"] == 0 and got["staleDuring"] is True
    assert got["after"] == 5 and got["stale"] is False


@needs_node
def test_visible_tab_runs_the_facts_pass_once_for_two_pauses():
    got = _node(_facts_script(False))
    assert got["during"] == 5 and got["staleDuring"] is False
    assert got["queued"] == 1  # two quick pauses are one timer, so one queued pass


def test_entering_the_tab_runs_a_stale_pass():
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    assert "if (docFactsStale && currentDoc) runDocFacts();" in _function(source, "async function loadDocuments(")


def test_the_live_view_reads_the_text_through_the_per_version_cache():
    """D18: a table or [TOC] in view joined the whole document on every keystroke
    (and again for the facts pass); `docStr` makes it one join per version."""
    cm = (JS / "documents-cm.js").read_text(encoding="utf-8")
    assert not re.search(r"\bdoc\.toString\(\)", cm), "documents-cm.js reads the text through docStr(doc)"
    assert "sourceText = docStr(doc)" in cm and "mdTocEntries(docStr(doc))" in cm


def test_a_long_document_waits_longer_for_its_facts_and_the_prose_window_is_the_view():
    """D20: the wait grows with the text (one pass per burst, not per key), and the
    prose pass reads 14,000 characters around the view, not the 30,000 it once did."""
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    assert "return len > 120000 ? 600 : len > 40000 ? 300 : 120;" in _function(source, "function docFactsDelay(")
    window = _function(source, "function docProseWindow(")
    assert "const view = 14000;" in window and "DOC_PROSE_WINDOW_CHARS / 2" not in window


@needs_node
def test_the_rule_pass_is_kept_only_for_an_answer_that_changes_nothing():
    """D18 to D20: the grammar and link-offer answers repaint with `again`, and get
    the findings the key's own pass made; any other caller runs the rules afresh."""
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    start = source.index("const docProse = {")
    body = source[start : source.index("\n};\n", start) + 4]
    got = _node(
        """
const docProseIgnored = new Set(); let docWordlist = new Set(["a"]);
const docDictionary = () => new Set(), docSpellingVariant = () => "us", docCheckLinkText = () => true;
const docSpell = { packKey: () => "" };
let runs = 0;
const docProseFindings = (t) => { runs += 1; return [{ start: 0, end: t.length }]; };
"""
        + body
        + """
const first = docProse.rules("some text", false);
first[0].start += 100;                       // the caller shifts offsets: the memo must not move
const again = docProse.rules("some text", true);
const other = docProse.rules("some other text", true);
const fresh = docProse.rules("some other text", false);
docProseIgnored.add("x");
const ignored = docProse.rules("some other text", true);
console.log(JSON.stringify({ runs, again: again[0].start, other: other[0].end, fresh: fresh.length, ignored: ignored.length }));
"""
    )
    # first: 1 run; again: memo; other text: 1 run; fresh: 1 run; a dismissal changes the key: 1 run
    assert got == {"runs": 4, "again": 0, "other": 15, "fresh": 1, "ignored": 1}


@needs_node
def test_editor_listeners_are_one_per_type_and_idle_on_another_tab():
    """D21: what only the editor needs registers through `docListen`: one document
    listener per type and phase, nothing run while the Documents tab is hidden, the
    handlers in the order added, one that throws not stopping the rest."""
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    got = _node(
        """
let hidden = false;
const registered = [];
const document = { addEventListener(type, fn, capture) { registered.push([type, capture, fn]); } };
const $ = () => ({ classList: { contains: () => hidden } });
const reported = [];
globalThis.window = { reportError: (e) => reported.push(e.message) };
"""
        + _function(source, "function docListen(")
        + """
const ran = [];
docListen("input", () => ran.push("a"));
docListen("input", () => { ran.push("b"); throw new Error("boom"); });
docListen("input", () => ran.push("c"));
docListen("keydown", () => ran.push("k"), true);
docListen("keydown", () => ran.push("k2"), false);
const input = registered.find(([t]) => t === "input")[2];
hidden = true; input({});
const whileHidden = ran.length;
hidden = false; input({});
for (const key of ["a", "b", "c"]) docListen("selectionchange", () => {});
console.log(JSON.stringify({ listeners: registered.length, types: registered.map(([t, c]) => t + ":" + c), whileHidden, ran, reported }));
"""
    )
    assert got["listeners"] == 4 and got["types"] == ["input:false", "keydown:true", "keydown:false", "selectionchange:false"]
    assert got["whileHidden"] == 0 and got["ran"] == ["a", "b", "c"] and got["reported"] == ["boom"]


def test_the_editor_only_listeners_go_through_docListen():
    #: documents-callouts.js (audit row 22) took the preview's mouseover with it,
    #: inside its closure, so both files are read and an indented call counts.
    source = "".join((JS / name).read_text(encoding="utf-8") for name in ("documents.js", "documents-prose-check.js", "documents-suggest-panel.js", "documents-commands.js", "documents-templates.js", "documents-cm-load.js", "documents-tablemenu.js", "documents-preview.js", "documents-edit-keys.js", "documents-richpaste.js", "documents-block-ids.js", "documents-links-panels.js", "documents-save.js", "documents-callouts.js"))
    raw = re.findall(r'^\s*document\.addEventListener\(\s*"(input|selectionchange|focusout|dblclick|mouseover)"', source, re.M)
    assert not raw, f"{raw}: register editor-only handlers with docListen (D21)"
    assert len(re.findall(r"^\s*docListen\(", source, re.M)) >= 10


@needs_node
def test_a_watcher_wired_twice_leaves_one_observer():
    """D37: the lock watcher keeps its observer and lets go of the old one before a
    second, so wiring it again cannot stack observers (the live count stays 1)."""
    source = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    got = _node(
        """
const live = new Set(); let made = 0;
class MutationObserver { constructor() { made += 1; } observe() { live.add(this); } disconnect() { live.delete(this); } }
globalThis.MutationObserver = MutationObserver;
const overlay = { classList: { contains: () => true }, dataset: {} };
const document = { getElementById: () => overlay };
let docCmView = null, docHistoryOwner = null, docHistories = new Map();
"""
        + _function(source, "function docWatchLock(")
        + """
for (let i = 0; i < 5; i++) docWatchLock();
console.log(JSON.stringify({ made, live: live.size }));
"""
    )
    assert got == {"made": 5, "live": 1}
