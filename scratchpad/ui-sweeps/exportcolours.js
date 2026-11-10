// The owner, 2026-09-24: "I exported a mindmap selection as an image to the
// library, the mindmap nodes turned white??"
//
// A map (three topics) and a board (two text boxes with no colour of their
// own), each selected and exported through the same builder the Library
// export uses (`wbBuildExportSvg("selection")` then `wbRasterizeSvg`). The
// PNG is written to disk and read with scratchpad/pngpixel.py, and so is a
// screenshot of the board: the pixel inside each box, clear of its words,
// has to match between the two (a map topic's fill; a text box's ink is read
// off its own glyphs as the darkest or lightest pixel along its first line).
//
//   BASE=http://127.0.0.1:8785 SCRATCH=/tmp/mm-mapfix THEME=dark \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/exportcolours.js
const { boot } = require("./lib.js");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const OUT = (process.env.SCRATCH || ".") + "/shots";
const PY = process.env.PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const THEME = process.env.THEME || "light";
let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}
function pixel(file, x, y) {
  const out = execFileSync(PY, [path.join("scratchpad", "pngpixel.py"), file, String(Math.round(x)), String(Math.round(y))], { encoding: "utf8" });
  const m = out.match(/\((\d+), (\d+), (\d+)/);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}
const dist = (a, b) => (a && b ? Math.max(...a.map((v, i) => Math.abs(v - b[i]))) : 999);

async function exportSelection(page, file) {
  const res = await page.evaluate(async () => {
    const { svg, width, height } = wbBuildExportSvg("selection");
    const blob = await wbRasterizeSvg(svg, width, height, "image/png");
    const buf = new Uint8Array(await blob.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    const b = wbSelectionBounds();
    return { b64: btoa(bin), minX: b.minX, minY: b.minY };
  });
  fs.writeFileSync(file, Buffer.from(res.b64, "base64"));
  return res;
}

async function openNew(page, name, kind) {
  await page.evaluate(() => document.querySelector('[data-tab="library"]')?.click());
  await page.waitForTimeout(500);
  await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]')?.click());
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new")?.click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", name);
  if (kind === "map") await page.click('#wb-template-kind button[data-value="map"]');
  await page.click("#wb-template-create");
  await page.waitForFunction((kind) => (kind === "map" ? wbIsMap() && wbMapIndex().roots.length > 0 : Boolean(window.currentBoardId)), kind, { timeout: 90000 });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const { browser, page } = await boot({});
  // --- the map ---------------------------------------------------------------
  await openNew(page, `Export colours ${THEME}`, "map");
  const ids = await page.evaluate(async () => {
    const root = wbMapIndex().roots[0];
    const a = await wbMapAddChild(root.id);
    const b = await wbMapAddChild(root.id);
    return [root.id, a.id, b.id];
  });
  await page.waitForTimeout(1200);
  await page.mouse.click(1300, 760);
  await page.waitForTimeout(300);
  await page.evaluate((ids) => {
    wbSelectedItem = null;
    wbMultiSelection.clear();
    for (const id of ids) wbMultiSelection.add(wbMultiKey("object", id));
    wbApplySelectionHighlight();
  }, ids);
  await page.waitForTimeout(300);
  const shot = `${OUT}/exportcolours-${THEME}-screen.png`;
  const png = `${OUT}/exportcolours-${THEME}-map.png`;
  // The screen is read with the selection outline off, so the pixel is the
  // topic's own fill rather than the selection ring.
  const probes = await page.evaluate((ids) => ids.map((id) => {
    const el = document.querySelector(`#wb-html-layer .wb-object[data-id="${id}"]`);
    const r = el.getBoundingClientRect();
    const node = wbState.objects.find((o) => o.id === id);
    const size = wbMapNodeSize(node);
    // Half way across and 5px under the top edge: inside the box, above the
    // line of words, clear of the spine (left) and the fold chevron (right).
    return { id, sx: r.left + r.width / 2, sy: r.top + 5, bx: node.x + size.w / 2, by: node.y + 5 };
  }), ids);
  // A branch: a ribbon is a closed outline out along one side and back along
  // the other, so the midpoint of its quarter and three-quarter points is
  // inside the ribbon, in board coordinates and on screen.
  const ribbon = await page.evaluate(() => {
    const path = document.querySelector(".wb-map-edges .wb-map-edge");
    if (!path) return null;
    const len = path.getTotalLength();
    const a = path.getPointAtLength(len * 0.25), b = path.getPointAtLength(len * 0.75);
    const bx = (a.x + b.x) / 2, by = (a.y + b.y) / 2;
    const m = path.getScreenCTM();
    return { bx, by, sx: m.a * bx + m.c * by + m.e, sy: m.b * bx + m.d * by + m.f };
  });
  const exp = await exportSelection(page, png);
  await page.evaluate(() => { wbMultiSelection.clear(); wbApplySelectionHighlight(); });
  await page.waitForTimeout(300);
  await page.screenshot({ path: shot });
  for (const p of probes) {
    const onScreen = pixel(shot, p.sx, p.sy);
    const inPng = pixel(png, p.bx - exp.minX, p.by - exp.minY);
    check(`${THEME} map topic ${p.id}: the export's fill is the screen's`, dist(onScreen, inPng) <= 12,
      `screen ${onScreen} export ${inPng}`);
  }
  if (ribbon) {
    const onScreen = pixel(shot, ribbon.sx, ribbon.sy);
    const inPng = pixel(png, ribbon.bx - exp.minX, ribbon.by - exp.minY);
    check(`${THEME} a branch: the export's colour is the screen's`, dist(onScreen, inPng) <= 40,
      `screen ${onScreen} export ${inPng}`);
  }
  // --- a board's text boxes ----------------------------------------------------
  await openNew(page, `Export ink ${THEME}`, "board");
  const boxes = await page.evaluate(async () => {
    const one = await wbCreateObject("text", { content: "MMMMMMMM" }, 200, 200, 240, 80);
    const two = await wbCreateObject("text", { content: "WWWWWWWW" }, 520, 200, 240, 80);
    return [one.id, two.id];
  });
  await page.waitForTimeout(1200);
  await page.mouse.click(1300, 760);
  await page.evaluate((ids) => {
    for (const id of ids) wbMultiSelection.add(wbMultiKey("object", id));
    wbApplySelectionHighlight();
  }, boxes);
  const png2 = `${OUT}/exportcolours-${THEME}-board.png`;
  const exp2 = await exportSelection(page, png2);
  const bg = pixel(png2, 4, 4);
  // The ink is whichever pixel along the first line differs most from the
  // ground: glyphs are the only thing drawn there.
  for (const id of boxes) {
    const o = await page.evaluate((id) => { const x = wbState.objects.find((q) => q.id === id); return { x: x.x, y: x.y }; }, id);
    let best = null, bestD = -1;
    for (let dx = 10; dx < 150; dx += 2) {
      const p = pixel(png2, o.x - exp2.minX + dx, o.y - exp2.minY + 20);
      const d = dist(p, bg);
      if (d > bestD) { bestD = d; best = p; }
    }
    const ink = await page.evaluate((id) => getComputedStyle(document.querySelector(`#wb-html-layer .wb-object[data-id="${id}"] .wb-text-content`)).color, id);
    const want = ink.match(/\d+/g).slice(0, 3).map(Number);
    check(`${THEME} text box ${id}: the export's ink is the screen's`, dist(best, want) <= 40,
      `screen ink ${want} export darkest-contrast pixel ${best} on ground ${bg}`);
  }
  await browser.close();
  console.log(failures ? `${failures} failed` : "all passed");
  process.exit(failures ? 1 : 0);
})();
