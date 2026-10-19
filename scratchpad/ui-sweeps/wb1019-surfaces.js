// W/H link and grouped library elements (INBOX 1307, 1308).
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1019-surfaces.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const id = await page.evaluate(async (bid) => {
    const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: "M 100 100 L 300 100 L 300 200 L 100 200 Z", shape: "rect", color: "#335599", width: 2, fill: "#ffcc00" }),
      x: 0, y: 0, z: 1, board_id: bid }) });
    await fetchWhiteboardState(); renderWhiteboardNow(); selectWbItem("sketch", s.id); return s.id;
  }, board.id);
  await page.waitForTimeout(400);
  await page.keyboard.press("Control+Shift+P");
  await page.waitForTimeout(400);
  await page.click("#wb-format-tab-arrange");
  await page.waitForTimeout(300);
  const read = () => page.evaluate(() => ({ w: +document.getElementById("wb-fmt-w").value, h: +document.getElementById("wb-fmt-h").value, p: document.getElementById("wb-fmt-link").getAttribute("aria-pressed") }));
  const set = async (f, v) => { await page.fill(`#wb-fmt-${f}`, String(v)); await page.press(`#wb-fmt-${f}`, "Tab"); await page.waitForTimeout(700); };
  const a = await read();
  await set("w", 300);
  const unlinked = await read();
  check("unlinked: width alone changes", unlinked.w === 300 && unlinked.h === a.h && unlinked.p === "false", { a, unlinked });
  await page.click("#wb-fmt-link"); await page.waitForTimeout(200);
  await set("w", 150);
  const l = await read();
  check("linked: height follows at the ratio (300x100 -> 150x50)", l.w === 150 && l.h === 50 && l.p === "true", l);
  await set("h", 100);
  const l2 = await read();
  check("linked: height edit scales width (100 -> 300)", l2.h === 100 && l2.w === 300, l2);
  const box = await page.evaluate(() => { const r = document.getElementById("wb-fmt-link").getBoundingClientRect(); const w = document.getElementById("wb-fmt-w").getBoundingClientRect(); const h = document.getElementById("wb-fmt-h").getBoundingClientRect(); return { l: r.left, w: w.right, h: h.left, bw: r.width, bh: r.height }; });
  check("chain sits between W and H, 24px+ target", box.l >= box.w - 1 && box.l + box.bw <= box.h + 1 && box.bh >= 24, box);
  // library group
  const grp = await page.evaluate(async (bid) => {
    const r = await apiJson(`/whiteboard/boards/${bid}/place`, { method: "POST", body: JSON.stringify({ builtin: "uml/class", x: 600, y: 400 }) });
    return r.sketches.map((s) => s.group_id);
  }, board.id);
  check("a placed class is one group", grp.length === 4 && new Set(grp).size === 1 && grp[0], grp);
  // select similar: two yellow rects, one blue
  const sim = await page.evaluate(async (bid) => {
    const mk = async (fill, x) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: `M ${x} 600 L ${x + 80} 600 L ${x + 80} 660 L ${x} 660 Z`, shape: "rect", color: "#335599", width: 2, fill }), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const a = await mk("#ffcc00", 0), b = await mk("#ffcc00", 120), c = await mk("#00aa55", 240);
    await fetchWhiteboardState(); renderWhiteboardNow(); selectWbItem("sketch", a);
    wbSelectSimilar();
    return { keys: [...wbMultiSelection], a, b, c };
  }, board.id);
  check("select similar takes the yellow shapes (the board has three), not the green one", sim.keys.length === 3 && sim.keys.includes(`sketch:${sim.b}`) && !sim.keys.includes(`sketch:${sim.c}`), sim);
  const lane = await page.evaluate(async (bid) => (await apiJson(`/whiteboard/boards/${bid}/place`, { method: "POST", body: JSON.stringify({ builtin: "flowchart/swimlane-h3", x: 0, y: 0 }) })).sketches.length, board.id);
  check("a swimlane places (5 parts + labels as one group)", lane >= 5, lane);
  await browser.close();
  summary();
})();
