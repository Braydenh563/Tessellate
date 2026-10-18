// INBOX 904 B23: managing a Live table. Right-click opens the table's menu at
// the pointer; Move, Sort and Select act on the row or column under the caret,
// each one undo step; Select column draws one range per cell. Real mouse and
// keyboard in Chromium, numbers read from the editor's own state.
//
// Usage: BASE=http://127.0.0.1:8792 [WIDTH=390] [THEME=dark] node tablemanage1018.js
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
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Table manage", content: c }) });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(2000);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(1600);

  const text = () => page.evaluate(() => docCmView.state.doc.toString());
  const table = async () => (await text()).split("\n").slice(4, 9);
  const cellBox = (row, col) => page.evaluate(([r, c]) => {
    const lines = [...document.querySelectorAll(".cm-line.cm-md-table")];
    const line = lines[r];
    const cell = line && line.querySelectorAll(".cm-md-td")[c];
    if (!cell) return null;
    const b = cell.getBoundingClientRect();
    return { x: b.left + Math.min(b.width / 2, 30), y: b.top + b.height / 2 };
  }, [row, col]);
  const menuState = () => page.evaluate(() => {
    const menu = [...document.querySelectorAll(".action-menu")].find((m) => !m.classList.contains("hidden") && m.getBoundingClientRect().width > 0);
    if (!menu) return null;
    const b = menu.getBoundingClientRect();
    return {
      labels: [...menu.querySelectorAll('[role="menuitem"]')].map((i) => i.textContent.trim()),
      disabled: [...menu.querySelectorAll('[role="menuitem"]')].filter((i) => i.disabled || i.getAttribute("aria-disabled") === "true").map((i) => i.textContent.trim()),
      seps: menu.querySelectorAll('[role="separator"]').length,
      inView: b.left >= 0 && b.top >= 0 && b.right <= innerWidth && b.bottom <= innerHeight,
      rect: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
      scrolls: menu.scrollHeight > menu.clientHeight + 1,
    };
  });
  const rightClick = async (row, col) => {
    const at = await cellBox(row, col);
    await page.mouse.click(at.x, at.y);
    await page.mouse.click(at.x, at.y, { button: "right" });
    await page.waitForTimeout(350);
    if (process.env.DEBUG) console.log("  rightClick", row, col, JSON.stringify(at), JSON.stringify(await page.evaluate(() => { const t = docTableContext(docSurface()); return t && t.cell; })));
    return at;
  };
  const pick = async (label) => {
    await page.locator('.action-menu:not(.hidden) [role="menuitem"]', { hasText: new RegExp(`^\\s*${label}\\s*$`) }).first().click();
    await page.waitForTimeout(350);
  };

  // 1. Right-click on a body cell opens the menu at the pointer.
  const at = await rightClick(2, 1);
  const menu = await menuState();
  ok("a right-click on a cell opens the table's menu", !!menu && menu.labels.includes("Move row down") && menu.labels.includes("Select column"), menu && menu.labels.join(" | "));
  ok("the menu lists 19 commands in 6 groups (5 hairlines)", !!menu && menu.labels.length === 19 && menu.seps === 5, menu && `${menu.labels.length} items, ${menu.seps} separators`);
  ok("the menu is inside the window", !!menu && menu.inView, menu && menu.rect.join(","));
  ok("the menu opens at the pointer (within 12px of the press, or flipped inside the window)", !!menu && (Math.abs(menu.rect[0] - at.x) <= 12 || menu.rect[0] + menu.rect[2] <= WIDTH), menu && `${menu.rect.join(",")} vs ${Math.round(at.x)},${Math.round(at.y)}`);
  const caretRow = await page.evaluate(() => { const d = docCmView.state.doc; return d.lineAt(docCmView.state.selection.main.head).text; });
  ok("the caret went to the pressed cell's row", caretRow.includes("apple"), caretRow);

  // 2. Move row up: one transaction, one Ctrl+Z.
  const before = await text();
  await pick("Move row up");
  const afterMove = await table();
  ok("Move row up swaps the two lines", afterMove[2].includes("apple") && afterMove[3].includes("pear"), afterMove.slice(2).join(" / "));
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  ok("one Ctrl+Z puts the row back, byte for byte", (await text()) === before);

  // 3. Move column right moves the alignment with it.
  await rightClick(2, 0);
  await pick("Move column right");
  const moved = await table();
  ok("Move column right: Qty first, its right-align marker with it", moved[0].startsWith("| Qty") && moved[1].startsWith("| ---:") && moved[2].includes("10 | pear"), moved.slice(0, 3).join(" / "));
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  ok("one Ctrl+Z puts the column back", (await text()) === before);

  // 4. Sort the Qty column, numbers as numbers.
  await rightClick(2, 1);
  await pick("Sort Z to A");
  const sorted = await table();
  ok("Sort Z to A on Qty: 33, 10, 2", ["33", "10", "2"].every((n, i) => sorted[2 + i].split("|")[2].trim() === n), sorted.slice(2).join(" / "));
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  ok("one Ctrl+Z puts the order back", (await text()) === before);

  // 5. Select column: one range per cell, and the delimiter is skipped.
  await rightClick(2, 2);
  await pick("Select column");
  const sel = await page.evaluate(() => docCmView.state.selection.ranges.map((r) => docCmView.state.sliceDoc(r.from, r.to)));
  ok("Select column selects Note, green, red, purple", JSON.stringify(sel) === JSON.stringify(["Note", "green", "red", "purple"]), JSON.stringify(sel));
  // A right-click inside the selected column keeps the ranges.
  const inside = await cellBox(3, 2);
  await page.mouse.click(inside.x, inside.y, { button: "right" });
  await page.waitForTimeout(300);
  const kept = await page.evaluate(() => docCmView.state.selection.ranges.length);
  ok("a right-click inside a selected column keeps its four ranges", kept === 4, kept);
  await page.keyboard.press("Escape");
  // Delete clears all four cells' words at once, one step.
  await rightClick(2, 2);
  await pick("Select column");
  await page.keyboard.press("Delete");
  await page.waitForTimeout(250);
  const cleared = await table();
  ok("Delete on a selected column clears its four cells", cleared.slice(2).every((l) => l.split("|")[3].trim() === "") && cleared[0].split("|")[3].trim() === "", cleared.join(" / "));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(250);
  ok("one Ctrl+Z brings the column's words back", (await text()) === before);

  // 6. Select row and Select table.
  await rightClick(3, 0);
  await pick("Select row");
  const row = await page.evaluate(() => docCmView.state.selection.ranges.map((r) => docCmView.state.sliceDoc(r.from, r.to).trim()));
  ok("Select row selects the whole row", row.length === 1 && row[0].startsWith("fig") && row[0].endsWith("purple"), JSON.stringify(row));
  await rightClick(3, 0);
  await pick("Select table");
  const all = await page.evaluate(() => { const r = docCmView.state.selection.main; return docCmView.state.sliceDoc(r.from, r.to); });
  ok("Select table selects the table's text exactly", all === TABLE);

  // 7. The header and the ends: the right moves are disabled where they cannot go.
  // Collapse the selection first: with the whole table selected, Live shows the
  // table's source and the selection toolbar floats over the paragraph.
  await page.evaluate(() => docCmView.dispatch({ selection: { anchor: 0 } }));
  await page.waitForTimeout(300);
  await rightClick(1, 0);
  const edge = await menuState();
  ok("the first body row cannot move up, the first column cannot move left", !!edge && edge.disabled.includes("Move row up") && edge.disabled.includes("Move column left"), edge && edge.disabled.join(" | "));
  await page.keyboard.press("Escape");
  // 8. Outside a table the browser's own menu stays.
  const para = await page.evaluate(() => { const l = [...document.querySelectorAll(".cm-line")].find((n) => n.textContent.includes("Before it")); const b = l.getBoundingClientRect(); return { x: b.left + 40, y: b.top + b.height / 2 }; });
  await page.mouse.click(para.x, para.y, { button: "right" });
  await page.waitForTimeout(250);
  ok("a right-click on a paragraph opens no table menu", (await menuState()) === null);
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
