// The board's sidebar and object library (WHITEBOARD_PLAN decisions 25, 26).
// The features audit's acceptance: save 3 linked shapes, place twice: 6 items,
// 4 links... (here 2 links per placement of a pair: the counts below), 2 undo
// steps; export, delete, import: the same; keyboard-only placement announced;
// 0 console errors at 1440, 820 and 390.
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1005-library.js
// W=1440 (default) | 820 | 390; THEME=dark; SHOTS=<dir> for screenshots.
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = +(process.env.W || 1440);
const SHOTS = process.env.SHOTS || "";

(async () => {
  const phone = W < 600;
  const { browser, page, errors, board } = await openBoard({
    viewport: { width: W, height: phone ? 844 : 900 },
    boot: phone ? { hasTouch: true, isMobile: true } : {},
  });
  const counts = () => page.evaluate(() => ({
    shapes: (wbState.sketches || []).filter((s) => !/"type"\s*:\s*"link-/.test(s.data)).length,
    links: (wbState.sketches || []).filter((s) => /"type"\s*:\s*"link-/.test(s.data)).length,
    objects: (wbState.objects || []).length,
  }));

  // 1. The sidebar opens from the top bar on the Library tab.
  await page.click("#wb-add-note");
  await page.waitForTimeout(1200);
  const opened = await page.evaluate(() => {
    const panel = document.getElementById("wb-sidebar-panel");
    const side = document.getElementById("wb-sidebar").getBoundingClientRect();
    const canvas = document.getElementById("whiteboard-container").getBoundingClientRect();
    return {
      open: !panel.classList.contains("hidden"),
      tiles: document.querySelectorAll("#wb-lib-list .wb-lib-tile").length,
      groups: [...document.querySelectorAll("#wb-lib-list .wb-lib-group-head span:nth-child(2)")].map((s) => s.textContent),
      inside: side.left >= canvas.left - 1 && side.right <= canvas.right + 1 && side.bottom <= canvas.bottom + 1,
      hscroll: document.getElementById("wb-sidebar-panel").scrollWidth > document.getElementById("wb-sidebar-panel").clientWidth + 1,
    };
  });
  check(`${W}: the Library button opens the sidebar's library`, opened.open && opened.tiles > 20, opened);
  check(`${W}: the built-in sets are there`, ["General", "Flowchart", "Arrows", "Frames", "Icons", "Yours"].every((g) => opened.groups.includes(g)), opened.groups);
  check(`${W}: the sidebar sits inside the board, no sideways scroll`, opened.inside && !opened.hscroll, opened);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/wblib-${W}-${process.env.THEME || "light"}.png` });

  // 2. Search, then the keyboard: Enter places the decision diamond, announced.
  await page.fill("#wb-lib-search", "decision");
  await page.waitForTimeout(300);
  const found = await page.evaluate(() => [...document.querySelectorAll("#wb-lib-list .wb-lib-tile .wb-lib-name")].map((n) => n.textContent));
  check(`${W}: search finds the decision shape`, found.includes("Decision"), found);
  const c0 = await counts();
  await page.focus("#wb-lib-search");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1200);
  const c1 = await counts();
  const said = await page.textContent("#wb-announcer");
  check(`${W}: Enter places it from the keyboard`, c1.shapes === c0.shapes + 1, { c0, c1 });
  check(`${W}: and it is announced`, /Placed Decision/.test(said), said);
  const placed = await page.evaluate(() => {
    const s = (wbState.sketches || []).at(-1);
    const d = JSON.parse(s.data);
    return { shape: d.shape, fill: d.fill, ref: d.library_ref, selected: wbSelectedItem?.id === s.id, kind: wbUpdateContextBar.sweep?.wbContextKindOf?.() };
  });
  check(`${W}: it is a fillable, selected shape that remembers its source`, placed.shape === "custom" && placed.selected && placed.ref?.builtin === "flowchart/decision", placed);
  // Shift+Enter: a process box joined to the selected diamond.
  await page.fill("#wb-lib-search", "process");
  await page.waitForTimeout(300);
  await page.focus("#wb-lib-search");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Shift+Enter");
  await page.waitForTimeout(1500);
  const c2 = await counts();
  check(`${W}: Shift+Enter places it joined to the selection`, c2.shapes === c1.shapes + 1 && c2.links === c1.links + 1, { c1, c2 });
  // One undo takes the joined place back whole.
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(1000);
  const c3 = await counts();
  check(`${W}: one Undo takes the placement and its link back`, c3.shapes === c1.shapes && c3.links === c1.links, { c1, c3 });

  // 3. Save three linked shapes, place twice: 6 shapes, 4 links, 2 undo steps.
  const ids = await page.evaluate(async (bid) => {
    const make = async (x) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: `M ${x} 600 L ${x + 100} 600 L ${x + 100} 660 L ${x} 660 Z`, shape: "rect", color: "#335599", width: 2 }),
      x: 0, y: 0, z: 5, board_id: bid,
    }) })).id;
    const a = await make(0), b = await make(200), c = await make(400);
    for (const [s, t] of [[a, b], [b, c]]) {
      await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
        data: JSON.stringify({ type: "link-straight", sourceId: s, sourceKind: "sketch", targetId: t, targetKind: "sketch", color: "#000000" }),
        x: 0, y: 0, z: 1, board_id: bid,
      }) });
    }
    await fetchWhiteboardState();
    renderWhiteboardNow();
    clearWbSelection();
    for (const id of [a, b, c]) wbMultiSelection.add(wbMultiKey("sketch", id));
    return [a, b, c];
  }, board.id);
  await page.evaluate(() => { window.promptDialog = async () => "Three in a row"; });
  await page.evaluate(() => wbRunCommand("save-selection"));
  await page.waitForTimeout(1200);
  const saved = await page.evaluate(async () => (await apiJson("/board-library")).items.find((i) => i.name === "Three in a row"));
  check(`${W}: the selection saves to Yours with its two links`, saved && saved.payload.items.length === 3 && saved.payload.links.length === 2, saved?.payload && { items: saved.payload.items.length, links: saved.payload.links.length });
  const before = await counts();
  const undoDepth = await page.evaluate(() => wbUndoStack.length);
  await page.evaluate(async () => {
    await wbLoadLibrary({ force: true });
    const entry = wbLibEntries().find((e) => e.name === "Three in a row");
    await wbLibPlace(entry, [2000, 0]);
    await wbLibPlace(entry, [2000, 600]);
  });
  await page.waitForTimeout(800);
  const after = await counts();
  const undoAfter = await page.evaluate(() => wbUndoStack.length);
  check(`${W}: placed twice: 6 shapes and 4 links more`, after.shapes - before.shapes === 6 && after.links - before.links === 4, { before, after });
  check(`${W}: as two undo steps`, undoAfter - undoDepth === 2, { undoDepth, undoAfter });

  // 4. Export, delete, import: the same item comes back with a new id.
  const round = await page.evaluate(async (id) => {
    const lib = await apiJson("/board-library");
    const res = await api(`/board-library/export?library_id=${lib.yours_id}`);
    const file = await res.json();
    await apiJson(`/board-library/${id}`, { method: "DELETE" });
    const out = await apiJson("/board-library/import", { method: "POST", body: JSON.stringify(file) });
    const back = (await apiJson(`/board-library?library_id=${out.library.id}`)).items.find((i) => i.name === "Three in a row");
    return { items: out.items, back: back && { id: back.id, n: back.payload.items.length, links: back.payload.links.length } };
  }, saved.id);
  check(`${W}: export, delete, import gives it back with a new id`, round.back && round.back.id !== saved.id && round.back.n === 3 && round.back.links === 2, round);

  // 5. Favourite from the keyboard, the Notes and Layers tabs.
  await page.evaluate(() => wbOpenSidebar("library"));
  await page.fill("#wb-lib-search", "");
  await page.waitForTimeout(400);
  await page.focus("#wb-lib-search");
  await page.keyboard.press("ArrowDown");
  const ref = await page.evaluate(() => document.activeElement?.dataset.ref);
  const isFav = () => page.evaluate((r) => [...document.querySelectorAll('#wb-lib-list .wb-lib-group[data-group="favourites"] .wb-lib-tile')].some((t) => t.dataset.ref === r), ref);
  const was = await isFav();
  await page.keyboard.press("f");
  await page.waitForTimeout(1200);
  const now = await isFav();
  check(`${W}: F on a tile stars or unstars it`, Boolean(ref) && now !== was, { ref, was, now });
  check(`${W}: the focus stays on that tile`, await page.evaluate((r) => document.activeElement?.dataset.ref === r, ref));
  await page.click(phone ? "#wb-sidebar-close" : '#wb-sidebar [data-side-tab="layers"]');
  if (phone) {
    await page.evaluate(() => wbOpenSidebar("layers"));
  }
  await page.waitForTimeout(500);
  const layers = await page.evaluate(() => ({
    rows: document.querySelectorAll("#wb-layers-tree [role='treeitem']").length,
    heads: [...document.querySelectorAll("#wb-layers-tree .wb-layer-head")].map((h) => h.textContent),
    named: [...document.querySelectorAll("#wb-layers-tree [role='treeitem']")].every((r) => r.getAttribute("aria-label")),
  }));
  check(`${W}: Layers lists every item, each named`, layers.rows >= 10 && layers.named, layers);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/wblayers-${W}-${process.env.THEME || "light"}.png` });
  check(`${W}: no console errors`, errors.length === 0, errors);
  summary();
  await browser.close();
})();
