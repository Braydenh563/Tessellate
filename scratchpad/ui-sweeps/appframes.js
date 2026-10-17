// B87b: what the app costs per frame, app-wide, with the companion off (so the
// companion is not in the ranking) and the CPU slowed by CDP
// Emulation.setCPUThrottlingRate (RATE, default 4). For each tab: 3 s idle,
// then 3 s of small wheel steps; per phase the frame times from a
// requestAnimationFrame loop (fps, median, p95, worst) and the main-thread
// time per frame split into style, layout and script from Performance
// getMetrics; and over everything a CPU profile ranked by self time per
// function. Prints the ranking last.
// Env: BASE, TABS (dashboard,notes,chat,library,timeline,graph), RATE, OUT.
const fs = require('fs');
const { boot } = require('./lib.js');
const TABS = (process.env.TABS || 'dashboard,notes,chat,library,timeline,graph').split(',');
const RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stats = (dts) => {
  if (!dts.length) return null;
  const s = [...dts].sort((a, b) => a - b);
  const total = dts.reduce((a, b) => a + b, 0);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(q * s.length))];
  return { frames: dts.length, fps: +(dts.length / (total / 1000)).toFixed(1), median: +at(0.5).toFixed(1), p95: +at(0.95).toFixed(1), worst: +s[s.length - 1].toFixed(1) };
};
const metrics = async (cdp) => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));

(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  await cdp.send('Profiler.enable');
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => {
    window.__fr = { on: false, dts: [], last: 0 };
    const loop = (t) => { const f = window.__fr; if (f.on) { if (f.last) f.dts.push(t - f.last); f.last = t; } else f.last = 0; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
  const self = new Map();
  const phases = {};
  for (const tab of TABS) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    await page.evaluate((t) => revealTab(t), tab);
    await page.waitForTimeout(3000);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
    for (const phase of ['idle', 'scroll']) {
      await page.evaluate(() => { __fr.dts = []; __fr.on = true; });
      const m0 = await metrics(cdp);
      await cdp.send('Profiler.start');
      if (phase === 'idle') await sleep(3000);
      else {
        await page.mouse.move(700, 450);
        for (let i = 0; i < 40; i += 1) { await page.mouse.wheel(0, 40); await sleep(70); }
      }
      const prof = (await cdp.send('Profiler.stop')).profile;
      const dts = await page.evaluate(() => { __fr.on = false; return [...__fr.dts]; });
      const m1 = await metrics(cdp);
      const n = Math.max(1, dts.length);
      const per = (k) => +(((m1[k] - m0[k]) * 1000) / n).toFixed(2);
      phases[`${tab}/${phase}`] = { ...stats(dts), styleMs: per('RecalcStyleDuration'), layoutMs: per('LayoutDuration'), scriptMs: per('ScriptDuration') };
      const byId = new Map(prof.nodes.map((nd) => [nd.id, nd]));
      prof.samples.forEach((id, i) => {
        const nd = byId.get(id);
        const fn = nd.callFrame.functionName;
        if (fn === '(idle)' || fn === '(program)' || fn === '(root)') return;
        const key = `${fn || '(anon)'} ${nd.callFrame.url.split('/').pop().split('?')[0]}:${nd.callFrame.lineNumber + 1}`;
        self.set(key, (self.get(key) || 0) + (prof.timeDeltas[i] || 0));
      });
      console.log(`${tab}/${phase}`.padEnd(18), JSON.stringify(phases[`${tab}/${phase}`]));
    }
  }
  const top = [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, us]) => `${(us / 1000).toFixed(0)}ms ${k}`);
  console.log('top self time (all tabs, all phases):');
  for (const t of top) console.log('  ', t);
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify({ phases, top }, null, 1));
  await browser.close();
})();
