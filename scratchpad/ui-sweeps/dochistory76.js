// Brief 76 (DOCUMENTS 24 row 4): version history as Google Docs's. Names the
// current version through the dialog's own prompt, filters Named, opens a
// side-by-side Changes, restores a version and presses Ctrl+Z: prints whether
// the text came back byte-equal.
//   BASE=http://127.0.0.1:8834 [VW=1440] node dochistory76.js
const { boot } = require('./lib.js');
(async () => {
  const VW = Number(process.env.VW || 1440);
  const { browser, page } = await boot(VW < 600 ? { viewport: { width: VW, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: VW, height: 900 } });
  const ev = (fn, a) => page.evaluate(fn, a);
  const st = Date.now();
  const id = await ev(async (st) => {
    const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'History ' + st, content: 'Line one.\nLine two.\nLine three.\n', file_type: 'md' }) });
    await apiJson(`/documents/${d.id}`, { method: 'PUT', body: JSON.stringify({ content: 'Line one.\nLine 2, rewritten.\nLine three.\nLine four.\n' }) });
    return d.id;
  }, st);
  await ev(() => switchTab('documents')); await page.waitForTimeout(700);
  await ev((id) => loadDocuments(id), id); await page.waitForTimeout(1800);
  const out = {};
  //: Through the dock's button: the dialog's code is documents-history.js (docs-1101), fetched by this press.
  out.beforePress = await ev(() => typeof docRenderDiff);
  await ev(() => document.getElementById('doc-history').click()); await page.waitForTimeout(1500);
  out.afterPress = await ev(() => typeof docRenderDiff);
  await page.click('#doc-history-name');
  await page.waitForTimeout(500);
  const prompt = await ev(() => { const o = document.querySelector('.confirm-overlay'); return o ? { inDialog: !!o.closest('dialog[open]'), reachable: document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.closest('.confirm-overlay') != null } : null; });
  out.prompt = prompt;
  await page.keyboard.type('Sent to Sam'); await page.keyboard.press('Enter'); await page.waitForTimeout(1200);
  out.named = await ev(async (id) => (await apiJson(`/documents/${id}/revisions`)).filter((r) => r.name).map((r) => r.name), id);
  await page.click('#doc-history-filter [data-history-filter="named"]'); await page.waitForTimeout(400);
  out.namedRows = await ev(() => document.querySelectorAll('#doc-history-list > li').length);
  await page.click('#doc-history-filter [data-history-filter="all"]'); await page.waitForTimeout(400);
  const last = '#doc-history-list > li:last-child';
  await page.click(`${last} .doc-history-actions button:first-child`); await page.waitForTimeout(900);
  out.diff = await ev((sel) => {
    const box = document.querySelector(sel + ' .doc-diff');
    if (!box) return null;
    const cs = getComputedStyle(box);
    const lines = [...box.querySelectorAll('.doc-diff-line')];
    const left = lines.filter((l) => l.style.gridColumn === '1').length, right = lines.filter((l) => l.style.gridColumn === '2').length;
    const heads = [...box.querySelectorAll('.doc-diff-split-head')].map((h) => h.textContent);
    const b = box.getBoundingClientRect();
    const xs = [...new Set(lines.map((l) => Math.round(l.getBoundingClientRect().left)))];
    return { display: cs.display, cols: cs.gridTemplateColumns, left, right, heads, columnsX: xs, overflowX: box.scrollWidth > box.clientWidth + 1, width: Math.round(b.width) };
  }, last);
  const before = await ev(() => docText());
  await page.click(`${last} .doc-history-actions button:nth-child(3)`); await page.waitForTimeout(1500);
  out.dialogClosed = await ev(() => !document.getElementById('doc-history-dialog').open);
  const restored = await ev(() => docText());
  out.restoredChanged = restored !== before;
  await ev(() => document.activeElement?.blur?.());
  await page.keyboard.press('Control+z'); await page.waitForTimeout(1500);
  const after = await ev(() => docText());
  const server = await ev(async (id) => (await apiJson(`/documents/${id}`)).content, id);
  out.undoByteEqual = after === before && server === before;
  console.log(JSON.stringify(out));
  await browser.close();
})();
