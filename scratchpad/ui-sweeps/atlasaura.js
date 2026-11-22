// Atlas's aura in its large view (INBOX 536, the owner: "the companion
// background glow needs a lot of fixing"). Opens the companion's large
// view per look and theme, and measures: the figure's box on screen (every
// painted part but the glows), the aura's centre against it (as a share of
// the figure's size), and, from a screenshot of the card, the alpha of the
// glow along the card's four edges (the card's own fill subtracted: a pixel
// there that differs from the card's plain colour by more than 5% of the
// way to the aura's colour is glow touching the edge). Writes a PNG per
// case to OUT_DIR. Env: BASE, THEME, OUT_DIR. Exits 1 when the centre is
// off by more than 4% or glow reaches an edge.
const fs = require('fs');
const { boot } = require('./lib.js');
const OUT = process.env.OUT_DIR || '/tmp/atlasaura';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  let bad = 0;
  for (const [look, pose, mood] of [['feminine', 'stand', 'calm'], ['feminine', 'hang', 'sleepy'], ['feminine', 'sit', 'happy'], ['masculine', 'stand', 'calm'], ['masculine', 'hang', 'sleepy']]) {
    await page.evaluate(([look]) => {
      localStorage.setItem('atlas-look', look);
      const b = $('avatar-buddy'); b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true }));
    }, [look]);
    await page.waitForTimeout(300);
    await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
    await page.waitForTimeout(2600);
    await page.evaluate(([pose, mood]) => { window.__pose = pose; window.__mood = mood; }, [pose, mood]);
    await page.evaluate(() => {
      clearTimeout(nmb.timer);
      window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
      window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
      const buddy = document.getElementById('nm-buddy');
      nameMarkBuddyRide(null, 700, 420);
      nameMarkBuddyMoveTo(buddy, { kind: 'card', pose: window.__pose, legs: '', x: 700, y: 420 }, true);
      if (window.__mood !== 'calm') setAtlasMood(window.__mood, 0, { quiet: true });
      buddy.querySelector('.nm-buddy-face').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    });
    await page.waitForTimeout(1400);
    // Six readings 250ms apart, averaged: a hanging figure bobs, and one frame read 2.6 to 6.3% off by when it fell.
    const reads = [];
    for (let k = 0; k < 6; k += 1) {
      if (k) await page.waitForTimeout(250);
      reads.push(await page.evaluate(() => {
      const buddy = document.getElementById('nm-buddy');
      for (const a of document.querySelector('.nm-viewer-card').getAnimations({ subtree: true })) { a.pause(); a.currentTime = 1500; }
      const glow = (el) => el.closest('.atl-aura, .atl-band-haze, .atl-ear-glow, .atl-core-glow, .atl-const-glow, .atl-fx, .atl-tail-glow, defs, title, .nmb-hold, .atl-seeds, .nm-say, .atl-orbit, .atl-orbiter');
      let l = Infinity; let t = Infinity; let r = -Infinity; let b = -Infinity;
      for (const el of buddy.querySelectorAll('svg.atl-layer :is(path, ellipse, circle)')) {
        if (glow(el)) continue;
        if (Number(getComputedStyle(el).opacity) === 0) continue;
        const box = el.getBoundingClientRect();
        if (!box.width || !box.height) continue;
        l = Math.min(l, box.left); t = Math.min(t, box.top); r = Math.max(r, box.right); b = Math.max(b, box.bottom);
      }
      const auras = [...buddy.querySelectorAll('.atl-aura')].map((a) => a.getBoundingClientRect()).filter((a) => a.width);
      const a = auras[0];
      const card = document.querySelector('.nm-viewer-card').getBoundingClientRect();
      const blobs = buddy.querySelectorAll('.atl-band-haze .atl-band-cloud').length;
      return { fig: [l, t, r, b].map(Math.round), aura: a ? [a.left + a.width / 2, a.top + a.height / 2, a.width, a.height].map(Math.round) : null, card: [card.left, card.top, card.width, card.height].map(Math.round), blobs };
      }));
    }
    const avg = (key) => reads[0][key] && reads[0][key].map((_, j) => Math.round(reads.reduce((t, r) => t + r[key][j], 0) / reads.length));
    const m = { ...reads[reads.length - 1], fig: avg('fig'), aura: reads.every((r) => r.aura) ? avg('aura') : null };
    const fw = m.fig[2] - m.fig[0];
    const fh = m.fig[3] - m.fig[1];
    const off = m.aura ? [Math.abs(m.aura[0] - (m.fig[0] + fw / 2)) / fw, Math.abs(m.aura[1] - (m.fig[1] + fh / 2)) / fh] : [1, 1];
    const shot = `${OUT}/${look}-${pose}-${process.env.THEME || 'light'}.png`;
    await page.screenshot({ path: shot, clip: { x: m.card[0], y: m.card[1], width: m.card[2], height: m.card[3] } });
    // The card's edges: two pixels in from each side, sampled every 4px.
    const edge = await page.evaluate(async (src) => {
      const img = await new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = src; });
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
      const g = c.getContext('2d'); g.drawImage(img, 0, 0);
      const px = (x, y) => [...g.getImageData(x, y, 1, 1).data];
      const ref = px(Math.round(img.width / 2), img.height - 6);
      let worst = 0;
      const inset = 12;
      const pts = [];
      for (let x = inset; x < img.width - inset; x += 4) pts.push([x, inset], [x, img.height - inset]);
      for (let y = inset; y < img.height - inset; y += 4) pts.push([inset, y], [img.width - inset, y]);
      // Clear of the corners: the card is rounded and carries a resize grip
      // bottom right, neither of them glow (40 device px, 20 at 2x).
      const corner = 40;
      for (const [x, y] of pts) {
        if ((x < corner || x > img.width - corner) && (y < corner || y > img.height - corner)) continue;
        const p = px(x, y);
        worst = Math.max(worst, Math.max(...[0, 1, 2].map((k) => Math.abs(p[k] - ref[k]))));
      }
      return { worst, ref };
    }, `data:image/png;base64,${fs.readFileSync(shot).toString('base64')}`);
    // A glow at 5% alpha over the card moves a channel by about 5% of the
    // difference between the glow's colour and the card's: under 6 levels.
    const ok = off[0] <= 0.04 && off[1] <= 0.04 && edge.worst <= 6 && m.blobs === 0;
    if (!ok) bad += 1;
    console.log(ok ? 'ok ' : 'BAD', look, pose, mood, JSON.stringify({ ...m, off: off.map((v) => +v.toFixed(3)), edgeWorst: edge.worst }));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    await page.evaluate(() => setAtlasMood('calm', 0, { quiet: true }));
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS');
  await browser.close();
  process.exitCode = bad ? 1 : 0;
})();
