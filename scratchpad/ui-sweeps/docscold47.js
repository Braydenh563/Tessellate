// Cold open of Documents (L-documents-47): from the tab press to a rendered
// editor on a document, a fresh browser context each run (empty HTTP cache, no
// engine bundle). Ready = the engine mounted with the text and either the editor or
// the preview (the phone opens on the preview) on screen. WIDTHS=1440,390 RUNS=5 BASE=http://127.0.0.1:8852 node docscold47.js
const { boot } = require('./lib.js');
const widths = (process.env.WIDTHS || '1440,390').split(',').map(Number);
const runs = Number(process.env.RUNS || 5);
(async () => {
  for (const w of widths) {
    const times = [];
    for (let i = 0; i < runs; i++) {
      const phone = w < 720;
      const { browser, page } = await boot({ viewport: { width: w, height: phone ? 844 : 900 }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
      const ms = await page.evaluate(async () => {
        const r = await api('/documents', { method: 'GET' });
        const list = await r.json();
        const docs = Array.isArray(list) ? list : list.documents || [];
        let id = docs[0]?.id;
        if (!id) {
          const c = await (await api('/documents', { method: 'POST', body: JSON.stringify({ title: 'Cold sweep', content: '# Cold\n\n' + 'word '.repeat(300) }) })).json();
          id = c.id;
        }
        const t0 = performance.now();
        await switchTab('documents');
        if (!document.querySelector('#doc-editor .cm-content')) await openDocument(id);
        for (let k = 0; k < 400; k++) {
          const el = document.querySelector('#doc-editor .cm-content');
          const pv = document.getElementById('doc-preview');
          if (el && el.textContent.length > 0 && (el.offsetParent !== null || (pv && pv.offsetParent !== null))) return performance.now() - t0;
          await new Promise((r) => setTimeout(r, 10));
        }
        return -1;
      });
      times.push(Math.round(ms));
      await browser.close();
    }
    const s = [...times].sort((a, b) => a - b);
    console.log(`width ${w}: runs ${times.join(', ')} ms, median ${s[Math.floor(s.length / 2)]} ms`);
  }
})();
