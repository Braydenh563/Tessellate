// INBOX 1319: the Statistics overlay's fit under the header, and whether its
// charts answer the pointer.  BASE=http://127.0.0.1:8781 node stats1319.js
const { boot } = require('./lib.js');
(async () => {
  const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
  const { page, browser } = await boot({ viewport: { width: W, height: H }, theme: process.env.THEME });
  await page.waitForTimeout(2500);
  await page.evaluate(() => ensureModule('statistics').then(() => openStatistics()));
  await page.waitForTimeout(2000);
  const out = await page.evaluate(() => {
    const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom), Math.round(b.left), Math.round(b.right)]; };
    const card = document.querySelector('.stats-card');
    const hdr = [...document.querySelectorAll('header, .topbar, #topbar, .app-header')].map((e) => e.getBoundingClientRect()).filter((b) => b.height > 0);
    const z = (s) => { const e = document.querySelector(s); return e ? getComputedStyle(e).zIndex : null; };
    const chart = document.querySelector('.stats-chart svg');
    return {
      card: r('.stats-card'), overlay: r('.stats-overlay'), head: r('.stats-card .dialog-head'),
      headerBottoms: hdr.map((b) => Math.round(b.bottom)),
      overlayZ: z('.stats-overlay'), cardScroll: card && [card.scrollHeight, card.clientHeight, getComputedStyle(card).overflowY],
      bodyScroll: [document.querySelector('.stats-body').scrollHeight, document.querySelector('.stats-body').clientHeight],
      chartPointer: chart && getComputedStyle(chart).pointerEvents,
      chartTitles: chart ? chart.querySelectorAll('title').length : -1,
      chartCircles: chart ? chart.querySelectorAll('circle').length : -1,
      topAt: (() => { const e = document.elementFromPoint(innerWidth / 2, (card.getBoundingClientRect().top + 10)); return e && (e.className && String(e.className.baseVal ?? e.className)).slice(0, 60) + ' ' + e.tagName; })(),
    };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
