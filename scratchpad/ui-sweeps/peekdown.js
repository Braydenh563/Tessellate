// The owner: "is there a peak half hidden animation for the companion like
// with the bottom bar for the top bar as well?" Hangs the companion from the
// top bar, runs `peekdown`, then `peekback`, and samples every frame how far
// the figure shows below the bar's bottom edge (the rest is clipped behind
// the bar) and whether the face's clip is on. Reports the most shown while
// peeking (the head only: well under the figure's height), how much is shown
// at the end (back to hanging), and the largest frame-to-frame change of the
// shown part. Env: KIND (atlas|me), VW, VH. Exits 1 when the peek shows more
// than half the figure or nothing, or a frame jumps over 12px.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const KIND = process.env.KIND || 'atlas';

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.waitForTimeout(5000);
  const out = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    const bar = document.getElementById('top-bar').getBoundingClientRect();
    nameMarkBuddyAct('');
    nameMarkBuddyMoveTo(buddy, { x: innerWidth - 260, y: Math.round(bar.bottom) - NMB_GRIP, pose: 'hang', kind: 'hang' }, true);
    await new Promise((r) => setTimeout(r, 1500));
    const char = buddy.querySelector('.nm-buddy-char');
    const face = buddy.querySelector('.nm-buddy-face');
    const full = char.getBoundingClientRect().height;
    const log = [];
    const t0 = performance.now();
    let phase = 'down';
    const sample = () => {
      const r = char.getBoundingClientRect();
      // Shown: the part below the bar's bottom edge. Flipped, the box is
      // above its origin; either way only what is under the edge is seen.
      const shown = Math.max(0, r.bottom - bar.bottom);
      log.push({ t: Math.round(performance.now() - t0), shown: Math.round(shown), clip: getComputedStyle(face).clipPath !== 'none', phase });
    };
    nameMarkBuddyAct('peekdown', 60000);
    await new Promise((resolve) => {
      const tick = () => { sample(); if (performance.now() - t0 < 3000) requestAnimationFrame(tick); else resolve(); };
      requestAnimationFrame(tick);
    });
    phase = 'back';
    nameMarkBuddyAct('');
    await new Promise((resolve) => {
      const t1 = performance.now();
      const tick = () => { sample(); if (performance.now() - t1 < 2200) requestAnimationFrame(tick); else resolve(); };
      requestAnimationFrame(tick);
    });
    const down = log.filter((f) => f.phase === 'down');
    const hold = down.filter((f) => f.t > 2400);
    let jump = 0;
    // The change per 16.7ms frame, not per sample: a loaded machine stalls a frame to 47ms (and fires the next
    // one 2ms later), and the per-sample step then reads the same smooth rise as 24px. Each sample is compared with
    // the last one at least 33ms older (two frames), and its change scaled to one frame.
    for (let i = 1; i < log.length; i += 1) {
      let j = i - 1;
      while (j > 0 && log[i].t - log[j].t < 33) j -= 1;
      const dt = Math.max(33, log[i].t - log[j].t);
      jump = Math.max(jump, Math.round((Math.abs(log[i].shown - log[j].shown) * 16.7) / dt));
    }
    const end = log[log.length - 1];
    return { full: Math.round(full), barBottom: Math.round(bar.bottom), peekShown: Math.max(...hold.map((f) => f.shown)), minHidden: Math.min(...down.map((f) => f.shown)), endShown: end.shown, endClip: end.clip, holdClip: hold.every((f) => f.clip), maxFrameJump: jump, act: nmb.act };
  });
  console.log(JSON.stringify({ kind: KIND, vw: VW, ...out }));
  await browser.close();
  // One line the lane runners count (they read FAIL, not the exit code alone).
  console.log((out.peekShown > out.full / 2 || out.peekShown < 8 || out.maxFrameJump > 12) ? 'FAIL peekdown: a measure above is out of bounds' : 'PASS peekdown');
  process.exit(out.peekShown > out.full / 2 || out.peekShown < 8 || out.maxFrameJump > 12 ? 1 : 0);
})();
