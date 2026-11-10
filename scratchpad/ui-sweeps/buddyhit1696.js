// INBOX 1696 bb: how far the drawn companion reaches past its grab box, per look and pose.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/buddyhit1696.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  const out = [];
  for (const look of (process.env.LOOKS || 'atlas,atlas-feminine,cat,fox').split(',')) {
  await page.evaluate((look) => { prefs.set('avatar-buddy', look); syncNameMarkBuddy(); }, look);
  await page.waitForTimeout(3000);
  const r = await page.evaluate(() => {
    const b = document.getElementById('nm-buddy');
    if (!b) return 'no buddy';
    const face = b.querySelector('.nm-buddy-face');
    const f = face.getBoundingClientRect();
    let u = null;
    for (const el of b.querySelectorAll('svg *, img, canvas')) {
      const q = el.getBoundingClientRect();
      if (!q.width || !q.height) continue;
      u = u ? { l: Math.min(u.l, q.left), t: Math.min(u.t, q.top), r: Math.max(u.r, q.right), b: Math.max(u.b, q.bottom) } : { l: q.left, t: q.top, r: q.right, b: q.bottom };
    }
    // Probe a grid over the drawn union: which points does a press reach the face?
    let drawnMiss = 0, n = 0;
    for (let x = u.l; x <= u.r; x += 4) for (let y = u.t; y <= u.b; y += 4) {
      const hit = document.elementFromPoint(x, y);
      const onFig = [...b.querySelectorAll('svg path, svg ellipse, svg circle, svg rect, svg polygon, svg use')].some((el) => { const q = el.getBoundingClientRect(); return x >= q.left && x <= q.right && y >= q.top && y <= q.bottom; });
      if (!onFig) continue;
      n++;
      if (!hit || !hit.closest('#nm-buddy')) drawnMiss++;
    }
    return { pose: b.dataset.pose, look: b.dataset.look || b.className, face: [f.left, f.top, f.width, f.height].map(Math.round), drawn: u && [u.l - f.left, u.t - f.top, u.r - f.right, u.b - f.bottom].map(Math.round), probes: n, missOnDrawn: drawnMiss };
  });
  console.log(look, JSON.stringify(r));
  }
  await browser.close();
})();
