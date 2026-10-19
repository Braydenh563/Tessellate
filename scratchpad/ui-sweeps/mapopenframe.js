// Owner, 2026-10-19: "when I go onto the mindmap it doesnt focus me on the
// content and puts me down and to the right where nothing is."
//
// Opens a board, pans it, opens a 10-topic map from the Library, goes back to
// the board, and measures the topics' screen boxes against the canvas rect.
// Before the fix a map too big to fit opened with its root in the middle of
// the canvas (content at x 330..850 of a 10..790 canvas at 800x700); each
// board also inherited the other's camera. Now: the content starts at the
// canvas's top-left, and a board returns to the view it was left in.
//
//   BASE=http://127.0.0.1:8847 SCRATCH=/tmp/mm PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mapopenframe.js
const { boot } = require("./lib.js");

let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

(async () => {
  for (const [w, h] of [[1440, 900], [800, 700]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    await page.evaluate(() => document.querySelector('[data-tab="library"]')?.click());
    await page.waitForTimeout(500);
    await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]')?.click());
    await page.waitForTimeout(800);
    const ids = await page.evaluate(async () => {
      const map = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", name: "M" + Date.now(), content: "# Root\n- A\n  - A1\n  - A2\n- B\n  - B1\n  - B2\n- C\n  - C1\n  - C2" }) });
      const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "B" + Date.now(), type: "board" }) });
      for (const [x, y] of [[100, 100], [900, 600], [1500, 200]]) await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: b.id, kind: "text", x, y, width: 180, height: 90, data: { content: "t" } }) });
      return { map: map.id, board: b.id };
    });
    const view = () => page.evaluate(() => { const t = d3.zoomTransform(document.getElementById("whiteboard-container")); return { x: Math.round(t.x), y: Math.round(t.y), k: +t.k.toFixed(3) }; });
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    await page.waitForTimeout(1500);
    await page.evaluate(() => d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity.translate(-300, 120).scale(1.3)));
    await page.waitForTimeout(300);
    await page.evaluate((id) => openWhiteboardBoard(id), ids.map);
    await page.waitForTimeout(2500);
    const m = await page.evaluate(() => {
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      const rects = [...document.querySelectorAll(".wb-map-node")].map((e) => e.getBoundingClientRect()).filter((r) => r.width);
      const root = rects.reduce((a, r) => (r.top < a.top ? r : a), rects[0]);
      const onScreen = rects.filter((r) => r.right > c.left && r.left < c.right && r.bottom > c.top && r.top < c.bottom).length;
      return { n: rects.length, onScreen, rootInside: root.left >= c.left && root.right <= c.right && root.top >= c.top && root.bottom <= c.bottom,
        leftGap: Math.round(Math.min(...rects.map((r) => r.left)) - c.left), topGap: Math.round(Math.min(...rects.map((r) => r.top)) - c.top),
        cw: Math.round(c.width), ch: Math.round(c.height) };
    });
    console.log(w + "x" + h, JSON.stringify(m));
    check(`${w}x${h}: the root is inside the canvas`, m.rootInside);
    check(`${w}x${h}: content starts within 200px of the canvas top-left`, m.leftGap < 200 && m.topGap < 200, `gap ${m.leftGap},${m.topGap}`);
    check(`${w}x${h}: the root and its first branches are on screen`, m.onScreen >= 3, `${m.onScreen}/${m.n}`);
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    await page.waitForTimeout(1500);
    const back = await view();
    check(`${w}x${h}: the board returns to the view it was left in`, back.k === 1.3 && back.x === -300 && back.y === 120, JSON.stringify(back));
    await browser.close();
  }
  process.exit(failures ? 1 : 0);
})();
