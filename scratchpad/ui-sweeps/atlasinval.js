// What a thrown Atlas restyles each frame: Chromium's style invalidation
// tracking over the flight (the 1.3 s after the release), grouped by the
// element and the reason, per drawn frame. Companion to atlasrecalc.js.
// Env: BASE, RATE (1), PHASE (flight | carry), TOP (30), BEFORE_DIR (lib.js `routeBefore`).
const { boot, routeBefore } = require('./lib.js');
const RATE = Number(process.env.RATE || 1);
const PHASE = process.env.PHASE || 'flight';
const TOP = Number(process.env.TOP || 30);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await routeBefore(ctx, page);
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await page.evaluate(() => nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 }, true));
  await sleep(900);
  const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const events = [];
  cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
  const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
  const start = () => cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline.invalidationTracking', transferMode: 'ReportEvents' });
  if (PHASE === 'carry') {
    await page.mouse.move(f[0], f[1]);
    await page.mouse.down();
    await start();
    for (let i = 1; i <= 40; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
  } else {
    // A flick's release speed depends on the pointer's timing, and a slow one is a drop, not a
    // throw: the flight is started directly, the same throw every run, with its random feel fixed.
    await start();
    await page.evaluate(async () => {
      await ensureModule('companionThrow');
      const r = Math.random;
      Math.random = () => 0.5;
      nameMarkBuddyThrow(document.getElementById('nm-buddy'), 1.6, -0.9, nameMarkBuddyWorld(nameMarkBuddyTab()));
      Math.random = r;
    });
    await sleep(1300);
  }
  await cdp.send('Tracing.end');
  if (PHASE === 'carry') await page.mouse.up();
  await done;
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const recalcs = events.filter((e) => e.name === 'UpdateLayoutTree' && e.ph === 'X');
  const by = new Map();
  let n = 0;
  for (const e of events) {
    if (!/Invalidation/.test(e.name)) continue;
    const d = e.args?.data || {};
    n += 1;
    const k = `${e.name} ${d.nodeName || ''} ${d.reason || d.invalidationList?.[0]?.classes?.join('.') || ''} ${d.changedAttribute || d.changedClass || d.changedId || d.changedPseudo || ''}`.replace(/\s+/g, ' ');
    by.set(k, (by.get(k) || 0) + 1);
  }
  const els = recalcs.reduce((a, e) => a + (e.args?.elementCount ?? 0), 0);
  console.log(JSON.stringify({ phase: PHASE, rate: RATE, recalcs: recalcs.length, elements: els, perRecalc: +(els / Math.max(1, recalcs.length)).toFixed(1), ms: Math.round(recalcs.reduce((a, e) => a + e.dur, 0) / 1000), invalidations: n }));
  for (const [k, c] of [...by.entries()].sort((a, b) => b[1] - a[1]).slice(0, TOP)) console.log(c, k.slice(0, 220));
  await browser.close();
})();
