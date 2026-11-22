// WHITEBOARD_PLAN section 12 structure rows, measured on a live board: tags and the tag filter, a folded frame
// (one Undo, export skips what it hides), the frame drop highlight during a real drag, and find limited to a frame.
//   BASE=http://127.0.0.1:8898 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbstructure3.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 1440 });
  const { check, summary } = checker();
  // A frame holding two boxes and a connector, a second frame holding one, three loose boxes (two tagged).
  const ids = await page.evaluate(async () => {
    const b = window.currentBoardId;
    const post = (kind, data, x, y, width, height, z = 1) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind, data, board_id: b, x, y, z, width, height }) });
    const out = {};
    out.f1 = (await post("frame", { content: "Alpha frame" }, 100, 100, 420, 260, 0)).id;
    out.k1 = (await post("text", { content: "needle one" }, 130, 140, 140, 50)).id;
    out.k2 = (await post("text", { content: "needle two" }, 330, 260, 140, 50)).id;
    out.f2 = (await post("frame", { content: "Beta frame" }, 620, 100, 300, 200, 0)).id;
    out.k3 = (await post("text", { content: "needle three" }, 650, 140, 140, 50)).id;
    out.t1 = (await post("text", { content: "tagged a", tags: ["alpha"] }, 100, 460, 140, 50)).id;
    out.t2 = (await post("text", { content: "tagged b", tags: ["beta", "alpha"] }, 300, 460, 140, 50)).id;
    out.u1 = (await post("text", { content: "untagged" }, 500, 460, 140, 50)).id;
    const link = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 0, data: JSON.stringify({ type: "link-curved", sourceKind: "object", sourceId: out.k1, targetKind: "object", targetId: out.k2 }) }) });
    out.link = link.id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return out;
  });
  await page.waitForTimeout(500);
  const sel = (kind, id) => (kind === "object" ? `.wb-object[data-id="${id}"]` : `.sketch-group[data-id="${id}"]`);
  const opacity = (kind, id) => page.evaluate(([s]) => { const el = document.querySelector(s); return el ? Number(getComputedStyle(el).opacity) : null; }, [sel(kind, id)]);

  // --- The server bounds ----------------------------------------------------------------------------------
  const refused = await page.evaluate(async () => {
    const b = window.currentBoardId;
    const post = (tags) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "x", tags }, board_id: b, x: 0, y: 0, z: 1, width: 100, height: 40 }) }).then(() => 200, () => 422);
    const sketch = (tags) => apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 0, data: JSON.stringify({ type: "link-curved", tags }) }) }).then(() => 200, () => 422);
    return { many: await post(Array.from({ length: 21 }, (_, i) => `t${i}`)), long: await post(["x".repeat(41)]), empty: await post([""]), sketchLong: await sketch(["x".repeat(41)]) };
  });
  errors.length = 0; // the four refusals above log their own 422s
  check("the server refuses 21 tags, a 41-character tag and an empty one", refused.many === 422 && refused.long === 422 && refused.empty === 422 && refused.sketchLong === 422, refused);

  // --- Tags: edit through the Data tab, then filter -------------------------------------------------------
  await page.evaluate((id) => { wbFormatOpen("data"); wbSelectExactly([["object", wbFindItem("object", id)]]); wbFormatSyncSoon(); }, ids.u1);
  await page.waitForTimeout(400);
  const hasField = await page.evaluate(() => { const f = document.getElementById("wb-fmt-tag-input"); return Boolean(f) && !f.closest("[hidden]"); });
  check("the Data tab shows the tag field for a text box", hasField);
  await page.fill("#wb-fmt-tag-input", "gamma, alpha");
  await page.press("#wb-fmt-tag-input", "Enter");
  await page.waitForTimeout(500);
  const saved = await page.evaluate((id) => wbFindItem("object", id).data.tags, ids.u1);
  check("Enter saves two tags on the item", JSON.stringify(saved) === JSON.stringify(["gamma", "alpha"]), saved);
  const chips = await page.evaluate(() => [...document.querySelectorAll("#wb-fmt-tags .wb-tag-chip")].map((c) => c.textContent.trim()));
  check("each tag is a chip in the Data tab", chips.join() === "gamma,alpha", chips);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(500);
  const undone = await page.evaluate((id) => wbFindItem("object", id).data.tags || null, ids.u1);
  check("one Undo takes both tags back", undone === null, undone);
  await page.evaluate(() => wbRedo());
  await page.waitForTimeout(500);

  await page.evaluate(() => { wbSelectExactly([]); wbOpenBoardSearch(); });
  await page.waitForTimeout(300);
  const options = await page.evaluate(() => { const s = document.getElementById("wb-search-tag"); s.dispatchEvent(new Event("focus")); return [...s.options].map((o) => o.textContent); });
  check("the find bar lists the tags in use with counts", options.join("|") === "Any tag|alpha (3)|beta (1)|gamma (1)", options);
  const barBox = await page.evaluate(() => { const r = document.getElementById("wb-search-bar").getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), vw: innerWidth }; });
  check("the find bar still fits the window with the new controls", barBox.right <= barBox.vw && barBox.h < 120, barBox);
  await page.selectOption("#wb-search-tag", "beta");
  await page.waitForTimeout(300);
  const dim = { tagged: await opacity("object", ids.t2), other: await opacity("object", ids.t1), plain: await opacity("object", ids.u1), frame: await opacity("object", ids.f1) };
  check("the tag filter keeps the tagged item at 1 and dims the rest to 0.25", dim.tagged === 1 && dim.other === 0.25 && dim.plain === 0.25 && dim.frame === 0.25, dim);
  const pressable = await page.evaluate((id) => getComputedStyle(document.querySelector(`.wb-object[data-id="${id}"]`)).pointerEvents, ids.t1);
  check("a dimmed item stays pressable", pressable !== "none", pressable);
  await page.selectOption("#wb-search-tag", "");
  await page.waitForTimeout(200);
  check("Any tag brings every item back to 1", (await opacity("object", ids.t1)) === 1 && (await opacity("object", ids.u1)) === 1);
  await page.selectOption("#wb-search-tag", "alpha");
  await page.click("#wb-search-close");
  await page.waitForTimeout(300);
  check("closing the bar clears the filter", (await opacity("object", ids.u1)) === 1);
  const cmds = await page.evaluate(() => ["edit-tags", "filter-tag", "collapse-frame", "expand-frame", "find-in-frame"].map((id) => WB_COMMANDS.some((c) => c.id === id)));
  check("Ctrl+K has the five new commands", cmds.every(Boolean), cmds);

  // --- Collapse -------------------------------------------------------------------------------------------
  const frameRect = (id) => page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; }, sel("object", id));
  const display = (kind, id) => page.evaluate((s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).display : "gone"; }, sel(kind, id));
  const k = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
  const full = await frameRect(ids.f1);
  await page.evaluate((id) => { wbSelectExactly([["object", wbFindItem("object", id)]]); }, ids.f1);
  await page.evaluate(() => wbRunCommand("collapse-frame"));
  await page.waitForTimeout(600);
  const bar = await frameRect(ids.f1);
  check("a folded frame is its title bar (40 board units)", Math.abs(bar.h - 40 * k) <= 2 && bar.w === full.w, { bar, full, k });
  const hid = [await display("object", ids.k1), await display("object", ids.k2), await display("sketch", ids.link)];
  check("its two boxes and the connector between them are hidden", hid.every((d) => d === "none"), hid);
  check("a box outside the frame and the other frame stay", (await display("object", ids.t1)) !== "none" && (await display("object", ids.k3)) !== "none");
  const counted = await page.evaluate((s) => document.querySelector(s).dataset.folded, sel("object", ids.f1));
  check("the bar says how many items it hides", counted === "2 items", counted);
  const svg = await page.evaluate(() => wbBuildExportSvg("all").svg);
  check("the export skips what the fold hides and keeps the rest", !svg.includes("needle one") && !svg.includes("needle two") && svg.includes("needle three") && svg.includes("Alpha frame"), svg.length);
  const selectAll = await page.evaluate(() => { wbSelectAllItems(); const keys = [...wbMultiSelection]; wbSelectExactly([]); return keys; });
  check("Select all skips the hidden items", !selectAll.includes(`object:${ids.k1}`) && selectAll.includes(`object:${ids.k3}`), selectAll.length);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(600);
  const back = await frameRect(ids.f1);
  const shown = [await display("object", ids.k1), await display("object", ids.k2), await display("sketch", ids.link)];
  check("one Undo restores the frame's height and shows all three again", Math.abs(back.h - full.h) <= 1 && shown.every((d) => d !== "none"), { back, full, shown });
  await page.evaluate(() => wbRedo());
  await page.waitForTimeout(600);
  check("Redo folds it again", Math.abs((await frameRect(ids.f1)).h - bar.h) <= 1 && (await display("object", ids.k1)) === "none");
  // Dragging the folded bar carries what it hides.
  const moved = await page.evaluate(async (id) => {
    const f = wbFindItem("object", id);
    const keys = wbFrameContents(f);
    return keys.length;
  }, ids.f1);
  check("the folded frame still carries its two boxes on a drag", moved === 2, moved);
  await page.evaluate((id) => { wbSelectExactly([["object", wbFindItem("object", id)]]); wbFormatSyncSoon(); }, ids.f1);
  await page.waitForTimeout(300);
  const box = await page.evaluate(() => document.getElementById("wb-fmt-collapse")?.checked);
  check("the Format panel's Collapsed box is ticked", box === true, box);
  await page.evaluate(() => wbRunCommand("expand-frame"));
  await page.waitForTimeout(600);
  const open = await frameRect(ids.f1);
  check("Expand puts the full height back and shows the items", Math.abs(open.h - full.h) <= 1 && (await display("object", ids.k1)) !== "none", open);

  // --- The drop highlight ---------------------------------------------------------------------------------
  await page.evaluate(() => { wbSelectExactly([]); wbSelectToolRef?.("select"); });
  const pos = await page.evaluate(([a, f]) => {
    const r = document.querySelector(`.wb-object[data-id="${a}"]`).getBoundingClientRect();
    const fr = document.querySelector(`.wb-object[data-id="${f}"]`).getBoundingClientRect();
    return { sx: r.left + r.width / 2, sy: r.top + r.height / 2, fx: fr.left + fr.width / 2, fy: fr.top + fr.height * 0.8 };
  }, [ids.u1, ids.f2]);
  await page.mouse.move(pos.sx, pos.sy);
  await page.mouse.down();
  await page.mouse.move(pos.sx + 10, pos.sy - 20, { steps: 3 });
  const idle = await page.evaluate((f) => document.querySelector(`.wb-object[data-id="${f}"]`).classList.contains("wb-drop-target"), ids.f2);
  await page.mouse.move(pos.fx, pos.fy, { steps: 12 });
  await page.waitForTimeout(150);
  const over = await page.evaluate((f) => {
    const el = document.querySelector(`.wb-object[data-id="${f}"]`);
    const cs = getComputedStyle(el);
    return { on: el.classList.contains("wb-drop-target"), outline: cs.outlineStyle, width: cs.outlineWidth, others: document.querySelectorAll(".wb-drop-target").length };
  }, ids.f2);
  check("no highlight until the carried box is over a frame", idle === false);
  check("a frame under the carried box wears the drop class (2px outline, one frame only)", over.on && over.outline === "solid" && over.width === "2px" && over.others === 1, over);
  await page.mouse.move(pos.sx, pos.sy + 120, { steps: 8 });
  await page.waitForTimeout(100);
  check("leaving the frame takes the class off", (await page.evaluate(() => document.querySelectorAll(".wb-drop-target").length)) === 0);
  await page.mouse.move(pos.fx, pos.fy, { steps: 8 });
  await page.waitForTimeout(100);
  await page.mouse.up();
  await page.waitForTimeout(500);
  check("releasing clears it", (await page.evaluate(() => document.querySelectorAll(".wb-drop-target").length)) === 0);

  // --- Find in this frame ---------------------------------------------------------------------------------
  await page.evaluate(() => wbUndo()); // the drop above moved the box into the second frame: put it back
  await page.waitForTimeout(500);
  await page.evaluate((id) => { wbSelectExactly([["object", wbFindItem("object", id)]]); wbOpenBoardSearch({ replace: true }); }, ids.f1);
  await page.waitForTimeout(300);
  await page.fill("#wb-search-input", "needle");
  await page.waitForTimeout(300);
  const whole = await page.textContent("#wb-search-count");
  check("without the scope, find spans every frame (3 matches)", /of 3$/.test(whole.trim()), whole);
  await page.click("#wb-search-frame");
  await page.waitForTimeout(300);
  const scoped = await page.textContent("#wb-search-count");
  const pressed = await page.getAttribute("#wb-search-frame", "aria-pressed");
  check("with This frame on, only the selected frame's 2 matches count", pressed === "true" && /of 2$/.test(scoped.trim()), { scoped, pressed });
  await page.fill("#wb-replace-input", "pin");
  await page.click("#wb-replace-all");
  await page.waitForTimeout(700);
  const texts = await page.evaluate((i) => Object.fromEntries(["k1", "k2", "k3"].map((n) => [n, wbFindItem("object", i[n]).data.content])), ids);
  check("Replace all stays inside the frame", texts.k1 === "pin one" && texts.k2 === "pin two" && texts.k3 === "needle three", texts);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(500);
  const undoneText = await page.evaluate((i) => ["k1", "k2"].map((n) => wbFindItem("object", i[n]).data.content).join("|"), ids);
  check("one Undo takes the replace back", undoneText === "needle one|needle two", undoneText);
  await page.click("#wb-search-frame");
  await page.waitForTimeout(300);
  check("turning the scope off finds all 3 again", /of 3$/.test((await page.textContent("#wb-search-count")).trim()));
  await page.evaluate(() => { wbSelectExactly([]); });
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
