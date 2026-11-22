// INBOX 615 (the owner: "the atlas masculine main body and lower body are
// slightly misaligned"). For each look, the Atlas companion in its large
// view (2.2x): every 100ms over 20s of idle, then through each pose change
// (sit, float, hang, lie, walk, happy, sad, think, startled), reads the
// torso's outline (the body layer's skin path) and the lower body's (the
// lower layer's fill), each through every transform on the way (probe
// points, then an affine per element), and at the join, the rows of the
// drawing's y 54 to 56, where the torso's own edge still shows (its fade
// runs 52 to 58; below 56 it is under a third), the
// horizontal step between the two outlines on each side, in screen px.
// Exits 1 when the step is ever over MAX px at 2.2x (default 1: under a
// pixel there, under half a pixel at the companion's own size, is no step an
// eye sees; 0 exactly is not a float's, and his cloak's flare leaves the
// torso's taper at the join by 0.1 to 0.2 units of the drawing).
//   BASE=... LOOKS=masculine,feminine THEME=dark MAX=0.5 node atlas615-join.js
const { boot } = require('./lib.js');
(async () => {
  const MAX = Number(process.env.MAX || 1);
  const fails = [];
  for (const look of (process.env.LOOKS || 'masculine,feminine').split(',')) {
    const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
    await page.evaluate((look) => {
      localStorage.setItem('atlas-look', look);
      document.documentElement.dataset.avatarMotion = 'always';
      localStorage.removeItem('nm-buddy-spots');
      const b = $('avatar-buddy');
      b.value = 'atlas';
      b.dispatchEvent(new Event('change', { bubbles: true }));
    }, look);
    await page.waitForTimeout(3500);
    await page.evaluate(() => document.querySelector('#nm-buddy .nm-buddy-face').dispatchEvent(new MouseEvent('dblclick', { bubbles: true })));
    await page.waitForTimeout(1000);
    await page.evaluate(() => {
      const NS = 'http://www.w3.org/2000/svg';
      const screen = (g, x, y) => {
        const c = document.createElementNS(NS, 'circle');
        c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 0.01);
        g.appendChild(c);
        const r = c.getBoundingClientRect();
        c.remove();
        return [r.left + r.width / 2, r.top + r.height / 2];
      };
      const affine = (g) => {
        const o = screen(g, 0, 0); const ex = screen(g, 10, 0); const ey = screen(g, 0, 10);
        return (x, y) => [o[0] + ((ex[0] - o[0]) * x + (ey[0] - o[0]) * y) / 10, o[1] + ((ex[1] - o[1]) * x + (ey[1] - o[1]) * y) / 10];
      };
      const outline = (path) => {
        const map = affine(path.parentNode);
        const len = path.getTotalLength();
        return Array.from({ length: 200 }, (_, i) => { const p = path.getPointAtLength((len * i) / 200); return map(p.x, p.y); });
      };
      const sides = (pts, y) => {
        const xs = [];
        for (let i = 1; i < pts.length; i += 1) {
          const [a, b] = [pts[i - 1], pts[i]];
          if ((a[1] - y) * (b[1] - y) <= 0 && a[1] !== b[1]) xs.push(a[0] + ((y - a[1]) / (b[1] - a[1])) * (b[0] - a[0]));
        }
        return xs.length >= 2 ? [Math.min(...xs), Math.max(...xs)] : null;
      };
      window.__join = () => {
        const box = document.querySelector('.nm-viewer .atl-figure-box');
        const torso = box.querySelector('.atl-layer-body .atl-fills .nmb-torso > path.atl-skin');
        const lower = box.querySelector('.atl-layer-lower .atl-fills :is(.atl-sower-fill, .atl-ribbon-veil)');
        if (!torso || !lower) return null;
        // Both outlines in the torso's own frame (so a figure lying down is
        // measured along its own rows), the step then in screen px.
        const map = affine(torso.parentNode);
        const o = map(0, 0); const ex = map(1, 0); const ey = map(0, 1);
        const [a11, a21, a12, a22] = [ex[0] - o[0], ex[1] - o[1], ey[0] - o[0], ey[1] - o[1]];
        const det = a11 * a22 - a12 * a21;
        const local = ([sx, sy]) => { const dx = sx - o[0]; const dy = sy - o[1]; return [(a22 * dx - a12 * dy) / det, (-a21 * dx + a11 * dy) / det]; };
        const t = outline(torso).map(local);
        const l = outline(lower).map(local);
        const px = Math.hypot(a11, a21);
        let step = 0;
        window.__lastRows = [];
        for (const y of [54, 55, 56]) {
          const a = sides(t, y);
          const b = sides(l, y);
          window.__lastRows.push([y, a && a.map((v) => +v.toFixed(2)), b && b.map((v) => +v.toFixed(2))]);
          if (!a || !b) continue;
          step = Math.max(step, Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));
        }
        return +(step * px).toFixed(2);
      };
    });
    if (process.env.STATIC) {
      console.log(look, JSON.stringify(await page.evaluate(async () => { document.getAnimations().forEach((a) => a.pause()); await new Promise((r) => setTimeout(r, 300)); return [window.__join(), window.__lastRows]; })));
      await browser.close();
      continue;
    }
    let worst = { step: 0 };
    const idle = await page.evaluate(async () => {
      const out = [];
      const t0 = performance.now();
      while (performance.now() - t0 < 20000) {
        await new Promise((r) => setTimeout(r, 200));
        out.push(window.__join());
      }
      return out;
    });
    const idleMax = Math.max(...idle.filter((v) => v !== null));
    worst = { step: idleMax, what: 'idle' };
    const poses = {};
    for (const [name, how] of [
      ['sit', { pose: 'sit' }], ['float', { pose: 'float' }], ['hang', { pose: 'hang' }], ['lie', { act: 'lie' }], ['walk', { walk: true }],
      ['happy', { mood: 'happy' }], ['sad', { mood: 'sad' }], ['think', { mood: 'thinking' }], ['startled', { mood: 'surprised' }],
    ]) {
      const rows = await page.evaluate(async (how) => {
        const buddy = document.getElementById('nm-buddy');
        nameMarkBuddyAct('');
        setAtlasMood('calm', 0, { quiet: true });
        buddy.classList.remove('nmb-walking');
        if (how.pose) buddy.dataset.pose = how.pose;
        if (how.act) nameMarkBuddyAct(how.act, 20000);
        if (how.mood) setAtlasMood(how.mood, 20000, { quiet: true });
        if (how.walk) buddy.classList.add('nmb-walking');
        const out = [];
        const t0 = performance.now();
        while (performance.now() - t0 < 1800) {
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          out.push(window.__join());
        }
        buddy.classList.remove('nmb-walking');
        buddy.dataset.pose = 'stand';
        return out;
      }, how);
      poses[name] = Math.max(...rows.filter((v) => v !== null));
      if (poses[name] > worst.step) worst = { step: poses[name], what: name };
    }
    console.log(look, JSON.stringify({ idleMax, poses, worst }));
    if (worst.step > MAX) fails.push(`${look}: the torso and the lower body step ${worst.step}px apart (${worst.what})`);
    await browser.close();
  }
  console.log(fails.length ? `FAIL\n  ${fails.join('\n  ')}` : 'ok');
  process.exit(fails.length ? 1 : 0);
})();
