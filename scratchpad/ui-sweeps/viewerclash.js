// The owner (2026-09-27), of the enlarged companion view: "make sure the text
// doesnt clash with the avatar in the expanded companion panel". Opens the
// large view (`openNameMarkViewer`) for Atlas in each look and for a few
// generated faces, and measures the drawing's real box (every drawn
// descendant of the figure, as it is drawn, sampled over 1.5s so a mood's
// loop is caught at its lowest) against the name and the caption below it.
// Reports per face: art bottom, name top, the gap (negative = overlap), the
// art's top against the card's (clipped), and the caption text.
// Env: VW, VH, SEEDS (comma list; "Atlas:masculine" picks a look).
// Exits 1 on any overlap or clipped art.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const SEEDS = (process.env.SEEDS || 'Atlas:masculine,Atlas:feminine,You,Brayden,Mira,Quill').split(',');

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  const rows = [];
  for (const entry of SEEDS) {
    const [seed, look] = entry.split(':');
    if (look) {
      await page.evaluate((l) => {
        const sel = document.getElementById('atlas-look');
        if (sel) { sel.value = l; sel.dispatchEvent(new Event('change', { bubbles: true })); }
        try { localStorage.setItem('atlas-look', l); } catch (e) {}
      }, look);
      await page.waitForTimeout(300);
    }
    await page.evaluate((s) => openNameMarkViewer(s), seed);
    await page.waitForTimeout(700);
    const row = await page.evaluate(async () => {
      const card = document.querySelector('.nm-viewer-card');
      const fig = card.querySelector('.nm-viewer-figure');
      const name = card.querySelector('.nm-viewer-name').getBoundingClientRect();
      const reading = card.querySelector('.nm-viewer-reading');
      const cbox = card.getBoundingClientRect();
      // Alive while open: its first small act (a glance) is running by now.
      await new Promise((r) => setTimeout(r, 400));
      const idleActs = fig.getAnimations({ subtree: true }).filter((a) => !(a instanceof CSSAnimation) && !(a instanceof CSSTransition)).length;
      const hintBox = card.querySelector('.nm-viewer-hint')?.getBoundingClientRect();
      let top = Infinity; let bottom = -Infinity; let left = Infinity; let right = -Infinity;
      const sample = () => {
        for (const el of fig.querySelectorAll('*')) {
          const cs = getComputedStyle(el);
          if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) < 0.05) continue;
          if (el.tagName === 'g' || el.tagName === 'svg' || el.tagName === 'defs' || el.closest('defs, clipPath, mask, filter, linearGradient, radialGradient')) continue;
          const r = el.getBoundingClientRect();
          if (!r.width || !r.height) continue;
          // An element with children only positions them (a box around
          // parts): its own box is not ink.
          if (!(el instanceof SVGElement) && el.children.length && !cs.backgroundImage.includes('url')) continue;
          top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom);
          left = Math.min(left, r.left); right = Math.max(right, r.right);
        }
      };
      for (let i = 0; i < 15; i += 1) { sample(); await new Promise((r) => setTimeout(r, 100)); }
      const f = fig.getBoundingClientRect();
      return {
        artTop: Math.round(top), artBottom: Math.round(bottom), figTop: Math.round(f.top), figBottom: Math.round(f.bottom),
        nameTop: Math.round(name.top), gap: Math.round(name.top - bottom), cardTop: Math.round(cbox.top), clippedTop: Math.round(Math.max(0, cbox.top - top)),
        artW: Math.round(right - left), cardH: Math.round(cbox.height), caption: reading.textContent, idleActs, hintBelowCaption: hintBox ? Math.round(hintBox.top - reading.getBoundingClientRect().bottom) : null,
      };
    });
    rows.push({ face: entry, ...row });
    await page.evaluate(() => document.querySelector('.nm-viewer')?.remove());
  }
  console.log(JSON.stringify({ vw: VW, vh: VH, rows }, null, 0));
  await browser.close();
  // One line the lane runners count (they read FAIL, not the exit code alone).
  console.log((rows.some((r) => r.gap < 4 || r.clippedTop > 0)) ? 'FAIL viewerclash: a measure above is out of bounds' : 'PASS viewerclash');
  process.exit(rows.some((r) => r.gap < 4 || r.clippedTop > 0) ? 1 : 0);
})();
