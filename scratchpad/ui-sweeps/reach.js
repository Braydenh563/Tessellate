// Trust contract rule 2 (WORLD_CLASS_PLAN 28.1): three clicks to anything.
// A breadth-first crawl of the click graph from the dashboard: the tab bar,
// the header, every sub-tab strip, every menu (a menu is a click, its item
// another), settings sections, and the first item of each repeated list (a
// note, a document, a board, a map). A destination is a view state: which
// page, which sub-tabs are lit, which dialog or panel is on top. Prints every
// destination with its depth and the click path, those deeper than 3, and the
// destinations no palette command names.
//
//   BASE=http://127.0.0.1:8791 [THEME=dark] [MAXD=4] [WORKERS=3] node reach.js
// **What it does not see:** right-click menus, keyboard-only routes, controls
// that appear only while something is selected, and anything behind a label
// the allow-list below does not call navigation. A destination missing here is
// therefore "not found by the crawl", not "does not exist". Palette matching
// is by words: a destination counts as named when every word of its last label
// appears in one command's label, keywords, about or target.
const L = require('./trustlib.js');
const MAXD = Number(process.env.MAXD || 4);
const NAVISH = /^(open|go to|manage|customi[sz]e|settings|tools|history|browse|view|show|see|details|properties|more|help|guide|tour|templates?|new|edit|find|filter|select|sort|search|bin|trash|activity|tidy|tags|categories|spaces?|notifications?|account|appearance|import|export|backup|about|shortcuts|recent|quick|capture|compose|ask|write|record|read|library|dashboard|notes|chat|graph|timeline|reminders|documents?|boards?|maps?|skills|images|files|links|bookmarks|contents)/i;
const DANGER = /(delete|remove|clear|reset|wipe|erase|lock|quit|sign out|log ?out|uninstall|discard|empty|destroy|factory|restart|stop|shut ?down|close the app|unlink|forget|revoke|disconnect|update now|install|download|pull|run now)/i;

// Everything in-page, so a state and its candidates are read in one round trip.
async function look(page) {
  return page.evaluate(({ NAVISH, DANGER }) => {
    const nav = new RegExp(NAVISH.s, NAVISH.f), danger = new RegExp(DANGER.s, DANGER.f);
    const vis = (e) => { const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return b.width > 2 && b.height > 2 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
    const txt = (e) => (e.getAttribute('aria-label') || e.title || e.textContent || '').trim().replace(/\s+/g, ' ').replace(/[“"][^”"]*[”"]/g, '').replace(/\d+/g, '#').slice(0, 48);
    const overlays = [...document.querySelectorAll('[role="dialog"], .modal-overlay, .confirm-overlay, .sheet, #palette-overlay, .panel-overlay, .drawer, [role="menu"]')]
      .filter((o) => vis(o) && !o.classList.contains('hidden') && o.getBoundingClientRect().width > 120);
    const top = overlays[overlays.length - 1] || null;
    const page = [...document.querySelectorAll('.tab-page')].find((p) => !p.classList.contains('hidden') && vis(p));
    // What is lit is read inside the dialog when one is open: a panel opened from
    // any page is the same destination, so the page underneath must not name it.
    const litRoot = top || document;
    const lit = [...litRoot.querySelectorAll('[role="tab"][aria-selected="true"], .modal-nav .active, #settings-nav .active, [data-section].active, [data-target].active')]
      .filter(vis).map(txt).filter(Boolean);
    // A view inside the page (a board canvas, the boards list, a document pane)
    // is a place too: the visible ids that name one are part of the signature.
    const views = page ? [...page.querySelectorAll('[id*="-view"]')].filter((e) => vis(e) && !e.closest('.hidden')).map((e) => e.id).sort().join(',') : '';
    const heading = top ? ((top.querySelector('h1,h2,h3,[role="heading"]') || {}).textContent || top.getAttribute('aria-label') || top.id || top.className.split(' ')[0]) : '';
    const sig = [top ? '' : (page ? page.id + (views ? '~' + views : '') : ''), [...new Set(lit)].sort().join('+'), top ? 'ON:' + heading.trim().replace(/\s+/g, ' ').slice(0, 40) : ''].join(' | ');
    const scope = top || document.body;
    const out = new Map();
    const add = (e, kind) => {
      if (!vis(e) || e.disabled || e.closest('.toast, #boot-splash')) return;
      const l = txt(e);
      if (!l || danger.test(l)) return;
      const k = kind + '|' + l;
      if (!out.has(k)) out.set(k, 1);
    };
    for (const e of scope.querySelectorAll('[role="tab"], [data-tab], [data-target], [data-section], .quick-link, nav button, .header-controls button, #settings-btn, a[href^="#"]')) add(e, 'nav');
    for (const e of scope.querySelectorAll('.kebab-opener, [aria-haspopup="menu"]')) add(e, 'menu');
    for (const e of scope.querySelectorAll('.action-menu:not(.hidden) button, [role="menu"]:not(.hidden) [role="menuitem"]')) add(e, 'item');
    for (const e of scope.querySelectorAll('button')) { if (nav.test(txt(e))) add(e, 'btn'); }
    // The first of each repeated list: opening an item is a destination.
    for (const [sel, name] of [['#entry-list > li .card-open, #entry-list > li', 'a note'], ['.doc-list-item', 'a document'], ['#library-boards-grid .library-card', 'a board'], ['.library-card .card-open', 'a library card'], ['#chat-conversations li, .conv-item', 'a chat']]) {
      const e = [...scope.querySelectorAll(sel)].find(vis);
      if (e) out.set('list|' + name + (e.closest('[data-kind]') ? ' (' + e.closest('[data-kind]').dataset.kind + ')' : ''), 1);
    }
    return { sig, candidates: [...out.keys()] };
  }, { NAVISH: { s: NAVISH.source, f: NAVISH.flags }, DANGER: { s: DANGER.source, f: DANGER.flags } });
}

async function clickKey(page, key) {
  const [kind, ...rest] = key.split('|');
  const label = rest.join('|');
  const ok = await page.evaluate(({ kind, label }) => {
    const vis = (e) => { const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return b.width > 2 && b.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const txt = (e) => (e.getAttribute('aria-label') || e.title || e.textContent || '').trim().replace(/\s+/g, ' ').replace(/[“"][^”"]*[”"]/g, '').replace(/\d+/g, '#').slice(0, 48);
    const overlays = [...document.querySelectorAll('[role="dialog"], .modal-overlay, .confirm-overlay, .sheet, #palette-overlay, .panel-overlay, .drawer, [role="menu"]')].filter((o) => vis(o) && !o.classList.contains('hidden') && o.getBoundingClientRect().width > 120);
    const scope = overlays[overlays.length - 1] || document.body;
    let pool = [];
    if (kind === 'list') {
      const sels = { 'a note': '#entry-list > li .card-open, #entry-list > li', 'a document': '.doc-list-item', 'a board': '#library-boards-grid .library-card', 'a library card': '.library-card .card-open', 'a chat': '#chat-conversations li, .conv-item' };
      const name = label.replace(/ \(.*\)$/, '');
      const kindWant = (label.match(/\((.*)\)$/) || [])[1];
      pool = [...scope.querySelectorAll(sels[name] || 'x-none')].filter(vis).filter((e) => !kindWant || (e.closest('[data-kind]') || {dataset: {}}).dataset.kind === kindWant);
    } else if (kind === 'menu') pool = [...scope.querySelectorAll('.kebab-opener, [aria-haspopup="menu"]')].filter(vis).filter((e) => txt(e) === label);
    else if (kind === 'item') pool = [...scope.querySelectorAll('.action-menu:not(.hidden) button, [role="menu"]:not(.hidden) [role="menuitem"]')].filter(vis).filter((e) => txt(e) === label);
    else pool = [...scope.querySelectorAll('[role="tab"], [data-tab], [data-target], [data-section], .quick-link, nav button, .header-controls button, #settings-btn, a[href^="#"], button')].filter(vis).filter((e) => txt(e) === label);
    const e = pool[0];
    if (!e) return false;
    e.setAttribute('data-probe', '1');
    return true;
  }, { kind, label });
  if (!ok) return false;
  const done = await page.click('[data-probe="1"]', { timeout: 2500 }).then(() => true).catch(() => false);
  await page.evaluate(() => document.querySelectorAll('[data-probe]').forEach((e) => e.removeAttribute('data-probe')));
  return done;
}

async function home(page) {
  await L.closeOverlays(page);
  await page.evaluate(() => { try { closeActionMenus(); } catch (e) {} switchTab('dashboard'); });
  await page.waitForTimeout(500);
  await L.closeOverlays(page);
}
// Back to a node's state. A press that landed on an already-seen destination used
// to cost a full replay from the dashboard; closing overlays and reading the page
// is one round trip, and when it already is the node's state nothing is replayed.
let replays = 0, restores = 0;
async function restore(page, node) {
  await L.closeOverlays(page);
  const now = await look(page);
  if (now.sig === node.sig && JSON.stringify(now.candidates) === JSON.stringify(node.candidates)) { restores++; return true; }
  replays++;
  return replay(page, node.path);
}
async function replay(page, path) {
  await home(page);
  for (const key of path) {
    if (!(await clickKey(page, key))) return false;
    await page.waitForTimeout(420);
  }
  return true;
}

(async () => {
  const { browser, page } = await L.boot();
  await L.ensureSeed(page);
  // The crawl is split across WORKERS browsers (default 3, of four cores): each takes the next
  // node of the level from one queue, and `seen` and `pressed` are shared, so a destination or a
  // press is still done once. Depth 3 alone outran 40 minutes on one browser.
  const NW = Math.max(1, Number(process.env.WORKERS || 3));
  const pages = [page], browsers = [browser];
  for (let i = 1; i < NW; i++) { const b = await L.boot(); pages.push(b.page); browsers.push(b.browser); await home(b.page); }
  await home(page);
  const start = await look(page);
  const seen = new Map([[start.sig, { depth: 0, path: [], name: 'Dashboard' }]]);
  const report = async (doneDepth) => {
    const rows = [...seen.entries()].map(([sig, v]) => ({ sig, ...v })).sort((a, b) => a.depth - b.depth);
    console.log('\n===== REPORT after depth ' + doneDepth + ' =====\nALL DESTINATIONS (depth, path)');
    for (const r of rows) console.log(`${r.depth}  ${r.name}   [${r.sig}]`);
    const deep = rows.filter((r) => r.depth > 3);
    console.log(`\nDEEPER THAN 3: ${deep.length}`);
    for (const r of deep) console.log(`${r.depth}  ${r.name}`);

    // The palette's registry against the destinations.
    await home(page);
    const cmds = await page.evaluate(() => paletteCommands().map((c) => [c.label, c.keywords || '', c.about || '', c.tab || '', c.reveal || ''].join(' ').toLowerCase().replace(/ph:[a-z-]+/g, '')));
    // An 'About X' help popover is reached by the Guide's topic X (L-world-class-781): the Guide's
    // titles join the haystack as 'guide ...' rows, so the help branch below matches them.
    const guide = await page.evaluate(() => apiJson('/help/topics').then((l) => l.groups.flatMap((g) => g.topics.map((t) => 'guide ' + t.title.toLowerCase()))).catch(() => []));
    if (!guide.length) throw new Error('reach.js: GET /help/topics gave no Guide topics');
    cmds.push(...guide);
    console.log(`\nPALETTE: ${cmds.length - guide.length} commands (each one chord or one click away), Guide topics ${guide.length}`);
    const words = (s) => s.toLowerCase().replace(/&/g, ' and ').split(/[^a-z]+/).filter((w) => w.length > 2 && !['and', 'the', 'new', 'tab'].includes(w));
    const missing = [];
    for (const r of rows.filter((r) => r.depth > 0)) {
      const last = r.path[r.path.length - 1].split('|').slice(1).join('|').replace(/^(actions for|more actions).*/i, '');
      const w = words(last.replace(/\(.*$/, ''));
      if (!w.length) continue;
      if (/^(menu)\|/.test(r.path[r.path.length - 1])) continue;
      // A help popover (the '?' recipe) is reached by the Guide's topic of the same name, so it is matched
      // on its topic words alone, against every command and the Guide's own topic rows.
      if (/help|^about /i.test(last)) {
        // A plural label ('About accounts') names the singular topic ('Account and security').
        const topic = words(last.replace(/help|^about /gi, '')).map((x) => x.replace(/s$/, ''));
        if (!topic.length || cmds.some((c) => /guide|manual/.test(c) && topic.some((x) => c.includes(x)))) continue;
        if (cmds.some((c) => topic.filter((x) => c.includes(x)).length >= Math.ceil(topic.length * 0.7))) continue;
      }
      if (!cmds.some((c) => w.filter((x) => c.includes(x)).length >= Math.ceil(w.length * 0.7))) missing.push(r);
    }
    console.log(`DESTINATIONS WITH NO PALETTE COMMAND: ${missing.length} of ${rows.length - 1}`);
    for (const r of missing) console.log(`${r.depth}  ${r.name}`);
    const byDepth = {};
    for (const r of rows) byDepth[r.depth] = (byDepth[r.depth] || 0) + 1;
    console.log(`\nSUMMARY (${process.env.THEME || 'light'}): destinations ${rows.length}, by depth ${JSON.stringify(byDepth)}, deeper than 3: ${deep.length}, no palette command: ${missing.length}, palette commands ${cmds.length - guide.length}, Guide topics ${guide.length}`);
  };
  let frontier = [{ path: [], sig: start.sig, candidates: start.candidates, page: start.sig.split(' | ')[0] }];
  // The header and the tab bar are on every page: pressed from the first page
  // only, or each of them is pressed once per page for the same destination.
  const chrome = new Set(start.candidates.filter((k) => k.startsWith('nav|')));
  const pressed = new Set();
  const waitMs = Number(process.env.WAIT || 450);
  const T0 = Date.now();
  for (let depth = 1; depth <= MAXD; depth++) {
    const next = [];
    let n = 0;
    const queue = frontier.slice();
    const processNode = async (pg, node) => {
      n++;
      const inOverlay = / \| ON:/.test(node.sig);
      // Past depth 3 only the doors are pressed (tabs, menus, lists), not every button.
      const cands = node.candidates.filter((k) => !(chrome.has(k) && node.path.length > 0)
        && (depth <= 3 || /^(nav|menu|item|list)\|/.test(k)))
        .filter((k) => { const id = (inOverlay ? node.sig : node.page) + '#' + k; if (pressed.has(id)) return false; pressed.add(id); return true; });
      let inPlace = false;
      for (const key of cands.slice(0, Number(process.env.CAP || 45))) {
        if (!inPlace) { if (!(await restore(pg, node))) break; }
        if (!(await clickKey(pg, key))) { inPlace = false; continue; }
        await pg.waitForTimeout(waitMs);
        const now = await look(pg);
        // Nothing opened: the page is as it was, no replay needed for the next press.
        inPlace = now.sig === node.sig && JSON.stringify(now.candidates) === JSON.stringify(node.candidates);
        if (seen.has(now.sig)) continue;
        const path = [...node.path, key];
        seen.set(now.sig, { depth, path, name: path.map((k) => k.split('|').slice(1).join('|')).join(' > ') });
        if (depth < MAXD) next.push({ path, sig: now.sig, candidates: now.candidates, page: now.sig.split(' | ')[0] });
      }
      if (process.env.DEBUG) console.log(`  depth ${depth} node ${n}/${frontier.length} done, ${seen.size} destinations, ${Math.round((Date.now() - T0) / 1000)}s`);
    };
    await Promise.all(pages.map(async (pg) => { for (let node; (node = queue.shift());) await processNode(pg, node); }));
    console.log(`depth ${depth} (${Math.round((Date.now() - T0) / 1000)}s, ${NW} browsers): replays ${replays}, cheap restores ${restores}, ${[...seen.values()].filter((s) => s.depth === depth).length} new destinations (frontier ${next.length})`);
    frontier = next;
    await report(depth);
  }
  await Promise.all(browsers.map((b) => b.close()));
})();
