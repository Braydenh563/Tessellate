// UI Phase 11 item 6: Documents on a phone. Read view by default when
// nothing is stored; Edit is the page with the selection bar above the
// keyboard and no formatting strip; the outline is in the sidebar sheet,
// reached from the head's opener. At 1024 the default stays Live Preview.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2000);
  const findings = [];
  await page.evaluate(async () => { localStorage.removeItem('doc-view-mode'); await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'Phone reading', content: '# Phone reading\n\nA paragraph.\n\n## Second\n\nMore.\n\n## Third\n\nEnd.' }) }).catch(() => {}); });
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(3500);
  await page.evaluate(async () => { const docs = await apiJson('/documents'); const d = (docs.items || docs).find((x) => x.title === 'Phone reading'); switchTab('documents'); await openDocument(d.id); });
  await page.waitForTimeout(1500);
  const vis = (sel) => page.evaluate((s) => { const el = document.querySelector(s); if (!el) return null; const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.right > 0; }, sel);
  const read = { view: await page.evaluate(() => typeof docView !== 'undefined' ? docView : null), preview: await vis('#doc-preview'), editor: await vis('.doc-main .cm-editor'), strip: await vis('.doc-toolbar'), bar: await vis('#doc-phone-bar') };
  console.log('read', JSON.stringify(read));
  if (read.view !== 'rendered' || !read.preview || read.editor) findings.push('a phone did not open the document to read: ' + JSON.stringify(read));
  if (read.strip) findings.push('the formatting strip shows on a phone');
  // Edit: the page, with the selection bar above the keyboard.
  await page.click('#doc-view-seg button[data-doc-view-group="edit"]'); await page.waitForTimeout(800);
  const edit = await page.evaluate(() => { const bar = document.getElementById('doc-phone-bar'); const b = bar.getBoundingClientRect(); const buttons = [...bar.querySelectorAll('button')].filter((x) => x.getBoundingClientRect().width > 0); return { view: docView, editor: !!document.querySelector('.doc-main .cm-editor') && document.querySelector('.doc-main .cm-editor').getBoundingClientRect().height > 0, strip: (() => { const s = document.querySelector('.doc-toolbar'); return !!s && s.getBoundingClientRect().height > 0; })(), barShown: b.height > 0, barBottom: Math.round(b.bottom), buttons: buttons.length, minH: Math.min(...buttons.map((x) => Math.round(x.getBoundingClientRect().height))), floor: (() => { const dock = document.getElementById('phone-tab-dock'); const r = dock && dock.getBoundingClientRect(); return r && r.height > 0 ? Math.round(r.top) : window.innerHeight; })() }; });
  console.log('edit', JSON.stringify(edit));
  if (!edit.editor || edit.view === 'rendered') findings.push('Edit did not open the editor');
  if (edit.strip) findings.push('the formatting strip shows while editing on a phone');
  if (!edit.barShown || edit.buttons < 6 || edit.minH < 44 || Math.abs(edit.barBottom - edit.floor) > 1) findings.push('the selection bar is not above the keyboard edge: ' + JSON.stringify(edit));
  // The outline is in the sidebar sheet.
  await page.click('.doc-dock > .dock-nav > button'); await page.waitForTimeout(600);
  // The sheet is the sidebar, whose tabs are the documents list and the
  // outline; the Outline tab is the sheet's own.
  await page.evaluate(() => showDocSidebarSection('outline')); await page.waitForTimeout(400);
  const outline = await page.evaluate(() => { const a = document.getElementById('doc-sidebar'); const sec = document.getElementById('doc-sidebar-outline'); const w = document.getElementById('doc-outline-wrap'); const vis = (el) => !!el && !el.classList.contains('hidden') && el.getBoundingClientRect().height > 0 && el.getBoundingClientRect().right > 0; return { open: a.classList.contains('sidebar-sheet-open'), left: Math.round(a.getBoundingClientRect().left), outlineShown: vis(sec) && vis(w), headings: w ? [...w.querySelectorAll('li, .doc-outline-item, button')].filter((x) => x.getBoundingClientRect().height > 0).length : 0 }; });
  console.log('outline', JSON.stringify(outline));
  if (!outline.open || outline.left !== 0) findings.push('the sidebar sheet did not open');
  if (!outline.outlineShown || outline.headings < 3) findings.push('the outline is not in the sheet: ' + JSON.stringify(outline));
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  // Desktop default stays Live Preview.
  await page.evaluate(() => localStorage.removeItem('doc-view-mode'));
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(3500);
  await page.evaluate(() => switchTab('documents')); await page.waitForTimeout(1200);
  const desk = await page.evaluate(() => (typeof docView !== 'undefined' ? docView : null));
  if (desk !== 'live') findings.push('the desktop default moved: ' + desk);
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
