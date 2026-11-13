// INBOX 816: a selected topic's + and link buttons scale with the topic
// (20 to 35px (INBOX 1450 lets it grow)), sit clear of a neighbour, and below 50% zoom only + shows.
//   BASE=... WT=$PWD node scratchpad/ui-sweeps/mapactions.js
const { boot, openBoardsTab } = require("./lib.js");
(async () => {
  let fails = 0;
  for (const [W, H, touch] of [[1440, 900, false], [390, 844, true]]) {
    const { browser, page } = await boot({ viewport: { width: W, height: H }, hasTouch: touch, isMobile: touch });
    await page.evaluate(() => { const d = document.getElementById("recovery-key-dialog"); if (d && d.open) d.close(); });
    await openBoardsTab(page);
    await page.evaluate(async () => {
      const lines = ["# Zoom", "- Trunk"];
      for (let b = 1; b <= 4; b++) { lines.push(`  - Branch ${b}`); for (let l = 1; l <= 3; l++) lines.push(`    - Leaf ${b}${l}`); }
      const board = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: lines.join("\n"), name: "Zoom " + Date.now() }) });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 1500));
      await wbMapTidy({ quiet: true });
      await new Promise((r) => setTimeout(r, 600));
    });
    if (process.env.LAYOUT) { await page.evaluate((l) => wbMapSetLayout(l), process.env.LAYOUT); await page.waitForTimeout(1500); }
    for (const k of [0.25, 0.5, 1, 2]) {
      const r = await page.evaluate(async (k) => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        const nodes = wbMapIndex().nodes;
        const n = nodes.find((x) => (x.data?.content || "") === "Leaf 22");
        selectWbItem("object", n.id);
        const container = document.getElementById("whiteboard-container");
        const el = () => document.querySelector(`.wb-object[data-id="${n.id}"]`);
        // centre the topic at zoom k
        const rect = container.getBoundingClientRect();
        const cx = n.x + (n.width || 150) / 2, cy = n.y + (n.height || 40) / 2;
        d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(rect.width / 2 - k * cx, rect.height / 2 - k * cy).scale(k));
        await wait(900);
        const T = el().getBoundingClientRect();
        const add = el().querySelector(".wb-map-add"), ref = el().querySelector(".wb-map-ref");
        const rr = (e) => { const b = e.getBoundingClientRect(); return { w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10, l: b.left, t: b.top, r: b.right, b: b.bottom, shown: getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden" && b.width > 0 }; };
        const a = rr(add), l = rr(ref);
        const others = [...document.querySelectorAll(".wb-object.wb-map-node")].filter((o) => o !== el()).map((o) => o.getBoundingClientRect());
        const hit = (x) => x.shown && others.some((o) => !(o.left >= x.r || o.right <= x.l || o.top >= x.b || o.bottom <= x.t));
        const onTopic = (x) => x.shown && !(T.left >= x.r || T.right <= x.l || T.top >= x.b || T.bottom <= x.t);
        const near = others.filter((o) => !(o.left >= a.r - 2.5 || o.right <= a.l + 2.5 || o.top >= a.b || o.bottom <= a.t)).map((o) => [o.left, o.top, o.right, o.bottom].map(Math.round)); const AT = [a.l, a.t, a.r, a.b, l.l, l.t, l.r, l.b].map(Math.round); return { near, AT, T: [T.left, T.top, T.right, T.bottom].map(Math.round), k, topic: [Math.round(T.width), Math.round(T.height)], add: [a.w, a.shown, hit(a)], ref: [l.w, l.shown, hit(l)], addOnTopic: onTopic(a) };
      }, k);
      console.log(`${W} k=${k}`, JSON.stringify(r));
      const ok = r.k >= 0.5 ? true : !r.ref[1];
      const addOk = r.add[1] && r.add[0] >= 19.5 && r.add[0] <= (touch ? 44.5 : 35.5) && (!r.add[2] || r.k < 0.5) && !r.near.length;
      const refOk = r.k < 0.5 ? !r.ref[1] : (r.ref[1] && r.ref[0] >= 19.5 && r.ref[0] <= (touch ? 44.5 : 35.5) && !r.ref[2]);
      if (!addOk || !refOk) { fails++; console.log("  FAIL", JSON.stringify({ addOk, refOk })); }
    }
    await browser.close();
  }
  console.log(fails ? `FAIL: ${fails}` : "PASS");
  process.exit(fails ? 1 : 0);
})();
