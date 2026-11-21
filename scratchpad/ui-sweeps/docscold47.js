// Cold open of Documents (L-documents-47): from the tab press to a rendered
// editor on a document, a fresh browser context each run (empty HTTP cache, no
// engine bundle). Ready = the engine mounted with the text and either the editor or
// the preview (the phone opens on the preview) on screen. WIDTHS=1440,390 RUNS=5 BASE=http://127.0.0.1:8852 node docscold47.js
// L-documents-83: wall time moves with the box's load, so each run also reads the main thread's CPU
// from CDP (Performance.getMetrics deltas: Task, Script, RecalcStyle, Layout durations) between the
// tab press and the mount; the budget is judged on that median CPU (BUDGET_MS), wall beside it.
const BUDGET_MS = 800;
const { boot } = require('./lib.js');
const widths = (process.env.WIDTHS || '1440,390').split(',').map(Number);
const runs = Number(process.env.RUNS || 5);
(async () => {
  for (const w of widths) {
    const times = [];
    const cpu = [];
    for (let i = 0; i < runs; i++) {
      const phone = w < 720;
      const { browser, page } = await boot({ viewport: { width: w, height: phone ? 844 : 900 }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
      const cdp = await page.context().newCDPSession(page);
      await cdp.send('Performance.enable');
      const snap = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value * 1000]));
      const id = await page.evaluate(async () => {
        const r = await api('/documents', { method: 'GET' });
        const list = await r.json();
        const docs = Array.isArray(list) ? list : list.documents || [];
        let id = docs[0]?.id;
        if (!id) {
          const c = await (await api('/documents', { method: 'POST', body: JSON.stringify({ title: 'Cold sweep', content: '# Cold\n\n' + 'word '.repeat(300) }) })).json();
          id = c.id;
        }
        return id;
      });
      await page.waitForTimeout(1500);
      const m0 = await snap();
      const ms = await page.evaluate(async (id) => {
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
      }, id);
      const m1 = await snap();
      const d = (k) => Math.round(m1[k] - m0[k]);
      cpu.push({ task: d('TaskDuration'), script: d('ScriptDuration'), style: d('RecalcStyleDuration'), layout: d('LayoutDuration') });
      times.push(Math.round(ms));
      await browser.close();
    }
    const s = [...times].sort((a, b) => a - b);
    const med = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
    const c = Object.fromEntries(['task', 'script', 'style', 'layout'].map((k) => [k, med(cpu.map((r) => r[k]))]));
    console.log(`width ${w} cpu: task runs ${cpu.map((r) => r.task).join(', ')} ms, median ${c.task} ms (script ${c.script}, style ${c.style}, layout ${c.layout}); budget ${BUDGET_MS} ms ${c.task < BUDGET_MS ? 'met' : 'over'}`);
    console.log(`width ${w}: runs ${times.join(', ')} ms, median ${s[Math.floor(s.length / 2)]} ms`);
  }
})();
