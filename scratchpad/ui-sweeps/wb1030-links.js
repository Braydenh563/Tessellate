// Audit 1028 B17, measured: the fallback scan of wbLinkedSketchesFor over a
// board of 600 sketches (500 strokes, 100 links), ms per 20 lookups.
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1030-links.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const r = await page.evaluate(() => {
    const pts = (i) => "M " + Array.from({ length: 150 }, (_, k) => `${k * 3 + i} ${(k * 7) % 90}`).join(" L ");
    const sketches = [];
    for (let i = 0; i < 500; i++) sketches.push({ id: 1000 + i, data: JSON.stringify({ d: pts(i), color: "#333", width: 2 }) });
    for (let i = 0; i < 100; i++) sketches.push({ id: 2000 + i, data: JSON.stringify({ type: "link-arrow", sourceId: i, sourceKind: "node", targetId: i + 1, targetKind: "node" }) });
    wbState.sketches = sketches;
    const time = () => { const t = performance.now(); let n = 0; for (let i = 0; i < 20; i++) n += wbLinkedSketchesFor(i % 50, "node").length; return { ms: +(performance.now() - t).toFixed(1), found: n }; };
    const cold = time();
    const warm = time();
    const warm2 = time();
    return { cold, warm, warm2 };
  });
  console.log("B17", JSON.stringify(r));
  check("B17: warm lookups find the same links", r.warm.found === r.cold.found && r.warm.found > 0, r);
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
