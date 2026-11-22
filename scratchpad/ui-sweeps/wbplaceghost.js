// The owner, 2026-10-10: "I tried dragging to create a frame and it randomly
// visually cut off half way on the screen??" and "dragging to create any
// object should ghost preview that object, not be the drag selection." The
// frame, sticky and text tools are dragged across most of the canvas, with
// the button held: the preview must cover the whole box the release makes
// (its drawn extent against the box), be drawn as that object (not the
// selection marquee's dashed accent wash), and the release must make it.
//   BASE=http://127.0.0.1:8783 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbplaceghost.js
const { boot } = require("./lib.js");
let fails = 0, passes = 0;
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); ok ? passes++ : fails++; };
(async () => {
  const sizes = (process.env.SIZES || "1440x900,1024x700").split(",").map((s) => s.split("x").map(Number));
  for (const [W, H] of sizes) {
    const { browser, page } = await boot({ viewport: { width: W, height: H } });
    await page.click('[data-tab="library"]');
    await page.waitForTimeout(700);
    await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
    await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
    const board = await page.evaluate(async () => {
      await initWhiteboard();
      return apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Ghost " + Date.now() }) });
    });
    await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
    await page.waitForTimeout(1000);
    await page.evaluate(() => document.querySelector(".wb-empty-hint, #wb-empty-hint")?.remove?.());
    for (const tool of ["frame", "sticky", "text"]) {
      await page.evaluate((tool) => wbSelectToolRef?.(tool) ?? (window.currentTool = tool), tool);
      await page.waitForTimeout(200);
      const c = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
      const from = { x: c.x + c.w * 0.18, y: c.y + c.h * 0.2 };
      const to = { x: c.x + c.w * 0.82, y: c.y + c.h * 0.78 };
      await page.mouse.move(from.x, from.y);
      await page.mouse.down();
      await page.mouse.move(to.x, to.y, { steps: 12 });
      await page.waitForTimeout(150);
      const ghost = await page.evaluate(({ from, to }) => {
        const marquee = document.querySelector(".wb-marquee");
        const g = document.querySelector(".wb-place-ghost");
        const out = { marquee: Boolean(marquee), ghost: null };
        if (marquee) {
          const r = marquee.getBoundingClientRect();
          out.marqueeRect = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
        }
        if (g) {
          const r = g.getBoundingClientRect();
          const cs = getComputedStyle(g);
          out.ghost = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), kind: g.dataset.kind, bg: cs.backgroundColor, border: cs.borderStyle };
          //: The part of the ghost that is visible: clipped by any ancestor?
          let vis = r;
          for (let e = g.parentElement; e && e !== document.body; e = e.parentElement) {
            const ecs = getComputedStyle(e);
            if (ecs.overflow !== "visible" || ecs.clipPath !== "none" || ecs.contain.includes("paint")) {
              const er = e.getBoundingClientRect();
              const l = Math.max(vis.left, er.left), t = Math.max(vis.top, er.top);
              const rr = Math.min(vis.right, er.right), b = Math.min(vis.bottom, er.bottom);
              vis = { left: l, top: t, right: rr, bottom: b };
            }
          }
          out.visibleShare = Math.round((Math.max(0, vis.right - vis.left) * Math.max(0, vis.bottom - vis.top)) / (r.width * r.height) * 100);
        }
        out.wanted = { w: Math.round(to.x - from.x), h: Math.round(to.y - from.y) };
        return out;
      }, { from, to });
      check(!ghost.marquee, `${W}: ${tool}: no selection marquee while placing (${ghost.marquee ? JSON.stringify(ghost.marqueeRect) : "none"})`);
      check(Boolean(ghost.ghost) && ghost.ghost.kind === tool, `${W}: ${tool}: a ghost of the ${tool} is drawn (${JSON.stringify(ghost.ghost)})`);
      if (ghost.ghost) {
        check(Math.abs(ghost.ghost.w - ghost.wanted.w) <= 3 && Math.abs(ghost.ghost.h - ghost.wanted.h) <= 3, `${W}: ${tool}: the ghost is the dragged box (${ghost.ghost.w}x${ghost.ghost.h} for ${ghost.wanted.w}x${ghost.wanted.h})`);
        check(ghost.visibleShare >= 99, `${W}: ${tool}: the whole ghost is visible (${ghost.visibleShare}%)`);
      }
      await page.mouse.up();
      await page.waitForTimeout(900);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
      const made = await page.evaluate((tool) => {
        const o = (wbState.objects || []).filter((o) => (tool === "frame" ? o.kind === "frame" : o.kind === "text")).slice(-1)[0];
        return o && { w: Math.round(o.width), h: Math.round(o.height) };
      }, tool);
      check(Boolean(made), `${W}: ${tool}: the release made it (${JSON.stringify(made)})`);
      await page.evaluate(async () => { for (const o of [...(wbState.objects || [])]) await apiJson(`/whiteboard/objects/${o.id}`, { method: "DELETE" }).catch(() => {}); await fetchWhiteboardState(); renderWhiteboardNow(); });
    }
    //: The selection marquee keeps its canvas: a container that grows
    //: during the drag must not leave the rectangle cut at the old edge.
    if (W === sizes[0][0]) {
      await page.evaluate(() => wbSelectToolRef?.("select") ?? (window.currentTool = "select"));
      await page.setViewportSize({ width: 900, height: H });
      await page.waitForTimeout(300);
      const c0 = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
      await page.mouse.move(c0.x + c0.w * 0.3, c0.y + c0.h * 0.3);
      await page.mouse.down();
      await page.mouse.move(c0.x + c0.w * 0.4, c0.y + c0.h * 0.4, { steps: 4 });
      await page.setViewportSize({ width: W, height: H });
      await page.waitForTimeout(300);
      const c1 = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
      await page.mouse.move(c1.x + c1.w * 0.95, c1.y + c1.h * 0.8, { steps: 6 });
      await page.waitForTimeout(150);
      const m = await page.evaluate(() => { const el = document.querySelector(".wb-marquee"); const c = document.getElementById("whiteboard-container"); return el && { cw: el.getBoundingClientRect().width, kw: c.clientWidth }; });
      check(Boolean(m) && Math.abs(m.cw - m.kw) <= 1, `${W}: the marquee canvas follows a container that grew mid-drag (${JSON.stringify(m)})`);
      await page.mouse.up();
    }
    await browser.close();
  }
  console.log(`${passes}/${passes + fails}`);
  process.exit(fails ? 1 : 0);
})();
