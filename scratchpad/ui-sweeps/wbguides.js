// Smart guides on drawn shapes (wb-phase2 step 4). Three rectangles: two
// 40 apart in a row, the third dragged by the pointer to land 3 past the
// row's rhythm and 4 below its top: it snaps to the gap and the top edge,
// the guides show while it moves (a spacing mark and an edge line, read off
// the DOM), and they go when it lands. Alt held: no snap at all.
//   BASE=http://127.0.0.1:8795 W=390 H=844 THEME=dark PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbguides.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
  const { browser, page, errors, board } = await openBoard({ viewport: { width: W, height: H } });
  const rect = (x, y) => `M ${x} ${y} L ${x + 100} ${y} L ${x + 100} ${y + 60} L ${x} ${y + 60} Z`;
  const ids = await page.evaluate(async ([bid, r]) => {
    const post = async (d) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify({ d, shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const ids = [];
    for (const d of r) ids.push(await post(d));
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit();
    return ids;
  }, [board.id, [rect(0, 0), rect(140, 0), rect(300, 120)]]);
  await page.waitForTimeout(700);
  await page.evaluate(() => wbSelectToolRef?.("select"));

  const screenOf = (x, y) => page.evaluate(([x, y]) => {
    const svg = document.getElementById("wb-svg-layer");
    const pt = svg.createSVGPoint();
    pt.x = x; pt.y = y;
    const s = pt.matrixTransform(document.getElementById("wb-zoom-group").getScreenCTM());
    return { x: s.x, y: s.y, k: d3.zoomTransform(document.getElementById("whiteboard-container")).k };
  }, [x, y]);
  const boxOf = (id) => page.evaluate((id) => wbPathBBox(JSON.parse(wbFindItem("sketch", id).data).d), id);

  // Drag the third shape by its middle so it would land at (283, 4).
  const drag = async (alt) => {
    const from = await screenOf(350, 150);
    const to = await screenOf(350 - 17, 150 - 116);
    await page.mouse.move(from.x, from.y);
    if (alt) await page.keyboard.down("Alt");
    await page.mouse.down();
    const steps = 12;
    let seen = { spacing: 0, edge: 0 };
    for (let i = 1; i <= steps; i += 1) {
      await page.mouse.move(from.x + ((to.x - from.x) * i) / steps, from.y + ((to.y - from.y) * i) / steps);
      if (i === steps) {
        await page.waitForTimeout(60);
        seen = await page.evaluate(() => ({
          spacing: document.querySelectorAll(".wb-align-guides .wb-align-guide-spacing").length,
          edge: document.querySelectorAll(".wb-align-guides .wb-align-guide-edge").length,
        }));
      }
    }
    await page.mouse.up();
    if (alt) await page.keyboard.up("Alt");
    await page.waitForTimeout(900);
    return seen;
  };

  const seen = await drag(false);
  const box = await boxOf(ids[2]);
  check("while dragging, a spacing mark pair and an edge line show", seen.spacing === 2 && seen.edge >= 1, seen);
  check("the shape lands on the row's spacing and top edge", Math.abs(box.minX - 280) < 0.6 && Math.abs(box.minY - 0) < 0.6, box);
  const gone = await page.evaluate(() => document.querySelectorAll(".wb-align-guides line").length);
  check("the guides go when it lands", gone === 0, gone);

  // Put it back and drag with Alt: no snap.
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(900);
  const back = await boxOf(ids[2]);
  check("Undo puts it back", Math.abs(back.minX - 300) < 0.6 && Math.abs(back.minY - 120) < 0.6, back);
  const altSeen = await drag(true);
  const free = await boxOf(ids[2]);
  check("with Alt held nothing snaps and no guide shows", altSeen.spacing === 0 && altSeen.edge === 0 && Math.abs(free.minX - 283) < 1.5 && Math.abs(free.minY - 4) < 1.5, { altSeen, free });

  check("no console errors", errors.length === 0, errors.slice(0, 5));
  const ok = summary();
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
