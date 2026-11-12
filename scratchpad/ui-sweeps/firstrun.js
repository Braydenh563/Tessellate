// INBOX 472, the first-run walk: a brand-new person on a fresh data dir.
// Lock screen in setup mode, the welcome and its slides, every tab and
// sub-tab with an EMPTY notebook, the no-AI state, at a width and theme.
// Does NOT use lib.js's boot: that marks the welcome done before the app
// loads, which is exactly what this walk has to see.
//
//   rm -rf /tmp/mm-a865 && bash scratchpad/ui-sweeps/serve.sh 8865 /tmp/mm-a865
//   BASE=http://127.0.0.1:8865 W=1440 THEME=light SCRATCH=/tmp/fr node firstrun.js
//
// The first run against a fresh dir sets the password; later runs unlock.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://127.0.0.1:8865';
const W = +(process.env.W || 1440);
const H = W < 600 ? 844 : 900;
const THEME = process.env.THEME || 'light';
const OUT = (process.env.SCRATCH || '.') + '/fr';
fs.mkdirSync(OUT, { recursive: true });
const tag = `${W}-${THEME}`;
const phone = W < 600;

function emptyProbe() {
  // Every visible element that looks like an empty state in the active panel.
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const out = [];
  const sel = '[class*="empty"], .muted.center, [class*="placeholder"]:not(input):not(textarea)';
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    if (el.closest('.hidden')) continue;
    if (el.parentElement && el.parentElement.closest(sel) && vis(el.parentElement.closest(sel))) continue;
    const r = el.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) continue;
    const btns = [...el.querySelectorAll('button, a[href]')].filter(vis).map((b) => (b.textContent || b.getAttribute('aria-label') || '').trim().slice(0, 40));
    out.push({ cls: el.className.toString().slice(0, 70), id: el.id, text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 220), btns, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] });
  }
  // Anything that reads like an error.
  const errs = [];
  for (const el of document.querySelectorAll('.error, .status.error, [role="alert"], .toast, .warn, [class*="error"]')) {
    if (!vis(el)) continue;
    const t = (el.innerText || '').trim();
    if (t) errs.push({ cls: el.className.toString().slice(0, 60), id: el.id, text: t.replace(/\s+/g, ' ').slice(0, 200) });
  }
  return { out, errs };
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, ...(phone ? { isMobile: true, hasTouch: true } : {}) });
  await ctx.addInitScript((t) => { try { if (!localStorage.getItem('theme')) localStorage.setItem('theme', t); } catch (e) {} }, THEME);
  const page = await ctx.newPage();
  const log = [];
  page.on('pageerror', (e) => log.push('PAGEERROR ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') log.push(m.type().toUpperCase() + ' ' + m.text().slice(0, 200)); });
  page.on('response', (r) => { if (r.status() >= 400) log.push(`HTTP ${r.status()} ${r.url().replace(BASE, '')}`); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.waitForTimeout(1200);
  const mode = await page.evaluate(() => document.getElementById('lock-overlay').dataset.mode);
  const lock = await page.evaluate(() => {
    const q = (id) => document.getElementById(id);
    const r = (el) => { const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
    const card = document.querySelector('.lock-card');
    return { title: q('lock-title').textContent, msg: q('lock-message').textContent, note: q('lock-setup-note').textContent, noteHidden: q('lock-setup-note').classList.contains('hidden'), submit: q('lock-submit').textContent, card: r(card), cardScroll: [card.scrollHeight, card.clientHeight], field: r(q('lock-password')), btn: r(q('lock-submit')), fs: getComputedStyle(q('lock-setup-note')).fontSize, kids: [...card.children].filter((c) => c.getBoundingClientRect().height > 0).map((c) => c.id || c.className) };
  });
  console.log('LOCK', mode, JSON.stringify(lock));
  await page.screenshot({ path: `${OUT}/${tag}-00-lock.png` });
  // too-short password first: what does the error look like
  await page.fill('#lock-password', 'ab');
  await page.click('#lock-submit');
  await page.waitForTimeout(400);
  console.log('SHORT', await page.evaluate(() => document.getElementById('lock-error').textContent));
  await page.fill('#lock-password', 'testpassword123');
  await page.click('#lock-submit');
  await page.waitForTimeout(3500);
  const ob = await page.evaluate(() => !document.getElementById('onboarding-overlay').classList.contains('hidden'));
  console.log('ONBOARDING visible', ob);
  for (let i = 0; i < 6 && ob; i++) {
    await page.waitForTimeout(1500);
    const s = await page.evaluate(() => {
      const q = (id) => document.getElementById(id);
      const c = q('onboarding-card').getBoundingClientRect();
      return { title: q('onboarding-title').textContent, text: q('onboarding-text').innerText, atlas: q('onboarding-atlas').innerText, actions: [...q('onboarding-actions').querySelectorAll('button')].map((b) => b.textContent + ' | ' + b.title), next: q('onboarding-next').textContent, skip: q('onboarding-skip').textContent, card: [Math.round(c.left), Math.round(c.top), Math.round(c.width), Math.round(c.height)], scroll: [q('onboarding-card').scrollHeight, q('onboarding-card').clientHeight] };
    });
    console.log('SLIDE', i, JSON.stringify(s));
    await page.screenshot({ path: `${OUT}/${tag}-01-slide${i}.png` });
    if (/tour|started/i.test(s.next)) break;
    await page.click('#onboarding-next');
  }
  if (ob) {
    // Decline the tour: the walk is of the empty app, not the tour.
    await page.click('#onboarding-skip');
    await page.waitForTimeout(1200);
  }
  await page.screenshot({ path: `${OUT}/${tag}-02-after-welcome.png` });
  const toasts = await page.evaluate(() => [...document.querySelectorAll('.toast, [class*="toast"]')].filter((t) => t.getBoundingClientRect().height > 0).map((t) => t.innerText.replace(/\s+/g, ' ').slice(0, 200)));
  console.log('TOASTS after welcome', JSON.stringify(toasts));
  // AI status, wherever the pill is
  const ai = await page.evaluate(() => [...document.querySelectorAll('[id*="ai-status"], [id*="model-status"], .ai-pill, [class*="ai-status"]')].filter((e) => e.getBoundingClientRect().height > 0).map((e) => ({ id: e.id, cls: e.className.toString().slice(0, 50), text: e.innerText.replace(/\s+/g, ' ').slice(0, 120), title: e.title })));
  console.log('AI', JSON.stringify(ai));

  const tabs = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];
  for (const t of tabs) {
    await page.evaluate((t) => switchTab(t), t);
    await page.waitForTimeout(1800);
    const p = await page.evaluate(emptyProbe);
    console.log(`TAB ${t}`, JSON.stringify(p));
    await page.screenshot({ path: `${OUT}/${tag}-10-${t}.png` });
    // sub-tabs inside the panel
    const subs = await page.evaluate((t) => [...document.querySelectorAll(`#tab-${t} [role="tab"]`)].filter((b) => b.getBoundingClientRect().height > 0).map((b) => b.textContent.trim().replace(/\W+/g, '_')), t);
    for (const [i, id] of subs.entries()) {
      if (i === 0) continue;
      await page.evaluate(([t, i]) => [...document.querySelectorAll(`#tab-${t} [role="tab"]`)].filter((b) => b.getBoundingClientRect().height > 0)[i].click(), [t, i]);
      await page.waitForTimeout(1300);
      const sp = await page.evaluate(emptyProbe);
      console.log(`  SUB ${t}/${id}`, JSON.stringify(sp));
      await page.screenshot({ path: `${OUT}/${tag}-11-${t}-${id}.png` });
    }
  }
  console.log('LOG', JSON.stringify([...new Set(log)], null, 1));
  await browser.close();
})();
