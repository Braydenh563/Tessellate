// Backup rows, measured (INBOX 805): latest mark, date in words, origin, size, checked.
//   BASE=http://127.0.0.1:8798 node scratchpad/ui-sweeps/backuprows.js
const { boot } = require('./lib.js');
(async () => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { browser, page } = await boot({ viewport: vp });
    await page.evaluate(async () => { for (let i = 0; i < 3; i++) { await apiJson('/backups', { method: 'POST' }); await new Promise((r) => setTimeout(r, 1100)); } });
    await page.evaluate(() => openSettingsModal('data'));
    await page.waitForTimeout(1500);
    const rows = await page.evaluate(() => [...document.querySelectorAll('#backup-list > li')].map((li) => {
      const r = li.getBoundingClientRect();
      return { text: li.innerText.replace(/\n/g, ' | '), w: Math.round(r.width), h: Math.round(r.height), sw: li.scrollWidth, cw: li.clientWidth,
        badges: [...li.querySelectorAll('.item-label')].map((b) => b.textContent) };
    }));
    console.log(vp.width, JSON.stringify(rows, null, 1));
    await browser.close();
  }
})();
