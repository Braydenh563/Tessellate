// Runs the worker's flat many-body and collide forces beside d3's own on the
// same notes (random, some stacked on one spot) and prints the largest
// difference in the pushes they leave; tests/test_graph_flat_forces.py wants 0.
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const root = path.resolve(__dirname, "..", "frontend");
const sandbox = { console, Math, Date, Float32Array, Map, Set, setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {}, performance: { now: () => Date.now() }, postMessage: () => {} };
sandbox.self = sandbox;
vm.createContext(sandbox);
sandbox.importScripts = (url) => vm.runInContext(fs.readFileSync(path.join(root, url.replace(/^\//, "")), "utf8"), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sandbox);
const result = vm.runInContext(`(() => {
  const out = {};
  const make = (n, seed, stacked) => {
    let s = seed;
    const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    const list = [];
    for (let i = 0; i < n; i++) {
      const dup = stacked && i % 7 === 3 && list.length;
      const src = dup ? list[i - 1] : null;
      list.push({ index: i, x: src ? src.x : (rnd() - 0.5) * 800, y: src ? src.y : (rnd() - 0.5) * 800, vx: (rnd() - 0.5) * 4, vy: (rnd() - 0.5) * 4, r: 4 + rnd() * 10 });
    }
    return list;
  };
  const run = (force, list, alpha) => { force.initialize(list, (() => { let s = 1; return () => (s = (1664525 * s + 1013904223) % 4294967296) / 4294967296; })()); force(alpha); return list.map((d) => [d.vx, d.vy]); };
  const diff = (a, b) => a.reduce((m, p, i) => Math.max(m, Math.abs(p[0] - b[i][0]), Math.abs(p[1] - b[i][1])), 0);
  const radius = (d) => d.r + 6;
  for (const [n, stacked] of [[1, false], [2, false], [60, false], [400, true], [1500, false]]) {
    const a = make(n, 11 + n, stacked), b = make(n, 11 + n, stacked);
    out["charge" + n] = diff(
      run(quadCharge().strength(-340).distanceMax(900).theta(1.1), a, 0.7),
      run(d3.forceManyBody().strength(-340).distanceMax(900).theta(1.1), b, 0.7));
    const c = make(n, 5 + n, stacked), e = make(n, 5 + n, stacked);
    out["collide" + n] = diff(run(quadCollide(radius), c, 0.5), run(d3.forceCollide().radius(radius), e, 0.5));
  }
  return out;
})()`, sandbox);
console.log(JSON.stringify(result));
