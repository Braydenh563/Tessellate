// dog1-1025 line 21: the first-run update question must not trap the page.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForFunction(() => document.querySelector(".confirm-overlay"), null, { timeout: 25000 }).catch(() => {});
  await page.waitForTimeout(500);
  const up = () => page.evaluate(() => { const o = document.querySelector('.confirm-overlay'); return o ? o.textContent.slice(0, 40) : null; });
  console.log('open', await up());
  await page.mouse.click(20, 400);
  await page.waitForTimeout(500);
  console.log('after backdrop click', await up());
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  console.log('after esc', await up());
  console.log('choice', await page.evaluate(() => fetch('/preferences').then(r => r.json()).then(j => j.update_choice_made).catch(e => String(e))));
  await browser.close();
})();
