// Does the 1,000-note month's calendar hold all 1,000, and what does the dock's count say?
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { localStorage.setItem('timeline-view', 'calendar'); localStorage.setItem('timeline-scale', 'day'); localStorage.setItem('timeline-cal-span', 'month'); });
  await page.evaluate(() => switchTab('timeline'));
  const samples = [];
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(700);
    samples.push(await page.evaluate(() => ({
      chip: document.getElementById('timeline-count')?.textContent,
      cells: [...document.querySelectorAll('.timeline-cal-monthcell')].reduce((n, c) => n + (+c.dataset.count || 0), 0),
    })));
  }
  const api = await page.evaluate(async () => {
    const r = await apiJson('/timeline?kind=note&start=2026-10-01T00:00:00&end=2026-10-31T23:59:59&tz=0&limit=1000');
    return { rows: r.rows.length, more: r.has_more };
  });
  console.log(JSON.stringify({ samples, api }));
  await browser.close();
})();
