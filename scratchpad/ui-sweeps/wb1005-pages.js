// Pages and the hover lock (WHITEBOARD_PLAN decisions 22 and 28, INBOX
// 557a): the Pages tab lists the frames in presentation order, named rows;
// Alt+Down moves a page and the presentation follows, one undo step; a
// locked shape shows a lock under the pointer, the first press says how to
// unlock it, and right-click on it offers "Unlock this item".
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1005-pages.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 1440);

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  const ids = await page.evaluate(async (bid) => {
    const frame = async (x, y, title) => (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
      kind: "frame", data: { content: title }, board_id: bid, x, y, width: 240, height: 140, z: 0,
    }) })).id;
    const a = await frame(0, 0, "Intro");
    const b = await frame(320, 0, "Middle");
    const c = await frame(0, 260, "End");
    const shape = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: "M 700 400 L 860 400 L 860 500 L 700 500 Z", shape: "rect", color: "#335599", width: 2, fill: "#88aaee", locked: true }),
      x: 0, y: 0, z: 3, board_id: bid,
    }) })).id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit({ animate: false });
    wbOpenSidebar("pages");
    return { a, b, c, shape };
  }, board.id);
  await page.waitForTimeout(700);
  const rows = await page.evaluate(() => [...document.querySelectorAll("#wb-pages-list [role='treeitem']")].map((r) => r.getAttribute("aria-label")));
  check("three named pages in reading order", JSON.stringify(rows) === JSON.stringify(["Page 1: Intro", "Page 2: Middle", "Page 3: End"]), rows);
  await page.focus(`#wb-pages-list [data-id="${ids.a}"]`);
  await page.keyboard.press("Alt+ArrowDown");
  await page.waitForTimeout(900);
  const moved = await page.evaluate(() => ({
    rows: [...document.querySelectorAll("#wb-pages-list [role='treeitem']")].map((r) => r.getAttribute("aria-label")),
    steps: wbPresentSteps().map((s) => s.title()),
    focus: document.activeElement?.getAttribute("aria-label"),
    said: document.getElementById("wb-announcer")?.textContent,
  }));
  check("Alt+Down moves Intro to page 2", moved.rows[1] === "Page 2: Intro", moved.rows);
  check("the presentation follows", JSON.stringify(moved.steps) === JSON.stringify(["Middle", "Intro", "End"]), moved.steps);
  check("the focus stays on the moved page, and it is announced", moved.focus === "Page 2: Intro" && /page 2 of 3/.test(moved.said || ""), moved);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(900);
  const back = await page.evaluate(() => wbPresentSteps().map((s) => s.title()));
  check("one Undo puts the order back", JSON.stringify(back) === JSON.stringify(["Intro", "Middle", "End"]), back);

  // Hover lock.
  await page.evaluate(() => wbCloseSidebar());
  const centre = await page.evaluate((id) => {
    const el = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-path`);
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, ids.shape);
  const badge = await page.evaluate((id) => {
    const pin = document.querySelector("#wb-lock-marks .wb-lock-pin");
    return { shown: Boolean(pin) && pin.getBoundingClientRect().width >= 0, pe: pin ? getComputedStyle(pin).pointerEvents : null };
  }, ids.shape);
  check("a lock badge shows on a locked shape without hover", badge.shown && badge.pe === "none", badge);
  await page.mouse.move(centre.x, centre.y, { steps: 3 });
  await page.mouse.down();
  await page.mouse.up();
  await page.waitForTimeout(400);
  const toastText = await page.evaluate(() => [...document.querySelectorAll(".toast, .toast-message, [role='status']")].map((t) => t.textContent).join(" | "));
  check("the first press says how to unlock it", /Right-click to unlock/.test(toastText), toastText);
  await page.mouse.click(centre.x, centre.y, { button: "right" });
  await page.waitForTimeout(500);
  const menu = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role='menuitem'], .action-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim()));
  check("right-click on it offers to unlock this one first", /Unlock this item/.test(menu[0] || ""), menu);
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
