// Every .modal-overlay: shown by removing `hidden`, then a press on its backdrop corner; closed = hidden again or not displayed.
const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  const ids = await page.evaluate(() => [...document.querySelectorAll('.modal-overlay[id]')].map((o) => o.id));
  for (const id of ids) {
    await page.evaluate((id) => { const o = document.getElementById(id); o.classList.remove('hidden'); o.hidden = false; }, id);
    await page.waitForTimeout(150);
    const at = await page.evaluate((id) => { const o = document.getElementById(id); const b = o.getBoundingClientRect(); const el = document.elementFromPoint(b.left + 4, b.top + b.height / 2); return { x: b.left + 4, y: b.top + b.height / 2, hit: el === o, vis: getComputedStyle(o).display, close: !!o.querySelector('[data-close], .modal-close, [aria-label^="Close"]') }; }, id);
    await page.mouse.click(at.x, at.y); await page.waitForTimeout(200);
    const gone = await page.evaluate((id) => { const o = document.getElementById(id); return o.classList.contains('hidden') || o.hidden || getComputedStyle(o).display === 'none'; }, id);
    console.log(`${id}: backdrop hit ${at.hit} display ${at.vis} close btn ${at.close} -> ${gone ? 'closes' : 'STAYS'}`);
    await page.evaluate((id) => { const o = document.getElementById(id); o.classList.add('hidden'); }, id);
  }
  await browser.close();
})();
