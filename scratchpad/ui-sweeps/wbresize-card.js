// one picture card, se grip, 5px steps: where does the box leave the pointer?
const { openBoard } = require("./wb1005-lib.js");
(async () => {
  const { browser, page } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const id = await page.evaluate(async () => {
    const cv = document.createElement("canvas"); cv.width = 1600; cv.height = 1200;
    cv.getContext("2d").fillRect(0, 0, 1600, 1200);
    const blob = await new Promise((r) => cv.toBlob(r, "image/png"));
    const fd = new FormData(); fd.append("file", new File([blob], "p.png", { type: "image/png" }));
    const up = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: fd });
    for (const [x, w] of [[700, 240], [400, 200]]) { wbState.objects.push(await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", x, y: 100, width: w, height: 160, z: 2, board_id: window.currentBoardId, data: { content: "n" } }) })); }
    const entry = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `random ahh sketch\n\n![sketch](${up.url})`, defer_filing: true }) });
    const node = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: entry.id, board_id: window.currentBoardId, x: 200, y: 150, width: 260, height: 220, z: 1 }) });
    wbState.nodes.push(node);
    await refreshEntries([entry.id]);
    renderWhiteboardNow();
    return node.id;
  });
  await page.waitForTimeout(1500);
  await page.evaluate((i) => selectWbItem("node", i), id);
  await page.waitForTimeout(500);
  const snap = () => page.evaluate((i) => {
    const el = document.querySelector(`.node-card[data-id="${i}"]`);
    const h = el.querySelector('.wb-resize-handle[data-handle="se"]').getBoundingClientRect();
    const d = wbState.nodes.find((n) => n.id === i);
    return { w: el.getBoundingClientRect().width, h: el.getBoundingClientRect().height, dw: d.width, dh: d.height, hx: h.left + h.width / 2, hy: h.top + h.height / 2, sw: el.style.width, rg: (() => { const g = document.querySelector('#wb-clone-grips g[data-dir=right] path'); const r = g && g.getBoundingClientRect(); return r ? r.left + r.width / 2 : null; })(), right: el.getBoundingClientRect().right };
  }, id);
  const b = await snap();
  await page.mouse.move(b.hx, b.hy);
  await page.mouse.down();
  for (let d = 5; d <= 120; d += 5) {
    await page.mouse.move(b.hx + d, b.hy + d);
    await page.waitForTimeout(60);
    const s = await snap();
    console.log(d, "box", s.w.toFixed(0), s.h.toFixed(0), "d", s.dw, s.dh, "handle-pointer", (s.hx - (b.hx + d)).toFixed(1), "arrow-right minus box-right", s.rg == null ? null : (s.rg - s.right).toFixed(1));
  }
  await page.mouse.up();
  await browser.close();
})();
