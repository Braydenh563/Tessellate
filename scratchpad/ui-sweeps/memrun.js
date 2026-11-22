// L-world-class-24: the ten-minute browser memory check. Headless Chromium,
// typical use in a loop (notes, a note open, search, every tab, the graph,
// Settings), heap sampled at the start, every minute and the end after a
// forced GC (CDP HeapProfiler.collectGarbage + Performance.getMetrics), with
// performance.memory beside it.
//   BASE=http://127.0.0.1:8792 MIN=10 SCRATCH=/tmp/x PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node memrun.js
const { boot } = require('./lib.js');
const MIN = Number(process.env.MIN || 10);
const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline', 'reminders'];
(async () => {
  const { browser, ctx, page } = await boot({ args: ['--enable-precise-memory-info', '--js-flags=--expose-gc'] });
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const ids = await page.evaluate(async () => {
    const r = await fetch('/entries?limit=60', { headers: { 'X-Auth-Token': localStorage.getItem('token') } });
    return (await r.json()).map((e) => e.id);
  });
  const sample = async (label) => {
    const raw = await page.evaluate(() => performance.memory.usedJSHeapSize);
    for (let i = 0; i < 3; i++) { await cdp.send('HeapProfiler.collectGarbage').catch(() => {}); await page.waitForTimeout(300); }
    const by = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    const gc = await page.evaluate(() => performance.memory.usedJSHeapSize);
    const row = { label, rawUsedMB: +(raw / 1048576).toFixed(1), gcUsedMB: +(gc / 1048576).toFixed(1),
      cdpHeapMB: +(by.JSHeapUsedSize / 1048576).toFixed(1), nodes: by.Nodes, listeners: by.JSEventListeners, docs: by.Documents };
    console.log(JSON.stringify(row)); return row;
  };
  const step = async (fn, wait = 350) => { try { await page.evaluate(fn[0], fn[1]); } catch (e) { errors.push(String(e.message).slice(0, 100)); } await page.waitForTimeout(wait); };
  const typeIn = async (sel, text) => { try { await page.fill(sel, text); } catch (e) {} await page.waitForTimeout(500); try { await page.fill(sel, ''); } catch (e) {} };
  await page.waitForTimeout(4000);
  const rows = [await sample('start')];
  const t0 = Date.now(); let minute = 1, loops = 0;
  while (Date.now() - t0 < MIN * 60000) {
    for (const tab of TABS) {
      await step([(n) => switchTab(n), tab], 500);
      if (tab === 'notes') {
        for (let k = 0; k < 3; k++) await step([(id) => openNoteEditor(id), ids[(loops * 3 + k) % ids.length]], 450);
        await typeIn('#finder-input', ['topic1', 'bulk note', 'zebra'][loops % 3]);
      }
      if (tab === 'graph') await page.waitForTimeout(1500);
    }
    await step([() => openSettingsModal('data'), null], 500);
    await step([() => { const m = document.getElementById('settings-modal'); document.getElementById('settings-close')?.click(); }, null], 300);
    loops++;
    if (Date.now() - t0 >= minute * 60000) { rows.push(await sample('min' + minute)); minute++; }
  }
  rows.push(await sample('end'));
  const first = rows[1] || rows[0], last = rows[rows.length - 1];
  console.log(JSON.stringify({ loops, errors: errors.slice(0, 8), startGcMB: rows[0].gcUsedMB, endGcMB: last.gcUsedMB,
    growthAfterMin1MB: +(last.gcUsedMB - first.gcUsedMB).toFixed(1), nodesStartToEnd: [rows[0].nodes, last.nodes], listenersStartToEnd: [rows[0].listeners, last.listeners] }));
  await browser.close();
})().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
