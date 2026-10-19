// INBOX 266 part 1 and INBOX 270's rule, the owner: "the user needs to be
// able to view and access what they want within around 3 clicks and they need
// to know how to instantly access what they want after loading the app."
//
// Each primary task is driven from a fresh load of the dashboard by pressing
// the controls a person would see, one visible click at a time, and the task
// passes when its end state is on screen within its budget (three, unless the
// row says otherwise and why). The count is the number of presses this script
// made, not an estimate: a path that needs a control the script could not find
// or press fails rather than being counted. Typing and the OS file dialog are
// not clicks and are not counted. The table these rows produce is in
// docs/roadmap/archive/agent-remaining/guideia.md.
//
//   BASE=http://127.0.0.1:8797 node scratchpad/ui-sweeps/clicks.js
//   ONLY="board" BASE=... node scratchpad/ui-sweeps/clicks.js   (rows whose task matches)
//
// Wants a notebook with at least one note and one binned note
// (scratchpad/g2-seed.js makes one). Exit code 1 on any row over budget.
const { boot } = require('./lib.js');

const dash = (label) => `#tab-dashboard button:has-text("${label}")`;
const settings = (section) => ['#settings-btn', `#settings-modal [data-section="${section}"]`];
// checkVisibility, not offsetParent: a tab page and the Settings modal are
// fixed-position, and a fixed element has no offsetParent however visible.
// A string, not a closure: `page.evaluate` sends a function's source to the
// page, and a closed-over `id` does not travel with it (it arrived as an
// undefined name and every row using this failed with the pane on screen).
const shown = (id) => `Boolean(document.getElementById(${JSON.stringify(id)})?.checkVisibility())`;

const PATHS = [
  // [task, [selectors pressed in order], end state (runs in the page), budget]
  ['Write a note', [dash('New note')], () => Boolean(document.activeElement?.closest('#entry-content, #capture'))],
  ['Search everything', ['#dash-find'], () => !document.getElementById('finder-overlay').classList.contains('hidden')],
  ['Ask a question of your notes', [dash('Ask your notes')], () => ['question', 'chat-input'].includes(document.activeElement?.id)],
  ['Set a reminder', [dash('Remind me')], () => ['reminder-magic', 'reminder-text'].includes(document.activeElement?.id)],
  ['Record a meeting', [dash('Meeting notes')], () => Boolean(document.getElementById('meeting-record')?.checkVisibility())],
  ['Learn how something works (the guide)', ['#status-guide'], () => Boolean(document.querySelector('[data-sheet="guide"]'))],
  ['Edit a note', ['#tab-btn-notes', '#tab-notes button[title="Edit this entry"]'], () => Boolean(document.querySelector('#tab-notes .cm-editor, #tab-notes textarea:not([hidden])'))],
  ['See the graph', ['#tab-btn-graph'], shown('tab-graph')],
  ['See the timeline', ['#tab-btn-timeline'], shown('tab-timeline')],
  ['Create a document', ['#tab-btn-library', '#library-new-doc', '.library-create-picker [data-kind="document"]'], () => Boolean(document.querySelector('.cm-editor')?.offsetParent)],
  ['Create a board', ['#tab-btn-library', '#library-new-doc', '.library-create-picker [data-kind="board"]'], () => Boolean(document.getElementById('wb-topbar')?.offsetParent)],
  ['Create a mind map', ['#tab-btn-library', '#library-new-doc', '.library-create-picker [data-kind="map"]'],
    // A map asks for its subject first (`createConceptMap`), which is typing,
    // not a click: the question on screen is the end of the clicking.
    () => Boolean([...document.querySelectorAll('.modal-overlay, dialog[open]')].find((el) => el.checkVisibility() && /what is this map about/i.test(el.textContent)))],
  ['Upload a file', ['#tab-btn-library', '#library-new-doc', '.library-create-picker [data-kind="file"]'], () => Boolean(document.querySelector('#library-subtabs button[data-media-kind="files"][aria-selected="true"], #library-subtabs button[data-media-kind="files"].active'))],
  // Four: the bin, then a card, then Restore. A deleted note's toast offers
  // Undo in one; this row is the later, deliberate recovery, and the fourth
  // press is the one that reads the note before deciding, on purpose.
  ['Restore a note from the bin', ['#tab-btn-library', '#library-filters button:has-text("Bin")', '#library-grid article', '#binned-restore'], () => /Restored/.test(document.querySelector('.toast:last-child, #toast')?.textContent || document.body.textContent), 4],
  ['Import notes from files', settings('data'), shown('import-md')],
  ['Back up the notebook', settings('data'), shown('backup-now')],
  ['Connect a model', settings('models'), shown('settings-models')],
  ['See keyboard shortcuts', settings('shortcuts'), shown('settings-shortcuts')],
  ['Take the guided tour', [...settings('help'), '#tour-replay-buttons button'], () => Boolean(document.querySelector('.tour-card')?.checkVisibility())],
  ['Change the dashboard widgets', ['#dash-widgets-open'], () => Boolean(document.getElementById('dash-widgets-dialog')?.open)],
  ['Switch space or make one', ['#space-switcher-btn'], () => Boolean([...document.querySelectorAll('[role="menu"], .action-menu, .space-menu')].find((m) => m.offsetParent && /new space/i.test(m.textContent)))],
  ['Change the theme', ['#theme-btn'], () => document.documentElement.dataset.mode === 'dark' || localStorage.getItem('theme') === 'dark'],
];

(async () => {
  let fails = 0;
  const only = process.env.ONLY ? new RegExp(process.env.ONLY, 'i') : null;
  for (const [task, steps, done, budget = 3] of PATHS) {
    if (only && !only.test(task)) continue;
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    let clicks = 0; let stuck = '';
    for (const sel of steps) {
      const loc = page.locator(sel).filter({ visible: true }).first();
      if (!(await loc.count())) { stuck = `nothing visible matches ${sel}`; break; }
      await loc.click({ timeout: 3000 }).catch((e) => { stuck = `could not press ${sel}: ${e.message.split('\n')[0]}`; });
      if (stuck) break;
      clicks++;
      await page.waitForTimeout(1000);
    }
    const reached = stuck ? false : await page.evaluate(done).catch(() => false);
    const ok = reached && clicks <= budget;
    if (!ok) fails++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${clicks}/${budget} ${task}${stuck ? ' (' + stuck + ')' : reached ? '' : ' (end state not reached)'}`);
    await browser.close();
  }
  console.log(fails ? `\nFAIL: ${fails} path${fails === 1 ? '' : 's'}` : '\nPASS: every task within its budget');
  process.exitCode = fails ? 1 : 0;
})();
