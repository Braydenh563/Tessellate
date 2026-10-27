// The wrap toggle on a reply's table and code cards (the owner, 2026-10-27:
// "can you add a button to toggle wrap text in tables or code blocks??").
// Renders a wide table and a long code line as an assistant bubble and reports
// scrollWidth vs clientWidth before and after pressing each card's toggle, and
// the computed look of every control in the card's head.
//   BASE=http://127.0.0.1:8951 THEME=dark W=1280 node wraptoggle.js
//   SNAP=/path.json  writes the head's computed styles (for a before/after diff)
const { boot } = require('./lib.js');
const MD = [
  'Here is the table.', '',
  '| Name | Role | Notes | Location | Started | Manager |',
  '| --- | --- | --- | --- | --- | --- |',
  '| Alexandria Montgomery-Whitfield | Principal infrastructure engineer | Leads the migration of every legacy billing service onto the new platform | Edinburgh, United Kingdom | 2019-03-11 | Bartholomew Featherstonehaugh |',
  '', 'And the code.', '',
  '```python',
  'result = compute_the_quarterly_totals(accounts=all_active_accounts, include_adjustments=True, currency="GBP", rounding="bankers", as_of="2026-09-30")',
  '```',
].join('\n');
(async () => {
  const width = Number(process.env.W || 1280);
  const { page, browser } = await boot({ viewport: { width, height: 800 } });
  await page.waitForTimeout(2000);
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  await page.evaluate((md) => {
    const b = addBubble('assistant', '');
    renderMarkdown(b.querySelector('.msg-body'), md);
    b.scrollIntoView();
  }, MD);
  await page.waitForTimeout(400);
  const fit = (sel) => page.evaluate((s) => {
    const el = document.querySelector(s);
    return el ? { scrollW: el.scrollWidth, clientW: el.clientWidth } : null;
  }, sel);
  const T = '#chat-messages .md-table-block > .md-table-wrap';
  const C = '#chat-messages .code-block:not(.md-table-block) > pre';
  const head = (kind) => page.evaluate((k) => {
    const block = k === 'table' ? document.querySelector('#chat-messages .md-table-block') : document.querySelector('#chat-messages .code-block:not(.md-table-block)');
    const out = [];
    for (const el of block.querySelectorAll('.code-actions > *')) {
      const btn = el.matches('.menu-wrap') ? el.querySelector('button') : el;
      const cs = getComputedStyle(btn);
      const r = btn.getBoundingClientRect();
      out.push({ cls: btn.className, label: btn.getAttribute('aria-label') || btn.textContent.trim(), pressed: btn.getAttribute('aria-pressed'), title: btn.title,
        w: Math.round(r.width), h: Math.round(r.height), bg: cs.backgroundColor, color: cs.color, shadow: cs.boxShadow, radius: cs.borderRadius, pad: cs.padding,
        seam: getComputedStyle(el).boxShadow });
    }
    return out;
  }, kind);
  const res = { width };
  res.tableBefore = await fit(T); res.codeBefore = await fit(C);
  res.tableHead = await head('table'); res.codeHead = await head('code');
  if (process.env.SNAP) require('fs').writeFileSync(process.env.SNAP, JSON.stringify({ t: res.tableHead, c: res.codeHead }, null, 1));
  const press = async (kind) => {
    const btn = page.locator(`${kind === 'table' ? '#chat-messages .md-table-block' : '#chat-messages .code-block:not(.md-table-block)'} .wrap-toggle`);
    if (!(await btn.count())) return false;
    await btn.click();
    await page.waitForTimeout(250);
    return true;
  };
  res.tablePressed = await press('table'); res.tableAfter = await fit(T);
  res.codePressed = await press('code'); res.codeAfter = await fit(C);
  // A card drawn after the presses starts as they left it; pressing again unwraps and is remembered too.
  await page.evaluate((md) => { const b = addBubble('assistant', ''); renderMarkdown(b.querySelector('.msg-body'), md); }, MD);
  res.nextCard = await page.evaluate(() => { const c = [...document.querySelectorAll('#chat-messages .code-block:not(.md-table-block)')].pop(); const t = [...document.querySelectorAll('#chat-messages .md-table-block')].pop();
    return { codeWrap: c.dataset.wrap, codePressed: c.querySelector('.wrap-toggle').getAttribute('aria-pressed'), tableView: t.dataset.tableView, tablePressed: t.querySelector('.wrap-toggle').getAttribute('aria-pressed') }; });
  await page.locator('#chat-messages .code-block:not(.md-table-block) .wrap-toggle').last().click();
  res.codeUnwrap = await page.evaluate(() => ({ pref: prefs.get('wrap-code', null), pre: (() => { const p = [...document.querySelectorAll('#chat-messages .code-block:not(.md-table-block) pre')].pop(); return [p.scrollWidth, p.clientWidth]; })() }));
  res.docScrollW = await page.evaluate(() => document.documentElement.scrollWidth);
  res.remembered = await page.evaluate(() => ({ table: prefs.get('wrap-table', null), code: prefs.get('wrap-code', null) }));
  console.log(JSON.stringify(res));
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT });
  await browser.close();
})();
