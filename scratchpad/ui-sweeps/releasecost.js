// B87a follow-up (companion-1018): what the release and landing frames spend.
// Counts and times (in page, performance.now) the calls that force layout or
// read animations from pointer-up to rest: nameMarkBuddyShown (with its
// callers), nameMarkBuddyBlend, getAnimations, and CDP style recalc / layout
// counts for the window. Counts are the measure; fps at 4x is noisy.
// Env: BASE, KINDS (atlas,me), RATE (4), RUNS (3), MODE (throw|drop).
const { boot } = require('./lib.js');
const KINDS = (process.env.KINDS || 'atlas,me').split(',');
const RATE = Number(process.env.RATE || 4);
const RUNS = Number(process.env.RUNS || 3);
const MODE = process.env.MODE || 'throw';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const metrics = async (cdp) => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  for (const kind of KINDS) {
    await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, kind);
    await page.evaluate(() => revealTab('notes'));
    await page.waitForTimeout(3500);
    await page.evaluate(() => {
      if (window.__probe) return;
      const P = (window.__probe = { on: false, n: {}, ms: {}, callers: {}, long: [] });
      const wrap = (name) => {
        const fn = window[name];
        window[name] = function (...a) {
          if (!P.on) return fn.apply(this, a);
          const t = performance.now();
          const r = fn.apply(this, a);
          const d = performance.now() - t;
          if (name !== 'nameMarkBuddyShown' && d > 5) (P.tl ||= []).push(`${Math.round(t - P.t0)}ms ${name} ${d.toFixed(0)}ms`);
          P.n[name] = (P.n[name] || 0) + 1; P.ms[name] = (P.ms[name] || 0) + d;
          const st = (new Error().stack.split('\n')[2] || '').trim().replace(/\(.*\/(\w[\w.-]*\.js)\S*?:(\d+):\d+\)/, '$1:$2').replace(/^at /, '');
          const k = `${name} < ${st}`;
          P.callers[k] = (P.callers[k] || 0) + 1;
          return r;
        };
      };
      ['nameMarkBuddyShown', 'nameMarkBuddyBlend', 'nameMarkBuddyPopups', 'nameMarkBuddyObstacles', 'nameMarkBuddyCheck'].forEach(wrap);
      const ga = Element.prototype.getAnimations;
      Element.prototype.getAnimations = function (o) { if (!P.on) return ga.call(this, o); const t = performance.now(); const r = ga.call(this, o); const d = performance.now() - t; P.n.getAnimations = (P.n.getAnimations || 0) + 1; P.ms.getAnimations = (P.ms.getAnimations || 0) + d; const st = (new Error().stack.split('\n')[2] || '').trim().replace(/\(.*\/(\w[\w.-]*\.js)\S*?:(\d+):\d+\)/, '$1:$2').replace(/^at /, ''); const k = `getAnimations < ${st}`; P.callers[k] = (P.callers[k] || 0) + 1; P.callers[k + ' ms'] = +(((P.callers[k + ' ms'] || 0) + d)).toFixed(1); return r; };
    });
    const faceMid = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    const out = [];
    for (let run = 0; run < RUNS; run += 1) {
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await page.evaluate(() => { const spot = { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 }; nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true); nmb.placedAt = Date.now(); });
      await sleep(900);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
      const f = await faceMid();
      await page.mouse.move(f[0], f[1]); await page.mouse.down();
      for (let i = 1; i <= 30; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
      if (MODE === 'throw') { const x0 = f[0] + 360; for (let i = 1; i <= 5; i += 1) { await page.mouse.move(x0 + i * 70, f[1] - 40 - i * 6); await sleep(16); } } else await sleep(300);
      await page.evaluate(() => { Object.assign(__probe, { on: true, n: {}, ms: {}, callers: {}, tl: [], t0: performance.now() }); window.__frames = []; let l = 0; const loop = (t) => { if (__probe.on) { if (l && t - l > 50) __probe.tl.push(`${Math.round(t - __probe.t0)}ms FRAME ${Math.round(t - l)}`); if (l) __frames.push(t - l); l = t; requestAnimationFrame(loop); } }; requestAnimationFrame(loop); });
      const m0 = await metrics(cdp);
      await page.mouse.up();
      await sleep(2600);
      const m1 = await metrics(cdp);
      const r = await page.evaluate(() => { __probe.on = false; return { tl: __probe.tl, n: __probe.n, ms: Object.fromEntries(Object.entries(__probe.ms).map(([k, v]) => [k, +v.toFixed(1)])), callers: __probe.callers, frames: __frames.length, worst: Math.round(Math.max(...__frames)), over50: __frames.filter((d) => d > 50).length, sum50: Math.round(__frames.filter((d) => d > 50).reduce((a, b) => a + b, 0)) }; });
      r.recalcCount = m1.RecalcStyleCount - m0.RecalcStyleCount; r.layoutCount = m1.LayoutCount - m0.LayoutCount;
      out.push(r);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await sleep(400);
    }
    const sum = (f) => out.reduce((a, r) => a + f(r), 0) / out.length;
    console.log(kind, MODE, 'rate', RATE, JSON.stringify({ shownN: sum((r) => r.n.nameMarkBuddyShown || 0), shownMs: +sum((r) => r.ms.nameMarkBuddyShown || 0).toFixed(1), blendN: sum((r) => r.n.nameMarkBuddyBlend || 0), blendMs: +sum((r) => r.ms.nameMarkBuddyBlend || 0).toFixed(1), gaN: sum((r) => r.n.getAnimations || 0), gaMs: +sum((r) => r.ms.getAnimations || 0).toFixed(1), obstaclesN: sum((r) => r.n.nameMarkBuddyObstacles || 0), checkN: sum((r) => r.n.nameMarkBuddyCheck || 0), recalc: sum((r) => r.recalcCount), layout: sum((r) => r.layoutCount), over50: sum((r) => r.over50), sum50: sum((r) => r.sum50), worst: Math.max(...out.map((r) => r.worst)) }));
    if (process.env.TL) console.log(out.map((r) => r.tl.join(' | ')).join('\n'));
    if (process.env.CALLERS) console.log(JSON.stringify(out[0].callers, null, 1));
  }
  await browser.close();
})();
