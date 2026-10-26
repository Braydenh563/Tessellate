// INBOX 1354 items 3 and 4: Group and Ungroup are one control on every
// surface, and groups nest. Seven boxes: group five, then the five and the
// other two; ungroup the outer and the five stay a group. Reload, undo and
// redo keep it; a double-click goes one group further in.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/paint1026-groups.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 1280);

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  const ids = await page.evaluate(async (bid) => {
    const out = [];
    for (let i = 0; i < 7; i++) {
      const x = 120 + i * 110;
      const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
        data: JSON.stringify({ d: `M ${x} 200 h 80 v 60 h -80 Z`, shape: "rect", color: "#335599", width: 2, fill: "#ffcc00" }),
        x: 0, y: 0, z: 1, board_id: bid,
      }) });
      out.push(s.id);
    }
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit();
    return out;
  }, board.id);
  await page.waitForTimeout(800);
  const centre = async (id) => {
    const b = await page.locator(`.sketch-group[data-id="${id}"]`).first().boundingBox();
    return [b.x + b.width / 2, b.y + b.height / 2];
  };
  // `mouse.click` takes no modifiers: Shift is held on the keyboard instead.
  const click = async (id, opts = {}) => {
    const [x, y] = await centre(id);
    for (const m of opts.modifiers || []) await page.keyboard.down(m);
    await page.mouse.click(x, y);
    for (const m of opts.modifiers || []) await page.keyboard.up(m);
    await page.waitForTimeout(250);
  };
  const selected = () => page.evaluate(() => wbMultiSelection.size || (wbSelectedItem ? 1 : 0));
  const chains = () => page.evaluate((ids) => ids.map((id) => wbState.sketches.find((s) => s.id === id)?.group_id || null), ids);
  // Which of Group and Ungroup each surface shows, as "G", "U", "GU" or "".
  const surfaces = async (id) => {
    const bar = await page.evaluate(() => ["wb-multi-group", "wb-multi-ungroup"].map((i) => {
      const e = document.getElementById(i); return e && !e.classList.contains("hidden") && e.getClientRects().length ? (i.endsWith("ungroup") ? "U" : "G") : "";
    }).join(""));
    const arrange = await page.evaluate(() => {
      const m = document.getElementById("wb-arrange-menu");
      if (!m) return "?";
      wbSyncCommandRows(m);
      return [...m.querySelectorAll("[data-wb-either]")].filter((r) => !r.hidden).map((r) => (r.dataset.wbCmd === "ungroup" ? "U" : "G") + (r.classList.contains("is-muted") ? "-" : "")).join("");
    });
    const [x, y] = await centre(id);
    await page.mouse.click(x, y, { button: "right" });
    await page.waitForTimeout(300);
    const ctx = await page.evaluate(() => {
      const m = document.querySelector(".wb-ctx-menu");
      const rows = [...(m?.querySelectorAll("button") || [])].filter((b) => !b.hidden && b.getClientRects().length && !b.closest(".hidden"));
      globalThis.__ctxRows = rows.map((b) => b.textContent.trim().slice(0, 24));
      return rows.map((b) => b.textContent.trim()).filter((t) => /^(Group|Ungroup)/.test(t)).map((t) => (t.startsWith("Un") ? "U" : "G")).join("");
    });
    console.log("ctx rows", JSON.stringify(await page.evaluate(() => globalThis.__ctxRows)));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(150);
    return { bar, ctx, arrange };
  };

  // Five of seven.
  await click(ids[0]);
  for (const id of ids.slice(1, 5)) await click(id, { modifiers: ["Shift"] });
  check("five selected", (await selected()) === 5);
  let s = await surfaces(ids[0]);
  check("five loose: Group only on every surface", s.bar === "G" && s.arrange === "G" && !s.ctx.includes("U"), s);
  // The right-click may have changed the selection; select the five again.
  await click(ids[0]);
  for (const id of ids.slice(1, 5)) await click(id, { modifiers: ["Shift"] });
  await page.keyboard.press("Control+g");
  await page.waitForTimeout(600);
  await page.mouse.click(10, 10);
  await click(ids[2]);
  check("a click on one of the five selects the five", (await selected()) === 5, await selected());
  s = await surfaces(ids[2]);
  check("a group: Ungroup only on every surface", s.bar === "U" && s.arrange === "U" && !s.ctx.includes("G"), s);
  // The five and the other two.
  await click(ids[2]);
  await click(ids[5], { modifiers: ["Shift"] });
  await click(ids[6], { modifiers: ["Shift"] });
  check("the group and two more: seven selected", (await selected()) === 7, await selected());
  s = await surfaces(ids[6]);
  check("a group plus loose items: Group only", s.bar === "G" && s.arrange === "G", s);
  await click(ids[2]);
  await click(ids[5], { modifiers: ["Shift"] });
  await click(ids[6], { modifiers: ["Shift"] });
  await page.keyboard.press("Control+g");
  await page.waitForTimeout(800);
  let c = await chains();
  const nested = c.slice(0, 5).every((g) => g && g.split(">").length === 2) && c.slice(5).every((g) => g && g.split(">").length === 1);
  check("the five hold two groups, the two hold one", nested, c);
  await page.mouse.click(10, 10);
  await click(ids[0]);
  check("a click selects all seven", (await selected()) === 7, await selected());
  // Double-click goes in: the five, then the one.
  const [x0, y0] = await centre(ids[0]);
  await page.mouse.dblclick(x0, y0);
  await page.waitForTimeout(300);
  check("a double-click selects the inner five", (await selected()) === 5, await selected());
  const editing = await page.evaluate(() => !!document.querySelector(".wb-shape-label-editor, [contenteditable=true]"));
  check("the double-click did not open the label editor", !editing);
  await page.mouse.dblclick(x0, y0);
  await page.waitForTimeout(300);
  check("another double-click selects the one", (await page.evaluate(() => wbSelectedItem?.id)) === ids[0]);
  // Reload: the chains come back from the server.
  const before = await chains();
  await page.evaluate(async () => { await fetchWhiteboardState(); renderWhiteboardNow(); });
  await page.waitForTimeout(500);
  check("the nesting survives a reload", JSON.stringify(await chains()) === JSON.stringify(before), await chains());
  // Ungroup the outer: the five stay a group.
  await page.mouse.click(10, 10);
  await click(ids[6]);
  await page.keyboard.press("Control+Shift+g");
  await page.waitForTimeout(800);
  c = await chains();
  const innerKept = c.slice(0, 5).every((g) => g && g === c[0] && !g.includes(">")) && c.slice(5).every((g) => !g);
  check("ungrouping the outer leaves the five grouped", innerKept, c);
  await page.mouse.click(10, 10);
  await click(ids[6]);
  check("one of the two now selects alone", (await selected()) === 1);
  await click(ids[1]);
  check("one of the five still selects the five", (await selected()) === 5);
  // Undo puts the outer back; redo takes it off again.
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1000);
  c = await chains();
  check("undo brings the outer group back", c.every((g) => g) && c[0].split(">").length === 2, c);
  await page.keyboard.press("Control+y");
  await page.waitForTimeout(1000);
  c = await chains();
  check("redo takes it off again", c.slice(5).every((g) => !g) && c.slice(0, 5).every((g) => g && !g.includes(">")), c);
  // Cost of a click into a group on a 500-item board: the walk is per click,
  // never per frame.
  const ms = await page.evaluate((id) => {
    const extra = [];
    for (let i = 0; i < 500; i++) extra.push({ id: 900000 + i, data: "{}", group_id: i % 3 ? null : `x${i % 7}>y${i % 5}` });
    wbState.sketches.push(...extra);
    const t0 = performance.now();
    for (let i = 0; i < 50; i++) { wbMultiSelection.clear(); wbHandleItemClick("sketch", id, { shiftKey: false, detail: 1 }); wbHandleItemClick("sketch", id, { shiftKey: false, detail: 2 }); }
    const per = (performance.now() - t0) / 100;
    const t1 = performance.now();
    const chain = wbGroupChain(wbState.sketches.find((x) => x.id === id));
    for (let i = 0; i < 100; i++) { wbSelectedGroupDepth(chain); wbItemsWithGroupPrefix(chain.slice(0, 1)); }
    globalThis.__walk = +((performance.now() - t1) / 100).toFixed(3);
    wbState.sketches.splice(wbState.sketches.length - 500, 500);
    return { per: +per.toFixed(3), walk: globalThis.__walk };
  }, ids[0]);
  console.log("click into a group, 507 items:", JSON.stringify(ms), "ms per click (whole handler, and the group walk alone)");
  check("the group walk costs under 1 ms on 507 items", ms.walk < 1, ms);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
