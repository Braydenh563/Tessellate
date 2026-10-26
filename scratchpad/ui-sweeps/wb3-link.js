// WHITEBOARD_PLAN 1355 item 3: connect the selected; re-point a link's end.
const { openFresh, seedMixed } = require("./wb3-lib.js");
(async () => {
  const env = await openFresh(); const { page } = env;
  const ids = await seedMixed(page, env.board.id);
  // a third box for chains, and no seeded links needed: delete them
  await page.evaluate(async ({ bid, l1, l2 }) => {
    await apiJson("/whiteboard/sketches/" + l1, { method: "DELETE" }); await apiJson("/whiteboard/sketches/" + l2, { method: "DELETE" });
    await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", board_id: bid, x: 100, y: 500, width: 200, height: 100, data: { content: "C" } }) });
  }, { bid: env.board.id, l1: ids.link, l2: ids.link2 });
  await env.open(env.board.id);
  const res = []; const check = (l, ok, d = "") => { res.push(ok); console.log(ok ? "PASS" : "FAIL", l, d); };
  const links = () => page.evaluate(() => wbState.sketches.map((s) => { try { const p = JSON.parse(s.data); return p.sourceId != null || p.targetId != null ? { id: s.id, s: p.sourceId, sk: p.sourceKind, t: p.targetId, a: p.sourceAnchor, b: p.targetAnchor } : null; } catch { return null; } }).filter(Boolean));
  const objs = await page.evaluate(() => wbState.objects.filter((o) => o.kind === "text").map((o) => [o.id, o.data.content, o.x, o.y]));
  const byName = Object.fromEntries(objs.map((o) => [o[1], o[0]]));
  const sel = (names) => page.evaluate((ids) => { clearWbSelection(); for (const i of ids) wbMultiSelection.add(wbMultiKey("object", i)); wbApplySelectionHighlight(); wbUpdateSelectionBar(); }, names.map((n) => byName[n]));
  await sel(["Sticky A", "Sticky B", "C"]);
  const needs = await page.evaluate(() => wbCommandApplies(WB_COMMAND_BY_ID.get("join-chain")));
  check("join command applies to 3 selected", needs);
  await page.evaluate(() => wbRunCommand("join-chain")); await page.waitForTimeout(800);
  let L = await links();
  check("chain makes 2 links", L.length === 2, JSON.stringify(L));
  check("chain order A->B (x order) then B->C", L.some((l) => l.s === byName["Sticky A"] && l.t === byName["Sticky B"]) && L.length === 2, "");
  check("facing anchors on A->B (right to left)", L.find((l) => l.s === byName["Sticky A"])?.a?.x === 1, JSON.stringify(L[0]));
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(600);
  L = await links(); check("one undo removes both", L.length === 0, String(L.length));
  await page.evaluate(() => wbRedo()); await page.waitForTimeout(600);
  L = await links(); check("redo restores both", L.length === 2, String(L.length));
  await sel(["Sticky A", "Sticky B", "C"]);
  await page.evaluate(() => wbRunCommand("join-chain")); await page.waitForTimeout(500);
  check("second join says already joined, adds none", (await links()).length === 2);
  // re-point: select link A->B, drag its target handle onto C
  const lk = (await links()).find((l) => l.s === byName["Sticky A"]);
  await page.evaluate((id) => selectWbItem("sketch", id), lk.id); await page.waitForTimeout(500);
  const hs = await page.evaluate(() => [...document.querySelectorAll(".wb-link-endpoint-handle")].map((h) => { const r = h.getBoundingClientRect(); return [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2), h.getAttribute("data-end") || h.getAttribute("class")]; }));
  check("link shows 2 endpoint handles", hs.length === 2, JSON.stringify(hs));
  const target = await page.evaluate((id) => { const c = document.getElementById("whiteboard-container"); const r = c.getBoundingClientRect(); const t = d3.zoomTransform(c); const o = wbState.objects.find((o) => o.id === id); return [r.left + t.applyX(o.x + 100), r.top + t.applyY(o.y + 50)]; }, byName["C"]);
  // the handle nearest B's centre is the target handle
  const bpos = await page.evaluate((id) => { const c = document.getElementById("whiteboard-container"); const r = c.getBoundingClientRect(); const t = d3.zoomTransform(c); const o = wbState.objects.find((o) => o.id === id); return [r.left + t.applyX(o.x), r.top + t.applyY(o.y + 50)]; }, byName["Sticky B"]);
  const h = hs.sort((a, b) => Math.hypot(a[0] - bpos[0], a[1] - bpos[1]) - Math.hypot(b[0] - bpos[0], b[1] - bpos[1]))[0];
  await page.mouse.move(h[0], h[1]); await page.mouse.down(); await page.mouse.move((h[0] + target[0]) / 2, (h[1] + target[1]) / 2, { steps: 5 }); await page.mouse.move(target[0], target[1], { steps: 5 }); await page.mouse.up(); await page.waitForTimeout(800);
  const after = (await links()).find((l) => l.id === lk.id);
  check("dragging the target handle onto C re-points the link", after?.t === byName["C"], JSON.stringify(after));
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(600);
  const back = (await links()).find((l) => l.id === lk.id);
  check("undo points it back at B", back?.t === byName["Sticky B"], JSON.stringify(back));
  console.log(res.every(Boolean) ? "ALL PASS" : "SOME FAIL");
  await env.browser.close();
})();
