// Measures the four shell fixes of the 2026-11-11 zoom sweep, by number:
// the Edit layout widget heads (one line, inside the card), the Quick access
// edit tile's label against its menu button, and the focus rings of the
// Widgets dialog's first Reset and of the movable panels' resize grips.
//   BASE=http://127.0.0.1:8821 VPS=1366x768@1,768x1024@1 node dashedit-zoom.js
const { boot } = require('./lib.js');
const VPS = (process.env.VPS || '1366x768@1,768x1024@1').split(',');
(async () => {
  for (const spec of VPS) {
    const [wh, sc] = spec.split('@'); const [w, h] = wh.split('x').map(Number);
    const { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: Number(sc || 1) });
    await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden')).catch(() => {});
    const out = await page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      switchTab('dashboard'); await wait(400);
      applyDashDensity('full'); dashEditMode = true; await renderDashboard(); await wait(1200);
      const heads = [...document.querySelectorAll('#dash-grid > section.dash-widget > .row.space-between')].filter((r) => r.offsetParent);
      let wrapped = 0, over = 0, maxH = 0;
      for (const r of heads) {
        const t = r.querySelector('h2').getBoundingClientRect(), a = r.querySelector('.dash-edit-actions').getBoundingClientRect();
        if (Math.abs(t.top + t.height / 2 - (a.top + a.height / 2)) > 4) wrapped++;
        if (r.scrollWidth > r.clientWidth + 1) over++;
        maxH = Math.max(maxH, r.getBoundingClientRect().height);
      }
      dashEditMode = false; await renderDashboard(); await wait(800);
      quickEditing = true; renderQuickLinks(); await wait(600);
      let qOverlap = 0;
      for (const tile of document.querySelectorAll('.quick-edit-tile')) {
        const b = tile.querySelector('.kebab-opener')?.getBoundingClientRect(); if (!b) continue;
        for (const n of tile.querySelectorAll('.quick-link *')) {
          if (!n.childNodes.length || ![...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) continue;
          const r = document.createRange(); r.selectNodeContents(n);
          // the painted glyphs: a label that ellipsises is clipped by its own box
          const clip = getComputedStyle(n).overflowX !== 'visible' ? n.getBoundingClientRect() : null;
          for (const y of r.getClientRects()) { const x = clip ? { left: y.left, right: Math.min(y.right, clip.right), top: y.top, bottom: y.bottom } : y; qOverlap = Math.max(qOverlap, Math.max(0, Math.min(x.right, b.right) - Math.max(x.left, b.left)) * (Math.min(x.bottom, b.bottom) > Math.max(x.top, b.top) ? 1 : 0)); }
        }
      }
      quickEditing = false; renderQuickLinks();
      document.getElementById('dash-widgets-open').click(); await wait(900);
      const list = document.getElementById('dash-widgets-list');
      const reset = list.querySelector('.row.space-between > button.ghost.small');
      reset.focus({ focusVisible: true });
      const rs = getComputedStyle(reset), ring = parseFloat(rs.outlineWidth) + parseFloat(rs.outlineOffset);
      const rr = reset.getBoundingClientRect(), lr = list.getBoundingClientRect();
      const resetCut = Math.max(0, (lr.top + list.clientTop) - (rr.top - ring));
      const grip = document.querySelector('#dash-widgets-dialog > button.panel-grip');
      const gripRing = grip ? (() => { grip.focus({ focusVisible: true }); const s = getComputedStyle(grip); return parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset); })() : null;
      document.getElementById('dash-widgets-dialog').close();
      document.getElementById('notif-btn').click(); await wait(900);
      const ng = document.querySelector('#notif-panel > button.panel-grip');
      const notifRing = ng ? (() => { ng.focus({ focusVisible: true }); const s = getComputedStyle(ng); return parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset); })() : null;
      return { heads: heads.length, wrapped, over, maxH: Math.round(maxH), qOverlap: Math.round(qOverlap * 10) / 10, resetCut, gripRing, notifRing };
    });
    console.log(spec, JSON.stringify(out));
    await browser.close();
  }
})();
