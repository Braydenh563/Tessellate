// The first Notes card's box tree (two levels) with margins, at 1093x614@1.25.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1093, height: 614 }, deviceScaleFactor: 1.25 });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(2000);
  console.log(await page.evaluate(() => {
    const li = document.querySelector("#entry-list > li");
    const line = (e, d) => { const b = e.getBoundingClientRect(), s = getComputedStyle(e); return `${"  ".repeat(d)}${e.tagName.toLowerCase()}.${[...e.classList].join(".")} ${Math.round(b.top)}-${Math.round(b.bottom)} m=${s.margin} p=${s.padding} d=${s.display} lh=${s.lineHeight}`; };
    const out = [line(li, 0)];
    for (const c of li.children) { if (!c.getClientRects().length) continue; out.push(line(c, 1)); for (const g of c.children) if (g.getClientRects().length) out.push(line(g, 2)); }
    return out.join("\n");
  }));
  await browser.close();
})();
