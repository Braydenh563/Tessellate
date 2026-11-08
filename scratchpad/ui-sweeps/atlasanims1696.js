// The in-app Atlas's running animations by name, with what each animates (INBOX 1696 l).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('notes'); });
  await page.waitForTimeout(4000);
  const r = await page.evaluate(() => {
    const by = {};
    for (const a of document.getAnimations()) {
      if (a.playState !== 'running') continue;
      const t = a.effect?.target; const name = a.animationName || a.transitionProperty || a.id || 'waapi';
      const kf = a.effect?.getKeyframes?.() || [];
      const props = [...new Set(kf.flatMap((k) => Object.keys(k).filter((p) => !['offset', 'easing', 'composite', 'computedOffset'].includes(p))))].join(',');
      const key = `${name} [${props}] on ${t?.tagName}${t instanceof SVGElement ? '(svg)' : ''}`;
      by[key] = (by[key] || 0) + 1;
    }
    return Object.entries(by).sort((a, b) => b[1] - a[1]);
  });
  for (const [k, n] of r) console.log(n, k);
  await browser.close();
})();
