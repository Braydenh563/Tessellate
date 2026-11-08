// INBOX 1696 l: a throw after Settings opened and closed froze 7.5 s (spotNow, 6.9 s forced layout).
// Measures the cost of one forced layout after a restyle of the companion (what a release does) before
// and after Settings opens and closes, at RATE x CPU, plus the DOM size and the throw's spotNow time.
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const TAB = process.env.TAB || 'dashboard';
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.evaluate((k) => { prefs.set('avatar-buddy', k); const b = document.getElementById('avatar-buddy'); if (b) b.value = k; syncNameMarkBuddy(); }, process.env.KIND || 'atlas');
  await page.evaluate((t) => revealTab(t), TAB);
  await page.waitForTimeout(4000);
  const probe = (label) => page.evaluate((label) => {
    const b = document.getElementById('nm-buddy');
    const out = { label, els: document.getElementsByTagName('*').length };
    const runs = [];
    for (let i = 0; i < 3; i++) {
      b.classList.toggle('nm-buddy-dragging');
      const t0 = performance.now();
      b.getBoundingClientRect();
      runs.push(+(performance.now() - t0).toFixed(1));
      document.documentElement.offsetHeight;
    }
    b.classList.remove('nm-buddy-dragging');
    // A whole-page dirtying, as a class on body would do.
    document.body.classList.toggle('x-probe');
    let t0 = performance.now(); document.body.getBoundingClientRect(); out.bodyRestyle = +(performance.now() - t0).toFixed(1);
    document.body.classList.toggle('x-probe');
    document.documentElement.offsetHeight;
    out.buddyRestyle = runs;
    const sm = document.getElementById('settings-modal');
    if (sm) { const cs = getComputedStyle(sm); out.settings = { display: cs.display, vis: cs.visibility, cv: cs.contentVisibility, els: sm.getElementsByTagName('*').length, cls: sm.className }; }
    return out;
  }, label);
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  console.log(JSON.stringify(await probe('before')));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  await page.click('#settings-btn');
  await page.waitForTimeout(2500);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  console.log(JSON.stringify(await probe('open')));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1500);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  console.log(JSON.stringify(await probe('closed')));
  const throwOnce = async (label) => {
  await page.evaluate(() => { window.__loaf = []; if (!window.__obs) { window.__obs = new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.duration > 50) __loaf.push({ d: Math.round(e.duration), fl: Math.round(e.forcedStyleAndLayoutDuration || 0), s: e.scripts.filter((x) => x.duration > 10).map((x) => `${x.sourceFunctionName || x.invoker} ${Math.round(x.duration)} fl ${Math.round(x.forcedStyleAndLayoutDuration)}`) }); }); __obs.observe({ type: 'long-animation-frame', buffered: false }); } });
  await page.evaluate(() => { if (false) {} if (typeof nameMarkBuddyThrowSpot !== 'function' || window.__wrapped) { window.__spot = []; return; } window.__wrapped = 1; const f = nameMarkBuddyThrowSpot; window.__spot = []; window.nameMarkBuddyThrowSpot = (s) => { const t = performance.now(); const r = f(s); __spot.push(+(performance.now() - t).toFixed(1)); return r; }; });
  const r = await page.evaluate(() => { const e = document.querySelector('#nm-buddy .nm-buddy-face') || document.getElementById('nm-buddy'); const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
  const a = await m();
  await page.mouse.move(r[0], r[1]); await page.mouse.down();
  for (let i = 1; i <= 8; i++) { await page.mouse.move(r[0] - i * 25, r[1] - i * 20); await page.waitForTimeout(16); }
  await page.mouse.up();
  await page.waitForTimeout(4000);
  const b = await m();
  console.log(JSON.stringify({ label, thrown: await page.evaluate(() => nmb.thrown), loaf: await page.evaluate(() => __loaf.slice(0, 6)), spotNow: await page.evaluate(() => __spot), layoutMs: +((b.LayoutDuration - a.LayoutDuration) * 1000).toFixed(0), styleMs: +((b.RecalcStyleDuration - a.RecalcStyleDuration) * 1000).toFixed(0), layouts: b.LayoutCount - a.LayoutCount }));
  };
  await throwOnce('after settings');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 }); await page.waitForTimeout(3000); await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  await throwOnce('again, no settings');
  await browser.close();
})();
