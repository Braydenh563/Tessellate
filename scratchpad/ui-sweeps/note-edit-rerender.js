// Sweep (notes e2e flake, #224): a list render between Edit and the next frame must not lose the
// edit form's caret, or its editor never mounts (notes.spec.js:61 waited 90 s for .cm-content).
const { boot } = require('./lib');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  const id = await page.evaluate(async () => {
    const saved = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'Rerender check: the bike lock code' }) });
    return saved.id ?? saved.entry?.id;
  });
  await page.evaluate(() => revealTab('notes'));
  await page.click('#notes-subtabs [data-section="browse"]');
  await page.evaluate(() => loadEntries());
  await page.waitForSelector(`#entry-list > li[data-id="${id}"]`);
  let fails = 0;
  for (let i = 0; i < 5; i++) {
    // Edit, then a second render in the same task: the refresh that filing sends just after a capture.
    await page.evaluate(async (n) => { await openNoteEditor(n); await new Promise((r) => setTimeout(r, 600)); renderEntries(); }, id);
    await page.waitForTimeout(300);
    const ok = await page.waitForSelector(`#entry-list > li[data-id="${id}"] .cm-content[aria-label="Note text"]`, { timeout: 4000 }).then(() => true, () => false);
    const focused = await page.evaluate(() => !!document.activeElement?.closest?.('.cm-editor'));
    console.log(ok && focused ? 'PASS' : 'FAIL', ` round ${i}: editor mounted ${ok}, caret in it ${focused}`);
    if (!(ok && focused)) fails += 1;
        await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  }
  // What was typed in the form is still there after a redraw, and typing goes on in it.
  await page.evaluate((n) => openNoteEditor(n), id);
  await page.waitForSelector('.cm-editor.cm-focused, #entry-list .cm-content:focus', { timeout: 4000 }).catch(() => {});
  await page.keyboard.press('Control+End');
  await page.keyboard.insertText(' is 2210');
  await page.evaluate(() => renderEntries());
  await page.waitForTimeout(300);
  await page.keyboard.insertText(', not 2201');
  const text = await page.evaluate((n) => document.querySelector(`#entry-list > li[data-id="${n}"] .cm-content`)?.textContent || '', id);
  const kept = /is 2210, not 2201/.test(text);
  console.log(kept ? 'PASS' : 'FAIL', ` typing survives a redraw: "${text.slice(-30)}"`);
  if (!kept) fails += 1;
  console.log(errors.length ? 'FAIL  page errors ' + errors.join(' | ') : 'PASS  no page errors');
  console.log(fails ? `${fails} FAIL` : '6/6 PASS');
  process.exitCode = fails || errors.length ? 1 : 0;
  await browser.close();
})();
