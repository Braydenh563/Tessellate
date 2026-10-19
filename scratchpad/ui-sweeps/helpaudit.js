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
const VENV_PY = process.env.VENV_PY || '/home/user/MemoryMap-AI/.venv/bin/python';

//: What the help says a tab holds. Static labels only: a menu a script draws
//: on press is read from the source by the person triaging, not here.
const TAB_CLAIMS = {
  dashboard: ['Customise', 'View', 'Widgets', 'Edit layout', 'Edit quick access', 'Reset quick access', 'All skills', 'Tools & features', 'Commands', 'Ask your notes', 'Sketch', 'Remind me', 'Meeting notes', 'New note'],
  notes: ['Capture a thought', 'Capture', 'Ask', 'Writing room', 'Questions', 'Select', 'Manage tags', 'Manage categories', 'Sort notes', 'Filter notes', 'Split into notes', 'Suggest a title'],
  chat: ['Agent mode', 'Plan', 'Skills', 'Fork', 'Compress the earlier messages', 'Export as Markdown', 'New chat'],
  graph: ['Concept maps', 'Display', 'Suggest links', 'Gravity', 'Spread', 'Link force', 'Length by similarity', 'Group by category', 'Labels', 'Label backgrounds', 'Curved links', 'Cluster glow', 'Arrows', 'Text fade', 'Link thickness', 'Minimap', 'Saved views', 'Export as PNG', 'Unpin all', 'Groups', 'Force', 'Tree', 'Radial', 'Arc', 'Colour', 'Size', 'Trace', 'Legend', 'Similarity', 'Entities', 'Documents', 'Boards', 'Tags', 'Attachments', 'Unwritten links', 'Hide unlinked', 'Strength', 'Time filter', 'Reset'],
  library: ['All', 'Documents', 'Boards & maps', 'Images', 'Files', 'AI skills', 'Bookmarks', 'Contents', 'Include the bin', 'Filter', 'Import a file as a document', 'Map from notes', 'Import outline', 'Expand all', 'Collapse all', 'Manage groups', 'New group'],
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
    const missing = p.segments.filter((seg) => !words[p.section].includes(norm(seg).replace(/\s*\(.*$/, '')));
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

  // 4. Tab-level claims.
  await page.evaluate(() => { const m = document.getElementById('settings-modal'); if (m && typeof closeSettingsModal === 'function') closeSettingsModal(); });
  let tabMiss = 0;
  for (const [tab, labels] of Object.entries(TAB_CLAIMS)) {
    await page.evaluate((t) => { location.hash = `#/${t}`; }, tab);
    await page.waitForTimeout(1200);
    const pool = norm(await corpus(page, `#tab-${tab}`));
    for (const label of labels) {
      if (!pool.includes(norm(label))) { console.log(`CLAIM tab ${tab}: "${label}" is not on the tab`); tabMiss++; }
    }
    // A check that cannot fail proves nothing: a label no tab has must be missed,
    // and the old names this audit corrected must still be missed.
    for (const gone of ['Whiteboards sub-tab', 'Writing Room', 'Files & Images gallery', 'Extract notes now']) {
      if (pool.includes(norm(gone))) { console.log(`FAIL control: "${gone}" is found on ${tab}, so a name the UI dropped is back or the check is too loose`); fails++; }
    }
  }
  console.log(`tab claims: ${tabMiss} not found`);

  // 5. Every help '?' points at something.
  const dead = await page.evaluate(() => [...document.querySelectorAll('[data-help-for]')]
    .filter((t) => !document.getElementById(t.dataset.helpFor)).map((t) => t.dataset.helpFor));
  for (const id of dead) { console.log(`FAIL popover: data-help-for="${id}" has no element`); fails++; }
  console.log(`popovers: ${claims.popovers.length} declared, ${dead.length} dead`);

  await browser.close();
  console.log(fails ? `helpaudit: ${fails} failure(s)` : 'helpaudit: every named path opens and reads as written');
  process.exit(fails ? 1 : 0);
})();
