// The default board writes a stored thumbnail: edit it, wait out the 3 s settle, read the boards list.
//   BASE=http://127.0.0.1:8951 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbthumb-default.js
const { openBoard, checker } = require("./wb1005-lib.js");

(async () => {
  const { check, summary } = checker();
  const { browser, page } = await openBoard({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async () => { await openWhiteboardBoard(null); });
  await page.waitForTimeout(1500);
  await page.evaluate(async () => {
    const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", x: 100, y: 100, width: 220, height: 120, z: 2, board_id: null, data: { content: "default board note", sticky: true, bg: "#ffe680" } }) });
    wbState.objects.push(o);
    wbScheduleRender();
  });
  await page.waitForTimeout(5500);
  const row = await page.evaluate(async () => (await apiJson("/whiteboard/boards")).find((b) => b.id === null));
  check("the default board has a current stored thumbnail", Boolean(row && row.thumb_v), row && row.thumb_v);
  const code = await page.evaluate(async (v) => (await fetch(`/media/board-thumb/0?v=${v}`)).status, row && row.thumb_v);
  check("it is served at /media/board-thumb/0", code === 200, code);
  const ok = summary();
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
