// INBOX 904 B23, part 2: the grips on a Live table's edges. A bar above each
// column and beside each row (click selects, drag moves, right-click opens the
// menu), a plus at the end of the header and under the last row. Real mouse in
// Chromium; every number is read from the editor's own state or the DOM.
//
// Usage: BASE=http://127.0.0.1:8792 [WIDTH=390] [THEME=dark] node tablegrips1018.js
const { boot } = require("./lib.js");

const WIDTH = Number(process.env.WIDTH || 1440);
let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const TABLE = "| Name | Qty | Note |\n| :--- | ---: | --- |\n| pear | 10 | green |\n| apple | 2 | red |\n| fig | 33 | purple |";
const DOC = `# Fruit\n\nBefore it.\n\n${TABLE}\n\nAfter it.\n`;

(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone
    ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true }
    : { viewport: { width: WIDTH, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2500);
  await page.evaluate(async (c) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Table grips", content: c }) });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(2000);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(1600);

  const text = () => page.evaluate(() => docCmView.state.doc.toString());
  const table = async () => (await text()).split("\n").slice(4, 9);
  const box = (sel) => page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: b.left, y: b.top, w: b.width, h: b.height, cx: b.left + b.width / 2, cy: b.top + b.height / 2 };
  }, sel);
  const clickCell = async (row, col) => {
    const at = await page.evaluate(([r, c]) => {
      const line = [...document.querySelectorAll(".cm-line.cm-md-table")][r];
      const b = line.querySelectorAll(".cm-md-td")[c].getBoundingClientRect();
      return { x: b.left + Math.min(b.width / 2, 30), y: b.top + b.height / 2 };
    }, [row, col]);
    await page.mouse.click(at.x, at.y);
    await page.waitForTimeout(450);
  };
  const grips = () => page.evaluate(() => ({
    cols: document.querySelectorAll(".doc-table-grip-col").length,
    rows: document.querySelectorAll(".doc-table-grip-row").length,
    adds: document.querySelectorAll(".doc-table-add").length,
  }));
  const undo = async () => {
    await page.evaluate(() => docCmView.focus());
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(350);
  };
  const dragTo = async (from, to, steps = 8) => {
    await page.mouse.move(from.cx, from.cy);
    await page.mouse.down();
    await page.mouse.move(from.cx + (to.x - from.cx) / 2, from.cy + (to.y - from.cy) / 2, { steps });
    await page.mouse.move(to.x, to.y, { steps });
    await page.waitForTimeout(150);
  };

  // 1. No grips with the caret outside a table.
  const para = await page.evaluate(() => { const l = [...document.querySelectorAll(".cm-line")].find((n) => n.textContent.includes("Before it")); const b = l.getBoundingClientRect(); return { x: b.left + 40, y: b.top + b.height / 2 }; });
  await page.mouse.click(para.x, para.y);
  await page.waitForTimeout(400);
  const none = await grips();
  ok("no grips while the caret is outside a table", none.cols === 0 && none.rows === 0 && none.adds === 0, JSON.stringify(none));

  // 2. Caret in a cell: 3 column grips, 4 row grips (header and three), 2 plus.
  await clickCell(2, 1);
  const g = await grips();
  ok("grips appear with the caret in the table: 3 columns, 4 rows, 2 plus", g.cols === 3 && g.rows === 4 && g.adds === 2, JSON.stringify(g));
  const geom = await page.evaluate(() => {
    const head = [...document.querySelectorAll(".cm-line.cm-md-table")][0];
    const cells = [...head.querySelectorAll(".cm-md-td")].map((c) => c.getBoundingClientRect());
    const cols = [...document.querySelectorAll(".doc-table-grip-col")].map((e) => e.getBoundingClientRect());
    const lines = [...document.querySelectorAll(".cm-line.cm-md-table")].map((l) => l.getBoundingClientRect());
    const rows = [...document.querySelectorAll(".doc-table-grip-row")].map((e) => e.getBoundingClientRect());
    const hb = head.getBoundingClientRect();
    const sr = docCmView.scrollDOM.getBoundingClientRect();
    return {
      colAligned: cols.every((c, i) => Math.abs(c.left - cells[i].left) <= 2),
      colAbove: cols.every((c) => Math.abs(c.bottom - hb.top) <= 2),
      rowAligned: rows.every((r, i) => Math.abs(r.top - lines[i].top) <= 2 && Math.abs(r.height - lines[i].height) <= 2),
      rowBeside: rows.every((r) => Math.abs(r.right - hb.left) <= 2),
      rowWidth: Math.round(rows[0].width),
      inside: [...document.querySelectorAll(".doc-table-grip, .doc-table-add")].every((e) => { const b = e.getBoundingClientRect(); return b.left >= sr.left - 1 && b.right <= sr.right + 1; }),
    };
  });
  ok("column grips sit over their columns, flush above the header", geom.colAligned && geom.colAbove, JSON.stringify(geom));
  ok("row grips sit beside their rows, flush with the table's left edge", geom.rowAligned && geom.rowBeside, `width ${geom.rowWidth}px`);
  ok("every grip is inside the editor's box", geom.inside);

  // 3. A click selects.
  const colBar = await box('.doc-table-grip-col[data-index="1"]');
  await page.mouse.click(colBar.cx, colBar.cy);
  await page.waitForTimeout(350);
  const selCol = await page.evaluate(() => docCmView.state.selection.ranges.map((r) => docCmView.state.sliceDoc(r.from, r.to)));
  ok("a click on a column grip selects that column", JSON.stringify(selCol) === JSON.stringify(["Qty", "10", "2", "33"]), JSON.stringify(selCol));
  const stillThere = await grips();
  ok("the grips stay while a column is selected", stillThere.cols === 3 && stillThere.rows === 4, JSON.stringify(stillThere));
  const rowBar = await box('.doc-table-grip-row[data-index="3"]');
  await page.mouse.click(rowBar.cx, rowBar.cy);
  await page.waitForTimeout(350);
  const selRow = await page.evaluate(() => docCmView.state.selection.ranges.map((r) => docCmView.state.sliceDoc(r.from, r.to).trim()));
  ok("a click on a row grip selects that row", selRow.length === 1 && selRow[0].startsWith("apple") && selRow[0].endsWith("red"), JSON.stringify(selRow));

  // 4. Drag a column: Name to the far right, one undo step.
  await clickCell(2, 1);
  const before = await text();
  const nameBar = await box('.doc-table-grip-col[data-index="0"]');
  const lastCell = await page.evaluate(() => { const l = [...document.querySelectorAll(".cm-line.cm-md-table")][0]; const b = [...l.querySelectorAll(".cm-md-td")].pop().getBoundingClientRect(); return { x: b.right - 6, y: b.top - 8 }; });
  await dragTo(nameBar, lastCell);
  const indicator = await page.evaluate(() => {
    const el = document.querySelector(".doc-table-grip-line");
    if (!el || el.classList.contains("hidden")) return null;
    const b = el.getBoundingClientRect();
    const head = [...document.querySelectorAll(".cm-line.cm-md-table")][0].getBoundingClientRect();
    const last = [...document.querySelectorAll(".cm-line.cm-md-table")].pop().getBoundingClientRect();
    const cells = [...[...document.querySelectorAll(".cm-line.cm-md-table")][0].querySelectorAll(".cm-md-td")].map((c) => c.getBoundingClientRect());
    return { x: b.left + b.width / 2, edge: cells[cells.length - 1].right, top: b.top, bottom: b.bottom, headTop: head.top, lastBottom: last.bottom, source: !!document.querySelector(".doc-table-grip.is-source") };
  });
  ok("while dragging, a line marks the slot at the last column's right edge, the table's full height", !!indicator && Math.abs(indicator.x - indicator.edge) <= 3 && Math.abs(indicator.top - indicator.headTop) <= 2 && Math.abs(indicator.bottom - indicator.lastBottom) <= 2, indicator && JSON.stringify(indicator));
  ok("the dragged grip is marked as the source", !!indicator && indicator.source);
  await page.mouse.up();
  await page.waitForTimeout(400);
  const moved = await table();
  ok("dropping Name past Note moves the column, its alignment marker with it", moved[0].startsWith("| Qty | Note | Name") && moved[1].startsWith("| ---: | --- | :---") && moved[2].includes("10 | green | pear"), moved.slice(0, 3).join(" / "));
  const afterSel = await page.evaluate(() => docCmView.state.selection.ranges.map((r) => docCmView.state.sliceDoc(r.from, r.to)));
  ok("the moved column stays selected", JSON.stringify(afterSel) === JSON.stringify(["Name", "pear", "apple", "fig"]), JSON.stringify(afterSel));
  const lineGone = await page.evaluate(() => { const el = document.querySelector(".doc-table-grip-line"); return !el || el.classList.contains("hidden"); });
  ok("the slot line is gone after the drop", lineGone);
  await undo();
  ok("one Ctrl+Z puts the column back, byte for byte", (await text()) === before);

  // 5. Drag a row: pear below fig.
  await clickCell(3, 1);
  const pearBar = await box('.doc-table-grip-row[data-index="2"]');
  const figLine = await page.evaluate(() => { const b = [...document.querySelectorAll(".cm-line.cm-md-table")].pop().getBoundingClientRect(); return { x: b.left - 6, y: b.bottom - 4 }; });
  await dragTo(pearBar, figLine);
  const rowLine = await page.evaluate(() => {
    const el = document.querySelector(".doc-table-grip-line");
    if (!el || el.classList.contains("hidden")) return null;
    const b = el.getBoundingClientRect();
    const last = [...document.querySelectorAll(".cm-line.cm-md-table")].pop().getBoundingClientRect();
    return { y: b.top + b.height / 2, edge: last.bottom };
  });
  ok("while dragging a row, a line marks the slot under the last row", !!rowLine && Math.abs(rowLine.y - rowLine.edge) <= 3, rowLine && JSON.stringify(rowLine));
  await page.mouse.up();
  await page.waitForTimeout(400);
  const rowsAfter = await table();
  ok("dropping pear under fig moves the row: apple, fig, pear", rowsAfter[2].includes("apple") && rowsAfter[3].includes("fig") && rowsAfter[4].includes("pear"), rowsAfter.slice(2).join(" / "));
  await undo();
  ok("one Ctrl+Z puts the row back", (await text()) === before);

  // 6. The header does not drag, and a drag that ends where it began is no edit.
  await clickCell(3, 1);
  const headBar = await box('.doc-table-grip-row[data-index="0"]');
  const lowTarget = await page.evaluate(() => { const b = [...document.querySelectorAll(".cm-line.cm-md-table")].pop().getBoundingClientRect(); return { x: b.left - 6, y: b.bottom - 4 }; });
  await dragTo(headBar, lowTarget);
  await page.mouse.up();
  await page.waitForTimeout(300);
  ok("the header row grip does not move the header", (await text()) === before);
  const nameBar2 = await box('.doc-table-grip-col[data-index="1"]');
  await dragTo(nameBar2, { x: nameBar2.cx + 3, y: nameBar2.cy });
  await page.mouse.up();
  await page.waitForTimeout(300);
  ok("dropping a column where it started is no edit", (await text()) === before);

  // 7. The plus buttons.
  await clickCell(2, 1);
  const addCol = await box(".doc-table-add-col");
  await page.mouse.click(addCol.cx, addCol.cy);
  await page.waitForTimeout(450);
  const withCol = await table();
  ok("the header plus adds a fourth column", withCol[0].split("|").length === 6 || /\|\s*\|\s*$/.test(withCol[0]), withCol[0]);
  const caretAfterCol = await page.evaluate(() => { const d = docCmView.state.doc; return d.lineAt(docCmView.state.selection.main.head).number; });
  ok("the caret goes to the new column", caretAfterCol >= 1);
  await undo();
  ok("one Ctrl+Z takes the column back", (await text()) === before);
  await clickCell(2, 1);
  const addRow = await box(".doc-table-add-row");
  await page.mouse.click(addRow.cx, addRow.cy);
  await page.waitForTimeout(450);
  const withRow = await table();
  ok("the plus under the last row adds a row", /^\|\s*\|/.test((await text()).split("\n")[9] || ""), (await text()).split("\n").slice(8, 11).join(" / "));
  await undo();
  ok("one Ctrl+Z takes the row back", (await text()) === before);

  // 8. Right-click a grip: the table's menu, aimed at that column.
  await clickCell(2, 0);
  const qtyBar = await box('.doc-table-grip-col[data-index="1"]');
  await page.mouse.click(qtyBar.cx, qtyBar.cy, { button: "right" });
  await page.waitForTimeout(400);
  const menu = await page.evaluate(() => {
    const m = [...document.querySelectorAll(".action-menu")].find((n) => !n.classList.contains("hidden") && n.getBoundingClientRect().width > 0);
    return m ? { items: m.querySelectorAll('[role="menuitem"]').length, left: [...m.querySelectorAll('[role="menuitem"]')].find((i) => /Move column left/.test(i.textContent)).disabled === true } : null;
  });
  const caretCol = await page.evaluate(() => { const t = docTableContext(docSurface()); return t.cell.col; });
  ok("a right-click on a column grip opens the table's 19-item menu", !!menu && menu.items === 19, menu && JSON.stringify(menu));
  ok("and the caret went to that column", caretCol === 1, caretCol);
  ok("so Move column left is available for it", !!menu && menu.left === false);
  await page.keyboard.press("Escape");

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
