// K10: the selection bar with Pin and Unpin fits at 1440, 720 and 390 (scrollWidth vs clientWidth, wrapped rows).
const { boot } = require("./lib.js");
(async () => {
  for (const [W, H] of [[1440, 900], [720, 900], [390, 844]]) {
    const { browser, page } = await boot({ viewport: { width: W, height: H } });
    await page.evaluate(() => { try { prefs.set("graph-layout", "force"); } catch (e) {} });
    await page.evaluate(() => switchTab("graph"));
    await page.waitForTimeout(5000);
    const m = await page.evaluate(() => {
      for (const n of gcTab.nodes.slice(0, 3)) gcTab.selected.add(n.id);
      gcSelectionChanged(gcTab);
      const d = document.getElementById("graph-selection-dock");
      const r = d.getBoundingClientRect();
      const tops = new Set([...d.children].map((c) => Math.round(c.getBoundingClientRect().top)));
      return { W: innerWidth, dockLeft: Math.round(r.left), dockRight: Math.round(r.right), scrollW: d.scrollWidth, clientW: d.clientWidth, rows: tops.size, pinH: Math.round(document.getElementById("graph-selection-pin").getBoundingClientRect().height) };
    });
    console.log(JSON.stringify(m));
    await browser.close();
  }
})();
