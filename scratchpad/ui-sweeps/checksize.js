// The owner, 2026-11-10: "this radio button is massive" (Timeline, Options, Dates beside the strip).
// Prints the box of every checkbox inside a dock menu on the Timeline, with the rule that sized it.
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => switchTab("timeline")); await page.waitForTimeout(1500);
  await page.evaluate(() => { for (const d of document.querySelectorAll("#tab-timeline details.dock-menu")) d.open = true; });
  await page.waitForTimeout(300);
  const out = await page.evaluate(() => [...document.querySelectorAll(".dock-menu-check > input[type=checkbox], .dock-menu-check input")].map((i) => {
    const b = i.getBoundingClientRect(), cs = getComputedStyle(i);
    return { id: i.id, w: Math.round(b.width), h: Math.round(b.height), visible: b.width > 0, appearance: cs.appearance, minH: cs.minHeight, minW: cs.minWidth };
  }));
  console.log(JSON.stringify(out));
  await browser.close();
})();
