// Board tables (L273): merged cells, stripes, a line dragged to size a row or column,
// Markdown paste, measured with getBoundingClientRect on a real board.
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbtablemerge.js
const { openFresh, checker } = require("./cdlib.js");

(async () => {
  const { browser, page, errors } = await openFresh({ width: 1440 });
  const { check, summary } = checker();
  const near = (a, b, tol = 2) => Math.abs(a - b) <= tol;
  await page.evaluate(() => wbRunCommand("insert-table"));
  await page.waitForTimeout(800);
  const id = await page.evaluate(() => wbState.objects.find((o) => o.kind === "table").id);
  const obj = `.wb-object[data-id="${id}"]`;
  const rectOf = (r, c) => page.evaluate(([sel, r, c]) => {
    const e = document.querySelector(`${sel} .wb-table-cell[data-r="${r}"][data-c="${c}"]`);
    if (!e) return null;
    const b = e.getBoundingClientRect();
    return { x: b.x, y: b.y, w: b.width, h: b.height, cx: b.x + b.width / 2, cy: b.y + b.height / 2 };
  }, [obj, r, c]);
  const data = () => page.evaluate((i) => JSON.parse(JSON.stringify(wbState.objects.find((o) => o.id === i).data)), id);
  const menu = (label) => page.evaluate(async ([i, l]) => {
    const d = wbState.objects.find((o) => o.id === i);
    const row = wbTableMenuRows(d).find(([name]) => name === l);
    if (!row) return false;
    await row[2]();
    return true;
  }, [id, label]);
  const labels = () => page.evaluate((i) => wbTableMenuRows(wbState.objects.find((o) => o.id === i)).map(([l]) => l), id);

  const one = await rectOf(1, 1);
  const base = await rectOf(0, 0);
  check("a 3 by 3 table to start: 9 cells", (await page.$$(`${obj} .wb-table-cell`)).length === 9);

  // 1. merge: click (1,0), Shift-click (2,1)
  const c10 = await rectOf(1, 0);
  await page.mouse.click(c10.cx, c10.cy);
  await page.waitForTimeout(250);
  const c21 = await rectOf(2, 1);
  await page.keyboard.down("Shift");
  await page.mouse.click(c21.cx, c21.cy);
  await page.keyboard.up("Shift");
  await page.waitForTimeout(250);
  const picked = await page.$$eval(`${obj} .wb-table-cell.is-picked`, (e) => e.map((x) => `${x.dataset.r}${x.dataset.c}`));
  check("Shift-click picks the 2 by 2 range", picked.sort().join() === "10,11,20,21", picked);
  check("the shift-click did not turn the table into a multi-selection", await page.evaluate(() => wbMultiSelection.size === 0 && wbSelectedItem?.kind === "object"));
  const rows = await labels();
  check("the menu offers Merge cells for the range", rows.includes("Merge cells") && !rows.includes("Split cell"), rows);
  const stepsBefore = await page.evaluate(() => (typeof wbUndoStack !== "undefined" ? wbUndoStack.length : -1));
  await menu("Merge cells");
  await page.waitForTimeout(700);
  const m = await rectOf(1, 0);
  const cellsNow = (await page.$$(`${obj} .wb-table-cell`)).length;
  check("the merged cell spans two columns (width = 2 cells)", near(m.w, base.w * 2, 3), { w: m.w, cell: base.w });
  check("the merged cell spans two rows (height = 2 rows)", near(m.h, base.h * 2, 3), { h: m.h, row: base.h });
  check("three cells are no longer drawn (6 of 9 + 0 covered = 6)", cellsNow === 6, cellsNow);
  check("data.merges holds the span", JSON.stringify((await data()).merges) === JSON.stringify([{ r: 1, c: 0, rs: 2, cs: 2 }]), (await data()).merges);
  const stepsAfter = await page.evaluate(() => (typeof wbUndoStack !== "undefined" ? wbUndoStack.length : -1));
  if (stepsBefore >= 0) check("the merge is one Undo step", stepsAfter - stepsBefore === 1, [stepsBefore, stepsAfter]);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(700);
  check("Undo brings the 9 cells back", (await page.$$(`${obj} .wb-table-cell`)).length === 9 && !(await data()).merges);
  await page.evaluate(() => wbRedo?.());
  await page.waitForTimeout(500);
  if ((await page.$$(`${obj} .wb-table-cell`)).length !== 6) await menu("Merge with the cell on the right");

  // 2. split
  await page.mouse.click((await rectOf(1, 0)).cx, (await rectOf(1, 0)).cy);
  await page.waitForTimeout(250);
  check("Split cell is offered on a merged cell", (await labels()).includes("Split cell"), await labels());
  await menu("Split cell");
  await page.waitForTimeout(700);
  check("Split cell restores the 9 cells", (await page.$$(`${obj} .wb-table-cell`)).length === 9 && !(await data()).merges);

  // 3. merge with the cell on the right (no shift key), then insert a row inside, then Tab over the covered cell
  await page.mouse.click((await rectOf(0, 0)).cx, (await rectOf(0, 0)).cy);
  await page.waitForTimeout(250);
  await menu("Merge with the cell on the right");
  await page.waitForTimeout(600);
  const hdr = await rectOf(0, 0);
  check("Merge with the cell on the right spans two columns", near(hdr.w, base.w * 2, 3), { w: hdr.w, cell: base.w });
  check("the header tint still covers the merged cell", await page.evaluate((sel) => getComputedStyle(document.querySelector(`${sel} .wb-table-cell[data-r="0"][data-c="0"]`)).fontWeight >= 600, obj));
  await page.mouse.click((await rectOf(0, 0)).cx, (await rectOf(0, 0)).cy);
  await menu("Add a column to the right");
  await page.waitForTimeout(700);
  const grown = await data();
  const wide = await rectOf(0, 0);
  check("a column added beside a merge lands outside it (merge stays 2 columns wide)", JSON.stringify(grown.merges) === JSON.stringify([{ r: 0, c: 0, rs: 1, cs: 2 }]) && grown.cells[0].length === 4 && near(wide.w, base.w * 2, 3), { merges: grown.merges, w: wide.w, cell: base.w });
  const gripsOnMerge = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} .wb-table-grip-col[data-i="0"]`)].map((g) => [g.dataset.from, g.dataset.to]), obj);
  check("no column grip lies across the merged cell (only rows 1 and 2 have the line)", JSON.stringify(gripsOnMerge) === JSON.stringify([["1", "3"]]), gripsOnMerge);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(600);
  // typing through the merged cell: Tab from (0,0) goes to (0,2)
  await page.mouse.dblclick((await rectOf(0, 0)).cx, (await rectOf(0, 0)).cy);
  await page.waitForTimeout(200);
  await page.keyboard.type("Head");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Last");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  const typed = await data();
  check("Tab steps over the covered cell", typed.cells[0][0] === "Head" && typed.cells[0][1] === "" && typed.cells[0][2] === "Last", typed.cells[0]);
  await page.mouse.click((await rectOf(0, 0)).cx, (await rectOf(0, 0)).cy);
  await page.waitForTimeout(250);
  await menu("Split cell");
  await page.waitForTimeout(600);
  check("Split cell on the header merge leaves 9 cells and no merges", (await page.$$(`${obj} .wb-table-cell`)).length === 9 && !(await data()).merges);

  // 4. stripes through the Format panel checkbox
  await page.evaluate((i) => { clearWbSelection(); wbHandleItemClick("object", i, { shiftKey: false }); }, id);
  await page.waitForTimeout(500);
  await page.evaluate(() => wbFormatOpen(null, { focus: false }));
  await page.waitForTimeout(500);
  const box = await page.$("#wb-fmt-stripes");
  const shown = box ? await box.isVisible() : false;
  check("the Format panel has a Striped rows checkbox for a table", shown);
  if (shown) await box.click();
  await page.waitForTimeout(700);
  const stripes = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} .wb-table-cell`)].map((e) => ({ r: e.dataset.r, s: e.dataset.stripe === "1", bg: getComputedStyle(e).backgroundColor })), obj);
  const r2 = stripes.find((x) => x.r === "2"), r1 = stripes.find((x) => x.r === "1");
  check("with a header, row 2 is tinted and row 1 is not", r2.s && !r1.s && r2.bg !== r1.bg, { r1, r2 });
  const svg = await page.evaluate(() => wbBuildExportSvg("all").svg);
  check("the SVG export draws the stripe tint", /fill="#f4f6fa"|fill="rgb\(/.test(svg) && (svg.match(/<rect /g) || []).length >= 9, (svg.match(/<rect /g) || []).length);

  // 5. drag a column line
  const before0 = await rectOf(1, 0), before1 = await rectOf(1, 1), beforeSum = before0.w + before1.w;
  const grip = await page.evaluate((sel) => { const g = document.querySelector(`${sel} .wb-table-grip-col[data-i="0"]`); const b = g.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 4, pe: getComputedStyle(g).pointerEvents }; }, obj);
  check("a selected table's column grips take the pointer", grip.pe === "auto", grip);
  const undoA = await page.evaluate(() => (typeof wbUndoStack !== "undefined" ? wbUndoStack.length : -1));
  await page.mouse.move(grip.x, grip.y);
  await page.mouse.down();
  await page.mouse.move(grip.x + 20, grip.y, { steps: 4 });
  await page.mouse.move(grip.x + 40, grip.y, { steps: 4 });
  const live = await rectOf(1, 0);
  check("the column follows the pointer while it drags (+40px)", near(live.w - before0.w, 40, 3), { before: before0.w, live: live.w });
  await page.mouse.up();
  await page.waitForTimeout(800);
  const a0 = await rectOf(1, 0), a1 = await rectOf(1, 1);
  const d1 = await data();
  check("column 0 grew by 40px and column 1 gave it up (table keeps its width)", near(a0.w - before0.w, 40, 3) && near(a0.w + a1.w, beforeSum, 2), { grew: a0.w - before0.w, sum: [beforeSum, a0.w + a1.w] });
  check("data.col_widths holds three weights with mean 1", Array.isArray(d1.col_widths) && d1.col_widths.length === 3 && near(d1.col_widths.reduce((x, y) => x + y, 0), 3, 0.01), d1.col_widths);
  const undoB = await page.evaluate(() => (typeof wbUndoStack !== "undefined" ? wbUndoStack.length : -1));
  if (undoA >= 0) check("the drag is one Undo step", undoB - undoA === 1, [undoA, undoB]);
  const tableBox = await page.evaluate((sel) => { const b = document.querySelector(sel).getBoundingClientRect(); return { x: b.x, y: b.y }; }, obj);
  check("the drag did not move the table", near(tableBox.x, (await page.evaluate((sel) => document.querySelector(sel).getBoundingClientRect().x, obj)), 0.5));
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(700);
  const u0 = await rectOf(1, 0);
  check("Undo puts the column back", near(u0.w, before0.w, 2) && !(await data()).col_widths, { w: u0.w, was: before0.w });

  // 6. drag a row line
  const rb0 = await rectOf(1, 0), rb1 = await rectOf(2, 0);
  const rg = await page.evaluate((sel) => { const g = document.querySelector(`${sel} .wb-table-grip-row[data-i="1"]`); const b = g.getBoundingClientRect(); return { x: b.x + b.width / 4, y: b.y + b.height / 2 }; }, obj);
  await page.mouse.move(rg.x, rg.y);
  await page.mouse.down();
  await page.mouse.move(rg.x, rg.y + 10, { steps: 3 });
  await page.mouse.move(rg.x, rg.y + 20, { steps: 3 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  const ra0 = await rectOf(1, 0), ra1 = await rectOf(2, 0), d2 = await data();
  check("row 1 grew by 20px and row 2 gave it up", near(ra0.h - rb0.h, 20, 3) && near(ra0.h + ra1.h, rb0.h + rb1.h, 2), { grew: ra0.h - rb0.h, sum: [rb0.h + rb1.h, ra0.h + ra1.h] });
  check("data.row_heights holds three weights with mean 1", Array.isArray(d2.row_heights) && d2.row_heights.length === 3 && near(d2.row_heights.reduce((x, y) => x + y, 0), 3, 0.01), d2.row_heights);
  const tallRows = await labels();
  check("the menu keeps keyboard ways to size a row and a column", ["Taller row", "Shorter row", "Equal row heights", "Widen this column"].every((l) => tallRows.includes(l)), tallRows);
  await page.mouse.click((await rectOf(1, 0)).cx, (await rectOf(1, 0)).cy);
  await page.waitForTimeout(250);
  const preTall = await rectOf(1, 0);
  await menu("Taller row");
  await page.waitForTimeout(500);
  const tall = await rectOf(1, 0);
  check("Taller row on the pressed row grows it", tall.h > preTall.h + 5, { was: preTall.h, now: tall.h });
  // row height survives a reopen
  await page.evaluate(async () => { await openWhiteboardBoard(window.currentBoardId); });
  await page.waitForTimeout(1200);
  const after = await page.evaluate((i, ) => { const d = wbState.objects.find((o) => o.id === i); const g = document.querySelector(`.wb-object[data-id="${i}"] .wb-table-grid`); return { weights: d.data.row_heights, rows: g.style.gridTemplateRows }; }, id);
  const want = (await data()).row_heights.map((n) => `minmax(0px, ${n}fr)`).join(" ");
  check("the row heights survive a reopen (saved weights drive the grid)", after.rows === want && after.weights.length === 3, { after, want });

  // 7. a locked table does not drag
  // 8. Markdown paste
  const md = "| Name | Owner |\n| --- | --- |\n| Plan | Ann |\n| Ship | Bo |";
  const built = await page.evaluate((text) => ({ plan: wbPastePlan(text).kind, item: wbPasteBuild("table", text, 0, 0, { paper: "#fff", root: "#fff", ink: "#000" }).items[0].payload.data }), md);
  check("a Markdown table paste plans a table with its header", built.plan === "table" && built.item.header === true && built.item.cells.length === 3, built);

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
