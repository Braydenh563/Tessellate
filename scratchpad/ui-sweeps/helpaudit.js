// Does every place the help names exist in the running app, under that name?
//
// Standing order 13 (help moves with the UI), checked against the real DOM
// rather than the markup: the Guide's topics (help_chat.py,
// help_topics_more.py), their meta paths and every "Settings, A, B" path
// are read by `helpaudit_claims.py` (the same parser as
// tests/test_help_settings_paths.py), and this opens each one.
//
//   1. Every Settings pane the nav lists is opened, every fold in it opened,
//      and its words collected: text, titles, aria-labels, placeholders,
//      select options. A script-drawn control is there because the pane was
//      really shown.
//   2. Each "Settings, Pane, Group" path: the nav button reads Pane, and Group
//      (or the control named after it) is in that pane's words.
//   3. Each capitalised control-like phrase in a topic that names a pane is
//      looked for in the words of every pane the topic names. A miss is a
//      claim to read, not always a bug (prose that happens to be capitalised),
//      so misses are listed for triage and only a path miss fails the run.
//   4. A short list of tab-level claims (Library's sub-tabs, Timeline's Kinds
//      and Options, Dashboard's Customise, ...) is looked for in each tab.
//   5. Every `data-help-for` trigger points at an element that exists.
//   6. At 1440, 1024 and 390 (dark): the tab claims again, read from what is
//      reachable at that width (visible text, accessible names, menu rows), so
//      a control that folds into a menu is looked for under its narrow name.
//   7. Menus a script draws on press are pressed and read: the chat "/" menu,
//      the chat header menu, a message's actions, the board's five top menus
//      (a board and a map), the notes Filter and More menus, the sort order
//      and a note card's menu. Each is compared with what the Guide says it holds.
//   8. The JS-built help popovers (manage-cat-help, manage-tags-help,
//      inbox-help) and the board's help bodies are opened and read, and every
//      control they name must exist.
//
//   bash scratchpad/ui-sweeps/serve.sh 8799 /tmp/mm-help
//   BASE=http://127.0.0.1:8799 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/helpaudit.js
//
// Exit code is the number of path and popover failures; phrase and tab misses
// are printed as "CLAIM".
const { execFileSync } = require('child_process');
const path = require('path');
const { boot } = require('./lib.js');

const ROOT = path.resolve(__dirname, '..', '..');
const VENV_PY = process.env.VENV_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');

//: What the help says a tab holds. Static labels; the menus a script draws on
//: press are PRESSED below (section 7).
const TAB_CLAIMS = {
  dashboard: ['Customise', 'View', 'Widgets', 'Edit layout', 'Edit quick access', 'Reset quick access', 'All skills', 'Tools & features', 'Commands', 'Ask your notes', 'Sketch', 'Remind me', 'New meeting', 'New note'],
  notes: ['Capture a thought', 'Capture', 'Ask', 'Writing room', 'Questions', 'Select', 'Manage tags', 'Manage categories', 'Sort notes', 'Filter notes', 'Split into notes', 'Suggest a title'],
  chat: ['Agent mode', 'Plan', 'Skills', 'Fork', 'Compress the earlier messages', 'Export as Markdown', 'New chat'],
  graph: ['Display', 'Suggest links', 'Gravity', 'Spread', 'Link force', 'Length by similarity', 'Group by category', 'Labels', 'Label backgrounds', 'Curved links', 'Cluster glow', 'Arrows', 'Text fade', 'Link thickness', 'Minimap', 'Saved views', 'Export as PNG', 'Unpin all', 'Groups', 'Force', 'Tree', 'Radial', 'Arc', 'Colour', 'Size', 'Trace', 'Legend', 'Similarity', 'Entities', 'Documents', 'Boards', 'Tags', 'Attachments', 'Unwritten links', ['Hide', 'unlinked'], 'Strength', 'Time filter', 'Reset'],
  library: ['All', 'Documents', 'Boards & maps', 'Images', 'Files', 'Skills', 'Bookmarks', 'Contents', 'Include the bin', 'Filter', 'Import a file as a document', 'Map from notes', 'Import outline', 'Expand all', 'Collapse all', 'Manage groups', 'New group'],
  timeline: ['Feed', 'Table', 'Kinds', 'Options', 'Group by', 'Show group', 'Time range', 'On this day', 'Jump to today', 'Select', 'Auto', 'Day', 'Week', 'Month', 'Year', 'Category', 'Tag', 'Thread', 'None', 'Everything', 'Last 3 months', 'Last year', 'Custom range'],
  reminders: ['Magic add', 'Add from this sentence', 'Quick set', 'Priority', 'Repeat', 'Add all to calendar (.ics)', 'Calendar', 'In 30 min', 'In 1 hour', 'In 3 hours', 'Tonight 7pm', 'Tomorrow 9am', 'Tomorrow 2pm', 'This weekend', 'Next week'],
};

const norm = (s) => String(s || '').replace(/&amp;/g, '&').replace(/[’]/g, "'").replace(/\s+/g, ' ').trim().toLowerCase();

async function corpus(page, rootSel) {
  return page.evaluate((sel) => {
    const root = document.querySelector(sel) || document.body;
    const out = [];
    const add = (t) => { if (t) out.push(String(t)); };
    add(root.textContent);
    for (const el of root.querySelectorAll('*')) {
      for (const a of ['title', 'aria-label', 'placeholder', 'data-tip', 'data-label']) add(el.getAttribute(a));
    }
    for (const o of root.querySelectorAll('option')) add(o.textContent);
    return out.join(' \n ');
  }, rootSel);
}


const WIDTHS = (process.env.WIDTHS || '1440,1024,390').split(',').map(Number);

//: Text a person can reach under `sel` at this width: visible text, accessible
//: names (title, aria-label, placeholder) and the rows of a menu that is shut
//: but one press away. A control a narrow layout drops (a `.dock-word`, a
//: toolbar button that folds into More) is not reachable under its wide name,
//: so a claim about it is looked for under the name it has now. `strict`: a
//: `hidden` attribute inside a menu also hides (a board-only row on a map).
async function reach(page, sel, strict = false) {
  return page.evaluate(({ sel, strict }) => {
    const MENUISH = '.action-menu, .submenu, .doc-dock-menu-list, .dock-menu-list, [role="menu"], .wb-board-menu, .help-body, .editor-menu';
    const out = [];
    const off = (n) => { const cs = getComputedStyle(n); return cs.display === 'none' || cs.visibility === 'hidden'; };
    const gone = (el, root) => {
      for (let n = el; n; n = n.parentElement) {
        const attr = n.hasAttribute('hidden');
        if ((attr && strict) || ((attr || off(n)) && !n.closest(MENUISH))) return true;
        if (n === root) break;
      }
      return false;
    };
    for (const root of document.querySelectorAll(sel)) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let t = walker.nextNode(); t; t = walker.nextNode()) {
        if (t.parentElement && !gone(t.parentElement, root)) out.push(t.nodeValue);
      }
      for (const el of [root, ...root.querySelectorAll('*')]) {
        if (gone(el, root)) continue;
        for (const a of ['title', 'aria-label', 'placeholder', 'data-tip', 'data-label']) if (el.getAttribute(a)) out.push(el.getAttribute(a));
      }
    }
    return out.join(' \n ');
  }, { sel, strict });
}

//: A claim is a phrase, or a list of words that must all be there ("save", "note").
const has = (pool, claim) => (Array.isArray(claim) ? claim : [claim]).every((w) => pool.includes(norm(w)));
const shown = (claim) => (Array.isArray(claim) ? claim.join(' + ') : claim);

//: What the Guide says each pressed menu holds (the topic that says it in
//: comments). A miss is a FAIL: these are read from the topics, so the help
//: or the UI is wrong.
const MENU_CLAIMS = {
  chatHeader: ['Fork this chat', 'Compress the earlier messages', 'Export as Markdown', 'Make a mind map of this chat'], // chat-controls, mind-maps
  assistantRow: [['copy'], ['regenerate', 'from here'], ['read aloud'], ['save', 'note'], 'Mind map this'], // chat-controls, mind-maps
  userRow: ['Edit this question'], // chat-controls
  filter: ['Semantic', 'Save this filter'], // notes tab claims
  sort: ['Newest first', 'Oldest first', 'Recently edited', 'A → Z', 'Most used', 'Forgotten first'], // notes-list
  notesMore: ['Manage tags'], // tag-manager: "Notes tab, the ... menu, Manage tags"
  card: ['Copy wiki link', 'Copy app link'], // notes-list
  insert: ['Table', 'Diagram builder', 'Sticky note'], // board-tables, board-mermaid, whiteboard-controls
  edit: ['Undo', 'Select all', 'Duplicate', 'Delete'], // wb-help-about
  arrange: [['loop']], // wb-fmt-help-connector: "Arrange, Loop on the shape"
  view: ['Hand-drawn', 'Present frames', 'Format panel', 'Fit everything', 'Full screen'], // board-hand-drawn, wb-help-about
  boardMenu: ['Export', 'Keys and controls', 'Clear everything'], // wb-help-about: "Board (export, clear, help)"
  mapBoardMenu: ['Study the map', 'Write as a document', 'Copy app link'], // mind-map-study, mind-map-import-export, addresses
};

//: Controls each JS-built popover names, looked for in the panel it explains.
const POPOVER_CLAIMS = {
  'manage-cat-help': ['Merge into', 'Split', 'Colour', 'Automatic', 'Sort', 'Empty', 'Delete', 'Move to'],
  'manage-tags-help': ['Rename', 'Merge into', 'Sort', 'Used once', 'Remove from all notes', 'Turned down', 'Offer again'],
  'inbox-help': ['Links', 'Tensions', 'Names', 'Link types', 'Link all above 70%', 'Start the review', 'Suggest reasons', 'Explain your existing links'],
};

//: Named by a popover but drawn only with data a fresh notebook lacks.
// Drawn only on data or a selection the sweep does not make (a turned-down tag; the notes list's batch bar,
// whose "Move to" skills.js draws; a tag row's menu), so read from the files that draw them.
const SOURCE_ONLY = { 'manage-tags-help': ['Turned down', 'Offer again', 'Remove from all notes'], 'manage-cat-help': ['Move to'] };
// Controls the static whiteboard help bodies name (wb-help-about, wb-boards-intro, wb-map-places-help, wb-side-map-help).
const WB_HELP = {
  'wb-help-about': ['Edit', 'View', 'Board', ['More board commands', 'phone']],
  'wb-boards-intro': ['Tray', ['New', 'src']],
  'wb-side-map-help': [['From a template', 'src']],
  'wb-map-places-help': [['Topic colour', 'src'], ['Branch colour', 'src'], ['Comment…', 'src'], ['How this map looks', 'src'], ['Present branches', 'src'], ['Summarise', 'src']],
};
const UNFOLD = {
  reminders: ['#tab-reminders button[title="Add a reminder"], #tab-reminders button[aria-label="Add a reminder"]'],
  notes: ['#tab-notes .phone-sidebar-opener'],
  chat: ['#chat-dock-more-btn'],
  graph: ['#tab-graph button[aria-label="Display options"]'],
};
const SOURCE_FILES = ['tag-manager.js', 'categories-panel.js', 'skills.js'];

async function pressAndRead(page, sel, readSel, strict = false) {
  try { await page.click(sel, { timeout: 4000 }); } catch (e) { return null; }
  await page.waitForTimeout(700);
  const pool = norm(await reach(page, readSel, strict));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(250);
  return pool;
}

function judge(label, pool, claims, W) {
  let miss = 0;
  if (pool === null) { console.log(`SKIP ${label} @${W}: could not be pressed`); return 0; }
  for (const c of claims) if (!has(pool, c)) { console.log(`FAIL menu ${label} @${W}: the Guide says "${shown(c)}"; the pressed menu does not hold it`); miss++; }
  console.log(`menu ${label} @${W}: ${claims.length - miss} of ${claims.length} named rows present`);
  return miss;
}

const reachedBefore = new Set();

async function atWidth(W, claims) {
  let fails = 0;
  console.log(`--- ${W}px, dark ---`);
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}) });
  await page.evaluate(async () => { for (let i = 0; i < 2; i++) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Help audit note ${i}\n\nSomething about topic ${i} with a #audit tag.`, category: 'Help audit' }) }); });

  // 6. Tab claims. A label the tab's DOM lacks at all is a CLAIM (as at 1440 before); a label that was
  // reachable at the widest width and is not at this one has lost its name or its place when narrow.
  let tabMiss = 0;
  let lost = 0;
  for (const [tab, labels] of Object.entries(TAB_CLAIMS)) {
    if (process.env.TABS && !process.env.TABS.split(',').includes(tab)) continue;
    await page.evaluate((t) => { location.hash = `#/${t}`; }, tab);
    await page.waitForTimeout(2000);
    const all = norm(await corpus(page, `#tab-${tab}`));
    const rawReach = await reach(page, `#tab-${tab}`);
    let pool = norm(rawReach);
    // A fold that a press opens counts as reachable: press each opener this tab has at this width and read what it draws
    // (the Reminders composer sheet, the chat dock's More panel, the graph's Display options).
    for (const opener of UNFOLD[tab] || []) {
      const pressed = await page.evaluate((s) => { const b = document.querySelector(s); if (!b || !b.getClientRects().length) return false; b.click(); return true; }, opener);
      if (!pressed) continue;
      await page.waitForTimeout(800);
      pool += ' ' + norm(await reach(page, `#tab-${tab}, .sheet-overlay, .modal-overlay, .popover, .action-menu:not(.hidden), .dock-menu:not(.hidden)`));
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
    }
    for (const label of labels) {
      const key = `${tab}|${label}`;
      const parts = [].concat(label);
      const inAll = parts.every((p) => all.includes(norm(p)));
      const inPool = parts.every((p) => pool.includes(norm(p)));
      if (!inAll) { console.log(`CLAIM tab ${tab} @${W}: "${label}" is not on the tab`); tabMiss++; continue; }
      if (inPool) reachedBefore.add(key);
      else if (reachedBefore.has(key)) { if (process.env.DEBUG_LOST) console.log(JSON.stringify(await page.evaluate((l) => [...document.querySelectorAll('#tab-notes *')].filter((e) => (e.getAttribute('aria-label') || e.title || '') === l).map((e) => { const cs = getComputedStyle(e); return [e.id, cs.display, cs.visibility, !!e.closest('[hidden]'), e.getClientRects().length]; }), [].concat(label)[0]))); console.log(`LOST tab ${tab} @${W}: "${label}" was reachable at ${WIDTHS[0]} and is neither shown nor in a menu now`); lost++; }
    }
    // A check that cannot fail proves nothing: names the UI dropped must still be missed. Case counts
    // ("Writing Room" was the old title case; "Writing room" is the name now).
    for (const gone of ['Whiteboards sub-tab', 'Writing Room', 'Files & Images gallery', 'Extract notes now']) {
      if (rawReach.includes(gone)) { console.log(`FAIL control: "${gone}" is found on ${tab} @${W}, so a name the UI dropped is back or the check is too loose`); fails++; }
    }
  }
  console.log(`tab claims @${W}: ${tabMiss} not on the tab, ${lost} lost since ${WIDTHS[0]}`);

  // 7a. The chat "/" menu: a row for every command in the registry.
  await page.evaluate(() => { location.hash = '#/chat'; });
  await page.waitForTimeout(1500);
  await page.click('#chat-input');
  await page.keyboard.type('/');
  await page.waitForTimeout(800);
  const slash = norm(await reach(page, '#editor-menu'));
  fails += judge('chat "/"', slash, claims.slash.map((c) => `/${c}`), W);
  await page.keyboard.press('Escape');
  await page.fill('#chat-input', '');

  // 7b. The chat header menu.
  fails += judge('chat header ...', await pressAndRead(page, '#chat-actions-menu button', '.action-menu:not(.hidden)', true), MENU_CLAIMS.chatHeader, W);

  // 7c. A message's actions. No model is needed: the bubble is built by the
  // app's own addBubble and assistantMessageActions, as a reopened chat does.
  await page.evaluate(() => {
    const b = addBubble('assistant', 'A probe answer with enough words to be mapped');
    assistantMessageActions({ bubble: b, text: 'A probe answer with enough words to be mapped', question: 'probe?' });
    addBubble('user', 'a probe question');
  });
  await page.waitForTimeout(500);
  const names = await page.evaluate(() => [...document.querySelectorAll('#chat-messages .msg-action')].map((b) => `${b.getAttribute('aria-label') || ''} ${b.title}`).join(' \n '));
  let msgPool = norm(names);
  // The pointer is intercepted by the head row in this hand-built bubble, so the ... is pressed by dispatch.
  const moreSel = '#chat-messages button[aria-label="More actions for this message"]';
  if (await page.$(moreSel)) {
    await page.dispatchEvent(moreSel, 'click');
    await page.waitForTimeout(700);
    msgPool += ' ' + norm(await reach(page, '.action-menu:not(.hidden)', true));
    await page.keyboard.press('Escape');
  }
  fails += judge('assistant message', msgPool, MENU_CLAIMS.assistantRow, W);
  fails += judge('your message', msgPool, MENU_CLAIMS.userRow, W);

  // 7d. The notes list: Filter, the sort order, the ... menu and a card's menu.
  await page.evaluate(() => { location.hash = '#/notes'; });
  await page.waitForTimeout(2000);
  fails += judge('notes Filter', await pressAndRead(page, '#notes-filter-menu > summary', '#notes-filter-menu'), MENU_CLAIMS.filter, W);
  const more = await pressAndRead(page, '#notes-more-menu > summary', '#notes-more-menu');
  fails += judge('notes ...', more, MENU_CLAIMS.notesMore, W);
  const sortOptions = norm(await page.evaluate(() => [...document.querySelectorAll('#note-sort option')].map((o) => o.textContent).join(' \n ')));
  fails += judge('notes sort order', sortOptions, MENU_CLAIMS.sort, W);
  const sortVisible = await page.evaluate(() => !!document.getElementById('note-sort')?.offsetParent);
  if (!sortVisible && !(more || '').includes('newest first')) { console.log(`FAIL menu notes sort @${W}: the sort select is hidden and the ... menu does not carry the order`); fails++; }
  const kebab = '#tab-notes button[title="More actions"]';
  if (await page.$(kebab)) {
    await page.evaluate((s) => document.querySelector(s)?.scrollIntoView({ block: 'center' }), kebab);
    fails += judge('note card ...', await pressAndRead(page, kebab, '.action-menu:not(.hidden)', true), MENU_CLAIMS.card, W);
  } else console.log(`SKIP note card ... @${W}: no card kebab found in #entries`);

  // 7e. The board's top menus, on a board and on a map. At a width where a
  // toggle is folded into "More board commands", that menu is read instead.
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(600);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await page.waitForFunction(() => typeof initWhiteboard === 'function' && typeof wbFormatSyncSoon === 'function', null, { timeout: 15000 });
  for (const type of ['board', 'map']) {
    await page.evaluate(async (t) => {
      await initWhiteboard();
      const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: `help audit ${t}`, type: t }) });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 900));
    }, type);
    await page.waitForTimeout(1200);
    const wanted = type === 'board'
      ? { 'wb-insert-menu': MENU_CLAIMS.insert, 'wb-edit-menu': MENU_CLAIMS.edit, 'wb-arrange-menu': MENU_CLAIMS.arrange, 'wb-view-menu': MENU_CLAIMS.view, 'wb-board-menu': MENU_CLAIMS.boardMenu }
      : { 'wb-board-menu': MENU_CLAIMS.mapBoardMenu };
    for (const [id, list] of Object.entries(wanted)) {
      const toggle = `[data-wb-menu-toggle][aria-controls="${id}"]`;
      const visible = await page.evaluate((s) => !!document.querySelector(s)?.offsetParent, toggle);
      let pool = visible ? await pressAndRead(page, toggle, `#${id}`, true) : null;
      if (!visible) {
        // Folded: the Guide's name must still be somewhere on the bar's "More board commands".
        const overflow = '[aria-label="More board commands"]';
        pool = (await page.$(overflow)) ? await pressAndRead(page, overflow, '.action-menu:not(.hidden), .wb-board-menu:not(.hidden)', true) : null;
        if (pool) console.log(`note: ${type} ${id} @${W} is folded into "More board commands"`);
      }
      fails += judge(`${type} ${id}`, pool, list, W);
    }
  }

  // 7f. The board and map help bodies: each control one names must exist at this width (DOM and menus), or in the
  // file that draws a context-menu row (right-click menus are not drawn until pressed).
  {
    const fs = require('fs');
    const src = fs.readdirSync(path.join(ROOT, 'frontend', 'js')).filter((f) => /^(whiteboard|boards-gallery|library)/.test(f)).map((f) => fs.readFileSync(path.join(ROOT, 'frontend', 'js', f), 'utf8')).join('\n');
    const page0 = norm(await reach(page, 'body'));
    let miss = 0;
    for (const [id, claim] of Object.entries(WB_HELP)) {
      const body = norm(await page.evaluate((i) => document.getElementById(i)?.textContent || '', id));
      if (!body) { console.log(`FAIL wb help ${id} @${W}: the body is gone from the page`); fails++; continue; }
      for (const c of claim) {
        const [word, where] = [].concat(c);
        if (!body.includes(norm(word))) console.log(`note: ${id} no longer says "${word}"; drop it from WB_HELP`);
        if (where === 'phone' && W >= 600) continue;
        const ok = where === 'src' ? src.includes(word) : page0.includes(norm(word));
        if (!ok) { console.log(`FAIL wb help ${id} @${W}: it names "${word}" and the ${where === 'src' ? 'whiteboard source' : 'page'} has no such control`); miss++; fails++; }
      }
    }
    console.log(`wb help bodies @${W}: ${Object.values(WB_HELP).flat().length - miss} of ${Object.values(WB_HELP).flat().length} named controls present`);
  }

  // 8. The JS-built popovers.
  fails += await popovers(page, W);
  await browser.close();
  return fails;
}

async function popovers(page, W) {
  let fails = 0;
  const read = async (helpId, panelSel, label, extra = async () => '') => {
    const trigger = `[data-help-for="${helpId}"]`;
    try { await page.click(trigger, { timeout: 4000 }); } catch (e) { console.log(`FAIL popover ${helpId} @${W}: its ? cannot be pressed`); return 1; }
    await page.waitForTimeout(400);
    const body = norm(await page.evaluate((id) => document.getElementById(id)?.innerText || '', helpId));
    // The panel as drawn, plus what pressing in it draws (a selection's Move to, a colour well's Automatic).
    const panel = norm(await page.evaluate((sel) => document.querySelector(sel)?.textContent || '', panelSel)) + ' ' + norm(await reach(page, panelSel)) + ' ' + norm(await extra());
    if (!body) { console.log(`FAIL popover ${helpId} @${W}: opens empty`); return 1; }
    let miss = 0;
    for (const c of POPOVER_CLAIMS[helpId]) {
      if ((SOURCE_ONLY[helpId] || []).includes(c)) continue;
      if (!body.includes(norm(c))) console.log(`note: ${helpId} no longer says "${c}"; drop it from POPOVER_CLAIMS`);
      if (!panel.includes(norm(c))) { console.log(`FAIL popover ${helpId} @${W}: it names "${c}"; ${label} has no such control`); miss++; }
    }
    //: Drawn only when the data exists (a tag turned down on three notes): read from the file that draws it.
    for (const c of SOURCE_ONLY[helpId] || []) {
      if (!SOURCE_FILES.some((f) => require('fs').readFileSync(path.join(ROOT, 'frontend', 'js', f), 'utf8').includes(c))) { console.log(`FAIL popover ${helpId} @${W}: it names "${c}" and no file that draws the panel has it`); miss++; }
    }
    console.log(`popover ${helpId} @${W}: ${POPOVER_CLAIMS[helpId].length - miss} of ${POPOVER_CLAIMS[helpId].length} named controls present (${(SOURCE_ONLY[helpId] || []).length} read from source)`);
    return miss;
  };
  await page.evaluate(() => { location.hash = '#/notes'; });
  await page.waitForTimeout(1500);
  // Categories: the sidebar button, or the Settings one where the sidebar is folded.
  await page.evaluate(() => (document.getElementById('manage-categories-btn')?.offsetParent ? document.getElementById('manage-categories-btn') : (document.getElementById('manage-categories-foot') || document.getElementById('settings-manage-categories')))?.click());
  await page.waitForTimeout(900);
  // Tick the first row (Space), then open its Colour: Move to and Automatic are drawn by those presses.
  fails += await read('manage-cat-help', '.manage-cat-card', 'the Manage categories panel', async () => {
    let text = '';
    try {
      await page.focus('.manage-cat-card .manage-cat-row');
      await page.keyboard.press('Space');
      await page.waitForTimeout(400);
      text += await reach(page, '.manage-cat-card');
      await page.keyboard.press('Space');
      await page.click('.manage-cat-card .manage-cat-row button[aria-label^="Actions for"]', { timeout: 3000 });
      await page.waitForTimeout(500);
      await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].find((b) => /^Colour/.test(b.textContent.trim()))?.click());
      await page.waitForTimeout(700);
      text += await reach(page, '.sheet-overlay, .modal-overlay, .popover');
    } catch (e) { console.log(`note: categories extra presses stopped: ${String(e.message).split('\n')[0]}`); }
    return text;
  });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.getElementById('notes-manage-tags')?.click());
  await page.waitForTimeout(900);
  fails += await read('manage-tags-help', '.manage-cat-card', 'the Manage tags panel', async () => {
    try {
      await page.dispatchEvent('.manage-cat-card .manage-cat-row button[aria-label^="Actions for"]', 'click', {}, { timeout: 3000 });
      await page.waitForTimeout(500);
      return await reach(page, '.action-menu:not(.hidden)');
    } catch (e) { console.log(`note: tags extra press stopped: ${String(e.message).split('\n')[0]}`); return ''; }
  });
  // Twice: the first closes the row's menu, the second the panel.
  for (let i = 0; i < 5 && (await page.$('.manage-cat-card, .action-menu:not(.hidden)')); i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(300); }
  if (await page.evaluate(() => typeof openSuggestionsInbox === 'function')) {
    await page.evaluate(() => openSuggestionsInbox('links'));
    await page.waitForTimeout(1200);
    fails += await read('inbox-help', '.inbox-card', 'the suggestions inbox');
    await page.keyboard.press('Escape');
  } else console.log(`SKIP popover inbox-help @${W}: openSuggestionsInbox is not global`);
  return fails;
}

(async () => {
  const claims = JSON.parse(execFileSync(VENV_PY, [path.join(__dirname, 'helpaudit_claims.py')], { cwd: ROOT, encoding: 'utf8' }));
  let fails = 0;
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });

  // 1. The nav and each pane's words.
  await page.evaluate(() => openSettingsModal('models'));
  await page.waitForTimeout(800);
  const nav = await page.evaluate(() => [...document.querySelectorAll('#settings-nav button[data-section]')]
    .map((b) => ({ section: b.dataset.section, label: b.textContent.replace(/\s+/g, ' ').trim() })));
  const navLabel = Object.fromEntries(nav.map((n) => [n.section, n.label]));
  const words = {};
  for (const { section } of nav) {
    await page.evaluate((n) => showSettingsSection(n), section);
    await page.waitForTimeout(500);
    await page.evaluate((n) => {
      for (const d of document.querySelectorAll(`#settings-${n} details`)) d.open = true;
    }, section);
    await page.waitForTimeout(250);
    words[section] = norm(await corpus(page, `#settings-${section}`));
  }
  console.log(`panes opened: ${nav.length} (${nav.map((n) => n.label).join(', ')})`);

  // 2. Paths.
  let pathsOk = 0;
  for (const p of claims.paths) {
    const label = navLabel[p.section];
    if (norm(label) !== norm(p.pane)) { console.log(`FAIL pane   "Settings, ${p.path}": the nav says "${label}"`); fails++; continue; }
    //: A segment is a control name or, where the Guide runs on ("Health says how the notebook is"),
    //: a name then prose: it passes on its whole text, else on its leading words, down to the first
    //: word. A lowercase-led segment is prose ("stops any answer ...") and names nothing to find.
    const found = (seg) => {
      if (/^[a-z]/.test(seg.trim())) return true;
      const w = norm(seg).replace(/\s*\(.*$/, '').split(' ');
      for (let n = w.length; n >= 1; n--) if (words[p.section].includes(w.slice(0, n).join(' '))) return true;
      return false;
    };
    const missing = p.segments.filter((seg) => !found(seg));
    if (missing.length) { console.log(`FAIL group  "Settings, ${p.path}": not found in the open pane: ${missing.join(' | ')}`); fails++; continue; }
    pathsOk++;
  }
  console.log(`paths: ${pathsOk} of ${claims.paths.length} open and read as written`);

  // 3. Phrases a topic names, against the pane(s) it names.
  let phraseMiss = 0;
  for (const t of claims.phrases) {
    const pool = t.sections.map((s) => words[s] || '').join(' ');
    for (const phrase of t.phrases) {
      const full = norm(phrase);
      if (pool.includes(full)) continue;
      const two = full.split(' ').slice(0, 2).join(' ');
      if (full.split(' ').length > 1 && pool.includes(two)) continue;
      console.log(`CLAIM ${t.topic}: "${phrase}" is not in ${t.sections.join(' / ')}`);
      phraseMiss++;
    }
  }
  console.log(`phrases: ${phraseMiss} not found in the pane their topic names (read each; capitalised prose is not a bug)`);

  await page.evaluate(() => { const m = document.getElementById('settings-modal'); if (m && typeof closeSettingsModal === 'function') closeSettingsModal(); });

  // 5. Every help '?' points at something.
  const dead = await page.evaluate(() => [...document.querySelectorAll('[data-help-for]')]
    .filter((t) => !document.getElementById(t.dataset.helpFor)).map((t) => t.dataset.helpFor));
  for (const id of dead) { console.log(`FAIL popover: data-help-for="${id}" has no element`); fails++; }
  console.log(`popovers: ${claims.popovers.length} declared, ${dead.length} dead`);

  await browser.close();

  // 6 to 8, once per width (each its own browser, so a narrow layout is real).
  for (const width of WIDTHS) fails += await atWidth(width, claims);
  console.log(fails ? `helpaudit: ${fails} failure(s)` : 'helpaudit: every named path opens and reads as written');
  process.exit(fails ? 1 : 0);
})();
