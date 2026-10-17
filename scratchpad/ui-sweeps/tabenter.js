// Tab entry cost: click each tab button (the real switchTab path), and for the
// 2 s after the press record rAF frame times, long tasks (>50 ms) with
// timestamps, and optionally a CPU profile ranked by self time. Companion off.
// Two passes: the first visit pays the lazy bundles, the second does not.
// Env: BASE, RATE (default 4), TABS, OUT, PROFILE=1 for the function ranking.
const fs = require('fs');
const { boot } = require('./lib.js');
const TABS = (process.env.TABS || 'notes,dashboard,chat,library,timeline,graph,reminders').split(',');
const RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Profiler.enable');
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => {
    window.__fr = { on: false, dts: [], last: 0, long: [], t0: 0 };
    const loop = (t) => { const f = window.__fr; if (f.on) { if (f.last) f.dts.push([t - f.t0, t - f.last]); f.last = t; } else f.last = 0; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (window.__fr.on) window.__fr.long.push([+(e.startTime - window.__fr.t0).toFixed(0), +e.duration.toFixed(0)]); }).observe({ entryTypes: ['longtask'] });
  });
  // A fresh data dir asks about update checks once; it would block every click.
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  const self = new Map();
  const rows = {};
  for (const pass of [1, 2]) {
    for (const tab of TABS) {
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await page.getByRole('button', { name: "Don't check" }).click({ timeout: 400 }).catch(() => {});
      await page.waitForTimeout(1500);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
      if (process.env.PROFILE) await cdp.send('Profiler.start');
      await page.evaluate(() => { __fr.dts = []; __fr.long = []; __fr.t0 = performance.now(); __fr.on = true; });
      await page.click(`#tab-bar button[data-tab="${tab}"]`, { timeout: 4000 }).catch(async () => { console.log('BLOCKED', tab, await page.evaluate(() => document.querySelector('.confirm-overlay')?.innerText)); });
      await sleep(2000);
      const r = await page.evaluate(() => { __fr.on = false; return { dts: __fr.dts, long: __fr.long }; });
      if (process.env.PROFILE) {
        const prof = (await cdp.send('Profiler.stop')).profile;
        const byId = new Map(prof.nodes.map((nd) => [nd.id, nd]));
        const parent = new Map();
        for (const nd of prof.nodes) for (const c of nd.children || []) parent.set(c, nd.id);
        // A native leaf (querySelectorAll, getBoundingClientRect: the forced
        // style and layout lands there) is blamed on the nearest page-script caller.
        const owner = (nd) => { let cur = nd; while (cur && !cur.callFrame.url.includes('/js/')) cur = byId.get(parent.get(cur.id)); return cur || nd; };
        prof.samples.forEach((id, i) => {
          let nd = byId.get(id); const fn0 = nd.callFrame.functionName;
          if (fn0 === '(idle)' || fn0 === '(program)' || fn0 === '(root)') return;
          const native = nd.callFrame.url === '';
          const nm = native ? fn0 : '';
          nd = owner(nd);
          const fn = (nm ? `${nm} <- ` : '') + nd.callFrame.functionName;
          const key = `${tab} ${fn || '(anon)'} ${nd.callFrame.url.split('/').pop().split('?')[0]}:${nd.callFrame.lineNumber + 1}`;
          self.set(key, (self.get(key) || 0) + (prof.timeDeltas[i] || 0));
        });
      }
      const worst = r.dts.reduce((a, b) => (b[1] > a[1] ? b : a), [0, 0]);
      const over50 = r.dts.filter((d) => d[1] > 50).length;
      rows[`${tab}#${pass}`] = { frames: r.dts.length, worst: +worst[1].toFixed(0), worstAt: +worst[0].toFixed(0), over50, longSum: r.long.reduce((a, b) => a + b[1], 0), long: r.long.slice(0, 6) };
      console.log(`${tab}#${pass}`.padEnd(14), JSON.stringify(rows[`${tab}#${pass}`]));
    }
  }
  if (process.env.PROFILE) {
    console.log('top self time per tab (both passes summed):');
    for (const tab of TABS) {
      const top = [...self.entries()].filter(([k]) => k.startsWith(`${tab} `)).sort((a, b) => b[1] - a[1]).slice(0, 7);
      console.log(' ', tab, top.map(([k, us]) => `${(us / 1000).toFixed(0)}ms ${k.slice(tab.length + 1)}`).join(' | '));
    }
  }
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify(rows, null, 1));
  await browser.close();
})();
