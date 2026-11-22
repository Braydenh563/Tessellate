// Timeline "Add to <date>" sheet: the header's buttons sit at its right edge (the owner, 2026-11-22).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => switchTab('timeline'));
  await page.waitForTimeout(1500);
  await page.evaluate(() => lazyScript('/js/timeline-calendar.js'));
  await page.evaluate(() => { const d = new Date(); const p = (n) => String(n).padStart(2, '0'); timelineCalAdd(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`); });
  await page.waitForSelector('[data-sheet="calendar-add"] .sheet-head', { timeout: 15000 });
  const m = await page.evaluate(() => {
    const head = document.querySelector('[data-sheet="calendar-add"] .sheet-head');
    const r = (e) => e.getBoundingClientRect();
    const cs = getComputedStyle(head);
    return {
      head: [Math.round(r(head).left), Math.round(r(head).right)], display: cs.display, padR: cs.paddingRight,
      kids: [...head.children].map((c) => ({ cls: c.className.slice(0, 50), left: Math.round(r(c).left), right: Math.round(r(c).right), ml: getComputedStyle(c).marginLeft, flex: getComputedStyle(c).flex })),
    };
  });
  console.log(JSON.stringify(m, null, 1));
  await browser.close();
})();
