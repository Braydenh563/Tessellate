"""Tidy spacing, off by default (INBOX 1529, the owner's gr1b decision).

The line-clearance force (`clearanceForce`) was the layout's dearest pass:
53,000 checks a tick at 2,000 notes. It now runs only while the Graph's
Physics switch "Tidy spacing" is on. Measured with this file's worker run at
2,000 notes and 3,800 links (CPU shared with a suite run): 40 to 44 ms a tick
off, 137 to 154 ms on.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const run = (code) => vm.runInContext(code, sb);
const nodes = [], edges = [];
for (let i = 0; i < 40; i++) nodes.push({ id: "n" + i, group: "g" + (i % 4), r: 6 });
for (let i = 1; i < 40; i++) edges.push({ source: "n" + (i - 1), target: "n" + i, kind: "link" });
const params = (tidy) => ({ gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true,
  orbit: true, curved: true, shape: "organic", ...(tidy === undefined ? {} : { tidy }) });
const out = {};
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1, params: params(undefined),
  world: { left: -500, top: -500, right: 500, bottom: 500, aspect: 1 } } });
run("stopLoop()");
out.initDefault = run("!!simulation.force('clear')");
sb.onmessage({ data: { type: "params", params: params(true) } });
run("stopLoop()");
out.paramsOn = run("!!simulation.force('clear')");
sb.onmessage({ data: { type: "params", params: params(false) } });
run("stopLoop()");
out.paramsOff = run("!!simulation.force('clear')");
sb.onmessage({ data: { type: "init", epoch: 2, nodes, edges, alpha: 1, params: params(true),
  world: { left: -500, top: -500, right: 500, bottom: 500, aspect: 1 } } });
run("stopLoop()");
out.initOn = run("!!simulation.force('clear')");
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_clearance_force_runs_only_with_tidy_spacing_on():
    done = subprocess.run(["node", "-e", SCRIPT, str(FRONTEND)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout.strip().splitlines()[-1])
    assert got == {"initDefault": False, "paramsOn": True, "paramsOff": False, "initOn": True}


def test_the_switch_is_off_by_default_and_sent_to_the_worker():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert '<input type="checkbox" id="graph-tidy">' in html
    graph = (FRONTEND / "js" / "graph.js").read_text(encoding="utf-8")
    assert '"graph-tidy": false,' in graph
    assert '"graph-tidy"' in graph[graph.index("const GRAPH_STORED_OFF") :].split("\n", 1)[0]
    canvas = (FRONTEND / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert 'tidy: prefs.get("graph-tidy", null) === "1",' in canvas
