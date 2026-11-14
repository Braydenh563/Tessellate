// The live-app measures behind tests/test_companion_live_1114.py (ledger L84, L131, L143, L144, L147). One boot, then each
// measure in turn; prints one JSON object. Env: BASE (the server), SWEEPS (scratchpad/ui-sweeps), RATE (CPU slow-down, 4).
const { boot, setBuddy } = require(process.env.SWEEPS + '/lib.js');
const RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Counts what a frame callback reads: the page's layout reads while one of the companion's own callbacks runs, and how long each takes.
const SPY = () => {
  const spy = (window.__spy = { frames: 0, ms: [], reads: 0, follow: [], followReads: 0, in: '', stacks: [] });
  const reads = ['getBoundingClientRect', 'getClientRects'];
  for (const name of reads) {
    const orig = Element.prototype[name];
    Element.prototype[name] = function (...a) { if (spy.in) { spy.reads += 1; if (spy.in && spy.stacks.length < 12) spy.stacks.push(new Error().stack.split('\n').slice(2, 5).map((l) => l.trim().replace(/\(.*\/(.*)\)/, '$1')).join(' < ')); if (spy.in === 'follow') spy.followReads += 1; } return orig.apply(this, a); };
  }
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => raf(function wrapped(now) {
    const kind = cb.name === 'frame' ? 'flight' : cb.name === 'nameMarkBuddyFollowTurn' ? 'follow' : '';
    if (!kind) return cb(now);
    spy.in = kind;
    const t = performance.now();
    const r0 = spy.reads;
    try { return cb(now); } finally { spy.in = ''; if (kind === 'flight') { spy.frames += 1; spy.ms.push(performance.now() - t); if (spy.reads > r0 || performance.now() - t > 8) (spy.slow ||= []).push([spy.frames, +(performance.now() - t).toFixed(1), spy.reads - r0]); } }
  });
  // The follow loop looks in a task after a drawn frame (`nameMarkBuddyFollowTask`); time those too.
  const st = window.setTimeout.bind(window);
  window.setTimeout = (cb, ms, ...rest) => typeof cb === 'function' && cb.name === 'nameMarkBuddyFollowTask'
    ? st(function wrapped() { spy.in = 'follow'; const t = performance.now(); try { return cb(); } finally { spy.in = ''; spy.follow.push([Math.round(performance.now()), performance.now() - t]); } }, ms, ...rest)
    : st(cb, ms, ...rest);
};

(async () => {
  const out = {};
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  // A fresh profile has the companion off; the pick is saved to the server a moment after the change, and mounts on the page at once.
  await setBuddy(page, 'atlas');
  await page.evaluate(() => revealTab('notes'));
  await page.waitForSelector('#nm-buddy .nm-buddy-face', { state: 'attached', timeout: 15000 });
  // A fresh profile is asked once whether to check for updates; the answer is no, and the dialog is out of the way.
  await page.waitForTimeout(2500);
  await page.evaluate(() => { if (document.getElementById('confirm-name-1')) [...document.querySelectorAll('button')].find((b) => /Don.t check/.test(b.innerText))?.click(); });
  await page.waitForTimeout(500);
  // After the app's own lag watch has wrapped `requestAnimationFrame`, so this wrapper sees the callbacks by name.
  await page.evaluate(SPY);
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const face = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  const metrics = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));

  // L144: the follow loop. Perched on a panel (`nmb.glue`), still: how often it looks and what each look reads; then woken.
  // The companion wanders off by its own mind now and then, so a window counts only when it stayed perched the whole of it.
  const glue = async () => {
    for (let attempt = 0; attempt < 8 && !(await page.evaluate(() => !!nmb.glue)); attempt += 1) {
      await page.evaluate(() => {
        const el = [...document.querySelectorAll('.tab-main')].find((e) => e.getBoundingClientRect().width > 200);
        const r = el.getBoundingClientRect();
        nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'sit', legs: '', x: r.left + 120, y: r.top + 200, anchor: el }, true);
      });
      await sleep(1500);
    }
    return page.evaluate(() => !!nmb.glue);
  };
  out.glued = await glue();
  let idle = { looks: 0, reads: 0 };
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await glue();
    await sleep(2500);
    await page.evaluate(() => { window.__spy.follow = []; window.__spy.followReads = 0; });
    await sleep(6000);
    idle = await page.evaluate(() => ({ looks: window.__spy.follow.length, reads: window.__spy.followReads, still: !!nmb.glue }));
    if (idle.still) break;
  }
  out.follow = { stillSeconds: 6, perched: idle.still, looks: idle.looks, readsPerLook: idle.looks ? +(idle.reads / idle.looks).toFixed(2) : 0 };
  await glue();
  // A resize wakes the loop for about a second and a half; the trace counts the layouts and restyles a script forced, by function.
  const events = [];
  cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
  const traced = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
  await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline.stack', transferMode: 'ReportEvents' });
  await page.evaluate(() => { window.__spy.follow = []; window.__spy.followReads = 0; document.dispatchEvent(new Event('scroll')); window.dispatchEvent(new Event('resize')); });
  await page.setViewportSize({ width: 1380, height: 880 });
  await sleep(1400);
  const awake = await page.evaluate(() => ({ glue: !!nmb.glue, until: nmbFollow.until - performance.now(), looks: window.__spy.follow.length, reads: window.__spy.followReads, running: !!nmbFollow.frame }));
  await cdp.send('Tracing.end');
  await traced;
  const forced = {};
  for (const e of events) {
    if (!['Layout', 'UpdateLayoutTree'].includes(e.name) || e.ph === 'E') continue;
    const st = e.args?.beginData?.stackTrace;
    if (!st || !st.length) continue;
    const key = st.slice(0, 3).map((f) => f.functionName || '(anon)').find((n) => /^nameMarkBuddy/.test(n)) || st[0].functionName || '(anon)';
    forced[`${e.name} ${key}`] = (forced[`${e.name} ${key}`] || 0) + 1;
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  out.followForced = forced;
  out.followStacks = await page.evaluate(() => window.__spy.stacks);
  out.followAwake = { looks: awake.looks, readsPerLook: awake.looks ? +(awake.reads / awake.looks).toFixed(2) : 0 };

  // Something to scroll: a tall block in the notes pane, every scroller scrolled 150px in.
  const scrolls = () => page.evaluate(() => {
    const rows = { window: Math.round(scrollY) };
    for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) rows[el.id || el.className || el.tagName] = Math.round(el.scrollTop);
    return rows;
  });
  await page.evaluate(() => {
    const pane = document.querySelector('#notes-list, #tab-notes, main') || document.body;
    const tall = document.createElement('div');
    tall.id = 'live-tall'; tall.style.height = '6000px';
    pane.appendChild(tall);
    for (const el of document.querySelectorAll('*')) {
      const o = getComputedStyle(el).overflowY;
      if ((o === 'auto' || o === 'scroll') && el.scrollHeight > el.clientHeight + 200) el.scrollTop = 150;
    }
    window.scrollTo(0, 150);
  });
  await sleep(600);
  // L84: a throw by mouse, by touch and by keyboard leaves every scroller where it was.
  const before = await scrolls();
  out.scrollBefore = before;
  const [fx, fy] = await face();
  await page.mouse.move(fx, fy); await page.mouse.down();
  for (let i = 1; i <= 30; i += 1) { await page.mouse.move(fx + i * 14, fy - Math.sin(i / 6) * 40); await sleep(16); }
  await page.mouse.move(fx + 460, fy - 20); await sleep(10); await page.mouse.move(fx + 560, fy - 30);
  await page.mouse.up();
  await sleep(2500);
  out.scrollMouse = await scrolls();
  out.faceMoved = [[fx, fy], await face()];
  const [tx, ty] = await face();
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: tx, y: ty }] });
  for (let i = 1; i <= 20; i += 1) { await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: tx - i * 14, y: ty - i * 9 }] }); await sleep(16); }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await sleep(2500);
  out.scrollTouch = await scrolls();
  await page.focus('#nm-buddy .nm-buddy-face');
  for (const key of ['ArrowDown', 'PageDown', 'Space', 'End', 'ArrowRight', 'Home']) { await page.keyboard.press(key); await sleep(120); }
  await sleep(1500);
  out.scrollKeys = await scrolls();
  await page.evaluate(() => document.activeElement?.blur());

  // L143: the throw's own frame callback, at RATE x CPU: what it costs and how many page reads it makes.
  await page.evaluate(() => { window.__spy.frames = 0; window.__spy.ms = []; window.__spy.reads = 0; });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  for (let run = 0; run < 3; run += 1) {
    const [x, y] = await face();
    await page.mouse.move(x, y); await page.mouse.down();
    for (let i = 1; i <= 25; i += 1) { await page.mouse.move(x + i * 12, y - Math.sin(i / 6) * 30); await sleep(16); }
    await page.mouse.move(x + 380, y - 20); await sleep(8); await page.mouse.move(x + 470, y - 28);
    await page.mouse.up();
    await sleep(2600);
    (out.moved ||= []).push([Math.round(x), Math.round(y), ...(await face()).map(Math.round)]);
  }
  const spy = await page.evaluate(() => window.__spy);
  const ms = [...spy.ms].sort((a, b) => a - b);
  out.slow = spy.slow;
  out.flight = { frames: spy.frames, medianMs: +(ms[Math.floor(ms.length / 2)] || 0).toFixed(2), p95Ms: +(ms[Math.floor(ms.length * 0.95)] || 0).toFixed(2), maxMs: +(ms[ms.length - 1] || 0).toFixed(2), reads: spy.reads, rate: RATE };
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });

  // L131/L147: a click on Atlas in the large view, at RATE x CPU: the call's own cost and the main thread after it.
  await page.evaluate(() => openNameMarkViewer('Atlas'));
  // The viewer is open when its figure is laid out, not after a fixed sleep a loaded machine can miss.
  await page.waitForFunction(() => { const f = document.querySelector('.nm-viewer .nm-viewer-figure'); return f && f.getBoundingClientRect().width > 0; }, null, { timeout: 30000 });
  await sleep(500);
  await page.evaluate(() => {
    window.__mood = [];
    const orig = window.setAtlasMood;
    window.setAtlasMood = function (...a) { const t = performance.now(); const r = orig.apply(this, a); window.__mood.push(performance.now() - t); return r; };
  });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  let landed = 0;
  for (let i = 0; i < 12; i += 1) {
    // Where the figure is now, and only if it is what a click there would reach (a dialog or the companion may be over it).
    let head = null;
    for (let tries = 0; tries < 10 && !head; tries += 1) {
      head = await page.evaluate(() => { const f = document.querySelector('.nm-viewer .nm-viewer-figure'); if (!f) return null; const r = f.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height * (0.25 + (Math.random() * 0.2)); const top = document.elementFromPoint(x, y); return f.contains(top) || top?.closest?.('.nm-viewer-figure') ? [x, y] : null; });
      if (!head) await sleep(300);
    }
    if (head) { landed += 1; await page.mouse.click(head[0], head[1]); }
    await sleep(1700);
  }
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const mood = (await page.evaluate(() => window.__mood)).sort((a, b) => a - b);
  out.click = { landed, calls: mood.length, medianMs: +(mood[Math.floor(mood.length / 2)] || 0).toFixed(2), maxMs: +(mood[mood.length - 1] || 0).toFixed(2), rate: RATE };
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
