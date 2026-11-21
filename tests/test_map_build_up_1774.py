"""Build a map up, take it apart (INBOX 1774, MINDMAP_PLAN "Placed from INBOX, 2026-11-11").

The marked region of whiteboard-map.js (`WB-MAP-BUILD-BEGIN` to `-END`) is pure,
so node runs it here. The run itself is driven in the browser by
`scratchpad/ui-sweeps/wbpresent.js` MODE=build.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MAP_JS = frontend_text("whiteboard-map.js")
BOARD = frontend_text("whiteboard.js")
COMMANDS = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")


def _run(expr: str, tree: dict) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    region = MAP_JS[MAP_JS.index("// WB-MAP-BUILD-BEGIN") : MAP_JS.index("// WB-MAP-BUILD-END")]
    script = (
        region
        + "\nconst t = " + json.dumps(tree) + ";\n"
        + "const node = (id) => ({ id, data: { collapsed: (t.collapsed || []).includes(id) } });\n"
        + "const index = { roots: t.roots.map(node), childrenOf: new Map(Object.entries(t.children).map(([k, v]) => [Number(k), v.map(node)])) };\n"
        + "index.nodes = [...new Set([...t.roots, ...Object.values(t.children).flat()])].map(node);\n"
        + "index.byId = new Map(index.nodes.map((n) => [n.id, n]));\n"
        + "const subtree = (id) => [id, ...(index.childrenOf.get(id) || []).flatMap((k) => subtree(k.id))];\n"
        + "const folded = new Set(index.nodes.filter((n) => n.data.collapsed).flatMap((n) => subtree(n.id).slice(1)));\n"
        + f"console.log(JSON.stringify({expr}));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


#: 1 is the centre; branch 2 has depth 3 (2, 5, 7), branch 3 has depth 1.
TREE = {"roots": [1], "children": {"1": [2, 3], "2": [5], "5": [7]}}
REVEALS = "wbMapBuild.plan(index, folded).map((s) => s.reveal)"


def test_steps_run_centre_then_each_branch_a_level_at_a_time_then_the_whole_map():
    got = _run(REVEALS, TREE)
    assert got == [[1], [2], [5], [7], [3], []]
    kinds = _run("wbMapBuild.plan(index, folded).map((s) => [s.kind, s.id, s.level])", TREE)
    assert kinds == [["centre", None, 0], ["branch", 2, 1], ["branch", 2, 2], ["branch", 2, 3], ["branch", 3, 1], ["whole", None, 0]]


def test_several_central_topics_all_start_the_talk():
    tree = {"roots": [1, 10], "children": {"1": [2], "10": [11]}}
    got = _run(REVEALS, tree)
    assert got[0] == [1, 10]
    assert got == [[1, 10], [2], [11], []]


def test_a_folded_branch_keeps_its_topic_but_what_is_folded_under_it_never_shows():
    tree = {**TREE, "collapsed": [2]}
    got = _run(REVEALS, tree)
    assert got == [[1], [2], [3], []]
    shown = _run("[...new Set(wbMapBuild.plan(index, folded).flatMap((s) => s.reveal))]", tree)
    assert 5 not in shown and 7 not in shown


def test_shown_at_each_step_is_the_union_so_far_and_previous_hides_exactly_that_part():
    expr = (
        "(() => { const p = wbMapBuild.plan(index, folded);"
        " const hid = (i) => [...wbMapBuild.hiddenAt(p, i)].sort((a, b) => a - b);"
        " return p.map((s, i) => [hid(i), s.reveal]); })()"
    )
    got = _run(expr, TREE)
    assert got[0][0] == [2, 3, 5, 7]
    assert got[-1][0] == []
    for i in range(1, len(got)):
        before, now, reveal = set(got[i - 1][0]), set(got[i][0]), set(got[i][1])
        #: Going back one step hides again exactly what this step revealed.
        assert before - now == reveal
        assert now <= before


def test_a_map_of_bare_trunks_has_no_branch_to_build():
    assert _run("wbMapBuild.plan(index, folded).filter((s) => s.kind === 'branch').length", {"roots": [1], "children": {}}) == 0


RING = "(() => { const r = wbMapBuild.ring(index, folded, %d); return [r.ids.sort((a, b) => a - b), r.fold]; })()"


def test_more_opens_only_the_shallowest_folded_ring():
    #: 2 and 3 are folded at depth 2; 5 (under 2) is folded too but hidden by 2's fold.
    tree = {"roots": [1], "children": {"1": [2, 3], "2": [5], "3": [6], "5": [7]}, "collapsed": [2, 3, 5]}
    assert _run(RING % 1, tree) == [[2, 3], False]


def test_less_folds_only_the_deepest_open_ring_and_keeps_a_ragged_map_ragged():
    tree = {"roots": [1], "children": {"1": [2, 3], "2": [5], "5": [7]}}
    #: Open topics with branches: 1 (depth 1), 2 (2), 5 (3). The deepest is 5.
    assert _run(RING % -1, tree) == [[5], True]
    #: 5 folded: the next ring in is 2, and 3 (a leaf, depth 2) is untouched.
    assert _run(RING % -1, {**tree, "collapsed": [5]}) == [[2], True]


def test_more_never_shuts_a_branch_opened_by_hand_and_less_never_opens():
    tree = {"roots": [1], "children": {"1": [2, 3], "2": [5], "3": [6]}, "collapsed": [3]}
    assert _run(RING % 1, tree) == [[3], False]
    ids, fold = _run(RING % -1, tree)
    assert fold is True and 3 not in ids


def test_nothing_to_change_is_an_empty_ring():
    assert _run(RING % 1, TREE)[0] == []
    assert _run(RING % -1, {"roots": [1], "children": {"1": [2]}, "collapsed": [1]})[0] == []


def test_levels_shown_counts_from_the_trunks_as_one():
    assert _run("wbMapBuild.levels(index, folded)", TREE) == 4
    assert _run("wbMapBuild.levels(index, folded)", {**TREE, "collapsed": [2]}) == 2


# --- static: the doors and the wiring ---------------------------------------


def test_alt_equal_and_minus_step_the_levels_on_the_canvas_only():
    assert re.search(r'e\.altKey && !e\.ctrlKey && !e\.metaKey && !e\.shiftKey && \(e\.code === "Equal" \|\| e\.code === "Minus"\) && wbIsMap\(\) && !wbPresent', BOARD)
    assert 'wbMapFoldToLevel({ by: e.code === "Equal" ? 1 : -1 })' in BOARD
    assert "async function wbMapFoldToLevel(level)" in MAP_JS
    assert '"wbMapFoldToLevel"' in BOARD[BOARD.index("const WB_RECORDED = [") :][:900]


def test_the_palette_the_sheet_the_map_menu_and_the_canvas_menu_carry_both_steps():
    for cid, keys, by in (("fold-level-more", "Alt+=", 1), ("fold-level-less", "Alt+-", -1)):
        assert f'id: "{cid}"' in COMMANDS and f'keys: "{keys}"' in COMMANDS
        assert f"wbMapFoldToLevel({{ by: {by} }})" in COMMANDS
    assert 'keys: ["Alt+=", "Alt+-"]' in COMMANDS
    assert "Show one more level" in MAP_JS and "Show one less level" in MAP_JS
    assert "Show one more level" in BOARD and "Show one less level" in BOARD


def test_build_up_is_a_view_that_conceals_only_while_on_and_ends_with_the_run():
    concealed = MAP_JS[MAP_JS.index("function wbMapConcealed(index)") :][:900]
    assert "if (wbMapBuild.on)" in concealed and "wbMapBuild.hidden" in concealed
    stop = BOARD[BOARD.index("function wbStopPresenting()") :][:600]
    assert "wbMapBuild.end()" in stop and "wbMapEndStudy()" in stop
    assert "if (wbMapBuild.on) return wbMapBuild.steps;" in BOARD[BOARD.index("function wbPresentSteps()") :][:1200]
    assert "steps[at].enter?.()" in BOARD[BOARD.index("function wbPresentShow(index)") :][:900]


def test_build_up_starts_from_the_board_menu_the_map_menu_and_the_palette():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="wb-map-build"' in html and "Build up branch by branch" in html
    assert '$("wb-map-build")?.addEventListener("click"' in BOARD
    assert "Build up branch by branch" in MAP_JS
    assert 'id: "present-build"' in COMMANDS and "Nothing to build up yet: add a branch first." in MAP_JS


def test_the_study_marks_moved_into_the_study_object_to_pay_for_the_new_global():
    for gone in ("function wbMapStudyKey", "function wbMapStudyLoad", "function wbMapStudySave"):
        assert gone not in MAP_JS
    assert "wbStudy.load()" in MAP_JS and "wbStudy.save()" in MAP_JS


def test_the_help_says_both():
    from tests._help_text import help_chat_text, help_core_text, help_more_text

    text = help_chat_text() + help_core_text() + help_more_text()
    assert "Alt+= and Alt+- show one more or one less level" in text
    assert "Build up branch by branch shows the centre" in text


def test_a_second_start_is_refused_and_a_shell_that_did_not_open_puts_the_map_back_whole():
    start = MAP_JS[MAP_JS.index("  start() {\n    //: One presentation at a time") :][:1500]
    assert "if (wbPresent) return;" in start
    assert "if (!wbPresent) wbMapBuild.end();" in start


def test_the_canvas_menu_greys_a_level_step_that_would_change_nothing():
    menu = BOARD[BOARD.index("const openMapCanvasMenu") :][:2600]
    assert "moreLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, 1).ids.length" in menu
    assert "lessLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, -1).ids.length" in menu
