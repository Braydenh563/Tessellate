// Atlas look from the companion menu, before Settings has ever opened (owner 11-02: "I cant change atlas to feminine").
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); prefs.set('atlas-look', 'auto'); syncNameMarkBuddy(); });
  await page.waitForTimeout(800);
  const before = await page.evaluate(() => ({ body: !SETTINGS_BODY.tpl === false ? 'unbuilt' : 'built', look: atlasLook() }));
  await page.evaluate(() => nameMarkBuddyMenu(document.getElementById('nm-buddy')));
  await page.waitForTimeout(200);
  const btn = (re) => page.evaluate((src) => { const b = [...nmb.menu.querySelectorAll('button')].find((x) => new RegExp(src).test(x.textContent)); if (b) b.click(); return !!b; }, re);
  const a = await btn('Atlas look'); await page.waitForTimeout(200);
  const f = await page.evaluate(() => { const b = [...document.querySelectorAll('.action-menu button')].find((x) => /^\s*Feminine/.test(x.textContent.replace(/\s+/g,' ').trim()) && x.getBoundingClientRect().width); if (b) b.click(); return !!b; });
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => ({ pref: prefs.get('atlas-look', null), look: atlasLook() }));
  console.log(JSON.stringify({ before, a, f, after }));
  console.log(after.pref === 'feminine' && after.look === 'feminine' ? 'PASS' : 'FAIL');
  await browser.close();
})();
