// Probe (L-ui-modernisation-201): where the idle Atlas's main-thread time goes, from a 4 s trace.
const { boot, pinFullFigure } = require('./lib');
(async () => {
  const kind = process.env.KIND || 'atlas';
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await pinFullFigure(page);
  await page.evaluate(async (k) => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, kind);
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(8000);
  const cdp = await page.context().newCDPSession(page);
  const ev = [];
  cdp.on('Tracing.dataCollected', (d) => ev.push(...d.value));
  const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
  await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline,v8.execute', transferMode: 'ReportEvents' });
  await page.waitForTimeout(4000);
  await cdp.send('Tracing.end'); await done;
  const main = ev.find((e) => e.name === 'thread_name' && e.args.name === 'CrRendererMain' && ev.some((x) => x.tid === e.tid && x.name === 'RunTask'));
  const own = ev.filter((e) => e.pid === main.pid && e.tid === main.tid && e.ph === 'X');
  const by = {};
  for (const e of own) { const k = e.name; by[k] = by[k] || [0, 0]; by[k][0] += (e.tdur || e.dur || 0) / 1000; by[k][1]++; }
  const top = Object.entries(by).sort((a, b) => b[1][0] - a[1][0]).slice(0, 16);
  for (const [k, [ms, n]] of top) console.log(`${(ms / 4).toFixed(1)} ms/s  ${n} ${k}`);
  const fns = {};
  for (const e of own.filter((x) => x.name === 'FunctionCall' || x.name === 'TimerFire' || x.name === 'FireAnimationFrame')) {
    const k = `${e.name}:${e.args?.data?.functionName || ''}:${(e.args?.data?.url || '').split('/').pop()}:${e.args?.data?.lineNumber || ''}`; fns[k] = fns[k] || [0, 0]; fns[k][0] += (e.tdur || e.dur) / 1000; fns[k][1]++;
  }
  for (const [k, [ms, n]] of Object.entries(fns).sort((a, b) => b[1][0] - a[1][0]).slice(0, 12)) console.log(`  ${(ms / 4).toFixed(1)} ms/s ${n} ${k}`);
  const ult = own.filter((e) => e.name === 'UpdateLayoutTree'); console.log('ULT elementCount sum/s', ult.reduce((a, e) => a + (e.args?.elementCount || 0), 0) / 4);
  await browser.close();
})();
