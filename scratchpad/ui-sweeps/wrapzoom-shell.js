// Wrap/zoom sweep of the app shell (owner, 2026-11-11: "make sure the wrapping
// and ui issues arent an issue anywhere else from zoom or resolution").
// Surface: the top bar (spaces menu, tabs, right-hand icons), the status bar,
// the Dashboard and every widget on it, the command palette, notifications,
// the lock screen. Read-only: measures, never edits.
//
// Zoom is the CSS viewport the OS zoom yields, at deviceScaleFactor = zoom.
// Each state is measured, in the page, for five defect classes:
//   wrap      a one-line flex row whose visible items fall onto two lines, or a
//             short control label that breaks onto a second line
//   clip      a control (or its 4px focus face) cut by an ancestor whose
//             overflow is not visible; a scroller only counts when it is at
//             its limit in that direction (the control cannot be scrolled to)
//   overlap   an interactive element over a text node that is not its own
//             (Range rects, same layer, and on top at the meeting point), and
//             text under a fixed or sticky bar at a scroller's either end
//   overflow  scrollWidth > clientWidth + 1 on a non-scrolling element, or a
//             horizontal scrollbar on the page
//   misalign  a help ? neither beside its label (<= 16px) nor at the row end
//             (<= 6px), or off its label's centre line by more than 6px
//
// Run (dark matrix, then light at 1440):
//   BASE=http://127.0.0.1:8823 THEME=dark SCRATCH=<dir> node wrapzoom-shell.js
//   BASE=... THEME=light VPS=1440x900@1 SCRATCH=<dir> node wrapzoom-shell.js
//   SUMMARY=1 SCRATCH=<dir> node wrapzoom-shell.js     (de-duplicated table)
// VPS picks viewports (WxH@scale, comma separated); ONLY=<prefix> picks states.
const fs = require('fs');
const SCRATCH = process.env.SCRATCH || '.';
const THEME = process.env.THEME || 'dark';

const MATRIX = ['1280x720@1', '1366x768@1', '1440x900@1', '1920x1080@1', '2560x1440@1',
  '1536x864@1.25', '1280x720@1.5', '960x540@2', '1280x720@2', '768x1024@1'];

// ---------------------------------------------------------------- in the page
function detect() {
  const out = [];
  const csMap = new Map();
  const cs = (e) => { let s = csMap.get(e); if (!s) { s = getComputedStyle(e); csMap.set(e, s); } return s; };
  const VW = document.documentElement.clientWidth, VH = document.documentElement.clientHeight;
  const R = (n) => Math.round(n * 10) / 10;
  const sig = (el) => {
    const parts = [];
    for (let e = el, n = 0; e && e !== document.body && n < 4; e = e.parentElement, n++) {
      let s = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(s + '#' + e.id); break; }
      const c = typeof e.className === 'string' ? e.className.trim().split(/\s+/).filter((x) => x && !/^(active|open|hidden|ph|ph-.*)$/.test(x)).slice(0, 2).join('.') : '';
      parts.unshift(s + (c ? '.' + c : ''));
    }
    return parts.join(' > ');
  };
  const label = (el) => (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('title')) || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const goneMemo = new Map();
  const gone = (e) => { // display none or near-zero opacity on it or any ancestor
    if (!e || e === document.documentElement) return false;
    if (goneMemo.has(e)) return goneMemo.get(e);
    const s = cs(e);
    const g = s.display === 'none' || +s.opacity < 0.05 || (e.tagName === 'DIALOG' && !e.open) || gone(e.parentElement);
    goneMemo.set(e, g); return g;
  };
  // The ancestors that can clip `el`, honouring absolute/fixed escape.
  const clipMemo = new Map();
  function clips(el) {
    if (clipMemo.has(el)) return clipMemo.get(el);
    const boxes = [];
    let pos = cs(el).position;
    for (let a = el.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
      const s = cs(a);
      const contains = pos === 'absolute' ? (s.position !== 'static' || s.transform !== 'none')
        : pos === 'fixed' ? (s.transform !== 'none' || s.filter !== 'none' || /paint|strict|content/.test(s.contain)) : true;
      if (!contains) continue;
      const cx = s.overflowX !== 'visible', cy = s.overflowY !== 'visible';
      if (cx || cy) boxes.push({ a, s, cx, cy });
      pos = s.position;
      if (pos === 'fixed' && s.transform === 'none') break;
    }
    clipMemo.set(el, boxes); return boxes;
  }
  const box = (a) => { const r = a.getBoundingClientRect(); const l = r.left + a.clientLeft, t = r.top + a.clientTop; return { left: l, top: t, right: l + a.clientWidth, bottom: t + a.clientHeight }; };
  const inter = (a, b) => ({ left: Math.max(a.left, b.left), top: Math.max(a.top, b.top), right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) });
  const empty = (r) => r.right - r.left < 0.5 || r.bottom - r.top < 0.5;
  // The part of rect `r` (of element `el`) that is actually painted on screen.
  function visPart(el, r) {
    let v = inter(r, { left: 0, top: 0, right: VW, bottom: VH });
    for (const { a, cx, cy } of clips(el)) {
      const b = box(a);
      v = inter(v, { left: cx ? b.left : -1e9, right: cx ? b.right : 1e9, top: cy ? b.top : -1e9, bottom: cy ? b.bottom : 1e9 });
      if (empty(v)) return null;
    }
    return empty(v) ? null : v;
  }
  const shown = (el) => { if (gone(el) || cs(el).visibility === 'hidden') return null; const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null; return visPart(el, r); };

  const all = [...document.body.querySelectorAll('*')].filter((e) => !(e instanceof SVGElement) && !['SCRIPT', 'STYLE', 'TEMPLATE', 'OPTION', 'BR', 'LINK', 'META', 'NOSCRIPT'].includes(e.tagName));
  const vis = new Map();
  for (const e of all) { const v = shown(e); if (v) vis.set(e, v); }
  // Visually-hidden boxes (the 1px clip pattern) are not on screen.
  for (const e of [...vis.keys()]) { const r = e.getBoundingClientRect(); if (r.width <= 2 && r.height <= 2) vis.delete(e); }
  const INTERACTIVE = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=menuitem], [role=option], [role=switch], [role=checkbox], [contenteditable=true]';
  const isInteractive = (e) => e.matches(INTERACTIVE);

  // ---- wrap: one-line rows
  const ROWISH = /(^|[\s_-])(row|head|header|bar|toolbar|topbar|dock|tabs|tablist|subtabs|seg|segmented|split|cluster|actions|controls|strip|foot|footer|btn-group|button-group|tools|chips|editbar|switcher|identity)($|[\s_-])/i;
  const flatKids = (el) => { const ks = []; for (const k of el.children) { if (cs(k).display === 'contents') ks.push(...flatKids(k)); else ks.push(k); } return ks; };
  for (const [el] of vis) {
    const s = cs(el);
    if (!/flex/.test(s.display) || s.flexDirection.startsWith('column')) continue;
    const name = (typeof el.className === 'string' ? el.className : '') + ' ' + el.id;
    const role = el.getAttribute('role') || '';
    if (!(ROWISH.test(name) || /toolbar|tablist|menubar/.test(role) || ['HEADER', 'NAV', 'FOOTER'].includes(el.tagName))) continue;
    const kids = flatKids(el).filter((k) => vis.has(k) && !['absolute', 'fixed'].includes(cs(k).position));
    if (kids.length < 2) continue;
    const rs = kids.map((k) => k.getBoundingClientRect()).sort((a, b) => a.top - b.top);
    const lines = [];
    for (const r of rs) { const L = lines[lines.length - 1]; if (L && r.top < L.bottom - 1) { L.bottom = Math.max(L.bottom, r.bottom); L.n++; } else lines.push({ top: r.top, bottom: r.bottom, n: 1 }); }
    if (lines.length > 1) {
      const tops = rs.map((r) => r.top);
      out.push({ kind: 'wrap', sel: sig(el), what: 'row', flexWrap: s.flexWrap, items: kids.length, lines: lines.length, spread: R(Math.max(...tops) - Math.min(...tops)), height: R(el.getBoundingClientRect().height), text: label(el).slice(0, 30) });
    }
  }
  // ---- wrap: a short control label on two lines. Only text that flows
  // inline counts: a title and a hint stacked as blocks are two lines by design.
  for (const [el] of vis) {
    if (!el.matches('button, [role=tab], [role=button], [role=menuitem], .chip, .tab-label, .status-item, .dialog-head-title, label, h1, h2, h3, .space-switcher-name, .privacy-chip-word, .menu-item, .dash-widget-title')) continue;
    const txt = (el.textContent || '').trim().replace(/\s+/g, ' ');
    if (!txt || txt.length > 40) continue;
    const fsz = parseFloat(cs(el).fontSize);
    const rects = []; let selfWrap = 0;
    const tw2 = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = tw2.nextNode(); n; n = tw2.nextNode()) {
      if (!n.textContent.trim()) continue;
      // A line-clamped hint is allowed its lines (quick-link-hint clamps at 2).
      let clamped = false;
      for (let a = n.parentElement; a && a !== el.parentElement; a = a.parentElement) if (cs(a).webkitLineClamp && cs(a).webkitLineClamp !== 'none') { clamped = true; break; }
      if (clamped) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      const rs = [...range.getClientRects()].filter((r) => r.width > 0.5 && r.height > 0.5 && r.height < 3 * fsz);
      if (rs.length > 1) { const t = rs.map((r) => r.top); selfWrap = Math.max(selfWrap, Math.max(...t) - Math.min(...t)); }
      let inline = true;
      for (let a = n.parentElement; a && a !== el; a = a.parentElement) if (cs(a).display !== 'inline') { inline = false; break; }
      if (inline) rects.push(...rs);
    }
    const tops = rects.map((r) => r.top);
    const spread = Math.max(selfWrap, tops.length > 1 ? Math.max(...tops) - Math.min(...tops) : 0);
    if (spread > fsz * 0.8) out.push({ kind: 'wrap', sel: sig(el), what: 'label', lines: Math.round(spread / (fsz * 1.1)) + 1, spread: R(spread), width: R(el.getBoundingClientRect().width), text: txt.slice(0, 30) });
  }

  // ---- clip: controls cut by an overflow ancestor. A nearer scroller that
  // can still scroll that way excuses the cut (scroll to it); the face pass
  // uses the control's own :focus-visible ring, measured by focusing it.
  const cutOf = (el, rr) => {
    const excused = {};
    for (const { a, s, cx, cy } of clips(el)) {
      const b = box(a);
      const maxL = a.scrollWidth - a.clientWidth, maxT = a.scrollHeight - a.clientHeight;
      const scrollX = /auto|scroll/.test(s.overflowX) && maxL > 1, scrollY = /auto|scroll/.test(s.overflowY) && maxT > 1;
      const cut = {};
      const dirs = [];
      if (cx) dirs.push(['left', b.left - rr.left, scrollX && a.scrollLeft > 0], ['right', rr.right - b.right, scrollX && a.scrollLeft < maxL - 1]);
      if (cy) dirs.push(['top', b.top - rr.top, scrollY && a.scrollTop > 0], ['bottom', rr.bottom - b.bottom, scrollY && a.scrollTop < maxT - 1]);
      for (const [d, by, canScroll] of dirs) {
        if (by <= 1) continue;
        if (canScroll) { excused[d] = true; continue; }
        if (excused[d]) continue;
        cut[d] = R(by);
      }
      if (Object.keys(cut).length && !empty(inter(el.getBoundingClientRect(), b))) return { by: sig(a), overflow: s.overflowX + '/' + s.overflowY, cut };
    }
    return null;
  };
  const faceCands = [];
  for (const [el] of vis) {
    if (!isInteractive(el) || el.closest('.visually-hidden, .sr-only')) continue;
    const r = el.getBoundingClientRect();
    const hit = cutOf(el, r);
    if (hit) { out.push({ kind: 'clip', sel: sig(el), what: 'control', ...hit, rect: [R(r.left), R(r.top), R(r.width), R(r.height)], text: label(el) }); continue; }
    if (cutOf(el, { left: r.left - 6, top: r.top - 6, right: r.right + 6, bottom: r.bottom + 6 })) faceCands.push(el);
  }
  {
    const prev = document.activeElement;
    for (const el of faceCands.slice(0, 120)) {
      try { el.focus({ preventScroll: true, focusVisible: true }); } catch (e) { continue; }
      if (document.activeElement !== el) continue;
      const s = getComputedStyle(el);
      let ext = s.outlineStyle !== 'none' ? parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset) : 0;
      for (const sh of (s.boxShadow === 'none' ? [] : s.boxShadow.split(/,(?![^(]*\))/))) {
        if (/inset/.test(sh)) continue;
        const n = (sh.replace(/rgba?\([^)]*\)/, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
        if (n.length >= 4) ext = Math.max(ext, n[3] + Math.max(Math.abs(n[0]), Math.abs(n[1])));
        else if (n.length === 3) ext = Math.max(ext, n[2] / 2);
      }
      if (ext <= 0.5) continue;
      const r = el.getBoundingClientRect();
      const hit = cutOf(el, { left: r.left - ext, top: r.top - ext, right: r.right + ext, bottom: r.bottom + ext });
      if (hit) out.push({ kind: 'clip', sel: sig(el), what: 'focus-ring', ring: R(ext), ...hit, rect: [R(r.left), R(r.top), R(r.width), R(r.height)], text: label(el) });
    }
    try { prev?.focus?.({ preventScroll: true }); } catch (e) {}
  }
  // ---- clip: a scroller whose own box is cut by a non-scrolling ancestor
  // (its last rows can never be scrolled into sight)
  for (const [el] of vis) {
    const s = cs(el);
    const sx = /auto|scroll/.test(s.overflowX) && el.scrollWidth > el.clientWidth + 1, sy = /auto|scroll/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 1;
    if (!sx && !sy) continue;
    const r = el.getBoundingClientRect();
    const hit = cutOf(el, r);
    if (hit) out.push({ kind: 'clip', sel: sig(el), what: 'scroller', ...hit, rect: [R(r.left), R(r.top), R(r.width), R(r.height)] });
  }
  // ---- clip: a text label cut without an ellipsis
  for (const [el] of vis) {
    const s = cs(el);
    if (s.overflowX === 'visible' || s.textOverflow === 'ellipsis' || el.clientWidth < 3) continue;
    if (!(el.scrollWidth > el.clientWidth + 1)) continue;
    if (/auto|scroll/.test(s.overflowX)) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) continue;
    out.push({ kind: 'clip', sel: sig(el), what: 'text', client: el.clientWidth, scroll: el.scrollWidth, text: label(el) });
  }

  // ---- overflow: content wider than a box that does not scroll
  for (const [el] of vis) {
    const s = cs(el);
    if (el.clientWidth < 3 || !(el.scrollWidth > el.clientWidth + 1)) continue;
    if (/auto|scroll/.test(s.overflowX) || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) continue;
    if (s.overflowX !== 'visible' && s.textOverflow === 'ellipsis') continue;
    const er = el.getBoundingClientRect();
    const edge = er.left + el.clientLeft + el.clientWidth;
    const spill = [...el.children].filter((k) => vis.has(k) && !['absolute', 'fixed'].includes(cs(k).position) && k.getBoundingClientRect().right > edge + 1);
    if (!spill.length) continue;
    out.push({ kind: 'overflow', sel: sig(el), client: el.clientWidth, scroll: el.scrollWidth, overflowX: s.overflowX, worst: sig(spill.sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)[0]), by: R(Math.max(...spill.map((k) => k.getBoundingClientRect().right)) - edge) });
  }
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1 || document.body.scrollWidth > de.clientWidth + 1) out.push({ kind: 'overflow', sel: 'page', client: de.clientWidth, scroll: Math.max(de.scrollWidth, document.body.scrollWidth) });

  // ---- overlap: interactive over another element's text
  const layerOf = (e) => {
    for (let a = e; a && a !== document.body; a = a.parentElement) {
      const s = cs(a); const role = a.getAttribute('role') || '';
      if (a.tagName === 'DIALOG' || s.position === 'fixed' || (s.position === 'absolute' && s.zIndex !== 'auto' && +s.zIndex > 0) || (s.position === 'sticky' && s.zIndex !== 'auto') || /^(dialog|menu|listbox|tooltip|alertdialog)$/.test(role)) return a;
    }
    return document.body;
  };
  const texts = [];
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (!n.textContent.trim()) continue;
    const p = n.parentElement;
    if (!p || !vis.has(p) || p.closest('svg, select, option, .visually-hidden, .sr-only')) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    for (const r of range.getClientRects()) {
      if (r.width < 1 || r.height < 1) continue;
      let v = visPart(p, { left: r.left + 1, top: r.top + 1, right: r.right - 1, bottom: r.bottom - 1 });
      // An ellipsised label's range runs past its own box: its own overflow clips it too.
      const ps = cs(p);
      if (v && (ps.overflowX !== 'visible' || ps.overflowY !== 'visible')) { const b = box(p); v = inter(v, { left: ps.overflowX !== 'visible' ? b.left : -1e9, right: ps.overflowX !== 'visible' ? b.right : 1e9, top: ps.overflowY !== 'visible' ? b.top : -1e9, bottom: ps.overflowY !== 'visible' ? b.bottom : 1e9 }); if (empty(v)) v = null; }
      if (v) texts.push({ n, p, v });
    }
  }
  // A scroll row's edge arrows sit over the row's chips by design (scroll-row-host).
  const inters = [...vis.keys()].filter((e) => isInteractive(e) && !e.closest('.visually-hidden, .sr-only') && !e.matches('.scroll-row-arrow'));
  const layerMemo = new Map(); const layer = (e) => { if (!layerMemo.has(e)) layerMemo.set(e, layerOf(e)); return layerMemo.get(e); };
  const seenPair = new Set();
  for (const I of inters) {
    const ir = vis.get(I);
    for (const t of texts) {
      if (I.contains(t.p)) continue;
      const x = inter(ir, t.v);
      if (x.right - x.left < 3 || x.bottom - x.top < 3) continue;
      // Inside a control that wraps both (a card button holding the label
      // and the help ?): the text is the outer control's own.
      if (layer(I.parentElement || I) !== layer(t.p)) continue;
      const cx = (x.left + x.right) / 2, cy = (x.top + x.bottom) / 2;
      const top = document.elementFromPoint(cx, cy);
      if (!top) continue;
      const real = I.contains(top) || top === t.p || (t.p.contains(top) && !top.contains(I));
      if (!real) continue;
      const key = sig(I) + '|' + sig(t.p);
      if (seenPair.has(key)) continue; seenPair.add(key);
      out.push({ kind: 'overlap', sel: sig(I), over: sig(t.p), text: t.n.textContent.trim().slice(0, 30), ctl: label(I), w: R(x.right - x.left), h: R(x.bottom - x.top), onTop: I.contains(top) ? 'control' : 'text' });
    }
  }

  // ---- misalign: help ? not beside its label nor at the row end
  for (const [el] of vis) {
    if (!el.matches('[data-help-for], .graph-help-toggle, .help-toggle')) continue;
    const r = el.getBoundingClientRect();
    const p = el.parentElement; if (!p) continue;
    const ps = cs(p);
    const pr = p.getBoundingClientRect();
    const contentRight = pr.right - parseFloat(ps.paddingRight) - parseFloat(ps.borderRightWidth);
    // The label: the nearest visible sibling before it with text, else the
    // parent's own text before it.
    let lab = null;
    for (let s = el.previousElementSibling; s; s = s.previousElementSibling) { if (vis.has(s) && s.textContent.trim()) { lab = s; break; } }
    let lr = null;
    if (lab) {
      const range = document.createRange(); range.selectNodeContents(lab);
      const rs = [...range.getClientRects()].filter((x) => x.width > 0.5);
      lr = rs.length ? rs.reduce((m, x) => (x.bottom > m.bottom - 1 && x.right > m.right ? x : m), rs[0]) : lab.getBoundingClientRect();
    } else {
      for (let n = el.previousSibling; n; n = n.previousSibling) if (n.nodeType === 3 && n.textContent.trim()) { const range = document.createRange(); range.selectNodeContents(n); const rs = [...range.getClientRects()]; if (rs.length) lr = rs[rs.length - 1]; break; }
    }
    const after = [...p.children].filter((k) => k !== el && vis.has(k) && !['absolute', 'fixed'].includes(cs(k).position) && k.getBoundingClientRect().left >= r.right - 1 && Math.abs(k.getBoundingClientRect().top - r.top) < r.height);
    const toEnd = R(contentRight - r.right);
    const atEnd = toEnd <= 6 || (after.length && after.every((k) => isInteractive(k) || k.querySelector('button')) && contentRight - Math.max(...after.map((k) => k.getBoundingClientRect().right)) <= 6);
    if (!lr) { if (!atEnd) out.push({ kind: 'misalign', sel: sig(el), why: 'no label, not at row end', toEnd, text: label(el) }); continue; }
    const gap = R(r.left - lr.right);
    const dy = R(Math.abs((r.top + r.bottom) / 2 - (lr.top + lr.bottom) / 2));
    const beside = gap >= -1 && gap <= 16;
    if (!beside && !atEnd) out.push({ kind: 'misalign', sel: sig(el), why: 'floats mid-row', gap, toEnd, dy, label: lab ? label(lab).slice(0, 30) : '', text: label(el) });
    else if (beside && dy > 6 && r.top >= lr.top - 2) out.push({ kind: 'misalign', sel: sig(el), why: 'off the label line', gap, dy, label: lab ? label(lab).slice(0, 30) : '', text: label(el) });
  }
  // ---- misalign: a dialog head's trailing actions not at the row end
  for (const [el] of vis) {
    if (!el.matches('.dialog-head-actions')) continue;
    const p = el.parentElement; if (!p || !vis.has(p)) continue;
    const ps = cs(p); const pr = p.getBoundingClientRect(); const r = el.getBoundingClientRect();
    const toEnd = R(pr.right - parseFloat(ps.paddingRight) - parseFloat(ps.borderRightWidth) - r.right);
    if (toEnd > 6) out.push({ kind: 'misalign', sel: sig(el), why: 'trailing actions short of the row end', toEnd });
  }
  return out;
}

// Text left under a fixed or sticky bar with its scroller at either end.
// Mutates scroll positions, so it runs after detect() and puts them back.
function underBars() {
  const out = [];
  const cs = (e) => getComputedStyle(e);
  const sig = (el) => { const parts = []; for (let e = el, n = 0; e && e !== document.body && n < 4; e = e.parentElement, n++) { let s = e.tagName.toLowerCase(); if (e.id) { parts.unshift(s + '#' + e.id); break; } const c = typeof e.className === 'string' ? e.className.trim().split(/\s+/).slice(0, 2).join('.') : ''; parts.unshift(s + (c ? '.' + c : '')); } return parts.join(' > '); };
  const visible = (e) => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false; for (let a = e; a && a !== document.documentElement; a = a.parentElement) { const s = cs(a); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) return false; } return true; };
  const BAR = /(^|[\s_-])(bar|foot|footer|head|header|dock|toolbar|editbar|actions)($|[\s_-])/i;
  const NOT = /(overlay|dialog|menu|toast|help|popup|popover|tooltip|suggest|tray|panel|modal|splash)/i;
  const bars = [...document.querySelectorAll('body *')].filter((e) => {
    const p = cs(e).position; if (p !== 'fixed' && p !== 'sticky') return false;
    const name = (typeof e.className === 'string' ? e.className : '') + ' ' + e.id + ' ' + e.tagName;
    if (p === 'fixed' && (!BAR.test(name) || NOT.test(name))) return false;
    const r = e.getBoundingClientRect();
    return visible(e) && r.width > 120 && r.height < innerHeight * 0.3;
  });
  const nearScroller = (e) => { for (let a = e; a && a !== document.body; a = a.parentElement) { const s = cs(a); if (/auto|scroll/.test(s.overflowY) && a.scrollHeight > a.clientHeight + 2) return a; } return document.scrollingElement; };
  const scrollers = [document.scrollingElement, ...[...document.querySelectorAll('body *')].filter((e) => { const s = cs(e); return /auto|scroll/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 2 && visible(e); })];
  for (const S of scrollers) {
    const keep = S.scrollTop;
    const max = S.scrollHeight - S.clientHeight;
    for (const [end, to] of [['top', 0], ['bottom', max]]) {
      S.scrollTop = to;
      const sb = S === document.scrollingElement ? { top: 0, bottom: innerHeight, left: 0, right: innerWidth } : S.getBoundingClientRect();
      for (const B of bars) {
        if (B.contains(S)) continue;
        // A sticky bar belongs to its own scroller.
        if (cs(B).position === 'sticky' && nearScroller(B.parentElement) !== S) continue;
        const br = B.getBoundingClientRect();
        // Only a bar that sits over this scroller's own area.
        if (br.bottom <= sb.top || br.top >= sb.bottom || br.right <= sb.left || br.left >= sb.right) continue;
        const tw = document.createTreeWalker(S === document.scrollingElement ? document.body : S, NodeFilter.SHOW_TEXT);
        for (let n = tw.nextNode(); n; n = tw.nextNode()) {
          const p = n.parentElement;
          if (!n.textContent.trim() || !p || B.contains(p) || p.contains(B) || !visible(p)) continue;
          // Only text this scroller moves: a nested scroller's text is that scroller's.
          if (nearScroller(p) !== S) continue;
          if (p.closest('[role=dialog], dialog, .visually-hidden, .sr-only')) continue;
          const range = document.createRange(); range.selectNodeContents(n);
          for (const r of range.getClientRects()) {
            const l = Math.max(r.left, br.left), t = Math.max(r.top, br.top), rr = Math.min(r.right, br.right), bb = Math.min(r.bottom, br.bottom);
            if (rr - l < 3 || bb - t < 3) continue;
            // Within the scroller's own box (text clipped away is not under the bar).
            if (r.bottom <= sb.top + 1 || r.top >= sb.bottom - 1) continue;
            const top = document.elementFromPoint((l + rr) / 2, (t + bb) / 2);
            if (!top || !B.contains(top)) continue;
            out.push({ kind: 'overlap', what: 'under-bar', sel: sig(B), scroller: sig(S), end, text: n.textContent.trim().slice(0, 30), h: Math.round(bb - t), over: sig(p) });
            break;
          }
          if (out.length > 200) break;
        }
      }
    }
    S.scrollTop = keep;
  }
  // one row per bar+scroller+end
  const seen = new Set();
  return out.filter((o) => { const k = o.sel + o.scroller + o.end; if (seen.has(k)) return false; seen.add(k); return true; });
}

// ---------------------------------------------------------------- the states
const wait = (p, ms) => p.waitForTimeout(ms);
const ev = (fn, arg) => (p) => p.evaluate(fn, arg);
const tab = (t) => async (p) => { await p.evaluate((t) => switchTab(t), t); await wait(p, 900); };
const esc = async (p) => { for (let i = 0; i < 3; i++) await p.keyboard.press('Escape'); await wait(p, 250); };
const closeAll = async (p) => {
  await esc(p);
  await p.evaluate(() => {
    document.querySelectorAll('dialog[open]').forEach((d) => d.close());
    for (const id of ['notif-panel', 'space-menu']) document.getElementById(id)?.classList.add('hidden');
    document.querySelectorAll('.help-body:not(.hidden)').forEach((h) => h.classList.add('hidden'));
    document.querySelectorAll('.action-menu:not(.hidden)').forEach((m) => m.classList.add('hidden'));
    document.getElementById('palette-overlay')?.classList.add('hidden');
  }).catch(() => {});
};
const density = (d) => async (p) => {
  await p.evaluate(async (d) => { switchTab('dashboard'); await new Promise((r) => setTimeout(r, 300)); applyDashDensity(d); await renderDashboard(); }, d);
  await wait(p, 1500);
};
const STATES = [];
const S = (name, setup, opts = {}) => STATES.push({ name, setup, ...opts });

S('dash-full', density('full'));
S('dash-full-scrolled', async (p) => { await density('full')(p); await p.evaluate(() => { const t = document.getElementById('tab-dashboard'); for (let e = t; e; e = e.parentElement) { if (e.scrollHeight > e.clientHeight + 2 && /auto|scroll/.test(getComputedStyle(e).overflowY)) { e.scrollTop = e.scrollHeight; break; } } document.scrollingElement.scrollTop = 1e6; }); await wait(p, 900); });
S('dash-compact', density('compact'));
S('dash-focused', density('focused'));
S('dash-edit', async (p) => { await density('full')(p); await p.evaluate(async () => { dashEditMode = true; await renderDashboard(); }); await wait(p, 1200); }, { after: (p) => p.evaluate(async () => { dashEditMode = false; await renderDashboard(); }) });
S('dash-widgets-dialog', async (p) => { await density('full')(p); await p.evaluate(() => document.getElementById('dash-widgets-open').click()); await wait(p, 900); });
S('dash-more-menu', async (p) => { await density('full')(p); await p.evaluate(() => document.querySelector('#dash-more button')?.click()); await wait(p, 600); });
S('dash-customise-menu', async (p) => { await density('full')(p); await p.evaluate(() => document.querySelector('#dash-customise button')?.click()); await wait(p, 600); });
S('dash-help', async (p) => { await density('full')(p); await p.evaluate(() => document.getElementById('dash-help-toggle')?.click()); await wait(p, 500); });
S('dash-quick-edit', async (p) => { await density('full')(p); await p.evaluate(() => { quickEditing = true; renderQuickLinks(); }); await wait(p, 700); }, { after: (p) => p.evaluate(() => { quickEditing = false; renderQuickLinks(); }) });
S('dash-widget-menu', async (p) => { await density('full')(p); await p.evaluate(() => document.querySelector('#dash-grid .kebab-opener, #dash-grid [aria-haspopup="menu"]')?.click()); await wait(p, 600); });
S('top-space-menu', async (p) => { await tab('dashboard')(p); await p.evaluate(() => document.getElementById('space-switcher-btn').click()); await wait(p, 700); });
const pickSpace = (re) => async (p) => { await p.evaluate(() => document.getElementById('space-switcher-btn').click()); await wait(p, 600); await p.evaluate((src) => { const o = [...document.querySelectorAll('#space-menu [role^=menuitem], #space-menu button')].find((b) => new RegExp(src).test(b.textContent)); o?.click(); }, re); await wait(p, 2000); };
S('top-space-named', async (p) => { await tab('dashboard')(p); await pickSpace('Work projects 2026')(p); }, { after: async (p) => { await closeAll(p); await pickSpace('All spaces')(p); } });
S('top-notifications', async (p) => { await tab('dashboard')(p); await p.evaluate(() => document.getElementById('notif-btn').click()); await wait(p, 1000); });
S('top-tabs-each', async (p) => { /* measured per tab below */ }, { perTab: true });
S('status-ai-popup', async (p) => { await tab('dashboard')(p); await p.hover('#ai-status').catch(() => {}); await p.evaluate(() => document.getElementById('ai-status')?.focus()); await wait(p, 600); });
S('status-clock-on', async (p) => { await tab('dashboard')(p); await p.evaluate(() => { prefsCache.status_bar_clock = true; applyStatusClock(); }); await wait(p, 600); }, { after: (p) => p.evaluate(() => { prefsCache.status_bar_clock = false; applyStatusClock(); }) });
S('status-tray', async (p) => { await tab('dashboard')(p); await p.evaluate(() => document.getElementById('status-tray').click()); await wait(p, 1200); });
S('status-agent', async (p) => { await tab('dashboard')(p); await p.evaluate(() => toggleAgentPalette()); await wait(p, 1200); });
S('status-find', async (p) => { await tab('dashboard')(p); await p.evaluate(() => openFinder('zoom')); await wait(p, 1500); });
S('palette', async (p) => { await tab('dashboard')(p); await p.evaluate(() => openPalette()); await wait(p, 900); });
S('palette-query', async (p) => { await tab('dashboard')(p); await p.evaluate(() => openPalette()); await wait(p, 600); await p.fill('#palette-input', 'note').catch(() => {}); await wait(p, 1200); });
S('palette-help', async (p) => { await tab('dashboard')(p); await p.evaluate(() => openPalette()); await wait(p, 600); await p.evaluate(() => document.querySelector('[data-help-for="palette-help"]')?.click()); await wait(p, 500); });
S('toast-action', async (p) => { await tab('dashboard')(p); await p.evaluate(() => toastAction('Moved 3 notes to Research and planning for the autumn term', 'Undo', () => {})); await wait(p, 700); });
S('lock-unlock', async (p) => { await p.evaluate(() => lockNow()); await wait(p, 1500); }, { lock: true });
S('lock-setup', async (p) => { await p.evaluate(() => showLockScreen(true)); await wait(p, 500); }, { lock: true });
S('lock-lan', async (p) => { await p.evaluate(() => { showLockScreen(false); document.documentElement.dataset.lan = '1'; document.querySelector('[data-help-for="lock-lan-cert-help"]')?.click(); }); await wait(p, 600); }, { lock: true });
S('lock-forgot', async (p) => { await p.evaluate(() => { delete document.documentElement.dataset.lan; document.getElementById('lock-forgot').click(); }); await wait(p, 2000); }, { lock: true });
S('lock-forgot-help', async (p) => { await p.evaluate(() => document.querySelector('[data-help-for="lock-forgot-help"]')?.click()); await wait(p, 500); }, { lock: true, last: true });

// ---------------------------------------------------------------- the driver
async function seed(page) {
  await page.evaluate(async () => {
    const have = await (await api('/documents')).json();
    if ((have.documents || have).some((d) => /Zoom plan/.test(d.title))) return;
    const cats = ['Research', 'Work projects', 'Personal and family admin'];
    const ids = [];
    for (let i = 0; i < 9; i++) {
      const r = await api('/entries', { method: 'POST', body: JSON.stringify({ content: `Zoom note ${i}: a reasonably long line of text about the quarterly planning review so a card has body copy to wrap and truncate - [ ] follow up with the team ${i}`, tags: [`zoom${i % 3}`, 'planning', 'long-tag-name-here'] }) });
      const e = await r.json(); ids.push(e.id);
    }
    for (let i = 0; i < ids.length; i++) await api(`/entries/${ids[i]}`, { method: 'PUT', body: JSON.stringify({ category: cats[i % 3], pinned: i < 3 }) });
    for (const t of ['Zoom plan for the autumn term', 'Meeting notes: design review', 'Reading list']) await api('/documents', { method: 'POST', body: JSON.stringify({ title: t, content: `# ${t}\n\nSome text with **bold**.\n` }) });
    await api('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: 'Zoom board with a long name' }) });
    await api('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: 'Zoom map', type: 'map' }) });
    const day = 86400000;
    for (const [t, d, restore] of [['Send the quarterly report to the finance team before the board meeting', 2 * day, false], ['Renew passport', 5 * day, false], ['Call the dentist about the appointment that moved', -day, true], ['Water the plants', 3600000, false]]) {
      await api('/reminders', { method: 'POST', body: JSON.stringify({ text: t, due_at: new Date(Date.now() + d).toISOString(), restore }) });
    }
    for (const n of ['Research and reading', 'Work projects 2026', 'Family']) await api('/spaces', { method: 'POST', body: JSON.stringify({ name: n }) });
  });
}
async function prepare(page) {
  // Every widget on, and notifications with long rows.
  await page.evaluate(async () => {
    const l = dashLayout();
    if (l.hidden.length) await saveDashLayout({ ...l, hidden: [] });
    const rows = [['reminder', 'Call the dentist about the appointment that moved', 'Due yesterday'], ['job', 'Finished: re-indexing 1,204 notes for search', 'took 2 min 14 s'], ['agent', 'Atlas filed 12 notes into Work projects 2026 and Research and reading', ''], ['error', 'The import of “Quarterly planning export.zip” stopped early', 'Open the logs to see why']];
    for (const [kind, title, detail] of rows) recordNotification({ kind, title, detail, key: 'wz-' + title.slice(0, 20), action: { tab: 'reminders' } });
  });
}

async function measure(page) {
  const a = await page.evaluate(detect);
  const b = await page.evaluate(underBars).catch((e) => [{ kind: 'error', sel: 'underBars', text: String(e.message).slice(0, 80) }]);
  return [...a, ...b];
}

async function runViewport(spec, rows) {
  const { boot } = require('./lib.js');
  const [wh, sc] = spec.split('@'); const [w, h] = wh.split('x').map(Number); const scale = Number(sc || 1);
  let { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
  if (!process.env.NOSEED) { await seed(page); }
  await prepare(page);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await wait(page, 2500);
  if (await page.isVisible('#lock-password').catch(() => false)) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await wait(page, 3000); }
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden')).catch(() => {});
  const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
  const push = (state, found) => {
    const seen = new Map();
    for (const f of found) { const k = f.kind + f.sel + (f.what || '') + (f.over || '') + (f.end || ''); if (seen.has(k)) { seen.get(k).count++; continue; } const row = { vp: spec, theme: THEME, state, count: 1, ...f }; seen.set(k, row); rows.push(row); }
    rows.push({ vp: spec, theme: THEME, state, kind: 'measured', n: found.length });
  };
  for (const st of STATES) {
    if (ONLY.length && !ONLY.some((o) => st.name.startsWith(o))) continue;
    try {
      if (!st.lock) await closeAll(page);
      if (st.perTab) {
        for (const t of ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders']) {
          await page.evaluate((t) => switchTab(t), t); await wait(page, 1300);
          // only the shell rows on the other tabs (their bodies are other surfaces)
          const found = (await page.evaluate(detect)).filter((f) => /#top-bar|#tab-bar|#status-bar|header-controls|space-switcher|^page$/.test(f.sel + ' ' + (f.by || '')) || f.sel === 'page');
          push('tab-' + t, found);
        }
        continue;
      }
      await st.setup(page);
      push(st.name, await measure(page));
      if (st.after) await st.after(page).catch(() => {});
      if (st.last) {
        await page.evaluate(() => { document.getElementById('lock-forgot-close')?.click(); showLockScreen(false); });
        await wait(page, 500);
        await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit');
        await page.waitForFunction(() => document.getElementById('lock-overlay')?.classList.contains('hidden'), null, { timeout: 20000 }).catch(() => {});
        await wait(page, 1500);
      }
    } catch (e) {
      rows.push({ vp: spec, theme: THEME, state: st.name, kind: 'error', sel: String(e.message).split('\n')[0].slice(0, 120) });
      if (/crash|closed|Target/i.test(e.message)) { await browser.close().catch(() => {}); ({ browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: scale })); }
    }
  }
  await browser.close();
}

function summary() {
  const files = fs.readdirSync(SCRATCH).filter((f) => /^wrapzoom-shell-.*\.json$/.test(f));
  const rows = files.flatMap((f) => JSON.parse(fs.readFileSync(`${SCRATCH}/${f}`, 'utf8')));
  const measured = rows.filter((r) => r.kind === 'measured');
  const errors = rows.filter((r) => r.kind === 'error');
  const groups = new Map();
  for (const r of rows.filter((r) => !['measured', 'error'].includes(r.kind))) {
    const k = r.kind + ' | ' + (r.what || '') + ' | ' + r.sel + (r.over ? ' over ' + r.over : '') + (r.scroller ? ' in ' + r.scroller + ' @' + r.end : '');
    if (!groups.has(k)) groups.set(k, { k, vps: new Set(), states: new Set(), themes: new Set(), sample: r });
    const g = groups.get(k); g.vps.add(r.vp); g.states.add(r.state); g.themes.add(r.theme);
  }
  console.log(`${measured.length} state measurements across ${new Set(measured.map((r) => r.vp + r.theme)).size} viewport/theme runs; ${errors.length} errors`);
  for (const e of errors) console.log('ERROR', e.vp, e.theme, e.state, e.sel);
  for (const g of [...groups.values()].sort((a, b) => a.k.localeCompare(b.k))) {
    const { vp, theme, state, kind, sel, ...nums } = g.sample;
    console.log(`${g.k}\n   vps=${[...g.vps].join(',')} themes=${[...g.themes].join(',')} states=${[...g.states].slice(0, 8).join(',')}${g.states.size > 8 ? '…' : ''}\n   ${JSON.stringify(nums)}`);
  }
}

(async () => {
  if (process.env.SUMMARY) return summary();
  const vps = (process.env.VPS || MATRIX.join(',')).split(',');
  for (const spec of vps) {
    const rows = [];
    try { await runViewport(spec, rows); } catch (e) { rows.push({ vp: spec, theme: THEME, state: 'boot', kind: 'error', sel: String(e.message).slice(0, 120) }); }
    const file = `${SCRATCH}/wrapzoom-shell-${THEME}-${spec.replace(/[@.]/g, '_')}.json`;
    fs.writeFileSync(file, JSON.stringify(rows, null, 1));
    const bad = rows.filter((r) => !['measured'].includes(r.kind));
    console.log(spec, THEME, 'states', rows.filter((r) => r.kind === 'measured').length, 'findings', bad.length, '->', file);
  }
})();
