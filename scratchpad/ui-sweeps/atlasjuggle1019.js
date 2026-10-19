// Juggling stars: sample each star's transform / bounding box over 2 s. Env: BASE, MODE (buddy|large)
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', reducedMotion: process.env.RM || 'no-preference' });
  await page.evaluate((LOOK) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); const l = document.getElementById('atlas-look'); l.value = LOOK; l.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.LOOK || 'masculine');
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  if (process.env.POSE) { await page.evaluate((po) => nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: po, legs: '', x: 300, y: 380 }, true), process.env.POSE); await page.waitForTimeout(1500); }
  if (process.env.RELOOK) { await page.evaluate(async () => { for (const v of ['feminine','masculine','auto']) { const l = document.getElementById('atlas-look'); l.value = v; l.dispatchEvent(new Event('change', { bubbles: true })); await new Promise((r) => setTimeout(r, 1200)); } const b = document.getElementById('avatar-buddy'); b.value = 'cat'; b.dispatchEvent(new Event('change', { bubbles: true })); await new Promise((r) => setTimeout(r, 1200)); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); await new Promise((r) => setTimeout(r, 2000)); }); }
  if (process.env.MOODS) { await page.evaluate(async () => { for (const m of ['happy','thinking','calm']) { setAtlasMood(m); await new Promise((r) => setTimeout(r, 700)); } }); }
  if (process.env.VIEWER) { await page.evaluate(() => openNameMarkViewer(document.getElementById('nm-buddy').dataset.seed || '', { visit: true })); await page.waitForTimeout(1500); const chip = page.locator('.nm-viewer-act', { hasText: 'Juggle stars' }); console.log('chip', await chip.count()); await chip.first().click(); }
  else
  if (process.env.PERF) { await page.evaluate(() => { document.documentElement.dataset.motion = 'reduced'; document.documentElement.dataset.perf = 'on'; nameMarkBuddyMotionApply(); }); }
  if (!process.env.VIEWER) await page.evaluate(() => nameMarkBuddyAct('juggle', 5400));
  await page.waitForTimeout(600);
  const rows = [];
  for (let i = 0; i < 20; i += 1) {
    rows.push(await page.evaluate(() => {
      const st = [...document.querySelectorAll('#nm-buddy .nmp-stars > .atl-juggle')];
      const root = document.querySelector('#nm-buddy .nmp-stars');
      return { cls: document.getElementById('nm-buddy').className.match(/nmb-act-\w+/g), rootOp: root && getComputedStyle(root).opacity,
        stars: st.map((s) => { const r = s.getBoundingClientRect(); return [getComputedStyle(s).opacity, Math.round(r.left * 10) / 10, Math.round(r.top * 10) / 10, s.style.transform, getComputedStyle(s).animationName]; }) };
    }));
    await page.waitForTimeout(100);
  }
  const spread = [0, 1, 2].map((k) => { const xs = rows.map((r) => r.stars[k]?.[0]), ys = rows.map((r) => r.stars[k]?.[1]); return [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)]; });
  console.log(JSON.stringify({ first: rows[0], last: rows[19], spread }));
  await browser.close();
})();
