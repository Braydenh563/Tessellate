// Wrap/zoom sweep of Settings, the shell's dialogs and popovers, and the
// desktop companion page (owner, 2026-11-11: "make sure the wrapping and ui
// issues arent an issue anywhere else from zoom or resolution").
// Surface: every Settings section in the nav (at rest, then with Expand all),
// its pane bar with a "Reset N changes" button showing, every help ? in it
// (the popover measured), its kebab menus and dropdown menus, the Settings
// search results; the shell's confirm and prompt dialogs, Keyboard shortcuts,
// Tools and features, the space dialogs, Quick note, the recovery key, a
// binned note, a note's history and connections, and their help popovers; and
// /desktop-companion.html in each state at its own window size.
// Read-only: measures, never edits the app (it does change two settings per
// pane and puts them back, in the sweep's own data dir).
//
// `detect` and `underBars` are wrapzoom-shell.js's, taking a root selector so
// a state measures its own surface and not the app behind the window.
// Defect classes (wrapzoom-shell.js has the full definitions):
//   wrap / clip / overlap / overflow / misalign, plus
//   offscreen: a popover, menu or dialog card partly outside the viewport.
//
// Run (dark matrix, then light at 1440):
//   BASE=http://127.0.0.1:8815 THEME=dark SCRATCH=<dir> node wrapzoom-settings.js
//   BASE=... THEME=light VPS=1440x900@1 SCRATCH=<dir> node wrapzoom-settings.js
//   DESK=1 BASE=... SCRATCH=<dir> node wrapzoom-settings.js   (the companion page)
//   SUMMARY=1 SCRATCH=<dir> node wrapzoom-settings.js         (de-duplicated table)
// VPS picks viewports (WxH@scale, comma separated); ONLY=<prefix,...> picks states;
// SECTIONS=<name,...> picks Settings sections.
const fs = require('fs');
const SCRATCH = process.env.SCRATCH || '.';
const THEME = process.env.THEME || 'dark';

const MATRIX = ['1280x720@1', '1366x768@1', '1440x900@1', '1920x1080@1', '2560x1440@1',
  '1536x864@1.25', '1280x720@1.5', '960x540@2', '1280x720@2', '768x1024@1'];

// ---------------------------------------------------------------- in the page
function detect(rootSel) {
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
    // A shut <details> keeps laying out its content (it still has rects) but
    // paints none of it: everything but its summary is gone.
    const shut = e.parentElement && e.parentElement.tagName === 'DETAILS' && !e.parentElement.open && e.tagName !== 'SUMMARY';
    const g = shut || s.display === 'none' || +s.opacity < 0.05 || (e.tagName === 'DIALOG' && !e.open) || gone(e.parentElement);
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

  const ROOT = (rootSel && document.querySelector(rootSel)) || document.body;
  const all = [...ROOT.querySelectorAll('*'), ...(ROOT !== document.body ? [ROOT] : [])].filter((e) => !(e instanceof SVGElement) && !['SCRIPT', 'STYLE', 'TEMPLATE', 'OPTION', 'BR', 'LINK', 'META', 'NOSCRIPT'].includes(e.tagName));
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
      const b0 = box(a);
      // `overflow: clip` paints out to its overflow-clip-margin (the ring-room recipe, 08-consistency.css).
      const m = (s.overflowX === 'clip' || s.overflowY === 'clip') ? parseFloat(s.overflowClipMargin) || 0 : 0;
      const b = { left: b0.left - (s.overflowX === 'clip' ? m : 0), right: b0.right + (s.overflowX === 'clip' ? m : 0), top: b0.top - (s.overflowY === 'clip' ? m : 0), bottom: b0.bottom + (s.overflowY === 'clip' ? m : 0) };
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
function underBars(rootSel) {
  const out = [];
  const cs = (e) => getComputedStyle(e);
  const sig = (el) => { const parts = []; for (let e = el, n = 0; e && e !== document.body && n < 4; e = e.parentElement, n++) { let s = e.tagName.toLowerCase(); if (e.id) { parts.unshift(s + '#' + e.id); break; } const c = typeof e.className === 'string' ? e.className.trim().split(/\s+/).slice(0, 2).join('.') : ''; parts.unshift(s + (c ? '.' + c : '')); } return parts.join(' > '); };
  const visible = (e) => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false; for (let a = e; a && a !== document.documentElement; a = a.parentElement) { const s = cs(a); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) return false; if (a.parentElement && a.parentElement.tagName === 'DETAILS' && !a.parentElement.open && a.tagName !== 'SUMMARY') return false; } return true; };
  const BAR = /(^|[\s_-])(bar|foot|footer|head|header|dock|toolbar|editbar|actions)($|[\s_-])/i;
  const NOT = /(overlay|dialog|menu|toast|help|popup|popover|tooltip|suggest|tray|panel|modal|splash)/i;
  let bars = [...document.querySelectorAll('body *')].filter((e) => {
    const p = cs(e).position; if (p !== 'fixed' && p !== 'sticky') return false;
    const name = (typeof e.className === 'string' ? e.className : '') + ' ' + e.id + ' ' + e.tagName;
    if (p === 'fixed' && (!BAR.test(name) || NOT.test(name))) return false;
    const r = e.getBoundingClientRect();
    return visible(e) && r.width > 120 && r.height < innerHeight * 0.3;
  });
  const nearScroller = (e) => { for (let a = e; a && a !== document.body; a = a.parentElement) { const s = cs(a); if (/auto|scroll/.test(s.overflowY) && a.scrollHeight > a.clientHeight + 2) return a; } return document.scrollingElement; };
  let scrollers = [document.scrollingElement, ...[...document.querySelectorAll('body *')].filter((e) => { const s = cs(e); return /auto|scroll/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 2 && visible(e); })];
  { const R0 = rootSel && document.querySelector(rootSel); if (R0) { bars = bars.filter((b) => R0.contains(b)); scrollers = scrollers.filter((s) => R0.contains(s)); } }
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


// A floating surface (popover, menu, dialog card) inside the viewport.
function offscreen(rootSel) {
  const el = document.querySelector(rootSel);
  if (!el) return [];
  const r = el.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return [];
  const VW = document.documentElement.clientWidth, VH = document.documentElement.clientHeight;
  const cut = {};
  if (r.left < -1) cut.left = Math.round(-r.left);
  if (r.top < -1) cut.top = Math.round(-r.top);
  if (r.right > VW + 1) cut.right = Math.round(r.right - VW);
  if (r.bottom > VH + 1) cut.bottom = Math.round(r.bottom - VH);
  if (!Object.keys(cut).length) return [];
  return [{ kind: 'offscreen', sel: (el.id ? '#' + el.id : el.className), cut, rect: [r.left, r.top, r.width, r.height].map(Math.round), vw: VW, vh: VH }];
}

// ---------------------------------------------------------------- helpers
const wait = (p, ms) => p.waitForTimeout(ms);
const ROOT_ATTR = 'data-wz-root';
const ROOT_SEL = `[${ROOT_ATTR}]`;
async function measure(page, rootSel, { bars = true } = {}) {
  const a = await page.evaluate(detect, rootSel);
  const b = bars ? await page.evaluate(underBars, rootSel).catch((e) => [{ kind: 'error', sel: 'underBars', text: String(e.message).slice(0, 80) }]) : [];
  return [...a, ...b];
}
// `detect` measures only what is painted, so a long pane is measured a
// screen at a time: its scroller (the given one, else the tallest scroller in
// the root) is stepped by 85% of its height from the top to the bottom, and
// each step's findings are pushed as `<state>@<step>`. Put back at the top.
async function measureSteps(page, rootSel, state, push, scrollerSel = null) {
  const steps = await page.evaluate(({ rootSel, scrollerSel }) => {
    const root = document.querySelector(rootSel) || document.body;
    let sc = scrollerSel ? document.querySelector(scrollerSel) : null;
    if (!sc) sc = [root, ...root.querySelectorAll('*')].filter((e) => /auto|scroll/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 2 && e.getClientRects().length).sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
    if (!sc) return 1;
    document.querySelectorAll('[data-wz-scroller]').forEach((e) => e.removeAttribute('data-wz-scroller'));
    sc.setAttribute('data-wz-scroller', '1');
    sc.scrollTop = 0;
    return Math.min(14, 1 + Math.ceil((sc.scrollHeight - sc.clientHeight) / (sc.clientHeight * 0.85)));
  }, { rootSel, scrollerSel });
  for (let i = 0; i < steps; i++) {
    if (i) {
      await page.evaluate((i) => { const sc = document.querySelector('[data-wz-scroller]'); if (sc) sc.scrollTop = Math.round(i * sc.clientHeight * 0.85); }, i);
      await wait(page, 250);
    }
    push(steps > 1 ? `${state}@${i}` : state, await measure(page, rootSel, { bars: i === 0 }));
  }
  await page.evaluate(() => { const sc = document.querySelector('[data-wz-scroller]'); if (sc) sc.scrollTop = 0; });
  await wait(page, 150);
}

// Mark the element a state measures, so detect can be scoped to it.
const markRoot = (page, sel) => page.evaluate(({ sel, attr }) => {
  document.querySelectorAll(`[${attr}]`).forEach((e) => e.removeAttribute(attr));
  const el = typeof sel === 'string' ? document.querySelector(sel) : null;
  if (el) el.setAttribute(attr, '1');
  return !!el;
}, { sel, attr: ROOT_ATTR });
const closeFloating = (page) => page.evaluate(() => {
  try { closeHelpPopovers(); } catch (e) {}
  try { closeActionMenus(); } catch (e) {}
}).catch(() => {});
const closeAll = async (page) => {
  for (let i = 0; i < 2; i++) await page.keyboard.press('Escape').catch(() => {});
  await page.evaluate(() => {
    try { closeHelpPopovers(); } catch (e) {}
    try { closeActionMenus(); } catch (e) {}
    document.querySelectorAll('.confirm-overlay').forEach((o) => { const c = [...o.querySelectorAll('button')].find((b) => /cancel|keep|don.t/i.test(b.textContent)); if (c) c.click(); else o.remove(); });
    document.querySelectorAll('dialog[open]').forEach((d) => d.close());
    for (const id of ['shortcuts-overlay', 'features-overlay', 'binned-overlay', 'history-overlay', 'connections-overlay']) document.getElementById(id)?.classList.add('hidden');
    if (!document.getElementById('settings-modal')?.classList.contains('hidden')) closeSettingsModal();
  }).catch(() => {});
  await wait(page, 300);
};

// Every visible help ? inside `scopeSel`: press it, measure the popover it
// opened (scoped), check it is on screen, close it.
async function helpPopovers(page, scopeSel, state, push) {
  const ids = await page.evaluate((s) => [...document.querySelectorAll(`${s} [data-help-for]`)]
    .filter((t) => {
      if (!t.getClientRects().length || t.offsetParent === null) return false;
      // Inside a shut fold (and not on its summary) a ? still has a rect but is not shown.
      for (let d = t.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) if (!d.open && !d.querySelector(':scope > summary')?.contains(t)) return false;
      return true;
    }).map((t) => t.dataset.helpFor), scopeSel);
  for (const id of [...new Set(ids)]) {
    const opened = await page.evaluate(({ s, id }) => {
      const t = document.querySelector(`${s} [data-help-for="${id}"]`);
      if (!t) return false;
      t.scrollIntoView({ block: 'center' });
      return true;
    }, { s: scopeSel, id });
    if (!opened) continue;
    // The scroll's own event closes open popovers (closeActionMenusOnScroll),
    // so the press waits for it to land.
    await wait(page, 300);
    await page.evaluate(({ s, id }) => document.querySelector(`${s} [data-help-for="${id}"]`)?.click(), { s: scopeSel, id });
    await wait(page, 380);
    const ok = await page.evaluate((id) => { const p = document.getElementById(id); if (!p) return false; const r = p.getBoundingClientRect(); return !p.classList.contains('hidden') && r.width > 0 && r.height > 0; }, id);
    if (!ok) { push(`${state}?${id}`, [{ kind: 'error', sel: `help ${id} did not open` }]); continue; }
    await markRoot(page, `#${CSS_ESCAPE(id)}`);
    const off = await page.evaluate(offscreen, ROOT_SEL);
    // Where its ? was when it opened: a popover off screen beside a ? that is
    // itself off screen is the scroll, not the popover.
    if (off.length) off[0].trigger = await page.evaluate(({ s, id }) => { const t = document.querySelector(`${s} [data-help-for="${id}"]`); const r = t.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); }, { s: scopeSel, id });
    const found = [...await measure(page, ROOT_SEL, { bars: false }), ...off];
    push(`${state}?${id}`, found);
    await closeFloating(page); await wait(page, 120);
  }
}
const CSS_ESCAPE = (s) => s.replace(/([^\w-])/g, '\\$1');

// Kebab menus and dropdown menus inside `scopeSel` (at most `max` of each).
async function menus(page, scopeSel, state, push, max = 3) {
  for (const kind of ['kebab', 'select']) {
    const n = await page.evaluate(({ s, kind }) => {
      const q = kind === 'kebab' ? `${s} .menu-wrap > button` : `${s} .select-shell > .select-opener`;
      document.querySelectorAll('[data-wz-opener]').forEach((b) => b.removeAttribute('data-wz-opener'));
      const list = [...document.querySelectorAll(q)].filter((b) => b.getClientRects().length && b.offsetParent !== null && !b.disabled);
      list.forEach((b, i) => b.setAttribute('data-wz-opener', kind + i));
      return list.length;
    }, { s: scopeSel, kind });
    for (let i = 0; i < Math.min(n, max); i++) {
      const label = await page.evaluate((k) => {
        const b = document.querySelector(`[data-wz-opener="${k}"]`);
        if (!b) return null;
        b.scrollIntoView({ block: 'center' });
        return (b.getAttribute('aria-label') || b.textContent || '').trim().slice(0, 30);
      }, kind + i);
      if (label === null) continue;
      await wait(page, 300);
      await page.evaluate((k) => document.querySelector(`[data-wz-opener="${k}"]`)?.click(), kind + i);
      await wait(page, 400);
      const has = await page.evaluate((attr) => {
        const m = [...document.querySelectorAll('.action-menu:not(.hidden)')].filter((e) => e.getClientRects().length).pop();
        document.querySelectorAll(`[${attr}]`).forEach((e) => e.removeAttribute(attr));
        if (!m) return false;
        m.setAttribute(attr, '1');
        return true;
      }, ROOT_ATTR);
      if (!has) { push(`${state}:${kind}${i}`, [{ kind: 'error', sel: `${kind} "${label}" opened no menu` }]); continue; }
      const off = await page.evaluate(offscreen, ROOT_SEL);
      if (off.length) off[0].trigger = await page.evaluate((k) => { const r = document.querySelector(`[data-wz-opener="${k}"]`).getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); }, kind + i);
      const found = [...await measure(page, ROOT_SEL, { bars: false }), ...off];
      push(`${state}:${kind}${i}:${label}`, found);
      await closeFloating(page); await wait(page, 150);
    }
  }
}

// ---------------------------------------------------------------- Settings
const SAFE_NUDGE = /^(pref-(auto-tag|auto-link|auto-dedupe|auto-stale-review|smart-punctuation|link-offers|check-link-text|autocorrect|before-includes-day|auto-caption-images|auto-read-image-text|warm-search-model|battery-mode|smart-model-routing|web-store|notif-mute-except-reminders|update-bar)|voice-skip-silence|status-bar-clock-toggle|searxng-autostart)$/;
async function settingsSections(page, push) {
  await page.evaluate(() => openSettingsModal('models'));
  await page.waitForFunction(() => !document.getElementById('settings-modal').classList.contains('hidden'), null, { timeout: 15000 });
  await wait(page, 2500);
  let names = await page.evaluate(() => [...document.querySelectorAll('#settings-nav button[data-section]')].map((b) => b.dataset.section));
  const pick = (process.env.SECTIONS || '').split(',').filter(Boolean);
  if (pick.length) names = names.filter((n) => pick.includes(n));
  const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
  const want = (st) => !ONLY.length || ONLY.some((o) => st.startsWith(o));
  for (const name of names) {
    const st = `set:${name}`;
    try {
      await closeFloating(page);
      await page.evaluate((n) => { if (document.getElementById('settings-modal').classList.contains('hidden')) return openSettingsModal(n); showSettingsSection(n); }, name);
      await wait(page, 1400);
      await page.evaluate((n) => { const p = document.getElementById('settings-' + n); p && (p.scrollTop = 0); const c = document.querySelector('#settings-modal .modal-content'); if (c) c.scrollTop = 0; }, name);
      if (want(st)) await measureSteps(page, '#settings-modal', st, push, '#settings-modal .modal-content');
      // Expand all (the pane bar's own button where it has one).
      const how = await page.evaluate((n) => {
        const pane = document.getElementById('settings-' + n);
        const b = pane?.querySelector('[data-fold-all="expand"]');
        if (b) { b.click(); return 'button'; }
        const folds = [...(pane?.querySelectorAll('details') || [])];
        folds.forEach((d) => { d.open = true; });
        return folds.length ? 'opened' : 'none';
      }, name);
      if (how !== 'none') {
        await wait(page, 900);
        if (want(st + ':expanded')) await measureSteps(page, '#settings-modal', st + ':expanded', push, '#settings-modal .modal-content');
      }
      if (want(st + '?')) await helpPopovers(page, `#settings-${name}`, st, push);
      if (want(st + ':')) await menus(page, `#settings-${name}`, st, push);
      // The pane bar with "Reset N changes" showing: two safe switches moved.
      if (want(st + ':reset')) {
        const moved = await page.evaluate(({ n, re }) => {
          const pane = document.getElementById('settings-' + n);
          const rows = (typeof SETTING_ROWS !== 'undefined' ? SETTING_ROWS : []).filter((r) => new RegExp(re).test(r.id));
          const hit = [];
          for (const r of rows) {
            const el = document.getElementById(r.id);
            if (!el || !pane.contains(el) || el.type !== 'checkbox' || !el.getClientRects().length && !el.closest('label')?.getClientRects().length) continue;
            el.click(); hit.push(r.id);
            if (hit.length === 2) break;
          }
          return hit;
        }, { n: name, re: SAFE_NUDGE.source });
        if (moved.length) {
          await wait(page, 1500);
          await page.evaluate(() => document.querySelectorAll('.confirm-overlay').forEach((o) => { const c = [...o.querySelectorAll('button')].find((b) => /cancel|keep|don.t/i.test(b.textContent)); c?.click(); }));
          await page.evaluate((n) => { try { paintSettingRows?.(n); } catch (e) {} const p = document.getElementById('settings-' + n); if (p) p.scrollTop = 0; const c = document.querySelector('#settings-modal .modal-content'); if (c) c.scrollTop = 0; }, name).catch(() => {});
          await wait(page, 700);
          const shown = await page.evaluate((n) => { const b = document.querySelector(`#settings-${n} .settings-reset-section`); return !!(b && !b.hidden && b.getClientRects().length); }, name);
          push(st + ':reset', shown ? await measure(page, '#settings-modal') : [{ kind: 'error', sel: `reset bar not shown after moving ${moved.join(',')}` }]);
          await page.evaluate((n) => { const b = document.querySelector(`#settings-${n} .settings-reset-section`); if (b && !b.hidden) b.click(); }, name);
          await wait(page, 1200);
          // Belt: anything still moved goes back by its row reset.
          await page.evaluate((ids) => ids.forEach((id) => { const el = document.getElementById(id); const b = el?.closest('.setting-modified')?.querySelector('.setting-reset'); b?.click(); }), moved);
          await wait(page, 400);
        }
      }
    } catch (e) {
      push(st, [{ kind: 'error', sel: String(e.message).split('\n')[0].slice(0, 140) }]);
    }
  }
  // The Settings search, with results showing.
  if (!ONLY.length || ONLY.some((o) => 'set-search'.startsWith(o) || o.startsWith('set-search'))) {
    try {
      await page.evaluate(() => { if (document.getElementById('settings-modal').classList.contains('hidden')) return openSettingsModal('models'); });
      await wait(page, 600);
      await page.fill('#settings-search', 'reminders notifications').catch(() => {});
      await wait(page, 1200);
      push('set-search', await measure(page, '#settings-modal'));
      await page.fill('#settings-search', 'model').catch(() => {});
      await wait(page, 1200);
      push('set-search-model', await measure(page, '#settings-modal'));
      await page.fill('#settings-search', '').catch(() => {});
    } catch (e) { push('set-search', [{ kind: 'error', sel: String(e.message).slice(0, 120) }]); }
  }
  await closeAll(page);
}

// ---------------------------------------------------------------- shell dialogs
const DIALOGS = [
  ['confirm-plain', `() => { window.__wz = confirmDialog('Delete this note?'); }`, '.confirm-overlay'],
  ['confirm-two-para', `() => { window.__wz = confirmDialog('Check for updates automatically?\\n\\nTessellate can look for a new version once a day. Nothing about your notes is sent.', { confirmLabel: 'Check automatically', cancelLabel: "Don't check", danger: false }); }`, '.confirm-overlay'],
  ['confirm-long-labels', `() => { window.__wz = confirmDialog('Make this space ordinary?\\n\\nIts notes will show in search, the graph and the dashboard again, and anyone who opens the notebook can read them.', { confirmLabel: 'Make it ordinary', cancelLabel: 'Keep it private', danger: false }); }`, '.confirm-overlay'],
  ['confirm-checkbox', `() => { window.__wz = confirmDialog('Remove this picture?\\n\\nIt goes to the recycle bin for 30 days.', { checkbox: { label: 'Also take this picture out of the notes that show it', checked: true } }); }`, '.confirm-overlay'],
  ['confirm-reindex', `() => { window.__wz = confirmDialog('Switch the search model?\\n\\nEvery note is read again with the new model, which can take several minutes on a large notebook.', { confirmLabel: 'Switch and re-index', danger: false }); }`, '.confirm-overlay'],
  ['prompt-segment', `() => { window.__wz = promptDialog('Name the new board', 'Planning for the autumn term', { confirmLabel: 'Create', segment: { label: 'Kind', value: 'board', options: [{ value: 'board', label: 'Whiteboard' }, { value: 'map', label: 'Mind map' }, { value: 'diagram', label: 'Diagram' }] } }); }`, '.confirm-overlay, .modal-overlay:not(.hidden) .prompt-card'],
  ['shortcuts', `() => openShortcuts()`, '#shortcuts-overlay'],
  ['features', `() => openFeatures()`, '#features-overlay'],
  ['space-create', `() => openSpaceCreate()`, '#space-create-dialog'],
  ['space-edit', `() => privateSpaces('edit', (spacesCache.find((s) => s.id !== 'default') || spacesCache[0]).id)`, '#space-edit-dialog'],
  ['space-delete', `() => rmSpace((spacesCache.find((s) => s.id !== 'default') || spacesCache[0]).id)`, '#space-delete-dialog'],
  ['quick-note', `() => openQuickNote()`, '#quick-note'],
  // Not awaited: showRecoveryKey resolves only when its dialog is closed.
  ['recovery-key', `() => { showRecoveryKey('K7QX-3MPR-9WZT-HB2D-LC4N-8VYE-FJ6S-A5UG'); }`, '#recovery-key-dialog'],
  ['binned-note', `async () => { const e = await (await api('/entries', { method: 'POST', body: JSON.stringify({ content: 'A binned note about the quarterly planning review, long enough to wrap onto a second line', tags: ['planning'] }) })).json(); await api('/entries/' + e.id, { method: 'DELETE' }); await openBinnedNote(e.id); }`, '#binned-overlay'],
  ['note-history', `async () => { const e = await apiJson('/entries?limit=5'); const x = (Array.isArray(e) ? e : (e.entries || e.items || []))[0]; await ensureModule('noteHistory').catch(() => {}); if (typeof openEntryHistory !== 'function') await lazyScript('/js/note-history.js'); await openEntryHistory(x); }`, '#history-overlay'],
  ['connections', `async () => { const e = await apiJson('/entries?limit=5'); const x = (Array.isArray(e) ? e : (e.entries || e.items || []))[0]; await lazyScript('/js/connections.js'); await openConnections('entries', x.id, 'A note about planning'); }`, '#connections-overlay'],
];
async function shellDialogs(page, push) {
  const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
  for (const [name, open, sel] of DIALOGS) {
    const st = `dlg:${name}`;
    if (ONLY.length && !ONLY.some((o) => st.startsWith(o))) continue;
    try {
      await closeAll(page);
      // An opener that waits for its dialog to close must not hang the sweep.
      await Promise.race([page.evaluate(`(${open})()`), new Promise((r) => setTimeout(r, 8000))]);
      await wait(page, 1300);
      // The card itself: the first match that is on screen.
      const root = await page.evaluate(({ sel, attr }) => {
        document.querySelectorAll(`[${attr}]`).forEach((e) => e.removeAttribute(attr));
        const el = [...document.querySelectorAll(sel)].find((e) => e.getClientRects().length && !e.classList.contains('hidden'));
        if (!el) return null;
        el.setAttribute(attr, '1');
        const card = el.matches('.modal-card, dialog') ? el : el.querySelector('.modal-card, .confirm-card, .card') || el;
        card.setAttribute('data-wz-card', '1');
        return el.tagName + (el.id ? '#' + el.id : '.' + el.className);
      }, { sel, attr: ROOT_ATTR });
      if (!root) { push(st, [{ kind: 'error', sel: `${sel} not open` }]); continue; }
      push(st + ':card', await page.evaluate(offscreen, '[data-wz-card]'));
      await measureSteps(page, ROOT_SEL, st, push);
      const scope = await page.evaluate((s) => { const el = document.querySelector(s); el.setAttribute('data-wz-scope', '1'); return true; }, ROOT_SEL);
      if (scope) { await helpPopovers(page, '[data-wz-scope]', st, push); await menus(page, '[data-wz-scope]', st, push, 2); }
      await page.evaluate(() => document.querySelectorAll('[data-wz-scope],[data-wz-card]').forEach((e) => { e.removeAttribute('data-wz-scope'); e.removeAttribute('data-wz-card'); }));
    } catch (e) {
      push(st, [{ kind: 'error', sel: String(e.message).split('\n')[0].slice(0, 140) }]);
    }
  }
  await closeAll(page);
}

// ---------------------------------------------------------------- seeding
async function seed(page) {
  await page.evaluate(async () => {
    const have = await (await api('/documents')).json();
    if ((have.documents || have).some((d) => /Settings zoom plan/.test(d.title))) return;
    const ids = [];
    for (let i = 0; i < 6; i++) {
      const r = await api('/entries', { method: 'POST', body: JSON.stringify({ content: `Settings zoom note ${i}: the quarterly planning review needs a long enough line to wrap on a narrow window - [ ] follow up ${i}`, tags: ['planning', `zoom${i}`] }) });
      ids.push((await r.json()).id);
    }
    await api(`/entries/${ids[0]}`, { method: 'PUT', body: JSON.stringify({ content: 'Settings zoom note 0, edited once so it has a history to show' }) });
    await api(`/entries/${ids[5]}`, { method: 'DELETE' });
    for (const t of ['Settings zoom plan for the autumn term', 'Meeting notes: design review']) await api('/documents', { method: 'POST', body: JSON.stringify({ title: t, content: `# ${t}\n\nSome text.\n` }) });
    const day = 86400000;
    for (const [t, d] of [['Send the quarterly report to the finance team before the board meeting', 2 * day], ['Renew passport', 5 * day]]) await api('/reminders', { method: 'POST', body: JSON.stringify({ text: t, due_at: new Date(Date.now() + d).toISOString() }) });
    for (const n of ['Research and reading', 'Work projects 2026']) await api('/spaces', { method: 'POST', body: JSON.stringify({ name: n }) });
  });
}

// ---------------------------------------------------------------- the driver
function pusher(spec, rows) {
  return (state, found) => {
    if (process.env.PROGRESS) process.stderr.write(`${new Date().toISOString().slice(11, 19)} ${spec} ${state} ${found.length}\n`);
    const seen = new Map();
    for (const f of found) { const k = f.kind + f.sel + (f.what || '') + (f.over || '') + (f.end || ''); if (seen.has(k)) { seen.get(k).count++; continue; } const row = { vp: spec, theme: THEME, state, count: 1, ...f }; seen.set(k, row); rows.push(row); }
    rows.push({ vp: spec, theme: THEME, state, kind: 'measured', n: found.length });
  };
}
const parse = (spec) => { const [wh, sc] = spec.split('@'); const [w, h] = wh.split('x').map(Number); return { w, h, scale: Number(sc || 1) }; };

async function runViewport(spec, rows) {
  const { boot } = require('./lib.js');
  const { w, h, scale } = parse(spec);
  const { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
  try {
    const dpr = await page.evaluate(() => [devicePixelRatio, innerWidth, innerHeight]);
    rows.push({ vp: spec, theme: THEME, state: 'boot', kind: 'measured', n: 0, dpr });
    if (!process.env.NOSEED) await seed(page);
    const push = pusher(spec, rows);
    const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
    if (!ONLY.length || ONLY.some((o) => o.startsWith('set'))) await settingsSections(page, push);
    if (!ONLY.length || ONLY.some((o) => o.startsWith('dlg'))) await shellDialogs(page, push);
  } finally { await browser.close(); }
}

// The desktop companion's window: each state at the size it asks its window
// for (logical px; pywebview scales them, so the CSS viewport is that size and
// devicePixelRatio is the zoom), unlocked and locked, plain and ?overlay.
const DESK_SIZES = { rest: [112, 152], menu: [248, 312], context: [248, 268], note: [320, 500], search: [340, 440] };
async function runDesk(rows) {
  const { chromium } = require('playwright');
  const BASE = process.env.BASE || 'http://127.0.0.1:8781';
  const browser = await chromium.launch();
  for (const scale of [1, 1.25, 1.5, 2]) {
    const spec = `desk@${scale}`;
    const push = pusher(spec, rows);
    const ctx = await browser.newContext({ viewport: { width: 112, height: 152 }, deviceScaleFactor: scale });
    await ctx.addInitScript((t) => { try { localStorage.setItem('theme', t); } catch (e) {} }, THEME);
    const page = await ctx.newPage();
    page.on('pageerror', (e) => rows.push({ vp: spec, theme: THEME, state: 'pageerror', kind: 'error', sel: e.message.slice(0, 120) }));
    const token = (await (await ctx.request.post(BASE + '/auth/unlock', { data: { password: 'testpassword123' } })).json()).token;
    for (const mode of ['', '?overlay=1']) {
      for (const tok of [token, '']) {
        const tag = (mode ? 'overlay' : 'window') + (tok ? '' : '-locked');
        await page.setViewportSize({ width: 112, height: 152 });
        await page.goto(BASE + '/desktop-companion.html' + mode, { waitUntil: 'domcontentloaded' });
        await page.evaluate((t) => { if (t) localStorage.setItem('token', t); else localStorage.removeItem('token'); }, tok);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await wait(page, 1500);
        const go = async (state) => {
          const [sw, sh] = DESK_SIZES[state];
          await page.setViewportSize({ width: sw, height: sh });
          await wait(page, 350);
          push(`desk:${tag}:${state}`, await measure(page, null));
        };
        if (!mode) await go('rest');
        // A trusted press: the pet tells a click from a drag by its pointer events.
        if (await page.isVisible('#desk-pet').catch(() => false)) await page.click('#desk-pet').catch(() => {}); else await page.evaluate(() => document.getElementById('desk-pet')?.click());
        await wait(page, 450);
        await go('menu');
        const items = await page.$$eval('#desk-menu button', (b) => b.map((x) => x.textContent.trim()));
        if (tok && items.some((t) => /Quick note/.test(t))) {
          await page.evaluate(() => [...document.querySelectorAll('#desk-menu button')].find((b) => /Quick note/.test(b.textContent))?.click()); await wait(page, 600);
          await go('note');
          await page.keyboard.press('Escape'); await wait(page, 300);
          if (await page.isVisible('#desk-pet').catch(() => false)) await page.click('#desk-pet').catch(() => {}); else await page.evaluate(() => document.getElementById('desk-pet')?.click());
          await wait(page, 400);
          await page.evaluate(() => [...document.querySelectorAll('#desk-menu button')].find((b) => /Quick search/.test(b.textContent))?.click()); await wait(page, 600);
          await page.fill('#desk-search-text', 'planning').catch(() => {}); await wait(page, 1400);
          await go('search');
          await page.keyboard.press('Escape'); await wait(page, 300);
        }
        if (!mode) {
          await page.setViewportSize({ width: 112, height: 152 });
          await page.click('#desk-pet', { button: 'right' }).catch(() => {}); await wait(page, 450);
          await go('context');
          await page.keyboard.press('Escape');
        }
      }
    }
    await ctx.close();
  }
  await browser.close();
}

function summary() {
  const files = fs.readdirSync(SCRATCH).filter((f) => /^wrapzoom-settings-.*\.json$/.test(f));
  const rows = files.flatMap((f) => JSON.parse(fs.readFileSync(`${SCRATCH}/${f}`, 'utf8')));
  const measured = rows.filter((r) => r.kind === 'measured');
  const errors = rows.filter((r) => r.kind === 'error');
  const groups = new Map();
  for (const r of rows.filter((r) => !['measured', 'error'].includes(r.kind))) {
    const k = r.kind + ' | ' + (r.what || '') + ' | ' + r.sel + (r.over ? ' over ' + r.over : '') + (r.scroller ? ' in ' + r.scroller + ' @' + r.end : '');
    if (!groups.has(k)) groups.set(k, { k, vps: new Set(), states: new Set(), themes: new Set(), samples: [] });
    const g = groups.get(k); g.vps.add(r.vp); g.states.add(r.state); g.themes.add(r.theme); if (g.samples.length < 3) g.samples.push(r);
  }
  console.log(`${measured.length} state measurements across ${new Set(measured.map((r) => r.vp + r.theme)).size} viewport/theme runs; ${errors.length} errors`);
  const errG = new Map(); for (const e of errors) { const k = e.state.replace(/\?.*/, '?') + ' ' + e.sel; errG.set(k, (errG.get(k) || []).concat(e.vp + '/' + e.theme)); }
  for (const [k, v] of errG) console.log('ERROR', k, v.length, v.slice(0, 4).join(','));
  for (const g of [...groups.values()].sort((a, b) => a.k.localeCompare(b.k))) {
    console.log(`${g.k}\n   vps=${[...g.vps].join(',')} themes=${[...g.themes].join(',')} states(${g.states.size})=${[...g.states].slice(0, 6).join(',')}${g.states.size > 6 ? '…' : ''}`);
    for (const s of g.samples) { const { theme, kind, sel, ...nums } = s; console.log('   ' + JSON.stringify(nums).slice(0, 400)); }
  }
}

(async () => {
  if (process.env.SUMMARY) return summary();
  if (process.env.DESK) {
    const rows = [];
    try { await runDesk(rows); } catch (e) { rows.push({ vp: 'desk', theme: THEME, state: 'desk', kind: 'error', sel: String(e.message).slice(0, 160) }); }
    const file = `${SCRATCH}/wrapzoom-settings-desk-${THEME}.json`;
    fs.writeFileSync(file, JSON.stringify(rows, null, 1));
    console.log('desk', THEME, 'states', rows.filter((r) => r.kind === 'measured').length, 'findings', rows.filter((r) => r.kind !== 'measured').length, '->', file);
    return;
  }
  const vps = (process.env.VPS || MATRIX.join(',')).split(',');
  for (const spec of vps) {
    const rows = [];
    const t0 = Date.now();
    try { await runViewport(spec, rows); } catch (e) { rows.push({ vp: spec, theme: THEME, state: 'boot', kind: 'error', sel: String(e.message).slice(0, 160) }); }
    const file = `${SCRATCH}/wrapzoom-settings-${THEME}-${spec.replace(/[@.]/g, '_')}.json`;
    fs.writeFileSync(file, JSON.stringify(rows, null, 1));
    console.log(spec, THEME, 'states', rows.filter((r) => r.kind === 'measured').length, 'findings', rows.filter((r) => r.kind !== 'measured').length, Math.round((Date.now() - t0) / 1000) + 's ->', file);
  }
})();
