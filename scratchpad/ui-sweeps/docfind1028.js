// Audit 1028 U9, D29, D17: the find panel's match count, Replace in every
// document's whole word and leave-out box, and an emptied title on autosave.
//   BASE=http://127.0.0.1:8791 node docfind1028.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const ev = (fn, a) => page.evaluate(fn, a);
  const st = Date.now();
  const ids = await ev(async (st) => {
    const out = [];
    for (let n = 0; n < 3; n++) out.push((await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Find ${st} ${n}`, content: `cafe${st} cafe${st}s and cafe${st} again`, file_type: 'md' }) })).id);
    return out;
  }, st);
  await ev(() => switchTab('documents')); await page.waitForTimeout(700);
  await ev((id) => loadDocuments(id), ids[0]); await page.waitForTimeout(1500);
  await ev(() => { docCmView.focus(); toggleDocFindBar(true); }); await page.waitForTimeout(300);
  await page.type('.cm-search .cm-textfield[name="search"]', `cafe${st}`); await page.waitForTimeout(400);
  const count = await ev(() => document.querySelector('.cm-search-count')?.textContent);
  await page.keyboard.press('Escape');
  await ev(() => openDocReplace()); await page.waitForTimeout(400);
  await page.check('#doc-replace-word');
  await page.fill('#doc-replace-find', `cafe${st}`);
  await page.fill('#doc-replace-with', 'tea');
  await page.waitForTimeout(2500);
  const summary = await ev(() => document.getElementById('doc-replace-summary').textContent);
  const snippet = await ev(() => document.querySelector('.doc-replace-snippet')?.textContent);
  const rows = await ev(() => document.querySelectorAll('#doc-replace-list input[type=checkbox]').length);
  await page.locator('#doc-replace-list input[type=checkbox]').nth(1).uncheck();
  await page.click('#doc-replace-run'); await page.waitForTimeout(2500);
  const after = await ev(async (ids) => Promise.all(ids.map(async (id) => (await apiJson(`/documents/${id}`)).content)), ids);
  await ev((id) => loadDocuments(id), ids[2]); await page.waitForTimeout(1200);
  await page.fill('#doc-title', ''); await page.waitForTimeout(2500);
  const blankSaved = await ev(async (id) => (await apiJson(`/documents/${id}`)).title, ids[2]);
  const fieldWhileBlank = await ev(() => document.getElementById('doc-title').value);
  await ev(() => document.getElementById('doc-title').blur()); await page.waitForTimeout(2500);
  const afterBlur = await ev(async (id) => [(await apiJson(`/documents/${id}`)).title, document.getElementById('doc-title').value], ids[2]);
  console.log(JSON.stringify({ count, summary, rows, snippet, after, blankSaved, fieldWhileBlank, afterBlur }));
  await browser.close();
})();
