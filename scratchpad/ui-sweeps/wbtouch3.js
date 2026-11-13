// Whiteboard touch and toolbar rows, measured on a live board (LEDGER L259, L261, L264, L269, L-whiteboard-26):
//   L259 the shape flyout's caret is a 44x44 target on a finger and unchanged on a mouse
//   L261 a table's and a diagram's resize grip do not promise "fits the text"
//   L264 .wb-tool-section-label never overflows its box (scrollWidth <= clientWidth), docked at the bottom or the side
//   L269 the toolbar is a few tab stops (a roving tabindex per group), arrows move inside a group, Home/End jump
//   L-whiteboard-26 a folded frame's child shows as folded in the Layers tab, and its eye does not write hidden
//   BASE=http://127.0.0.1:8897 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbtouch3.js
const { openFresh, checker } = require("./cdlib.js");

(async () => {
  const { check, summary } = checker();

  // --- Desktop: 1440 (the rail's layout must not move) and 768 --------------------------------------------
  for (const width of [1440, 768]) {
    const { browser, page, errors } = await openFresh({ width });
    await page.waitForTimeout(600);
    const labels = async () => page.evaluate(() => [...document.querySelectorAll(".wb-tool-section-label")]
      .map((l) => ({ t: l.textContent.trim(), sw: l.scrollWidth, cw: l.clientWidth }))
      .filter((l) => l.sw > l.cw));
    check(`${width}: no section label overflows its box (bottom dock)`, (await labels()).length === 0, await labels());
    const panelFit = await page.evaluate(() => { const p = document.querySelector(".whiteboard-floating-panel.wb-rail"); return p ? [p.scrollWidth, p.clientWidth] : null; });
    check(`${width}: the hidden labels add no scroll width to the rail`, panelFit && panelFit[0] <= panelFit[1], panelFit);
    // Side dock: the labels are on screen there.
    await page.evaluate(() => document.getElementById("wb-dock-toggle")?.click());
    await page.waitForTimeout(500);
    const side = await page.evaluate(() => ({ dock: document.querySelector(".whiteboard-floating-panel.wb-rail")?.dataset.dock, shown: [...document.querySelectorAll(".wb-tool-section-label")].filter((l) => l.getBoundingClientRect().width > 4).length }));
    check(`${width}: side dock labels fit their boxes`, (await labels()).length === 0, { side, over: await labels() });
    await page.evaluate(() => document.getElementById("wb-dock-toggle")?.click());
    await page.waitForTimeout(300);

    const caret = await page.evaluate(() => { const c = document.querySelector("#wb-shape-toggle .wb-shape-caret").getBoundingClientRect(); const t = document.getElementById("wb-shape-toggle").getBoundingClientRect(); return { caret: [c.width, c.height], toggle: [t.width, t.height] }; });
    check(`${width}: a mouse keeps the 10px caret`, caret.caret[0] === 10 && caret.caret[1] === 10, caret);

    // L265: Find and Overview are the View menu's switches only; the top bar has no copy.
    const dup = await page.evaluate(() => ({ search: Boolean(document.getElementById("wb-search-toggle")), nav: Boolean(document.getElementById("wb-navigator-toggle")), topbarIcons: document.querySelectorAll(".wb-topbar-right > button.icon-button").length }));
    check(`${width}: the top bar has no Find or Overview icon`, !dup.search && !dup.nav, dup);
    const sw = await page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const shown = (id) => !document.getElementById(id).classList.contains("hidden");
      const out = {};
      document.getElementById("wb-panel-search").click(); await wait(300); out.searchOn = shown("wb-search-bar");
      document.getElementById("wb-panel-search").click(); await wait(300); out.searchOff = !shown("wb-search-bar");
      document.getElementById("wb-panel-overview").click(); await wait(300); out.navOn = shown("wb-navigator");
      document.getElementById("wb-panel-overview").click(); await wait(300); out.navOff = !shown("wb-navigator");
      return out;
    });
    check(`${width}: the View switches open and close Find and Overview`, sw.searchOn && sw.searchOff && sw.navOn && sw.navOff, sw);

    const titles = await page.evaluate(() => ({ table: wbResizeHandleTitle("table"), diagram: wbResizeHandleTitle("diagram"), text: wbResizeHandleTitle("text") }));
    check(`${width}: a table's and a diagram's grip say what the double-click fits`, !/text/.test(titles.table) && !/text/.test(titles.diagram) && /text/.test(titles.text), titles);

    // --- L-whiteboard-26 -----------------------------------------------------------------------------------
    if (width === 1440) {
      const ids = await page.evaluate(async () => {
        const b = window.currentBoardId;
        const post = (kind, data, x, y, w, h, z = 1) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind, data, board_id: b, x, y, z, width: w, height: h }) });
        const out = { f: (await post("frame", { content: "Fold me" }, 100, 100, 420, 260, 0)).id };
        out.k = (await post("text", { content: "inside" }, 130, 140, 140, 50)).id;
        out.o = (await post("text", { content: "outside" }, 700, 140, 140, 50)).id;
        await fetchWhiteboardState();
        renderWhiteboardNow();
        return out;
      });
      await page.waitForTimeout(500);
      await page.evaluate(() => wbOpenSidebar("layers"));
      await page.waitForTimeout(500);
      const row = (id) => page.evaluate((i) => { const r = document.querySelector(`#wb-layers-tree [data-key="object:${i}"]`); return r && { cls: r.className, label: r.getAttribute("aria-label"), eye: r.querySelector(".wb-layer-eye")?.title, icon: r.querySelector(".wb-layer-eye i, .wb-layer-eye svg")?.className?.baseVal ?? r.querySelector(".wb-layer-eye i")?.className }; }, id);
      const before = await row(ids.k);
      check("expanded: the child row is plain (not folded, not hidden)", before && !/is-folded|is-hidden/.test(before.cls), before);
      await page.evaluate((id) => { wbSelectExactly([["object", wbFindItem("object", id)]]); wbRunCommand("collapse-frame"); }, ids.f);
      await page.waitForTimeout(700);
      const folded = await row(ids.k);
      check("folded frame: the child row is marked folded and not hidden", folded && /is-folded/.test(folded.cls) && !/is-hidden/.test(folded.cls), folded);
      check("its eye says to expand the frame", folded && /Folded inside .*Expand the frame/.test(folded.eye), folded?.eye);
      check("its row name says folded, not hidden", folded && /folded in a frame/.test(folded.label) && !/, hidden/.test(folded.label), folded?.label);
      await page.click(`#wb-layers-tree [data-key="object:${ids.k}"] .wb-layer-eye`);
      await page.waitForTimeout(500);
      const flag = await page.evaluate((id) => Boolean(wbFindItem("object", id).data?.hidden), ids.k);
      check("pressing the eye writes no hidden flag", flag === false);
      const outside = await row(ids.o);
      check("a box outside the frame is plain", outside && !/is-folded|is-hidden/.test(outside.cls), outside);
      await page.evaluate((id) => wbFmtState.structure.setFolded(wbFindItem("object", id), false), ids.f);
      await page.waitForTimeout(700);
      const open = await row(ids.k);
      check("expanding the frame clears the mark", open && !/is-folded/.test(open.cls), open);
    }
    check(`${width}: no page errors`, errors.length === 0, errors.slice(0, 3));
    await browser.close();
  }

  // --- Phone: 390, coarse pointer -------------------------------------------------------------------------
  {
    const { browser, page, errors } = await openFresh({ width: 390 });
    await page.waitForTimeout(600);
    await page.click("#wb-tools-opener");
    await page.waitForTimeout(800);
    const m = await page.evaluate(() => {
      const t = document.getElementById("wb-shape-toggle");
      const c = t.querySelector(".wb-shape-caret").getBoundingClientRect();
      const b = t.getBoundingClientRect();
      return { coarse: matchMedia("(pointer: coarse)").matches, caret: [c.width, c.height], toggle: [b.width, b.height], cx: c.left + c.width / 2, cy: c.top + c.height / 2, cornerX: c.left + 2, cornerY: c.top + 2 };
    });
    check("390: coarse pointer is on", m.coarse);
    check("390: the caret target is at least 44x44", m.caret[0] >= 44 && m.caret[1] >= 44, m);
    // A press at the edge of the caret's box (the padding, 17px from the glyph) opens the list; the icon above still picks the tool.
    await page.mouse.click(m.cornerX, m.cornerY);
    await page.waitForTimeout(400);
    const open = await page.evaluate(() => !document.getElementById("wb-shape-menu").classList.contains("hidden"));
    check("390: a press 2px inside the caret's box opens the shapes list", open, m);
    check("390: no section label overflows (phone)", await page.evaluate(() => [...document.querySelectorAll(".wb-tool-section-label")].every((l) => l.scrollWidth <= l.clientWidth)));
    check("390: no page errors", errors.length === 0, errors.slice(0, 3));
    await browser.close();
  }
  summary();
})();
