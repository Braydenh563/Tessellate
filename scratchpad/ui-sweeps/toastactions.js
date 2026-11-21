// L616: drive error toasts per surface with every request failing (a stubbed 500) and
// count which carry a what-to-do action of their own (not only the default Open the logs).
//   BASE=http://127.0.0.1:8802 node scratchpad/ui-sweeps/toastactions.js
const { boot } = require('./lib.js');

const CASES = [
  ['meetings', 'openMeetingSheet(1)'],
  
  ['notes', 'openNotePropertiesSheet({ id: 1 })'],
  ['reminders', 'clearDoneReminders()'],
  //: L-world-class-44: the lazy surfaces, opened first (`ensureModule`), then driven the same way.
  ['wb-export', 'ensureModule("boards").then(() => wbLibExport(1))'],
  ['wb-history', 'ensureModule("boards").then(() => wbOpenHistory())'],
  ['doc-bookmark', 'ensureModule("library").then(() => { currentDoc = { id: 1, title: "t", content: "" }; return attachBookmarkToDocument(); }).finally(() => { currentDoc = null; })'],
];

(async () => {
  const { browser, page } = await boot({});
  await page.evaluate(() => {
    const real = window.fetch.bind(window);
    window.__failing = false;
    window.fetch = (url, opts) => window.__failing
      ? Promise.resolve(new Response(JSON.stringify({ detail: 'Internal error' }), { status: 500, headers: { 'content-type': 'application/json' } }))
      : real(url, opts);
  });
  const rows = [];
  for (const [surface, call] of CASES) {
    const row = await page.evaluate(async (call) => {
      document.querySelectorAll('.toast').forEach((t) => t.remove());
      window.__failing = true;
      try { await (0, eval)(call); } catch (e) { window.__err = String(e); }
      await new Promise((r) => setTimeout(r, 2500));
      window.__failing = false;
      const note = document.querySelector('.toast.error');
      if (!note) return { toast: false, text: window.__err || "" };
      const buttons = [...note.querySelectorAll('button')].map((b) => b.textContent.trim());
      return { toast: true, text: note.querySelector('.toast-msg').textContent, buttons };
    }, call);
    rows.push({ surface, ...row });
  }
  let own = 0;
  for (const r of rows) {
    const mine = r.toast && r.buttons.some((b) => b && b !== 'Report this' && b !== 'Open the logs' && b.length > 1);
    if (mine) own++;
    console.log(r.surface.padEnd(12), r.toast ? (mine ? 'action ' : 'DEFAULT') : 'NO TOAST', JSON.stringify(r.buttons || []), (r.text || '').slice(0, 60));
  }
  console.log(`${own} of ${rows.length} sampled surfaces carry their own action`);
  await browser.close();
  process.exit(own === rows.length ? 0 : 1);
})();
