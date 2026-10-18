// How far an Atlas drawing's painted parts reach past its own svg box, per framed host (INBOX 743 tail).
//   BASE=http://127.0.0.1:8798 node scratchpad/ui-sweeps/atlasspill1018.js
const { boot } = require('./lib.js');
const MEASURE = () => {
  const out = [];
  for (const svg of document.querySelectorAll('svg.nm-atlas, svg.name-mark')) {
    if (svg.closest('.atl-layer') && svg.parentElement.closest('svg.nm-atlas')) continue;
    const b = svg.parentElement.getBoundingClientRect();  // the holder is the frame
    if (!b.width) continue;
    let l = b.left, t = b.top, r = b.right, bt = b.bottom;
    for (const el of svg.querySelectorAll('*')) { const q = el.getBoundingClientRect(); if (!q.width && !q.height) continue; l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); bt = Math.max(bt, q.bottom); }
    out.push({ host: (svg.parentElement.className || svg.parentElement.id || '').toString().slice(0, 34), box: [Math.round(b.width), Math.round(b.height)], spill: { l: Math.round(b.left - l), t: Math.round(b.top - t), r: Math.round(r - b.right), b: Math.round(bt - b.bottom) }, clip: getComputedStyle(svg).clipPath + '/' + getComputedStyle(svg).overflow });
  }
  return out;
};
(async () => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { browser, page } = await boot({ viewport: vp });
    await page.evaluate(() => { document.getElementById('onboarding-overlay')?.classList.remove('hidden'); onboardingRun.index = 0; renderOnboardingSlide(); });
    await page.waitForTimeout(1500);
    console.log(vp.width, 'welcome', JSON.stringify(await page.evaluate(MEASURE)));
    await page.evaluate(() => { document.getElementById('onboarding-overlay')?.classList.add('hidden'); openHelpChat(); });
    await page.waitForTimeout(1500);
    console.log(vp.width, 'help', JSON.stringify(await page.evaluate(MEASURE)));
    await browser.close();
  }
})();
