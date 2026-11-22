// L-whiteboard-21: Select all and the Tab walk take a board's connectors.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbselectlinks.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({ title: "wbselectlinks" });
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const ids = await ev(async (bid) => {
    const shape = async (x, y) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: bid, x: 0, y: 0, z: 2,
      data: JSON.stringify({ d: `M ${x} ${y} L ${x + 160} ${y} L ${x + 160} ${y + 90} L ${x} ${y + 90} Z`, shape: "rect", color: "#335599", width: 2 }) }) })).id;
    const a = await shape(200, 200), b = await shape(600, 200);
    const link = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: bid, x: 0, y: 0, z: 3,
      data: JSON.stringify({ type: "link-straight", sourceKind: "sketch", sourceId: a, targetKind: "sketch", targetId: b, color: "#445566", width: 3, label: "flows" }) }) })).id;
    await fetchWhiteboardState(); renderWhiteboardNow(); return { a, b, link };
  }, board.id);
  await page.waitForTimeout(800);
  await ev(() => { clearWbSelection(); document.getElementById("whiteboard-container").focus(); });
  await page.keyboard.press("Control+a"); await page.waitForTimeout(400);
  let r = await ev((l) => ({ n: wbMultiSelection.size, link: wbMultiSelection.has(wbMultiKey("sketch", l)) }), ids.link);
  check("Ctrl+A selects the connector too", r.n === 3 && r.link, r);
  await ev(() => { clearWbSelection(); document.getElementById("whiteboard-container").focus(); });
  const said = [];
  for (let i = 0; i < 3; i++) { await page.keyboard.press("Tab"); await page.waitForTimeout(350); said.push(await ev(() => document.getElementById("wb-announcer")?.textContent || "")); }
  check("Tab reaches the connector and names it", said.some((t) => /Connector: flows, \d of 3/.test(t)), said);
  summary(); await browser.close();
})();
