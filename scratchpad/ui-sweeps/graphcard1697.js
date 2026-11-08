// The graph's hover card under the graph's own dock (owner 2026-11-08: "the top of popup cards can be
// cut off by the top bar in the graph on hover"). A node is put just under the dock and hovered; the
// card's top is measured against the dock's bottom.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/graphcard1697.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.VW || 1440), height: 900 } });
  await page.evaluate(async () => {
    const have = (await apiJson('/entries?limit=20')).length;
    for (let i = have; i < 10; i++) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Graph sweep ${i}\n\nLectures on cloud computing and study notes, part ${i}. #cloud`, category: 'Sweep' }) });
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(5000);
  const out = [];
  for (const below of [4, 20, 60, 140]) {
    out.push(await page.evaluate((below) => {
      const s = gcTab;
      const c = s.canvas.getBoundingClientRect();
      const dock = document.querySelector('.dock[data-dock-name="graph"]').getBoundingClientRect();
      const node = [...s.byId.values()].find((n) => !n.isGroup);
      // Put the node `below` px under the dock's bottom, mid-width.
      const t = s.transform;
      t.x = c.width / 2 - node.x * t.k;
      t.y = (dock.bottom - c.top + below) - node.y * t.k;
      s.hoveredId = node.id;
      gcHoverCardFrame(s);
      const card = s._hoverCard;
      card._at = null;
      gcHoverCardFrame(s);
      const r = card.getBoundingClientRect();
      return { below, cardTop: Math.round(r.top), dockBottom: Math.round(dock.bottom), canvasTop: Math.round(c.top), hiddenBy: Math.max(0, Math.round(dock.bottom - r.top)) };
    }, below));
  }
  console.log(JSON.stringify(out));
  await browser.close();
})();
