// INBOX 1609: every visible .search-field: icon centre vs field centre, input text box centre.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.reload(); await page.waitForTimeout(2500);
  if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(2500); }
  const sections = (process.env.SECTIONS || 'logs').split(',');
  for (const s of sections) {
    await page.evaluate((s) => openSettingsModal(s), s); await page.waitForTimeout(1500);
    const rows = await page.evaluate(() => [...document.querySelectorAll('.search-field')].filter((f) => f.getClientRects().length && f.getBoundingClientRect().width > 0).map((f) => {
      const box = f.getBoundingClientRect(); const icon = f.querySelector('.search-field-icon'); const glyph = icon?.querySelector('::before') || icon; const ir = icon?.getBoundingClientRect(); const input = f.querySelector('input'); const inr = input?.getBoundingClientRect(); const cs = input && getComputedStyle(input);
      const g = icon && getComputedStyle(icon);
      return { id: input?.id, field: [Math.round(box.top), Math.round(box.height)], iconMid: ir && +(ir.top + ir.height / 2 - (box.top + box.height / 2)).toFixed(1), iconH: ir && ir.height, iconLH: g?.lineHeight, inputMid: inr && +(inr.top + inr.height / 2 - (box.top + box.height / 2)).toFixed(1), inputLH: cs?.lineHeight, inputFS: cs?.fontSize, inputPad: cs && cs.paddingTop + '/' + cs.paddingBottom, inputH: inr?.height };
    }));
    for (const r of rows) console.log(s, JSON.stringify(r));
  }
  await browser.close();
})();
