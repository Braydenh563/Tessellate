// INBOX 904 B19: drag a snippet from the library into the text, with a ghost
// caret where it will land and a scroll at the editor's top and bottom edge.
// Real mouse events (Chromium's own drag and drop), numbers not pictures.
//
// Usage: BASE=http://127.0.0.1:8792 [THEME=dark] node snippetdrag1018.js
const { boot } = require("./lib.js");

let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const LINES = Array.from({ length: 160 }, (_, i) => `value_${i} = ${i}  # line ${i + 1}`).join("\n") + "\n";

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2500);
  await page.evaluate(async (c) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Drag probe", content: c, file_type: "py" }) });
    await loadDocuments(d.id);
  }, LINES);
  await page.waitForTimeout(2000);
  await page.evaluate(() => docCodeSideFrom("snippets"));
  await page.waitForTimeout(1200);

  const rows = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-row")].map((r) => ({ name: r.querySelector(".doc-snippet-name").textContent, drag: r.draggable })));
  ok("rows listed and draggable", rows.length > 3 && rows.every((r) => r.drag), `${rows.length} rows, first "${rows[0] && rows[0].name}"`);
  const rowBox = await page.locator("#doc-snippet-list .doc-snippet-row").first().boundingBox();
  const row = { x: rowBox.x + rowBox.width / 2, y: rowBox.y + rowBox.height / 2 };
  const edit = await page.evaluate(() => {
    const r = docCmView.scrollDOM.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, scrollTop: docCmView.scrollDOM.scrollTop, docLen: docCmView.state.doc.length, lines: docCmView.state.doc.lines };
  });
  const midY = Math.round((edit.top + edit.bottom) / 2);
  const midX = Math.round(edit.left + 220);
  const lineAt = (y, x) => page.evaluate(([px, py]) => {
    const view = docCmView;
    const pos = view.posAtCoords({ x: px, y: py }, false);
    const line = view.state.doc.lineAt(pos);
    const c = view.coordsAtPos(pos);
    return { pos, line: line.number, left: c.left, top: c.top, height: c.bottom - c.top };
  }, [x, y]);

  // 1. Mid-text: the ghost stands where the drop will land.
  await page.mouse.move(row.x, row.y);
  await page.mouse.down();
  await page.mouse.move(row.x - 20, row.y + 5, { steps: 4 });
  await page.mouse.move(midX, midY, { steps: 12 });
  //: Chromium's synthetic drag delivers a dragover per move, with no repeat
  //: while the pointer rests (a real drag repeats every 50 ms), so the last
  //: step is repeated to land the final dragover on the target.
  await page.mouse.move(midX + 1, midY);
  await page.mouse.move(midX, midY);
  await page.waitForTimeout(250);
  const target = await lineAt(midY, midX);
  const ghost = await page.evaluate(() => {
    const g = document.querySelector(".doc-drop-ghost");
    if (!g) return null;
    const b = g.getBoundingClientRect();
    const s = getComputedStyle(g);
    return { left: b.left, top: b.top, width: b.width, height: b.height, hidden: g.classList.contains("hidden"), bg: s.backgroundColor, events: s.pointerEvents, display: s.display };
  });
  ok("a ghost caret is up over the text", !!ghost && !ghost.hidden && ghost.display !== "none", JSON.stringify(ghost));
  ok("the ghost is at the caret position of the pointer (within 2px)", !!ghost && Math.abs(ghost.left + ghost.width / 2 - target.left) <= 2 && Math.abs(ghost.top - target.top) <= 2, `ghost ${ghost && Math.round(ghost.left)},${ghost && Math.round(ghost.top)} vs ${Math.round(target.left)},${Math.round(target.top)}`);
  ok("the ghost is a line high and takes no pointer events", !!ghost && Math.abs(ghost.height - target.height) <= 2 && ghost.events === "none", `${ghost && ghost.height} vs ${target.height}`);
  const lenBefore = await page.evaluate(() => docCmView.state.doc.length);
  await page.mouse.up();
  await page.waitForTimeout(500);
  const after = await page.evaluate((line) => {
    const doc = docCmView.state.doc;
    return { len: doc.length, at: doc.line(line).text, lines: doc.lines, ghost: !!document.querySelector(".doc-drop-ghost"), caret: doc.lineAt(docCmView.state.selection.main.head).number };
  }, target.line);
  ok("the drop inserted the snippet at the pointer's line", after.len > lenBefore && after.at !== `value_${target.line - 1} = ${target.line - 1}  # line ${target.line}`, `line ${target.line} now "${after.at.slice(0, 40)}", +${after.len - lenBefore} chars`);
  ok("the ghost is gone after the drop", !after.ghost);
  const dropped = after.len - lenBefore;
  // One Ctrl+Z takes it out.
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(300);
  const undone = await page.evaluate(() => docCmView.state.doc.length);
  ok("one Ctrl+Z takes the dropped snippet out", undone === lenBefore, `${undone} vs ${lenBefore}`);

  // 2. The bottom edge scrolls while the pointer rests there.
  await page.evaluate(() => { docCmView.scrollDOM.scrollTop = 0; });
  await page.waitForTimeout(200);
  await page.mouse.move(row.x, row.y);
  await page.mouse.down();
  await page.mouse.move(row.x - 20, row.y + 5, { steps: 4 });
  await page.mouse.move(midX, midY, { steps: 8 });
  await page.mouse.move(midX, edit.bottom - 6, { steps: 10 });
  const t0 = await page.evaluate(() => docCmView.scrollDOM.scrollTop);
  for (let i = 0; i < 12; i++) {
    await page.mouse.move(midX, edit.bottom - 6 - (i % 2));
    await page.waitForTimeout(60);
  }
  const t1 = await page.evaluate(() => docCmView.scrollDOM.scrollTop);
  ok("resting at the bottom edge scrolls the text down", t1 - t0 > 40, `scrollTop ${Math.round(t0)} to ${Math.round(t1)} in about 0.7 s`);
  const ghostBottom = await page.evaluate(() => {
    const g = document.querySelector(".doc-drop-ghost");
    const r = docCmView.scrollDOM.getBoundingClientRect();
    if (!g) return null;
    const b = g.getBoundingClientRect();
    return { hidden: g.classList.contains("hidden"), inside: b.top >= r.top - 1 && b.bottom <= r.bottom + 1 };
  });
  ok("the ghost keeps following inside the editor while it scrolls", !!ghostBottom && (!ghostBottom.hidden && ghostBottom.inside), JSON.stringify(ghostBottom));
  // 3. Then the top edge scrolls back up.
  await page.mouse.move(midX, edit.top + 6, { steps: 10 });
  const u0 = await page.evaluate(() => docCmView.scrollDOM.scrollTop);
  for (let i = 0; i < 12; i++) {
    await page.mouse.move(midX, edit.top + 6 + (i % 2));
    await page.waitForTimeout(60);
  }
  const u1 = await page.evaluate(() => docCmView.scrollDOM.scrollTop);
  ok("resting at the top edge scrolls the text up", u0 - u1 > 40, `scrollTop ${Math.round(u0)} to ${Math.round(u1)}`);
  // 4. Letting go outside the editor inserts nothing and clears the ghost.
  const lenOut = await page.evaluate(() => docCmView.state.doc.length);
  await page.mouse.move(row.x, row.y, { steps: 10 });
  await page.mouse.up();
  await page.waitForTimeout(400);
  const out = await page.evaluate(() => ({ len: docCmView.state.doc.length, ghost: !!document.querySelector(".doc-drop-ghost") }));
  ok("a drop outside the editor inserts nothing and leaves no ghost", out.len === lenOut && !out.ghost, JSON.stringify(out));
  // 5. A click still inserts at the caret.
  await page.evaluate(() => { docCmView.focus(); docCmView.dispatch({ selection: { anchor: 0 } }); });
  await page.locator("#doc-snippet-list .doc-snippet-row").first().click();
  await page.waitForTimeout(300);
  const clicked = await page.evaluate(() => docCmView.state.doc.length);
  ok("a click still inserts at the caret", clicked > lenOut, `${clicked} vs ${lenOut}`);
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed (dropped ${dropped} chars)`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
