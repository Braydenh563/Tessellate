// INBOX 1648: a docked panel stays between the top bar and the status bar. Opens Library's Create picker,
// docks it left, right and max through panelDock + panelFit, and measures its box against both bars.
const { boot } = require('./lib.js');
(async () => {
  for (const [w, h] of [[1440, 900], [1000, 700]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    await page.evaluate(() => switchTab('library')); await page.waitForTimeout(1200);
    await page.waitForFunction(() => typeof openLibraryCreatePicker === 'function', null, { timeout: 15000 }); await page.click('#library-new-doc'); await page.waitForTimeout(1000);
    for (const zone of ['left', 'right', 'max']) {
      const r = await page.evaluate((z) => {
        const card = document.querySelector('.library-create-picker');
        if (typeof panelLoad === 'function') panelLoad?.();
        const st = PANEL_STATE.get(card);
        if (!st) return 'not movable';
        panelDock(card, st, z); panelFit(card, st);
        const b = card.getBoundingClientRect();
        const top = document.getElementById('top-bar')?.getBoundingClientRect();
        const foot = document.getElementById('status-bar')?.getBoundingClientRect();
        return { zone: z, top: Math.round(b.top), bottom: Math.round(b.bottom), barBottom: top && Math.round(top.bottom), footTop: foot && Math.round(foot.top), clear: (!top || b.top >= top.bottom - 0.5) && (!foot || b.bottom <= foot.top + 0.5) };
      }, zone);
      console.log(w, JSON.stringify(r));
    }
    await browser.close();
  }
})();
