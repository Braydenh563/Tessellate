// The picker dialogs (INBOX 548, redesigned for INBOX 572): `pickLibraryItemDialog`
// (the map's "Point a new node at…"), `pickEntryDialog`, `pickNotesDialog` and
// `pickMediaDialog` on one shell, `pickerDialog` in selection.js. At 1440 and
// 390 (THEME=dark for dark) asserts, per dialog:
//   - the dialog head (a 16px title, the X last), the `.search-field` well
//     (its focus ring 1px over the accent edge, the one 2px ring), one filled
//     button at most, the card inside the window, no page overflow;
//   - rows with a FULL list (25 notes: the owner's report only showed once the
//     list overflowed and every row shrank): one row height, no tile
//     intersecting another row, every tile centred in its row within 1px, no
//     text overflowing (a title may only be clipped by its ellipsis);
//   - the sources: a track the card's width, equal segments of one height,
//     the chosen one filled, a count on each, no label clipped; the arrows,
//     Home and End walk them, and the chosen source is remembered;
//   - type icons: a bookmark by what it points at, a file by its type;
//   - one dialog height whatever the filter (a match, none, cleared);
//   - the keys: Down lights the next row, Enter takes it, Escape closes and
//     gives the focus back;
//   - several notes: the Attach picker's rows, one height, the foot on one
//     row, the button off until a tick.
//
//   BASE=http://127.0.0.1:8810 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/pickers.js
const { boot, openBoardsTab } = require('./lib.js');

(async () => {
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(ok ? 'ok  ' : 'FAIL', name, ok ? '' : JSON.stringify(detail));
  };
  const theme = process.env.THEME || 'light';
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const w = viewport.width;
    const { browser, page, OUT } = await boot({ viewport });
    await page.evaluate(async () => {
      try { localStorage.removeItem('libraryPickSource'); } catch (e) { /* none */ }
      const have = (allEntries || []).filter((e) => !e.is_draft && !e.is_deleted).length;
      const titles = ['Picker sweep: a fairly long note title that should ellipsise inside its row, well past the right edge of the dialog', 'Picker sweep two'];
      for (let i = have; i < 25; i += 1) {
        const t = titles[i] || `Picker sweep note ${i}`;
        await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `${t}\n\nBody.` }) }).catch(() => 0);
      }
      const docs = await apiJson('/documents').catch(() => []);
      if (!(Array.isArray(docs) ? docs : docs.documents || []).length) {
        await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'Picker sweep document', content: 'Words.' }) }).catch(() => 0);
      }
      const links = await apiJson('/bookmarks').catch(() => []);
      if (!links.length) {
        await apiJson('/bookmarks', { method: 'POST', body: JSON.stringify({ url: 'https://www.youtube.com/watch?v=x', title: 'A video' }) }).catch(() => 0);
        await apiJson('/bookmarks', { method: 'POST', body: JSON.stringify({ url: 'https://github.com/a/b', title: 'A repository' }) }).catch(() => 0);
      }
      const files = await apiJson('/files/gallery').catch(() => []);
      if (!files.length) {
        const host = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'Picker sweep file holder' }) }).catch(() => null);
        if (host) {
          const fd = new FormData();
          fd.append('file', new Blob(['%PDF-1.4\n%%EOF'], { type: 'application/pdf' }), 'sweep-report.pdf');
          await fetch(`/entries/${host.id}/files`, { method: 'POST', headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() }, body: fd }).catch(() => 0);
        }
      }
      if (typeof loadEntries === 'function') await loadEntries();
    });
    await page.waitForTimeout(800);
    const measure = () => page.evaluate(() => {
      const card = document.querySelector('.confirm-overlay .entry-pick-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      const title = card.querySelector('.dialog-head-title');
      const btns = [...card.querySelector('.dialog-head-actions').children];
      const rows = [...card.querySelectorAll('.entry-pick-row, .note-picker-row')];
      const list = card.querySelector('.entry-pick-list, .media-pick-grid');
      const lr = list && list.getBoundingClientRect();
      const boxes = rows.map((row) => row.getBoundingClientRect());
      // Only rows in the list's window: one scrolled out is not drawn.
      const shown = rows.map((row, i) => ({ row, box: boxes[i] })).filter(({ box }) => lr && box.bottom > lr.top && box.top < lr.bottom);
      const tileOf = (row) => row.querySelector('.rich-picker-tile, .note-picker-tile, .note-picker-thumb');
      // A text box overflows when its text is wider than it and it is not
      // clipped with an ellipsis (an ellipsis is the clip, not an overflow).
      const spills = (el) => el.scrollWidth > el.clientWidth + 1 && !(getComputedStyle(el).textOverflow === 'ellipsis' && getComputedStyle(el).overflow.includes('hidden'));
      const seg = card.querySelector('.picker-kinds');
      const segs = seg ? [...seg.children] : [];
      const active = seg && seg.querySelector('.active');
      // INBOX 715: a tab strip; the chosen tab is the one in ink (the others muted), so 'filled' is a colour difference.
      const clear = (c) => !c || c === 'transparent' || c === 'rgba(0, 0, 0, 0)';
      const field = card.querySelector('.search-field');
      const fs = field && getComputedStyle(field);
      return {
        inside: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
        width: Math.round(r.width),
        cardH: Math.round(r.height),
        titleSize: title && getComputedStyle(title).fontSize,
        lastIsClose: btns[btns.length - 1]?.getAttribute('aria-label') === 'Close',
        field: !!card.querySelector('.search-field > .search-field-input'),
        ring: fs && document.activeElement?.closest('.search-field') === field ? `${fs.outlineWidth} ${fs.borderTopWidth}` : null,
        filled: card.querySelectorAll('button.accent:not(.ghost)').length,
        rows: rows.length,
        heights: [...new Set(rows.map((row) => Math.round(row.getBoundingClientRect().height)))],
        overflow: rows.filter((row) => row.scrollWidth > row.clientWidth + 1).length,
        textSpill: [...card.querySelectorAll('.rich-picker-label, .rich-picker-about, .note-picker-name, .note-picker-meta, .dialog-head-title')].filter(spills).length,
        // A tile drawn over any other row (the owner's screenshot).
        tileHits: shown.filter(({ row }) => {
          const t = tileOf(row)?.getBoundingClientRect();
          return t && shown.some(({ row: other, box }) => other !== row && t.bottom > box.top + 0.5 && t.top < box.bottom - 0.5);
        }).length,
        offCentre: Math.max(0, ...shown.map(({ row, box }) => {
          const t = tileOf(row)?.getBoundingClientRect();
          return t ? Math.abs((t.top + t.bottom) / 2 - (box.top + box.bottom) / 2) : 0;
        })),
        stacked: rows.filter((row) => {
          const tile = row.querySelector('.rich-picker-tile')?.getBoundingClientRect();
          const text = row.querySelector('.rich-picker-text, .note-picker-lines')?.getBoundingClientRect();
          return tile && text && text.left < tile.right;
        }).length,
        footRows: new Set([...card.querySelectorAll('.space-dialog-actions button')].map((b) => Math.round(b.getBoundingClientRect().top))).size,
        tiles: [...new Set(rows.map((row) => Math.round(row.querySelector('.rich-picker-tile')?.getBoundingClientRect().width || 0)))],
        abouts: rows.filter((row) => row.querySelector('.rich-picker-about, .note-picker-meta')?.textContent.trim()).length,
        icons: rows.map((row) => (row.querySelector('.rich-picker-tile i')?.className || '').replace(/^ph ph-/, '')),
        listH: lr && Math.round(lr.height),
        seg: seg && {
          span: Math.round(seg.getBoundingClientRect().width) >= Math.round(card.clientWidth - 2 * parseFloat(getComputedStyle(card).paddingLeft)) - 1,
          heights: [...new Set(segs.map((b) => Math.round(b.getBoundingClientRect().height)))],
          widths: segs.map((b) => b.getBoundingClientRect().width),
          clipped: segs.filter((b) => [...b.children].some((c) => c.scrollWidth > c.clientWidth + 1) || b.scrollWidth > b.clientWidth + 1).length,
          counts: segs.map((b) => b.querySelector('.seg-count')?.textContent || ''),
          filled: !!active && segs.filter((b) => b !== active).every((b) => getComputedStyle(b).color !== getComputedStyle(active).color),
          active: active?.dataset.pickKind,
        },
        state: list?.querySelector('.empty-state') ? {
          icon: !!list.querySelector('.empty-state .empty-icon'),
          title: list.querySelector('.empty-state .empty-title')?.textContent || '',
        } : null,
        scrollbar: list && getComputedStyle(list).scrollbarWidth,
        gutter: list && list.offsetWidth - list.clientWidth,
        pageOverflow: document.documentElement.scrollWidth - innerWidth,
        active: document.activeElement?.className,
      };
    });
    const rowsOk = (m) => m && m.heights.length === 1 && m.tileHits === 0 && m.offCentre <= 1 && m.overflow === 0 && m.textSpill === 0 && m.stacked === 0;
    const open = (expr) => page.evaluate((e) => { window.__pick = 'pending'; (0, eval)(e).then((v) => (window.__pick = v)); }, expr);

    // 1. The map's picker, the one the owner pointed at.
    await open("pickLibraryItemDialog('Point a new node at…')");
    await page.waitForTimeout(1200);
    let m = await measure();
    check(`${w} ${theme} library picker: head, field, X last, inside`, m && m.titleSize === '16px' && m.lastIsClose && m.field && m.inside && m.pageOverflow === 0, m);
    check(`${w} ${theme} library picker: the field's ring is the one 2px ring (1px outline on the accent edge)`, m && m.ring === '1px 1px', m && m.ring);
    check(`${w} ${theme} library picker: a full list (25 notes), one row height, no tile over another row, tiles centred, no text spilling`, m && m.rows >= 25 && m.tiles[0] === 32 && m.abouts === m.rows && rowsOk(m), m);
    check(`${w} ${theme} library picker: the sources span the card, tabs of one height, the chosen one filled, counted, none clipped`,
      m && m.seg && m.seg.span && m.seg.heights.length === 1 && m.seg.filled && m.seg.clipped === 0 && m.seg.counts.every((c) => /^\d+$/.test(c)), m && m.seg);
    check(`${w} ${theme} library picker: the list scrolls on the thin scrollbar`, m && m.scrollbar === 'auto' && (!process.env.SCROLLBARS || m.gutter === 10), { scrollbar: m && m.scrollbar, gutter: m && m.gutter });
    await page.screenshot({ path: `${OUT}/picker-library-${w}-${theme}.png` });
    const cardHs = [m.cardH];
    const listHs = [m.listH];
    for (const kind of ['document', 'file', 'link']) {
      await page.click(`.entry-pick-card [data-pick-kind="${kind}"]`);
      await page.waitForTimeout(500);
      const k = await measure();
      listHs.push(k.listH);
      cardHs.push(k.cardH);
      check(`${w} ${theme} library picker (${kind}): rows hold, segments filled on the chosen one`, k.rows >= 1 && rowsOk(k) && k.seg.active === kind && k.seg.filled, k);
      if (kind === 'link') check(`${w} ${theme} library picker: a bookmark's tile says what it points at`, k.icons.includes('play-circle') && k.icons.includes('code'), k.icons);
      if (kind === 'file') check(`${w} ${theme} library picker: a file's tile is its type`, k.icons.includes('file-pdf'), k.icons);
      await page.screenshot({ path: `${OUT}/picker-library-${kind}-${w}-${theme}.png` });
    }
    check(`${w} ${theme} library picker: one list and card height on every tab`, new Set(listHs).size === 1 && new Set(cardHs).size === 1, { listHs, cardHs });
    // The filter never moves the dialog: a match, no match (the empty state), cleared.
    await page.click('.entry-pick-card [data-pick-kind="note"]');
    await page.focus('.entry-pick-card .search-field-input');
    const filterHs = [(await measure()).cardH];
    await page.keyboard.type('sweep two');
    await page.waitForTimeout(300);
    filterHs.push((await measure()).cardH);
    await page.keyboard.type('zzqx');
    await page.waitForTimeout(300);
    const none = await measure();
    filterHs.push(none.cardH);
    await page.screenshot({ path: `${OUT}/picker-library-empty-${w}-${theme}.png` });
    check(`${w} ${theme} library picker: nothing matching is the empty state (icon, title), and the counts follow the words`, none.state && none.state.icon && /No notes match/.test(none.state.title) && none.seg.counts[0] === '0', { state: none.state, counts: none.seg.counts });
    await page.fill('.entry-pick-card .search-field-input', '');
    await page.waitForTimeout(300);
    filterHs.push((await measure()).cardH);
    check(`${w} ${theme} library picker: one dialog height while filtering`, new Set(filterHs).size === 1, filterHs);
    await page.focus('.entry-pick-card [data-pick-kind="note"]');
    await page.keyboard.press('End');
    const end = await page.evaluate(() => document.activeElement?.dataset.pickKind);
    await page.keyboard.press('ArrowRight');
    const wrap = await page.evaluate(() => document.activeElement?.dataset.pickKind);
    await page.keyboard.press('ArrowLeft');
    const back = await page.evaluate(() => document.activeElement?.dataset.pickKind);
    check(`${w} ${theme} library picker: End, the arrows (wrapping) walk the tabs`, end === 'link' && wrap === 'note' && back === 'link', { end, wrap, back });
    // Remembered: closed on Bookmarks, it opens on Bookmarks.
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    await open("pickLibraryItemDialog('Point a new node at…')");
    await page.waitForTimeout(600);
    const again = await measure();
    check(`${w} ${theme} library picker: the source is remembered`, again.seg.active === 'link', again.seg.active);
    await page.click('.entry-pick-card [data-pick-kind="note"]');
    await page.waitForTimeout(200);
    await page.focus('.entry-pick-card .search-field-input');
    const lit0 = await page.evaluate(() => document.activeElement.getAttribute('aria-activedescendant'));
    await page.keyboard.press('ArrowDown');
    const lit1 = await page.evaluate(() => document.activeElement.getAttribute('aria-activedescendant'));
    const ring = await page.evaluate(() => getComputedStyle(document.querySelector('.entry-pick-row.active')).boxShadow);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
    const picked = await page.evaluate(() => ({ v: window.__pick && window.__pick.kind, open: !!document.querySelector('.entry-pick-card') }));
    check(`${w} ${theme} library picker: Down lights the next row (edged), Enter takes it`, lit0 && lit1 && lit0 !== lit1 && ring !== 'none' && picked.v === 'note' && !picked.open, { lit0, lit1, ring, picked });

    // 2. One note.
    await open("pickEntryDialog('Add this to which note?')");
    await page.waitForTimeout(500);
    m = await measure();
    check(`${w} ${theme} note picker: the same shell and rows, a full list holding`, m && m.titleSize === '16px' && m.lastIsClose && m.field && m.rows >= 25 && m.tiles[0] === 32 && rowsOk(m) && m.inside, m);
    await page.screenshot({ path: `${OUT}/picker-entry-${w}-${theme}.png` });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const esc = await page.evaluate(() => ({ v: window.__pick, open: !!document.querySelector('.entry-pick-card') }));
    check(`${w} ${theme} note picker: Escape closes with nothing`, esc.v === null && !esc.open, esc);

    // 3. Several notes. `pickNotesDialog` lives in the whiteboard bundle, so
    // the bundle is loaded first (OPEN 843: "pickNotesDialog is not defined").
    if (await page.evaluate(() => typeof pickNotesDialog !== 'function')) await openBoardsTab(page, ['pickNotesDialog']);
    await open("pickNotesDialog('Make a map of these notes', { confirmLabel: 'Propose a map' })");
    await page.waitForTimeout(500);
    m = await measure();
    const off = await page.evaluate(() => [...document.querySelectorAll('.entry-pick-card .space-dialog-actions button')].find((b) => /Propose/.test(b.textContent))?.disabled);
    check(`${w} ${theme} notes picker: Attach rows (a full list holding), one filled button, off until a tick`, m && m.rows >= 25 && m.filled === 1 && off === true && rowsOk(m) && m.footRows === 1 && m.inside, { m, off });
    await page.focus('.entry-pick-card .search-field-input');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Space');
    const on = await page.evaluate(() => [...document.querySelectorAll('.entry-pick-card .space-dialog-actions button')].find((b) => /Propose/.test(b.textContent))?.disabled);
    await page.screenshot({ path: `${OUT}/picker-notes-${w}-${theme}.png` });
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
    const many = await page.evaluate(() => window.__pick);
    check(`${w} ${theme} notes picker: Down, Space ticks, Enter confirms`, on === false && Array.isArray(many) && many.length === 1, { on, many });

    // 4. Pictures.
    await open('pickMediaDialog()');
    await page.waitForTimeout(800);
    m = await measure();
    check(`${w} ${theme} media picker: the same shell, its state on the recipe`, m && m.titleSize === '16px' && m.lastIsClose && m.field && m.inside && (m.state === null || m.state.icon), m);
    await page.screenshot({ path: `${OUT}/picker-media-${w}-${theme}.png` });
    await page.click('.entry-pick-card .dialog-head-actions button[aria-label="Close"]');
    await page.waitForTimeout(200);
    check(`${w} ${theme} media picker: the X closes`, await page.evaluate(() => window.__pick === null && !document.querySelector('.entry-pick-card')), null);
    await browser.close();
  }
  console.log(fails ? `${fails} failing` : 'all ok');
  process.exit(fails ? 1 : 0);
})();
