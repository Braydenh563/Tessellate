// Boot long tasks (L-world-class-354, the follow-on of L971): every task over 50 ms between
// opening the app signed in and the dashboard going quiet, attributed to a function by the
// long-animation-frame (LoAF) scripts list, at no throttle and at 4x CPU. PASS or FAIL per task.
//
//   BASE=http://127.0.0.1:8812 SCRATCH=<dir> node scratchpad/ui-sweeps/bootlongtasks.js
//
// Env: RATES (default "1,4"), BAR (50 ms), RUNS (3: the worst of each rate is the verdict),
// SETTLE (ms of quiet to wait after the shell shows, 4000), TRACE=<file> writes a Chromium
// trace of the last 4x run. The login happens once in a first context; every measured run
// is a cold load in a fresh context that carries that login (the "boot after login").
// A long task is attributed to the LoAF whose window holds it: the script with the most time
// in that frame (invoker, source file, function), plus that frame's forced style and layout ms.
const { boot } = require('./lib.js');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');

const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const BAR = Number(process.env.BAR || 50);
const RATES = (process.env.RATES || '1,4').split(',').map(Number);
const RUNS = Number(process.env.RUNS || 3);
const SETTLE = Number(process.env.SETTLE || 4000);
const STATE = (process.env.SCRATCH || '.') + '/bootlt-state.json';

const OBSERVE = () => {
  window.__lt = { longtask: [], loaf: [], event: [] };
  const add = (type, list, map) => {
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) list.push(map(e)); })
        .observe({ type, buffered: true, ...(type === 'event' ? { durationThreshold: 16 } : {}) });
    } catch (e) {}
  };
  add('longtask', window.__lt.longtask, (e) => ({ s: e.startTime, d: e.duration }));
  add('long-animation-frame', window.__lt.loaf, (e) => ({
    s: e.startTime, d: e.duration, block: e.blockingDuration, sl: e.styleAndLayoutStart,
    scripts: e.scripts.map((x) => ({
      d: x.duration, forced: x.forcedStyleAndLayoutDuration, type: x.invokerType, inv: x.invoker,
      src: String(x.sourceURL || '').replace(/^.*\/js\//, '').replace(/\?.*$/, ''),
      fn: x.sourceFunctionName, pos: x.sourceCharPosition, exec: x.executionStart,
    })),
  }));
  add('event', window.__lt.event, (e) => ({ s: e.startTime, d: e.duration, n: e.name, proc: e.processingEnd - e.processingStart, t: e.target && (e.target.id || e.target.className || e.target.tagName) }));
};

function attribute(loaf) {
  if (!loaf) return 'no LoAF covers it';
  const top = [...loaf.scripts].sort((a, b) => b.d - a.d)[0];
  const forced = loaf.scripts.reduce((a, x) => a + (x.forced || 0), 0);
  const render = Math.max(0, loaf.d - (loaf.sl || loaf.d));
  const who = top ? `${top.src}:${top.fn || top.inv || '(anon)'}@${top.pos} ${Math.round(top.d)}ms (${top.type})` : 'no script';
  return `${who}; scripts ${loaf.scripts.length}, forced style+layout ${Math.round(forced)}ms, render ${Math.round(render)}ms`;
}

async function oneRun(browser, rate, traceFile) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: STATE });
  await ctx.addInitScript(OBSERVE);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  if (rate > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  if (traceFile) await browser.startTracing(page, { path: traceFile, categories: ['devtools.timeline', 'disabled-by-default-devtools.timeline', 'v8.execute', 'blink.user_timing'] });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const splash = document.getElementById('boot-splash');
    const ov = document.getElementById('lock-overlay');
    return (!splash || splash.classList.contains('hidden')) && ov && ov.classList.contains('hidden')
      && !document.documentElement.classList.contains('shell-curtain');
  }, null, { timeout: 120000, polling: 100 });
  await page.waitForTimeout(SETTLE * (rate > 1 ? 1.5 : 1));
  const data = await page.evaluate(() => window.__lt);
  if (traceFile) await browser.stopTracing();
  await ctx.close();
  return data;
}

(async () => {
  const first = await boot();
  await first.ctx.storageState({ path: STATE });
  await first.browser.close();
  const browser = await chromium.launch();
  let failed = 0;
  for (const rate of RATES) {
    const runs = [];
    for (let i = 0; i < RUNS; i += 1) runs.push(await oneRun(browser, rate, process.env.TRACE && rate === RATES[RATES.length - 1] && i === RUNS - 1 ? process.env.TRACE : null));
    // The worst run is the verdict: a boot is judged on its bad day, not its median.
    const worst = (r) => Math.max(0, ...r.longtask.map((t) => t.d));
    const pick = [...runs].sort((a, b) => worst(b) - worst(a))[0];
    console.log(`\n== ${rate}x CPU, worst of ${RUNS} runs; per-run longest long task: ${runs.map((r) => Math.round(worst(r))).join(', ')} ms`);
    const tasks = pick.longtask.map((t) => {
      const l = pick.loaf.find((f) => t.s >= f.s - 1 && t.s <= f.s + f.d + 1);
      return { t, l };
    });
    if (!tasks.length) console.log('no long task over 50 ms');
    for (const { t, l } of tasks) {
      const ok = t.d <= BAR;
      if (!ok) failed += 1;
      console.log(`${ok ? 'PASS' : 'FAIL'} ${Math.round(t.d)} ms at ${Math.round(t.s)} ms: ${attribute(l)}`);
      if (process.env.DETAIL && l) for (const x of l.scripts) console.log(`     ${Math.round(x.d)} ms ${x.type} ${x.src}:${x.fn || x.inv}@${x.pos} forced ${Math.round(x.forced || 0)}`);
    }
    const forced = pick.loaf.reduce((a, f) => a + f.scripts.reduce((b, x) => b + (x.forced || 0), 0), 0);
    const bigLoaf = pick.loaf.filter((f) => f.d > BAR && !tasks.some(({ l }) => l === f));
    console.log(`boot forced style+layout (sum over frames): ${Math.round(forced)} ms; frames over ${BAR} ms with no long task: ${bigLoaf.length}`);
    for (const f of bigLoaf) console.log(`  frame ${Math.round(f.d)} ms at ${Math.round(f.s)}: ${attribute(f)}`);
    //: Per item, the median over the runs (a script's longest LoAF entry in each run, 0 when absent):
    //: variance is about 40 ms at 4x, so one run's number is not a verdict on one item.
    const per = new Map();
    runs.forEach((r, i) => { for (const f of r.loaf) for (const x of f.scripts) {
      const k = `${x.src.replace(/^https?:\/\/[^/]+\//, '')}:${/^https?:/.test(x.inv || '') ? 'eval' : (x.fn || x.inv || x.type)}`;
      const row = per.get(k) || Array(runs.length).fill(0); row[i] = Math.max(row[i], x.d); per.set(k, row);
    } });
    const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
    console.log(`median of the per-run longest long task: ${Math.round(med(runs.map(worst)))} ms; scripts with a median over 30 ms:`);
    for (const [k, row] of [...per].map(([k, r]) => [k, r]).sort((a, b) => med(b[1]) - med(a[1]))) if (med(row) > 30) console.log(`  ${med(row) > BAR ? 'OVER' : 'under'} ${Math.round(med(row))} ms median (${row.map(Math.round).join(', ')}) ${k}`);
    const ev = pick.event.filter((e) => e.proc > 100);
    for (const e of ev) console.log(`${e.d > 100 ? 'FAIL' : 'PASS'} event ${e.n} ${Math.round(e.d)} ms (handler ${Math.round(e.proc)}) on ${e.t}`);
    if (ev.length) failed += ev.length;
  }
  await browser.close();
  console.log(failed ? `\nFAIL: ${failed} item(s) over the bar` : '\nPASS: every boot task is under the bar');
  process.exit(failed ? 1 : 0);
})();
