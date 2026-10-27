// wb-1027: a connector label drags by its words; a drawn shape is selected and the tool returns to Select.
//   BASE=http://127.0.0.1:8787 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1027-drawlabel.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, errors, board } = await openBoard();
  const ids = await page.evaluate(async (bid) => {
    const rect = (x, y) => `M ${x} ${y} L ${x + 120} ${y} L ${x + 120} ${y + 70} L ${x} ${y + 70} Z`;
    const shape = async (x, y) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: rect(x, y), shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const a = await shape(0, 0); const b = await shape(420, 0);
    const link = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ type: "link-straight", sourceId: a, sourceKind: "sketch", targetId: b, targetKind: "sketch", color: "#222222", width: 2, endCap: "arrow", label: "test Label" }),
      x: 0, y: 0, z: 1, board_id: bid }) })).id;
    await fetchWhiteboardState(); renderWhiteboardNow(); wbZoomToFit();
    return { a, b, link };
  }, board.id);
  await page.waitForTimeout(800);
  const labelBox = () => page.evaluate((id) => { const r = document.querySelector(`.sketch-group[data-id="${id}"] .wb-link-label`).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height }; }, ids.link);
  const t = () => page.evaluate((id) => { const s = wbState.sketches.find((q) => q.id === id); return JSON.parse(s.data).label_t; }, ids.link);
  const grips = await page.evaluate(() => document.querySelectorAll(".wb-link-label-handle").length);
  check("no separate label grip exists", grips === 0, grips);

  // Unselected connector: press the words and drag along the line.
  let b0 = await labelBox();
  await page.mouse.move(b0.x, b0.y); await page.mouse.down();
  await page.mouse.move(b0.x + 40, b0.y + 1, { steps: 6 }); await page.mouse.move(b0.x + 90, b0.y + 1, { steps: 6 });
  await page.mouse.up(); await page.waitForTimeout(900);
  let b1 = await labelBox(); const t1 = await t();
  console.log("label dx", (b1.x - b0.x).toFixed(1), "label_t", t1, "label width", b0.w.toFixed(1));
  check("dragging the words slides the label", b1.x - b0.x > 60 && t1 > 0.5, [b1.x - b0.x, t1]);
  const sel = await page.evaluate(() => wbSelectedItem && wbSelectedItem.kind + ":" + wbSelectedItem.id);
  check("the connector is selected after the slide", sel === "sketch:" + ids.link, sel);
  // Undo restores in one step.
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(700);
  const t2 = await t(); const b2 = await labelBox();
  check("one undo returns the label to the middle", (t2 === undefined || Math.abs(t2 - 0.5) < 0.01) && Math.abs(b2.x - b0.x) < 2, [t2, b2.x - b0.x]);
  // Click selects, no move saved.
  await page.evaluate(() => clearWbSelection());
  b0 = await labelBox(); await page.mouse.click(b0.x, b0.y); await page.waitForTimeout(400);
  const sel2 = await page.evaluate(() => wbSelectedItem && wbSelectedItem.id); const t3 = await t();
  check("a click on the words selects and saves no move", sel2 === ids.link && (t3 === undefined || Math.abs(t3 - 0.5) < 0.01), [sel2, t3]);
  // Double-click edits.
  await page.mouse.dblclick(b0.x, b0.y); await page.waitForTimeout(500);
  const editor = await page.evaluate(() => Boolean(document.querySelector(".wb-link-label-editor")));
  const bends = await page.evaluate((id) => (JSON.parse(wbState.sketches.find((q) => q.id === id).data).points || []).length, ids.link);
  check("a double-click opens the label editor, adds no bend", editor && bends === 0, [editor, bends]);
  await page.keyboard.press("Escape"); await page.waitForTimeout(300);

  // Drawn shape: rectangle selected, tool returns to Select; pen keeps its tool.
  await page.evaluate(() => clearWbSelection());
  await page.keyboard.press("r");
  const before = await page.evaluate(() => wbState.sketches.length);
  await page.mouse.move(300, 600); await page.mouse.down(); await page.mouse.move(380, 650, { steps: 5 }); await page.mouse.move(460, 700, { steps: 5 }); await page.mouse.up();
  await page.waitForTimeout(900);
  const after = await page.evaluate(() => ({ n: wbState.sketches.length, tool: window.currentTool, sel: wbSelectedItem && wbSelectedItem.kind, selId: wbSelectedItem && wbSelectedItem.id, last: wbState.sketches[wbState.sketches.length - 1].id }));
  console.log(JSON.stringify(after));
  check("rectangle drawn, selected, tool is select", after.n === before + 1 && after.tool === "select" && after.sel === "sketch" && after.selId === after.last, after);
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(700);
  const un = await page.evaluate(() => wbState.sketches.length);
  check("one undo removes the shape", un === before, [un, before]);
  await page.keyboard.press("p");
  await page.mouse.move(300, 600); await page.mouse.down(); await page.mouse.move(340, 640, { steps: 5 }); await page.mouse.up();
  await page.waitForTimeout(700);
  const pen = await page.evaluate(() => ({ tool: window.currentTool, n: wbState.sketches.length }));
  check("the pen keeps its tool", pen.tool === "draw" && pen.n === before + 1, pen);
  for (const key of ["l", "o", "d"]) {
    await page.keyboard.press(key);
    await page.mouse.move(300, 700); await page.mouse.down(); await page.mouse.move(360, 740, { steps: 4 }); await page.mouse.move(420, 780, { steps: 4 }); await page.mouse.up();
    await page.waitForTimeout(700);
    const r = await page.evaluate(() => ({ tool: window.currentTool, sel: wbSelectedItem && wbSelectedItem.kind }));
    check(`shape tool ${key} returns to select with a selection`, r.tool === "select" && r.sel === "sketch", r);
  }
  check("no page errors", errors.length === 0, errors);
  summary(); await browser.close();
})();
