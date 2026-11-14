// L281: a board opened by clicking its card on the boards landing, timed from the click (not a direct openWhiteboardBoard(id)):
// to the canvas shown, to every item drawn, and the longest task in between. Run three times; the median is reported.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wbopenclick.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page, board } = await openBoard({ title: "wbopenclick-host" });
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const N = 120;
  const target = await ev(async (n) => {
    const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Click target " + Date.now(), type: "board" }) });
    for (let i = 0; i < n; i++) {
      const x = 80 + (i % 12) * 170, y = 80 + Math.floor(i / 12) * 120;
      if (i % 2) await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: `Card ${i}` }, board_id: b.id, x, y, z: 1, width: 140, height: 70 }) });
      else await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b.id, x: 0, y: 0, z: 2, data: JSON.stringify({ d: `M ${x} ${y} L ${x + 140} ${y} L ${x + 140} ${y + 70} L ${x} ${y + 70} Z`, shape: "rect", color: "#335599", width: 2, label: `Shape ${i}` }) }) });
    }
    return b;
  }, N);
  const runs = [];
  for (let r = 0; r < 3; r++) {
    await ev(() => wbShowBoardsLanding());
    await page.waitForTimeout(1500);
    const card = page.locator(".library-board-card", { hasText: target.name }).first();
    await card.waitFor({ timeout: 10000 });
    await ev((n) => {
      window.__open = { long: 0 };
      const po = new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__open.long = Math.max(window.__open.long, e.duration); });
      po.observe({ type: "longtask" }); window.__open.po = po;
      const t0 = performance.now(); window.__open.t0 = t0;
      const tick = () => {
        const shown = !document.getElementById("wb-canvas-view")?.classList.contains("hidden");
        if (shown && !window.__open.shown) window.__open.shown = performance.now() - t0;
        const drawn = document.querySelectorAll("#whiteboard-container .sketch-group, #whiteboard-container [data-object-id], #whiteboard-container .wb-object").length;
        if (drawn >= n && !window.__open.drawn) window.__open.drawn = performance.now() - t0;
        if (!window.__open.drawn && performance.now() - t0 < 15000) requestAnimationFrame(tick);
      };
      document.addEventListener("click", () => { window.__open.t0 = performance.now(); requestAnimationFrame(tick); }, { once: true, capture: true });
    }, N);
    await card.locator(".library-card-title").click();
    await page.waitForFunction(() => window.__open.drawn || performance.now() - window.__open.t0 > 15000, null, { timeout: 20000 });
    runs.push(await ev(() => { window.__open.po.disconnect(); const { shown, drawn, long } = window.__open; return { shown: Math.round(shown), drawn: Math.round(drawn), long: Math.round(long) }; }));
  }
  const med = (k) => runs.map((x) => x[k]).sort((a, b) => a - b)[1];
  console.log(JSON.stringify({ items: N, runs, median: { shown: med("shown"), drawn: med("drawn"), long: med("long") } }));
  check("the canvas shows within 300 ms of the click", med("shown") <= 300, runs);
  check(`all ${N} items are drawn within 1500 ms of the click`, med("drawn") > 0 && med("drawn") <= 1500, runs);
  summary(); await browser.close();
})();
