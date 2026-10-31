// INBOX 1467 sweep: drag to reorder, copy and paste objects, drag anywhere,
// the tray. Reports numbers; run with a seeded data dir (see the header of
// seed-objmove.js, or any notebook with a few notes, documents, boards, maps
// and pictures):
//   BASE=http://127.0.0.1:8799 SCRATCH=/tmp/x PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/objmove.js [reorder|copy|drag|tray]
const { boot } = require('./lib.js');
const PART = process.argv[2] || 'all';
const say = (k, v) => console.log(k.padEnd(44), JSON.stringify(v));

const SURFACES = {
  notes: { tab: async (p) => { await p.evaluate(() => switchTab('notes')); }, unit: '#entry-list > li[data-id]', list: '#entry-list', select: 'note-sort' },
  docs: { tab: async (p) => { await p.evaluate(() => { switchTab('library'); }); await p.waitForTimeout(800); await p.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-docs"]').click()); }, unit: '#library-docs-list > li', list: '#library-docs-list', select: 'library-docs-sort' },
  boards: { tab: async (p) => { await p.evaluate(() => { switchTab('library'); }); await p.waitForTimeout(800); await p.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]').click()); }, unit: '#library-boards-grid > .library-board-card', list: '#library-boards-grid', select: 'library-boards-sort' },
  media: { tab: async (p) => { await p.evaluate(() => { switchTab('library'); }); await p.waitForTimeout(800); await p.evaluate(() => document.querySelector('#library-subtabs [data-media-kind="images"]').click()); }, unit: '#library-images-grid > .library-image-tile', list: '#library-images-grid', select: 'library-media-sort' },
};

async function keys(page, s) {
  return page.evaluate(({ unit }) => [...document.querySelectorAll(unit)].filter((e) => e.offsetParent).map((u) => (u.dataset.obj || u.querySelector('[data-obj]')?.dataset.obj || 'note:' + u.dataset.id)), { unit: s.unit }).then((r) => r);
}
async function center(page, sel, i) {
  return page.evaluate(([sel, i]) => { const r = [...document.querySelectorAll(sel)].filter((e) => e.offsetParent)[i].getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height }; }, [sel, i]);
}
// A real press, hold, move in steps, optional release.
async function drag(page, from, to, { hold = 220, release = true, steps = 14 } = {}) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.waitForTimeout(hold);
  await page.mouse.move(from.x + 8, from.y + 8, { steps: 3 });
  await page.mouse.move(to.x, to.y, { steps });
  await page.waitForTimeout(120);
  if (release) await page.mouse.up();
}
async function sortState(page, s) {
  return page.evaluate((id) => ({ select: document.getElementById(id).value }), s.select);
}

async function reorder(page) {
  for (const [name, s] of Object.entries(SURFACES)) {
    await s.tab(page);
    await page.waitForTimeout(2200);
    const before = await keys(page, s);
    say(`${name}: units`, before.length);
    if (before.length < 3) { say(`${name}: skipped`, 'fewer than 3'); continue; }
    // 1. a drop at the start index: nothing changes
    const a = await center(page, s.unit, 0);
    await drag(page, a, { x: a.x + 3, y: a.y + 2 }, { steps: 4 });
    await page.waitForTimeout(500);
    say(`${name}: same-index drop, order unchanged`, JSON.stringify(await keys(page, s)) === JSON.stringify(before));
    say(`${name}: same-index drop, sort`, (await sortState(page, s)).select);
    // 2. Escape mid-drag: nothing changes, and no gap or ghost left behind
    const b0 = await center(page, s.unit, 0); const b2 = await center(page, s.unit, 2);
    await drag(page, b0, b2, { release: false });
    const mid = await page.evaluate(() => ({ ghost: !!document.querySelector('.obj-ghost'), gap: !!document.querySelector('.obj-gap'), cls: document.documentElement.classList.contains('obj-dragging') }));
    await page.keyboard.press('Escape');
    await page.mouse.up();
    await page.waitForTimeout(400);
    const left = await page.evaluate(() => ({ ghost: !!document.querySelector('.obj-ghost'), gap: !!document.querySelector('.obj-gap'), lifted: document.querySelectorAll('.obj-lifted').length }));
    say(`${name}: mid-drag ghost/gap`, mid);
    say(`${name}: Escape leaves`, left);
    say(`${name}: Escape, order unchanged`, JSON.stringify(await keys(page, s)) === JSON.stringify(before));
    say(`${name}: Escape, sort`, (await sortState(page, s)).select);
    // 3. a drop at a new index: first card to after the third
    const c0 = await center(page, s.unit, 0); const c2 = await center(page, s.unit, 2);
    const horiz = Math.abs(c2.y - c0.y) < 20;
    await drag(page, c0, horiz ? { x: c2.x + c2.w * 0.3, y: c2.y } : { x: c2.x, y: c2.y + c2.h * 0.3 });
    await page.waitForTimeout(900);
    const after = await keys(page, s);
    say(`${name}: before`, before.slice(0, 4));
    say(`${name}: after`, after.slice(0, 4));
    say(`${name}: first card moved to place`, after.indexOf(before[0]) + 1);
    say(`${name}: sort now`, (await sortState(page, s)).select);
    say(`${name}: stored order length`, await page.evaluate((n) => JSON.parse(localStorage.getItem('order-' + n) || '[]').length, name));
    // 4. Undo puts the old order back
    await page.evaluate(() => document.getElementById('status-undo').click());
    await page.waitForTimeout(900);
    say(`${name}: after Undo order restored`, JSON.stringify(await keys(page, s)) === JSON.stringify(before));
    say(`${name}: after Undo sort`, (await sortState(page, s)).select);
    // 5. keyboard: Alt+ArrowDown on a focused card
    await page.evaluate((unit) => { const u = document.querySelectorAll(unit)[0]; const f = u.matches('[tabindex]') ? u : u.querySelector('[tabindex]'); f && f.focus(); }, s.unit);
    await page.keyboard.press('Alt+ArrowDown');
    await page.waitForTimeout(900);
    const kb = await keys(page, s);
    say(`${name}: Alt+ArrowDown moved first card to place`, kb.indexOf(before[0]) + 1);
    say(`${name}: focus stays on the moved card`, await page.evaluate(() => { const a = document.activeElement; const u = a.closest('[data-obj], #entry-list > li[data-id]'); return u ? (u.dataset.obj || 'note:' + u.dataset.id) : ''; }));
    await page.evaluate(() => document.getElementById('status-undo').click());
    await page.waitForTimeout(600);
    // leave the list as it was
    await page.evaluate(([id, n]) => { const el = document.getElementById(id); el.value = el.options[0].value; el.dispatchEvent(new Event('change', { bubbles: true })); localStorage.removeItem('order-' + n); }, [s.select, name]);
  }
}

// Part 3: copy a card, paste it in the chat composer and on a board.
async function focusCard(page, s, i) {
  await page.evaluate(([unit, i]) => {
    const u = [...document.querySelectorAll(unit)].filter((e) => e.offsetParent)[i];
    const stop = u.matches('[tabindex]') ? u : u.querySelector('[tabindex]');
    stop.focus();
  }, [s.unit, i]);
}
async function chatCounts(page) {
  return page.evaluate(() => ({
    notes: attachedNoteIds.length, docs: attachedDocuments.length, boards: typeof attachedBoards !== 'undefined' ? attachedBoards.length : -1,
    cards: document.querySelectorAll('#chat-attachments > *, #chat-doc-attachments > *, #chat-board-attachments > *, #chat-image-attachments > *, #chat-file-attachments > *').length,
  }));
}
async function clipState(page) {
  return page.evaluate(() => (objClip ? { key: objKey(objClip.ref), title: objClip.ref.title, text: objClip.text } : null));
}
async function clearChat(page) {
  await page.evaluate(() => { attachedNoteIds.length = 0; attachedDocuments.length = 0; renderAttachments(); renderDocumentAttachments(); });
}
async function copy(page) {
  const toasts = () => page.evaluate(() => [...document.querySelectorAll('.toast, [role="status"] .toast-message, #toast-region *')].map((e) => e.textContent.trim()).filter(Boolean).slice(-2));
  // a note: focus, Ctrl+C, the toast, then paste into the chat composer
  await SURFACES.notes.tab(page); await page.waitForTimeout(2000);
  await focusCard(page, SURFACES.notes, 1);
  await page.keyboard.press('Control+C');
  await page.waitForTimeout(300);
  say('copy note: in-app clipboard', await clipState(page));
  say('copy note: toast', await toasts());
  await page.evaluate(() => switchTab('chat')); await page.waitForTimeout(900);
  await clearChat(page);
  await page.focus('#chat-input');
  await page.keyboard.press('Control+V');
  await page.waitForTimeout(500);
  say('paste note in chat: staged', await chatCounts(page));
  say('paste note in chat: composer text', await page.inputValue('#chat-input'));
  // a document through the card menu's Copy
  await SURFACES.docs.tab(page); await page.waitForTimeout(2200);
  await page.evaluate(() => { const c = document.querySelector('#library-docs-list > li'); c.querySelector('.kebab-opener').click(); });
  await page.waitForTimeout(300);
  say('card menu rows', await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item, .action-menu-card .menu-item')].map((e) => e.textContent.trim())));
  await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item, .action-menu-card .menu-item')].find((e) => e.textContent.trim() === 'Copy').click());
  await page.waitForTimeout(300);
  say('copy document via menu: in-app clipboard', await clipState(page));
  await page.evaluate(() => switchTab('chat')); await page.waitForTimeout(900);
  await clearChat(page);
  await page.focus('#chat-input');
  await page.keyboard.press('Control+V');
  await page.waitForTimeout(500);
  say('paste document in chat: staged', await chatCounts(page));
  // words copied after the object are an ordinary paste
  await page.fill('#chat-input', 'hello');
  await page.evaluate(() => navigator.clipboard.writeText('plain words').catch(() => {}));
  await clearChat(page);
  // a note on a board: open the board first, then copy a note it does not hold
  await page.evaluate(() => { switchTab('library'); });
  await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]').click());
  await page.waitForTimeout(1500);
  await page.evaluate(() => [...document.querySelectorAll('#library-boards-grid > .library-board-card')].find((c) => (c.dataset.obj || '').startsWith('board:')).click());
  await page.waitForTimeout(2500);
  const held = await page.evaluate(() => wbState.nodes.map((n) => n.entry_id));
  await page.evaluate(async () => { await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'Copy sweep note ' + Date.now(), defer_filing: true }) }); await loadEntries(); });
  await SURFACES.notes.tab(page); await page.waitForTimeout(2000);
  const free = await page.evaluate((held) => [...document.querySelectorAll('#entry-list > li[data-id]')].findIndex((li) => !held.includes(Number(li.dataset.id))), held);
  await focusCard(page, SURFACES.notes, free);
  await page.keyboard.press('Control+C');
  await page.waitForTimeout(300);
  await page.evaluate(() => { switchTab('library'); });
  await page.waitForTimeout(1500);
  const nodes = () => page.evaluate(() => ({ nodes: wbState.nodes.length, objects: wbState.objects ? wbState.objects.length : -1 }));
  const b0 = await nodes();
  await page.mouse.click(700, 500);
  await page.keyboard.press('Control+V');
  await page.waitForTimeout(1500);
  const b1 = await nodes();
  say('paste note on board: items before', b0);
  say('paste note on board: items after', b1);
  // a document on a board: a text box with its link
  await page.evaluate(() => { document.activeElement?.blur(); });
  await page.evaluate(() => objClipPut(objRef('document', 1, 'Pasted doc'), null));
  await page.mouse.click(760, 520);
  await page.keyboard.press('Control+V');
  await page.waitForTimeout(1500);
  say('paste document on board: items after', await nodes());
  await page.keyboard.press('Control+Z');
  await page.waitForTimeout(800);
  say('Ctrl+Z takes the last one back', await nodes());
}

// Parts 4 and 5: carry a card anywhere, and the tray.
async function openTray(page) {
  if (await page.evaluate(() => document.getElementById('obj-tray').classList.contains('hidden'))) { await page.click('#status-tray'); await page.waitForTimeout(500); }
}
async function trayState(page) {
  return page.evaluate(() => ({ held: objTray.length, badge: document.querySelector('#status-tray .status-tray-count').textContent, label: document.getElementById('status-tray').getAttribute('aria-label'), stored: JSON.parse(sessionStorage.getItem('obj-tray') || '[]').length }));
}
async function ghostState(page) {
  return page.evaluate(() => ({ ghost: !!document.querySelector('.obj-ghost'), targets: [...document.querySelectorAll('.obj-target')].map((e) => e.id || e.className.split(' ')[0]), tab: document.querySelector('#tab-bar [aria-selected="true"]')?.dataset.tab }));
}
async function box(page, sel) {
  return page.evaluate((sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel);
}
async function carry(page) {
  const notes = SURFACES.notes;
  await page.evaluate(() => { sessionStorage.removeItem('obj-tray'); objTray = []; objTrayPaint(); attachedNoteIds.length = 0; });
  await notes.tab(page); await page.waitForTimeout(2000);
  // 1. a card dragged to the tray control
  const first = await center(page, notes.unit, 0);
  const tray = await box(page, '#status-tray');
  await drag(page, first, tray, { release: false });
  say('carry to tray: mid-drag', await ghostState(page));
  say('carry to tray: target outline, ghost z-index', await page.evaluate(() => [getComputedStyle(document.getElementById('status-tray')).outlineStyle + ' ' + getComputedStyle(document.getElementById('status-tray')).outlineWidth, getComputedStyle(document.querySelector('.obj-ghost')).zIndex]));
  await page.mouse.up(); await page.waitForTimeout(400);
  say('carry to tray: after drop', await trayState(page));
  say('carry to tray: ghost left behind', await ghostState(page));
  // 2. Escape over a target: nothing happens
  const second = await center(page, notes.unit, 1);
  await drag(page, second, tray, { release: false });
  await page.keyboard.press('Escape'); await page.mouse.up(); await page.waitForTimeout(300);
  say('Escape over the tray: held', (await trayState(page)).held);
  // 3. a drop nowhere
  const third = await center(page, notes.unit, 2);
  await drag(page, third, { x: 700, y: 40 });
  await page.waitForTimeout(300);
  say('drop on nothing: held', (await trayState(page)).held);
  say('drop on nothing: order of the list', await keys(page, notes));
  // 3b. out of the list and back in: carried, then reordering again
  const orderBefore = JSON.stringify(await keys(page, notes));
  const out1 = await center(page, notes.unit, 0); const back = await center(page, notes.unit, 2);
  await page.mouse.move(out1.x, out1.y); await page.mouse.down(); await page.waitForTimeout(220);
  await page.mouse.move(out1.x + 8, out1.y + 8, { steps: 3 });
  await page.mouse.move(tray.x, tray.y, { steps: 10 }); await page.waitForTimeout(120);
  const outState = await page.evaluate(() => ({ gap: !!document.querySelector('.obj-gap'), target: !!document.querySelector('.obj-target') }));
  await page.mouse.move(back.x, back.y, { steps: 12 }); await page.waitForTimeout(150);
  const inState = await page.evaluate(() => ({ gap: !!document.querySelector('.obj-gap'), target: !!document.querySelector('.obj-target') }));
  await page.keyboard.press('Escape'); await page.mouse.up(); await page.waitForTimeout(300);
  say('out of the list: gap/target', outState);
  say('back over the list: gap/target', inState);
  say('Escape after out and back: order, sort', [JSON.stringify(await keys(page, notes)) === orderBefore, (await sortState(page, notes)).select]);
  // 4. hover the Chat tab 500 ms mid-drag, then drop on the composer
  const fourth = await center(page, notes.unit, 3);
  const chatTab = await box(page, '#tab-btn-chat');
  await page.mouse.move(fourth.x, fourth.y); await page.mouse.down(); await page.waitForTimeout(220);
  await page.mouse.move(fourth.x + 8, fourth.y + 8, { steps: 3 });
  await page.mouse.move(chatTab.x, chatTab.y, { steps: 12 });
  await page.waitForTimeout(250);
  say('hover a tab 250 ms: page', (await ghostState(page)).tab);
  await page.waitForTimeout(450);
  say('hover a tab 700 ms: page', (await ghostState(page)).tab);
  const input = await box(page, '#chat-input');
  await page.mouse.move(input.x, input.y, { steps: 10 });
  await page.waitForTimeout(150);
  say('over the composer', await ghostState(page));
  await page.mouse.up(); await page.waitForTimeout(600);
  say('dropped on the composer: staged', await chatCounts(page));
  // 5. the tray survives a page change
  say('tray after the tab change', await trayState(page));
  // 6. open the tray and drag an item onto the reminder form
  await page.evaluate(() => switchTab('reminders')); await page.waitForTimeout(1200);
  await openTray(page);
  say('tray open: rows', await page.evaluate(() => [...document.querySelectorAll('#obj-tray .obj-tray-item')].map((e) => e.dataset.obj)));
  const item = await box(page, '#obj-tray .obj-tray-item .obj-tray-use');
  const field = await box(page, '#reminder-magic');
  await page.fill('#reminder-magic', '');
  await drag(page, item, field);
  await page.waitForTimeout(500);
  say('dropped on the reminder form: text', await page.inputValue('#reminder-magic'));
  say('tray keeps the item after a drag out', (await trayState(page)).held);
  // 7. item remove and clear all
  await page.evaluate(() => { objTrayAdd(objRef('document', 4, 'Second')); objTrayAdd(objRef('board', 7, 'Third')); });
  await openTray(page);
  const before = (await trayState(page)).held;
  await page.click('#obj-tray .obj-tray-item button:not(.obj-tray-use)'); await page.waitForTimeout(300);
  say('remove one: held before/after', [before, (await trayState(page)).held]);
  await page.click('#obj-tray .obj-tray-head button'); await page.waitForTimeout(300);
  say('clear all: held, stored', await trayState(page));
}
async function board(page) {
  // a note from the tray onto an open board's canvas
  await page.evaluate(() => { switchTab('library'); }); await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]').click()); await page.waitForTimeout(1500);
  await page.evaluate(() => [...document.querySelectorAll('#library-boards-grid > .library-board-card')].find((c) => (c.dataset.obj || '').startsWith('board:')).click());
  await page.waitForTimeout(2500);
  //: A new note, which the board cannot hold yet, so the count moves.
  await page.evaluate(async () => { sessionStorage.removeItem('obj-tray'); objTray = []; const made = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'Tray sweep note ' + Date.now(), defer_filing: true }) }); objTrayAdd(objRef('note', made.id, 'Tray note')); objTrayAdd(objRef('document', 4, 'Tray doc')); });
  const counts = () => page.evaluate(() => ({ nodes: wbState.nodes.length, objects: wbState.objects ? wbState.objects.length : -1 }));
  const b0 = await counts();
  await openTray(page);
  const items = await page.evaluate(() => [...document.querySelectorAll('#obj-tray .obj-tray-use')].map((e) => { const r = e.getBoundingClientRect(); return { x: r.left + 40, y: r.top + r.height / 2 }; }));
  const canvas = await box(page, '#whiteboard-container');
  await drag(page, items[0], { x: canvas.x + 80, y: canvas.y + 40 });
  await page.waitForTimeout(1500);
  const b1 = await counts();
  say('drop a note on the board: nodes before/after', [b0.nodes, b1.nodes]);
  await openTray(page);
  const items2 = await page.evaluate(() => [...document.querySelectorAll('#obj-tray .obj-tray-use')].map((e) => { const r = e.getBoundingClientRect(); return { x: r.left + 40, y: r.top + r.height / 2 }; }));
  await drag(page, items2[1], { x: canvas.x - 120, y: canvas.y + 100 });
  await page.waitForTimeout(1500);
  const b2 = await counts();
  say('drop a document on the board: objects before/after', [b1.objects, b2.objects]);
  await page.keyboard.press('Control+Z'); await page.waitForTimeout(600);
  say('Ctrl+Z after the drop', await counts());
  say('Escape mid-drag over the board: items', await (async () => {
    await openTray(page);
    const it = await page.evaluate(() => { const r = document.querySelector('#obj-tray .obj-tray-use').getBoundingClientRect(); return { x: r.left + 40, y: r.top + r.height / 2 }; });
    const had = await counts();
    await drag(page, it, { x: canvas.x, y: canvas.y + 150 }, { release: false });
    await page.keyboard.press('Escape'); await page.mouse.up(); await page.waitForTimeout(500);
    return [had, await counts()];
  })());
  await page.evaluate(() => { objTray = []; objTrayChanged(); });
}

(async () => {
  const { browser, page } = await boot({ permissions: ['clipboard-read', 'clipboard-write'] });
  if (PART === 'all' || PART === 'reorder') await reorder(page);
  if (PART === 'all' || PART === 'copy') await copy(page);
  if (PART === 'all' || PART === 'drag' || PART === 'tray') await carry(page);
  if (PART === 'all' || PART === 'drag' || PART === 'tray') await board(page);
  await browser.close();
})();
