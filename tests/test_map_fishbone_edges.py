"""L-mindmap-12: a fishbone's line to a main topic's 2nd and later causes
stays left of the causes above it (node `vm`, the layout and anchor functions)."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
SRC = Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-map.js"
#: The file calls names defined in scripts above it at load; each missing one is
#: stubbed with a permissive proxy and the load retried.
LOAD = r"""
const vm=require('vm'),fs=require('fs');
const lib=fs.readFileSync(process.argv[1],'utf8'),probe=fs.readFileSync(process.argv[2],'utf8');
const stub=()=>new Proxy(function(){},{get:(t,k)=>k===Symbol.toPrimitive?()=>0:stub(),apply:()=>stub()});
const extra={};
for(let i=0;i<200;i++){
  const ctx={console,Math,Number,Object,Set,Map,JSON,Array,String,Promise,Boolean,RegExp,Date,
    setTimeout:()=>0,clearTimeout:()=>{},addEventListener:()=>{},
    document:{querySelector:()=>null,querySelectorAll:()=>[],getElementById:()=>null,addEventListener:()=>{},documentElement:{dataset:{}}},...extra};
  ctx.window=ctx;ctx.__out=(v)=>process.stdout.write(JSON.stringify(v));vm.createContext(ctx);
  try{vm.runInContext(lib,ctx);vm.runInContext(probe,ctx);break;}
  catch(e){const m=/(\w+) is not defined/.exec(String(e.message));if(!m||extra[m[1]]!==undefined)throw e;extra[m[1]]=stub();}
}
"""


def run(tmp_path, body):
    lib, probe = tmp_path / "lib.js", tmp_path / "probe.js"
    lib.write_text(_js_scope.unwrapped(frontend_text("whiteboard-map.js")), encoding="utf-8")
    probe.write_text(body, encoding="utf-8")
    proc = subprocess.run(["node", "-e", LOAD, str(lib), str(probe)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)

BODY = r"""
wbMapGapBreadth = () => 10; wbMapGapDepth = () => 40;
const mk = (id, parent_id) => ({ id, parent_id, x: 0, y: 0, width: 100, height: 30, data: {} });
const nodes = [mk(1, null), mk(2, 1), mk(3, 2), mk(4, 2), mk(5, 2), mk(6, 1), mk(7, 6), mk(8, 6)];
const idx = { nodes, byId: new Map(nodes.map((n) => [n.id, n])), roots: [nodes[0]], childrenOf: new Map() };
for (const n of nodes) idx.childrenOf.set(n.id, nodes.filter((k) => k.parent_id === n.id));
const pos = wbMapColumnPositions(idx, "fishbone");
for (const n of nodes) Object.assign(n, pos.get(n.id));
const out = [];
for (const n of nodes) {
  if (n.parent_id == null) continue;
  const parent = idx.byId.get(n.parent_id);
  const a = wbMapEdgeAnchors(parent, n, "fishbone");
  const older = nodes.filter((k) => k.parent_id === n.parent_id && k.id < n.id);
  //: The line's x range against the boxes of the causes above/below it.
  const lo = Math.min(a.x1, a.x2), hi = Math.max(a.x1, a.x2);
  const top = Math.min(a.y1, a.y2), bot = Math.max(a.y1, a.y2);
  const hits = nodes.filter((k) => k.id !== n.id && k.id !== parent.id && k.parent_id !== null &&
    hi > k.x + 1 && lo < k.x + k.width - 1 && bot > k.y + 1 && top < k.y + k.height - 1).map((k) => k.id);
  out.push({ id: n.id, rib: !!a.rib, hits });
}
__out(out);
"""


@needs_node
def test_causes_lines_cross_no_other_topic(tmp_path):
    rows = run(tmp_path, BODY)
    causes = [r for r in rows if r["id"] not in (2, 6)]
    assert len(causes) == 5
    assert all(r["hits"] == [] for r in causes), causes


RADIAL = r"""
wbMapGapBreadth = () => 24; wbMapGapDepth = () => 80;
window.wbMapState = { layout: "radial" };
const mk = (id, parent_id) => ({ id, parent_id, x: 0, y: 0, width: 200, height: 64, data: {} });
const nodes = [mk(1, null)];
let id = 2;
for (let b = 0; b < 6; b++) { const bid = id++; nodes.push(mk(bid, 1)); for (let l = 0; l < 4; l++) nodes.push(mk(id++, bid)); }
const bounds = (narrow) => {
  const idx = { nodes, byId: new Map(nodes.map((n) => [n.id, n])), roots: [nodes[0]], childrenOf: new Map() };
  for (const n of nodes) { idx.childrenOf.set(n.id, nodes.filter((k) => k.parent_id === n.id)); n._leaf = narrow && !idx.childrenOf.get(n.id).length; }
  const pos = wbMapTidyPositions(idx, "radial");
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const n of nodes) { const p = pos.get(n.id), s = wbMapNodeSize(n); x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x + s.w); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y + s.h); }
  return { w: Math.round(x1 - x0), h: Math.round(y1 - y0), n: nodes.length };
};
__out({ wide: bounds(false), narrow: bounds(true) });
"""


@needs_node
def test_radial_leaves_are_narrower_so_a_31_topic_map_is_smaller(tmp_path):
    out = run(tmp_path, RADIAL)
    assert out["narrow"]["n"] == 31
    #: Measured in this harness: 1911 wide before the leaf cap, 1240 after.
    assert out["narrow"]["w"] < out["wide"]["w"] * 0.8, out
