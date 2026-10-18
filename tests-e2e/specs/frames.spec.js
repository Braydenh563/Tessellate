// Frame time and idle redraws for the graph, boards, mind maps and the other
// busy screens. Report first: it records numbers and fails only when
// TESSELLATE_E2E_FRAMES_STRICT=1. It runs alone, from the Performance workflow.
const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");
const { openApp, openTab } = require("../helpers");

const ON = process.env.TESSELLATE_E2E_FRAMES === "1";
const STRICT = process.env.TESSELLATE_E2E_FRAMES_STRICT === "1";
const IDLE_MS = 3000;
const CAPS = { idleRafPerSec: 10, idleLongTasks: 1, p95FrameMs: 50, slowFrames: 10 };
const rows = [];
let ids = {};

test.skip(!ON, "set TESSELLATE_E2E_FRAMES=1 (the Performance workflow does)");
test.describe.configure({ mode: "serial" });
test.beforeEach(() => test.setTimeout(180_000));

test.beforeAll(async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext();
  const page = await context.newPage();
  await openApp(page);
  ids = await page.evaluate(async () => {
    const post = async (p, body) => apiJson(p, { method: "POST", body: JSON.stringify(body) });
    const board = await post("/whiteboard/boards", { name: "Frames board", type: "board" });
    for (let start = 0; start < 500; start += 20) {
      await Promise.all(Array.from({ length: 20 }, (_, k) => {
        const i = start + k;
        return post("/whiteboard/objects", {
          kind: "text", board_id: board.id, x: (i % 25) * 220, y: Math.floor(i / 25) * 140,
          width: 200, height: 100, data: { content: `Card ${i} with a few words of text on it` },
        });
      }));
    }
    return { board: board.id };
  });
  await context.close();
});

test.afterAll(() => {
  if (!rows.length) return;
  fs.writeFileSync(path.join(__dirname, "..", "frames-report.json"), JSON.stringify(rows, null, 2));
  const cell = (v) => (v === undefined || v === null ? "" : v);
  const lines = [
    "## Frame time and idle redraws", "",
    "| Scenario | rAF/s | rAF ms/s | Long tasks | p50 ms | p95 ms | Max ms | Frames over 50 ms |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
  ];
  for (const r of rows) {
    lines.push(r.skipped
      ? `| ${r.scenario} | skipped: ${r.skipped} | | | | | | |`
      : `| ${r.scenario} | ${cell(r.rafPerSec)} | ${cell(r.rafMsPerSec)} | ${cell(r.longTasks)} | ${cell(r.p50)} | ${cell(r.p95)} | ${cell(r.max)} | ${cell(r.slow)} |`);
  }
  console.log(lines.join("\n"));
  if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, lines.join("\n") + "\n");
});

async function instrument(page) {
  await page.evaluate(() => {
    if (window.__fr) return;
    const fr = { raf: 0, rafMs: 0, long: 0, longMs: 0, by: {} };
    const native = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => native((t) => {
      const began = performance.now();
      try { cb(t); } finally {
        fr.raf++; fr.rafMs += performance.now() - began;
        // Who asked, so an idle screen that redraws names the loop (an anonymous one by its first 50 characters).
        const who = cb.name || String(cb).replace(/\s+/g, " ").slice(0, 50);
        fr.by[who] = (fr.by[who] || 0) + 1;
      }
    });
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) { fr.long++; fr.longMs += e.duration; }
      }).observe({ type: "longtask" });
    } catch (e) { fr.noLongTasks = true; }
    window.__fr = fr;
  });
}
const reset = (page) => page.evaluate(() => Object.assign(window.__fr, { raf: 0, rafMs: 0, long: 0, longMs: 0, by: {} }));
const read = (page) => page.evaluate(() => ({ ...window.__fr }));
const round = (n) => Math.round(n * 10) / 10;

async function idle(page, name) {
  await instrument(page);
  await page.waitForTimeout(1500);
  await reset(page);
  await page.waitForTimeout(IDLE_MS);
  const f = await read(page);
  const secs = IDLE_MS / 1000;
  const top = Object.entries(f.by || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([who, n]) => `${who} x${n}`).join("; ");
  const row = { scenario: `${name}: idle${top && f.raf / secs > CAPS.idleRafPerSec ? ` (${top})` : ""}`, rafPerSec: round(f.raf / secs), rafMsPerSec: round(f.rafMs / secs), longTasks: f.long };
  rows.push(row);
  if (STRICT) {
    expect.soft(row.rafPerSec, `${name} idle rAF/s`).toBeLessThanOrEqual(CAPS.idleRafPerSec);
    expect.soft(row.longTasks, `${name} idle long tasks`).toBeLessThanOrEqual(CAPS.idleLongTasks);
  }
}

async function frames(page, name, gesture) {
  await instrument(page);
  await page.evaluate(() => {
    const s = { dt: [], run: true, last: performance.now() };
    const tick = (now) => { s.dt.push(now - s.last); s.last = now; if (s.run) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    window.__sample = s;
  });
  await reset(page);
  const began = Date.now();
  await gesture();
  const secs = Math.max(0.001, (Date.now() - began) / 1000);
  const out = await page.evaluate(() => {
    const s = window.__sample;
    s.run = false;
    const dt = s.dt.slice(1).sort((a, b) => a - b);
    const at = (p) => (dt.length ? dt[Math.min(dt.length - 1, Math.floor(dt.length * p))] : 0);
    return { p50: at(0.5), p95: at(0.95), max: dt.length ? dt[dt.length - 1] : 0, slow: dt.filter((x) => x > 50).length };
  });
  const f = await read(page);
  const row = {
    scenario: name, rafMsPerSec: round(f.rafMs / secs), longTasks: f.long,
    p50: round(out.p50), p95: round(out.p95), max: round(out.max), slow: out.slow,
  };
  rows.push(row);
  if (STRICT) {
    expect.soft(row.p95, `${name} p95 frame ms`).toBeLessThanOrEqual(CAPS.p95FrameMs);
    expect.soft(row.slow, `${name} frames over 50 ms`).toBeLessThanOrEqual(CAPS.slowFrames);
  }
}

async function scenario(name, run) {
  try { await run(); } catch (e) { rows.push({ scenario: name, skipped: String(e.message).split("\n")[0] }); }
}

async function drag(page, box, from, to, steps = 40) {
  await page.mouse.move(box.x + from[0], box.y + from[1]);
  await page.mouse.down();
  await page.mouse.move(box.x + to[0], box.y + to[1], { steps });
  await page.mouse.up();
}

async function wheel(page, box, dy, times, ctrl = false) {
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  if (ctrl) await page.keyboard.down("Control");
  for (let i = 0; i < times; i++) { await page.mouse.wheel(0, dy); await page.waitForTimeout(16); }
  if (ctrl) await page.keyboard.up("Control");
}

async function surfaceBox(page, selector) {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`${selector} has no box`);
  return box;
}

test("idle: busy screens redraw little when nothing changes", async ({ page }) => {
  await openApp(page);
  for (const tab of ["dashboard", "notes", "timeline", "library"]) {
    await scenario(`${tab}`, async () => { await openTab(page, tab); await idle(page, tab); });
  }
});

test("graph: drag and zoom", async ({ page }) => {
  await openApp(page);
  await scenario("graph", async () => {
    await openTab(page, "graph");
    await page.waitForFunction(() => typeof graphNodesRef !== "undefined" && graphNodesRef && graphNodesRef.length > 50, null, { timeout: 60_000 });
    const box = await surfaceBox(page, "#tab-graph");
    await idle(page, "graph");
    await frames(page, "graph: drag", () => drag(page, box, [box.width * 0.3, box.height * 0.5], [box.width * 0.7, box.height * 0.4]));
    await frames(page, "graph: zoom in", () => wheel(page, box, -300, 15));
    await frames(page, "graph: zoom out", () => wheel(page, box, 300, 15));
  });
});

test("board: 500 objects, drag, zoom and move one object", async ({ page }) => {
  await openApp(page, `/#/library/board/${ids.board}`);
  await scenario("board", async () => {
    await page.waitForFunction(() => document.querySelectorAll("#wb-canvas-view .wb-object").length >= 500, null, { timeout: 60_000 });
    const box = await surfaceBox(page, "#wb-canvas-view");
    await idle(page, "board (500 objects)");
    await frames(page, "board: drag across", () => drag(page, box, [8, 8], [box.width * 0.6, box.height * 0.6]));
    await frames(page, "board: wheel", () => wheel(page, box, 240, 15));
    await frames(page, "board: ctrl+wheel zoom", () => wheel(page, box, -240, 15, true));
    const obj = await page.locator("#wb-canvas-view .wb-object").first().boundingBox();
    if (obj) {
      const cx = obj.x + obj.width / 2, cy = obj.y + obj.height / 2;
      await frames(page, "board: move one object", async () => {
        await page.mouse.move(cx, cy);
        await page.mouse.down();
        await page.mouse.move(cx + 220, cy + 120, { steps: 40 });
        await page.mouse.up();
      });
    }
  });
});

test("mind map: an existing map, drag and zoom", async ({ page }) => {
  await openApp(page);
  await scenario("mind map", async () => {
    const boards = await page.evaluate(() => apiJson("/whiteboard/boards"));
    const map = boards.find((b) => /map/i.test(b.type || b.kind || ""));
    if (!map) throw new Error("no mind map in the seeded notebook");
    await openApp(page, `/#/library/board/${map.id}`);
    await page.waitForTimeout(1500);
    const box = await surfaceBox(page, "#wb-canvas-view");
    await idle(page, "mind map");
    await frames(page, "mind map: drag across", () => drag(page, box, [8, 8], [box.width * 0.6, box.height * 0.6]));
    await frames(page, "mind map: ctrl+wheel zoom", () => wheel(page, box, -240, 15, true));
  });
});

test("scroll: notes list and timeline", async ({ page }) => {
  await openApp(page);
  for (const tab of ["notes", "timeline"]) {
    await scenario(`${tab} scroll`, async () => {
      await openTab(page, tab);
      await page.waitForTimeout(800);
      const box = await surfaceBox(page, `#tab-${tab}`);
      await frames(page, `${tab}: scroll down`, () => wheel(page, box, 400, 30));
      await frames(page, `${tab}: scroll up`, () => wheel(page, box, -400, 30));
    });
  }
});
