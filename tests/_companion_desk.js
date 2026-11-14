// The desk companion's page at rest (ledger L744): restyles a minute and running animations idle, then after a pointer move.
// Prints one JSON object. Env: BASE, SWEEPS (scratchpad/ui-sweeps).
const { boot } = require(process.env.SWEEPS + '/lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
  await page.evaluate(() => { try { prefs.set('avatar-buddy', 'atlas'); } catch (e) {} });
  await page.goto(process.env.BASE + '/desktop-companion.html', { waitUntil: 'domcontentloaded' });
  await sleep(6000);
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const running = () => page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
  const a = await m();
  await sleep(12000);
  const b = await m();
  const idleRunning = await running();
  await page.mouse.move(40, 40);
  await page.mouse.move(60, 70);
  await sleep(1500);
  const awakeRunning = await running();
  const c = await m();
  await sleep(4000);
  const d = await m();
  console.log(JSON.stringify({
    idleRecalcPerMin: Math.round(((b.RecalcStyleCount - a.RecalcStyleCount) * 60) / 12),
    idleRunning, awakeRunning,
    awakeRecalcPerMin: Math.round(((d.RecalcStyleCount - c.RecalcStyleCount) * 60) / 4),
  }));
  await browser.close();
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
