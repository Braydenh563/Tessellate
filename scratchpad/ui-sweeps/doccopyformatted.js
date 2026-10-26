// docs3-1026: "Copy as formatted text" puts rendered HTML and the Markdown on
// the clipboard. Reads both back at 1440x900 and 720x900.
//   BASE=http://127.0.0.1:8796 node doccopyformatted.js
const { boot } = require('./lib.js');
(async () => {
  const out = {};
  for (const width of [1440, 720]) {
    const { browser, page } = await boot({ viewport: { width, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
    const ev = (fn, a) => page.evaluate(fn, a);
    const id = await ev(async () => (await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Copy ${Date.now()}`, content: '# Head\n\nSome **bold** and a [link](https://example.com).\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n', file_type: 'md' }) })).id);
    await ev(() => switchTab('documents')); await page.waitForTimeout(700);
    await ev((id) => loadDocuments(id), id); await page.waitForTimeout(2000);
    await ev(() => docCopyFormatted()); await page.waitForTimeout(500);
    out[width] = await ev(async () => {
      const items = await navigator.clipboard.read();
      const types = items[0].types;
      const html = await (await items[0].getType('text/html')).text();
      const plain = await (await items[0].getType('text/plain')).text();
      return { types, tags: ['h1', 'strong', 'a', 'ul', 'table'].map((t) => html.includes('<' + t)), noData: !/data-|onclick|style=/.test(html), plainIsMarkdown: plain.startsWith('# Head') };
    });
    await browser.close();
  }
  console.log(JSON.stringify(out));
})();
