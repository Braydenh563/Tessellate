// Second pass for seed-contrast1018.js: shapes and connectors on the board,
// and every topic decoration on the map (markers, labels, callout, due, task,
// note, edge label, boundary, summary, stamps).
const { boot, openBoardsTab } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  await openBoardsTab(page);
  const r = await page.evaluate(async () => {
    const post = async (p, b) => (await api(p, { method: 'POST', body: JSON.stringify(b) })).json();
    const boards = await apiJson('/whiteboard/boards');
    const board = boards.find((b) => b.title === 'Contrast board');
    const map = boards.find((b) => b.title === 'Contrast map');
    const out = {};
    const a = await post(`/whiteboard/boards/${board.id}/place`, { builtin: 'drawio-flowchart/decision', x: 1100, y: 300 });
    const b = await post(`/whiteboard/boards/${board.id}/place`, { builtin: 'drawio-flowchart/process', x: 1100, y: 540 });
    out.placed = [Object.keys(a), Object.keys(b)];
    const sk = (x) => (x.sketches || [])[0];
    const sa = sk(a), sb = sk(b);
    out.ids = [sa && sa.id, sb && sb.id];
    if (sa && sb) {
      const made = await post('/whiteboard/sketches', { data: JSON.stringify({ type: 'link-elbow', route: 'elbow', sourceId: sa.id, sourceKind: 'sketch', sourceAnchor: { x: 0.5, y: 1 }, targetId: sb.id, targetKind: 'sketch', targetAnchor: { x: 0.5, y: 0 }, width: 2, endCap: 'arrow', label: 'yes' }), x: 0, y: 0, z: 3, board_id: board.id });
      out.link = made.id;
    }
    const tree = await apiJson(`/whiteboard/?board_id=${map.id}`);
    const nodes = (tree.objects || []).map((o) => ({ ...o, data: typeof o.data === 'string' ? JSON.parse(o.data) : o.data }));
    out.n = nodes.length;
    const deco = [
      { markers: ['star'], priority: 1, progress: 50, flag: true },
      { labels: ['alpha', 'beta'], callout: 'A callout bubble' },
      { due: '2026-10-30', task: 'open', note: 'A note behind this topic' },
      { task: 'done', stamps: { up: 3, heart: 1 } },
      { boundary: 'rounded', boundary_label: 'Boundary words' },
      { summary: 'A summary', summary_span: 2, edge_label: 'edge words' },
    ];
    let i = 0;
    for (const n of nodes.filter((x) => x.parent_id)) {
      const d = deco[i++ % deco.length];
      const res = await api(`/whiteboard/objects/${n.id}`, { method: 'PUT', body: JSON.stringify({ kind: 'topic', board_id: map.id, x: n.x, y: n.y, width: n.width, height: n.height, z: n.z, data: { ...n.data, ...d } }) }).catch((e) => ({ err: String(e) }));
      if (res.err) out.err = res.err;
    }
    return out;
  });
  console.log(JSON.stringify(r));
  await browser.close();
})();
