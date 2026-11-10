const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => document.getElementById("space-create-dialog").showModal());
  await page.focus("#space-create-name"); await page.keyboard.press("Tab"); await page.keyboard.press("Shift+Tab");
  await page.waitForTimeout(300);
  const r = await page.evaluate(() => {
    const l = document.querySelector('label[for="space-create-name"]'), i = document.getElementById("space-create-name");
    const lb = l.getBoundingClientRect(), ib = i.getBoundingClientRect(), cs = getComputedStyle(i);
    return { labelBottom: lb.bottom, inputTop: ib.top, gap: ib.top - lb.bottom, outline: cs.outlineWidth + " " + cs.outlineOffset, shadow: cs.boxShadow, labelMargin: getComputedStyle(l).margin };
  });
  console.log(JSON.stringify(r));
  await page.screenshot({ path: process.env.OUT || "/tmp/spacedlg.png", clip: { x: 520, y: 150, width: 420, height: 300 } });
  await browser.close();
})();
