// INBOX 1696 (q): "documents.js SCRIPT[src=codemirror.min.js].onload 106ms (forced layout 42ms)" on notes.
// Boots at 4x CPU on the notes tab and prints every long-animation-frame script naming codemirror.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/cmload1696q.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await page.evaluate(() => {
    window.__loaf = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) for (const s of e.scripts) window.__loaf.push({ inv: s.invoker, fn: s.sourceFunctionName, dur: Math.round(s.duration), forced: Math.round(s.forcedStyleAndLayoutDuration), frame: Math.round(e.duration) }); }).observe({ type: 'long-animation-frame', buffered: true });
  });
  await page.evaluate(() => switchTab("notes")); await page.waitForTimeout(1500); await page.click("#entry-content");
  await page.waitForTimeout(8000);
  console.log(JSON.stringify(await page.evaluate(() => ({ cm: !!window.CM6, loaf: window.__loaf }))));
  await browser.close();
})();
