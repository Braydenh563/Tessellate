// INBOX 1352 audit: how the board draws a shape (corner, centre with Alt,
// Shift constraints), which format controls exist, the rail's sizes and
// tooltips, and the status readouts. Numbers only.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/paint1026-audit.js
const { openBoard } = require("./wb1005-lib.js");

async function drag(page, key, from, to, mods = []) {
  await page.keyboard.press("Escape");
  await page.keyboard.press(key);
  for (const m of mods) await page.keyboard.down(m);
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  // A bow in the middle, so a stroke that is not straightened shows it.
  for (let i = 1; i <= 6; i++) await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 6, from[1] + ((to[1] - from[1]) * i) / 6 + (i > 0 && i < 6 ? 40 : 0));
  await page.mouse.up();
  for (const m of mods) await page.keyboard.up(m);
  await page.waitForTimeout(500);
  return page.evaluate(([fx, fy]) => {
    const s = wbState.sketches[wbState.sketches.length - 1];
    if (!s) return null;
    const d = JSON.parse(s.data);
    if (!d.d) return { raw: s.data.slice(0, 160) };
    const b = wbPathBBox(d.d);
    // The press point in board coordinates, to say whether the box grew from it.
    const [px, py] = wbClientToBoard(fx, fy);
    return { shape: d.shape, x: Math.round(b.minX ?? b.x) - Math.round(px), y: Math.round(b.minY ?? b.y) - Math.round(py), w: Math.round(b.w ?? b.width ?? (b.maxX - b.minX)), h: Math.round(b.h ?? b.height ?? (b.maxY - b.minY)) };
  }, from);
}

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const c = await page.locator("#whiteboard-container").boundingBox();
  const cx = c.x + c.width / 2, cy = c.y + c.height / 2;
  const out = {};
  out.rectDown = await drag(page, "r", [cx, cy], [cx + 120, cy + 60]);
  out.rectShiftDown = await drag(page, "r", [cx, cy], [cx + 120, cy + 60], ["Shift"]);
  out.rectShiftUpLeft = await drag(page, "r", [cx, cy], [cx - 60, cy - 120], ["Shift"]);
  out.rectAlt = await drag(page, "r", [cx, cy], [cx + 120, cy + 60], ["Alt"]);
  out.ellipseAlt = await drag(page, "o", [cx, cy], [cx + 120, cy + 60], ["Alt"]);
  out.triShiftUpLeft = await drag(page, "g", [cx, cy], [cx - 60, cy - 120], ["Shift"]);
  out.lineShift = await drag(page, "l", [cx + 200, cy - 250], [cx + 320, cy - 236], ["Shift"]);
  out.penShift = await drag(page, "p", [cx + 200, cy + 200], [cx + 320, cy + 200], ["Shift"]);
  for (const [k, v] of Object.entries(out)) console.log(k.padEnd(16), JSON.stringify(v));

  // The rail: every tool button's size, tooltip and whether it names a key.
  const rail = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("#whiteboard-toolbar button, .wb-toolbar button, [data-tool]")].filter((b) => b.offsetParent);
    const sizes = {};
    let noKey = 0, noTitle = 0;
    for (const b of btns) {
      const r = b.getBoundingClientRect();
      const k = `${Math.round(r.width)}x${Math.round(r.height)}`;
      sizes[k] = (sizes[k] || 0) + 1;
      const t = b.title || b.getAttribute("aria-label") || "";
      if (!t) noTitle++;
      else if (!/\([^)]*\)/.test(t)) noKey++;
    }
    return { visible: btns.length, sizes, noTitle, noKeyInTooltip: noKey };
  });
  console.log("rail", JSON.stringify(rail));
  // Status readouts: zoom, cursor position, size.
  const status = await page.evaluate(() => ({
    zoomReadout: !!document.querySelector("#wb-zoom-level, .wb-zoom-level, #wb-zoom-readout"),
    zoomSlider: !!document.querySelector("#whiteboard-view input[type=range][aria-label*=oom], .wb-zoom input[type=range]"),
    cursorReadout: [...document.querySelectorAll("#library-view-whiteboard *")].some((e) => /^\s*-?\d+\s*,\s*-?\d+\s*(px)?\s*$/.test(e.textContent) && e.children.length === 0),
  }));
  console.log("status", JSON.stringify(status));
  // Stroke and fill controls on the bar (present and visible).
  const fmt = await page.evaluate(() => {
    const ids = ["wb-stroke-width", "wb-dash-style", "wb-stroke-color", "wb-fill-color", "wb-fill-opacity", "wb-fill-none", "wb-stroke-none", "wb-line-end", "wb-corner-radius", "wb-opacity", "wb-font"];
    const r = {};
    for (const id of ids) { const e = document.getElementById(id); r[id] = e ? (e.offsetParent ? "shown" : "hidden") : "absent"; }
    return r;
  });
  console.log("barFormat", JSON.stringify(fmt));
  console.log("errors", errors.length, errors.slice(0, 3));
  await browser.close();
})();
