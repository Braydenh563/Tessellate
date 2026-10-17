// B62: the profile picture's enlarged view (double-click a `[data-user-mark]`).
// Samples the view: which parts animate, which faces it wears over SECS
// seconds (and as it is poked three times), whether its eyes follow the
// pointer, and the same under reduced motion (REDUCED=1).
// Env: BASE, SECS (12), REDUCED.
const { boot } = require('./lib.js');
const SECS = Number(process.env.SECS || 12);
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', reducedMotion: process.env.REDUCED ? 'reduce' : 'no-preference' });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  await page.waitForTimeout(2500);
  const faces = [];
  await page.exposeFunction('nmvFace', (f) => faces.push(f));
  await page.evaluate(() => {
    const h = document.querySelector('[data-user-mark]');
    h.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  });
  await page.waitForSelector('.nm-viewer .nm-viewer-figure', { state: 'attached' });
  await page.evaluate(() => {
    const fig = document.querySelector('.nm-viewer .nm-viewer-figure');
    const t0 = performance.now();
    new MutationObserver(() => {
      const now = fig.querySelector(':scope > .nm-figure:not(.nmv-leaving)');
      window.nmvFace([Math.round(performance.now() - t0), now?.dataset.expr || '']);
    }).observe(fig, { childList: true });
  });
  const seen = await page.evaluate((secs) => new Promise((done) => {
    const fig = document.querySelector('.nm-viewer .nm-viewer-figure');
    const by = {};
    const t0 = performance.now();
    const step = () => {
      for (const a of fig.getAnimations({ subtree: true })) {
        const el = a.effect?.target;
        const k = `${a.animationName || 'waapi'}:${(el?.getAttribute?.('class') || '').split(' ')[0]}`;
        by[k] = (by[k] || 0) + 1;
      }
      if (performance.now() - t0 < secs * 1000) setTimeout(step, 100);
      else done(by);
    };
    step();
  }), SECS);
  const box = await page.evaluate(() => { const r = document.querySelector('.nm-viewer .nm-viewer-stage').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  const before = faces.length;
  for (let i = 0; i < 3; i += 1) { await page.mouse.click(box[0], box[1]); await page.waitForTimeout(500); }
  const poked = faces.slice(before).map((f) => f[1]);
  await page.mouse.move(box[0] - 500, box[1] - 100);
  await page.waitForTimeout(400);
  const left = await page.evaluate(() => document.querySelector('.nm-viewer .nm-viewer-figure > .nm-figure:not(.nmv-leaving)').style.getPropertyValue('--nmv-x'));
  await page.mouse.move(box[0] + 500, box[1] - 100);
  await page.waitForTimeout(400);
  const right = await page.evaluate(() => document.querySelector('.nm-viewer .nm-viewer-figure > .nm-figure:not(.nmv-leaving)').style.getPropertyValue('--nmv-x'));
  await page.waitForTimeout(3000);
  const count = await page.evaluate(() => document.querySelectorAll('.nm-viewer .nm-viewer-figure > .nm-figure').length);
  console.log(JSON.stringify({ errors, reduced: !!process.env.REDUCED, faces: faces.slice(0, before), poked, follow: { left, right }, figuresAfter: count, animating: seen }));
  await browser.close();
})();
