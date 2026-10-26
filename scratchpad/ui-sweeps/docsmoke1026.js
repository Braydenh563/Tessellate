// Never-driven document features, smoke level (docdog-1026 "Not verified"):
// Live/Source/Split switching, outline, version history, templates dialog,
// the bin and wiki-link typeahead, with console and page errors counted and
// each dialog's box checked against the window. THEME=dark for the dark theme.
// BASE=http://127.0.0.1:8797 SCRATCH=<dir> node docsmoke1026.js
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  page.on('pageerror', (e) => errs.push('page: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });
  await openDoc(page, { title: 'Smoke notes', content: '# Smoke notes\n\nSome **bold** text and a [[Other page]] link.\n\n## Part one\n\n- a\n- b\n\n## Part two\n\nMore text.\n' });
  const out = [];
  const step = async (name, fn) => { try { out.push({ name, ...(await fn()) }); } catch (e) { out.push({ name, error: String(e).slice(0, 120) }); } };
  for (const v of ['live', 'source', 'split', 'live']) {
    await step('view ' + v, async () => {
      await page.evaluate((v) => document.querySelector(`[data-doc-view="${v}"]`)?.click(), v);
      await page.waitForTimeout(700);
      return page.evaluate(() => { const c = [...document.querySelectorAll('.cm-content')].find((e) => e.offsetParent); return { editor: !!c, text: c ? c.innerText.slice(0, 20) : null }; });
    });
  }
  await step('outline', async () => page.evaluate(() => ({ rows: document.querySelectorAll('#doc-outline [data-line], #doc-outline button, #doc-outline li').length })));
  await step('history', async () => {
    await page.evaluate(() => openDocHistory());
    await page.waitForTimeout(900);
    const r = await page.evaluate(() => { const d = [...document.querySelectorAll('dialog[open], .modal:not(.hidden)')].pop(); if (!d) return { open: false }; const b = d.getBoundingClientRect(); return { open: true, inside: b.left >= 0 && b.right <= innerWidth && b.top >= 0 && b.bottom <= innerHeight }; });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    return r;
  });
  await step('templates', async () => {
    await page.evaluate(() => openDocTemplateDialog());
    await page.waitForTimeout(900);
    const r = await page.evaluate(() => { const d = [...document.querySelectorAll('dialog[open], .modal:not(.hidden)')].pop(); if (!d) return { open: false }; const b = d.getBoundingClientRect(); return { open: true, inside: b.left >= 0 && b.right <= innerWidth && b.top >= 0 && b.bottom <= innerHeight, tiles: d.querySelectorAll('button').length }; });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    return r;
  });
  await step('wiki link typeahead', async () => {
    await page.click('.cm-content');
    await page.keyboard.press('Control+End');
    await page.keyboard.type('\n[[Sm');
    await page.waitForTimeout(900);
    const r = await page.evaluate(() => ({ menu: !!document.querySelector('.doc-wiki-menu, .editor-menu, [role="listbox"]:not(.hidden)') }));
    await page.keyboard.press('Escape');
    return r;
  });
  await step('delete and restore', async () => {
    const id = await page.evaluate(() => (typeof currentDocId !== 'undefined' ? currentDocId : null));
    return { id };
  });
  for (const o of out) console.log(JSON.stringify(o));
  console.log('errors', errs.length, errs.slice(0, 5));
  await browser.close();
})();
