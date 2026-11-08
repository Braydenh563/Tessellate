// Style ms per second each Atlas animation group costs at rest: pause the group, measure, resume (INBOX 1696 l).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('notes'); });
  await page.waitForTimeout(4000);
  const keys = await page.evaluate(() => {
    window.__key = (a) => { const kf = a.effect?.getKeyframes?.() || []; const t = a.effect?.target; return `${a.animationName || 'waapi'}:${[...new Set(kf.flatMap((k) => Object.keys(k)))].filter((p) => !['offset', 'easing', 'composite', 'computedOffset'].includes(p)).join(',')}:${t?.tagName}`; };
    return [...new Set(document.getAnimations().filter((a) => a.playState === 'running').map(__key))];
  });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  const cost = async () => { const a = await m(); await page.waitForTimeout(2000); const b = await m(); return Math.round(((b.RecalcStyleDuration - a.RecalcStyleDuration) * 1000) / 2); };
  console.log('all running', await cost());
  for (const k of keys) {
    await page.evaluate((k) => { window.__p = document.getAnimations().filter((a) => a.playState === 'running' && __key(a) === k); __p.forEach((a) => a.pause()); }, k);
    const c = await cost();
    await page.evaluate(() => __p.forEach((a) => a.play()));
    console.log(c, k);
  }
  await page.evaluate(() => document.getAnimations().forEach((a) => a.pause()));
  console.log('all paused', await cost());
  await browser.close();
})();
