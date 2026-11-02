// INBOX 1534: a tab press's own task at 4x CPU, with a profile of what it ran.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await page.waitForTimeout(3000);
  const tabs = (process.env.TABS || 'dashboard,notes,chat,timeline,library,dashboard,chat').split(',');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  for (const t of tabs) {
    await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 200 }); await cdp.send('Profiler.start');
    const ms = await page.evaluate((t) => { const s = performance.now(); document.getElementById(`tab-btn-${t}`).click(); return performance.now() - s; }, t);
    const { profile } = await cdp.send('Profiler.stop');
    const byId = new Map(profile.nodes.map((n) => [n.id, n])); const parent = new Map();
    profile.nodes.forEach((n) => (n.children || []).forEach((c) => parent.set(c, n.id)));
    const self = {}, incl = {};
    const key = (x) => `${x.callFrame.functionName || '(anon)'} ${x.callFrame.url.split('/').pop().split('?')[0]}:${x.callFrame.lineNumber + 1}`;
    profile.samples.forEach((id, i) => { const dt = profile.timeDeltas[i] / 1000; const x = byId.get(id); self[key(x)] = (self[key(x)] || 0) + dt;
      const seen = new Set(); for (let c = id; c; c = parent.get(c)) { const k = key(byId.get(c)); if (!seen.has(k)) { seen.add(k); incl[k] = (incl[k] || 0) + dt; } } });
    const top = (o, n) => Object.entries(o).filter(([k]) => !/^\((idle|program|root)/.test(k)).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => `${v.toFixed(0)} ${k}`).join(' | ');
    console.log(`${t}: click ${ms.toFixed(0)}ms\n  self: ${top(self, 6)}\n  incl: ${top(incl, 10)}`);
    await page.waitForTimeout(1500);
  }
  await browser.close();
})();
