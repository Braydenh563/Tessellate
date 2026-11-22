"""L-mindmap-27: a grammar answer repaints only the labels that wear, or are about to wear, a mark.

The first pan frame on a 500-topic map measured 40 to 46ms (mapperf.js, CDP ThreadTime), and the
time was `wbGrammarRepaint`: each Harper answer arriving during the pan painted all 500 drawn
topics, and every paint asked the label for `querySelector` and `isContentEditable`, the second a
style read the pan had just made stale. A label with no kept finding and no mark on it has nothing
to wear or take off, so it is not touched. `wbGrammarPaint` runs in a node `vm` against fakes that
count those reads.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_lag_map_grammar_repaint import MORE, _fn

CASE = r"""
let queries = 0, editableReads = 0;
const queued = [];
var wbGrammar = { found: new Map(), queue: { add: (t) => queued.push(t) }, timer: 1 };
function wbGrammarAvailable() { return true; }
function wbGrammarSoon() {}
function label() {
  const el = { dataset: {} };
  Object.defineProperty(el, "isContentEditable", { get() { editableReads++; return false; } });
  return el;
}
function node() {
  const text = label();
  return { text, querySelector() { queries++; return text; } };
}
FN
const N = 500;
const topics = Array.from({ length: N }, (_, i) => ({ kind: "topic", data: { content: "topic " + i } }));
const nodes = topics.map(() => node());
for (const t of topics) wbGrammar.found.set(t.data.content, null);
topics[7].data.content = "they has a cat";
wbGrammar.found.set("they has a cat", { message: "Use have" });
topics[9].data.content = "not asked yet";
nodes.forEach((n, i) => wbGrammarPaint(n, topics[i]));
const first = { queries, editableReads, marked: nodes.filter((n) => n.text.dataset.grammar).length, queued: [...queued] };
queries = editableReads = 0;
//: The finding goes (the label was fixed elsewhere): the marked label is asked once and loses it.
wbGrammar.found.set("they has a cat", null);
nodes.forEach((n, i) => wbGrammarPaint(n, topics[i]));
const second = { queries, marked: nodes.filter((n) => n.text.dataset.grammar).length };
queries = 0;
nodes.forEach((n, i) => wbGrammarPaint(n, topics[i]));
process.stdout.write(JSON.stringify({ first, second, third: queries }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_repaint_touches_only_labels_with_a_mark_to_wear_or_drop(tmp_path: Path) -> None:
    case = tmp_path / "case.js"
    case.write_text(CASE.replace("FN", _fn(MORE, "function wbGrammarPaint(")), encoding="utf-8")
    out = subprocess.run(["node", str(case)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout)
    assert got["first"] == {"queries": 1, "editableReads": 1, "marked": 1, "queued": ["not asked yet"]}, got
    assert got["second"] == {"queries": 1, "marked": 0}, got
    assert got["third"] == 0, got
