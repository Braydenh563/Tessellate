// INBOX 601 (the owner: "make the tail seem more integrated with the body
// instead of just coming out from the butt ... smooth and biological. also
// add more movement and variation to the tail position, behaviour,
// movement"). For each look, the Atlas companion, measures:
//   - over 20s in the large view: the tail tip's travel (px, at 2.2x), the
//     behaviours it went through (`atlasTail.act`), how many distinct
//     shapes it drew, and the longest run in which the tip moved under
//     0.75px in a second;
//   - across poses and moods on the page (stand, sit, hang, float, lie,
//     walk, happy, sad, startled): whether the tail's root, and its point a
//     thirty-second along (reported only: the tail may leave the body by then), lie inside the body's own silhouette (the torso's
//     skin path, `isPointInFill` in its own space), read through every
//     transform on the way by probe points, not by assuming a matrix.
// Exits 1 when the tail is still for over 600ms (stepped at 60fps over 60s;
// in real time too when the run drew 20 frames a second), visits fewer than 2
// behaviours, or its root leaves the body in any pose.
//   BASE=... LOOKS=masculine,feminine THEME=dark node atlas601-tail.js
const { boot } = require('./lib.js');
(async () => {
  const fails = [];
  const out = {};
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
    // Where a point of the tail's drawing is on screen, and whether a
    // screen point is inside the torso: each through probe points.
    await page.evaluate(() => {
      const NS = 'http://www.w3.org/2000/svg';
      window.__screen = (g, x, y) => {
        const c = document.createElementNS(NS, 'circle');
        c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 0.01);
        g.appendChild(c);
        const r = c.getBoundingClientRect();
        c.remove();
        return [r.left + r.width / 2, r.top + r.height / 2];
      };
      window.__inBody = (box, sx, sy) => {
        const torso = box.querySelector('.atl-layer-body .atl-fills .nmb-torso > path.atl-skin');
        const g = torso.parentNode;
        const o = window.__screen(g, 0, 0); const ex = window.__screen(g, 10, 0); const ey = window.__screen(g, 0, 10);
        const a = (ex[0] - o[0]) / 10; const b = (ex[1] - o[1]) / 10; const c = (ey[0] - o[0]) / 10; const d = (ey[1] - o[1]) / 10;
        const det = a * d - b * c;
        const dx = sx - o[0]; const dy = sy - o[1];
        const lx = (d * dx - c * dy) / det; const ly = (-b * dx + a * dy) / det;
        return { inside: torso.isPointInFill(new DOMPoint(lx, ly)), at: [+lx.toFixed(2), +ly.toFixed(2)] };
      };
      window.__root = (box) => {
        const tail = box.atlasTail;
        const g = box.querySelector('svg.atl-layer-tail:not(.atl-layer-tail-tip) .atl-fills .atl-tail-swish');
        const pts = tail.shape.pts;
        return [0, 1].map((i) => window.__inBody(box, ...window.__screen(g, pts[i][0], pts[i][1])));
      };
    });
    // Poses and moods on the page.
    const poses = {};
    for (const [name, how] of [
      ['stand', { pose: 'stand' }], ['sit', { pose: 'sit' }], ['hang', { pose: 'hang' }], ['float', { pose: 'float' }],
      ['lie', { act: 'lie' }], ['walk', { walk: true }], ['happy', { mood: 'happy' }], ['sad', { mood: 'sad' }], ['startled', { mood: 'surprised' }],
    ]) {
      poses[name] = await page.evaluate(async (how) => {
        const buddy = document.getElementById('nm-buddy');
        const box = buddy.querySelector('.atl-figure-box');
        nameMarkBuddyAct('');
        setAtlasMood('calm', 0, { quiet: true });
        buddy.classList.remove('nmb-walking');
        nameMarkBuddyMoveTo(buddy, { kind: 'card', pose: how.pose || 'stand', legs: '', x: 600, y: 400 }, true);
        if (how.act) nameMarkBuddyAct(how.act, 20000);
        if (how.mood) setAtlasMood(how.mood, 20000, { quiet: true });
        if (how.walk) buddy.classList.add('nmb-walking');
        const seen = [];
        for (let i = 0; i < 6; i += 1) {
          await new Promise((r) => setTimeout(r, 400));
          seen.push(window.__root(box));
        }
        buddy.classList.remove('nmb-walking');
        return { act: box.atlasTail.act, root: seen.every((s) => s[0].inside), near: seen.every((s) => s[1].inside), at: (seen.find((s) => !s[0].inside || !s[1].inside) || seen[seen.length - 1]).map((s) => s.at), bad: seen.map((s, i) => (s[0].inside && s[1].inside ? "" : i)).join("") };
      }, how);
      if (!poses[name].root) fails.push(`${look} ${name}: the tail's root left the body (${JSON.stringify(poses[name].at)})`);
    }
    // 20s in the large view, with a poke at 2s.
    await page.evaluate(() => { nameMarkBuddyAct(''); setAtlasMood('calm', 0, { quiet: true }); });
    await page.evaluate(() => document.querySelector('#nm-buddy .nm-buddy-face').dispatchEvent(new MouseEvent('dblclick', { bubbles: true })));
    await page.waitForTimeout(800);
    const life = await page.evaluate(async () => {
      const box = document.querySelector('.nm-viewer .atl-figure-box');
      const tail = box.atlasTail;
      const g = box.querySelector('svg.atl-layer-tail:not(.atl-layer-tail-tip) .atl-fills .atl-tail-swish');
      const tip = () => { const p = tail.shape.pts; return window.__screen(g, p[p.length - 1][0], p[p.length - 1][1]); };
      const acts = new Set();
      const shapes = new Set();
      const t0 = performance.now();
      let anchor = tip(); let anchorT = 0; let still = 0; let stillAt = 0; let minX = 1e9; let maxX = -1e9; let minY = 1e9; let maxY = -1e9;
      let poked = false;
      while (performance.now() - t0 < 20000) {
        await new Promise((r) => setTimeout(r, 50));
        const t = performance.now() - t0;
        if (!poked && t > 2000) { box.querySelector('.name-mark')?.dispatchEvent(new MouseEvent('click', { bubbles: true })); poked = true; }
        acts.add(tail.act);
        shapes.add(box.querySelector('svg.atl-layer-tail .atl-fills .atl-skin').getAttribute('d').length + ':' + box.querySelector('svg.atl-layer-tail .atl-fills .atl-skin').getAttribute('d').slice(40, 70));
        const p = tip();
        minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]); minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
        if (Math.hypot(p[0] - anchor[0], p[1] - anchor[1]) > 0.75) {
          if (t - anchorT > still) { still = t - anchorT; stillAt = t; }
          anchor = p; anchorT = t;
        }
      }
      still = Math.max(still, 20000 - anchorT);
      return { acts: [...acts], shapes: shapes.size, tipRange: [+(maxX - minX).toFixed(1), +(maxY - minY).toFixed(1)], stillMs: Math.round(still), stillEndsAt: Math.round(stillAt) };
    });
    // The same reading with the clock stepped by hand at 60 frames a second
    // over 60s of the tail's own time: the motion's design, whatever the
    // machine's load (a loaded run draws four frames a second and reads the
    // frame rate, not the tail). `fps` above is the real run's draws.
    life.fps = +(life.shapes / 20).toFixed(1);
    life.sim = await page.evaluate(() => {
      const box = document.querySelector('.nm-viewer .atl-figure-box');
      const tail = box.atlasTail;
      const g = box.querySelector('svg.atl-layer-tail:not(.atl-layer-tail-tip) .atl-fills .atl-tail-swish');
      const tip = () => { const p = tail.shape.pts; return window.__screen(g, p[p.length - 1][0], p[p.length - 1][1]); };
      cancelAnimationFrame(tail.raf);
      const t0 = performance.now();
      let anchor = tip(); let anchorT = 0; let still = 0; let n = 0; let during = ''; const acts = new Set();
      for (let t = 0; t <= 60000; t += 1000 / 60) {
        atlasTailFrame(tail, t0 + t);
        cancelAnimationFrame(tail.raf);
        acts.add(tail.act);
        if (n++ % 3) continue;
        const p = tip();
        if (Math.hypot(p[0] - anchor[0], p[1] - anchor[1]) > 0.75) {
          if (t - anchorT > still) { still = t - anchorT; during = `${tail.act} ${Object.entries(tail.p).map(([k, j]) => `${k} ${j.x.toFixed(2)}`).join(' ')}`; }
          anchor = p; anchorT = t;
        }
      }
      tail.at = 0;
      tail.raf = requestAnimationFrame((t) => atlasTailFrame(tail, t));
      return { stillMs: Math.round(Math.max(still, 60000 - anchorT)), acts: acts.size, during };
    });
    out[look] = { poses, life };
    console.log(look, JSON.stringify(out[look]));
    if (life.sim.stillMs > 600) fails.push(`${look}: the tail's tip still for ${life.sim.stillMs}ms (stepped)`);
    if (life.fps >= 20 && life.stillMs > 600) fails.push(`${look}: the tail's tip still for ${life.stillMs}ms at ${life.fps}fps`);
    if (life.acts.length < 2) fails.push(`${look}: one behaviour in 20s (${life.acts})`);
    await browser.close();
  }
  console.log(fails.length ? `FAIL\n  ${fails.join('\n  ')}` : 'ok');
  process.exit(fails.length ? 1 : 0);
})();
