// Row 17: which of the companion's running animations are NOT on the compositor.
// Chromium restyles every animated element every frame (60/s) when any one
// running animation cannot be composited, so one culprit costs all. For each
// distinct animation, everything else is paused for 700 ms and the style
// recalcs counted (a composited one adds under 5; a main-thread one about 40).
// Prints the offenders. Env: BASE, KIND (atlas), TAB (chat), SETTLE (12000), SKIP_BUDDY=1 to test the page's own.
//   BASE=http://127.0.0.1:8784 node scratchpad/ui-sweeps/companioncomposite1101.js
const { boot } = require('./lib.js');
const KEY = `(a) => { const t = a.effect.target; const cls = (t.getAttribute('class') || '').split(' ').filter((c) => /^atl-|^emblem|^nmb|^nm-/.test(c)).join('.'); const props = [...new Set(a.effect.getKeyframes().flatMap((k) => Object.keys(k)).filter((k) => !/offset|easing|composite/.test(k)))].join(','); return (a.animationName || a.id || 'waapi') + ' ' + (t instanceof SVGElement ? 'svg' : 'html') + ' ' + (t.tagName.toLowerCase()) + '.' + cls + ' [' + props + ']'; }`;
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.evaluate((k) => { const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.evaluate((t) => { localStorage.removeItem('nm-buddy-spots'); revealTab(t); }, process.env.TAB || 'chat');
  await page.waitForTimeout(Number(process.env.SETTLE || 12000));
  const count = async () => (await cdp.send('Performance.getMetrics')).metrics.find((x) => x.name === 'RecalcStyleCount').value;
  const keys = await page.evaluate((KEY) => { const f = eval(KEY); return [...new Set(document.getAnimations().filter((a) => a.playState === 'running').map(f))]; }, KEY);
  const bad = [];
  for (const k of keys) {
    await page.evaluate(([KEY, k]) => { const f = eval(KEY); window.__held = []; for (const a of document.getAnimations()) if (a.playState === 'running' && f(a) !== k) { a.pause(); window.__held.push(a); } }, [KEY, k]);
    await page.waitForTimeout(300);
    const a = await count(); await page.waitForTimeout(700); const b = await count();
    await page.evaluate(() => { for (const a of window.__held) a.play(); });
    if (b - a > 12) bad.push(`${b - a} frames/0.7s  ${k}`);
  }
  console.log(`${keys.length} animation kinds; main-thread ones:`);
  console.log(bad.length ? bad.join('\n') : '(none)');
  await browser.close();
})();
