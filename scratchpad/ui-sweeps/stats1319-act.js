// INBOX 1319 step 1: do the Statistics charts answer hover, focus, arrows, click, resize?
//   BASE=http://127.0.0.1:8798 [THEME=dark] node stats1319-act.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 }, theme: process.env.THEME });
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  const open = async () => { await page.evaluate(() => ensureModule('statistics').then(() => openStatistics())); await page.waitForTimeout(1500); };
  await open();
  const out = {};
  const pts = page.locator('.stats-chart').first().locator('.ask-chart-pt');
  out.points = await pts.count();
  console.log('pre', out.points, await page.evaluate(() => document.querySelector('.confirm-card')?.textContent?.slice(0,200) || 'none'));
  const tip = page.locator('.stats-chart').first().locator('.ask-chart-tip');
  await pts.nth(8).hover();
  out.hoverTip = { visible: await tip.isVisible(), text: await tip.textContent() };
  await page.mouse.move(5, 5);
  out.afterLeave = await tip.isVisible();
  await pts.nth(0).focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  out.focusTip = { visible: await tip.isVisible(), text: await tip.textContent(), index: await page.evaluate(() => document.activeElement.dataset.i) };
  await page.keyboard.press('End');
  out.end = await page.evaluate(() => document.activeElement.dataset.i);
  const tipBox = await tip.boundingBox(); const card = await page.locator('.stats-card').boundingBox();
  out.tipInsideCard = tipBox.x >= card.x && tipBox.x + tipBox.width <= card.x + card.width;
  out.tipColors = await tip.evaluate((e) => { const c = getComputedStyle(e); return [c.color, c.backgroundColor]; });
  // resize: chart svg width vs card
  const w1 = await page.evaluate(() => { const s = document.querySelector('.stats-chart svg'); return [s.viewBox.baseVal.width, Math.round(s.getBoundingClientRect().width)]; });
  await page.setViewportSize({ width: 900, height: 900 }); await page.waitForTimeout(600);
  const w2 = await page.evaluate(() => { const s = document.querySelector('.stats-chart svg'); return [s.viewBox.baseVal.width, Math.round(s.getBoundingClientRect().width)]; });
  out.resize = { wide: w1, narrow: w2 };
  await page.setViewportSize({ width: 1440, height: 900 }); await page.waitForTimeout(600);
  out.confirm = await page.evaluate(() => document.querySelector('.confirm-card')?.textContent?.slice(0,200) || null);
  console.log(JSON.stringify(out));
  // click a month point -> timeline
  await page.locator('.stats-chart').first().locator('.ask-chart-pt').nth(8).click();
  await page.waitForTimeout(1200);
  out.afterMonthClick = await page.evaluate(() => ({ card: !!document.querySelector('.stats-card'), tab: prefs.get('activeTab', null), stripEnd: timelineStripEnd }));
  // feature bar click
  await open();
  const bars = page.locator('.stats-chart').nth(1).locator('.ask-chart-pt');
  out.bars = await bars.count(); console.log(JSON.stringify(out.afterMonthClick), out.bars, await page.locator('.stats-chart').count());
  out.firstBar = await bars.first().getAttribute('aria-label');
  await bars.first().focus(); await page.keyboard.press('Enter'); await page.waitForTimeout(1000);
  out.afterBarEnter = await page.evaluate(() => ({ card: !!document.querySelector('.stats-card'), tab: prefs.get('activeTab', null) }));
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
