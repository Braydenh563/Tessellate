// Paragraphs over 120 characters outside popovers, per tab and per Settings section, at 1440x900.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8801';
const SCAN = (rootSel) => {
  const out = [];
  for (const e of document.querySelectorAll(rootSel + ' *')) {
    if (['SCRIPT', 'STYLE', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION', 'OPTGROUP', 'SVG', 'PATH', 'INPUT', 'CODE', 'PRE'].includes(e.tagName)) continue;
    if (e.closest('.popover, [role=tooltip], [role=listbox], .help-popover, [data-help-popover], [data-help-for], button, select, textarea, .md, .markdown, .note-body, .msg-body, .chat-msg, .answer, pre, [contenteditable=true], .cm-editor, .hidden')) continue;
    const b = e.getBoundingClientRect();
    if (!b.width || !b.height || getComputedStyle(e).visibility === 'hidden') continue;
    const t = [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
    if (t.length > 120) out.push((e.id ? '#' + e.id : '.' + String(e.className).split(' ')[0] || e.tagName) + ' | ' + t.length + ' ' + t.slice(0, 400));
  }
  return out;
};
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  if (await page.isVisible('#lock-password').catch(() => false)) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(3000); }
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  await page.waitForTimeout(800);
  const seen = new Set(); let total = 0;
  const report = (where, rows) => { for (const r of rows) { const k = r; if (seen.has(k)) continue; seen.add(k); total++; console.log(where + ' | ' + r); } };
  for (const tab of ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders']) {
    await page.evaluate((t) => document.getElementById('tab-btn-' + t).click(), tab);
    await page.waitForTimeout(1500);
    report(tab, await page.evaluate(SCAN, '#tab-' + tab));
  }
  await page.evaluate(() => openSettingsModal('models')).catch(() => {});
  await page.waitForTimeout(900);
  const NAV = '#settings-nav button, #settings-nav a, #settings-nav [data-section]';
  const n = await page.evaluate((NAV) => document.querySelectorAll(NAV).length, NAV);
  for (let i = 0; i < n; i++) {
    await page.evaluate(([NAV, i]) => document.querySelectorAll(NAV)[i]?.click(), [NAV, i]);
    await page.waitForTimeout(350);
    report('settings' + i, await page.evaluate(SCAN, '#settings-modal'));
  }
  console.log('TOTAL', total);
  await browser.close();
})();
