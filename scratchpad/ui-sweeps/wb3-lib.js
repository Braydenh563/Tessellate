// Shared setup for the wb3 sweeps: boot, open a fresh board, seed objects by API.
const { boot } = require("./lib.js");
async function openFresh(opts = {}, name = "wb3 " + Date.now()) {
  const env = await boot({ viewport: { width: 1440, height: 900 }, ...opts });
  const { page } = env;
  page.on("pageerror", (e) => console.log("pageerror", e.message));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {
    window.confirmDialog = async () => true;
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  const board = await page.evaluate(async (n) => apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: n, type: "board" }) }), name);
  await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
  await page.waitForTimeout(1000);
  env.board = board;
  env.open = async (id) => { await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, id); await page.waitForTimeout(900); };
  return env;
}
// Seed a mixed board; returns ids. Reloads state by reopening.
async function seedMixed(page, boardId) {
  const ids = await page.evaluate(async (bid) => {
    const post = (p, b) => apiJson(p, { method: "POST", body: JSON.stringify({ board_id: bid, ...b }) });
    const a = await post("/whiteboard/objects", { kind: "text", x: 100, y: 100, width: 200, height: 100, data: { content: "Sticky A", bg: "#fff4a3" } });
    const b = await post("/whiteboard/objects", { kind: "text", x: 400, y: 100, width: 200, height: 100, data: { content: "Sticky B" } });
    const f = await post("/whiteboard/objects", { kind: "frame", x: 60, y: 60, width: 600, height: 240, z: -1, data: { content: "Frame" } });
    const outside = await post("/whiteboard/objects", { kind: "text", x: 900, y: 100, width: 200, height: 100, data: { content: "Left behind" } });
    const sk = await post("/whiteboard/sketches", { x: 0, y: 0, data: JSON.stringify({ d: "M 120 400 L 220 440 L 320 400", color: "#e11", width: 3 }) });
    const link = await post("/whiteboard/sketches", { x: 0, y: 0, data: JSON.stringify({ type: "link-straight", color: "#333", width: 2, sourceId: a.id, sourceKind: "object", targetId: b.id, targetKind: "object" }) });
    const link2 = await post("/whiteboard/sketches", { x: 0, y: 0, data: JSON.stringify({ type: "link-straight", color: "#333", width: 2, sourceId: b.id, sourceKind: "object", targetId: outside.id, targetKind: "object" }) });
    return { a: a.id, b: b.id, f: f.id, outside: outside.id, sk: sk.id, link: link.id, link2: link2.id };
  }, boardId);
  return ids;
}
module.exports = { openFresh, seedMixed };
