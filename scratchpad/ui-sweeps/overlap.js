// Trust contract rule 7 (WORLD_CLASS_PLAN 28.1): nothing clashes or overflows.
// At 320, 390, 820, 1024 and 1440, for each surface, three counts:
//   overflow  elements whose content is wider than the box (scrollWidth over
//             clientWidth) where the box does not scroll and does not mean to
//             truncate (overflow is visible or hidden, and no ellipsis)
//   docks     pairs of sibling controls in a .dock or toolbar whose rectangles
//             intersect (absolute and fixed children are overlays, skipped)
//   clip      text nodes whose range rectangle leaves the parent's rectangle
//             by more than a pixel while the parent is on screen
// plus the worst ten selectors across all widths. Bar: 0 per width.
//
//   BASE=http://127.0.0.1:8791 [THEME=dark] [WIDTHS=320,390] [ONLY="settings"] node overlap.js
const L = require('./trustlib.js');
const WIDTHS = (process.env.WIDTHS || '320,390,820,1024,1440').split(',').map(Number);
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);

async function measure(page, rootSel) {
  return page.evaluate((rootSel) => {
    const vw = window.innerWidth;
    // `contentVisibilityAuto`: a card a window off screen is not drawn, and
    // measuring it lays it out unfitted (the note card's details line folds
    // its tags when it is drawn; scrolled into view, 40 of 40 fit at 390).
    const vis = (e) => { if (!e.checkVisibility({ contentVisibilityAuto: true })) return false; const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const name = (e) => {
      let s = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '');
      const cls = [...e.classList].filter((c) => !/^(hidden|active|open|selected)$/.test(c)).slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      if (!e.id) { const up = e.parentElement && e.parentElement.closest('[id]'); if (up) s = '#' + up.id + ' ' + s; }
      return s;
    };
    const roots = rootSel.split(',').map((s) => document.querySelector(s.trim())).filter((r) => r && vis(r));
    const out = { overflow: [], docks: [], clip: [], page: document.documentElement.scrollWidth > vw + 1 ? document.documentElement.scrollWidth - vw : 0, root: roots.length > 0, bars: 0, pairs: 0 };
    // Visually hidden text (the clip-path: inset(50%) or 1px-box pattern a
    // dock uses for a word folded behind its icon) is meant to be clipped:
    // counting it reported the Notes dock's folded words as overflow.
    const srOnly = (e) => {
      for (let x = e; x; x = x.parentElement) {
        const s = getComputedStyle(x);
        if (s.clipPath === 'inset(50%)' || (s.position === 'absolute' && x.clientWidth <= 1 && s.overflow === 'hidden')) return true;
      }
      return false;
    };
    for (const root of roots) {
      // overflow
      for (const e of root.querySelectorAll('*')) {
        if (!vis(e) || e.closest('svg, canvas, [aria-hidden="true"], .visually-hidden, .sr-only') || srOnly(e)) continue;
        const s = getComputedStyle(e);
        if (s.position === 'fixed') continue;
        const d = e.scrollWidth - e.clientWidth;
        if (d <= 1 || e.clientWidth === 0) continue;
        const ox = s.overflowX;
        if (ox === 'auto' || ox === 'scroll') continue;
        if (s.textOverflow === 'ellipsis') continue;
        if (e.matches('input, textarea, select, .cm-content, .cm-scroller')) continue;
        // Overhang that is drawn on purpose is not a clash (L606, the 4 px rows):
        // a badge pinned with position: absolute past its button's corner
        // (#notes-tidy), and a scroll row that bleeds 4 px each side by a
        // negative margin so its focus rings are not cut (#timeline .timeline-body,
        // .library-controls). Skip the box only when every child that passes its
        // edge is one of those; a plain in-flow child past the edge still counts.
        const eb = e.getBoundingClientRect();
        const over = [...e.children].filter((k) => { const b = k.getBoundingClientRect(); return b.width > 0 && (b.right > eb.right + 1 || b.left < eb.left - 1); });
        if (over.length && over.every((k) => { const ks = getComputedStyle(k); return ks.position === 'absolute' || parseFloat(ks.marginLeft) < 0 || parseFloat(ks.marginRight) < 0; })) continue;
        out.overflow.push({ sel: name(e), px: d, how: ox });
      }
      // docks and toolbars
      const bars = root.querySelectorAll('.dock, [role="toolbar"], [class*="toolbar"], [class*="topbar"], .tabs-line, [class*="-dock"], .library-subtabs, .notes-subtabs');
      for (const bar of bars) {
        if (!vis(bar)) continue;
        out.bars++;
        const kids = [...bar.children].filter((k) => vis(k) && !['absolute', 'fixed'].includes(getComputedStyle(k).position) && !k.matches('.dock-native-hidden, .visually-hidden, .hidden'));
        out.pairs += kids.length * (kids.length - 1) / 2;
        for (let i = 0; i < kids.length; i++) {
          const a = kids[i].getBoundingClientRect();
          for (let j = i + 1; j < kids.length; j++) {
            const b = kids[j].getBoundingClientRect();
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (w > 2 && h > 2) out.docks.push({ sel: name(bar) + ' > ' + name(kids[i]).split(' ').pop() + ' x ' + name(kids[j]).split(' ').pop(), px: Math.round(Math.min(w, h)) });
          }
        }
      }
      // clipped text
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const range = document.createRange();
      let n;
      while ((n = walker.nextNode())) {
        if (!n.nodeValue.trim()) continue;
        const p = n.parentElement;
        if (!p || p.closest('script, style, svg, canvas, option, [aria-hidden="true"], .visually-hidden, .sr-only, .hidden') || !vis(p) || srOnly(p)) continue;
        const pr = p.getBoundingClientRect();
        if (pr.right < 0 || pr.left > vw) continue;
        range.selectNodeContents(n);
        const rr = range.getBoundingClientRect();
        if (rr.width === 0) continue;
        const over = Math.max(rr.right - pr.right, pr.left - rr.left);
        if (over > 1.5 && getComputedStyle(p).textOverflow !== 'ellipsis') out.clip.push({ sel: name(p), px: Math.round(over) });
      }
    }
    return out;
  }, rootSel);
}

(async () => {
  const worst = new Map();
  const table = [];
  for (const width of WIDTHS) {
    const height = width < 600 ? 844 : 900;
    const { browser, page } = await L.boot({ viewport: { width, height }, hasTouch: width < 820, isMobile: width < 600 });
    await L.ensureSeed(page);
    const totals = { overflow: 0, docks: 0, clip: 0, page: 0 };
    console.log(`\n== ${width} x ${height} (${process.env.THEME || 'light'})`);
    for (const surface of L.SURFACES) {
      if (ONLY.length && !ONLY.includes(surface.name)) continue;
      await L.closeOverlays(page);
      await surface.open(page).catch(() => {});
      await page.waitForTimeout(500);
      const r = await measure(page, surface.root);
      for (const kind of ['overflow', 'docks', 'clip']) {
        for (const f of r[kind]) {
          const key = kind + ' ' + f.sel;
          const w = worst.get(key) || { kind, sel: f.sel, n: 0, px: 0, widths: new Set(), surfaces: new Set() };
          w.n++; w.px = Math.max(w.px, f.px); w.widths.add(width); w.surfaces.add(surface.name);
          worst.set(key, w);
        }
        totals[kind] += r[kind].length;
      }
      totals.page += r.page ? 1 : 0;
      const row = { width, surface: surface.name, overflow: r.overflow.length, docks: r.docks.length, clip: r.clip.length, page: r.page, root: r.root };
      table.push(row);
      console.log(`  ${surface.name.padEnd(12)} overflow ${String(row.overflow).padStart(3)}  docks ${String(row.docks).padStart(3)}  clip ${String(row.clip).padStart(3)}  page-scroll ${row.page}px  (bars ${r.bars}, pairs ${r.pairs})${r.root ? '' : '  (surface not on screen)'}`);
    }
    console.log(`  TOTAL ${width}: overflow ${totals.overflow}, docks ${totals.docks}, clip ${totals.clip}, pages scrolling sideways ${totals.page}`);
    await browser.close();
  }
  const top = [...worst.values()].sort((a, b) => b.n - a.n || b.px - a.px).slice(0, 10);
  console.log('\nWORST TEN SELECTORS (count over all widths and surfaces, largest px, widths)');
  for (const w of top) console.log(`  ${w.kind.padEnd(8)} ${String(w.n).padStart(4)}x  ${String(w.px).padStart(4)}px  [${[...w.widths].join(',')}]  ${w.sel}  (${[...w.surfaces].join(', ')})`);
  console.log(`\nSUMMARY (${process.env.THEME || 'light'}): ` + WIDTHS.map((w) => { const t = table.filter((r) => r.width === w); return `${w}: o${t.reduce((a, r) => a + r.overflow, 0)} d${t.reduce((a, r) => a + r.docks, 0)} c${t.reduce((a, r) => a + r.clip, 0)}`; }).join('  '));
})();
