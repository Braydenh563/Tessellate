// Which subtree a companion class toggle restyles (INBOX 1696 l): element counts and per-toggle style ms.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('dashboard'); });
  await page.waitForTimeout(4000);
  const counts = await page.evaluate(() => { const b = document.getElementById('nm-buddy'); return { buddy: b.getElementsByTagName('*').length, svg: b.getElementsByTagName('svg').length, anims: document.getAnimations().length, buddyAnims: b.getAnimations({ subtree: true }).length }; });
  console.log(JSON.stringify(counts));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  const t = await page.evaluate(() => {
    const b = document.getElementById('nm-buddy'); const out = [];
    for (const cls of ['nm-buddy-dragging', 'nmb-walking', 'nmb-act-cheer']) {
      document.documentElement.offsetHeight; b.classList.toggle(cls);
      const t0 = performance.now(); getComputedStyle(b).width; out.push(cls + ' ' + (performance.now() - t0).toFixed(1)); b.classList.toggle(cls); document.documentElement.offsetHeight;
    }
    return out;
  });
  console.log(JSON.stringify(t));
  await browser.close();
})();
