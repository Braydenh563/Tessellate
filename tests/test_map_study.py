"""Study the map (MINDMAP_PLAN §12.3 item 5, decision 36): the questions are
the trunks' branches with topics under them, and the tally is the last mark.

The marked region of whiteboard-map.js (`WB-MAP-STUDY-BEGIN` to `-END`) is
pure, so node runs it here; the run itself is driven in the browser by
`scratchpad/ui-sweeps/op5-1005.js` MODE=study.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = ROOT / "frontend" / "js" / "whiteboard-map.js"


def _run(expr: str, tree: dict) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = MAP_JS.read_text(encoding="utf-8")
    region = text[text.index("// WB-MAP-STUDY-BEGIN") : text.index("// WB-MAP-STUDY-END")]
    #: The index shape `wbMapIndex` hands it: roots, and children by parent id.
    script = (
        region
        + "\nconst t = " + json.dumps(tree) + ";\n"
        + "const node = (id) => ({ id, data: { note: (t.notes || {})[id] } });\n"
        + "const index = { roots: t.roots.map(node), childrenOf: new Map(Object.entries(t.children).map(([k, v]) => [Number(k), v.map(node)])) };\n"
        + f"console.log(JSON.stringify({expr}));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


TREE = {
    "roots": [1],
    # 1: Centre; 2 and 3 are branches with topics under them, 4 has none.
    "children": {"1": [2, 3, 4], "2": [5, 6], "5": [7], "3": [8]},
}


def test_a_question_is_a_branch_with_topics_under_it_in_map_order():
    got = _run("wbMapStudyQuestions(index).map((q) => [q.id, q.hides.sort((a, b) => a - b)])", TREE)
    assert got == [[2, [5, 6, 7]], [3, [8]]]


def test_a_map_of_bare_branches_has_nothing_to_recall():
    assert _run("wbMapStudyQuestions(index)", {"roots": [1], "children": {"1": [2, 3]}}) == []


def test_every_trunk_asks_its_own_branches():
    tree = {"roots": [1, 10], "children": {"1": [2], "2": [3], "10": [11], "11": [12]}}
    assert _run("wbMapStudyQuestions(index).map((q) => q.id)", tree) == [2, 11]


def test_the_tally_counts_the_last_mark_only():
    expr = (
        "(() => { const q = wbMapStudyQuestions(index);"
        " const t = wbMapStudyTally(q, { 2: { knew: 1, missed: 2, last: 'knew' }, 3: { knew: 3, last: 'missed' } });"
        " return [t.knew, t.of, [...t.missed]]; })()"
    )
    assert _run(expr, TREE) == [1, 2, [3]]


def test_a_topic_with_a_note_asks_for_its_note_after_the_branches():
    tree = {**TREE, "notes": {"4": "The answer to four", "5": "  ", "8": "Eight's note"}}
    got = _run("wbMapStudyQuestions(index).map((q) => [q.id, q.hides.length, q.answer || null])", tree)
    #: 2 and 3 are branch questions; 4 (a bare branch) asks for its note; 8 sits
    #: under question 3, so it is hidden until 3 is shown and is not asked; 5's
    #: blank note is none.
    assert got == [[2, 3, None], [3, 1, None], [4, 0, "The answer to four"]]


def test_a_branch_question_with_a_note_stays_one_question():
    tree = {**TREE, "notes": {"2": "note on a branch"}}
    got = _run("wbMapStudyQuestions(index).map((q) => [q.id, q.answer || null])", tree)
    assert got == [[2, None], [3, None]]


def test_a_map_of_bare_topics_with_one_note_has_one_question():
    tree = {"roots": [1], "children": {"1": [2, 3]}, "notes": {"3": "why"}}
    assert _run("wbMapStudyQuestions(index).map((q) => q.id)", tree) == [3]


def test_the_study_bar_and_the_guide_know_the_note_answer():
    mapjs = MAP_JS.read_text(encoding="utf-8")
    assert "function wbMapStudyShown(q)" in mapjs and "wbStudy.revealed.add(step.id)" in mapjs
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "its note is the" in guide
    #: The caption is set before the frame is fitted, and takes its own line when cut.
    board = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    show = board[board.index("function wbPresentShow(index)") :]
    assert show.index("wbPresentCaption(at, steps)") < show.index("const foot")
    #: The own line moved from an inline style to the picker's is-wide class
    #: when the caption became a page picker (INBOX 1425).
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    wide = css[css.index(".wb-present-count.wb-present-pick-slot.is-wide {") :]
    assert "function wbPresentCaption(at, steps)" in board and '"is-wide"' in board
    assert "flex: 1 0 100%;" in wide[: wide.index("}")]
