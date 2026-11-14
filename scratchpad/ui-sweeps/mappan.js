// INBOX 183, the two pan reports: "panning on the whiteboard by pressing down
// the scrollwheel with a mouse is horrible and doesnt work", and "when I drag
// around and pan using the hand tool, the note objects are fine, but all
// shapes, lines and connections lagg behind in position and arent synched".
//
// Both are measured here rather than looked at. The middle-button half reads
// the board transform before, during and after a real `page.mouse` gesture
// with `button: "middle"`; the sync half reads a note card's screen rect and a
// sketch path's screen rect after every single move of a left-button pan under
// the hand tool, and reports the largest drift between them. Two objects that
// pan as one layer never drift: the number is 0 or the report is real.
//
//   BASE=http://127.0.0.1:8791 SCRATCH=/tmp/mm-map \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mappan.js
const { boot } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 1440, height: 900 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 1440, height: h || 900 };
})();

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

// The board: two text objects, a drawn rectangle sketch and a link between the
// objects, so a pan has a card, a shape and a connector to keep together.
async function buildBoard(page) {
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  return page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
    const board = await apiJson("/whiteboard/boards", {
      method: "POST",
      body: JSON.stringify({ name: `pan ${Date.now()}`, type: "board" }),
    });
    window.currentBoardId = board.id;
    wbShowCanvasView();
    await fetchWhiteboardState(board.id);
    const mk = (x, y, text) => apiJson("/whiteboard/objects", {
      method: "POST",
      body: JSON.stringify({ board_id: board.id, kind: "text", x, y, width: 180, height: 90, data: { content: text } }),
    });
    const a = await mk(120, 120, "left");
    const b = await mk(520, 320, "right");
    await apiJson("/whiteboard/sketches", {
      method: "POST",
      body: JSON.stringify({
        board_id: board.id, x: 0, y: 0, z: 1,
        // A shape sketch is a path (`d`) the board draws, the rectangle tool's
        // own `M x y h w v h h -w Z`, with the shape name beside it. The old
        // fixture stored `{type: "rect", x, y, width, height}`, which is not a
        // path, so the renderer set it as `d` and the browser logged "Expected
        // moveto path command" on every draw.
        data: JSON.stringify({ d: "M 140 320 h 200 v 140 h -200 Z", shape: "rect", color: "#7dd3c8", width: 3 }),
      }),
    });
    await apiJson("/whiteboard/sketches", {
      method: "POST",
      body: JSON.stringify({
        board_id: board.id, x: 0, y: 0, z: 1,
        data: JSON.stringify({ type: "link-curved", sourceId: a.id, sourceKind: "object", targetId: b.id, targetKind: "object", color: "#7dd3c8" }),
      }),
    });
    await fetchWhiteboardState(board.id);
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 400));
    return { board: board.id, a: a.id, b: b.id };
  });
}

// Every number this sweep reports comes through here: the board transform, one
// card's screen rect, one shape's screen rect, and the gap between the two.
function probe(page) {
  return page.evaluate(() => {
    const read = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const m = new DOMMatrixReadOnly(getComputedStyle(el).transform);
      return { x: m.e, y: m.f, k: m.a };
    };
    const rect = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.left * 100) / 100, y: Math.round(r.top * 100) / 100 };
    };
    const card = document.querySelector("#wb-html-layer .wb-object, #wb-html-layer .wb-card, #wb-html-layer .node-card");
    const shape = document.querySelector("#wb-shapes-group path, #wb-shapes-group rect, #wb-zoom-group .sketch-group path");
    const link = document.querySelector(".wb-link-sketch path, #wb-lines-group path");
    return {
      html: read("#wb-html-layer"),
      svg: read("#wb-svg-layer"),
      overlay: read("#wb-overlay-layer"),
      card: rect(card),
      shape: rect(shape),
      link: rect(link),
    };
  });
}

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });
  const read = () => probe(page);
  // The fixture's own mistakes show up here, not as a pan failure: a sketch
  // whose data was not a valid path logged "Expected moveto path command" twice
  // for as long as this sweep existed, and nothing asserted on it.
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 140)); });
  const ids = await buildBoard(page);
  console.log("board", JSON.stringify(ids));
  const box = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
  const cx = Math.round(box.x + box.w / 2);
  const cy = Math.round(box.y + box.h / 2);

  // ---- 1a: the middle button ----------------------------------------------
  // A press with no movement must not start an autoscroll, and the drag must
  // move the board by exactly what the pointer moved.
  await page.click('#wb-tool-group [data-tool="select"]');
  await page.waitForTimeout(200);
  const before = await read();
  await page.mouse.move(cx, cy);
  await page.mouse.down({ button: "middle" });
  await page.waitForTimeout(60);
  // The cursor of what is under the pointer, which is the one a person sees.
  // It used to be read off the container, because the container carried it;
  // it is the pan shield's now (MINDMAP_PLAN 13a-view), and reading the
  // element at the point is true whichever element carries it.
  const midCursor = await page.evaluate(([x, y]) => {
    const c = document.getElementById("whiteboard-container");
    const at = document.elementFromPoint(x, y);
    return { cls: c.classList.contains("wb-mid-pan"), cursor: getComputedStyle(at).cursor, sel: getComputedStyle(at).userSelect };
  }, [cx, cy]);
  check("a middle press says it is a pan", midCursor.cls && midCursor.cursor === "grabbing",
    `class ${midCursor.cls}, cursor ${midCursor.cursor}, user-select ${midCursor.sel}`);
  const steps = [];
  for (let i = 1; i <= 6; i++) {
    await page.mouse.move(cx - i * 20, cy - i * 12);
    steps.push(await read());
  }
  await page.mouse.up({ button: "middle" });
  await page.waitForTimeout(250);
  const after = await read();
  const dx = after.html.x - before.html.x;
  const dy = after.html.y - before.html.y;
  check("middle button pans the board at all", Math.abs(dx) > 10 || Math.abs(dy) > 10,
    `moved ${Math.round(dx)},${Math.round(dy)} for a pointer move of -120,-72`);
  check("middle-button pan matches the pointer 1:1", Math.abs(dx + 120) < 2 && Math.abs(dy + 72) < 2,
    `dx ${dx.toFixed(1)} want -120, dy ${dy.toFixed(1)} want -72`);
  const tracked = steps.filter((s, i) => Math.abs(s.html.x - before.html.x + (i + 1) * 20) < 2).length;
  check("the board tracks every middle-drag move", tracked === steps.length,
    `${tracked}/${steps.length} moves landed where the pointer was`);
  const sel = await page.evaluate(() => (window.getSelection() || { toString: () => "" }).toString().length);
  check("a middle drag selects no text", sel === 0, `${sel} characters selected`);
  const strays = await page.evaluate(() => document.querySelectorAll(".wb-marquee").length);
  check("a middle drag leaves no marquee", strays === 0, `${strays} rectangles`);
  const restCursor = await page.evaluate(([x, y]) => {
    const c = document.getElementById("whiteboard-container");
    const at = document.elementFromPoint(x, y);
    return { cls: c.classList.contains("wb-mid-pan"), cursor: getComputedStyle(at).cursor };
  }, [cx - 120, cy - 72]);
  check("the grabbing cursor is dropped on release", !restCursor.cls && restCursor.cursor !== "grabbing",
    `class ${restCursor.cls}, cursor ${restCursor.cursor}`);

  // ---- 1b: every layer moves as one under the hand tool --------------------
  await page.click('#wb-tool-group [data-tool="pan"]');
  await page.waitForTimeout(300);
  const start = await read();
  const baseGapX = start.card && start.shape ? start.card.x - start.shape.x : null;
  const baseGapY = start.card && start.shape ? start.card.y - start.shape.y : null;
  const baseLinkX = start.card && start.link ? start.card.x - start.link.x : null;
  let worstShape = 0;
  let worstLink = 0;
  let worstLayer = 0;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (let i = 1; i <= 14; i++) {
    await page.mouse.move(cx + i * 18, cy + i * 9);
    const s = await read();
    if (s.card && s.shape) {
      worstShape = Math.max(worstShape, Math.abs(s.card.x - s.shape.x - baseGapX), Math.abs(s.card.y - s.shape.y - baseGapY));
    }
    if (s.card && s.link) worstLink = Math.max(worstLink, Math.abs(s.card.x - s.link.x - baseLinkX));
    worstLayer = Math.max(worstLayer, Math.abs(s.html.x - s.svg.x), Math.abs(s.html.y - s.svg.y),
      Math.abs(s.html.x - s.overlay.x), Math.abs(s.html.y - s.overlay.y));
  }
  await page.mouse.up();
  await page.waitForTimeout(300);
  const end = await read();
  check("a shape never drifts from a note during a hand pan", worstShape < 0.5,
    `worst drift ${worstShape.toFixed(2)}px over 14 moves`);
  check("a connector never drifts from a note during a hand pan", worstLink < 0.5,
    `worst drift ${worstLink.toFixed(2)}px`);
  check("the three zoom layers hold the same transform mid-pan", worstLayer < 0.5,
    `worst ${worstLayer.toFixed(2)}px`);
  const endGapX = end.card.x - end.shape.x;
  check("the shape lands where it started relative to the note", Math.abs(endGapX - baseGapX) < 0.5,
    `gap ${endGapX.toFixed(2)} vs ${baseGapX.toFixed(2)}`);

  check("the board draws with no console errors", consoleErrors.length === 0, consoleErrors.join(" | "));

  const bad = results.filter((r) => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} passed`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})();
