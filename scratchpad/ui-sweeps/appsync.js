// Appearance follows the person (WORLD_CLASS 25f): two browser contexts on one
// notebook. A changes the look; B, reloaded, shows it. `perf` stays in A. Density is the
// device's own (DEVICE_ONLY_KEYS), so shadow strength stands in for a mirrored setting below.
//   BASE=http://127.0.0.1:8863 node scratchpad/ui-sweeps/appsync.js
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const PW = 'testpassword123';
const fail = [];
const check = (name, ok, got) => { console.log(ok ? 'ok  ' : 'FAIL', name, ok ? '' : JSON.stringify(got)); if (!ok) fail.push(name); };

async function open(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); } catch (e) {}
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await load(page);
  return { ctx, page };
}
async function load(page, reload) {
  if (reload) await page.reload({ waitUntil: 'domcontentloaded' });
  else await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForFunction(() => {
    const f = document.getElementById('lock-password');
    const o = document.getElementById('lock-overlay');
    return (f && o && !o.classList.contains('hidden') && f.offsetParent !== null) || (o && o.classList.contains('hidden') && localStorage.getItem('token'));
  }, null, { timeout: 60000, polling: 100 });
  if (await page.locator('#lock-password:visible').count()) {
    await page.fill('#lock-password', PW);
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(3500);
  //: Seeded means marked (`ui-synced`); a loaded machine takes longer than the fixed wait.
  await page.waitForFunction(() => localStorage.getItem('ui-synced') !== null, null, { timeout: 25000 }).catch(() => {});
}
const read = (page, keys) => page.evaluate((ks) => Object.fromEntries(ks.map((k) => [k, localStorage.getItem(k)])), keys);
const attrs = (page) => page.evaluate(() => ({ theme: document.documentElement.dataset.theme, density: document.documentElement.dataset.density }));

(async () => {
  const browser = await chromium.launch({ args: ['--disable-dev-shm-usage'] });
  const A = await open(browser);
  const keys = ['theme', 'density', 'contrast', 'border-style', 'shadow-intensity', 'dash-mark', 'perf'];
  // A: the look, written the way every control writes it (localStorage, watched), then repainted.
  await A.page.evaluate(() => {
    localStorage.setItem('theme', 'dark'); localStorage.setItem('density', 'compact');
    localStorage.setItem('contrast', 'on'); localStorage.setItem('border-style', 'solid');
    localStorage.setItem('shadow-intensity', '70'); localStorage.setItem('dash-mark', 'none');
    localStorage.setItem('perf', 'on');
    applyAppearance(); applyThemeChoice('dark', false);
  });
  await A.page.waitForTimeout(2500);
  const server = await A.page.evaluate(async () => (await apiJson('/preferences')).ui_state);
  check('server holds the mirrored keys', ['theme', 'contrast', 'border-style', 'shadow-intensity', 'dash-mark'].every((k) => server[k] != null), server);
  check('server does not hold density, the device\'s own', server.density === undefined, server.density);
  check('server does not hold perf', server.perf === undefined, server.perf);

  // B: a second browser opening the notebook gets them; perf stays in A.
  const B = await open(browser);
  const b1 = await read(B.page, keys);
  check('B got theme dark', b1.theme === 'dark', b1);
  check('B got contrast, border, shadow, mark', b1.contrast === 'on' && b1['border-style'] === 'solid' && b1['shadow-intensity'] === '70' && b1['dash-mark'] === 'none', b1);
  check('B did not get perf', b1.perf === null, b1.perf);
  check('B painted dark', (await attrs(B.page)).theme === 'dark', await attrs(B.page));

  // A changes the theme and density; B reloads and shows them.
  await A.page.evaluate(() => {
    localStorage.setItem('theme', 'light'); localStorage.setItem('shadow-intensity', '30');
    applyAppearance(); applyThemeChoice('light', false);
  });
  await A.page.waitForTimeout(2500);
  await load(B.page, true);
  const b2 = await read(B.page, keys);
  check('B after reload: theme light', b2.theme === 'light', b2);
  check('B after reload: shadow 30', b2['shadow-intensity'] === '30', b2);
  check('B after reload painted light', (await attrs(B.page)).theme === 'light', await attrs(B.page));

  // An unsent change in B survives its own reload (the 800 ms window).
  await B.page.evaluate(() => { localStorage.setItem('shadow-intensity', '10'); });
  await B.page.reload({ waitUntil: 'domcontentloaded' });
  await B.page.waitForTimeout(3500);
  const b3 = await read(B.page, ['shadow-intensity']);
  check('B keeps its own unsent shadow across a quick reload', b3['shadow-intensity'] === '10', b3);
  //: Not asserted: the kept value reaches the notebook with the next mirrored write, which a loaded machine may not make inside a fixed wait.

  // D: a browser that never agreed with the notebook (the first load after the
  // upgrade, no `ui-synced` mark) holds an old look. The notebook's wins, and the
  // old one is not pushed back over it (data-1011).
  const ctxD = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctxD.addInitScript(() => {
    try {
      localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1');
      if (!sessionStorage.getItem('d-seeded')) { sessionStorage.setItem('d-seeded', '1'); localStorage.setItem('shadow-intensity', '55'); }
    } catch (e) {}
  });
  const D = await ctxD.newPage();
  await load(D);
  const d1 = await read(D, ['shadow-intensity', 'ui-synced']);
  check('D (no mark, stale shadow) takes the notebook\'s 10', d1['shadow-intensity'] === '10', d1);
  check('D now has a mark', d1['ui-synced'] != null, d1);
  await D.waitForTimeout(2500);
  const afterD = await A.page.evaluate(async () => (await apiJson('/preferences')).ui_state['shadow-intensity']);
  check('and did not push its old shadow over the notebook', afterD === '10', afterD);
  await browser.close();
  console.log(fail.length ? `FAILED ${fail.length}` : 'ALL OK');
  process.exit(fail.length ? 1 : 0);
})();
