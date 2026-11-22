// L285: the board's set of templates, style presets, align and distribute,
// find, copy as picture and the keys sheet, each driven and measured.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbl285.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board, errors } = await openBoard({ title: "l285" });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const ids = await page.evaluate(async (b) => {
    const mk = (o) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: b, z: 1, kind: "text", width: 120, height: 50, ...o }) });
    const a = await mk({ data: { content: "alpha apple" }, x: 100, y: 100 });
    const c = await mk({ data: { content: "beta" }, x: 160, y: 320 });
    const d = await mk({ data: { content: "gamma apple" }, x: 700, y: 180 });
    await openWhiteboardBoard(b);
    return [a.id, c.id, d.id];
  }, board.id);
  await page.waitForTimeout(1200);
  const objs = () => page.evaluate((list) => list.map((id) => { const o = wbState.objects.find((x) => x.id === id); return { x: o.x, y: o.y, w: o.width, data: o.data }; }), ids);
  const selectAll = () => page.evaluate((list) => wbSelectExactly(list.map((id) => ["object", wbState.objects.find((o) => o.id === id)])), ids);

  await selectAll();
  await page.evaluate(() => wbAlignSelection("left"));
  await page.waitForTimeout(600);
  const aligned = await objs();
  check("align left puts every left edge at one x", new Set(aligned.map((o) => Math.round(o.x))).size === 1, aligned.map((o) => o.x));

  await selectAll();
  await page.evaluate(() => wbDistributeSelection("vertical"));
  await page.waitForTimeout(600);
  const spread = (await objs()).map((o) => o.y).sort((p, q) => p - q);
  check("distribute vertically gives equal gaps", Math.abs((spread[1] - spread[0]) - (spread[2] - spread[1])) < 2, spread);

  await page.evaluate(() => wbUndo?.());
  await page.waitForTimeout(500);
  const undone = (await objs()).map((o) => o.y).sort((p, q) => p - q);
  check("Undo puts the distribute back", JSON.stringify(undone) !== JSON.stringify(spread), { undone, spread });

  await selectAll();
  const blue = await page.evaluate(async () => { const p = wbFmtState.board.PRESETS.find((x) => x.name === "Blue"); await wbFmtState.board.apply(p); return p; });
  await page.waitForTimeout(600);
  const styled = await objs();
  //: An unfilled text box takes the preset's ink only (patchFor); a sticky would take its fill too.
  check("a style preset inks every selected box", styled.every((o) => (o.data.color || "").toLowerCase() === blue.ink), styled.map((o) => o.data.color));

  await page.evaluate(() => wbOpenBoardSearch());
  await page.waitForTimeout(400);
  const field = await page.evaluate(() => { const el = document.activeElement; return el && el.tagName === "INPUT" ? el.id || el.className : null; });
  await page.keyboard.type("apple");
  await page.waitForTimeout(700);
  const found = await page.evaluate(() => document.body.innerText.match(/(\d+)\s+of\s+(\d+)/)?.[0] || null);
  check("Find opens with its field focused", Boolean(field), field);
  check("Find counts the two apples", found && /of 2\b/.test(found), found);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  await selectAll();
  await page.evaluate(() => wbCopyAsImage());
  await page.waitForTimeout(1500);
  const clip = await page.evaluate(async () => { try { const items = await navigator.clipboard.read(); const t = items[0]?.types || []; const png = t.includes("image/png") ? await items[0].getType("image/png") : null; return { types: t, bytes: png ? png.size : 0 }; } catch (e) { return { error: String(e) }; } });
  check("Copy as image puts a PNG on the clipboard", clip.types?.includes("image/png") && clip.bytes > 500, clip);

  await page.evaluate(() => { wbSelectExactly([]); document.activeElement?.blur(); });
  await page.mouse.click(1200, 700);
  await page.keyboard.press("Shift+Slash");
  await page.waitForTimeout(500);
  const keys = await page.evaluate(() => { const o = document.getElementById("wb-help-overlay"); return { open: o && !o.classList.contains("hidden"), rows: o ? o.querySelectorAll("kbd").length : 0 }; });
  check("? opens the keys sheet", keys.open && keys.rows > 10, keys);
  await page.keyboard.press("Escape");

  const tpl = await page.evaluate(async (b) => {
    const before = wbState.objects.length + wbState.sketches.length;
    await apiJson(`/whiteboard/boards/${b}/place`, { method: "POST", body: JSON.stringify({ builtin: "templates/flow", x: 0, y: 600 }) });
    await openWhiteboardBoard(b);
    await new Promise((r) => setTimeout(r, 1200));
    return { added: wbState.objects.length + wbState.sketches.length - before };
  }, board.id);
  check("a built-in template places on the board", tpl.added > 0, tpl);

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
