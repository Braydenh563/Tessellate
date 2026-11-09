// INBOX 1717: browser zoom 125/150/175/200 % on a 1440x900 window, every surface.
// Zoom renders as a smaller CSS viewport at a higher deviceScaleFactor, so that is
// what this emulates. For each surface it records, as numbers:
//   wrap     a flex-wrap:wrap bar/head whose children sit on more than one line, or a
//            control/tab whose label wraps onto a second line
//   overflow scrollWidth > clientWidth + 1 on an element that does not scroll, or an
//            element past the viewport's right edge
//   clip     overflow hidden, no ellipsis, text wider than its box
// Run: THEME=dark ZOOMS=125,150 ONLY=settings BASE=http://127.0.0.1:8795 SCRATCH=<dir> node zoom1717.js
// Output: <SCRATCH>/zoom1717-<theme>.json (rows) and a count table on stdout.
const {boot} = require('./lib.js');
const fs = require('fs');
const THEME = process.env.THEME || 'light';
const SCRATCH = process.env.SCRATCH || '.';
const ZOOMS = (process.env.ZOOMS || '125,150,175,200').split(',').map(Number);
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const SKIP_ROWS = process.env.COUNTS_ONLY === '1';

// Runs in the page: returns findings for what is on screen now.
function detect() {
  const out = [];
  const vw = innerWidth;
  const sig = (el) => {
    const parts = [];
    for (let e = el, n = 0; e && e !== document.body && n < 4; e = e.parentElement, n++) {
      let s = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(s + '#' + e.id); break; }
      const c = [...e.classList].slice(0, 2).join('.');
      parts.unshift(s + (c ? '.' + c : ''));
    }
    return parts.join(' > ');
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
      if (e.hidden || e.getAttribute('aria-hidden') === 'true' && e.classList.contains('hidden')) return false;
      if (cs.overflow !== 'visible' && e !== el) {
        const p = e.getBoundingClientRect();
        if (r.right <= p.left || r.left >= p.right || r.bottom <= p.top || r.top >= p.bottom) return false;
      }
    }
    return r.right > 0 && r.left < vw && r.bottom > 0;
  };
  const add = (el, kind, nums) => out.push({sel: sig(el), kind, ...nums});
  const bar = /(bar|head|toolbar|dock|tabs|foot|actions|controls|seg|strip|chips|menu)/i;
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg') || ['SCRIPT', 'STYLE', 'OPTION'].includes(el.tagName)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none') continue;
    const cw = el.clientWidth, sw = el.scrollWidth;
    // overflow / clip
    if (cw > 2 && sw > cw + 1 && el.clientHeight > 0) {
      const ox = cs.overflowX;
      if (ox === 'visible' || ox === 'hidden' || ox === 'clip') {
        if (visible(el)) {
          const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
          if (ox !== 'visible' && hasText && cs.textOverflow !== 'ellipsis') add(el, 'clip', {client: cw, scroll: sw, text: el.textContent.trim().slice(0, 30)});
          else if (ox === 'visible' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) {
            // only what is in flow and visible counts: a hidden popup or a visually-hidden label inflates scrollWidth alone
            const er = el.getBoundingClientRect();
            const spill = [...el.children].some((k) => { const kc = getComputedStyle(k); if (kc.position === 'absolute' || kc.position === 'fixed' || kc.display === 'none' || kc.visibility === 'hidden') return false; const kr = k.getBoundingClientRect(); return kr.width > 1 && kr.right > er.right + 1; });
            if (spill || !el.children.length) add(el, 'overflow', {client: cw, scroll: sw});
          }
          else if (ox === 'hidden' && !hasText && cs.display.includes('flex')) add(el, 'overflow', {client: cw, scroll: sw});
        }
      }
    }
    // wrapping bars
    if ((cs.display === 'flex' || cs.display === 'inline-flex') && cs.flexWrap !== 'nowrap' && !cs.flexDirection.startsWith('column')) {
      const kids = [...el.children].filter((k) => { const r = k.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(k).position !== 'absolute' && getComputedStyle(k).position !== 'fixed'; });
      if (kids.length > 1 && !el.classList.contains('tabs-wrapped') && (bar.test(el.className) || bar.test(el.id)) && visible(el)) {
        const tops = kids.map((k) => k.getBoundingClientRect().top);
        const h = Math.max(...kids.map((k) => k.getBoundingClientRect().height));
        if (Math.max(...tops) - Math.min(...tops) > h / 2) add(el, 'wrap', {kids: kids.length, lines: new Set(tops.map((t) => Math.round(t / (h / 2)))).size, spread: Math.round(Math.max(...tops) - Math.min(...tops))});
      }
    }
    // labels that wrap inside a control: the text's own line boxes, not the control's height
    if (el.matches('button, [role=tab], [role=button], summary:not(:has(h3)), .chip, label.chip, .select-opener, .seg > *, .tab-badge, h1, h2, h3, .dock-word, .dock-identity *') && el.children.length < 6) {
      const txt = el.textContent.trim();
      if (txt && txt.length <= 40 && !cs.flexDirection.startsWith('column') && !el.matches('.quick-link') && !el.querySelector('.tab-badge') && !el.classList.contains('tab-badge') && visible(el)) {
        const range = document.createRange(); range.selectNodeContents(el);
        const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0 && r.height < 3 * parseFloat(cs.fontSize));
        if (rects.length > 1) {
          const tops = rects.map((r) => r.top); const fs = parseFloat(cs.fontSize);
          if (Math.max(...tops) - Math.min(...tops) > fs * 0.8) add(el, 'wrap', {lines: new Set(tops.map((t) => Math.round(t / (fs * 0.8)))).size, text: txt.slice(0, 30)});
        }
      }
    }
    // any short label that breaks onto a second line, whatever element carries it
    else if (!['INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'BR', 'I', 'SVG'].includes(el.tagName) && !cs.flexDirection.startsWith('column') && [...el.children].every((k) => ['I', 'SVG', 'IMG', 'KBD'].includes(k.tagName))) {
      const txt = el.textContent.trim();
      if (txt && txt.length <= 24 && cs.whiteSpace !== 'pre' && cs.display !== 'inline' && visible(el)) {
        const range = document.createRange(); range.selectNodeContents(el);
        const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0 && r.height < 3 * parseFloat(cs.fontSize));
        const fs = parseFloat(cs.fontSize); const tops = rects.map((r) => r.top);
        if (rects.length > 1 && Math.max(...tops) - Math.min(...tops) > fs * 0.8) add(el, 'wrap', {lines: new Set(tops.map((t) => Math.round(t / (fs * 0.8)))).size, text: txt});
      }
    }
  }
  if (document.documentElement.scrollWidth > vw + 1) out.push({sel: 'document', kind: 'overflow', client: vw, scroll: document.documentElement.scrollWidth});
  return out;
}

const tab = (t) => (p) => p.evaluate((t) => switchTab(t), t);
const click = (sel) => (p) => p.evaluate((s) => document.querySelector(s)?.click(), sel);
const settle = (ms = 700) => (p) => p.waitForTimeout(ms);
const seq = (...fns) => async (p) => { for (const f of fns) await f(p); };
const esc = async (p) => { await p.keyboard.press('Escape'); await p.keyboard.press('Escape'); await p.waitForTimeout(250); };

const SURFACES = [];
const S = (name, setup) => SURFACES.push({name, setup});
S('shell+dashboard', seq(tab('dashboard'), settle(1200)));
S('notes-list', seq(tab('notes'), settle(1000)));
S('note-editor', seq(tab('notes'), settle(600), (p) => p.evaluate(() => { const c = document.querySelector('.entry-card, .note-card, [data-entry-id]'); if (c) c.click(); }), settle(1200)));
S('note-composer', seq(tab('notes'), settle(600), (p) => p.evaluate(() => document.querySelector('#entry-content, #note-input, textarea')?.focus()), settle(600)));
for (const v of ['documents', 'docs', 'whiteboard', 'media-images', 'media-files', 'recordings', 'skills', 'links', 'contents']) {
  const sel = v.startsWith('media-') ? `[data-target="library-view-media"][data-media-kind="${v.slice(6)}"]` : `#tab-library [data-target="library-view-${v}"]`;
  S('library-' + v, seq(tab('library'), settle(500), click(sel), settle(900)));
}
S('docs-editor', async (p) => { await p.evaluate(() => switchTab('library')); await p.waitForTimeout(400); await p.evaluate(() => document.querySelector('#tab-library [data-target="library-view-docs"]')?.click()); await p.waitForTimeout(700); await p.evaluate(() => { const d = document.querySelector('.doc-list-item[data-title*="Zoom doc"], .doc-list-item'); d?.click(); }); await p.waitForTimeout(1500); });
S('docs-editor-code', async (p) => { await p.evaluate(() => switchTab('library')); await p.waitForTimeout(400); await p.evaluate(() => document.querySelector('#tab-library [data-target="library-view-docs"]')?.click()); await p.waitForTimeout(700); await p.evaluate(() => { const ds = [...document.querySelectorAll('.doc-list-item')]; (ds.find((d) => /Zoom code/.test(d.textContent)) || ds[0])?.click(); }); await p.waitForTimeout(1500); });
S('diagram-builder', async (p) => { await p.evaluate(async () => { const ds = await (await api('/documents')).json(); const d = (ds.documents || ds).find((x) => /Zoom diagram/.test(x.title)); switchTab('library'); document.querySelector('#tab-library [data-target="library-view-docs"]')?.click(); await new Promise((r) => setTimeout(r, 600)); await openDocument(d.id); }); await p.waitForTimeout(1500); await p.evaluate(() => { try { setDocView('canvas', {persist: false}); } catch (e) {} }); await p.waitForTimeout(2000); });
for (const [n, re] of [['whiteboard', /Zoom board/], ['mindmap', /Zoom map/]]) {
  S(n, async (p) => { await p.evaluate(() => switchTab('library')); await p.waitForTimeout(400); await p.evaluate(() => document.querySelector('#tab-library [data-target="library-view-whiteboard"]')?.click()); await p.waitForTimeout(1200); await p.evaluate((src) => { const c = [...document.querySelectorAll('#library-boards-grid .library-card')]; (c.find((x) => new RegExp(src).test(x.textContent)) || c[0])?.click(); }, re.source); await p.waitForTimeout(2500); });
}
S('graph', seq(tab('graph'), settle(2500)));
S('graph-popup', async (p) => { await p.evaluate(() => switchTab('graph')); await p.waitForTimeout(2500); await p.evaluate(() => { const nodes = window.graphNodes || window.graphState?.nodes; const n = nodes?.[0]; if (n && typeof openGraphPopup === 'function') openGraphPopup({clientX: innerWidth / 2, clientY: innerHeight / 2, preventDefault() {}, stopPropagation() {}}, n); }); await p.waitForTimeout(900); });
S('timeline-feed', seq(tab('timeline'), settle(900)));
S('timeline-table', seq(tab('timeline'), settle(500), click('#timeline-view-table'), settle(900)));
S('calendar', seq(tab('timeline'), settle(500), click('#timeline-view-calendar'), settle(1000)));
S('chat', seq(tab('chat'), settle(1200)));
S('ask', seq(tab('chat'), settle(500), click('[data-chat-mode="chat"]'), settle(800), (p) => p.evaluate(() => document.querySelector('#chat-input, #chat-message, textarea')?.focus())));
S('chat-agent', seq(tab('chat'), settle(500), click('[data-chat-mode="agent"]'), settle(900)));
S('reminders', seq(tab('reminders'), settle(1000)));
const SECTIONS = ['models', 'searchindex', 'personas', 'skills', 'tools', 'memory', 'learned', 'websearch', 'preferences', 'general', 'templates', 'data', 'appearance', 'shortcuts', 'account', 'privacy', 'extras', 'tasks'];
for (const s of SECTIONS) S('settings-' + s, async (p) => { await p.evaluate((s) => openSettingsModal(s), s); await p.waitForTimeout(1100); });
S('palette', async (p) => { await p.evaluate(() => openPalette()); await p.waitForTimeout(700); });
S('quick-add', async (p) => { await p.evaluate(() => openQuickNote()); await p.waitForTimeout(800); });
S('companion', async (p) => { await p.evaluate(() => { try { document.querySelector('#desk-companion, .desk-companion, [data-companion]')?.click(); } catch (e) {} }); await p.waitForTimeout(800); });

(async () => {
  const rows = [];
  let seeded = false;
  for (const zoom of ZOOMS) {
    const f = zoom / 100;
    const mk = async () => { for (let i = 0; ; i++) { try { return await boot({viewport: {width: Math.round(1440 / f), height: Math.round(900 / f)}, deviceScaleFactor: f}); } catch (e) { if (i > 3) throw e; await new Promise((r) => setTimeout(r, 4000)); } } };
    let {browser, page} = await mk();
    if (!seeded) {
      seeded = true;
      await page.evaluate(async () => {
        const have = await (await api('/documents')).json();
        if ((have.documents || have).some((d) => /Zoom doc/.test(d.title))) return;
        for (let i = 0; i < 6; i++) await api('/entries', {method: 'POST', body: JSON.stringify({content: `Zoom note ${i}: a reasonably long line of text so the card has body copy to wrap and truncate at narrow widths #zoom${i % 3}`})});
        await api('/documents', {method: 'POST', body: JSON.stringify({title: 'Zoom doc', content: '# Zoom doc\n\nSome text with **bold** and a list\n\n- one\n- two\n'})});
        await api('/documents', {method: 'POST', body: JSON.stringify({title: 'Zoom code', content: 'function a() { return 1; }\n', file_type: 'js'})});
        await api('/documents', {method: 'POST', body: JSON.stringify({title: 'Zoom diagram', content: 'flowchart TD\n  A-->B\n  B-->C\n', file_type: 'mmd'})});
        await api('/whiteboard/boards', {method: 'POST', body: JSON.stringify({name: 'Zoom board'})});
        await api('/whiteboard/boards', {method: 'POST', body: JSON.stringify({name: 'Zoom map', type: 'map'})});
      });
      await page.reload({waitUntil: 'domcontentloaded'}); await page.waitForTimeout(3000);
    }
    for (const s of SURFACES) {
      if (ONLY.length && !ONLY.some((o) => s.name.startsWith(o))) continue;
      try {
        await page.evaluate(() => { document.querySelectorAll('.modal-overlay:not(.hidden)').forEach((m) => m.querySelector('[data-close], .modal-close, button[aria-label*=lose]')?.click()); });
        await esc(page);
        await s.setup(page);
        const found = await page.evaluate(detect);
        const seen = new Set();
        for (const f of found) { const k = f.kind + f.sel; if (seen.has(k)) continue; seen.add(k); rows.push({surface: s.name, zoom, theme: THEME, ...f}); }
        if (!found.length) rows.push({surface: s.name, zoom, theme: THEME, kind: 'clean'});
      } catch (e) {
        rows.push({surface: s.name, zoom, theme: THEME, kind: 'error', sel: String(e.message).slice(0, 80)});
        if (/crash|closed/i.test(e.message)) { await browser.close().catch(() => {}); ({browser, page} = await mk()); }
      }
      await esc(page).catch(() => {});
    }
    await browser.close();
  }
  fs.writeFileSync(`${SCRATCH}/zoom1717-${THEME}${process.env.TAG ? '-' + process.env.TAG : ''}.json`, JSON.stringify(rows, null, 1));
  const tally = {};
  for (const r of rows) { const k = `${r.zoom}`; tally[k] = tally[k] || {wrap: 0, overflow: 0, clip: 0, error: 0}; if (tally[k][r.kind] !== undefined) tally[k][r.kind]++; }
  console.log(THEME, JSON.stringify(tally));
  if (!SKIP_ROWS) for (const r of rows.filter((r) => r.kind !== 'clean')) console.log([r.zoom, r.surface, r.kind, r.sel, r.client ?? r.kids ?? '', r.scroll ?? r.lines ?? '', r.text || ''].join(' | '));
})();
