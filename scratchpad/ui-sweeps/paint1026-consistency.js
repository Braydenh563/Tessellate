// INBOX 1354 item 5 and 1352 gaps 5 and 8: one control height on the
// board's zoom dock and the map's topic strip, and the dock says the zoom.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=960 node scratchpad/ui-sweeps/paint1026-consistency.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 960);
const PHONE = W < 600;

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: W, height: PHONE ? 844 : 900 }, boot: PHONE ? { hasTouch: true, isMobile: true } : {} });
  const dock = () => page.evaluate(() => {
    const p = document.querySelector('[data-panel-id="zoom"]');
    const bs = [...p.querySelectorAll("button")].filter((b) => b.offsetParent);
    return { level: document.getElementById("wb-zoom-level")?.textContent || "", heights: [...new Set(bs.map((b) => Math.round(b.getBoundingClientRect().height)))], widths: bs.map((b) => Math.round(b.getBoundingClientRect().width)), k: Math.round(d3.zoomTransform(document.getElementById("whiteboard-container")).k * 100) };
  });
  let d = await dock();
  console.log("dock", JSON.stringify(d));
  const docked = await page.evaluate(() => Boolean(document.getElementById("wb-zoom-in")?.offsetParent));
  check("the zoom dock says the level", d.level === `${d.k}%`, d);
  check("one height on the zoom dock", d.heights.length <= 1, d.heights);
  if (docked) {
    await page.click("#wb-zoom-in"); await page.waitForTimeout(600);
    const after = await dock();
    check("zoom in updates the level", after.level === `${after.k}%` && after.k !== d.k, after);
    await page.click("#wb-zoom-level"); await page.waitForTimeout(600);
    d = await dock();
    check("the level button goes to 100%", d.level === "100%" && d.k === 100, d);
  } else console.log("the zoom dock is not shown at this width");
  // The map strip.
  const root = await page.evaluate(async () => {
    const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `cons map ${Date.now()}`, type: "map", layout: "tree-right" }) });
    const r = await apiJson(`/whiteboard/boards/${b.id}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", text: "Centre" }) });
    await apiJson(`/whiteboard/boards/${b.id}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", text: "One", parent_id: r.id }) });
    await openWhiteboardBoard(b.id); await wbMapTidyFresh(); wbZoomToFit();
    await new Promise((res) => setTimeout(res, 900));
    return r.id;
  });
  const box = await page.locator(`.wb-object[data-id="${root}"]`).first().boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(500);
  const strip = await page.evaluate(() => {
    const s = document.getElementById("wb-map-strip");
    const ctl = [...s.querySelectorAll("button, select, input, label.wb-colour-well, .wb-well")].filter((b) => b.offsetParent && b.getBoundingClientRect().height > 0);
    const hs = {};
    for (const b of ctl) { const h = Math.round(b.getBoundingClientRect().height); hs[h] = (hs[h] || 0) + 1; }
    return { heights: hs, odd: ctl.map((b) => `${b.id || b.className}:${Math.round(b.getBoundingClientRect().width)}x${Math.round(b.getBoundingClientRect().height)}`) };
  });
  console.log("strip", JSON.stringify(strip.heights));
  check("one control height in the map strip", Object.keys(strip.heights).length === 1, strip.odd);
  const md = await dock();
  check("the map's zoom dock says the level", md.level === `${md.k}%`, md);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
