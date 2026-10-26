// docs-1025:5: the formatting strip's More, open, at phone-to-tablet widths.
// Counts the rows the strip's visible controls fall on (row tops within 6px
// are one row), the strip's height, and whether any control sits outside it.
// Pass: at most 4 rows (the strip row plus up to three of folded tools) at any width listed, nothing outside, no sideways scroll.
// WIDTHS=600,700,820 BASE=http://127.0.0.1:8797 SCRATCH=<dir> node docmorerows.js
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');
const WIDTHS = (process.env.WIDTHS || '600,700,820').split(',').map(Number);
(async () => {
  let failures = 0;
  for (const width of WIDTHS) {
    const { browser, page } = await boot({ viewport: { width, height: 800 } });
    await page.evaluate(() => {
      localStorage.setItem('doc-toolbar-mode', 'row');
      localStorage.setItem('doc-toolbar-mode-migrated-2026-09-09', '1');
      localStorage.setItem('doc-toolbar-collapsed', '0');
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 }).catch(() => {});
    if (await page.isVisible('#lock-password').catch(() => false)) {
      await page.fill('#lock-password', 'testpassword123');
      await page.click('#lock-submit');
      await page.waitForTimeout(3000);
    }
    await openDoc(page, { title: 'More rows', content: '# More rows\n\nText.\n' });
    await page.evaluate(() => setDocView('live'));
    await page.waitForTimeout(600);
    const m = await page.evaluate(() => {
      const bar = document.getElementById('doc-toolbar');
      const more = bar.querySelector('.doc-toolbar-more');
      if (!more || !more.checkVisibility()) return { noMore: true };
      more.click();
      const br = bar.getBoundingClientRect();
      const ctrls = [...bar.querySelectorAll('button, summary, select')].filter((e) => e.checkVisibility() && !e.closest('.doc-dock-menu-list, .select-menu') && e.getBoundingClientRect().width > 0);
      const tops = [];
      for (const c of ctrls) { const r = c.getBoundingClientRect(); const t = Math.round(r.top + r.height / 2); if (!tops.some((x) => Math.abs(x - t) < 12)) tops.push(t); }
      tops.sort((a, b) => a - b);
      const outside = ctrls.filter((c) => { const r = c.getBoundingClientRect(); return r.left < br.left - 0.5 || r.right > br.right + 0.5 || r.bottom > br.bottom + 0.5; }).length;
      const out = { controls: ctrls.length, rows: tops.length, tops: tops.join(','), h: Math.round(br.height), w: Math.round(br.width), outside, sideways: bar.scrollWidth - bar.clientWidth };
      more.click();
      return out;
    });
    const bad = !m.noMore && (m.rows > 4 || m.outside > 0 || m.sideways > 0);
    if (bad) failures++;
    console.log(`${bad ? 'FAIL' : 'ok  '} ${width}`, JSON.stringify(m));
    await browser.close();
  }
  console.log(failures ? 'FAIL' : 'PASS');
})();
