// One ctrl+wheel notch of a mouse zooms the board by about a notch, not by 5x
// (maprender.md: d3-zoom multiplies a wheel delta by ten while ctrl is held,
// for trackpad pinch, and a mouse notch is 100 to 120 pixels of it). Opens a
// board, sends real wheel events with ctrl held through the browser and reads
// the zoom transform's scale before and after, for a mouse notch (deltaY 120)
// and for a pinch step (deltaY 4). Pinch must still move the scale, and by
// far less than a notch.
//
//   BASE=http://127.0.0.1:8799 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node ctrlwheelzoom.js
const { boot } = require("./lib.js");

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  let failed = 0;
  const ok = (name, pass, detail) => { if (!pass) failed++; console.log(`${pass ? "PASS" : "FAIL"}  ${name}  ${detail || ""}`); };
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", "Wheel zoom");
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
  const box = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  await page.mouse.move(box.x, box.y);
  const scale = () => page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
  const wheel = async (deltaY) => {
    await page.keyboard.down("Control");
    await page.mouse.wheel(0, deltaY);
    await page.keyboard.up("Control");
    await page.waitForTimeout(250);
  };
  const k0 = await scale();
  await wheel(-120);
  const k1 = await scale();
  ok("one mouse notch in zooms by well under 2x", k1 > k0 * 1.15 && k1 < k0 * 2, `${k0.toFixed(3)} -> ${k1.toFixed(3)} (x${(k1 / k0).toFixed(2)})`);
  await wheel(120);
  const k2 = await scale();
  ok("and one notch back returns to where it started", Math.abs(k2 - k0) < 0.02, `${k2.toFixed(3)} against ${k0.toFixed(3)}`);
  await wheel(-4);
  const k3 = await scale();
  ok("a pinch step still zooms, by far less than a notch", k3 > k2 * 1.01 && k3 < k2 * 1.15, `${k2.toFixed(3)} -> ${k3.toFixed(3)} (x${(k3 / k2).toFixed(3)})`);
  console.log(failed ? `${failed} failed` : "all passed");
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
