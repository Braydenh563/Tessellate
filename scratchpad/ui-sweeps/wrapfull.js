// A table's full view still opens from the ⋯ (its Fit row moved to the head's
// wrap toggle): starts fitted, the toggle is pressed there, and leaving puts the
// bubble back to what the reader last chose.
//   BASE=http://127.0.0.1:8951 THEME=dark node wrapfull.js
const { boot } = require('./lib.js');
const MD = '| A | B | C |\n| --- | --- | --- |\n| ' + 'long words '.repeat(12) + ' | b | c |';
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForTimeout(2000);
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(500);
  await page.evaluate((md) => { const b = addBubble('assistant', ''); renderMarkdown(b.querySelector('.msg-body'), md); b.scrollIntoView(); }, MD);
  const state = () => page.evaluate(() => { const t = document.querySelector('.md-table-block'); return { view: t.dataset.tableView, pressed: t.querySelector('.wrap-toggle').getAttribute('aria-pressed'), full: t.classList.contains('is-full'), pref: prefs.get('wrap-table', null) }; });
  console.log('bubble', JSON.stringify(await state()));
  await page.locator('.md-table-block .kebab-opener').click();
  const rows = await page.locator('.action-menu:not(.hidden) .menu-item').allTextContents();
  console.log('menu rows', JSON.stringify(rows.map((r) => r.trim())));
  await page.locator('.action-menu:not(.hidden) .menu-item', { hasText: 'Full view' }).click();
  await page.waitForTimeout(300);
  console.log('full', JSON.stringify(await state()));
  await page.locator('.md-table-block.is-full .wrap-toggle').click();
  console.log('full, wrap pressed off', JSON.stringify(await state()));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  console.log('back in bubble', JSON.stringify(await state()));
  await browser.close();
})();
