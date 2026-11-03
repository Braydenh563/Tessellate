// WCAG 2.2 AA scan with axe-core (INBOX 433): every tab, the Notes and
// Library sub-tabs, every Settings section, in light and dark.
//
//   npm pack axe-core@4 && tar xzf axe-core-*.tgz -C /tmp/axe-core
//   BASE=http://127.0.0.1:8781 AXE_JS=/tmp/axe-core/package/axe.min.js \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/axe.js
//
// THEMES=light,dark (default both), WIDTH=1440, ONLY=notes,settings to narrow.
// Prints one line per rule and surface with the first few targets, then a
// total. Exit 1 when anything is found. axe is not vendored: it is MPL-2.0
// and a dev tool, so the sweep reads it from AXE_JS.
//
// axe's own limits, said here so a clean run is not read as more than it is:
// it checks what the DOM states (names, roles, contrast of plain text over a
// solid background, landmarks, ARIA validity). It does not see focus order,
// text over gradients or images (it reports those as "incomplete", counted
// below), zoom reflow, or what a screen reader says aloud. zoom.js and
// srtree.js cover the middle two.
const fs = require('fs');
const { boot } = require('./lib.js');

const AXE_JS = process.env.AXE_JS || '/tmp/axe-core/package/axe.min.js';
if (!fs.existsSync(AXE_JS)) {
  console.error(`axe-core not found at ${AXE_JS}; see the header for how to fetch it`);
  process.exit(2);
}
const AXE = fs.readFileSync(AXE_JS, 'utf8');
const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline', 'reminders', 'documents', 'whiteboard'];
//: Library's sub-tabs are `data-target="library-view-*"`, not `data-section`;
//: the old names here matched nothing, so Library was only ever scanned on All.
const SUBTABS = { notes: ['browse', 'capture', 'writing-room', 'ask'], library: ['docs', 'whiteboard', 'media', 'skills', 'links', 'contents'] };
const SECTIONS = ['searchindex', 'account', 'privacy', 'learned', 'appearance', 'preferences', 'models', 'tools', 'skills', 'personas', 'templates', 'websearch', 'memory', 'tasks', 'data', 'logs', 'shortcuts', 'extras', 'help', 'about'];
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const want = (name) => !ONLY.length || ONLY.some((o) => name.startsWith(o));
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
//: Findings checked by hand and kept, each with why. A new entry needs a
//: reason a reviewer can verify, never "axe is wrong" alone.
const ACCEPTED = {
  //: The palette is a combobox: focus stays in its input and the arrow keys
  //: move `aria-activedescendant` through the options, scrolling the lit one
  //: into view (settings-panes.js), so every row is reached and announced by
  //: keyboard (2.1.1). axe's rule wants the list itself focusable, which
  //: would add a Tab stop where the arrow keys do nothing.
  'scrollable-region-focusable|#palette-list': 'combobox with aria-activedescendant',
  //: The slash menu is the same pattern with the editor as the combobox:
  //: focus stays in the document box, which names the list (`aria-controls`,
  //: `aria-haspopup="listbox"`) and carries `aria-activedescendant` while the
  //: arrow keys move through the rows (`editorLinkBox`, editor.js), so every
  //: row is reached and announced by keyboard. A Tab stop on the list would
  //: take the focus out of the text being written (audit 1102 DX22).
  'scrollable-region-focusable|#editor-menu-list': 'combobox with aria-activedescendant (the editor box)',
};

async function scan(page, where, context, seen, out) {
  await page.evaluate(AXE);
  const result = await page.evaluate(async ([ctx, tags]) => {
    const r = await window.axe.run(ctx ? document.querySelector(ctx) || document : document, {
      runOnly: { type: 'tag', values: tags },
      resultTypes: ['violations', 'incomplete'],
    });
    const pick = (list) => list.map((v) => ({
      id: v.id, impact: v.impact, help: v.help,
      targets: v.nodes.map((n) => n.target.join(' ')),
      summary: v.nodes[0] ? (v.nodes[0].failureSummary || '').split('\n').slice(1, 3).join(' ').trim() : '',
    }));
    return { violations: pick(r.violations), incomplete: r.incomplete.reduce((n, v) => n + v.nodes.length, 0) };
  }, [context, TAGS]);
  for (const v of result.violations) {
    //: The same node failing the same rule on every tab (the header, the
    //: status bar) is one finding, not nine: report it where it is first seen.
    const fresh = v.targets.filter((t) => !seen.has(v.id + '|' + t) && !ACCEPTED[v.id + '|' + t]);
    fresh.forEach((t) => seen.add(v.id + '|' + t));
    if (!fresh.length) continue;
    out.push(`[${where}] ${v.impact} ${v.id} (${fresh.length}): ${v.help}\n      ${fresh.slice(0, 4).join('\n      ')}${v.summary ? `\n      why: ${v.summary.slice(0, 220)}` : ''}`);
  }
  return result.incomplete;
}

(async () => {
  let total = 0;
  for (const theme of (process.env.THEMES || 'light,dark').split(',')) {
    process.env.THEME = theme;
    const width = Number(process.env.WIDTH || 1440);
    const { browser, page } = await boot({ viewport: { width, height: 900 } });
    const seen = new Set(); const out = []; let incomplete = 0;
    for (const t of TABS) {
      if (!want(t)) continue;
      await page.evaluate((name) => switchTab(name), t); await page.waitForTimeout(900);
      incomplete += await scan(page, t, null, seen, out);
      for (const s of SUBTABS[t] || []) {
        const ok = await page.click(`#tab-${t} [data-section="${s}"], #tab-${t} [data-view="${s}"], #library-subtabs [data-target="library-view-${s}"]`, { timeout: 1500 }).then(() => true).catch(() => false);
        if (!ok) continue;
        await page.waitForTimeout(600);
        incomplete += await scan(page, `${t}/${s}`, null, seen, out);
      }
    }
    if (want('settings')) {
      await page.click('#settings-btn').catch(() => {}); await page.waitForTimeout(600);
      for (const s of SECTIONS) {
        const ok = await page.click(`#settings-modal [data-section="${s}"]`, { timeout: 1500 }).then(() => true).catch(() => false);
        if (!ok) continue;
        await page.waitForTimeout(350);
        incomplete += await scan(page, `settings/${s}`, '#settings-modal', seen, out);
      }
      await page.keyboard.press('Escape');
    }
    //: Overlays: what a tab scan never sees because it is closed until asked
    //: for. Each opens through the app's own function, is scanned whole
    //: (an overlay is often a child of <body>, not of the tab), and closes.
    if (want('overlays')) {
      const OVERLAYS = [
        ['manage categories', "openManageCategories()"],
        ['tags sheet', "openTagsSheet()"],
        ['move to category', "chooseNoteCategory([allEntries[0].id], allEntries[0].category)"],
        ['note menu', "switchTab('notes'); document.querySelector('#entry-list .entry-overflow-btn, #entry-list [aria-label*=\"More actions\"]')?.click()"],
        ['note edit form', "switchTab('notes'); openNoteEditor(allEntries[0].id)"],
        ['palette', "document.getElementById('status-command').click()"],
        ['find anything', "openFinder()"],
        ['shortcuts', "document.getElementById('shortcuts-overlay')?.classList.remove('hidden')"],
      ];
      for (const [name, js] of OVERLAYS) {
        await page.evaluate((code) => { try { (0, eval)(code); } catch (e) { console.warn(e.message); } }, js);
        await page.waitForTimeout(900);
        incomplete += await scan(page, `overlay/${name}`, null, seen, out);
        await page.keyboard.press('Escape'); await page.waitForTimeout(300);
        await page.keyboard.press('Escape'); await page.waitForTimeout(300);
        await page.evaluate(() => typeof closeNoteForm === 'function' && closeNoteForm()).catch(() => {});
      }
    }
    console.log(`== ${theme} ${width}px: ${out.length} findings, ${incomplete} nodes axe could not decide (incomplete)`);
    out.forEach((line) => console.log('  ' + line));
    total += out.length;
    await browser.close();
  }
  process.exit(total ? 1 : 0);
})();
