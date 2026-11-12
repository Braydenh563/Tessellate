// INBOX 309: a whiteboard or a mind map as an object inside a note, and a
// note's own reminders on the note.
//
// The owner, verbatim: "there is also no way to attach a whiteboard or
// mindmap to a note as like an object in the notes. or to link reminders to
// notes". Two halves of one idea, so one sweep: the embed renders as a live
// preview card and opens the board, a board that is gone leaves a tombstone
// rather than vanishing, the "/" menu can insert one, and a note that caused
// reminders says so on the card.
const { boot } = require('./lib.js');

// `W=390 H=780 PHONE=1` runs it as a phone (default 1440x900): the card has to
// fit its note's row, in a chat answer too, and the inline `[[board:ID|label]]`
// chip has to open the board it names.
const W = Number(process.env.W || 0);
const H = Number(process.env.H || 900);
const PHONE = process.env.PHONE === '1';

(async () => {
  const { page, browser } = await boot(W ? { viewport: { width: W, height: H }, hasTouch: PHONE, isMobile: PHONE } : {});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2500);

  // Unique names per run: this sweep runs against whatever notebook the gate
  // has (its own earlier runs included), and two boards called "House jobs"
  // would make the title fallback in `boardEmbedTarget` ambiguous, which is
  // the sweep lying about the code rather than the code being wrong.
  // A board that has been opened has a saved thumbnail, and its preview is then
  // that picture (`mapRaster`, an img.board-minimap) rather than the drawn svg
  // (`mapPreview`); both are a preview, so "svg" below means either.
  const tag = String(Date.now()).slice(-6);
  const ids = await page.evaluate(async (tag) => {
    const post = (path, body) => apiJson(path, { method: 'POST', body: JSON.stringify(body) });
    const board = await post('/whiteboard/boards', { name: `House jobs ${tag}`, type: 'board' });
    const map = await post('/whiteboard/boards', { name: `The house ${tag}`, type: 'map' });
    // Something on each, so the preview has a real layout to draw rather
    // than the empty state: a miniature of nothing proves nothing. Cards on
    // a board and a reference node on a map, the two shapes `refchips.js`
    // already proves the API takes.
    const roof = await post('/entries', { content: `Roof quote ${tag}`, category: 'General' });
    const gutters = await post('/entries', { content: `Gutters ${tag}`, category: 'General' });
    await post('/whiteboard/nodes', { entry_id: roof.id, board_id: board.id, x: 20, y: 30 });
    await post('/whiteboard/nodes', { entry_id: gutters.id, board_id: board.id, x: 260, y: 180 });
    await post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'note', parent_id: null, text: '', ref_id: roof.id });
    const note = await post('/entries', {
      content: `Kitchen plan\n\n![[board:${board.id}|House jobs ${tag}]]\n\n![[map:${map.id}|The house ${tag}]]\n\n![[board:987654|Old plan ${tag}]]\n\nSee [[board:987655|Older plan ${tag}]] as well, and [[board:${board.id}|House jobs ${tag}]].`,
      category: 'General',
    });
    const due = new Date(Date.now() + 86400000).toISOString().slice(0, 19);
    await post('/reminders', { text: 'Ring the roofer', due_at: due, entry_id: note.id });
    await post('/reminders', { text: 'Measure the hall', due_at: due, entry_id: note.id });
    return { board: board.id, map: map.id, note: note.id };
  }, tag);

  const findingsDoc = [];
  await page.evaluate((id) => { window.__noteobjBoard = id; }, ids.board);
  await page.evaluate(() => switchTab('notes'));
  await page.evaluate(() => loadEntries());
  await page.waitForTimeout(1500);
  // Until every card has settled (a preview, or a tombstone), not a fixed wait:
  // each one is filled by a request for the boards index, and on a loaded
  // machine that took longer than three seconds, which read as cards stuck on
  // "loading" (a sweep measuring the load, not the app).
  await page.waitForFunction((id) => {
    const cards = [...document.querySelectorAll(`#entry-list li[data-id="${id}"] .board-embed`)];
    return cards.length > 0 && cards.every((c) => c.querySelector('svg, img.board-minimap') || c.classList.contains('board-embed-gone'));
  }, ids.note, { timeout: 20000 }).catch(() => {});

  const card = await page.evaluate((id) => {
    const li = document.querySelector(`#entry-list li[data-id="${id}"]`);
    if (!li) return null;
    const objects = [...li.querySelectorAll('.board-embed')].map((el) => {
      const r = el.getBoundingClientRect();
      return {
        text: el.textContent.trim().slice(0, 80),
        h: Math.round(r.height),
        w: Math.round(r.width),
        svg: !!el.querySelector('svg, img.board-minimap'),
        gone: el.classList.contains('board-embed-gone'),
        ref: el.dataset.boardRef || '',
      };
    });
    return {
      objects,
      body: li.querySelector('.entry-content')?.textContent.slice(0, 200) || '',
      reminderChip: (() => {
        const chip = li.querySelector('.chip.reminders');
        if (!chip) return null;
        const r = chip.getBoundingClientRect();
        return { text: chip.textContent.trim(), h: Math.round(r.height) };
      })(),
    };
  }, ids.note);
  console.log('card', JSON.stringify(card));

  // Pressing the board object opens that board.
  let opened = null;
  if (card && card.objects.length) {
    await page.click(`#entry-list li[data-id="${ids.note}"] .board-embed:not(.board-embed-gone)`);
    await page.waitForTimeout(1800);
    opened = await page.evaluate(() => window.currentBoardId ?? null);
    console.log('opened', opened, 'wanted', ids.board);
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(1200);
  }

  // The note's reminders, where the card says they are.
  let reminders = null;
  if (card && card.reminderChip) {
    await page.click(`#entry-list li[data-id="${ids.note}"] .chip.reminders`);
    await page.waitForTimeout(1200);
    reminders = await page.evaluate((id) => {
      const li = document.querySelector(`#entry-list li[data-id="${id}"]`);
      const rows = [...li.querySelectorAll('.entry-links .chip')].map((c) => c.textContent.trim());
      return rows;
    }, ids.note);
    console.log('reminders', JSON.stringify(reminders));
  }

  // A dead reference written inline is a dead board, not a name to create:
  // the offer to create "board:987655|Older plan" would make a note nobody
  // wants and leave the link dead anyway.
  let deadLink = null;
  const wiki = await page.$(`#entry-list li[data-id="${ids.note}"] .wiki-link`);
  if (wiki) {
    await wiki.click();
    await page.waitForTimeout(900);
    deadLink = await page.evaluate(() => ({
      label: document.querySelector('.wiki-link')?.textContent.trim() || '',
      // Visible ones only: the page carries a dozen `.modal-overlay`
      // elements in its markup, all `.hidden` until something opens them.
      dialog: [...document.querySelectorAll('.modal-overlay')].some((o) => o.offsetParent),
      toast: (document.querySelector('#toast, .toast')?.textContent || '').trim().slice(0, 80),
    }));
    console.log('deadLink', JSON.stringify(deadLink));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  }

  // The live id-form chip, the same text with a board that exists: it names
  // the board (not its address) and opens it.
  let liveChip = null;
  const chips = await page.$$(`#entry-list li[data-id="${ids.note}"] .entry-content .map-chip`);
  console.log('liveChip candidates', chips.length);
  if (chips.length >= 1) {
    const chip = chips[chips.length - 1];
    const label = (await chip.textContent()).trim();
    await chip.click();
    await page.waitForTimeout(1800);
    liveChip = { label, opened: await page.evaluate(() => window.currentBoardId ?? null) };
    console.log('liveChip', JSON.stringify(liveChip), 'wanted', ids.board);
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(1200);
  }

  // The "/" menu's own doorway. The capture box lives on the Notes tab's
  // Capture sub-tab, which is `display: none` from the list, so a sweep that
  // types into it from the list types into nothing.
  await page.click('#notes-subtabs button[data-section="capture"]');
  await page.waitForTimeout(700);
  await page.click('#entry-content');
  await page.waitForTimeout(900);
  // **Type where the person types.** Focusing the capture box mounts the
  // engine over it (`NOTE_SURFACES` in documents.js), so the textarea is the
  // form's value carrier and no longer the editing surface: typing into it
  // directly diverges from CodeMirror's own document and throws "Selection
  // points outside of document" on the next update. Measured: that error
  // appeared on a fresh notebook and nowhere a user could reach it.
  const composer = (await page.$('.note-surface .cm-content')) ? '.note-surface .cm-content' : '#entry-content';
  // A delay per character on purpose: typed at full speed the menu's own
  // refresh loses a keystroke and the menu shows the unfiltered shortlist,
  // which is a sweep measuring its own typing rather than the app.
  await page.type(composer, '/board', { delay: 60 });
  await page.waitForTimeout(900);
  const menu = await page.evaluate(() => {
    const el = document.getElementById('editor-menu');
    if (!el || el.classList.contains('hidden')) return null;
    return [...el.querySelectorAll('.editor-menu-item')].map((i) => i.textContent.trim()).slice(0, 8);
  });
  console.log('menu', JSON.stringify(menu));

  // The command all the way through: choose a board in the picker it opens
  // and read what landed in the note. A menu row that inserts nothing is the
  // shape this repo keeps meeting.
  let inserted = null;
  if (menu && menu.some((m) => /board|map/i.test(m))) {
    await page.click('#editor-menu .editor-menu-item');
    await page.waitForTimeout(1500);
    const rows = await page.$$('.entry-pick-list .entry-pick-row');
    if (rows.length) {
      await rows[0].click();
      await page.waitForTimeout(800);
      inserted = await page.evaluate(() => document.getElementById('entry-content').value);
    } else {
      inserted = '(the picker offered nothing)';
    }
    console.log('inserted', JSON.stringify(inserted));
  }

  // The other doorway: "add to a note" from the board itself, all the way
  // through to the note's own text.
  await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
  await page.waitForTimeout(2500);
  await page.click('button[aria-controls="wb-board-menu"]').catch(() => {});
  await page.waitForTimeout(600);
  // The row now lives in the Board menu's "Share and save" submenu (INBOX 1627),
  // so the sweep opens that group first; the check on the row itself is unchanged.
  await page.click('#wb-board-menu button:has-text("Share and save")', { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(500);
  const boardSide = await page.evaluate(() => {
    const el = document.getElementById('wb-add-to-note');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { text: el.textContent.trim(), h: Math.round(r.height), w: Math.round(r.width) };
  });
  console.log('boardSide', JSON.stringify(boardSide));

  let addedToNote = null;
  let addBlocked = null;
  if (boardSide && boardSide.h > 0) {
    // A press that cannot land is a finding with the thing that covers the row
    // named, not a thirty-second crash (at 390 it was timing out with the
    // board's own menu "intercepting" the press).
    try {
      await page.click('#wb-add-to-note', { timeout: 8000 });
    } catch {
      addBlocked = await page.evaluate(() => {
        const rows = [...document.querySelectorAll('#wb-add-to-note')];
        const el = rows[0];
        const r = el.getBoundingClientRect();
        const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        const menu = document.getElementById('wb-board-menu');
        const m = menu.getBoundingClientRect();
        return {
          rows: rows.length, row: [r.left, r.top, r.width, r.height].map(Math.round),
          at: at && (at.id || at.className.toString().slice(0, 50) || at.tagName),
          menu: [m.left, m.top, m.width, m.height].map(Math.round), menuHidden: menu.classList.contains('hidden'),
          menuScroll: [menu.scrollTop, menu.scrollHeight, menu.clientHeight], vh: innerHeight, vv: window.visualViewport && Math.round(window.visualViewport.height),
        };
      });
      console.log('addBlocked', JSON.stringify(addBlocked));
    }
  }
  if (boardSide && boardSide.h > 0 && !addBlocked) {
    await page.waitForTimeout(1000);
    await page.fill('.entry-pick-card input', 'Kitchen plan');
    await page.waitForTimeout(600);
    const rows = await page.$$('.entry-pick-list .entry-pick-row');
    if (rows.length) {
      await rows[0].click();
      await page.waitForTimeout(1500);
      addedToNote = await page.evaluate((id) => apiJson(`/entries/${id}`).then((e) => e.content), ids.note);
    }
    console.log('addedToNote', JSON.stringify((addedToNote || '').slice(-60)));
  }

  // The same object in a document, because `mdEmbedElement` is shared by the
  // note renderer and `renderMarkdown`, and "shared" is a claim until it is
  // measured on both.
  const inDocument = await page.evaluate(async (tag) => {
    const doc = await apiJson('/documents', {
      method: 'POST',
      body: JSON.stringify({ title: `House plan ${tag}`, content: `The plan\n\n![[board:${window.__noteobjBoard}|House jobs ${tag}]]\n` }),
    });
    return doc.id;
  }, tag).catch(() => null);
  if (inDocument) {
    await page.evaluate((id) => { switchTab('documents'); setTimeout(() => openDocument(id), 150); }, inDocument);
    await page.waitForTimeout(3000);
    // The rendered view, which is the one `renderMarkdown` draws; Live is the
    // engine's own decorations and has no transclusion of any kind.
    await page.evaluate(() => setDocView('rendered'));
    await page.waitForTimeout(1500);
    const drawn = await page.evaluate(() => {
      const el = document.querySelector('#doc-preview .board-embed');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { h: Math.round(r.height), svg: !!el.querySelector('svg, img.board-minimap'), gone: el.classList.contains('board-embed-gone') };
    });
    console.log('inDocument', JSON.stringify(drawn));
    if (!drawn) findingsDoc.push('the board object did not render in a document');
    else if (drawn.gone || !drawn.svg) findingsDoc.push('the board object in a document: ' + JSON.stringify(drawn));
  }

  // The note's card fits its row, and the same object drawn in a chat answer
  // (`renderMarkdown` shares `mdEmbedElement`; a model could write one) fits
  // the bubble, and its inline id-form chip opens the board it names.
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(1200);
  const inChat = await page.evaluate(async ({ board, tag }) => {
    const bubble = addBubble('assistant', '');
    const body = bubble.querySelector('.msg-body');
    renderMarkdown(body, `Here it is.\n\n![[board:${board}|House jobs ${tag}]]`);
    await new Promise((r) => setTimeout(r, 1500));
    const embed = body.querySelector('.board-embed');
    const room = body.getBoundingClientRect();
    const e = embed && embed.getBoundingClientRect();
    return {
      embed: e && { w: Math.round(e.width), h: Math.round(e.height), svg: !!embed.querySelector('svg, img.board-minimap'), fits: e.left >= room.left - 1 && e.right <= room.right + 1 },
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      bodyW: Math.round(room.width),
    };
  }, { board: ids.board, tag });
  console.log('inChat', JSON.stringify(inChat));
  const phoneFit = card && card.objects.filter((o) => !o.gone).map((o) => o.w);
  console.log('card widths', JSON.stringify(phoneFit), 'viewport', await page.evaluate(() => innerWidth));

  const findings = [...findingsDoc];
  if (!inChat.embed) findings.push('the board object did not render in a chat answer');
  else {
    if (!inChat.embed.svg) findings.push('the board object in a chat answer drew no preview: ' + JSON.stringify(inChat.embed));
    if (!inChat.embed.fits) findings.push('the board object overflows its chat bubble: ' + JSON.stringify(inChat.embed) + ' in ' + inChat.bodyW);
  }
  if (inChat.docOverflow > 0) findings.push('the chat answer made the page scroll sideways by ' + inChat.docOverflow + 'px');
  if (!liveChip) findings.push('the inline [[board:ID|label]] for a live board drew no board chip in the note');
  else {
    if (/board:/.test(liveChip.label)) findings.push('the live inline board chip reads as its address: ' + liveChip.label);
    if (liveChip.opened !== ids.board) findings.push(`the live inline board chip opened ${liveChip.opened}, wanted ${ids.board}`);
  }
  if (card && card.objects.some((o) => !o.gone && o.w > (W || 1e9))) findings.push('a board object in a note is wider than the window: ' + JSON.stringify(phoneFit));
  if (!card) findings.push('the note did not render');
  else {
    const live = card.objects.filter((o) => !o.gone);
    const gone = card.objects.filter((o) => o.gone);
    if (live.length !== 2) findings.push(`wanted 2 live board objects, got ${live.length}: ${JSON.stringify(card.objects)}`);
    for (const o of live) {
      if (!o.svg) findings.push('a board object drew no preview: ' + JSON.stringify(o));
      if (o.h < 60) findings.push('a board object is ' + o.h + 'px tall, too short to be a preview card');
    }
    if (!live.some((o) => /House jobs/.test(o.text))) findings.push('the board object does not name its board');
    if (!live.some((o) => /The house/.test(o.text))) findings.push('the map object does not name its map');
    if (gone.length !== 1) findings.push('a deleted board left no tombstone: ' + JSON.stringify(card.objects));
    else if (!/Old plan/.test(gone[0].text)) findings.push('the tombstone does not say what was there: ' + gone[0].text);
    if (/Nothing called/.test(card.body)) findings.push('an embedded board rendered as "Nothing called ... yet"');
    if (!card.reminderChip) findings.push('the note does not show its reminders');
    else if (!/2 reminders/.test(card.reminderChip.text)) findings.push('reminder chip text: ' + card.reminderChip.text);
  }
  if (card && card.objects.length && opened !== ids.board) findings.push(`pressing the board object opened ${opened}, wanted ${ids.board}`);
  if (reminders && !reminders.some((r) => /Ring the roofer/.test(r))) findings.push('the reminders panel does not list the reminder: ' + JSON.stringify(reminders));
  if (!deadLink) findings.push('the inline board reference drew no link at all');
  else {
    if (deadLink.dialog) findings.push('a dead board reference offered to create a note called after it');
    if (!/no longer in your notebook/.test(deadLink.toast)) findings.push('no word about the missing board: ' + JSON.stringify(deadLink));
    if (/board:/.test(deadLink.label)) findings.push('the inline reference reads as its address: ' + deadLink.label);
  }
  if (!menu) findings.push('the "/" menu did not open on /board');
  else if (!menu.some((m) => /board|map/i.test(m))) findings.push('no board or map command in the "/" menu: ' + JSON.stringify(menu));
  if (inserted !== null && !/!\[\[(board|map):\d+\|/.test(inserted)) findings.push('the "/" command inserted: ' + inserted);
  if (!boardSide) findings.push('no "add to a note" action on the board itself (#wb-add-to-note)');
  else if (!boardSide.h) findings.push('the board\'s "add to a note" row did not open with its menu');
  else if (addBlocked) findings.push('the board\'s "add to a note" row cannot be pressed: ' + JSON.stringify(addBlocked));
  else if (!addedToNote) findings.push('the board\'s "add to a note" reached no note');
  else if (!new RegExp(`!\\[\\[board:${ids.board}\\|`).test(addedToNote)) findings.push('the note did not gain the board object: ' + addedToNote.slice(-80));
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));

  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
