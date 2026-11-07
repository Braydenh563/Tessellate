// INBOX 1667 (2026-11-07 log): open a note from a dashboard list at 4x; long tasks + long-animation-frames.
const { boot } = require('../ui-sweeps/lib.js');
const RATE = Number(process.env.RATE || 4), RUNS = Number(process.env.RUNS || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate((b) => prefs.set('avatar-buddy', b), process.env.BUDDY || 'atlas');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  if (await page.locator('#lock-password').isVisible()) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
  await page.evaluate(() => { window.__ac = []; const o = nmb.afterClean; nmb.afterClean = function (fn, tries, snap) { const w = function () { const d0 = performance.now(); void document.documentElement.offsetHeight; const dirty = performance.now() - d0; const t = performance.now(); const r = fn(); window.__ac.push([Math.round(performance.now() - t), Math.round(dirty),  String(fn).replace(/\s+/g, ' ').slice(0, 110)]); return r; }; return o.call(this, w, tries, snap); }; });
  if (process.env.PROBE) {
  await page.evaluate(() => {
    window.__reads = [];
    const note = (kind, t) => { const d = performance.now() - t; if (d < 4) return; const st = (new Error().stack || '').split('\n').slice(2, 6).map((l) => l.trim().replace(/https?:\/\/[^/]+\/js\//, '').replace(/\?v=[^:]*/, '')).join(' < '); window.__reads.push([Math.round(d), kind, st]); };
    for (const name of ['getBoundingClientRect', 'getClientRects', 'scrollIntoView', 'elementsFromPoint']) { const o = Element.prototype[name] || Document.prototype[name]; if (!o) continue; const owner = Element.prototype[name] ? Element.prototype : Document.prototype; owner[name] = function (...a) { const t = performance.now(); const r = o.apply(this, a); note(name, t); return r; }; }
    for (const name of ['offsetHeight', 'offsetWidth', 'offsetTop', 'scrollHeight', 'clientHeight', 'scrollTop']) { const d = Object.getOwnPropertyDescriptor(Element.prototype, name) || Object.getOwnPropertyDescriptor(HTMLElement.prototype, name); if (!d || !d.get) continue; Object.defineProperty(d.get === undefined ? Element.prototype : (Object.getOwnPropertyDescriptor(HTMLElement.prototype, name) ? HTMLElement.prototype : Element.prototype), name, { ...d, get() { const t = performance.now(); const r = d.get.call(this); note(name, t); return r; } }); }
    const gcs = window.getComputedStyle; window.getComputedStyle = function (...a) { const cs = gcs.apply(this, a); return new Proxy(cs, { get(t, k) { const v = Reflect.get(t, k); if (typeof v === 'function') return v.bind(t); const t0 = performance.now(); const r = t[k]; note('gcs.' + String(k), t0); return r; } }); };
    document.elementFromPoint = ((o) => function (...a) { const t = performance.now(); const r = o.apply(this, a); note('elementFromPoint', t); return r; })(document.elementFromPoint);
  });
  }
  await page.evaluate(() => revealTab('dashboard'));
  await page.evaluate(() => { window.__lt = []; window.__loaf = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ type: 'longtask' });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push({ d: Math.round(e.duration), s: (e.scripts || []).map((s) => `${s.sourceURL.split('/').pop()}:${s.invokerType}:${s.invoker}@${s.sourceFunctionName}${s.sourceCharPosition}:${Math.round(s.duration)}:fl${Math.round(s.forcedStyleAndLayoutDuration)}`) }); }).observe({ type: 'long-animation-frame', buffered: false });
  });
  await page.waitForTimeout(8000);
  const n = await page.evaluate(() => document.querySelectorAll('.dash-list-preview').length);
  const li = await page.evaluate(() => document.querySelectorAll('.dash-list li:has(.dash-list-preview)').length);
  console.log('previews', n, 'li', li, 'buddy', await page.evaluate(() => !!document.getElementById('nm-buddy')));
  const all = [];
  for (let i = 0; i < RUNS; i += 1) {
    await page.evaluate(() => revealTab('dashboard'));
    await sleep(1500);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
    await page.evaluate(() => { window.__lt = []; window.__loaf = []; window.__reads = []; });
    const target = page.locator('.dash-list li:has(.dash-list-preview)').nth(2 + (i % 3));
    const box = await target.boundingBox();
    await page.mouse.move(box.x + 30, box.y + box.height / 2);
    const ev = []; if (process.env.TRACE) { cdp.removeAllListeners('Tracing.dataCollected'); cdp.on('Tracing.dataCollected', (d) => ev.push(...d.value)); await cdp.send('Tracing.start', { traceConfig: { includedCategories: ['devtools.timeline'] } }); }
    if (!process.env.IDLE) await target.click();
    await sleep(6000);
    if (process.env.TRACE) { const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r)); await cdp.send('Tracing.end'); await done;
      const x = ev.filter((e) => e.ph === 'X'); const top = (n) => x.filter((e) => e.name === n).sort((a, b) => b.dur - a.dur).slice(0, 4).map((e) => `${(e.dur / 1000).toFixed(0)}ms/${e.args?.elementCount ?? e.args?.beginData?.dirtyObjects ?? ''}`).join(' ');
      const sum = (n) => (x.filter((e) => e.name === n).reduce((a, e) => a + e.dur, 0) / 1000).toFixed(0);
      console.log('TRACE ult', sum('UpdateLayoutTree'), 'n', x.filter((e) => e.name === 'UpdateLayoutTree').length, 'top', top('UpdateLayoutTree'), '| layout', sum('Layout'), 'n', x.filter((e) => e.name === 'Layout').length, 'top', top('Layout'), '| paint', sum('Paint'), 'prepaint', sum('PrePaint'), 'hit', sum('HitTest')); }
    const r = await page.evaluate(() => ({ lt: window.__lt, loaf: window.__loaf, reads: (window.__reads || []).sort((a, b) => b[0] - a[0]).slice(0, 8), ac: window.__ac.filter((a) => a[0] > 15 || a[1] > 15), tab: document.querySelector('.tab-page:not(.hidden)')?.id }));
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    console.log(JSON.stringify(r));
    all.push(...r.loaf.map((x) => x.d));
  }
  all.sort((a, b) => a - b);
  console.log('frames', all.length, 'p95', all[Math.floor(all.length * 0.95)], 'max', all[all.length - 1]);
  await browser.close();
})();
