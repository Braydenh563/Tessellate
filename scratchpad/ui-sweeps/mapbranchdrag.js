// **Does a branch drag still carry its branch, and do the lines still
// follow?** (MINDMAP_PLAN.md 13a.)
//
// `mapperf.js` says how fast the drag is and nothing about whether it is
// still right, and 13a made the pick-up cheap by caching four things that
// used to be looked up fresh: a topic's measured box, the element each moved
// item is drawn as, the elements an edge is drawn from, and the canvas box.
// Each of those can go wrong silently and in a way no lint can see: an edge
// claimed by one end of a branch and then never redrawn, a topic anchored to
// a box it no longer has, a moved item whose element reference is stale.
//
// So this is the correctness half, and it is deliberately small and fast
// (about fifteen seconds against mapperf's three minutes): one six-topic map,
// one real drag of a middle topic, and the four questions that would each
// catch one of those caches being wrong. The last one is the resize case,
// which is the only gesture that changes a topic's box without a render.
//
//   BASE=http://127.0.0.1:8805 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mapbranchdrag.js
const { boot } = require("./lib.js");
const out = [];
const check = (l, ok, d) => { out.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({});
  await page.click('[data-tab="library"]'); await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]'); await page.waitForTimeout(1200);
  await page.evaluate(async () => { const v = document.getElementById("library-view-whiteboard"); for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v); await initWhiteboard(); });
  await page.waitForTimeout(500);
  const md = "# Branch\n- Root\n  - Mid\n    - Leaf one\n    - Leaf two\n  - Other";
  const board = await page.evaluate(async ([c]) => apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: c, name: "Branch drag" }) }), [md]);
  await page.evaluate(async ([id]) => { await openWhiteboardBoard(id); await new Promise(r => setTimeout(r, 900)); }, [board.id]);
  await page.waitForTimeout(600);
  const before = await page.evaluate(() => {
    const idx = wbMapIndex();
    const mid = idx.nodes.find(n => wbMapLabel(n).includes("Mid"));
    const kids = (idx.childrenOf.get(mid.id) || []).map(k => ({ id: k.id, x: k.x, y: k.y }));
    const el = document.querySelector(`.wb-object[data-id="${mid.id}"]`).getBoundingClientRect();
    const edge = document.querySelector(`.wb-map-edge[data-parent="${mid.id}"]`);
    return { mid: { id: mid.id, x: mid.x, y: mid.y }, kids, screen: { x: el.left + el.width / 2, y: el.top + el.height / 2 }, edgeD: edge?.getAttribute("d"), edgeChild: edge?.dataset.child };
  });
  await page.mouse.move(before.screen.x, before.screen.y);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(before.screen.x + i * 8, before.screen.y + i * 4); await page.waitForTimeout(12); }
  const mid = await page.evaluate(() => {
    const idx = wbMapIndex();
    const m = idx.nodes.find(n => wbMapLabel(n).includes("Mid"));
    const kids = (idx.childrenOf.get(m.id) || []).map(k => ({ id: k.id, x: k.x, y: k.y }));
    const edge = document.querySelector(`.wb-map-edge[data-parent="${m.id}"]`);
    return { x: m.x, y: m.y, kids, edgeD: edge?.getAttribute("d") };
  });
  await page.mouse.up();
  await page.waitForTimeout(900);
  const dx = Math.round(mid.x - before.mid.x), dy = Math.round(mid.y - before.mid.y);
  check("the dragged topic moved", Math.abs(dx) > 20 && Math.abs(dy) > 5, `dx ${dx} dy ${dy}`);
  const kidDeltas = mid.kids.map((k, i) => [Math.round(k.x - before.kids[i].x), Math.round(k.y - before.kids[i].y)]);
  check("its children came with it, by the same delta", kidDeltas.every(([a, b]) => Math.abs(a - dx) <= 1 && Math.abs(b - dy) <= 1), JSON.stringify(kidDeltas) + ` vs [${dx},${dy}]`);
  check("the line into a child was redrawn mid-drag", mid.edgeD && mid.edgeD !== before.edgeD, `${(before.edgeD || "").slice(0, 28)} -> ${(mid.edgeD || "").slice(0, 28)}`);
  const after = await page.evaluate(async ([id]) => {
    const tree = await apiJson(`/whiteboard/boards/${id}/tree`);
    const flat = [];
    const walk = (n) => { flat.push({ id: n.id, x: n.x, y: n.y }); for (const c of n.children || []) walk(c); };
    for (const r of tree.roots || tree.nodes || []) walk(r);
    return flat;
  }, [board.id]);
  const savedMid = after.find(o => o.id === before.mid.id);
  const savedKid = after.find(o => o.id === before.kids[0].id);
  check("the move was saved for the topic", Math.abs(savedMid.x - mid.x) <= 1, `${savedMid.x} vs ${mid.x}`);
  check("the move was saved for the branch", Math.abs(savedKid.x - mid.kids[0].x) <= 1, `${savedKid.x} vs ${mid.kids[0].x}`);
  // A resize after the drag: the size cache must not pin the old box.
  const resized = await page.evaluate(async ([id]) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const b0 = wbMapNodeSize({ id, width: 0, height: 0 });
    el.style.width = `${b0.w + 60}px`;
    wbForgetMapNodeSize(id);
    const b1 = wbMapNodeSize({ id, width: 0, height: 0 });
    return { before: b0.w, after: b1.w };
  }, [before.mid.id]);
  check("a topic re-measures once its own entry is dropped", resized.after === resized.before + 60, JSON.stringify(resized));
  console.log(`\n${out.filter(Boolean).length}/${out.length} passed`);
  await browser.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})();
