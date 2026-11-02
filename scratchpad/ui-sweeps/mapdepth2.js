// canvasdepth2 sweeps for the mind map surface, consolidated: one async function per case.
// Run one case by name, or every case in order with no argument:
//   node scratchpad/ui-sweeps/mapdepth2.js mapbranchstructure

// canvasdepth2: a structure per branch (XMind), measured: one main branch as
// an org chart and one as a fishbone inside a tree-right map; nothing
// overlaps, the org chart's topics sit under its top, the lines follow, the
// choice survives a reopen, and one Undo takes it back.
//   BASE=http://127.0.0.1:8860 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdepth2.js mapbranchstructure
async function mapbranchstructure() {
  const { openFresh, checker, openMap, overlapIn } = require("./cd2lib.js");
  const OUTLINE = ["# Plan", "- Plan", "  - Alpha", "    - A1", "    - A2", "    - A3", "  - Beta", "    - B1", "    - B2", "      - B21", "  - Gamma", "    - G1", "    - G2"].join("\n");
    const W = Number(process.env.W || 1440);
    const { browser, page, errors } = await openFresh({ width: W });
    const { check, summary } = checker();
    await openMap(page, OUTLINE);
    await page.evaluate(() => wbMapSetLayout("tree-right"));
    await page.waitForTimeout(900);
    const named = (label) => page.evaluate((l) => wbMapIndex().nodes.find((o) => wbMapLabel(o) === l)?.id, label);
    const alpha = await named("Alpha");
    const beta = await named("Beta");
    // Through the topic's menu, the route a person takes.
    await page.evaluate((id) => {
      const node = wbState.objects.find((o) => o.id === id);
      wbHandleItemClick("object", id, { shiftKey: false });
      const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
      wbOpenMapNodeMenu(node, r.x + 10, r.y + 10);
    }, alpha);
    await page.waitForTimeout(400);
    const menu = await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) [role=menuitem], .wb-ctx-menu:not(.hidden) button")].map((b) => b.textContent.trim()).filter(Boolean).slice(0, 80));
    check("the topic menu offers Structure", menu.some((t) => /^Structure/.test(t)), menu);
    await page.keyboard.press("Escape");
    await page.evaluate(async ([a, b]) => {
      await wbMapSetBranchLayout(wbState.objects.find((o) => o.id === a), "tree-down");
      await wbMapSetBranchLayout(wbState.objects.find((o) => o.id === b), "fishbone");
    }, [alpha, beta]);
    await page.waitForTimeout(900);
    const read = await page.evaluate((a) => {
      const index = wbMapIndex();
      const top = index.byId.get(a);
      const kids = index.childrenOf.get(a);
      const ts = wbMapNodeSize(top);
      return {
        under: kids.every((k) => k.y >= top.y + ts.h - 1),
        bl: kids.map((k) => k._bl),
        edges: kids.map((k) => document.querySelector(`.wb-map-edge[data-child="${k.id}"], .wb-map-edge[data-to="${k.id}"]`)?.getAttribute("d") || null),
        allEdges: document.querySelectorAll("#wb-zoom-group .wb-map-edges .wb-map-edge").length,
        topics: index.nodes.length,
      };
    }, alpha);
    check("the org chart's topics sit under its top", read.under, read);
    check("each topic in it knows its branch's structure", read.bl.every((b) => b === "tree-down"), read.bl);
    check("a line to every topic but the centre", read.allEdges >= read.topics - 1, read);
    const undone = await page.evaluate(async (b) => { await wbUndo(); return wbState.objects.find((o) => o.id === b)?.data?.branch_layout ?? null; }, beta);
    check("one Undo takes the last structure off", undone === null, undone);
    const redone = await page.evaluate(async (b) => { await wbRedo(); return wbState.objects.find((o) => o.id === b)?.data?.branch_layout ?? null; }, beta);
    check("and Redo puts it back", redone === "fishbone", redone);
    await page.waitForTimeout(500);
    const pairs = await overlapIn(page);
    check("nothing overlaps with two structures in a tree map", pairs === 0, pairs);
    for (const layout of ["tree-both", "radial", "timeline", "tree-table"]) {
      await page.evaluate((l) => wbMapSetLayout(l), layout);
      await page.waitForTimeout(900);
      const p = await overlapIn(page);
      check(`nothing overlaps in a ${layout} map`, p === 0, p);
    }
    // Free: only the structured branches are laid out, round their own topic.
    const free = await page.evaluate(async ([a, b]) => {
      await wbMapSetLayout("free");
      const index = wbMapIndex();
      const inside = new Set([...wbMapSubtree(index, a), ...wbMapSubtree(index, b)].map((o) => o.id));
      const before = new Map(index.nodes.map((o) => [o.id, [o.x, o.y]]));
      const positions = wbMapTidyPositions(index, "free");
      return { moved: [...positions.keys()].filter((id) => !inside.has(id)).length, kept: [...before].filter(([id]) => !inside.has(id)).every(([id, p]) => { const o = wbMapIndex().byId.get(id); return o.x === p[0] && o.y === p[1]; }), laid: positions.size };
    }, [alpha, beta]);
    check("on a Free map only the structured branches are laid out", free.moved === 0 && free.laid >= 8, free);
    await page.evaluate(() => wbMapSetLayout("tree-right"));
    await page.waitForTimeout(700);
    const reopen = await page.evaluate(async (a) => { await openWhiteboardBoard(window.currentBoardId); return wbState.objects.find((o) => o.id === a)?.data?.branch_layout; }, alpha);
    check("the structure survives a reopen", reopen === "tree-down", reopen);
    await page.waitForTimeout(600);
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/branchstructure-${W}.png` });
    check("no page errors", errors.length === 0, errors.slice(0, 3));
    summary();
    await browser.close();
}

// canvasdepth2: a callout on a topic (XMind), measured: added through the
// prompt, drawn over the words inside the card, the tidy makes room (no
// overlap), it survives a reopen, and one Undo takes it off.
//   BASE=http://127.0.0.1:8860 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdepth2.js mapcallout
async function mapcallout() {
  const { openFresh, checker, openMap, overlapIn, contrast } = require("./cd2lib.js");
  const OUTLINE = ["# Trip", "- Trip", "  - Book", "    - Flights", "    - Hotel", "    - Car", "  - Pack", "    - Clothes", "    - Charger"].join("\n");
    const W = Number(process.env.W || 1440);
    const { browser, page, errors } = await openFresh({ width: W });
    const { check, summary } = checker();
    await openMap(page, OUTLINE);
    await page.evaluate(() => wbMapSetLayout("tree-right"));
    await page.waitForTimeout(800);
    const hotel = await page.evaluate(() => wbMapIndex().nodes.find((o) => wbMapLabel(o) === "Hotel").id);
    const h0 = await page.evaluate((id) => document.querySelector(`.wb-object[data-id="${id}"]`).offsetHeight, hotel);
    await page.evaluate(async (id) => {
      window.promptDialog = async () => "Near the station, check in after 3";
      await wbMapEditCallout(wbState.objects.find((o) => o.id === id));
    }, hotel);
    await page.waitForTimeout(900);
    const read = await page.evaluate((id) => {
      const el = document.querySelector(`.wb-object[data-id="${id}"]`);
      const c = el.querySelector(".wb-map-callout");
      const t = el.querySelector(".wb-map-text");
      const cr = c.getBoundingClientRect(), tr = t.getBoundingClientRect(), er = el.getBoundingClientRect();
      const cs = getComputedStyle(c);
      return { shown: !c.hidden && cr.height > 0, text: c.textContent, above: cr.bottom <= tr.top + 0.5, inside: cr.left >= er.left - 0.5 && cr.right <= er.right + 0.5 && cr.top >= er.top - 0.5, h: el.offsetHeight, bg: cs.backgroundColor, color: cs.color };
    }, hotel);
    check("the callout is drawn over the words, inside the card", read.shown && read.above && read.inside, read);
    check("its words read on its bubble (4.5:1)", contrast(read.color, read.bg) >= 4.5, { ratio: contrast(read.color, read.bg), ...read });
    console.log("    card height", h0, "to", read.h, "contrast", contrast(read.color, read.bg));
    check("the card grows to hold it", read.h > h0 + 10, { before: h0, after: read.h });
    const pairs = await overlapIn(page);
    check("the tidy makes room: nothing overlaps", pairs === 0, pairs);
    await page.evaluate(async (id) => { window.promptDialog = async () => "Second words"; await wbMapEditCallout(wbState.objects.find((o) => o.id === id)); }, hotel);
    await page.waitForTimeout(500);
    const undone = await page.evaluate(async (id) => { await wbUndo(); return wbState.objects.find((o) => o.id === id)?.data?.callout; }, hotel);
    check("one Undo puts the earlier words back", undone === "Near the station, check in after 3", undone);
    await page.evaluate(async () => { await wbRedo(); await wbUndo(); });
    await page.waitForTimeout(400);
    const back = await page.evaluate(async (id) => { await openWhiteboardBoard(window.currentBoardId); return wbState.objects.find((o) => o.id === id)?.data?.callout; }, hotel);
    check("the callout survives a reopen", back === "Near the station, check in after 3", back);
    await page.waitForTimeout(600);
    const shownAgain = await page.evaluate((id) => !document.querySelector(`.wb-object[data-id="${id}"] .wb-map-callout`).hidden, hotel);
    check("and is drawn again on the reopened map", shownAgain);
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/callout-${W}-${process.env.THEME || "light"}.png` });
    check("no page errors", errors.length === 0, errors.slice(0, 3));
    summary();
    await browser.close();
}

// canvasdepth2: labels under a topic (XMind), measured: added through the
// prompt as a row of chips under the words inside the card, the tidy makes
// room, they read in both themes, survive a reopen, and Undo takes them off.
//   BASE=http://127.0.0.1:8860 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdepth2.js maplabels
async function maplabels() {
  const { openFresh, checker, openMap, overlapIn, contrast } = require("./cd2lib.js");
  const OUTLINE = ["# Trip", "- Trip", "  - Book", "    - Flights", "    - Hotel", "    - Car", "  - Pack", "    - Clothes"].join("\n");
    const W = Number(process.env.W || 1440);
    const { browser, page, errors } = await openFresh({ width: W });
    const { check, summary } = checker();
    await openMap(page, OUTLINE);
    await page.evaluate(() => wbMapSetLayout("tree-right"));
    await page.waitForTimeout(800);
    const hotel = await page.evaluate(() => wbMapIndex().nodes.find((o) => wbMapLabel(o) === "Hotel").id);
    await page.evaluate(async (id) => {
      window.promptDialog = async () => "booked, paid ,  receipt, booked";
      await wbMapEditLabels(wbState.objects.find((o) => o.id === id));
    }, hotel);
    await page.waitForTimeout(900);
    const read = await page.evaluate((id) => {
      const el = document.querySelector(`.wb-object[data-id="${id}"]`);
      const tags = [...el.querySelectorAll(".wb-map-tag")];
      const tr = el.querySelector(".wb-map-text").getBoundingClientRect(), er = el.getBoundingClientRect();
      const rs = tags.map((t) => t.getBoundingClientRect());
      const cs = tags[0] ? getComputedStyle(tags[0]) : null;
      return { words: tags.map((t) => t.textContent), under: rs.every((r) => r.top >= tr.bottom - 0.5), inside: rs.every((r) => r.left >= er.left - 0.5 && r.right <= er.right + 0.5 && r.bottom <= er.bottom + 0.5), h: el.offsetHeight, bg: cs?.backgroundColor, color: cs?.color, data: wbState.objects.find((o) => o.id === id).data.labels };
    }, hotel);
    console.log("    labels", JSON.stringify(read.words), "card", read.h, "contrast", read.bg && contrast(read.color, read.bg));
    check("three labels, trimmed and without the repeat", JSON.stringify(read.words) === '["booked","paid","receipt"]', read);
    check("drawn under the words, inside the card", read.under && read.inside, read);
    check("they read on their chips (4.5:1)", contrast(read.color, read.bg) >= 4.5, read);
    check("the tidy makes room: nothing overlaps", (await overlapIn(page)) === 0);
    const undone = await page.evaluate(async (id) => { await wbUndo(); return wbState.objects.find((o) => o.id === id)?.data?.labels ?? null; }, hotel);
    check("one Undo takes them off", undone === null, undone);
    await page.evaluate(async () => { await wbRedo(); });
    await page.waitForTimeout(500);
    const back = await page.evaluate(async (id) => { await openWhiteboardBoard(window.currentBoardId); return wbState.objects.find((o) => o.id === id)?.data?.labels; }, hotel);
    check("Redo puts them back and they survive a reopen", JSON.stringify(back) === '["booked","paid","receipt"]', back);
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/labels-${W}-${process.env.THEME || "light"}.png` });
    check("no page errors", errors.length === 0, errors.slice(0, 3));
    summary();
    await browser.close();
}

// canvasdepth2: reaction stamps and votes on a topic (Miro; MINDMAP_PLAN
// 14.4), measured: the menu's Stamps group adds one, a press on the chip adds
// another without dragging the topic, the chip is a touch target on a phone,
// the tidy makes room, counts survive a reopen, Undo takes one back.
//   BASE=http://127.0.0.1:8860 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdepth2.js mapstamps
async function mapstamps() {
  const { openFresh, checker, openMap, overlapIn, contrast } = require("./cd2lib.js");
    const W = Number(process.env.W || 1440);
    const { browser, page, errors, phone } = await openFresh({ width: W });
    const { check, summary } = checker();
    await openMap(page, ["# Ideas", "- Ideas", "  - Picnic", "  - Museum", "  - Hike"].join("\n"));
    await page.evaluate(() => wbMapSetLayout("tree-right"));
    await page.waitForTimeout(800);
    const picnic = await page.evaluate(() => wbMapIndex().nodes.find((o) => wbMapLabel(o) === "Picnic").id);
    await page.evaluate((id) => {
      const node = wbState.objects.find((o) => o.id === id);
      wbHandleItemClick("object", id, { shiftKey: false });
      const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
      wbOpenMapNodeMenu(node, r.x + 10, r.y + 10);
    }, picnic);
    await page.waitForTimeout(400);
    const group = await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) button")].map((b) => b.textContent.trim()).find((t) => /Stamps/.test(t)));
    check("the topic menu has a Stamps group", Boolean(group), group);
    await page.keyboard.press("Escape");
    //: A count from before the toggle (the owner's "star 8"): two votes nobody owns.
    await page.evaluate(async (id) => { const o = wbState.objects.find((x) => x.id === id); await wbMapSetExtra(o, { stamps: { up: 2 }, stamped: null }, ""); }, picnic);
    await page.waitForTimeout(700);
    const geo = (id) => page.evaluate((i) => {
      const b = document.querySelector(`.wb-object[data-id="${i}"] .wb-map-stamp[data-stamp="up"]`);
      if (!b) return null;
      const k = b.parentElement.querySelector(".kebab-opener");
      const r = b.getBoundingClientRect(), kr = k.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height, text: b.textContent.trim(), boardH: b.offsetHeight,
        kx: kr.x + kr.width / 2, ky: kr.y + kr.height / 2, kw: kr.width, kh: kr.height, kbw: k.offsetWidth, kbh: k.offsetHeight, pressed: b.getAttribute("aria-pressed"), cardW: b.closest(".wb-map-node").getBoundingClientRect().width };
    }, id);
    const state = (id) => page.evaluate((i) => { const o = wbState.objects.find((x) => x.id === i); return { stamps: o.data.stamps || null, stamped: o.data.stamped || null, x: o.x, y: o.y, text: document.querySelector(`.wb-object[data-id="${i}"] .wb-map-stamp[data-stamp="up"]`)?.textContent.trim() ?? null }; }, id);
    const chip = await geo(picnic);
    check("the chip shows the count", chip.text === "2", chip);
    const min = phone ? 44 : 20;
    check(`the chip is at least ${min} board px tall`, chip.boardH >= min - 0.5, chip);
    check(`the chip's menu opener is at least ${min} board px square`, chip.kbw >= min - 0.5 && chip.kbh >= min - 0.5, { kbw: chip.kbw, kbh: chip.kbh });
    const press = async (g, key) => { if (phone) await page.touchscreen.tap(g[key + "x"] ?? g.x, g[key + "y"] ?? g.y); else await page.mouse.click(g[key + "x"] ?? g.x, g[key + "y"] ?? g.y); await page.waitForTimeout(900); };
    const before = await state(picnic);
    await press(chip, "");
    const mine = await state(picnic);
    check("a press adds yours (2 to 3, yours named)", mine.stamps?.up === 3 && mine.stamped?.[0] === "up" && mine.text === "3", mine);
    check("and does not drag the topic", Math.abs(mine.x - before.x) < 1 && Math.abs(mine.y - before.y) < 1, { before, mine });
    const pressed = await geo(picnic);
    check("yours is aria-pressed", pressed.pressed === "true", pressed.pressed);
    const read = await page.evaluate((id) => { const b = document.querySelector(`.wb-object[data-id="${id}"] .wb-map-stamp`); const cs = getComputedStyle(b); return { bg: cs.backgroundColor, color: cs.color, pinned: !!document.querySelector(`.wb-object[data-id="${id}"].pinned`) }; }, picnic);
    check("its count reads (4.5:1)", contrast(read.color, read.bg) >= 4.5, { ratio: contrast(read.color, read.bg) });
    check("the tidy makes room: nothing overlaps", (await overlapIn(page)) === 0);
    await press(pressed, "");
    const back = await state(picnic);
    check("a second press takes yours back (3 to 2)", back.stamps?.up === 2 && back.stamped === null && back.text === "2", back);
    //: The chip's menu: Remove one, then Clear all.
    const openMenu = async () => { const g = await geo(picnic); await press(g, "k"); await page.waitForTimeout(300); };
    const pick = async (label) => { const ok = await page.evaluate((l) => { const b = [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .sheet-overlay .menu-item")].find((x) => x.textContent.trim() === l); if (!b) return false; b.click(); return true; }, label); await page.waitForTimeout(900); return ok; };
    await openMenu();
    const items = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .sheet-overlay .menu-item")].map((x) => x.textContent.trim()));
    check("the chip's menu offers Remove one and Clear all", items.includes("Remove one") && items.includes("Clear all"), items);
    check("Remove one", (await pick("Remove one")) && (await state(picnic)).stamps?.up === 1);
    await openMenu();
    check("Clear all", (await pick("Clear all")) && (await state(picnic)).stamps === null);
    const undone = await page.evaluate(async (id) => { await wbUndo(); return wbState.objects.find((o) => o.id === id).data.stamps?.up; }, picnic);
    check("one Undo brings Clear all back", undone === 1, undone);
    const reopened = await page.evaluate(async (id) => { await openWhiteboardBoard(window.currentBoardId); return wbState.objects.find((o) => o.id === id)?.data?.stamps; }, picnic);
    check("the count survives a reopen", reopened?.up === 1, reopened);
    console.log("    chip", Math.round(chip.w), "x", Math.round(chip.h), "opener", Math.round(chip.kw), "x", Math.round(chip.kh), "card", Math.round(chip.cardW), "contrast", contrast(read.color, read.bg));
    check("no page errors", errors.length === 0, errors.slice(0, 3));
    summary();
    await browser.close();
}

// canvasdepth2: a map out as .xmind, measured: the export dialog offers
// XMind, its button fits the dialog, the download is a zip named .xmind with
// content.json in it, and the file reads back in as the same map.
//   BASE=http://127.0.0.1:8860 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdepth2.js mapxmind
async function mapxmind() {
  const { openFresh, checker, openMap } = require("./cd2lib.js");
    const W = Number(process.env.W || 1440);
    const { browser, page, errors } = await openFresh({ width: W });
    const { check, summary } = checker();
    await openMap(page, ["# Trip", "- Trip", "  - Book", "    - Hotel", "  - Pack"].join("\n"));
    await page.evaluate(() => wbExportBoard());
    await page.waitForTimeout(500);
    const seg = await page.evaluate(() => {
      const b = [...document.querySelectorAll(".wb-export-seg button")].find((x) => x.textContent.trim() === "XMind");
      const dlg = b?.closest("dialog, .modal, [role=dialog]");
      const r = b?.getBoundingClientRect(), d = dlg?.getBoundingClientRect();
      return b ? { w: r.width, h: r.height, inside: r.left >= d.left && r.right <= d.right + 0.5, wrapW: b.parentElement.scrollWidth, wrapC: b.parentElement.clientWidth } : null;
    });
    check("the export dialog offers XMind, inside the dialog", seg && seg.inside, seg);
    check("its row does not scroll sideways", seg && seg.wrapW <= seg.wrapC + 1, seg);
    await page.keyboard.press("Escape");
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 15000 }),
      page.evaluate(() => wbExportMapText("xmind")),
    ]);
    const path = await download.path();
    const bytes = require("fs").readFileSync(path);
    check("a .xmind file", /\.xmind$/.test(download.suggestedFilename()), download.suggestedFilename());
    check("a zip (PK header)", bytes[0] === 0x50 && bytes[1] === 0x4b, bytes.slice(0, 2));
    const back = await page.evaluate(async (b64) => {
      const made = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "xmind", content: b64, name: "Back" }) });
      const st = await apiJson(`/whiteboard/?board_id=${made.id}`);
      return st.objects.map((o) => o.data.content).sort();
    }, bytes.toString("base64"));
    check("it reads back in as the same four topics", JSON.stringify(back) === JSON.stringify(["Book", "Hotel", "Pack", "Trip"]), back);
    console.log(`    ${bytes.length} bytes, ${download.suggestedFilename()}`);
    check("no page errors", errors.length === 0, errors.slice(0, 3));
    summary();
    await browser.close();
}

const CASES = {
  mapbranchstructure,
  mapcallout,
  maplabels,
  mapstamps,
  mapxmind,
};
const names = process.argv.slice(2);
const unknown = names.filter((n) => !Object.prototype.hasOwnProperty.call(CASES, n));
if (unknown.length) {
  console.error(`unknown case: ${unknown.join(", ")}`);
  console.error(`cases: ${Object.keys(CASES).join(", ")}`);
  process.exit(2);
}
(async () => {
  for (const name of names.length ? names : Object.keys(CASES)) await CASES[name]();
})();
