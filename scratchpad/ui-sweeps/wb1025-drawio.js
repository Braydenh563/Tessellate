// draw.io gaps built 10-25: Ctrl+Shift+Arrow resizes the selection (draw.io's
// key), and Flip left to right / top to bottom as Arrange commands (menu,
// right-click, palette) with Shift+H / Shift+V.
//   BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1025-drawio.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Drawio ${Date.now()}` }) })).id);
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.left, y: r.top }; });
  const tid = await page.evaluate(async () => { const o = await wbCreateObject("text", { content: "box" }, 200, 200, 120, 60, 2); wbScheduleRender(); return o.id; });
  await page.waitForTimeout(400);
  await page.evaluate((id) => { wbSelectExactly([["object", wbState.objects.find((o) => o.id === id)]]); document.getElementById("whiteboard-container").focus(); }, tid);
  const size = () => page.evaluate((id) => { const o = wbState.objects.find((x) => x.id === id); return { w: o.width, h: o.height, x: o.x, y: o.y }; }, tid);
  const s0 = await size();
  await page.keyboard.press("Control+Shift+ArrowRight");
  await page.waitForTimeout(400);
  await page.keyboard.press("Control+Shift+ArrowDown");
  await page.waitForTimeout(400);
  const s1 = await size();
  ok("Ctrl+Shift+Right and Down grow the box by a step, its corner stays", s1.w === s0.w + 10 && s1.h === s0.h + 10 && s1.x === s0.x && s1.y === s0.y, `${JSON.stringify(s0)} -> ${JSON.stringify(s1)}`);
  await page.keyboard.press("Control+Shift+ArrowLeft");
  await page.waitForTimeout(400);
  const s2 = await size();
  ok("Ctrl+Shift+Left shrinks it", s2.w === s0.w, JSON.stringify(s2));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(500);
  const s3 = await size();
  ok("one Undo per step", s3.w === s0.w + 10, JSON.stringify(s3));

  // A triangle, flipped top to bottom by Shift+V and the Arrange menu.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("g");
  await page.mouse.move(box.x + 600, box.y + 200);
  await page.mouse.down();
  await page.mouse.move(box.x + 760, box.y + 320, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(700);
  await page.keyboard.press("v");
  const sk = await page.evaluate(() => { const s = wbState.sketches[wbState.sketches.length - 1]; wbSelectedItem = { kind: "sketch", id: s.id }; wbMultiSelection.clear(); wbApplySelectionHighlight(); wbUpdateContextBar(); document.getElementById("whiteboard-container").focus(); return { id: s.id, d: JSON.parse(s.data).d }; });
  const apex = (d) => { const n = d.match(/-?[\d.]+/g).map(Number); const ys = n.filter((_, i) => i % 2); return { top: Math.min(...ys), first: n[1] }; };
  await page.keyboard.press("Shift+V");
  await page.waitForTimeout(600);
  const d1 = await page.evaluate((id) => JSON.parse(wbState.sketches.find((s) => s.id === id).data).d, sk.id);
  ok("Shift+V flips a shape top to bottom", d1 !== sk.d && Math.abs(apex(d1).first - apex(sk.d).first) > 50, `${sk.d.slice(0, 40)} -> ${d1.slice(0, 40)}`);
  const menu = await page.evaluate(() => {
    const names = WB_COMMANDS.filter((c) => /^flip-/.test(c.id)).map((c) => c.id);
    const rows = [...document.querySelectorAll('#wb-arrange-menu [data-wb-cmd^="flip-"]')].map((r) => r.dataset.wbCmd);
    const pal = wbPaletteCommands().map((c) => c.label.replace(/^ph:\S+ /, "")).filter((l) => /^Flip/.test(l));
    return { names, rows, pal };
  });
  ok("Flip commands in the table, the Arrange menu and the palette", menu.names.length === 2 && menu.rows.length === 2 && menu.pal.length === 2, JSON.stringify(menu));
  await page.evaluate(() => wbRunCommand("flip-v"));
  await page.waitForTimeout(600);
  const d2 = await page.evaluate((id) => JSON.parse(wbState.sketches.find((s) => s.id === id).data).d, sk.id);
  ok("the menu's Flip top to bottom flips it back", Math.abs(apex(d2).first - apex(sk.d).first) < 1, d2.slice(0, 40));
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
