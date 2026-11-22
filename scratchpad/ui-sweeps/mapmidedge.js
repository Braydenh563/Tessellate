// L759 (13g): a middle-button drag to each window edge and past it, held, then released,
// with a pointer-event trace. Run headless and headed (HEADED=1 under xvfb-run -a).
// 2026-11-12, both modes: the board follows the hand in all four directions
// (right +828, left -840, down +514, up -573 board px), stays put after release,
// and every middle mousedown is defaultPrevented (the autoscroll guard is reached).
// **Panning with the middle mouse button held** (INBOX: the owner, "the
// mindmap is still insanely laggy to pan around... also the whiteboard and
// mindmap goes haywire and moves to the left when I try to move around by
// pushing down my mouse scroll wheel and moving the mouse to the edges of the
// screen, no matter which direction").
//
// Two separate questions, and this probe answers them separately.
//
// **1. Is the middle-button pan the same code as the measured one?**
// `mapperf.js` pans with the Hand tool and a left-button drag, and reports a
// steady 16.7ms at every map size. The owner does not use the Hand tool: he
// holds the wheel down. That reaches d3-zoom through `wbZoomFilter`'s middle
// branch, which is a different door into the same behaviour, so this repeats
// the frame measurement through that door rather than assuming the two are
// the same. Same rAF recorder as mapperf, so the numbers are comparable.
//
// **2. Does the board move the way the pointer moved?** Four drags, one per
// direction, each starting from a recorded transform, each asserting that the
// board went the way the hand did and by roughly the distance the hand
// travelled. "Moves to the left no matter which direction" is exactly what
// this catches, and it needs a number per direction rather than a screenshot:
// a pan that is right for one direction and wrong for the other three would
// look fine in any single capture.
//
// **What this cannot see.** Chromium's middle-button autoscroll is a
// platform behaviour of the windowed browser; a headless run has none to
// suppress, so the `mousedown` guard that exists for it (INBOX 183) is not
// exercised here and this sweep passing is not evidence that the guard works
// on the owner's machine. Said plainly rather than left to be assumed.
//
//   BASE=http://127.0.0.1:8805 SCRATCH=/tmp/mm-maprender \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapmidpan.js
const { boot } = require("./lib.js");

const SIZES = (process.env.SIZES || "50,500").split(",").map(Number);
const results = [];
const check = (label, ok, detail) => {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
};
const r1 = (x) => Math.round(x * 10) / 10;
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};

function outline(n) {
  const lines = [`# Mid ${n}`];
  const depth = [0];
  lines.push(`- Trunk`);
  let made = 1, parent = 0, k = 0;
  while (made < n) {
    if (k === 5) { parent += 1; k = 0; continue; }
    const d = depth[parent] + 1;
    depth.push(d);
    lines.push(`${"  ".repeat(d)}- Topic ${made}`);
    made += 1; k += 1;
  }
  return lines.join("\n");
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await page.waitForTimeout(500);
  //: `__rafOn`, never `__on`: d3 keeps its own listener list on a node in a
  //: property called `__on`, and `event.view` is the window, so a probe that
  //: parks a boolean there makes `selection.on(...)` throw "push is not a
  //: function" inside d3-zoom's own mousedown handler. Cost half an hour and
  //: looked exactly like the app bug being hunted: the pan never started and
  //: every later mousemove threw. mapperf.js uses `__rafOn` for this reason.
  await page.evaluate(() => {
    window.__frames = [];
    window.__startFrames = () => {
      window.__frames = []; window.__rafOn = true;
      let last = performance.now();
      const tick = (t) => { if (!window.__rafOn) return; window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    };
    window.__stopFrames = () => { window.__rafOn = false; return window.__frames.slice(1); };
  });

  for (const n of SIZES) {
    const board = await page.evaluate(
      async ([content, name]) => apiJson("/whiteboard/boards/import", {
        method: "POST", body: JSON.stringify({ format: "markdown", content, name }),
      }),
      [outline(n), `Mid ${n}`]
    );
    const drawn = await page.evaluate(async ([id, want]) => {
      await openWhiteboardBoard(id);
      const deadline = performance.now() + 30000;
      while (performance.now() < deadline) {
        if (document.querySelectorAll("#wb-html-layer .wb-map-node").length >= want) break;
        await new Promise((r) => setTimeout(r, 8));
      }
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return document.querySelectorAll("#wb-html-layer .wb-map-node").length;
    }, [board.id, n]);
    check(`${n}: opened`, drawn >= n, `${drawn} topics drawn`);

    await page.click('#wb-tool-group button[data-tool="select"]');
    await page.waitForTimeout(300);
    const box = await page.evaluate(() => { const b = document.getElementById("whiteboard-container").getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; });
    await page.evaluate(() => {
      window.__trace = [];
      for (const t of ["pointerdown", "pointermove", "pointerup", "pointercancel", "mousedown", "mouseup", "auxclick", "lostpointercapture", "blur"])
        window.addEventListener(t, (e) => window.__trace.push([t, e.button, e.buttons, Math.round(e.clientX || 0), Math.round(e.clientY || 0), e.defaultPrevented]), true);
    });
    const tf = () => page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return [Math.round(t.x), Math.round(t.y)]; });
    const cx = (box.l + box.r) / 2, cy = (box.t + box.b) / 2;
    // To each edge, then past it (outside the window), held there, then back.
    const edges = [["right", box.r - 2, cy, box.r + 120, cy], ["left", box.l + 2, cy, -120, cy], ["down", cx, box.b - 2, cx, box.b + 120], ["up", cx, box.t + 2, cx, -120]];
    for (const [name, ex, ey, ox, oy] of edges) {
      await page.mouse.move(cx, cy);
      const before = await tf();
      await page.evaluate(() => { window.__trace = []; });
      await page.mouse.down({ button: "middle" });
      for (let i = 1; i <= 20; i++) { await page.mouse.move(cx + (ex - cx) * i / 20, cy + (ey - cy) * i / 20); await page.waitForTimeout(8); }
      const atEdge = await tf();
      for (let i = 1; i <= 10; i++) { await page.mouse.move(ex + (ox - ex) * i / 10, ey + (oy - ey) * i / 10); await page.waitForTimeout(8); }
      await page.waitForTimeout(600);
      const held = await tf();
      await page.mouse.up({ button: "middle" });
      await page.waitForTimeout(400);
      const after = await tf();
      const trace = await page.evaluate(() => window.__trace);
      const kinds = {}; for (const e of trace) kinds[e[0]] = (kinds[e[0]] || 0) + 1;
      const prevented = trace.filter((e) => e[0] === "mousedown" && e[5]).length;
      console.log(JSON.stringify({ name, before, atEdge, held, after, kinds, mousedownPrevented: prevented }));
    }
  }
  await browser.close();
})();
