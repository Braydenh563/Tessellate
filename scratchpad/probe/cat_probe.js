// How often the in-app companion moves, vanishes and teleports while the app
// is used (INBOX 1673, the owner: "it teleports and appears and disappears
// all over my screen ... it should stay on other parts or other screens for
// longer before moving ... like a house cat that is there but has a mind of
// its own"). Samples #nm-buddy at 10 Hz (an in-page timer: its box, the
// opacity it is drawn at through every ancestor, visibility, the tab shown,
// `nmb.moveWhy`) while the script:
//   A. switches tabs every 1 to 3 s (seeded) for 60 s across Dashboard,
//      Notes, Library, Chat, Graph and Timeline;
//   B. scrolls a long Notes list down and up by wheel (40 s);
//   C. stays idle for 120 s on the Dashboard.
// Per minute of each phase it reports, twice: `screen` (where it is drawn)
// and `own` (its place on the page, the ride with a scrolling panel taken out):
//   relocations   a shown centre that moved over 40px from where it rested
//                 (`routes`: the `data-route` of the move that took it)
//   teleports     over 100px between two samples under 150ms apart, or
//                 drawn under 0.2 and back over 100px from where it was last seen
//   appears, disappears   shown (visible, opacity >= 0.2, a fifth or more not
//                 clipped by the window or a riding band) toggling
//   longestPutS   the longest run shown and within 40px of one place
//   shownPct      the share of samples it was shown
// Env: BASE (http://127.0.0.1:8796), SEED (1673), LOOK (atlas | you), NOTES (60),
// OUT_JSON (a path for the raw samples). Read-only: it changes nothing but the
// data dir it is pointed at. Run in the background (about 4.5 minutes).
process.env.BASE = process.env.BASE || 'http://127.0.0.1:8796';
const fs = require('fs');
const { boot } = require('../ui-sweeps/lib.js');

const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline'];
const MOVE_PX = 40;
const TELE_PX = 100;
const TELE_MS = 150;
const SHOWN_OP = 0.2;

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

async function tab(page, name) {
  const btn = await page.$(`#tab-bar button[data-tab="${name}"]`);
  if (btn && await btn.isVisible()) await btn.click({ timeout: 3000 }).catch(() => page.evaluate((n) => switchTab(n), name));
  else await page.evaluate((n) => switchTab(n), name);
}

//: Shown: visible, drawn at 0.2 or more, and at least a fifth of it unclipped.
const isShown = (p) => p.ok && p.vis && p.op >= SHOWN_OP && (p.seen ?? 1) >= SHOWN_OP;
//: **Where it is on the page, not on the screen.** Riding a panel that
//: scrolls (`nmb.ride`, a ScrollTimeline), the companion moves on screen with
//: the content, which the owner asked for (INBOX 426 m); that is not a move of
//: its own. Its own place is its centre plus the ridden scroller's offset;
//: where the ridden scroller changes, the place carries on from the screen
//: delta, so changing what it rides is not counted as a jump.
function ownCoords(samples) {
  let prev = null;
  let off = [0, 0];
  for (const p of samples) {
    if (!p.ok) { p.ox = p.oy = NaN; continue; }
    const sx = p.sl || 0;
    const sy = p.sc || 0;
    if (prev && prev.ok && prev.rid !== p.rid) {
      off = [prev.ox + (p.cx - prev.cx) - (p.cx + sx), prev.oy + (p.cy - prev.cy) - (p.cy + sy)];
    }
    p.ox = p.cx + sx + off[0];
    p.oy = p.cy + sy + off[1];
    prev = p;
  }
}

//: `own`: counted in its own place (scroll riding taken out); else on screen.
function analyse(samples, from, to, own = false) {
  const s = samples.filter((p) => p.t >= from && p.t < to);
  const X = own ? 'ox' : 'cx';
  const Y = own ? 'oy' : 'cy';
  const out = { relocations: 0, teleports: 0, teleJump: 0, teleBlink: 0, appears: 0, disappears: 0, longestPutS: 0, shownPct: 0, routes: {} };
  if (!s.length) return out;
  let anchor = null; // where it rests
  let putFrom = null; // when it came to rest there (shown)
  let lastShown = null;
  let prev = null;
  let hidden = false;
  let shownN = 0;
  const closePut = (t) => {
    if (putFrom !== null) out.longestPutS = Math.max(out.longestPutS, (t - putFrom) / 1000);
    putFrom = null;
  };
  const d = (a, b) => Math.hypot(a[X] - b[X], a[Y] - b[Y]);
  for (const p of s) {
    const shown = isShown(p);
    if (shown) shownN += 1;
    if (prev) {
      const prevShown = isShown(prev);
      if (shown && !prevShown) out.appears += 1;
      if (!shown && prevShown) out.disappears += 1;
      if (shown && prevShown && p.t - prev.t <= TELE_MS && d(p, prev) > TELE_PX) { out.teleports += 1; out.teleJump += 1; }
    }
    if (!shown) {
      hidden = true;
      closePut(p.t);
    } else {
      if (hidden && lastShown && d(p, lastShown) > TELE_PX) { out.teleports += 1; out.teleBlink += 1; }
      hidden = false;
      if (!anchor) { anchor = p; putFrom = p.t; }
      else if (d(p, anchor) > MOVE_PX) {
        out.relocations += 1;
        const why = p.route || '?';
        out.routes[why] = (out.routes[why] || 0) + 1;
        closePut(p.t);
        anchor = p;
        putFrom = p.t;
      } else if (putFrom === null) putFrom = p.t;
      lastShown = p;
    }
    prev = p;
  }
  closePut(s.at(-1).t);
  out.shownPct = Math.round((100 * shownN) / s.length);
  out.longestPutS = +out.longestPutS.toFixed(1);
  return out;
}

(async () => {
  const random = rng(Number(process.env.SEED || 1673));
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  // A long Notes list to scroll.
  const want = Number(process.env.NOTES || 60);
  await page.evaluate(async (n) => {
    const have = (await apiJson('/entries')).length || 0;
    for (let i = have; i < n; i += 1) {
      await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Cat probe note ${i}\n\nA paragraph about topic ${i % 9} so the card has a body to it, with a #probe tag.`, category: 'General' }) });
    }
  }, want);
  // The companion on, with no remembered spots.
  await page.evaluate((look) => {
    localStorage.removeItem('nm-buddy-spots');
    prefs.set('nm-buddy-spots', '{}');
    prefs.set('avatar-buddy', look === 'you' ? 'me' : 'atlas');
    syncNameMarkBuddy();
  }, process.env.LOOK || 'atlas');
  await tab(page, 'dashboard');
  await page.waitForFunction(() => {
    const b = document.getElementById('nm-buddy');
    return b && !b.classList.contains('nmb-away') && Number(getComputedStyle(b).opacity) > 0.5;
  }, null, { timeout: 20000, polling: 200 }).catch(() => console.log('WARN: companion not shown after 20 s'));
  await page.mouse.move(720, 470);
  await page.waitForTimeout(4000);

  // The in-page sampler, 10 Hz.
  await page.evaluate(() => {
    window.__cat = { t0: performance.now(), samples: [] };
    const read = () => {
      const b = document.getElementById('nm-buddy');
      const t = Math.round(performance.now() - window.__cat.t0);
      const tabName = document.body.dataset.tab || '';
      if (!b) return window.__cat.samples.push({ t, ok: false, tab: tabName });
      const r = b.getBoundingClientRect();
      let op = 1;
      let vis = true;
      for (let el = b.querySelector('.nm-buddy-char') || b; el && el !== document.body; el = el.parentElement) {
        const cs = getComputedStyle(el);
        op *= Number(cs.opacity);
        if (cs.display === 'none') vis = false;
      }
      if (getComputedStyle(b).visibility === 'hidden') vis = false;
      //: How much of it is not clipped: the window, and every ancestor that
      //: clips (the band and its shutter while it rides a scrolling panel).
      let L = Math.max(0, r.left), T = Math.max(0, r.top), R = Math.min(innerWidth, r.right), B = Math.min(innerHeight, r.bottom);
      for (let el = b.parentElement; el && el !== document.body; el = el.parentElement) {
        const cs = getComputedStyle(el);
        if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
        const c = el.getBoundingClientRect();
        L = Math.max(L, c.left); T = Math.max(T, c.top); R = Math.min(R, c.right); B = Math.min(B, c.bottom);
      }
      const area = Math.max(1, r.width * r.height);
      const seen = +(Math.max(0, R - L) * Math.max(0, B - T) / area).toFixed(2);
      let why = '';
      let perch = '';
      let rid = '';
      let sc = 0;
      let sl = 0;
      try {
        why = nmb.moveWhy || '';
        perch = nmb.perch || '';
        const el = nmb.ride?.el;
        if (el) { rid = el.id || el.className || 'ride'; sc = Math.round(el.scrollTop); sl = Math.round(el.scrollLeft); }
      } catch (e) { /* nmb is a page global */ }
      window.__cat.samples.push({ t, ok: r.width > 0, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), cx: Math.round(r.left + r.width / 2), cy: Math.round(r.top + r.height / 2), op: +op.toFixed(2), vis, seen, tab: tabName, away: b.classList.contains('nmb-away'), route: b.dataset.route || '', why, perch, rid, sc, sl });
    };
    window.__cat.timer = setInterval(read, 100);
    read();
  });
  const now = () => page.evaluate(() => performance.now() - window.__cat.t0);
  const phases = [];

  // A. tab switching, 60 s.
  let a0 = await now();
  let order = [];
  let last = 'dashboard';
  while ((await now()) - a0 < 60000) {
    const choices = TABS.filter((x) => x !== last);
    last = choices[Math.floor(random() * choices.length)];
    order.push(last);
    await tab(page, last);
    await page.waitForTimeout(1000 + Math.round(random() * 2000));
  }
  phases.push({ name: 'A tabs every 1-3 s', from: a0, to: await now(), extra: { switches: order.length } });

  // B. a long Notes list, wheeled down and up, 40 s.
  await tab(page, 'notes');
  await page.waitForTimeout(3000);
  const list = await page.evaluate(() => {
    const ul = document.getElementById('entry-list');
    let el = ul;
    while (el && el !== document.body) {
      const cs = getComputedStyle(el);
      if (/auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 1) break;
      el = el.parentElement;
    }
    const box = (el && el !== document.body ? el : ul).getBoundingClientRect();
    return { items: ul.children.length, scroller: el && el !== document.body ? (el.id || el.className) : 'none', scrollH: el ? el.scrollHeight : 0, clientH: el ? el.clientHeight : 0, cx: Math.round(box.left + box.width / 2), cy: Math.round(box.top + Math.min(box.height, 600) / 2) };
  });
  const b0 = await now();
  await page.mouse.move(list.cx, list.cy);
  for (let round = 0; round < 2; round += 1) {
    for (let i = 0; i < 50; i += 1) { await page.mouse.wheel(0, 120); await page.waitForTimeout(100); }
    await page.waitForTimeout(2500);
    for (let i = 0; i < 50; i += 1) { await page.mouse.wheel(0, -120); await page.waitForTimeout(100); }
    await page.waitForTimeout(2500);
  }
  const maxScroll = await page.evaluate(() => {
    let el = document.getElementById('entry-list');
    while (el && el !== document.body) { const cs = getComputedStyle(el); if (/auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 1) return el.scrollHeight - el.clientHeight; el = el.parentElement; }
    return 0;
  });
  phases.push({ name: 'B notes scroll', from: b0, to: await now(), extra: { ...list, maxScroll } });

  // C. idle on the Dashboard, 120 s.
  await tab(page, 'dashboard');
  await page.mouse.move(720, 470);
  await page.waitForTimeout(3000);
  const c0 = await now();
  await page.waitForTimeout(120000);
  phases.push({ name: 'C idle 120 s on dashboard', from: c0, to: await now(), extra: {} });

  const samples = await page.evaluate(() => { clearInterval(window.__cat.timer); return window.__cat.samples; });
  ownCoords(samples);
  const report = { base: process.env.BASE, look: process.env.LOOK || 'atlas', seed: Number(process.env.SEED || 1673), tabs: order, phases: [], errors: errors.slice(0, 5) };
  for (const ph of phases) {
    const minutes = [];
    for (let m = ph.from; m < ph.to - 5000; m += 60000) {
      const b = Math.min(ph.to, m + 60000);
      minutes.push({ minute: minutes.length + 1, seconds: Math.round((b - m) / 1000), screen: analyse(samples, m, b), own: analyse(samples, m, b, true) });
    }
    report.phases.push({ name: ph.name, seconds: Math.round((ph.to - ph.from) / 1000), ...ph.extra, minutes });
  }
  if (process.env.OUT_JSON) fs.writeFileSync(process.env.OUT_JSON, JSON.stringify({ report, samples }, null, 0));
  console.log(JSON.stringify(report, null, 1));
  await browser.close();
})().catch((e) => { console.error('PROBE-FAIL', e); process.exit(2); });
