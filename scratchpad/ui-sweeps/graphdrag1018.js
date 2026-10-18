// graph100-1011 "Open": do a dragged note's neighbours follow it? On the real page and worker:
// six notes of 4 to 6 links are pressed, carried DIST screen px (default 200) in 10 steps, held
// 1.5 s, and the mean distance their linked notes travelled is read from the page's own graph
// state (gcTab.nodes), as a share of the distance the note in hand moved; then released and read
// again 3 s later. BASELINE=<path to an older graph-worker.js> serves that file instead, for the
// before number.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/graphdrag1018.js
const fs = require("fs");
const { boot } = require("./lib.js");
(async () => {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
  if (process.env.BASELINE) {
    const body = fs.readFileSync(process.env.BASELINE, "utf8");
    await ctx.route("**/graph-worker.js*", (route) => { console.error("worker served from BASELINE"); return route.fulfill({ status: 200, contentType: "text/javascript", body }); });
  }
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(9000);
  const picks = await page.evaluate(() => {
    const s = gcTab;
    const nb = new Map();
    for (const e of s.edges) {
      if (e.kind !== "link") continue;
      for (const [a, b] of [[e.source.id, e.target.id], [e.target.id, e.source.id]]) {
        if (!nb.has(a)) nb.set(a, new Set());
        nb.get(a).add(b);
      }
    }
    return [...nb.entries()].filter(([, l]) => l.size >= 4 && l.size <= 6).map(([id, l]) => ({ id, nb: [...l] })).slice(0, 300);
  });
  const DIST = Number(process.env.DIST || 200);
  const read = (ids) => page.evaluate((ids) => {
    const byId = new Map(gcTab.nodes.map((n) => [n.id, n]));
    return ids.map((id) => [byId.get(id).x, byId.get(id).y]);
  }, ids);
  const box = await page.evaluate(() => {
    const r = gcTab.canvas.getBoundingClientRect();
    return { x: r.left, y: r.top, width: r.width, height: r.height };
  });
  const rows = [];
  for (const p of picks) {
    if (rows.length >= 6) break;
    const on = await page.evaluate(([id, b]) => {
      const s = gcTab, t = s.transform, n = s.nodes.find((x) => x.id === id);
      const x = n.x * t.k + t.x, y = n.y * t.k + t.y;
      const hit = gcNodeAtWorld(n.x, n.y);
      return x > 60 && y > 60 && x < b.width - 60 && y < b.height - 60 && hit && hit.id === id;
    }, [p.id, box]);
    if (process.env.DEBUG) console.error('cand', p.id, on, rows.length);
    if (!on) continue;
    const ids = [p.id, ...p.nb];
    const before = await read(ids);
    const screen = await page.evaluate((id) => {
      const s = gcTab, t = s.transform, n = s.nodes.find((x) => x.id === id);
      return [n.x * t.k + t.x, n.y * t.k + t.y, t.k];
    }, p.id);
    const x0 = box.x + screen[0], y0 = box.y + screen[1];
    // Carry toward the middle of the canvas so the note stays on screen.
    const dir = [box.x + box.width / 2 - x0, box.y + box.height / 2 - y0];
    const len = Math.hypot(dir[0], dir[1]) || 1;
    const x1 = x0 + (dir[0] / len) * DIST, y1 = y0 + (dir[1] / len) * DIST;
    if (process.env.DEBUG) console.error('el', await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return e ? e.tagName + '#' + e.id + '.' + e.className : null; }, [x0, y0]));
    await page.mouse.move(x0, y0);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) { await page.mouse.move(x0 + ((x1 - x0) * i) / 10, y0 + ((y1 - y0) * i) / 10); await page.waitForTimeout(30); }
    await page.waitForTimeout(1500);
    const held = await read(ids);
    await page.mouse.up();
    // A drop on another note offers a link kind: this probe never links, it cancels.
    await page.keyboard.press('Escape');
    await page.waitForTimeout(3000);
    const rest = await read(ids);
    const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    const carried = d(held[0], before[0]);
    if (process.env.DEBUG) console.error('carried', p.id, carried);
    if (carried < 20) continue;
    const mean = (arr) => arr.slice(1).reduce((a, v, i) => a + d(v, before[i + 1]), 0) / (arr.length - 1);
    rows.push({ id: p.id, carried: Math.round(carried), held: +(mean(held) / carried).toFixed(2), rest: +(mean(rest) / carried).toFixed(2) });
  }
  const avg = (k) => +(rows.reduce((a, r) => a + r[k], 0) / rows.length).toFixed(2);
  console.log(JSON.stringify({ heldShare: avg("held"), restShare: avg("rest"), rows }));
  await browser.close();
})();
