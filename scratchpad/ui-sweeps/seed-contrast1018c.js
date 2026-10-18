// Third pass: one map per branch palette (no explicit colours, so the palette
// colours the branches), each with a solid, a self-filled, a branch-filled and
// an unfilled branch, three levels deep. Titles start "Contrast palette ".
const { boot, openBoardsTab } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  await openBoardsTab(page);
  const r = await page.evaluate(async () => {
    const post = async (p, b) => (await api(p, { method: 'POST', body: JSON.stringify(b) })).json();
    const put = async (p, b) => (await api(p, { method: 'PUT', body: JSON.stringify(b) })).json();
    const made = [];
    for (const pal of ['classic', 'deep', 'soft', 'vivid', 'bold', 'paired', 'bright', 'earth']) {
      const map = await post('/whiteboard/boards', { name: 'Contrast palette ' + pal, type: 'map' });
      await put(`/whiteboard/boards/${map.id}`, { theme: { palette: pal } });
      const node = (text, parent) => post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'topic', text, ...(parent ? { parent_id: parent } : {}) });
      const root = await node('Root ' + pal, null);
      const fills = ['solid', 'self', 'branch', 'none'];
      for (let i = 0; i < 10; i++) {
        const b = await node('Branch ' + (i + 1), root.id);
        await api(`/whiteboard/objects/${b.id}`, { method: 'PUT', body: JSON.stringify({ kind: 'topic', board_id: map.id, x: b.x, y: b.y, width: b.width, height: b.height, z: b.z, data: { ...b.data, fill: fills[i % 4] } }) });
        const c = await node(`Sub ${i + 1}`, b.id);
        await node(`Leaf ${i + 1}`, c.id);
      }
      made.push(map.id);
    }
    return made;
  });
  console.log('seeded maps', JSON.stringify(r));
  await browser.close();
})();
