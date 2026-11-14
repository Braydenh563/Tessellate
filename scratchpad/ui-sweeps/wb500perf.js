// L-whiteboard-15: board idle and drag cost at 500 objects, with the
// companion off and on (as you). Per kind: 3 s idle, then a 60-step drag
// of one text box with page.mouse. Counts long tasks (PerformanceObserver)
// and rAF gaps over 20 ms; checks the dragged box moved.
//   BASE=http://127.0.0.1:8899 node scratchpad/ui-sweeps/wb500perf.js
const { openBoard, checker } = require("./wb1005-lib.js");
const N = Number(process.env.N || 500);
const KINDS = (process.env.KINDS || "off,me").split(",");
const { check, summary } = checker();

async function watch(page) {
  await page.evaluate(() => {
    window.__lt = 0; window.__gaps = 0; window.__fr = 0; window.__worst = 0; window.__wbOn = true;
    if (!window.__ltObs) {
      window.__ltObs = new PerformanceObserver((l) => { window.__lt += l.getEntries().length; });
      window.__ltObs.observe({ entryTypes: ["longtask"] });
    }
    let last = performance.now();
    const tick = (t) => {
      const d = t - last; last = t; window.__fr += 1;
      if (d > 20) window.__gaps += 1;
      if (d > window.__worst) window.__worst = d;
      if (window.__wbOn) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
const stop = (page) => page.evaluate(() => { window.__wbOn = false; return { longTasks: window.__lt, gaps: window.__gaps, frames: window.__fr, worst: Math.round(window.__worst) }; });

(async () => {
  for (const kind of KINDS) {
    const { browser, page, board, errors } = await openBoard({ title: `wb500 ${kind}` });
    await page.evaluate((k) => {
      localStorage.removeItem("nm-buddy-spots");
      prefs.set("avatar-buddy", k);
      const b = document.getElementById("avatar-buddy");
      if (b) b.value = k;
      syncNameMarkBuddy();
    }, kind);
    await page.evaluate(async ([id, n]) => {
      const cols = Math.ceil(Math.sqrt(n));
      const jobs = [];
      for (let i = 0; i < n; i++) {
        jobs.push(apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
          kind: "text", data: { content: `Item ${i}` }, board_id: id,
          x: (i % cols) * 220, y: Math.floor(i / cols) * 110, z: 1, width: 180, height: 70 }) }));
        if (jobs.length >= 25) await Promise.all(jobs.splice(0));
      }
      await Promise.all(jobs);
      await openWhiteboardBoard(id);
    }, [board.id, N]);
    await page.waitForTimeout(2500);
    await page.evaluate(() => { wbSelectToolRef?.("select"); wbZoomToFit({ animate: false }); });
    await page.waitForTimeout(1500);
    const count = await page.evaluate(() => (wbState.objects || []).length);
    const buddy = await page.evaluate(() => { const b = document.getElementById("nm-buddy"); const r = b && b.getBoundingClientRect(); return !!(r && r.width > 0 && getComputedStyle(b).display !== "none"); });
    await watch(page);
    await page.waitForTimeout(3000);
    const idle = await stop(page);
    // Drag the box nearest the canvas centre.
    const pick = await page.evaluate(() => {
      const r = document.getElementById("whiteboard-container").getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      let best = null, bd = 1e9;
      for (const el of document.querySelectorAll("#whiteboard-container .wb-object")) {
        const b = el.getBoundingClientRect();
        const d = Math.hypot(b.left + b.width / 2 - cx, b.top + b.height / 2 - cy);
        const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        if (d < bd && b.width > 8 && hit && hit.closest(".wb-object") === el) { bd = d; best = { x: b.left + b.width / 2, y: b.top + b.height / 2, id: el.dataset.id || el.id }; }
      }
      return best;
    });
    const before = pick && await page.evaluate((id) => { const n = (wbState.objects || []).find((x) => String(x.id) === String(id).replace(/^\D+/, "")); return n ? [n.x, n.y] : null; }, pick.id);
    await watch(page);
    if (pick) {
      await page.mouse.move(pick.x, pick.y);
      await page.mouse.down();
      for (let i = 1; i <= 60; i++) { await page.mouse.move(pick.x + i * 3, pick.y + i * 2); await page.waitForTimeout(16); }
      await page.mouse.up();
    }
    await page.waitForTimeout(300);
    const drag = await stop(page);
    await page.waitForTimeout(800);
    // Read back from the server: the drag's save is the proof it moved.
    const after = pick && await page.evaluate(async (id) => {
      const st = await apiJson(`/whiteboard/?board_id=${window.currentBoardId}`).catch(() => null);
      const o = (st?.objects || []).find((x) => String(x.id) === String(id));
      return o ? [o.x, o.y] : null;
    }, pick.id);
    console.log(JSON.stringify({ kind, count, buddy, idle, drag, before, after }));
    check(`${kind}: the companion is ${kind === "off" ? "hidden" : "on screen"}`, buddy === (kind !== "off"), buddy);
    check(`${kind}: ${N} objects on the board`, count >= N, count);
    check(`${kind}: no long task at idle`, idle.longTasks === 0, idle);
    check(`${kind}: idle frames have no gap over 50 ms`, idle.worst <= 50, idle);
    check(`${kind}: drag moved the box`, before && after && (after[0] !== before[0] || after[1] !== before[1]), { before, after });
    check(`${kind}: drag gaps over 20 ms under 5% of frames`, drag.gaps <= Math.max(1, drag.frames * 0.05), drag);
    check(`${kind}: no page errors`, errors.length === 0, errors.slice(0, 3));
    await browser.close();
  }
  process.exit(summary() ? 0 : 1);
})();
