// The owner (2026-09-27): "instead the slight position displacements, the
// companion instead walks or jumps, fly, to the new position ... if it is
// further away then it will teleport ... no sudden movements". For each kind
// of move (a small step, a walk, a far move, its panel jumping under it)
// samples the drawn figure every frame and reports: how it went (the
// locomotion declared: nmb-walking, a poof, a hop or float animation), the
// largest frame-to-frame move while it could be seen, the largest change of
// speed between frames (a velocity jump), and whether it ended where it was
// sent. Env: KIND (atlas|me), VW, VH.
// Exits 1 when a visible frame moves over 14px, or the speed changes by over
// 8px a frame in one frame, or a move does not end at its place.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const KIND = process.env.KIND || 'me';

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.waitForTimeout(6000);
  const cases = [['step', 22], ['walk', 160], ['far', 640], ['panel', 40]];
  const rows = [];
  for (const [name, dist] of cases) {
    const row = await page.evaluate(async ([name, dist]) => {
      const buddy = document.getElementById('nm-buddy');
      const char = buddy.querySelector('.nm-buddy-char');
      nameMarkBuddyAct('');
      // A clean start: on the bottom bar, mid-window, nothing glued.
      const bar = nameMarkBuddyLedges().bottom;
      const y0 = Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1);
      nameMarkBuddyMoveTo(buddy, { x: 200, y: y0, pose: 'stand', kind: 'bar' }, true);
      await new Promise((r) => setTimeout(r, 1200));
      const log = [];
      const sample = () => {
        const r = char.getBoundingClientRect();
        let op = 1;
        for (let el = char; el && el !== document.body; el = el.parentElement) op *= Number(getComputedStyle(el).opacity);
        log.push({ t: performance.now(), x: r.left, y: r.top, op, how: buddy.classList.contains('nmb-poofing') ? 'poof' : buddy.classList.contains('nmb-walking') ? 'walk' : (nmb.hopAnim && nmb.hopAnim.playState === 'running') ? 'hop/float' : (nmb.anim && nmb.anim.playState === 'running') ? 'anim' : '' });
      };
      let target;
      if (name === 'panel') {
        // Its panel jumps under it: glued to a box moved in one frame.
        const box = document.createElement('div');
        box.style.position = 'fixed';
        box.style.left = '180px';
        box.style.top = '300px';
        box.style.width = '120px';
        box.style.height = '60px';
        document.body.appendChild(box);
        nameMarkBuddyMoveTo(buddy, { x: 200, y: 300 - NMB_FEET + 1, pose: 'stand', kind: 'card', anchor: box }, true);
        await new Promise((r) => setTimeout(r, 800));
        sample();
        box.style.top = `${300 + dist}px`;
        target = { x: 200, y: 300 + dist - NMB_FEET + 1 };
        nmb.sweep.nameMarkBuddyKeepUp();
        window.__box = box;
      } else {
        target = { x: 200 + dist, y: y0 };
        nameMarkBuddyMoveTo(buddy, { x: target.x, y: y0, pose: 'stand', kind: 'bar' });
      }
      const t0 = performance.now();
      await new Promise((resolve) => {
        const tick = () => { sample(); if (performance.now() - t0 < 2200) requestAnimationFrame(tick); else resolve(); };
        requestAnimationFrame(tick);
      });
      window.__box?.remove();
      window.__box = null;
      let maxStep = 0; let maxAccel = 0; let prevV = null; let maxFade = 0; const hows = new Set();
      for (let i = 1; i < log.length; i += 1) {
        const a = log[i - 1]; const b = log[i];
        if (b.how) hows.add(b.how);
        // A poof shrinks the figure as it fades (its box moves with the
        // scale, not the place): there, only the fade is judged, per frame.
        if (a.how === 'poof' || b.how === 'poof') { maxFade = Math.max(maxFade, Math.abs(b.op - a.op)); prevV = null; if (b.how) hows.add(b.how); continue; }
        const seen = a.op > 0.05 && b.op > 0.05;
        const dt = Math.max(1, b.t - a.t) / 16.7;
        const vx = (b.x - a.x) / dt; const vy = (b.y - a.y) / dt;
        const step = Math.hypot(vx, vy);
        if (seen) maxStep = Math.max(maxStep, step);
        if (seen && prevV) maxAccel = Math.max(maxAccel, Math.hypot(vx - prevV[0], vy - prevV[1]));
        prevV = seen ? [vx, vy] : null;
      }
      const end = log[log.length - 1];
      return { name, dist, how: [...hows].join('+'), maxStepPx: Math.round(maxStep * 10) / 10, maxSpeedChangePx: Math.round(maxAccel * 10) / 10, poofMaxFadePerFrame: Math.round(maxFade * 100) / 100, endOff: Math.round(Math.hypot(nmb.x - target.x, nmb.y - target.y)), endOp: Math.round(end.op * 100) / 100 };
    }, [name, dist]);
    rows.push(row);
  }
  console.log(JSON.stringify({ kind: KIND, vw: VW, rows }));
  await browser.close();
  process.exit(rows.some((r) => r.maxStepPx > 14 || r.maxSpeedChangePx > 8 || r.poofMaxFadePerFrame > 0.35 || r.endOff > 2) ? 1 : 0);
})();
