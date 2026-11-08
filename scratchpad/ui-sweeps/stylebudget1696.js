// Style recalc per second at rest on a tab, companion off vs each kind (INBOX 1696 l, q). RATE x CPU.
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  for (const tab of (process.env.TABS || 'dashboard').split(',')) {
    for (const kind of ['off', 'atlas', 'me']) {
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await page.evaluate(([k, t]) => { prefs.set('avatar-buddy', k); syncNameMarkBuddy(); revealTab(t); }, [kind, tab]);
      await page.waitForTimeout(3000);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
      const a = await m(); await page.waitForTimeout(4000); const b = await m();
      const per = (k) => Math.round(((b[k] - a[k]) * 1000) / 4);
      console.log(tab, kind, 'style ms/s', per('RecalcStyleDuration'), 'layout ms/s', per('LayoutDuration'), 'script ms/s', per('ScriptDuration'), 'anims', await page.evaluate(() => document.getAnimations().filter((x) => x.playState === 'running').length));
    }
  }
  await browser.close();
})();
