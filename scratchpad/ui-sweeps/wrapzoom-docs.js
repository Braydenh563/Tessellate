// Wrap, clip, overlap, overflow and misalign sweep for Documents (the editor
// dock and formatting toolbar, the sidebar, the status line, find and
// replace, export), the code editor and its run panel, the diagram builder,
// and whiteboards (top bar, menus, shelves, side panels), across the zoom
// and resolution matrix the owner asked about (2026-11-11: "make sure the
// wrapping and ui issues arent an issue anywhere else from zoom or
// resolution"). OS zoom is simulated as the CSS viewport it yields, with
// deviceScaleFactor set to the zoom factor. Measures only: no screenshot.
//
//   BASE=http://127.0.0.1:8813 node wrapzoom-docs.js seed > seed.json
//   BASE=... SEEDF=seed.json THEME=dark VPS=0,1 OUTF=out.jsonl node wrapzoom-docs.js
//   node wrapzoom-docs.js sum out*.jsonl
//
// VPS picks rows of MATRIX by index (default all); ONLY=<prefix> picks states.
// The measure() below is wrapzoom-notes.js's, with an exclusion list: the
// areas the brief leaves to other sessions are not measured at all (EXCL).
const fs = require('fs');
const MATRIX = [
  { w: 1280, h: 720, s: 1 }, { w: 1366, h: 768, s: 1 }, { w: 1440, h: 900, s: 1 },
  { w: 1920, h: 1080, s: 1 }, { w: 2560, h: 1440, s: 1 }, { w: 1536, h: 864, s: 1.25 },
  { w: 1280, h: 720, s: 1.5 }, { w: 960, h: 540, s: 2 }, { w: 1280, h: 720, s: 2 },
  { w: 768, h: 1024, s: 1 },
];
// Owned elsewhere (the brief): the sidebar's Recent row and the Outline tab's
// "This document" ?, the sidebar foot (918bd50ae), the diagram builder's list
// foot, its "Turn it sideways" offer and its full-screen expand.
const EXCL = ['#doc-sidebar-list > .sidebar-head', '#doc-sidebar-outline > .sidebar-head', '#doc-list-help', '#doc-outline-help',
  '.doc-storage-toggle', '.dgm-foot', '.dgm-sideways', '[aria-label*="full screen" i]', '[title*="full screen" i]'];

// ---- in-page measurement ---------------------------------------------------
function measure({ roots, passB, excl }) {
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
  const EX = (excl || []).join(', ');
  const skip = (el) => !!(EX && el.closest && el.closest(EX));
  const visEls = all.filter((el) => vis(el) && !skip(el));
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
      const pe = n.parentElement; if (!pe || !vis(pe) || skip(pe)) continue;
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

// ---- seed ------------------------------------------------------------------
const LONG_MD = `# Quarterly planning notes for the north office

A paragraph long enough to wrap at every width, so the page, the status line and the find bar have text under them. The office move, the budget review and the hiring plan are the three threads this quarter.

## Budget review

- Travel is over by a fifth, and the training line is under.
- [ ] Ask finance for the revised forecast
- [x] Book the review meeting

| Line | Planned | Spent |
| --- | ---: | ---: |
| Travel | 4,000 | 4,850 |
| Training | 6,000 | 2,100 |

## Hiring plan

1. Two engineers by the end of March.
2. One designer, part time.

> A quote, so the rendered view has a block quote to lay out.

### Office move

\`\`\`js
console.log("inline code block");
\`\`\`

${'More text so the document scrolls past one screen and the sticky foot has something to cover. '.repeat(40)}

## Appendix

${'The appendix repeats a sentence to make the page long. '.repeat(30)}
`;
const CODE_JS = `// A small script with output, a table and an error, for the run panel.
function total(rows) { return rows.reduce((s, r) => s + r.spent, 0); }
const rows = [{ line: "Travel", spent: 4850 }, { line: "Training", spent: 2100 }, { line: "Equipment and furniture for the new north office", spent: 12950 }];
console.log("Total spent this quarter:", total(rows));
console.table(rows);
console.warn("Travel is over its planned budget by more than twenty per cent this quarter, ask finance");
for (let i = 0; i < 12; i++) console.log("line", i, "of the output so the panel scrolls");
throw new Error("A deliberate error at the end, so the error row is drawn");
`;
const CODE_PY = `# A Python file, for the code editor's dock and gutter.
def total(rows):
    return sum(r["spent"] for r in rows)

rows = [{"line": "Travel", "spent": 4850}, {"line": "Training", "spent": 2100}]
print("Total:", total(rows))
`;
const MMD = `flowchart TD
  A[Start the quarterly review] --> B{Budget over plan?}
  B -->|Yes| C[Ask finance for the revised forecast]
  B -->|No| D[Carry on]
  C --> E[Book the review meeting]
  D --> E
  subgraph Hiring
    F[Two engineers] --> G[One designer]
  end
  E --> F
`;
async function seed() {
  const { boot } = require('./lib.js');
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const ids = await page.evaluate(async ({ LONG_MD, CODE_JS, CODE_PY, MMD }) => {
    const post = (path, body) => apiJson(path, { method: 'POST', body: JSON.stringify(body) });
    for (let i = 0; i < 6; i++) await post('/entries', { content: `Sweep note ${i}\n\nSomething about the office move and the budget review, with a #planning tag.`, category: 'Work' }).catch(() => {});
    const now = Date.now();
    for (let i = 0; i < 4; i++) await post('/reminders', { text: `Sweep reminder ${i}: ring the garage`, due_at: new Date(now + (i + 1) * 3600e3).toISOString() }).catch(() => {});
    const doc = async (title, content, file_type) => (await post('/documents', file_type ? { title, content, file_type } : { title, content })).id;
    const out = {};
    out.md = await doc('Quarterly planning notes for the north office', LONG_MD);
    out.md2 = await doc('Meeting notes', '# Meeting notes\n\nShort.\n\n## Actions\n\n- one\n- two\n');
    out.js = await doc('budget-report.js', CODE_JS, 'js');
    out.py = await doc('budget_report.py', CODE_PY, 'py');
    out.mmd = await doc('Quarterly review flow', MMD, 'mmd');
    out.mmdEmpty = await doc('Empty diagram', '', 'mmd');
    for (let i = 0; i < 4; i++) await doc(`Sweep document ${i}`, `# Sweep document ${i}\n\nText.`);
    // A whiteboard with text, and a map with topics.
    const board = await post('/whiteboard/boards', { name: 'Office move board' });
    out.board = board.id;
    const words = ['Pack the second floor', 'Book the vans', 'New desks', 'Network', 'Keys and passes', 'Move day'];
    for (let i = 0; i < words.length; i++) await post('/whiteboard/objects', { kind: 'text', data: { content: words[i] }, board_id: board.id, x: 120 + (i % 3) * 220, y: 120 + Math.floor(i / 3) * 140, z: 1, width: 180, height: 80 }).catch((e) => { out.objErr = String(e); });
    const map = await post('/whiteboard/boards', { name: 'Hiring plan map', type: 'map', layout: 'tree-right' });
    out.map = map.id;
    for (let i = 0; i < 4; i++) await post('/whiteboard/objects', { board_id: map.id, kind: 'topic', x: 300, y: 100 + i * 80, width: 170, height: 52, data: { content: `Topic ${i}` } }).catch(() => {});
    return out;
  }, { LONG_MD, CODE_JS, CODE_PY, MMD });
  console.log(JSON.stringify(ids));
  await browser.close();
}

// ---- driver ----------------------------------------------------------------
async function run() {
  const { boot } = require('./lib.js');
  const ids = JSON.parse(fs.readFileSync(process.env.SEEDF, 'utf8'));
  const which = (process.env.VPS || MATRIX.map((_, i) => i).join(',')).split(',').map(Number);
  const outf = process.env.OUTF || '/dev/stdout';
  const theme = process.env.THEME || 'light';
  const emit = (o) => fs.appendFileSync(outf, JSON.stringify(o) + '\n');
  for (const i of which) {
    const m = MATRIX[i];
    const vp = `${m.w}x${m.h}@${m.s}/${theme}`;
    const t0 = Date.now();
    const { browser, page } = await boot({ viewport: { width: m.w, height: m.h }, deviceScaleFactor: m.s, scale: m.s });
    const ev = (fn, arg) => page.evaluate(fn, arg).catch((e) => ({ err: String(e).slice(0, 160) }));
    const settle = (ms = 500) => page.waitForTimeout(ms);
    const closeAll = async () => {
      await page.keyboard.press('Escape').catch(() => {});
      await ev(() => {
        document.querySelectorAll('details[open]').forEach((d) => { d.open = false; });
        document.querySelectorAll('.action-menu:not(.hidden)').forEach((m) => m.classList.add('hidden'));
        document.querySelectorAll('.wb-board-menu:not(.hidden)').forEach((m) => m.classList.add('hidden'));
        document.querySelectorAll('[data-wb-menu-toggle][aria-expanded="true"]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
        document.querySelectorAll('.help-body:not(.hidden)').forEach((h) => { const b = document.querySelector(`[data-help-for="${h.id}"]`); if (b) b.click(); else h.classList.add('hidden'); });
        document.querySelectorAll('dialog[open]').forEach((d) => d.close());
      });
      await settle(200);
    };
    const doMeasure = async (state, roots) => {
      const tm = Date.now();
      const a = await ev(measure, { roots, passB: false, excl: EXCL });
      // Pass B: every vertical scroller in the roots at its end (a sticky foot over text).
      const restore = await ev((roots) => {
        const list = [];
        for (const s of roots) for (const r of document.querySelectorAll(s)) for (const el of [r, ...r.querySelectorAll('*'), r.closest('.tab-page')].filter(Boolean)) {
          const cs = getComputedStyle(el);
          if (/auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 4) { list.push([el, el.scrollTop]); el.scrollTop = el.scrollHeight; }
        }
        window.__wzRestore = list; return list.length;
      }, roots);
      let b = [];
      if (restore > 0) { await settle(250); b = await ev(measure, { roots, passB: true, excl: EXCL }); await ev(() => { for (const [el, t] of window.__wzRestore || []) el.scrollTop = t; }); }
      const part = (x) => (x && x.findings ? x.findings : x && x.err ? [x] : []);
      const findings = [...part(a), ...part(b)];
      emit({ vp, state, roots: a && a.roots, ms: Date.now() - tm, at: Math.round((Date.now() - t0) / 1000), n: findings.length, findings });
    };
    // Openers inside a scope: menus, help ?s, menu toggles, the first kebab of each kind.
    const openers = (scope) => ev(({ scope, EXCL }) => {
      const root = document.querySelector(scope); if (!root) return [];
      document.querySelectorAll('[data-wz-opener]').forEach((e) => e.removeAttribute('data-wz-opener'));
      const vis = (el) => el.checkVisibility && el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && el.getClientRects().length;
      const picks = [], kinds = new Set();
      const els = [...root.querySelectorAll('details > summary, [data-help-for], .graph-help-toggle, .kebab-opener, button[aria-haspopup="menu"], button[aria-haspopup="true"], button[aria-haspopup="listbox"], [data-wb-menu-toggle]')];
      for (const el of els) {
        if (!vis(el) || el.closest(EXCL.join(', '))) continue;
        // One per kind: a per-row menu ("Shape: Box", "Menu for Hiring") counts once.
        const lab = (el.getAttribute('aria-label') || '').replace(/[:\s].*$/, '');
        const kind = (el.id ? '#' + el.id : [...el.classList].join('.') + (el.getAttribute('aria-controls') || '') + lab) + '|' + (el.closest('[id]') || {}).id;
        const k2 = el.matches('.kebab-opener') ? 'kebab|' + (el.closest('li, tr, .card, [id]') || {}).className : kind;
        if (kinds.has(k2)) continue; kinds.add(k2);
        el.setAttribute('data-wz-opener', String(picks.length));
        picks.push(el.id ? '#' + el.id : (el.getAttribute('aria-label') || el.title || el.textContent.trim()).replace(/\s+/g, ' ').slice(0, 30));
      }
      return picks.slice(0, 24);
    }, { scope, EXCL });
    const popRoots = ['dialog[open]', '.action-menu:not(.hidden)', 'details[open] > .dock-menu-list', 'details[open] > .doc-dock-menu-list', 'details[open]',
      '.help-body:not(.hidden)', '[popover]:popover-open', '.toast', '.confirm-overlay', '.wb-board-menu:not(.hidden)', '.select-menu:not(.hidden)', '[role=menu]:not(.hidden)', '[role=listbox]:not(.hidden)'];
    const sweepOpeners = async (state, scope, reset) => {
      const picks = await openers(scope);
      if (!Array.isArray(picks)) { emit({ vp, state, error: 'openers: ' + JSON.stringify(picks).slice(0, 150) }); return; }
      for (let k = 0; k < picks.length; k++) {
        if (process.env.ONLY_OPENER && !picks[k].includes(process.env.ONLY_OPENER)) continue;
        const ok = await ev((k) => { const el = document.querySelector(`[data-wz-opener="${k}"]`); if (!el) return false; el.scrollIntoView({ block: 'nearest' }); el.click(); return true; }, k);
        if (!ok) continue;
        await settle(450);
        await doMeasure(`${state} :: ${picks[k]}`, popRoots);
        // A submenu inside what just opened: the first one, measured open.
        const sub = await ev(() => {
          const t = [...document.querySelectorAll('.wb-board-menu:not(.hidden) .menu-item.has-submenu, .action-menu:not(.hidden) .menu-item.has-submenu, details[open] .has-submenu')].find((x) => x.checkVisibility());
          if (!t) return null; t.click(); return (t.textContent || '').trim().slice(0, 24);
        });
        if (typeof sub === 'string') { await settle(350); await doMeasure(`${state} :: ${picks[k]} > ${sub}`, popRoots); }
        await closeAll();
        if (reset) await reset();
      }
    };
    const S = async (name, setup, roots, scope, reset) => {
      if (process.env.ONLY && !name.startsWith(process.env.ONLY)) return;
      try {
        await closeAll();
        await setup();
        await settle(700);
        await doMeasure(name, roots);
        if (scope) await sweepOpeners(name, scope, reset);
      } catch (e) { emit({ vp, state: name, error: String(e).slice(0, 200) }); }
    };
    const DOC = ['#tab-documents'];
    const openDoc = async (id, view) => {
      await ev(async ({ id, view }) => {
        if (document.querySelector('.doc-focus')) document.getElementById('doc-focus-exit')?.click();
        switchTab('documents');
        if ((typeof currentDoc !== 'undefined' && currentDoc && currentDoc.id) !== id) await openDocument(id);
        if (view) setDocView(view);
      }, { id, view });
      await page.waitForSelector('#doc-editor .cm-content, .dgm-pane', { state: 'visible', timeout: 15000 }).catch(() => {});
      await settle(700);
    };
    const toolbar = (shown, mode) => ev(({ shown, mode }) => { if (mode) setDocToolbarMode(mode); setDocToolbarCollapsed(!shown); }, { shown, mode });

    // ---- Documents: the markdown document ----
    const md = async (view = 'live') => { await openDoc(ids.md, view); await toolbar(true, 'wrap'); };
    await S('docs/md/live', () => md('live'), DOC, '#tab-documents', () => md('live'));
    for (const v of ['rendered', 'source', 'split', 'plain']) await S(`docs/md/${v}`, () => md(v), DOC);
    await S('docs/md/toolbar-row', async () => { await openDoc(ids.md, 'live'); await toolbar(true, 'row'); }, DOC, '#doc-toolbar');
    await S('docs/md/toolbar-hidden', async () => { await openDoc(ids.md, 'live'); await toolbar(false, 'wrap'); }, DOC);
    await S('docs/md/scrolled-mid', async () => { await md('live'); await ev(() => { const s = document.querySelector('#doc-editor .cm-scroller'); if (s) s.scrollTop = s.scrollHeight / 2; }); }, DOC);
    await S('docs/md/find', async () => { await md('live'); await ev(() => document.getElementById('doc-find-toggle')?.click()); await settle(400);
      const f = page.locator('#doc-editor .cm-search input[name=search], .cm-panel.cm-search input').first(); if (await f.count()) await f.fill('budget').catch(() => {}); }, DOC, '#doc-editor .cm-panels');
    await S('docs/md/replace-everywhere', async () => { await md('live'); await ev(() => openDocReplace()); await settle(500);
      await page.fill('#doc-replace-find', 'budget').catch(() => {}); await page.fill('#doc-replace-with', 'spending plan for the north office').catch(() => {}); await settle(900); }, ['#doc-replace-dialog'], '#doc-replace-dialog');
    for (const sec of ['list', 'outline']) await S(`docs/sidebar/${sec}`, async () => { await md('live'); await ev((s) => showDocSidebarSection(s), sec); }, ['#doc-sidebar'], '#doc-sidebar');
    await S('docs/md/ai-panel', async () => { await md('live'); await ev(() => document.getElementById('doc-ai')?.click()); await settle(600); }, [...DOC, '#doc-ai-panel'], '#doc-ai-panel');
    await S('docs/md/prose-panel', async () => { await md('live'); await settle(1200); await ev(() => document.getElementById('doc-prose')?.click()); await settle(600); }, [...DOC, '#doc-prose-panel'], '#doc-prose-panel');
    await ev(() => { const p = document.getElementById('doc-prose-panel'); if (p && p.checkVisibility()) document.getElementById('doc-prose')?.click(); });
    await S('docs/md/focus', async () => { await md('live'); await ev(() => document.getElementById('doc-focus-toggle')?.click()); await settle(500); await page.mouse.move(m.w / 2, 30); }, DOC, '#doc-focus-bar');
    await S('docs/md/focus-tools', async () => { await md('live'); if (!(await ev(() => !!document.querySelector('.doc-focus')))) await ev(() => document.getElementById('doc-focus-toggle')?.click()); await settle(400);
      await ev(() => { const b = document.getElementById('doc-focus-tools'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }); await page.mouse.move(m.w / 2, 30); }, DOC);
    await S('docs/md/focus-sidebar', async () => { await md('live'); if (!(await ev(() => !!document.querySelector('.doc-focus')))) await ev(() => document.getElementById('doc-focus-toggle')?.click()); await settle(400);
      await ev(() => { const b = document.getElementById('doc-focus-sidebar'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }); await page.mouse.move(m.w / 2, 30); }, DOC);
    await ev(() => { if (document.querySelector('.doc-focus')) document.getElementById('doc-focus-exit')?.click(); });
    await settle(300);
    // Dialogs reached from the dock menu and the status line.
    const dlg = [['history', () => document.getElementById('doc-history').click()], ['stats', () => docRunTextTool('stats')], ['word-goal', () => promptDocWordGoal()],
      ['template', () => document.getElementById('doc-new-template')?.click()], ['ai-history', () => openDocAiHistory()]];
    for (const [name, fn] of dlg) {
      await S(`docs/dialog/${name}`, async () => { await md('live'); await page.evaluate(fn).catch(() => {}); await settle(1500); }, ['dialog[open]', '.confirm-overlay'], 'dialog[open]');
    }
    // Two documents open: the tab row.
    await S('docs/tabs', async () => { await openDoc(ids.md2, 'live'); await openDoc(ids.md, 'live'); await openDoc(ids.js); await openDoc(ids.mmd); await openDoc(ids.md, 'live'); }, DOC);

    // ---- Code editor and run panel ----
    await S('code/py', async () => { await openDoc(ids.py, 'source'); }, DOC, '.doc-dock', async () => { await openDoc(ids.py, 'source'); });
    for (const side of ['assist', 'snippets']) {
      await S(`code/side/${side}`, async () => { await openDoc(ids.py, 'source'); await ev((s) => { const b = document.querySelector(`[aria-controls="doc-code-side"][data-side="${s}"]`); if (b && b.getAttribute('aria-expanded') !== 'true') b.click(); }, side); await settle(600); }, DOC, '#doc-code-side');
    }
    await ev(() => document.getElementById('doc-code-side-close')?.click());
    await S('code/js/run', async () => { await openDoc(ids.js, 'source'); await ev(() => docRunCode()); await page.waitForSelector('.cm-run-panel .cm-run-row', { timeout: 15000 }).catch(() => {}); await settle(1200); }, DOC, '.cm-run-panel');
    await S('code/js/split', async () => { await openDoc(ids.js, 'split'); }, DOC);
    await ev(() => typeof docRunClose === 'function' && docRunClose());

    // ---- Diagram builder ----
    await S('diagram/rendered', async () => { await openDoc(ids.mmd, 'rendered'); await page.waitForSelector('.dgm-pane, .dgm-picture', { timeout: 8000 }).catch(() => {}); }, DOC, '#tab-documents .doc-dock', async () => { await openDoc(ids.mmd, 'rendered'); });
    const segs = await ev(() => [...document.querySelectorAll('#doc-diagram-seg button')].map((b, i) => { b.setAttribute('data-wz-seg', i); return (b.getAttribute('aria-label') || b.title || b.textContent).trim().slice(0, 20); }));
    for (let k = 0; k < (Array.isArray(segs) ? segs.length : 0); k++) {
      await S(`diagram/seg/${segs[k]}`, async () => { await openDoc(ids.mmd, 'rendered'); await ev((k) => document.querySelector(`#doc-diagram-seg [data-wz-seg="${k}"]`)?.click(), k); await settle(900); }, DOC, '.dgm-pane',
        async () => { await openDoc(ids.mmd, 'rendered'); await ev((k) => document.querySelector(`#doc-diagram-seg [data-wz-seg="${k}"]`)?.click(), k); await settle(600); });
    }
    await S('diagram/split', async () => { await openDoc(ids.mmd, 'split'); }, DOC);
    await S('diagram/select-block', async () => { await openDoc(ids.mmd, 'rendered'); await ev(() => document.querySelector('#doc-diagram-seg [data-wz-seg="0"]')?.click()); await settle(600);
      await ev(() => document.querySelector('.dgm-block .dgm-card, .dgm-block')?.click()); }, DOC);
    await S('diagram/suggest-menu', async () => { await openDoc(ids.mmd, 'rendered'); await ev(() => document.querySelector('.dgm-suggest')?.click()); await settle(500); }, popRoots);
    await S('diagram/empty', async () => { await openDoc(ids.mmdEmpty, 'rendered'); await settle(600); }, DOC);
    await S('diagram/template-dialog', async () => { await openDoc(ids.mmdEmpty, 'rendered'); await ev(() => document.querySelector('.dgm-empty button')?.click()); await settle(800); }, ['dialog[open]', '.dgm-template-dialog']);

    // ---- Whiteboards ----
    const { openBoardsTab, waitForBoardOpen } = require('./lib.js');
    const LIB = ['#tab-library'];
    const landing = async () => { await ev(() => { if (document.getElementById('wb-topbar')?.offsetParent) document.getElementById('wb-back-to-boards')?.click(); }); await openBoardsTab(page).catch(() => {}); await settle(900); };
    await S('wb/landing', landing, LIB, '#wb-boards-landing', landing);
    const board = async (id, n = 0) => {
      await openBoardsTab(page).catch(() => {});
      await ev((id) => openWhiteboardBoard(id), id);
      await waitForBoardOpen(page, n, 15000).catch(() => {});
      await settle(600);
    };
    const wbB = async () => { await board(ids.board, 3); };
    await S('wb/board', wbB, LIB, '#wb-topbar', wbB);
    await S('wb/board/shelf', async () => { await wbB(); await ev(() => { const o = document.getElementById('wb-tools-opener'); if (o && o.checkVisibility()) o.click(); }); await settle(500); }, LIB, '#wb-tools-panel', async () => { await wbB(); });
    await S('wb/board/selected', async () => { await wbB(); const o = page.locator('#whiteboard-container .wb-object').first(); if (await o.count()) await o.click({ timeout: 3000 }).catch(() => {}); await settle(500); }, LIB, '#wb-context',
      async () => { await wbB(); const o = page.locator('#whiteboard-container .wb-object').first(); if (await o.count()) await o.click({ timeout: 3000 }).catch(() => {}); await settle(300); });
    await S('wb/board/multi', async () => { await wbB(); await page.mouse.click(m.w / 2, m.h / 2).catch(() => {}); await page.keyboard.press('Control+a').catch(() => {}); await settle(500); }, LIB);
    for (const tab of ['library', 'notes', 'layers', 'pages']) {
      await S(`wb/board/side/${tab}`, async () => { await wbB(); await ev((t) => wbOpenSidebar(t, { focus: false }), tab); await settle(700); }, [...LIB, '#wb-sidebar'], '#wb-sidebar',
        async () => { await wbB(); await ev((t) => wbOpenSidebar(t, { focus: false }), tab); await settle(400); });
    }
    await ev(() => document.getElementById('wb-sidebar-close')?.click());
    for (const tab of ['style', 'text', 'arrange', 'data']) {
      await S(`wb/board/format/${tab}`, async () => { await wbB(); const o = page.locator('#whiteboard-container .wb-object').first(); if (await o.count()) await o.click({ timeout: 3000 }).catch(() => {});
        await ev((t) => wbFormatOpen(t, { focus: false }), tab); await settle(700); }, [...LIB, '#wb-format'], tab === 'style' ? '#wb-format' : null);
    }
    await ev(() => document.getElementById('wb-format-close')?.click());
    await S('wb/board/search', async () => { await wbB(); await ev(() => wbOpenBoardSearch()); await settle(400); await page.fill('#wb-search-input', 'desks').catch(() => {}); }, LIB);
    await ev(() => document.getElementById('wb-search-close')?.click());
    await S('wb/board/navigator', async () => { await wbB(); await ev(() => wbToggleNavigator()); await settle(500); }, LIB);
    await ev(() => document.getElementById('wb-navigator-close')?.click());
    await S('wb/board/help', async () => { await wbB(); await ev(() => document.getElementById('wb-help-btn')?.click()); await settle(600); }, ['#wb-help-overlay', ...LIB], '#wb-help-overlay');
    await ev(() => document.getElementById('wb-help-close')?.click());
    const mapB = async () => { await board(ids.map, 1); };
    await S('wb/map', mapB, LIB, '#wb-topbar', mapB);
    await S('wb/map/selected', async () => { await mapB(); const o = page.locator('#whiteboard-container .wb-object').nth(1); if (await o.count()) await o.click({ timeout: 3000 }).catch(() => {}); await settle(600); }, LIB, '#wb-map-strip',
      async () => { await mapB(); const o = page.locator('#whiteboard-container .wb-object').nth(1); if (await o.count()) await o.click({ timeout: 3000 }).catch(() => {}); await settle(300); });
    for (const tab of ['map', 'outline']) {
      await S(`wb/map/side/${tab}`, async () => { await mapB(); await ev((t) => wbOpenSidebar(t, { focus: false }), tab); await settle(700); }, [...LIB, '#wb-sidebar'], '#wb-sidebar');
    }
    await ev(() => document.getElementById('wb-sidebar-close')?.click());
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
      if (!groups.has(key)) groups.set(key, { key, vps: new Set(), states: new Set(), samples: [] });
      const g = groups.get(key); g.vps.add(o.vp); g.states.add(o.state); if (g.samples.length < 3) g.samples.push(o.vp + ' ' + JSON.stringify({ ...fd, defect: undefined, sel: undefined }));
    }
  }
  console.log('done:', done.join('; '));
  if (errors.length) console.log('errors:', [...new Set(errors)].slice(0, 40).join('\n  '));
  const rows = [...groups.values()].sort((a, b) => a.key.localeCompare(b.key));
  for (const g of rows) {
    console.log(`\n${g.key}\n  vps(${g.vps.size}): ${[...g.vps].join(' ')}\n  states(${g.states.size}): ${[...g.states].slice(0, 5).join(' ; ')}`);
    for (const s of g.samples) console.log('  ' + s.slice(0, 420));
  }
}

if (process.argv[2] === 'sum') sum(process.argv.slice(3));
else if (process.argv[2] === 'seed') seed().catch((e) => { console.error(e); process.exit(1); });
else run().catch((e) => { console.error(e); process.exit(1); });
