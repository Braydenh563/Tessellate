// The mind map's perf budgets in CPU time (L-ui-modernisation-61 and -97), shared
// by the CI spec (specs/map-budgets.spec.js) and the sweep (scratchpad/ui-sweeps/mapcpu.js).
//
// **Why CPU time.** mapperf.js reads rAF frame deltas, which are wall time: on a
// shared runner at load 6 to 18 on 4 cores a 17ms frame reads 50 to 133ms because
// the renderer thread is descheduled, not because the code got slower (a CDP trace
// of the same gestures showed 37 to 73% of a long task waiting). A CDP trace's
// `RunTask` carries `tdur`, the thread's CPU time for that task, which waiting does
// not add to.
//
// **Rate 4.** `Emulation.setCPUThrottlingRate` makes the renderer do 4x the work,
// so each task is four times longer in `tdur` and the signal stands four times
// higher above the scheduler's noise (measured: open at 200 topics 252 to 384ms at
// rate 1, 1374 to 1394ms at rate 4). Every figure returned is divided by the rate
// again, so it is "CPU ms on this machine" and is held to the budgets as written
// (50ms for a task, 1s for the open); nothing is widened.
//
// No imports, like budget-measure.js: the spec and the sweep load different
// copies of Playwright. Every function takes a Playwright `page` whose whiteboard
// view is already showing (`initWhiteboard` has run).

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};
const r1 = (x) => Math.round(x * 10) / 10;

// A balanced outline of exactly `n` topics, the shape mapperf.js builds.
function outline(n) {
  const lines = [`# Perf ${n}`, "- Trunk"];
  const depth = [0];
  let made = 1;
  let parent = 0;
  let kids = 0;
  while (made < n) {
    if (kids === 5) { parent += 1; kids = 0; continue; }
    const d = depth[parent] + 1;
    depth.push(d);
    lines.push(`${"  ".repeat(d)}- Topic ${made}`);
    made += 1;
    kids += 1;
  }
  return lines.join("\n");
}

// Run `gesture` under a CDP trace at CPU throttle `rate`; return the main thread's
// task CPU, in ms at rate 1: the sum, the worst task, and the task count.
async function traced(cdp, rate, gesture) {
  const events = [];
  const onData = (d) => events.push(...d.value);
  cdp.on("Tracing.dataCollected", onData);
  const done = new Promise((r) => cdp.once("Tracing.tracingComplete", r));
  await cdp.send("Emulation.setCPUThrottlingRate", { rate });
  await cdp.send("Tracing.start", { categories: "devtools.timeline,disabled-by-default-devtools.timeline", transferMode: "ReportEvents" });
  let value;
  try {
    value = await gesture();
  } finally {
    await cdp.send("Tracing.end");
    await done;
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
    cdp.off("Tracing.dataCollected", onData);
  }
  const main = events.find((e) => e.name === "thread_name" && e.args && e.args.name === "CrRendererMain");
  const tasks = main
    ? events.filter((e) => e.name === "RunTask" && e.ph === "X" && e.pid === main.pid && e.tid === main.tid && e.tdur !== undefined)
    : [];
  const cpu = tasks.map((e) => e.tdur / 1000 / rate);
  return { value, sum: r1(cpu.reduce((a, b) => a + b, 0)), worst: r1(Math.max(0, ...cpu)), tasks: cpu.length };
}

async function importMap(page, n) {
  return page.evaluate(
    ({ content, name }) => apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content, name }) }),
    { content: outline(n), name: `Perf ${n}` }
  );
}

async function canvasCentre(page) {
  return page.evaluate(() => {
    const b = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
  });
}

// Open to painted: the call, every node in the DOM, two frames (as mapperf.js).
async function openCpu(page, cdp, rate, board, n) {
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(300);
  await page.evaluate(() => switchTab("library"));
  await page.waitForFunction(() => typeof window.openWhiteboardBoard === "function", null, { timeout: 30_000 });
  return traced(cdp, rate, () =>
    page.evaluate(async ([id, want]) => {
      await openWhiteboardBoard(id);
      const deadline = performance.now() + 60000;
      while (performance.now() < deadline && document.querySelectorAll("#wb-html-layer .wb-map-node").length < want) {
        await new Promise((r) => setTimeout(r, 8));
      }
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return document.querySelectorAll("#wb-html-layer .wb-map-node").length;
    }, [board.id, n])
  );
}

async function panCpu(page, cdp, rate) {
  const c = await canvasCentre(page);
  await page.click('#wb-tool-group button[data-tool="pan"]');
  await page.waitForTimeout(300);
  const r = await traced(cdp, rate, async () => {
    await page.mouse.move(c.x - 250, c.y);
    await page.mouse.down();
    for (let i = 1; i <= 30; i++) {
      await page.mouse.move(c.x - 250 + i * 12, c.y + Math.sin(i / 4) * 40);
      await page.waitForTimeout(8);
    }
    await page.mouse.up();
  });
  await page.click('#wb-tool-group button[data-tool="select"]');
  await page.waitForTimeout(300);
  return r;
}

async function zoomCpu(page, cdp, rate) {
  const c = await canvasCentre(page);
  const before = await page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return { k: t.k, x: t.x, y: t.y }; });
  await page.mouse.move(c.x, c.y);
  await page.keyboard.down("Control");
  const r = await traced(cdp, rate, async () => {
    for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 12); await page.waitForTimeout(16); }
    for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, -12); await page.waitForTimeout(16); }
  });
  await page.keyboard.up("Control");
  const after = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
  await page.evaluate(([k, x, y]) => {
    d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity.translate(x, y).scale(k));
  }, [before.k, before.x, before.y]);
  await page.waitForTimeout(200);
  r.zoomed = Math.abs(after - before.k) > 0;
  return r;
}

// One branch drag on the biggest branch on screen, from the view the open leaves.
async function branchCpu(page, cdp, rate) {
  await page.evaluate(() => {
    const root = wbMapIndex().roots[0];
    if (root) wbCenterOn(wbItemBBox("object", root), { animate: false, minScale: 1 });
  });
  await page.waitForTimeout(200);
  const pt = await page.evaluate(() => {
    const c = document.getElementById("whiteboard-container").getBoundingClientRect();
    const idx = wbMapIndex();
    let best = null;
    for (const el of document.querySelectorAll("#wb-html-layer .wb-map-node")) {
      const b = el.getBoundingClientRect();
      if (b.width === 0) continue;
      const cx = b.left + b.width / 2;
      const cy = b.top + b.height / 2;
      if (!(cx > c.left + 60 && cx < c.right - 60 && cy > c.top + 60 && cy < c.bottom - 60)) continue;
      const id = Number(el.dataset.id);
      const size = wbMapSubtree(idx, id).length;
      if (!best || size > best.size) best = { x: cx, y: cy, size, id };
    }
    return best;
  });
  if (!pt) return { sum: 0, worst: 0, tasks: 0, moved: 0, size: 0 };
  const at = () => page.evaluate((i) => { const o = (wbState.objects || []).find((x) => x.id === i); return o ? { x: o.x, y: o.y } : null; }, pt.id);
  const from = await at();
  const r = await traced(cdp, rate, async () => {
    await page.mouse.move(pt.x, pt.y);
    await page.mouse.down();
    for (let i = 1; i <= 25; i++) {
      await page.mouse.move(pt.x + i * 6, pt.y + i * 3);
      await page.waitForTimeout(8);
    }
    await page.mouse.up();
  });
  await page.waitForTimeout(400);
  const to = await at();
  r.moved = from && to ? Math.round(Math.hypot(to.x - from.x, to.y - from.y)) : 0;
  r.size = pt.size;
  return r;
}

async function addLinks(page, count) {
  return page.evaluate(async (want) => {
    const topics = (wbState.objects || []).filter((o) => o.kind === "topic");
    if (topics.length < 4) return 0;
    for (let i = 0; i < want; i++) {
      const a = topics[i % topics.length];
      const b = topics[(i * 7 + 3) % topics.length];
      if (a.id === b.id) continue;
      const row = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({
          data: JSON.stringify({ type: "link-curved", sourceId: a.id, targetId: b.id, sourceKind: "object", targetKind: "object", color: "#888888" }),
          x: 0, y: 0, z: 1, board_id: window.currentBoardId,
        }),
      });
      wbState.sketches.push(row);
    }
    renderWhiteboardNow();
    return (wbState.sketches || []).length;
  }, count);
}

// One full pass at one size. `links` sketches go on after the plain branch drag.
async function mapCpu(page, cdp, n, { rate = 4, links = 300 } = {}) {
  const board = await importMap(page, n);
  const open = await openCpu(page, cdp, rate, board, n);
  const pan = await panCpu(page, cdp, rate);
  const zoom = await zoomCpu(page, cdp, rate);
  const plain = await branchCpu(page, cdp, rate);
  const madeLinks = await addLinks(page, links);
  const linked = await branchCpu(page, cdp, rate);
  return {
    n, drawn: open.value, openCpu: open.sum, panWorst: pan.worst, zoomWorst: zoom.worst, zoomed: zoom.zoomed,
    branchPlain: plain.worst, branchLinked: linked.worst, branchSize: plain.size, moved: Math.min(plain.moved, linked.moved),
    links: madeLinks,
  };
}

// `rounds` passes at one size, each on a fresh import, the median of every figure.
async function mapCpuMedians(page, cdp, n, { rounds = 3, ...opts } = {}) {
  const rows = [];
  for (let i = 0; i < rounds; i++) rows.push(await mapCpu(page, cdp, n, opts));
  const med = (k) => r1(median(rows.map((r) => r[k])));
  return {
    n, rounds, rows,
    drawn: Math.min(...rows.map((r) => r.drawn)), zoomed: rows.every((r) => r.zoomed),
    moved: Math.min(...rows.map((r) => r.moved)), links: Math.min(...rows.map((r) => r.links)), branchSize: rows[0].branchSize,
    openCpu: med("openCpu"), panWorst: med("panWorst"), zoomWorst: med("zoomWorst"),
    branchPlain: med("branchPlain"), branchLinked: med("branchLinked"),
  };
}

// The budgets as written in the ledger rows: 50ms a task, 1s the open, links within
// twice the plain drag (or 50ms).
const BUDGET = { taskMs: 50, openMs: 1000 };
function failures(row) {
  const out = [];
  if (row.drawn < row.n) out.push(`${row.n}: ${row.drawn} of ${row.n} nodes drawn`);
  if (!row.zoomed) out.push(`${row.n}: the wheel did not zoom the board`);
  if (row.moved <= 50) out.push(`${row.n}: a branch drag moved ${row.moved} units`);
  if (row.openCpu > BUDGET.openMs) out.push(`${row.n}: open to painted ${row.openCpu}ms CPU over ${BUDGET.openMs}`);
  if (row.panWorst >= BUDGET.taskMs) out.push(`${row.n}: worst pan task ${row.panWorst}ms CPU`);
  if (row.zoomWorst >= BUDGET.taskMs) out.push(`${row.n}: worst zoom task ${row.zoomWorst}ms CPU`);
  if (row.branchLinked > Math.max(BUDGET.taskMs, row.branchPlain * 2)) out.push(`${row.n}: links took the branch drag from ${row.branchPlain} to ${row.branchLinked}ms CPU`);
  return out;
}

module.exports = { median, outline, traced, mapCpu, mapCpuMedians, failures, BUDGET };
