"""Blind test of the diagram builder (dgbt-1109): one test per finding, each failing before its fix.

Pure model behaviour runs under node (as tests/test_diagram_outline_1679.py does); the rest reads the source, and the browser
numbers are in the CHANGELOG lines and docs/roadmap/agent-remaining/dgbt-1109.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _run(files: list[str], expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},structuredClone,console};vm.createContext(ctx);"
        f"for (const f of {json.dumps(files)}) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const ops=ctx.diagramModel.ops;const o=ctx.diagramModel.outline;"
        "const chain=(ids)=>({nodes: ids.map((id)=>({id,text:id})), subgraphs: [], kept: [], edges: ids.slice(1).map((to,i)=>({from: ids[i], to, label:'', style:'solid', arrow:true}))});"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


FILES = ["diagram-ops.js", "diagram-outline.js"]
LISTED = "o.order(m, ops.layout(m)).map((i) => i.id).join('')"


@needs_node
def test_move_up_on_the_last_block_of_a_chain_swaps_it_with_the_one_above_by_rewiring_the_arrows():
    got = _run(FILES, f"(() => {{ const m = chain(['A','B','C','D','E']); const ok = o.swap(m, 'n:E', -1); return [ok, {LISTED}, m.edges.map((e) => e.from + e.to).join()]; }})()")
    assert got == [True, "ABCED", "AB,BC,CE,ED"]


@needs_node
def test_move_down_swaps_with_the_one_below_and_a_branch_or_an_end_refuses():
    down = _run(FILES, f"(() => {{ const m = chain(['A','B','C','D']); const ok = o.swap(m, 'n:B', 1); return [ok, {LISTED}]; }})()")
    assert down == [True, "ACBD"]
    # The first block has nothing above; a block that has two arrows out is a branch, and swapping it would say something else.
    ends = _run(FILES, "(() => { const m = chain(['A','B','C']); const b = chain(['A','B','C']); b.edges.push({from:'A',to:'C',label:'',style:'solid',arrow:true}); return [o.swap(m, 'n:A', -1), o.swap(m, 'n:C', 1), o.swap(b, 'n:B', -1)]; })()")
    assert ends == [False, False, False]


@needs_node
def test_a_grip_dropped_before_or_after_its_chain_neighbour_swaps_the_two():
    got = _run(
        FILES,
        f"(() => {{ const m = chain(['A','B','C','D']); const a = o.drop(m, 'n:D', {{op: 'before', key: 'n:C'}}); const b = {LISTED}; "
        f"const far = o.drop(m, 'n:A', {{op: 'after', key: 'n:D'}}); return [a, b, far]; }})()",
    )
    assert got == [True, "ABDC", False]


def test_the_row_menu_and_the_drop_go_through_the_outline_so_the_list_really_changes():
    builder = _js("diagram-builder.js")
    assert "diagramModel.outline.move(S, helpers, key, dir)" in builder
    assert "diagramModel.outline.drop(m, g.key, target)" in _js("diagram-pointer.js")


@needs_node
def test_a_new_block_joins_the_picked_block_or_else_the_last_one():
    got = _run(
        FILES,
        "(() => { const m = chain(['A','B','C']); return [o.tail(m, 'n:B'), o.tail(m, null), o.tail(m, 'g:G'), o.tail({nodes: [], edges: []}, null)]; })()",
    )
    assert got == ["B", "C", None, None]


def test_add_block_connects_what_it_adds_unless_a_drop_a_group_or_a_caller_said_otherwise():
    builder = _js("diagram-builder.js")
    assert "from = !group && !into && before === undefined ? diagramModel.outline.tail(m, sel) : null" in builder
    # The default is "not said"; a caller that passes no `from` gets the join, one that passes null does not.
    assert "from = undefined" in builder.split("function addBlock(", 1)[1].split(") {", 1)[0]
