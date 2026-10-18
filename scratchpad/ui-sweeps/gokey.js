// C23: "t" (Tessellate) arms the quick-nav chord, "m" still does; Timeline is t then i;
// t t closes the guide; on a board bare T stays the text tool.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({});
  await page.waitForTimeout(1500);
  const tab = () => page.evaluate(() => document.querySelector('[role="tab"][data-tab].active')?.dataset.tab);
  const guide = () => page.evaluate(() => { const g = document.querySelector('.chord-guide-panel'); return !!(g && g.offsetParent !== null); });
  const out = {};
  await page.locator('body').click({ position: { x: 5, y: 5 } }).catch(() => {});
  await page.keyboard.press('t'); await page.waitForTimeout(300); out.guideAfterT = await guide();
  await page.keyboard.press('t'); await page.waitForTimeout(300); out.guideAfterTT = await guide();
  await page.keyboard.press('t'); await page.keyboard.press('i'); await page.waitForTimeout(800); out.tIi = await tab();
  await page.keyboard.press('m'); await page.keyboard.press('d'); await page.waitForTimeout(800); out.mD = await tab();
  await page.keyboard.press('t'); await page.keyboard.press('n'); await page.waitForTimeout(800); out.tN = await tab();
  console.log(JSON.stringify(out));
  const ok = out.guideAfterT && !out.guideAfterTT && out.tIi === 'timeline' && out.mD === 'dashboard' && out.tN === 'notes';
  console.log(ok ? 'PASS' : 'FAIL'); await browser.close(); process.exit(ok ? 0 : 1);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
