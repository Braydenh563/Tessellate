// WHITEBOARD_PLAN 1355 item 2: multi-object copy, cut, paste, duplicate, links, undo.
const { openFresh, seedMixed } = require("./wb3-lib.js");
(async () => {
  const env = await openFresh(); const { page } = env;
  const ids = await seedMixed(page, env.board.id); await env.open(env.board.id);
  const res = [];
  const check = (l, ok, d = "") => { res.push(ok); console.log(ok ? "PASS" : "FAIL", l, d); };
  const snap = () => page.evaluate(() => ({
    o: wbState.objects.map((o) => [o.id, o.kind, Math.round(o.x), Math.round(o.y)]),
    s: wbState.sketches.map((s) => [s.id, s.data]),
  }));
  const sel = (keys) => page.evaluate((ks) => { clearWbSelection(); for (const [k, i] of ks) wbMultiSelection.add(wbMultiKey(k, i)); wbApplySelectionHighlight(); wbUpdateSelectionBar(); }, keys);
  const settle = () => page.waitForTimeout(700);
  const links = () => page.evaluate(() => wbState.sketches.map((s) => { try { const p = JSON.parse(s.data); return p.sourceId != null ? { id: s.id, s: p.sourceId, t: p.targetId } : null; } catch { return null; } }).filter(Boolean));
  const undo = async () => { await page.evaluate(() => wbUndo()); await settle(); };
  const redo = async () => { await page.evaluate(() => wbRedo()); await settle(); };
  await page.mouse.move(700, 500);
  const base = await snap();
  await sel([["object", ids.a], ["object", ids.b], ["object", ids.f], ["sketch", ids.sk]]);
  await page.keyboard.press("Control+c"); await page.waitForTimeout(200);
  await page.keyboard.press("Control+v"); await settle();
  let s1 = await snap();
  check("paste adds 3 objects + 1 sketch + 1 link", s1.o.length - base.o.length === 3 && s1.s.length - base.s.length === 2, `objs +${s1.o.length - base.o.length} sketches +${s1.s.length - base.s.length}`);
  const newA = s1.o.find((r) => !base.o.some((b) => b[0] === r[0]) && r[2] === 100 + 24 && r[3] === 100 + 24);
  check("first paste offset one grid step (24,24)", !!newA, JSON.stringify(newA));
  const L = await links(); const nl = L.filter((l) => !base.s.some((b) => b[0] === l.id));
  const newIds = s1.o.filter((r) => !base.o.some((b) => b[0] === r[0])).map((r) => r[0]);
  check("copied link points at the copies", nl.length === 1 && newIds.includes(nl[0].s) && newIds.includes(nl[0].t), JSON.stringify(nl));
  check("no link to the left-behind item", !L.some((l) => l.id !== ids.link2 && (l.t === ids.outside) ), "");
  await page.keyboard.press("Control+v"); await settle();
  let s2 = await snap();
  const second = s2.o.filter((r) => !s1.o.some((b) => b[0] === r[0]) && r[1] === "text");
  check("second paste offset 48", second.some((r) => r[2] === 148 && r[3] === 148), JSON.stringify(second));
  await page.keyboard.press("Control+Shift+v"); await settle();
  let s3 = await snap();
  const third = s3.o.filter((r) => !s2.o.some((b) => b[0] === r[0]) && r[1] === "text");
  check("Ctrl+Shift+V pastes in place (100,100)", third.some((r) => r[2] === 100 && r[3] === 100), JSON.stringify(third));
  await undo(); let u = await snap();
  check("one undo reverses the in-place paste", u.o.length === s2.o.length && u.s.length === s2.s.length, `${u.o.length}/${u.s.length} vs ${s2.o.length}/${s2.s.length}`);
  await redo(); u = await snap();
  check("redo restores it with its link", u.o.length === s3.o.length && u.s.length === s3.s.length, `${u.o.length}/${u.s.length}`);
  const lk = await links(); const ok2 = lk.every((l) => u.o.some((o) => o[0] === l.s) && u.o.some((o) => o[0] === l.t));
  check("after redo every link end exists", ok2, JSON.stringify(lk));
  // duplicate
  const before = await snap();
  await sel([["object", ids.a], ["object", ids.b]]);
  await page.keyboard.press("Control+d"); await settle();
  const after = await snap(); const lk2 = await links();
  check("Ctrl+D copies 2 + their link", after.o.length - before.o.length === 2 && after.s.length - before.s.length === 1, `+${after.o.length - before.o.length}/+${after.s.length - before.s.length}`);
  await undo(); const ud = await snap();
  check("one undo reverses duplicate", ud.o.length === before.o.length && ud.s.length === before.s.length);
  // cut then cross-board paste
  const pre = await snap();
  await sel([["object", ids.a], ["object", ids.b]]);
  await page.keyboard.press("Control+x"); await settle();
  const cut = await snap();
  check("cut removes the items", cut.o.length === pre.o.length - 2, `${pre.o.length}->${cut.o.length}`);
  await undo(); const uc = await snap();
  check("one undo restores a cut (items and link)", uc.o.length === pre.o.length && uc.s.length === pre.s.length, `${uc.o.length}/${uc.s.length} vs ${pre.o.length}/${pre.s.length}`);
  await sel([["object", ids.a], ["object", ids.b]]);
  await page.keyboard.press("Control+c"); await page.waitForTimeout(200);
  const b2 = await page.evaluate(async () => apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "wb3 other", type: "board" }) }));
  await env.open(b2.id);
  await page.mouse.move(700, 500);
  await page.keyboard.press("Control+v"); await settle();
  const x = await snap(); const lx = await links();
  check("cross-board paste: 2 objects, 1 link, in place", x.o.length === 2 && lx.length === 1 && x.o.some((o) => o[2] === 100 && o[3] === 100), JSON.stringify(x.o));
  // timing: 50 items
  await page.evaluate(async () => {
    const items = []; for (let i = 0; i < 50; i++) items.push({ kind: "object", key: "t" + i, payload: { kind: "text", data: { content: "n" + i }, board_id: window.currentBoardId, x: (i % 10) * 220, y: Math.floor(i / 10) * 140, z: 1, width: 200, height: 100, rotation: null, group_id: null } });
    window.__copy50 = { items, things: 50, box: { minX: 0, minY: 0, maxX: 2000, maxY: 700 }, board: window.currentBoardId };
  });
  const t = await page.evaluate(async () => {
    const longs = []; const po = new PerformanceObserver((l) => longs.push(...l.getEntries().map((e) => Math.round(e.duration)))); po.observe({ entryTypes: ["longtask"] });
    const t0 = performance.now(); await wbPlaceCopies(window.__copy50, null, 1); await new Promise((r) => setTimeout(r, 300));
    return { ms: Math.round(performance.now() - t0 - 300), longs };
  });
  console.log("paste 50 items:", JSON.stringify(t));
  console.log(res.every(Boolean) ? "ALL PASS" : "SOME FAIL");
  await env.browser.close();
})();
