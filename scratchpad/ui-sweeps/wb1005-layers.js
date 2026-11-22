// The Layers tab (WHITEBOARD_PLAN decision 27; INBOX 557b): a hidden item is
// absent from the board, the PNG and SVG export, search and the Tab walk; a
// restack writes z; every row is named; Undo brings a hidden item back.
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1005-layers.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard();
  const ids = await page.evaluate(async (bid) => {
    const box = async (x, words) => (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
      kind: "text", data: { content: words }, board_id: bid, x, y: 0, z: 1, width: 160, height: 80,
    }) })).id;
    const a = await box(0, "Alpha words");
    const b = await box(60, "Beta words");
    const s = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: "M 0 200 L 100 200 L 100 260 L 0 260 Z", shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 5, board_id: bid,
    }) })).id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbOpenSidebar("layers");
    return { a, b, s };
  }, board.id);
  await page.waitForTimeout(600);
  const rows = await page.evaluate(() => [...document.querySelectorAll("#wb-layers-tree [role='treeitem']")].map((r) => [r.dataset.key, r.getAttribute("aria-label"), r.getAttribute("aria-level")]));
  check("every item is a named tree row", rows.length === 3 && rows.every((r) => r[1] && r[2] === "2"), rows);
  // Decision 43: cards and drawings stack in one list, so the sketch made at z 5 is first, then Beta, then Alpha.
  check("front first: sketch (z 5), then Beta (made last), then Alpha", rows[0][0] === `sketch:${ids.s}` && rows[1][0] === `object:${ids.b}` && rows[2][0] === `object:${ids.a}`, rows.map((r) => r[0]));

  // Hide Alpha from the keyboard.
  await page.focus(`#wb-layers-tree [data-key="object:${ids.a}"]`);
  await page.keyboard.press("h");
  await page.waitForTimeout(900);
  const hidden = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const { svg } = wbBuildExportSvg("whole");
    wbOpenBoardSearch();
    wbBoardSearchRun("Alpha");
    //: "1 of 2" when it finds something, "No matches" when it ran and found
    //: nothing; anything else (an empty count) means the search never ran.
    const said = document.getElementById("wb-search-count")?.textContent || "";
    const found = /^\d/.test(said) ? 1 : said === "No matches" ? 0 : `search did not run: "${said}"`;
    wbCloseBoardSearch();
    return {
      drawn: el ? getComputedStyle(el).display !== "none" : false,
      inExport: svg.includes("Alpha"),
      found,
      walk: wbSelectableItems().some(([k, i]) => k === "object" && i.id === id),
      row: document.querySelector(`#wb-layers-tree [data-key="object:${id}"]`)?.getAttribute("aria-label"),
    };
  }, ids.a);
  check("a hidden item is drawn nowhere", !hidden.drawn, hidden);
  check("and is in no export", !hidden.inExport, hidden);
  check("and search does not find it", hidden.found === 0, hidden);
  check("and the Tab walk and Select all pass it by", !hidden.walk, hidden);
  check("its row says hidden", /hidden/.test(hidden.row || ""), hidden.row);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(800);
  const back = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    return el && getComputedStyle(el).display !== "none";
  }, ids.a);
  check("Undo shows it again", back);

  // Restack: Alpha in front of Beta with Alt+Up.
  await page.evaluate(() => wbRenderLayers());
  await page.focus(`#wb-layers-tree [data-key="object:${ids.a}"]`);
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(900);
  const order = await page.evaluate(([a, b]) => {
    const za = wbFindItem("object", a).z, zb = wbFindItem("object", b).z;
    // The z-5 sketch stays on top (decision 43), so "in front" is the first object row.
    const first = document.querySelector("#wb-layers-tree [role='treeitem'][data-key^='object:']")?.dataset.key;
    return { za, zb, first, focus: document.activeElement?.dataset?.key };
  }, [ids.a, ids.b]);
  check("Alt+Up puts Alpha in front, z written", order.za > order.zb && order.first === `object:${ids.a}`, order);
  check("the focus stays on the moved row", order.focus === `object:${ids.a}`, order);

  // Lock from the row; Enter on a locked row says so rather than selecting.
  await page.keyboard.press("l");
  await page.waitForTimeout(800);
  const locked = await page.evaluate((a) => wbIsLocked("object", wbFindItem("object", a)), ids.a);
  check("L locks it", locked);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  check("Enter on a locked row says it is locked", /locked/.test(await page.textContent("#wb-announcer")));
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
