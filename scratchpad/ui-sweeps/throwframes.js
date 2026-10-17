// B87a (the owner: throwing the companion is "framey and laggy"): frame times
// of a carry (the pointer dragging it) and of a throw (its flight), measured
// in the page by a requestAnimationFrame loop, with the CPU slowed by CDP
// Emulation.setCPUThrottlingRate (RATE, default 4; 1 for none). Per phase:
// frames, fps, median and p95 and worst frame in ms, and the share of frames
// over 33 ms; "air" is the frames while it flies (nmb.flight set), the landing left out. Also CDP Performance.getMetrics deltas for the phase (style
// recalc, layout and script ms per frame) and, with PROFILE=1, the top
// self-time functions from a CPU profile of the phase.
// Env: BASE, KINDS (me,atlas), TAB (notes), RATE (4), RUNS (3), PROFILE, OUT.
const fs = require('fs');
const { boot, routeBefore } = require('./lib.js');
const KINDS = (process.env.KINDS || 'me,atlas').split(',');
const TAB = process.env.TAB || 'notes';
const RATE = Number(process.env.RATE || 4);
const RUNS = Number(process.env.RUNS || 3);
const PROFILE = process.env.PROFILE;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const stats = (dts) => {
  if (!dts.length) return null;
  const s = [...dts].sort((a, b) => a - b);
  const total = dts.reduce((a, b) => a + b, 0);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(q * s.length))];
  return { frames: dts.length, fps: +(dts.length / (total / 1000)).toFixed(1), median: +at(0.5).toFixed(1), p95: +at(0.95).toFixed(1), worst: +s[s.length - 1].toFixed(1), over33: +(dts.filter((d) => d > 33.4).length / dts.length * 100).toFixed(0) };
};
const metrics = async (cdp) => {
  const { metrics: m } = await cdp.send('Performance.getMetrics');
  return Object.fromEntries(m.map((x) => [x.name, x.value]));
};
const perFrame = (a, b, frames) => {
  const ms = (k) => +(((b[k] - a[k]) * 1000) / Math.max(1, frames)).toFixed(2);
  return { style: ms('RecalcStyleDuration'), layout: ms('LayoutDuration'), script: ms('ScriptDuration'), task: ms('TaskDuration') };
};

(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  // BEFORE_DIR: older copies of frontend js or css files served in place of the current ones,
  // to measure the same gesture against the code as it was (lib.js `routeBefore`).
  await routeBefore(ctx, page);
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  if (PROFILE) await cdp.send('Profiler.enable');
  const result = {};
  for (const kind of KINDS) {
    await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, kind);
    await page.evaluate((tab) => revealTab(tab), TAB);
    await page.waitForTimeout(3500);
    await page.evaluate(() => {
      if (window.__frLoop) return;
      window.__frLoop = true;
      window.__fr = { on: false, dts: [], air: [], last: 0 };
      const loop = (t) => { const f = window.__fr; if (f.on) { if (f.last) { f.dts.push(t - f.last); if (typeof nmb !== "undefined" && nmb.flight) f.air.push(t - f.last); } f.last = t; } else f.last = 0; requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    });
    const faceMid = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    const put = async (x, y) => {
      await page.evaluate(([px, py]) => {
        const spot = { kind: 'yours', pose: 'float', legs: '', x: px, y: py };
        nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true);
        nmb.placedAt = Date.now();
        const spots = nameMarkBuddySpots();
        spots[nameMarkBuddyTab()] = nameMarkBuddySpotFor(spot);
        nameMarkBuddyKeepSpots(spots);
      }, [x, y]);
      await sleep(800);
    };
    const runs = { carry: [], flight: [] };
    const cost = { carry: [], flight: [] };
    for (let run = 0; run < RUNS; run += 1) {
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await put(180, 380);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
      const f = await faceMid();
      // Carry: 40 moves a frame apart across 600px, then a flick of five fast ones and let go.
      await page.mouse.move(f[0], f[1]);
      await page.mouse.down();
      const m0 = await metrics(cdp);
      await page.evaluate(() => { __fr.dts = []; __fr.air = []; __fr.on = true; });
      if (PROFILE) await cdp.send('Profiler.start');
      for (let i = 1; i <= 40; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
      const carry = await page.evaluate(() => { __fr.on = false; return [...__fr.dts]; });
      const m1 = await metrics(cdp);
      // The flick, with the frame loop on again through the flight (to rest, 2.5 s at most).
      await page.evaluate(() => { __fr.dts = []; __fr.air = []; __fr.on = true; });
      const x0 = f[0] + 480;
      for (let i = 1; i <= 5; i += 1) { await page.mouse.move(x0 + i * 70, f[1] - 40 - i * 6); await sleep(16); }
      await page.mouse.up();
      await sleep(2600);
      const [flight, air] = await page.evaluate(() => { __fr.on = false; return [[...__fr.dts], [...__fr.air]]; });
      (runs.air ||= []).push(air);
      const m2 = await metrics(cdp);
      let prof = null;
      if (PROFILE) prof = (await cdp.send('Profiler.stop')).profile;
      runs.carry.push(carry);
      // The flight window includes the settle after the throw; only the frames while it flew count: the first 1.3 s.
      let acc = 0;
      runs.flight.push(flight.filter((d) => { acc += d; return acc <= 1300; }));
      // DUMP=1: each run's flight frame times, to see where the long ones fall.
      if (process.env.DUMP) console.log(kind, 'flight dts', runs.flight[runs.flight.length - 1].map((d) => Math.round(d)).join(' '));
      cost.carry.push(perFrame(m0, m1, carry.length));
      cost.flight.push(perFrame(m1, m2, flight.length));
      if (prof && run === 0) {
        const self = new Map();
        const byId = new Map(prof.nodes.map((n) => [n.id, n]));
        const dt = prof.timeDeltas;
        prof.samples.forEach((id, i) => { const n = byId.get(id); const k = `${n.callFrame.functionName || '(anon)'} ${n.callFrame.url.split('/').pop()}:${n.callFrame.lineNumber + 1}`; self.set(k, (self.get(k) || 0) + (dt[i] || 0)); });
        result[`${kind}-profile`] = [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, us]) => `${(us / 1000).toFixed(0)}ms ${k}`);
        // Who calls the native layout and style reads: their self time by caller.
        const parent = new Map();
        for (const n of prof.nodes) for (const c of n.children || []) parent.set(c, n);
        const by = new Map();
        prof.samples.forEach((id, i) => {
          const n = byId.get(id);
          if (!/^(getBoundingClientRect|getAnimations|getComputedStyle|offset\w+)$/.test(n.callFrame.functionName)) return;
          const p = parent.get(id);
          const k = `${n.callFrame.functionName} < ${p?.callFrame.functionName || '(anon)'}:${(p?.callFrame.url || '').split('/').pop().split('?')[0]}:${(p?.callFrame.lineNumber ?? -1) + 1}`;
          by.set(k, (by.get(k) || 0) + (dt[i] || 0));
        });
        result[`${kind}-readers`] = [...by.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, us]) => `${(us / 1000).toFixed(0)}ms ${k}`);
        console.log(kind, 'readers', JSON.stringify(result[`${kind}-readers`]));
      }
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
      await sleep(500);
    }
    result[kind] = { rate: RATE, carry: stats(runs.carry.flat()), flight: stats(runs.flight.flat()), air: stats((runs.air || []).flat()), carryCostPerFrame: cost.carry, flightCostPerFrame: cost.flight };
    console.log(kind, JSON.stringify({ rate: RATE, carry: result[kind].carry, flight: result[kind].flight, air: result[kind].air }));
    console.log(kind, 'cost/frame carry', JSON.stringify(cost.carry[0]), 'flight', JSON.stringify(cost.flight[0]));
    if (result[`${kind}-profile`]) console.log(kind, 'profile', JSON.stringify(result[`${kind}-profile`]));
  }
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify(result, null, 1));
  await browser.close();
})();
