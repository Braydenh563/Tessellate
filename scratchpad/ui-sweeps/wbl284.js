// L284: a resize shows its size readout (plain and with Shift), a sticker's
// glyph grows with its box, and double-clicking a turned frame's rotate
// handle stands it and what is inside it upright again.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbl284.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board, errors } = await openBoard({ title: "l284" });
  const ids = await page.evaluate(async (b) => {
    const mk = (o) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: b, z: 1, ...o }) });
    const st = await mk({ kind: "text", data: { content: "😀", sticker: true }, x: 100, y: 100, width: 80, height: 80 });
    const fr = await mk({ kind: "frame", data: { content: "F" }, x: 400, y: 100, width: 300, height: 200, z: 0 });
    const kid = await mk({ kind: "text", data: { content: "inside" }, x: 450, y: 150, width: 120, height: 50 });
    await openWhiteboardBoard(b);
    return { st: st.id, fr: fr.id, kid: kid.id };
  }, board.id);
  await page.waitForTimeout(1500);
  await page.evaluate(() => { wbSelectToolRef?.("select"); });
  const sel = (id) => `.wb-object[data-id="${id}"]`;
  const glyph = () => page.evaluate((s) => parseFloat(getComputedStyle(document.querySelector(s + " .wb-text-content")).fontSize), sel(ids.st));
  const g0 = await glyph();
  for (const shift of [false, true]) {
    await page.evaluate((id) => wbSelectExactly([["object", wbState.objects.find((o) => o.id === id)]]), ids.st);
    await page.waitForTimeout(300);
    const h = await page.evaluate((s) => { const el = document.querySelector(s + " .wb-resize-handle.se, " + s + ' .wb-resize-handle[data-handle="se"]') || [...document.querySelectorAll(s + " .wb-resize-handle")].pop(); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel(ids.st));
    await page.mouse.move(h.x, h.y);
    if (shift) await page.keyboard.down("Shift");
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(h.x + i * 6, h.y + i * 6);
    const readout = await page.evaluate(() => document.querySelector(".wb-size-readout text")?.textContent || null);
    const count = await page.evaluate(() => document.querySelectorAll(".wb-size-readout").length);
    await page.mouse.up();
    if (shift) await page.keyboard.up("Shift");
    await page.waitForTimeout(400);
    check(`resize${shift ? " with Shift" : ""} shows one size readout`, readout && /^\d+ x \d+$/.test(readout) && count === 1, { readout, count });
  }
  const g1 = await glyph();
  check("the sticker's glyph grew with its box", g1 > g0 * 1.3, { g0, g1 });
  // Frame: turned with its contents, then double-click the rotate handle.
  const kid0 = await page.evaluate((id) => { const o = wbState.objects.find((x) => x.id === id); return [o.x, o.y, o.rotation || 0]; }, ids.kid);
  await page.evaluate((id) => wbSelectExactly([["object", wbState.objects.find((o) => o.id === id)]]), ids.fr);
  await page.waitForTimeout(300);
  const rh = await page.evaluate((s) => { const el = document.querySelector(s + " .wb-rotate-handle"); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel(ids.fr));
  const box = await page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel(ids.fr));
  if (rh) {
    await page.mouse.move(rh.x, rh.y); await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(rh.x + i * 15, rh.y + i * 12);
    await page.mouse.up(); await page.waitForTimeout(600);
  }
  const turned = await page.evaluate(([f, k]) => { const a = wbState.objects.find((x) => x.id === f); const b = wbState.objects.find((x) => x.id === k); return { frame: a.rotation || 0, kid: [b.x, b.y, b.rotation || 0] }; }, [ids.fr, ids.kid]);
  check("the frame turned and its contents with it", Math.abs(turned.frame) > 10 && Math.abs(turned.kid[2]) > 10, turned);
  const rh2 = await page.evaluate((s) => { const el = document.querySelector(s + " .wb-rotate-handle"); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel(ids.fr));
  if (rh2) await page.mouse.dblclick(rh2.x, rh2.y);
  await page.waitForTimeout(800);
  const back = await page.evaluate(([f, k]) => { const a = wbState.objects.find((x) => x.id === f); const b = wbState.objects.find((x) => x.id === k); return { frame: a.rotation || 0, kid: [b.x, b.y, b.rotation || 0] }; }, [ids.fr, ids.kid]);
  check("double-click stands the frame upright", Math.abs(back.frame) < 0.5, back);
  check("and its contents upright where they were", Math.abs(back.kid[2]) < 0.5 && Math.abs(back.kid[0] - kid0[0]) < 2 && Math.abs(back.kid[1] - kid0[1]) < 2, { back, kid0 });
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
