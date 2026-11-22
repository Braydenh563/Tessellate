// Select mode survives a repaint: a note saved elsewhere (its save event
// repaints the Notes list) must keep the ticks and the list's scroll place.
// Run: BASE=... node scratchpad/ui-sweeps/selectrepaint.js
const { boot } = require('./lib');
(async () => {
  const { browser, page } = await boot();
  const fails = [];
  const check = (ok, what, got) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}  ${JSON.stringify(got)}`); if (!ok) fails.push(what); };
  const stamp = Date.now().toString(36);
  const ids = await page.evaluate(async (s) => {
    const out = [];
    for (let i = 0; i < 40; i++) out.push((await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Select repaint ${s} ${i}\n\nA line so the row has height.` }) })).id);
    return out;
  }, stamp);
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(600);
  await page.evaluate(() => loadEntries());
  await page.evaluate(() => document.querySelector('[data-section="browse"]')?.click());
  await page.waitForTimeout(1500);
  console.log('rows', await page.evaluate((p) => { const li = [...document.querySelectorAll('#entry-list > li[data-id]')]; return [li.length, li.slice(0, 5).map((e) => e.dataset.id), li.findIndex((e) => e.dataset.id == p)]; }, ids[20]));
  await page.evaluate(() => document.getElementById('select-btn').click());
  await page.waitForTimeout(500);
  const scroller = () => { let el = document.querySelector('#entry-list'); while (el && el !== document.body) { const s = getComputedStyle(el); if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight) return el; el = el.parentElement; } return document.scrollingElement; };
  // Tick two rows that sit mid-list, after scrolling to them.
  const picks = [ids[20], ids[22]];
  for (const id of picks) {
    const row = page.locator(`#entry-list > li[data-id="${id}"]`).first();
    await row.scrollIntoViewIfNeeded();
    await row.click({ position: { x: 30, y: 6 } });
    await page.waitForTimeout(300);
  }
  const before = await page.evaluate(([sc, p]) => { const el = (new Function(`return (${sc})`))()(); return { top: Math.round(el.scrollTop), count: document.getElementById('batch-count').textContent.trim(), checked: p.map((id) => !!document.querySelector(`#entry-list > li[data-id="${id}"] input[type=checkbox]`)?.checked) }; }, [scroller.toString(), picks]);
  check(before.top > 0 && /^2 selected/.test(before.count) && before.checked.every(Boolean), 'two ticks, scrolled down the list', before);
  await page.evaluate((id) => { document.querySelector(`#entry-list > li[data-id="${id}"]`).__sweepMark = 1; }, picks[0]);
  // A note saved elsewhere, then the app's own reload and repaint: the path
  // every save event takes into the Notes list.
  const extra = await page.evaluate(async (s) => (await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Select repaint ${s} saved elsewhere` }) })).id, stamp);
  await page.evaluate(async () => { await loadEntries(); renderEntries(); });
  await page.waitForTimeout(1500);
  const repainted = await page.evaluate(([id, x]) => ({ newRow: !!document.querySelector(`#entry-list > li[data-id="${x}"]`), sameNode: !!document.querySelector(`#entry-list > li[data-id="${id}"]`)?.__sweepMark }), [picks[0], extra]);
  check(repainted.newRow && !repainted.sameNode, 'the list was repainted (new row nodes, the new note listed)', repainted);
  const after = await page.evaluate(([sc, p]) => { const el = (new Function(`return (${sc})`))()(); return { top: Math.round(el.scrollTop), count: document.getElementById('batch-count').textContent.trim(), checked: p.map((id) => !!document.querySelector(`#entry-list > li[data-id="${id}"] input[type=checkbox]`)?.checked), selectMode }; }, [scroller.toString(), picks]);
  check(after.selectMode && /^2 selected/.test(after.count) && after.checked.every(Boolean), 'the ticks survive the repaint', after);
  check(Math.abs(after.top - before.top) <= 150, 'the list keeps its scroll place (within one row)', { before: before.top, after: after.top });
  await page.evaluate(async (all) => { for (const id of all) { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); } }, [...ids, extra]).catch(() => {});
  await browser.close();
  console.log(fails.length ? `${fails.length} failed` : 'all passed');
  process.exit(fails.length ? 1 : 0);
})();
