"""L-mindmap-19: the map's grammar repaint looks each drawn topic up once, not by a scan per topic.

A CDP sampling profile of a 500-topic board put 20 to 43ms of self time in each `wbGrammarRepaint`
pass after the board opened: it ran a `find` over `wbState.objects` for every `.wb-map-node`, so
500 x 500 comparisons. The function is loaded into a node `vm` with 500 topics and 500 drawn nodes,
and the reads of the objects array are counted: an index built once per pass reads each object a
small constant number of times, a scan per topic reads it hundreds of times.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")


def _fn(src: str, head: str) -> str:
    start = src.index(head)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(head)


CASE = r"""
const N = 500;
let reads = 0;
const raw = Array.from({ length: N }, (_, i) => ({ id: i + 1, kind: "topic", data: { content: "topic " + i } }));
raw.push({ id: "s1", kind: "sticky", data: {} });
const objects = new Proxy(raw, { get(t, k, r) { if (typeof k === "string" && /^\d+$/.test(k)) reads++; return Reflect.get(t, k, r); } });
var wbState = { objects };
const nodes = Array.from({ length: N }, (_, i) => ({ dataset: { id: String(N - i) } }));
nodes.push({ dataset: { id: "gone" } });
var document = { querySelectorAll: () => nodes };
// The board instances (wbInstances.queryAll) query every mounted board the same way.
var wbInstances = { queryAll: () => nodes };
const painted = [];
function wbGrammarPaint(el, datum) { painted.push([el.dataset.id, datum.id]); }
FN
wbGrammarRepaint();
process.stdout.write(JSON.stringify({ reads, painted: painted.length, matched: painted.every(([a, b]) => a === String(b)) }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_grammar_repaint_indexes_the_objects_once_per_pass(tmp_path: Path) -> None:
    case = tmp_path / "case.js"
    case.write_text(CASE.replace("FN", _fn(MORE, "function wbGrammarRepaint(")), encoding="utf-8")
    out = subprocess.run(["node", str(case)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout)
    assert got["painted"] == 500 and got["matched"], got
    # One pass over 501 objects is about 501 reads; a find per topic was about 125,000.
    assert got["reads"] <= 2 * 501, got
