// AT finding (L675): attribute writes a second from the corner Atlas while Settings covers it.
// Counts the loops' attribute writes (paths, transforms, styles; a mood or class change is an event,
// not a loop) under #nm-buddy over 5s: shut, Settings open, shut again. Fails over 10% covered.
//   BASE=... node atlas-covered-writes.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
  //: The select lives in a Settings pane that is built on first open (L675): set the pref and reload.
  await page.evaluate(() => prefs.set('avatar-buddy', 'atlas'));
  await page.waitForTimeout(800);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  if (await page.$('#lock-password:visible')) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; });
  await page.waitForSelector('#nm-buddy .atl-figure-box', { timeout: 15000 });
  await page.waitForTimeout(3500);
  const count = () => page.evaluate(() => new Promise((done) => {
    let n = 0; const by = {}; window.__by = by;
    const mo = new MutationObserver((r) => { for (const m of r) if (m.type === 'attributes' && !['class', 'data-atlas-mood'].includes(m.attributeName)) { n++; const k = (m.target.getAttribute('class') || m.target.tagName).split(' ')[0] + ':' + m.attributeName; by[k] = (by[k] || 0) + 1; } });
    mo.observe(document.getElementById('nm-buddy'), { attributes: true, subtree: true });
    setTimeout(() => { mo.disconnect(); done(n / 5); }, 5000);
  }));
  await page.waitForTimeout(6000);
  const open = await count();
  const tailOn = () => page.evaluate(() => { const b = document.querySelector('#nm-buddy .atl-figure-box'); return { tail: !!(b && b.atlasTail && b.atlasTail.raf), state: b?.atlasTail?.state }; });
  const t0 = await tailOn();
  await page.evaluate(() => openSettingsModal());
  await page.waitForTimeout(1500);
  const cover = await page.evaluate(() => document.getElementById('nm-buddy')?.dataset.cover || '');
  const covered = await count();
  const coveredBy = await page.evaluate(() => window.__by);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1500);
  const after = await count();
  const t1 = await tailOn();
  console.log(JSON.stringify({ uncovered_per_s: open, cover, covered_per_s: covered, after_close_per_s: after, t0, t1, coveredBy }));
  await browser.close();
  process.exit(covered > open / 10 || after < open / 2 ? 1 : 0);
})();
