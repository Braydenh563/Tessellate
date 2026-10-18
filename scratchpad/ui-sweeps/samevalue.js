// companion-1018: does a same-value write on #nm-buddy cost a restyle? Times a
// forced flush after each kind of write (1x and 4x CPU), median of 15.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(4000);
  for (const rate of [1, 4]) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    const r = await page.evaluate(async () => {
      const b = document.getElementById('nm-buddy');
      const med = (a) => a.sort((x, y) => x - y)[a.length >> 1];
      const cases = {
        none: () => {},
        sameDataset: () => { b.dataset.pose = b.dataset.pose; b.dataset.legs = b.dataset.legs; b.dataset.perch = b.dataset.perch; },
        sameEdge: () => b.style.setProperty('--nmb-edge', b.style.getPropertyValue('--nmb-edge') || '40px'),
        changedEdge: (() => { let i = 0; return () => b.style.setProperty('--nmb-edge', `${40 + (i++ % 2)}px`); })(),
        classToggle: () => b.classList.toggle('zz-probe'),
      };
      const out = {};
      for (const [k, w] of Object.entries(cases)) {
        const ts = [];
        for (let i = 0; i < 15; i += 1) { await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 30))); b.getBoundingClientRect(); w(); const t = performance.now(); b.getBoundingClientRect(); ts.push(performance.now() - t); }
        out[k] = +med(ts).toFixed(2);
      }
      return out;
    });
    console.log('rate', rate, JSON.stringify(r));
  }
  await browser.close();
})();
