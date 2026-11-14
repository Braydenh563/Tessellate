// L-whiteboard-35: one eraser swipe over three strokes is one Undo step, and
// that Undo brings all three back.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbl35.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board, errors } = await openBoard({ title: "l35" });
  await page.evaluate(async (b) => {
    for (const x of [100, 220, 340]) {
      await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, data: JSON.stringify({ type: "path", d: `M${x} 100 L${x} 300`, color: "#e11d48", width: 8 }) }) });
    }
    await openWhiteboardBoard(b);
  }, board.id);
  await page.waitForTimeout(1500);
  const before = await page.evaluate(() => ({ n: wbState.sketches.length, undo: wbUndoStack.length }));
  await page.evaluate(() => wbSelectToolRef?.("eraser"));
  const pts = await page.evaluate(() => [...document.querySelectorAll(".sketch-group")].map((g) => { const r = g.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }));
  check("three strokes drawn", pts.length === 3, pts);
  pts.sort((p, q) => p.x - q.x);
  await page.mouse.move(pts[0].x - 30, pts[0].y); await page.mouse.down();
  for (let i = 0; i <= 30; i++) await page.mouse.move(pts[0].x - 30 + ((pts[2].x - pts[0].x + 60) * i) / 30, pts[0].y);
  await page.mouse.up();
  await page.waitForTimeout(1200);
  const after = await page.evaluate(() => ({ n: wbState.sketches.length, undo: wbUndoStack.length }));
  check("the swipe erased all three", after.n === before.n - 3, { before, after });
  check("the swipe is one Undo step", after.undo === before.undo + 1, { before, after });
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(1500);
  const back = await page.evaluate(() => wbState.sketches.length);
  check("one Undo brings all three back", back === before.n, { back, before });
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
