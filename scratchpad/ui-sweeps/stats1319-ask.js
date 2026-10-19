// INBOX 1319 step 3: the Ask box answers sample questions; compare with sqlite counts printed by the caller.
//   BASE=http://127.0.0.1:8798 [THEME=dark] node stats1319-ask.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 }, theme: process.env.THEME });
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  await page.evaluate(() => ensureModule('statistics').then(() => openStatistics()));
  await page.waitForTimeout(1500);
  const out = { chips: await page.locator('.stats-ask-chip').allTextContents() };
  const ask = async (q) => {
    await page.fill('#stats-ask-input', q); await page.keyboard.press('Enter'); await page.waitForTimeout(700);
    return page.locator('.stats-ask-text').textContent();
  };
  out.answers = {};
  for (const q of ['how many notes did I write in July', 'how many notes this month', 'what do I use most', 'am I writing more than last month', 'summarise my month', 'how many notes do I have']) out.answers[q] = await ask(q);
  await page.locator('.stats-ask-chip').nth(0).click(); await page.waitForTimeout(700);
  out.chip = await page.locator('.stats-ask-text').textContent();
  const b = await page.evaluate(() => { const a = document.querySelector('.stats-ask'); const r = a.getBoundingClientRect(); const body = document.querySelector('.stats-body'); return [Math.round(r.width), body.scrollWidth, body.clientWidth]; });
  out.fit = b;
  out.colors = await page.evaluate(() => { const e = document.querySelector('.stats-ask-answer'); const c = getComputedStyle(e); return [c.backgroundColor, getComputedStyle(document.querySelector('.stats-ask-text')).color]; });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
