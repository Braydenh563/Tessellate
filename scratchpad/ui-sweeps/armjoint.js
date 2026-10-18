// companion-1018 (BACKLOG 2026-10-12: "Atlas's right arm still looks disconnected from the body"):
// the arm's root against the torso, per look, side and pose, over time. The arm outline's cut
// end at the shoulder (the closing line of the stem: its first point to its last explicit one) are taken through every transform on
// the way to the screen and into the torso path's own space; "out" is how far each lies outside the
// torso's fill (0 inside), by the distance to the torso outline sampled every 0.5 units. The arm is
// meant to leave the torso, so only the cut end matters: any of its points outside the torso is
// the background showing between arm and body. Samples each 100 ms for SECS of idle in each of the three arm variants, then each pose
// (POSES) and each act (ACTS) in the large view at 1x. Reports the worst out per look and side (drawing units and px).
// Env: BASE, LOOKS (masculine,feminine), POSES, ACTS, SECS (3 per variant), MAX (0.6 units).
const { boot } = require('./lib.js');
const MAX = Number(process.env.MAX || 0.6);
(async () => {
  const fails = [];
  for (const look of (process.env.LOOKS || 'masculine,feminine').split(',')) {
    const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
    await page.evaluate((look) => {
      localStorage.setItem('atlas-look', look);
      document.documentElement.dataset.avatarMotion = 'always';
      localStorage.removeItem('nm-buddy-spots');
      const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true }));
    }, look);
    await page.waitForTimeout(3500);
    const res = await page.evaluate(async ({ secs, poses, acts }) => {
      const buddy = document.getElementById('nm-buddy');
      const body = buddy.querySelector('svg.atl-layer-body');
      const torso = body.querySelector('.atl-fills .nmb-torso path.atl-skin');
      const worst = {};
      const dist = (el, px, py) => {
        const L = el.getTotalLength(); let best = 1e9;
        for (let s = 0; s <= L; s += 0.5) { const q = el.getPointAtLength(s); best = Math.min(best, Math.hypot(q.x - px, q.y - py)); }
        return best;
      };
      const sample = (tag) => {
        for (const side of ['l', 'r']) {
          const path = body.querySelector(`.atl-fills .nmb-arm-${side}.atl-rigged > path.atl-skin`) || body.querySelector(`.atl-fills .nmb-arm-${side}:not(.atl-arm-probe) > path.atl-skin`);
          if (!path || !torso) continue;
          // The cut at the shoulder is the closing line of the stem's outline: from its last
          // explicit point to its first. Sampled along its length (11 points), each through
          // every transform into the torso's space.
          const nums = path.getAttribute('d').match(/-?\d*\.?\d+/g).map(Number);
          const A = { x: nums[0], y: nums[1] }; const B = { x: nums[nums.length - 2], y: nums[nums.length - 1] };
          const toScreen = path.getScreenCTM(); const fromScreen = torso.getScreenCTM().inverse();
          let out = 0;
          for (let i = 0; i <= 10; i += 1) {
            const p = { x: A.x + (B.x - A.x) * i / 10, y: A.y + (B.y - A.y) * i / 10 };
            const tp = new DOMPoint(p.x, p.y).matrixTransform(toScreen).matrixTransform(fromScreen);
            if (!torso.isPointInFill(tp)) out = Math.max(out, dist(torso, tp.x, tp.y));
          }
          const k = `${side} ${tag.split(':')[0]}`;
          const scale = toScreen.a || 1;
          if (!worst[k] || out > worst[k].out) worst[k] = { out: +out.toFixed(2), px: +(out * Math.abs(scale)).toFixed(2), at: tag };
        }
      };
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      // Each way to hold the arms (`data-atlas-variant`, 0 to 2) at rest, eased in first.
      for (const v of [0, 1, 2]) {
        buddy.dataset.atlasVariant = String(v); await sleep(900);
        for (let i = 0; i < secs * 10; i += 1) { sample(`variant${v}:${i}`); await sleep(100); }
      }
      buddy.dataset.atlasVariant = '0';
      for (const pose of poses) {
        buddy.dataset.pose = pose; buddy.dataset.legs = '';
        for (let i = 0; i < 12; i += 1) { sample(`pose-${pose}:${i}`); await sleep(100); }
      }
      buddy.dataset.pose = 'stand';
      for (const act of acts) {
        buddy.classList.add(`nmb-act-${act}`);
        for (let i = 0; i < 14; i += 1) { sample(`act-${act}:${i}`); await sleep(100); }
        buddy.classList.remove(`nmb-act-${act}`);
        await sleep(400);
      }
      return { worst, torso: !!torso };
    }, { secs: Number(process.env.SECS || 3), poses: (process.env.POSES || 'sit,float,hang,lie,curl,lean').split(','), acts: (process.env.ACTS || 'wave,bell,facepalm,shrug,stretch').split(',') });
    const rows = Object.entries(res.worst).sort((a, b) => b[1].out - a[1].out);
    console.log(look, 'torso found', res.torso, 'worst', JSON.stringify(rows.slice(0, Number(process.env.TOP || 8)).map(([k, v]) => `${k} ${v.out}u ${v.px}px @${v.at}`)));
    for (const [k, v] of rows) if (v.out > MAX) fails.push(`${look} ${k} ${v.out}`);
    await browser.close();
  }
  if (fails.length) { console.log('FAIL over', MAX, fails.join('; ')); process.exit(1); }
  console.log('PASS');
})();
