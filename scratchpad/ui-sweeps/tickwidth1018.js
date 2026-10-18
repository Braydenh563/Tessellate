// The widest label the strip can draw against the gutter it has.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  await page.evaluate(() => window.switchTab('timeline'));
  await page.waitForTimeout(1500);
  const r = await page.evaluate(async () => {
    await lazyScript('/css/timeline-ticks-lazy.css');
    const strip = document.getElementById('timeline-scrubber');
    strip.classList.add('has-ticks');
    const layer = document.createElement('div');
    layer.className = 'timeline-ticks';
    strip.prepend(layer);
    const worst = {};
    for (const t of ['Sep 28', 'May 30', 'Aug 31', 'Mar 30', 'Dec 30', 'Wed 30', '2026', 'Sep', '28']) {
      const el = document.createElement('span');
      el.className = 'timeline-tick is-major';
      el.textContent = t;
      el.style.top = '50px';
      layer.appendChild(el);
      worst[t] = Math.round(el.getBoundingClientRect().width * 10) / 10;
    }
    return { gutter: Math.round(layer.getBoundingClientRect().width), room: Math.round(layer.getBoundingClientRect().width - 8), worst };
  });
  console.log(JSON.stringify(r));
  await browser.close();
})();
