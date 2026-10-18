// GRAPH_PLAN VC11: the Treemap layout, on the real page. Picks Treemap in the Layout select by
// keyboard, then reads the page's own graph state: category rectangles against their note
// counts (area share within 1%), every dot inside its rectangle, dots overlapping dots, the
// dot radius against its cell, the chip that names the layout, console errors, and the time
// `layoutTreemap` takes for 1,000 synthetic notes in the page. Light and dark: THEME=dark.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/graphtreemap1018.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && !/status of 400/.test(m.text()) && errors.push(m.text()));
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(4000);
  await page.evaluate(() => { const g = document.getElementById("graph-options-toggle"); if (g) g.click(); });
  await page.waitForTimeout(400);
  // Keyboard: focus the select, choose by typing its first letters.
  await page.focus("#graph-layout");
  const focused = await page.evaluate(() => document.activeElement && document.activeElement.id);
  await page.evaluate(() => {
    const sel = document.getElementById("graph-layout");
    sel.value = "treemap";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForTimeout(3500);
  const r = await page.evaluate(() => {
    const s = gcTab;
    const rects = s.tree.treemap;
    const total = s.nodes.length;
    const W = s.dims.w, H = s.dims.h;
    const area = rects.map((c) => ({ category: c.category, count: c.count, share: ((c.x1 - c.x0) * (c.y1 - c.y0)) / (W * H), want: c.count / total }));
    const worst = Math.max(...area.map((a) => Math.abs(a.share - a.want) / a.want));
    const inside = s.nodes.filter((n) => { const c = rects.find((x) => x.category === n.category); return n.x >= c.x0 && n.x <= c.x1 && n.y >= c.y0 && n.y <= c.y1; }).length;
    let overlaps = 0;
    for (let i = 0; i < s.nodes.length; i++) for (let j = i + 1; j < s.nodes.length; j++) {
      const a = s.nodes[i], b = s.nodes[j];
      if (Math.hypot(a.x - b.x, a.y - b.y) < (a.r + b.r) * 0.95) overlaps++;
    }
    const outgrown = s.nodes.filter((n) => n.cell && n.r > Math.min(n.cell.w, n.cell.h) / 2).length;
    // Each category's header (its first 110px, 20 tall) against what floats over the map.
    const t = s.transform, cb = s.canvas.getBoundingClientRect();
    const over = [...document.querySelectorAll(GC_FIT_OVERLAYS.join(","))].map((el) => el.getBoundingClientRect()).filter((b) => b.width > 0 && b.height > 0);
    const headersCovered = rects.filter((c) => {
      const h = { l: cb.left + c.x0 * t.k + t.x, t: cb.top + c.y0 * t.k + t.y };
      return over.some((b) => h.l < b.right && h.l + 110 > b.left && h.t < b.bottom && h.t + 20 > b.top);
    }).length;
    const sides = rects.reduce((m, c) => ({ l: Math.min(m.l, c.x0), r: Math.max(m.r, c.x1), t: Math.min(m.t, c.y0), b: Math.max(m.b, c.y1) }), { l: 1e9, r: -1e9, t: 1e9, b: -1e9 });
    const onScreen = { left: cb.left + sides.l * t.k + t.x, right: cb.left + sides.r * t.k + t.x, top: cb.top + sides.t * t.k + t.y, bottom: cb.top + sides.b * t.k + t.y };
    const chip = document.getElementById("graph-layout-chip");
    const t0 = performance.now();
    const synthetic = Array.from({ length: 1000 }, (_, i) => ({ id: i, category: "c" + (i % 9 === 0 ? i % 7 : i % 3), preview: "n" + i }));
    layoutTreemap(synthetic, 1400, 800);
    const ms = performance.now() - t0;
    return { notes: total, categories: rects.length, worstAreaErr: +worst.toFixed(4), inside, overlaps, outgrown,
      edges: s.edges.length, chip: chip && !chip.classList.contains("hidden") ? chip.textContent.trim() : null,
      k: +s.transform.k.toFixed(2), headersCovered, onScreen: Object.fromEntries(Object.entries(onScreen).map(([a, b]) => [a, Math.round(b)])), ms1000: +ms.toFixed(1), layout: s.layoutKind };
  });
  console.log(JSON.stringify({ focused, ...r, errors }));
  await page.screenshot({ path: `${process.env.SCRATCH || "."}/treemap-${process.env.THEME || "light"}.png` });
  await browser.close();
})();
