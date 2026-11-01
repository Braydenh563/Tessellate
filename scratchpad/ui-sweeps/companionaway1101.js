// Row 17, the off-tab half: the companion held away (its arrival timer cleared)
// for MS ms at RATE x CPU; CDP task, script, layout and style-recalc deltas per
// second, live animations by playState, and the away state's computed style.
//   BASE=http://127.0.0.1:8784 RATE=4 node scratchpad/ui-sweeps/companionaway1101.js
const { boot } = require('./lib.js');
const MS = Number(process.env.MS || 6000);
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); revealTab('chat'); });
  await page.waitForTimeout(5000);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.env.RATE || 4) });
  await page.evaluate(async () => { switchTab('dashboard'); await new Promise((r) => setTimeout(r, 150)); clearTimeout(nmb.awayTimer); });
  await page.waitForTimeout(1000);
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const a = await m(); await page.waitForTimeout(MS); const b = await m();
  const s = MS / 1000, d = (k) => +(((b[k] - a[k]) / s) * (k.endsWith('Duration') ? 1000 : 1)).toFixed(1);
  const st = await page.evaluate(() => { const e = document.getElementById('nm-buddy'); const c = getComputedStyle(e); const an = document.getAnimations();
    return { cls: e.className, visibility: c.visibility, display: c.display, opacity: c.opacity, anims: an.length, running: an.filter((x) => x.playState === 'running').length,
      buddyRunning: an.filter((x) => x.playState === 'running' && x.effect.target.closest('#nm-buddy')).length }; });
  console.log(JSON.stringify({ rate: Number(process.env.RATE || 4), taskMsPerSec: d('TaskDuration'), scriptMsPerSec: d('ScriptDuration'), layoutMs: d('LayoutDuration'), styleMs: d('RecalcStyleDuration'), recalcPerSec: d('RecalcStyleCount'), ...st }));
  await browser.close();
})();
