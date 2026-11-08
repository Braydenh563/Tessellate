// Cost of root class toggles (INBOX 1696 l): is-idle and a made-up class, before and after Settings opens.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('dashboard'); });
  await page.waitForTimeout(4000);
  const probe = (label) => page.evaluate((label) => {
    const root = document.documentElement; const out = [label];
    for (const cls of ['is-idle', 'x-probe', 'is-idle']) {
      root.classList.add(cls); root.offsetHeight;
      root.classList.remove(cls);
      const t = performance.now(); document.body.getBoundingClientRect(); out.push(`${cls} ${(performance.now() - t).toFixed(1)}`);
    }
    return out.join(' | ');
  }, label);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  console.log(await probe('before'));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  await page.click('#settings-btn'); await page.waitForTimeout(2500); await page.keyboard.press('Escape'); await page.waitForTimeout(1500);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  console.log(await probe('after settings'));
  for (const t of ['notes', 'library', 'chat', 'dashboard']) { await page.evaluate((t) => revealTab(t), t); await page.waitForTimeout(1500); }
  console.log(await probe('after four tabs'));
  await browser.close();
})();
