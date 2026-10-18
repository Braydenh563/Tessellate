// UX audit 1018 items 3, 11: a new empty map shows one empty state; the
// boards header count agrees with the list. BASE=http://127.0.0.1:8809
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await openBoardsTab(page);
  await page.waitForTimeout(800);
  const boards = await page.evaluate(() => {
    const t = (s) => (document.querySelector(s)?.innerText || "").replace(/\s+/g, " ").trim();
    return { side: t("#wb-sidebar").slice(0, 400) };
  });
  console.log("boards", JSON.stringify(boards));
  await page.evaluate(async () => {
    const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `m ${Date.now()}`, type: "map" }) });
    await openWhiteboardBoard(board.id);
  });
  await waitForBoardOpen(page, 0);
  await page.waitForTimeout(800);
  console.log("map", JSON.stringify(await page.evaluate(() => {
    const v = (id) => { const e = document.getElementById(id); if (!e || e.hidden || !e.offsetParent) return null; const r = e.getBoundingClientRect(); return Math.round(r.width) + "x" + Math.round(r.height); };
    return { templates: v("wb-map-templates"), empty: v("wb-map-empty") };
  })));
  await browser.close();
})();
