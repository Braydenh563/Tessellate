// INBOX 426 x: "the companion showing makes everything noticeably slower",
// "heavy and glitchy". Measures what the page costs with the companion off,
// as you, and as Atlas: idle for 4s, then 4s of small wheel steps (12px
// every frame or so, as a trackpad sends). Per phase, from CDP
// Performance.getMetrics deltas: scripting ms per second and per frame,
// layouts and style recalcs per second; from a devtools.timeline trace,
// forced layouts (a Layout with a JS stack); from a CPU profile, the
// functions with the most self time.
// Env: KINDS (off,me,atlas), TAB (dashboard), OUT (json), MS (4000).
// IDLE=1 is decision 7's idle-minute measure (Brief 34): no frame counter,
// trace or profiler (each would cost frames of its own), MS of idle only,
// reported per minute and per 10s. A kind may carry a state after a colon:
// me:hidden (document.hidden, as a minimised window), me:locked (lockNow), me:reduced (the
// system asks for less motion), me:appreduce (the app's own Reduce motion), me:animoff (Appearance, Avatar animation off).
// Exits 1 when the companion adds more than 1ms of scripting per frame
// while scrolling, more than 0.2ms per frame idle, or more than 120ms a
// second of main thread idle, over the page with it off.
const fs = require('fs');
const os = require('os');
const { boot } = require('./lib.js');
const KINDS = (process.env.KINDS || 'off,me,atlas').split(',');
const TAB = process.env.TAB || 'dashboard';
const OUT = process.env.OUT || `${os.tmpdir()}/companion-perf.json`;
const MS = Number(process.env.MS || 4000);

async function metrics(cdp) {
  const { metrics: m } = await cdp.send('Performance.getMetrics');
  return Object.fromEntries(m.map((x) => [x.name, x.value]));
}

async function phase(page, cdp, browser, name, act) {
  await page.evaluate(() => {
    window.__frames = 0;
    window.__fstop = false;
    const tick = () => { window.__frames += 1; if (!window.__fstop) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  const tracePath = `${os.tmpdir()}/cperf-${process.pid}-${name}.json`;
  await browser.startTracing(page, { path: tracePath, categories: ['devtools.timeline', 'disabled-by-default-devtools.timeline'] });
  await cdp.send('Profiler.enable');
  await cdp.send('Profiler.setSamplingInterval', { interval: 200 });
  await cdp.send('Profiler.start');
  const a = await metrics(cdp);
  const t0 = Date.now();
  await act();
  const secs = (Date.now() - t0) / 1000;
  const b = await metrics(cdp);
  const { profile } = await cdp.send('Profiler.stop');
  await browser.stopTracing();
  const frames = await page.evaluate(() => { window.__fstop = true; return window.__frames; });
  // Forced layouts: a Layout event that carries a JS stack.
  let forced = 0; let layouts = 0; const forcedBy = {};
  try {
    const trace = JSON.parse(fs.readFileSync(tracePath, 'utf8'));
    for (const e of trace.traceEvents || []) {
      if (e.name !== 'Layout' || e.ph !== 'B' && e.ph !== 'X') continue;
      layouts += 1;
      const st = e.args?.beginData?.stackTrace;
      if (st && st.length) {
        forced += 1;
        const k = `${st[0].functionName}@${(st[0].url || '').split('/').pop().split('?')[0]}`;
        forcedBy[k] = (forcedBy[k] || 0) + 1;
      }
    }
    fs.unlinkSync(tracePath);
  } catch (e) { /* no trace */ }
  // Self time per function, from the samples.
  const self = {};
  const byId = new Map(profile.nodes.map((n) => [n.id, n]));
  const dt = profile.timeDeltas || [];
  const parent = new Map();
  for (const n of profile.nodes) for (const c of n.children || []) parent.set(c, n.id);
  (profile.samples || []).forEach((id, i) => {
    let n = byId.get(id);
    // A native call (querySelectorAll, getBoundingClientRect) is charged to
    // the script function that made it, so the list names the caller.
    while (n && !n.callFrame.url && parent.has(n.id) && !['(idle)', '(program)', '(garbage collector)', '(root)'].includes(n.callFrame.functionName)) {
      const up = byId.get(parent.get(n.id));
      if (!up || up.callFrame.functionName === '(root)') break;
      n = up;
    }
    const f = n.callFrame;
    if (!f.url && ['(idle)', '(program)', '(garbage collector)', '(root)'].includes(f.functionName)) return;
    const k = `${f.functionName || '(anon)'}@${(f.url || '').split('/').pop().split('?')[0]}:${f.lineNumber + 1}`;
    self[k] = (self[k] || 0) + (dt[i] || 0) / 1000;
  });
  const top = Object.entries(self).sort((x, y) => y[1] - x[1]).slice(0, 8).map(([k, v]) => `${k} ${v.toFixed(1)}ms`);
  const d = (k) => b[k] - a[k];
  return {
    phase: name, secs: +secs.toFixed(2), frames,
    scriptMsPerSec: +(d('ScriptDuration') * 1000 / secs).toFixed(2),
    scriptMsPerFrame: +(d('ScriptDuration') * 1000 / Math.max(1, frames)).toFixed(3),
    taskMsPerSec: +(d('TaskDuration') * 1000 / secs).toFixed(1),
    layoutsPerSec: +(d('LayoutCount') / secs).toFixed(1),
    stylesPerSec: +(d('RecalcStyleCount') / secs).toFixed(1),
    layoutMsPerSec: +(d('LayoutDuration') * 1000 / secs).toFixed(2),
    styleMsPerSec: +(d('RecalcStyleDuration') * 1000 / secs).toFixed(2),
    forcedLayouts: forced, traceLayouts: layouts, forcedBy, top,
  };
}

async function idleRun() {
  const rows = [];
  for (const spec of KINDS) {
    const [kind, state] = spec.split(':');
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, reducedMotion: state === 'reduced' ? 'reduce' : undefined });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    await page.evaluate(async ([k, st]) => {
      localStorage.removeItem('nm-buddy-spots');
      if (st === 'appreduce') { localStorage.setItem('motion', 'reduced'); document.documentElement.dataset.motion = 'reduced'; }
      if (st === 'animoff') { localStorage.setItem('avatar-motion', 'off'); document.documentElement.dataset.avatarMotion = 'off'; }
      prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy();
    }, [kind, state || '']);
    await page.evaluate((t) => revealTab(t), TAB);
    await page.waitForTimeout(6000);
    // Headless Chromium keeps a page in the background visible, so the
    // app is told it is hidden the way a minimised window tells it.
    if (state === 'hidden') {
      await page.evaluate(() => {
        Object.defineProperty(document, 'hidden', { get: () => true, configurable: true });
        Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
        document.dispatchEvent(new Event('visibilitychange'));
      });
      await page.waitForTimeout(1500);
    }
    if (state === 'locked') { await page.evaluate(() => lockNow()); await page.waitForTimeout(1500); }
    const hidden = await page.evaluate(() => document.hidden);
    const a = await metrics(cdp);
    const t0 = Date.now();
    await page.waitForTimeout(MS);
    const secs = (Date.now() - t0) / 1000;
    const b = await metrics(cdp);
    const d = (k) => b[k] - a[k];
    const per = (v, s) => +(v * s / secs).toFixed(2);
    const row = {
      kind: spec, hidden, secs: +secs.toFixed(1),
      scriptMsPerMin: per(d('ScriptDuration') * 1000, 60), taskMsPerMin: per(d('TaskDuration') * 1000, 60),
      scriptMsPer10s: per(d('ScriptDuration') * 1000, 10), taskMsPer10s: per(d('TaskDuration') * 1000, 10),
      layoutsPerMin: per(d('LayoutCount'), 60), stylesPerMin: per(d('RecalcStyleCount'), 60),
    };
    rows.push(row);
    console.log(JSON.stringify(row));
    await browser.close();
  }
  fs.writeFileSync(OUT, JSON.stringify(rows, null, 1));
}

(async () => {
  if (process.env.IDLE) return idleRun();
  const results = [];
  for (const kind of KINDS) {
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, kind);
    await page.evaluate(() => localStorage.removeItem('nm-buddy-spots'));
    await page.evaluate((t) => revealTab(t), TAB);
    await page.waitForTimeout(6000);
    const idle = await phase(page, cdp, browser, `${kind}-idle`, () => page.waitForTimeout(MS));
    await page.mouse.move(720, 500);
    const scroll = await phase(page, cdp, browser, `${kind}-scroll`, async () => {
      const end = Date.now() + MS;
      let dir = 1; let n = 0;
      while (Date.now() < end) {
        await page.mouse.wheel(0, 12 * dir);
        await page.waitForTimeout(16);
        n += 1;
        if (n % 60 === 0) dir = -dir;
      }
    });
    results.push({ kind, idle, scroll });
    console.log(JSON.stringify({ kind, idle, scroll }));
    await browser.close();
  }
  fs.writeFileSync(OUT, JSON.stringify(results, null, 1));
  const off = results.find((r) => r.kind === 'off');
  let bad = false;
  if (off) {
    for (const r of results.filter((x) => x.kind !== 'off')) {
      const dScroll = r.scroll.scriptMsPerFrame - off.scroll.scriptMsPerFrame;
      const dIdle = r.idle.scriptMsPerFrame - off.idle.scriptMsPerFrame;
      // The main thread as a whole while idle (style, layout, paint of its
      // drawing): Atlas was +218ms a second over the page with it off,
      // 2.7ms a frame, before its idle motion was paced.
      const dTask = r.idle.taskMsPerSec - off.idle.taskMsPerSec;
      console.log(`${r.kind}: +${dScroll.toFixed(3)}ms/frame scrolling, +${dIdle.toFixed(3)}ms/frame idle, +${dTask.toFixed(0)}ms/s main thread idle, forced layouts ${r.scroll.forcedLayouts} scrolling (${off.scroll.forcedLayouts} off)`);
      if (dScroll > 1 || dIdle > 0.2 || dTask > 120) bad = true;
    }
  }
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
})();
