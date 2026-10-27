// The same cards in a note's Read view (#doc-preview), where the table rule is
// its own (09-editor.css: width auto): does the toggle change anything there?
//   BASE=http://127.0.0.1:8951 THEME=dark W=1280 node wrapnote.js
const { boot } = require('./lib.js');
const MD = [
  '| Name | Role | Notes | Location | Started | Manager |',
  '| --- | --- | --- | --- | --- | --- |',
  '| Alexandria Montgomery-Whitfield | Principal infrastructure engineer | Leads the migration of every legacy billing service onto the new platform | Edinburgh, United Kingdom | 2019-03-11 | Bartholomew Featherstonehaugh |',
  '', '```python',
  'result = compute_the_quarterly_totals(accounts=all_active_accounts, include_adjustments=True, currency="GBP", rounding="bankers", as_of="2026-09-30")',
  '```',
].join('\n');
(async () => {
  const { page, browser } = await boot({ viewport: { width: Number(process.env.W || 1280), height: 800 } });
  await page.waitForTimeout(2000);
  await page.evaluate((md) => {
    const host = document.getElementById('doc-preview');
    document.body.appendChild(host); host.classList.remove('hidden');
    host.style.width = '600px';
    host.style.position = 'fixed'; host.style.top = '60px'; host.style.left = '20px'; host.style.zIndex = 9999; host.style.background = '#111';
    renderMarkdown(host, md);
  }, MD);
  await page.waitForTimeout(300);
  const m = () => page.evaluate(() => {
    const t = document.querySelector('#doc-preview .md-table-wrap');
    const p = document.querySelector('#doc-preview .code-block:not(.md-table-block) pre');
    return { table: [t.scrollWidth, t.clientWidth], code: [p.scrollWidth, p.clientWidth], view: document.querySelector('#doc-preview .md-table-block').dataset.tableView };
  });
  console.log('before', JSON.stringify(await m()));
  await page.locator('#doc-preview .md-table-block .wrap-toggle').click();
  await page.locator('#doc-preview .code-block:not(.md-table-block) .wrap-toggle').click();
  await page.waitForTimeout(200);
  console.log('after', JSON.stringify(await m()));
  await browser.close();
})();
