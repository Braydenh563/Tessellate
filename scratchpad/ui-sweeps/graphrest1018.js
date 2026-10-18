// GRAPH_PLAN "the graph is not idle at rest" (OPEN 956): how long after the tab opens does the
// canvas keep drawing, and what asks for the frames? Samples per second for SECS seconds: draws,
// layouts, script ms, long tasks, and the rAF callers by name.
// CACHED=1 reloads the app onto the Graph with the positions cache warm (the usual case).
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/graphrest1018.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  const hook = () =>
    page.evaluate(() => {
      window.__rest = { draws: 0, long: 0, src: {} };
      new PerformanceObserver((l) => { window.__rest.long += l.getEntries().length; }).observe({ entryTypes: ["longtask"] });
      const raf = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = (f) => {
        const src = String(f).slice(0, 48).replace(/\s+/g, " ");
        window.__rest.src[src] = (window.__rest.src[src] || 0) + 1;
        return raf(f);
      };
      const d = window.gcDraw;
      window.gcDraw = function (...a) { window.__rest.draws++; return d.apply(this, a); };
    });
  const m = async () => Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((x) => [x.name, x.value]));
  const rows = [];
  const sample = async (secs) => {
    for (let i = 0; i < secs; i++) {
      const a = await m();
      const d0 = await page.evaluate(() => ({ ...window.__rest.src, d: window.__rest.draws, l: window.__rest.long }));
      await page.waitForTimeout(1000);
      const b = await m();
      const d1 = await page.evaluate(() => ({ ...window.__rest.src, d: window.__rest.draws, l: window.__rest.long }));
      rows.push({ t: rows.length + 1, draws: d1.d - d0.d, long: d1.l - d0.l, layouts: b.LayoutCount - a.LayoutCount,
        scriptMs: Math.round((b.ScriptDuration - a.ScriptDuration) * 1000) });
    }
  };
  await hook();
  await page.evaluate(() => switchTab("graph"));
  await sample(Number(process.env.SECS || 12));
  console.log(rows.map((r) => JSON.stringify(r)).join("\n"));
  console.log(JSON.stringify(await page.evaluate(() => window.__rest.src)));
  await browser.close();
})();
