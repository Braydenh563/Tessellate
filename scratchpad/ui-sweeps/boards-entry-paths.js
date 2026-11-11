// dec-1111-d2 (audit-1028 D22): every entry path that reaches board code
// after the `library` / `boards` bundle split. One fresh browser per path;
// per path it records: opened (window.currentBoardId set and #wb-canvas-view
// visible), console/page errors, how many times ensureModule("boards") was
// called, and how many times /js/whiteboard.js was requested (must be 1).
//
//   BASE=http://127.0.0.1:8805 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/boards-entry-paths.js [name ...]
// The data dir needs a whiteboard "Launch plan" and a mind map "Bubble tea"
// with content (seed-boards.js makes both); this script adds a note and puts
// it on the board.
const { boot } = require('./lib.js');

const only = process.argv.slice(2);

async function seed() {
  const { browser, page } = await boot();
  const ids = await page.evaluate(async () => {
    const post = async (p, b) => (await api(p, { method: 'POST', body: JSON.stringify(b) })).json();
    const boards = await (await api('/whiteboard/boards')).json();
    const board = boards.find((b) => b.title === 'Launch plan' || b.name === 'Launch plan');
    const map = boards.find((b) => b.title === 'Bubble tea' || b.name === 'Bubble tea');
    let list = await (await api('/entries?limit=50')).json();
    let note = (list.items || list).find((e) => /D22 probe note/.test(e.content || ''));
    if (!note) {
      note = await post('/entries', { content: 'D22 probe note about launch plans', defer_filing: true });
      await post('/whiteboard/nodes', { entry_id: note.id, board_id: board.id, x: 80, y: 80, z: 1 }).catch(() => null);
    }
    if (!(list.items || list).some((e) => /D22 outline note/.test(e.content || ''))) await post('/entries', { content: 'D22 outline note\n\n# Launch\n- one\n- two\n\n# Review\n- three', defer_filing: true });
    return { board: board.id, map: map.id, note: note.id };
  });
  await browser.close();
  return ids;
}

const visible = (page) => page.evaluate(() => {
  const v = document.getElementById('wb-canvas-view');
  return { id: window.currentBoardId ?? null, canvas: !!(v && v.offsetParent !== null && v.getBoundingClientRect().width > 0) };
});

async function opened(page, id, ms = 15000) {
  const t = Date.now();
  while (Date.now() - t < ms) {
    const v = await visible(page);
    if (v.id === id && v.canvas) return true;
    await page.waitForTimeout(250);
  }
  return false;
}

// Counts ensureModule("boards") calls; re-applied after a reload, which drops it.
const instrument = (page) => page.evaluate((logInserts) => {
  const orig = window.ensureModule;
  if (orig.__counted) return;
  window.__ens = window.__ens || [];
  window.ensureModule = (n) => { window.__ens.push(n); return orig(n); };
  window.ensureModule.__counted = true;
  // INSERTS=1: the order lazy scripts are put on the page, with what asked, for a load-order report.
  if (logInserts) {
    const add = document.head.appendChild.bind(document.head);
    window.__inserts = [];
    document.head.appendChild = (el) => { if (el.tagName === 'SCRIPT') window.__inserts.push(String(el.src).split('/').pop().split('?')[0] + ' <- ' + new Error().stack.split('\n').slice(2, 6).map((l) => l.trim().split(' ')[1]).join(' < ')); return add(el); };
  }
}, !!process.env.INSERTS);

// A note menu item may sit in a group (Connect, Add, ...): open each group until the item shows.
// The flyout opens on hover after a delay, so a miss reopens the whole menu (up to three tries).
async function noteMenuItem(page, noteText, label) {
  const card = page.locator('#entry-list li:not(.rail-subject)', { hasText: noteText }).first();
  await card.waitFor({ timeout: 15000 });
  const item = page.locator('button.menu-item:visible', { hasText: label }).first();
  for (let attempt = 0; attempt < 3; attempt++) {
    await card.locator('button[title="More actions"]').first().click();
    await page.waitForTimeout(600);
    const groups = page.locator('.action-menu:visible > .menu-group > button.has-submenu');
    const n = await groups.count();
    for (let i = 0; i < n && !(await item.isVisible()); i++) {
      await groups.nth(i).hover().catch(() => null);
      await page.waitForTimeout(900);
    }
    if (await item.isVisible()) return item.click({ timeout: 5000 });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  }
  throw new Error('menu item not found: ' + label);
}

const openNotif = (page) => page.evaluate(() => (document.getElementById('notif-btn') ? document.getElementById('notif-btn').click() : openNotifications()));

// Each path returns the board id it expects to be open, 'any', or -1 for a setup failure.
const DEFS = {
  async dashFeature(page, ids) {
    await page.evaluate(() => switchTab('dashboard'));
    await page.locator('.dash-board-feature').first().waitFor({ timeout: 15000 });
    const which = await page.evaluate(() => document.querySelector('.dash-board-feature .dash-list-title').textContent);
    await page.locator('.dash-board-feature').first().click();
    return which === 'Bubble tea' ? ids.map : ids.board;
  },
  async dashRow(page, ids) {
    await page.evaluate(() => switchTab('dashboard'));
    await page.locator('.dash-board-feature').first().waitFor({ timeout: 15000 });
    const row = page.locator('[data-obj^="board:"], [data-obj^="map:"]').first();
    await row.waitFor({ timeout: 8000 });
    const obj = await row.getAttribute('data-obj');
    await row.click();
    return Number(obj.split(':')[1]);
  },
  // Back in one session: the board was opened here, so boards is already loaded.
  async backInSession(page, ids) {
    await page.evaluate(() => switchTab('library'));
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    if (!(await opened(page, ids.board))) return -1;
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(800);
    await page.evaluate(() => { window.currentBoardId = null; });
    await page.click('#status-back');
    return ids.board;
  },
  // Browser Back after a reload: the bundle is not loaded and the history entry is a board.
  async backAfterReload(page, ids) {
    await page.evaluate(() => switchTab('library'));
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    if (!(await opened(page, ids.board))) return -1;
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(800);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    // A reload leaves the same address twice in the browser's history (the boot pushes one), so the board is two steps back.
    await page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => null);
    await page.waitForTimeout(1500);
    await page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => null);
    return ids.board;
  },
  async forwardAfterReload(page, ids) {
    await page.evaluate(() => switchTab('library'));
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    if (!(await opened(page, ids.board))) return -1;
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(800);
    await page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => null);
    await page.waitForTimeout(1500);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    await page.goForward({ waitUntil: 'domcontentloaded' }).catch(() => null);
    return ids.board;
  },
  async notificationBoard(page, ids) {
    await page.evaluate((id) => { toastAction('D22 probe: board ready.', 'Open', () => {}, { go: { open: 'board', id } }); }, ids.board);
    await page.waitForTimeout(1500);
    // The toast's own closure is live in this document and would run instead of the stored `go`; a reload leaves only the stored go, which is what a notification found later does.
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    await openNotif(page);
    await page.waitForTimeout(800);
    await page.locator('#notif-list .notif-cta').first().click({ timeout: 8000 });
    return ids.board;
  },
  async notificationMap(page, ids) {
    await page.evaluate((id) => { toastAction('D22 probe: map ready.', 'Open', () => {}, { go: { open: 'board', id } }); }, ids.map);
    await page.waitForTimeout(1500);
    // The toast's own closure is live in this document and would run instead of the stored `go`; a reload leaves only the stored go, which is what a notification found later does.
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    await openNotif(page);
    await page.waitForTimeout(800);
    await page.locator('#notif-list .notif-cta').first().click({ timeout: 8000 });
    return ids.map;
  },
  async timelineRow(page, ids) {
    await page.evaluate(() => switchTab('timeline'));
    await page.waitForTimeout(2500);
    const row = page.locator('#tab-timeline li.timeline-row', { hasText: 'Bubble tea' }).first();
    await row.waitFor({ timeout: 15000 });
    await row.click();
    await page.locator('button:has-text("Open this map")').first().click({ timeout: 8000 });
    return ids.map;
  },
  async graphMapToast(page) {
    await page.evaluate(() => switchTab('graph'));
    await page.waitForFunction(() => typeof gcTab !== 'undefined' && gcTab.byId && gcTab.byId.size > 1, null, { timeout: 30000 });
    await page.evaluate(() => {
      const s = gcTab;
      for (const x of [...s.byId.values()].filter((n) => Number.isInteger(n.id)).slice(0, 2)) s.selected.add(x.id);
      gcSelectionChanged(s);
    });
    await page.waitForTimeout(500);
    await page.evaluate(() => document.getElementById('graph-selection-map').click());
    const input = page.locator('.confirm-overlay input:visible').first();
    await input.waitFor({ timeout: 8000 });
    await input.fill('D22 graph map');
    await page.keyboard.press('Enter');
    await page.locator('[class*=toast] button:has-text("Open")').first().click({ timeout: 15000 });
    return 'any';
  },
  async connectionsSheet(page, ids) {
    await page.evaluate((id) => lazyScript('/js/connections.js').then(() => openConnections('entries', id, 'D22 probe note')), ids.note);
    await page.locator('.connection-row', { hasText: 'Launch plan' }).first().click({ timeout: 10000 });
    return ids.board;
  },
  async entryMenuMap(page) {
    await page.evaluate(() => switchTab('notes'));
    await noteMenuItem(page, 'D22 outline note', 'Make a mind map');
    return 'any';
  },
  async attachToOpen(page, ids) {
    await page.evaluate(() => switchTab('notes'));
    await noteMenuItem(page, 'D22 probe note', 'Add to a board or map');
    const attach = page.locator('#entry-list button:visible', { hasText: /^\s*Attach\s*$/ }).first();
    await attach.waitFor({ timeout: 8000 }).catch(async (e) => { console.log('  inline:', await page.evaluate(() => [...document.querySelectorAll('#entry-list li')].map((l) => l.textContent.replace(/\s+/g, ' ').slice(-120)))); throw e; });
    await page.locator('select').filter({ has: page.locator('option', { hasText: 'Launch plan' }) }).first().selectOption({ label: 'Launch plan' }).catch(() => null);
    await attach.click();
    await page.locator('[class*=toast] button:has-text("Open")').first().click({ timeout: 10000 });
    return ids.board;
  },
  // Gallery click, then reload: does the board come back?
  async reloadAfterGallery(page, ids) {
    await page.evaluate(() => switchTab('library'));
    await page.click('#library-subtabs button[data-target="library-view-whiteboard"]');
    const card = page.locator('#library-view-whiteboard').getByText('Launch plan').first();
    await card.waitFor({ timeout: 15000 });
    await card.click();
    if (!(await opened(page, ids.board))) return -1;
    await page.waitForTimeout(1500);
    console.log('  hash after click:', await page.evaluate(() => location.hash));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    return ids.board;
  },
  async reloadAfterDirect(page, ids) {
    await page.evaluate(() => switchTab('library'));
    await page.evaluate((id) => openWhiteboardBoard(id), ids.board);
    if (!(await opened(page, ids.board))) return -1;
    await page.waitForTimeout(1500);
    console.log('  hash after open:', await page.evaluate(() => location.hash));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    await instrument(page);
    return ids.board;
  },
};

(async () => {
  const ids = await seed();
  console.log('ids', JSON.stringify(ids));
  for (const [name, fn] of Object.entries(DEFS)) {
    if (only.length && !only.includes(name)) continue;
    const { browser, page } = await boot();
    const errs = [];
    page.on('pageerror', (e) => errs.push('PAGE ' + e.message.slice(0, 120)));
    page.on('console', (m) => { if (m.type() === 'error') errs.push('CON ' + m.text().slice(0, 120)); });
    let wbReq = 0, d3Req = 0;
    page.on('request', (r) => { const u = r.url(); if (/\/js\/whiteboard\.js/.test(u)) wbReq++; if (/d3\.v7/.test(u)) d3Req++; });
    await instrument(page);
    const pre = await page.evaluate(() => !!document.querySelector('script[src*="whiteboard.js"]'));
    let ok = false, note = '';
    try {
      const want = await fn(page, ids);
      if (want === 'any') {
        const t = Date.now();
        while (Date.now() - t < 15000 && !(await visible(page)).canvas) await page.waitForTimeout(250);
        const v = await visible(page);
        ok = v.canvas && v.id != null;
      } else ok = want !== -1 && (await opened(page, want, 20000));
    } catch (e) { note = String(e.message).split('\n')[0].slice(0, 140); }
    // The counter lives on the page that was instrumented: a reload drops it, so after a reload it counts only the new document.
    const ens = await page.evaluate(() => (window.__ens || []).filter((n) => n === 'boards').length).catch(() => -1);
    if (process.env.INSERTS) console.log((await page.evaluate(() => (window.__inserts || []).join('\n'))));
    const v = await visible(page).catch(() => ({}));
    console.log(JSON.stringify({ name, boardsLoadedBefore: pre, opened: ok, board: v.id, ensureBoardsCalls: ens, whiteboardJsReq: wbReq, d3Req, errors: errs.slice(0, 3), note }));
    await browser.close();
  }
})();
