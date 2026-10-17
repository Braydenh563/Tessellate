// The owner, 2026-10-17 (B88a): the companion "sometimes loses its perch and
// is left stuck floating and not anchored to something". Seats the companion
// on a perch of the tab, then does each thing that can take the perch away
// (resize, scroll, hide it, remove it, switch surface and back, draw its list
// again) and reads, 0.4s, 2s and 6s after, whether it is on a perch again or
// floats with nothing under it. A float is fine only when it was put in open
// air by hand (`nmb.spot` of kind yours, pose float, kept); any other float
// that lasts is the bug. Env: BASE, TAB (chat), KIND (atlas), VW, VH, ONLY (a
// scenario name), OUT. Exits 1 when any scenario floats at 6s.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1280);
const VH = Number(process.env.VH || 800);
const TAB = process.env.TAB || 'chat';
const KIND = process.env.KIND || 'atlas';
const MODE = process.env.MODE || '';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// What a viewer sees: on a perch (a pose that touches something) or floating,
// and whether the thing it stands on is still on the page, shown, and under it.
const read = () => page.evaluate(() => {
  const buddy = document.getElementById('nm-buddy');
  const g = nmb.glue;
  const box = g && g.el && g.el.isConnected ? g.el.getBoundingClientRect() : null;
  return {
    pose: nmb.pose, perch: nmb.perch, x: Math.round(nmb.x), y: Math.round(nmb.y), tab: nameMarkBuddyTab(),
    glue: g ? { lost: g.lost, held: g.held, conn: !!(g.el && g.el.isConnected), w: box ? Math.round(box.width) : 0, top: box ? Math.round(box.top) : null } : null,
    deliberate: !!(nmb.spot && nmb.spot.kind === 'yours' && nmb.spot.pose === 'float'),
    supported: nameMarkBuddySupported(), pinned: !!nmb.pinned, moving: !!(nmb.anim && nmb.anim.playState === 'running'),
    // The bar or edge it holds on to is gone from the page (hidden, emptied, removed).
    edgeGone: (() => { const el = nmb.spot && nmb.spot.edge && nmb.spot.edge.el; if (!el || !['bar', 'hang'].includes(nmb.spot.edge.kind)) return false; const r = el.isConnected ? el.getBoundingClientRect() : null; return !r || !r.width || !r.height || getComputedStyle(el).visibility === 'hidden'; })(),
    away: !!nmb.away, hidden: !!(buddy && buddy.classList.contains('hidden')), act: nmb.act || '',
  };
});
let page;

(async () => {
  const b = await boot({ viewport: { width: VW, height: VH } });
  page = b.page;
  await page.evaluate((kind) => { localStorage.removeItem('nm-buddy-spots'); const s = document.getElementById('avatar-buddy'); s.value = kind; s.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.evaluate((tab) => switchTab(tab), TAB);
  await page.waitForTimeout(4500);

  const scenarios = {
    // The page gets narrower, then wider again.
    resize: async () => { await page.setViewportSize({ width: 700, height: 600 }); await sleep(900); await page.setViewportSize({ width: VW, height: VH }); },
    // A long scroll in whatever scrolls, and back.
    scroll: async () => {
      await page.evaluate(() => { for (const el of document.querySelectorAll('*')) { if (el.scrollHeight > el.clientHeight + 40 && /auto|scroll/.test(getComputedStyle(el).overflowY)) el.scrollTop = el.scrollHeight; } });
      await sleep(900);
      await page.evaluate(() => { for (const el of document.querySelectorAll('*')) if (el.scrollTop) el.scrollTop = 0; });
    },
    // The perch hidden (display none), shown again 3s on.
    hide: async () => {
      await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; if (el) { el.dataset.pl = el.style.display || ' '; el.style.display = 'none'; window.__pl = el; } });
      await sleep(3000);
      await page.evaluate(() => { const el = window.__pl; if (el) el.style.display = el.dataset.pl === ' ' ? '' : el.dataset.pl; });
    },
    // The perch hidden and left hidden.
    hideforever: async () => { await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; if (el) el.style.display = 'none'; }); },
    // The perch faded out (opacity 0 with visibility hidden), as a closing panel is.
    fade: async () => { await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; if (el) el.style.visibility = 'hidden'; }); },
    // The perch taken out of the page for good.
    remove: async () => { await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; if (el) el.remove(); }); },
    // The surface changed and changed back.
    surface: async () => {
      await page.evaluate(() => switchTab('graph'));
      await sleep(1500);
      await page.evaluate((tab) => switchTab(tab), TAB);
    },
    // The perch's parent drawn again (innerHTML), as a list redraw is.
    redraw: async () => { await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; const p = el && el.parentElement; if (p) p.innerHTML = p.innerHTML; }); },
    // The window's own bars gone (a status bar switched off, a focus mode).
    barhide: async () => { await page.evaluate(() => { for (const id of ['status-bar', 'top-bar', 'phone-tab-dock']) { const el = document.getElementById(id); if (el) el.style.display = 'none'; } }); },
    // Whatever it settles on taken away again and again, 1.2s apart.
    chain: async () => {
      for (let i = 0; i < 4; i += 1) {
        await sleep(1200);
        await page.evaluate(() => { const g = nmb.glue; const el = g && g.el; if (el) el.style.display = 'none'; else { const b = document.getElementById('status-bar'); if (b && nmb.perch === 'bar') b.style.display = 'none'; } });
      }
    },
    // A phone-sized window and back.
    phone: async () => { await page.setViewportSize({ width: 390, height: 844 }); await sleep(2500); await page.setViewportSize({ width: VW, height: VH }); },
    // The status bar or top bar it is on goes without a word (no class, no resize): what a page's own script does.
    silent: async () => { await page.evaluate(() => { const el = document.getElementById(nmb.perch === 'hang' ? 'top-bar' : 'status-bar'); if (el) el.style.display = 'none'; }); },
    // The perch moved to the other side of the page (a layout change).
    shove: async () => { await page.evaluate(() => { const el = nmb.glue && nmb.glue.el; if (el) { el.style.transform = 'translate(-3000px, 0)'; } }); },
  };

  const only = process.env.ONLY ? process.env.ONLY.split(',') : Object.keys(scenarios);
  const out = {};
  let failed = 0;
  for (const name of only) {
    // Fresh each time: back on the tab, free of any earlier test, seated.
    await page.setViewportSize({ width: VW, height: VH });
    await page.evaluate((tab) => { localStorage.removeItem('nm-buddy-spots'); }, TAB);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const pw = await page.isVisible('#lock-password');
    if (pw) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
    await page.waitForTimeout(1500);
    await page.evaluate((tab) => switchTab(tab), TAB);
    await page.waitForTimeout(4500);
    // MODE=yours: a place of its own on the perch, as a drop keeps it; MODE=pinned: Stay here on every page.
    if (MODE === 'yours') {
      await page.evaluate(() => {
        const buddy = document.getElementById('nm-buddy');
        const landed = nameMarkBuddyDrop(nmb.x, nmb.y);
        nameMarkBuddyMoveTo(buddy, landed, true);
        const spots = nameMarkBuddySpots();
        spots[nameMarkBuddyTab()] = nameMarkBuddySpotFor(landed);
        nameMarkBuddyKeepSpots(spots);
        nmb.placedAt = Date.now();
      });
      await sleep(1200);
    } else if (MODE === 'bar' || MODE === 'hang') {
      // On the window's own bar, as the bar perch is made (no panel to follow).
      await page.evaluate((mode) => {
        const buddy = document.getElementById('nm-buddy');
        const { top, bottom } = nameMarkBuddyLedges();
        const x = Math.round(innerWidth / 2);
        nameMarkBuddyMoveTo(buddy, mode === 'bar'
          ? { kind: 'bar', pose: 'sit', legs: 'peek', x, y: bottom.top - NMB_SEAT, edge: { el: document.getElementById('status-bar'), type: 'top', kind: 'bar', y: bottom.top } }
          : { kind: 'hang', pose: 'hang', legs: '', x, y: top.bottom - NMB_GRIP, edge: { el: document.getElementById('top-bar'), type: 'under', kind: 'hang', y: top.bottom } }, true);
        nmb.placedAt = Date.now();
      }, MODE);
      await sleep(1500);
    } else if (MODE === 'pinned') {
      await page.evaluate(() => {
        const buddy = document.getElementById('nm-buddy');
        const box = buddy.getBoundingClientRect();
        const x = Math.round(box.left); const y = Math.round(box.top);
        nameMarkBuddyKeepSpots({ '*': { x, y, pose: nmb.pose, legs: nmb.legs, side: buddy.dataset.side || '', w: innerWidth, h: innerHeight, keep: 1 } });
        nameMarkBuddyMoveTo(buddy, { kind: 'pinned', x, y, pose: nmb.pose, legs: nmb.legs, side: buddy.dataset.side || '' }, true);
      });
      await sleep(1200);
    }
    const start = await read();
    await scenarios[name]();
    // Every 250ms for 7s: bad is floating with nothing to float for, or posed on something that is not there.
    const samples = {};
    let worst = 0;
    let run = 0;
    const isBad = (r) => !r.pinned && !r.away && !r.moving && ((r.pose === 'float' && !r.deliberate) || (r.edgeGone && r.pose !== 'float') || (['sit', 'stand', 'hang'].includes(r.pose) && !r.supported));
    const WINDOW = Number(process.env.WINDOW || 7000);
    for (let t = 250; t <= WINDOW; t += 250) {
      await sleep(250);
      const r = await read();
      run = isBad(r) ? run + 250 : 0;
      worst = Math.max(worst, run);
      if (t === 500) samples['t0.4'] = r;
      if (t === 2000) samples.t2 = r;
      if (t === WINDOW) samples.t6 = r;
    }
    const end = samples.t6;
    const floating = isBad(end);
    if (floating) failed += 1;
    out[name] = { start, samples, floating, worst };
    console.log(name.padEnd(12), floating ? 'FLOATS' : 'ok    ', 'bad for up to', worst + 'ms', 'start', start.pose, start.perch, '| 0.4s', samples['t0.4'].pose, '| 2s', samples.t2.pose, '| 6s', end.pose, end.perch, JSON.stringify(end.glue));
  }
  if (process.env.OUT) require('fs').writeFileSync(process.env.OUT, JSON.stringify(out, null, 1));
  await b.browser.close();
  process.exit(failed ? 1 : 0);
})();
