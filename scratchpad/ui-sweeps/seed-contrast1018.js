// Seeds one board (every sticky paper, text cards, shapes, a connector, tinted
// frames) and one mind map (three levels, coloured and filled topics) for the
// dark-theme contrast sweep. Fresh data dir only: contrast.js opens the first
// board and the first map it finds.
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/seed-contrast1018.js
const { boot, openBoardsTab, waitForBoardOpen } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  await openBoardsTab(page);
  const made = await page.evaluate(async () => {
    const post = async (p, b) => (await api(p, { method: 'POST', body: JSON.stringify(b) })).json();
    const put = async (p, b) => (await api(p, { method: 'PUT', body: JSON.stringify(b) })).json();
    const board = await post('/whiteboard/boards', { name: 'Contrast board', type: 'board' });
    const papers = ['#fff4a3', '#ffd8a8', '#ffc9de', '#e5d4ff', '#cfe8ff', '#d3f5c4', '#ececec'];
    for (let i = 0; i < papers.length; i++) {
      await post('/whiteboard/objects', { kind: 'text', board_id: board.id, x: 40 + i * 190, y: 60, width: 170, height: 130, z: 2,
        data: { content: 'Sticky ' + (i + 1) + ' on paper', sticky: true, bg: papers[i], color: '#2a2a1f', font_size: 16 } });
    }
    await post('/whiteboard/objects', { kind: 'text', board_id: board.id, x: 40, y: 220, width: 300, height: 60, z: 2, data: { content: 'Plain text box, no fill' } });
    await post('/whiteboard/objects', { kind: 'text', board_id: board.id, x: 360, y: 220, width: 300, height: 80, z: 2, data: { content: 'Dark card', bg: '#1f3a5f', border_color: '#3d6fb8' } });
    await post('/whiteboard/objects', { kind: 'text', board_id: board.id, x: 680, y: 220, width: 300, height: 80, z: 2, data: { content: 'Red card', bg: '#4a2c2c', border_color: '#b85555' } });
    const tints = ['neutral', 'red', 'amber', 'green', 'teal', 'blue', 'violet', 'pink'];
    for (let i = 0; i < tints.length; i++) {
      await post('/whiteboard/objects', { kind: 'frame', board_id: board.id, x: 40 + (i % 4) * 330, y: 340 + Math.floor(i / 4) * 230, width: 310, height: 210, z: 1,
        data: { content: 'Frame ' + tints[i], tint: tints[i], hint: 'What goes in this frame' } });
    }
    await post('/whiteboard/objects', { kind: 'table', board_id: board.id, x: 1050, y: 60, width: 300, height: 120, z: 2, data: { cells: [['Name', 'Value'], ['one', '1']], header: true } }).catch(() => null);
    const map = await post('/whiteboard/boards', { name: 'Contrast map', type: 'map' });
    const node = async (text, parent, extra = {}) => post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'topic', text, ...(parent ? { parent_id: parent } : {}), ...extra });
    const root = await node('Product launch', null);
    const colors = ['#e5484d', '#f5a524', '#2e9e5b', '#3b82f6', '#8b5cf6', '#db2777'];
    const fills = ['self', 'solid', 'branch', 'branch', 'self', 'none'];
    const errs = [];
    for (let i = 0; i < 6; i++) {
      const b = await node('Branch ' + (i + 1), root.id, { color: colors[i] });
      const r = await api(`/whiteboard/objects/${b.id}`, { method: 'PUT', body: JSON.stringify({ kind: 'topic', board_id: map.id, x: b.x, y: b.y, width: b.width, height: b.height, z: b.z, data: { ...b.data, fill: fills[i] } }) });
      if (!r.ok) errs.push(r.status + ' ' + (await r.text()).slice(0, 120));
      for (let j = 0; j < 2; j++) {
        const c = await node(`Subtopic ${i + 1}.${j + 1}`, b.id);
        await node(`Detail ${i + 1}.${j + 1} with some longer words`, c.id);
      }
    }
    return { board: board.id, map: map.id, errs: errs.slice(0, 2) };
  });
  console.log('seeded', JSON.stringify(made));
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, made.board);
  await waitForBoardOpen(page, 0);
  await page.waitForTimeout(500);
  const r = await page.evaluate(async () => {
    const out = {};
    try {
      await wbLibPlace(wbLibEntries().find((e) => e.ref === 'builtin:drawio-flowchart/decision'), [1100, 300]);
      const proc = wbLibEntries().find((e) => e.ref === 'builtin:drawio-flowchart/process');
      if (proc) await wbLibPlace(proc, [1100, 520]);
      const sk = wbState.sketches.filter((s) => /drawio/.test(s.data));
      out.shapes = sk.length;
      if (sk.length >= 2) {
        await apiJson('/whiteboard/sketches', { method: 'POST', body: JSON.stringify({ data: JSON.stringify({ type: 'link-straight', sourceId: sk[0].id, sourceKind: 'sketch', targetId: sk[1].id, targetKind: 'sketch', width: 2, endCap: 'arrow' }), x: 0, y: 0, z: 3, board_id: sk[0].board_id }) });
        out.link = true;
      }
    } catch (e) { out.err = String(e); }
    return out;
  });
  console.log('shapes', JSON.stringify(r));
  await browser.close();
})();
