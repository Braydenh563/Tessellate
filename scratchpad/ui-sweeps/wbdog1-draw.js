// Dogfood 2026-10-25 item 7: rectangle and circle share one drag model
// (corner to corner). Press at (500,400), drag to (640,480): both shapes'
// screen boxes must be that rectangle.
//   BASE=http://127.0.0.1:8814 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdog1-draw.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page } = await openBoard({});
  const drawn = {};
  for (const tool of ["rect", "circle"]) {
    await page.evaluate((t) => { clearWbSelection(); wbSelectToolRef?.(t); }, tool);
    const n0 = await page.evaluate(() => wbState.sketches.length);
    await page.mouse.move(500, 400);
    await page.mouse.down();
    await page.mouse.move(570, 440, { steps: 5 });
    await page.mouse.move(640, 480, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(900);
    drawn[tool] = await page.evaluate((n0) => {
      const s = wbState.sketches[n0];
      if (!s) return null;
      const g = document.querySelector(`.sketch-group[data-id="${s.id}"] path`) || document.querySelector(`.sketch-group[data-id="${s.id}"]`);
      const r = g.getBoundingClientRect();
      return { x: Math.round(r.left), y: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom) };
    }, n0);
    console.log(tool, JSON.stringify(drawn[tool]));
  }
  const a = drawn.rect, c = drawn.circle;
  check("both shapes were made", a && c, drawn);
  const near = (p, q) => Math.abs(p - q) <= 8; // stroke width slack
  check("circle's box is the dragged box, like the rectangle's", a && c && near(a.x, c.x) && near(a.y, c.y) && near(a.r, c.r) && near(a.b, c.b), drawn);
  check("circle does not reach above or left of the press", c && c.y >= 400 - 8 && c.x >= 500 - 8, c);
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
