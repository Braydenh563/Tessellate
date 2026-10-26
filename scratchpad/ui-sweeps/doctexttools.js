// docs3-1026: document statistics and text tools, at 1440x900 and a half-screen
// 720x900. Opens the statistics from the status bar's counts, measures the
// dialog against the viewport, then runs the case, sort and heading tools.
//   BASE=http://127.0.0.1:8796 node doctexttools.js
const { boot } = require('./lib.js');
(async () => {
  const out = {};
  for (const width of [1440, 720]) {
    const { browser, page } = await boot({ viewport: { width, height: 900 } });
    const ev = (fn, a) => page.evaluate(fn, a);
    const body = '# Report\n\n## Method\n\nzebra\napple\nItem 10\nItem 2\napple\n\n## Results\n\n' + 'The cat sat on the mat and looked around the garden carefully. '.repeat(6) + '\n';
    const id = await ev(async (b) => (await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Tools ${Date.now()}`, content: b, file_type: 'md' }) })).id, body);
    await ev(() => switchTab('documents')); await page.waitForTimeout(700);
    await ev((id) => loadDocuments(id), id); await page.waitForTimeout(2000);
    const r = {};
    await page.click('#doc-counts'); await page.waitForTimeout(300);
    r.dialog = await ev(() => { const d = document.getElementById('doc-stats-dialog'); const b = d.getBoundingClientRect(); return { open: d.open, left: Math.round(b.left), right: Math.round(b.right), vw: innerWidth, hScroll: d.scrollWidth > d.clientWidth, rows: d.querySelectorAll('dt').length }; });
    await page.keyboard.press('Escape'); await page.waitForTimeout(200);
    r.focusable = await ev(() => { const c = document.getElementById('doc-counts'); c.focus(); return document.activeElement === c; });
    await page.keyboard.press('Enter'); await page.waitForTimeout(300);
    r.openByKey = await ev(() => document.getElementById('doc-stats-dialog').open);
    await page.keyboard.press('Escape');
    r.tools = await ev(() => {
      docRunTextTool('number-headings');
      const numbered = docText().split('\n').filter((l) => /^##? /.test(l)).join('|');
      docRunTextTool('unnumber-headings');
      const t = docText(); const a = t.indexOf('zebra'); const b = t.indexOf('apple\n\n') + 5;
      docSurface().setSelectionRange(a, b); docRunTextTool('sort-asc');
      return { numbered, sorted: docText().slice(a, b).replace(/\n/g, '/') };
    });
    r.undo = await ev(async () => { docSurface().focus(); return true; });
    await page.keyboard.press('Control+z'); await page.waitForTimeout(300);
    r.afterUndo = await ev(() => docText().includes('zebra\napple\nItem 10'));
    out[width] = r;
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
