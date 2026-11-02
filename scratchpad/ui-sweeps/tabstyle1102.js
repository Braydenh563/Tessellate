// INBOX 1534: which script forces each style pass and layout in a tab press (trace with stacks), 4x CPU.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(3000);
  const cdp = await page.context().newCDPSession(page);
  const order = (process.env.TABS || 'dashboard,chat,notes,chat,timeline,library').split(',');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  for (const t of order) {
    const events = [];
    cdp.removeAllListeners('Tracing.dataCollected');
    cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
    const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
    await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.stack', transferMode: 'ReportEvents' });
    await page.evaluate((t) => new Promise((ok) => { document.getElementById(`tab-btn-${t}`).click(); requestAnimationFrame(() => setTimeout(ok, 30)); }), t);
    await cdp.send('Tracing.end'); await done;
    const rows = {};
    for (const e of events) {
      if (!['UpdateLayoutTree', 'Layout'].includes(e.name) || e.ph !== 'X') continue;
      const st = e.args?.beginData?.stackTrace || e.args?.data?.stackTrace;
      const where = st && st.length ? st.slice(0, 2).map((f) => `${f.functionName || '(anon)'} ${f.url.split('/').pop().split('?')[0]}:${f.lineNumber + 1}`).join(' < ') : '(frame)';
      const k = `${e.name === 'Layout' ? 'L' : 'S'} ${where}`;
      rows[k] = rows[k] || [0, 0]; rows[k][0]++; rows[k][1] += e.dur / 1000;
    }
    console.log(`== ${t}`);
    for (const [k, [n, ms]] of Object.entries(rows).sort((a, b) => b[1][1] - a[1][1]).slice(0, 9)) console.log(`  ${ms.toFixed(0).padStart(4)}ms x${n} ${k}`);
    await page.waitForTimeout(1200);
  }
  await browser.close();
})();
