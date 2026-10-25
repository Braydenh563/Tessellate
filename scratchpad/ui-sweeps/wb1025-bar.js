// The 22-10 bug doc's format bar rows: what the selection bar shows for a
// line, a shape and two items, its size and rows at VW, and whether a line's
// End turns it into an arrow and back.
//   VW=720 BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1025-bar.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
const VW = Number(process.env.VW || 1440), VH = Number(process.env.VH || 900);
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Bar ${Date.now()}` }) })).id);
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  const bar = () => page.evaluate(() => {
    const el = document.getElementById("wb-context");
    const r = el.getBoundingClientRect();
    const groups = [...el.querySelectorAll(".wb-context-group:not(.hidden)")].map((g) => g.dataset.wbCtx);
    const tops = new Set([...el.querySelectorAll(".wb-context-group:not(.hidden)")].map((g) => Math.round(g.getBoundingClientRect().top)));
    const vis = (id) => { const b = document.getElementById(id); return !!b && b.offsetParent !== null && !b.hidden && getComputedStyle(b).display !== "none"; };
    // Overlaps between visible controls (the "clash").
    const ctrls = [...el.querySelectorAll(".wb-context-group:not(.hidden) > *")].filter((c) => c.offsetParent).map((c) => c.getBoundingClientRect());
    let clash = 0;
    for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
      const a = ctrls[i], b = ctrls[j];
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 1 && oy > 1) clash++;
    }
    return { radius: getComputedStyle(el).borderTopLeftRadius, sizes: [...el.querySelectorAll(".wb-cap-size")].filter((c) => (c.closest(".select-shell") || c).offsetParent).length, hidden: el.classList.contains("hidden"), w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left), right: Math.round(r.right), rows: tops.size, groups, clash,
      group: vis("wb-multi-group"), ungroup: vis("wb-multi-ungroup") };
  });
  // A line.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("l");
  await page.mouse.move(box.x + 120, box.y + 200);
  await page.mouse.down();
  await page.mouse.move(box.x + 320, box.y + 260, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(700);
  await page.keyboard.press("v");
  await page.mouse.click(box.x + 220, box.y + 230);
  await page.waitForTimeout(500);
  const line = await bar();
  console.log("line bar", JSON.stringify(line));
  console.log("line groups", JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("#wb-context .wb-context-group:not(.hidden)")].map((g) => { const r = g.getBoundingClientRect(); return [g.dataset.wbCtx, Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }))));
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT, clip: { x: Math.max(0, line.left - 10), y: 370, width: Math.min(VW - Math.max(0, line.left - 10), line.w + 20), height: 190 } });
  ok("line: bar shown in one window", !line.hidden && line.left >= 0 && line.right <= VW, JSON.stringify(line));
  ok("line: no controls overlap", line.clash === 0, String(line.clash));
  ok("line: no end size shown for an end with no mark", line.sizes === 0, String(line.sizes));
  const startLines = await page.evaluate(() => { const gs = [...document.querySelectorAll("#wb-context > .wb-context-group:not(.hidden)")]; return gs.filter((g, i) => i && g.getBoundingClientRect().top > gs[i - 1].getBoundingClientRect().top + 2 && parseFloat(getComputedStyle(g).borderLeftWidth) > 0 && getComputedStyle(g).borderLeftColor !== "rgba(0, 0, 0, 0)").length; });
  ok("line: no row starts with a hairline", startLines === 0, String(startLines) + " " + await page.evaluate(() => JSON.stringify([...document.querySelectorAll("#wb-context > .wb-context-group:not(.hidden)")].map((g) => [g.className, g.offsetTop, getComputedStyle(g).borderLeftWidth]))));
  ok("line: a wrapped bar is not a pill", line.rows === 1 || parseFloat(line.radius) <= 16, `${line.rows} rows, radius ${line.radius}`);
  const kind = () => page.evaluate(() => { const s = wbState.sketches[wbState.sketches.length - 1]; const p = JSON.parse(s.data); return { shape: p.shape, fmt: wbFmtKind({ kind: "sketch", item: s }), end: p.endCap || null, d: p.d.slice(0, 80) }; });
  console.log("line data", JSON.stringify(await kind()));
  // End: an arrow mark.
  const setEnd = (v) => page.evaluate((v) => { const s = document.getElementById("wb-prop-endcap"); s.value = v; s.dispatchEvent(new Event("change", { bubbles: true })); }, v);
  await setEnd("triangle");
  await page.waitForTimeout(700);
  const asArrow = await kind();
  ok("End set to a mark makes it an arrow, still an arrow to the Format panel", /triangle/.test(asArrow.end || "") && asArrow.fmt === "arrow", JSON.stringify(asArrow));
  await setEnd("none");
  await page.waitForTimeout(700);
  const asLine = await kind();
  ok("End set to None makes it a line", asLine.shape === "line" || asLine.end === "none", JSON.stringify(asLine));
  // Two items: Group shows, Ungroup not.
  await page.evaluate(async () => {
    await wbCreateObject("text", { content: "a" }, 400, 300, 120, 60, 2);
    await wbCreateObject("text", { content: "b" }, 560, 300, 120, 60, 2);
    wbScheduleRender();
  });
  await page.waitForTimeout(500);
  await page.evaluate(() => wbSelectAllItems());
  await page.waitForTimeout(400);
  const multi = await bar();
  console.log("multi bar", JSON.stringify(multi));
  ok("multi: Group shows, Ungroup does not", multi.group && !multi.ungroup, JSON.stringify({ g: multi.group, u: multi.ungroup }));
  ok("multi: no overlap, inside the window", multi.clash === 0 && multi.left >= 0 && multi.right <= VW, JSON.stringify(multi));
  const menuRows = () => page.evaluate(async () => {
    const row = document.querySelector('#wb-topbar [data-wb-cmd="group"]');
    const wrap = row.closest(".wb-board-menu");
    const toggle = document.querySelector(`[aria-controls="${wrap.id}"]`);
    toggle.click();
    await new Promise((r) => setTimeout(r, 250));
    const vis = (c) => { const el = wrap.querySelector(`[data-wb-cmd="${c}"]`); return el.getClientRects().length > 0; };
    const out = { group: vis("group"), ungroup: vis("ungroup"), palette: wbPaletteCommands().map((c) => c.label.replace(/^ph:\S+ /, "")).filter((l) => /^(Group|Ungroup)$/.test(l)) };
    toggle.click();
    return out;
  });
  const mixedMenu = await menuRows();
  ok("Arrange menu, two loose items: Group only", mixedMenu.group && !mixedMenu.ungroup && mixedMenu.palette.join() === "Group", JSON.stringify(mixedMenu));
  await page.keyboard.press("Control+g");
  await page.waitForTimeout(600);
  await page.evaluate(() => wbSelectAllItems());
  await page.waitForTimeout(400);
  const grouped = await bar();
  const groupedMenu = await menuRows();
  ok("Arrange menu, one group: Ungroup only", !groupedMenu.group && groupedMenu.ungroup && groupedMenu.palette.join() === "Ungroup", JSON.stringify(groupedMenu));
  // The group plus the line: Group (merge), not both.
  await page.evaluate(async () => { const o = await wbCreateObject("text", { content: "c" }, 400, 420, 120, 60, 2); wbMultiSelection.add(wbMultiKey("object", o.id)); wbApplySelectionHighlight(); wbUpdateContextBar(); wbUpdateSelectionBar(); });
  await page.waitForTimeout(300);
  const mixed = await bar();
  const mixedM = await menuRows();
  ok("a group plus a loose item: Group only, on the bar and in the menu", mixed.group && !mixed.ungroup && mixedM.group && !mixedM.ungroup, JSON.stringify({ bar: [mixed.group, mixed.ungroup], menu: mixedM }));
  ok("grouped: Ungroup shows, Group does not", !grouped.group && grouped.ungroup, JSON.stringify({ g: grouped.group, u: grouped.ungroup }));
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
