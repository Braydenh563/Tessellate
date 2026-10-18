// C19 + C20: the companion put over a board's canvas is drawn under the
// board's panels and over its objects, and is sized to the board's zoom; on
// a panel it is its own size above everything. elementFromPoint pairs.
const { boot, openBoardsTab, waitForBoardOpen } = require(process.cwd() + '/lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true })); } });
  await openBoardsTab(page);
  const board = await page.evaluate(async () => {
    const b = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: 'Canvas ' + Date.now() }) });
    for (let i = 0; i < 8; i++) await apiJson('/whiteboard/objects', { method: 'POST', body: JSON.stringify({ kind: 'text', data: { content: 'Box ' + i }, board_id: b.id, x: 80 + (i % 4) * 300, y: 80 + Math.floor(i / 4) * 260, z: 1, width: 200, height: 100 }) });
    return b;
  });
  await page.evaluate((id) => openWhiteboardBoard(id), board.id);
  await waitForBoardOpen(page, 8);
  await page.evaluate(() => wbFormatOpen(null, { focus: false }));
  await page.waitForTimeout(800);
  const put = (spot) => page.evaluate(async (s) => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyIndexReset();
    if (s.under) { const t = document.getElementById('wb-topbar').getBoundingClientRect(); s = { kind: 'dock', pose: 'hang', legs: '', x: 600, y: t.bottom - NMB_GRIP, edge: { el: document.getElementById('wb-topbar'), type: 'under', kind: 'dock', y: t.bottom, left: t.left, right: t.right, top: t.top, bottom: t.bottom } }; }
    nameMarkBuddyMoveTo(buddy, s, true);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const b = buddy.querySelector('.nm-buddy-face').getBoundingClientRect();
    const el = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    const bandZ = getComputedStyle(document.getElementById('nm-buddy-band')).zIndex;
    await new Promise((r) => setTimeout(r, 1500));
    const f = document.getElementById('wb-format').getBoundingClientRect();
    const after = buddy.querySelector('.nm-buddy-face').getBoundingClientRect();
    const stillOverFormat = after.right > f.left && after.left < f.right && after.bottom > f.top && after.top < f.bottom;
    return { stillOverFormat, hit: el?.closest('#nm-buddy') ? 'companion' : el?.closest('#wb-format') ? 'format' : el?.closest('.wb-object') ? 'object' : String(el?.id || el?.className).slice(0, 30), bandZ, scale: nmb.scale, faceW: Math.round(b.width) };
  }, spot);
  const f = await page.evaluate(() => { const r = document.getElementById('wb-format').getBoundingClientRect(); return [r.left, r.top]; });
  const o = await page.evaluate(() => { const r = document.querySelectorAll('#whiteboard-container .wb-object')[1].getBoundingClientRect(); return [r.left, r.top]; });
  const out = {};
  out.overFormat = await put({ kind: 'yours', pose: 'float', legs: '', x: f[0] + 60, y: f[1] + 160 });
  out.overObject = await put({ kind: 'yours', pose: 'float', legs: '', x: o[0] + 40, y: o[1] - 10 });
  await page.evaluate(() => { const c = document.getElementById('whiteboard-container'); d3.select(c).call(wbZoom.scaleTo, 0.5); });
  await page.waitForTimeout(600);
  out.zoomedOut = await page.evaluate(() => ({ k: document.getElementById('whiteboard-container').__zoom?.k, scale: nmb.scale }));
  await page.evaluate(() => { const c = document.getElementById('whiteboard-container'); d3.select(c).call(wbZoom.scaleTo, 2); });
  await page.waitForTimeout(600);
  out.zoomedIn = await page.evaluate(() => ({ k: document.getElementById('whiteboard-container').__zoom?.k, scale: nmb.scale }));
  out.onTopBar = await put({ under: true });
  console.log(JSON.stringify(out));
  await browser.close();
})();
