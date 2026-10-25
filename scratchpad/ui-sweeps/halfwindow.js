// Half-window, part-window and phone pass (owner, 2026-10-25: "do all ui fit
// on a half screen window??"). Per surface and width it records:
//   hscroll  the page scrolls sideways (documentElement scrollWidth > clientWidth)
//   off      a visible control with a box outside the viewport, not inside a
//            scroller that is meant to scroll
//   overlap  two visible controls whose boxes cross by more than 4 px each way
//   clip     a leaf text element cut off (overflow hidden, no ellipsis, scrollWidth > clientWidth + 1)
//   blank    a vertical gap above the app (top bar not at y 0) or below it (status bar not at the viewport bottom)
//
//   BASE=http://127.0.0.1:8794 WIDTHS=960,700,420 THEME=light node halfwindow.js [surface-filter]
//   JSON=/path writes the findings; the last line is the count per width.
const { boot } = require('./lib.js');
const fs = require('fs');
const WIDTHS = (process.env.WIDTHS || '960,700,420').split(',').map(Number);
const FILTER = process.argv[2] || '';
const SETTINGS = ['models','searchindex','personas','skills','tools','memory','learned','websearch','preferences','general','templates','data','appearance','shortcuts','account','privacy','extras','tasks','logs','help','about'];
const NOTES = ['browse','capture','writing-room','ask','questions'];
const LIB = ['library-view-documents','library-view-docs','library-view-whiteboard','library-view-media','library-view-recordings','library-view-skills','library-view-links','library-view-contents'];

function surfaces() {
  const out = [];
  for (const t of ['dashboard','notes','chat','library','graph','timeline','reminders']) out.push({ name: 'tab:' + t, go: async (p) => { await closeAll(p); await tab(p, t); } });
  for (const s of NOTES) out.push({ name: 'notes:' + s, go: async (p) => { await closeAll(p); await tab(p, 'notes'); await p.evaluate((s) => document.querySelector(`#notes-subtabs [data-section="${s}"]`)?.click(), s); } });
  for (const s of LIB) out.push({ name: 'library:' + s.replace('library-view-', ''), go: async (p) => { await closeAll(p); await tab(p, 'library'); await p.evaluate((s) => { const b = [...document.querySelectorAll(`#library-subtabs [data-target="${s}"]`)][0]; b?.click(); }, s); } });
  for (const s of SETTINGS) out.push({ name: 'settings:' + s, go: async (p) => { await closeAll(p); await p.evaluate(() => document.getElementById('settings-btn')?.click()); await p.waitForTimeout(500); await p.evaluate((s) => document.querySelector(`#settings-nav [data-section="${s}"]`)?.click(), s); } });
  out.push({ name: 'guide', go: async (p) => { await closeAll(p); await p.evaluate(() => document.getElementById('show-guide-btn')?.click() || document.getElementById('status-guide-btn')?.click()); } });
  out.push({ name: 'notif', go: async (p) => { await closeAll(p); await p.evaluate(() => document.getElementById('notif-btn')?.click()); } });
  out.push({ name: 'space-switcher', go: async (p) => { await closeAll(p); await p.evaluate(() => document.getElementById('space-switcher-btn')?.click()); } });
  out.push({ name: 'note:open', go: async (p) => { await closeAll(p); await tab(p, 'notes'); await p.evaluate(() => document.querySelector('#notes-subtabs [data-section="browse"]')?.click()); await p.waitForTimeout(400); await p.click('#entry-list > li', { timeout: 3000 }).catch(() => {}); await p.waitForTimeout(500); } });
  out.push({ name: 'note:menu', go: async (p) => { await out.find((x) => x.name === 'note:open').go(p); await p.evaluate(() => { const b = document.querySelector('#entry-list > li [aria-label*="ore actions" i], #entry-list > li summary, #entry-list > li .kebab, #entry-list > li [data-menu]'); b?.click(); }); await p.waitForTimeout(300); } });
  out.push({ name: 'doc:open', go: async (p) => { await closeAll(p); await tab(p, 'library'); await p.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-docs"]')?.click()); await p.waitForTimeout(500); await p.evaluate(() => document.querySelector('#library-view-docs .library-card, #library-view-docs [data-doc-id], #library-docs-grid > *')?.click()); await p.waitForTimeout(1500); } });
  out.push({ name: 'ask:answer', go: async (p) => { await closeAll(p); await tab(p, 'notes'); await p.evaluate(() => document.querySelector('#notes-subtabs [data-section="ask"]')?.click()); await p.waitForTimeout(300); await p.fill('#question', 'what did I plan for the weekly review').catch(() => {}); await p.click('#ask-btn').catch(() => {}); await p.waitForTimeout(2500); } });
  out.push({ name: 'chat:suggest', go: async (p) => { await closeAll(p); await tab(p, 'chat'); await p.waitForTimeout(600); await p.evaluate(() => document.getElementById('chat-suggest')?.classList.remove('hidden')); } });
  out.push({ name: 'board:open', go: async (p) => { await closeAll(p); await tab(p, 'library'); await p.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click()); await p.waitForTimeout(600); await p.click('#library-boards-grid .library-card, #library-boards-grid > *', { timeout: 2500 }).catch(() => {}); await p.waitForTimeout(1500); } });
  return out.filter((s) => !FILTER || new RegExp(FILTER).test(s.name));
}
async function tab(p, t) { await p.evaluate((t) => (document.querySelector(`[data-tab="${t}"]`) || document.querySelector(`#phone-more-btn`))?.click(), t); }
async function closeAll(p) {
  await p.keyboard.press('Escape').catch(() => {});
  await p.evaluate(() => {
    document.getElementById('settings-close')?.click();
    document.querySelectorAll('.modal-overlay:not(.hidden) .dialog-head-btn[id$="close"]').forEach((b) => b.click());
  });
  await p.waitForTimeout(250);
}

const MEASURE = () => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const vis = (e) => { if (!e.checkVisibility || !e.checkVisibility({ checkOpacity: false, checkVisibilityCSS: true })) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  // On top: the topmost thing at a point inside the box is the element or part of it, so a control under an open dialog is not counted.
  const onTop = (e) => { const r = e.getBoundingClientRect(); const x = Math.min(Math.max(r.left + r.width / 2, 0), vw - 1), y = Math.min(Math.max(r.top + r.height / 2, 0), vh - 1); const t = document.elementFromPoint(x, y); return !!t && (e === t || e.contains(t) || t.contains(e)); };
  const name = (e) => (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : e.tagName.toLowerCase()) + ((e.title || e.textContent || '').trim().slice(0, 24) ? ` "${(e.getAttribute('aria-label') || e.title || e.textContent).trim().replace(/\s+/g, ' ').slice(0, 24)}"` : '');
  const scrollerX = (e) => { for (let a = e.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if ((o === 'auto' || o === 'scroll') && a.scrollWidth > a.clientWidth) return a; if (a === document.body) break; } return null; };
  const hidden = (e) => { for (let a = e; a; a = a.parentElement) if (a.classList && (a.classList.contains('hidden') || a.hasAttribute('hidden'))) return true; return false; };
  const f = [];
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) f.push({ k: 'hscroll', n: `scrollWidth ${de.scrollWidth} > ${de.clientWidth}` });
  const ctrls = [...document.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab]')].filter((e) => vis(e) && !hidden(e) && onTop(e));
  for (const e of ctrls) {
    const r = e.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1 || r.bottom < -1 || r.top > vh + 1 && !scrollerY(e)) {
      if (scrollerX(e) && r.top <= vh) continue;
      if (e.closest('[inert], [aria-hidden=true], .sr-only, .skip-link, .toast')) continue;
      if (r.top > vh + 1) continue;
      f.push({ k: 'off', n: name(e), v: `${Math.round(r.left)}..${Math.round(r.right)} of ${vw}` });
    }
  }
  function scrollerY(e) { for (let a = e.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowY; if (o === 'auto' || o === 'scroll') return true; } return false; }
  const inside = ctrls.filter((e) => { const r = e.getBoundingClientRect(); return r.right <= vw + 1 && r.left >= -1 && r.top < vh; });
  for (let i = 0; i < inside.length; i++) {
    const a = inside[i], ra = a.getBoundingClientRect();
    for (let j = i + 1; j < inside.length; j++) {
      const b = inside[j];
      if (a.contains(b) || b.contains(a) || (a.closest('#status-bar, #tab-bar') ? !b.closest('#status-bar, #tab-bar') : !!b.closest('#status-bar, #tab-bar')) || /theme-eye|space-option|space-menu/.test(a.className + ' ' + b.className) || (a.closest('.space-menu,.space-pop,[popover]') !== b.closest('.space-menu,.space-pop,[popover]') && document.getElementById('space-switcher-btn')?.getAttribute('aria-expanded') === 'true') || (a.matches('summary') && b.closest('summary') === a) || (b.matches('summary') && a.closest('summary') === b) || a.closest('.toast') || b.closest('.toast')) continue;
      const rb = b.getBoundingClientRect();
      const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (ox > 4 && oy > 4) {
        const za = getComputedStyle(a).position, zb = getComputedStyle(b).position;
        f.push({ k: 'overlap', n: name(a) + '  X  ' + name(b), v: `${Math.round(ox)}x${Math.round(oy)}` });
      }
    }
  }
  for (const e of document.querySelectorAll('button, a, label, span, p, h1, h2, h3, h4, h5, summary, li, td, th, div')) {
    if (!vis(e) || hidden(e)) continue;
    if (e.children.length && ![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const cs = getComputedStyle(e);
    if ((cs.overflowX === 'hidden' || cs.overflowX === 'clip') && e.clientWidth > 2 && e.scrollWidth > e.clientWidth + 1 && cs.textOverflow !== 'ellipsis' && e.textContent.trim()) {
      if (e.closest('.sr-only, .visually-hidden, .toast')) continue;
      f.push({ k: 'clip', n: name(e), v: `${e.scrollWidth} > ${e.clientWidth}` });
    }
  }
  // A dock (or bar) with height and nothing visible in it: the blank bar.
  for (const d of document.querySelectorAll('.dock, .selectbar, .modal-nav')) {
    if (!vis(d) || hidden(d)) continue;
    const kids = [...d.querySelectorAll('*')].filter((k) => vis(k) && (k.children.length === 0) && (k.textContent.trim() || /^(INPUT|SELECT|BUTTON|SVG|IMG|I|TEXTAREA)$/i.test(k.tagName)));
    if (!kids.length && d.getBoundingClientRect().height > 8) f.push({ k: 'blank', n: name(d), v: `empty ${Math.round(d.getBoundingClientRect().height)}px tall` });
  }
  const top = document.getElementById('top-bar'), sb = document.getElementById('status-bar');
  if (top && vis(top) && Math.abs(top.getBoundingClientRect().top) > 1) f.push({ k: 'blank', n: 'top-bar', v: `top ${Math.round(top.getBoundingClientRect().top)}` });
  if (sb && vis(sb)) { const g = vh - sb.getBoundingClientRect().bottom; if (Math.abs(g) > 1) f.push({ k: 'blank', n: 'status-bar', v: `gap below ${Math.round(g)}` }); }
  return f;
};

(async () => {
  const all = {};
  for (const width of WIDTHS) {
    const { browser, page } = await boot({ viewport: { width, height: 800 }, hasTouch: width < 600, isMobile: width < 600 });
    let total = 0;
    for (const s of surfaces()) {
      await s.go(page).catch((e) => console.log('GO-FAIL', s.name, e.message.slice(0, 80)));
      await page.waitForTimeout(500);
      const f = await page.evaluate(MEASURE).catch((e) => [{ k: 'err', n: e.message.slice(0, 80) }]);
      const seen = new Set(); const u = f.filter((x) => { const key = x.k + x.n; if (seen.has(key)) return false; seen.add(key); return true; });
      all[`${width}|${s.name}`] = u; total += u.length;
      for (const x of u) console.log(`${width} ${s.name} ${x.k} ${x.n} ${x.v || ''}`);
    }
    console.log(`TOTAL ${width} ${process.env.THEME || 'light'}: ${total}`);
    await browser.close();
  }
  if (process.env.JSON) fs.writeFileSync(process.env.JSON, JSON.stringify(all, null, 1));
})();
