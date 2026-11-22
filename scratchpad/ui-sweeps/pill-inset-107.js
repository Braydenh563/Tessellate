// L-world-class-107: the gap from a connection pill's edge to its x and its menu button (INBOX 403).
const { boot } = require('./lib.js');
(async () => {
  const out = {};
  for (const [w, h, touch] of [[1440, 900, false], [1093, 614, false], [390, 844, true]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
    await page.evaluate(() => document.querySelector('#tab-btn-notes, [data-tab="notes"]')?.click());
    await page.waitForTimeout(2000);
    out[`${w}x${h}`] = await page.evaluate(() => {
      const ins = (pill, btn) => { const p = pill.getBoundingClientRect(), b = btn.getBoundingClientRect(); const cs = getComputedStyle(btn); const pl = parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth); return { circle: +(b.width - 2 * pl).toFixed(1), clip: cs.backgroundClip, border: cs.borderTopWidth, ring: +(b.top - p.top + pl).toFixed(1) + '/' + (p.bottom - b.bottom + pl).toFixed(1) + '/' + (p.right - b.right + pl).toFixed(1), pill: `${Math.round(p.width)}x${(p.height).toFixed(1)}`, btn: `${b.width.toFixed(1)}x${b.height.toFixed(1)}`, top: +(b.top - p.top).toFixed(1), bottom: +(p.bottom - b.bottom).toFixed(1), end: +(p.right - b.right).toFixed(1) }; };
      const first = (sel, inner) => { for (const p of document.querySelectorAll(sel)) { const b = p.querySelector(inner); if (b && b.getBoundingClientRect().width && p.getBoundingClientRect().top < innerHeight) return ins(p, b); } return null; };
      return { unlink: first('.chip', ':scope > .unlink:last-child'), connMenu: first('#entry-list .link-connection', ':scope > .menu-wrap > button'), conns: document.querySelectorAll('#entry-list .link-connection').length };
    });
    await browser.close();
  }
  console.log(JSON.stringify(out));
})();
// HOVER=1: the drawn circle (content box) on hover, which is what reads as the gap.
