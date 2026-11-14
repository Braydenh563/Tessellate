// The owner (2026-09-27): "new companion states with simple props, for
// example lying down and sleeping, reading, sitting on a beanbag, pulling
// out a chair and sitting, face palming, and other gestures, each with
// smooth transitions in and out ... it must stay cheap". Stands the
// companion on the bottom bar, runs each act, and measures: the prop shown
// (its opacity) once settled, the largest frame-to-frame move of the figure
// going in and coming out, the figure's box when settled (how far below the
// ledge it reaches), the arm against the head for a face palm, the prop gone
// and the body back after, and layouts a second while it rests in the act
// (CDP LayoutCount over 3s). Shots of each settled act go to $SCRATCH/shots.
// Env: KIND (atlas|me), VW, VH, ACTS.
// Exits 1 when a prop is not shown, a frame moves over 12px, anything is
// left behind after, or a resting act lays out more than once a second.
const { boot, OUT } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const KIND = process.env.KIND || 'me';
const ACTS = (process.env.ACTS || 'lie,read,beanbag,chair,facepalm,shrug').split(',');
const PROP = { lie: 'pillow', read: 'book', beanbag: 'beanbag', chair: 'chair' };

(async () => {
  // TOUCH=1: a coarse pointer (a tablet); THEME=dark is lib.js's own.
  const { browser, page } = await boot({ viewport: { width: VW, height: VH }, ...(process.env.TOUCH ? { hasTouch: true, isMobile: true } : {}) });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const layouts = async () => (await cdp.send('Performance.getMetrics')).metrics.find((m) => m.name === 'LayoutCount').value;
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, KIND);
  await page.waitForTimeout(6000);
  const rows = [];
  for (const act of ACTS) {
    await page.evaluate(async () => {
      const buddy = document.getElementById('nm-buddy');
      nameMarkBuddyAct('');
      const bar = nameMarkBuddyLedges().bottom;
      nameMarkBuddyMoveTo(buddy, { x: Math.round(innerWidth / 2), y: Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1), pose: 'stand', kind: 'bar' }, true);
      await new Promise((r) => setTimeout(r, 1600));
      window.__track = (ms) => new Promise((resolve) => {
        const char = buddy.querySelector('.nm-buddy-char');
        const t0 = performance.now(); let prev = null; let max = 0;
        const tick = () => {
          const r = char.getBoundingClientRect();
          const c = [r.left + r.width / 2, r.top + r.height / 2];
          if (prev) max = Math.max(max, Math.hypot(c[0] - prev[0], c[1] - prev[1]));
          prev = c;
          if (performance.now() - t0 < ms) requestAnimationFrame(tick); else resolve(Math.round(max * 10) / 10);
        };
        requestAnimationFrame(tick);
      });
    });
    const inStep = await page.evaluate((a) => { nameMarkBuddyAct(a, 60000); return window.__track(1800); }, act);
    const settled = await page.evaluate((a) => {
      const buddy = document.getElementById('nm-buddy');
      const prop = { lie: 'pillow', read: 'book', beanbag: 'beanbag', chair: 'chair' }[a];
      const el = prop ? buddy.querySelector(`.nms-${prop}`) : null;
      const char = buddy.querySelector('.nm-buddy-char').getBoundingClientRect();
      const bar = nameMarkBuddyLedges().bottom;
      const arm = buddy.querySelector(':is(.nm-figure, .atl-figure) .nmb-arm-r')?.getBoundingClientRect();
      const head = buddy.querySelector('.nm-buddy-head, .atl-head, .name-mark')?.getBoundingClientRect();
      const armToHead = arm && head ? Math.round(Math.hypot((arm.left + arm.right) / 2 - (head.left + head.right) / 2, Math.min(arm.top, arm.bottom) - (head.top + head.bottom) / 2)) : null;
      return { propOpacity: el ? Number(getComputedStyle(el).opacity) : null, belowLedge: bar ? Math.round(char.bottom - bar.top) : null, charW: Math.round(char.width), charH: Math.round(char.height), armToHead, act: nmb.act };
    }, act);
    const box = await page.evaluate(() => { const r = document.getElementById('nm-buddy').getBoundingClientRect(); return { x: r.left - 70, y: r.top - 50, width: 210, height: 170 }; });
    await page.screenshot({ path: `${OUT}/act-${KIND}-${act}.png`, clip: { x: Math.max(0, box.x), y: Math.max(0, box.y), width: box.width, height: Math.min(box.height, VH - Math.max(0, box.y)) } });
    const l0 = await layouts();
    await page.waitForTimeout(3000);
    const restLayoutsPerSec = Math.round(((await layouts()) - l0) / 3 * 10) / 10;
    const outStep = await page.evaluate(() => { nameMarkBuddyAct(''); return window.__track(1800); });
    const after = await page.evaluate((a) => {
      const buddy = document.getElementById('nm-buddy');
      const shown = [...buddy.querySelectorAll('.nms')].filter((el) => Number(getComputedStyle(el).opacity) > 0.02).map((el) => el.getAttribute('class'));
      return { leftShown: shown, charTransform: getComputedStyle(buddy.querySelector('.nm-buddy-char')).transform, unwind: buddy.classList.contains('nmb-unwind') };
    }, act);
    rows.push({ act, inStep, outStep, ...settled, restLayoutsPerSec, ...after });
  }
  console.log(JSON.stringify({ kind: KIND, vw: VW, rows }));
  await browser.close();
  const bad = rows.filter((r) => (PROP[r.act] && r.propOpacity < 0.99) || r.inStep > 12 || r.outStep > 12 || r.leftShown.length || r.charTransform !== 'none' || r.restLayoutsPerSec > 1);
  process.exit(bad.length ? 1 : 0);
})();
