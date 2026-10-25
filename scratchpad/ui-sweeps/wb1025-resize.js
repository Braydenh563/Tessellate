// The 22-10 bug doc's board rows (OPEN.md): an emoji sticker's glyph follows
// its box during a resize, a shape's selection box and grips follow a resize
// live (not on release), and the "W x H" readout shows on a shape's resize
// as it does on a draw.
//
//   BASE=http://127.0.0.1:8791 SCRATCH=/tmp/x PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/wb1025-resize.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Resize sweep ${Date.now()}` }) })).id);
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  await page.keyboard.press("Escape");
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.left, y: r.top }; });

  // 1. An emoji sticker.
  const sid = await page.evaluate(async () => (await wbCreateObject("text", { content: "\u{1F634}", sticker: true }, 200, 200, 64, 64, 2)).id);
  await page.evaluate(() => wbScheduleRender());
  await page.waitForTimeout(400);
  const fontOf = () => page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const t = el.querySelector(".wb-text-content");
    return { font: parseFloat(getComputedStyle(t).fontSize), w: el.getBoundingClientRect().width, glyph: (() => { const r = document.createRange(); r.selectNodeContents(t); return r.getBoundingClientRect().height; })() };
  }, sid);
  await page.evaluate((id) => document.querySelector(`.wb-object[data-id="${id}"] .wb-text-content`).dispatchEvent(new MouseEvent("click", { bubbles: true })), sid);
  const se = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    el.classList.add("wb-selected");
    const r = el.querySelector('.wb-resize-handle[data-handle="se"]').getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, sid);
  const f0 = await fontOf();
  await page.mouse.move(se.x, se.y);
  await page.mouse.down();
  await page.mouse.move(se.x + 150, se.y + 150, { steps: 10 });
  await page.waitForTimeout(100);
  const fMid = await fontOf();
  const readMid = await page.evaluate(() => document.querySelector(".wb-size-readout text")?.textContent || "");
  await page.mouse.up();
  await page.waitForTimeout(800);
  const fEnd = await fontOf();
  ok("sticker glyph grows with its box during the drag", fMid.font > f0.font * 1.8, `before ${JSON.stringify(f0)} mid ${JSON.stringify(fMid)}`);
  ok("sticker glyph keeps its size after release", fEnd.font > f0.font * 1.8 && fEnd.glyph > f0.glyph * 1.8, JSON.stringify(fEnd));
  ok("a box's resize shows the size readout", /\d+ x \d+/.test(readMid), readMid);

  // 2. A drawn rectangle shape.
  await page.keyboard.press("Escape");
  await page.evaluate(() => { window.wbClearSelection?.(); document.getElementById("whiteboard-container").focus(); });
  await page.keyboard.press("r");
  await page.mouse.move(box.x + 600, box.y + 200);
  await page.mouse.down();
  await page.mouse.move(box.x + 760, box.y + 300, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(900);
  await page.keyboard.press("v");
  await page.mouse.click(box.x + 600, box.y + 250);
  await page.waitForTimeout(300);
  const h0 = await page.evaluate(() => {
    const r = document.querySelector('.wb-sketch-resize-handle[data-handle="se"]')?.getBoundingClientRect();
    return r ? { x: r.x + r.width / 2, y: r.y + r.height / 2 } : null;
  });
  ok("a drawn shape is selected with its grips", !!h0, JSON.stringify(h0) + " " + await page.evaluate(() => JSON.stringify({ tool: window.currentTool, n: wbState.sketches.length, sel: wbSelectedItem })));
  if (h0) {
    await page.mouse.move(h0.x, h0.y);
    await page.mouse.down();
    await page.mouse.move(h0.x + 120, h0.y + 90, { steps: 10 });
    await page.waitForTimeout(100);
    const mid = await page.evaluate(() => {
      const sel = document.querySelector(".wb-sketch-selection-box")?.getBoundingClientRect();
      const path = document.querySelector(".sketch-group .sketch-path")?.getBoundingClientRect();
      const se = document.querySelector('.wb-sketch-resize-handle[data-handle="se"]')?.getBoundingClientRect();
      const rot = document.querySelector(".wb-sketch-rotate-handle")?.getBoundingClientRect();
      return { selW: Math.round(sel.width), pathW: Math.round(path.width), selH: Math.round(sel.height), pathH: Math.round(path.height),
        seX: Math.round(se.x + se.width / 2), pathR: Math.round(path.right), rotX: Math.round(rot.x + rot.width / 2), pathMid: Math.round(path.x + path.width / 2),
        readout: document.querySelector(".wb-size-readout text")?.textContent || "" };
    });
    await page.mouse.up();
    await page.waitForTimeout(600);
    ok("shape: the selection box follows the resize live", Math.abs(mid.selW - mid.pathW) <= 8 && Math.abs(mid.selH - mid.pathH) <= 8, JSON.stringify(mid));
    ok("shape: the corner grip follows the pointer", Math.abs(mid.seX - mid.pathR) <= 6, `${mid.seX} vs ${mid.pathR}`);
    ok("shape: the rotate grip stays over the middle", Math.abs(mid.rotX - mid.pathMid) <= 4, `${mid.rotX} vs ${mid.pathMid}`);
    ok("shape: the size readout shows during the resize", /\d+ x \d+/.test(mid.readout), mid.readout);
    const after = await page.evaluate(() => document.querySelectorAll(".wb-size-readout").length);
    ok("shape: the readout goes on release", after === 0, String(after));
  }
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
