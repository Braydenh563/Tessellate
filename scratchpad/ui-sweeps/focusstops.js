// WCAG 2.4.7 and 2.4.11 on the PR's surfaces: Tab through the timeline calendar
// (month, week, day), its add sheet, the chat's new page and Settings, and for
// every stop read (a) whether it draws a focus indicator that differs from its
// unfocused state (outline or box-shadow), and (b) whether the focused control
// is covered by something else at its centre and corners (focus obscured).
//
//   BASE=http://127.0.0.1:8791 [THEME=dark] [W=1358] [STOPS=40] node focusstops.js
const { boot } = require('./lib.js');
const W = Number(process.env.W || 1358);
const STOPS = Number(process.env.STOPS || 40);
const PHONE = W < 600;

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: PHONE ? 844 : 900 }, ...(PHONE ? { hasTouch: true, isMobile: true } : {}) });
  page.setDefaultTimeout(6000);
  await page.waitForTimeout(2500);
  let total = 0;
  const walk = async (label, start) => {
    try { await start(); } catch (e) { console.log(`?? ${label}: could not start (${String(e.message).split('\n')[0].slice(0, 80)})`); return; }
    await page.waitForTimeout(600);
    const seen = new Set(); const bad = [];
    for (let i = 0; i < STOPS; i++) {
      await page.keyboard.press('Tab');
      const r = await page.evaluate(() => {
        const a = document.activeElement;
        if (!a || a === document.body) return null;
        const cs = getComputedStyle(a);
        const has = (c) => (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0 ? 'outline' : '') + (c.boxShadow !== 'none' ? ' shadow' : '');
        const ring = has(cs) || (a.parentElement && a.parentElement.matches(':focus-within') ? has(getComputedStyle(a.parentElement)) : '');
        const rect = a.getBoundingClientRect();
        const pts = [[0.5, 0.5], [0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9]].map(([fx, fy]) => [rect.left + rect.width * fx, rect.top + rect.height * fy]);
        let covered = 0; let by = '';
        for (const [x, y] of pts) {
          if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
          const t = document.elementFromPoint(x, y);
          if (t && t !== a && !a.contains(t) && !t.contains(a)) { covered++; by = (t.id || t.className || t.tagName).toString().slice(0, 40); }
        }
        const offscreen = rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth;
        return { key: (a.id || a.className || a.tagName).toString().slice(0, 50) + '|' + (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 20), ring, covered, by, offscreen, w: Math.round(rect.width), h: Math.round(rect.height) };
      });
      if (!r) continue;
      if (seen.has(r.key)) continue;
      seen.add(r.key);
      if (!r.ring) bad.push(`no ring: ${r.key} ${r.w}x${r.h}`);
      if (r.covered >= 3) bad.push(`obscured by ${r.by}: ${r.key}`);
      if (r.offscreen) bad.push(`offscreen: ${r.key}`);
    }
    total += bad.length;
    for (const b of bad) console.log(`FIND ${label} ${b}`);
    console.log(`== ${label}: ${seen.size} stops, ${bad.length} findings`);
  };

  await page.evaluate(() => { localStorage.setItem('timeline-view', 'calendar'); });
  for (const span of ['month', 'week', 'day']) {
    await walk(`calendar ${span}`, async () => {
      await page.evaluate((sp) => { localStorage.setItem('timeline-cal-span', sp); switchTab('timeline'); if (typeof timelineCal !== 'undefined') { timelineCal.url = ''; timelineCal.span = sp; } paintTimeline(); }, span);
      await page.waitForTimeout(1500);
      await page.focus('#tab-timeline .dock button, #tab-timeline .dock input').catch(() => {});
    });
  }
  await walk('calendar add sheet', async () => {
    await page.evaluate(() => { localStorage.setItem('timeline-cal-span', 'month'); switchTab('timeline'); timelineCal.url = ''; timelineCal.span = 'month'; paintTimeline(); });
    await page.waitForTimeout(1500);
    await page.focus('.timeline-cal-monthcell[tabindex="0"]'); await page.keyboard.press('n');
  });
  await page.keyboard.press('Escape');
  await walk('chat new page', async () => { await page.evaluate(() => switchTab('chat')); await page.waitForTimeout(1200); await page.focus('#chat-input'); });
  await walk('dashboard', async () => { await page.evaluate(() => switchTab('dashboard')); await page.waitForTimeout(1200); await page.evaluate(() => document.body.focus()); });
  await walk('notes', async () => { await page.evaluate(() => switchTab('notes')); await page.waitForTimeout(1200); await page.evaluate(() => document.body.focus()); });
  for (const s of ['models', 'appearance', 'skills', 'packages']) {
    await walk(`settings/${s}`, async () => { await page.evaluate((x) => openSettingsModal(x), s); await page.waitForTimeout(1200); });
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  }
  console.log(`TOTAL ${total} at ${W} ${process.env.THEME || 'light'}`);
  await browser.close();
})();
