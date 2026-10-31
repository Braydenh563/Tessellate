"""Documents perf, audit 1028 D19 and D20, run on the real functions under node.

D19: the document text is read once per version (a `Text` is immutable, so the
string is keyed by the object); D20: the facts pass does nothing while the
Documents tab is hidden and runs once on the way back in.
"""

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
    source = (JS / "documents.js").read_text(encoding="utf-8")
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
    source = (JS / "documents.js").read_text(encoding="utf-8")
    body = "\n".join(_function(source, head) for head in ("function runDocFacts(", "function scheduleDocFacts("))
    return (
        f"""
let docFactsTimer = null, docFactsStale = false, docFactsIdle = 0;
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
    source = (JS / "documents.js").read_text(encoding="utf-8")
    assert "if (docFactsStale && currentDoc) runDocFacts();" in _function(source, "async function loadDocuments(")
