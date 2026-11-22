// WHITEBOARD_PLAN decision 15: lock.
//
// A sticky, a rectangle and a note card on a board, inside a frame. The
// sticky is locked from its right-click menu, the rectangle with Ctrl+Shift+L,
// the card the same way; each then lets the pointer through (a press on it
// reaches the board, a drag from it moves nothing), Select all, a marquee and
// the eraser pass them by, the frame's drag leaves them where they are, and
// the card's lock survives a fresh read of the board. Ctrl+Z takes the last
// lock back. The board's own right-click menu names how many are locked and
// unlocks them; Ctrl+Shift+L with nothing selected does the same.
//
//   BASE=http://127.0.0.1:8800 SCRATCH=/tmp/x THEME=light VW=1440 VH=900 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wblock.js
const { boot, newBoard: libNewBoard } = require("./lib.js");

let pass = 0;
let fail = 0;
function ok(label, good, detail) {
  if (good) pass += 1;
  else fail += 1;
  console.log(`${good ? "OK  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
}
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
//: At phone width everything is laid out smaller, on a board zoomed to half.
const S = VW < 600 ? 0.55 : 1;
//: And lower, clear of the board's own bar, which is taller on a phone.
const OY = VW < 600 ? 150 : 0;

(async () => {
  const phone = VW < 600;
  const { browser, page } = await boot({
    viewport: { width: VW, height: VH },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await libNewBoard(page, `Lock sweep ${Date.now()}`, 'board');
  await page.keyboard.press("Escape");
  const box = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
  const kStart = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);

  // Built from state, at board coordinates the screen shows: a frame, and in
  // it a sticky, a rectangle and a note card.
  const ids = await page.evaluate(async ([S, OY]) => {
    if (S < 1) d3.select("#whiteboard-container").call(wbZoom.transform, d3.zoomIdentity.scale(0.5));
    const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
    const at = (sx, sy) => [t.invertX(sx), t.invertY(sy)];
    const [fx, fy] = at(60 * S, 140 * S + OY);
    const frame = await wbCreateObject("frame", { content: "Area" }, fx, fy, (520 * S) / t.k, (300 * S) / t.k, -1);
    const [sx, sy] = at(100 * S, 200 * S + OY);
    const sticky = await wbCreateObject("text", { content: "Pinned", bg: "#fff4a3" }, sx, sy, (140 * S) / t.k, (100 * S) / t.k);
    const note = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "Lock sweep card" }) });
    const [cx, cy] = at(300 * S, 200 * S + OY);
    const card = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: note.id, board_id: window.currentBoardId, x: cx, y: cy, z: 1 }) });
    if (typeof allEntries !== "undefined" && !allEntries.some((e) => e.id === note.id)) allEntries.push(note);
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return { frame: frame.id, sticky: sticky.id, card: card.id };
  }, [S, OY]);
  // The rectangle, drawn with the tool.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("r");
  if (process.env.DEBUG) console.log("tool", await page.evaluate(() => [window.currentTool, document.activeElement?.id, wbState.objects.length, wbState.nodes.length]));
  await page.mouse.move(box.x + 120 * S, box.y + 340 * S + OY);
  await page.mouse.down();
  await page.mouse.move(box.x + 240 * S, box.y + 410 * S + OY, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  await page.keyboard.press("Escape");
  await page.keyboard.press("v");
  ids.rect = await page.evaluate(() => wbState.sketches[wbState.sketches.length - 1].id);

  const centre = (sel) =>
    page.evaluate((sel) => {
      const r = document.querySelector(sel).getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }, sel);
  const stickySel = `.wb-object[data-id="${ids.sticky}"]`;
  const cardSel = `.node-card[data-id="${ids.card}"]`;
  const rectSel = `.sketch-group[data-id="${ids.rect}"]`;
  const locked = () =>
    page.evaluate((ids) => ({
      sticky: wbIsLocked("object", wbState.objects.find((o) => o.id === ids.sticky)),
      rect: wbIsLocked("sketch", wbState.sketches.find((s) => s.id === ids.rect)),
      card: wbIsLocked("node", wbState.nodes.find((n) => n.id === ids.card)),
    }), ids);

  // 1. The sticky, from its right-click menu.
  const sc = await centre(stickySel);
  await page.mouse.click(sc.x, sc.y);
  await page.waitForTimeout(300);
  await page.mouse.click(sc.x, sc.y, { button: "right" });
  await page.waitForTimeout(400);
  const lockRow = await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim()));
  ok("the item's right-click menu offers Lock", lockRow.includes("Lock"), JSON.stringify(lockRow));
  await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].find((b) => b.textContent.trim() === "Lock").click());
  await page.waitForTimeout(800);

  // 2. The rectangle and the card, with Ctrl+Shift+L.
  const rc = await page.evaluate((sel) => {
    const r = document.querySelector(sel).getBoundingClientRect();
    return { x: r.left + 2, y: r.top + r.height / 2 };
  }, rectSel);
  await page.mouse.click(rc.x, rc.y);
  await page.waitForTimeout(300);
  const rectSelected = await page.evaluate((id) => wbSelectedItem?.kind === "sketch" && wbSelectedItem.id === id, ids.rect);
  if (process.env.DEBUG) {
    console.log("dbg", await page.evaluate(async () => {
      try { const sel = [wbSelectedItem, [...wbMultiSelection]]; await wbLockSelection(); return JSON.stringify(sel) + " ok " + JSON.stringify(wbLockedItems().map(([k, i]) => k + i.id)); } catch (e) { return String(e.stack); }
    }));
  }
  await page.keyboard.press("Control+Shift+L");
  await page.waitForTimeout(800);
  const cc = await centre(cardSel);
  await page.mouse.click(cc.x, cc.y);
  await page.waitForTimeout(300);
  await page.keyboard.press("Control+Shift+L");
  await page.waitForTimeout(1000);
  const all = await locked();
  ok("the sticky, the rectangle and the card are locked", all.sticky && all.rect && all.card, JSON.stringify({ ...all, rectSelected }));
  const painted = await page.evaluate(({ a, b, c }) => [a, b, c].map((s) => document.querySelector(s)?.classList.contains("wb-locked")), { a: stickySel, b: rectSel, c: cardSel });
  ok("each is drawn as locked", painted.every(Boolean), JSON.stringify(painted));

  // 3. The pointer goes through.
  const through = await page.evaluate(({ points }) => points.map(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return el?.closest(".wb-object, .node-card, .sketch-group") ? "item" : "board";
  }), { points: [[sc.x, sc.y], [cc.x, cc.y], [rc.x, rc.y]] });
  ok("a press on a locked item reaches the board", through.every((w) => w === "board"), JSON.stringify(through));
  const before = await page.evaluate((ids) => ({ x: wbState.objects.find((o) => o.id === ids.sticky).x, card: wbState.nodes.find((n) => n.id === ids.card).x }), ids);
  await page.mouse.move(sc.x, sc.y);
  await page.mouse.down();
  await page.mouse.move(sc.x + 80, sc.y + 40, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(600);
  const after = await page.evaluate((ids) => ({ x: wbState.objects.find((o) => o.id === ids.sticky).x, card: wbState.nodes.find((n) => n.id === ids.card).x }), ids);
  ok("a drag from a locked sticky moves nothing", before.x === after.x, `${before.x} -> ${after.x}`);

  // 4. Select all, and a marquee over everything, leave them out.
  await page.mouse.click(box.x + box.w - 30, box.y + 470 * S + OY);
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(400);
  const selAll = await page.evaluate(() => [...wbMultiSelection].concat(wbSelectedItem ? [`${wbSelectedItem.kind}:${wbSelectedItem.id}`] : []));
  ok("Select all passes the locked items by", !selAll.some((k) => [`object:${ids.sticky}`, `sketch:${ids.rect}`, `node:${ids.card}`].includes(k)), JSON.stringify(selAll));
  await page.keyboard.press("Escape");
  if (process.env.DEBUG) {
    await page.screenshot({ path: `${process.env.SCRATCH}/wblock-pre-marquee.png` });
    console.log("at start", await page.evaluate(({ x, y }) => { const el = document.elementFromPoint(x, y); return [el?.tagName, el?.id, el?.className?.baseVal ?? el?.className, window.currentTool]; }, { x: box.x + 700, y: box.y + 520 }));
  }
  await page.mouse.move(box.x + Math.min(700 * S, box.w - 6), box.y + 520 * S + OY);
  await page.mouse.down();
  await page.mouse.move(box.x + 20 * S, box.y + 100 * S + OY, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(400);
  const swept = await page.evaluate(() => [...wbMultiSelection].concat(wbSelectedItem ? [`${wbSelectedItem.kind}:${wbSelectedItem.id}`] : []));
  ok("a marquee over everything passes them by, and takes the frame it holds whole", !swept.some((k) => [`object:${ids.sticky}`, `sketch:${ids.rect}`, `node:${ids.card}`].includes(k)) && swept.includes(`object:${ids.frame}`), JSON.stringify(swept));
  await page.keyboard.press("Escape");

  // 5. The frame's drag leaves them where they are.
  const ft = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-frame-title`).getBoundingClientRect();
    return { x: r.left + 10, y: r.top + r.height / 2 };
  }, ids.frame);
  const pos = () => page.evaluate((ids) => ({
    frame: wbState.objects.find((o) => o.id === ids.frame).x,
    sticky: wbState.objects.find((o) => o.id === ids.sticky).x,
    card: wbState.nodes.find((n) => n.id === ids.card).x,
  }), ids);
  const p0 = await pos();
  await page.mouse.move(ft.x, ft.y);
  await page.mouse.down();
  await page.mouse.move(ft.x + 60, ft.y + 20, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  const p1 = await pos();
  ok("the frame moves and leaves its locked contents", p1.frame !== p0.frame && p1.sticky === p0.sticky && p1.card === p0.card, JSON.stringify({ p0, p1 }));
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800);

  // 6. The eraser passes them by.
  await page.keyboard.press("e");
  await page.mouse.move(sc.x - 60, sc.y);
  await page.mouse.down();
  await page.mouse.move(sc.x + 60, sc.y, { steps: 10 });
  await page.mouse.move(cc.x, cc.y, { steps: 10 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  await page.keyboard.press("v");
  const still = await page.evaluate((ids) => ({
    sticky: wbState.objects.some((o) => o.id === ids.sticky), card: wbState.nodes.some((n) => n.id === ids.card),
  }), ids);
  ok("the eraser passes them by", still.sticky && still.card, JSON.stringify(still));

  // 7. Saved: a fresh read of the board says the card is locked.
  const fresh = await page.evaluate(async (ids) => {
    const st = await apiJson(`/whiteboard/?board_id=${window.currentBoardId}`);
    return { card: st.nodes.find((n) => n.id === ids.card)?.locked, sticky: st.objects.find((o) => o.id === ids.sticky)?.data?.locked };
  }, ids);
  ok("the locks are saved", fresh.card === true && fresh.sticky === true, JSON.stringify(fresh));

  // 8. Undo takes the last lock back (the card's), and redo puts it on again.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(900);
  const undone = await locked();
  ok("Ctrl+Z takes the last lock back", !undone.card && undone.sticky && undone.rect, JSON.stringify(undone));
  await page.keyboard.press("Control+Shift+z");
  await page.waitForTimeout(900);
  const redone = await locked();
  ok("Ctrl+Shift+Z puts it on again", redone.card, JSON.stringify(redone));

  // 9. The board's menu names them and unlocks them.
  await page.mouse.click(sc.x, sc.y, { button: "right" });
  await page.waitForTimeout(400);
  const rows = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .action-menu:not(.hidden) button")].map((b) => b.textContent.trim()).filter(Boolean));
  const unlockRow = rows.find((r) => /Unlock 3 locked items/.test(r));
  ok("a right-click on a locked item opens the board's menu, naming three", Boolean(unlockRow), JSON.stringify(rows));
  await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .action-menu:not(.hidden) button")].find((b) => /Unlock 3 locked items/.test(b.textContent)).click());
  await page.waitForTimeout(1200);
  const open = await locked();
  ok("Unlock frees all three", !open.sticky && !open.rect && !open.card, JSON.stringify(open));
  const reachable = await page.evaluate(({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest(".wb-object")), sc);
  ok("the sticky takes the pointer again", reachable);

  // 10. Ctrl+Shift+L with nothing selected unlocks everything.
  await page.mouse.click(sc.x, sc.y);
  await page.waitForTimeout(300);
  await page.keyboard.press("Control+Shift+L");
  await page.waitForTimeout(800);
  await page.keyboard.press("Escape");
  await page.evaluate(() => { clearWbSelection(); document.getElementById("whiteboard-container").focus(); });
  await page.keyboard.press("Control+Shift+L");
  await page.waitForTimeout(800);
  const freed = await locked();
  ok("Ctrl+Shift+L with nothing selected unlocks", !freed.sticky, JSON.stringify(freed));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
