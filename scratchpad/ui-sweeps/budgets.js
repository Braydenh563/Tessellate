// Brief 53 (WORLD_CLASS_PLAN 25g): the six interaction timings of decision 54,
// measured in headless Chromium against a data dir seeded by
// scratchpad/budgets-seed.py (500 notes, a 500-object board, a 50,000-word
// document). Prints one JSON line; RUNS=n repeats each interaction.
//
//   BASE=http://127.0.0.1:8852 BOARD=504 DOC=6 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/budgets.js
const { chromium } = require('playwright');
const m = require('../../tests-e2e/budget-measure.js');
const BASE = process.env.BASE || 'http://127.0.0.1:8852';
const PW = 'testpassword123';
const RUNS = +(process.env.RUNS || 5);
const INIT = () => { try { localStorage.setItem('theme', 'light'); localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); localStorage.setItem('nm-buddy-hint', 'done'); } catch (e) {} };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 30000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForFunction(() => !!localStorage.getItem('token'), null, { timeout: 30000 });
  const dismiss = async () => page.evaluate(() => { for (const id of ['onboarding-overlay']) { const o = document.getElementById(id); if (o) o.classList.add('hidden'); } const d = document.querySelector('#recovery-key-dialog[open]'); if (d) d.close(); });
  await page.waitForTimeout(6000); await dismiss();
  const dontCheck = page.locator('.confirm-overlay button', { hasText: "Don't check" });
  if (await dontCheck.isVisible().catch(() => false)) await dontCheck.click();
  await page.waitForTimeout(1000);
  const state = await ctx.storageState();
  const out = { runs: RUNS, boot: [] };
  const openPage = async () => { const c = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: state }); await c.addInitScript(INIT); return c.newPage(); };
  for (let i = 0; i < RUNS; i++) out.boot.push(await m.boot(openPage, BASE));
  out.firstPaint = m.p50(out.boot.map((r) => r.firstPaint));
  out.firstInteraction = m.p50(out.boot.map((r) => r.firstInteraction));
  out.listPaint = await m.listPaint(page, RUNS + 2);
  out.search = await m.search(page);
  out.boardOpenFirst = null;
  out.boardOpen = await m.boardOpen(page, +process.env.BOARD, 500, RUNS);
  out.documentOpen = await m.documentOpen(page, +process.env.DOC, RUNS);
  console.log('BUDGETS', JSON.stringify(out));
  await browser.close();
})();
