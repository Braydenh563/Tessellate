// Forgot your password? and the recovery key (INBOX 663), measured in a browser.
//
//   bash scratchpad/ui-sweeps/serve.sh 8811 <scratch>/mm-fp   # a FRESH data dir
//   BASE=http://127.0.0.1:8811 node scratchpad/ui-sweeps/forgotpw.js
//
// Needs a notebook with no password yet: every pass starts at setup and ends
// with the in-app reset, which is setup again, so the passes chain. Four
// passes: light and dark, 390 (a phone, touch) and 1440. Each pass:
//
//   1. setup, then the recovery key offer, Make, the key shown once
//   2. a private note, then lock; the lock card's "Forgot your password?"
//   3. the card, "I have my recovery key" with a new password: in, the note
//      readable, and the successor key shown once
//   4. lock, the card, "I don't have it", RESET: back to setup
//
// Measured on every surface it reaches: console errors and page errors,
// text contrast (WCAG: 4.5:1, 3:1 for large text) against the composited
// background, every visible control's box against the floor (44px under a
// touch pointer, 28px otherwise), horizontal overflow, and that the key
// leaves the page when its dialog closes. Prints numbers; exits 1 on any
// finding.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8811';
const PW = 'testpassword123';
const NEW_PW = 'a brand new passphrase';
const SECRET = 'the spare key is under the mat';
const findings = [];
const numbers = [];

function note(label, line) {
  findings.push(`${label}: ${line}`);
  console.log(`  FINDING ${line}`);
}

async function measure(page, label, rootSelector, touch) {
  const r = await page.evaluate(({ rootSelector, touch }) => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 1;
    const cx = cv.getContext('2d', { willReadFrequently: true });
    const parse = (c) => {
      if (!c || c === 'transparent') return null;
      const m = c.match(/^rgba?\(([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\)$/);
      if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
      cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
      const d = cx.getImageData(0, 0, 1, 1).data; return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
    };
    const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
    const over = (t, b) => ({ r: t.r * t.a + b.r * (1 - t.a), g: t.g * t.a + b.g * (1 - t.a), b: t.b * t.a + b.b * (1 - t.a), a: 1 });
    // The lock overlay paints two soft blobs over `--page`; the page colour
    // is what text on it is read against (the blobs are 70% transparent at
    // their edge and lighter than the card's own fill).
    const pageColour = parse(getComputedStyle(document.documentElement).getPropertyValue('--page').trim());
    const bgOf = (el) => {
      const layers = []; let base = null;
      for (let e = el; e; e = e.parentElement) {
        const cs = getComputedStyle(e);
        const c = parse(cs.backgroundColor);
        if (c && c.a > 0) { if (c.a >= 0.9) { base = c; break; } layers.push(c); }
        if (cs.backgroundImage && cs.backgroundImage !== 'none' && pageColour) { base = pageColour; break; }
      }
      if (!base) base = pageColour || { r: 255, g: 255, b: 255, a: 1 };
      let c = base; for (let i = layers.length - 1; i >= 0; i--) c = over(layers[i], c);
      return c;
    };
    const root = document.querySelector(rootSelector);
    if (!root) return { missing: true };
    const low = []; let texts = 0;
    for (const el of root.querySelectorAll('*')) {
      if (!el.checkVisibility || !el.checkVisibility()) continue;
      const text = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).map((n) => n.textContent.trim()).join(' ');
      if (!text) continue;
      const cs = getComputedStyle(el); const fg = parse(cs.color); if (!fg) continue;
      texts++;
      const bg = bgOf(el); const rr = ratio(fg.a < 1 ? over(fg, bg) : fg, bg);
      const size = parseFloat(cs.fontSize); const bold = parseInt(cs.fontWeight) >= 700;
      const need = (size >= 18.66 || (bold && size >= 14)) ? 3 : 4.5;
      if (rr < need) low.push(`${rr.toFixed(2)} <${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}> "${text.slice(0, 30)}"`);
    }
    const floor = touch ? 44 : 28;
    const small = []; let controls = 0; let minH = Infinity;
    for (const el of root.querySelectorAll('button, input, a[href], select, textarea')) {
      if (!el.checkVisibility || !el.checkVisibility()) continue;
      const b = el.getBoundingClientRect(); if (!b.width || !b.height) continue;
      controls++; minH = Math.min(minH, b.height);
      const iconOnly = !el.textContent.trim() && el.tagName === 'BUTTON';
      if (b.height < floor - 0.5 || (iconOnly && b.width < floor - 0.5)) small.push(`${el.id || el.className || el.tagName} ${Math.round(b.width)}x${Math.round(b.height)}`);
    }
    const box = root.getBoundingClientRect();
    return {
      texts, low, controls, small, minH: Math.round(minH),
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      rootOverflow: Math.max(0, Math.round(box.right - window.innerWidth), Math.round(-box.left)),
      width: Math.round(box.width),
    };
  }, { rootSelector, touch });
  if (r.missing) { note(label, `${rootSelector} not found`); return; }
  numbers.push(`${label}: ${r.texts} texts, ${r.controls} controls (min ${r.minH}px), width ${r.width}, page overflow ${r.overflowX}px`);
  console.log(`  ${label}: ${r.texts} texts, ${r.low.length} low contrast; ${r.controls} controls, smallest ${r.minH}px, ${r.small.length} under floor; overflow ${r.overflowX}px`);
  if (!r.texts) note(label, 'nothing measured');
  for (const l of r.low) note(label, `contrast ${l}`);
  for (const s of r.small) note(label, `target ${s}`);
  if (r.overflowX > 0) note(label, `page scrolls sideways by ${r.overflowX}px`);
  if (r.rootOverflow > 0) note(label, `surface leaves the window by ${r.rootOverflow}px`);
}

async function waitVisible(page, selector, timeout = 20000) {
  await page.waitForFunction((s) => { const el = document.querySelector(s); return el && el.checkVisibility && el.checkVisibility(); }, selector, { timeout, polling: 100 });
}

async function waitAppOpen(page) {
  await page.waitForFunction(() => document.getElementById('lock-overlay').classList.contains('hidden')
    && !document.documentElement.classList.contains('shell-curtain'), null, { timeout: 30000, polling: 100 });
}

async function pass(theme, width) {
  const touch = width < 600;
  const label = `${theme} ${width}`;
  console.log(`== ${label}`);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width, height: touch ? 844 : 900 },
    ...(touch ? { hasTouch: true, isMobile: true } : {}),
  });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      localStorage.setItem('nm-buddy-hint', 'done');
    } catch (e) { /* a fresh profile */ }
  }, theme);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console ${m.text().slice(0, 160)}`); });
  //: Which requests were refused, so "expected" is a list rather than a count.
  const refused = [];
  page.on('response', (r) => { if (r.status() === 401) refused.push(new URL(r.url()).pathname); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });

  // 1. Setup, and the offer.
  await page.waitForFunction(() => document.getElementById('lock-overlay')?.dataset.mode === 'setup', null, { timeout: 20000 });
  const linkInSetup = await page.isVisible('#lock-forgot');
  if (linkInSetup) note(label, 'the forgot link shows during setup');
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await waitAppOpen(page);
  // The update question a fresh notebook asks once, answered so it sits over nothing.
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    for (const card of document.querySelectorAll('.confirm-overlay')) {
      const no = [...card.querySelectorAll('button')].find((b) => /Don.t check/.test(b.textContent));
      if (no) no.click();
    }
  });
  await waitVisible(page, '#recovery-key-dialog');
  await measure(page, `${label} offer`, '#recovery-key-dialog', touch);
  await page.click('#recovery-key-make');
  await waitVisible(page, '#recovery-key-value');
  const key = (await page.textContent('#recovery-key-value')).trim();
  if (!/^([A-Z2-7]{4}-){7}[A-Z2-7]{4}$/.test(key)) note(label, `key shape ${key}`);
  await measure(page, `${label} key shown`, '#recovery-key-dialog', touch);
  await page.click('#recovery-key-done');
  const leftover = await page.evaluate(() => document.getElementById('recovery-key-value').textContent);
  if (leftover) note(label, 'the key stayed in the page after Done');

  // 1b. Settings: the button says Replace it now; replacing asks the password
  // on the lock card's prompt and shows a different key, once.
  await page.evaluate(() => openSettingsModal('account'));
  await page.waitForFunction(() => /Replace it/.test(document.getElementById('account-recovery-make')?.textContent || ''), null, { timeout: 20000, polling: 100 });
  await page.click('#account-recovery-make');
  await page.waitForFunction(() => [...document.querySelectorAll('.confirm-overlay button')].some((b) => /Replace/.test(b.textContent)), null, { timeout: 15000 });
  await page.evaluate(() => [...document.querySelectorAll('.confirm-overlay button')].find((b) => b.textContent.trim() === 'Replace').click());
  await page.waitForFunction(() => document.getElementById('lock-overlay').dataset.mode === 'prompt', null, { timeout: 15000 });
  if (await page.isVisible('#lock-forgot')) note(label, 'the forgot link shows on a password prompt');
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await waitVisible(page, '#recovery-key-value');
  const replaced = (await page.textContent('#recovery-key-value')).trim();
  if (!replaced || replaced === key) note(label, 'Replace it did not show a new key');
  await measure(page, `${label} settings replaced`, '#recovery-key-dialog', touch);
  await page.click('#recovery-key-done');
  await page.waitForFunction(() => /Recovery key replaced/.test(document.getElementById('account-recovery-status')?.textContent || ''), null, { timeout: 10000 }).catch(() => note(label, 'no "Recovery key replaced." status'));
  await page.evaluate(() => document.querySelector('#settings-close')?.click());
  await page.waitForTimeout(400);

  // 2. A private note, then lock.
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const made = await page.evaluate(async ({ token, SECRET }) => {
    const h = { 'Content-Type': 'application/json', 'X-Auth-Token': token };
    const e = await (await fetch('/entries', { method: 'POST', headers: h, body: JSON.stringify({ content: SECRET }) })).json();
    await fetch(`/entries/${e.id}/privacy`, { method: 'POST', headers: h, body: JSON.stringify({ private: true }) });
    return e.id;
  }, { token, SECRET });
  await page.evaluate(() => lockNow());
  await waitVisible(page, '#lock-forgot');
  await measure(page, `${label} lock card`, '#lock-card', touch);

  // 3. The card, with the key.
  await page.click('#lock-forgot');
  await waitVisible(page, '#lock-forgot-card');
  if (await page.isVisible('#lock-card')) note(label, 'the lock card shows beside the forgot card');
  await measure(page, `${label} card key path`, '#lock-forgot-card', touch);
  // A wrong key first, the one Replace it just retired: the error under the field.
  await page.fill('#lock-recovery-key', key);
  await page.fill('#lock-recovery-new', NEW_PW);
  await page.fill('#lock-recovery-confirm', NEW_PW);
  await page.click('#lock-recovery-submit');
  await page.waitForFunction(() => document.getElementById('lock-forgot-error').textContent.trim(), null, { timeout: 15000 });
  const wrong = (await page.textContent('#lock-forgot-error')).trim();
  if (wrong !== 'That recovery key is wrong.') note(label, `wrong key said "${wrong}"`);
  await measure(page, `${label} card wrong key`, '#lock-forgot-card', touch);
  await page.fill('#lock-recovery-key', replaced.toLowerCase().replace(/-/g, ' '));
  await page.click('#lock-recovery-submit');
  await waitAppOpen(page);
  await waitVisible(page, '#recovery-key-value');
  const successor = (await page.textContent('#recovery-key-value')).trim();
  if (!successor || successor === replaced) note(label, 'no new key after the reset');
  await measure(page, `${label} new key`, '#recovery-key-dialog', touch);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  if (await page.evaluate(() => document.getElementById('recovery-key-value').textContent)) note(label, 'the key stayed after Escape');
  const readable = await page.evaluate(async (id) => {
    const r = await fetch(`/entries/${id}`, { headers: { 'X-Auth-Token': localStorage.getItem('token') } });
    return (await r.json()).content;
  }, made);
  if (readable !== SECRET) note(label, `private note after the reset: "${String(readable).slice(0, 40)}"`);

  // 4. The reset without a key.
  await page.evaluate(() => lockNow());
  await waitVisible(page, '#lock-forgot');
  await page.click('#lock-forgot');
  await waitVisible(page, '#lock-forgot-card');
  await page.click('#lock-forgot-lost');
  await waitVisible(page, '#lock-forgot-reset-pane');
  await measure(page, `${label} card reset path`, '#lock-forgot-card', touch);
  if (!(await page.isDisabled('#lock-reset-submit'))) note(label, 'Reset armed before RESET was typed');
  await page.fill('#lock-reset-confirm', 'RESET');
  if (!(await page.isDisabled('#lock-reset-submit'))) note(label, 'Reset armed without the code (INBOX 1424)');
  // The code is read from the server's terminal output (DATA_DIR/server.log), as a person would.
  const logPath = process.env.SERVER_LOG;
  const before = logPath ? require('fs').readFileSync(logPath, 'utf8') : '';
  await page.click('#lock-reset-send');
  let code = null;
  for (let i = 0; i < 20 && !code; i++) {
    await page.waitForTimeout(250);
    const text = require('fs').readFileSync(logPath, 'utf8').slice(before.length);
    const m = text.match(/reset code: (\d{6})/);
    if (m) code = m[1];
  }
  if (!code) { note(label, 'no code in the server log'); return; }
  await page.fill('#lock-reset-code', '000000');
  await page.click('#lock-reset-submit');
  await page.waitForTimeout(600);
  const wrongMsg = await page.textContent('#lock-forgot-error');
  console.log('  wrong code message:', wrongMsg);
  if (!/wrong|run out/i.test(wrongMsg)) note(label, 'wrong code gave no message');
  await page.fill('#lock-reset-code', code);
  if (await page.isDisabled('#lock-reset-submit')) note(label, 'Reset not armed after RESET and the code');
  await page.click('#lock-reset-submit');
  await page.waitForFunction(() => document.getElementById('lock-overlay').dataset.mode === 'setup', null, { timeout: 15000 });
  if (await page.isVisible('#lock-forgot-card')) note(label, 'the card stayed over setup');
  const status = await page.evaluate(async () => (await fetch('/auth/status')).json());
  if (!status.setup_required) note(label, 'not at setup after the reset');

  // Expected refusals: a wrong key's 401 is the browser's own console line.
  const real = errors.filter((e) => !/status of 401/.test(e));
  numbers.push(`${label}: ${real.length} console errors (${errors.length - real.length} 401 lines; refused: ${refused.join(', ')})`);
  for (const e of real) note(label, e);
  await browser.close();
}

(async () => {
  for (const theme of ['light', 'dark']) {
    for (const width of [390, 1440]) {
      await pass(theme, width);
    }
  }
  console.log('\n== numbers');
  for (const n of numbers) console.log('  ' + n);
  console.log(`\n== ${findings.length ? findings.length + ' findings' : 'no findings'}`);
  for (const f of findings) console.log('  ' + f);
  process.exit(findings.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
