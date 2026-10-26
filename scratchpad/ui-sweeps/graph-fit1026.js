// Arc, tree, radial and treemap framed in the map's free area (the owner,
// 2026-10-26: "the graph arc view positioning and auto fit is off, same with
// the tree view and others"). Prints, per layout, the drawing's screen box
// against the free box (canvas minus header dock, legend, zoom dock, minimap).
const { boot } = require("./lib");
const W = +(process.env.W || 1440), H = +(process.env.H || 900);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(async () => {
    const have = (await apiJson("/entries?limit=5")).length || 0;
    if (have >= 30) return;
    const topics = ["lecture on algorithms and data structures", "gym session legs and cardio", "recipe for pasta dinner", "essay draft on history", "guitar practice chords", "meeting with tutor about exam", "budget for rent and groceries", "reading a novel chapter", "sketch ideas for poster"];
    for (let i = 0; i < 37; i++) await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `${topics[i % topics.length]} note ${i} and [[note ${(i * 7) % 37}]]` }) });
  });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(4000);
  const out = {};
  for (const layout of (process.env.LAYOUTS || "arc,tree,radial,treemap").split(",")) {
    await page.evaluate((v) => { const s = document.getElementById("graph-layout"); s.value = v; s.dispatchEvent(new Event("change", { bubbles: true })); }, layout);
    await page.waitForTimeout(2500);
    out[layout] = await page.evaluate((layout) => {
      const s = gcTab;
      const c = s.canvas.getBoundingClientRect();
      const ins = gcFitInsets(s);
      const t = d3.zoomTransform(s.svg.node());
      const free = { left: c.left + ins.left, right: c.right - ins.right, top: c.top + ins.top, bottom: c.bottom - ins.bottom };
      const box = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity };
      const add = (x, y) => { const X = c.left + t.applyX(x), Y = c.top + t.applyY(y); box.left = Math.min(box.left, X); box.right = Math.max(box.right, X); box.top = Math.min(box.top, Y); box.bottom = Math.max(box.bottom, Y); };
      for (const n of s.nodes) { if (n.corner) continue; add(n.x, n.y); }
      if (layout === "arc") for (const e of s.edges || []) { const a = e.source, b = e.target; if (!a || !b) continue; const rx = Math.abs(b.x - a.x) / 2; add((a.x + b.x) / 2, Math.min(a.y, b.y) - rx * 0.6); }
      if (layout === "treemap") for (const n of s.nodes) if (n.corner) add(n.x, n.y);
      const r = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Math.round(v)]));
      const over = { left: Math.round(free.left - box.left), right: Math.round(box.right - free.right), top: Math.round(free.top - box.top), bottom: Math.round(box.bottom - free.bottom) };
      return { k: +t.k.toFixed(3), free: r(free), drawn: r(box), overflow: over, fillW: +((box.right - box.left) / (free.right - free.left)).toFixed(2), fillH: +((box.bottom - box.top) / (free.bottom - free.top)).toFixed(2), insets: r(ins) };
    }, layout);
  }
  if (process.env.RESIZE) {
    const [w2, h2] = process.env.RESIZE.split("x").map(Number);
    await page.setViewportSize({ width: w2, height: h2 });
    await page.waitForTimeout(2500);
    out.afterResize = await page.evaluate(() => {
      const s = gcTab, c = s.canvas.getBoundingClientRect(), t = d3.zoomTransform(s.svg.node()), ins = gcFitInsets(s);
      let l = Infinity, r = -Infinity, tp = Infinity, b = -Infinity;
      for (const n of s.nodes) { const X = c.left + t.applyX(n.x), Y = c.top + t.applyY(n.y); l = Math.min(l, X); r = Math.max(r, X); tp = Math.min(tp, Y); b = Math.max(b, Y); }
      return { k: +t.k.toFixed(3), canvas: [Math.round(c.width), Math.round(c.height)], dots: [Math.round(l), Math.round(r), Math.round(tp), Math.round(b)], free: [Math.round(c.left + ins.left), Math.round(c.right - ins.right), Math.round(c.top + ins.top), Math.round(c.bottom - ins.bottom)] };
    });
  }
  const mm = await page.evaluate(() => { const m = document.querySelector("#graph-minimap, .graph-minimap"); if (!m) return null; const b = m.getBoundingClientRect(); return { id: m.id, cls: m.className, box: [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)] }; });
  out.minimap = mm;
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
