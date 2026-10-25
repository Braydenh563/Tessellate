// Dogfood 2026-10-25 item 6: an arrow drawn with the Arrow tool from one
// shape's edge to another binds to both and follows a moved shape.
//   BASE=http://127.0.0.1:8814 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdog1-arrow.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({});
  const ids = await page.evaluate(async (bid) => {
    const post = async (data) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const a = await post({ d: "M 100 100 h 120 v 60 h -120 Z", shape: "rect", color: "#335599", width: 2 });
    const b = await post({ d: "M 400 100 h 120 v 60 h -120 Z", shape: "rect", color: "#335599", width: 2 });
    await fetchWhiteboardState(); renderWhiteboardNow(); wbZoomToFit(); clearWbSelection();
    return { a, b };
  }, board.id);
  await page.waitForTimeout(700);
  const screenOf = (x, y) => page.evaluate(([x, y]) => {
    const svg = document.getElementById("wb-svg-layer");
    const pt = svg.createSVGPoint(); pt.x = x; pt.y = y;
    const s = pt.matrixTransform(document.getElementById("wb-zoom-group").getScreenCTM());
    return { x: s.x, y: s.y };
  }, [x, y]);
  await page.evaluate(() => wbSelectToolRef?.("arrow"));
  // From just outside A's right edge (3 board units) to just inside B's left edge.
  const from = await screenOf(223, 130), to = await screenOf(404, 130);
  const n0 = await page.evaluate(() => wbState.sketches.length);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move((from.x + to.x) / 2, from.y + 4, { steps: 5 });
  await page.mouse.move(to.x, to.y, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(900);
  const linkId = await page.evaluate((ids) => wbState.sketches.find((s) => ![ids.a, ids.b].includes(s.id))?.id, ids);
  const made = await page.evaluate((id) => { const s = wbState.sketches.find((k) => k.id === id); return s ? JSON.parse(s.data) : null; }, linkId);
  check("the arrow is a connector bound to both shapes", made && made.type === "link-straight" && made.sourceId === ids.a && made.targetId === ids.b && made.endCap === "arrow", made);
  // The shaft's far end in board units, read from the link's own drawn path.
  const tip = () => page.evaluate((id) => {
    const d = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-hitbox`).getAttribute("d");
    const m = d.match(/^M ([\d.-]+) ([\d.-]+) L ([\d.-]+) ([\d.-]+)/);
    return { sx: Math.round(Number(m[1])), ex: Math.round(Number(m[3])) };
  }, linkId);
  const before = await tip();
  // Move shape B 80 board units right through the app's own save path.
  await page.evaluate(async (id) => {
    const sk = wbState.sketches.find((k) => k.id === id);
    await wbSaveSketchProps(sk, { d: "M 480 100 h 120 v 60 h -120 Z" });
    renderWhiteboardNow();
  }, ids.b);
  await page.waitForTimeout(700);
  console.log(await page.evaluate(([l, b]) => JSON.stringify({ groups: [...document.querySelectorAll(".sketch-group")].map((g) => g.dataset.id), link: wbState.sketches.find((s) => s.id === l)?.data, b: wbState.sketches.find((s) => s.id === b)?.data }), [linkId, ids.b]));
  const after = await tip();
  console.log("arrow box before", JSON.stringify(before), "after", JSON.stringify(after));
  check("the arrow's far end followed the moved shape", after.ex >= before.ex + 70 && after.sx === before.sx, { before, after });
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
