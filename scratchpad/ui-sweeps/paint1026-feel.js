// INBOX 1354 item 1: how rotating, resizing, moving and editing feel on the
// board, measured. Per handle: how far from its centre a press still lands
// on it (hit radius, screen px). Per gesture: whether a 2px slip on a click
// moves the item, whether a drag lands where the pointer went, what rotate
// does near 0/90 without Shift, and whether a double-click edits. Frame time
// and long tasks over each drag.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1280 node scratchpad/ui-sweeps/paint1026-feel.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 1280);
const TOUCH = W < 600;
//: A phone moves 40 across, not 100: the resize after it would end within
//: the edge pan's band at the right of a 390 screen and measure the pan.
const MOVE_X = TOUCH ? 40 : 100;
const MIN_HIT = TOUCH ? 12 : 8; // radius: 16px across on a mouse, 24 on touch (WCAG 2.5.8)

(async () => {
  const { browser, page, errors, board } = await openBoard({
    viewport: { width: W, height: TOUCH ? 844 : 900 }, boot: TOUCH ? { hasTouch: true, isMobile: true } : {},
  });
  const made = await page.evaluate(async (bid) => {
    const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: "M 200 200 h 160 v 100 h -160 Z", shape: "rect", color: "#335599", width: 2, fill: "#ffcc00", label: "Box" }),
      x: 0, y: 0, z: 1, board_id: bid,
    }) });
    const t = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Text box" }, board_id: bid, x: 200, y: 520, z: 1, width: 180, height: 80 }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    const c = document.getElementById("whiteboard-container");
    //: Zoom 1, centred, at every width: a fit zoom moves with the window and
    //: put the grips under the bar on a phone, measuring the layout instead.
    d3.select(c).call(wbZoom.transform, d3.zoomIdentity);
    wbCenterOn({ minX: 200, minY: 200, maxX: 460, maxY: 600 }, { animate: false });
    return { rect: s.id, text: t.id };
  }, board.id);
  await page.waitForTimeout(900);
  await page.evaluate(() => wbSelectToolRef?.("select"));

  // Frame stats while a gesture runs: rAF deltas and long tasks.
  const startFrames = () => page.evaluate(() => {
    window.__frames = []; window.__long = [];
    let last = performance.now();
    const tick = (t) => { window.__frames.push(t - last); last = t; if (window.__frames.length < 2000) window.__raf = requestAnimationFrame(tick); };
    window.__raf = requestAnimationFrame(tick);
    try { window.__po = new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)); }); window.__po.observe({ type: "longtask" }); } catch {}
  });
  const stopFrames = () => page.evaluate(() => {
    cancelAnimationFrame(window.__raf); window.__po?.disconnect();
    const f = window.__frames.slice(1).sort((a, b) => a - b);
    const p = (q) => +(f[Math.min(f.length - 1, Math.floor(f.length * q))] || 0).toFixed(1);
    return { frames: f.length, p50: p(0.5), p95: p(0.95), max: +(f[f.length - 1] || 0).toFixed(1), long: window.__long };
  });
  const rectBox = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }, sel);
  const drag = async (from, to, steps = 20) => {
    await page.mouse.move(from[0], from[1]);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / steps, from[1] + ((to[1] - from[1]) * i) / steps);
    await page.mouse.up();
    await page.waitForTimeout(400);
  };
  const sketchBox = (id) => page.evaluate((i) => { const b = wbPathBBox(JSON.parse(wbState.sketches.find((s) => s.id === i).data).d); return { x: Math.round(b.minX ?? b.x), y: Math.round(b.minY ?? b.y), w: Math.round((b.maxX ?? 0) - (b.minX ?? 0)), h: Math.round((b.maxY ?? 0) - (b.minY ?? 0)) }; }, id);
  const zoom = () => page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);

  // Select the rectangle.
  let r = await rectBox(`.sketch-group[data-id="${made.rect}"]`);
  await page.mouse.click(r.x + r.w / 2, r.y + r.h / 2);
  await page.waitForTimeout(400);
  // Hit radius of every handle on screen.
  const hits = await page.evaluate(() => {
    const out = [];
    for (const h of document.querySelectorAll(".wb-sketch-resize-handle, .wb-sketch-rotate-handle, .wb-resize-handle, .wb-rotate-handle")) {
      if (!h.getClientRects().length) continue;
      const b = h.getBoundingClientRect();
      if (!b.width) continue;
      const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
      let radius = 0, blocker = null;
      for (let d = 1; d <= 30 && !blocker; d++) {
        for (const [dx, dy] of [[d, 0], [-d, 0], [0, d], [0, -d]]) {
          const e = document.elementFromPoint(cx + dx, cy + dy);
          if (!(e === h || h.contains(e) || e?.closest?.("[data-handle]") === h)) { blocker = `${dx},${dy} ${e?.getAttribute?.("class")?.split(" ")[0] || e?.tagName}`; break; }
        }
        if (!blocker) radius = d;
      }
      out.push({ cls: h.getAttribute("class").split(" ")[0], visual: Math.round(b.width), radius, blocker });
    }
    return out;
  });
  const byCls = {};
  for (const h of hits) { const k = h.cls; byCls[k] = byCls[k] || { n: 0, minRadius: 99, visual: h.visual }; byCls[k].n++; if (h.radius < byCls[k].minRadius) { byCls[k].minRadius = h.radius; byCls[k].blocker = h.blocker; } }
  const gaps = await page.evaluate((id) => {
    const top = document.querySelector(`.sketch-group[data-id="${id}"]`).getBoundingClientRect().top;
    const at = (sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return Math.round(top - (b.top + b.height / 2)); };
    const bar = document.getElementById("wb-context")?.getBoundingClientRect();
    return { rotate: at(".wb-sketch-rotate-handle"), cloneUp: at('.wb-clone-grip[data-dir="up"]'), top: Math.round(top), bar: bar && [Math.round(bar.top), Math.round(bar.bottom), Math.round(bar.left), Math.round(bar.right)] };
  }, made.rect);
  console.log("handles", JSON.stringify(byCls), "zoom", await zoom(), "above the top edge", JSON.stringify(gaps));
  for (const [k, v] of Object.entries(byCls)) check(`${k}: a press within ${MIN_HIT}px of its centre lands on it`, v.minRadius >= MIN_HIT, v);

  // A click that slips 2px does not move the shape.
  const before = await sketchBox(made.rect);
  r = await rectBox(`.sketch-group[data-id="${made.rect}"]`);
  await drag([r.x + r.w / 2, r.y + r.h / 2], [r.x + r.w / 2 + 2, r.y + r.h / 2 + 1], 2);
  const slipped = await sketchBox(made.rect);
  check("a 2px slip on a click leaves the shape where it was", slipped.x === before.x && slipped.y === before.y, { before, slipped });

  // A 100px drag lands 100px (in board units at this zoom) away.
  const k = await zoom();
  r = await rectBox(`.sketch-group[data-id="${made.rect}"]`);
  await startFrames();
  await drag([r.x + r.w / 2, r.y + r.h / 2], [r.x + r.w / 2 + MOVE_X, r.y + r.h / 2 + 50], 30);
  const moveFrames = await stopFrames();
  const moved = await sketchBox(made.rect);
  const dx = Math.round((moved.x - slipped.x) * k), dy = Math.round((moved.y - slipped.y) * k);
  check(`a ${MOVE_X}x50 drag moves the shape ${MOVE_X}x50 on screen (2px)`, Math.abs(dx - MOVE_X) <= 2 && Math.abs(dy - 50) <= 2, { dx, dy, k });
  console.log("move frames", JSON.stringify(moveFrames));

  // Resize from the bottom-right handle by +60,+40.
  await page.waitForTimeout(300);
  const se = await page.evaluate(() => {
    let best = null;
    for (const h of document.querySelectorAll(".wb-sketch-resize-handle")) {
      const b = h.getBoundingClientRect();
      if (!best || b.x + b.y > best.x + best.y) best = { x: b.x + b.width / 2, y: b.y + b.height / 2 };
    }
    return best;
  });
  if (se) {
    const b0 = await sketchBox(made.rect);
    await startFrames();
    await drag([se.x, se.y], [se.x + 60, se.y + 40], 30);
    const resizeFrames = await stopFrames();
    const b1 = await sketchBox(made.rect);
    const gw = Math.round((b1.w - b0.w) * k), gh = Math.round((b1.h - b0.h) * k);
    check("a +60,+40 corner drag grows it 60x40 on screen (3px)", Math.abs(gw - 60) <= 3 && Math.abs(gh - 40) <= 3, { gw, gh, b0, b1 });
    console.log("resize frames", JSON.stringify(resizeFrames));
  } else check("a corner handle shows", false);

  // Rotate: drag the rotate handle to about 87 degrees without Shift.
  const rot = await rectBox(".wb-sketch-rotate-handle");
  if (rot) {
    const box = await rectBox(`.sketch-group[data-id="${made.rect}"]`);
    const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
    const rad = Math.hypot(rot.x + rot.w / 2 - cx, rot.y + rot.h / 2 - cy);
    const a = (88 - 90) * Math.PI / 180; // 88 degrees clockwise from up
    if (process.env.PROBE) await page.evaluate(() => { const f = wbSketchAngleFromCenterDeg; window.__ang = []; wbSketchAngleFromCenterDeg = (...a) => { const v = f(...a); window.__ang.push(v); return v; }; window.__hit = []; addEventListener("pointerdown", (e) => window.__hit.push(e.target.getAttribute("class")), true); });
    await startFrames();
    await drag([rot.x + rot.w / 2, rot.y + rot.h / 2], [cx + rad * Math.cos(a), cy + rad * Math.sin(a)], 30);
    const rotFrames = await stopFrames();
    const angle = await page.evaluate((i) => { const d = JSON.parse(wbState.sketches.find((s) => s.id === i).data); return d.turned ?? null; }, made.rect);
    if (process.env.PROBE) console.log("probe", JSON.stringify(await page.evaluate(() => ({ n: window.__ang.length, last: window.__ang.slice(-2), hit: window.__hit, gest: !!wbGesture }))));
    console.log("rotate to ~88 without Shift:", angle, "frames", JSON.stringify(rotFrames));
    check("rotating to within 3 degrees of 90 settles on 90", angle != null && Math.abs(angle - 90) < 0.5, angle);
  } else check("a rotate handle shows", false);

  // Double-click the text box edits it.
  const tb = await rectBox(`.wb-object[data-id="${made.text}"]`);
  await page.mouse.dblclick(tb.x + tb.w / 2, tb.y + tb.h / 2);
  await page.waitForTimeout(300);
  const editing = await page.evaluate(() => document.activeElement?.isContentEditable || document.activeElement?.tagName === "TEXTAREA");
  check("a double-click on a text box puts the caret in it", editing);
  await page.keyboard.press("Escape");
  // Double-click the shape writes in it.
  r = await rectBox(`.sketch-group[data-id="${made.rect}"]`);
  await page.mouse.click(10, 10);
  await page.mouse.dblclick(r.x + r.w / 2, r.y + r.h / 2);
  await page.waitForTimeout(300);
  const shapeEdit = await page.evaluate(() => document.activeElement?.isContentEditable || document.activeElement?.tagName === "TEXTAREA");
  check("a double-click on a shape writes in it", shapeEdit);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
