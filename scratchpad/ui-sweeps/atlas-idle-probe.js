// Probe (L-ui-modernisation-201): Atlas idle CPU with parts switched off, to find the cost.
const { boot, mainCpuMs, pinFullFigure } = require('./lib');
const CSS = {
  base: '',
  notrans: '#nm-buddy, #nm-buddy * { transition: none !important; }',
  noanim: '#nm-buddy, #nm-buddy * { animation: none !important; }',
  torso: 'PAUSE:g.nmb-torso',
  svgall: 'PAUSE:svg *',
  neither: '#nm-buddy, #nm-buddy * { transition: none !important; animation: none !important; }',
};
async function one(v) {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await pinFullFigure(page);
  await page.evaluate(async (k) => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, v === 'off' ? 'off' : 'atlas');
  if (CSS[v] && CSS[v].startsWith('PAUSE:')) await page.evaluate((sel) => { const go = () => document.getAnimations().forEach((a) => { const t = a.effect && a.effect.target; if (t && t.closest('#nm-buddy') && t.matches(sel)) a.pause(); }); go(); setInterval(go, 500); }, CSS[v].slice(6));
  else if (CSS[v]) await page.evaluate((c) => { const sh = new CSSStyleSheet(); sh.replaceSync(c); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; }, CSS[v]);
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(8000);
  const c0 = await mainCpuMs(browser);
  await page.waitForTimeout(4000);
  const r = (await mainCpuMs(browser) - c0) / 4;
  await browser.close();
  return r;
}
(async () => {
  const vs = (process.env.VS || 'off,base,notrans,noanim,neither').split(',');
  for (let i = 0; i < Number(process.env.RUNS || 2); i++) for (const v of vs) console.log(i, v, (await one(v)).toFixed(0));
})();
