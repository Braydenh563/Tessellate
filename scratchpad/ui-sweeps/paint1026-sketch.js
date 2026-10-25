// INBOX 1352: the quick sketch pad, measured. Where a shape grows from (the
// corner, the centre with Alt), what Shift does, the fill modes, the tools'
// tooltips and keys, the status line, and the dialog's fit at W.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1440 node scratchpad/ui-sweeps/paint1026-sketch.js
const { boot } = require("./lib.js");
const W = Number(process.env.W || 1440);
const PHONE = W < 600;

let pass = 0, fail = 0;
function check(name, good, detail) {
  if (good) pass++; else fail++;
  console.log(`${good ? "PASS" : "FAIL"}  ${name}${detail !== undefined ? "  " + JSON.stringify(detail) : ""}`);
}

// The drawn ink's box in canvas pixels, relative to the press point.
async function inkBox(page, from) {
  return page.evaluate(([fx, fy]) => {
    const c = document.getElementById("sketch-canvas");
    const r = c.getBoundingClientRect();
    const sx = c.width / r.width, sy = c.height / r.height;
    const px = (fx - r.left) * sx, py = (fy - r.top) * sy;
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1, filled = 0;
    for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
      if (d[(y * c.width + x) * 4 + 3] > 0) { filled++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    }
    if (x1 < 0) return null;
    // Whether the centre of the box is painted: a filled shape is, an outline is not.
    const mx = Math.round((x0 + x1) / 2), my = Math.round((y0 + y1) / 2);
    const centre = d[(my * c.width + mx) * 4 + 3] > 0;
    return { x: Math.round(x0 - px), y: Math.round(y0 - py), w: x1 - x0 + 1, h: y1 - y0 + 1, centre, filled, scale: +sx.toFixed(3) };
  }, from);
}

async function draw(page, tool, from, to, mods = []) {
  await page.evaluate(() => { const c = document.getElementById("sketch-canvas"); c.getContext("2d").clearRect(0, 0, c.width, c.height); });
  await page.click(`#sketch-tool-${tool}`);
  for (const m of mods) await page.keyboard.down(m);
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 8, from[1] + ((to[1] - from[1]) * i) / 8);
  await page.mouse.up();
  for (const m of mods) await page.keyboard.up(m);
  await page.waitForTimeout(150);
  return inkBox(page, from);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: PHONE ? 844 : 900 }, ...(PHONE ? { hasTouch: true, isMobile: true } : {}) });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluate(() => openSketch());
  await page.waitForFunction(() => typeof sketchTogglePalette === "function");
  await page.waitForTimeout(400);
  page.on("dialog", (d) => d.accept("Hi"));

  const fit = await page.evaluate(() => {
    const card = document.getElementById("sketch-card").getBoundingClientRect();
    const bar = document.getElementById("sketch-toolbar");
    const canvas = document.getElementById("sketch-canvas").getBoundingClientRect();
    const btns = [...bar.querySelectorAll("button, input")].filter((b) => b.offsetParent);
    const tops = new Set(btns.map((b) => Math.round(b.getBoundingClientRect().top)));
    const tips = btns.map((b) => b.title || b.getAttribute("aria-label") || "");
    const tools = [...bar.querySelectorAll("[id^=sketch-tool-]")];
    return {
      cardW: Math.round(card.width), vw: innerWidth, overflowX: document.documentElement.scrollWidth > innerWidth,
      barOverflow: bar.scrollWidth > bar.clientWidth + 1, rows: tops.size, controls: btns.length,
      toolsWithKey: tools.filter((b) => /\([A-Z0-9+]+\)/.test(b.title)).length, tools: tools.length,
      untitled: tips.filter((t) => !t).length,
      canvasW: Math.round(canvas.width), canvasH: Math.round(canvas.height),
      cardBottom: Math.round(card.bottom), vh: innerHeight,
    };
  });
  console.log("fit", JSON.stringify(fit));
  check("no page overflow", !fit.overflowX, fit);
  check("toolbar does not overflow its box", !fit.barOverflow);
  check("the card fits the viewport height", fit.cardBottom <= fit.vh);
  check("every tool's tooltip names its key", fit.toolsWithKey === fit.tools, `${fit.toolsWithKey}/${fit.tools}`);

  const c = await page.locator("#sketch-canvas").boundingBox();
  const cx = c.x + c.width / 2, cy = c.y + c.height / 2;
  const k = c.width / (await page.evaluate(() => document.getElementById("sketch-canvas").width));
  const px = (n) => Math.round(n / k); // screen px to canvas px
  const tol = (a, b) => Math.abs(a - b) <= 8;

  const rect = await draw(page, "rect", [cx, cy], [cx + 120, cy + 60]);
  check("rectangle grows from the press corner", rect && tol(rect.x, 0) && tol(rect.y, 0) && tol(rect.w, px(120)), rect);
  const sq = await draw(page, "rect", [cx, cy], [cx - 60, cy - 120], ["Shift"]);
  check("Shift up-left: a square that ends at the press point", sq && tol(sq.w, sq.h) && tol(sq.x + sq.w, 0) && tol(sq.y + sq.h, 0), sq);
  const alt = await draw(page, "rect", [cx, cy], [cx + 60, cy + 40], ["Alt"]);
  check("Alt: the rectangle grows from its centre", alt && tol(alt.x, -px(60)) && tol(alt.y, -px(40)), alt);
  const ell = await draw(page, "circ", [cx, cy], [cx + 120, cy + 60]);
  check("ellipse: drawn corner to corner, not as a radius", ell && tol(ell.x, 0) && tol(ell.w, px(120)) && tol(ell.h, px(60)), ell);
  const circ = await draw(page, "circ", [cx, cy], [cx + 120, cy + 60], ["Shift"]);
  check("Shift ellipse: a circle", circ && tol(circ.w, circ.h), circ);
  const line = await draw(page, "line", [cx, cy], [cx + 120, cy + 14], ["Shift"]);
  check("Shift line: snapped to 0 or 45 degrees", line && line.h <= 12, line);

  const fillModes = await page.evaluate(() => [...document.querySelectorAll("#sketch-toolbar [data-sketch-fill]")].map((b) => b.dataset.sketchFill));
  check("outline, fill and both modes", ["outline", "fill", "both"].every((m) => fillModes.includes(m)), fillModes);
  if (fillModes.includes("fill")) {
    await page.click('[data-sketch-fill="fill"]');
    const filled = await draw(page, "rect", [cx, cy], [cx + 100, cy + 60]);
    check("fill mode paints the inside", filled && filled.centre, filled);
    await page.click('[data-sketch-fill="outline"]');
  }
  const custom = await page.evaluate(() => !!document.querySelector("#sketch-palette input[type=color]"));
  check("a custom colour in the palette", custom);
  const dropper = await page.evaluate(() => !!document.getElementById("sketch-tool-picker"));
  check("a colour picker tool", dropper);
  const bucket = await page.evaluate(() => !!document.getElementById("sketch-tool-bucket"));
  check("a fill bucket", bucket);
  if (bucket) {
    await draw(page, "rect", [cx - 50, cy - 30], [cx + 50, cy + 30]);
    await page.click("#sketch-tool-bucket");
    await page.mouse.click(cx, cy);
    await page.waitForTimeout(150);
    const b = await inkBox(page, [cx, cy]);
    check("the bucket fills the closed shape", b && b.centre, b);
  }
  // Text in place, not a browser prompt.
  let prompted = false;
  page.once("dialog", () => { prompted = true; });
  await page.click("#sketch-tool-text");
  await page.mouse.click(cx, cy);
  await page.waitForTimeout(200);
  const inline = await page.evaluate(() => !!document.querySelector("#sketch-canvas-wrap .sketch-text-input"));
  check("text is typed in place, not in a prompt", !prompted && inline, { prompted, inline });
  if (inline) { await page.keyboard.type("Hi"); await page.keyboard.press("Enter"); }
  // The status line: canvas size and the pointer.
  await page.mouse.move(cx + 10, cy + 10);
  const status = await page.evaluate(() => document.getElementById("sketch-pos")?.textContent || "");
  check("a status readout with the pointer position", /\d+\s*,\s*\d+/.test(status), status);
  const dl = await page.evaluate(() => !!document.getElementById("sketch-download"));
  check("download as a PNG", dl);
  // Keys: B for the brush and the bracket keys for size.
  await page.keyboard.press("r");
  const rKey = await page.evaluate(() => document.getElementById("sketch-tool-rect").classList.contains("active"));
  check("R picks the rectangle", rKey);
  const before = await page.evaluate(() => sketchPen.size);
  await page.keyboard.press("]");
  const after = await page.evaluate(() => sketchPen.size);
  check("] makes the brush larger", after > before, { before, after });
  check("no page errors", errors.length === 0, errors.slice(0, 2));
  console.log(`${pass}/${pass + fail}`);
  await browser.close();
})();
