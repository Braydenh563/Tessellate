// INBOX 431 (the owner, 2026-09-28, Windows): "the fit drag mini fit map on
// the whiteboard and mindmap is reallllly glitchy and laggy."
//
// The board overview (`#wb-navigator`, whiteboard.js "The navigator") is one
// widget on both surfaces: a mind map is a board whose objects are topics.
// This sweep measures the two gestures the report names, on a board of ~150
// cards with ~100 links and on a ~150-topic map, at a 4x CPU throttle (CDP
// `Emulation.setCPUThrottlingRate`) to stand in for the owner's laptop:
//
//   drag  press on the viewport rectangle's centre, 60 `page.mouse` moves over
//         about a second, release. A rAF logger started before the press
//         gives the frame intervals (count, p50, p95, max); a `longtask`
//         PerformanceObserver gives every main-thread task over 50ms; CDP
//         `Performance.getMetrics` gives the layouts and style recalcs the
//         gesture cost. **Tracking**: right after the last move (two frames
//         later, still pressed) the distance between the viewport
//         rectangle's centre and the pointer, both in screen px. A drag that
//         keeps up and does not rescale the map under the pointer reads 0.
//   fit   a click on the overview's Fit button; the same frame and long-task
//         numbers over its animation.
//
//   BASE=http://127.0.0.1:8794 SCRATCH=/tmp/mm-minimap \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/minimapdrag.js
//
// THROTTLE=1 for an unthrottled run; N=150 for the item count.
const { boot } = require("./lib.js");

const N = Number(process.env.N || 150);
const THROTTLE = Number(process.env.THROTTLE || 4);

const pct = (xs, p) => {
  const s = [...xs].sort((a, b) => a - b);
  if (!s.length) return 0;
  return s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))];
};
const r1 = (x) => Math.round(x * 10) / 10;

function outline(n) {
  const lines = [`# Minimap ${n}`, "- Trunk"];
  const depth = [0];
  let made = 1;
  let parent = 0;
  let kids = 0;
  while (made < n) {
    if (kids === 5) {
      parent += 1;
      kids = 0;
      continue;
    }
    const d = depth[parent] + 1;
    depth.push(d);
    lines.push(`${"  ".repeat(d)}- Topic ${made}`);
    made += 1;
    kids += 1;
  }
  return lines.join("\n");
}

async function seedBoard(page, n) {
  return page.evaluate(async (n) => {
    const board = await apiJson("/whiteboard/boards", {
      method: "POST",
      body: JSON.stringify({ name: `minimap ${Date.now()}`, type: "board" }),
    });
    const cols = 15;
    const half = Math.floor(n / 2);
    const nodes = [];
    // Half note cards (the kind measured from the live DOM), half text boxes.
    for (let i = 0; i < half; i += 10) {
      const batch = [];
      for (let j = i; j < Math.min(i + 10, half); j++) {
        batch.push((async () => {
          const e = await apiJson("/entries", {
            method: "POST",
            body: JSON.stringify({ content: `Minimap card ${j}\n\nSome words so the card has a body.`, category: "Sweep" }),
          });
          const node = await apiJson("/whiteboard/nodes", {
            method: "POST",
            body: JSON.stringify({ board_id: board.id, entry_id: e.id, x: (j % cols) * 260, y: Math.floor(j / cols) * 220, z: 1 }),
          });
          return { kind: "node", id: node.id };
        })());
      }
      nodes.push(...(await Promise.all(batch)));
    }
    for (let i = half; i < n; i += 10) {
      const batch = [];
      for (let j = i; j < Math.min(i + 10, n); j++) {
        batch.push(apiJson("/whiteboard/objects", {
          method: "POST",
          body: JSON.stringify({
            board_id: board.id, kind: "text",
            x: (j % cols) * 260, y: Math.floor(j / cols) * 220 + 40,
            width: 180, height: 90, data: { content: `Box ${j}` },
          }),
        }).then((o) => ({ kind: "object", id: o.id })));
      }
      nodes.push(...(await Promise.all(batch)));
    }
    // About 100 links, each between neighbours in the grid.
    const links = [];
    for (let i = 0; i + 1 < nodes.length && links.length < 100; i += 1) {
      const a = nodes[i];
      const b = nodes[i + 1];
      links.push(apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({
          board_id: board.id, x: 0, y: 0, z: 1,
          data: JSON.stringify({ type: "link-curved", sourceId: a.id, sourceKind: a.kind, targetId: b.id, targetKind: b.kind, color: "#7dd3c8" }),
        }),
      }));
      if (links.length % 10 === 0) await Promise.all(links.slice(-10));
    }
    await Promise.all(links);
    return board.id;
  }, n);
}

async function seedMap(page, n) {
  const board = await page.evaluate(
    async ([content, name]) =>
      apiJson("/whiteboard/boards/import", {
        method: "POST",
        body: JSON.stringify({ format: "markdown", content, name }),
      }),
    [outline(n), `Minimap map ${n}`]
  );
  return board.id;
}

async function openBoard(page, id) {
  await page.evaluate(async (id) => {
    await openWhiteboardBoard(id);
    await new Promise((r) => setTimeout(r, 1500));
    wbToggleNavigator(true);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }, id);
  await page.waitForTimeout(800);
}

// Frames, long tasks and a pointer log, started before a gesture.
async function startRecording(page) {
  await page.evaluate(() => {
    window.__mm = { frames: [], long: [], on: true };
    let last = performance.now();
    const tick = (t) => {
      if (!window.__mm.on) return;
      window.__mm.frames.push(t - last);
      last = t;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    try {
      window.__mmObs = new PerformanceObserver((list) => {
        for (const e of list.getEntries()) window.__mm.long.push(e.duration);
      });
      window.__mmObs.observe({ type: "longtask" });
    } catch (e) {
      /* no longtask support: reported as none */
    }
  });
}

async function stopRecording(page) {
  return page.evaluate(() => {
    window.__mm.on = false;
    window.__mmObs?.disconnect();
    return { frames: window.__mm.frames.slice(1), long: window.__mm.long };
  });
}

function viewportRect(page) {
  return page.evaluate(() => {
    const r = document.querySelector("#wb-navigator-map .wb-nav-viewport")?.getBoundingClientRect();
    const m = document.getElementById("wb-navigator-map").getBoundingClientRect();
    return r ? { cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height, map: { x: m.left, y: m.top, w: m.width, h: m.height } } : null;
  });
}

async function metrics(cdp) {
  const { metrics } = await cdp.send("Performance.getMetrics");
  const m = Object.fromEntries(metrics.map((x) => [x.name, x.value]));
  return { layouts: m.LayoutCount, styles: m.RecalcStyleCount, script: m.ScriptDuration, layoutMs: m.LayoutDuration };
}

function summary(rec) {
  const f = rec.frames;
  return {
    frames: f.length,
    p50: r1(pct(f, 50)),
    p95: r1(pct(f, 95)),
    max: r1(Math.max(0, ...f)),
    longTasks: rec.long.length,
    longestTask: r1(Math.max(0, ...rec.long)),
  };
}

async function measure(page, cdp, label) {
  const out = { label };
  // ---- drag --------------------------------------------------------------
  const start = await viewportRect(page);
  if (!start) {
    console.log(label, "no viewport rectangle drawn");
    return out;
  }
  // Toward the middle of the map, 60px of travel, so the rectangle stays on
  // the map the whole way and a correct drag can track exactly.
  const mx = start.map.x + start.map.w / 2;
  const my = start.map.y + start.map.h / 2;
  let dx = mx - start.cx;
  let dy = my - start.cy;
  const len = Math.hypot(dx, dy);
  if (len < 20) {
    dx = 1;
    dy = 0.4;
  }
  const norm = Math.hypot(dx, dy);
  const travel = 60;
  const ex = start.cx + (dx / norm) * travel;
  const ey = start.cy + (dy / norm) * travel;
  const before = await page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return { x: t.x, y: t.y, k: t.k }; });
  await page.mouse.move(start.cx, start.cy);
  await page.waitForTimeout(200);
  const m0 = await metrics(cdp);
  await startRecording(page);
  const t0 = Date.now();
  await page.mouse.down();
  const STEPS = 60;
  for (let i = 1; i <= STEPS; i++) {
    const target = t0 + (i * 1000) / STEPS;
    await page.mouse.move(start.cx + ((ex - start.cx) * i) / STEPS, start.cy + ((ey - start.cy) * i) / STEPS);
    const wait = target - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
  }
  const dragMs = Date.now() - t0;
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const end = await viewportRect(page);
  await page.mouse.up();
  const rec = await stopRecording(page);
  const m1 = await metrics(cdp);
  await page.waitForTimeout(300);
  const settled = await viewportRect(page);
  const after = await page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return { x: t.x, y: t.y, k: t.k }; });
  out.drag = {
    ...summary(rec),
    ms: dragMs,
    layouts: m1.layouts - m0.layouts,
    styles: m1.styles - m0.styles,
    scriptMs: r1((m1.script - m0.script) * 1000),
    layoutMs: r1((m1.layoutMs - m0.layoutMs) * 1000),
    trackPx: end ? r1(Math.hypot(end.cx - ex, end.cy - ey)) : null,
    settledPx: settled ? r1(Math.hypot(settled.cx - ex, settled.cy - ey)) : null,
    boardMoved: r1(Math.hypot(after.x - before.x, after.y - before.y)),
  };
  console.log(`${label} drag  ${JSON.stringify(out.drag)}`);

  // ---- fit ---------------------------------------------------------------
  // Pan away first so the fit has somewhere to go.
  await page.evaluate(() => {
    const c = document.getElementById("whiteboard-container");
    d3.select(c).call(wbZoom.transform, d3.zoomIdentity.translate(-1200, -600).scale(1));
  });
  await page.waitForTimeout(400);
  const f0 = await metrics(cdp);
  await startRecording(page);
  // FITJUMP=1: the same fit with no animation, for comparing the two.
  if (process.env.FITJUMP) await page.evaluate(() => wbZoomToFit({ animate: false }));
  else await page.click("#wb-navigator-fit");
  await page.waitForTimeout(700);
  const frec = await stopRecording(page);
  const f1 = await metrics(cdp);
  out.fit = {
    ...summary(frec),
    layouts: f1.layouts - f0.layouts,
    styles: f1.styles - f0.styles,
    scriptMs: r1((f1.script - f0.script) * 1000),
  };
  console.log(`${label} fit   ${JSON.stringify(out.fit)}`);
  // FRAMES=1: every frame interval of the fit, to tell one heavy frame from
  // a run of slow ones.
  if (process.env.FRAMES) console.log(`${label} fit frames ${frec.frames.map((x) => Math.round(x)).join(" ")}`);
  return out;
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  const boardId = process.env.BOARD_ID ? Number(process.env.BOARD_ID) : await seedBoard(page, N);
  const mapId = process.env.MAP_ID ? Number(process.env.MAP_ID) : await seedMap(page, N);
  console.log(`board ${boardId}, map ${mapId} (BOARD_ID=${boardId} MAP_ID=${mapId} to reuse)`);

  const results = [];
  for (const [label, id] of [["board", boardId], ["map", mapId]]) {
    await openBoard(page, id);
    const counts = await page.evaluate(() => ({
      nodes: wbState.nodes.length, objects: wbState.objects.length, sketches: wbState.sketches.length,
      navItems: document.querySelectorAll("#wb-navigator-map .wb-nav-item").length,
    }));
    console.log(`${label} ${JSON.stringify(counts)}`);
    if (THROTTLE > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: THROTTLE });
    results.push(await measure(page, cdp, label));
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  }
  console.log(`\nthrottle ${THROTTLE}x`);
  for (const r of results) {
    if (!r.drag) continue;
    const d = r.drag;
    const f = r.fit;
    console.log(`${r.label.padEnd(6)} drag frames ${d.frames} p50 ${d.p50} p95 ${d.p95} max ${d.max} long ${d.longTasks} (max ${d.longestTask}) layouts ${d.layouts} track ${d.trackPx}px settled ${d.settledPx}px`);
    console.log(`${r.label.padEnd(6)} fit  frames ${f.frames} p50 ${f.p50} p95 ${f.p95} max ${f.max} long ${f.longTasks} (max ${f.longestTask}) layouts ${f.layouts}`);
  }
  await browser.close();
})();
