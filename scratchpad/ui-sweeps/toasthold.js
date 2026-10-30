// Audit 1028 S19: a toast stays while pointed at, and leaves after its life
// once the pointer goes.  BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/toasthold.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const count = () => page.evaluate(() => [...document.querySelectorAll(".toast")].filter((t) => !t.classList.contains("is-leaving") && /hold check/.test(t.textContent)).length);
  await page.evaluate(() => toast("hold check one", "info"));
  await page.waitForTimeout(200);
  const box = await page.evaluate(() => { const r = [...document.querySelectorAll(".toast")].find((t) => /hold check/.test(t.textContent)).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await page.mouse.move(box[0], box[1]);
  await page.waitForTimeout(7500);
  console.log(`hovered 7.5 s: ${await count()} on screen (want 1)`);
  await page.mouse.move(5, 5);
  await page.waitForTimeout(6500);
  console.log(`left 6.5 s: ${await count()} on screen (want 0)`);
  await page.evaluate(() => toast("hold check two", "info"));
  await page.waitForTimeout(6500);
  console.log(`untouched 6.5 s: ${await count()} on screen (want 0)`);
  await browser.close();
})();
