// The perf probe's board step (owner-asks-audit 1667 f; w34-def1-1111).
// The owner's lag log named "d3.v7.min.js onmousemove 667 ms, forced layout 639 ms" on the Library,
// and no probe step ever opened a board. This seeds one large board (BOARD_OBJECTS, default 400,
// text cards on a grid with a connector every fifth), opens it, and moves the mouse across the
// canvas at CPU=4 (the default; CPU=1 for none), then prints each handler that ran inside a long
// animation frame: count, worst duration and worst forced style and layout.
//   BASE=http://127.0.0.1:8806 [BOARD_OBJECTS=400] [CPU=4] [MOVES=150] node scratchpad/ui-sweeps/boardlag.js
const { boot } = require("./lib.js");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 } });
  const want = Number(process.env.BOARD_OBJECTS || 400);
  const id = await page.evaluate(async (want) => {
    const post = async (path, body) => (await api(path, { method: "POST", body: JSON.stringify(body) })).json();
    const boards = await (await api("/whiteboard/boards")).json();
    let board = boards.find((b) => b.title === "Large board");
    if (!board) {
      board = await post("/whiteboard/boards", { title: "Large board", type: "board" });
      const cols = 25;
      let made = 0;
      while (made < want) {
        const wave = [];
        for (let i = made; i < Math.min(made + 20, want); i += 1) {
          wave.push(post("/whiteboard/objects", {
            kind: "text", board_id: board.id, x: 40 + (i % cols) * 240, y: 40 + Math.floor(i / cols) * 140,
            width: 200, height: 100, data: { content: `Card ${i}` },
          }));
        }
        await Promise.all(wave);
        made += wave.length;
      }
    }
    return board.id;
  }, want);
  console.log("board", id, "objects wanted", want);
  await page.evaluate((id) => openWhiteboardBoard(id), id);
  await page.waitForTimeout(4000);
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => {
    window.__loaf = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) for (const s of e.scripts) window.__loaf.push({ who: `${s.invoker.replace(/\?v=.*/, "")} ${s.sourceURL.split("/").pop().replace(/\?v=.*/, "")}`, d: s.duration, forced: s.forcedStyleAndLayoutDuration, frame: e.duration });
    }).observe({ type: "long-animation-frame" });
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: Number(process.env.CPU || 4) });
  const box = await page.evaluate(() => { const r = document.getElementById("wb-svg-layer")?.getBoundingClientRect() || document.body.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  const moves = Number(process.env.MOVES || 150);
  for (let i = 0; i < moves; i += 1) {
    await page.mouse.move(box.x + 40 + ((i * 23) % (box.w - 80)), box.y + 40 + ((i * 31) % (box.h - 80)));
    await sleep(16);
  }
  await sleep(1500);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  const rows = await page.evaluate(() => window.__loaf);
  const by = {};
  for (const r of rows) {
    const k = by[r.who] || (by[r.who] = { n: 0, worst: 0, forced: 0, frame: 0 });
    k.n += 1;
    k.worst = Math.max(k.worst, r.d);
    k.forced = Math.max(k.forced, r.forced);
    k.frame = Math.max(k.frame, r.frame);
  }
  const top = Object.entries(by).sort((a, b) => b[1].worst - a[1].worst).slice(0, 8);
  console.log("objects on screen", await page.evaluate(() => document.querySelectorAll(".wb-object").length), "long frames", new Set(rows.map((r) => r.frame)).size);
  for (const [who, v] of top) console.log(`${who.padEnd(70)} n=${v.n} worst=${v.worst.toFixed(0)}ms forced=${v.forced.toFixed(0)}ms frame=${v.frame.toFixed(0)}ms`);
  // lag-watch.js wraps every requestAnimationFrame callback, so the rows above name it, not the callback:
  // its owner table (callback name and file) says whose frame it was.
  const owners = await page.evaluate(() => [...LAG_RAF.owners].map(([k, v]) => [k, v.n, v.max]).sort((a, b) => b[2] - a[2]).slice(0, 6));
  for (const [who, n, max] of owners) console.log(`raf ${String(who).slice(0, 90).padEnd(90)} n=${n} max=${max.toFixed(0)}ms`);
  await browser.close();
})();
