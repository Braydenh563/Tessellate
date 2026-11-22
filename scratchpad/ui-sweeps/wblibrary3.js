// Board library, third pass: the Shape libraries dialog, stemmed search, a library item dropped onto a line, update
// from the source, linked copies (WHITEBOARD_PLAN "More-shapes dialog", "Sidebar search", "Drag a library item into a
// connector"; LEDGER L-whiteboard-9 and L275), plus "Place on this board" for a template.
//   BASE=http://127.0.0.1:8895 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wblibrary3.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ title: "wblibrary3" });
  const names = () => page.evaluate(() => [...document.querySelectorAll("#wb-lib-list .wb-lib-tile .wb-lib-name")].map((n) => n.textContent));
  const search = async (q) => {
    await page.fill("#wb-lib-search", q);
    await page.waitForTimeout(700);
    return names();
  };
  const api = (path, method, body) => page.evaluate(([p, m, b]) => apiJson(p, { method: m, body: b ? JSON.stringify(b) : undefined }), [path, method, body]);

  await page.click("#wb-add-note");
  await page.waitForTimeout(1200);

  // 1. Shape libraries dialog: the menu row, one row per set, the switch hides a set from the list and from search.
  const menuHas = await page.evaluate(() => wbLibPanelMenu().some((i) => /Shape libraries/.test(i.label)));
  check("the Library menu has Shape libraries", menuHas);
  const before = await search("arrow");
  await page.fill("#wb-lib-search", "");
  await page.evaluate(() => wbFmtState.libraryMore.sets.open());
  await page.waitForSelector("#wb-sets-dialog .wb-sets-row");
  const dlg = await page.evaluate(() => {
    const card = document.querySelector("#wb-sets-dialog .wb-sets-card").getBoundingClientRect();
    const rows = [...document.querySelectorAll("#wb-sets-dialog .wb-sets-row")];
    return {
      rows: rows.length, withCount: rows.filter((r) => /\d/.test(r.querySelector(".wb-sets-count").textContent)).length,
      names: rows.map((r) => r.querySelector("span").textContent), inside: card.left >= 0 && card.right <= innerWidth && card.top >= 0 && card.bottom <= innerHeight,
      checked: rows.filter((r) => r.querySelector("input").checked).length,
    };
  });
  check("the dialog has one row per set with a count, all on, inside the window", dlg.rows >= 15 && dlg.withCount === dlg.rows && dlg.checked === dlg.rows && dlg.inside, dlg);
  const arrowTiles = async () => page.evaluate(() => wbLibEntries().filter((e) => e.group === "set:arrows").length);
  const nBefore = await arrowTiles();
  await page.click('#wb-sets-dialog input[data-set="arrows"]');
  await page.waitForTimeout(500);
  const nAfter = await arrowTiles();
  const groups = await page.evaluate(() => [...document.querySelectorAll("#wb-lib-list .wb-lib-group-head span:nth-child(2)")].map((s) => s.textContent));
  check("turning Arrows off removes its entries and its group", nBefore > 0 && nAfter === 0 && !groups.includes("Arrows"), { nBefore, nAfter, groups });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const gone = await page.evaluate(() => !document.getElementById("wb-sets-dialog"));
  check("Escape closes the dialog", gone);
  const after = await search("arrow");
  const bySet = await page.evaluate(() => wbLibEntries().filter((e) => /arrow/i.test(e.name) && e.group === "set:arrows").length);
  check("search no longer lists the off set", bySet === 0 && after.length < before.length, { before: before.length, after: after.length, bySet });
  const stored = await page.evaluate(() => localStorage.getItem("wb-lib-sets-off"));
  check("the choice is kept on this device", /arrows/.test(stored || ""), stored);
  // A draw.io set that is off is not fetched even by a search; turning it on fetches it.
  await page.evaluate(() => wbFmtState.libraryMore.sets.setOn("drawio-networks", false));
  const fetchedOff = await page.evaluate(async () => { wbLibSets.delete("drawio-networks"); await wbLoadShapeSets(); return wbLibSets.has("drawio-networks"); });
  await page.evaluate(() => wbFmtState.libraryMore.sets.setOn("drawio-networks", true));
  const fetchedOn = await page.evaluate(() => wbLibSets.has("drawio-networks"));
  check("an off draw.io set is not loaded; turning it on loads it", !fetchedOff && fetchedOn, { fetchedOff, fetchedOn });
  await page.evaluate(() => wbFmtState.libraryMore.sets.setOn("arrows", true));
  await page.waitForTimeout(300);

  // 2. Stemmed search.
  const arrows = await search("arrows");
  const arrow = await search("arrow");
  check("arrows (plural) finds what arrow finds", arrows.length > 0 && arrows.length >= arrow.length - 0 && arrow.every((n) => arrows.includes(n)), { arrows: arrows.length, arrow: arrow.length });
  const connecting = await search("connecting");
  check("connecting finds a connector", connecting.some((n) => /connect/i.test(n)), connecting.slice(0, 8));
  await page.fill("#wb-lib-search", "");

  // 3. A library item of our own, for the rest.
  const payload = (d, colour) => ({ box: { w: 100, h: 60 }, links: [], items: [{ key: "s1", kind: "sketch", z: 5, data: { d, shape: "custom", color: colour, fill: "ink", width: 2 } }] });
  const rect = "M 0 0 L 100 0 L 100 60 L 0 60 Z";
  const tri = "M 50 0 L 100 60 L 0 60 Z";
  const item = await api("/board-library", "POST", { kind: "element", name: "Zed shape", tags: [], payload: payload(rect, "#cc2222") });
  const placeNamed = (name, x, y, opts) => page.evaluate(async ([n, px, py, o]) => {
    wbLibState.lib = null;
    await wbLoadLibrary({ force: true });
    const entry = wbLibEntries().find((e) => e.name === n);
    await wbLibPlace(entry, [px, py], o || {});
    return (wbState.sketches || []).length;
  }, [name, x, y, opts]);
  const sk = () => page.evaluate(() => (wbState.sketches || []).filter((s) => !/"type"\s*:\s*"link-/.test(s.data)).map((s) => ({ id: s.id, d: JSON.parse(s.data).d, ref: JSON.parse(s.data).library_ref })));
  const links = () => page.evaluate(() => (wbState.sketches || []).filter((s) => /"type"\s*:\s*"link-/.test(s.data)).map((s) => ({ id: s.id, ...JSON.parse(s.data) })));

  // 4. Drop onto a line: 2 links, one undo.
  await placeNamed("Zed shape", 0, 0);
  await placeNamed("Zed shape", 600, 0);
  const two = await sk();
  const link = await api("/whiteboard/sketches", "POST", {
    data: JSON.stringify({ type: "link-straight", sourceId: two[0].id, sourceKind: "sketch", targetId: two[1].id, targetKind: "sketch", color: "#335599", endCap: "arrow" }),
    x: 0, y: 0, z: 1, board_id: board.id,
  });
  await page.evaluate(async () => { await fetchWhiteboardState(); wbScheduleRender(); });
  await page.waitForTimeout(600);
  const mid = await page.evaluate((id) => {
    const el = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-hitbox`) || document.querySelector(`.sketch-group[data-id="${id}"]`);
    const path = el.tagName === "path" ? el : el.querySelector("path");
    const len = path.getTotalLength();
    const p = path.getPointAtLength(len / 2);
    const m = path.getScreenCTM();
    return { x: m.a * p.x + m.c * p.y + m.e, y: m.b * p.x + m.d * p.y + m.f };
  }, link.id);
  const under = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest?.(".sketch-group[data-id]")?.dataset.id || null, [mid.x, mid.y]);
  check("the line is the element under the pointer at its middle", String(under) === String(link.id), { under, id: link.id });
  const l0 = await links();
  const s0 = (await sk()).length;
  await page.fill("#wb-lib-search", "Zed");
  await page.waitForTimeout(500);
  await page.evaluate(([x, y]) => {
    const tile = [...document.querySelectorAll("#wb-lib-list .wb-lib-tile")].find((t) => /Zed shape/.test(t.textContent));
    const dt = new DataTransfer();
    tile.dispatchEvent(new DragEvent("dragstart", { bubbles: true, cancelable: true, dataTransfer: dt, clientX: 50, clientY: 50 }));
    const over = document.elementFromPoint(x, y);
    over.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt, clientX: x, clientY: y }));
    window.__drop = { g: over.closest(".sketch-group[data-id]")?.dataset.id || null };
    over.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt, clientX: x, clientY: y }));
  }, [mid.x, mid.y]);
  await page.waitForTimeout(1800);
  console.log("drop saw", JSON.stringify(await page.evaluate(() => window.__drop)));
  const l1 = await links();
  const s1 = await sk();
  const placedId = s1.map((s) => s.id).find((id) => !two.some((t) => t.id === id));
  const first = l1.find((l) => l.targetId === placedId);
  const second = l1.find((l) => l.sourceId === placedId);
  check("dropping on a line makes 2 links and 1 new shape", l0.length === 1 && l1.length === 2 && s1.length === s0 + 1, { l0: l0.length, l1: l1.length, s0, s1: s1.length });
  check("A to item and item to B, split at its ports", first && second && first.sourceId === two[0].id && first.targetId === placedId && second.sourceId === placedId && second.targetId === two[1].id
    && first.targetAnchor?.x === 0 && second.sourceAnchor?.x === 1, { first, second });
  await page.evaluate(() => wbUndo?.());
  await page.waitForTimeout(1200);
  const l2 = await links();
  const s2 = await sk();
  check("one Undo puts the line back whole", l2.length === 1 && l2[0].targetId === two[1].id && s2.length === s0, { links: l2.length, shapes: s2.length });
  await page.fill("#wb-lib-search", "");

  // 5. Update from the source: keeps place and size, one undo step, says so when the source is gone.
  const geom = () => page.evaluate(() => (wbState.sketches || []).filter((s) => !/"type"\s*:\s*"link-/.test(s.data)).map((s) => { const b = wbPathBBox(JSON.parse(s.data).d); return { id: s.id, d: JSON.parse(s.data).d, minX: b.minX, minY: b.minY, w: b.width, h: b.height }; }));
  const target = (await geom())[0];
  await page.evaluate((id) => { clearWbSelection(); wbSelectedItem = { kind: "sketch", id }; wbApplySelectionHighlight(); }, target.id);
  const offered = await page.evaluate(() => wbCommandApplies(WB_COMMAND_BY_ID.get("update-from-library")) && Boolean(wbCommandMenuRow("update-from-library")));
  check("Update from the library is offered for a placed copy (palette and menu)", offered);
  await api(`/board-library/${item.id}`, "PUT", { payload: payload(tri, "#cc2222") });
  await page.evaluate(() => wbRunCommand("update-from-library"));
  await page.waitForTimeout(1500);
  const upd = (await geom()).find((g) => g.id === target.id);
  check("update from source: the outline changed, place and size kept", upd.d !== target.d && Math.abs(upd.minX - target.minX) < 0.01 && Math.abs(upd.minY - target.minY) < 0.01 && Math.abs(upd.w - target.w) < 0.01 && Math.abs(upd.h - target.h) < 0.01, { target, upd });
  await page.evaluate(() => wbUndo?.());
  await page.waitForTimeout(1200);
  const undone = (await geom()).find((g) => g.id === target.id);
  check("one Undo restores the copy", undone.d === target.d, { undone: undone.d, target: target.d });
  await api(`/board-library/${item.id}`, "DELETE");
  await page.evaluate(() => wbRunCommand("update-from-library"));
  await page.waitForTimeout(800);
  const toastText = await page.evaluate(() => [...document.querySelectorAll(".toast, #toast-container *")].map((n) => n.textContent).join(" | "));
  const kept = (await geom()).find((g) => g.id === target.id);
  check("a gone source is said and the copy is left as it is", /is gone/.test(toastText) && kept.d === target.d, toastText.slice(0, 160));
  await api(`/board-library/${item.id}/restore`, "POST");

  // 6. Linked: a change to the item reaches the copy when the board opens; Unlink stops it.
  await page.evaluate(() => { wbLibState.lib = null; });
  const linkedItem = await api("/board-library", "POST", { kind: "element", name: "Linked sample", tags: [], payload: payload(rect, "#2255cc") });
  await placeNamed("Linked sample", 0, 300, { linked: true });
  const linkedCopy = (await sk()).find((s) => s.ref && s.ref.id === linkedItem.id);
  check("a linked placement carries the signature", linkedCopy && linkedCopy.ref.linked && typeof linkedCopy.ref.linked.sig === "string", linkedCopy);
  const gBefore = (await geom()).find((g) => g.id === linkedCopy.id);
  await api(`/board-library/${linkedItem.id}`, "PUT", { payload: payload(tri, "#2255cc") });
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, board.id);
  await page.waitForTimeout(3000);
  const gAfter = (await geom()).find((g) => g.id === linkedCopy.id);
  check("linked: the copy follows the item on board load, place and size kept", gAfter && gAfter.d !== gBefore.d && Math.abs(gAfter.minX - gBefore.minX) < 0.01 && Math.abs(gAfter.w - gBefore.w) < 0.01, { gBefore, gAfter });
  // And on a library edit made while the board is open.
  await api(`/board-library/${linkedItem.id}`, "PUT", { payload: payload(rect, "#2255cc") });
  const refreshed = await page.evaluate(() => wbFmtState.libraryMore.copies.refresh());
  const gEdit = (await geom()).find((g) => g.id === linkedCopy.id);
  check("linked: a library edit reaches it without a reload", refreshed === 1 && gEdit.d !== gAfter.d, { refreshed });
  await page.evaluate((id) => { clearWbSelection(); wbSelectedItem = { kind: "sketch", id }; wbApplySelectionHighlight(); }, linkedCopy.id);
  const canUnlink = await page.evaluate(() => wbCommandApplies(WB_COMMAND_BY_ID.get("unlink-library")));
  await page.evaluate(() => wbRunCommand("unlink-library"));
  await page.waitForTimeout(1000);
  await api(`/board-library/${linkedItem.id}`, "PUT", { payload: payload(tri, "#2255cc") });
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, board.id);
  await page.waitForTimeout(3000);
  const gUnlinked = (await geom()).find((g) => g.id === linkedCopy.id);
  check("unlink: the copy stays when the item changes", canUnlink && gUnlinked.d === gEdit.d, { canUnlink });

  // 7. Place on this board, for a template (b90d8934): shapes land on the open board, no new board.
  await api("/board-library", "POST", { kind: "template", name: "Zed template", tags: ["template", "board"], payload: { board: { type: "board" }, element: payload(tri, "#118833") } });
  const tpl = await page.evaluate(async () => {
    wbLibState.lib = null;
    await wbLoadLibrary({ force: true });
    await wbLoadShapeSets();
    const entry = wbLibEntries().find((e) => e.name === "Zed template");
    const row = wbLibMenuItems(entry).find((i) => /Place on this board/.test(i.label));
    if (!row) return { name: "no menu row" };
    const idBefore = window.currentBoardId;
    const n0 = (wbState.sketches || []).length + (wbState.objects || []).length;
    await row.run();
    await new Promise((r) => setTimeout(r, 1500));
    return { name: entry.name, idBefore, idAfter: window.currentBoardId, n0, n1: (wbState.sketches || []).length + (wbState.objects || []).length };
  });
  check("Place on this board puts a template's shapes on the open board", tpl.idBefore === tpl.idAfter && tpl.n1 > tpl.n0, tpl);

  check("no console errors", errors.length === 0, errors.slice(0, 5));
  const ok = summary();
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
