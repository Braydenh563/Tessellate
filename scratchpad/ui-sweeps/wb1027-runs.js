// wb-1027: a run (size, font, text colour, highlight) set on selected card text applies to those words only,
// is stored in the text, survives save and reload and export, and the Format panel's text controls are reachable.
//   BASE=http://127.0.0.1:8787 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1027-runs.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, errors, board } = await openBoard();
  const id = await page.evaluate(async (bid) => {
    const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: bid, kind: "text", x: 200, y: 200, width: 360, height: 120, data: { content: "alpha beta gamma" } }) });
    await fetchWhiteboardState(); renderWhiteboardNow(); selectWbItem("object", o.id);
    return o.id;
  }, board.id);
  await page.waitForTimeout(600);
  const content = () => page.evaluate((i) => wbState.objects.find((o) => o.id === i).data.content, id);
  const sel = `#wb-html-layer .wb-object[data-id="${id}"] .wb-text-content`;
  // Edit, select "beta" by offsets.
  await page.dblclick(sel); await page.waitForTimeout(400);
  await page.evaluate((s) => {
    const el = document.querySelector(s); el.focus();
    el.wbEditorSurface.setSelectionRange(6, 10);
    document.dispatchEvent(new Event("selectionchange"));
  }, sel);
  await page.waitForTimeout(500);
  const bar = await page.evaluate(() => { const b = document.querySelector("#selection-bar [data-board-run]"); const r = b && b.getBoundingClientRect(); return b && { hidden: b.hidden, w: r.width, h: r.height, shown: !document.getElementById("selection-bar").classList.contains("hidden") }; });
  console.log("run button", JSON.stringify(bar));
  check("the bar has a visible Text style button on selected card text", bar && !bar.hidden && bar.w > 0 && bar.shown, bar);
  const pick = async (word) => {
    await page.evaluate(() => document.querySelector("#selection-bar [data-board-run]").dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })));
    await page.waitForSelector("#wb-colour-menu:not(.hidden)");
    await page.click(`#wb-colour-menu >> text="${word}"`, { timeout: 4000 }).catch(async () => { await page.click(`#wb-colour-menu [aria-label="${word}"]`); });
  };
  const choose = async (group, label) => {
    await page.evaluate(() => document.querySelector("#selection-bar [data-board-run]").dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })));
    await page.waitForSelector("#wb-colour-menu:not(.hidden)");
    await page.click(`#wb-colour-menu [aria-label="${group}"] >> text="${label}"`).catch(async () => { await page.click(`#wb-colour-menu [aria-label="${group}"] [aria-label="${label}"]`); });
    await page.waitForTimeout(300);
  };
  const menuBox = await page.evaluate(() => { document.querySelector("#selection-bar [data-board-run]").dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })); const m = document.getElementById("wb-colour-menu"); const r = m.getBoundingClientRect(); return { w: r.width, h: r.height, x: r.x, y: r.y, vw: innerWidth, vh: innerHeight, text: m.innerText.replace(/\n+/g, " | ") }; });
  console.log("menu", JSON.stringify(menuBox));
  check("the menu opens inside the window with Size, Font, Text colour, Highlight and the whole-box link",
    menuBox.x >= 0 && menuBox.y >= 0 && menuBox.x + menuBox.w <= menuBox.vw && menuBox.y + menuBox.h <= menuBox.vh &&
    ["Size", "Font", "Text colour", "Highlight", "Text settings for the whole box"].every((w) => menuBox.text.includes(w)), menuBox);
  await page.evaluate(() => closeActionMenus()); await page.waitForTimeout(300);
  await page.evaluate((s) => { const el = document.querySelector(s); el.focus(); el.wbEditorSurface.setSelectionRange(6, 10); }, sel);
  await choose("Size", "28");
  await choose("Font", "Serif");
  await choose("Text colour", "Red");
  await choose("Highlight colour", "Yellow");
  const live = await page.evaluate((s) => document.querySelector(s).wbEditorSurface.text, sel);
  console.log("surface text", JSON.stringify(live));
  check("the four picks are one run in the text, on the selected words only", live === "alpha {{size=28 font=serif ink=red hl=yellow|beta}} gamma", live);
  // Leave the box (blur saves), then read what is stored and drawn.
  await page.keyboard.press("Escape"); await page.waitForTimeout(900);
  const stored = await content();
  check("saved in the text", stored === "alpha {{size=28 font=serif ink=red hl=yellow|beta}} gamma", stored);
  const drawn = () => page.evaluate((s) => {
    const el = document.querySelector(s);
    const run = el.querySelector("mark.text-highlight, span[style]"); const inkEl = run && (run.querySelector(".text-ink") || run);
    const base = getComputedStyle(el);
    const rs = run && getComputedStyle(run);
    return { runText: run && run.textContent, runSize: rs && rs.fontSize, runFont: rs && rs.fontFamily.slice(0, 20), runColour: inkEl && getComputedStyle(inkEl).color, runBg: rs && rs.backgroundColor, baseSize: base.fontSize, text: el.innerText, marks: el.innerHTML.includes("{{") };
  }, sel);
  let d = await drawn();
  console.log("drawn", JSON.stringify(d));
  check("only the run is drawn larger, serif, red and highlighted", d.runText === "beta" && d.runSize === "28px" && /Georgia/.test(d.runFont) && d.runColour === "rgb(185, 28, 28)" && d.runBg !== "rgba(0, 0, 0, 0)" && d.baseSize !== "28px" && !d.marks && d.text.replace(/\s+/g, " ").trim() === "alpha beta gamma", d);
  // Survives save and reload.
  await page.evaluate(async () => { await fetchWhiteboardState(); renderWhiteboardNow(); });
  await page.waitForTimeout(600);
  d = await drawn();
  check("survives a reload of the board's rows", d.runSize === "28px" && d.runText === "beta", d);
  // Export carries the run per tspan.
  const svg = await page.evaluate(() => wbBuildExportSvg("board").svg);
  const tspans = [...svg.matchAll(/<tspan[^>]*font-size="(\d+)"[^>]*>([^<]*)<\/tspan>/g)].map((m) => [m[1], m[2]]);
  console.log("export tspans", JSON.stringify(tspans), "serif", /Georgia/.test(svg), "red", svg.includes("#b91c1c"), "hl", svg.includes('fill-opacity="0.25"'));
  check("the export draws the run as its own sized, coloured, highlighted tspan", tspans.some(([s, t]) => s === "28" && t === "beta") && tspans.some(([s, t]) => s !== "28" && t === "alpha") && svg.includes("#b91c1c") && svg.includes('fill-opacity="0.25"') && /Georgia/.test(svg), tspans);
  // Undo.
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(800);
  const undone = await content();
  check("one undo takes the run off", undone === "alpha beta gamma", undone);
  // Reachable Format panel.
  await page.evaluate(() => wbRedo && wbRedo()); await page.waitForTimeout(500);
  await page.evaluate(() => { selectWbItem("object", arguments[0]); }, id).catch(() => {});
  await page.evaluate((i) => selectWbItem("object", i), id);
  await page.dblclick(sel); await page.waitForTimeout(400);
  await page.evaluate((s) => { const el = document.querySelector(s); el.focus(); el.wbEditorSurface.setSelectionRange(0, 5); document.dispatchEvent(new Event("selectionchange")); }, sel);
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector("#selection-bar [data-board-run]").dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true })));
  await page.waitForSelector("#wb-colour-menu:not(.hidden)");
  await page.click("#wb-colour-menu >> text=Text settings for the whole box"); await page.waitForTimeout(600);
  const panel = await page.evaluate(() => ({ open: wbFormatIsOpen(), tab: wbFmtState.fmtTab, sizeVisible: Boolean(document.getElementById("wb-fmt-size")?.getClientRects().length) }));
  check("the Format panel's text controls open from the menu", panel.open && panel.tab === "text" && panel.sizeVisible, panel);
  check("no page errors", errors.length === 0, errors);
  summary(); await browser.close();
})();
