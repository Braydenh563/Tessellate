// dog1-1025: a drag across note cards and library cards must not select card
// chrome (titles, dates, buttons); previews and the open note stay selectable.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 900 } });
  await page.waitForTimeout(2500);
  const have = await page.evaluate(async () => (await apiJson('/entries?limit=5')).length ?? 0).catch(() => -1);
  if (!have || have < 4) {
    for (let i = 1; i <= 5; i++) await page.evaluate(async (i) => apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Card ${i} heading\n\nBody text number ${i} with a few words to read and copy. `.repeat(3) }) }), i);
  }
  await page.evaluate(() => { switchTab('notes'); showNotesSection('browse'); });
  await page.waitForTimeout(1500);
  const drag = async (sel) => {
    const boxes = await page.$$eval(sel, (els) => els.slice(0, 5).map((e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }));
    if (boxes.length < 2) return 'cards:' + boxes.length;
    const a = boxes[0], b = boxes[boxes.length - 1];
    await page.mouse.move(a[0] + 4, a[1] + 4); await page.mouse.down();
    await page.mouse.move(b[2] - 4, b[3] - 4, { steps: 8 }); await page.mouse.up();
    return await page.evaluate(() => {
      const s = getSelection(); if (!s.rangeCount) return 0;
      const frag = s.getRangeAt(0).cloneContents();
      const chrome = [...frag.querySelectorAll('.entry-title, .entry-meta, .entry-date, .library-card-title, .library-card-meta, button')].map((e) => e.textContent).join('').length;
      return { total: s.toString().length, chromeChars: chrome };
    });
  };
  console.log('notes', JSON.stringify(await drag('#entry-list > li')));
  await page.evaluate(() => getSelection().removeAllRanges());
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(2500);
  console.log('library', JSON.stringify(await drag('.library-card')));
  await page.evaluate(() => getSelection().removeAllRanges());
  const us = await page.evaluate(() => { const g = (s) => { const e = document.querySelector(s); return e ? getComputedStyle(e).userSelect : null; }; return { libCard: g('.library-card'), libPreview: g('.library-card-preview'), libTitle: g('.library-card-title') }; });
  console.log('user-select', JSON.stringify(us));
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1500);
  const p0 = await page.$eval('#entry-list li .entry-content', (e) => { const r = e.getBoundingClientRect(); return [r.left + 40, r.top + 8]; });
  await page.mouse.dblclick(p0[0], p0[1]);
  console.log('preview word selectable chars', await page.evaluate(() => getSelection().toString().length));
  await browser.close();
})();
