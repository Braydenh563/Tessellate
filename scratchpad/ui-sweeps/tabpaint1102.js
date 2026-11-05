// INBOX 1534: press to next paint per tab at 4x CPU, with the layouts and style passes it cost.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.waitForTimeout(3000);
  const order = (process.env.TABS || 'dashboard,notes,chat,timeline,library').split(',');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  const res = {};
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  for (let round = 0; round < 3; round++) for (const t of order) {
    const a = await m();
    const ms = await page.evaluate((t) => new Promise((done) => { const s = performance.now(); document.getElementById(`tab-btn-${t}`).click(); requestAnimationFrame(() => setTimeout(() => done(performance.now() - s))); }), t);
    const b = await m();
    (res[t] ||= []).push(`${ms.toFixed(0)}ms L${b.LayoutCount - a.LayoutCount}/${((b.LayoutDuration - a.LayoutDuration) * 1000).toFixed(0)} S${b.RecalcStyleCount - a.RecalcStyleCount}/${((b.RecalcStyleDuration - a.RecalcStyleDuration) * 1000).toFixed(0)}`);
    await page.waitForTimeout(1200);
  }
  for (const [t, v] of Object.entries(res)) console.log(t.padEnd(10), v.join('  '));
  await browser.close();
})();
