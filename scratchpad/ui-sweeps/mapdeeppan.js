// A new deep topic brings itself into view by the least move (mapdog-1026:
// Maths > Biology > Cells panned 627px and left the root 16px from the window's
// left edge). Builds a chain of topics, Tabs a new child under the deepest one
// five times, and records per step: how far the view moved, where the root and
// the new topic sit. Pass: the new topic is inside the canvas every step, no
// step pans more than the topic needed (new topic's right edge ends 8 to 80px
// inside the window), and the parent stays visible.
// W=1440 H=900 BASE=http://127.0.0.1:8797 SCRATCH=<dir> node mapdeeppan.js
const { boot } = require('./lib.js');
(async () => {
  const W = +(process.env.W || 1440), H = +(process.env.H || 900);
  const { page, browser } = await boot({ viewport: { width: W, height: H }, hasTouch: W < 600, isMobile: W < 600 });
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await page.waitForFunction(() => ['initWhiteboard', 'wbOpenSidebar', 'wbMapTidyFresh'].every((f) => typeof window[f] === 'function'), null, { timeout: 15000 });
  const ids = await page.evaluate(async () => {
    await initWhiteboard();
    const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: `pan ${Date.now()}`, type: 'map', layout: 'tree-right' }) });
    const mk = async (text, parent) => (await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text, ...(parent ? { parent_id: parent } : {}) }) })).id;
    const root = await mk('Maths');
    const bio = await mk('Biology', root);
    const cells = await mk('Cells', bio);
    await openWhiteboardBoard(board.id);
    await wbMapTidyFresh();
    await new Promise((r) => setTimeout(r, 900));
    return { root, cells };
  });
  const rect = (id) => page.evaluate((id) => { const el = document.querySelector(`.wb-object[data-id="${id}"]`); if (!el) return null; const r = el.getBoundingClientRect(); return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom) }; }, id);
  const sel = async (id) => { const r = await rect(id); await page.mouse.click((r.l + r.r) / 2, (r.t + r.b) / 2); await page.waitForTimeout(300); };
  if (process.env.DEBUG) await page.evaluate(() => { window.__log = []; const orig = wbZoom.transform; wbZoom.transform = function (sel, t, ...rest) { const st = (new Error().stack || '').split('\n').slice(2, 5).map((l) => (l.match(/at (\S+)/) || [])[1]).join('<'); if (t && t.x !== undefined) window.__log.push(`to ${Math.round(t.x)},${Math.round(t.y)} k${t.k.toFixed(2)} via ${st}`); return orig.call(this, sel, t, ...rest); }; });
  await sel(ids.cells);
  const rows = [];
  let parent = ids.cells;
  for (let i = 0; i < 5; i++) {
    const before = { root: await rect(ids.root), parent: await rect(parent) };
    const x0 = await page.evaluate(() => Math.round(d3.zoomTransform(document.getElementById('whiteboard-container')).x));
    await page.keyboard.press('Tab');
    if (process.env.POLL) { const tr = []; for (let q = 0; q < 14; q++) { tr.push(await page.evaluate((id) => { const el = document.querySelector(`.wb-object[data-id="${id}"]`); return Math.round(d3.zoomTransform(document.getElementById('whiteboard-container')).x) + '/' + (el ? Math.round(el.getBoundingClientRect().left) : 'x'); }, ids.root)); await page.waitForTimeout(100); } console.log('poll', i + 1, tr.join(' ')); }
    await page.waitForTimeout(100);
    const x1 = await page.evaluate(() => Math.round(d3.zoomTransform(document.getElementById('whiteboard-container')).x));
    await page.waitForTimeout(900);
    const newId = await page.evaluate(() => (typeof wbSelectedItem !== 'undefined' && wbSelectedItem ? wbSelectedItem.id : null));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    const after = { root: await rect(ids.root), parent: await rect(parent), node: newId ? await rect(newId) : null };
    const view = await page.evaluate(() => { const r = (typeof wbVisibleCanvasRect === 'function') ? wbVisibleCanvasRect() : null; return r ? { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom) } : null; });
    if (process.env.DEBUG) console.log(await page.evaluate(() => { const l = window.__log.join(' | '); window.__log = []; return l; }));
    rows.push({ step: i + 1, scr: await page.evaluate(() => { const o = []; for (let e = document.querySelector('.wb-object .wb-map-text, .wb-object'); e; e = e.parentElement) if (e.scrollLeft || e.scrollTop) o.push((e.id || e.className || e.tagName) + ':' + e.scrollLeft + ',' + e.scrollTop); return o.join(' '); }), dom: await page.evaluate((id) => { const el = document.querySelector(`.wb-object[data-id="${id}"]`); const g = document.getElementById('wb-zoom-group'); return { tf: el.getAttribute('style') || el.getAttribute('transform'), parent: el.parentElement.id || el.parentElement.className, group: g && (g.getAttribute('transform') || g.getAttribute('style')), tag: el.tagName }; }, ids.root), rootBoard: await page.evaluate((id) => { const o = wbState.objects.find((q) => q.id === id); return [Math.round(o.x), Math.round(o.y)]; }, ids.root), x0, x1, x2: await page.evaluate(() => Math.round(d3.zoomTransform(document.getElementById('whiteboard-container')).x)), pan: before.root && after.root ? after.root.l - before.root.l : null, rootL: after.root && after.root.l, parentVisible: !!after.parent && after.parent.l >= view.l && after.parent.r <= view.r, nodeRightGap: after.node && view.r - after.node.r, nodeInside: !!after.node && after.node.l >= view.l && after.node.r <= view.r && after.node.t >= view.t && after.node.b <= view.b });
    if (newId) parent = newId;
  }
  for (const r of rows) console.log(JSON.stringify(r));
  const bad = rows.filter((r) => !r.nodeInside || !r.parentVisible || r.nodeRightGap > 80);
  console.log(bad.length ? 'FAIL' : 'PASS', 'errors', errors.length);
  await browser.close();
})();
