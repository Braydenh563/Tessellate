// The flows deepflows.js runs. Each is `async (env) => {...}` and throws on a
// broken expectation; page errors, bad responses and overflow are collected by
// the runner. See deepflows.js for the env fields.
const flows = {};

//: Poll `fn` (run in the page) until it returns something truthy, up to `ms`.
async function until(env, fn, arg, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) {
    const v = await env.js(fn, arg);
    if (v) return v;
    if (Date.now() > end) return null;
    await env.wait(250);
  }
}

//: A note made through the API, as a fixture for flows that are not about making one.
async function fixtureNote(env, text, extra = {}) {
  return env.js(async ([content, more]) => apiJson('/entries', { method: 'POST', body: JSON.stringify({ content, ...more }) }), [text, extra]);
}

//: Phone: the open note page goes back to the list.
async function closeNotePage(env) {
  const back = env.page.locator('.sheet-overlay[data-sheet="note"] .sheet-close');
  if (await back.count()) {
    await back.first().click();
    await env.wait(450);
  }
}

//: Press the dark confirm button of a confirmDialog (the one that is not Cancel).
async function confirmYes(env) {
  const yes = env.page.locator('.confirm-overlay .confirm-actions button:not(:has-text("Cancel"))').last();
  await yes.waitFor({ state: 'visible', timeout: 4000 });
  await yes.click();
  await env.wait(700);
}

//: A note's row in the Your notes list, by id.
const rowSel = (id) => `#entry-list > li[data-id="${id}"]`;

async function showNotesList(env) {
  await closeNotePage(env);
  await env.js(() => switchTab('notes'));
  await env.wait(500);
  await env.js(() => loadEntries());
  await env.js(() => document.querySelector('[data-section="browse"]')?.click());
  await env.wait(1200);
}

//: Save a new note the way a person does: New note, type, Save.
async function createNote(env, text) {
  await env.js(() => switchTab('notes'));
  await env.wait(400);
  if (await env.page.isVisible('#notes-new-note')) await env.page.click('#notes-new-note');
  else await env.js(() => startNewNote());
  await env.wait(900);
  env.at('click the capture box');
  await env.page.locator('#capture .cm-content').first().click({ timeout: 6000 });
  env.at('type the note');
  await env.page.keyboard.type(text);
  await env.page.click('#save-btn');
  const found = await until(env, async (s) => {
    const body = await apiJson('/entries?limit=10');
    const list = Array.isArray(body) ? body : body.entries || [];
    return list.find((e) => e.content.includes(s)) || null;
  }, text, 20000);
  if (!found) throw new Error('saved note never reached /entries');
  return found;
}

//: Open the row's "More actions" menu and press the item whose text contains `label`. Labels are
//: matched by prefix: a card's icon buttons end in the note's name (audit 1029 N17, entry-card.js).
async function rowMenu(env, id, label, group = null) {
  await openRow(env, id);
  await actionsOf(env, id).locator('button[aria-label^="More actions"]').first().click();
  await env.wait(250);
  if (group) {
    await env.page.locator('[role="menuitem"]:visible', { hasText: new RegExp(`^\\s*${group}\\s*›?\\s*$`) }).first().click();
    await env.wait(300);
  }
  const item = env.page.locator('[role="menuitem"]:visible', { hasText: label }).first();
  await item.waitFor({ state: 'visible', timeout: 4000 });
  await item.click();
  await env.wait(500);
}

//: Make a row's actions reachable. Desktop: click the card. Phone: the tap
//: opens the note as a page, whose actions are in the thumb bar.
async function openRow(env, id) {
  if (env.phone) {
    //: One page at a time: another note's page is put away first.
    const open = await env.page.$('.sheet-overlay[data-sheet="note"] .sheet-title, .sheet-overlay[data-sheet="note"] h2');
    if (open && !(await env.page.locator('.sheet-overlay[data-sheet="note"] .note-page-list > li').first().getAttribute('data-id').then((v) => v === String(id), () => false))) await closeNotePage(env);
    if (await env.page.$('.sheet-overlay[data-sheet="note"] .note-page-bar')) return;
    const li = env.page.locator(rowSel(id));
    await li.scrollIntoViewIfNeeded();
    await li.locator('.entry-content').first().tap({ position: { x: 20, y: 8 } });
    await env.page.waitForSelector('.sheet-overlay[data-sheet="note"] .note-page-bar', { timeout: 4000 });
    return;
  }
  const li = env.page.locator(rowSel(id));
  await li.scrollIntoViewIfNeeded();
  if (!(await li.locator('button[aria-label^="More actions"]').first().isVisible().catch(() => false))) {
    await li.locator('.entry-content').first().click({ position: { x: 20, y: 8 } });
    await env.wait(500);
  }
}

//: Where a note's own action buttons are: on its row, or in the phone page's bar.
const actionsOf = (env, id) => env.page.locator(env.phone ? '.sheet-overlay[data-sheet="note"] .note-page-bar' : rowSel(id));

flows.note = async (env) => {
  const text = `Deep flow note ${env.STAMP}${env.width} ${env.theme}`;
  const made = await createNote(env, text);
  env.at('find the new note in the list');
  await showNotesList(env);
  if (!(await env.page.isVisible(rowSel(made.id)))) throw new Error('new note is not in the list');
  await env.overflow('list with the new note');
  env.at('open the row and press Edit');
  await openRow(env, made.id);
  await actionsOf(env, made.id).locator('button[aria-label^="Edit this entry"]').first().click();
  await env.wait(800);
  await env.overflow('edit form');
  env.at('type into the edit form');
  const edited = `${text} EDITED`;
  const surface = env.page.locator('#entry-list .note-edit-box ~ .cm-editor .cm-content, #entry-list li .cm-content').first();
  if (await surface.count()) {
    await surface.click();
    await env.page.keyboard.press('End');
    await env.page.keyboard.type(' EDITED');
  } else {
    await env.page.locator('#entry-edit-content').fill(edited);
  }
  await env.wait(400);
  //: Home inside the tags box moves the caret in the box (the notes list used to take
  //: it for "go to the first note" and move the focus away).
  env.at('Home in the tags box');
  const tagsBox = env.page.locator('#entry-list .note-edit-tag-input').first();
  await tagsBox.click();
  await env.page.keyboard.type('ab');
  await env.page.keyboard.press('Home');
  await env.page.keyboard.type('X');
  const tagsNow = await tagsBox.inputValue();
  if (!tagsNow.startsWith('Xab')) throw new Error(`Home in the tags box did not move the caret: ${JSON.stringify(tagsNow)}`);
  await tagsBox.fill('');
  env.at('Save changes');
  await env.page.locator('#entry-list button:has-text("Save changes")').first().click();
  await env.wait(1200);
  const after = await env.js(async (id) => (await apiJson(`/entries/${id}`)).content, made.id);
  if (!after.includes('EDITED')) throw new Error(`edit did not save: ${after.slice(0, 80)}`);
  env.at('Move to bin');
  // Delete: bin, then Undo from the toast restores it.
  await showNotesList(env);
  await rowMenu(env, made.id, 'Move to bin');
  await env.wait(900);
  //: A binned note answers 404 on its own route (the bin is read through the
  //: Library), so the 404 is the expected sign and the flow says so.
  env.expect(404, `/entries/${made.id}`);
  const live = (id) => env.js(async (i) => { const r = await fetch(`/entries/${i}`, { headers: { 'X-Auth-Token': authToken() } }); return r.status === 200; }, id);
  if (await live(made.id)) throw new Error('after Move to bin the note is still live');
  await env.overflow('after bin');
  env.at('Undo');
  await env.page.getByRole('button', { name: 'Undo' }).first().click();
  await env.wait(1200);
  if (!(await live(made.id))) throw new Error('Undo did not restore the note');
  // Bin it again, and bring it back from the Library's Bin.
  env.at('restore from the Library bin');
  await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); }, made.id);
  await env.js(() => switchTab('library'));
  await env.wait(1200);
  //: The list is still loading for a moment after the tab opens, and a press
  //: on a chip while it redraws can be lost: press until the Bin chip is on.
  for (let tries = 0; tries < 6; tries++) {
    await env.page.locator('#tab-library .library-chip', { hasText: /^Bin\s*\d/ }).first().click();
    await env.wait(700);
    if (await env.page.locator('#tab-library .library-chip.active', { hasText: /^Bin/ }).count()) break;
  }
  await env.page.locator(`#tab-library button[aria-label^="Actions for ${text.slice(0, 30)}"]`).first().click();
  await env.page.locator('[role="menuitem"]:visible', { hasText: 'Restore' }).first().click();
  await env.wait(1200);
  if (!(await live(made.id))) throw new Error('Restore in the Library bin did not bring the note back');
  await env.overflow('library bin');
  // Clean up behind ourselves: gone for good, so nothing sits in the bin.
  await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); }, made.id);
};

flows.private = async (env) => {
  const made = await fixtureNote(env, `Private flow ${env.STAMP}${env.width}${env.theme} secret text`);
  await showNotesList(env);
  env.at('Make private');
  await rowMenu(env, made.id, 'Make private');
  await confirmYes(env);
  await env.wait(800);
  let now = await env.js(async (id) => (await apiJson(`/entries/${id}`)).is_private, made.id);
  if (!now) throw new Error('note is not private after Make private');
  await showNotesList(env);
  const chip = await env.page.locator(`${rowSel(made.id)} >> text=/^\\s*private/`).count();
  if (!chip) throw new Error('the row has no private chip');
  await env.overflow('a private row');
  env.at('Make readable');
  await rowMenu(env, made.id, 'Make readable');
  await env.wait(900);
  now = await env.js(async (id) => (await apiJson(`/entries/${id}`)).is_private, made.id);
  if (now) throw new Error('note is still private after Make readable');
  const text = await env.js(async (id) => (await apiJson(`/entries/${id}`)).content, made.id);
  if (!text.includes('secret text')) throw new Error(`the text did not survive the round trip: ${text.slice(0, 60)}`);
  await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); }, made.id);
};

flows.link = async (env) => {
  const a = await fixtureNote(env, `Link flow A ${env.STAMP}${env.width}${env.theme}`);
  const b = await fixtureNote(env, `Link flow B ${env.STAMP}${env.width}${env.theme}`);
  await showNotesList(env);
  env.at('Link to another on A');
  await rowMenu(env, a.id, 'Link to another', 'Connect');
  await showNotesList(env);
  env.at('Link to another on B');
  await rowMenu(env, b.id, 'Link to another', 'Connect');
  await env.wait(1200);
  const links = await env.js(async (id) => (await apiJson(`/entries/${id}`)).links.map((l) => l.entry_id), a.id);
  if (!links.includes(b.id)) throw new Error(`A is not linked to B: ${JSON.stringify(links)}`);
  await showNotesList(env);
  await env.overflow('linked rows');
  // A [[wiki link]] typed in a note makes a link too, and an aliased one draws its shown words.
  const c = await fixtureNote(env, `Link flow C ${env.STAMP}${env.width}${env.theme} points at [[Link flow B ${env.STAMP}${env.width}${env.theme}|the second one]]`);
  await showNotesList(env);
  const label = await env.js((id) => document.querySelector(`#entry-list > li[data-id="${id}"] .wiki-link`)?.textContent || null, c.id);
  if (label !== 'the second one') throw new Error(`an aliased [[A|B]] link draws "${label}", not "the second one"`);
  const cLinks = await env.js(async (id) => (await apiJson(`/entries/${id}`)).links.map((l) => l.entry_id), c.id);
  if (!cLinks.includes(b.id)) throw new Error('the [[wiki|alias]] link was not stored');
  for (const n of [a, b, c]) await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); }, n.id);
};

//: Where a graph node, or the middle of a link, is on the screen. Read from the
//: canvas's own state (`gcTab`, graph-canvas.js) so the click goes through the
//: same hit-test a person's does.
const graphPoints = () => {
  const s = gcTab;
  const r = s.canvas.getBoundingClientRect();
  const t = s.transform || d3.zoomIdentity;
  const onScreen = ([x, y]) => x > r.left + 20 && x < r.right - 20 && y > r.top + 20 && y < r.bottom - 20;
  const screen = (x, y) => { const p = t.apply([x, y]); return [r.left + p[0], r.top + p[1]]; };
  const world = ([sx, sy]) => t.invert([sx - r.left, sy - r.top]);
  const nodes = s.nodes.filter((n) => Number.isFinite(n.x) && onScreen(screen(n.x, n.y)) && (n.degree || 0) > 0)
    .sort((a, b) => (b.degree || 0) - (a.degree || 0));
  let node = null;
  for (const n of nodes) {
    const [sx, sy] = screen(n.x, n.y);
    const w = world([sx, sy]);
    if (gcRequestDraw.inspect.gcNodeAtWorld(w[0], w[1], s) === n) { node = { id: n.id, x: sx, y: sy, preview: n.preview }; break; }
  }
  let link = null;
  for (const e of s.edges) {
    if (e.kind !== 'link' || !e.source || !e.target || !Number.isFinite(e.source.x)) continue;
    const a = e.source; const b = e.target;
    const curved = !s.tree && gcRequestDraw.inspect.gcCurvedLinks(s);
    let mx = (a.x + b.x) / 2; let my = (a.y + b.y) / 2;
    if (curved) { const c = gcRequestDraw.inspect.gcBowPoint(a, b); mx = 0.25 * a.x + 0.5 * c.x + 0.25 * b.x; my = 0.25 * a.y + 0.5 * c.y + 0.25 * b.y; }
    const sp = screen(mx, my);
    if (!onScreen(sp)) continue;
    const w = world(sp);
    if (gcRequestDraw.inspect.gcNodeAtWorld(w[0], w[1], s)) continue;
    if (gcRequestDraw.inspect.gcEdgeAtWorld(w[0], w[1], s) === e) { link = { x: sp[0], y: sp[1], a: a.id, b: b.id }; break; }
  }
  return { node, link, total: s.nodes.length, edges: s.edges.length };
};

flows.graph = async (env) => {
  await env.js(() => switchTab('graph'));
  env.at('wait for the graph to draw');
  const ready = await until(env, () => typeof gcTab !== 'undefined' && gcTab.nodes && gcTab.nodes.length > 5 && gcTab.canvas.width > 0, null, 15000);
  if (!ready) throw new Error('the graph never drew nodes');
  await env.wait(3000); // let the layout settle
  await env.overflow('graph');
  let pts = await env.js(graphPoints);
  if (!pts.node) throw new Error(`no clickable node among ${pts.total}`);
  env.at('click a node');
  await env.page.mouse.click(pts.node.x, pts.node.y);
  await env.wait(900);
  const popup = await env.js(() => typeof graphPopupId !== 'undefined' ? graphPopupId : null);
  if (popup == null) throw new Error(`clicking node ${pts.node.id} (${pts.node.preview}) opened no popup`);
  await env.overflow('node popup');
  await env.page.keyboard.press('Escape');
  await env.wait(500);
  pts = await env.js(graphPoints);
  if (!pts.link) throw new Error(`no clickable link among ${pts.edges} edges`);
  env.at('click a link');
  await env.page.mouse.click(pts.link.x, pts.link.y);
  await env.wait(700);
  if (!(await env.page.$('#graph-link-peek'))) throw new Error('clicking a link opened no peek');
  await env.overflow('link peek');
  await env.page.keyboard.press('Escape');
  await env.wait(300);
};

//: Library > Boards & maps, then open the board called `title`.
async function openBoardByTitle(env, title) {
  await env.js(() => switchTab('library'));
  await env.wait(900);
  await env.js(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await env.wait(1500);
  await env.page.locator('#library-view-whiteboard').getByText(title, { exact: true }).first().click();
  await env.page.waitForSelector('#wb-back-to-boards', { state: 'visible', timeout: 8000 });
  await env.wait(1500);
}

const boardId = (env, title) => env.js(async (t) => (await apiJson('/whiteboard/boards')).find((b) => b.title === t)?.id, title);

flows.mindmap = async (env) => {
  const id = await boardId(env, 'Bubble tea');
  if (!id) throw new Error('the seeded map is missing (run deepflows-seed.js)');
  const flat = (i) => env.js(async (b) => {
    const out = [];
    const walk = (list) => { for (const n of list || []) { out.push(n); walk(n.children); } };
    walk((await apiJson(`/whiteboard/boards/${b}/tree`)).roots);
    return out.map((n) => ({ id: n.id, text: n.text }));
  }, i);
  const count = async () => (await flat(id)).length;
  const before = await count();
  env.at('open the map');
  await openBoardByTitle(env, 'Bubble tea');
  await env.overflow('map open');
  env.at('select the root topic');
  await env.page.locator('.wb-map-node, [data-map-node], .wb-card').filter({ hasText: /^Bubble tea/ }).first().click({ position: { x: 20, y: 10 } });
  await env.wait(700);
  env.at('Add a child topic');
  const add = env.page.locator('button[aria-label="Add a child topic"]:visible').first();
  await add.click();
  await env.wait(700);
  //: Home and the arrows belong to the text while a topic is being typed, not to the map.
  //: Short, so it stays on one visual line: Home goes to the start of the
  //: visual line, and a long stamp wraps in a narrow topic.
  await env.page.keyboard.type('opic');
  await env.page.keyboard.press('Home');
  await env.page.keyboard.type('T');
  await env.page.keyboard.press('End');
  await env.page.keyboard.type(` ${env.STAMP}${env.width}${env.theme}`);
  //: Enter is a new line in a name (the owner, 2026-10-10); Escape keeps it.
  await env.page.keyboard.press('Escape');
  await env.wait(1500);
  const after = await count();
  if (after !== before + 1) throw new Error(`the map has ${after} topics, wanted ${before + 1}`);
  const typed = (await flat(id)).find((n) => /^T?opic df/.test(n.text || ''));
  if (!typed || !(typed.text || '').startsWith(`Topic ${env.STAMP}`)) throw new Error(`Home inside a topic's text did not move the caret: the topic reads ${JSON.stringify(typed && typed.text)}`);
  await env.overflow('after adding a topic');
  // Leave the map as found.
  const added = (await flat(id)).filter((n) => /^Topic df/.test(n.text || '')).map((n) => n.id);
  for (const nid of added) await env.js(async (n) => { await api(`/whiteboard/objects/${n}`, { method: 'DELETE' }); }, nid);
  await env.js(() => document.getElementById('wb-back-to-boards')?.click());
  await env.wait(500);
};

flows.whiteboard = async (env) => {
  const id = await boardId(env, 'Launch plan');
  if (!id) throw new Error('the seeded board is missing (run deepflows-seed.js)');
  const objects = (i) => env.js(async (b) => (await apiJson(`/whiteboard/?board_id=${b}`)).objects.map((o) => ({ id: o.id, kind: o.kind, data: o.data })), i);
  //: A sticky an earlier, failed run left on the board goes first.
  for (const stray of (await objects(id)).filter((o) => /S?ticky df\d/.test(JSON.stringify(o.data)))) {
    await env.js(async (n) => { await api(`/whiteboard/objects/${n}`, { method: 'DELETE' }); }, stray.id);
  }
  const before = await objects(id);
  env.at('open the board');
  await openBoardByTitle(env, 'Launch plan');
  await env.overflow('board open');
  env.at('Insert > Sticky note');
  await env.page.locator('button[title="Add something to the board"]:visible').first().click();
  await env.page.locator('[role="menuitem"]:visible', { hasText: 'Sticky note' }).first().click();
  await env.wait(400);
  const stage = await env.page.locator('#wb-stage, #whiteboard-stage, .wb-stage, #wb-canvas').first().boundingBox().catch(() => null);
  const x = stage ? stage.x + stage.width * 0.55 : env.width * 0.55;
  const y = stage ? stage.y + stage.height * 0.5 : 400;
  env.at('click the canvas to drop the sticky');
  await env.page.mouse.click(x, y);
  await env.wait(700);
  await env.page.keyboard.type(`ticky ${env.STAMP}${env.width}${env.theme}`);
  //: Ctrl+Home, not Home: the text wraps in a sticky, and Home is the start of the line shown.
  await env.page.keyboard.press('Control+Home');
  await env.page.keyboard.type('S');
  await env.page.keyboard.press('Escape');
  await env.wait(1500);
  const after = await objects(id);
  const made = after.filter((o) => !before.some((b) => b.id === o.id));
  if (made.length !== 1) throw new Error(`wanted one new object, found ${made.length}: ${JSON.stringify(made).slice(0, 160)}`);
  if (!JSON.stringify(made[0].data).includes(`Sticky ${env.STAMP}`)) throw new Error(`the sticky holds no text: ${JSON.stringify(made[0]).slice(0, 160)}`);
  await env.overflow('sticky placed');
  for (const o of made) await env.js(async (n) => { await api(`/whiteboard/objects/${n}`, { method: 'DELETE' }); }, o.id);
  await env.js(() => document.getElementById('wb-back-to-boards')?.click());
  await env.wait(500);
};

flows.document = async (env) => {
  const original = '# Trip plan\n\nFlights, hotel and a list of places to see.';
  const doc = await env.js(async () => (await apiJson('/documents')).find((d) => d.title === 'Trip plan'));
  if (!doc) throw new Error('the seeded document is missing (run deepflows-seed.js)');
  const restore = () => env.js(async ([id, text]) => { await api(`/documents/${id}`, { method: 'PUT', body: JSON.stringify({ title: 'Trip plan', content: text }) }); }, [doc.id, original]);
  const content = () => env.js(async (id) => (await apiJson(`/documents/${id}`)).content, doc.id);
  try {
    env.at('open the document');
    await env.js(() => switchTab('library'));
    await env.wait(900);
    await env.js(() => document.querySelector('#library-subtabs [data-target="library-view-docs"]')?.click());
    await env.wait(1500);
    await env.page.locator('#library-view-docs').getByText('Trip plan', { exact: true }).first().click();
    //: A phone opens a document to read it; Edit is one press away.
    await env.page.waitForSelector('#doc-back', { state: 'visible', timeout: 8000 });
    await env.wait(1000);
    if (!(await env.page.isVisible('#tab-documents .cm-content'))) {
      await env.page.locator('button[title="Edit the document"]:visible').first().click();
    }
    await env.page.waitForSelector('#tab-documents .cm-content', { state: 'visible', timeout: 8000 });
    await env.wait(800);
    await env.overflow('document open');
    env.at('type into the document');
    await env.page.locator('#tab-documents .cm-content').first().click();
    await env.page.keyboard.press('Control+End');
    await env.page.keyboard.type(` Typed ${env.STAMP}${env.width}${env.theme}. See [[Alpha project|the alpha note]] for more.`);
    env.at('add a properties block');
    await env.page.keyboard.press('Control+Home');
    await env.page.keyboard.type('---\nstatus: draft\n---\n');
    await env.page.waitForSelector('.doc-props input.doc-prop-input', { state: 'visible', timeout: 5000 });
    await env.overflow('properties panel');
    env.at('set the property');
    const field = env.page.locator('.doc-props input.doc-prop-input:not(.doc-prop-new-input)').first();
    await field.fill('done');
    await field.press('Enter');
    await env.wait(2500); // autosave
    const text = await content();
    if (!/status:\s*done/.test(text)) throw new Error(`the property did not reach the file: ${JSON.stringify(text.slice(0, 60))}`);
    if (!text.includes(`Typed ${env.STAMP}${env.width}${env.theme}.`)) throw new Error('typed text did not save');
    //: An aliased [[A|B]] link draws B in the live view (the caret is off its
    //: line, so the brackets and target are hidden) and in the Read view.
    env.at('the [[A|B]] link in the live view');
    await env.page.locator('#tab-documents .cm-content').first().click();
    await env.page.keyboard.press('Control+Home');
    await env.page.keyboard.press('Control+Home');
    await env.wait(400);
    const live = await env.js(() => [...document.querySelectorAll('#tab-documents .cm-md-wiki')].map((e) => e.textContent));
    if (!live.includes('the alpha note')) throw new Error(`the live view draws the aliased link as ${JSON.stringify(live)}`);
    env.at('the [[A|B]] link in the Read view');
    await env.page.locator('button[title^="The finished document on its own"]:visible').first().click();
    await env.wait(800);
    const read = await env.js(() => [...document.querySelectorAll('#tab-documents .wiki-link')].map((e) => e.textContent));
    if (!read.includes('the alpha note')) throw new Error(`the Read view draws the aliased link as ${JSON.stringify(read)}`);
    await env.overflow('document read view');
    // Back to the list through the document's own back button.
    await env.js(() => document.getElementById('doc-back')?.click());
    await env.wait(600);
  } finally {
    await restore();
  }
};

//: No model is connected in the sandbox, so the answer is the graceful one: the
//: notes' own words and a way to connect a model, never an error.
flows.ask = async (env) => {
  await env.js(() => switchTab('notes'));
  await env.wait(600);
  await env.js(() => document.querySelector('[data-section="ask"]')?.click());
  await env.wait(900);
  env.at('type the question');
  await env.page.fill('#question', 'What is in Alpha project?');
  await env.page.press('#question', 'Enter');
  env.at('wait for the answer');
  const answer = await until(env, () => {
    const t = document.querySelector('#ai-answer')?.innerText || '';
    return t.trim().length > 30 && !/Searching your notes|Stargazing/.test(t) ? t : null;
  }, null, 20000);
  if (!answer) throw new Error('no answer was drawn');
  //: With no model the composer answers from the notes' own sentences (it no
  //: longer announces the missing model in the answer itself).
  if (!/Alpha project|Body text|no model|isn.t running|not running|not connected/i.test(answer)) throw new Error(`the no-model answer neither quotes the note nor says why: ${answer.slice(0, 120)}`);
  if (/error|traceback|undefined|\[object/i.test(answer)) throw new Error(`the answer carries a raw error: ${answer.slice(0, 160)}`);
  await env.overflow('ask answer');
  const connect = await env.page.locator('button:has-text("Connect a model")').count();
  if (!connect) throw new Error('the no-model state offers no way to connect one');
};

flows.notifications = async (env) => {
  const k = `${env.STAMP}${env.width}${env.theme}`;
  await env.js(([key]) => {
    recordNotification({ kind: 'job', title: `Sweep one ${key}`, detail: 'first', key: `sweep:${key}:1` });
    recordNotification({ kind: 'job', title: `Sweep two ${key}`, detail: 'second', key: `sweep:${key}:2` });
  }, [k]);
  env.at('open the bell');
  await env.page.locator('#notif-btn').click();
  await env.page.waitForSelector('#notif-panel:not(.hidden)', { timeout: 4000 });
  await env.wait(500);
  const rows = () => env.js((key) => [...document.querySelectorAll('#notif-list > li')].filter((li) => li.textContent.includes(key)).length, k);
  if ((await rows()) !== 2) throw new Error(`the panel shows ${await rows()} of the 2 notifications`);
  await env.overflow('notifications panel');
  env.at('remove one');
  //: The row's remove button is revealed by pointing at the row (always there on touch).
  await env.page.locator(`#notif-list > li:has-text("Sweep one ${k}")`).hover();
  await env.page.locator(`#notif-panel button[aria-label="Remove: Sweep one ${k}"]`).click();
  await env.wait(500);
  if ((await rows()) !== 1) throw new Error('Remove did not take the row out');
  const stored = await env.js((key) => storedNotifications().filter((n) => String(n.title).includes(key)).map((n) => n.title), k);
  if (stored.length !== 1 || !stored[0].includes('two')) throw new Error(`the wrong one is left in storage: ${JSON.stringify(stored)}`);
  env.at('mark the other read');
  await env.page.locator(`#notif-list > li:has-text("${k}")`).first().hover();
  await env.page.locator(`#notif-list > li:has-text("${k}") button.notif-read-toggle`).first().click();
  await env.wait(400);
  env.at('close the panel');
  await env.page.locator('#notif-close').click();
  await env.wait(400);
  if (await env.page.isVisible('#notif-panel')) throw new Error('the panel did not close');
  await env.js((key) => { for (const n of storedNotifications().filter((x) => String(x.title).includes(key))) dismissNotification(n); }, k);
};

//: The dashboard on a notebook with properties and private notes: every widget
//: draws, none prints a `---` block as a note's words.
flows.dashboard = async (env) => {
  await env.js(() => switchTab('dashboard'));
  await env.wait(3500);
  const bad = await env.js(() => [...document.querySelectorAll('#tab-dashboard .dash-list-text, #tab-dashboard .random-note, #tab-dashboard .dash-list li')]
    .map((e) => e.innerText.trim()).filter((t) => /^---|status: active|priority: \d+/.test(t)).slice(0, 2));
  if (bad.length) throw new Error(`the dashboard prints a properties block as words: ${JSON.stringify(bad).slice(0, 160)}`);
  await env.overflow('dashboard');
};

//: A full reload, then back in the way `lib.js` boots: the lock field when the
//: app asks, otherwise straight to the app.
async function reloadApp(env) {
  await env.page.reload({ waitUntil: 'domcontentloaded' });
  const way = await (await env.page.waitForFunction(() => {
    const field = document.getElementById('lock-password');
    const overlay = document.getElementById('lock-overlay');
    const splash = document.getElementById('boot-splash');
    if (field && overlay && !overlay.classList.contains('hidden') && field.offsetParent !== null) return 'lock';
    const settled = !splash || splash.classList.contains('hidden');
    if (settled && overlay && overlay.classList.contains('hidden') && localStorage.getItem('token')) return 'app';
    return false;
  }, null, { timeout: 20000, polling: 100 })).jsonValue();
  if (way === 'lock') {
    await env.page.fill('#lock-password', 'testpassword123');
    await env.page.click('#lock-submit');
  }
  await env.wait(2500);
  await env.js(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
}

//: Settings sections, in nav order, from the nav itself.
const settingsSections = (env) => env.js(() => [...document.querySelectorAll('#settings-nav button[data-section]')].map((b) => b.dataset.section));

//: Go to a section the way the screen offers it: the nav on a desktop, the
//: "Jump to a settings section" menu on a phone.
async function goSettings(env, name) {
  if (env.phone) await env.page.selectOption('#settings-jump', name);
  else await env.page.locator(`#settings-nav button[data-section="${name}"]`).click();
  await env.wait(450);
  //: A section that loads its values from the server (Profile, General) shows
  //: the form's defaults until the answer lands. Wait until what the switches
  //: say stops changing, or a run reads defaults as the notebook's own state
  //: (it did, and left three preferences switched on).
  let last = null;
  for (let tries = 0; tries < 10; tries++) {
    const now = JSON.stringify((await switchesHere(env)).map((s) => [s.i, s.on]));
    if (now === last) break;
    last = now;
    await env.wait(350);
  }
}

async function openSettingsByGear(env) {
  await env.reset();
  if (env.phone) await env.js(() => openSettingsModal());
  else await env.page.click('#settings-btn');
  await env.page.waitForSelector('#settings-modal:not(.hidden)', { timeout: 5000 });
  await env.wait(700);
}

//: What the sweep leaves alone, and why: turning these changes how the app is
//: reached or what it does to the machine, not how it looks or behaves for the
//: person at the screen. Simple mode (`pref-simple-mode`) hides whole sections, so the read-back
//: and put-back could not reach What it learned behind it; tests/test_usage_ledger.py covers it.
const SETTINGS_SKIP = /pref-simple-mode|password when the app opens|other devices on this network|newer version|Update automatically|newest changes|SearXNG|autonomous optimization/i;

//: Every switch visible in the current section: its index, label and state.
const switchesHere = (env) => env.js(() => [...document.querySelectorAll('#settings-modal input[type="checkbox"]')]
  .map((c, i) => ({ c, i }))
  .filter(({ c }) => {
    if (c.disabled) return false;
    //: A row's selection tick (Extras' `.select-check`, settings-packages.js) picks rows for the
    //: bar's actions; it is not a preference and is not meant to outlive a reload.
    if (c.classList.contains('select-check')) return false;
    const label = c.closest('label') || c;
    //: Reachable the way a person reaches it: it has a box, and what is at its
    //: middle is it (a switch in a closed fold, or under another panel, is not).
    label.scrollIntoView({ block: 'nearest' });
    const r = label.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const hit = document.elementFromPoint(r.x + Math.min(r.width / 2, 120), r.y + r.height / 2);
    return Boolean(hit && label.contains(hit));
  })
  .map(({ c, i }) => ({
    i,
    id: c.id || '',
    label: ((c.closest('label') || c.parentElement).textContent || '').trim().replace(/\s+/g, ' ').slice(0, 70),
    on: c.checked,
  }))
  //: `i` is the index among every checkbox in the modal, and it moves when a
  //: list elsewhere (the tools, the skills) has or has not drawn yet: after a
  //: reload it is not the number it was. A switch is found again by its words
  //: and which of the same words it is in its section (`nth`).
  .map((sw, k, all) => ({ ...sw, nth: all.slice(0, k).filter((o) => o.label === sw.label).length })));

//: The switch a `toggled` record means, in a fresh listing.
//: A label may carry a live count ("Hide models too big for this computer (3 hidden)",
//: settings-models.js) that the press itself changes: compare without it.
const bareLabel = (s) => s.replace(/\s*\([^()]*\)\s*$/, '');
const findSw = (here, t) => here.filter((x) => bareLabel(x.label) === bareLabel(t.label))[t.nth];
//: A list drawn from the server (the tools, the skills) can still be empty when the section's
//: switches first read as settled: look again for up to three seconds before calling it gone.
async function findSwSoon(env, t, here) {
  for (let tries = 0; tries < 6; tries++) {
    const sw = findSw(here || (await switchesHere(env)), t);
    if (sw) return sw;
    here = null;
    await env.wait(500);
  }
  return null;
}

async function clickSwitch(env, index) {
  const handle = await env.page.evaluateHandle((i) => {
    const c = document.querySelectorAll('#settings-modal input[type="checkbox"]')[i];
    return c.closest('label') || c;
  }, index);
  await handle.asElement().click({ timeout: 4000 });
}

//: Press back every switch the run pressed (`toggled`: { section, i, id, label, was }).
//: Last pressed, first put back: a switch that turns another off or greys it out (a tool
//: another tool needs) is undone before the one it held.
async function putBack(env, sections, toggled) {
  for (const section of [...sections].reverse()) {
    const mine = toggled.filter((t) => t.section === section).reverse();
    if (!mine.length) continue;
    await goSettings(env, section);
    for (const t of mine) {
      const sw = await findSwSoon(env, t);
      if (!sw) throw new Error(`cannot find "${t.label.slice(0, 40)}" in ${section} to put it back`);
      if (sw.on !== t.was) { await clickSwitch(env, sw.i); await env.wait(120); }
    }
  }
}

//: A failed run still puts the notebook back as it found it.
flows.settings = async (env) => {
  const toggled = [];
  try {
    await settingsBody(env, toggled);
  } catch (e) {
    try {
      await openSettingsByGear(env);
      await putBack(env, await settingsSections(env), toggled);
      await env.wait(2000);
    } catch (again) { /* the first failure is the one worth reading */ }
    throw e;
  }
};

async function settingsBody(env, toggled) {
  await openSettingsByGear(env);
  const sections = await settingsSections(env);
  const skipped = [];
  env.at('toggle every switch');
  for (const section of sections) {
    await goSettings(env, section);
    //: A fold's heading row holds its words, chevron and '?' (nothing sticking out of the summary).
    const spill = await env.js(() => [...document.querySelectorAll('#settings-modal summary')].filter((s) => s.offsetParent).map((s) => {
      const sr = s.getBoundingClientRect();
      const worst = [...s.querySelectorAll('*')].filter((e) => e.offsetParent).reduce((m, e) => { const r = e.getBoundingClientRect(); return Math.max(m, r.bottom - sr.bottom, sr.top - r.top); }, 0);
      return { text: s.textContent.trim().replace(/\s+/g, ' ').slice(0, 40), spill: Math.round(worst) };
    }).filter((x) => x.spill > 2));
    for (const s of spill) env.report(`settings ${section}: the fold "${s.text}" has content ${s.spill}px outside its heading row`);
    const here = await switchesHere(env);
    for (const sw of here) {
      if (SETTINGS_SKIP.test(`${sw.id} ${sw.label}`)) { skipped.push(`${section}: ${sw.label.slice(0, 40)}`); continue; }
      //: An earlier switch can switch this one off ("Pause all learning").
      if (!(await switchesHere(env)).some((x) => x.i === sw.i)) { skipped.push(`${section}: ${sw.label.slice(0, 40)} (turned off by another)`); continue; }
      try { await clickSwitch(env, sw.i); } catch (e) { throw new Error(`could not press "${sw.label}" in ${section}: ${String(e.message).split('\n')[0]}`); }
      await env.wait(150);
      //: A switch that asks first (a dialog) is answered No: it is not a plain preference.
      const asked = await env.page.locator('.confirm-overlay:visible').count();
      if (asked) {
        await env.page.locator('.confirm-overlay .confirm-actions button:has-text("Cancel")').first().click();
        await env.wait(300);
        skipped.push(`${section}: ${sw.label.slice(0, 40)} (asks first)`);
        continue;
      }
      const now = (await switchesHere(env)).find((x) => x.i === sw.i);
      if (!now || now.on === sw.on) throw new Error(`pressing "${sw.label}" in ${section} did not change it`);
      toggled.push({ section, i: sw.i, id: sw.id, label: sw.label, nth: sw.nth, was: sw.on });
    }
  }
  await env.overflow('settings after toggling');
  env.at('reload and read them back');
  await env.wait(2500); // the autosave is debounced
  await reloadApp(env);
  await openSettingsByGear(env);
  const lost = [];
  const absent = [];
  for (const section of sections) {
    const mine = toggled.filter((t) => t.section === section);
    if (!mine.length) continue;
    await goSettings(env, section);
    const here = await switchesHere(env);
    for (const t of mine) {
      const sw = await findSwSoon(env, t, here);
      //: A switch another pressed switch withdraws (Pause all learning takes the memory tools out of
      //: /chat/tools) is absent here, not lost: the put-back below must find it, or it fails there.
      if (!sw) { absent.push(`${section}: ${t.label.slice(0, 30)}`); continue; }
      if (sw.on === t.was) lost.push(`${section}: "${t.label.slice(0, 40)}" went back to ${t.was ? 'on' : 'off'}`);
    }
  }
  // Put every one back, and read that back too.
  env.at('put them back');
  await putBack(env, sections, toggled);
  await env.wait(2500);
  await reloadApp(env);
  await openSettingsByGear(env);
  const stuck = [];
  for (const section of sections) {
    const mine = toggled.filter((t) => t.section === section);
    if (!mine.length) continue;
    await goSettings(env, section);
    const here = await switchesHere(env);
    for (const t of mine) {
      const sw = await findSwSoon(env, t, here);
      if (!sw || sw.on !== t.was) stuck.push(`${section}: "${t.label.slice(0, 40)}"${sw ? '' : ' (not found)'}`);
    }
  }
  if (absent.length) env.info(`settings: ${absent.length} withdrawn by another switch until put back (${absent.join('; ')})`);
  env.info(`settings: ${toggled.length} switches pressed, ${skipped.length} left alone (${skipped.slice(0, 8).join('; ')})`);
  if (lost.length || stuck.length) {
    throw new Error(`${lost.length} did not persist: ${lost.slice(0, process.env.DF_FULL ? 40 : 6).join(' | ')}${stuck.length ? `; ${stuck.length} would not go back: ${stuck.slice(0, 4).join(' | ')}` : ''}`);
  }
}

const activeTab = (env) => env.js(() => [...document.querySelectorAll('.tab-page')].filter((t) => !t.classList.contains('hidden')).map((t) => t.id.replace(/^tab-/, '')));

async function openPaletteUi(env) {
  if (!env.phone) await env.page.keyboard.press('Control+k');
  //: A phone has no Ctrl+K and no status bar, and nothing in its menus opens the command
  //: palette (the top bar's Find opens "Find anything", the search): a finding to report,
  //: so the flow opens it by its function there to cover the rest of it.
  else await env.js(() => openPalette());
  await env.page.waitForSelector('#palette-overlay:not(.hidden)', { timeout: 4000 });
  await env.wait(500);
}

flows.palette = async (env) => {
  env.at('open');
  await openPaletteUi(env);
  const rows = await env.js(() => document.querySelectorAll('#palette-list li').length);
  if (rows < 4) throw new Error(`the palette lists ${rows} rows with nothing typed`);
  if (!(await env.js(() => document.activeElement === document.getElementById('palette-input')))) throw new Error('the palette input is not focused on open');
  await env.overflow('palette open');
  env.at('find a note');
  await env.page.keyboard.type('Alpha project');
  await env.wait(900);
  const found = await env.js(() => [...document.querySelectorAll('#palette-list li')].some((li) => /Alpha project/.test(li.textContent)));
  if (!found) throw new Error('typing a note\'s title finds no row for it');
  await env.overflow('palette with results');
  env.at('run a command');
  await env.page.keyboard.press('Escape');
  await env.wait(400);
  if (await env.page.isVisible('#palette-overlay')) throw new Error('Escape did not close the palette');
  await openPaletteUi(env);
  await env.page.keyboard.type('go to graph');
  await env.wait(700);
  await env.page.keyboard.press('Enter');
  await env.wait(1200);
  if (await env.page.isVisible('#palette-overlay')) throw new Error('the palette stayed open after running a command');
  const tab = await activeTab(env);
  if (!tab.includes('graph')) throw new Error(`"Go to Graph" left the app on ${tab.join(',')}`);
  //: The palette does not search what you keep (INBOX 666): a typed title offers
  //: "Search everything for", and Enter there opens Find anything.
  env.at('hand a typed title to Find anything');
  await openPaletteUi(env);
  await env.page.keyboard.type('Alpha project');
  await env.wait(900);
  const typedRows = await env.js(() => [...document.querySelectorAll('#palette-overlay [role="option"]')].map((e) => e.textContent));
  if (!typedRows.some((t) => /Search everything for/.test(t))) throw new Error('the palette offers no way on to Find anything for a typed title');
};

flows.tabs = async (env) => {
  const names = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];
  const moreLabel = { dashboard: 'Dashboard', timeline: 'Timeline', reminders: 'Reminders' };
  if (env.phone) {
    const dock = await env.js(() => { const d = document.getElementById('phone-tab-dock').getBoundingClientRect(); return { bottom: d.bottom, h: innerHeight }; });
    if (Math.abs(dock.bottom - dock.h) > 1.5) throw new Error(`the tab bar is not pinned to the bottom: ends at ${dock.bottom} of ${dock.h}`);
  }
  for (const name of names) {
    env.at(`go to ${name}`);
    const button = env.page.locator(`#tab-bar [data-tab="${name}"]`);
    if (await button.isVisible()) {
      if (env.phone) {
        const box = await button.boundingBox();
        if (box.height < 44 || box.width < 44) throw new Error(`the ${name} tab is ${Math.round(box.width)}x${Math.round(box.height)}, under the 44px touch size`);
        await button.tap();
      } else await button.click();
    } else if (env.phone && moreLabel[name]) {
      await env.page.locator('#phone-more-btn').tap();
      await env.page.waitForSelector('.sheet-overlay', { timeout: 3000 });
      await env.page.locator('.sheet-overlay button', { hasText: moreLabel[name] }).first().tap();
      await env.wait(500);
    } else throw new Error(`no way to reach ${name}`);
    await env.wait(900);
    const shown = await activeTab(env);
    if (shown.length !== 1 || shown[0] !== name) throw new Error(`pressing ${name} shows ${JSON.stringify(shown)}`);
    if (await button.isVisible()) {
      const selected = await button.getAttribute('aria-selected');
      if (selected !== 'true') throw new Error(`the ${name} tab is not marked selected (aria-selected=${selected})`);
    }
    await env.overflow(name);
  }
};

//: The `[[` picker in the capture box offers the note being named first, even
//: when newer notes mention it, and Enter links to that one.
flows.picker = async (env) => {
  const tag = `Pickerz ${env.STAMP}${env.width}${env.theme}`;
  const made = [];
  made.push(await fixtureNote(env, `# ${tag}\n\nThe note being named.`));
  for (let i = 0; i < 8; i++) made.push(await fixtureNote(env, `# Mention ${i} ${env.STAMP}\n\nPoints at [[${tag}]] again.`));
  try {
    await env.js(() => switchTab('notes'));
    await env.wait(400);
    await env.js(() => loadEntries());
    await env.wait(900);
    await env.js(() => startNewNote());
    await env.wait(1000);
    await env.page.locator('#capture .cm-content').first().click();
    await env.page.keyboard.type(`See [[${tag.slice(0, 14)}`);
    env.at('the picker lists the note being named first');
    const pickerRow = () => { const row = [...document.querySelectorAll('.rich-picker-list li, [role="listbox"] [role="option"]')].filter((e) => e.offsetParent && !/^Notes$/.test(e.textContent.trim()))[0]; return row ? row.textContent.trim().replace(/\s+/g, ' ') : null; };
    const first = await until(env, pickerRow, null, 5000);
    if (!first || !first.includes(tag)) throw new Error(`the first row for [[${tag.slice(0, 14)} is "${first}", not the note by that name`);
    await env.overflow('picker open');
    await env.page.keyboard.press('Enter');
    await env.wait(500);
    const text = await env.js(() => document.querySelector('#capture .cm-content').textContent);
    if (!text.includes(tag)) throw new Error(`Enter linked to something else: ${JSON.stringify(text.slice(0, 80))}`);
  } finally {
    await env.page.keyboard.press('Control+a').catch(() => {});
    await env.page.keyboard.press('Delete').catch(() => {});
    for (const n of made) await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); }, n.id).catch(() => {});
  }
};

//: Select mode: a press on a note ticks it (and on a phone does not also open its
//: page), the bar counts them, and Tags adds a tag to every one.
flows.select = async (env) => {
  const tag = `swept${env.STAMP.slice(2)}${env.width}${env.theme}`;
  const a = await fixtureNote(env, `Select flow A ${env.STAMP}${env.width}${env.theme}`);
  const b = await fixtureNote(env, `Select flow B ${env.STAMP}${env.width}${env.theme}`);
  try {
    await showNotesList(env);
    env.at('Select');
    //: Folded into the dock's menu on a narrow dock (data-fold-narrow), so the
    //: page's own click reaches it whether it is a button or a menu row.
    await env.js(() => document.getElementById('select-btn').click());
    await env.wait(500);
    for (const n of [a, b]) {
      env.at(`tick note ${n.id}`);
      const row = env.page.locator(`${rowSel(n.id)} .entry-content`).first();
      await row.scrollIntoViewIfNeeded();
      if (env.phone) await row.tap({ position: { x: 30, y: 6 } });
      else await row.click({ position: { x: 30, y: 6 } });
      await env.wait(350);
      if (await env.page.$('.sheet-overlay[data-sheet="note"]')) throw new Error('a tap in Select mode opened the note page');
    }
    const count = await env.js(() => document.getElementById('batch-count').textContent);
    if (!/^2 selected/.test(count)) throw new Error(`the bar says "${count}" after ticking two notes`);
    await env.overflow('select bar');
    env.at('Tags for all');
    await env.page.locator('#batch-tag').click();
    const input = env.page.locator('input[placeholder^="Tags, separated"]').first();
    await input.waitFor({ state: 'visible', timeout: 4000 });
    await input.fill(tag);
    await env.overflow('batch tags sheet');
    await env.page.locator('button:has-text("Apply"):visible').first().click();
    await env.wait(1500);
    for (const n of [a, b]) {
      const tags = await env.js(async (id) => (await apiJson(`/entries/${id}`)).tags, n.id);
      if (!tags.includes(tag)) throw new Error(`note ${n.id} has tags ${JSON.stringify(tags)}, wanted ${tag}`);
    }
    //: Applying leaves Select mode by itself; Done is only there while it is on.
    if (await env.page.isVisible('#batch-cancel')) await env.page.locator('#batch-cancel').click();
    await env.wait(400);
  } finally {
    for (const n of [a, b]) await env.js(async (id) => { await api(`/entries/${id}`, { method: 'DELETE' }); await api(`/entries/${id}/purge`, { method: 'DELETE' }); }, n.id).catch(() => {});
  }
};

//: Every Library view and its Create menu, and every Timeline and Reminders
//: view mode: each draws, none sticks out of the screen.
flows.views = async (env) => {
  await env.js(() => switchTab('library'));
  await env.wait(1200);
  const targets = await env.js(() => [...document.querySelectorAll('#library-subtabs button[data-target]')].map((b) => [b.dataset.target, b.textContent.trim()]));
  for (const [target, label] of targets) {
    env.at(`Library: ${label}`);
    await env.js((t) => document.querySelector(`#library-subtabs [data-target="${t}"]`)?.click(), target);
    await env.wait(1100);
    const shown = await env.js((t) => { const v = document.getElementById(t); return Boolean(v && !v.classList.contains('hidden') && v.offsetParent); }, target);
    if (!shown) throw new Error(`the ${label} view is not shown after pressing its tab`);
    const skeletons = await env.js((t) => document.querySelectorAll(`#${t} .skeleton`).length, target);
    if (skeletons) throw new Error(`${skeletons} skeletons still showing in ${label} after a second`);
    await env.overflow(`library ${label}`);
  }
  env.at('Library: Create menu');
  await env.js(() => document.querySelector('#library-subtabs [data-target="library-view-documents"]')?.click());
  await env.wait(900);
  await env.page.locator('#tab-library button:has-text("Create"):visible').first().click();
  await env.wait(500);
  if (!(await env.page.locator('[role="dialog"]:visible button:has-text("New note")').count())) throw new Error('the Create sheet opened without its New note row');
  await env.overflow('library create sheet');
  await env.page.keyboard.press('Escape');
  await env.wait(400);
  if (await env.page.locator('[role="dialog"]:visible button:has-text("New note")').count()) throw new Error('Escape did not close the Create sheet');
  for (const tab of ['timeline', 'reminders']) {
    env.at(`${tab} views`);
    await env.js((t) => switchTab(t), tab);
    await env.wait(1500);
    const buttons = await env.js((t) => [...document.querySelectorAll(`#tab-${t} [aria-pressed], #tab-${t} .seg button, #tab-${t} [role="tab"]`)].filter((b) => b.offsetParent).length, tab);
    for (let i = 0; i < Math.min(buttons, 6); i++) {
      await env.js(([t, k]) => [...document.querySelectorAll(`#tab-${t} [aria-pressed], #tab-${t} .seg button, #tab-${t} [role="tab"]`)].filter((b) => b.offsetParent)[k]?.click(), [tab, i]);
      await env.wait(700);
      await env.overflow(`${tab} view ${i}`);
    }
  }
};

//: Find anything: the notebook-wide search, by the way a person reaches it on this screen.
async function openFind(env) {
  if (env.phone) {
    await env.page.locator('button[aria-label="More"]:visible').first().tap();
    await env.page.locator('[role="menuitem"]:visible', { hasText: /^Find/ }).first().tap();
  } else await env.page.click('#status-find');
  await env.page.waitForSelector('#finder-overlay:not(.hidden)', { timeout: 4000 });
  await env.wait(500);
}

flows.find = async (env) => {
  env.at('open Find');
  await openFind(env);
  if (!(await env.js(() => document.activeElement === document.getElementById('finder-input')))) throw new Error('the Find input is not focused on open');
  await env.overflow('find open');
  env.at('search');
  await env.page.keyboard.type('Alpha project');
  const row = await until(env, () => ([...document.querySelectorAll('#finder-results *')].find((e) => e.offsetParent && e.children.length === 0 && /Alpha project/.test(e.textContent)) ? true : null), null, 10000);
  if (!row) throw new Error('searching for a note by its title shows no row for it');
  await env.overflow('find results');
  env.at('open a result');
  await env.page.locator('#finder-results').getByText('Alpha project', { exact: false }).first().click();
  await env.wait(1200);
  if (await env.page.isVisible('#finder-overlay')) throw new Error('opening a result left Find open');
  env.at('Escape closes Find');
  await openFind(env);
  await env.page.keyboard.press('Escape');
  await env.wait(400);
  if (await env.page.isVisible('#finder-overlay')) throw new Error('Escape did not close Find');
};

module.exports = flows;
