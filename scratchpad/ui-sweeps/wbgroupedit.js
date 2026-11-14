// Edit inside a group, first-use tool hints and saved workspaces, driven in the real board
// (L-whiteboard-7, -8, -10, -19). Measured with getComputedStyle, not by eye.
//   BASE=http://127.0.0.1:8871 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbgroupedit.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ title: "wbgroupedit" });

  // --- Edit inside a group ---
  const ids = await page.evaluate(async (bid) => {
    const box = async (x, y, words, group) => (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
      kind: "text", data: { content: words }, board_id: bid, x, y, z: 1, width: 120, height: 60, group_id: group || null,
    }) })).id;
    const a = await box(250, 300, "Inside A", "g1");
    const b = await box(550, 300, "Inside B", "g1");
    const c = await box(250, 500, "Outside C");
    const d = await box(550, 500, "Outside D");
    const link = async (s, t) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      board_id: bid, x: 0, y: 0, z: 3, data: JSON.stringify({ type: "link-straight", sourceKind: "object", sourceId: s, targetKind: "object", targetId: t, color: "#445566", width: 3, endCap: "arrow" }),
    }) })).id;
    const inIn = await link(a, b);
    const mixed = await link(a, c);
    const outOut = await link(c, d);
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return { a, b, c, d, inIn, mixed, outOut };
  }, board.id);
  await page.waitForTimeout(800);

  const probe = () => page.evaluate((i) => {
    const look = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { opacity: Number(cs.opacity), pe: cs.pointerEvents, dimmed: el.classList.contains("wb-dimmed") };
    };
    const obj = (id) => look(`.wb-object[data-id="${id}"]`);
    const sk = (id) => look(`.sketch-group[data-id="${id}"]`);
    return {
      a: obj(i.a), b: obj(i.b), c: obj(i.c), d: obj(i.d),
      inIn: sk(i.inIn), mixed: sk(i.mixed), outOut: sk(i.outOut),
      active: wbFmtState.isolate.active(), isolating: document.getElementById("library-view-whiteboard").classList.contains("wb-isolating"),
    };
  }, ids);

  const before = await probe();
  check("outside a group nothing is dimmed", [before.a, before.b, before.c, before.d, before.inIn, before.mixed, before.outOut].every((x) => x && !x.dimmed && x.opacity === 1), before);

  // Enter by double-clicking a member, the way the owner does.
  const box = await page.evaluate((id) => { const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, ids.a);
  await page.mouse.dblclick(box.x, box.y);
  await page.waitForTimeout(500);
  let inside = await probe();
  if (!inside.active) {
    // Fall back to the command, and say so.
    await page.evaluate(() => wbFmtState.isolate.enter(["g1"]));
    await page.waitForTimeout(300);
    inside = await probe();
    console.log("note: double-click did not open the group; opened with isolate.enter");
  } else console.log("note: double-click on a member opened the group");
  check("the group is open and the board says so", inside.active && inside.isolating, inside);
  check("members are full opacity and clickable", [inside.a, inside.b].every((x) => x.opacity === 1 && x.pe !== "none" && !x.dimmed), [inside.a, inside.b]);
  check("items outside are dimmed to 0.25 and out of reach", [inside.c, inside.d].every((x) => x.opacity === 0.25 && x.pe === "none" && x.dimmed), [inside.c, inside.d]);
  check("a connector between two members stays full opacity and clickable", inside.inIn.opacity === 1 && inside.inIn.pe !== "none" && !inside.inIn.dimmed, inside.inIn);
  check("a connector from a member to an outside item is dimmed", inside.mixed.opacity === 0.25 && inside.mixed.pe === "none", inside.mixed);
  check("a connector between two outside items is dimmed", inside.outOut.opacity === 0.25 && inside.outOut.pe === "none", inside.outOut);

  // The member connector is live: a real press selects it, and it is in Select all.
  const reach = await page.evaluate((i) => {
    const out = (id) => wbFmtState.isolate.outside("sketch", wbFindItem("sketch", id));
    return { inIn: out(i.inIn), mixed: out(i.mixed), outOut: out(i.outOut) };
  }, ids);
  check("the group's own reach test (Select all, sweeps) counts the member connector in and the others out", reach.inIn === false && reach.mixed === true && reach.outOut === true, reach);
  const mid = await page.evaluate((id) => {
    const el = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-hitbox`) || document.querySelector(`.sketch-group[data-id="${id}"] .sketch-path`);
    const len = el.getTotalLength(), p = el.getPointAtLength(len / 2), m = el.getScreenCTM();
    return { x: m.a * p.x + m.c * p.y + m.e, y: m.b * p.x + m.d * p.y + m.f, top: document.elementFromPoint(m.a * p.x + m.c * p.y + m.e, m.b * p.x + m.d * p.y + m.f)?.closest?.(".sketch-group")?.dataset.id };
  }, ids.inIn);
  check("the member connector is the topmost thing under the pointer", String(mid.top) === String(ids.inIn), mid);
  await page.mouse.click(mid.x, mid.y);
  await page.waitForTimeout(400);
  const picked = await page.evaluate(() => { const k = [...wbSelectedKeys()]; return k; });
  check("clicking the member connector selects it", picked.length === 1 && picked[0] === `sketch:${ids.inIn}`, picked);

  // Escape leaves.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  const left = await probe();
  check("Escape leaves the group and nothing stays dimmed", !left.active && !left.isolating && [left.a, left.b, left.c, left.d, left.inIn, left.mixed, left.outOut].every((x) => x.opacity === 1 && !x.dimmed), left);

  // --- First-use tool hints ---
  await page.evaluate(() => {
    window.__toasts = [];
    const was = window.toast;
    window.toast = (t, k) => { window.__toasts.push(t); return was?.(t, k); };
    for (const t of ["draw", "eraser", "shape-hexagon"]) prefs.set(`wb-tool-hint-${t}`, "unseen");
  });
  const hint = (tool) => page.evaluate((t) => { const n = window.__toasts.length; wbSelectToolRef(t); return window.__toasts.slice(n); }, tool);
  const first = await hint("draw");
  check("the first time Draw is held, one hint is shown", first.length === 1 && /freehand/.test(first[0]), first);
  const again = await hint("draw");
  check("the second time it is not", again.length === 0, again);
  await page.evaluate(() => wbSelectToolRef("select"));
  const eraser = await hint("eraser");
  check("another tool has its own hint", eraser.length === 1 && /rub them out/.test(eraser[0]), eraser);
  const remembered = await page.evaluate(() => prefs.get("wb-tool-hint-draw", null));
  check("the hint is remembered per tool on this device", remembered === "seen", remembered);
  const shape = await hint("shape-hexagon");
  check("shape variants share one line", shape.length === 1 && /Shift to keep it square/.test(shape[0]), shape);
  await page.evaluate(() => wbSelectToolRef("select"));

  // --- Saved workspaces ---
  const ws = await page.evaluate(async () => {
    const W = wbFmtState.workspaces;
    for (const w of W.saved()) W.remove(w.name);
    const open = (id) => { const e = document.getElementById(id); return Boolean(e) && !e.classList.contains("hidden"); };
    const state = () => ({ ...W.snapshot(), formatOpen: open("wb-format"), sideOpen: open("wb-sidebar-panel") });
    // Layout one: Format open, Layers open.
    if (!open("wb-format")) wbFormatToggle();
    wbOpenSidebar("layers", { focus: false });
    const one = state();
    await W.save("Layout one");
    // Layout two: Format closed, sidebar closed, search open.
    if (open("wb-format")) wbFormatToggle();
    wbCloseSidebar();
    if (!open("wb-search-bar")) (wbOpenBoardSearch());
    const two = state();
    await W.save("Layout two");
    const list = W.saved().map((w) => w.name);
    W.use("Layout one");
    const backOne = state();
    W.use("Layout two");
    const backTwo = state();
    const menuRows = W.rows().length;
    const mounted = Boolean(document.querySelector("#wb-workspaces .menu-wrap"));
    return { one, two, list, backOne, backTwo, menuRows, mounted, stored: JSON.parse(prefs.get("wb-workspaces", "[]")).length };
  });
  check("two workspaces are saved by name and kept on this device", ws.list.join() === "Layout one,Layout two" && ws.stored === 2, ws);
  check("the saved layouts differ", ws.one.format !== ws.two.format && ws.one.side !== ws.two.side, [ws.one, ws.two]);
  check("switching to layout one restores Format, the Layers tab and a closed search bar", ws.backOne.format === true && ws.backOne.side === "layers" && ws.backOne.search === false, ws.backOne);
  check("switching to layout two restores a closed Format panel and sidebar and the search bar", ws.backTwo.format === false && ws.backTwo.side === "" && ws.backTwo.search === true, ws.backTwo);
  check("the View menu holds the workspaces menu with a row for each", ws.mounted && ws.menuRows === 5, ws);

  check("no page errors", errors.length === 0, errors);
  await browser.close();
  process.exit(summary() ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
