// L531: the boot budget (`first_paint`, routes_bench.py) is measured cold at
// 1440x900 with no service worker. This adds the two starts it leaves out,
// on the same data dir in the same run so the three are comparable:
//   cold   1440x900, a fresh context (empty cache, no service worker)
//   warm   1440x900, one context reloaded: the service worker is in control
//          and the HTTP cache is full (a person's second start)
//   phone  390x844, mobile and touch, a fresh context
// Each reports first contentful paint and app up (splash and lock gone), the
// p50 of RUNS runs. Phone stops at app up: its shell has no Notes tab button.
//
//   BASE=http://127.0.0.1:8852 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node tests-e2e/boot-warm-measure.js
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const m = require('./budget-measure.js');
const BASE = process.env.BASE || 'http://127.0.0.1:8852';
const PW = 'testpassword123';
const RUNS = +(process.env.RUNS || 5);
const INIT = () => { try { localStorage.setItem('theme', 'light'); localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); localStorage.setItem('nm-buddy-hint', 'done'); } catch (e) {} };
const DESK = { viewport: { width: 1440, height: 900 } };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };

const UP = () => {
  const splash = document.getElementById('boot-splash');
  const lock = document.getElementById('lock-overlay');
  return (!splash || splash.classList.contains('hidden')) && lock && lock.classList.contains('hidden') && !document.documentElement.classList.contains('shell-curtain');
};
const READ = () => {
  const paint = performance.getEntriesByName('first-contentful-paint')[0];
  return { firstPaint: paint ? Math.round(paint.startTime) : null, up: Math.round(performance.now()), sw: !!navigator.serviceWorker?.controller };
};

async function start(page) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(UP, null, { timeout: 60000, polling: 20 });
  return page.evaluate(READ);
}

const p50 = (rows, key) => m.p50(rows.map((r) => r[key]));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext(DESK);
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 30000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForFunction(() => !!localStorage.getItem('token'), null, { timeout: 30000 });
  await page.waitForTimeout(6000);
  const dontCheck = page.locator('.confirm-overlay button', { hasText: "Don't check" });
  if (await dontCheck.isVisible().catch(() => false)) await dontCheck.click();
  await page.waitForTimeout(1000);
  const state = await ctx.storageState();
  await ctx.close();
  const fresh = async (opts) => { const c = await browser.newContext({ ...opts, storageState: state }); await c.addInitScript(INIT); return c.newPage(); };
  const out = { runs: RUNS, cold: [], warm: [], phone: [] };
  for (let i = 0; i < RUNS; i++) { const p = await fresh(DESK); out.cold.push(await start(p)); await p.context().close(); }
  for (let i = 0; i < RUNS; i++) { const p = await fresh(PHONE); out.phone.push(await start(p)); await p.context().close(); }
  // Warm: one context, a first start to install the worker and fill the cache,
  // a wait for the worker to take control, then RUNS reloads.
  const w = await fresh(DESK);
  await start(w);
  await w.evaluate(() => navigator.serviceWorker?.ready).catch(() => {});
  await w.waitForTimeout(3000);
  for (let i = 0; i < RUNS; i++) out.warm.push(await start(w));
  await w.context().close();
  const sum = {};
  for (const k of ['cold', 'warm', 'phone']) sum[k] = { firstPaint: p50(out[k], 'firstPaint'), up: p50(out[k], 'up'), sw: out[k].filter((r) => r.sw).length };
  console.log('BOOTWARM', JSON.stringify(sum));
  console.log('RAW', JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
