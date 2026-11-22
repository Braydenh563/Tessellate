// Audit FEAT-02 (features.md): time from Tab or Enter on a topic to an
// editable new topic, at three map sizes, and how many full renders one add
// costs. The gate: at or under 100ms at 300 topics.
//
//   BASE=http://127.0.0.1:8844 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mmdoc1005-mapaddlatency.js
//
// SIZES=6,101,301 (default) and ADDS=6 per size. Each map is imported from a
// Markdown outline (a root, branches of nine), so it opens in tree-right.
const { boot } = require("./lib.js");

const SIZES = (process.env.SIZES || "6,101,301").split(",").map(Number);
const ADDS = Number(process.env.ADDS || 6);

function outline(n) {
  const lines = ["# Latency " + n, "", "- Centre"];
  let made = 1;
  let b = 0;
  while (made < n) {
    lines.push(`  - Branch ${b}`);
    made++;
    for (let k = 0; k < 9 && made < n; k++, made++) lines.push(`    - Leaf ${b}.${k}`);
    b++;
  }
  return lines.join("\n");
}

(async () => {
  const { page, browser } = await boot();
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(800);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  const report = [];
  for (const n of SIZES) {
    const board = await page.evaluate(async (content) => {
      const b = await apiJson("/whiteboard/boards/import", {
        method: "POST", body: JSON.stringify({ format: "markdown", content }),
      });
      await openWhiteboardBoard(b.id);
      if (typeof wbMapTidyFresh === "function") await wbMapTidyFresh();
      return b;
    }, outline(n));
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
      window.__renders = [];
      if (!window.__wrapped) {
        const real = window.renderWhiteboardNow;
        window.renderWhiteboardNow = function (...args) {
          const t = performance.now();
          const out = real.apply(this, args);
          window.__renders.push(Math.round(performance.now() - t));
          return out;
        };
        window.__wrapped = true;
      }
      document.addEventListener("keydown", (e) => {
        if (e.key === "Tab" || e.key === "Enter") window.__t0 = performance.now();
      }, true);
    });
    const times = [];
    const renders = [];
    for (let k = 0; k < ADDS; k++) {
      // Select a branch (Tab adds a child under it), alternating Tab and Enter.
      const key = k % 2 ? "Enter" : "Tab";
      await page.evaluate((k) => {
        const objs = (wbState.objects || []).filter((o) => /^Branch /.test(o.data?.content || ""));
        const pick = objs[k % objs.length] || (wbState.objects || [])[0];
        selectWbItem("object", pick.id);
        if (k % 2) {
          // Enter on a leaf adds a sibling.
          const leaf = (wbState.objects || []).find((o) => o.parent_id === pick.id);
          if (leaf) selectWbItem("object", leaf.id);
        }
        document.activeElement?.blur?.();
        window.__renders = [];
        window.__t0 = 0;
      }, k);
      await page.waitForTimeout(150);
      const waiter = page.evaluate(() => new Promise((resolve) => {
        const started = performance.now();
        const tick = () => {
          const el = document.activeElement;
          if (el && el.classList?.contains("wb-map-text") && el.isContentEditable && window.__t0) {
            resolve(Math.round(performance.now() - window.__t0));
            return;
          }
          if (performance.now() - started > 5000) { resolve(-1); return; }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }));
      await page.keyboard.press(key);
      const ms = await waiter;
      await page.keyboard.type(`Added ${k}`);
      await page.keyboard.press("Enter");
      await page.waitForTimeout(900);
      times.push(ms);
      renders.push(await page.evaluate(() => window.__renders.slice()));
    }
    const state = await page.evaluate(async (id) => {
      const tree = await apiJson(`/whiteboard/boards/${id}/tree`);
      const all = [];
      const walk = (nodes) => nodes.forEach((x) => { all.push(x.text); walk(x.children); });
      walk(tree.roots);
      return { count: all.length, added: all.filter((t) => /^Added /.test(t)).length };
    }, board.id);
    const sorted = times.slice().sort((a, b) => a - b);
    report.push({ topics: n, times, median: sorted[Math.floor(sorted.length / 2)], renders, ...state });
  }
  console.log(JSON.stringify(report, null, 1));
  await browser.close();
})();
