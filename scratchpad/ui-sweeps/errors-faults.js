// errors.js's fault-injection pass (WORLD_CLASS_PLAN H9, row 27: "retry as a
// grammar ... the fake server returns 500 on one route at a time. Gate: zero
// routes whose failure leaves the surface blank").
//
//   FAULTS=1 BASE=http://127.0.0.1:8865 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/errors.js        (or run this file directly)
//
// Method: boot once and record every app route the boot and a walk through
// the seven tabs call (GET, no static files). Then for each route, a fresh
// page in which that one route answers 500 and everything else is real: boot,
// walk the tabs, and read two things per tab:
// - an uncaught page error (a failure the code did not expect at all);
// - a blank surface: the tab's page shows under 40 characters of text and no
//   `surfaceFailed` notice (`.is-failed`), so a person sees nothing and
//   is told nothing. A tab that says why, or shows its other parts, passes.
// ONLY=/entries,/tags narrows the routes; LIMIT caps them (default 60).
// Exit 1 when anything is found.
const { chromium } = require('playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const PW = 'testpassword123';
const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline', 'reminders'];
const STATIC = /^\/(js|css|vendor|fonts|media|files|favicon|icon|apple-touch|manifest|sw\.js|clip\.html)|\.(png|svg|ico|webmanifest|woff2?)$/;

async function signIn(page) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const field = await page.waitForSelector('#lock-password', { state: 'visible', timeout: 8000 }).catch(() => null);
  if (field) {
    await page.fill('#lock-password', PW);
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(3500);
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden'));
}

async function walk(page, read) {
  const out = {};
  for (const tab of TABS) {
    await page.evaluate((n) => { try { switchTab(n); } catch (e) {} }, tab);
    await page.waitForTimeout(1300);
    if (read) out[tab] = await page.evaluate((n) => {
      const pageEl = document.getElementById(`tab-${n}`) || document.querySelector('.tab-page:not(.hidden)');
      if (!pageEl) return { text: 0, told: false };
      const text = (pageEl.innerText || '').replace(/\s+/g, ' ').trim().length;
      const told = !!pageEl.querySelector('.is-failed');
      return { text, told };
    }, tab);
  }
  return out;
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); } catch (e) {} });
  const first = await ctx.newPage();
  const routes = new Set();
  first.on('request', (req) => {
    const url = new URL(req.url());
    if (url.origin !== new URL(BASE).origin || req.method() !== 'GET' || STATIC.test(url.pathname) || url.pathname === '/') return;
    routes.add(url.pathname.replace(/\/\d+(?=\/|$)/g, '/*'));
  });
  await signIn(first);
  await walk(first, false);
  await first.close();
  let list = [...routes].sort();
  if (process.env.ONLY) list = list.filter((r) => process.env.ONLY.split(',').some((o) => r.startsWith(o)));
  list = list.slice(0, Number(process.env.LIMIT || 60));
  console.log(`${list.length} routes seen at boot and on the seven tabs`);
  let findings = 0;
  for (const route of list) {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message.slice(0, 120)));
    const pattern = new RegExp(`^${BASE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}${route.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '\\d+')}(\\?.*)?$`);
    await page.route(pattern, (r) => r.request().method() === 'GET'
      ? r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected failure (errors-faults.js)' }) })
      : r.continue());
    await signIn(page);
    const tabs = await walk(page, true);
    const blank = Object.entries(tabs).filter(([, v]) => v.text < 40 && !v.told).map(([k]) => k);
    const bad = errors.length + blank.length;
    findings += bad;
    console.log(`${bad ? 'FAIL' : 'ok  '} ${route}${errors.length ? `  uncaught: ${[...new Set(errors)].join(' | ')}` : ''}${blank.length ? `  blank: ${blank.join(', ')}` : ''}`);
    await page.close();
  }
  console.log(findings ? `FAIL: ${findings} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
