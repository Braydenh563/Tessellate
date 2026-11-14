// INBOX 641/642 audit (mc1): how the map's levels, icons and the app's
// emoji/icon pickers measure. Numbers only.
//   BASE=http://127.0.0.1:8798 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mc1-mapcore-audit.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
    const content = ["- Centre", "  - Branch one", "    - Leaf a", "    - Leaf b", "  - Branch two", "    - Leaf c"];
    const board = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: "Audit" }) });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1800));
  });
  const out = await page.evaluate(() => {
    const index = wbMapIndex();
    const pick = (re) => index.nodes.find((n) => re.test(n.data?.content || ""));
    const m = (n) => {
      const el = document.querySelector(`.wb-object[data-id="${n.id}"]`);
      const cs = getComputedStyle(el);
      const t = getComputedStyle(el.querySelector(".wb-map-text"));
      const r = el.getBoundingClientRect();
      return { font: t.fontSize, weight: t.fontWeight, radius: cs.borderRadius, bg: cs.backgroundColor, h: Math.round(r.height), w: Math.round(r.width), borderL: cs.borderLeftWidth, level: el.dataset.level || null };
    };
    const root = index.roots[0];
    return {
      roots: index.roots.length,
      centre: m(root), branch: m(pick(/Branch one/)), leaf: m(pick(/Leaf a/)),
      iconChoices: document.getElementById("wb-map-strip-icon")?.options.length,
      libraryOnMap: typeof wbLibEntries === "function" ? wbLibEntries().filter(wbLibFits).length : null,
      docEmoji: typeof docEmojiList === "function" ? docEmojiList().length : null,
      phosphor: [...document.styleSheets].filter((s) => (s.href || "").includes("phosphor")).map((s) => [...s.cssRules].filter((r) => /^\.ph\.ph-[a-z0-9-]+::?before$/.test(r.selectorText || "")).length)[0],
      picker: typeof openIconPicker === "function",
      rootNames: index.roots.map((r) => [r.kind, r.data?.content, (index.childrenOf.get(r.id) || []).length]),
    };
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
