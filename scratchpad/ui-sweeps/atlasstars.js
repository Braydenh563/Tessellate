// Atlas's throwing stars (B88b): the juggle's stars, sampled in the page's
// own coordinates, and a throw's spill. Prints, per star, its x and y range
// over the juggle in drawing units, the largest step between frames, the arm
// swing, and over a throw the stars' opacity and fall.
// Env: BASE, RATE (1), BEFORE_DIR (lib.js `routeBefore`).
const { boot, routeBefore } = require('./lib.js');
const RATE = Number(process.env.RATE || 1);
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await routeBefore(ctx, page);
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const juggle = await page.evaluate(() => new Promise((done) => {
    const box = document.querySelector('#nm-buddy .atl-figure-box');
    const stars = [...box.querySelectorAll('.atl-layer .nmp-stars > .atl-juggle')];
    const root = box.querySelector('.atl-layer .nmp-stars');
    const svg = root.ownerSVGElement;
    const arms = [...box.querySelectorAll('.atl-layer-body .nmb-arm-l.atl-rigged, .atl-layer-body .nmb-arm-r.atl-rigged')];
    nameMarkBuddyAct('juggle', 4000);
    const pts = stars.map(() => []);
    const sh = [];
    const t0 = performance.now();
    let frames = 0;
    const step = () => {
      frames += 1;
      const inv = svg.getScreenCTM().inverse();
      for (const [k, s] of stars.entries()) {
        const r = s.querySelector('.atl-juggle-star').getBoundingClientRect();
        const p = new DOMPoint(r.left + r.width / 2, r.top + r.height / 2).matrixTransform(inv);
        pts[k].push([+p.x.toFixed(1), +p.y.toFixed(1)]);
      }
      sh.push(arms.map((a) => a.style.transform));
      if (performance.now() - t0 < 3500) requestAnimationFrame(step);
      else done({ count: stars.length, frames, shown: getComputedStyle(root).opacity, pts, sh: sh.slice(30, 34), fps: +(frames / 3.5).toFixed(1) });
    };
    requestAnimationFrame(step);
  }));
  const sum = juggle.pts.map((pts) => {
    const xs = pts.slice(20).map((p) => p[0]);
    const ys = pts.slice(20).map((p) => p[1]);
    const steps = pts.slice(20).map((p, i, a) => (i ? Math.abs(p[0] - a[i - 1][0]) + Math.abs(p[1] - a[i - 1][1]) : 0));
    return { x: [Math.min(...xs), Math.max(...xs)], y: [Math.min(...ys), Math.max(...ys)], maxStep: +Math.max(...steps).toFixed(1) };
  });
  console.log(JSON.stringify({ juggle: { count: juggle.count, frames: juggle.frames, fps: juggle.fps, shown: juggle.shown, stars: sum, arms: juggle.sh } }));
  await page.waitForTimeout(1500);
  const thrown = await page.evaluate(() => new Promise((done) => {
    const box = document.querySelector('#nm-buddy .atl-figure-box');
    const stars = [...box.querySelectorAll('.atl-layer .nmp-stars > .atl-juggle')];
    const root = box.querySelector('.atl-layer .nmp-stars');
    nameMarkBuddyThrow(document.getElementById('nm-buddy'), 1.6, -0.9, nameMarkBuddyWorld(nameMarkBuddyTab()));
    const seen = [];
    const t0 = performance.now();
    const step = () => {
      seen.push({ t: Math.round(performance.now() - t0), shown: getComputedStyle(root).opacity, o: stars.map((s) => s.style.opacity), tr: stars[1].style.transform });
      if (performance.now() - t0 < 1400) requestAnimationFrame(step);
      else done(seen);
    };
    requestAnimationFrame(step);
  }));
  const pick = (ms) => thrown.find((s) => s.t >= ms) || thrown[thrown.length - 1];
  console.log(JSON.stringify({ thrown: [pick(30), pick(450), pick(900), pick(1300)] }));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  await browser.close();
})();
