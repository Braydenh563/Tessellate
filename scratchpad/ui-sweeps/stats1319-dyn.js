// INBOX 1319 step 2: range, tiles that open, week sparklines.
//   BASE=http://127.0.0.1:8798 [THEME=dark] node stats1319-dyn.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 }, theme: process.env.THEME });
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  const open = async () => { await page.evaluate(() => ensureModule('statistics').then(() => openStatistics())); await page.waitForTimeout(1500); };
  const out = {};
  await open();
  out.rangeDefault = await page.locator('.stats-chart').first().locator('.ask-chart-pt').count();
  await page.selectOption('#stats-range', '3'); await page.waitForTimeout(800);
  out.range3 = { points: await page.locator('.stats-chart').first().locator('.ask-chart-pt').count(), title: await page.locator('.stats-chart .ask-chart-title').first().textContent() };
  await page.selectOption('#stats-range', 'all'); await page.waitForTimeout(800);
  out.rangeAll = { points: await page.locator('.stats-chart').first().locator('.ask-chart-pt').count(), title: await page.locator('.stats-chart .ask-chart-title').first().textContent() };
  out.sparks = await page.evaluate(() => [...document.querySelectorAll('.stats-week-row')].map((r) => { const s = r.querySelector('.stats-spark'); const b = s && s.getBoundingClientRect(); return [r.dataset.stat, !!s, b && Math.round(b.width), s && s.querySelector('.stats-spark-this').getAttribute('points').split(' ').length]; }));
  out.tiles = await page.evaluate(() => [...document.querySelectorAll('.stats-tile')].map((t) => [t.tagName, t.textContent.replace(/\s+/g, ' '), t.classList.contains('is-link')]));
  const tileTargets = [['notes', 'notes'], ['documents', 'library'], ['links', 'graph'], ['no link', 'dashboard']];
  out.clicks = {};
  for (const [needle, expect] of tileTargets) {
    await page.locator('.stats-tile.is-link', { hasText: needle }).first().click(); await page.waitForTimeout(900);
    out.clicks[needle] = [await page.evaluate(() => prefs.get('activeTab', null)), expect, await page.locator('.stats-card').count()];
    await open();
  }
  for (const [needle, filter] of [['late', 'open'], ['done', 'done'], ['made', 'all']]) {
    await page.locator('.stats-tile.is-link', { hasText: new RegExp(`^\\s*\\d+\\s*${needle}`) }).first().click(); await page.waitForTimeout(900);
    out.clicks['rem-' + needle] = [await page.evaluate(() => prefs.get('activeTab', null)), await page.evaluate(() => document.querySelector('#reminder-filter .active')?.dataset.filter), filter];
    await open();
  }
  const card = await page.locator('.stats-card').boundingBox();
  out.fit = await page.evaluate(() => { const b = document.querySelector('.stats-body'); return [b.scrollWidth, b.clientWidth]; });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
