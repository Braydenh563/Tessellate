// The 22-10 bug doc: a frame stood upright (double-click its rotate grip)
// stands up what it holds too, in one Undo step.
//   BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1025-frameup.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Frame up ${Date.now()}` }) })).id);
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  const ids = await page.evaluate(async () => {
    const f = await wbCreateObject("frame", { content: "Frame 1" }, 100, 100, 400, 300, 0);
    const t = await wbCreateObject("text", { content: "inside" }, 200, 200, 120, 60, 2);
    wbScheduleRender();
    return { f: f.id, t: t.id };
  });
  await page.waitForTimeout(600);
  const grip = async () => page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    el.classList.add("wb-selected");
    const r = el.querySelector(".wb-rotate-handle").getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, cx: el.getBoundingClientRect().x + el.getBoundingClientRect().width / 2, cy: el.getBoundingClientRect().y + el.getBoundingClientRect().height / 2 };
  }, ids.f);
  let g = await grip();
  await page.mouse.move(g.x, g.y);
  await page.mouse.down();
  await page.mouse.move(g.cx + 300, g.cy - 10, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  const rot = () => page.evaluate((ids) => {
    const f = wbState.objects.find((o) => o.id === ids.f), t = wbState.objects.find((o) => o.id === ids.t);
    return { frame: Math.round(f.rotation || 0), inside: Math.round(t.rotation || 0), tx: t.x, ty: t.y };
  }, ids);
  const turned = await rot();
  ok("a drag of the frame's grip turns it and what it holds", turned.frame !== 0 && turned.inside === turned.frame, JSON.stringify(turned));
  g = await grip();
  await page.mouse.dblclick(g.x, g.y);
  await page.waitForTimeout(1000);
  const up = await rot();
  ok("double-click on the grip stands the frame and what it holds upright", up.frame === 0 && up.inside === 0 && Math.abs(up.tx - 200) <= 1 && Math.abs(up.ty - 200) <= 1, JSON.stringify(up));
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800);
  const back = await rot();
  ok("one Undo turns both back", back.frame === turned.frame && back.inside === turned.inside, JSON.stringify(back));
  await page.reload({ waitUntil: "domcontentloaded" });
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
