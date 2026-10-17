// prefers-reduced-motion: with the system setting on, which CSS animations and
// transitions are still running on each surface? Reads document.getAnimations():
// anything running whose effect is infinite, or finite and longer than 100 ms,
// is listed with its target and name. Surfaces: every tab, the PR's calendar
// (and its add sheet), the new chat page and each Settings pane.
//
//   BASE=http://127.0.0.1:8791 [W=1358] node reducedmotion.js
const { boot } = require('./lib.js');
const W = Number(process.env.W || 1358);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 }, reducedMotion: 'reduce' });
  page.setDefaultTimeout(6000);
  await page.waitForTimeout(2500);
  let total = 0;
  const probe = async (label) => {
    await page.waitForTimeout(700);
    const r = await page.evaluate(() => {
      const out = [];
      for (const a of document.getAnimations()) {
        if (a.playState !== 'running') continue;
        const t = a.effect?.getTiming?.() || {};
        const dur = typeof t.duration === 'number' ? t.duration : 0;
        const inf = t.iterations === Infinity;
        if (!inf && dur <= 100) continue;
        const el = a.effect?.target;
        const cs = el ? getComputedStyle(el) : null;
        if (el && (cs.visibility === 'hidden' || !el.getClientRects().length)) continue;
        out.push(`${a.animationName || a.transitionProperty || 'anim'} ${inf ? 'infinite' : dur + 'ms'} on ${el ? (el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className).split(/\s+/).slice(0, 2).join('.')) : '?'}`);
      }
      return [...new Set(out)].slice(0, 8);
    });
    total += r.length;
    for (const x of r) console.log(`FIND ${label} ${x}`);
    console.log(`== ${label}: ${r.length}`);
  };
  for (const t of ['dashboard', 'notes', 'chat', 'library', 'reminders', 'documents', 'graph']) {
    await page.evaluate((x) => switchTab(x), t); await probe(t);
  }
  await page.evaluate(() => { localStorage.setItem('timeline-view', 'calendar'); switchTab('timeline'); });
  await page.waitForTimeout(1500);
  await probe('timeline calendar');
  await page.click('.timeline-cal-add').catch(() => {});
  await probe('calendar add sheet');
  await page.keyboard.press('Escape');
  await page.evaluate(() => { switchTab('chat'); });
  await page.waitForTimeout(500);
  await page.evaluate(() => { try { newChat(); } catch (e) { /* the page is already new */ } });
  await probe('chat new page');
  for (const s of ['models', 'appearance', 'skills', 'packages', 'tasks']) {
    await page.evaluate((x) => openSettingsModal(x), s); await probe(`settings/${s}`);
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  }
  console.log(`TOTAL ${total} at ${W}`);
  await browser.close();
})();
