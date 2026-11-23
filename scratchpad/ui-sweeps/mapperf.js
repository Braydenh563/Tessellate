// **Is the mind map slow?** (INBOX 305, the owner: "the mindmap is slow.")
//
// This is the one claim in that report that had to be measured before
// anything was designed, because if it is true it outranks the other five:
// no amount of control-layout work rescues a surface that stutters. So this
// probe takes five numbers at three map sizes and asserts nothing about
// taste.
//
// **The five numbers, and why each one.**
//
//  1. `open` — from the call that opens the board to the frame on which all
//     N nodes are in the DOM *and* the browser has painted twice. Two rAFs,
//     not one: the first fires after the render pass has written the layer,
//     the second only once that write has actually been composited, so a
//     single rAF would report the time to queue the paint rather than the
//     time to see it.
//  2. `pan` — the frame deltas during a real hand-tool drag across the
//     canvas, driven with `page.mouse` rather than dispatched events, so the
//     hit-testing, the pointer capture and the transform write are all on
//     the measured path.
//  3. `drag` — the same, on one node, which is the other gesture a person
//     makes constantly and which re-renders rather than re-transforms.
//  4. `zoom` — the frame deltas during a real ctrl-wheel zoom in and back
//     out again, driven with `page.mouse.wheel`. The third thing the owner
//     named, and the one that had never been measured: see the block that
//     takes it for why it is the one of the three that cannot be composited.
//  5. `layout` — `wbMapTidyPositions`, the pure position computation, timed
//     on its own with no network and no render, plus `wbMapIndex` (which
//     every map action calls first) and `renderWhiteboard` (which every map
//     action calls last). Splitting the three is the whole point: a tidy
//     that feels slow is one of them, and the fix is different for each.
//
// **The map is built through the real route.** `/whiteboard/boards/import`
// with a Markdown outline is a route a person actually has (the Board menu's
// own import), it produces ordinary `topic` objects with real `parent_id`
// edges, and it is the only way to get to 500 nodes without measuring 500
// round trips of `wbMapAddChild` instead of the thing being asked about.
//
// Frame deltas are collected in the page by a rAF loop installed before the
// gesture and stopped after it, so what is reported is what the compositor
// actually did, not what a timer around the gesture would suggest.
//
// **It is not a fast sweep**, and it cannot be: building and opening a
// 500-node map is the thing being measured. Budget about three minutes for
// the default three sizes. `SIZES=50` cuts it to one size when what is
// wanted is a regression check rather than the shape of the curve.
//
//   BASE=http://127.0.0.1:8804 SCRATCH=/tmp/mm-mapread \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapperf.js
const { boot, openBoardsTab } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 1440, height: 900 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 1440, height: h || 900 };
})();

const SIZES = (process.env.SIZES || "50,200,500").split(",").map(Number);

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

// A balanced outline of exactly `n` topics: one trunk, then breadth-first
// with a branching factor of 5, which is the shape of a map somebody made on
// purpose rather than a chain or a star.
function outline(n) {
  const lines = [`# Perf ${n}`];
  const depth = [0];
  lines.push(`- Trunk`);
  let made = 1;
  let parent = 0;
  let childrenOfParent = 0;
  while (made < n) {
    if (childrenOfParent === 5) {
      parent += 1;
      childrenOfParent = 0;
      continue;
    }
    const d = depth[parent] + 1;
    depth.push(d);
    lines.push(`${"  ".repeat(d)}- Topic ${made}`);
    made += 1;
    childrenOfParent += 1;
  }
  return lines.join("\n");
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};
const r1 = (x) => Math.round(x * 10) / 10;

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });

  // Get to the whiteboard view once; every board below opens inside it.
  // Wait for the lazy board bundle rather than sleeping for it: on a loaded
  // runner a fixed 1.2s left `initWhiteboard` undefined (2026-11-14).
  await openBoardsTab(page);
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await page.waitForTimeout(500);

  // The rAF frame recorder, installed once and driven per gesture.
  await page.evaluate(() => {
    window.__frames = [];
    window.__rafOn = false;
    window.__startFrames = () => {
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
    };
    window.__stopFrames = () => {
      window.__rafOn = false;
      // The first delta is the gap from installing the loop to its first
      // callback, which is not a frame the gesture produced.
      return window.__frames.slice(1);
    };
  });

  const table = [];

  for (const n of SIZES) {
    // 1. Build the map through the import route.
    const board = await page.evaluate(
      async ([content, name]) =>
        apiJson("/whiteboard/boards/import", {
          method: "POST",
          body: JSON.stringify({ format: "markdown", content, name }),
        }),
      [outline(n), `Perf ${n}`]
    );
    check(`${n}: import made a map`, board && board.id, `object_count ${board && board.object_count}`);

    // 2. Open it, and time to the painted frame.
    const open = await page.evaluate(async ([id, want]) => {
      const t0 = performance.now();
      await openWhiteboardBoard(id);
      // Poll for the nodes rather than trusting the promise: the open path
      // fetches state and queues a render, so the promise resolving is not
      // the nodes being there.
      const deadline = t0 + 30000;
      while (performance.now() < deadline) {
        const drawn = document.querySelectorAll("#wb-html-layer .wb-map-node").length;
        if (drawn >= want) break;
        await new Promise((r) => setTimeout(r, 8));
      }
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return {
        ms: performance.now() - t0,
        drawn: document.querySelectorAll("#wb-html-layer .wb-map-node").length,
        objects: (wbState.objects || []).length,
      };
    }, [board.id, n]);
    check(`${n}: opened and painted`, open.drawn >= n, `${r1(open.ms)}ms, ${open.drawn} nodes drawn of ${open.objects}`);

    // 3. The costs inside one map action, each on its own.
    //
    // **A render is timed against a change, never against nothing.** The
    // render is differential now (MINDMAP_PLAN.md 13a): it repaints the
    // objects whose drawn state has changed and leaves the rest alone. Five
    // renders in a row of an unchanged board would therefore measure the
    // skip and report it as the render, which is the "a screenshot is not a
    // measurement" trap in another costume. So three numbers are taken:
    //
    //   `render`    one topic has moved, which is what a drag, a rename, an
    //               add, a collapse or an undo actually leaves behind. This
    //               is the number a person feels.
    //   `renderAll` every topic has moved: the ceiling, and the number
    //               directly comparable with the single figure this sweep
    //               reported before the render was differential.
    //   `idle`      nothing changed at all. What is left is the work a
    //               render does regardless of the board's state, so it is
    //               the floor the two above are measured from.
    const cost = await page.evaluate(() => {
      const times = (fn, runs, prep) => {
        const out = [];
        for (let i = 0; i < runs; i++) {
          if (prep) prep(i);
          const t = performance.now();
          fn();
          out.push(performance.now() - t);
        }
        return out;
      };
      const index = times(() => wbMapIndex(), 7);
      const idx = wbMapIndex();
      const layout = times(() => wbMapTidyPositions(idx, wbMapLayout()), 7);
      const objects = wbState.objects || [];
      // Back and forth by the same 4px, so the board is where it started
      // (within one nudge) when the pan and drag below are measured on it.
      const nudge = (o, i) => { o.x += i % 2 ? 4 : -4; };
      const idle = times(() => renderWhiteboardNow(), 5);
      const render = times(() => renderWhiteboardNow(), 5, (i) => objects[0] && nudge(objects[0], i));
      const renderAll = times(() => renderWhiteboardNow(), 5, (i) => { for (const o of objects) nudge(o, i); });
      return { index, layout, render, renderAll, idle };
    });

    // 4. A hand-tool pan across the canvas, with frames recorded.
    const canvas = await page.evaluate(() => {
      const c = document.getElementById("whiteboard-container");
      const b = c.getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2, w: b.width, h: b.height };
    });
    await page.click('#wb-tool-group button[data-tool="pan"]');
    await page.waitForTimeout(300);
    await page.evaluate(() => window.__startFrames());
    await page.mouse.move(canvas.x - 250, canvas.y);
    await page.mouse.down();
    for (let i = 1; i <= 30; i++) {
      await page.mouse.move(canvas.x - 250 + i * 12, canvas.y + Math.sin(i / 4) * 40);
      await page.waitForTimeout(8);
    }
    await page.mouse.up();
    const panFrames = await page.evaluate(() => window.__stopFrames());
    await page.click('#wb-tool-group button[data-tool="select"]');
    await page.waitForTimeout(300);

    // 4b. A wheel zoom, in and back out again, with frames recorded.
    //
    // **The third thing the owner named** ("laggy to pan around, move
    // objects, and zoom"), and the one no sweep in this repository had ever
    // measured. Ctrl is held because that is what this board's own zoom
    // filter asks for: a plain wheel pans here, the way it does in Miro and
    // Figma, so a wheel without it would measure the pan a second time.
    //
    // Zoom is the one of the three that cannot be composited: a pan moves a
    // promoted layer and can reuse its raster, a zoom changes its scale and
    // the text under it has to be drawn again at the new size. So the frame
    // this reports is a real repaint of every visible topic, and it is
    // reported rather than asserted on for that reason.
    // **Twelve units a notch, not a hundred and twenty.** d3-zoom multiplies a
    // wheel delta by ten when ctrl is held, because that is how a browser
    // reports a trackpad pinch, so a full mouse notch here is 5.3x per step:
    // two of them and the board is pinned against `scaleExtent`, and a
    // gesture that spends half its frames clamped measures the clamp. Twelve
    // is 1.18x a step, which is the pinch a hand actually makes. (That the
    // full notch is 5.3x is a real edge of this control and is written up in
    // MINDMAP_PLAN 13.1; it is not what this number is about.)
    //
    // Out first and then back in: zoomed out is the expensive direction,
    // because more of the map is on screen to re-raster.
    const before = await page.evaluate(() => {
      const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
      return { k: t.k, x: t.x, y: t.y };
    });
    await page.mouse.move(canvas.x, canvas.y);
    await page.keyboard.down("Control");
    await page.evaluate(() => window.__startFrames());
    for (let i = 0; i < 6; i++) {
      await page.mouse.wheel(0, 12);
      await page.waitForTimeout(16);
    }
    for (let i = 0; i < 6; i++) {
      await page.mouse.wheel(0, -12);
      await page.waitForTimeout(16);
    }
    const zoomFrames = await page.evaluate(() => window.__stopFrames());
    await page.keyboard.up("Control");
    const zoomAfter = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
    // A gesture that changed nothing measured nothing: without this the two
    // numbers below would read as a fast zoom rather than as no zoom at all.
    check(`${n}: the wheel zoomed the board`, zoomFrames.length > 0 && Math.abs(zoomAfter - before.k) < before.k,
      `k ${r1(before.k)} to ${r1(zoomAfter)}, ${zoomFrames.length} frames`);
    // Put the view back exactly where the zoom found it: the drag below is
    // measured next, and a drag at 0.3x is a different measurement from the
    // one this sweep has always reported.
    await page.evaluate(([k, x, y]) => {
      d3.select(document.getElementById("whiteboard-container"))
        .call(wbZoom.transform, d3.zoomIdentity.translate(x, y).scale(k));
    }, [before.k, before.x, before.y]);
    await page.waitForTimeout(200);

    // 5. A node drag, with frames recorded. The node picked is one that is
    // actually on screen: a 500-node map runs off the canvas, and dragging
    // at a point where `elementFromPoint` returns the shell measures nothing.
    const node = await page.evaluate(() => {
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      for (const el of document.querySelectorAll("#wb-html-layer .wb-map-node")) {
        const b = el.getBoundingClientRect();
        if (b.width === 0) continue;
        const cx = b.left + b.width / 2;
        const cy = b.top + b.height / 2;
        if (cx > c.left + 60 && cx < c.right - 60 && cy > c.top + 60 && cy < c.bottom - 60) {
          return { x: cx, y: cy };
        }
      }
      return null;
    });
    let dragFrames = [];
    if (node) {
      await page.evaluate(() => window.__startFrames());
      await page.mouse.move(node.x, node.y);
      await page.mouse.down();
      for (let i = 1; i <= 25; i++) {
        await page.mouse.move(node.x + i * 6, node.y + i * 3);
        await page.waitForTimeout(8);
      }
      await page.mouse.up();
      dragFrames = await page.evaluate(() => window.__stopFrames());
      await page.waitForTimeout(500);
    }
    check(`${n}: a node was on screen to drag`, Boolean(node), node ? "" : "none inside the canvas");

    // 6. The same gesture on the biggest branch on screen, before and after a
    // few hundred link sketches are put on the board.
    //
    // **Why this pair exists.** Picking a topic up captures every topic under
    // it (`wbCaptureBulkMoveOrigin`), and each member used to ask
    // `wbLinkedSketchesFor` for its own link lines, which walked and
    // `JSON.parse`d every sketch on the board. That is members x sketches
    // with a parse in the middle of it, and it was invisible to this sweep
    // for one reason: a map built by the import route above has no link
    // sketches at all, so the inner count was zero however big the branch
    // got. The links below are the missing half of the fixture, and the drag
    // is taken twice so the difference between the two numbers is the cost of
    // the links rather than the cost of the branch.
    // The topic on screen with the most under it, found fresh each time: a
    // leaf captures one member and would measure nothing this is about, and
    // the previous drag left whichever topic it grabbed 150px from where it
    // was, so a second gesture at the first one's coordinates grabs canvas.
    const findBranch = () => page.evaluate(() => {
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
    // One branch drag, with the frames, and with proof that the board moved:
    // a gesture that grabbed nothing reports a quiet 16.7ms and would read as
    // a fast drag rather than as no drag at all.
    const branchDrag = async () => {
      //: **Put the view back on the root first.** Measured on this probe: a
      //: 500-topic map opens centred on its root at 1x and shows *two*
      //: topics, so the only branch there is to grab is the root's, and the
      //: drag before this one carried it 150px away. Re-centring is the same
      //: call `wbFrameMapOnOpen` makes, so both drags start from the view the
      //: open leaves and measure the same gesture.
      await page.evaluate(() => {
        const root = wbMapIndex().roots[0];
        if (root) wbCenterOn(wbItemBBox("object", root), { animate: false, minScale: 1 });
      });
      await page.waitForTimeout(200);
      const pt = await findBranch();
      if (!pt) return { frames: [], moved: 0, size: 0 };
      const at = (id) => page.evaluate((i) => {
        const o = (wbState.objects || []).find((x) => x.id === i);
        return o ? { x: o.x, y: o.y } : null;
      }, id);
      const before = await at(pt.id);
      await page.evaluate(() => window.__startFrames());
      await page.mouse.move(pt.x, pt.y);
      await page.mouse.down();
      for (let i = 1; i <= 25; i++) {
        await page.mouse.move(pt.x + i * 6, pt.y + i * 3);
        await page.waitForTimeout(8);
      }
      await page.mouse.up();
      const frames = await page.evaluate(() => window.__stopFrames());
      await page.waitForTimeout(400);
      const after = await at(pt.id);
      const moved = before && after ? Math.round(Math.hypot(after.x - before.x, after.y - before.y)) : 0;
      return { frames, moved, size: pt.size };
    };
    const plain = await branchDrag();
    const links = process.env.LINKS === undefined ? 300 : Number(process.env.LINKS);
    const madeLinks = await page.evaluate(async (count) => {
      const topics = (wbState.objects || []).filter((o) => o.kind === "topic");
      if (topics.length < 4) return 0;
      for (let i = 0; i < count; i++) {
        const a = topics[i % topics.length];
        const b = topics[(i * 7 + 3) % topics.length];
        if (a.id === b.id) continue;
        // The shape `wbFinishLink` posts for a link dragged between two map
        // topics, which is what makes these real to `wbLinkedSketchesFor`.
        const row = await apiJson("/whiteboard/sketches", {
          method: "POST",
          body: JSON.stringify({
            data: JSON.stringify({
              type: "link-curved",
              sourceId: a.id,
              targetId: b.id,
              sourceKind: "object",
              targetKind: "object",
              color: "#888888",
            }),
            x: 0, y: 0, z: 1,
            board_id: window.currentBoardId,
          }),
        });
        wbState.sketches.push(row);
      }
      renderWhiteboardNow();
      return (wbState.sketches || []).length;
    }, links);
    check(`${n}: the board carries link sketches for the second drag`, madeLinks >= links,
      `${madeLinks} sketches`);
    const linked = await branchDrag();
    check(`${n}: both branch drags moved the branch they grabbed`,
      plain.moved > 50 && linked.moved > 50,
      `${plain.moved} board units without links, ${linked.moved} with, branches of ${plain.size} and ${linked.size}`);

    const row = {
      n,
      openMs: r1(open.ms),
      drawn: open.drawn,
      indexMs: r1(median(cost.index)),
      layoutMs: r1(median(cost.layout)),
      renderMs: r1(median(cost.render)),
      renderAllMs: r1(median(cost.renderAll)),
      renderIdleMs: r1(median(cost.idle)),
      panMedian: r1(median(panFrames)),
      panWorst: r1(Math.max(0, ...panFrames)),
      panFrames: panFrames.length,
      dragMedian: r1(median(dragFrames)),
      dragWorst: r1(Math.max(0, ...dragFrames)),
      dragFrames: dragFrames.length,
      // Where the worst frame falls, as a fraction of the gesture. This is
      // the number that decides the fix: a stall at the very start is the
      // pick-up, one at the very end is the drop and its re-render, and one
      // in the middle would be the move handler itself. Reported rather
      // than reasoned about, because the three have different repairs.
      dragWorstAt: dragFrames.length
        ? Math.round((dragFrames.indexOf(Math.max(...dragFrames)) / (dragFrames.length - 1)) * 100) / 100
        : null,
      panWorstAt: panFrames.length
        ? Math.round((panFrames.indexOf(Math.max(...panFrames)) / (panFrames.length - 1)) * 100) / 100
        : null,
      branchSize: plain.size,
      branchWorst: r1(Math.max(0, ...plain.frames)),
      branchLinkedWorst: r1(Math.max(0, ...linked.frames)),
      linkSketches: madeLinks,
      zoomMedian: r1(median(zoomFrames)),
      zoomWorst: r1(Math.max(0, ...zoomFrames)),
      zoomFrames: zoomFrames.length,
    };
    table.push(row);
    console.log("    " + JSON.stringify(row));

    // 60fps is a 16.7ms frame. A median above it during a gesture is the
    // report being true; below it, at this size, it is not.
    check(`${n}: pan holds 60fps at the median`, row.panMedian <= 17, `${row.panMedian}ms median, ${row.panWorst}ms worst`);
    // MINDMAP_PLAN 13a-view's gate: the worst frame of the pan and of the
    // zoom, not only the median. Both were 116 to 166ms at 500 topics before
    // it, and both were one thing: a press and a release that restyled every
    // element on the board (the container's own `:active` cursor, inherited
    // by eleven thousand elements, and a `[class*="card"] *` rule in Settings
    // that made any class change restyle a whole subtree).
    check(`${n}: the worst pan frame is under 50ms`, row.panWorst < 50, `${row.panWorst}ms`);
    check(`${n}: the worst zoom frame is under 50ms`, row.zoomWorst < 50, `${row.zoomWorst}ms`);
    check(`${n}: drag holds 60fps at the median`, !node || row.dragMedian <= 17, `${row.dragMedian}ms median, ${row.dragWorst}ms worst`);
    // The two gate figures MINDMAP_PLAN.md 13a set for this surface, asserted
    // at the size they were set at rather than described in a table nobody
    // runs. Both were measured at 500 topics; the smaller maps are strictly
    // easier, so the same budget holds for them.
    check(`${n}: a render after a change is under 200ms`, row.renderAllMs <= 200,
      `${row.renderMs}ms for one topic, ${row.renderAllMs}ms for every topic, ${row.renderIdleMs}ms idle`);
    check(`${n}: open to painted is under 1s`, row.openMs <= 1000, `${row.openMs}ms`);
    // Not a budget, a ratio: what is being watched here is the link sketches
    // turning a branch pick-up into something quadratic again. Measured at
    // 500 topics with 300 links, on the head this fixture was written
    // against and on the one after it: **66.7ms without the links and 950.0
    // with**, then 66.7 and 116.7. Twice the worst frame of the same gesture
    // on the same branch sits well above this machine's run-to-run spread
    // (one frame either way at 16.7ms) and an order of magnitude below what
    // the scan cost.
    check(`${n}: links do not double the worst frame of a branch drag`,
      !plain.size || row.branchLinkedWorst <= Math.max(50, row.branchWorst * 2),
      `${row.branchWorst}ms without, ${row.branchLinkedWorst}ms with ${row.linkSketches} links, branch of ${row.branchSize}`);
  }

  console.log("\n  size | open ms | index ms | layout ms | render one/all/idle | pan med/worst | drag med/worst | zoom med/worst | branch worst plain/linked");
  for (const r of table) {
    console.log(
      `  ${String(r.n).padStart(4)} | ${String(r.openMs).padStart(7)} | ${String(r.indexMs).padStart(8)} | ` +
        `${String(r.layoutMs).padStart(9)} | ` +
        `${String(r.renderMs).padStart(6)}/${String(r.renderAllMs).padStart(6)}/${String(r.renderIdleMs).padEnd(5)} | ` +
        `${String(r.panMedian).padStart(5)}/${String(r.panWorst).padEnd(6)} | ${r.dragMedian}/${r.dragWorst}` +
        ` | ${r.zoomMedian}/${r.zoomWorst} | ${r.branchWorst}/${r.branchLinkedWorst}`
    );
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
