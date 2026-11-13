// L-whiteboard-12: frames bound to a note property. A card dragged into the
// Done frame writes status: Done to its note; the note set to Doing elsewhere
// moves the card into Doing when the board opens; the frame menu binds.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbbinds.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board, errors } = await openBoard({ title: "binds" });
  const ids = await page.evaluate(async (b) => {
    const mk = (o) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: b, z: 0, kind: "frame", width: 300, height: 400, y: 0, ...o }) });
    const doing = await mk({ data: { content: "Doing", binds: { property: "status", value: "Doing" } }, x: 0 });
    const done = await mk({ data: { content: "Done", binds: { property: "status", value: "Done" } }, x: 400 });
    const loose = await mk({ data: { content: "Later" }, x: 800 });
    const note = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "# Ship it\nbody" }) });
    const card = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: note.id, board_id: b, x: 40, y: 80 }) });
    await openWhiteboardBoard(b);
    return { doing: doing.id, done: done.id, loose: loose.id, note: note.id, card: card.id };
  }, board.id);
  await page.waitForTimeout(1500);
  await page.evaluate(() => wbSelectToolRef?.("select"));
  const cardEl = `#wb-html-layer .node-card[data-id="${ids.card}"]`;
  const box = await page.evaluate((sel) => { const el = document.querySelector(sel); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + 20, y: r.top + 12 }; }, cardEl);
  const doneBox = await page.evaluate((id) => { const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, ids.done);
  check("the card is on the board", Boolean(box), cardEl);
  if (box) {
    await page.mouse.move(box.x, box.y); await page.mouse.down();
    for (let i = 1; i <= 12; i++) await page.mouse.move(box.x + ((doneBox.x - box.x) * i) / 12, box.y + ((doneBox.y - box.y) * i) / 12);
    await page.mouse.up();
    await page.waitForTimeout(1500);
  }
  const props = (id) => page.evaluate((e) => apiJson(`/entries/${e}/properties`).then((r) => r.properties), id);
  const p1 = await props(ids.note);
  check("dragging the card into Done writes status: Done", JSON.stringify(p1.status) === '["Done"]', p1);

  await page.evaluate((e) => apiJson(`/entries/${e}/properties`, { method: "PUT", body: JSON.stringify({ properties: { status: "Doing" } }) }), ids.note);
  await page.evaluate((b) => openWhiteboardBoard(b), board.id);
  await page.waitForTimeout(2500);
  const where = await page.evaluate(([c, f]) => { const n = wbState.nodes.find((x) => x.id === c); const fr = wbState.objects.find((x) => x.id === f); return { x: n.x, y: n.y, fx: fr.x, fw: fr.width }; }, [ids.card, ids.doing]);
  check("the note set to Doing moved the card into Doing on open", where.x >= where.fx && where.x <= where.fx + where.fw, where);

  // The frame menu: bind the loose frame.
  await page.evaluate(() => { window.promptDialog = async () => "phase"; });
  await page.evaluate(() => wbSelectExactly([]));
  const lb = await page.evaluate((id) => { const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect(); return { x: r.left + 6, y: r.top + 6 }; }, ids.loose);
  await page.evaluate(([id, p]) => wbOpenContextMenuFor("object", id, p.x, p.y), [ids.loose, lb]);
  await page.waitForTimeout(500);
  const menuItem = page.locator("text=Bind to a property…").first();
  const shown = await menuItem.count();
  check("the frame's menu offers Bind to a property", shown > 0);
  if (shown) { await menuItem.click(); await page.waitForTimeout(1000); }
  const bound = await page.evaluate((id) => wbState.objects.find((o) => o.id === id)?.data?.binds, ids.loose);
  check("binding saves phase: Later", bound && bound.property === "phase" && bound.value === "Later", bound);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
