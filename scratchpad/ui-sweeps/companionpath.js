// INBOX 1305: the companion's position every frame for a short, medium and long move, between
// heights, and a throw. Per case: route, duration, frames, worst frame-to-frame jump (px), frames over 40px,
// min opacity. Env: BASE, KIND (me), REDUCE=1 for prefers-reduced-motion, RUNS (3).
const { boot } = require('./lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const KIND = process.env.KIND || 'me';
const RUNS = Number(process.env.RUNS || 3);
const CASES = [
  ['short 60', [300, 400], [360, 400]],
  ['short 90 diag', [300, 400], [360, 470]],
  ['medium 400', [200, 500], [600, 500]],
  ['medium 300 up', [200, 600], [450, 330]],
  ['long 1000', [100, 500], [1100, 500]],
  ['long across+height', [100, 120], [1300, 700]],
  ['long across+up', [1300, 760], [120, 160]],
];
(async () => {
  if (process.env.ONLY) CASES.length = 0;
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', reducedMotion: process.env.REDUCE ? 'reduce' : 'no-preference' });
  await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await page.evaluate(() => ensureModule('companionMenu')); await page.waitForTimeout(1500);
  await page.evaluate(() => { for (const n of ['nameMarkBuddyTick', 'nameMarkBuddyDrift', 'nameMarkBuddyErrand', 'nameMarkBuddyBored']) if (typeof window[n] === 'function') window[n] = () => {}; });
  await page.evaluate(() => {
    window.__s = { on: false, pts: [] };
    const loop = (t) => { if (__s.on) { const b = document.getElementById('nm-buddy'); const r = b.getBoundingClientRect(); __s.pts.push([t, r.left + r.width / 2, r.top + r.height / 2, +getComputedStyle(b).opacity, b.dataset.route || '']); } requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
  const put = (x, y, instant) => page.evaluate(([px, py, inst]) => {
    nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'stand', legs: '', x: px, y: py }, inst);
    nmb.placedAt = Date.now();
    const spots = nameMarkBuddySpots(); spots[nameMarkBuddyTab()] = nameMarkBuddySpotFor({ kind: 'yours', pose: 'stand', legs: '', x: px, y: py }); nameMarkBuddyKeepSpots(spots);
    return [document.getElementById('nm-buddy').dataset.route || '', !!nmb.outOfSight, nmb.x, nmb.y];
  }, [x, y, instant]);
  const sum = (pts, info) => {
    let worst = 0, over = 0, minOp = 1; const routes = new Set();
    for (let i = 1; i < pts.length; i += 1) { const d = Math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]); worst = Math.max(worst, d); if (d > 40) over += 1; }
    for (const p of pts) { minOp = Math.min(minOp, p[3]); if (p[4]) routes.add(p[4]); }
    // moving window: first to last frame whose position differs from the end by >2px
    const end = pts[pts.length - 1]; let last = 0;
    for (let i = 0; i < pts.length; i += 1) if (Math.hypot(pts[i][1] - end[1], pts[i][2] - end[2]) > 2) last = i;
    const first = pts.findIndex((p) => Math.hypot(p[1] - pts[0][1], p[2] - pts[0][2]) > 2);
    return { route: info ? info[0] : '', out: info ? info[1] : '', ms: first < 0 ? 0 : Math.round(pts[last][0] - pts[first][0]), worst: +worst.toFixed(1), over40: over, minOp: +minOp.toFixed(2) };
  };
  const out = {};
  for (const [name, a, b] of CASES) {
    out[name] = [];
    for (let r = 0; r < RUNS; r += 1) {
      await put(a[0], a[1], true); await sleep(1500);
      await page.evaluate(() => { __s.pts = []; __s.on = true; });
      const info = await put(b[0], b[1], false); await sleep(2800);
      out[name].push(sum(await page.evaluate(() => { __s.on = false; return __s.pts; }), info));
    }
  }
  // throw: flick right from (300,400)
  out.throw = [];
  for (let r = 0; r < RUNS; r += 1) {
    await put(300, 400, true); await sleep(1200);
    const f = await page.evaluate(() => { const q = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [q.left + q.width / 2, q.top + q.height / 2]; });
    await page.mouse.move(f[0], f[1]); await page.mouse.down();
    for (let i = 1; i <= 8; i += 1) { await page.mouse.move(f[0] + i * 8, f[1] - i * 3); await sleep(16); }
    for (let i = 1; i <= 5; i += 1) { await page.mouse.move(f[0] + 64 + i * 60, f[1] - 24 - i * 6); await sleep(16); }
    await page.evaluate(() => { __s.pts = []; __s.on = true; }); await page.mouse.up(); await sleep(4500);
    out.throw.push(sum(await page.evaluate(() => { __s.on = false; return __s.pts; })));
  }
  for (const [k, v] of Object.entries(out)) console.log(k.padEnd(20), v.map((x) => `${x.route || '-'} out${x.out} ${x.ms}ms worst ${x.worst} over40 ${x.over40} op ${x.minOp}`).join(' | '));
  await browser.close();
})();
