// The owner, 2026-11-10: tidy the graph popup's header (title colon, the bare "95%", the indented
// category chip, "03/08/2026"). Opens the popup, fills the header as a filed note would, and prints
// the left edges of the glyph, chip and meta line, the confidence text, the title and the meta text.
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const id = await page.evaluate(async () => (await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "Ice Breakers:\nTwo truths and a lie.", tags: ["conversation"] }) })).id);
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(3000);
  await page.evaluate(async (id) => { await openGraphPopup({ stopPropagation() {}, clientX: 500, clientY: 300 }, { id, preview: "Ice Breakers:" }); }, id);
  await page.waitForTimeout(800);
  const out = await page.evaluate(() => {
    renderGraphPopupHeader({ content: "Ice Breakers:\nx", category: "Communication & Connection", ai_confidence: 95 }, {});
    const L = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().left) : null; };
    const T = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; };
    return { title: document.getElementById("graph-popup-title").textContent, conf: document.getElementById("graph-popup-confidence").textContent,
      glyphL: L("#graph-popup .pop-glyph"), chipL: L("#graph-popup-category"), metaL: L("#graph-popup-info"), confL: L("#graph-popup-confidence"),
      chipT: T("#graph-popup-category"), confT: T("#graph-popup-confidence"), meta: document.getElementById("graph-popup-info").textContent,
      headH: Math.round(document.querySelector("#graph-popup .graph-popup-head").getBoundingClientRect().height) };
  });
  console.log(JSON.stringify(out));
  await page.locator("#graph-popup").screenshot({ path: process.env.OUT || "/tmp/gph.png" });
  await browser.close();
})();
