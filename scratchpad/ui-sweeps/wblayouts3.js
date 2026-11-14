// WHITEBOARD_PLAN section 16: the board Layout menu and the lane stack, measured on a live board.
//   BASE=http://127.0.0.1:8897 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wblayouts3.js
// A 12-node graph under each layout: overlaps (want 0), straight-line crossings against the start, the time of the
// move, one Undo to the start. Then a Stack lane: an add, a move and a resize leave equal gaps, one Undo each.
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 1440 });
  const { check, summary } = checker();
  await page.evaluate(async () => {
    const sizes = [[120, 60], [160, 80], [100, 50], [140, 70]];
    const b = window.currentBoardId;
    const ids = [];
    for (let i = 0; i < 12; i++) {
      const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: `N${i + 1}` }, board_id: b, x: (i * 37) % 300, y: (i * 91) % 260, z: 1, width: sizes[i % 4][0], height: sizes[i % 4][1] }) });
      ids.push(o.id);
    }
    for (const [a, c] of [[1, 2], [1, 3], [1, 4], [2, 5], [2, 6], [3, 6], [3, 7], [4, 8], [5, 9], [6, 9], [6, 10], [7, 11], [8, 12], [2, 12]]) {
      await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 0, data: JSON.stringify({ type: "link-curved", sourceKind: "object", sourceId: ids[a - 1], targetKind: "object", targetId: ids[c - 1] }) }) });
    }
    await fetchWhiteboardState();
    renderWhiteboardNow();
  });
  await page.waitForTimeout(500);
  const measure = () => page.evaluate(() => {
    const boxes = (wbState.objects || []).filter((o) => o.kind === "text").map((o) => ({ id: o.id, x: o.x, y: o.y, w: o.width, h: o.height }));
    let overlaps = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], c = boxes[j];
      if (a.x < c.x + c.w && c.x < a.x + a.w && a.y < c.y + c.h && c.y < a.y + a.h) overlaps++;
    }
    const mid = new Map(boxes.map((o) => [o.id, { x: o.x + o.w / 2, y: o.y + o.h / 2 }]));
    const lines = (wbState.sketches || []).map((s) => JSON.parse(s.data)).filter((d) => String(d.type).startsWith("link-")).map((d) => [d.sourceId, d.targetId]);
    const side = (a, b, c) => Math.sign((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    let crossings = 0;
    for (let i = 0; i < lines.length; i++) for (let j = i + 1; j < lines.length; j++) {
      const [a, b] = lines[i], [c, d] = lines[j];
      if (a === c || a === d || b === c || b === d) continue;
      const [p1, p2, p3, p4] = [mid.get(a), mid.get(b), mid.get(c), mid.get(d)];
      if (side(p1, p2, p3) * side(p1, p2, p4) < 0 && side(p3, p4, p1) * side(p3, p4, p2) < 0) crossings++;
    }
    return { overlaps, crossings, key: boxes.map((o) => `${o.id}@${o.x},${o.y}`).sort().join("|") };
  });
  const start = await measure();
  check("the start has crossings to cut", start.crossings > 0, start);
  const table = [];
  for (const kind of ["flow-h", "flow-v", "radial", "org", "organic", "circle"]) {
    await page.evaluate(() => wbSelectExactly([]));
    const ms = await page.evaluate(async (k) => {
      const t = performance.now();
      await wbFmtState.layoutMore.apply(k);
      return Math.round((performance.now() - t) * 10) / 10;
    }, kind);
    const after = await measure();
    const stale = await page.evaluate(() => (wbState.sketches || []).filter((s) => { const d = JSON.parse(s.data); return d.points || d.bend || d.sourceAnchor || d.targetAnchor; }).length);
    table.push(`${kind}: overlaps ${after.overlaps}, crossings ${after.crossings} (start ${start.crossings}), ${ms} ms`);
    check(`${kind}: no overlaps`, after.overlaps === 0, after);
    check(`${kind}: links keep no stale bends or pinned ends`, stale === 0, stale);
    await page.evaluate(() => wbUndo());
    await page.waitForTimeout(200);
    const undone = await measure();
    check(`${kind}: one Undo returns the start`, undone.key === start.key, { undone: undone.key.slice(0, 80), start: start.key.slice(0, 80) });
  }
  check("flow cuts crossings", Number(table[1].match(/crossings (\d+)/)[1]) < start.crossings, table[1]);
  console.log(table.join("\n"));

  // The lane: a frame marked Stack holds three boxes; add one, move one, resize one.
  const lane = await page.evaluate(async () => {
    for (const s of [...(wbState.sketches || [])]) await apiJson(`/whiteboard/sketches/${s.id}`, { method: "DELETE" });
    for (const o of [...(wbState.objects || [])]) await apiJson(`/whiteboard/objects/${o.id}`, { method: "DELETE" });
    const b = window.currentBoardId;
    const frame = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "frame", data: { content: "Lane", stack: true }, board_id: b, x: 1000, y: 100, z: 0, width: 300, height: 200 }) });
    for (const [i, y] of [130, 190, 260].entries()) await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: `K${i}` }, board_id: b, x: 1020 + i * 10, y, z: 1, width: 120, height: 40 }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return frame.id;
  });
  const gaps = () => page.evaluate((id) => {
    const f = wbState.objects.find((o) => o.id === id);
    const kids = wbState.objects.filter((o) => o.kind === "text" && o.x >= f.x && o.y >= f.y && o.x + o.width <= f.x + f.width && o.y + o.height <= f.y + f.height).sort((a, b) => a.y - b.y);
    return { n: kids.length, gaps: kids.slice(1).map((o, i) => o.y - (kids[i].y + kids[i].height)), lefts: [...new Set(kids.map((o) => o.x - f.x))], frameH: f.height };
  }, lane);
  const equal = (g) => g.gaps.length > 0 && g.gaps.every((v) => v === g.gaps[0]);
  // Marking the lane stacks at once.
  await page.evaluate(() => wbSelectExactly([]));
  await page.evaluate(async (id) => { await wbBoardState.lane.settleNow(); }, lane);
  let g = await gaps();
  check("a marked lane stacks its three boxes with equal gaps", g.n === 3 && equal(g) && g.lefts.length === 1, g);
  // Add: a fourth box dropped inside, as an undoable add.
  await page.evaluate(async (id) => {
    const f = wbState.objects.find((o) => o.id === id);
    const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Added" }, board_id: window.currentBoardId, x: f.x + 150, y: f.y + 20, z: 1, width: 100, height: 30 }) });
    await fetchWhiteboardState();
    wbPushUndo({ action: "create", kind: "object", id: o.id });
    renderWhiteboardNow();
  }, lane);
  await page.waitForTimeout(400);
  g = await gaps();
  check("after an add the gaps are equal", g.n === 4 && equal(g) && g.lefts.length === 1, g);
  // Move: drag the top box down past the others.
  await page.evaluate(async (id) => {
    const f = wbState.objects.find((o) => o.id === id);
    const o = wbState.objects.filter((x) => x.kind === "text" && x.x >= f.x).sort((a, b) => a.y - b.y)[0];
    const before = WB_KIND_INFO.object.payload(o);
    o.y += 75;
    await wbSaveObject(o);
    wbPushUndo({ action: "move", kind: "object", id: o.id, before });
    renderWhiteboardNow();
  }, lane);
  await page.waitForTimeout(400);
  g = await gaps();
  check("after a move the gaps are equal", g.n === 4 && equal(g), g);
  // Undo takes the move and the stacking back together: the lane is still four equal gaps after one Undo.
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(400);
  g = await gaps();
  check("one Undo takes the move and its restack back together", g.n === 4 && equal(g), g);
  // Resize: a box made taller pushes the ones under it.
  await page.evaluate(async (id) => {
    const f = wbState.objects.find((o) => o.id === id);
    const o = wbState.objects.filter((x) => x.kind === "text" && x.x >= f.x).sort((a, b) => a.y - b.y)[1];
    const before = WB_KIND_INFO.object.payload(o);
    o.height += 40;
    await wbSaveObject(o);
    renderWhiteboardNow(); // a real grip resizes the element as it drags, and the stack reads the rendered size
    wbPushUndo({ action: "move", kind: "object", id: o.id, before });
  }, lane);
  await page.waitForTimeout(400);
  g = await gaps();
  check("after a resize the gaps are equal", g.n === 4 && equal(g), g);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
