// L-ui-modernisation-95: the companion's idle cost in CPU time, not wall time (a busy
// runner doubles TaskDuration and frame counts, never the CPU a renderer burns). Per kind
// (off, me, atlas): the main thread's on-CPU ms per second idle, and per wheel step
// while scrolling, from /proc schedstat (lib.js mainCpuMs); medians over RUNS, kinds
// interleaved so a drifting machine hits all three alike. No frame counter, trace or
// profiler: each would be a dirty frame of its own.
//   node scratchpad/ui-sweeps/companioncpu.js     (RUNS=5 MS=4000 TAB=dashboard)
// Budgets (never widened): scroll +1 ms per step, atlas idle +120 ms/s over off.
const { boot, mainCpuMs } = require('./lib.js');
const RUNS = Number(process.env.RUNS || 3);
const MS = Number(process.env.MS || 4000);
const TAB = process.env.TAB || 'dashboard';
const KINDS = (process.env.KINDS || 'off,me,atlas').split(',');
const med = (a) => a.slice().sort((x, y) => x - y)[a.length >> 1];

async function one(kind) {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(async (k) => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, kind);
  await page.evaluate((t) => revealTab(t), TAB);
  await page.waitForTimeout(6000);
  const c0 = await mainCpuMs(browser);
  await page.waitForTimeout(MS);
  const idle = (await mainCpuMs(browser) - c0) / (MS / 1000);
  await page.mouse.move(720, 500);
  const s0 = await mainCpuMs(browser); let steps = 0; const end = Date.now() + MS;
  while (Date.now() < end) { await page.mouse.wheel(0, 12 * (steps % 120 < 60 ? 1 : -1)); await page.waitForTimeout(16); steps += 1; }
  const scroll = (await mainCpuMs(browser) - s0) / steps;
  await browser.close();
  return { idle, scroll };
}

(async () => {
  const got = Object.fromEntries(KINDS.map((k) => [k, []]));
  for (let i = 0; i < RUNS; i++) for (const k of KINDS) { const r = await one(k); got[k].push(r); console.log(i, k, r.idle.toFixed(0), 'ms/s idle', r.scroll.toFixed(2), 'ms/step scrolling'); }
  const m = Object.fromEntries(KINDS.map((k) => [k, { idle: med(got[k].map((r) => r.idle)), scroll: med(got[k].map((r) => r.scroll)) }]));
  console.log(JSON.stringify(m));
  let bad = false;
  for (const k of KINDS.filter((x) => x !== 'off')) {
    const dI = m[k].idle - m.off.idle; const dS = m[k].scroll - m.off.scroll;
    console.log(`${k}: +${dI.toFixed(0)} ms/s idle CPU (limit 120 for atlas), +${dS.toFixed(2)} ms/step scrolling (limit 1)`);
    if (dS > 1 || (k === 'atlas' && dI > 120)) bad = true;
  }
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
})();
