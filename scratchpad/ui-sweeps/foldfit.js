// L-world-class-95: per Notes card at 1093x614@1.25, its height, and whether its link row and details line fit one row.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1093, height: 614 }, deviceScaleFactor: 1.25 });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(2000);
  console.log(await page.evaluate(() => [...document.querySelectorAll("#entry-list > li")].slice(0, 10).map((li) => {
    const mc = (el) => { if (!el) return 0; const k = el.cloneNode(true); k.style.cssText = "position:absolute;width:max-content;visibility:hidden"; li.appendChild(k); const w = k.getBoundingClientRect().width; k.remove(); return Math.round(w); };
    const links = li.querySelector(":scope > .entry-links"), meta = li.querySelector(":scope > .entry-meta");
    const inner = li.clientWidth - parseFloat(getComputedStyle(li).paddingLeft) - parseFloat(getComputedStyle(li).paddingRight);
    return `h${Math.round(li.getBoundingClientRect().height)} links${mc(links)} pills${links ? links.querySelectorAll(".link-connection").length : 0} meta${mc(meta)} inner${Math.round(inner)} fits=${links ? mc(links) + mc(meta) + 16 <= inner : "-"}`;
  }).join("\n")));
  await browser.close();
})();
