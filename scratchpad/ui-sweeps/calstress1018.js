// TIMELINE_PLAN section 9 "Not verified (Brief 55)": a 1,000-note month, and
// the week grid at 1024 under a coarse pointer.
//   seed: seed-timeline-bulk.py <db> 1000 2026-10   then
//   BASE=http://127.0.0.1:8789 node calstress1018.js
// Prints per case: open time (switchTab to month cells painted), cells that
// overflow (scrollHeight vs clientHeight), dots and "+n" counts, horizontal
// scroll, the grid drawn, hour-row cells under 44 px high on a coarse pointer.
const { boot } = require('./lib.js');
const cases = [
  { name: 'month1440', span: 'month', opts: { viewport: { width: 1440, height: 900 } } },
  { name: 'week1024coarse', span: 'week', opts: { viewport: { width: 1024, height: 768 }, hasTouch: true, isMobile: true } },
  { name: 'month1024', span: 'month', opts: { viewport: { width: 1024, height: 768 } } },
];
(async () => {
  const out = {};
  for (const c of cases) {
    const { browser, page } = await boot(c.opts);
    await page.evaluate((span) => { localStorage.setItem('timeline-view', 'calendar'); localStorage.setItem('timeline-scale', 'day'); localStorage.setItem('timeline-cal-span', span); }, c.span);
    const t0 = Date.now();
    await page.evaluate(() => switchTab('timeline'));
    await page.waitForFunction(() => document.querySelectorAll('#timeline-calendar .timeline-cal-monthcell, #timeline-calendar .timeline-cal-hourcell').length > 20, null, { timeout: 30000 }).catch(() => {});
    const openMs = Date.now() - t0;
    await page.waitForTimeout(1200);
    out[c.name] = { openMs, ...(await page.evaluate(() => {
      const box = document.getElementById('timeline-calendar');
      const cells = [...box.querySelectorAll('.timeline-cal-monthcell, .timeline-cal-alldaycell, .timeline-cal-hourcell')];
      const over = cells.filter((x) => x.scrollHeight > x.clientHeight + 1 || x.scrollWidth > x.clientWidth + 1);
      const coarse = matchMedia('(pointer: coarse)').matches;
      const hours = [...box.querySelectorAll('.timeline-cal-hourcell')];
      const hh = hours.map((x) => x.getBoundingClientRect().height);
      const doc = document.documentElement;
      const month = box.querySelector('.timeline-cal-month');
      const items = box.querySelectorAll('.timeline-cal-item').length;
      return {
        grid: month ? 'month' : box.querySelector('.timeline-cal-weekwrap') ? 'week' : 'other',
        cells: cells.length, overCount: over.length, over: over.slice(0, 3).map((x) => `${x.dataset.calDay}${x.dataset.calHour ? '@' + x.dataset.calHour : ''} ${x.scrollHeight}/${x.clientHeight}`),
        dots: box.querySelectorAll('.timeline-cal-dot').length, more: box.querySelectorAll('.timeline-cal-more:not([hidden])').length, items,
        hscroll: doc.scrollWidth - doc.clientWidth, coarse, hourCells: hours.length, hourMin: hh.length ? Math.round(Math.min(...hh)) : null,
        title: box.querySelector('.timeline-cal-title')?.textContent || '', count: document.getElementById('timeline-count')?.textContent || '',
      };
    })) };
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
