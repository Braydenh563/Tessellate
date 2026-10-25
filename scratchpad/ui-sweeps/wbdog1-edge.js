// Dogfood 2026-10-25 edge-drag: a press near (not on) a connection point moves
// the shape; a press on the point still draws a connector.
//   BASE=http://127.0.0.1:8814 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdog1-edge.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({});
  const id = await page.evaluate(async (bid) => {
    const r = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify({ d: "M 100 100 h 160 v 80 h -160 Z", shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 1, board_id: bid }) });
    await fetchWhiteboardState(); renderWhiteboardNow(); wbZoomToFit(); clearWbSelection(); wbSelectToolRef?.("select");
    return r.id;
  }, board.id);
  await page.waitForTimeout(700);
  const screenOf = (x, y) => page.evaluate(([x, y]) => {
    const pt = document.getElementById("wb-svg-layer").createSVGPoint(); pt.x = x; pt.y = y;
    const s = pt.matrixTransform(document.getElementById("wb-zoom-group").getScreenCTM());
    return { x: s.x, y: s.y };
  }, [x, y]);
  const state = () => page.evaluate((id) => ({ n: wbState.sketches.length, minX: Math.round(wbItemBBox("sketch", wbFindItem("sketch", id)).minX) }), id);
  const k = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
  const topMid = await screenOf(180, 100);
  async function dragFrom(dx) {
    await page.mouse.move(topMid.x + dx, topMid.y + 40);
    await page.mouse.move(topMid.x + dx, topMid.y, { steps: 3 });
    await page.waitForTimeout(150);
    await page.mouse.down();
    await page.mouse.move(topMid.x + dx + 60, topMid.y + 60, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(900);
  }
  const s0 = await state();
  await dragFrom(8);
  const s1 = await state();
  console.log("zoom", k, "before", JSON.stringify(s0), "after press 8px from the top-middle point", JSON.stringify(s1));
  check("a press 8px from a point moves the shape and makes no connector", s1.n === s0.n && s1.minX !== s0.minX, { s0, s1 });
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(800);
  const s2 = await state();
  const topMid2 = await screenOf(180, 100);
  topMid.x = topMid2.x; topMid.y = topMid2.y;
  await dragFrom(0);
  const s3 = await state();
  check("a press on the point still draws a connector", s3.n === s2.n + 1 && s3.minX === s2.minX, { s2, s3 });
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
