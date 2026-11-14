// Note edit form's strip is a clone of the capture strip: is any stateful bit
// of the capture strip (collapse state, colour selects) carried over wrongly?
//   BASE=http://127.0.0.1:8831 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/editstrip.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async () => {
    await ensureModule('library'); await api('/entries', { method: 'POST', body: JSON.stringify({ content: 'strip probe note', category: 'General' }) });
  });
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1200);
  const res = {};
  for (const collapsed of [false, true]) {
    res[collapsed ? 'collapsed' : 'open'] = await page.evaluate(async (c) => {
      setDocToolbarCollapsed(c);
      const id = (await api('/entries?limit=5')).map?.((e) => e.id)?.[0] ?? null;
      const first = document.querySelector('#notes-list li[data-id], .note-card[data-id], li[data-id]');
      const entryId = Number(first?.dataset.id);
      setEditingNote(entryId); await loadEntries?.();
      await new Promise((r) => setTimeout(r, 600));
      const src = document.getElementById('note-toolbar');
      const clone = document.querySelector('.note-edit-toolbar');
      const opts = (bar) => [...bar.querySelectorAll('select[data-md-colour]')].map((s) => s.options.length);
      const out = {
        found: Boolean(clone), srcCollapsed: src.classList.contains('is-collapsed'), cloneCollapsed: clone?.classList.contains('is-collapsed'),
        srcOpts: opts(src), cloneOpts: clone ? opts(clone) : null,
        cloneBtnPressed: clone?.querySelector('.doc-toolbar-collapse')?.getAttribute('aria-pressed'),
        cloneShells: clone?.querySelectorAll('.select-shell').length, srcShells: src.querySelectorAll('.select-shell').length, cloneToolsCount: clone?.querySelectorAll('.doc-toolbar-tools').length,
      };
      setEditingNote(null); await loadEntries?.();
      return out;
    }, collapsed);
  }
  console.log(JSON.stringify(res, null, 1));
  await browser.close();
})();
