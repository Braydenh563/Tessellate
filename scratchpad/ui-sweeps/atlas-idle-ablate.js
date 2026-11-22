// Probe (L-ui-modernisation-201): idle Atlas main-thread ms/s with one piece switched off at a time.
const { boot, pinFullFigure } = require('./lib');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await pinFullFigure(page);
  await page.evaluate(async () => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(6000);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const m = async () => { const r = await cdp.send('Performance.getMetrics'); const o = {}; for (const x of r.metrics) o[x.name] = x.value; return o; };
  const cpu = async (label) => { const ms = []; for (let k = 0; k < 3; k++) { const a = await m(); await page.waitForTimeout(3000); const b = await m(); ms.push(Math.round(((b.TaskDuration - a.TaskDuration) * 1000) / 3)); } ms.sort((x, y) => x - y); console.log(label, ms.join(','), 'p50', ms[1]); };
  await cpu('all'); await page.evaluate(() => { atlasRigLower.morph.px = 1; }); await cpu('px1'); await page.evaluate(() => { atlasRigLower.morph.px = 2; }); await cpu('px2'); await browser.close(); return;
  await page.evaluate(() => { window.__p = atlasRigLower.morph.pass; atlasRigLower.morph.pass = () => {}; }); await cpu('no-morph');
  await page.evaluate(() => { window.__s = atlasBlink.saccade.pace; atlasBlink.saccade.pace = () => {}; }); await cpu('no-morph-no-saccade');
  await page.evaluate(() => { document.querySelectorAll('.atl, .atl *').forEach((e) => e.getAnimations().forEach((a) => a.pause())); }); await cpu('also-anims-paused');
  await page.evaluate(() => { document.documentElement.setAttribute('data-atlas-hidden', ''); }); await cpu('hidden');
  await browser.close();
})();
