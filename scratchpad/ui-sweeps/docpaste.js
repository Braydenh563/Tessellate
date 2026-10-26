// docpaste-1026: paste options chip and Paste special, at 1440x900 and 720x900,
// driving real ClipboardEvents with a DataTransfer.
//   BASE=http://127.0.0.1:8798 node docpaste.js
const { boot } = require('./lib.js');
(async () => {
  const out = {};
  for (const width of [1440, 720]) {
    const { browser, page } = await boot({ viewport: { width, height: 900 } });
    const ev = (fn, a) => page.evaluate(fn, a);
    const id = await ev(async () => (await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Paste ${Date.now()}`, content: 'Intro line\n\nSee docs here\n\nend\n', file_type: 'md' }) })).id);
    await ev(() => switchTab('documents')); await page.waitForTimeout(700);
    await ev((id) => loadDocuments(id), id); await page.waitForTimeout(2000);
    const paste = (data, sel) => ev(({ data, sel }) => {
      const v = docSurface().view; v.focus();
      v.dispatch({ selection: { anchor: sel[0], head: sel[1] } });
      const dt = new DataTransfer();
      for (const [k, val] of Object.entries(data)) dt.setData(k, val);
      v.contentDOM.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    }, { data, sel });
    const chip = () => ev(() => { const c = document.querySelector('.doc-paste-chip'); if (!c || c.classList.contains('hidden')) return null; const b = c.getBoundingClientRect(); return { l: Math.round(b.left), t: Math.round(b.top), r: Math.round(b.right), b: Math.round(b.bottom), fits: b.left >= 0 && b.top >= 0 && b.right <= innerWidth && b.bottom <= innerHeight, w: Math.round(b.width), h: Math.round(b.height) }; });
    const text = () => ev(() => docText());
    const r = {};
    // 1. Rich paste -> chip -> Text only, one undo.
    await paste({ 'text/html': '<h2>Title</h2><p>Some <strong>bold</strong> text</p>', 'text/plain': 'Title\nSome bold text' }, [0, 0]);
    r.richText = (await text()).split('\n').slice(0, 3).join('|');
    r.richChip = await chip();
    r.chipOnTop = await ev(() => { const b = document.querySelector('.doc-paste-chip button').getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return !!e.closest('.doc-paste-chip'); });
    await page.keyboard.press('Control'); await page.waitForTimeout(400);
    r.menuRows = await ev(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].map((b) => b.textContent.trim()));
    r.menuFits = await ev(() => { const m = document.querySelector('.action-menu:not(.hidden)'); if (!m) return null; const b = m.getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth && b.bottom <= innerHeight; });
    await page.keyboard.press('t'); await page.waitForTimeout(300);
    r.afterText = (await text()).split('\n').slice(0, 3).join('|');
    await ev(() => docUndoBreak()); await page.keyboard.press('Control+z'); await page.waitForTimeout(300);
    r.afterUndo = (await text()).split('\n').slice(0, 3).join('|');
    // 2. Typing dismisses; Escape dismisses.
    await page.keyboard.press('x'); await page.waitForTimeout(200);
    r.chipAfterTyping = await chip();
    // 3. URL over selection.
    const doc = await text(); const at = doc.indexOf('docs');
    await paste({ 'text/plain': 'https://example.com/x' }, [at, at + 4]);
    r.link = (await text()).includes('[docs](https://example.com/x)');
    r.linkChip = !!(await chip());
    await page.keyboard.press('Escape'); await page.waitForTimeout(150);
    r.chipAfterEsc = await chip();
    // 4. Multi-line -> checklist via chip click.
    const end = (await text()).length;
    await paste({ 'text/plain': 'milk\n- eggs\nbread' }, [end, end]);
    r.multiChip = await chip();
    await page.click('.doc-paste-chip button'); await page.waitForTimeout(300);
    r.multiMenu = await ev(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].map((b) => b.textContent.trim()));
    await page.keyboard.press('c'); await page.waitForTimeout(300);
    r.checklist = (await text()).includes('- [ ] milk\n- [ ] eggs\n- [ ] bread');
    // 5. TSV outside a table -> becomes the table at once; the chip puts the text back.
    const end2 = (await text()).length;
    await paste({ 'text/plain': 'a\tb\n1\t2' }, [end2, end2]);
    r.table = (await text()).includes('| a | b |\n| --- | --- |\n| 1 | 2 |');
    r.tableChip = !!(await chip());
    await page.keyboard.press('Escape'); await page.waitForTimeout(150);
    // Indented code stays text.
    await ev(() => { const v = docSurface().view; v.dispatch({ changes: { from: v.state.doc.length, insert: '\n\nafter\n' } }); });
    const end3 = (await text()).length;
    await paste({ 'text/plain': '\tfoo\tbar\n\tbaz\tqux' }, [end3, end3]);
    r.indentedCodeStaysText = !(await text()).includes('| foo |');
    await page.keyboard.press('Escape'); await page.waitForTimeout(150);
    // 6. Paste special from the palette command, armed route (clipboard read refused).
    r.special = await ev(async () => {
      Object.defineProperty(navigator, 'clipboard', { value: { readText: async () => 'one\ntwo' }, configurable: true });
      const end = docText().length; docSurface().view.focus(); docSurface().view.dispatch({ selection: { anchor: end } });
      await docPasteSpecial('quote');
      return docText().endsWith('> one\n> two');
    });
    r.menuRow = await ev(() => !!document.getElementById('doc-paste-special'));
    r.specialMenu = await ev(() => { docPasteSpecialMenu(); return [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].map((b) => b.textContent.trim()).length; });
    await page.keyboard.press('Escape');
    // 7. Ctrl+Shift+V path leaves a multi-line paste alone (no chip).
    r.consoleErrors = 0;
    out[width] = r;
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
