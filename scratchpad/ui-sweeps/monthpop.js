// Timeline month picker: the title, 7 weekday names and the month's days render; console errors listed.
const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  const errs = []; page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await page.evaluate(() => typeof showView === 'function' ? showView('timeline') : document.querySelector('[data-view="timeline"], #tab-btn-timeline')?.click());
  await page.waitForTimeout(1500);
  await page.click('#timeline-month-btn');
  await page.waitForTimeout(600);
  const r = await page.evaluate(() => { const p = document.getElementById('timeline-month-pop'); const b = p.getBoundingClientRect();
    return { hidden: p.classList.contains('hidden'), title: document.getElementById('timeline-month-title').textContent, days: p.querySelectorAll('.timeline-monthday').length, dow: p.querySelectorAll('.timeline-monthpop-dow').length, h: Math.round(b.height), w: Math.round(b.width) }; });
  console.log(JSON.stringify(r), errs.slice(0, 5));
  await browser.close();
})();
