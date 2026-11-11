// INBOX 1771: the builder's connector rows. Menu beside its row, a click selects both ends, first row clear of the sticky bar, labels not squeezed.
//   BASE=http://127.0.0.1:8861 THEME=dark node scratchpad/ui-sweeps/diagram-links.js
process.env.BASE ||= "http://127.0.0.1:8861";
const { boot } = require("./lib.js");
const SRC = "flowchart TD\n  A[Bug reported] --> B{Can you reproduce it?}\n  B -->|No| C[Ask for details]\n  B -->|Yes| D[Fix it]\n  C -.-> B\n";
const ALL = [[1440, 900, false], [1100, 800, false], [820, 900, false], [390, 844, true]];
const SIZES = process.env.W ? ALL.filter((s) => String(s[0]) === process.env.W) : ALL;
(async () => {
  const out = [];
  for (const [w, h, touch] of SIZES) {
    const { browser, page } = await boot({ viewport: { width: w, height: h }, ...(touch ? { isMobile: true, hasTouch: true } : {}) });
    await page.evaluate(async (src) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Links", content: src, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
    }, SRC);
    await page.waitForTimeout(1500);
    if (await page.locator(".dgm-body.dgm-fold-left").count()) await page.locator('.dgm-body > button[data-side="left"]').first().click();
    if (w <= 600) await page.locator('button[title="Blocks list"]').first().click();
    await page.waitForSelector(".dgm-join", { state: "visible", timeout: 15000 });
    await page.waitForTimeout(600);
    const first = await page.evaluate(() => {
      const c = document.querySelector(".dgm-block > .dgm-card").getBoundingClientRect();
      const bar = [...document.querySelectorAll("body *")].filter((e) => getComputedStyle(e).position === "sticky" && e.getBoundingClientRect().height > 0 && !e.closest(".hidden")).map((e) => ({ cls: String(e.className).slice(0, 40), t: Math.round(e.getBoundingClientRect().top), b: Math.round(e.getBoundingClientRect().bottom) }));
      const labels = [...document.querySelectorAll(".dgm-card .dgm-label")].map((l) => ({ t: l.textContent, h: Math.round(l.getBoundingClientRect().height), sw: l.scrollWidth, cw: l.clientWidth }));
      return { cardTop: Math.round(c.top), bar, labels };
    });
    await page.evaluate(() => document.querySelectorAll(".dgm-join")[1].scrollIntoView({ block: "center" }));
    const go = page.locator(".dgm-join:visible").nth(1);
    await go.click();
    await page.waitForTimeout(300);
    const went = await page.evaluate(() => ({ selected: document.querySelector('.dgm-block[aria-selected="true"]')?.getAttribute("aria-label"), arrow: document.querySelector(".dgm-edge-on")?.getAttribute("d")?.length || 0, focusOnRow: document.activeElement?.classList.contains("dgm-join") }));
    const chip = page.locator(".dgm-join-dots:visible").nth(1);
    const rb = await page.locator(".dgm-joinline:visible").nth(1).boundingBox();
    const row = rb;
    await chip.click();
    await page.waitForTimeout(400);
    const menu = await page.evaluate(() => { const m = document.querySelector(".action-menu:not(.hidden):not(.submenu)"); if (!m) return null; const r = m.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), r: Math.round(r.right), b: Math.round(r.bottom) }; });
    const overlap = menu && !(menu.r <= row.x || menu.x >= row.x + row.width || menu.b <= row.y || menu.y >= row.y + row.height);
    out.push({ w, went, row: [row.x, row.y, row.width, row.height].map(Math.round), menu, overlap, first });
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
