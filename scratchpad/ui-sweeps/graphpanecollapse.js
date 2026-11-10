// **The local map survives a collapse** (the owner, 2026-10-10: "I collapsed
// and opened the local map and the stuff disappeared??"). Opens a note with
// links in Notes so the local map shows, measures it (notes drawn inside the
// canvas, the camera, the canvas size and opacity), collapses it, waits,
// expands it and measures again, at once and after the layout has settled.
// Pass: onScreen after equals onScreen before (every note inside the box),
// k finite and > 0.1, opacity 1. WAIT (ms, default 2500) is the collapsed time.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // The local map is the graph bundle's (graph-canvas.js); a visit to the
  // Graph tab is what loads it, so load it as that visit would.
  await page.evaluate(() => ensureModule("graph"));
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(2500);
  const id = await page.evaluate(async () => {
    const g = await apiJson("/graph");
    const deg = new Map();
    for (const e of g.edges) for (const k of [e.source, e.target]) deg.set(k, (deg.get(k) || 0) + 1);
    return [...deg].sort((a, b) => b[1] - a[1])[0][0];
  });
  await page.evaluate((id) => flashEntry(id), id);
  await page.waitForTimeout(4000);
  const measure = (label) => page.evaluate((label) => {
    const s = graphPaneSurface, pane = document.getElementById("graph-pane");
    if (!s) return { label, none: true };
    const t = s.transform, W = s.canvas.clientWidth, H = s.canvas.clientHeight;
    const on = s.nodes.filter((n) => { const x = t.applyX(n.x), y = t.applyY(n.y); return x >= 0 && x <= W && y >= 0 && y <= H; }).length;
    return { label, hidden: pane.hidden, collapsed: pane.dataset.collapsed, nodes: s.nodes.length, onScreen: on, k: +t.k.toFixed(3), x: Math.round(t.x), y: Math.round(t.y), dims: [s.dims.w, s.dims.h], canvas: [W, H, s.canvas.width, s.canvas.height], opacity: getComputedStyle(s.canvas).opacity, finite: s.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y)) };
  }, label);
  const before = await measure("before");
  await page.click("#graph-pane-toggle");
  await page.waitForTimeout(Number(process.env.WAIT || 2500));
  const collapsed = await measure("collapsed");
  await page.click("#graph-pane-toggle");
  await page.waitForTimeout(150);
  const expanded = await measure("expanded");
  await page.waitForTimeout(3000);
  const settled = await measure("settled");
  await page.locator("#graph-pane").screenshot({ path: `${process.env.SCRATCH || "."}/shots/pane-after.png` });
  console.log(JSON.stringify({ id, before, collapsed, expanded, settled, errors }, null, 1));
  await browser.close();
})();
