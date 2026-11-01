// Audit 1031 row 17: the companion at rest (1440x900), idle 10 s, per CPU rate.
// Counts atlasRigFrame calls, live animations, long-animation-frame ms, and the
// off-tab state (hidden vs opacity 0). Env: BASE, KIND (atlas|me), RATES (1,4), MS, TAB (chat).
//   BASE=http://127.0.0.1:8784 node scratchpad/ui-sweeps/companionrest1101.js
const { boot } = require('./lib.js');
const KIND = process.env.KIND || 'atlas';
const MS = Number(process.env.MS || 10000);
const TAB = process.env.TAB || 'chat';
const OTHER = process.env.OTHER || 'dashboard';
(async () => {
  const rows = [];
  for (const rate of (process.env.RATES || '1,4').split(',').map(Number)) {
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    const cdp = await page.context().newCDPSession(page);
    await page.evaluate(([k]) => {
      localStorage.removeItem('nm-buddy-spots');
      const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true }));
    }, [KIND]);
    await page.evaluate((t) => revealTab(t), TAB);
    await page.waitForTimeout(5000);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    await page.evaluate(() => {
      window.__rig = 0; window.__loaf = 0; window.__loafN = 0; window.__rigT = []; window.__loafE = [];
      const orig = atlasRigFrame;
      atlasRigFrame = function (...a) { window.__rig += 1; window.__rigT.push(Math.round(performance.now() % 100000)); return orig.apply(this, a); };
      new PerformanceObserver((l) => { for (const e of l.getEntries()) { window.__loaf += e.duration; window.__loafN += 1; window.__loafE.push([Math.round(e.startTime % 100000), Math.round(e.duration), e.scripts.map((x) => x.sourceFunctionName + '@' + x.sourceURL.split('/').pop() + ':' + x.sourceCharPosition + ' ' + Math.round(x.duration)).join(' | ')]); } }).observe({ type: 'long-animation-frame', buffered: false });
    });
    await cdp.send('Performance.enable');
    const met = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    const m0 = await met();
    await page.waitForTimeout(MS);
    const m1 = await met();
    const here = await page.evaluate(() => ({ rig: window.__rig, loaf: window.__loaf, loafN: window.__loafN, rigT: window.__rigT, loafE: window.__loafE, anims: document.getAnimations().length,
      running: document.getAnimations().filter((a) => a.playState === 'running').length }));
    // off tab
    await page.evaluate((t) => switchTab(t), OTHER);
    await page.waitForTimeout(Number(process.env.OFFWAIT || 300));
    const off = await page.evaluate(() => { const b = document.getElementById('nm-buddy'); if (!b) return null; const cs = getComputedStyle(b);
      return { hiddenAttr: b.hidden, display: cs.display, visibility: cs.visibility, opacity: cs.opacity, cls: b.className, anims: document.getAnimations().length,
        running: document.getAnimations().filter((a) => a.playState === 'running').length }; });
    const s = MS / 1000;
    if (process.env.RAW) rows.push({ rigT: here.rigT, loafE: here.loafE });
    rows.push({ rate, taskMsPerSec: +((m1.TaskDuration - m0.TaskDuration) / (MS / 1000) * 1000).toFixed(0), stylePerSec: +((m1.RecalcStyleCount - m0.RecalcStyleCount) / (MS / 1000)).toFixed(0), rigPerSec: +(here.rig / s).toFixed(2), loafMsPerSec: +(here.loaf / s).toFixed(1), loafN: here.loafN, anims: here.anims, running: here.running, off });
    await browser.close();
  }
  console.log(JSON.stringify(rows, null, 1));
})();
