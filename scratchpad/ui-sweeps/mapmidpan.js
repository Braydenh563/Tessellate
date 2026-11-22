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

    // The Select tool, deliberately: the whole point of the middle button is
    // that it pans from any tool, and Select is what a person is on.
    await page.click('#wb-tool-group button[data-tool="select"]');
    await page.waitForTimeout(300);
    const canvas = await page.evaluate(() => {
      const b = document.getElementById("whiteboard-container").getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    });

    //: **Both doors, in the same run, and compared to each other rather than
    //: to a fixed budget.** Panning a large map is bimodal on this machine:
    //: the identical gesture measures 16.7ms per frame in one run and 116 to
    //: 150ms in the next, whichever tool and whichever button, because the
    //: cost is the browser re-rasterising a promoted layer that holds every
    //: topic rather than anything on the JS path (measured under the CPU
    //: profiler: under 10ms of script across a whole 30-move gesture). A
    //: fixed 16.7ms assertion here would be a coin toss. What *is* stable is
    //: the comparison: the middle button must not be worse than the Hand
    //: tool, because they are the same code reached through two doors, and if
    //: they ever diverge that is a real finding.
    const panWith = async (tool, button) => {
      await page.click(`#wb-tool-group button[data-tool="${tool}"]`);
      await page.waitForTimeout(300);
      await page.mouse.move(canvas.x - 250, canvas.y);
      await page.evaluate(() => window.__startFrames());
      await page.mouse.down({ button });
      for (let i = 1; i <= 30; i++) {
        await page.mouse.move(canvas.x - 250 + i * 12, canvas.y + Math.sin(i / 4) * 40);
        await page.waitForTimeout(8);
      }
      await page.mouse.up({ button });
      const f = await page.evaluate(() => window.__stopFrames());
      await page.evaluate(() => d3.select("#whiteboard-container").call(wbZoom.transform, d3.zoomIdentity));
      await page.waitForTimeout(200);
      return { median: r1(median(f)), worst: r1(Math.max(0, ...f)), frames: f.length };
    };
    const hand = await panWith("pan", "left");
    const mid = await panWith("select", "middle");
    console.log(`    ${JSON.stringify({ n, hand, middleFromSelect: mid })}`);
    check(
      `${n}: the middle button is no worse a pan than the Hand tool`,
      mid.median <= Math.max(hand.median * 2, 20),
      `hand ${hand.median}ms median, middle ${mid.median}ms median`
    );
    if (mid.median > 17 || hand.median > 17) {
      console.log(`    NOTE ${n}: panning is over 16.7ms per frame on this run (hand ${hand.median}, middle ${mid.median}). ` +
        `That is the render pass, not the pan path: MINDMAP_PLAN 13a-open.`);
    }
    await page.click('#wb-tool-group button[data-tool="select"]');
    await page.waitForTimeout(250);

    // And one drag per direction, each asking only: did the board go the way
    // the hand went?
    for (const [name, dx, dy] of [["right", 240, 0], ["left", -240, 0], ["down", 0, 200], ["up", 0, -200]]) {
      const before = await page.evaluate(() => {
        const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
        return { x: t.x, y: t.y, k: t.k };
      });
      await page.mouse.move(canvas.x, canvas.y);
      await page.mouse.down({ button: "middle" });
      for (let i = 1; i <= 12; i++) {
        await page.mouse.move(canvas.x + (dx * i) / 12, canvas.y + (dy * i) / 12);
        await page.waitForTimeout(10);
      }
      await page.mouse.up({ button: "middle" });
      await page.waitForTimeout(150);
      const after = await page.evaluate(() => {
        const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
        return { x: t.x, y: t.y, k: t.k };
      });
      const movedX = r1(after.x - before.x), movedY = r1(after.y - before.y);
      // Within a quarter of the travel: the gesture is real, so a few pixels
      // of rounding and one dropped move are expected; a sign flip or a
      // stationary board is not.
      const okX = Math.abs(movedX - dx) <= Math.max(30, Math.abs(dx) / 4);
      const okY = Math.abs(movedY - dy) <= Math.max(30, Math.abs(dy) / 4);
      check(
        `${n}: a middle drag ${name} moves the board ${name}`,
        okX && okY,
        `hand ${dx},${dy} board ${movedX},${movedY} (k ${r1(after.k)})`
      );
    }
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
