// INBOX 1696 bb, lead: a press on the companion outside its grab handle (tail, prop) starts a text
// selection, and a pull toward the window's edge is the browser's selection autoscroll.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('dashboard'); });
  await page.waitForTimeout(3000);
  const spots = await page.evaluate(() => {
    const b = document.getElementById('nm-buddy'); const face = b.querySelector('.nm-buddy-face');
    const r = b.getBoundingClientRect(); const out = [];
    for (let y = r.top - 150; y < r.bottom + 150; y += 10) for (let x = r.left - 150; x < r.right + 150; x += 10) {
      const el = document.elementFromPoint(x, y);
      if (el && b.contains(el) && !face?.contains(el)) out.push([x, y, `${el.tagName}.${String(el.className?.baseVal ?? el.className).slice(0, 30)}`]);
    }
    return { face: !!face, faceBox: face && [face.getBoundingClientRect().width, face.getBoundingClientRect().height], box: [r.width, r.height], outside: out.length, sample: out.filter((_, i) => i % Math.max(1, Math.floor(out.length / 6)) === 0).slice(0, 6) };
  });
  console.log(JSON.stringify(spots));
  for (const [x, y, what] of spots.sample) {
    const s0 = await page.evaluate(() => document.getElementById('tab-dashboard').scrollTop);
    await page.mouse.move(x, y); await page.mouse.down();
    for (let i = 1; i <= 10; i++) { await page.mouse.move(x - i * 10, Math.min(899, y + i * 60)); await page.waitForTimeout(30); }
    await page.waitForTimeout(600);
    const mid = await page.evaluate(() => ({ top: document.getElementById('tab-dashboard').scrollTop, sel: String(getSelection()).length, grabbed: nmb.grabbed }));
    await page.mouse.up(); await page.waitForTimeout(1500);
    console.log(JSON.stringify({ what, s0, ...mid }));
    await page.evaluate(() => { document.getElementById('tab-dashboard').scrollTop = 0; getSelection().removeAllRanges(); });
    await page.waitForTimeout(1500);
  }
  await browser.close();
})();
