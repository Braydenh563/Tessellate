// Audit 1028 B18, measured: layout reads (offsetWidth/offsetHeight) and ms for
// a render of a 200-topic map that changed nothing, and after one text edit.
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1030-map.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const N = Number(process.env.N || 200);

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 }, type: "map", title: "wb1030 map" });
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
  const r = await page.evaluate(async () => {
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
  console.log("B18", JSON.stringify(r));
  check("B18: a no-op render of the map reads layout for at most 10% of the topics", r.noop[2].reads <= r.count * 2 * 0.1, r.noop[2]);
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
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
