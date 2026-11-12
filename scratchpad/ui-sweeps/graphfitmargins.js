// **A fitted graph has even margins** (the owner, 2026-10-10: "this is my
// graph's fitted view and it is a bit off"). Opens the graph on the notebook
// already in the data dir, waits for the fit to settle, then measures the
// drawn extent (dots, placed names, topic plates) on screen against the card.
// Pass: |left - right| < 4 and |top - bottom| < 4, the limiting pair near 9% of
// the short side. Also measured after a Fit button press. BASE=..., MODE=topic
// to colour by topic (plates drawn).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  if (process.env.MODE) await page.evaluate((m) => { try { localStorage.setItem("graphColourMode", m); } catch (e) {} }, process.env.MODE);
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(7000);
  const measure = () => page.evaluate(() => {
    const s = gcTab, t = s.transform;
    let l = Infinity, r = -Infinity, tp = Infinity, b = -Infinity;
    for (const n of s.nodes) {
      if (!Number.isFinite(n.x)) continue;
      const rad = n.r || 6;
      l = Math.min(l, t.applyX(n.x - rad)); r = Math.max(r, t.applyX(n.x + rad));
      tp = Math.min(tp, t.applyY(n.y - rad)); b = Math.max(b, t.applyY(n.y + rad));
    }
    for (const box of [...(s.labelBoxes || []), ...(s.topicPlates || [])]) {
      l = Math.min(l, t.applyX(box.left)); r = Math.max(r, t.applyX(box.right));
      tp = Math.min(tp, t.applyY(box.top)); b = Math.max(b, t.applyY(box.bottom));
    }
    const W = s.dims.w, H = s.dims.h;
    return { k: +t.k.toFixed(3), left: Math.round(l), right: Math.round(W - r), top: Math.round(tp), bottom: Math.round(H - b), target: Math.round(Math.min(W, H) * 0.09), labels: (s.labelBoxes || []).length, n: s.nodes.length };
  });
  const first = await measure();
  await page.waitForTimeout(4000);
  const later = await measure();
  const alpha = await page.evaluate(() => gcTab.alpha);
  await page.evaluate(() => { gcTab.userZoomed = true; gcTab.svg.call(gcTab.zoom.translateBy, 200, 90); });
  await page.waitForTimeout(400);
  await page.evaluate(() => document.getElementById("graph-zoom-fit")?.click());
  await page.waitForTimeout(2500);
  const refit = await measure();
  console.log(JSON.stringify({ first, later, alpha, refit }));
  await browser.close();
})();
