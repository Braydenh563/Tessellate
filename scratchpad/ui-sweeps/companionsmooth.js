// INBOX 426 (round 2, item 2): does the companion trail its panel by a frame
// under real smooth scrolling? A reading of getBoundingClientRect cannot say:
// it is the main thread's view, and a smooth or threaded scroll is drawn by
// the compositor before the main thread hears of it. So this reads the
// composited frames themselves (CDP screencast), with the card outlined in
// magenta and the companion in green, and measures, frame by frame, the
// gap between the card's top edge and the companion's box. Glued, the gap
// never changes; a frame behind, it changes by that frame's scroll.
// Three scrolls, each with the main thread kept busy 12ms a frame (a heavy
// page): 8 to 16px wheel steps every frame, a programmatic smooth scroll
// (`scrollTo({behavior: "smooth"})`), and a long fast wheel flick.
// Env: TAB (notes), CARD (#tab-notes li), BUSY (12, ms a frame), OUT (json).
// Exits 1 when more than a tenth of a phase's frames have the gap off its
// usual value by more than 1px. Measured: riding the scroll (a
// ScrollTimeline), 2 to 6% off, each a single frame at a gesture's start
// or turn, and the same with the main thread 30ms busy (so it is the
// compositor moving it); the script follow before it, 14% of wheel
// frames, 59% of smooth-scroll frames and every flick frame, by up to 262px.
const fs = require('fs');
const os = require('os');
const { boot } = require('./lib.js');
const OUT = process.env.OUT || `${os.tmpdir()}/companion-smooth.json`;
const BUSY = Number(process.env.BUSY || 12);
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const decoder = await page.context().newPage();
  await decoder.setContent('<canvas id="c"></canvas>');
  const have = await page.evaluate(async () => (await apiJson('/entries?limit=50')).length || 0).catch(() => -1);
  if (have >= 0 && have < 14) {
    await page.evaluate(async (n) => {
      for (let i = 0; i < n; i += 1) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Smooth probe note ${i}. A line of words so the card has a body to it, and a second sentence for height.` }) });
    }, 16 - have);
  }
  await page.evaluate(async () => { prefs.set('avatar-buddy', 'me'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.evaluate(() => localStorage.removeItem('nm-buddy-spots'));
  await page.evaluate((t) => revealTab(t), process.env.TAB || 'notes');
  await page.waitForTimeout(3000);
  const setup = await page.evaluate((sel) => {
    const card = [...document.querySelectorAll(sel)].find((el) => { const r = el.getBoundingClientRect(); return r.width > 200 && r.top > 330 && r.top < 520; });
    if (!card) return { error: 'no card' };
    card.dataset.probeCard = '1';
    const r = card.getBoundingClientRect();
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyIndexReset();
    const landed = nameMarkBuddyDrop(Math.round(r.left + 360), Math.round(r.top - 74));
    nameMarkBuddyMoveTo(buddy, landed, true);
    card.style.outline = '3px solid rgb(255, 0, 255)';
    card.style.outlineOffset = '0px';
    buddy.style.outline = '3px solid rgb(0, 255, 0)';
    // Nothing else on its own schedule while this measures.
    nmb.pinned = false;
    clearTimeout(nmb.timer);
    return { x: nmb.x, y: nmb.y, cardTop: r.top, riding: !!nmb.ride, glued: !!nmb.glue };
  }, process.env.CARD || '#tab-notes li');
  console.log('setup', JSON.stringify(setup));
  if (setup.error) { await browser.close(); process.exitCode = 1; return; }
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', async (f) => {
    frames.push({ t: f.metadata.timestamp, data: f.data, phase: current });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  let current = 'still';
  await page.evaluate((ms) => {
    window.__busy = true;
    const spin = () => { const t = performance.now(); while (performance.now() - t < ms) { /* a heavy page */ } if (window.__busy) requestAnimationFrame(spin); };
    requestAnimationFrame(spin);
  }, BUSY);
  await cdp.send('Page.startScreencast', { format: 'png', everyNthFrame: 1 });
  await page.waitForTimeout(400);
  await page.mouse.move(700, 600);
  current = 'wheel';
  for (let i = 0; i < 40; i += 1) { await page.mouse.wheel(0, 8 + (i % 9)); await page.waitForTimeout(16); }
  for (let i = 0; i < 40; i += 1) { await page.mouse.wheel(0, -(8 + (i % 9))); await page.waitForTimeout(16); }
  await page.waitForTimeout(300);
  current = 'smooth';
  await page.evaluate(() => { const c = document.querySelector('[data-probe-card]'); let s = c.parentElement; while (s && !(s.scrollHeight > s.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(s).overflowY))) s = s.parentElement; (s || document.scrollingElement).scrollBy({ top: 260, behavior: 'smooth' }); });
  await page.waitForTimeout(900);
  await page.evaluate(() => { const c = document.querySelector('[data-probe-card]'); let s = c.parentElement; while (s && !(s.scrollHeight > s.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(s).overflowY))) s = s.parentElement; (s || document.scrollingElement).scrollBy({ top: -260, behavior: 'smooth' }); });
  await page.waitForTimeout(900);
  current = 'flick';
  for (let i = 0; i < 6; i += 1) { await page.mouse.wheel(0, 40); await page.waitForTimeout(16); }
  for (let i = 0; i < 6; i += 1) { await page.mouse.wheel(0, -40); await page.waitForTimeout(16); }
  await page.waitForTimeout(400);
  await cdp.send('Page.stopScreencast');
  await page.evaluate(() => { window.__busy = false; });
  // Decode each frame and find the card's top edge and the companion's
  // bottom edge: the first and last rows with a run of their colour.
  const out = [];
  for (const f of frames) {
    const m = await decoder.evaluate(async (b64) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const c = document.getElementById('c');
      c.width = img.width; c.height = img.height;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      const d = ctx.getImageData(0, 0, img.width, img.height).data;
      let cardTop = -1; let buddyBottom = -1; let buddyTop = -1;
      for (let y = 0; y < img.height; y += 1) {
        let mag = 0; let grn = 0;
        for (let x = 0; x < img.width; x += 1) {
          const i = (y * img.width + x) * 4;
          const r = d[i]; const g = d[i + 1]; const b = d[i + 2];
          if (r > 230 && g < 40 && b > 230) mag += 1;
          else if (r < 40 && g > 230 && b < 40) grn += 1;
        }
        if (mag > 40 && cardTop < 0) cardTop = y;
        if (grn > 30) { if (buddyTop < 0) buddyTop = y; buddyBottom = y; }
      }
      return { cardTop, buddyTop, buddyBottom, w: img.width };
    }, f.data);
    out.push({ phase: f.phase, t: f.t, ...m, gap: m.cardTop >= 0 && m.buddyBottom >= 0 ? m.cardTop - m.buddyBottom : null });
  }
  const phases = {};
  for (const p of ['wheel', 'smooth', 'flick']) {
    const all = out.filter((o) => o.phase === p);
    // Only frames where both edges are in sight and the companion's box is
    // whole (its top edge is not the band's clip).
    const rows = all.filter((o) => o.gap !== null && o.buddyBottom - o.buddyTop > 80);
    const gaps = rows.map((o) => o.gap);
    const moved = rows.filter((o, i) => i && o.cardTop !== rows[i - 1].cardTop).length;
    const counts = {};
    for (const g of gaps) counts[g] = (counts[g] || 0) + 1;
    const mode = Number(Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0]);
    const off = gaps.filter((g) => Math.abs(g - mode) > 1).length;
    phases[p] = { frames: all.length, measured: rows.length, framesWhereCardMoved: moved, gap: mode, framesOff: off, offShare: gaps.length ? +(off / gaps.length).toFixed(3) : null, gapMin: Math.min(...gaps), gapMax: Math.max(...gaps) };
  }
  fs.writeFileSync(OUT, JSON.stringify({ setup, phases, frames: out }, null, 1));
  console.log(JSON.stringify(phases));
  await browser.close();
  const bad = Object.values(phases).some((p) => p.offShare === null || p.offShare > 0.1 || p.framesWhereCardMoved < 3);
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
})();
