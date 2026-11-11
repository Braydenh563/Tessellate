// Wrap, clip, overlap, overflow and misalign sweep for Notes (list, cards,
// the edit form and its panels, the sections, Quick note), the Library (every
// sub-tab), the Timeline and Reminders, across the zoom and resolution matrix
// the owner asked about ("make sure the wrapping and ui issues arent an issue
// anywhere else from zoom or resolution"). OS zoom is simulated as the CSS
// viewport it yields, with deviceScaleFactor set to the zoom factor.
//
//   BASE=http://127.0.0.1:8822 THEME=dark VPS=0,1,2 OUTF=/tmp/x.jsonl node wrapzoom-notes.js
//
// VPS picks rows of MATRIX by index (default all). Each state prints one JSON
// line {vp, state, findings:[...]}; aggregate with wrapzoom-notes-sum.py-style
// de-duplication by selector (the `sum` mode below: `node wrapzoom-notes.js sum F...`).
// Measures only: nothing is judged from a screenshot.
const fs = require('fs');
const MATRIX = [
  { w: 1280, h: 720, s: 1 }, { w: 1366, h: 768, s: 1 }, { w: 1440, h: 900, s: 1 },
  { w: 1920, h: 1080, s: 1 }, { w: 2560, h: 1440, s: 1 }, { w: 1536, h: 864, s: 1.25 },
  { w: 1280, h: 720, s: 1.5 }, { w: 960, h: 540, s: 2 }, { w: 1280, h: 720, s: 2 },
  { w: 768, h: 1024, s: 1 },
];

// ---- in-page measurement ---------------------------------------------------
// Runs inside the page: `roots` are the selectors of what the state shows (a
// tab panel, an open dialog or menu). Returns a list of findings.
function measure({ roots, passB }) {
  const out = [];
  // Effective opacity: a hover-revealed group is opacity 0 on the group, not
  // on its buttons, and checkVisibility only reads the element's own.
  const opq = new Map();
  const eff = (el) => { if (!el || el.nodeType !== 1) return 1; if (opq.has(el)) return opq.get(el); const v = parseFloat(getComputedStyle(el).opacity) * eff(el.parentElement); opq.set(el, v); return v; };
  const vis = (el) => el && el.checkVisibility && el.checkVisibility({ visibilityProperty: true })
    && el.getClientRects().length > 0 && eff(el) > 0.05;
  const R = (r) => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  const STATE = /^(active|hidden|open|is-[a-z-]+|has-[a-z-]+|selected|pressed|focus|hover|dragging|editing)$/;
  const desc = (el) => {
    if (!el || el.nodeType !== 1) return '';
    const own = (e) => {
      const id = e.id && !/\d{2,}/.test(e.id) ? '#' + e.id : '';
      if (id) return id;
      const cls = [...e.classList].filter((c) => !STATE.test(c) && !/\d{3,}/.test(c)).slice(0, 3);
      return e.tagName.toLowerCase() + (cls.length ? '.' + cls.join('.') : '');
    };
    if (el.id && !/\d{2,}/.test(el.id)) return '#' + el.id;
    let a = el.parentElement, anc = '';
    let hops = 0;
    while (a && hops < 12) { if (a.id && !/\d{2,}/.test(a.id)) { anc = '#' + a.id; break; } a = a.parentElement; hops++; }
    const par = el.parentElement && el.parentElement !== a ? own(el.parentElement) + ' > ' : '';
    return (anc ? anc + ' ' : '') + par + own(el);
  };
  // The next ancestor whose overflow can clip `x`: an absolutely placed box
  // is clipped only from its containing block outwards (offsetParent), a
  // fixed one by nothing here.
  const up = (x) => { const p = getComputedStyle(x).position; if (p === 'fixed') return null; if (p === 'absolute') return x.offsetParent; return x.parentElement; };
  const rootEls = [];
  for (const s of roots) for (const el of document.querySelectorAll(s)) if (vis(el) && !rootEls.some((r) => r.contains(el))) rootEls.push(el);
  const inRoots = (el) => rootEls.some((r) => r.contains(el));
  const all = [];
  for (const r of rootEls) { all.push(r); for (const el of r.querySelectorAll('*')) all.push(el); }
  const visEls = all.filter(vis);
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const onScreen = (r) => r.right > 0 && r.bottom > 0 && r.left < vw && r.top < vh;

  if (!passB) {
    // ---- wrap ----
    const ONE_LINE = '.row, .sidebar-head, .dialog-head, .dock, .dock-group, [role=toolbar], [role=tablist], .seg, .tabs-line, '
      + '[class*="split"], [class*="toolbar"], [class*="-head"], [class*="-bar"], [class*="actions"], .btn-group, .dialog-foot, .card-foot';
    for (const el of visEls) {
      if (!el.matches(ONE_LINE)) continue;
      const cs = getComputedStyle(el);
      if (!/flex/.test(cs.display) || /column/.test(cs.flexDirection)) continue;
      const kids = [...el.children].filter((k) => {
        if (!vis(k)) return false;
        const p = getComputedStyle(k).position;
        if (p === 'absolute' || p === 'fixed') return false;
        const r = k.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
      if (kids.length < 2) continue;
      const rs = kids.map((k) => k.getBoundingClientRect());
      const tops = rs.map((r) => Math.round(r.top));
      // A real second line: some child starts at or below another child's bottom.
      const minBottom = Math.min(...rs.map((r) => r.bottom));
      const wrapped = Math.max(...tops) - Math.min(...tops) > 4 && rs.some((r) => r.top >= minBottom - 2);
      if (wrapped) {
        const er = el.getBoundingClientRect();
        if (!onScreen(er)) continue;
        out.push({ defect: 'wrap', sel: desc(el), flexWrap: cs.flexWrap, w: Math.round(er.width), h: Math.round(er.height),
          tops, kids: kids.map((k) => desc(k).split(' ').pop()).slice(0, 10) });
      }
      // A split button or icon segment coming apart sideways.
      if (el.matches('.seg, [class*="split"], .btn-group') && !wrapped) {
        const cg = parseFloat(cs.columnGap) || 0;
        for (let i = 1; i < rs.length; i++) {
          const gap = rs[i].left - rs[i - 1].right;
          if (gap > cg + 3) { out.push({ defect: 'wrap', sub: 'split-gap', sel: desc(el), gap: Math.round(gap) }); break; }
        }
      }
    }
    // ---- clip ----
    const INTER = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=menuitem], [role=checkbox], [role=switch]';
    for (const el of visEls) {
      if (!el.matches(INTER)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      let a = up(el);
      while (a && a !== document.body) {
        const cs = getComputedStyle(a);
        const ox = cs.overflowX, oy = cs.overflowY;
        if (ox !== 'visible' || oy !== 'visible') {
          const ar = a.getBoundingClientRect();
          const box = { l: ar.left + a.clientLeft, t: ar.top + a.clientTop };
          box.r = box.l + a.clientWidth; box.b = box.t + a.clientHeight;
          const scrollX = /auto|scroll/.test(ox), scrollY = /auto|scroll/.test(oy);
          const maxX = a.scrollWidth - a.clientWidth, maxY = a.scrollHeight - a.clientHeight;
          const inter = r.right > box.l && r.left < box.r && r.bottom > box.t && r.top < box.b;
          // Wholly outside a clipping ancestor: scrolled away or hidden, not cut.
          if (!inter && a.clientWidth > 0 && a.clientHeight > 0) break;
          // Cut along a scroller's own axis mid-scroll: that is scrolling, and
          // nothing further out can be judged for this element.
          const midScroll = (scrollY && (r.top < box.t - 0.5 && a.scrollTop > 0 || r.bottom > box.b + 0.5 && a.scrollTop < maxY - 1))
            || (scrollX && (r.left < box.l - 0.5 && a.scrollLeft > 0 || r.right > box.r + 0.5 && a.scrollLeft < maxX - 1));
          if (midScroll) break;
          if (inter && a.clientWidth > 0 && a.clientHeight > 0) {
            const cut = [];
            if (r.left < box.l - 0.5 && (!scrollX || a.scrollLeft <= 0)) cut.push(['left', box.l - r.left]);
            if (r.right > box.r + 0.5 && (!scrollX || a.scrollLeft >= maxX - 1)) cut.push(['right', r.right - box.r]);
            if (r.top < box.t - 0.5 && (!scrollY || a.scrollTop <= 0)) cut.push(['top', box.t - r.top]);
            if (r.bottom > box.b + 0.5 && (!scrollY || a.scrollTop >= maxY - 1)) cut.push(['bottom', r.bottom - box.b]);
            // The focus ring (2px outline, 2px offset) cut by a hidden/clip edge.
            const ring = [];
            if (!cut.length) {
              if (!scrollX && ox !== 'visible') { if (r.left - box.l < 3.5) ring.push(['left', +(r.left - box.l).toFixed(1)]); if (box.r - r.right < 3.5) ring.push(['right', +(box.r - r.right).toFixed(1)]); }
              if (!scrollY && oy !== 'visible') { if (r.top - box.t < 3.5) ring.push(['top', +(r.top - box.t).toFixed(1)]); if (box.b - r.bottom < 3.5) ring.push(['bottom', +(box.b - r.bottom).toFixed(1)]); }
            }
            if (cut.length) out.push({ defect: 'clip', sel: desc(el), by: desc(a), overflow: ox + '/' + oy, rect: R(r), box: [box.l, box.t, box.r, box.b].map(Math.round), cut: cut.map(([s, v]) => s + ':' + v.toFixed(1)) });
            else if (ring.length && !/^(li|tr|td)$/i.test(el.tagName) && el.matches('button, a[href], summary, select, input, [role=button], [role=tab]')) {
              // Measure the ring the element really draws when focused from the keyboard.
              const prevFocus = document.activeElement;
              try { el.focus({ preventScroll: true, focusVisible: true }); } catch (e) {}
              const fcs = getComputedStyle(el);
              const ext = fcs.outlineStyle === 'none' ? 0 : parseFloat(fcs.outlineWidth) + parseFloat(fcs.outlineOffset);
              const focused = document.activeElement === el;
              el.blur(); if (prevFocus && prevFocus.focus) try { prevFocus.focus({ preventScroll: true }); } catch (e) {}
              const cutRing = ring.filter(([, v]) => ext > v + 0.5);
              if (focused && cutRing.length) out.push({ defect: 'clip', sub: 'ring', sel: desc(el), by: desc(a), overflow: ox + '/' + oy, ringPx: +ext.toFixed(1), room: cutRing.map(([s, v]) => s + ':' + v) });
            }
            if (cut.length) break;
          }
        }
        a = up(a);
      }
    }
    // ---- overflow ----
    for (const el of visEls) {
      const cs = getComputedStyle(el);
      if (/^inline$|^contents$|table-cell|table-row/.test(cs.display)) continue;
      if (/auto|scroll/.test(cs.overflowX)) continue;
      if (/^(PRE|CODE|svg|path|IMG|CANVAS|VIDEO|TEXTAREA|INPUT|SELECT|OPTION)$/i.test(el.tagName)) continue;
      if (cs.textOverflow === 'ellipsis') continue;
      if (el.clientWidth <= 2 || el.matches('.visually-hidden, .sr-only, .toolbar-word')) continue;
      const extra = el.scrollWidth - el.clientWidth;
      if (el.clientWidth > 0 && extra > 1) {
        const r = el.getBoundingClientRect();
        if (!onScreen(r)) continue;
        // Skip when only an absolutely placed descendant makes the width.
        let flow = false;
        for (const k of el.children) {
          const p = getComputedStyle(k).position;
          if (p === 'absolute' || p === 'fixed') continue;
          const kr = k.getBoundingClientRect();
          if (kr.right > r.left + el.clientLeft + el.clientWidth + 1 || kr.left < r.left - 1) { flow = true; break; }
        }
        // Text that runs past its own box (no element child does it).
        // (A ::before/::after mark poking out is decoration: only the text's own rects count.)
        if (!flow) {
          const right = r.left + el.clientLeft + el.clientWidth;
          for (const n of el.childNodes) {
            if (n.nodeType !== 3 || !n.textContent.trim()) continue;
            const rg = document.createRange(); rg.selectNodeContents(n);
            if ([...rg.getClientRects()].some((q) => q.right > right + 1 || q.left < r.left - 1)) { flow = true; break; }
          }
        }
        if (flow) out.push({ defect: 'overflow', sel: desc(el), scrollW: el.scrollWidth, clientW: el.clientWidth, ox: cs.overflowX, ws: cs.whiteSpace });
      }
    }
    const de = document.documentElement;
    if (de.scrollWidth > de.clientWidth + 1) out.push({ defect: 'overflow', sel: 'html (page horizontal scrollbar)', scrollW: de.scrollWidth, clientW: de.clientWidth });
    for (const r of rootEls) {
      const sc = r.closest('.tab-page') || r;
      if (sc.scrollWidth > sc.clientWidth + 1 && /auto|scroll/.test(getComputedStyle(sc).overflowX)) out.push({ defect: 'overflow', sub: 'h-scroll', sel: desc(sc), scrollW: sc.scrollWidth, clientW: sc.clientWidth });
    }
    // ---- misalign: help ? ----
    for (const el of visEls) {
      if (!el.matches('[data-help-for], .graph-help-toggle, .help-toggle')) continue;
      const p = el.parentElement; if (!p) continue;
      const r = el.getBoundingClientRect();
      if (!onScreen(r)) continue;
      const sibs = [...p.children].filter((k) => k !== el && vis(k) && !['absolute', 'fixed'].includes(getComputedStyle(k).position) && !k.matches('.help-body'));
      const idx = [...p.children].indexOf(el);
      const prev = sibs.filter((k) => [...p.children].indexOf(k) < idx).pop();
      const next = sibs.find((k) => [...p.children].indexOf(k) > idx);
      const pr = p.getBoundingClientRect(), pcs = getComputedStyle(p);
      const contentRight = pr.right - parseFloat(pcs.paddingRight) - parseFloat(pcs.borderRightWidth);
      const cy = (r.top + r.bottom) / 2;
      let gapPrev = null, dyPrev = null;
      if (prev) { const q = prev.getBoundingClientRect(); gapPrev = Math.round(r.left - q.right); dyPrev = Math.round(cy - (q.top + q.bottom) / 2); }
      const gapEnd = Math.round(contentRight - r.right);
      const besideLabel = prev && gapPrev >= -1 && gapPrev <= 16 && Math.abs(dyPrev) <= 4;
      const atEnd = gapEnd <= 16 && (!next || next.getBoundingClientRect().top > r.bottom);
      const groupWithNext = next && Math.abs(next.getBoundingClientRect().left - r.right) <= 16 && Math.abs(((next.getBoundingClientRect().top + next.getBoundingClientRect().bottom) / 2) - cy) <= 4;
      if (!besideLabel && !atEnd && !groupWithNext) out.push({ defect: 'misalign', sel: desc(el), rect: R(r), gapPrev, dyPrev, gapEnd, prev: prev ? desc(prev).split(' ').pop() : null, next: next ? desc(next).split(' ').pop() : null });
      else if (besideLabel && Math.abs(dyPrev) > 4) out.push({ defect: 'misalign', sub: 'vertical', sel: desc(el), dyPrev });
    }
  }
  // ---- overlap: a control over text that is not its own ----
  const layerOf = (el) => el.closest('dialog, [popover], .action-menu, .dock-menu-list, .help-body, [role=dialog], [role=menu], [role=listbox], .toast, [class*="tooltip"], [class*="popover"]') || null;
  const texts = [];
  for (const r of rootEls) {
    const tw = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = tw.nextNode())) {
      if (!n.textContent.trim()) continue;
      const pe = n.parentElement; if (!pe || !vis(pe)) continue;
      if (pe.closest('script, style, option, select')) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const tr of rg.getClientRects()) if (tr.width > 1 && tr.height > 1 && onScreen(tr)) texts.push({ n, pe, tr });
    }
  }
  const pointClipped = (el, x, y) => {
    let a = el;
    while (a && a !== document.documentElement) {
      const cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const ar = a.getBoundingClientRect();
        if (x < ar.left || x > ar.right || y < ar.top || y > ar.bottom) return true;
      }
      a = up(a);
    }
    return false;
  };
  // Scrolled-under: one of the pair rides a sticky bar and the other scrolls
  // beneath it, and the scroller is off its start. That is scrolling.
  const stickyOf = (el) => { let s = el; while (s && s !== document.body) { if (getComputedStyle(s).position === 'sticky') return s; s = s.parentElement; } return null; };
  const scrollerOf = (el) => { let s = el && el.parentElement; while (s && s !== document.documentElement) { const o = getComputedStyle(s).overflowY; if (/auto|scroll/.test(o) && s.scrollHeight > s.clientHeight + 1) return s; s = s.parentElement; } return document.scrollingElement; };
  const scrolledUnder = (a, b) => {
    const sa = stickyOf(a), sb = stickyOf(b);
    if (sa === sb) return false;
    const sc = scrollerOf(sa || sb);
    return !!(sc && sc.scrollTop > 0);
  };
  const INTER2 = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=menuitem]';
  const seen = new Set();
  for (const el of visEls) {
    if (!el.matches(INTER2) || el.matches('img, video, canvas')) continue;
    if (passB) {
      // Pass B (scrollers at their end): only controls in a bottom-sticky foot.
      let s = el, foot = false;
      while (s && s !== document.body) { const cs = getComputedStyle(s); if (cs.position === 'sticky' && cs.bottom !== 'auto') { foot = true; break; } s = s.parentElement; }
      if (!foot) continue;
    }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || !onScreen(r)) continue;
    const L = layerOf(el);
    for (const t of texts) {
      if (el.contains(t.pe) || !vis(t.pe)) continue;
      if (layerOf(t.pe) !== L) continue;
      const tr = t.tr;
      const ix = Math.min(r.right, tr.right) - Math.max(r.left, tr.left);
      const iy = Math.min(r.bottom, tr.bottom) - Math.max(r.top, tr.top);
      if (ix <= 1.5 || iy <= 1.5) continue;
      const cx = Math.max(r.left, tr.left) + ix / 2, cy = Math.max(r.top, tr.top) + iy / 2;
      if (pointClipped(t.pe, cx, cy) || pointClipped(el, cx, cy)) continue;
      if (!passB && scrolledUnder(el, t.pe)) continue;
      const hit = document.elementFromPoint(cx, cy);
      // A label's <input> sits under its own text on purpose (custom checkbox);
      // a control that is the text's own label target is skipped too.
      if (t.pe.closest('label') && t.pe.closest('label').contains(el)) continue;
      const key = desc(el) + '|' + desc(t.pe);
      if (seen.has(key)) continue; seen.add(key);
      out.push({ defect: 'overlap', pass: passB ? 'scrolled-end' : 'top', sel: desc(el), text: t.n.textContent.trim().slice(0, 40), textEl: desc(t.pe),
        ctl: R(r), txt: R(tr), inter: [Math.round(ix), Math.round(iy)], hitIsCtl: !!(hit && (el === hit || el.contains(hit))) });
    }
  }
  return { roots: rootEls.length, findings: out };
}

// ---- driver ----------------------------------------------------------------
async function run() {
  const { boot } = require('./lib.js');
  const which = (process.env.VPS || MATRIX.map((_, i) => i).join(',')).split(',').map(Number);
  const outf = process.env.OUTF || '/dev/stdout';
  const theme = process.env.THEME || 'light';
  const emit = (o) => fs.appendFileSync(outf, JSON.stringify(o) + '\n');
  for (const i of which) {
    const m = MATRIX[i];
    const vp = `${m.w}x${m.h}@${m.s}/${theme}`;
    const t0 = Date.now();
    const { browser, page } = await boot({ viewport: { width: m.w, height: m.h }, deviceScaleFactor: m.s, scale: m.s });
    const ev = (fn, arg) => page.evaluate(fn, arg).catch((e) => ({ err: String(e).slice(0, 120) }));
    const settle = (ms = 500) => page.waitForTimeout(ms);
    const closeAll = async () => {
      await page.keyboard.press('Escape').catch(() => {});
      await ev(() => {
        document.querySelectorAll('details[open]').forEach((d) => { if (!d.closest('.entry-edit, #capture-help-hint')) d.open = false; });
        document.querySelectorAll('.action-menu:not(.hidden)').forEach((m) => m.classList.add('hidden'));
        document.querySelectorAll('.help-body:not(.hidden)').forEach((h) => { const b = document.querySelector(`[data-help-for="${h.id}"]`); if (b) b.click(); else h.classList.add('hidden'); });
      });
      await settle(200);
    };
    const doMeasure = async (state, roots) => {
      const a = await ev(measure, { roots, passB: false });
      // Pass B: every vertical scroller in the roots at its end.
      const restore = await ev((roots) => {
        const list = [];
        for (const s of roots) for (const r of document.querySelectorAll(s)) for (const el of [r, ...r.querySelectorAll('*'), r.closest('.tab-page')].filter(Boolean)) {
          const cs = getComputedStyle(el);
          if (/auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 4) { list.push([el, el.scrollTop]); el.scrollTop = el.scrollHeight; }
        }
        window.__wzRestore = list; return list.length;
      }, roots);
      let b = [];
      if (restore > 0) { await settle(250); b = await ev(measure, { roots, passB: true }); await ev(() => { for (const [el, t] of window.__wzRestore || []) el.scrollTop = t; }); }
      const part = (x) => (x && x.findings ? x.findings : x && x.err ? [x] : []);
      const findings = [...part(a), ...part(b)];
      emit({ vp, state, roots: a && a.roots, n: findings.length, findings });
    };
    // Openers inside a scope: menus, help ?s and the first kebab of each kind.
    const openers = (scope) => ev((scope) => {
      const root = document.querySelector(scope); if (!root) return [];
      // Tags from an earlier state would win querySelector: clear them first.
      document.querySelectorAll('[data-wz-opener]').forEach((e) => e.removeAttribute('data-wz-opener'));
      const vis = (el) => el.checkVisibility && el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && el.getClientRects().length;
      const picks = [], kinds = new Set();
      const els = [...root.querySelectorAll('details.dock-menu > summary, details.doc-dock-menu > summary, [data-help-for], .graph-help-toggle, .kebab-opener, button[aria-haspopup="menu"], button[aria-haspopup="true"]')];
      for (const el of els) {
        if (!vis(el)) continue;
        // Excluded by the brief: the Documents sidebar Recent row and the Outline ? (docs session).
        if (el.closest('#doc-sidebar, .doc-outline, #doc-outline')) continue;
        const kind = (el.id ? '#' + el.id : [...el.classList].join('.')) + '|' + (el.closest('[id]') || {}).id;
        const k2 = el.matches('.kebab-opener') ? 'kebab|' + (el.closest('li, tr, .card, [id]') || {}).className : kind;
        if (kinds.has(k2)) continue; kinds.add(k2);
        el.setAttribute('data-wz-opener', String(picks.length));
        picks.push(el.id ? '#' + el.id : (el.getAttribute('aria-label') || el.title || el.textContent.trim()).slice(0, 30));
      }
      return picks.slice(0, 14);
    }, scope);
    const popRoots = ['dialog[open]', '.action-menu:not(.hidden)', 'details[open] > .dock-menu-list', 'details[open] > .doc-dock-menu-list',
      // Some menus are carried out of their <details> to float (Library documents).
      '.dock-menu-list', '.doc-dock-menu-list', '.help-body:not(.hidden)', '[popover]:popover-open', '.toast', '.confirm-overlay'];
    const sweepOpeners = async (state, scope, reset) => {
      const picks = await openers(scope);
      if (!Array.isArray(picks)) return;
      for (let k = 0; k < picks.length; k++) {
        const ok = await ev((k) => { const el = document.querySelector(`[data-wz-opener="${k}"]`); if (!el) return false; el.scrollIntoView({ block: 'nearest' }); el.click(); return true; }, k);
        if (!ok) continue;
        await settle(450);
        await doMeasure(`${state} :: ${picks[k]}`, popRoots);
        await closeAll();
        if (reset) await reset();
      }
    };
    const S = async (name, setup, roots, scope, reset) => {
      //: ONLY=<prefix> runs just the states whose name starts with it.
      if (process.env.ONLY && !name.startsWith(process.env.ONLY)) return;
      try {
        await closeAll();
        await setup();
        await settle(700);
        await doMeasure(name, roots);
        if (scope) await sweepOpeners(name, scope, reset);
      } catch (e) { emit({ vp, state: name, error: String(e).slice(0, 200) }); }
    };
    const tab = (t) => ev((t) => switchTab(t), t);
    const notesSec = (s) => ev((s) => showNotesSection(s), s);
    // ---- Notes ----
    const browse = async (view) => { await tab('notes'); await notesSec('browse'); await settle(300); await ev((v) => document.getElementById('notes-view-' + v)?.click(), view); await settle(500); };
    for (const view of ['rows', 'cards']) {
      await S(`notes/${view}`, () => browse(view), ['#tab-notes'], '#tab-notes', null);
      // Hover the first row or card so its hover actions are measured visible.
      await S(`notes/${view}/hover`, async () => {
        await browse(view);
        const li = page.locator('#entry-list > li').first();
        if (await li.count()) await li.hover({ timeout: 3000 }).catch(() => {});
      }, ['#entry-list']);
      await S(`notes/${view}/editor`, async () => {
        await browse(view);
        await ev(async () => { const id = (window.allEntries || [])[0]?.id; if (id != null) await openNoteEditor(id); });
        await settle(1800);
      }, ['#tab-notes'], '#entry-list', null);
      await ev(() => typeof closeNoteForm === 'function' && closeNoteForm());
    }
    await S('notes/rail', async () => { await browse('rows'); await ev(() => { document.getElementById('notes-rail-toggle')?.click(); }); await settle(400);
      await ev(() => document.querySelector('#entry-list > li')?.click()); await settle(800); }, ['#tab-notes'], '#notes-rail');
    await ev(() => { const r = document.getElementById('notes-rail'); if (r && !r.hidden) document.getElementById('notes-rail-toggle')?.click(); });
    for (const sec of ['capture', 'writing-room', 'ask', 'questions']) {
      await S(`notes/${sec}`, async () => { await tab('notes'); await notesSec(sec); }, ['#tab-notes'], '#tab-notes');
    }
    await S('notes/capture/typed', async () => { await tab('notes'); await notesSec('capture');
      await page.fill('#entry-content', 'A typed note with a #tag and a [[link]] so the capture form shows its suggestions and counters.').catch(() => {});
      await page.fill('#entry-tags', 'work, ideas').catch(() => {}); }, ['#tab-notes']);
    await ev(() => { const c = document.getElementById('entry-content'); if (c) { c.value = ''; c.dispatchEvent(new Event('input')); } const t = document.getElementById('entry-tags'); if (t) t.value = ''; });
    await S('quick-note', async () => { await ev(() => openQuickNote()); await settle(400); await page.fill('#quick-note-text', 'Buy milk tomorrow at 9').catch(() => {}); }, ['#quick-note'], '#quick-note',
      async () => { await ev(() => { if (!document.getElementById('quick-note').open) openQuickNote(); }); await settle(300); });
    await ev(() => { const d = document.getElementById('quick-note'); if (d?.open) d.close(); });
    // ---- Library ----
    const libTabs = await ev(() => { switchTab('library'); return [...document.querySelectorAll('#library-subtabs [data-target]')].map((b) => b.dataset.target).filter((t, i, l) => l.indexOf(t) === i); });
    for (const target of Array.isArray(libTabs) ? libTabs : []) {
      const open = async () => {
        await tab('library');
        await page.waitForFunction((t) => { const b = document.querySelector(`#library-subtabs [data-target="${t}"]`); if (!b) return true; if (!b.classList.contains('active')) { b.click(); return false; } return true; }, target, { timeout: 8000, polling: 150 }).catch(() => {});
        await settle(target === 'library-view-whiteboard' || target === 'library-view-documents' ? 1500 : 600);
      };
      await S(`library/${target.replace('library-view-', '')}`, open, ['#tab-library', '#tab-documents'], '#' + target, open);
    }
    // The media sub-tab's two views.
    for (const mv of ['preview', 'type']) {
      await S(`library/media/${mv}`, async () => { await tab('library'); await ev(() => document.querySelector('#library-subtabs [data-target="library-view-media"]')?.click()); await settle(600);
        await ev((mv) => document.getElementById('library-media-view-' + mv)?.click(), mv); }, ['#tab-library']);
    }
    // ---- Timeline ----
    for (const v of ['feed', 'table', 'calendar']) {
      const open = async () => { await tab('timeline'); await settle(600); await ev((v) => document.getElementById('timeline-view-' + v)?.click(), v); await settle(700); };
      await S(`timeline/${v}`, open, ['#tab-timeline'], '#tab-timeline', open);
    }
    // The calendar's own month / week / day segment, whatever it offers.
    const calSegs = await ev(() => [...document.querySelectorAll('#timeline-calendar .seg button, #timeline-calendar [role=tablist] button')].map((b, i) => { b.setAttribute('data-wz-cal', i); return b.title || b.textContent.trim(); }));
    for (let i = 0; i < (Array.isArray(calSegs) ? calSegs.length : 0); i++) {
      await S(`timeline/calendar/${calSegs[i].slice(0, 20)}`, async () => { await tab('timeline'); await ev(() => document.getElementById('timeline-view-calendar')?.click()); await settle(500);
        await ev((i) => document.querySelector(`[data-wz-cal="${i}"]`)?.click(), i); }, ['#tab-timeline']);
    }
    await S('timeline/month-pop', async () => { await tab('timeline'); await ev(() => document.getElementById('timeline-view-feed')?.click()); await settle(400); await ev(() => document.getElementById('timeline-month-btn')?.click()); }, ['#tab-timeline']);
    await S('timeline/select', async () => { await tab('timeline'); await settle(300);
      await ev(() => { const b = document.getElementById('timeline-select-btn'); if (b) b.click(); });
      await settle(400); await ev(() => { const c = document.querySelector('#timeline-feed input[type=checkbox], #timeline-feed .tl-select'); c?.click(); }); }, ['#tab-timeline']);
    await ev(() => document.getElementById('timeline-batch-done')?.click());
    // ---- Reminders ----
    for (const v of ['list', 'calendar']) {
      const open = async () => { await tab('reminders'); await settle(500); await ev((v) => document.querySelector(`#reminder-view-toggle [data-view="${v}"]`)?.click(), v); await settle(600); };
      await S(`reminders/${v}`, open, ['#tab-reminders', '#tab-timeline'], v === 'list' ? '#tab-reminders' : null, open);
    }
    // A reminder row's hover strip (+1h, Tomorrow, Edit, ⋯) over its time.
    await S('reminders/hover', async () => { await tab('reminders'); await ev(() => document.querySelector('#reminder-view-toggle [data-view="list"]')?.click()); await settle(500);
      const li = page.locator('#reminder-groups li').first(); if (await li.count()) await li.hover({ timeout: 3000 }).catch(() => {}); }, ['#tab-reminders']);
    await S('reminders/typed', async () => { await tab('reminders'); await ev(() => document.querySelector('#reminder-view-toggle [data-view="list"]')?.click());
      await page.fill('#reminder-text', 'Ring the garage about the car service and the tyres').catch(() => {}); }, ['#tab-reminders']);
    await page.fill('#reminder-text', '').catch(() => {});
    // ---- Popups the click-through above can miss (a summary press that an
    // outside-click closer undoes in the same tick): opened directly here.
    const direct = [
      ['notes', 'capture', '#capture-help'], ['notes', 'writing-room', '#draft-help'], ['notes', 'ask', '[data-help-for][aria-label="About AI answers"], #ask [data-help-for]'],
      ['library', 'library-view-documents', '#library-filter-menu'], ['library', 'library-view-documents', '#library-more-menu'],
      ['library', 'library-view-contents', '#contents-help'], ['library', 'library-view-skills', '#skills-help'],
      ['library', 'library-view-whiteboard', '#library-view-whiteboard details.dock-more'],
    ];
    for (const [t, sub, sel] of direct) {
      await S(`popups/${sub}/${sel.split(',')[0]}`, async () => {
        await tab(t);
        if (t === 'notes') await notesSec(sub);
        else await page.waitForFunction((x) => { const b = document.querySelector(`#library-subtabs [data-target="${x}"]`); if (!b) return true; if (!b.classList.contains('active')) { b.click(); return false; } return true; }, sub, { timeout: 8000, polling: 150 }).catch(() => {});
        await settle(900);
        const how = await ev((sel) => {
          const el = document.querySelector(sel); if (!el) return 'missing';
          if (el.tagName === 'DETAILS') { el.open = true; return 'details'; }
          el.click(); return 'click';
        }, sel);
        if (how === 'missing') emit({ vp, state: `popups/${sub}/${sel}`, error: 'opener missing' });
      }, popRoots);
      await closeAll();
    }
    emit({ vp, state: '__done', secs: Math.round((Date.now() - t0) / 1000) });
    await browser.close();
  }
}

// ---- summary: de-duplicate by defect + selector across viewports -------------
function sum(files) {
  const groups = new Map(), errors = [], done = [];
  for (const f of files) for (const line of fs.readFileSync(f, 'utf8').split('\n').filter(Boolean)) {
    const o = JSON.parse(line);
    if (o.error) { errors.push(`${o.vp} ${o.state}: ${o.error}`); continue; }
    if (o.state === '__done') { done.push(`${o.vp} ${o.secs}s`); continue; }
    for (const fd of o.findings || []) {
      if (fd.err) { errors.push(`${o.vp} ${o.state}: ${fd.err}`); continue; }
      const key = [fd.defect, fd.sub || '', fd.sel, fd.textEl || '', fd.by || ''].join(' | ');
      if (!groups.has(key)) groups.set(key, { key, vps: new Set(), states: new Set(), sample: fd });
      const g = groups.get(key); g.vps.add(o.vp); g.states.add(o.state);
    }
  }
  console.log('done:', done.join('; '));
  if (errors.length) console.log('errors:', [...new Set(errors)].slice(0, 30).join('\n  '));
  const rows = [...groups.values()].sort((a, b) => a.key.localeCompare(b.key));
  for (const g of rows) {
    const s = { ...g.sample }; delete s.defect; delete s.sel;
    console.log(`\n${g.key}\n  vps(${g.vps.size}): ${[...g.vps].join(' ')}\n  states: ${[...g.states].slice(0, 6).join(' ; ')}\n  ${JSON.stringify(s).slice(0, 400)}`);
  }
}

if (process.argv[2] === 'sum') sum(process.argv.slice(3));
else run().catch((e) => { console.error(e); process.exit(1); });
