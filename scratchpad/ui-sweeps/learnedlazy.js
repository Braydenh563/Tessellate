// The Learned section after it moved into settings-controls.js (lazy,
// 2026-11-02): opening Settings at "What it learned" draws the switches and
// the list, and nothing throws.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)));
  await page.waitForTimeout(3000);
  const before = await page.evaluate(() => typeof renderLearned);
  await page.evaluate(async () => { await openSettingsModal(); showSettingsSection("learned"); });
  await page.waitForTimeout(2500);
  const r = await page.evaluate(() => ({
    fn: typeof renderLearned,
    switches: document.querySelectorAll("#learned-switches input, #learned-switches [role=switch], #learned-switches button").length,
    html: (document.getElementById("learned-switches") || {}).childElementCount,
  }));
  console.log(before === "undefined" ? "ok  not in boot" : "FAIL in boot: " + before);
  console.log(r.fn === "function" && r.html > 0 ? "ok  learned drawn " + JSON.stringify(r) : "FAIL " + JSON.stringify(r));
  console.log(errors.length ? "FAIL errors " + JSON.stringify(errors) : "ok  no errors");
  await browser.close();
})();
