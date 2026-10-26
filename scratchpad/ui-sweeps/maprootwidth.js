// Root and title node width (mapdog-1026: a board name like "C career-map
// 1793027349720" made the root box four lines about 120px wide while level-1
// topics were 155px). Opens maps whose root text is short, a long name, and a
// long unbroken word; prints each root's box, line count and the widest child.
// Pass: no root narrower than its first-level topics, none over 7 lines, no
// word clipped (scrollWidth <= clientWidth).
// W=1440 H=900 BASE=http://127.0.0.1:8797 SCRATCH=<dir> node maprootwidth.js
const { boot } = require('./lib.js');
(async () => {
  const W = +(process.env.W || 1440), H = +(process.env.H || 900);
  const { page, browser } = await boot({ viewport: { width: W, height: H }, hasTouch: W < 600, isMobile: W < 600 });
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await page.waitForFunction(() => ['initWhiteboard', 'wbOpenSidebar', 'wbMapTidyFresh'].every((f) => typeof window[f] === 'function'), null, { timeout: 15000 });
  await page.evaluate(() => initWhiteboard());
  const cases = [['short', 'Maths'], ['long name', 'C career-map 1793027349720'], ['template short', 'Plan', 'maps/career-map'], ['template long name', 'C career-map 1793027349720', 'maps/career-map'], ['template long title', 'Planning the whole second semester of the biology course', 'maps/swot'], ['long title', 'Planning the whole second semester of the biology course'], ['one word', 'Internationalisation-and-localisation-strategy']];
  const out = [];
  for (const [label, text, builtin] of cases) {
    const ids = await page.evaluate(async ({ text, builtin }) => {
      if (builtin) {
        const b = await apiJson('/board-library/new-board', { method: 'POST', body: JSON.stringify({ builtin, name: text }) });
        const rows = (await apiJson(`/whiteboard/?board_id=${b.id}`)).objects;
        const root = rows.find((r) => r.parent_id === null);
        await openWhiteboardBoard(b.id);
        await wbMapTidyFresh();
        wbZoomToFit();
        await new Promise((r) => setTimeout(r, 900));
        return { root: root.id, kids: rows.filter((r) => r.parent_id === root.id).map((r) => r.id) };
      }
      const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: text, type: 'map', layout: 'tree-right' }) });
      const mk = async (t, parent) => (await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: t, ...(parent ? { parent_id: parent } : {}) }) })).id;
      const root = await mk(text);
      const kids = [];
      for (const t of ['Alpha', 'Beta branch', 'Gamma']) kids.push(await mk(t, root));
      await openWhiteboardBoard(board.id);
      await wbMapTidyFresh();
      wbZoomToFit();
      await new Promise((r) => setTimeout(r, 900));
      return { root, kids };
    }, { text, builtin });
    const m = await page.evaluate(({ root, kids }) => {
      const box = (id) => { const el = document.querySelector(`.wb-object[data-id="${id}"]`); const r = el.getBoundingClientRect(); const tx = el.querySelector('.wb-map-text'); const cs = getComputedStyle(tx); const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3; const k = d3.zoomTransform(document.getElementById('whiteboard-container')).k; return { w: Math.round(el.offsetWidth), h: Math.round(el.offsetHeight), lines: Math.round(tx.getBoundingClientRect().height / (lh * k)), clipped: tx.scrollWidth > tx.clientWidth + 1 }; };
      return { root: box(root), kids: kids.map(box), k: +d3.zoomTransform(document.getElementById('whiteboard-container')).k.toFixed(2) };
    }, ids);
    const kidW = Math.max(...m.kids.map((q) => q.w));
    out.push({ label, root: m.root, kidW, k: m.k, ok: m.root.w >= Math.min(kidW, 160) && m.root.lines <= 7 && !m.root.clipped });
  }
  for (const o of out) console.log(JSON.stringify(o));
  console.log(out.every((o) => o.ok) ? 'PASS' : 'FAIL', 'errors', errors.length);
  await browser.close();
})();
