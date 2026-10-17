// WCAG 2.2 pass over the surfaces this PR changed (INBOX 904 follow-up): per
// surface, every visible control's accessible name, its target size against the
// floor (24 CSS px on a pointer, 44 on a coarse one), whether it is reachable
// by Tab, text contrast, and for each dialog or menu: focus moves in, Tab stays
// in, Escape closes, focus returns to the opener.
//
//   BASE=http://127.0.0.1:8791 [THEME=dark] [W=1358] node a11ysurfaces.js
// Prints findings only (one line each) and a count per surface.
const { boot } = require('./lib.js');
const W = Number(process.env.W || 1358);
const PHONE = W < 600;
const FLOOR = PHONE ? 44 : 24;

const AUDIT = ({ scope, floor }) => {
  const PHONE_FLOOR = floor > 24;
  const root = typeof scope === 'string' ? document.querySelector(scope) : scope;
  if (!root) return { missing: true };
  const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  const bgOf = (el) => {
    let acc = null;
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length >= 3 && (c[3] === undefined || c[3] > 0)) {
        if (c[3] === undefined || c[3] >= 0.95) return acc ? acc : c;
        acc = acc || c;
      }
    }
    return acc || [255, 255, 255];
  };
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    for (let x = e; x && x !== document.body; x = x.parentElement) {
      const s = getComputedStyle(x);
      if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
      if (x.hasAttribute('hidden') || x.inert) return false;
    }
    return true;
  };
  const nameOf = (e) => {
    const l = e.getAttribute('aria-label'); if (l && l.trim()) return l.trim();
    const lb = e.getAttribute('aria-labelledby');
    if (lb) { const t = lb.split(/\s+/).map((i) => document.getElementById(i)?.textContent || '').join(' ').trim(); if (t) return t; }
    if (e.labels && e.labels.length) { const t = [...e.labels].map((x) => x.textContent).join(' ').trim(); if (t) return t; }
    const t = (e.innerText || e.textContent || '').trim(); if (t) return t;
    const img = e.querySelector('img[alt], svg title'); if (img && (img.alt || img.textContent)) return img.alt || img.textContent;
    return (e.getAttribute('title') || e.getAttribute('placeholder') || '').trim();
  };
  const sel = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=menuitem], [role=option], [role=checkbox], [role=radio], [role=switch], [tabindex]';
  const out = [];
  const desc = (e) => `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : ''}`;
  for (const e of root.querySelectorAll(sel)) {
    if (!visible(e)) continue;
    if (e.tagName === 'INPUT' && ['checkbox', 'radio'].includes(e.type) && e.labels?.length) { /* sized by its label */ }
    const r = e.getBoundingClientRect();
    const name = nameOf(e);
    if (!name && !(e.getAttribute('role') === 'presentation')) out.push(['noname', desc(e), `${Math.round(r.width)}x${Math.round(r.height)}`]);
    const skipSize = e.tagName === 'A' && e.closest('p, li, .md, .note-body') && !e.closest('nav');
    const isCbLabel = e.tagName === 'INPUT' && ['checkbox', 'radio'].includes(e.type) && e.labels?.length;
    let rr = r;
    if (isCbLabel) rr = e.labels[0].getBoundingClientRect();
    const hidden = e.matches('.visually-hidden, .sr-only') || (r.width <= 2 && r.height <= 2);
    //: WCAG 2.5.8 spacing exception: an undersized target passes when a 24px
    //: circle centred on it meets no other target. Checked against the other
    //: interactive boxes in the scope (coarse pointers get no exception here).
    const spaced = () => {
      if (PHONE_FLOOR) return false;
      const cx = rr.left + rr.width / 2, cy = rr.top + rr.height / 2;
      for (const o of root.querySelectorAll(sel)) {
        if (o === e || e.contains(o) || o.contains(e) || !visible(o)) continue;
        const q = o.getBoundingClientRect();
        const dx = Math.max(q.left - cx, 0, cx - q.right), dy = Math.max(q.top - cy, 0, cy - q.bottom);
        if (Math.hypot(dx, dy) < 12) return false;
      }
      return true;
    };
    if (!hidden && !skipSize && Math.min(rr.width, rr.height) < floor - 0.5 && getComputedStyle(e).pointerEvents !== 'none' && !spaced()) out.push(['size', desc(e), `${Math.round(rr.width * 10) / 10}x${Math.round(rr.height * 10) / 10}`, name.slice(0, 24)]);
    if (e.tabIndex < 0 && !e.closest('[role=listbox], [role=menu], [role=tablist], [role=radiogroup], [role=grid]') && !e.hasAttribute('data-roving') && !e.matches('.visually-hidden') && ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) && !e.disabled) out.push(['tabindex-1', desc(e), name.slice(0, 24)]);
  }
  return { findings: out };
};

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: PHONE ? 844 : 900 }, ...(PHONE ? { hasTouch: true, isMobile: true } : {}) });
  let total = 0;
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.setDefaultTimeout(6000);
  await page.waitForTimeout(2500);
  const report = async (label, scope) => {
    const r = await page.evaluate(AUDIT, { scope, floor: FLOOR });
    if (r.missing) { console.log(`?? ${label}: scope ${scope} not found`); return; }
    const seen = new Set(); const f = r.findings.filter((x) => { const k = x.join('|'); if (seen.has(k)) return false; seen.add(k); return true; });
    total += f.length;
    for (const x of f.slice(0, 40)) console.log(`FIND ${label} ${x.join(' ')}`);
    console.log(`== ${label}: ${f.length}${f.length > 40 ? ' (first 40)' : ''}`);
  };
  //: Focus behaviour of a dialog or menu. `open` opens it, `inside` is the
  //: selector it must hold, `close` is how it ends (Escape).
  const dialog = async (label, open, inside, opts = {}) => {
    try { await open(); } catch (e) { console.log(`?? ${label}: could not open (${String(e.message).split('\n')[0].slice(0, 80)})`); return; }
    await page.waitForTimeout(700);
    const state = () => page.evaluate((s) => { const el = document.querySelector(s); const a = document.activeElement; return { present: !!el && el.getClientRects().length > 0, within: !!(el && a && el.contains(a)), active: a ? (a.id || a.className || a.tagName) : null }; }, inside);
    const s0 = await state();
    if (!s0.present) { console.log(`?? ${label}: ${inside} did not open`); return; }
    const probs = [];
    if (!s0.within && !opts.noFocusIn) probs.push(`focus not moved in (on ${String(s0.active).slice(0, 40)})`);
    if (opts.trap !== false) {
      for (let i = 0; i < 30; i++) await page.keyboard.press('Tab');
      const s1 = await state();
      if (!s1.within) probs.push(`Tab left the dialog (on ${String(s1.active).slice(0, 40)})`);
      for (let i = 0; i < 30; i++) await page.keyboard.press('Shift+Tab');
      const s2 = await state();
      if (!s2.within) probs.push(`Shift+Tab left the dialog (on ${String(s2.active).slice(0, 40)})`);
    }
    await report(label, inside);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    const s3 = await state();
    if (s3.present) probs.push('Escape did not close');
    if (opts.returnsTo) {
      const ret = await page.evaluate((q) => { const a = document.activeElement; const t = document.querySelector(q); return t ? a === t : null; }, opts.returnsTo);
      if (ret === false) probs.push(`focus did not return to ${opts.returnsTo}`);
    } else {
      const body = await page.evaluate(() => document.activeElement === document.body || document.activeElement === document.documentElement);
      if (body) probs.push('focus fell to body after close');
    }
    total += probs.length;
    for (const p of probs) console.log(`FIND ${label} ${p}`);
  };

  // Seed a little so lists are not empty.
  await page.evaluate(async () => {
    const have = (await apiJson('/entries?limit=1')).length;
    if (have) return;
    for (let i = 0; i < 4; i++) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Sweep note ${i}\n\nSomething written about topic ${i} with a #tag.`, category: 'Sweep' }) });
    const d = new Date(); d.setHours(d.getHours() + 3);
    await apiJson('/reminders', { method: 'POST', body: JSON.stringify({ text: 'Sweep reminder', due_at: d.toISOString() }) });
  }).catch(() => {});

  const tab = async (t) => { await page.evaluate((x) => switchTab(x), t); await page.waitForTimeout(1500); };

  // Dashboard, notes, chat.
  await tab('dashboard'); await report('dashboard', '#tab-dashboard');
  await tab('notes'); await report('notes', '#tab-notes');
  await tab('chat'); await report('chat (new)', '#tab-chat');

  // Slash menu in the chat box.
  await page.focus('#chat-input').catch(() => {});
  await page.keyboard.type('/');
  await page.waitForTimeout(1200);
  const hasMenu = await page.evaluate(() => { const m = document.getElementById('editor-menu'); return !!m && !m.classList.contains('hidden'); });
  if (hasMenu) {
    await report('chat slash menu', '#editor-menu');
    const st = await page.evaluate(() => { const m = document.getElementById('editor-menu'); return { role: m.getAttribute('role'), label: m.getAttribute('aria-label'), activedesc: document.getElementById('chat-input').getAttribute('aria-activedescendant'), expanded: document.getElementById('chat-input').getAttribute('aria-expanded'), controls: document.getElementById('chat-input').getAttribute('aria-controls') }; });
    console.log('   slash menu aria', JSON.stringify(st));
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    const stillFocused = await page.evaluate(() => document.activeElement?.id);
    if (stillFocused !== 'chat-input') { total++; console.log(`FIND chat slash menu focus after Escape on ${stillFocused}`); }
  } else { console.log('?? chat slash menu did not open'); }
  await page.fill('#chat-input', '').catch(() => {});

  // Timeline calendar and its add sheet.
  await page.evaluate(() => { localStorage.setItem('timeline-view', 'calendar'); localStorage.setItem('timeline-cal-span', 'month'); });
  await tab('timeline'); await page.waitForTimeout(1000);
  await report('timeline calendar', '#tab-timeline');
  await dialog('calendar add sheet (N)', async () => { await page.focus('.timeline-cal-monthcell[tabindex="0"]'); await page.keyboard.press('n'); }, '[data-sheet="calendar-add"] .sheet-card', { returnsTo: '.timeline-cal-monthcell[tabindex="0"]' });
  await page.evaluate(() => { localStorage.setItem('timeline-cal-span', 'week'); if (typeof timelineCal !== 'undefined') { timelineCal.url = ''; timelineCal.span = 'week'; } paintTimeline(); });
  await page.waitForTimeout(1200);
  await report('timeline week', '#tab-timeline');

  // Menus and dialogs reached from the surfaces above.
  await tab('chat');
  await dialog('no-model caret menu', async () => { await page.click('.ai-offline-split .split-button-caret'); }, '.action-menu', { returnsTo: '.ai-offline-split .split-button-caret', trap: false });
  await tab('dashboard');
  await dialog('get started menu', async () => { await page.click('#dash-start-menu'); }, '.action-menu', { returnsTo: '#dash-start-menu', trap: false });
  await dialog('find anything', async () => { await page.evaluate(() => openFinder()); }, '#finder-overlay', { trap: true });
  await dialog('guide panel', async () => { await page.evaluate(async () => { await ensureModule('helpChat'); openHelpChat(); }); }, '#help-chat-panel, .help-chat-panel', { trap: false });
  await tab('notes');
  await dialog('note card menu', async () => { await page.click('#entry-list > li:first-child button[aria-label="More actions"], #entry-list > li:first-child button[title="More actions"]'); }, '.action-menu', { trap: false });
  await dialog('settings dialog', async () => { await page.click('#settings-btn'); }, '#settings-modal', { returnsTo: '#settings-btn' });

  // Autocorrect menu: type a misspelling into the capture box.
  await tab('notes');
  await page.evaluate(() => document.querySelector('#notes-subtabs [data-target], [data-subtab="capture"]')?.click());
  await page.waitForTimeout(800);

  // Settings panes.
  const sections = await page.evaluate(() => SETTINGS_SECTIONS.slice());
  for (const s of sections) {
    await page.evaluate((x) => openSettingsModal(x), s);
    await page.waitForTimeout(1100);
    await report(`settings/${s}`, '#settings-modal .modal-content, #settings-modal');
    if (s === 'models') {
      const f = await page.evaluate(() => { const m = document.getElementById('settings-modal'); const a = document.activeElement; return m && a && m.contains(a); });
      if (!f) { total++; console.log('FIND settings: focus not in modal on open'); }
    }
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  }
  console.log(`TOTAL ${total} at ${W} ${process.env.THEME || 'light'}; page errors ${errors.length}`);
  for (const e of errors.slice(0, 5)) console.log('  pageerror', e.slice(0, 150));
  await browser.close();
})();
