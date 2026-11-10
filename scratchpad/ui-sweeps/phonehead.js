// UI_MODERNISATION Phase 11 item 1: the phone top bar is where you are, what
// came in, and one way to the rest. Measured before: six 44px controls at
// 320 and the last one ending at 332, so every phone page scrolled sideways.
// This reads the bar at three phone widths and one desktop width, opens the
// one menu, and reports numbers rather than a screenshot.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 320, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2500);
  const findings = [];
  const readBar = () => page.evaluate(() => {
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const controls = [...document.querySelectorAll('#top-bar .header-controls button')].filter(vis).filter((b) => !b.closest('.action-menu'));
    return {
      scrollW: document.documentElement.scrollWidth,
      n: controls.length,
      ids: controls.map((b) => b.id || b.getAttribute('aria-label')),
      heights: [...new Set(controls.map((b) => Math.round(b.getBoundingClientRect().height)))],
      right: Math.max(...controls.map((b) => Math.round(b.getBoundingClientRect().right))),
    };
  });
  for (const w of [320, 360, 390]) {
    await page.setViewportSize({ width: w, height: 844 });
    await page.waitForTimeout(400);
    const bar = await readBar();
    console.log(w, JSON.stringify(bar));
    if (bar.scrollW > w) findings.push(`${w}: page scrolls sideways, ${bar.scrollW} in ${w}`);
    if (bar.n > 3) findings.push(`${w}: ${bar.n} header controls, the phone bar takes three`);
    if (bar.heights.length !== 1) findings.push(`${w}: header controls at ${bar.heights.join('/')}px, one height expected`);
    if (bar.right > w) findings.push(`${w}: a header control ends at ${bar.right}`);
    if (!bar.ids.includes('App menu')) findings.push(`${w}: no App menu in the bar`);
  }
  // The menu: four rows, Lock following the desktop lock button, Escape closes.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.click('#header-more > button');
  await page.waitForTimeout(400);
  const menu = await page.evaluate(() => {
    // `escapeMenuIfClipped` may have reparented the open menu to the body.
    const m = document.querySelector('.action-menu:not(.hidden)');
    const rows = m ? [...m.querySelectorAll('.menu-item')] : [];
    const vis = (el) => !el.hidden && el.getBoundingClientRect().height > 0;
    return {
      open: !!m && !m.classList.contains('hidden'),
      rows: rows.map((r) => r.textContent.trim()),
      visible: rows.filter(vis).length,
      lockShown: rows[2] ? vis(rows[2]) : null,
      lockBtnHidden: document.getElementById('lock-btn').classList.contains('hidden'),
      rowHeights: [...new Set(rows.filter(vis).map((r) => Math.round(r.getBoundingClientRect().height)))],
    };
  });
  console.log('menu', JSON.stringify(menu));
  if (!menu.open) findings.push('the More menu did not open');
  // The four app verbs end the menu; since INBOX 392 the status bar's own
  // controls are the rows above them (`PHONE_STATUS_ROWS`), the bar being off
  // a phone's screen.
  const app = ['Light or dark', 'Settings', 'Lock', 'Quit Tessellate'];
  if (menu.rows.slice(-4).join('|') !== app.join('|')) findings.push('the More menu does not end with ' + app.join(', ') + ': ' + menu.rows.join(', '));
  if (!menu.rows.includes('Recent places')) findings.push('the status bar rows are missing from the More menu');
  if (menu.lockShown === menu.lockBtnHidden) findings.push('the Lock row does not follow the lock button');
  if (menu.rowHeights.some((h) => h < 44)) findings.push('a menu row is under 44px on a phone: ' + menu.rowHeights.join('/'));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  const closed = await page.evaluate(() => !document.querySelector('.action-menu:not(.hidden)'));
  if (!closed) findings.push('Escape did not close the More menu');
  // Desktop: the four buttons, no menu.
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.waitForTimeout(400);
  const desk = await page.evaluate(() => {
    const vis = (id) => { const el = document.getElementById(id); const r = el.getBoundingClientRect(); return r.width > 0; };
    return { theme: vis('theme-btn'), settings: vis('settings-btn'), quit: vis('quit-btn'), more: vis('header-more') };
  });
  console.log('desktop', JSON.stringify(desk));
  if (!desk.theme || !desk.settings || !desk.quit) findings.push('a desktop header button is missing at 1024');
  if (desk.more) findings.push('the More menu shows on the desktop');
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
