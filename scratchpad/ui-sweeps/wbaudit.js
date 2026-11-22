// INBOX 445 (2): the whiteboard, audited by driving every tool through the
// real UI and then measuring the board at about eighty items.
//
// Part A drives each rail tool with its own key and a real `page.mouse`
// gesture, and reports whether the item count moved (a tool that makes
// nothing is broken, whatever it looks like). Part B fills the board to
// TARGET items through the routes and measures pan, wheel zoom and a drag:
// rAF frame deltas, long tasks, CDP layout and style counts, and how many
// times `renderWhiteboard` ran per gesture. Part C is two minutes of mixed
// use (SOAK seconds) with the JS heap read before and after.
//
//   BASE=http://127.0.0.1:8798 SCRATCH=/tmp/mm-wb-a08 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbaudit.js
const { boot } = require("./lib.js");

const TARGET = Number(process.env.TARGET || 80);
const SOAK = Number(process.env.SOAK || 120);
const PARTS = process.env.PARTS || "ABC";

async function newBoard(page, name, type) {
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", name);
  if (type === "map") await page.click('#wb-template-kind button[data-value="map"]');
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
}

const count = (page) =>
  page.evaluate(() => (wbState.sketches || []).length + (wbState.objects || []).length + (wbState.nodes || []).length);

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};
const p95 = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.min(s.length - 1, Math.floor(s.length * 0.95))] : 0;
};
const r1 = (x) => Math.round(x * 10) / 10;

async function canvasBox(page) {
  return page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
}

async function drag(page, x1, y1, x2, y2, steps = 8) {
  await page.mouse.move(x1, y1);
  await page.mouse.down();
  await page.mouse.move((x1 + x2) / 2, (y1 + y2) / 2, { steps });
  await page.mouse.move(x2, y2, { steps });
  await page.mouse.up();
  await page.waitForTimeout(450);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");

  await newBoard(page, "Audit board", "board");
  const box = await canvasBox(page);
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;

  if (PARTS.includes("A")) {
    // --- A. Every tool, by its key, with a real gesture -------------------
    const tools = [
      ["r", "rectangle", "drag"],
      ["o", "circle", "drag"],
      ["g", "triangle", "drag"],
      ["d", "diamond", "drag"],
      ["l", "line", "drag"],
      ["a", "arrow", "drag"],
      ["p", "pen", "drag"],
      ["m", "highlighter", "drag"],
      ["n", "sticky", "click"],
      ["t", "text", "click"],
    ];
    let col = 0;
    for (const [key, name, how] of tools) {
      await page.mouse.click(box.x + 20, box.y + box.h - 30); // focus the canvas without a tool
      await page.keyboard.press("Escape");
      await page.keyboard.press(key);
      const tool = await page.evaluate(() => window.currentTool);
      const before = await count(page);
      const x = box.x + 120 + (col % 5) * 220;
      const y = box.y + 140 + Math.floor(col / 5) * 220;
      col += 1;
      if (how === "drag") await drag(page, x, y, x + 140, y + 100);
      else {
        await page.mouse.click(x + 60, y + 40);
        await page.waitForTimeout(500);
        await page.keyboard.type(`${name} item`);
        await page.keyboard.press("Escape");
        await page.waitForTimeout(500);
      }
      const after = await count(page);
      console.log(`${after > before ? "OK  " : "FAIL"} tool ${name} (key ${key} -> ${tool}) items ${before} -> ${after}`);
    }
    // Links: the straight link from the sticky to the text box.
    const pair = await page.evaluate(() => {
      const els = [...document.querySelectorAll("#wb-html-layer .wb-object")].slice(-2);
      return els.map((el) => {
        const r = el.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      });
    });
    if (pair.length === 2) {
      await page.keyboard.press("Escape");
      await page.keyboard.press("c");
      const before = await count(page);
      await drag(page, pair[0].x, pair[0].y, pair[1].x, pair[1].y);
      const after = await count(page);
      console.log(`${after > before ? "OK  " : "FAIL"} tool straight link items ${before} -> ${after}`);
    }
    // Undo and redo by key.
    const b = await count(page);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(700);
    const u = await count(page);
    await page.keyboard.press("Control+Shift+z");
    await page.waitForTimeout(700);
    const r = await count(page);
    console.log(`${u < b && r === b ? "OK  " : "FAIL"} undo/redo by key ${b} -> ${u} -> ${r}`);
    // Select all, duplicate, delete.
    await page.keyboard.press("v");
    await page.keyboard.press("Control+a");
    await page.waitForTimeout(300);
    const sel = await page.evaluate(() => wbMultiSelection.size);
    console.log(`${sel >= 10 ? "OK  " : "FAIL"} Ctrl+A selected ${sel}`);
    await page.keyboard.press("Escape");
  }

  // --- B. Fill to TARGET through the routes, then measure ----------------
  await page.evaluate(async (target) => {
    const board = window.currentBoardId;
    const post = async (path, body) => (await api(path, { method: "POST", body: JSON.stringify(body) })).json();
    let have = (wbState.sketches || []).length + (wbState.objects || []).length + (wbState.nodes || []).length;
    const made = [];
    for (let i = 0; have < target; i++, have++) {
      const x = 80 + (i % 10) * 260;
      const y = 600 + Math.floor(i / 10) * 220;
      const kind = i % 4;
      if (kind === 0) {
        made.push(await post("/whiteboard/sketches", { board_id: board, x: 0, y: 0, data: JSON.stringify({ d: `M ${x} ${y} L ${x + 180} ${y} L ${x + 180} ${y + 120} L ${x} ${y + 120} Z`, color: "#335577", width: 3, shape: "rect" }) }));
      } else if (kind === 1) {
        let d = `M ${x} ${y}`;
        for (let k = 1; k < 40; k++) d += ` L ${x + k * 5} ${y + Math.sin(k / 3) * 30}`;
        made.push(await post("/whiteboard/sketches", { board_id: board, x: 0, y: 0, data: JSON.stringify({ d, color: "#aa3344", width: 3 }) }));
      } else {
        made.push(await post("/whiteboard/objects", { kind: "text", board_id: board, x, y, width: 200, height: 110, data: { content: `Card ${i}\n\nSome **body** text for card ${i}.`, bg: kind === 2 ? "#fff3a8" : undefined } }));
      }
    }
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit({ animate: false });
  }, TARGET);
  await page.waitForTimeout(1000);
  const total = await count(page);
  console.log(`board holds ${total} items; dom: ${await page.evaluate(() => document.querySelectorAll("#wb-html-layer > *, #wb-zoom-group > *").length)} top nodes`);

  await page.evaluate(() => {
    window.__renders = 0;
    const orig = window.renderWhiteboard;
    window.renderWhiteboard = function () { window.__renders += 1; return orig.apply(this, arguments); };
    window.__navRenders = 0;
    const nav = window.wbRenderNavigator;
    window.wbRenderNavigator = function () { window.__navRenders += 1; return nav.apply(this, arguments); };
    window.__long = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(e.duration); }).observe({ entryTypes: ["longtask"] });
    window.__startFrames = () => {
      window.__frames = []; window.__rafOn = true; window.__renders = 0; window.__navRenders = 0; window.__long = [];
      let last = performance.now();
      const tick = (t) => { if (!window.__rafOn) return; window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    };
    window.__stopFrames = () => { window.__rafOn = false; return { frames: window.__frames.slice(1), renders: window.__renders, nav: window.__navRenders, long: window.__long }; };
  });

  const metrics = async () => {
    const { metrics: m } = await cdp.send("Performance.getMetrics");
    const o = {};
    for (const x of m) o[x.name] = x.value;
    return o;
  };
  async function measure(label, gesture) {
    const m0 = await metrics();
    await page.evaluate(() => window.__startFrames());
    await gesture();
    await page.waitForTimeout(200);
    const res = await page.evaluate(() => window.__stopFrames());
    const m1 = await metrics();
    const f = res.frames;
    console.log(
      `PERF ${label}: frames ${f.length} median ${r1(median(f))}ms p95 ${r1(p95(f))}ms max ${r1(Math.max(0, ...f))}ms` +
      ` >33ms ${f.filter((x) => x > 33).length}; renders ${res.renders}; navigator ${res.nav}; longtasks ${res.long.length} (${r1(res.long.reduce((a, b) => a + b, 0))}ms)` +
      `; layouts ${m1.LayoutCount - m0.LayoutCount} (${r1((m1.LayoutDuration - m0.LayoutDuration) * 1000)}ms)` +
      ` styles ${m1.RecalcStyleCount - m0.RecalcStyleCount} (${r1((m1.RecalcStyleDuration - m0.RecalcStyleDuration) * 1000)}ms)` +
      ` script ${r1((m1.ScriptDuration - m0.ScriptDuration) * 1000)}ms`
    );
  }

  if (PARTS.includes("B")) {
    await page.keyboard.press("Escape");
    await page.keyboard.press("h");
    await measure("pan (hand, 60 moves)", async () => {
      await page.mouse.move(cx, cy);
      await page.mouse.down();
      for (let i = 0; i < 60; i++) await page.mouse.move(cx + Math.sin(i / 8) * 300, cy + Math.cos(i / 8) * 150);
      await page.mouse.up();
    });
    await measure("zoom (ctrl+wheel, 30 notches)", async () => {
      await page.mouse.move(cx, cy);
      await page.keyboard.down("Control");
      for (let i = 0; i < 15; i++) { await page.mouse.wheel(0, -100); await page.waitForTimeout(16); }
      for (let i = 0; i < 15; i++) { await page.mouse.wheel(0, 100); await page.waitForTimeout(16); }
      await page.keyboard.up("Control");
    });
    await measure("wheel scroll pan (30 notches)", async () => {
      await page.mouse.move(cx, cy);
      for (let i = 0; i < 30; i++) { await page.mouse.wheel(0, i < 15 ? 80 : -80); await page.waitForTimeout(16); }
    });
    await page.keyboard.press("v");
    const card = await page.evaluate(() => {
      const el = [...document.querySelectorAll("#wb-html-layer .wb-object")].find((e) => { const r = e.getBoundingClientRect(); return r.top > 120 && r.bottom < 800 && r.left > 50 && r.right < 1400; });
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + 10 };
    });
    if (card) {
      await measure("drag one card (40 moves)", async () => {
        await page.mouse.move(card.x, card.y);
        await page.mouse.down();
        for (let i = 0; i < 40; i++) await page.mouse.move(card.x + i * 4, card.y + i * 2);
        await page.mouse.up();
      });
      await page.waitForTimeout(600);
    }
    await page.keyboard.press("Control+a");
    await page.waitForTimeout(300);
    const any = await page.evaluate(() => {
      const el = [...document.querySelectorAll("#wb-html-layer .wb-object")].find((e) => { const r = e.getBoundingClientRect(); return r.top > 120 && r.bottom < 800 && r.left > 50 && r.right < 1400; });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + 10 };
    });
    await measure(`drag everything selected (${await page.evaluate(() => wbMultiSelection.size)} items, 40 moves)`, async () => {
      await page.mouse.move(any.x, any.y);
      await page.mouse.down();
      for (let i = 0; i < 40; i++) await page.mouse.move(any.x + i * 3, any.y + i);
      await page.mouse.up();
    });
    await page.waitForTimeout(800);
    await page.keyboard.press("Escape");
    await measure("idle 2s (nothing touched)", async () => { await page.waitForTimeout(2000); });
  }

  if (PARTS.includes("C")) {
    const heap = async () => { await cdp.send("HeapProfiler.collectGarbage"); return (await metrics()).JSHeapUsedSize / 1048576; };
    const nodes = async () => (await metrics()).Nodes;
    const h0 = await heap();
    const n0 = await nodes();
    const t0 = Date.now();
    let loops = 0;
    while (Date.now() - t0 < SOAK * 1000) {
      loops += 1;
      await page.keyboard.press("h");
      await drag(page, cx, cy, cx + 200, cy + 80, 6);
      await drag(page, cx + 200, cy + 80, cx, cy, 6);
      await page.mouse.move(cx, cy);
      await page.keyboard.down("Control");
      await page.mouse.wheel(0, -200); await page.mouse.wheel(0, 200);
      await page.keyboard.up("Control");
      await page.keyboard.press("v");
      await page.mouse.click(cx, cy);
      await page.keyboard.press("Escape");
      await page.keyboard.press("Control+a");
      await page.keyboard.press("Escape");
    }
    const h1 = await heap();
    const n1 = await nodes();
    console.log(`SOAK ${SOAK}s, ${loops} loops: JS heap ${r1(h0)}MB -> ${r1(h1)}MB, DOM nodes ${n0} -> ${n1}`);
  }
  console.log(`page errors: ${errors.length}${errors.length ? "  " + errors.slice(0, 3).join(" | ") : ""}`);
  await browser.close();
})();
