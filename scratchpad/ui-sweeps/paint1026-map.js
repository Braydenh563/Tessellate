// INBOX 1352: the mind map's controls, measured at W. The strip's control
// sizes and rows, which tooltips name a key, how wide each menu opens, the
// zoom readout, and whether anything leaves the viewport.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=960 node scratchpad/ui-sweeps/paint1026-map.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 960);
const PHONE = W < 600;

(async () => {
  const { browser, page, errors, board } = await openBoard({
    viewport: { width: W, height: PHONE ? 844 : 900 },
    boot: PHONE ? { hasTouch: true, isMobile: true } : {},
  });
  const root = await page.evaluate(async () => {
    const b = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `paint map ${Date.now()}`, type: "map", layout: "tree-right" }) });
    const r = await apiJson(`/whiteboard/boards/${b.id}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", text: "Centre" }) });
    for (const t of ["One", "Two"]) await apiJson(`/whiteboard/boards/${b.id}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", text: t, parent_id: r.id }) });
    await openWhiteboardBoard(b.id);
    await wbMapTidyFresh();
    wbZoomToFit();
    await new Promise((res) => setTimeout(res, 900));
    return r.id;
  });
  const box = await page.locator(`.wb-object[data-id="${root}"]`).first().boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(500);
  const strip = await page.evaluate(() => {
    const s = document.getElementById("wb-map-strip");
    if (!s || !s.offsetParent) return { shown: false };
    const r = s.getBoundingClientRect();
    const ctl = [...s.querySelectorAll("button, select, input")].filter((b) => b.offsetParent);
    const hs = {};
    for (const b of ctl) { const h = Math.round(b.getBoundingClientRect().height); hs[h] = (hs[h] || 0) + 1; }
    const tops = new Set(ctl.map((b) => Math.round(b.getBoundingClientRect().top / 4)));
    return {
      shown: true, w: Math.round(r.width), left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth,
      controls: ctl.length, heights: hs, rows: tops.size,
      untitled: ctl.filter((b) => !(b.title || b.getAttribute("aria-label"))).length,
      each: ctl.map((b) => `${b.id || b.getAttribute("aria-controls") || b.tagName}:${Math.round(b.getBoundingClientRect().width)}x${Math.round(b.getBoundingClientRect().height)}`),
    };
  });
  console.log("strip", JSON.stringify(strip));
  check("the strip shows on a selected topic", strip.shown, strip);
  if (strip.shown) {
    check("the strip stays inside the viewport", strip.left >= 0 && strip.right <= strip.vw, strip);
    check("one control height", Object.keys(strip.heights).length === 1, strip.heights);
    check("every control is named", strip.untitled === 0, strip.untitled);
    for (const id of ["wb-map-text-menu", "wb-map-shape-menu", "wb-map-line-menu"]) {
      const opener = await page.$(`#wb-map-strip [aria-controls="${id}"], #wb-map-strip [data-menu="${id}"]`);
      if (!opener) { console.log("no opener for", id); continue; }
      await opener.evaluate((b) => b.click());
      await page.waitForTimeout(300);
      const m = await page.evaluate((mid) => {
        const e = document.getElementById(mid);
        if (!e || e.classList.contains("hidden") || !e.getClientRects().length) return null;
        const r = e.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left), right: Math.round(r.right), bottom: Math.round(r.bottom), vw: innerWidth, vh: innerHeight };
      }, id);
      check(`${id} opens inside the viewport and under 360 wide`, m && m.left >= 0 && m.right <= m.vw && m.bottom <= m.vh && m.w <= 360, m);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
    }
  }
  const zoom = await page.evaluate(() => {
    const z = document.querySelector('[data-panel-id="zoom"]');
    return { text: (z?.textContent || "").trim(), pct: /\d+%/.test(z?.textContent || "") };
  });
  check("the zoom dock says the zoom level", zoom.pct, zoom);
  check("no page errors", errors.length === 0, errors.slice(0, 2));
  summary();
  await browser.close();
})();
