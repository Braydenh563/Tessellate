// K7: Arc fit puts the baseline low. Free space above the top arc vs below the labels, within 10%.
// BASE=http://127.0.0.1:PORT; W,H viewport.
const { boot } = require("./lib.js");
(async () => {
  const W = +(process.env.W || 1440), H = +(process.env.H || 900);
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(() => { try { prefs.set("graph-layout", "arc"); } catch (e) {} });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(7000);
  const m = await page.evaluate(() => {
    const s = gcTab, t = s.transform;
    const links = s.tree?.links || [];
    let base = 0;
    for (const n of s.nodes) base = n.y;
    let arcTop = t.applyY(base);
    for (const l of links) arcTop = Math.min(arcTop, t.applyY(base - Math.max((l.target.x - l.source.x) / 2, 1) * 0.6));
    let lb = t.applyY(base);
    for (const b of s.labelBoxes || []) lb = Math.max(lb, t.applyY(b.bottom));
    return { k: +t.k.toFixed(3), baselineY: Math.round(t.applyY(base)), H: s.dims.h, above: Math.round(arcTop), below: Math.round(s.dims.h - lb), links: links.length, labels: (s.labelBoxes || []).length };
  });
  console.log(JSON.stringify(m));
  await browser.close();
})();
