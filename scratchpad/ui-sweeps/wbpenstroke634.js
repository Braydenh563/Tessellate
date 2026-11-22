// L634: after the pen handlers moved to whiteboard-strokes.js, a pen stroke and a rectangle still save, a tool switch
// mid-stroke drops the live path, and no page error is thrown.
//   BASE=http://127.0.0.1:8873 node scratchpad/ui-sweeps/wbpenstroke634.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({ title: "wbpenstroke634" });
  const errs = []; page.on("pageerror", (e) => errs.push(e.message));
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const box = await page.locator("#whiteboard-container").boundingBox();
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  const count = () => ev(() => document.querySelectorAll("#whiteboard-container .sketch-group").length);
  const before = await count();
  await ev(() => wbSelectToolRef("draw"));
  await page.mouse.move(cx - 100, cy); await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(cx - 100 + i * 10, cy + i * 3);
  await page.mouse.up(); await page.waitForTimeout(800);
  const afterPen = await count();
  check("a pen stroke saves", afterPen === before + 1, `${before} to ${afterPen}`);
  await ev(() => wbSelectToolRef("rect"));
  await page.mouse.move(cx, cy); await page.mouse.down(); await page.mouse.move(cx + 80, cy + 60, { steps: 6 }); await page.mouse.up();
  await page.waitForTimeout(800);
  const afterRect = await count();
  check("a rectangle saves and the tool returns to select", afterRect === afterPen + 1 && (await ev(() => window.currentTool)) === "select", `${afterRect}, ${await ev(() => window.currentTool)}`);
  await ev(() => wbSelectToolRef("draw"));
  await page.mouse.move(cx - 50, cy + 100); await page.mouse.down(); await page.mouse.move(cx, cy + 120, { steps: 5 });
  await ev(() => wbSelectToolRef("select"));
  await page.mouse.up(); await page.waitForTimeout(500);
  const orphans = await ev(() => document.querySelectorAll("#wb-overlay-zoom-group > path").length);
  check("a tool switch mid-stroke drops the live path", orphans === 0 && (await count()) === afterRect, `orphans ${orphans}`);
  check("no page error", errs.length === 0, errs.join(" | "));
  summary(); await browser.close();
})();
