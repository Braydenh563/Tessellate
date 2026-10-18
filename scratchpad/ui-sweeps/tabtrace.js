// Where a tab entry's time goes, by Chromium trace event (not by JS function):
// style (UpdateLayoutTree), layout, paint, script, GC, in the 2 s after the
// tab press, and the longest tasks with the events inside each. The profile in
// tabenter.js leaves out the rendering pipeline; this is the half it cannot see.
// Env: BASE, RATE (4), TABS (comma list; each is visited once to warm, then
// traced on a second visit), OUT.
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const TABS = (process.env.TABS || 'timeline,graph,library,dashboard,chat,notes').split(',');
const NAMES = ['UpdateLayoutTree', 'Layout', 'PrePaint', 'Paint', 'Layerize', 'Commit', 'FunctionCall', 'EvaluateScript', 'FireAnimationFrame', 'TimerFire', 'MinorGC', 'MajorGC', 'HitTest', 'ParseHTML', 'XHRLoad', 'v8.callFunction', 'EventDispatch', 'RunMicrotasks'];
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  // KILL=substring (or ALL_HAS=1): delete the stylesheet rules whose selector contains it,
  // to cost a selector shape by experiment rather than by theory.
  if (process.env.KILL_RANGE) {
    // KILL_RANGE=a-b: delete the a..b-th rules (document order) whose selector holds a
    // :has() that is not the plain :has(:focus-visible) pattern.
    const [a, b] = process.env.KILL_RANGE.split('-').map(Number);
    const n = await page.evaluate(([a, b]) => {
      const list = [];
      const walk = (cont) => { for (let i = 0; i < cont.cssRules.length; i += 1) { const r = cont.cssRules[i]; if (r.cssRules && !r.selectorText) walk(r); else if (r.selectorText && r.selectorText.replace(/:has\(:focus-visible\)/g, '').includes(':has(')) list.push([cont, r]); } };
      for (const sh of document.styleSheets) { try { walk(sh); } catch (e) {} }
      const kill = list.slice(a, b);
      for (const [cont, r] of kill) { const idx = [...cont.cssRules].indexOf(r); if (idx >= 0) cont.deleteRule(idx); }
      return [list.length, kill.length];
    }, [a, b]);
    console.log('killed range', n);
  }
  if (process.env.KILL) {
    const n = await page.evaluate((kill) => {
      let removed = 0;
      const walk = (rules) => { for (let i = rules.length - 1; i >= 0; i -= 1) { const r = rules[i]; if (r.cssRules && !r.selectorText) walk(r.cssRules); else if (r.selectorText && kill.some((k) => r.selectorText.includes(k))) { r.parentRule ? r.parentRule.deleteRule(i) : r.parentStyleSheet.deleteRule(i); removed += 1; } } };
      for (const sh of document.styleSheets) { try { walk(sh.cssRules); } catch (e) {} }
      return removed;
    }, process.env.KILL.split('|'));
    console.log('killed rules:', n);
  }
  const goto = async (tab) => {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    await page.getByRole('button', { name: "Don't check" }).click({ timeout: 300 }).catch(() => {});
    await page.waitForTimeout(1500);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
    await page.click(`#tab-bar button[data-tab="${tab}"]`, { timeout: 4000 });
  };
  for (const tab of TABS) {
    await goto(tab); await page.waitForTimeout(1500);
    await goto('reminders'); await page.waitForTimeout(500);
    const events = [];
    cdp.removeAllListeners('Tracing.dataCollected');
    cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
    const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
    await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.invalidationTracking,disabled-by-default-devtools.timeline.stack,v8', transferMode: 'ReportEvents' });
    await goto(tab);
    await page.waitForTimeout(2000);
    await cdp.send('Tracing.end');
    await done;
    // The renderer main thread is the one with the most RunTask time.
    const tasks = events.filter((e) => e.name === 'RunTask' && e.ph === 'X');
    const byThread = new Map();
    for (const t of tasks) byThread.set(`${t.pid}:${t.tid}`, (byThread.get(`${t.pid}:${t.tid}`) || 0) + t.dur);
    const main = [...byThread.entries()].sort((a, b) => b[1] - a[1])[0][0];
    const mine = events.filter((e) => `${e.pid}:${e.tid}` === main && e.ph === 'X');
    const mt = mine.filter((e) => e.name === 'RunTask');
    const t0 = Math.min(...mt.map((e) => e.ts));
    const sum = {};
    // self time by name: duration minus the duration of direct events inside it.
    const sorted = mine.slice().sort((a, b) => a.ts - b.ts || b.dur - a.dur);
    const stack = [];
    for (const e of sorted) {
      while (stack.length && stack[stack.length - 1].ts + stack[stack.length - 1].dur <= e.ts) stack.pop();
      if (stack.length) stack[stack.length - 1].child = (stack[stack.length - 1].child || 0) + e.dur;
      stack.push(e);
    }
    for (const e of mine) if (NAMES.includes(e.name)) sum[e.name] = (sum[e.name] || 0) + (e.dur - (e.child || 0));
    const totalTask = mt.reduce((a, e) => a + e.dur, 0);
    console.log(`${tab}: tasks ${(totalTask / 1000).toFixed(0)}ms |`, Object.entries(sum).filter(([, v]) => v > 3000).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${(v / 1000).toFixed(0)}`).join(', '));
    // What invalidated style, by reason, selector and the page function that did it.
    const inval = new Map();
    for (const e of events) {
      if (e.name !== 'StyleRecalcInvalidationTracking' && e.name !== 'StyleInvalidatorInvalidationTracking') continue;
      const d = (e.args && e.args.data) || {};
      const st = (d.stackTrace || []).find((f) => /\/js\//.test(f.url || ''));
      const where = st ? `${st.functionName || '(anon)'} ${st.url.split('/').pop().split('?')[0]}:${st.lineNumber}` : '-';
      const key = `${e.name === 'StyleRecalcInvalidationTracking' ? 'recalc' : 'invalidator'} ${d.reason || ''} ${d.extraData || ''} <- ${where}`;
      inval.set(key, (inval.get(key) || 0) + 1);
    }
    if (process.env.RAW) {
      const raw = events.filter((e) => e.name === 'StyleRecalcInvalidationTracking' && /has/.test(JSON.stringify(e.args.data.reason))).slice(0, 3);
      for (const r of raw) console.log('   RAW', JSON.stringify(r.args.data).slice(0, 700));
      const cnt = new Map();
      for (const r of events.filter((e) => e.name === 'StyleRecalcInvalidationTracking' && /has/.test(String(e.args.data.reason)))) { const k = `${r.args.data.nodeName}`; cnt.set(k, (cnt.get(k) || 0) + 1); }
      console.log('   :has() nodes', JSON.stringify([...cnt.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)));
    }
    console.log('   invalidations:', [...inval.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => `${v}x ${k}`).join(' | '));
    // ULT_MS=n lowers the 15 ms floor; ULT_TS=1 prefixes each with its start (ms from the first task).
    const ult = mine.filter((e) => e.name === 'UpdateLayoutTree' && e.dur > Number(process.env.ULT_MS || 15) * 1000).map((e) => `${process.env.ULT_TS ? `@${((e.ts - t0) / 1000).toFixed(0)} ` : ''}${(e.dur / 1000).toFixed(0)}ms/${(e.args && e.args.elementCount) || '?'}el`);
    console.log('   long style recalcs:', ult.join(' '));
    const long = mt.filter((e) => e.dur > 50000).sort((a, b) => b.dur - a.dur).slice(0, 4);
    for (const t of long) {
      const inside = mine.filter((e) => e.ts >= t.ts && e.ts + e.dur <= t.ts + t.dur && e !== t && e.dur > 8000 && e.name !== 'RunTask');
      const agg = {};
      for (const e of inside) agg[e.name] = (agg[e.name] || 0) + (e.dur - (e.child || 0));
      console.log(`   task @${((t.ts - t0) / 1000).toFixed(0)}ms ${(t.dur / 1000).toFixed(0)}ms:`, Object.entries(agg).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k, v]) => `${k} ${(v / 1000).toFixed(0)}`).join(', '));
    }
  }
  await browser.close();
})();
