// Who writes while the companion idles: attribute and child mutations tallied by target + attribute for 4 s.
const { boot } = require('../ui-sweeps/lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(() => prefs.set('avatar-buddy', 'atlas'));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  if (await page.locator('#lock-password').isVisible()) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(12000);
  const out = await page.evaluate(() => new Promise((res) => {
    const tally = {};
    const name = (el) => (el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className).split(' ').slice(0, 2).join('.'));
    const mo = new MutationObserver((rs) => { for (const r of rs) { const k = `${r.type}:${r.attributeName || ''}:${name(r.target)}${r.target.closest && r.target.closest('#nm-buddy') ? ' [in buddy]' : ''}`; tally[k] = (tally[k] || 0) + 1; } });
    mo.observe(document.documentElement, { attributes: true, childList: true, subtree: true, characterData: true });
    setTimeout(() => { mo.disconnect(); res(Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 14)); }, 4000);
  }));
  console.log(out.map((x) => x.join('  ')).join('\n'));
  await browser.close();
})();
