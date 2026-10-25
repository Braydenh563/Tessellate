const { openFresh, seedMixed } = require("./wb3-lib.js");
(async () => {
  const env = await openFresh(); const { page } = env;
  const ids = await seedMixed(page, env.board.id); await env.open(env.board.id);
  const r = await page.evaluate(() => { const c = document.getElementById("whiteboard-container"); const b = c.getBoundingClientRect(); return { w: b.width, h: b.height, l: b.left, t: b.top }; });
  const T = () => page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return [t.x, t.y, t.k]; });
  const screenOf = (bx, by, t) => [bx * t[2] + t[0], by * t[2] + t[1]];
  const sel = async (kind, id) => page.evaluate(([k, i]) => selectWbItem(k, i), [kind, id]);
  const out = [];
  // no selection, pointer on board
  await page.evaluate(() => wbZoomToFit({ animate: false })); await page.waitForTimeout(300);
  await page.mouse.move(r.l + 300, r.t + 200); await page.waitForTimeout(100);
  let t0 = await T(); const boardPt = [(300 - t0[0]) / t0[2], (200 - t0[1]) / t0[2]];
  await page.keyboard.press("Control+Equal"); await page.waitForTimeout(500);
  let t1 = await T(); let s = screenOf(...boardPt, t1);
  out.push(["pointer anchor", t1[2] > t0[2] && Math.abs(s[0] - 300) < 2 && Math.abs(s[1] - 200) < 2, `k ${t0[2].toFixed(2)}->${t1[2].toFixed(2)} pt ${s.map(Math.round)}`]);
  // selection
  await sel("object", ids.b); await page.waitForTimeout(200);
  const cen = await page.evaluate(() => { const b = wbSelectionBounds(); return [b.minX + b.width / 2, b.minY + b.height / 2]; });
  t0 = await T(); const before = screenOf(...cen, t0);
  await page.keyboard.press("Control+Minus"); await page.waitForTimeout(500);
  t1 = await T(); s = screenOf(...cen, t1);
  out.push(["selection anchor", t1[2] < t0[2] && Math.abs(s[0] - before[0]) < 2 && Math.abs(s[1] - before[1]) < 2, `k ${t0[2].toFixed(2)}->${t1[2].toFixed(2)} drift ${(s[0]-before[0]).toFixed(1)},${(s[1]-before[1]).toFixed(1)}`]);
  // button with selection
  t0 = await T();
  await page.click("#wb-zoom-in"); await page.waitForTimeout(600);
  t1 = await T(); s = screenOf(...cen, t1); const b2 = screenOf(...cen, t0);
  out.push(["button selection", t1[2] > t0[2] && Math.abs(s[0] - b2[0]) < 2, `k ${t0[2].toFixed(2)}->${t1[2].toFixed(2)}`]);
  // ctrl+wheel about pointer
  await page.evaluate(() => { wbMultiSelection.clear(); wbSelectedItem = null; wbApplySelectionHighlight?.(); });
  await page.mouse.move(r.l + 700, r.t + 400); t0 = await T(); const bp = [(700 - t0[0]) / t0[2], (400 - t0[1]) / t0[2]];
  await page.keyboard.down("Control"); await page.mouse.wheel(0, -200); await page.keyboard.up("Control"); await page.waitForTimeout(500);
  t1 = await T(); s = screenOf(...bp, t1);
  out.push(["ctrl+wheel pointer", t1[2] > t0[2] && Math.abs(s[0] - 700) < 2 && Math.abs(s[1] - 400) < 2, `k ${t0[2].toFixed(2)}->${t1[2].toFixed(2)}`]);
  for (const [l, ok, d] of out) console.log(ok ? "PASS" : "FAIL", l, d);
  await env.browser.close();
})();
