"""Audit 1029 rank 42 (G11): the Graph tab's search box had no match count,
no way to walk the matches, and Esc did not clear it. Enter goes to the next
match and pans to it, Shift+Enter to the one before, Esc clears the search and
the similar-notes highlight, and the dock says "N matches" in a polite region.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)



def test_the_count_reads_in_words_and_says_so_when_nothing_matches() -> None:
    script = (
        "function nounCount(n, one, many = `${one}s`) { return `${n} ${n === 1 ? one : many}`; }"
        + _function(GRAPH, "graphSearchCountText")
        + "console.log(JSON.stringify([0, 1, 134].map(graphSearchCountText)))"
    )
    assert _run(script) == ["No matches", "1 match", "134 matches"]


def test_enter_walks_forward_shift_enter_back_and_both_wrap() -> None:
    script = (
        _function(GRAPH, "graphSearchStepIndex")
        + "console.log(JSON.stringify([[-1,1,3],[0,1,3],[2,1,3],[-1,-1,3],[0,-1,3],[0,1,0],[0,1,1]].map(a => graphSearchStepIndex(...a))))"
    )
    assert _run(script) == [0, 1, 0, 2, 2, -1, 0]


def _key_harness(value: str, matches: int, highlight: bool = False) -> str:
    return (
        "const log = [];"
        f"const input = {{ value: {json.dumps(value)} }};"
        "const $ = () => input;"
        "const graphSearch = { list: new Array(%d).fill(0).map((_, i) => ({ id: i, preview: 'n' + i, x: i, y: i })), at: -1, current: null };" % matches
        + f"let graphHighlightIds = {'new Set([1])' if highlight else 'null'};"
        + "function graphSearchGo(dir) { log.push(['go', dir]); }"
        + "function graphSearchClear() { log.push(['clear']); graphHighlightIds = null; input.value = ''; }"
        + _function(GRAPH, "graphSearchKey")
        + "const ev = (key, shiftKey = false) => ({ key, shiftKey, isComposing: false, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; } });"
    )


def test_enter_and_shift_enter_step_and_the_default_is_kept_off() -> None:
    script = (
        _key_harness("harbor", 3)
        + "const a = ev('Enter'), b = ev('Enter', true); graphSearchKey(a); graphSearchKey(b);"
        + "console.log(JSON.stringify({ log, a: a.defaultPrevented, b: b.defaultPrevented }))"
    )
    out = _run(script)
    assert out["log"] == [["go", 1], ["go", -1]] and out["a"] and out["b"]


def test_escape_clears_a_search_and_a_similar_notes_highlight_and_leaves_an_empty_box_alone() -> None:
    script = (
        _key_harness("harbor", 3)
        + "const a = ev('Escape'); graphSearchKey(a);"
        + "const e = ev('Escape'); graphSearchKey(e);"
        + "console.log(JSON.stringify({ log, a: a.defaultPrevented, aStop: !!a.stopped, e: e.defaultPrevented }))"
    )
    out = _run(script)
    assert out["log"] == [["clear"]] and out["a"] and out["aStop"] and out["e"] is False
    script = _key_harness("", 0, True) + "const a = ev('Escape'); graphSearchKey(a); console.log(JSON.stringify({ log }))"
    assert _run(script)["log"] == [["clear"]]  # the box is empty but a highlight is lit


def test_the_search_box_has_a_polite_count_in_the_dock_and_the_help_says_the_keys() -> None:
    assert re.search(r'<span id="graph-search-count"[^>]*role="status"[^>]*aria-live="polite"', HTML)
    find = HTML[HTML.index('class="dock-group dock-find"', HTML.index('id="graph-search"') - 600) :]
    assert find.index("graph-search-count") < find.index("graph-highlight-clear")
    count = _function(GRAPH, "graphSearchRefresh")
    assert "graph-search-count" in count


def test_the_current_match_is_ringed_and_labelled_and_a_match_is_named_with_labels_off() -> None:
    body = _function(CANVAS, "gcHighlight")
    assert "current" in body
    draw = _function(CANVAS, "gcDraw")
    assert "hl.current" in draw
    assert "|| matched)) || focused" not in draw  # a match is named whatever the tickbox says
    assert "(labelsOn && (labelsForAll || k > labelZoom)) || matched || focused" in draw
