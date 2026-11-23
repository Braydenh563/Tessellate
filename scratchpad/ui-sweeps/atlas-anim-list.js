// Probe (L-ui-modernisation-201): which animations run on the idle Atlas, sampled over 6 s.
const { boot, pinFullFigure } = require('./lib');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await pinFullFigure(page);
  await page.evaluate(async () => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(8000);
  const seen = {};
  for (let i = 0; i < 30; i++) {
    const got = await page.evaluate(() => document.getAnimations().map((a) => {
      const t = a.effect && a.effect.target; const tag = t ? `${t.tagName.toLowerCase()}${t.id ? '#' + t.id : ''}.${[...(t.classList || [])].slice(0, 2).join('.')}` : '?';
      const props = a.effect ? [...new Set(a.effect.getKeyframes().flatMap((k) => Object.keys(k).filter((x) => !['offset', 'easing', 'composite', 'computedOffset'].includes(x))))].join('+') : '';
      return `${a.constructor.name}:${a.animationName || a.transitionProperty || ''}:${props}:${tag}:${Math.round(a.effect?.getTiming().duration || 0)}:${a.effect?.getTiming().iterations}`;
    }));
    for (const g of got) seen[g] = (seen[g] || 0) + 1;
    await page.waitForTimeout(200);
  }
  for (const [k, v] of Object.entries(seen).sort((a, b) => b[1] - a[1])) console.log(v, k);
  await browser.close();
})();
