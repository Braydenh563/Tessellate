// Dogfood 2026-10-25 item 12: Tab on a mind map keeps the new topic on screen.
//   W=1280 BASE=http://127.0.0.1:8814 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdog1-map.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const W = Number(process.env.W || 1280), H = Number(process.env.H || 800);
  const { browser, page } = await openBoard({ viewport: { width: W, height: H }, type: "map", title: "dog1 map" });
  await page.evaluate(async (id) => {
    await window.apiJson(`/whiteboard/boards/${id}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", text: "Centre", x: 0, y: 0 }) });
    await window.openWhiteboardBoard(id);
  }, (await page.evaluate(() => window.currentBoardId)));
  await page.waitForTimeout(2000);
  // Select the root and chain Tab (child) + type, 7 deep: a tree-right map walks off the right edge.
  await page.evaluate(() => { const r = wbState.objects.find((o) => o.parent_id == null); selectWbItem("object", r.id); });
  const rects = [];
  for (let i = 0; i < 7; i++) {
    await page.keyboard.press("Tab");
    await page.waitForTimeout(900);
    await page.keyboard.type("topic " + i);
    await page.waitForTimeout(150);
    const r = await page.evaluate(() => {
      const obj = document.activeElement?.closest?.(".wb-object") || document.querySelector(".wb-object.selected");
      const b = obj?.getBoundingClientRect();
      const free = wbVisibleCanvasRect();
      return b ? { l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top), b: Math.round(b.bottom), free: [Math.round(free.left), Math.round(free.top), Math.round(free.right), Math.round(free.bottom)] } : null;
    });
    rects.push(r);
  }
  console.log(JSON.stringify(rects));
  const inside = rects.every((r) => r && r.l >= 0 && r.r <= W && r.t >= 0 && r.b <= H);
  check("every new topic's rect is inside the window", inside, rects);
  const free = rects.every((r) => r && r.l >= r.free[0] - 1 && r.r <= r.free[2] + 1 && r.t >= r.free[1] - 1 && r.b <= r.free[3] + 1);
  check("and inside the canvas the chrome leaves free", free, rects);
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
