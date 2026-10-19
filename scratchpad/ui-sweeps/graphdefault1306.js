// INBOX 1306: the Graph's default layout as numbers at the fit: dot overlaps,
// label overlaps, labels drawn of notes, link crossings (curved links sampled),
// how much of the canvas the map fills, and the hub's crossings.
//   bash scratchpad/ui-sweeps/serve.sh 8797 $SCRATCH/data-graph1306
//   .venv/bin/python scratchpad/ui-sweeps/seed-graph40.py 8797
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/graphdefault1306.js   (THEME=dark)
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: Number(process.env.H || 900) } });
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(500);
  await page.evaluate(() => { document.querySelectorAll('dialog[open] button').forEach((b) => /don.t check/i.test(b.textContent) && b.click()); if (!document.getElementById('graph-options').classList.contains('hidden')) document.getElementById('graph-options-toggle').click(); });
  for (let i = 0; i < 120; i++) { await page.waitForTimeout(250); if (await page.evaluate(() => gcTab.nodes.length && gcTab.ticks > 5 && gcTab.alpha < 0.002)) break; }
  await page.waitForTimeout(2000);
  await page.mouse.move(2, 2);
  const m = await page.evaluate(() => {
    const s = gcTab, t = s.transform, k = t.k, W = s.dims.w, H = s.dims.h;
    const sx = (x) => x * k + t.x, sy = (y) => y * k + t.y;
    const nodes = s.nodes.filter((n) => Number.isFinite(n.x));
    let dotOverlap = 0;
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) if (Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) < nodes[i].r + nodes[j].r) dotOverlap++;
    const boxes = (s.labelBoxes || []).map((b) => ({ id: b.id, l: sx(b.left), r: sx(b.right), t: sy(b.top), b: sy(b.bottom) }));
    let labelOverlap = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) { const a = boxes[i], b = boxes[j]; if (a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t) labelOverlap++; }
    const curved = gcCurvedLinks(s) && !s.tree;
    const edges = s.edges.filter((e) => e.source && e.target && Number.isFinite(e.source.x) && Number.isFinite(e.target.x));
    const pl = (e) => { const a = e.source, b = e.target, pts = []; if (curved) { const c = gcBowPoint(a, b); for (let i = 0; i <= 12; i++) { const u = i / 12; pts.push([(1 - u) ** 2 * a.x + 2 * (1 - u) * u * c.x + u * u * b.x, (1 - u) ** 2 * a.y + 2 * (1 - u) * u * c.y + u * u * b.y]); } } else pts.push([a.x, a.y], [b.x, b.y]); return pts; };
    const polys = edges.map((e) => ({ e, pts: pl(e) }));
    const ccw = (a, b, c) => (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0]);
    const inter = (p, q, r, u) => ccw(p, r, u) !== ccw(q, r, u) && ccw(p, q, r) !== ccw(p, q, u);
    const deg = (n) => (s.adj.get(n.id) || { size: 0 }).size;
    const hub = nodes.reduce((p, n) => (deg(n) > deg(p) ? n : p), nodes[0]);
    let cross = 0, hubCross = 0;
    for (let i = 0; i < polys.length; i++) for (let j = i + 1; j < polys.length; j++) {
      const A = polys[i], B = polys[j];
      if ([A.e.source, A.e.target].some((n) => n === B.e.source || n === B.e.target)) continue;
      let hit = false;
      for (let a = 1; a < A.pts.length && !hit; a++) for (let b = 1; b < B.pts.length && !hit; b++) hit = inter(A.pts[a - 1], A.pts[a], B.pts[b - 1], B.pts[b]);
      if (hit) { cross++; if (A.e.source === hub || A.e.target === hub || B.e.source === hub || B.e.target === hub) hubCross++; }
    }
    const xs = nodes.map((n) => sx(n.x)), ys = nodes.map((n) => sy(n.y));
    const bw = Math.max(...xs) - Math.min(...xs), bh = Math.max(...ys) - Math.min(...ys);
    // long-title weight: label px of the drawn labels
    const labelPx = boxes.reduce((p, b) => p + (b.r - b.l), 0);
    return { n: nodes.length, links: edges.length, k: +k.toFixed(2), dotOverlap, labels: boxes.length, labelOverlap, labelPx: Math.round(labelPx), crossings: cross, hubDeg: deg(hub), hubCross, fillW: +(bw / W).toFixed(2), fillH: +(bh / H).toFixed(2), fillArea: +((bw * bh) / (W * H)).toFixed(2) };
  });
  console.log(JSON.stringify(m));
  await page.screenshot({ path: (process.env.SCRATCH || '.') + `/shots/default1306-${process.env.TAG || 'run'}.png` });
  await browser.close();
})();
