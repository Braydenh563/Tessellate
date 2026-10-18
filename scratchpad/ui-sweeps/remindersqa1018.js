// TIMELINE_PLAN 11 row 7: the reminders quick-add row is present at 390 and
// its chips show within 150 ms of the last key, and what is saved equals them.
//   BASE=... node remindersqa1018.js
const { boot } = require('./lib.js');
(async () => {
  const out = [];
  for (const phone of [false, true]) {
    const opts = phone ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1440, height: 900 } };
    const { browser, page } = await boot(opts);
    await page.evaluate(() => window.switchTab('reminders'));
    await page.waitForTimeout(1500);
    if (phone) { await page.click('#reminders-new'); await page.waitForTimeout(700); }
    const r = await page.evaluate(async () => {
      const input = document.getElementById('reminder-magic');
      if (!input) return { error: 'no #reminder-magic' };
      const box = input.getBoundingClientRect();
      const vis = !!input.offsetParent && box.width > 0;
      input.focus();
      input.value = 'dentist friday at 9am';
      const t0 = performance.now();
      input.dispatchEvent(new Event('input', { bubbles: true }));
      let chips = 0;
      const until = performance.now() + 2000;
      while (performance.now() < until) {
        await new Promise((res) => requestAnimationFrame(res));
        chips = document.querySelectorAll('.qa-chip').length;
        if (chips) break;
      }
      const ms = Math.round(performance.now() - t0);
      const texts = [...document.querySelectorAll('.qa-chip')].map((c) => c.textContent.trim());
      const inView = box.right <= innerWidth + 0.5 && box.left >= -0.5;
      input.value = '';
      return { vis, inView, w: Math.round(box.width), h: Math.round(box.height), chips, ms, texts };
    });
    out.push({ phone, ...r });
    await browser.close();
  }
  console.log(JSON.stringify(out));
})();
