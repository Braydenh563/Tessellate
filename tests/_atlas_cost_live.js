// What a class change on #nm-buddy, a mood change and a click on the face cost (ledger L232, L233, L238).
// Prints one JSON object. Env: BASE, SWEEPS (scratchpad/ui-sweeps), CPU (slowdown, 4), RUNS (3).
const fs = require('fs');
const os = require('os');
const { boot, setBuddy } = require(process.env.SWEEPS + '/lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const med = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
(async () => {
  const CPU = Number(process.env.CPU || 4);
  const runs = { elems: [], moodStyles: [], moodLayouts: [], ptr: [], click: [] };
  for (let run = 0; run < Number(process.env.RUNS || 3); run++) {
    const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
    await setBuddy(page, 'atlas');
    await page.evaluate(() => revealTab('dashboard'));
    await page.waitForSelector('#nm-buddy .nm-buddy-face', { state: 'attached', timeout: 15000 });
    await sleep(4000);
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Performance.enable');
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
    const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    const styles = []; const layouts = [];
    for (const mood of ['happy', 'calm', 'curious', 'calm', 'happy', 'calm']) {
      await sleep(700);
      const a = await m();
      await page.evaluate(async (mm) => { setAtlasMood(mm, 0, { quiet: true }); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }, mood);
      const b = await m();
      styles.push(b.RecalcStyleCount - a.RecalcStyleCount); layouts.push(b.LayoutCount - a.LayoutCount);
    }
    runs.moodStyles.push(med(styles)); runs.moodLayouts.push(med(layouts));
    const tp = `${os.tmpdir()}/atlas-cost-${process.pid}-${run}.json`;
    await browser.startTracing(page, { path: tp, categories: ['devtools.timeline', 'disabled-by-default-devtools.timeline'] });
    await page.evaluate(async () => {
      const b = document.getElementById('nm-buddy');
      for (let i = 0; i < 6; i++) { b.classList.toggle('zz-probe'); await new Promise((r) => setTimeout(r, 300)); }
      b.classList.remove('zz-probe');
    });
    await browser.stopTracing();
    const tr = JSON.parse(fs.readFileSync(tp, 'utf8')).traceEvents;
    fs.unlinkSync(tp);
    // The recalcs the six toggles caused are the largest ones in the window.
    const big = tr.filter((e) => e.name === 'UpdateLayoutTree' && e.ph === 'X' && e.args && e.args.elementCount != null).map((e) => e.args.elementCount).sort((x, y) => y - x).slice(0, 6);
    runs.elems.push(med(big));
    await page.evaluate(() => { window.__ev = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__ev.push([e.name, e.processingEnd - e.processingStart]); }).observe({ type: 'event', durationThreshold: 16, buffered: true }); });
    const box = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
    for (let i = 0; i < 4; i++) { await page.mouse.move(box.x, box.y); await page.mouse.down(); await page.mouse.up(); await sleep(900); }
    const ev = await page.evaluate(() => window.__ev);
    const worst = (n) => Math.max(0, ...ev.filter((e) => e[0] === n).map((e) => e[1]));
    runs.ptr.push(worst('pointerup')); runs.click.push(worst('click'));
    await browser.close();
  }
  console.log(JSON.stringify({ cpu: CPU, elems: med(runs.elems), moodStyles: med(runs.moodStyles), moodLayouts: med(runs.moodLayouts), pointerupMs: med(runs.ptr), clickMs: med(runs.click), runs }));
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
