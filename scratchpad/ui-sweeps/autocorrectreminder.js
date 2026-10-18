// INBOX 904 B04: autocorrect on the reminder boxes (#reminder-text, #reminder-magic).
// Types a slip, then reads the box, the underline, and the menu after a hover.
//   BASE=http://127.0.0.1:8784 node autocorrectreminder.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(3500);
  await page.evaluate(() => switchTab('reminders'));
  await page.waitForTimeout(1200);
  for (const sel of ['#reminder-text', '#reminder-magic']) {
    const vis = await page.evaluate((s) => { const e = document.querySelector(s); return e.offsetParent !== null; }, sel);
    console.log(sel, 'visible', vis);
    await page.click(sel, { force: true });
    await page.waitForTimeout(600);
    await page.keyboard.type('call teh dentist ', { delay: 30 });
    await page.waitForTimeout(400);
    const out = await page.evaluate((s) => {
      const m = document.querySelector('.autocorrect-mark');
      const r = m && m.getBoundingClientRect();
      const box = document.querySelector(s).getBoundingClientRect();
      return { value: document.querySelector(s).value, mark: m ? { w: Math.round(r.width), h: Math.round(r.height), inBox: r.left >= box.left && r.right <= box.right && r.top >= box.top - 2 && r.bottom <= box.bottom + 2 } : null };
    }, sel);
    let menu = null;
    if (out.mark) {
      const r = await page.evaluate(() => { const b = document.querySelector('.autocorrect-mark').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
      await page.mouse.move(r[0], r[1]);
      await page.waitForTimeout(1500);
      menu = await page.evaluate(() => [...document.querySelectorAll('.action-menu')].map((x) => x.innerText.replace(/\n/g, ' | ')).find((t) => /Put back/.test(t)) || null);
      await page.keyboard.press('Escape');
    }
    console.log(sel, JSON.stringify({ ...out, menu }));
    await page.fill(sel, '');
  }
  console.log('pageerrors:', errors.length);
  await browser.close();
})();
