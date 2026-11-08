// INBOX 1696 bb: a pull held at the window's bottom edge before letting go (a slow carry, not a flick).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('dashboard'); });
  await page.waitForTimeout(3000);
  for (const [tx, ty, hold] of [[700, 895, 1200], [700, 899, 1200], [5, 600, 1200], [1435, 600, 1200], [700, 3, 1200]]) {
    const r = await page.evaluate(() => { const b = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
    const s0 = await page.evaluate(() => document.getElementById('tab-dashboard').scrollTop);
    await page.mouse.move(r[0], r[1]); await page.mouse.down();
    for (let i = 1; i <= 15; i++) { await page.mouse.move(r[0] + (tx - r[0]) * i / 15, r[1] + (ty - r[1]) * i / 15); await page.waitForTimeout(30); }
    await page.waitForTimeout(hold);
    const mid = await page.evaluate(() => ({ top: document.getElementById('tab-dashboard').scrollTop, html: document.scrollingElement.scrollTop, sel: String(getSelection()).length }));
    await page.mouse.up(); await page.waitForTimeout(2500);
    const end = await page.evaluate(() => document.getElementById('tab-dashboard').scrollTop);
    console.log(JSON.stringify({ to: [tx, ty], s0, ...mid, end }));
    await page.evaluate(() => { document.getElementById('tab-dashboard').scrollTop = 0; });
  }
  await browser.close();
})();
