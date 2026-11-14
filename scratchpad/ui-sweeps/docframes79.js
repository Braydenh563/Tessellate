// L-documents-79: a frame measurement of the document editor. A 20k-word document is
// scrolled, then 40 keys are typed, at 4x CPU throttle. Reports frame times, long tasks,
// and which registration site (file:line of the rAF, scroll listener, ResizeObserver or
// MutationObserver) woke how many times in each phase, with the callbacks that did no work
// with the total handler time in ms (columns: wakes, handler ms, site).
//   BASE=http://127.0.0.1:8852 WIDTH=1440 RATE=4 node docframes79.js
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');
const W = Number(process.env.WIDTH || 1440);
const RATE = Number(process.env.RATE || 4);
const initTap = () => {
  const counts = (window.__wake = { phase: 'idle', sites: {} });
  const site = (kind) => {
    const lines = (new Error().stack || '').split('\n').slice(3);
    const hit = lines.find((l) => /\/js\/[\w.-]+\.js/.test(l)) || lines[0] || '?';
    const m = hit.match(/\/js\/([\w.-]+\.js)[^:]*:(\d+)/);
    return kind + ' ' + (m ? m[1] + ':' + m[2] : hit.trim().slice(0, 60));
  };
  const bump = (key, idle, ms) => {
    const row = (counts.sites[counts.phase] = counts.sites[counts.phase] || {});
    const e = (row[key] = row[key] || { wakes: 0, empty: 0 });
    e.wakes++;
    e.ms = (e.ms || 0) + (ms || 0);
    if (idle) e.empty++;
  };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => { const k = site('rAF'); return raf((t) => { const a = performance.now(); try { return cb(t); } finally { bump(k, false, performance.now() - a); } }); };
  const add = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opt) {
    if (type !== 'scroll' || typeof fn !== 'function') return add.call(this, type, fn, opt);
    const k = site('scroll');
    return add.call(this, type, function (...a) { const t = performance.now(); try { return fn.apply(this, a); } finally { bump(k, false, performance.now() - t); } }, opt);
  };
  const RO = window.ResizeObserver;
  window.ResizeObserver = class extends RO {
    constructor(cb) { const k = site('RO'); super((entries, o) => { const t = performance.now(); try { return cb(entries, o); } finally { bump(k, !entries.length, performance.now() - t); } }); }
  };
  const MO = window.MutationObserver;
  window.MutationObserver = class extends MO {
    constructor(cb) { const k = site('MO'); super((recs, o) => { const t = performance.now(); try { return cb(recs, o); } finally { bump(k, !recs.length, performance.now() - t); } }); }
  };
  window.__frames = [];
  window.__long = [];
  new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__long.push(Math.round(e.duration)))).observe({ type: 'longtask', buffered: true });
  const loop = (t) => { if (window.__last) window.__frames.push(t - window.__last); window.__last = t; raf(loop); };
  raf(loop);
};
(async () => {
  const phone = W < 720;
  const { browser, ctx, page } = await boot({ viewport: { width: W, height: phone ? 844 : 900 }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  await ctx.addInitScript(initTap);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  const words = Array.from({ length: 20000 }, (_, i) => 'word' + (i % 97)).join(' ');
  const para = (words.match(/(\S+ ){1,60}/g) || []).map((p, i) => (i % 40 === 0 ? '## Section ' + i + '\n\n' : '') + p).join('\n\n');
  await openDoc(page, { title: 'Frames 79', content: para });
  //: The phone opens a document on its preview; typing needs the source view.
  await page.evaluate(() => setDocView('source', { persist: false }));
  await page.waitForTimeout(1500);
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const phase = async (name, fn) => {
    await page.evaluate((n) => { window.__wake.phase = n; window.__frames = []; window.__long = []; }, name);
    await fn();
    return page.evaluate(() => {
      const f = window.__frames.slice().sort((a, b) => a - b);
      const q = (p) => Math.round(f[Math.min(f.length - 1, Math.floor(f.length * p))] || 0);
      return { frames: f.length, p50: q(0.5), p95: q(0.95), max: q(1), over50: f.filter((x) => x > 50).length, longTasks: window.__long.length, longMax: Math.max(0, ...window.__long) };
    });
  };
  const out = {};
  out.idle = await phase('idle', () => page.waitForTimeout(2000));
  out.scroll = await phase('scroll', async () => {
    await page.mouse.move(W / 2, 400);
    for (let i = 0; i < 60; i++) { await page.mouse.wheel(0, 400); await page.waitForTimeout(16); }
  });
  out.typing = await phase('typing', async () => {
    await page.click('#doc-editor .cm-content');
    for (let i = 0; i < 40; i++) { await page.keyboard.type('x'); await page.waitForTimeout(40); }
  });
  console.log(`width ${W}, ${RATE}x CPU`);
  console.log(JSON.stringify(out, null, 1));
  const sites = await page.evaluate(() => window.__wake.sites);
  for (const ph of ['idle', 'scroll', 'typing']) {
    console.log('--- wakes in ' + ph);
    Object.entries(sites[ph] || {}).sort((a, b) => b[1].wakes - a[1].wakes).forEach(([k, v]) => console.log(String(v.wakes).padStart(5), String(Math.round(v.ms * 10) / 10).padStart(7) + 'ms', k));
  }
  await browser.close();
})();
