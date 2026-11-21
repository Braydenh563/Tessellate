// Every menu in the app, opened and measured (INBOX 403: "poorly designed
// dropdown menus with bad widths, poor spacing, poor alignment").
//
//   BASE=http://127.0.0.1:8813 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     WIDTHS=1440,1024,390 THEME=light node scratchpad/ui-sweeps/menus.js
//
// **Discovered, not listed.** A list of menus written here is out of date the
// day somebody adds one, which is how the earlier version of this file came to
// check five menus in an app with sixty. So each surface (every tab, sub-tab,
// an open document, an open board and map, every Settings pane, the chrome) is
// searched for anything that opens a menu: `aria-haspopup`, a `details` whose
// body is a dock menu, the enhanced select's opener, the board's menu toggles.
// One opener per (label, list) is opened, so fifty note rows cost one kebab.
//
// What is measured on each, and the rule it answers to:
//   width     the menu's own box against its `max-content` width: a label cut
//             off or ellipsised is a finding, and so is a menu more than twice
//             as wide as what it holds.
//   rows      one height among single-line rows, one left padding.
//   column    per column of the menu (the board's View has two): every
//             command row starts (icon or first letter) on one x, the labels
//             after an icon on one x, and a section label or a select in a
//             section on the rows' x, all within 1px.
//   groups    a menu (not a listbox) past five rows draws a separator.
//   place     within 8px of its opener on the axis it opens along, lined up
//             with an edge of it on the other, and never past the window.
//   keys      ArrowDown puts focus (or `aria-activedescendant`) in the menu;
//             Escape closes it and gives focus back to the opener.
// A phone's action sheet is a sheet, so placement and width are not asked of
// it; rows, labels and keys still are.
//
// Prints findings only, then one count line per width.
const { chromium } = require('playwright');
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const WIDTHS = (process.env.WIDTHS || '1440,1024,390').split(',').map(Number);
const THEME = process.env.THEME || 'light';
const ONLY = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const VERBOSE = !!process.env.VERBOSE;

const TABS = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];
const SUBTABS = {
  notes: ['browse', 'capture', 'writing-room', 'ask'],
  library: ['docs', 'boards', 'images', 'files', 'skills', 'links', 'contents'],
};
const SECTIONS = ['account', 'appearance', 'preferences', 'models', 'tools', 'skills', 'personas',
  'templates', 'websearch', 'memory', 'tasks', 'data', 'logs', 'shortcuts', 'extras', 'help', 'about'];

// Runs in the page: tag every visible opener in `scope` with data-mm-op=n and
// return one descriptor per distinct (kind, label, list).
function findOpeners(scopeSel) {
  const vis = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true })
    && e.getBoundingClientRect().width > 0;
  const roots = scopeSel.split('|').map((s) => document.querySelector(s)).filter(Boolean);
  const seen = new Set();
  const out = [];
  const sel = [
    'button[aria-haspopup]:not([aria-haspopup="false"]):not([aria-haspopup="dialog"])',
    'details:has(> .doc-dock-menu-list) > summary',
    'details.dock-menu > summary',
    'details.doc-toolbar-menu > summary',
    '.select-opener',
    '[data-wb-menu-toggle]',
  ].join(',');
  for (const root of roots) {
    for (const el of root.querySelectorAll(sel)) {
      if (!vis(el)) continue;
      if (el.closest('.action-menu, .select-menu, .doc-dock-menu-list, [role="menu"], [role="listbox"]')) continue;
      const kind = el.matches('.select-opener') ? 'select'
        : el.tagName === 'SUMMARY' ? 'details'
          : el.matches('[data-wb-menu-toggle]') ? 'wbmenu' : 'popup';
      const label = (el.getAttribute('aria-label') || el.title || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
      let host = el.parentElement;
      while (host && !host.id) host = host.parentElement;
      //: A row's own name is not part of what makes its menu a different
      //: menu: "Actions for Weekly review" and "Actions for Reading list" are
      //: one kebab, opened once.
      const shape = label.replace(/^((?:more )?actions for|actions for the (?:link|reminder)(?: to)?)\b.*$/i, '$1');
      const key = `${kind}|${shape}|${host ? host.id : ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      //: A counter, not a count of what is tagged: a list re-rendered since
      //: the last surface drops its tags, and a count would hand the next
      //: opener a number something still on the page is carrying.
      const n = (window.__mmN = (window.__mmN || 0) + 1);
      el.setAttribute('data-mm-op', String(n));
      out.push({ n, kind, label, host: host ? host.id : '', id: el.id });
    }
  }
  return out;
}

// Runs in the page before a click: mark every menu-like surface already
// showing, so the one the click opened is the one not marked.
function markOpen(sel) {
  for (const e of document.querySelectorAll('[data-mm-was]')) e.removeAttribute('data-mm-was');
  for (const e of document.querySelectorAll(sel)) {
    if (e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true })) e.setAttribute('data-mm-was', '1');
  }
}

function MENU_SEL_IN_PAGE() {
  return '[role="menu"], [role="listbox"], .action-menu, .select-menu, .doc-dock-menu-list, .wb-board-menu, .sheet, [class*="-menu"]:not(button):not(details):not(summary):not(.menu-wrap):not(.menu-item)';
}

// Runs in the page after the click: find the new menu and measure it.
function measure(opIdx) {
  const opener = document.querySelector(`[data-mm-op="${opIdx}"]`);
  const visible = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true })
    && e.getBoundingClientRect().width > 2 && e.getBoundingClientRect().height > 2;
  const sel = '[role="menu"], [role="listbox"], .action-menu, .select-menu, .doc-dock-menu-list, .wb-board-menu, .sheet';
  let cands = [...document.querySelectorAll(sel)].filter((e) => visible(e) && !e.hasAttribute('data-mm-was')
    && !e.classList.contains('submenu'));
  const ctl = opener && opener.getAttribute('aria-controls') && document.getElementById(opener.getAttribute('aria-controls'));
  if (ctl && visible(ctl)) cands = [ctl];
  if (opener && opener.tagName === 'SUMMARY') {
    const d = opener.parentElement;
    const body = d.open && [...d.children].find((c) => c !== opener && visible(c));
    if (body) cands = [body];
  }
  // outermost only
  cands = cands.filter((c) => !cands.some((o) => o !== c && o.contains(c)));
  if (!cands.length) {
    return { none: true, expanded: opener && opener.getAttribute('aria-expanded') };
  }
  let menu = cands[0];
  // A sheet holds the menu; measure the list inside it.
  const inner = menu.matches('.sheet') && menu.querySelector('[role="menu"], [role="listbox"], .action-menu');
  if (inner) menu = inner;
  const isSheet = !!menu.closest('.sheet, [class*="sheet"]');
  const role = menu.getAttribute('role') || '';
  const mr = menu.getBoundingClientRect();
  const or = opener ? opener.getBoundingClientRect() : null;
  //: **Command rows**, the things a menu is a list of. A labelled select or a
  //: segmented control inside a dock menu is a form row with its own shape,
  //: so it answers to the section-label rule below, not to the row rules.
  const rowSel = '[role^="menuitem"], [role="option"], .menu-item, .doc-dock-menu-item, .wb-menu-item, .select-option, .nav-history-item, .doc-dock-menu-check, .dock-menu-check, .space-menu-item';
  const menuW = mr.width;
  let rows = [...menu.querySelectorAll(rowSel)].filter((e) => visible(e) && !e.closest('.segmented-control')
    && !(e.closest('.select-menu') && !menu.matches('.select-menu')));
  rows = rows.filter((r) => !rows.some((o) => o !== r && o.contains(r)));
  rows = rows.filter((r) => r.getBoundingClientRect().height < 120 && r.getBoundingClientRect().width > menuW * 0.4);
  const iconOf = (r) => {
    const i = r.querySelector('i.ph, svg, img, .swatch, [class*="dot"], input[type="checkbox"], input[type="radio"]');
    if (!i || !visible(i)) return null;
    const rr = r.getBoundingClientRect();
    const ir = i.getBoundingClientRect();
    // a trailing mark (a chevron, a check at the end) is not the icon column
    if (ir.left - rr.left > rr.width / 2) return null;
    return ir;
  };
  const textStart = (r) => {
    const tw = document.createTreeWalker(r, NodeFilter.SHOW_TEXT, {
      acceptNode: (t) => (t.textContent.trim() && !t.parentElement.closest('[aria-hidden="true"], .ph, i, kbd, .kbd, [class*="shortcut"], [class*="hint"], [class*="count"], [class*="badge"]'))
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
    });
    const t = tw.nextNode();
    if (!t) return null;
    const range = document.createRange();
    range.selectNodeContents(t);
    const rects = [...range.getClientRects()].filter((x) => x.width > 0);
    return rects.length ? { x: rects[0].left, text: t.textContent.trim().slice(0, 24), lines: new Set(rects.map((x) => Math.round(x.top))).size } : null;
  };
  const r1 = (v) => Math.round(v * 10) / 10;
  const rowInfo = rows.map((r) => {
    const cs = getComputedStyle(r);
    const rr = r.getBoundingClientRect();
    const lx = textStart(r);
    const ic = iconOf(r);
    const clipped = [r, ...r.querySelectorAll('*')].some((e) => {
      if (!visible(e)) return false;
      const c = getComputedStyle(e);
      if (c.overflowX === 'visible' && c.textOverflow !== 'ellipsis') return false;
      return e.scrollWidth > e.clientWidth + 1;
    });
    const lead = Math.min(ic ? ic.left : Infinity, lx ? lx.x : Infinity);
    return {
      text: lx ? lx.text : (r.getAttribute('aria-label') || '').slice(0, 24),
      h: r1(rr.height), pl: cs.paddingLeft, lx: lx ? r1(lx.x) : null,
      icon: ic ? r1(ic.left) : null, lead: Number.isFinite(lead) ? r1(lead) : null,
      clipped, multi: lx ? lx.lines > 1 : false,
      tall: r.querySelectorAll('small, .menu-desc, [class*="desc"], [class*="meta"]').length > 0,
      left: Math.round(rr.left),
    };
  });
  //: Section labels and form rows: their first letter or box edge should
  //: stand on the column the command rows' icons stand on.
  const heads = [...menu.querySelectorAll('.dock-menu-label, .wb-panel-group-label, .select-group-label, .menu-group-label, .wb-menu-row > span:first-child, .dock-menu-section > .select-shell > .select-opener, .dock-menu-section > .segmented-control')]
    .filter(visible).map((h) => {
      const t = h.matches('.select-opener, .segmented-control') ? { x: h.getBoundingClientRect().left, text: '[' + (h.getAttribute('aria-label') || h.className.split(' ')[0]).slice(0, 18) + ']' } : textStart(h);
      return t ? { text: t.text, x: r1(t.x), left: Math.round(h.getBoundingClientRect().left) } : null;
    }).filter(Boolean);
  const seps = [...menu.querySelectorAll('[role="separator"], .menu-sep, hr, .doc-dock-menu-sep, [class*="-sep"], [class*="divider"]')]
    // A hairline is 1px tall, which `visible` (more than 2px) would drop.
    .filter((e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true }) && e.getBoundingClientRect().width > 2).length;
  const sections = [...menu.querySelectorAll('[role="group"], .wb-menu-section, [class*="section"], [class*="heading"], [class*="-label"]')].filter(visible).length;
  // natural width
  const saved = [menu.style.width, menu.style.minWidth, menu.style.maxWidth];
  menu.style.width = 'max-content'; menu.style.minWidth = '0'; menu.style.maxWidth = 'none';
  const natural = menu.getBoundingClientRect().width;
  [menu.style.width, menu.style.minWidth, menu.style.maxWidth] = saved;
  const cs = getComputedStyle(menu);
  //: **Insets** (INBOX, menu gaps: "some dropdown menus across the app have
  //: wierd gaps at the start and end"): the first and last things drawn in
  //: the menu, text, a control, a row or a hairline, sit one menu padding
  //: from its edge. Measured from the leaves, so a wrapper's own padding or
  //: an empty leading label is the gap it adds rather than hidden by it.
  const leaves = [...rows.map((r) => r.getBoundingClientRect())];
  for (const e of menu.querySelectorAll('button, input, select, textarea, [role="separator"], .menu-sep, hr, .select-opener, .segmented-control, .seg')) {
    if (e.checkVisibility && e.checkVisibility({ visibilityProperty: true }) && e.getBoundingClientRect().width > 2) leaves.push(e.getBoundingClientRect());
  }
  const tw = document.createTreeWalker(menu, NodeFilter.SHOW_TEXT, { acceptNode: (t) => t.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  for (let t = tw.nextNode(); t; t = tw.nextNode()) {
    if (!t.parentElement.checkVisibility || !t.parentElement.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
    const range = document.createRange();
    range.selectNodeContents(t);
    for (const x of range.getClientRects()) if (x.width > 0) leaves.push(x);
  }
  const scrolls = menu.scrollHeight > menu.clientHeight + 1;
  const inset = leaves.length && !scrolls ? {
    top: r1(Math.min(...leaves.map((x) => x.top)) - mr.top - parseFloat(cs.borderTopWidth)),
    bottom: r1(mr.bottom - parseFloat(cs.borderBottomWidth) - Math.max(...leaves.map((x) => x.bottom))),
    pt: parseFloat(cs.paddingTop), pb: parseFloat(cs.paddingBottom),
  } : null;
  return {
    inset,
    role, isSheet, cls: menu.className.toString().slice(0, 60), id: menu.id,
    box: { l: Math.round(mr.left), t: Math.round(mr.top), r: Math.round(mr.right), b: Math.round(mr.bottom), w: Math.round(mr.width), h: Math.round(mr.height) },
    op: or ? { l: Math.round(or.left), t: Math.round(or.top), r: Math.round(or.right), b: Math.round(or.bottom) } : null,
    natural: Math.round(natural), vw: innerWidth, vh: innerHeight,
    overflowX: menu.scrollWidth > menu.clientWidth + 1 && getComputedStyle(menu).overflowX !== 'visible',
    rows: rowInfo, heads, seps, sections,
    //: A menu of switches or an icon grid (the board's shapes) has no
    //: command rows to line up, and is not empty for it.
    controls: [...menu.querySelectorAll('button, input, a[href], [tabindex="0"]')].filter((e) => e.getClientRects().length).length,
    sig: `bg=${cs.backgroundColor} r=${cs.borderTopLeftRadius} bd=${cs.borderTopWidth}`,
    focusIn: menu.contains(document.activeElement),
  };
}

function judge(m) {
  const f = [];
  const rows = m.rows;
  if (!rows.length && !m.heads.length && !m.controls) { f.push('nothing in it to press'); return f; }
  const clipped = rows.filter((r) => r.clipped).map((r) => r.text);
  if (clipped.length) f.push(`clipped labels: ${JSON.stringify(clipped.slice(0, 4))}`);
  if (m.overflowX) f.push('menu scrolls sideways');
  if (!m.isSheet && m.natural > 0 && m.box.w > 2 * m.natural + 8) f.push(`too wide: ${m.box.w}px for ${m.natural}px of content`);
  const single = rows.filter((r) => !r.multi && !r.tall);
  const hs = [...new Set(single.map((r) => r.h))];
  if (hs.length > 1 && Math.max(...hs) - Math.min(...hs) > 1) {
    const counts = {};
    for (const r of single) counts[r.h] = (counts[r.h] || 0) + 1;
    const mode = +Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
    f.push(`row heights ${JSON.stringify(hs)}; off: ${JSON.stringify(single.filter((r) => Math.abs(r.h - mode) > 1).map((r) => `${r.text}=${r.h}`).slice(0, 4))}`);
  }
  //: A row's own box starts at the menu's padding; text inside a row sits
  //: lower by the row's padding, so the allowance is half a row's height.
  if (m.inset && !m.isSheet) {
    const rowPad = rows.length ? Math.min(...rows.map((r) => r.h)) / 2 : 0;
    const slack = Math.max(m.inset.pt, m.inset.pb) + rowPad + 2;
    if (m.inset.top > slack || m.inset.bottom > slack || Math.abs(m.inset.top - m.inset.bottom) > Math.max(6, rowPad)) {
      f.push(`inset top ${m.inset.top} bottom ${m.inset.bottom} (padding ${m.inset.pt}/${m.inset.pb})`);
    }
  }
  const pls = [...new Set(rows.map((r) => r.pl))];
  if (pls.length > 1) f.push(`row padding-left ${JSON.stringify(pls)}`);
  //: Columns: a two-column menu (the board's View) is judged per column.
  const cols = [];
  for (const r of [...rows, ...m.heads.map((h) => ({ ...h, head: true }))]) {
    const x = r.left;
    let c = cols.find((cc) => Math.abs(cc.x - x) < 60);
    if (!c) cols.push(c = { x, items: [] });
    c.items.push(r);
  }
  const spreadOf = (xs) => Math.max(...xs) - Math.min(...xs);
  const modeOf = (xs) => { const n = {}; for (const x of xs) n[Math.round(x)] = (n[Math.round(x)] || 0) + 1; return +Object.entries(n).sort((a, b) => b[1] - a[1])[0][0]; };
  for (const c of cols) {
    const cr = c.items.filter((r) => !r.head && r.lead !== null);
    if (cr.length > 1 && spreadOf(cr.map((r) => r.lead)) > 1) {
      const mode = modeOf(cr.map((r) => r.lead));
      f.push(`rows start on ${new Set(cr.map((r) => Math.round(r.lead))).size} x; off: ${JSON.stringify(cr.filter((r) => Math.abs(r.lead - mode) > 1).map((r) => `${r.text}@${(r.lead - mode).toFixed(1)}`).slice(0, 4))}`);
    }
    const withIcon = cr.filter((r) => r.icon !== null && r.lx !== null);
    if (withIcon.length > 1 && spreadOf(withIcon.map((r) => r.lx)) > 1) {
      const mode = modeOf(withIcon.map((r) => r.lx));
      f.push(`labels after icons on ${new Set(withIcon.map((r) => Math.round(r.lx))).size} x; off: ${JSON.stringify(withIcon.filter((r) => Math.abs(r.lx - mode) > 1).map((r) => `${r.text}@${(r.lx - mode).toFixed(1)}`).slice(0, 4))}`);
    }
    const hs = c.items.filter((r) => r.head);
    if (hs.length && cr.length) {
      const mode = modeOf(cr.map((r) => r.lead));
      const off = hs.filter((h) => Math.abs(h.x - mode) > 1);
      if (off.length) f.push(`section labels off the row column; off: ${JSON.stringify(off.map((h) => `${h.text}@${(h.x - mode).toFixed(1)}`).slice(0, 4))}`);
    } else if (hs.length > 1 && spreadOf(hs.map((h) => h.x)) > 1) {
      f.push(`section labels on ${new Set(hs.map((h) => Math.round(h.x))).size} x`);
    }
  }
  if (m.role === 'menu' && rows.length > 5 && !m.seps && !m.sections) f.push(`${rows.length} rows, no groups`);
  if (!m.isSheet && m.op) {
    const { box: b, op: o } = m;
    if (b.l < -0.5 || b.t < -0.5 || b.r > m.vw + 0.5 || b.b > m.vh + 0.5) f.push(`off window: ${JSON.stringify(b)} in ${m.vw}x${m.vh}`);
    const below = b.t >= o.b - 2, above = b.b <= o.t + 2;
    const gap = below ? b.t - o.b : above ? o.t - b.b : null;
    if (gap !== null && gap > 8) f.push(`${gap}px from its opener`);
    if (gap === null) {
      // beside, or over the opener
      const side = b.l >= o.r - 2 ? b.l - o.r : b.r <= o.l + 2 ? o.l - b.r : null;
      if (side !== null && side > 8) f.push(`${side}px beside its opener`);
      if (side === null) f.push('covers its opener');
    } else {
      const aligned = Math.abs(b.l - o.l) <= 8 || Math.abs(b.r - o.r) <= 8 || (b.l <= o.l && b.r >= o.r);
      if (!aligned) f.push(`not lined up with its opener: menu ${b.l}-${b.r}, opener ${o.l}-${o.r}`);
    }
  }
  return f;
}

// Escape only while something is open: with nothing open it is the Settings
// modal's own close key, and pressing it blind ended the Settings pass after
// its first pane.
async function closeAll(page) {
  const open = await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden), .select-menu:not(.hidden), details[open] > .doc-dock-menu-list, .wb-board-menu:not(.hidden):not([hidden]), .sheet')]
    .some((e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true })));
  if (open) await page.keyboard.press('Escape').catch(() => {});
  await page.evaluate(() => {
    try { if (typeof closeActionMenus === 'function') closeActionMenus(); } catch (e) {}
    for (const d of document.querySelectorAll('details[open]')) {
      if (d.querySelector(':scope > .doc-dock-menu-list') || d.matches('.dock-menu, .doc-toolbar-menu')) d.open = false;
    }
    for (const b of document.querySelectorAll('.select-menu:not(.hidden)')) b.classList.add('hidden');
  }).catch(() => {});
  await page.waitForTimeout(150);
}

async function sweepSurface(page, where, scope, out, restore) {
  await page.mouse.move(2, 2);
  const ops = await page.evaluate(findOpeners, scope);
  for (const op of ops) {
    if (ONLY && !ONLY.test(`${where} ${op.label}`)) continue;
    await closeAll(page);
    if (restore) await restore();
    await page.evaluate(markOpen, MENU_SEL_IN_PAGE());
    //: Scrolled to and settled first: Playwright's own scroll-into-view lands
    //: its scroll event after the click, and every menu here closes on a
    //: scroll, so an opener below the fold read as "nothing opened". A person
    //: scrolls, stops, then clicks. A disabled opener is not a menu to open.
    const state = await page.evaluate((n) => {
      const el = document.querySelector(`[data-mm-op="${n}"]`);
      if (!el) return 'gone';
      if (el.disabled || el.getAttribute('aria-disabled') === 'true') return 'disabled';
      el.scrollIntoView({ block: 'center' });
      return el.getBoundingClientRect().width ? 'ok' : 'no box';
    }, op.n);
    if (state !== 'ok') { if (VERBOSE) out.push(`${where} :: ${op.kind} "${op.label}": ${state}`); continue; }
    await page.waitForTimeout(250);
    //: A row's ⋯ that shows on hover (the reminder rows) takes no clicks
    //: until the pointer is over its row, which is how a person reaches it.
    await page.hover(`[data-mm-op="${op.n}"]`, { force: true, timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(150);
    const clicked = await page.click(`[data-mm-op="${op.n}"]`, { timeout: 2500 }).then(() => true).catch((e) => String(e).split('\n')[0].slice(0, 90));
    const name = `${where} :: ${op.kind} "${op.label}"${op.host ? ' in #' + op.host : ''}`;
    if (clicked !== true) { out.push(`${name}: could not click (${clicked})`); continue; }
    await page.waitForTimeout(350);
    await page.mouse.move(2, 2);
    let m = await page.evaluate(measure, op.n);
    if (m.none) {
      //: A split button (the board's shape tool) picks its tool on a click
      //: and opens from its caret or the keyboard: try the keyboard's way.
      await page.evaluate((n) => document.querySelector(`[data-mm-op="${n}"]`)?.focus(), op.n);
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(300);
      m = await page.evaluate(measure, op.n);
    }
    if (m.none) {
      out.push(`${name}: nothing opened (aria-expanded=${m.expanded})`);
      continue;
    }
    const f = judge(m);
    // keyboard
    const focusBefore = await page.evaluate(() => { window.__mmFocus = document.activeElement; return document.activeElement && (document.activeElement.id || document.activeElement.className.toString().slice(0, 30)); });
    if (op.label === 'Choose an option') f.push('opener has no name of its own ("Choose an option")');
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(120);
    const k1 = await page.evaluate((n) => {
      const op = document.querySelector(`[data-mm-op="${n}"]`);
      const a = document.activeElement;
      const menus = [...document.querySelectorAll('[role="menu"], [role="listbox"], .action-menu, .select-menu, .doc-dock-menu-list, .wb-board-menu, .sheet')].filter((e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true }));
      const inMenu = menus.some((mm) => mm.contains(a));
      const ad = (a && a.getAttribute('aria-activedescendant')) || (op && op.getAttribute('aria-activedescendant'));
      return { inMenu, ad: !!ad, moved: a !== window.__mmFocus, a: a ?`${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}.${a.className.toString().split(' ')[0]}` : '' };
    }, op.n);
    if (!k1.inMenu && !k1.ad) f.push(`ArrowDown leaves focus on ${k1.a} (was ${focusBefore})`);
    //: Already in the menu (a select opens on its chosen row) is not proof
    //: the arrows work: with two rows or more, ArrowDown has to move.
    else if (k1.inMenu && !k1.moved && m.rows.length > 1) f.push(`ArrowDown does not move (stays on ${k1.a})`);
    //: And a second press walks on: the first can land by the opener's
    //: rule, the second is the menu's own.
    if (k1.inMenu && m.rows.length > 2) {
      await page.evaluate(() => { window.__mmFocus = document.activeElement; });
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(100);
      const moved = await page.evaluate(() => document.activeElement !== window.__mmFocus && !document.activeElement.matches('body'));
      if (!moved) f.push('a second ArrowDown does not walk the menu');
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const k2 = await page.evaluate((n) => {
      const op = document.querySelector(`[data-mm-op="${n}"]`);
      const menus = [...document.querySelectorAll('[role="menu"], [role="listbox"], .action-menu:not(.submenu), .select-menu, .doc-dock-menu-list, .wb-board-menu, .sheet')]
        .filter((e) => !e.hasAttribute('data-mm-was') && e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && e.getBoundingClientRect().height > 2);
      const a = document.activeElement;
      const back = !!op && (a === op || op.contains(a) || (a && a.contains(op) && a.tagName === 'DETAILS'));
      return { stillOpen: menus.length, back, a: a ? `${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}.${a.className.toString().split(' ')[0]}` : '' };
    }, op.n);
    if (k2.stillOpen) f.push('Escape does not close it');
    else if (!k2.back) f.push(`Escape leaves focus on ${k2.a}, not the opener`);
    if (f.length) out.push(`${name} [${m.role || m.cls.split(' ')[0]}${m.isSheet ? ', sheet' : ''}, ${m.rows.length} rows, ${m.box.w}px]: ${f.join('; ')}`);
    else if (VERBOSE) out.push(`${name}: ok (${m.rows.length} rows, ${m.box.w}/${m.natural}px) ${m.sig}`);
    out.count = (out.count || 0) + 1;
  }
}

(async () => {
  const browser = await chromium.launch();
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width, height: width < 600 ? 844 : 900 }, deviceScaleFactor: 1,
      hasTouch: width < 600, isMobile: width < 600,
    });
    await ctx.addInitScript((t) => {
      try {
        localStorage.setItem('theme', t);
        localStorage.setItem('onboardingDone', '1');
        localStorage.setItem('tourDone', '1');
      } catch (e) {}
    }, THEME);
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(e.message.slice(0, 140)));
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
    await page.fill('#lock-password', PW);
    await page.click('#lock-submit');
    await page.waitForTimeout(2500);
    await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
    const out = [];
    const chrome = '#app-header|header|#status-bar|.tab-bar|nav';
    await sweepSurface(page, 'chrome', chrome, out);
    for (const t of TABS) {
      await closeAll(page);
      await page.evaluate((n) => { try { switchTab(n); } catch (e) {} }, t);
      await page.waitForTimeout(900);
      const subs = SUBTABS[t] || [null];
      for (const s of subs) {
        if (s) {
          const ok = await page.click(`#tab-${t} [data-section="${s}"], #tab-${t} [data-view="${s}"]`, { timeout: 1500 }).then(() => true).catch(() => false);
          if (!ok) { await page.evaluate(([tt, ss]) => { const b = document.querySelector(`#tab-${tt} [data-section="${ss}"], #tab-${tt} [data-view="${ss}"]`); if (b) b.click(); }, [t, s]); }
          await page.waitForTimeout(700);
        }
        await sweepSurface(page, s ? `${t}/${s}` : t, `#tab-${t}`, out);
      }
    }
    // an open document
    await closeAll(page);
    const docOk = await page.evaluate(async () => {
      try { const r = await api('/documents'); const j = await r.json(); const list = Array.isArray(j) ? j : (j.documents || j.items || []); if (!list.length) return false; switchTab('documents'); await openDocument(list[0].id); return true; } catch (e) { return String(e); }
    });
    await page.waitForTimeout(1200);
    if (docOk === true) await sweepSurface(page, 'documents/open', '#tab-documents', out); else out.push(`documents: could not open one (${docOk})`);
    // a board and a map
    for (const kind of ['board', 'map']) {
      await closeAll(page);
      const ok = await page.evaluate(async (k) => {
        try { const r = await api('/whiteboard/boards'); const j = await r.json(); const list = Array.isArray(j) ? j : (j.boards || []); const b = list.find((x) => (x.type || 'board') === k); if (!b) return 'none of kind ' + k; switchTab('whiteboard'); await openWhiteboardBoard(b.id); return true; } catch (e) { return String(e); }
      }, kind);
      await page.waitForTimeout(1500);
      if (ok === true) await sweepSurface(page, `board/${kind}`, '#whiteboard-container|#whiteboard-sidebar|.wb-topbar|#tab-library', out); else out.push(`board/${kind}: ${ok}`);
    }
    // Settings
    await closeAll(page);
    await page.evaluate(() => { try { switchTab('dashboard'); } catch (e) {} });
    await page.waitForTimeout(500);
    const opened = await page.evaluate(() => { const b = document.getElementById('settings-btn'); if (b) { b.click(); return true; } try { openSettings(); return true; } catch (e) { return false; } });
    await page.waitForTimeout(700);
    if (opened) {
      for (const s of SECTIONS) {
        await page.evaluate((ss) => {
          const m = document.getElementById('settings-modal');
          if (m && m.classList.contains('hidden')) document.getElementById('settings-btn').click();
          const b = document.querySelector(`#settings-modal [data-section="${ss}"]`); if (b) b.click();
        }, s);
        await page.waitForTimeout(400);
        const restore = () => page.evaluate((ss) => {
          const m = document.getElementById('settings-modal');
          if (m && m.classList.contains('hidden')) {
            document.getElementById('settings-btn').click();
            const b = document.querySelector(`#settings-modal [data-section="${ss}"]`); if (b) b.click();
          }
        }, s).then(() => page.waitForTimeout(250));
        await sweepSurface(page, `settings/${s}`, '#settings-modal', out, restore);
      }
    }
    console.log(`== ${width}px ${THEME}: ${out.count || 0} menus opened, ${out.length} findings, ${errs.length} page errors`);
    for (const l of out) console.log('  ' + l);
    for (const e of [...new Set(errs)]) console.log('  PAGEERROR ' + e);
    await ctx.close();
  }
  await browser.close();
})();
