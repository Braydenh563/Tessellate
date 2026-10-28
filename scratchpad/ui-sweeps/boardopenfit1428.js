// INBOX 1428, the owner: "I clicked on the sequence diagram board from the
// timeline and it didnt fit the content to my screen at all" (the diagram's
// corner at the top left, the rest off screen). Opens board P, pans it so a
// corner of board Q's content would sit in view, then opens Q as the timeline
// does (openWhiteboardBoard) and counts Q's objects inside the canvas.
//   BASE=http://127.0.0.1:8799 SCRATCH=/tmp/x node scratchpad/ui-sweeps/boardopenfit1428.js
const { boot } = require("./lib.js");
let failures = 0;
const check = (label, ok, detail) => { if (!ok) failures += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`); };
(async () => {
  for (const [w, h] of [[1440, 900], [800, 700]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    await page.evaluate(() => document.querySelector('[data-tab="library"]')?.click());
    await page.waitForTimeout(500);
    await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]')?.click());
    await page.waitForTimeout(800);
    const ids = await page.evaluate(async () => {
      const mk = async (name, spots) => {
        const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name, type: "board" }) });
        for (const [x, y] of spots) await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: b.id, kind: "text", x, y, width: 180, height: 90, data: { content: "t" } }) });
        return b.id;
      };
      return { p: await mk("P" + Date.now(), [[0, 0]]), q: await mk("Q" + Date.now(), [[0, 0], [600, 0], [1200, 0], [0, 900], [600, 900], [1200, 900], [1800, 1500]]) };
    });
    await page.evaluate((id) => openWhiteboardBoard(id), ids.p);
    await page.waitForTimeout(1500);
    // The sequence diagram's case: a camera at 0.52 whose view holds only Q's top-left corner.
    await page.evaluate(() => d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity.translate(-40, -20).scale(0.52)));
    await page.waitForTimeout(300);
    await page.evaluate((id) => openWhiteboardBoard(id), ids.q);
    await page.waitForTimeout(2000);
    const m = await page.evaluate(() => {
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      const rects = [...document.querySelectorAll("#whiteboard-container .wb-object")].map((e) => e.getBoundingClientRect()).filter((r) => r.width);
      const inside = rects.filter((r) => r.left >= c.left && r.right <= c.right && r.top >= c.top && r.bottom <= c.bottom).length;
      return { n: rects.length, inside, k: +d3.zoomTransform(document.getElementById("whiteboard-container")).k.toFixed(3) };
    });
    console.log(w + "x" + h, JSON.stringify(m));
    check(`${w}x${h}: every object of the opened board is inside the canvas`, m.n >= 7 && m.inside === m.n, `${m.inside}/${m.n}`);
    await browser.close();
  }
  process.exit(failures ? 1 : 0);
})();
