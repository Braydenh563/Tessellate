// C25: scrolling Settings > Help at CPU 4x. Frame times (rAF), main-thread
// style/layout/script per frame, and the rest (paint, composite) by subtraction.
// Compares General. Env: BASE, RATE (4), PANES (help,general).
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stats = (dts) => { const s = [...dts].sort((a, b) => a - b); const at = (q) => s[Math.min(s.length - 1, Math.floor(q * s.length))]; return { frames: s.length, median: +at(0.5).toFixed(1), p95: +at(0.95).toFixed(1), worst: +s[s.length - 1].toFixed(1) }; };
const metrics = async (cdp) => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); } });
  await page.evaluate(() => {
    window.__fr = { on: false, dts: [], last: 0 };
    const loop = (t) => { const f = window.__fr; if (f.on) { if (f.last) f.dts.push(t - f.last); f.last = t; } else f.last = 0; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
  for (const pane of (process.env.PANES || 'general,help').split(',')) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    await page.evaluate((p) => openSettingsModal(p), pane);
    if (process.env.EXP_CSS) await page.evaluate((c) => { const sh = new CSSStyleSheet(); sh.replaceSync(c); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; }, process.env.EXP_CSS);
    await page.waitForTimeout(2500);
    const info = await page.evaluate((p) => {
      const sec = document.getElementById('settings-' + p);
      let el = sec; while (el && el.scrollHeight <= el.clientHeight + 4) el = el.parentElement;
      window.__scroller = el;
      return { nodes: sec.querySelectorAll('*').length, scrollH: el?.scrollHeight, clientH: el?.clientHeight, id: el?.id || el?.className };
    }, pane);
    const box = await page.evaluate(() => { const r = window.__scroller.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
    await page.mouse.move(box.x, box.y);
    await page.evaluate(() => { __fr.dts = []; __fr.on = true; });
    const m0 = await metrics(cdp);
    const evs = [];
    if (process.env.TRACE) { cdp.on('Tracing.dataCollected', (d) => evs.push(...d.value)); await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline', transferMode: 'ReportEvents' }); }
    for (let i = 0; i < 40; i += 1) { await page.mouse.wheel(0, 60); await sleep(70); }
    if (process.env.TRACE) { const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r)); await cdp.send('Tracing.end'); await done; const sum = {}; for (const e of evs) if (e.ph === 'X' && e.dur && e.pid && e.tid) sum[e.name] = (sum[e.name] || 0) + e.dur; console.log(Object.entries(sum).sort((a, b) => b[1] - a[1]).slice(0, 14).map(([k, v]) => k + ' ' + (v / 1000).toFixed(0) + 'ms').join(' | ')); }
    const dts = await page.evaluate(() => { __fr.on = false; return [...__fr.dts]; });
    const m1 = await metrics(cdp);
    const n = Math.max(1, dts.length);
    const per = (k) => +(((m1[k] - m0[k]) * 1000) / n).toFixed(2);
    console.log(pane, JSON.stringify(info), JSON.stringify({ ...stats(dts), styleMs: per('RecalcStyleDuration'), layoutMs: per('LayoutDuration'), scriptMs: per('ScriptDuration'), taskMs: per('TaskDuration') }));
  }
  await browser.close();
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
