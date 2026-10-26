// WHITEBOARD_PLAN 1355 item 5: the elements library: search, the Callouts and notes set, open time.
const { openFresh } = require("./wb3-lib.js");
(async () => {
  const env = await openFresh(); const { page } = env;
  const t = await page.evaluate(async () => {
    const longs = []; new PerformanceObserver((l) => longs.push(...l.getEntries().map((e) => Math.round(e.duration)))).observe({ entryTypes: ["longtask"] });
    const t0 = performance.now();
    await wbOpenSidebar("library", { focus: true });
    await new Promise((r) => setTimeout(r, 600));
    return { open: Math.round(performance.now() - t0 - 600), longs };
  });
  console.log("open library", JSON.stringify(t));
  const out = [];
  for (const q of ["callout", "tip", "flowchart", "brace", "arrow", "speech"]) {
    const r = await page.evaluate(async (q) => {
      const input = document.getElementById("wb-lib-search"); input.value = q;
      const t0 = performance.now(); input.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 500));
      const tiles = [...document.querySelectorAll("#wb-lib-grid .wb-lib-tile, .wb-lib-tile")];
      return { tiles: tiles.length, names: tiles.slice(0, 6).map((x) => x.getAttribute("aria-label") || x.textContent.trim().slice(0, 24)) };
    }, q);
    console.log(q, JSON.stringify(r));
  }
  await page.screenshot({ path: process.env.SHOT || "/tmp/wb3-elements.png", clip: { x: 0, y: 60, width: 520, height: 740 } });
  await env.browser.close();
})();
