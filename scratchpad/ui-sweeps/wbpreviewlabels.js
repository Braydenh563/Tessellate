// L257: board preview labels never run over another block, another label or the paper's edge.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbpreviewlabels.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({ title: "wbpreviewlabels" });
  const ev = (fn, arg) => page.evaluate(fn, arg);
  await ev(async (bid) => {
    const words = ["Retry budget for the uploader", "Queue depth", "A very long caption for the second card", "Owner", "Next step after that", "Cache", "Rollback plan in full", "Metrics"];
    let i = 0;
    for (let r = 0; r < 2; r++) for (let c = 0; c < 4; c++) {
      await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: words[i++] }, board_id: bid, x: 100 + c * 190, y: 100 + r * 120, z: 1, width: 150, height: 70 }) });
    }
  }, board.id);
  const out = await ev(async (bid) => {
    const boards = await apiJson("/whiteboard/boards");
    const list = Array.isArray(boards) ? boards : boards.boards || boards.items || [];
    const b = list.find((x) => x.id === bid);
    await ensureModule("mapPreview");
    const host = document.createElement("div"); host.style.cssText = "position:fixed;left:0;top:0;width:293px;z-index:99999;background:#fff";
    document.body.append(host);
    const svg = mapPreview(b, { size: "card" }); svg.style.width = "293px"; host.append(svg);
    await new Promise((r) => setTimeout(r, 800));
    const box = (e) => e.getBoundingClientRect();
    const hit = (a, c) => Math.min(a.right, c.right) - Math.max(a.left, c.left) > 0.5 && Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top) > 0.5;
    const inside = (a, c) => a.left >= c.left - 0.5 && a.right <= c.right + 0.5 && a.top >= c.top - 0.5 && a.bottom <= c.bottom + 0.5;
    const labels = [...svg.querySelectorAll(".board-minimap-label")].map(box);
    const blocks = [...svg.querySelectorAll("rect")].filter((r) => !r.classList.contains("board-minimap-paper") && !r.classList.contains("board-minimap-ghost")).map(box);
    const paper = box(svg);
    let overBlock = 0, overLabel = 0, offPaper = 0;
    labels.forEach((l, i) => {
      const own = blocks.filter((b) => inside(l, b));
      overBlock += blocks.filter((b) => !own.includes(b) && hit(l, b)).length;
      overLabel += labels.filter((m, j) => j > i && hit(l, m)).length;
      if (l.left < paper.left - 0.5 || l.right > paper.right + 0.5) offPaper += 1;
    });
    return { items: (b?.preview_items || []).length, labels: labels.length, blocks: blocks.length, overBlock, overLabel, offPaper };
  }, board.id);
  check("the preview draws labels", out.labels > 0, out);
  check("no label runs over another block", out.overBlock === 0, out);
  check("no two labels cross, none leaves the paper", out.overLabel === 0 && out.offPaper === 0, out);
  summary(); await browser.close();
})();
