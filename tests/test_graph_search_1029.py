"""Audit 1029 ranks 39 and 42 (G10, G11): the Graph tab's search box.

G10: 13 characters typed at 2,000 notes cost 5.4 s of long tasks (4x CPU).
Measured again before the change (scratchpad, seeded 2,000 notes, 4x, a key
every 250 ms): 24 long tasks, 7.3 s, longest 567 ms; at 1x 19 long tasks, 1.9 s.
The matching was not the cost (2,000 `includes` are 0.6 ms); every keystroke
repainted the whole scene and the canvas commit alone was 80 ms at 1x. The fix
is a match set found once per change and a search that rides the scene layers
the hover already uses: the dimmed map is painted once and kept, and only the
matches are drawn over it.

G11 (the match count, Enter and Esc) is in test_graph_search_keys_1029.py.
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
WIRING = (ROOT / "frontend" / "js" / "wiring.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _const(text: str, name: str) -> str:
    return re.search(rf"^const {name} = .*?;$", text, re.M).group(0) + "\n"


def _run(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _matching() -> str:
    return (
        _const(GRAPH, "graphPhrase")
        + _const(GRAPH, "graphSearch")
        + _function(GRAPH, "graphPreviewLower")
        + _function(GRAPH, "graphNodeMatches")
        + _function(GRAPH, "graphSearchFor")
    )


def test_a_preview_is_lowercased_once_per_node_not_once_per_look() -> None:
    script = (
        _matching()
        + "const n = { id: 1, preview: 'Harbor Launch' };"
        + "const a = graphPreviewLower(n); n.preview = 'Other'; const b = graphPreviewLower(n);"
        + "console.log(JSON.stringify({ a, b }))"
    )
    out = _run(script)
    assert out == {"a": "harbor launch", "b": "other"}  # follows a changed preview, never stale


def test_the_match_set_is_found_once_and_reused_for_the_same_query() -> None:
    script = (
        _matching()
        + "const nodes = [{id:1,preview:'Harbor plan'},{id:2,preview:'Soup'},{id:3,preview:'harbor notes',isGroup:false},{id:4,preview:'Harbor',isGroup:true}];"
        + "const a = graphSearchFor(nodes, 'harbor'); const ids = [...a.ids], listed = a.list.map(n => n.id); const b = graphSearchFor(nodes, 'harbor'); const same = a === b && a.ids === b.ids;"
        + "const c = graphSearchFor(nodes, 'soup');"
        + "console.log(JSON.stringify({ same, ids, listed, soup: [...c.ids], empty: graphSearchFor(nodes, '').ids === null }))"
    )
    out = _run(script)
    assert out["same"] is True
    assert out["ids"] == [1, 3] and out["listed"] == [1, 3]  # a group is a heading, not a match
    assert out["soup"] == [2] and out["empty"] is True


def test_a_phrase_filter_decides_the_matches_and_the_rest_must_still_match() -> None:
    script = (
        _matching()
        + "const nodes = [{id:1,preview:'Harbor plan'},{id:2,preview:'Harbor soup'},{id:3,preview:'Other'}];"
        + "graphPhrase.q = 'tagged work harbor'; graphPhrase.ids = new Set([1, 2, 3]); graphPhrase.rest = 'soup';"
        + "console.log(JSON.stringify([...graphSearchFor(nodes, 'tagged work harbor').ids]))"
    )
    assert _run(script) == [2]


def test_the_canvas_asks_the_set_instead_of_lowercasing_every_preview_per_look() -> None:
    body = _function(CANVAS, "gcHighlight")
    assert "toLowerCase" not in body.replace("query = (search ? search.value : \"\").trim().toLowerCase()", "")
    assert "graphQueryMatch" not in CANVAS and "graphQueryMatch" not in GRAPH
    assert "graphSearchFor(s.nodes, query)" in body


def test_a_search_is_drawn_over_the_dimmed_scene_not_as_a_whole_new_frame() -> None:
    composed = _function(CANVAS, "gcDrawComposed")
    assert "hovering || searching" in composed and "s.searchOver" in composed
    assert "gcSearchOver" in CANVAS
    # The two layers never carry the search, so they are good for every query.
    body = _function(CANVAS, "gcHighlight")
    assert 'paintMode === "rest"' in body or 'paintMode === "dim"' in body
    # A node or a line is lit in the over layer by being a match, with no hover to light it.
    draw = _function(CANVAS, "gcDraw")
    assert "s.searchOver" in draw


def test_typing_asks_for_one_redraw_per_frame_and_wiring_no_longer_debounces() -> None:
    """One frame is queued by `gcRequestDraw` however many keys arrive before it
    (the file's own rAF; a new one would be a new wake source), so the input
    handler only reads the matches and asks."""
    assert "graphSearchDebounceTimeout" not in WIRING and "setTimeout(applyGraphHighlight" not in WIRING
    assert '$("graph-search").addEventListener("input", () => applyGraphHighlight(true));' in GRAPH
    assert "requestAnimationFrame" not in _function(GRAPH, "applyGraphHighlight")
    # A query change is a cheap frame (the scene stays); everything else is a whole one.
    assert "gcRequestDraw(gcTab, cheap === true)" in _function(GRAPH, "applyGraphHighlight")
    # The server is asked about a phrase after a pause, not per key.
    assert "setTimeout(" in _function(GRAPH, "graphReadPhrase")
