// Escape on the reminders add form, the notes edit entry and the graph node popup.
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node esc-forms-1018.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  const r = {};
  await page.evaluate(async () => {
    for (const c of ['# Alpha\nfirst note about maps', '# Beta\nsecond note about maps', '# Gamma\nthird note']) {
      await api('/entries', { method: 'POST', body: JSON.stringify({ content: c }) });
    }
  });
  // reminders
  await page.evaluate(() => switchTab('reminders')); await page.waitForTimeout(1200);
  await page.fill('#reminder-text', 'call mum');
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);
  r.reminderTextAfterEscape = await page.inputValue('#reminder-text');
  r.reminderFocusAfter = await page.evaluate(() => document.activeElement.id || document.activeElement.tagName);
  // notes edit
  await page.evaluate(() => switchTab('notes')); await page.waitForTimeout(500); await page.evaluate(() => typeof loadEntries === 'function' && loadEntries()); await page.waitForTimeout(2000);
  await page.evaluate(() => { const e = allEntries.find((x) => /Alpha/.test(x.content)); openNoteEditor(e.id); });
  await page.waitForTimeout(800);
  r.editOpen = await page.evaluate(() => editingId !== null);
  r.editFocus = await page.evaluate(() => document.activeElement.id || document.activeElement.className);
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  r.editAfterEscapeBody = await page.evaluate(() => editingId !== null);
  await page.evaluate(() => { const e = allEntries.find((x) => /Alpha/.test(x.content)); openNoteEditor(e.id); });
  await page.waitForTimeout(800);
  await page.focus('.note-edit-title'); await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  r.editAfterEscapeTitle = await page.evaluate(() => editingId !== null);
  await page.evaluate(() => { const e = allEntries.find((x) => /Alpha/.test(x.content)); openNoteEditor(e.id); });
  await page.waitForTimeout(800);
  await page.focus('#entry-edit-content'); await page.keyboard.type(' typed'); await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  r.editDirtyEscape = await page.evaluate(() => ({ editing: editingId !== null, dialog: !!document.querySelector('.modal-overlay:not(.hidden), dialog[open], .confirm-actions') }));
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  r.editDirtyEscape2 = await page.evaluate(() => ({ editing: editingId !== null, dialog: !!document.querySelector('.confirm-actions') }));
  await page.evaluate(() => { const b = [...document.querySelectorAll('.confirm-actions button')].find((x) => /discard|cancel|leave/i.test(x.textContent)); b && b.click(); });
  await page.waitForTimeout(300);
  // graph popup
  await page.evaluate(() => switchTab('graph')); await page.waitForTimeout(3000);
  await page.evaluate(() => { const n = graphNodesRef.find((x) => /Beta/.test(x.title || x.label || '')) || graphNodesRef[0]; openGraphPopup({ clientX: 400, clientY: 300, stopPropagation() {} }, n); });
  await page.waitForTimeout(1200);
  r.popupOpen = await page.evaluate(() => !document.getElementById('graph-popup').classList.contains('hidden'));
  await page.evaluate(() => document.querySelector('#graph-popup button')?.focus());
  await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  r.popupAfterEscapeFocusInside = await page.evaluate(() => !document.getElementById('graph-popup').classList.contains('hidden'));
  await page.evaluate(() => { const n = graphNodesRef[0]; openGraphPopup({ clientX: 400, clientY: 300, stopPropagation() {} }, n); });
  await page.waitForTimeout(1000);
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  r.popupAfterEscapeBodyFocus = await page.evaluate(() => !document.getElementById('graph-popup').classList.contains('hidden'));
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
})();
