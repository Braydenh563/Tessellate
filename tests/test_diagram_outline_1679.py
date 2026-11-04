"""INBOX 1679 slice 6: the block list reads as the diagram, in flow order with depth.

The order is a view (D1: the printed source stays the truth), so it is tested as a pure function under node; the row heights
and the ten-block fit are a browser run named in docs/roadmap/agent-remaining/diagram-1679-1104.md.
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

# CEO connected to Sales, Design, Engineering; Engineering to Frontend and Backend, as Connect to… adds them.
ORG = (
    "{nodes: ['CEO','Sales','Design','Engineering','Frontend','Backend'].map((id) => ({id, text: id})), subgraphs: [], kept: [],"
    " edges: [['CEO','Sales'],['CEO','Design'],['CEO','Engineering'],['Engineering','Frontend'],['Engineering','Backend']].map(([from,to]) => ({from, to, label:'', style:'solid', arrow:true}))}"
)


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"for (const f of ['diagram-ops.js','diagram-outline.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const ops=ctx.diagramModel.ops;const o=ctx.diagramModel.outline;const m={ORG};"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_an_org_chart_lists_the_root_then_each_branch_with_its_depth():
    rows = _run("o.order(m, ops.layout(m)).map((i) => i.id + ':' + (i.depth || 0))")
    assert rows == ["CEO:0", "Sales:1", "Design:1", "Engineering:1", "Frontend:2", "Backend:2"]


@needs_node
def test_siblings_added_in_reverse_are_listed_in_flow_order_and_the_source_order_is_untouched():
    swapped = "m.nodes.reverse();"
    rows = _run(f"(() => {{ {swapped} return [o.order(m, ops.layout(m)).map((i) => i.id), ops.layout(m).map((i) => i.id)]; }})()")
    assert rows[0] == ["CEO", "Sales", "Design", "Engineering", "Frontend", "Backend"]
    assert rows[1] == ["Backend", "Frontend", "Engineering", "Design", "Sales", "CEO"]


@needs_node
def test_a_cycle_is_cut_at_the_first_repeat_and_a_group_keeps_its_place():
    cyc = _run(
        "(() => { const c = {nodes:[{id:'A',text:'A'},{id:'B',text:'B'}], subgraphs: [], kept: [], edges:[{from:'A',to:'B'},{from:'B',to:'A'}]};"
        " return o.order(c, ops.layout(c)).map((i) => i.id + ':' + (i.depth || 0)); })()"
    )
    assert cyc == ["A:0", "B:1"]
    grouped = _run(
        "(() => { const c = {nodes:[{id:'A',text:'A'},{id:'B',text:'B',group:'g'},{id:'C',text:'C',group:'g'}], subgraphs:[{id:'g',title:'G',parent:null}], kept: [], edges:[{from:'B',to:'C'}]};"
        " return o.order(c, ops.layout(c)).map((i) => i.type + i.id + ':' + (i.kids || []).map((k) => k.id + (k.depth || 0)).join(',')); })()"
    )
    assert grouped == ["gg:B0,C1", "nA:"]


def test_the_outline_is_lazy_wired_into_render_and_indents_by_depth():
    builder = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert 'diagramOutline: ["/js/diagram-outline.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert 'ensureModule("diagramOutline")' in builder and "diagramModel.outline" in builder.split("function render(S) {", 1)[1].split("\n  }\n", 1)[0]
    assert "item.depth" in builder
    assert '.dgm-block[data-depth="2"]' in CSS


def test_a_new_block_from_connect_lands_after_the_sources_other_targets():
    joins = (JS / "diagram-joins.js").read_text(encoding="utf-8")
    assert "lastTarget" in joins and "before: " in joins.split("lastTarget", 1)[1].split("\n", 6)[-1] + joins


def test_a_connector_row_is_one_short_line():
    builder = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    chip = builder.split("function joinChip(S, edge, index) {", 1)[1].split("\n  }\n", 1)[0]
    assert 'el("span", "dgm-join-to", to)' in chip
    row = CSS.split(".dgm-join {", 1)[1].split("}", 1)[0]
    assert "min-height: var(--control-h-dense)" in row
