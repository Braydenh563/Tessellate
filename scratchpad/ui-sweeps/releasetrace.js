// companion-1018: the release task, traced (Tracing, devtools.timeline). Per run: how long the
// pointer-up handler ran, how many restyles (UpdateLayoutTree) and layouts it forced and what they
// cost, and the elements each restyled. THROW=1 flicks it instead of dropping it. With LANDING=1
// the window is the landing frame of the flight instead (the last long task).
// Env: BASE, KIND (atlas), RATE (4), RUNS (3), THROW, BEFORE_DIR (older js/css served in place), LIST (print every event).
const { boot, routeBefore } = require('./lib.js');
const KIND = process.env.KIND || 'atlas', RATE = Number(process.env.RATE || 4), RUNS = Number(process.env.RUNS || 3);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await routeBefore(ctx, page);
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  const events = [];
  cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
  const rows = [];
  for (let run = 0; run < RUNS; run += 1) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    await page.evaluate(() => { nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 }, true); nmb.placedAt = Date.now(); });
    await sleep(900);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
    const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    await page.mouse.move(f[0], f[1]); await page.mouse.down();
    for (let i = 1; i <= 30; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
    if (process.env.THROW) { const x0 = f[0] + 360; for (let i = 1; i <= 5; i += 1) { await page.mouse.move(x0 + i * 70, f[1] - 40 - i * 6); await sleep(16); } } else await sleep(300);
    events.length = 0;
    await cdp.send('Tracing.start', { traceConfig: { includedCategories: ['devtools.timeline', 'disabled-by-default-devtools.timeline'] } });
    await page.mouse.up();
    await sleep(process.env.THROW ? 2800 : 700);
    const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
    await cdp.send('Tracing.end'); await done;
    const x = events.filter((e) => e.ph === 'X');
    const rel = x.find((e) => e.name === 'FunctionCall' && e.args?.data?.functionName === 'release');
    const within = (a, e) => e.ts >= a.ts && e.ts + e.dur <= a.ts + a.dur + 1;
    const sum = (list) => +(list.reduce((s, e) => s + e.dur, 0) / 1000).toFixed(0);
    const inRel = rel ? x.filter((e) => within(rel, e)) : [];
    const ult = inRel.filter((e) => e.name === 'UpdateLayoutTree'), lay = inRel.filter((e) => e.name === 'Layout');
    // The landing task of a throw: the longest main-thread task after the release one.
    const tasks = x.filter((e) => e.name === 'RunTask' && e.dur > 40000).sort((a, b) => a.ts - b.ts);
    const row = { release: rel ? +(rel.dur / 1000).toFixed(0) : null, restyles: ult.length, restyleMs: sum(ult), els: ult.map((e) => e.args?.elementCount), layouts: lay.length, layoutMs: sum(lay), longTasks: tasks.map((e) => +(e.dur / 1000).toFixed(0)), allRestyles: x.filter((e) => e.name === 'UpdateLayoutTree').length, allRestyleMs: sum(x.filter((e) => e.name === 'UpdateLayoutTree')), bigRestyles: x.filter((e) => e.name === 'UpdateLayoutTree' && e.args?.elementCount > 300).length, worstTask: tasks.length ? Math.max(...tasks.map((e) => +(e.dur / 1000).toFixed(0))) : 0 };
    row.tasks = tasks.filter((t) => t.dur > 100000).map((t) => `${((t.ts - (rel ? rel.ts : t.ts)) / 1000).toFixed(0)}ms+${(t.dur / 1000).toFixed(0)}: ` + x.filter((e) => e.name === 'UpdateLayoutTree' && within(t, e)).map((e) => `${(e.dur / 1000).toFixed(0)}ms/${e.args?.elementCount}`).join(' '));
    rows.push(row);
    console.log(JSON.stringify(row));
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    await sleep(500);
  }
  const med = (k) => rows.map((r) => r[k]).sort((a, b) => a - b)[rows.length >> 1];
  console.log('median', KIND, process.env.THROW ? 'throw' : 'drop', 'rate', RATE, JSON.stringify({ release: med('release'), restyles: med('restyles'), restyleMs: med('restyleMs'), allRestyles: med('allRestyles'), bigRestyles: med('bigRestyles'), allRestyleMs: med('allRestyleMs'), worstTask: med('worstTask'), layouts: med('layouts'), layoutMs: med('layoutMs') }), process.env.BEFORE_DIR ? 'BEFORE' : 'AFTER');
  await browser.close();
})();
