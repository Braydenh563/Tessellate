// The owner (2026-09-27): the companion "appeared for a split second at the
// top right in front of the top bar and then it smoothly appeared, but then
// ... pretty suddenly slightly adjusted its position to perch". Also: "the
// disappearing and reappearing animation needs to be improved again".
//
// Samples the companion every animation frame from the first script on the
// page, through unlock and across tab switches: the figure's box and its
// effective opacity (the product up the tree from the figure to the band).
// Reports, per run:
//   flash   frames drawn visible (opacity > 0.05) before its first placement
//           (`nmb.x` unset), or at the band's own corner before it was put;
//   snaps   a frame-to-frame move of the drawn figure over 2px while nothing
//           animates it (no running animation on the host, rider or figure,
//           and no walking/poofing class): a jump, not travel;
//   pops    a frame-to-frame opacity change over 0.5 (a vanish or appear with
//           no fade), and entries/exits with their durations.
// Env: KIND (atlas|me), VW, VH, TABS (dashboard,notes,chat,dashboard), BASE.
// Exits 1 on any flash frame, snap or pop.
const { boot } = require('./lib.js');
const KIND = process.env.KIND || 'atlas';
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const TABS = (process.env.TABS || 'notes,chat,dashboard,notes').split(',');
const REDUCED = !!process.env.REDUCED;

(async () => {
  const { chromium } = require('playwright');
  void chromium;
  const opts = { viewport: { width: VW, height: VH } };
  if (REDUCED) opts.reducedMotion = 'reduce';
  const { browser, ctx, page } = await boot(opts);
  await ctx.addInitScript((k) => {
    try { localStorage.setItem('avatar-buddy', k); localStorage.removeItem('nm-buddy-spots'); } catch (e) {}
    const log = [];
    window.__nmbLog = log;
    const t0 = performance.now();
    window.__nmbPuts = [];
    let hooked = false;
    const tick = () => {
      if (!hooked && typeof window.nameMarkBuddyPut === 'function') {
        hooked = true;
        for (const name of ['nameMarkBuddyPut', 'nameMarkBuddyMoveTo', 'nameMarkBuddyEnter', 'syncNameMarkBuddy', 'nameMarkBuddyRideBox']) {
          const f = window[name];
          window[name] = function (...args) {
            const st = (new Error().stack || '').split('\n').slice(2, 6).map((s) => s.trim().replace(/^at /, '').replace(/\(.*\/(\w+\.js)\?[^:]*:(\d+):\d+\)/, '$1:$2')).join(' < ');
            window.__nmbPuts.push({ t: Math.round(performance.now() - t0), name, a: args.filter((x) => typeof x !== 'object').map(String).join(','), st });
            return f.apply(this, args);
          };
        }
      }
      const b = document.getElementById('nm-buddy');
      if (b) {
        const ch = b.querySelector('.nm-buddy-char') || b;
        const r = ch.getBoundingClientRect();
        let op = 1;
        let hidden = false;
        for (let el = ch; el && el !== document.body; el = el.parentElement) {
          const cs = getComputedStyle(el);
          op *= Number(cs.opacity);
          if (cs.visibility === 'hidden' || cs.display === 'none') hidden = true;
        }
        const anims = [b, b.parentElement, ch].flatMap((el) => el ? el.getAnimations() : [])
          .filter((a) => a.playState === 'running' && !(a.timeline && a.timeline.constructor && a.timeline.constructor.name === 'ScrollTimeline'));
        const moving = anims.length > 0 || b.classList.contains('nmb-walking') || b.classList.contains('nmb-poofing') || b.classList.contains('nm-buddy-dragging');
        let placed = false;
        try { placed = Number.isFinite(nmb.x); } catch (e) {}
        const tab = document.querySelector('.tab-panel.active, .tab-content.active')?.id || '';
        log.push({ t: Math.round(performance.now() - t0), x: Math.round(r.left * 10) / 10, y: Math.round(r.top * 10) / 10, w: Math.round(r.width), op: hidden ? 0 : Math.round(op * 100) / 100, moving, placed, tab });
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, KIND);
  const t = Date.now();
  await page.reload({ waitUntil: 'domcontentloaded' });
  if (await page.$('#lock-password').then((e) => e && e.isVisible())) {
    await page.fill('#lock-password', 'testpassword123');
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(9000);
  const marks = [{ what: 'boot', at: 0 }];
  for (const tab of TABS) {
    const at = await page.evaluate(() => Math.round(performance.now()));
    marks.push({ what: tab, at });
    await page.evaluate((n) => revealTab(n), tab);
    await page.waitForTimeout(6000);
  }
  const log = await page.evaluate(() => window.__nmbLog);
  const flash = [];
  const snaps = [];
  const pops = [];
  for (let i = 0; i < log.length; i += 1) {
    const f = log[i];
    if (f.op > 0.05 && (!f.placed || (f.x < 4 && f.y < 4))) flash.push(f);
    const p = log[i - 1];
    if (!p) continue;
    const d = Math.hypot(f.x - p.x, f.y - p.y);
    // Seen in both frames, and on screen (a walk-in starts past the edge).
    const on = (q) => q.op > 0.05 && q.x < VW && q.x + q.w > 0;
    const visible = on(f) && on(p);
    // A jump: over 2px with nothing animating it, or over 30px in one frame
    // whatever runs (no walk, fall or glide moves that far in 16ms; the
    // placement jumps measured before the fix were 142px and 234px).
    if (visible && ((d > 2 && !f.moving && !p.moving && Math.abs(f.w - p.w) < 2) || (d > 30 && f.t - p.t < 20))) snaps.push({ t: f.t, d: Math.round(d), from: [p.x, p.y], to: [f.x, f.y], op: f.op });
    // A cut: fully shown to gone (or back) with no frame between.
    if (Math.abs(f.op - p.op) > 0.5 && Math.max(f.op, p.op) >= 0.9 && (on(f) || on(p)) && f.t - p.t < 40) pops.push({ t: f.t, from: p.op, to: f.op, dt: f.t - p.t });
  }
  // Entries and exits: runs of op rising from ~0 to ~1 and falling back.
  const fades = [];
  let start = null;
  for (let i = 1; i < log.length; i += 1) {
    const a = log[i - 1].op; const b = log[i].op;
    if (a <= 0.05 && b > 0.05) start = { kind: 'in', t: log[i - 1].t };
    if (a >= 0.95 && b < 0.95) start = { kind: 'out', t: log[i - 1].t };
    if (start && start.kind === 'in' && b >= 0.95) { fades.push({ ...start, ms: log[i].t - start.t }); start = null; }
    if (start && start.kind === 'out' && b <= 0.05) { fades.push({ ...start, ms: log[i].t - start.t }); start = null; }
  }
  const out = { kind: KIND, vw: VW, vh: VH, reduced: REDUCED, frames: log.length, marks, flashFrames: flash.length, flash: flash.slice(0, 6), snaps, pops, fades, secs: Math.round((Date.now() - t) / 1000) };
  if (process.env.DUMP) require('fs').writeFileSync(process.env.DUMP, JSON.stringify(log));
  if (process.env.PUTS) console.error(JSON.stringify(await page.evaluate(() => window.__nmbPuts.filter((p) => p.t < Number(20000)))));
  console.log(JSON.stringify(out));
  await browser.close();
  process.exit(flash.length || snaps.length || pops.length ? 1 : 0);
})();
