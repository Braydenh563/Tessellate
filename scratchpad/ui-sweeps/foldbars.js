// The header's and the status bar's visible children at 1093x614@1.25: where free width is.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1093, height: 614 }, deviceScaleFactor: 1.25 });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(2000);
  console.log(await page.evaluate(() => {
    const kids = (el, d = 0) => [...el.children].filter((c) => c.getClientRects().length).map((c) => { const b = c.getBoundingClientRect(); return `${"  ".repeat(d)}${c.tagName.toLowerCase()}#${c.id}.${[...c.classList].slice(0, 2).join(".")} x${Math.round(b.left)}-${Math.round(b.right)} "${(c.innerText || "").replace(/\s+/g, " ").slice(0, 30)}"`; });
    const header = document.querySelector("header");
    const sb = document.getElementById("status-bar");
    return ["HEADER", ...kids(header), ...[...header.children].flatMap((c) => kids(c, 1)), "STATUS", ...kids(sb), ...[...sb.children].flatMap((c) => kids(c, 1))].join("\n");
  }));
  await browser.close();
})();
