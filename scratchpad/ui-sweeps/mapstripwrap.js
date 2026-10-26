// Floating-bar wrap (mapdog-1026 found-not-fixed): at phone width a bar that
// has to wrap must not strand a divider at a row end or leave one control
// alone on a row. Opens a map, selects a topic, and for the map strip prints
// rows, per-row control counts and any divider that ends a row or starts one.
// Pass: the last line says PASS.
// W=390 H=844 BASE=http://127.0.0.1:8797 SCRATCH=<dir> node mapstripwrap.js
const { boot } = require('./lib.js');
(async () => {
  const W = +(process.env.W || 390), H = +(process.env.H || 844);
  const { page, browser } = await boot({ viewport: { width: W, height: H }, hasTouch: W < 600, isMobile: W < 600 });
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await page.waitForFunction(() => ['initWhiteboard', 'wbOpenSidebar', 'wbMapTidyFresh'].every((f) => typeof window[f] === 'function'), null, { timeout: 15000 });
  const ids = await page.evaluate(async () => {
    await initWhiteboard();
    const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: `strip ${Date.now()}`, type: 'map', layout: 'tree-right' }) });
    const root = await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: 'Centre' }) });
    const kids = [];
    for (const t of ['One', 'Two', 'Three']) kids.push((await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: t, parent_id: root.id }) })).id);
    await openWhiteboardBoard(board.id);
    await wbMapTidyFresh();
    await new Promise((r) => setTimeout(r, 900));
    return { board: board.id, root: root.id, kids };
  });
  const measure = async (label, sel) => page.evaluate(({ label, sel }) => {
    const bar = document.querySelector(sel);
    if (!bar || bar.classList.contains('hidden')) return { label, hidden: true };
    const bb = bar.getBoundingClientRect();
    const kids = [...bar.children].filter((c) => { const r = c.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const rows = [];
    for (const c of kids) { const r = c.getBoundingClientRect(); const y = Math.round(r.top + r.height / 2); let row = rows.find((q) => Math.abs(q.y - y) < 6); if (!row) rows.push(row = { y, items: [] }); row.items.push({ div: c.classList.contains('wb-topbar-divider'), w: Math.round(r.width) }); }
    rows.sort((a, b) => a.y - b.y);
    const strandedDivider = rows.length > 1 && rows.some((r) => r.items[0].div || r.items[r.items.length - 1].div);
    const loneControl = rows.length > 1 && rows.some((r) => r.items.filter((i) => !i.div).length === 1);
    return { label, w: Math.round(bb.width), h: Math.round(bb.height), left: Math.round(bb.left), right: Math.round(bb.right), rows: rows.length, perRow: rows.map((r) => r.items.map((i) => (i.div ? '|' : 'c')).join('')), strandedDivider, loneControl };
  }, { label, sel });
  const out = [];
  for (const [name, id] of [['root', ids.root], ['child', ids.kids[0]]]) {
    const el = await page.$(`.wb-object[data-id="${id}"]`);
    const b = await el.boundingBox();
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
    await page.waitForTimeout(500);
    out.push(await measure('map strip on ' + name, '#wb-map-strip'));
  }
  for (const o of out) console.log(JSON.stringify(o));
  const bad = out.filter((o) => !o.hidden && (o.strandedDivider || o.loneControl || o.right > W || o.left < 0));
  console.log(bad.length || out.some((o) => o.hidden) ? 'FAIL' : 'PASS', 'errors', errors.length);
  await browser.close();
})();
