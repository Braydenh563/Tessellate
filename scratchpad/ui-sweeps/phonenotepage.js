// UI Phase 11 item 2: a note tapped on a phone opens as a page. Full height,
// a back chevron in the head, the list's own card unclamped inside, and
// that card's actions in a thumb bar at the foot; Escape and the chevron go
// back to the row; a control's own tap does not open it; at 1024 a tap
// opens nothing.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2500);
  const long = Array.from({ length: 30 }, (_, i) => `Line ${i + 1} of a long note that should be clamped in the list and whole on the page.`).join('\n');
  await page.evaluate(async (c) => { await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: '# Page probe\n' + c }) }).catch(() => {}); }, long);
  await page.evaluate(() => { switchTab('notes'); showNotesSection('browse'); });
  await page.evaluate(() => loadEntries());
  await page.waitForTimeout(2000);
  const findings = [];
  const id = await page.evaluate(() => (allEntries.find((e) => (e.content || '').startsWith('# Page probe')) || {}).id);
  if (!id) { console.log('FAIL: probe note missing'); process.exit(1); }
  const sel = `#entry-list li[data-id="${id}"]`;
  const before = await page.evaluate((s) => { const li = document.querySelector(s); const c = li.querySelector('.entry-content'); return { clamped: c.classList.contains('entry-clamped'), h: Math.round(c.getBoundingClientRect().height) }; }, sel);
  // A tap on the row's own control (its ⋯, the one the row keeps below 600
  // since INBOX 392; the star is a swipe there) must not open the page.
  await page.click(`${sel} .entry-actions .menu-wrap > button`);
  await page.waitForTimeout(900);
  const starOpened = await page.evaluate(() => !!document.querySelector('.sheet-overlay[data-sheet="note"]'));
  if (starOpened) findings.push('tapping the row menu opened the page');
  await page.keyboard.press('Escape');
  await page.evaluate(() => loadEntries()); await page.waitForTimeout(1200);
  // A tap on the row opens it.
  await page.click(`${sel} .entry-content`);
  await page.waitForTimeout(700);
  const open = await page.evaluate(() => {
    const ov = document.querySelector('.sheet-overlay[data-sheet="note"]');
    if (!ov) return null;
    const card = ov.querySelector('.sheet-card');
    const c = card.querySelector('.entry-content');
    const bar = card.querySelector('.note-page-bar');
    const close = ov.querySelector('.sheet-close');
    const r = card.getBoundingClientRect();
    return { top: Math.round(r.top), h: Math.round(r.height), radius: getComputedStyle(card).borderTopLeftRadius, clamped: c.classList.contains('entry-clamped'), contentH: Math.round(c.getBoundingClientRect().height), barShown: !!bar && bar.getBoundingClientRect().height > 0, barButtons: bar ? [...bar.querySelectorAll('button')].filter((b) => b.getBoundingClientRect().width > 0).length : 0, barBottom: bar ? Math.round(bar.getBoundingClientRect().bottom) : null, barMinH: bar ? Math.min(...[...bar.querySelectorAll('button')].map((b) => Math.round(b.getBoundingClientRect().height))) : null, backLabel: close && close.getAttribute('aria-label'), backIcon: close && !!close.querySelector('.ph-arrow-left'), title: ov.getAttribute('aria-label'), listScrolls: (() => { const l = card.querySelector('.note-page-list'); return l.scrollHeight > l.clientHeight; })(), actionsInCard: !!card.querySelector('li .entry-actions') };
  });
  console.log('before', JSON.stringify(before), 'open', JSON.stringify(open));
  if (!open) findings.push('a tap on the row did not open the page');
  else {
    if (open.top !== 0 || open.h !== 844) findings.push(`the page is not the screen: top ${open.top}, height ${open.h}`);
    if (open.radius !== '0px') findings.push('the page has a rounded top: ' + open.radius);
    if (open.clamped || open.contentH <= before.h) findings.push(`the note is still clamped on the page (${open.contentH} vs ${before.h} in the list)`);
    if (!open.barShown || open.barButtons < 2) findings.push('the thumb bar is missing or empty: ' + open.barButtons);
    if (open.barBottom !== 844) findings.push('the thumb bar is not at the foot: bottom ' + open.barBottom);
    if (open.barMinH < 44) findings.push('a thumb bar button is under 44px: ' + open.barMinH);
    if (open.backLabel !== 'Back' || !open.backIcon) findings.push('the close is not a back chevron');
    if (!/Page probe/.test(open.title)) findings.push('the page is not titled by the note: ' + open.title);
    if (open.actionsInCard) findings.push('the card still holds its actions row as well as the bar');
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const closed = await page.evaluate((s) => ({ gone: !document.querySelector('.sheet-overlay[data-sheet="note"]'), focus: document.activeElement === document.querySelector(s) }), sel);
  if (!closed.gone) findings.push('Escape did not go back');
  if (!closed.focus) findings.push('focus did not return to the row');
  // The chevron goes back too.
  await page.click(`${sel} .entry-content`); await page.waitForTimeout(600);
  await page.click('.sheet-overlay[data-sheet="note"] .sheet-close'); await page.waitForTimeout(400);
  if (await page.evaluate(() => !!document.querySelector('.sheet-overlay[data-sheet="note"]'))) findings.push('the back chevron did not close the page');
  // Desktop: a tap opens nothing.
  await page.setViewportSize({ width: 1024, height: 800 }); await page.waitForTimeout(600);
  await page.click(`${sel} .entry-content`); await page.waitForTimeout(500);
  if (await page.evaluate(() => !!document.querySelector('.sheet-overlay[data-sheet="note"]'))) findings.push('the page opened at 1024');
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
