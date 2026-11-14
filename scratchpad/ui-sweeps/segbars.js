// INBOX 107d: the segmented mini bars in a couple of popups.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  await page.waitForTimeout(1200);
  await page.evaluate(() => switchTab('documents'));
  await page.waitForTimeout(2200);
  await page.evaluate(() => { document.getElementById('doc-ai-panel').classList.remove('hidden'); });
  await page.waitForTimeout(700);
  const m = (sel) => page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return 'missing';
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      w: +b.width.toFixed(1), h: +b.height.toFixed(1), radius: cs.borderRadius, bg: cs.backgroundColor,
      pad: cs.padding, gap: cs.gap, border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
      kids: [...el.children].map((k) => {
        const kb = k.getBoundingClientRect();
        const kc = getComputedStyle(k);
        const checked = k.querySelector && k.querySelector('input:checked');
        return { t: k.textContent.trim().slice(0, 14), w: +kb.width.toFixed(1), h: +kb.height.toFixed(1), radius: kc.borderRadius, bg: kc.backgroundColor, color: kc.color, fs: kc.fontSize, fw: kc.fontWeight, shadow: kc.boxShadow.replace(/\s+/g, ' ').slice(0, 60), on: !!(checked || k.classList.contains('active')) };
      }),
    };
  }, sel);
  console.log('doc-ai-verb   ', JSON.stringify(await m('#doc-ai-verb')));
  console.log('doc-view-seg  ', JSON.stringify(await m('#doc-view-seg')));
  const box = await (await page.$('#doc-ai-verb')).boundingBox();
  await page.screenshot({ path: (process.env.SCRATCH || '.') + '/segbar-docai.png', clip: { x: box.x - 10, y: box.y - 10, width: box.width + 20, height: box.height + 20 } });
  // #graph-layout is a <select> in the options popover since INBOX 670, not a seg bar: not measured here.
  await browser.close();
})();
