// Pan and zoom cost on a big board and a big graph, as trace numbers.
//
// Why a trace and not frame times alone: at 1x the sandbox is vsync-bound at
// 16.7ms whatever a handler does (graphmove.js's header), so a frame-time A/B
// at 1x reads the same number before and after. INBOX 424 (a) measured the
// board pan at 4x CPU with a devtools.timeline trace instead: 43 long tasks,
// 3.5s, of which `Layerize` was 2.4s. This takes the same kind of number for
// the same gestures, so a before and an after are comparable:
//
//   board pan   40 middle-button moves across a board of ~250 objects
//   board zoom  12 ctrl-wheel steps in and back out on the same board
//   graph pan   40 moves dragging empty canvas on a 400-note graph
//   graph zoom  12 wheel steps in and back out
//
// Each at CPU 4x (THROTTLE=1 for 1x). Reported per gesture: rAF frame deltas
// (median, p95, max), long tasks (> 50ms) and their total, and the sum of the
// trace's own event durations for script, style, layout, paint, prepaint,
// layerize and commit.
//
// The board is built once through the app's own routes (`GW perf`, 100 note
// cards, 80 text boxes, 70 shapes) if it is not already there; the graph uses
// whatever notes the data dir holds (`scratchpad/graph-fixture.js 400 1200`).
//
//   BASE=http://127.0.0.1:8797 SCRATCH=<dir> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/gwperf.js [board|graph|all]
const { boot } = require('./lib.js');

const WHICH = process.argv[2] || 'all';
const RATE = Number(process.env.THROTTLE || 4);
const CATS = ['devtools.timeline', 'disabled-by-default-devtools.timeline', 'blink', 'cc', 'toplevel'];

const pct = (xs, p) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.min(s.length - 1, Math.floor(s.length * p))] : 0;
};
const r1 = (x) => Math.round(x * 10) / 10;

function summarise(buf) {
  const ev = JSON.parse(buf.toString()).traceEvents || [];
  // The renderer's main thread: the thread that runs the most `RunTask`s
  // carrying a `FunctionCall` is the page's, not the GPU's or the browser's.
  const main = new Map();
  for (const e of ev) if (e.name === 'FunctionCall' || e.name === 'EventDispatch') main.set(`${e.pid}:${e.tid}`, (main.get(`${e.pid}:${e.tid}`) || 0) + 1);
  const mainKey = [...main.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const sums = {};
  const want = {
    script: ['FunctionCall', 'EventDispatch', 'TimerFire', 'FireAnimationFrame'],
    style: ['UpdateLayoutTree', 'RecalculateStyles'],
    layout: ['Layout'],
    prepaint: ['PrePaint'],
    paint: ['Paint'],
    layerize: ['Layerize'],
    commit: ['Commit'],
  };
  const long = [];
  for (const e of ev) {
    if (e.ph !== 'X' || !e.dur) continue;
    const onMain = `${e.pid}:${e.tid}` === mainKey;
    if (e.name === 'RunTask' && onMain && e.dur > 50000) long.push(e.dur / 1000);
    for (const [k, names] of Object.entries(want)) {
      if (names.includes(e.name) && onMain) sums[k] = (sums[k] || 0) + e.dur / 1000;
    }
  }
  if (process.env.DETAIL) {
    // Totals by event name on the page's main thread (nested events counted
    // inside their parents too), for finding what a long task is made of
    // when the named buckets do not add up to it.
    const by = {};
    for (const e of ev) {
      if (e.ph !== 'X' || !e.dur || `${e.pid}:${e.tid}` !== mainKey || e.name === 'RunTask') continue;
      by[e.name] = (by[e.name] || 0) + e.dur / 1000;
    }
    console.log('  top: ' + Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 14).map(([k, v]) => `${k} ${Math.round(v)}`).join(', '));
  }
  return { sums, long };
}

async function startFrames(page) {
  await page.evaluate(() => {
    window.__frames = [];
    window.__rafOn = true;
    let last = performance.now();
    const tick = (t) => {
      if (!window.__rafOn) return;
      window.__frames.push(t - last);
      last = t;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
async function stopFrames(page) {
  return page.evaluate(() => { window.__rafOn = false; return window.__frames.slice(1); });
}

async function measure(label, browser, page, cdp, gesture) {
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  await browser.startTracing(page, { categories: CATS });
  await startFrames(page);
  await gesture();
  await page.waitForTimeout(300);
  const frames = await stopFrames(page);
  const buf = await browser.stopTracing();
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const { sums, long } = summarise(buf);
  const s = Object.entries(sums).map(([k, v]) => `${k} ${Math.round(v)}`).join(', ');
  console.log(`${label} @${RATE}x  frames ${frames.length}: median ${r1(pct(frames, 0.5))}, p95 ${r1(pct(frames, 0.95))}, max ${r1(Math.max(0, ...frames))}ms; long tasks ${long.length}, ${Math.round(long.reduce((a, b) => a + b, 0))}ms; ${s}`);
  return { frames, sums, long };
}

async function buildBoard(page) {
  return page.evaluate(async () => {
    const boards = await apiJson('/whiteboard/boards');
    const have = (boards || []).find((b) => b.title === 'GW perf');
    if (have) return have.id;
    const b = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: 'GW perf' }) });
    const entries = await api('/entries?limit=100').then((r) => r.json());
    const list = Array.isArray(entries) ? entries : entries.items || entries.entries || [];
    const jobs = [];
    list.slice(0, 100).forEach((e, i) => {
      jobs.push(() => apiJson('/whiteboard/nodes', { method: 'POST', body: JSON.stringify({ entry_id: e.id, board_id: b.id, x: (i % 10) * 320, y: Math.floor(i / 10) * 220 }) }));
    });
    for (let i = 0; i < 80; i++) {
      jobs.push(() => apiJson('/whiteboard/objects', { method: 'POST', body: JSON.stringify({ kind: 'text', board_id: b.id, x: 3300 + (i % 8) * 240, y: Math.floor(i / 8) * 160, width: 200, height: 100, data: { content: `Text box ${i} with a few words on it` } }) }));
    }
    for (let i = 0; i < 70; i++) {
      const x = (i % 10) * 300, y = 2300 + Math.floor(i / 10) * 200;
      const d = i % 2 ? `M${x} ${y} L${x + 220} ${y} L${x + 220} ${y + 140} L${x} ${y + 140} Z` : `M${x} ${y} L${x + 240} ${y + 120}`;
      jobs.push(() => apiJson('/whiteboard/sketches', { method: 'POST', body: JSON.stringify({ board_id: b.id, x: 0, y: 0, z: 5, data: JSON.stringify({ d, color: '#3b82f6', width: 3, shape: i % 2 ? 'square' : 'line' }) }) }));
    }
    for (let i = 0; i < jobs.length; i += 20) await Promise.all(jobs.slice(i, i + 20).map((j) => j()));
    return b.id;
  });
}

(async () => {
  const { browser, page } = await boot({});
  const cdp = await page.context().newCDPSession(page);

  if (WHICH === 'all' || WHICH === 'board') {
    await page.click('[data-tab="library"]');
    await page.waitForTimeout(700);
    await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
    await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
    await page.evaluate(async () => {
      const v = document.getElementById('library-view-whiteboard');
      for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle('hidden', s !== v);
      await initWhiteboard();
    });
    const id = await buildBoard(page);
    await page.evaluate(async (bid) => { await openWhiteboardBoard(bid); }, id);
    await page.waitForTimeout(2000);
    // Frame the whole board, so a pan moves every object rather than a corner.
    await page.evaluate(() => { wbZoomToFit({ animate: false }); });
    await page.waitForTimeout(800);
    const info = await page.evaluate(() => {
      const c = document.getElementById('whiteboard-container');
      const r = c.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2, cards: document.querySelectorAll('#whiteboard-container .node-card').length, objs: document.querySelectorAll('#whiteboard-container .wb-object').length, sketches: document.querySelectorAll('#whiteboard-container .sketch-group').length, k: d3.zoomTransform(c).k };
    });
    console.log(`board: ${info.cards} cards, ${info.objs} objects, ${info.sketches} sketches drawn; zoom ${r1(info.k)}`);
    await page.screenshot({ path: `${process.env.SHOTS || '.'}/board-${process.env.TAG || 'run'}.png` }).catch(() => {});
    await measure('board pan ', browser, page, cdp, async () => {
      await page.mouse.move(info.x, info.y);
      await page.mouse.down({ button: 'middle' });
      for (let i = 1; i <= 40; i++) await page.mouse.move(info.x + (i % 20) * 12 - 120, info.y + (i % 10) * 6);
      await page.mouse.up({ button: 'middle' });
    });
    await measure('board zoom', browser, page, cdp, async () => {
      await page.mouse.move(info.x, info.y);
      await page.keyboard.down('Control');
      for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, -120); await page.waitForTimeout(30); }
      for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 120); await page.waitForTimeout(30); }
      await page.keyboard.up('Control');
    });
  }

  if (WHICH === 'all' || WHICH === 'graph') {
    await page.evaluate(() => switchTab('graph'));
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
      const i = document.getElementById('graph-layout');
      if (i) { i.value = 'force'; i.dispatchEvent(new Event('change', { bubbles: true })); }
    });
    await page.waitForTimeout(7000);
    const g = await page.evaluate(() => {
      const c = document.getElementById('graph-canvas');
      const r = (c || document.getElementById('graph-container')).getBoundingClientRect();
      return { x: r.left + 40, y: r.top + r.height - 60, cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height };
    });
    console.log(`graph: canvas ${Math.round(g.w)}x${Math.round(g.h)}`);
    await measure('graph pan ', browser, page, cdp, async () => {
      await page.mouse.move(g.x, g.y);
      await page.mouse.down();
      for (let i = 1; i <= 40; i++) await page.mouse.move(g.x + i * 6, g.y - i * 3);
      await page.mouse.up();
    });
    await measure('graph zoom', browser, page, cdp, async () => {
      await page.mouse.move(g.cx, g.cy);
      for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, -120); await page.waitForTimeout(30); }
      for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 120); await page.waitForTimeout(30); }
    });
  }
  await browser.close();
})().catch((e) => { console.log('ERR ' + e.stack); process.exit(1); });
