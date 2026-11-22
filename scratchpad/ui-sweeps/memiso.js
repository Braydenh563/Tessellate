// Which step of the memory loop (memrun.js) grows? Each action runs alone,
// 3 warm-up rounds then REPS measured rounds, listeners and DOM nodes read
// after a forced GC; the per-round growth is the number that matters.
const { boot } = require('./lib.js');
const REPS = Number(process.env.REPS || 20);
(async () => {
  const { browser, ctx, page } = await boot({ args: ['--js-flags=--expose-gc'] });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const ids = await page.evaluate(async () => (await (await fetch('/entries?limit=60', { headers: { 'X-Auth-Token': localStorage.getItem('token') } })).json()).map((e) => e.id));
  const read = async () => {
    for (let i = 0; i < 3; i++) { await cdp.send('HeapProfiler.collectGarbage').catch(() => {}); await page.waitForTimeout(250); }
    const by = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    return { l: by.JSEventListeners, n: by.Nodes, h: by.JSHeapUsedSize / 1048576 };
  };
  const ev = async (fn, arg) => { try { await page.evaluate(fn, arg); } catch (e) {} };
  let k = 0;
  const actions = {
    'tab:dashboard': async () => { await ev((n) => switchTab(n), 'dashboard'); await ev((n) => switchTab(n), 'notes'); },
    'tab:library': async () => { await ev((n) => switchTab(n), 'library'); await ev((n) => switchTab(n), 'notes'); },
    'tab:chat': async () => { await ev((n) => switchTab(n), 'chat'); await ev((n) => switchTab(n), 'notes'); },
    'tab:graph': async () => { await ev((n) => switchTab(n), 'graph'); await page.waitForTimeout(800); await ev((n) => switchTab(n), 'notes'); },
    'tab:timeline': async () => { await ev((n) => switchTab(n), 'timeline'); await ev((n) => switchTab(n), 'notes'); },
    'tab:reminders': async () => { await ev((n) => switchTab(n), 'reminders'); await ev((n) => switchTab(n), 'notes'); },
    'note-open': async () => { await ev((id) => openNoteEditor(id), ids[k++ % ids.length]); },
    'search': async () => { await page.fill('#finder-input', 'topic' + (k++ % 9)).catch(() => {}); await page.waitForTimeout(500); await page.fill('#finder-input', '').catch(() => {}); },
    'settings': async () => { await ev(() => openSettingsModal('data')); await page.waitForTimeout(200); await ev(() => document.getElementById('settings-close')?.click()); },
  };
  const only = process.env.ONLY;
  await ev((n) => switchTab(n), 'notes'); await page.waitForTimeout(3000);
  for (const [name, run] of Object.entries(actions)) {
    if (only && !name.includes(only)) continue;
    for (let i = 0; i < 3; i++) { await run(); await page.waitForTimeout(300); }
    const a = await read();
    for (let i = 0; i < REPS; i++) { await run(); await page.waitForTimeout(300); }
    const b = await read();
    console.log(`${name.padEnd(15)} listeners/round ${((b.l - a.l) / REPS).toFixed(1).padStart(7)}  nodes/round ${((b.n - a.n) / REPS).toFixed(1).padStart(8)}  heapKB/round ${(((b.h - a.h) * 1024) / REPS).toFixed(0).padStart(6)}`);
  }
  await browser.close();
})().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
