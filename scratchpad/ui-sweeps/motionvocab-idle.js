// INBOX 1506 B: what the motion vocabulary costs while nothing moves.
// Idle long tasks (PerformanceObserver "longtask") and requestAnimationFrame
// callbacks that fire while the page sits still for IDLE_MS, on the chat tab,
// after the app is open and its lazy bundles have landed. Run before and
// after a change; the two numbers must not grow.
//   LIB=$PWD/lib.js BASE=http://127.0.0.1:8873 node motionvocab-idle.js
const { boot } = require('./lib.js');
const IDLE_MS = Number(process.env.IDLE_MS || 6000);
(async () => {
  const { browser, page } = await boot({});
  await page.evaluate(() => {
    window.__idle = { raf: 0, long: 0, longMs: 0, on: false };
    const raf = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => raf((t) => { if (window.__idle.on) window.__idle.raf++; return cb(t); });
    new PerformanceObserver((l) => { if (!window.__idle.on) return; for (const e of l.getEntries()) { window.__idle.long++; window.__idle.longMs += e.duration; } })
      .observe({ entryTypes: ["longtask"] });
  });
  await page.waitForTimeout(4000);
  await page.evaluate(() => { window.__idle.on = true; });
  await page.waitForTimeout(IDLE_MS);
  const r = await page.evaluate(() => { window.__idle.on = false; return window.__idle; });
  console.log(JSON.stringify({ idleMs: IDLE_MS, rafCallbacks: r.raf, longTasks: r.long, longTaskMs: Math.round(r.longMs) }));
  await browser.close();
})();
