// INBOX 1300 C22: Settings, Keyboard shortcuts. The key chip shows it is
// the way to change the shortcut: a pencil after the keys, muted at rest,
// accent under the pointer, an x while capturing. Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => openSettingsModal('shortcuts')); await page.waitForTimeout(1200);
  const sel = '#shortcut-list-settings li:first-child .shortcut-key';
  const rd = () => page.$eval(sel, (b) => { const i = b.querySelector('.shortcut-edit'); const r = i.getBoundingClientRect(); const k = b.querySelector('kbd').getBoundingClientRect(); return { cls: i.className, color: getComputedStyle(i).color, w: Math.round(r.width), gapAfterKeys: Math.round(r.left - k.right), btnW: Math.round(b.getBoundingClientRect().width), btnH: Math.round(b.getBoundingClientRect().height) }; });
  console.log('rows', await page.$$eval('#shortcut-list-settings li', (l) => l.length), 'pencils', await page.$$eval('#shortcut-list-settings .shortcut-edit.ph-pencil-simple', (l) => l.length));
  console.log('rest', JSON.stringify(await rd()));
  await page.hover(sel); await page.waitForTimeout(300);
  console.log('hover', JSON.stringify(await rd()));
  await page.click(sel); await page.waitForTimeout(300);
  console.log('capturing', JSON.stringify(await rd()));
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  console.log('after esc', JSON.stringify(await rd()));
  const narrow = await page.evaluate(() => [...document.querySelectorAll('#shortcut-list-settings li')].filter((li) => li.scrollWidth > li.clientWidth + 1).length);
  console.log('rows overflowing', narrow);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
