// graph100-1011 "Open": a hover frame at 2,000 notes is 22 to 24 ms, over the 16 ms budget.
// Moves the pointer across STEPS notes of the fitted map, one every 90 ms, and times every
// gcDraw (performance.now around the call): median, p95, max, draws. PROFILE=1 adds a CPU profile
// summary (self time by function, top 8) over the same sweep.
//   BASE=http://127.0.0.1:8797 node scratchpad/ui-sweeps/graphhover1018.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(Number(process.env.WAIT || 25000));
  const notes = await page.evaluate(() => {
    const s = gcTab, t = s.transform, r = s.canvas.getBoundingClientRect();
    return s.nodes.filter((n) => !n.isGroup).map((n) => [r.left + n.x * t.k + t.x, r.top + n.y * t.k + t.y, n.id])
      .filter(([x, y]) => x > 80 && x < 1300 && y > 140 && y < 750);
  });
  const STEPS = Number(process.env.STEPS || 40);
  const stride = Math.max(1, Math.floor(notes.length / STEPS));
  await page.evaluate(() => {
    window.__t = [];
    const d = window.gcDraw;
    window.gcDraw = function (...a) { const t0 = performance.now(); const r = d.apply(this, a); window.__t.push(performance.now() - t0); return r; };
  });
  const cdp = await page.context().newCDPSession(page);
  if (process.env.PROFILE) { await cdp.send("Profiler.enable"); await cdp.send("Profiler.start"); }
  for (let i = 0; i < STEPS; i++) {
    const [x, y] = notes[(i * stride) % notes.length];
    await page.mouse.move(x, y, { steps: 2 });
    await page.waitForTimeout(90);
  }
  const times = await page.evaluate(() => window.__t);
  const sorted = times.slice().sort((a, b) => a - b);
  const q = (p) => +sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))].toFixed(1);
  const n = await page.evaluate(() => gcTab.nodes.length);
  const out = { notes: n, draws: times.length, median: q(0.5), p95: q(0.95), max: q(1) };
  if (process.env.PROFILE) {
    const { profile } = await cdp.send("Profiler.stop");
    const dt = profile.timeDeltas; const self = new Map();
    const byId = new Map(profile.nodes.map((x) => [x.id, x]));
    profile.samples.forEach((id, i) => { const f = byId.get(id).callFrame; const k = `${f.functionName || "(anon)"}:${f.lineNumber}`; self.set(k, (self.get(k) || 0) + dt[i]); });
    out.top = [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => `${k} ${(v / 1000).toFixed(0)}ms`);
  }
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
