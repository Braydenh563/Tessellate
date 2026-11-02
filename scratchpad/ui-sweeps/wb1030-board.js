// Audit 1028 board rows, measured: B31 (what a board switch leaves pending),
// B6 (listeners a re-init adds), B7 (deletes), B18 (layout reads of a no-op map
// render), B14 (one export dialog), B17 (link lookups), B19 (bound arrows).
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1030-board.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const other = await page.evaluate(async () => apiJson("/whiteboard/boards", {
    method: "POST", body: JSON.stringify({ name: "wb1030 b " + Date.now(), type: "board" }),
  }));
  // B31: queue frames and timers on this board, then switch.
  const pend = await page.evaluate(async (id) => {
    wbMarkMoving(); wbQueueReveal(); wbScheduleRender(); wbScheduleStickyDates(); wbScheduleCull();
    const before = { moving: document.getElementById("wb-canvas-view").classList.contains("wb-moving"), reveal: wbRevealTimer, render: wbRenderFrame, cull: wbCullFrame, dates: wbStickyDates.timer };
    const p = openWhiteboardBoard(id);
    const during = { moving: document.getElementById("wb-canvas-view").classList.contains("wb-moving"), reveal: wbRevealTimer, render: wbRenderFrame, cull: wbCullFrame, dates: wbStickyDates.timer };
    await p;
    return { before, during };
  }, other.id);
  console.log("B31 pending", JSON.stringify(pend));
  check("B31: nothing queued survives the switch call", !pend.during.moving && !pend.during.reveal && !pend.during.dates, pend);
  await page.waitForTimeout(800);
  // B6: listeners added by a board switch and by a second initWhiteboard.
  const counts = await page.evaluate(async ([a, b]) => {
    const n = { window: 0, document: 0, other: 0 };
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (...args) {
      if (this === window) n.window++; else if (this === document) n.document++; else n.other++;
      return orig.apply(this, args);
    };
    await openWhiteboardBoard(a);
    const switchAdds = { ...n };
    n.window = n.document = n.other = 0;
    await initWhiteboard();
    const reinitAdds = { ...n };
    EventTarget.prototype.addEventListener = orig;
    return { switchAdds, reinitAdds };
  }, [board.id, other.id]);
  console.log("B6 listeners", JSON.stringify(counts));
  check("B6: re-init adds no window or document listener", counts.reinitAdds.window === 0 && counts.reinitAdds.document === 0, counts);
  // B7: the Delete key and the top-level deletes still remove an object and a sketch.
  const del = await page.evaluate(async (id) => {
    await openWhiteboardBoard(id);
    const obj = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "gone" }, board_id: id, x: 10, y: 10, width: 100, height: 40 }) });
    const sk = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify({ d: "M 0 0 L 50 50", color: "#333", width: 2 }), x: 0, y: 0, z: 1, board_id: id }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    const before = { obj: wbState.objects.some((o) => o.id === obj.id), sk: wbState.sketches.some((s) => s.id === sk.id) };
    await wbDeleteObject(wbState.objects.find((o) => o.id === obj.id));
    await wbDeleteSketch(wbState.sketches.find((s) => s.id === sk.id));
    return { before, after: { obj: wbState.objects.some((o) => o.id === obj.id), sk: wbState.sketches.some((s) => s.id === sk.id) }, refs: typeof wbDeleteObjectRef };
  }, other.id);
  console.log("B7", JSON.stringify(del));
  check("B7: deletes remove an object and a sketch with no render ref", del.before.obj && del.before.sk && !del.after.obj && !del.after.sk && del.refs === "undefined", del);
  // B18 and B14 need a map: a fresh one with 200 topics.
  const N = Number(process.env.N || 200);
  const mapBoard = await page.evaluate(async () => {
    const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "wb1030 map " + Date.now(), type: "map" }) });
    await openWhiteboardBoard(b.id);
    return b;
  });
  await page.waitForTimeout(800);
  await page.evaluate(async (n) => {
    const bid = window.currentBoardId;
    const mk = async (i, parent) => {
      const made = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
        board_id: bid, kind: "topic", x: (i % 20) * 200, y: Math.floor(i / 20) * 90, width: 170, height: 52, data: { content: "Topic " + i },
      }) });
      if (parent) await apiJson(`/whiteboard/boards/${bid}/nodes/${made.id}/move`, { method: "PUT", body: JSON.stringify({ parent_id: parent }) });
      return made;
    };
    const root = await mk(0, null);
    for (let i = 1; i < n; i++) await mk(i, root.id);
    await fetchWhiteboardState(bid);
    renderWhiteboardNow();
  }, N);
  await page.waitForTimeout(1500);
  const rm = await page.evaluate(async () => {
    const reads = { n: 0 };
    for (const prop of ["offsetWidth", "offsetHeight"]) {
      const d = Object.getOwnPropertyDescriptor(HTMLElement.prototype, prop);
      Object.defineProperty(HTMLElement.prototype, prop, { configurable: true, get() { reads.n++; return d.get.call(this); } });
    }
    const run = (fn) => { reads.n = 0; const t = performance.now(); fn(); return { ms: +(performance.now() - t).toFixed(1), reads: reads.n }; };
    const noop = [];
    for (let i = 0; i < 3; i++) noop.push(run(() => renderWhiteboardNow()));
    const first = wbState.objects.find((o) => WB_MAP_KINDS.has(o.kind) && o.id !== wbState.objects[0].id) || wbState.objects[1];
    first.data = { ...first.data, content: "Edited topic text that is much longer than before so the box grows" };
    const edit = run(() => renderWhiteboardNow());
    return { count: wbState.objects.length, noop, edit };
  });
  console.log("B18", JSON.stringify(rm));
  check("B18: a no-op render of the map reads layout for at most 10% of the topics", rm.noop[2].reads <= rm.count * 2 * 0.1, rm.noop[2]);
  // B14: the branch export and the whole-map export are one dialog.
  const dlg = await page.evaluate(async () => {
    const read = () => {
      const o = document.querySelectorAll(".wb-export-overlay");
      const card = o[0];
      return { count: o.length, id: card?.getAttribute("aria-label"), go: Boolean(card?.querySelector("#wb-export-go")), on: [...(card?.querySelectorAll("[aria-pressed='true'], [aria-checked='true']") || [])].map((b) => b.textContent.trim()) };
    };
    const root = wbState.objects.find((o) => WB_MAP_KINDS.has(o.kind) && !o.parent_id);
    wbMapExportBranch(root.id);
    const branch = read();
    document.querySelector(".wb-export-overlay #wb-export-go").parentElement.firstChild.click();
    clearWbSelection();
    wbExportBoard();
    const board = read();
    document.querySelector(".wb-export-overlay").remove();
    return { branch, board };
  });
  console.log("B14", JSON.stringify(dlg));
  check("B14: branch and board export open the same dialog, the branch with its scope chosen", dlg.branch.count === 1 && dlg.board.count === 1 && dlg.branch.id === dlg.board.id && dlg.branch.go && dlg.branch.on.some((t) => /election|ranch|opic/i.test(t)), dlg);
  // B17 and B19 on the first board again.
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, board.id);
  await page.waitForTimeout(800);
  const rl = await page.evaluate(() => {
    const pts = (i) => "M " + Array.from({ length: 150 }, (_, k) => `${k * 3 + i} ${(k * 7) % 90}`).join(" L ");
    const sketches = [];
    for (let i = 0; i < 500; i++) sketches.push({ id: 1000 + i, data: JSON.stringify({ d: pts(i), color: "#333", width: 2 }) });
    for (let i = 0; i < 100; i++) sketches.push({ id: 2000 + i, data: JSON.stringify({ type: "link-arrow", sourceId: i, sourceKind: "node", targetId: i + 1, targetKind: "node" }) });
    wbState.sketches = sketches;
    const time = () => { const t = performance.now(); let n = 0; for (let i = 0; i < 20; i++) n += wbLinkedSketchesFor(i % 50, "node").length; return { ms: +(performance.now() - t).toFixed(1), found: n }; };
    const cold = time();
    const warm = time();
    const warm2 = time();
    return { cold, warm, warm2 };
  });
  console.log("B17", JSON.stringify(rl));
  check("B17: warm lookups find the same links", rl.warm.found === rl.cold.found && rl.warm.found > 0, rl);
  const ra = await page.evaluate(async (bid) => {
    const post = (blob) => apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(blob), x: 0, y: 0, z: 1, board_id: bid }) });
    const shape = await post({ d: "M 100 100 L 200 100 L 200 160 L 100 160 Z", shape: "rect", color: "#335599", width: 2, fill: "#88aaee" });
    const arrow = await post({ type: "link-straight", color: "#333", width: 2, endCap: "arrow", sourceId: shape.id, sourceKind: "sketch", targetPoint: { x: 500, y: 130 } });
    await fetchWhiteboardState(); renderWhiteboardNow();
    const startOf = () => document.querySelector(`.sketch-group[data-id="${arrow.id}"] .sketch-path`)?.getAttribute("d") || "";
    const before = startOf();
    const s = wbState.sketches.find((x) => x.id === shape.id);
    const blob = JSON.parse(s.data);
    s.data = JSON.stringify({ ...blob, d: "M 100 100 L 320 100 L 320 160 L 100 160 Z" });
    renderWhiteboardNow();
    return { before, after: startOf() };
  }, board.id);
  console.log("B19", JSON.stringify(ra));
  const x = (d) => Number((d.match(/M\s*([-\d.]+)/) || [])[1]);
  check("B19: the bound arrow's start follows the resized shape's edge", ra.before && ra.after && x(ra.after) > x(ra.before) + 50, ra);
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
