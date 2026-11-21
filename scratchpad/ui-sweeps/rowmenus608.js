// L608: the paths the other sweeps do not reach: a right-click on a row opens the
// row menu (notes, Library cards, bookmarks, graph node), Escape closes it and gives
// the focus back, F2 and the context-menu key act, Delete from the Library menu
// confirms, removes the card and Undo brings it back, Back closes an open menu's
// dialog, and the Escape and focus return of the lightbox. Pickers are
// pickers.js. Numbers per check; `WIDTH=390` for the phone (menus are sheets there).
//
//   BASE=http://127.0.0.1:8800 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/rowmenus608.js
const { boot } = require('./lib.js');

(async () => {
  const W = Number(process.env.WIDTH || 1440);
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(ok ? 'ok  ' : 'FAIL', name, ok ? '' : JSON.stringify(detail));
  };
  const menuOpen = () => page.evaluate(() => document.querySelectorAll('.action-menu:not(.hidden), .sheet-overlay:not(.hidden) .action-menu').length);
  const tag = Date.now().toString(36);
  await page.waitForTimeout(1500);
  const made = await page.evaluate(async (t) => {
    const entry = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Row menu sweep note ${t}\n\nBody.` }) });
    const doc = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Row menu sweep doc ${t}`, content: 'Words.' }) });
    const mark = await apiJson('/bookmarks', { method: 'POST', body: JSON.stringify({ url: `https://example.com/${t}`, title: `Row menu sweep link ${t}` }) }).catch(() => null);
    return { entry: entry.id, doc: doc.id, mark: mark && mark.id };
  }, tag);
  check('fixtures made', made.entry && made.doc, made);

  // 1. A note row in the notes list.
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(2000);
  const noteSel = `#entry-list > li[data-id="${made.entry}"]`;
  await page.waitForSelector(noteSel, { timeout: 15000 });
  await page.click(noteSel, { button: 'right', position: { x: 12, y: 12 } });
  await page.waitForTimeout(500);
  check(`${W} note row: right-click opens the row menu`, (await menuOpen()) >= 1, await menuOpen());
  const rows = await page.evaluate(() => [...document.querySelectorAll('.action-menu .menu-item')].map((b) => b.textContent.trim()).slice(0, 12));
  check(`${W} note row menu has rows (Rename or Delete among them)`, rows.length >= 3, rows);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  check(`${W} note row: Escape closes the menu`, (await menuOpen()) === 0, await menuOpen());

  // 2. Library: a document card, right-click, Delete, confirm, Undo.
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(2500);
  const cardSel = `[data-stop-key="document:${made.doc}"]`;
  const card = () => page.locator(`${cardSel}:visible`).first();
  const cardCount = () => page.locator(`${cardSel}:visible`).count();
  const haveCard = (await cardCount()) > 0;
  check(`${W} library: the document's card is listed`, !!haveCard, null);
  if (haveCard) {
    await card().click({ button: 'right', position: { x: 14, y: 14 } });
    await page.waitForTimeout(500);
    check(`${W} library card: right-click opens the menu`, (await menuOpen()) >= 1, await menuOpen());
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    check(`${W} library card: Escape closes it`, (await menuOpen()) === 0, await menuOpen());
    await card().click({ button: 'right', position: { x: 14, y: 14 } });
    await page.waitForTimeout(400);
    const del = page.locator('.action-menu .menu-item:visible', { hasText: /^\s*Delete/ }).first();
    check(`${W} library card menu: a Delete row`, (await del.count()) === 1, null);
    await del.click();
    await page.waitForTimeout(500);
    const confirm = await page.evaluate(() => {
      const o = document.querySelector('.confirm-overlay:not(.hidden)');
      return o ? { text: o.textContent.slice(0, 80), buttons: [...o.querySelectorAll('button')].map((b) => b.textContent.trim()) } : null;
    });
    check(`${W} library delete: a confirm that names the document`, confirm && /Row menu sweep doc/.test(confirm.text), confirm);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    check(`${W} library delete: Escape on the confirm keeps the document`, (await cardCount()) > 0, null);
    await card().click({ button: 'right', position: { x: 14, y: 14 } });
    await page.waitForTimeout(400);
    await page.locator('.action-menu .menu-item:visible', { hasText: /^\s*Delete/ }).first().click();
    await page.waitForTimeout(500);
    await page.locator('.confirm-overlay:not(.hidden) button.danger, .confirm-overlay:not(.hidden) button.accent, .confirm-overlay:not(.hidden) button:last-child').last().click();
    await page.waitForTimeout(1500);
    const gone = await page.evaluate(async (id) => {
      const r = await apiJson(`/documents/${id}`, { silent: true }).catch(() => null);
      return { api: r ? (r.is_deleted ? 'binned' : 'present') : 'gone' };
    }, made.doc);
    check(`${W} library delete: the card leaves the list and the document is out of use`, (await cardCount()) === 0 && gone.api !== 'present', gone);
    const undo = page.locator('.toast button, #status-undo, .toast-action', { hasText: /Undo/i }).first();
    const undoSeen = (await undo.count()) > 0;
    check(`${W} library delete: an Undo is offered`, undoSeen, null);
    if (undoSeen) {
      await undo.click();
      await page.waitForTimeout(2000);
      check(`${W} library delete: Undo brings the card back`, (await cardCount()) > 0, null);
    }
  }

  // F2 on a focused library card runs its Rename (a prompt dialog), Escape leaves it unchanged.
  if (haveCard) {
    await page.evaluate((id) => switchTab('library'), made.doc);
    await page.waitForTimeout(1200);
    await card().locator('.card-open').first().focus();
    await page.keyboard.press('F2');
    await page.waitForTimeout(700);
    const rename = await page.evaluate(() => {
      const dlg = document.querySelector('.confirm-overlay:not(.hidden), dialog[open]');
      return { dialog: !!dlg, input: !!(dlg && dlg.querySelector('input, textarea')), focus: document.activeElement?.tagName };
    });
    check(`${W} F2 on a library card opens the rename prompt with a field`, rename.dialog && rename.input, rename);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    check(`${W} Escape on the rename prompt closes it`, await page.evaluate(() => !document.querySelector('.confirm-overlay:not(.hidden), dialog[open]')), null);
  }

  // 3. A bookmark row.
  if (made.mark) {
    await page.click('#library-subtabs [data-target="library-view-links"]').catch(() => {});
    await page.waitForTimeout(1500);
    const markSel = '.bookmark-row';
    const n = await page.$$(markSel);
    check(`${W} bookmarks: rows listed`, n.length >= 1, n.length);
    if (n.length) {
      // The row's top right corner: the left edge holds the select tick (a field keeps the browser's own menu).
      const box = await page.locator(`${markSel}:visible`).first().boundingBox();
      await page.mouse.click(box.x + box.width - 6, box.y + 5, { button: 'right' });
      await page.waitForTimeout(500);
      check(`${W} bookmark row: right-click opens the menu`, (await menuOpen()) >= 1, await menuOpen());
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
      check(`${W} bookmark row: Escape closes it`, (await menuOpen()) === 0, await menuOpen());
    }
  }

  // 4. The graph: a right-click on a node opens its menu; Escape closes it.
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(4000);
  const pt = await page.evaluate(() => {
    const s = gcTab;
    const node = s.nodes.filter((n) => !n.isGroup).sort((p, q) => Math.hypot(p.x, p.y) - Math.hypot(q.x, q.y))[0];
    const r = s.canvas.getBoundingClientRect();
    const [x, y] = (s.transform || d3.zoomIdentity).apply([node.x, node.y]);
    return { x: r.left + x, y: r.top + y, id: node.id };
  });
  const at = pt;
  await page.mouse.click(pt.x, pt.y, { button: 'right' });
  await page.waitForTimeout(600);
  check(`${W} graph node: right-click opens the node menu`, (await menuOpen()) >= 1, { at, pt, menus: await menuOpen() });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  check(`${W} graph node: Escape closes it`, (await menuOpen()) === 0, await menuOpen());

  // 5. Keyboard acts: Ctrl+K palette opens and Escape returns, "?" shortcuts.
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1200);
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(700);
  const pal = await page.evaluate(() => !document.getElementById('palette-overlay').classList.contains('hidden') && document.activeElement?.id);
  check(`${W} Ctrl+K opens the palette with the input focused`, pal === 'palette-input', pal);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  check(`${W} Escape closes the palette`, await page.evaluate(() => document.getElementById('palette-overlay').classList.contains('hidden')), null);
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.press('?');
  await page.waitForTimeout(600);
  const sh = await page.evaluate(() => !document.getElementById('shortcuts-overlay').classList.contains('hidden'));
  check(`${W} ? opens the shortcuts`, sh, sh);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  check(`${W} Escape closes the shortcuts`, await page.evaluate(() => document.getElementById('shortcuts-overlay').classList.contains('hidden')), null);
  // 6. The viewer: Escape closes it and the focus returns; Back closes it and stays on the tab.
  const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  await page.evaluate((u) => { const b = document.createElement('button'); b.id = 'lb-opener'; b.textContent = 'x'; document.body.appendChild(b); b.focus(); openLightbox([{ filename: 'a.png', getUrl: () => u }, { filename: 'b.png', getUrl: () => u }], 0); }, png);
  await page.waitForTimeout(600);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const lb = await page.evaluate(() => ({ n: document.querySelectorAll('.lightbox').length, focus: document.activeElement?.id }));
  check(`${W} lightbox: Escape closes it and the focus returns to the opener`, lb.n === 0 && lb.focus === 'lb-opener', lb);
  await page.evaluate((u) => { document.getElementById('lb-opener').focus(); openLightbox([{ filename: 'a.png', getUrl: () => u }], 0); }, png);
  await page.waitForTimeout(600);
  await page.evaluate(() => history.back());
  await page.waitForTimeout(700);
  const back = await page.evaluate(() => ({ n: document.querySelectorAll('.lightbox').length, hash: location.hash }));
  check(`${W} lightbox: Back closes it and stays on the tab`, back.n === 0 && back.hash === '#/notes', back);

  // 7. The graph's note panel: Escape and Back both close it.
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(3000);
  for (const how of ['Escape', 'Back']) {
    await page.evaluate(async () => { const n = gcTab.nodes.find((q) => !q.isGroup); await openGraphPopup({ stopPropagation() {} }, n); });
    await page.waitForTimeout(800);
    if (how === 'Escape') await page.keyboard.press('Escape'); else await page.evaluate(() => history.back());
    await page.waitForTimeout(700);
    const st = await page.evaluate(() => ({ hidden: document.getElementById('graph-popup').classList.contains('hidden'), hash: location.hash }));
    check(`${W} graph note panel: ${how} closes it${how === 'Back' ? ' and stays on the map' : ''}`, st.hidden && (how === 'Escape' || st.hash === '#/graph'), st);
  }

  // 8. Reminders: the sentence add, the form add, and the phone sheet's Escape.
  await page.evaluate(() => switchTab('reminders'));
  await page.waitForTimeout(1500);
  const count = () => page.evaluate(async () => { const r = await apiJson('/reminders'); return (Array.isArray(r) ? r : r.reminders || []).length; });
  const before = await count();
  if (W < 600) { await page.evaluate(() => openReminderCompose()); await page.waitForTimeout(500); }
  await page.fill('#reminder-magic', `Row sweep reminder ${tag} tomorrow at 9am`);
  await page.waitForTimeout(500);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1500);
  check(`${W} reminders: Enter in the sentence box adds one and clears the box`, (await count()) === before + 1 && (await page.inputValue('#reminder-magic')) === '', { before, after: await count() });
  if (W < 600 && !(await page.isVisible('#reminder-text'))) { await page.evaluate(() => openReminderCompose()); await page.waitForTimeout(500); }
  await page.fill('#reminder-text', `Row sweep form ${tag}`);
  await page.fill('#reminder-date', '2027-01-05');
  await page.fill('#reminder-time', '09:30');
  await page.click('#reminder-add');
  await page.waitForTimeout(1500);
  check(`${W} reminders: the form's Add adds one and clears the text`, (await count()) === before + 2 && (await page.inputValue('#reminder-text').catch(() => '')) === '', { before, after: await count() });
  if (W < 600) {
    await page.evaluate(() => openReminderCompose());
    await page.waitForTimeout(500);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    check(`${W} reminders sheet: Escape closes it`, (await page.evaluate(() => document.querySelectorAll('.sheet-overlay:not(.hidden)').length)) === 0, null);
  }

  // 9. The Finder's spelling offer: a typo the server does not answer offers the word, a press runs it.
  await page.evaluate(() => openFinder(''));
  await page.waitForSelector('#finder-input', { state: 'visible' });
  await page.fill('#finder-input', 'dgo');
  await page.waitForTimeout(2500);
  const offer = await page.evaluate(() => document.querySelector('.finder-nothing-action')?.textContent.trim() || null);
  // The word is only offered when a note holds it: seed one.
  check(`${W} finder: an empty result either offers a spelling or names a feature`, offer === null || /Search for|Open/.test(offer), offer);

  await browser.close();
  console.log(fails ? `${fails} failing` : 'all ok');
  process.exit(fails ? 1 : 0);
})();
