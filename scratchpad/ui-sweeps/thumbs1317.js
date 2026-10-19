// Board thumbnails (INBOX 1317): open a board and a map, wait for the
// debounced thumbnail PUT, then measure bytes, that <img> previews load
// (naturalWidth > 0) and the widget render time, in the theme THEME names.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  const out = {};
  const puts = [];
  page.on('response', (r) => { if (r.request().method() === 'PUT' && r.url().includes('/thumbnail')) puts.push([r.url(), r.status(), r.request().postDataBuffer()?.length]); });
  for (const id of [1, 2]) {
    await page.evaluate((i) => openWhiteboardBoard(i), id);
    await page.waitForTimeout(6000);
  }
  await page.mouse.click(5, 5);
  await page.waitForTimeout(1500);
  out.puts = puts;
  out.rows = await page.evaluate(async () => {
    const boards = await (await api('/whiteboard/boards')).json();
    return boards.filter((b) => b.id).map((b) => ({ id: b.id, thumb_v: b.thumb_v }));
  });
  out.sizes = await page.evaluate(async (rows) => Promise.all(rows.map(async (r) => {
    const res = await api(`/media/board-thumb/${r.id}`);
    return { id: r.id, type: res.headers.get('content-type'), bytes: (await res.arrayBuffer()).byteLength };
  })), out.rows);
  out.render = await page.evaluate(async () => {
    const boards = await (await api('/whiteboard/boards')).json();
    const time = (b) => { const t = performance.now(); for (let i = 0; i < 50; i++) mapPreview(b, { size: 'card' }); return (performance.now() - t) / 50; };
    const withThumb = boards.filter((b) => b.thumb_v && b.id);
    const without = withThumb.map((b) => ({ ...b, thumb_v: null }));
    const loaded = await Promise.all(withThumb.map((b) => new Promise((res) => {
      const el = mapPreview(b, { size: 'card' }); document.body.appendChild(el);
      el.addEventListener('load', () => res({ id: b.id, w: el.naturalWidth, h: el.naturalHeight }));
      el.addEventListener('error', () => res({ id: b.id, err: true }));
      setTimeout(() => res({ id: b.id, timeout: true }), 4000);
      el.loading = 'eager';
    })));
    return { imgMs: withThumb.map(time), svgMs: without.map(time), loaded };
  });
  await page.evaluate(() => switchTab('library'));
  await page.evaluate(() => document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click());
  await page.waitForTimeout(3500);
  out.library = await page.evaluate(() => [...document.querySelectorAll('.library-board-card img.board-minimap')].map((i) => ({ w: i.naturalWidth, box: Math.round(i.getBoundingClientRect().width) + 'x' + Math.round(i.getBoundingClientRect().height) })));
  out.dash = await page.evaluate(async () => {
    await ensureModule('dashBoards');
    const boards = await (await api('/whiteboard/boards')).json();
    const host = document.createElement('div'); host.style.width = '320px'; document.body.appendChild(host);
    const row = document.createElement('div'); row.className = 'dash-list'; const ul = document.createElement('ul'); const li = document.createElement('li'); ul.appendChild(li); row.appendChild(ul); host.appendChild(row);
    const t = performance.now();
    const feature = dashMapFeature(boards.find((b) => b.id === 1)); host.appendChild(feature);
    const thumb = dashBoardThumb(boards.find((b) => b.id === 2)); li.appendChild(thumb);
    const ms = performance.now() - t;
    await new Promise((r) => setTimeout(r, 1500));
    const q = (e) => ({ tag: e.tagName, w: e.naturalWidth, box: Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height) });
    return { ms, feature: q(feature.querySelector('.board-minimap')), thumb: q(thumb) };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
