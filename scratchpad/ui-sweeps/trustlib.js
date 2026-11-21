// Shared by undo.js, reach.js and overlap.js (WORLD_CLASS_PLAN 28, phase T0):
// the nine surfaces the trust contract names, how to open each one, and the
// small API helpers the three sweeps need. Opening a surface is one function
// so the three agree on what "the whiteboard" means.
const { boot, openBoardsTab, waitForBoardOpen, BASE } = require('./lib.js');

async function jget(page, path) {
  return page.evaluate(async ({ base, path }) => {
    const r = await fetch(base + path, { headers: { 'X-Auth-Token': localStorage.getItem('token') || '' } });
    try { return await r.json(); } catch (e) { return null; }
  }, { base: BASE, path });
}
async function jsend(page, method, path, body) {
  return page.evaluate(async ({ base, method, path, body }) => {
    const r = await fetch(base + path, {
      method, headers: { 'X-Auth-Token': localStorage.getItem('token') || '', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    try { return await r.json(); } catch (e) { return null; }
  }, { base: BASE, method, path, body });
}

// Enough data that every surface has something to act on. Idempotent: it only
// tops up what a probe has consumed.
async function ensureSeed(page) {
  const entries = (await jget(page, '/entries?limit=500')) || [];
  for (let i = entries.length; i < 8; i++) await jsend(page, 'POST', '/entries', { content: `Probe note ${i} about the garden and the plan`, tags: ['probe'] });
  const docs = (await jget(page, '/documents')) || [];
  if (docs.length < 2) await jsend(page, 'POST', '/documents', { title: 'Probe document', content: '# Probe document\n\nFirst paragraph of words.\n\n## Part\n\nSecond paragraph of words.' });
  const rem = (await jget(page, '/reminders')) || [];
  if (rem.filter((r) => !r.done).length < 2) await jsend(page, 'POST', '/reminders', { text: 'Probe reminder', due_at: new Date(Date.now() + 7200e3).toISOString() });
  const bm = (await jget(page, '/bookmarks')) || [];
  if (bm.length < 2) await jsend(page, 'POST', '/bookmarks', { url: 'https://example.org/' + Date.now(), title: 'Probe bookmark', group_name: 'Probe' });
  let boards = (await jget(page, '/whiteboard/boards')) || [];
  const ents = (await jget(page, '/entries?limit=50')) || [];
  if (!boards.find((b) => b.title === 'Probe board')) {
    const b = await jsend(page, 'POST', '/whiteboard/boards', { name: 'Probe board', type: 'board' });
    for (let i = 0; b && i < 3 && ents[i]; i++) await jsend(page, 'POST', '/whiteboard/nodes', { entry_id: ents[i].id, board_id: b.id, x: 120 + i * 260, y: 160, z: i + 1 });
  }
  if (!boards.find((b) => b.title === 'Probe map')) {
    const m = await jsend(page, 'POST', '/whiteboard/boards', { name: 'Probe map', type: 'map' });
    const root = await jsend(page, 'POST', '/entries', { content: '# Probe map', tags: [], defer_filing: true, map_topic: true });
    if (m && root) await jsend(page, 'POST', '/whiteboard/nodes', { entry_id: root.id, board_id: m.id, x: 400, y: 260, z: 1 });
  }
}
async function boardIds(page) {
  const boards = (await jget(page, '/whiteboard/boards')) || [];
  const pick = (t) => (boards.find((b) => b.title === t) || {}).id;
  return { board: pick('Probe board'), map: pick('Probe map') };
}

async function tab(page, name) {
  await page.evaluate((n) => switchTab(n), name);
  await page.waitForTimeout(700);
}
async function sub(page, selector) {
  await page.click(selector, { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(700);
}

// name, the root element the surface lives in, and how to open it.
const SURFACES = [
  { name: 'notes list', root: '#tab-notes', open: async (p) => { await tab(p, 'notes'); await sub(p, '#notes-subtabs [data-section="browse"]'); } },
  { name: 'note editor', root: '#tab-notes', open: async (p) => {
    await tab(p, 'notes'); await sub(p, '#notes-subtabs [data-section="browse"]');
    await p.click('#entry-list [aria-label^="Edit this entry"]', { timeout: 4000 }).catch(() => {});
    await p.waitForTimeout(900); } },
  { name: 'documents', root: '#tab-documents', open: async (p) => {
    await tab(p, 'library'); await sub(p, '#library-subtabs [data-target="library-view-docs"]');
    await p.click('.doc-list-item', { timeout: 4000 }).catch(() => {});
    await p.waitForTimeout(1200);
    // Selected text, so the format controls have something to act on.
    await p.click('#tab-documents .cm-content', { timeout: 2500 }).catch(() => {});
    await p.keyboard.press('Control+A').catch(() => {});
  } },
  { name: 'whiteboard', root: '#library-view-whiteboard', open: async (p) => {
    const ids = await boardIds(p);
    await openBoardsTab(p).catch(() => {});
    await p.evaluate((id) => openWhiteboardBoard(id), ids.board);
    await waitForBoardOpen(p, 0).catch(() => {});
    await p.waitForTimeout(800);
    await p.click('#whiteboard-container .wb-card', { timeout: 2500 }).catch(() => {});
  } },
  { name: 'mind map', root: '#library-view-whiteboard', open: async (p) => {
    const ids = await boardIds(p);
    await openBoardsTab(p).catch(() => {});
    await p.evaluate((id) => openWhiteboardBoard(id), ids.map);
    await waitForBoardOpen(p, 0).catch(() => {});
    await p.waitForTimeout(1000);
    await p.click('#whiteboard-container .wb-card', { timeout: 2500 }).catch(() => {});
  } },
  { name: 'graph', root: '#tab-graph', open: async (p) => { await tab(p, 'graph'); await p.waitForTimeout(1500); } },
  { name: 'timeline', root: '#tab-timeline', open: async (p) => { await tab(p, 'timeline'); await p.waitForTimeout(800); } },
  { name: 'library', root: '#tab-library', open: async (p) => {
    await tab(p, 'library');
    // The Library reopens on the last sub-tab, and a board kept open is still
    // on screen: back to the list first so "library" is the Library.
    await p.click('#wb-back-to-boards', { timeout: 800 }).catch(() => {});
    await sub(p, '#library-subtabs [data-target="library-view-documents"]'); } },
  { name: 'settings', root: '#settings-modal', open: async (p) => {
    await p.keyboard.press('Escape').catch(() => {});
    // The gear moves into a menu on a phone, so the function is called: what is
    // measured is the dialog, not where its door is.
    await p.evaluate(() => openSettingsModal('models')).catch(() => {});
    await p.waitForTimeout(900); } },
  // Not in the brief's nine, but two more places a person works.
  { name: 'dashboard', root: '#tab-dashboard', open: async (p) => { await tab(p, 'dashboard'); await p.waitForTimeout(800); } },
  { name: 'chat', root: '#tab-chat', open: async (p) => { await tab(p, 'chat'); await p.waitForTimeout(600); } },
  { name: 'reminders', root: '#tab-reminders', open: async (p) => { await tab(p, 'reminders'); await p.waitForTimeout(600); } },
  // The agent (Brief 87): the palette above 600, its sheet below.
  { name: 'agent', root: '#command-palette-overlay:not(.hidden), .sheet-overlay[data-sheet="agent"]', open: async (p) => { await tab(p, 'dashboard'); await p.evaluate(() => toggleAgentPalette()); await p.waitForTimeout(900); } },
];
async function closeOverlays(page) {
  for (let i = 0; i < 3; i++) await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(150);
}
// A visible-box test written once, for use inside page.evaluate bodies.
const VISIBLE_FN = `(e)=>{const b=e.getBoundingClientRect();const s=getComputedStyle(e);return b.width>0&&b.height>0&&s.visibility!=='hidden'&&s.display!=='none';}`;

// Put the page back as it was opened: the keys localStorage held (a remembered
// filter or tab is how one probe leaks into the next), then a fresh load.
async function saveLocal(page) { return page.evaluate(() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }); }
async function reboot(page, saved) {
  if (saved) await page.evaluate((o) => { for (const k of Object.keys(localStorage)) if (!(k in o)) localStorage.removeItem(k); for (const k of Object.keys(o)) localStorage.setItem(k, o[k]); }, saved);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (await page.isVisible('#lock-password').catch(() => false)) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(2500); }
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  await page.waitForTimeout(500);
}

module.exports = { saveLocal, reboot, boot, jget, jsend, ensureSeed, boardIds, tab, sub, SURFACES, closeOverlays, VISIBLE_FN, BASE };
