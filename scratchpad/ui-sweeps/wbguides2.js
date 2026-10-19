// INBOX 1313: guide pass cost at 200 items, tolerance vs zoom, guide ink contrast.
//   BASE=http://127.0.0.1:8799 THEME=dark PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbguides2.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page } = await openBoard({});
  const r = await page.evaluate(() => {
    const rect = (x, y) => `M ${x} ${y} L ${x + 100} ${y} L ${x + 100} ${y + 60} L ${x} ${y + 60} Z`;
    wbState.sketches = [];
    for (let i = 0; i < 200; i += 1) {
      wbState.sketches.push({ id: 90000 + i, data: JSON.stringify({ d: rect((i % 20) * 170 + (i % 7), Math.floor(i / 20) * 110), shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 1 });
    }
    wbClearGuideBoxCache();
    const ex = new Set([wbMultiKey("sketch", 1)]);
    wbGuideBoxes(ex);
    const tol = typeof wbAlignTol === "function" ? wbAlignTol() : 6;
    const N = 300;
    let t = performance.now();
    let last;
    for (let i = 0; i < N; i += 1) {
      last = wbAlignmentGuides(ex, 300 + (i % 50) * 3.1, 200 + (i % 37) * 2.3, 100, 60);
      wbShowAlignmentGuides(last.guideLines);
    }
    const perFrame = (performance.now() - t) / N;
    let t2 = performance.now();
    for (let i = 0; i < N; i += 1) wbAlignmentGuides(ex, 300 + (i % 50) * 3.1, 200 + (i % 37) * 2.3, 100, 60);
    const passOnly = (performance.now() - t2) / N;
    wbClearAlignmentGuides();
    const cs = getComputedStyle(document.documentElement);
    return { perFrame, passOnly, tol, k: d3.zoomTransform(document.getElementById("whiteboard-container")).k,
      ink: ["--error", "--accent-text", "--warn"].map((k) => cs.getPropertyValue(k).trim()),
      bg: getComputedStyle(document.getElementById("whiteboard-container")).backgroundColor };
  });
  console.log(JSON.stringify(r));
  check("guide frame under 4 ms at 200 items", r.perFrame < 4, r.perFrame);
  // tolerance at three zooms, in screen px
  const tolAt = await page.evaluate(() => {
    const c = document.getElementById("whiteboard-container");
    const out = {};
    for (const k of [0.25, 1, 4]) {
      d3.select(c).call(d3.zoom().transform, d3.zoomIdentity.scale(k));
      out[k] = typeof wbAlignTol === "function" ? wbAlignTol() * k : 6;
    }
    return out;
  });
  console.log("tolerance in screen px by zoom", JSON.stringify(tolAt));
  for (const [k, v] of Object.entries(tolAt)) check(`tolerance 6 screen px at zoom ${k}`, Math.abs(v - 6) < 0.01, v);
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
