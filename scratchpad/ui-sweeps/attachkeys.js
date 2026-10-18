// The Attach panel redesign (INBOX 485): one height for every source, one
// search field, the keys (arrows, Space, Enter, Escape, the tabs' arrows, the
// image grid's columns), and at 390 a full-width sheet with 44px targets.
// Needs a notebook with notes, files and at least five images (seed them
// first). Prints PASS/FAIL lines.
const { boot } = require('./lib.js');
const ok = (name, pass, detail) => console.log(`${pass ? 'PASS' : 'FAIL'} ${name}${detail ? ' ' + JSON.stringify(detail) : ''}`);
const focused = (page) => page.evaluate(() => {
  const a = document.activeElement;
  const boxes = [...document.querySelectorAll('#note-picker-list .note-picker-box')];
  return { id: a.id, box: boxes.indexOf(a), tab: a.dataset?.pickerSource || null };
});
(async () => {
  {
    const { browser, page } = await boot();
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(1000);
    await page.click('#attach-note');
    await page.waitForTimeout(600);
    const heights = [];
    for (const src of ['notes', 'documents', 'files', 'images', 'maps']) {
      await page.click(`#note-picker-sources [data-picker-source="${src}"]`);
      await page.waitForTimeout(600);
      heights.push(await page.evaluate(() => {
        const p = document.getElementById('note-picker-panel');
        const inputs = [...p.querySelectorAll('input:not([type=checkbox])')].filter((i) => i.offsetParent).length;
        return [Math.round(p.getBoundingClientRect().height), inputs];
      }));
    }
    ok('one panel height and one search field on every source', new Set(heights.map((h) => h[0])).size === 1 && heights.every((h) => h[1] === 1), heights);

    await page.click('#note-picker-sources [data-picker-source="notes"]');
    await page.waitForTimeout(300);
    await page.keyboard.press('ArrowDown');
    let f = await focused(page);
    ok('ArrowDown from the field enters the list', f.box === 0, f);
    // The overlapping textbox (INBOX 485): unfocused, the input drew its own
    // bordered box over the well. One box means the input has no border and
    // sits inside the well.
    const field = await page.evaluate(() => {
      const i = document.getElementById('note-picker-search');
      const w = i.parentElement.getBoundingClientRect(); const b = i.getBoundingClientRect();
      return { border: getComputedStyle(i).borderTopWidth, inside: b.top >= w.top && b.bottom <= w.bottom };
    });
    ok('the unfocused search is one box', field.border === '0px' && field.inside, field);
    await page.keyboard.press('ArrowDown');
    f = await focused(page);
    ok('ArrowDown walks to the next row', f.box === 1, f);
    const before = await page.evaluate(() => attachedNoteIds.length);
    await page.keyboard.press(' ');
    const after = await page.evaluate(() => attachedNoteIds.length);
    ok('Space ticks the row', after === before + 1 || after === before - 1, { before, after });
    await page.waitForTimeout(400);
    const tickedFill = await page.evaluate(() => getComputedStyle(document.activeElement.closest('label')).backgroundColor);
    ok('a ticked row is filled', tickedFill !== 'rgba(0, 0, 0, 0)', tickedFill);
    await page.keyboard.press('ArrowUp');
    await page.keyboard.press('ArrowUp');
    f = await focused(page);
    ok('ArrowUp from the first row returns to the field', f.id === 'note-picker-search', f);
    const tabStops = await page.evaluate(() => [...document.querySelectorAll('#note-picker-list .note-picker-box')].filter((b) => b.tabIndex === 0).length);
    ok('the list is one tab stop', tabStops === 1, tabStops);

    await page.focus('#note-picker-sources [data-picker-source="notes"]');
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(500);
    f = await focused(page);
    ok('ArrowRight on a tab moves to the next source', f.tab === 'documents', f);

    await page.click('#note-picker-sources [data-picker-source="images"]');
    await page.waitForTimeout(800);
    const cols = await page.evaluate(() => notePickerColumns(document.getElementById('note-picker-list')));
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowRight');
    f = await focused(page);
    ok('ArrowRight in the image grid moves one picture', f.box === 1, f);
    await page.keyboard.press('ArrowDown');
    f = await focused(page);
    ok('ArrowDown in the image grid moves one row of pictures', f.box === 1 + cols || f.box === -1, { ...f, cols });
    const grid = await page.evaluate(() => getComputedStyle(document.getElementById('note-picker-list')).display);
    ok('images are a grid', grid === 'grid' && cols > 1, { grid, cols });

    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
    const closed = await page.evaluate(() => document.getElementById('note-picker-panel').classList.contains('hidden'));
    ok('Enter on a row ticks it and keeps the panel open (C09)', !closed);
    await page.focus('#note-picker-search');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
    ok('Enter in the search field is Done', await page.evaluate(() => document.getElementById('note-picker-panel').classList.contains('hidden')));
    await page.click('#attach-note');
    await page.waitForTimeout(400);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    const esc = await page.evaluate(() => document.getElementById('note-picker-panel').classList.contains('hidden'));
    ok('Escape closes', esc);

    await page.click('#attach-note');
    await page.waitForTimeout(400);
    await page.fill('#note-picker-search', 'zzzqqq');
    await page.waitForTimeout(400);
    const empty = await page.evaluate(() => {
      const e = document.querySelector('#note-picker-list .note-picker-empty');
      return e ? [e.textContent.trim(), !!e.querySelector('button')] : null;
    });
    ok('no match says so, with Clear search', empty && empty[1], empty);
    await browser.close();
  }
  {
    const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(1000);
    await page.evaluate(() => openNotePicker());
    await page.waitForTimeout(800);
    for (const src of ['notes', 'images']) {
      await page.evaluate((s) => setNotePickerSource(s), src);
      await page.waitForTimeout(700);
      const m = await page.evaluate(() => {
        const p = document.getElementById('note-picker-panel');
        const card = p.closest('.sheet-card');
        const r = (e) => e.getBoundingClientRect();
        const small = [...p.querySelectorAll('button, label.note-picker-row, label.note-picker-cell, .search-field')]
          .filter((e) => e.offsetParent && r(e).height < 43.5).map((e) => (e.id || e.className || e.tagName).toString().slice(0, 30) + ':' + Math.round(r(e).height));
        const seg = document.getElementById('note-picker-sources');
        return {
          sheet: !!card, cardW: card ? Math.round(r(card).width) : 0, vw: innerWidth,
          small, segOverflow: seg.scrollWidth - seg.clientWidth, pageOverflow: document.documentElement.scrollWidth - innerWidth,
          tabRows: new Set([...seg.children].map((b) => Math.round(r(b).top))).size,
          clipped: [...seg.children].filter((b) => b.scrollWidth > b.clientWidth + 1).map((b) => b.textContent.trim()),
        };
      });
      ok(`390 ${src}: a full-width sheet, 44px targets, nothing overflows`,
        m.sheet && m.cardW >= m.vw - 1 && !m.small.length && m.segOverflow <= 0 && m.pageOverflow <= 0 && m.tabRows === 1 && !m.clipped.length, m);
    }
    await browser.close();
  }
})();
