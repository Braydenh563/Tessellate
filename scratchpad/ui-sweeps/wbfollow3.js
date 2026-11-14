// Whiteboard follow-ups: the phone More sheet's Arrange submenus (L-whiteboard-30), smoothed ink width and rotation
// (L-whiteboard-31), sub/superscript (L-whiteboard-27), a drawn shape swapped in fresh (L-whiteboard-28).
//   BASE=http://127.0.0.1:8897 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbfollow3.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 390 });
  const { check, summary } = checker();
  // --- L-whiteboard-30 --------------------------------------------------------------------------------------
  await page.evaluate(() => document.getElementById("wb-more-toggle").click());
  await page.waitForTimeout(500);
  const top = await page.evaluate(() => {
    const menu = document.getElementById("wb-more-menu");
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const groups = [...menu.querySelectorAll(":scope > .menu-group")].filter(vis).map((g) => g.firstElementChild.textContent.trim());
    const flatArrange = [...menu.querySelectorAll(":scope > [data-wb-cmd]")].filter(vis).filter((r) => WB_COMMAND_BY_ID.get(r.dataset.wbCmd).group === "Arrange").length;
    const card = menu.closest(".sheet-card") || menu;
    return { groups, flatArrange, sw: card.scrollWidth, cw: card.clientWidth, rows: [...menu.querySelectorAll(":scope > .menu-item, :scope > .menu-group > .menu-item")].filter(vis).map((r) => Math.round(r.getBoundingClientRect().height)) };
  });
  check("L30: the sheet shows the Arrange submenus as group rows", top.groups.length >= 5, top.groups);
  check("L30: no flat Arrange row left beside the groups", top.flatArrange <= 6, top.flatArrange);
  check("L30: no horizontal overflow at the top level (scrollWidth <= clientWidth)", top.sw <= top.cw, [top.sw, top.cw]);
  check("L30: top-level rows are at least 44 px tall", Math.min(...top.rows) >= 44, Math.min(...top.rows));
  // Select two shapes so commands apply, then open each group.
  const names = await page.evaluate(() => [...document.querySelectorAll("#wb-more-menu > .menu-group")].map((g) => g.dataset.wbMoreGroup));
  for (const label of names) {
    const r = await page.evaluate(async (label) => {
      const wait = (ms) => new Promise((x) => setTimeout(x, ms));
      const menu = document.getElementById("wb-more-menu");
      const g = [...menu.querySelectorAll(":scope > .menu-group")].find((x) => x.dataset.wbMoreGroup === label);
      if (g.hidden) return { hidden: true };
      g.firstElementChild.click(); await wait(250);
      const sub = g.querySelector(".submenu");
      const rows = [...sub.querySelectorAll(":scope > .menu-item")].filter((x) => !x.hidden && x.getBoundingClientRect().height > 0);
      const heights = rows.map((x) => Math.round(x.getBoundingClientRect().height));
      const cmds = rows.filter((x) => x.dataset.wbCmd).length;
      const back = sub.querySelector(".menu-back");
      const out = { cmds, minH: Math.min(...heights), nested: menu.classList.contains("menu-nested"), back: Boolean(back), sw: menu.scrollWidth, cw: menu.clientWidth, total: sub.querySelectorAll("[data-wb-cmd]").length };
      back.click(); await wait(200);
      out.closed = !menu.classList.contains("menu-nested");
      return out;
    }, label);
    check(`L30: "${label}" opens nested with a back row, rows >= 44 px, no overflow, back to the top`, r.hidden || (r.nested && r.back && r.minH >= 44 && r.sw <= r.cw && r.closed && r.cmds === r.total), r);
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await browser.close();

  // --- L-whiteboard-31: width and turn on smoothed ink ------------------------------------------------------
  const wide = await openFresh({ width: 1440 });
  const p = wide.page;
  const box = await p.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  await p.evaluate(() => wbSelectToolRef("draw"));
  const [px, py] = [box.x + box.w / 2 - 200, box.y + box.h / 2];
  await p.mouse.move(px, py);
  await p.mouse.down();
  for (let i = 1; i <= 30; i++) await p.mouse.move(px + i * 8, py + Math.sin(i / 4) * 30);
  await p.mouse.up();
  await p.waitForTimeout(700);
  const ink = () => p.evaluate(() => { const s = wbState.sketches[wbState.sketches.length - 1]; const d = wbSketchParsedData(s); const b = wbPathBBox(d.d); return { id: s.id, w: Math.round(b.width), h: Math.round(b.height), width: d.width, pts: (d.pts || []).slice(0, 4), npts: (d.pts || []).length, pbox: d.pbox }; });
  const first = await ink();
  await p.evaluate(() => wbSelectToolRef("select"));
  await p.evaluate((id) => selectWbItem("sketch", id), first.id);
  await p.evaluate(() => wbFormatOpen?.());
  await p.waitForTimeout(500);
  const widthField = await p.evaluate(() => { const el = document.getElementById("wb-fmt-width"); const r = el?.getBoundingClientRect(); return { there: Boolean(el), shown: Boolean(r && r.width > 0) }; });
  check("L31: the Format panel offers the width on a smoothed stroke", widthField.there && widthField.shown, widthField);
  await p.fill("#wb-fmt-width", "14");
  await p.dispatchEvent("#wb-fmt-width", "change");
  await p.waitForTimeout(600);
  const fat = await ink();
  check("L31: width 14 draws a fatter outline from the kept points (taller than at 3)", fat.h > first.h + 10 && fat.width === 14, [first.h, fat.h, fat.width]);
  check("L31: the kept points stay (points and box saved again)", fat.npts >= 10 && Array.isArray(fat.pbox), fat);
  await p.evaluate(() => wbUndo());
  await p.waitForTimeout(500);
  const back = await ink();
  check("L31: one Undo takes the width back to the first outline", back.h === first.h && back.width === first.width, [first.h, back.h, back.width]);
  await p.evaluate(() => wbTurnSelection(90));
  await p.waitForTimeout(600);
  const turned = await ink();
  check("L31: a quarter turn swaps the outline's width and height", Math.abs(turned.w - first.h) <= 3 && Math.abs(turned.h - first.w) <= 3, [first.w, first.h, turned.w, turned.h]);
  await p.fill("#wb-fmt-width", "14");
  await p.dispatchEvent("#wb-fmt-width", "change");
  await p.waitForTimeout(600);
  const turnedFat = await ink();
  check("L31: width after the turn keeps it turned (still taller than wide) and fatter", turnedFat.h > turnedFat.w * 2 && turnedFat.w > turned.w + 5, [turned.w, turned.h, turnedFat.w, turnedFat.h]);
  await p.evaluate(() => wbUndo());
  await p.waitForTimeout(400);
  // L28: a drawn shape swapped in at a non-tile size is drawn fresh for the box, not stretched.
  const l28 = await p.evaluate(() => {
    const T = wbFmtState.shapeTable; const kind = T.kinds[0];
    const box = { minX: 10, minY: 20, width: 500, height: 40 };
    const out = wbFmtState.libraryMore.replaceData({}, { d: T.shapePath(kind), shapeKind: kind }, box, { minX: 0, minY: 0, width: 100, height: 100 }, wbTransformPathD);
    return { same: out.d === T.shapePathAt(kind, 10, 20, 500, 40), kind: out.shapeKind === kind };
  });
  check("L28: a replaced drawn shape equals the table outline for the box", l28.same && l28.kind, l28);

  // L27: the Text style menu wraps the selected words in ~ ~ and takes them out again.
  const tid = await p.evaluate(async () => {
    const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: window.currentBoardId ?? null, kind: "text", x: 200, y: 200, width: 360, height: 120, data: { content: "H2O" } }) });
    await fetchWhiteboardState(); renderWhiteboardNow(); selectWbItem("object", o.id); return o.id;
  });
  await p.waitForTimeout(600);
  const tsel = `#wb-html-layer .wb-object[data-id="${tid}"] .wb-text-content`;
  await p.dblclick(tsel); await p.waitForTimeout(400);
  const pickRange = (a, b) => p.evaluate(([s, a, b]) => { const el = document.querySelector(s); el.focus(); el.wbEditorSurface.setSelectionRange(a, b); document.dispatchEvent(new Event("selectionchange")); }, [tsel, a, b]);
  await pickRange(1, 2); await p.waitForTimeout(500);
  const press = async (label) => {
    await p.evaluate(() => document.querySelector("#selection-bar [data-board-run]").dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })));
    await p.waitForSelector("#wb-colour-menu:not(.hidden)");
    await p.click(`#wb-colour-menu >> text="${label}"`, { timeout: 4000 });
    await p.waitForTimeout(300);
  };
  const surf = () => p.evaluate((s) => document.querySelector(s).wbEditorSurface.text, tsel);
  await press("Subscript");
  const sub = await surf();
  check("L27: Subscript wraps the selected 2 as H~2~O", sub === "H~2~O", sub);
  await pickRange(2, 3); await p.waitForTimeout(300);
  await press("Subscript");
  const unsub = await surf();
  check("L27: pressing it on the wrapped 2 takes the marks out again", unsub === "H2O", unsub);
  await pickRange(1, 2); await p.waitForTimeout(300);
  await press("Superscript");
  const sup = await surf();
  check("L27: Superscript wraps it as H^2^O", sup === "H^2^O", sup);
  const ov = await p.evaluate(() => { const m = document.getElementById("wb-colour-menu"); return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }; });
  check("L27: no horizontal overflow", ov.sw <= ov.cw, ov);

  await wide.browser.close();
  summary(errors.concat(wide.errors));
})();
