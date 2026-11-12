// **Every layout a map offers, laid out and measured for overlap**
// (MINDMAP_PLAN.md §13e; §13.4: "tree-left and both-sides are missing, and
// both-sides is Coggle's signature").
//
// The gate §13e set: each layout laid out and measured for overlap at 12 and
// 200 topics. Overlap is the one thing a layout can get wrong that a
// screenshot cannot be trusted about: two boxes that share a pixel are a map
// nobody can read, and at 200 topics there is no way to see it by eye.
//
// It also asks the two questions a *new* layout raises that an existing one
// does not: does the choice survive the round trip through the server (a
// layout the API refuses is a picker that lies), and does the branch bar move
// to the edge the parent is actually on (a bar on the far side from the
// branch it belongs to points at nothing, which is why the downward case
// exists).
//
//   BASE=http://127.0.0.1:8794 SCRATCH=/tmp/mm-mapux2 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/maplayouts.js
const { boot } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 1440, height: 900 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 1440, height: h || 900 };
})();
const SIZES = (process.env.SIZES || "12,200").split(",").map(Number);
const LAYOUTS = ["tree-right", "tree-left", "tree-both", "tree-down", "radial", "logic-right", "timeline", "fishbone", "tree-table"];

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}
const show = (o) => console.log("    " + JSON.stringify(o));

// A balanced outline of exactly `n` topics, breadth-first with a branching
// factor of 4. Written as a tree and printed depth-first, because the import
// route reads indentation: a generator that walked the *lines* instead put 36
// of 40 topics under one branch, which is a map nobody makes and a split
// nothing can balance.
function outline(n, name) {
  const root = { kids: [] };
  const queue = [root];
  for (let i = 1; i < n; i += 1) {
    const parent = queue[0];
    const node = { kids: [] };
    parent.kids.push(node);
    queue.push(node);
    if (parent.kids.length === 4) queue.shift();
  }
  const lines = [`# ${name}`, "- Trunk"];
  let made = 0;
  const walk = (node, depth) => {
    for (const kid of node.kids) {
      made += 1;
      lines.push(`${"  ".repeat(depth)}- Topic ${made}`);
      walk(kid, depth + 1);
    }
  };
  walk(root, 1);
  return lines.join("\n");
}

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });

  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await page.waitForTimeout(500);

  // The picker offers what the plan promised.
  const options = await page.evaluate(() =>
    [...document.querySelectorAll("#wb-map-layout option")].map((o) => o.value));
  show({ options });
  check("the picker offers both of the layouts section 13.4 found missing",
    options.includes("tree-left") && options.includes("tree-both"),
    options.join(", "));

  for (const n of SIZES) {
    const board = await page.evaluate(
      async ([content, name]) => apiJson("/whiteboard/boards/import", {
        method: "POST",
        body: JSON.stringify({ format: "markdown", content, name }),
      }), [outline(n, `Layouts ${n}`), `Layouts ${n}`]);
    await page.evaluate(async ([id, want]) => {
      await openWhiteboardBoard(id);
      const deadline = performance.now() + 30000;
      while (performance.now() < deadline) {
        if (document.querySelectorAll("#wb-html-layer .wb-map-node").length >= want) break;
        await new Promise((r) => setTimeout(r, 8));
      }
    }, [board.id, n]);
    await page.waitForTimeout(600);

    for (const layout of LAYOUTS) {
      const read = await page.evaluate(async (want) => {
        // The board's own coordinates, not the screen's: a layout is right or
        // wrong whatever the camera is doing, and at 200 topics most of the
        // map is off screen.
        const index = wbMapIndex();
        const positions = wbMapTidyPositions(index, want);
        const boxes = [];
        for (const [id, pos] of positions) {
          const node = index.byId.get(id);
          const size = wbMapNodeSize(node);
          boxes.push({ id, x: pos.x, y: pos.y, w: size.w, h: size.h });
        }
        let worst = 0;
        let pairs = 0;
        // A 1px tolerance: two boxes that share an edge are laid out, not
        // overlapping, and the tidy's own arithmetic rounds.
        for (let i = 0; i < boxes.length; i++) {
          for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i], b = boxes[j];
            const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
            const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
            if (ox > 1 && oy > 1) { pairs += 1; worst = Math.max(worst, Math.round(ox * oy)); }
          }
        }
        const xs = boxes.map((b) => b.x);
        const trunk = positions.get(index.roots[0].id);
        const leftOfTrunk = boxes.filter((b) => b.x + b.w / 2 < trunk.x).length;
        const rightOfTrunk = boxes.filter((b) => b.x + b.w / 2 > trunk.x + 200).length;
        return {
          laid: boxes.length, pairs, worst,
          span: Math.round(Math.max(...xs) - Math.min(...xs)),
          leftOfTrunk, rightOfTrunk,
        };
      }, layout);
      show({ n, layout, ...read });
      check(`${layout} lays ${n} topics out with nothing overlapping`,
        read.laid >= n && read.pairs === 0,
        `${read.laid} boxes, ${read.pairs} overlapping pairs, worst ${read.worst} board units`);
      if (layout === "tree-both") {
        // Both sides, and within the heaviest single branch of each other:
        // that is the best a split that keeps the branches in order can do,
        // and it is what tells an even map from one that fell to one side.
        const gap = Math.abs(read.leftOfTrunk - read.rightOfTrunk);
        check(`${layout} puts branches on both sides of the trunk at ${n}`,
          read.leftOfTrunk > 0 && read.rightOfTrunk > 0 && gap <= Math.ceil(n / 3),
          `${read.leftOfTrunk} left, ${read.rightOfTrunk} right, gap ${gap}`);
      }
      //: MINDMAP_PLAN 15 row 6: the timeline runs right of its centre, the
      //: fishbone's bones run left of its head.
      if (layout === "timeline") {
        check(`${layout} runs right of the centre at ${n}`, read.leftOfTrunk === 0 && read.rightOfTrunk > 0,
          `${read.leftOfTrunk} left, ${read.rightOfTrunk} right`);
      }
      if (layout === "fishbone") {
        check(`${layout} lays its bones left of the head at ${n}`, read.leftOfTrunk >= n - 1 && read.rightOfTrunk === 0,
          `${read.leftOfTrunk} left, ${read.rightOfTrunk} right`);
      }
      if (layout === "tree-left") {
        check(`${layout} grows away from the trunk to the left at ${n}`,
          read.leftOfTrunk >= n - 1 && read.rightOfTrunk === 0,
          `${read.leftOfTrunk} left, ${read.rightOfTrunk} right`);
      }
    }
  }

  // The choice survives the server, and the bar moves to the edge the parent
  // is on. Driven through the picker, which is the route a person takes.
  for (const layout of ["tree-left", "tree-both", "logic-right", "timeline", "fishbone", "tree-table"]) {
    await page.selectOption("#wb-map-layout", layout);
    await page.waitForTimeout(1800);
    const after = await page.evaluate(async (want) => {
      const listed = await apiJson("/whiteboard/boards");
      const stored = listed.find((b) => b.id === window.currentBoardId)?.layout;
      const index = wbMapIndex();
      const mirrored = [...document.querySelectorAll(".wb-map-node.wb-map-node-mirrored")].length;
      // A branch's topic, not the trunk: the centre topic has no parent to face, so
// its bar is the same both sides (L354/L364: the first match was the centre).
      const rootIds = new Set(index.roots.map((r) => String(r.id)));
      const sample = [...document.querySelectorAll(".wb-map-node.wb-map-node-mirrored")].find((e) => !rootIds.has(e.dataset.id));
      const cs = sample ? getComputedStyle(sample) : null;
      return {
        stored, want, mirrored, topics: index.nodes.length,
        right: cs ? cs.borderRightWidth : null,
        left: cs ? cs.borderLeftWidth : null,
      };
    }, layout);
    show(after);
    check(`${layout} survives the round trip through the server`, after.stored === layout,
      `stored ${after.stored}`);
    if (!["tree-left", "tree-both"].includes(layout)) {
      const drawn = await page.evaluate(() => [...document.querySelectorAll("#wb-zoom-group .wb-map-edges .wb-map-edge")].map((e) => e.getAttribute("d") || "").filter((d) => /^M/.test(d)).length);
      check(`${layout} draws a line to every topic but the centre`, drawn >= after.topics - 1, `${drawn} lines, ${after.topics} topics`);
      if (layout === "fishbone") {
        // L358: no rib runs behind a cause box (a drawn line sampled in board units).
        const behind = await page.evaluate(() => {
          const boxes = wbMapIndex().nodes.map((n) => ({ id: n.id, x: n.x, y: n.y, ...wbMapNodeSize(n) }));
          let hits = 0;
          const rootIds = new Set(wbMapIndex().roots.map((r) => r.id));
          for (const path of document.querySelectorAll(".wb-map-edges path.wb-map-edge")) {
            if (!rootIds.has(Number(path.dataset.parent))) continue; // ribs only; cause-to-cause lines are L-mindmap-12
            const len = path.getTotalLength();
            const ends = [Number(path.dataset.child), Number(path.dataset.parent)];
            for (let i = 0; i <= 60; i++) {
              const pt = path.getPointAtLength((len * i) / 60);
              if (boxes.some((b) => !ends.includes(b.id) && pt.x > b.x + 2 && pt.x < b.x + b.w - 2 && pt.y > b.y + 2 && pt.y < b.y + b.h - 2)) { hits += 1; break; }
            }
          }
          return hits;
        });
        check("fishbone ribs run behind no cause box", behind === 0, `${behind} lines cross another topic's box`);
      }
      if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/layout-${layout}.png` });
      continue;
    }
    check(`${layout} carries the branch bar on the edge the parent is on`,
      after.mirrored > 0 && parseFloat(after.right) > parseFloat(after.left),
      `${after.mirrored} mirrored topics, right ${after.right} against left ${after.left}`);
  }

  const ok = results.filter((r) => r.ok).length;
  console.log(`\n${ok}/${results.length} checks passed`);
  await browser.close();
  process.exit(ok === results.length ? 0 : 1);
})();
