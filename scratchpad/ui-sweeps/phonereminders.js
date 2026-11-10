// UI Phase 11 item 8: the timeline opens as the table on a phone when no
// view is stored (and fits the width), and a reminder row swiped right is
// done, through its own checkbox.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2000);
  const findings = [];
  await page.evaluate(() => localStorage.removeItem('timeline-view'));
  await page.evaluate(() => switchTab('timeline')); await page.waitForTimeout(1500);
  const tl = await page.evaluate(() => ({ mode: timelineViewMode(), active: document.querySelector('#timeline-view-seg .active')?.dataset.timelineView, table: (() => { const t = document.querySelector('#tab-timeline table'); return t ? { shown: t.getBoundingClientRect().height > 0, w: Math.round(t.getBoundingClientRect().width) } : null; })(), scrollW: document.documentElement.scrollWidth }));
  console.log('timeline', JSON.stringify(tl));
  if (tl.mode !== 'table' || tl.active !== 'table') findings.push('the phone timeline is not the table: ' + JSON.stringify(tl));
  if (tl.scrollW > 390) findings.push('the timeline scrolls the page sideways: ' + tl.scrollW);
  // A reminder, swiped right.
  const rid = await page.evaluate(async () => { const r = await apiJson('/reminders', { method: 'POST', body: JSON.stringify({ text: 'Swipe me done', due_at: new Date(Date.now() + 3600e3).toISOString() }) }); return r.id; });
  await page.evaluate(() => switchTab('reminders')); await page.waitForTimeout(1500);
  const sel = `#reminder-groups li[data-id="${rid}"]`;
  const row = await page.evaluate((s) => { const li = document.querySelector(s); if (!li) return null; const b = li.getBoundingClientRect(); return { x: Math.round(b.left), w: Math.round(b.width), h: Math.round(b.height), right: li.dataset.swipeRight, left: li.dataset.swipeLeft || null, checkbox: !!li.querySelector('input[type="checkbox"]') }; }, sel);
  console.log('row', JSON.stringify(row));
  if (!row) { findings.push('the reminder row is not on screen'); }
  else {
    if (row.right !== 'Done' || row.left) findings.push('the reminder row does not say Done to the right and nothing to the left: ' + JSON.stringify(row));
    const cdp = await page.context().newCDPSession(page);
    // The list sits under the magic row, the presets and the due row; the
    // row has to be on screen for a finger to land on it.
    const r = await page.evaluate((s) => { const li = document.querySelector(s); li.scrollIntoView({ block: 'center' }); const b = li.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + Math.min(20, b.height / 2) }; }, sel);
    await page.waitForTimeout(300);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: r.x, y: r.y }] });
    for (let i = 1; i <= 8; i++) { await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: r.x + (110 * i) / 8, y: r.y }] }); await page.waitForTimeout(16); }
    const mid = await page.evaluate((s) => { const li = document.querySelector(s); return { armed: li.classList.contains('swipe-armed'), before: getComputedStyle(li, '::before').width, word: getComputedStyle(li, '::before').content }; }, sel);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await page.waitForTimeout(1500);
    const done = await page.evaluate(async (id) => { const all = await apiJson('/reminders'); const r = (all.items || all).find((x) => x.id === id); return r && r.done; }, rid);
    console.log('swipe', JSON.stringify({ mid, done }));
    if (!mid.armed || mid.before === '0px') findings.push('the reminder swipe did not arm: ' + JSON.stringify(mid));
    if (!/Done/.test(mid.word)) findings.push('the underlay does not say Done: ' + mid.word);
    if (!done) findings.push('the swipe did not mark the reminder done');
    // Left does nothing.
    await page.evaluate(() => switchTab('reminders')); await page.waitForTimeout(800);
    const still = await page.evaluate((s) => !!document.querySelector(s), sel);
    if (still) {
      const r2 = await page.evaluate((s) => { const li = document.querySelector(s); li.scrollIntoView({ block: 'center' }); const b = li.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + Math.min(20, b.height / 2) }; }, sel);
      await page.waitForTimeout(300);
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: r2.x, y: r2.y }] });
      for (let i = 1; i <= 6; i++) { await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: r2.x - (110 * i) / 6, y: r2.y }] }); await page.waitForTimeout(16); }
      const left = await page.evaluate((s) => document.querySelector(s).style.getPropertyValue('--swipe-x'), sel);
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      if (left && left !== '0px') findings.push('a reminder moved on a left swipe: ' + left);
    }
  }
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
