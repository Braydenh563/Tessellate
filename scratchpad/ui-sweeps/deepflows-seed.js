// Seed for deepflows.js: ~40 notes (some private, some with `---` property
// blocks, [[links]] including [[A|B]] aliases, tags), two documents, a board,
// a mind map and reminders. Plain fetch against the API, no browser.
//
//   BASE=http://127.0.0.1:8801 node scratchpad/ui-sweeps/deepflows-seed.js
//
// Sets the password first when the data dir is new (`/auth/setup` answers with
// the token), otherwise unlocks. deepflows.js runs it first; a notebook that
// already has the seeded board is left alone, so a second run adds nothing.
const BASE = process.env.BASE || 'http://127.0.0.1:8801';
const PW = 'testpassword123';

(async () => {
  const j = async (path, method = 'GET', body, token) => {
    const r = await fetch(BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json', ...(token ? { 'X-Auth-Token': token } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await r.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) { data = text; }
    if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${text.slice(0, 120)}`);
    return data;
  };
  const st = await j('/auth/status');
  const auth = st.setup_required
    ? await j('/auth/setup', 'POST', { password: PW })
    : await j('/auth/unlock', 'POST', { password: PW });
  const t = auth.token;
  const post = (p, b) => j(p, 'POST', b, t);
  //: Answer the ask-once "Download search by meaning?" question (No thanks): its toast
  //: stays up until answered and, on a phone, sits over the middle of Settings.
  await j('/preferences', 'PUT', { semantic_auto_install: false }, t);

  const titles = ['Alpha project', 'Beta review', 'Gamma ideas', 'Delta budget', 'Epsilon travel',
    'Zeta recipes', 'Eta reading', 'Theta fitness', 'Iota garden', 'Kappa finance'];
  const made = [];
  //: The CI data dir is shared by every sweep in a slice, so other notes are
  //: no sign of this seed: its board is.
  const boards = await j('/whiteboard/boards', 'GET', null, t);
  if ((Array.isArray(boards) ? boards : []).some((b) => b.title === 'Launch plan')) {
    console.log('deepflows seed already there');
    return;
  }
  for (let i = 0; i < 40; i++) {
    const name = i < titles.length ? titles[i] : `Plain note ${i}`;
    let content = `# ${name}\n\nBody text for ${name}, about topic ${i % 5}. Remember to follow up.`;
    if (i >= 1 && i < 12) content += `\n\nSee also [[${titles[i - 1]}]] and [[${titles[(i + 3) % 10]}|a friendly alias]].`;
    if (i % 7 === 3) content = `---\nstatus: active\npriority: ${i}\n---\n${content}`;
    const tags = [`topic${i % 5}`, ...(i % 3 === 0 ? ['work'] : []), ...(i % 4 === 0 ? ['personal'] : [])];
    const e = await post('/entries', { content, tags });
    made.push(e);
    if (i >= 36) await post(`/entries/${e.id}/privacy`, { private: true });
  }
  // A few explicit links so the graph has edges whatever the filer did.
  for (let i = 0; i < 8; i++) {
    try { await post(`/entries/${made[i].id}/links`, { target_id: made[i + 10].id, reason: 'seeded' }); } catch (e) { /* already linked */ }
  }
  await post('/documents', { title: 'Design system notes', content: '# Design system notes\n\nSurface tiers and the button ramp.\n\n## Rows\n\nTwo gaps.' });
  await post('/documents', { title: 'Trip plan', content: '# Trip plan\n\nFlights, hotel and a list of places to see.' });
  const board = await post('/whiteboard/boards', { name: 'Launch plan', type: 'board' });
  await post('/whiteboard/objects', { kind: 'text', board_id: board.id, x: 40, y: 40, width: 200, height: 100, data: { content: 'Backlog' } });
  const map = await post('/whiteboard/boards', { name: 'Bubble tea', type: 'map' });
  const root = await post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'topic', text: 'Bubble tea', x: 420, y: 300 });
  await post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'topic', text: 'Brewing', x: 120, y: 160, parent_id: root.id });
  await post(`/whiteboard/boards/${map.id}/nodes`, { kind: 'topic', text: 'Pearls', x: 760, y: 300, parent_id: root.id });
  await post('/reminders', { text: 'Send the weekly summary', due_at: new Date(Date.now() + 3600e3).toISOString() });
  await post('/reminders', { text: 'Water the plants', due_at: new Date(Date.now() + 5400e3).toISOString() });
  console.log(`seeded ${made.length} notes (4 private), 2 documents, board ${board.id}, map ${map.id}`);
})().catch((e) => { console.error('seed failed:', e.message); process.exit(1); });
