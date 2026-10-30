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

(async () => {
  const { browser, page } = await boot();
  if (PART === 'all' || PART === 'reorder') await reorder(page);
  await browser.close();
})();
