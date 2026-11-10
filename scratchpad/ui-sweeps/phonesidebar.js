// UI_MODERNISATION Phase 11 items 2 and 3: below 600 the sidebar rail is
// gone, the page beside a sidebar takes the full width, and each sidebar
// opens from a button at the leading edge of its own head. Above 600 the
// tablet keeps its rail. Numbers, per surface, at 390 and 768.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2500);
  await page.evaluate(async () => { await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'Phone doc', content: 'A line.' }) }).catch(() => {}); });
  const findings = [];
  const surfaces = [
    { tab: 'notes', aside: 'sidebar', dock: '[data-dock-name="notes"]', page: '#tab-notes .tab-main' },
    { tab: 'chat', aside: 'chat-sidebar', dock: '[data-dock-name="chat"]', page: '#tab-chat .tab-main, #tab-chat main, #tab-chat .chat-main' },
    { tab: 'documents', aside: 'doc-sidebar', dock: '.doc-dock', page: '.doc-main' },
  ];
  for (const s of surfaces) {
    await page.evaluate((t) => switchTab(t), s.tab);
    await page.waitForTimeout(900);
    const r = await page.evaluate((s) => {
      const aside = document.getElementById(s.aside);
      const dock = document.querySelector(s.dock);
      const opener = dock && dock.querySelector(':scope > .dock-nav > button');
      const main = document.querySelector(s.page);
      const box = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.left), w: Math.round(b.width), h: Math.round(b.height) }; };
      const railToggle = aside.querySelector('.sidebar-collapse-toggle');
      return {
        asideX: Math.round(aside.getBoundingClientRect().right),
        mainPad: main ? getComputedStyle(main).paddingLeft : null,
        opener: opener ? box(opener) : null,
        openerFirst: opener ? dock.firstElementChild === opener.parentElement : false,
        railToggleShown: railToggle ? railToggle.getBoundingClientRect().width > 0 : null,
      };
    }, s);
    console.log(s.tab, JSON.stringify(r));
    if (r.asideX > 0) findings.push(`${s.tab}: the closed sidebar still shows ${r.asideX}px at 390`);
    // The rail is 60px on a tablet; a phone keeps only the page's own 4px gutter.
    if (!(parseFloat(r.mainPad) <= 8)) findings.push(`${s.tab}: the page beside the sidebar still pads ${r.mainPad}`);
    if (!r.opener) findings.push(`${s.tab}: no opener in the dock`);
    else { if (r.opener.h < 44 || r.opener.w < 44) findings.push(`${s.tab}: opener ${r.opener.w}x${r.opener.h}`); if (!r.openerFirst) findings.push(`${s.tab}: the opener is not the dock's first child`); }
    if (r.railToggleShown) findings.push(`${s.tab}: the rail toggle still shows while closed`);
    // Open, then Escape.
    await page.click(`${s.dock} > .dock-nav > button`);
    await page.waitForTimeout(500);
    const open = await page.evaluate((s) => { const a = document.getElementById(s.aside); const b = a.getBoundingClientRect(); return { cls: a.classList.contains('sidebar-sheet-open'), left: Math.round(b.left), w: Math.round(b.width), closer: a.querySelector('.sidebar-collapse-toggle').getBoundingClientRect().width > 0, expanded: document.querySelector(`${s.dock} > .dock-nav > button`).getAttribute('aria-expanded') }; }, s);
    console.log(s.tab, 'open', JSON.stringify(open));
    if (!open.cls || open.left !== 0) findings.push(`${s.tab}: the sheet did not open at the edge (${JSON.stringify(open)})`);
    if (!open.closer) findings.push(`${s.tab}: the open sheet has no closer`);
    if (open.expanded !== 'true') findings.push(`${s.tab}: opener aria-expanded is ${open.expanded} while open`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    const closed = await page.evaluate((s) => !document.getElementById(s.aside).classList.contains('sidebar-sheet-open'), s);
    if (!closed) findings.push(`${s.tab}: Escape did not close the sheet`);
  }
  // Tablet keeps the rail and hides the opener.
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(700);
  const tab = await page.evaluate(() => ({ pad: getComputedStyle(document.querySelector('#tab-notes .tab-main')).paddingLeft, opener: document.querySelector('[data-dock-name="notes"] > .dock-nav').getBoundingClientRect().width, toggle: document.querySelector('#sidebar > .sidebar-collapse-toggle').getBoundingClientRect().width }));
  console.log('768', JSON.stringify(tab));
  if (tab.pad === '0px') findings.push('768: the tablet lost its rail');
  if (tab.opener > 0) findings.push('768: the phone opener shows on a tablet');
  if (!(tab.toggle > 0)) findings.push('768: the rail toggle is gone on a tablet');
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
