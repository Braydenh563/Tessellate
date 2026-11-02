// Audit 1031 row 23, CE3: typing in a 7,000-line .js file in the code editor.
// 20 keys, KEY_MS apart, mid-file, at CPU rate RATE (CDP): long tasks and
// long animation frames per key, how often the outline's work runs
// (renderDocOutline, docCodeSymbols), and the per-key dispatch-to-paint time.
// Env: BASE, RATES (1,4), LINES (7000), KEY_MS (120), KEYS (20), AV (the companion, e.g. atlas: its keyup dodge runs only with one), BEFORE_DIR (OVERRIDE_JS of the base files)
//   BASE=http://127.0.0.1:8784 node scratchpad/ui-sweeps/codetype1101.js
const { boot } = require('./lib.js');
const LINES = Number(process.env.LINES || 7000);
const KEYS = Number(process.env.KEYS || 20);
const KEY_MS = Number(process.env.KEY_MS || 120);
function source(n) {
  const out = [];
  let k = 0;
  while (out.length < n) {
    out.push(`function handler${k}(event, options = {}) {`);
    out.push(`  const value = options.value ?? ${k};`);
    out.push(`  if (event && event.type === "click") { return value + ${k}; }`);
    out.push(`  const items = [1, 2, 3].map((x) => x * value);`);
    out.push(`  return items.reduce((a, b) => a + b, 0); // handler ${k}`);
    out.push('}');
    out.push('');
    k += 1;
  }
  return out.slice(0, n).join('\n') + '\n';
}
(async () => {
  const rows = [];
  for (const rate of (process.env.RATES || '1,4').split(',').map(Number)) {
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    const cdp = await page.context().newCDPSession(page);
    if (process.env.AV) await page.evaluate((v) => { const b = document.getElementById('avatar-buddy'); b.value = v; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.AV);
    await page.evaluate(async (c) => {
      const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'big.js', content: c, file_type: 'js' }) });
      switchTab('documents');
      await loadDocuments(d.id);
    }, source(LINES));
    await page.waitForSelector('#doc-editor .cm-content', { timeout: 20000 });
    await page.waitForTimeout(4000);
    // Put the caret mid-file, scrolled there.
    await page.evaluate(() => {
      const v = docCmView; const line = v.state.doc.line(Math.floor(v.state.doc.lines / 2));
      v.dispatch({ selection: { anchor: line.to }, scrollIntoView: true }); v.focus();
    });
    await page.waitForTimeout(1500);
    await page.evaluate(() => {
      window.__n = { outline: 0, symbols: 0, tasks: [], loaf: [], keys: [] };
      const ro = renderDocOutline; renderDocOutline = function (...a) { window.__n.outline += 1; return ro.apply(this, a); };
      const dg = nameMarkBuddyDodge; nameMarkBuddyDodge = function (...a) { const t = performance.now(); const r = dg.apply(this, a); window.__n.dodgeMs = (window.__n.dodgeMs || 0) + performance.now() - t; window.__n.dodges = (window.__n.dodges || 0) + 1; return r; };
      const sy = docCodeSymbols; docCodeSymbols = function (...a) { window.__n.symbols += 1; return sy.apply(this, a); };
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__n.tasks.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: false });
      try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__n.loaf.push(Math.round(e.duration)); }).observe({ type: 'long-animation-frame', buffered: false }); } catch (e) {}
      // dispatch-to-next-paint per keydown
      document.addEventListener('keydown', () => { const t = performance.now(); requestAnimationFrame(() => setTimeout(() => window.__n.keys.push(Math.round(performance.now() - t)), 0)); }, true);
    });
    await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    if (process.env.PROFILE) { await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 300 }); await cdp.send('Profiler.start'); }
    for (let i = 0; i < KEYS; i += 1) { await page.keyboard.type('x'); await page.waitForTimeout(KEY_MS); }
    await page.waitForTimeout(1500);
    if (process.env.PROFILE) {
      const { profile } = await cdp.send('Profiler.stop');
      const self = {}; const byId = new Map(profile.nodes.map((x) => [x.id, x]));
      const parent = new Map(); for (const x of profile.nodes) for (const c of x.children || []) parent.set(c, x.id);
      const incl = {};
      profile.samples.forEach((id, i) => { const dt = profile.timeDeltas[i]; const x = byId.get(id); const k = `${x.callFrame.functionName || '(anon)'} ${x.callFrame.url.split('/').pop().split('?')[0]}:${x.callFrame.lineNumber + 1}`; self[k] = (self[k] || 0) + dt;
        const seen = new Set(); for (let c = id; c; c = parent.get(c)) { const y = byId.get(c); const kk = `${y.callFrame.functionName || '(anon)'} ${y.callFrame.url.split('/').pop().split('?')[0]}:${y.callFrame.lineNumber + 1}`; if (!seen.has(kk)) { seen.add(kk); incl[kk] = (incl[kk] || 0) + dt; } } });
      const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => (v / 1000).toFixed(0).padStart(6) + ' ms  ' + k).join('\n');
      console.log('SELF\n' + top(self, 14) + '\nINCLUSIVE\n' + top(incl, 30));
    }
    const n = await page.evaluate(() => window.__n);
    const sum = (a) => a.reduce((x, y) => x + y, 0);
    const sorted = [...n.keys].sort((a, b) => a - b);
    rows.push({ rate, lines: LINES, keys: KEYS, outlineCalls: n.outline, symbolCalls: n.symbols, longTasks: n.tasks.length, longTaskMs: sum(n.tasks), maxTaskMs: Math.max(0, ...n.tasks), loafN: n.loaf.length, loafMs: sum(n.loaf),
      keyP50: sorted[Math.floor(sorted.length / 2)], keyMax: sorted[sorted.length - 1], keyMean: Math.round(sum(n.keys) / Math.max(1, n.keys.length)), dodges: n.dodges || 0, dodgeMs: Math.round(n.dodgeMs || 0) });
    await browser.close();
  }
  console.log(JSON.stringify(rows, null, 1));
})();
