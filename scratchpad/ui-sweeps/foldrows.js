// Every visible box in the Notes tab's top 260px at 1093x614@1.25, and the first card's parts.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1093, height: 614 }, deviceScaleFactor: 1.25 });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(2000);
  const out = await page.evaluate(() => {
    const rows = [];
    const tab = document.getElementById("tab-notes");
    const walk = (el, depth) => {
      if (depth > 6) return;
      for (const c of el.children) {
        const b = c.getBoundingClientRect();
        if (!c.getClientRects().length || b.height < 2) continue;
        if (b.top < 260 && b.width > 300) rows.push(`${"  ".repeat(depth)}${c.tagName.toLowerCase()}#${c.id}.${[...c.classList].slice(0,3).join(".")} ${Math.round(b.top)}-${Math.round(b.bottom)} w${Math.round(b.width)}`);
        if (c.id !== "entry-list") walk(c, depth + 1);
      }
    };
    walk(tab, 0);
    const li = document.querySelector("#entry-list > li");
    const parts = li ? [...li.querySelectorAll("*")].filter((e) => e.children.length === 0 && e.getClientRects().length).slice(0, 14).map((e) => { const b = e.getBoundingClientRect(); return `${e.tagName.toLowerCase()}.${[...e.classList].slice(0,2).join(".")} ${Math.round(b.top)}-${Math.round(b.bottom)}`; }) : [];
    const cs = li && getComputedStyle(li);
    return { rows, parts, li: li && { pad: cs.padding, gap: getComputedStyle(li.parentElement).gap, top: Math.round(li.getBoundingClientRect().top), h: Math.round(li.getBoundingClientRect().height) }, density: document.documentElement.dataset.density };
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
