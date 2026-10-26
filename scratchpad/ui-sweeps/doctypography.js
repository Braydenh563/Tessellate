// docs3-1026: Text size and Line spacing rows in a document's menu. Measures the
// computed font-size and line-height of the Source editor and the Read pane for
// each step, at 1440x900 and 720x900, and that the choice survives a reload.
//   BASE=http://127.0.0.1:8796 node doctypography.js
const { boot } = require('./lib.js');
(async () => {
  const out = {};
  for (const width of [1440, 720]) {
    const { browser, page } = await boot({ viewport: { width, height: 900 } });
    const ev = (fn, a) => page.evaluate(fn, a);
    const id = await ev(async () => (await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Type ${Date.now()}`, content: '# Head\n\n' + 'Some prose to measure. '.repeat(40) + '\n', file_type: 'md' }) })).id);
    await ev(() => switchTab('documents')); await page.waitForTimeout(700);
    await ev((id) => loadDocuments(id), id); await page.waitForTimeout(2000);
    const measure = () => ev(() => {
      const css = (el) => { const c = getComputedStyle(el); return [c.fontSize, c.lineHeight]; };
      const ed = document.querySelector('.doc-source-wrap .cm-editor:not(.doc-content-code) .cm-scroller');
      const pv = document.getElementById('doc-preview');
      return { editor: ed ? css(ed) : null, preview: pv ? css(pv) : null,
        labels: [document.getElementById('doc-text-size-label').textContent, document.getElementById('doc-line-spacing-label').textContent] };
    });
    const r = { start: await measure() };
    for (let i = 0; i < 2; i++) { await ev(() => document.getElementById('doc-text-size').click()); r['size' + (i + 1)] = await measure(); }
    await ev(() => document.getElementById('doc-text-size').click());
    for (let i = 0; i < 2; i++) { await ev(() => document.getElementById('doc-line-spacing').click()); r['space' + (i + 1)] = await measure(); }
    await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
    r.afterReload = await ev(() => [...document.getElementById('tab-documents').classList].filter((c) => /^doc-(size|spacing)/.test(c)));
    // the dock menu fits the viewport
    out[width] = r;
    await browser.close();
  }
  console.log(JSON.stringify(out));
})();
