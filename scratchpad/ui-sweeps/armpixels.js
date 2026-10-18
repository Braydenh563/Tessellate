// companion-1018: is the shoulder gap visible in pixels? At 4x device scale, Atlas at rest (arms down), the
// points of each arm's cut line that lie outside the torso's fill (armjoint.js) are read from a screenshot and
// set against the page's own background and the torso's fill beside them. A point whose colour is within
// DELTA (per channel) of the background is a hole; otherwise it is covered (the arm's glow edge or the torso).
// Env: BASE, LOOKS, THEME, SCALE (4), DELTA (10).
const { boot } = require('./lib.js');
const { execFileSync } = require('child_process');
const fs = require('fs');
const SCALE = Number(process.env.SCALE || 4);
(async () => {
  for (const look of (process.env.LOOKS || 'feminine,masculine').split(',')) {
    const { browser, page } = await boot({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: SCALE });
    await page.evaluate((look) => {
      localStorage.setItem('atlas-look', look); document.documentElement.dataset.avatarMotion = 'always'; localStorage.removeItem('nm-buddy-spots');
      const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true }));
    }, look);
    await page.waitForTimeout(3500);
    // Large view for pixels to read: Atlas at its biggest (setting 'size').
    await page.evaluate(() => { if (typeof nameMarkBuddySetSize === 'function') nameMarkBuddySetSize(2.2, false); });
    await page.waitForTimeout(1500);
    const pts = await page.evaluate(() => {
      const body = document.querySelector('#nm-buddy svg.atl-layer-body');
      const torso = body.querySelector('.atl-fills .nmb-torso path.atl-skin');
      const res = {};
      for (const side of ['l', 'r']) {
        const path = body.querySelector(`.atl-fills .nmb-arm-${side}.atl-rigged > path.atl-skin`);
        const nums = path.getAttribute('d').match(/-?\d*\.?\d+/g).map(Number);
        const A = { x: nums[0], y: nums[1] }, B = { x: nums[nums.length - 2], y: nums[nums.length - 1] };
        const toS = path.getScreenCTM(), fromS = torso.getScreenCTM().inverse();
        const list = [];
        for (let i = 0; i <= 20; i += 1) {
          const p = new DOMPoint(A.x + (B.x - A.x) * i / 20, A.y + (B.y - A.y) * i / 20).matrixTransform(toS);
          if (!torso.isPointInFill(p.matrixTransform(fromS))) list.push([p.x, p.y]);
        }
        res[side] = list;
      }
      const r = body.getBoundingClientRect();
      res.box = [r.left, r.top, r.width, r.height];
      const tb = torso.getBBox(); const tc = new DOMPoint(tb.x + tb.width / 2, tb.y + tb.height * 0.3).matrixTransform(torso.getScreenCTM()); res.torso = [tc.x, tc.y];
      return res;
    });
    const file = `${process.env.TMPDIR || '/tmp'}/armpix-${look}.png`;
    await page.screenshot({ path: file });
    const q = [];
    for (const side of ['l', 'r']) for (const [x, y] of pts[side]) q.push(Math.round(x * SCALE), Math.round(y * SCALE));
    const bgx = Math.round((pts.box[0] - 30) * SCALE), bgy = Math.round((pts.box[1] + 30) * SCALE);
    const out = execFileSync('python3', [require('path').join(__dirname, '..', 'pngpixel.py'), file, String(bgx), String(bgy), String(Math.round(pts.torso[0] * SCALE)), String(Math.round(pts.torso[1] * SCALE)), ...q.map(String)], { encoding: 'utf8' });
    console.log(look, 'cut points outside torso: l', pts.l.length, 'r', pts.r.length, '\n' + '(first line: page background, second: torso fill, then each cut point outside the torso, left arm then right)\n' + out.split('\n').slice(0, 16).join('\n'));
    await browser.close();
  }
})();
