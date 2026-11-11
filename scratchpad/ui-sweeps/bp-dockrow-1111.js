// One-row check for the Documents dock (a markdown document, a .py and a .js file)
// and the Writing room's draft actions, across widths and zooms (the
// breakpoints fix, 2026-11-11: the wrapzoom rules moved onto Phase 9's set).
// Prints, per viewport, each row's width, height, rows of controls (distinct
// tops), the Python line's width and whether its text is cut, and which
// worded buttons show their word (W) or only their icon (i). Measures only.
//
//   BASE=http://127.0.0.1:8793 SEEDF=seed.json node bp-dockrow-1111.js
//   (seed.json from `node wrapzoom-docs.js seed`; M=1280x720@1,... picks viewports)
const fs = require('fs');
const { boot } = require('./lib.js');
const MATRIX = (process.env.M || '1280x720@1,1440x900@1,1536x864@1,1920x1080@1,2560x1440@1,1280x720@1.5,960x540@2,768x1024@1,360x780@1,853x480@1.5,640x360@2,1100x800@1,1200x800@1')
  .split(',').map((s) => { const [wh, sc] = s.split('@'); const [w, h] = wh.split('x').map(Number); return { w, h, s: Number(sc) }; });
const ids = JSON.parse(fs.readFileSync(process.env.SEEDF, 'utf8'));
function rows(sel) {
  const root = document.querySelector(sel); if (!root) return null;
  const vis = (el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && el.getClientRects().length;
  const btns = [...root.querySelectorAll('button, input:not([type=hidden]), summary, select')]
    .filter((b) => vis(b) && !b.closest('[popover], .action-menu, .hidden') && !(b.closest('details[open]') && !b.matches('summary')));
  const tops = [];
  for (const b of btns) { const t = b.getBoundingClientRect().top; if (!tops.some((x) => Math.abs(x - t) < 6)) tops.push(t); }
  const r = root.getBoundingClientRect();
  const words = btns.filter((b) => b.querySelector('.toolbar-word, .doc-ai-label, :scope > span')).map((b) => {
    const w = b.querySelector('.toolbar-word, .doc-ai-label, :scope > span');
    return b.id + ':' + (w && w.getBoundingClientRect().width > 4 && getComputedStyle(w).display !== 'none' ? 'W' : 'i');
  });
  const why = document.getElementById('doc-code-run-why');
  return { w: Math.round(r.width), h: Math.round(r.height), rows: tops.length, n: btns.length,
    why: why && vis(why) ? Math.round(why.getBoundingClientRect().width) + (why.scrollWidth > why.clientWidth + 1 ? ' cut' : ' whole') : '-',
    title: Math.round(document.querySelector('.doc-title-input')?.getBoundingClientRect().width || 0), words: words.join(' ') };
}
(async () => {
  for (const m of MATRIX) {
    const { browser, page } = await boot({ viewport: { width: m.w, height: m.h }, deviceScaleFactor: m.s, scale: m.s });
    const ev = (fn, a) => page.evaluate(fn, a).catch((e) => ({ err: String(e).slice(0, 120) }));
    const out = { vp: `${m.w}x${m.h}@${m.s}` };
    for (const [k, id] of [['md', ids.md], ['py', ids.py], ['js', ids.js]]) {
      await ev(async (id) => { switchTab('documents'); await openDocument(id); }, id);
      await page.waitForTimeout(1500);
      out[k] = await ev(rows, '#tab-documents .doc-dock');
    }
    await ev(() => { switchTab('notes'); showNotesSection('writing-room'); });
    await page.waitForTimeout(900);
    out.draft = await ev((f) => {
      // eslint-disable-next-line no-new-func
      const r = new Function('return ' + f)()('.draft-actions-row');
      const c = document.querySelector('.draft-actions-row')?.closest('.draft-column');
      if (r && c) r.col = Math.round(c.getBoundingClientRect().width);
      return r;
    }, rows.toString());
    console.log(JSON.stringify(out));
    await browser.close();
  }
})();
