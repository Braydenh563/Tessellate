// INBOX 1318: the Stats and Streak widgets open the Statistics page.
//   BASE=http://127.0.0.1:8791 node stats1318.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const ev = (fn, a) => page.evaluate(fn, a);
  const out = {};
  await ev(async () => { for (let n = 0; n < 3; n++) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Stats seed ${n}`, tags: [], defer_filing: true }) }); await loadEntries(); });
  for (const name of ['stats', 'streak']) {
    await ev(async (name) => { const l = dashLayout(); l.hidden = l.hidden.filter((n) => n !== name); await saveDashLayout(l); }, name);
    await ev(() => switchTab('dashboard')); await page.waitForTimeout(400);
    await ev(() => renderDashboard()); await page.waitForTimeout(2500);
    await ev((id) => document.getElementById(id)?.scrollIntoView(), `${name}-statistics`); await page.waitForTimeout(300);
    const id = `${name}-statistics`;
    const seen = await ev((id) => { const b = document.getElementById(id); if (!b) return null; const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), b.textContent.trim(), b.offsetParent !== null]; }, id);
    let opened = null;
    if (seen) {
      await page.click(`#${id}`); await page.waitForTimeout(2000);
      opened = await ev(() => [document.querySelector('.tab-page:not(.hidden)')?.id, [...document.querySelectorAll('dialog[open], .modal-overlay:not(.hidden)')].map((d) => d.id || d.className).join(',')]);
      await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    }
    out[name] = { seen, opened };
  }
  console.log(JSON.stringify(out));
  await browser.close();
})();
