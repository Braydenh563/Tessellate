// The 22-10 bug doc: a drag on the board highlighted page text (claimed fixed
// in 0.6.1). A marquee over cards and text boxes, a drag that runs off the
// board over the top bar, a move and a resize: the page selection stays empty.
//   BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1025-dragselect.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => {
    const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Drag ${Date.now()}` }) });
    const e = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "A note with words to highlight by accident" }) });
    await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: e.id, board_id: b.id, x: 300, y: 250 }) });
    return b.id;
  });
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  await page.evaluate(async () => { await wbCreateObject("text", { content: "Words in a text box here" }, 650, 260, 200, 80, 2); wbScheduleRender(); });
  await page.waitForTimeout(600);
  const r = await page.evaluate(() => { const b = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; });
  const sel = () => page.evaluate(() => window.getSelection().toString());
  const drag = async (x0, y0, x1, y1) => {
    await page.evaluate(() => window.getSelection().removeAllRanges());
    await page.mouse.move(x0, y0);
    await page.mouse.down();
    await page.mouse.move(x1, y1, { steps: 15 });
    const mid = await sel();
    await page.mouse.up();
    return mid + "|" + (await sel());
  };
  ok("a marquee over a card and a text box selects no text", (await drag(r.x + 60, r.y + 60, r.x + 1000, r.y + 500)) === "|");
  ok("a marquee that runs over the top bar selects no text", (await drag(r.x + 900, r.y + 500, r.x + 100, 5)) === "|");
  ok("a marquee off the left side selects no text", (await drag(r.x + 600, r.y + 500, 2, r.y + 100)) === "|");
  const card = await page.evaluate(() => { const c = document.querySelector(".node-card").getBoundingClientRect(); return { x: c.x + c.width / 2, y: c.y + 12 }; });
  ok("moving a card across text selects no text", (await drag(card.x, card.y, card.x + 400, card.y + 60)) === "|");
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
