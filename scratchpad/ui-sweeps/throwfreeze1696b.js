// Split of the companion class toggle's cost: style recalc vs layout (INBOX 1696 l).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab('dashboard'); });
  await page.waitForTimeout(4000);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  const r = await page.evaluate(() => {
    const b = document.getElementById('nm-buddy');
    const res = [];
    for (const [name, el, cls] of [['buddy', b, 'nm-buddy-dragging'], ['buddyX', b, 'x-probe'], ['body', document.body, 'x-probe'], ['leaf', document.querySelector('#dash-grid') || document.body, 'x-probe']]) {
      for (let i = 0; i < 3; i++) {
        document.documentElement.offsetHeight;
        el.classList.toggle(cls);
        let t = performance.now(); getComputedStyle(el).width; const st = performance.now() - t;
        t = performance.now(); el.getBoundingClientRect(); const ly = performance.now() - t;
        res.push(`${name} style ${st.toFixed(1)} layout ${ly.toFixed(1)}`);
      }
      el.classList.remove(cls);
    }
    return { res, pos: getComputedStyle(b).position, contain: getComputedStyle(b).contain, parent: b.parentElement.id || b.parentElement.tagName };
  });
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
})();
