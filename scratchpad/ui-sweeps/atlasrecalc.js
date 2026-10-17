// Forced style recalcs and layouts while Atlas is carried and thrown: a CDP
// trace of the carry and the flight, counting UpdateLayoutTree and Layout
// events, and those that came from script (a forced one carries its stack),
// grouped by the function that forced them. Companion to throwframes.js.
// Env: BASE, RATE (4), OUT, BEFORE_DIR (lib.js `routeBefore`).
const fs = require('fs');
const { boot, routeBefore } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await routeBefore(ctx, page);
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await page.evaluate(() => {
    const spot = { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 };
    nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true);
  });
  await sleep(900);
  const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const events = [];
  cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
  const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
  await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline.stack', transferMode: 'ReportEvents' });
  await page.mouse.move(f[0], f[1]);
  await page.mouse.down();
  for (let i = 1; i <= 40; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
  const x0 = f[0] + 480;
  for (let i = 1; i <= 5; i += 1) { await page.mouse.move(x0 + i * 70, f[1] - 40 - i * 6); await sleep(16); }
  await page.mouse.up();
  await sleep(1300);
  await cdp.send('Tracing.end');
  await done;
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const frames = events.filter((e) => e.name === 'BeginFrame' || e.name === 'DrawFrame').length;
  const count = { UpdateLayoutTree: 0, Layout: 0 };
  const forced = new Map();
  let forcedN = 0;
  for (const e of events) {
    if (!(e.name in count) || e.ph === 'E') continue;
    count[e.name] += 1;
    const st = e.args?.beginData?.stackTrace;
    if (st && st.length) {
      forcedN += 1;
      const k = `${e.name} ${st.slice(0, 2).map((s) => `${s.functionName || '(anon)'}:${s.url.split('/').pop().split('?')[0]}:${s.lineNumber + 1}`).join(' < ')}`;
      forced.set(k, (forced.get(k) || 0) + 1);
    }
  }
  // Restyle cost: total ms and elements restyled, forced and not.
  const cost = { forcedMs: 0, freeMs: 0, forcedEls: 0, freeEls: 0 };
  const big = [];
  for (const e of events) {
    if (e.name !== 'UpdateLayoutTree' || e.ph !== 'X') continue;
    const els = e.args?.elementCount ?? e.args?.endData?.elementCount ?? 0;
    const k = e.args?.beginData?.stackTrace?.length ? 'forced' : 'free';
    cost[`${k}Ms`] += (e.dur || 0) / 1000;
    cost[`${k}Els`] += els;
    big.push(els);
  }
  for (const k of Object.keys(cost)) cost[k] = Math.round(cost[k]);
  big.sort((a, b) => b - a);
  const out = { rate: RATE, drawFrames: frames, ...count, forced: forcedN, cost, biggest: big.slice(0, 8), median: big[Math.floor(big.length / 2)], top: [...forced.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12) };
  console.log(JSON.stringify(out, null, 1));
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify(out, null, 1));
  await browser.close();
})();
