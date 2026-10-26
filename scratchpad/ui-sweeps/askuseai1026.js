// K6: Ask's Use AI control renders from the provider status at load. Samples its state over the first seconds
// (no model runs on this data dir, so it must never read as on), then its box, at 1440 / 720 / 390.
const { boot } = require("./lib.js");
(async () => {
  for (const [W, H] of [[1440, 900], [720, 900], [390, 844]]) {
    const { browser, page } = await boot({ viewport: { width: W, height: H } });
    const read = () => page.evaluate(() => {
      const b = document.getElementById("ask-use-ai");
      if (!b) return null;
      const r = b.getBoundingClientRect();
      const on = b.matches("input") ? b.checked : b.classList.contains("active");
      return { tag: b.tagName, on, pressed: b.getAttribute("aria-pressed"), disabled: b.disabled || b.getAttribute("aria-disabled") === "true", title: (b.closest("label") || b).title.slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) };
    });
    await page.evaluate(() => switchTab('notes')).catch(() => {});
    await page.waitForTimeout(500);
    await page.evaluate(() => document.querySelector('#notes-subtabs [data-section="ask"]')?.click());
    const samples = [];
    for (const ms of [300, 1500, 2500, 4000]) {
      await page.waitForTimeout(ms === 300 ? 300 : 1000);
      samples.push(await read());
    }
    const overflow = await page.evaluate(() => { const h = document.querySelector("#ask .ask-header-actions"); return { scrollW: h.scrollWidth, clientW: h.clientWidth, docOverflow: document.documentElement.scrollWidth > innerWidth }; });
    console.log(W, JSON.stringify(samples), JSON.stringify(overflow));
    await browser.close();
  }
})();
