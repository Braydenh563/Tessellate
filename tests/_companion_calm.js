// The companion at rest under the system's reduce-motion hint (ledger L741): do the calm loops run, and what do they cost in
// restyles a minute. Prints one JSON object. Env: BASE, SWEEPS (scratchpad/ui-sweeps), SEC (window, 20).
const { boot, setBuddy } = require(process.env.SWEEPS + '/lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const SEC = Number(process.env.SEC || 20);
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', reducedMotion: 'reduce' });
  await setBuddy(page, 'atlas');
  await page.evaluate(() => revealTab('notes'));
  await page.waitForSelector('#nm-buddy .nm-buddy-face', { state: 'attached', timeout: 15000 });
  await sleep(2500);
  await page.evaluate(() => { if (document.getElementById('confirm-name-1')) [...document.querySelectorAll('button')].find((b) => /Don.t check/.test(b.innerText))?.click(); });
  await page.evaluate(() => nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'stand', legs: '', x: 300, y: 600 }, true));
  await sleep(4000);
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const info = await page.evaluate(() => {
    const body = document.querySelector('#nm-buddy .atl-lw-body');
    // The loops may be held at rest by the app's own rest rule (atlas-life.js), so what counts is that they are declared.
    const hop = document.querySelector('#nm-buddy .nm-live.atl-figure-box');
    return {
      motion: document.documentElement.dataset.motion,
      calm: document.documentElement.dataset.atlasCalm || '',
      body: body ? getComputedStyle(body).animationName : '',
      anims: document.getAnimations().length,
      breath: (() => { const e = document.querySelector('#nm-buddy .atl-lw-breathe'); return e ? getComputedStyle(e).animationName : ''; })(),
      mood: hop?.dataset.atlasMood || '',
    };
  });
  const a = await m();
  await sleep(SEC * 1000);
  const b = await m();
  const per = 60 / SEC;
  console.log(JSON.stringify({ ...info, recalcPerMin: Math.round((b.RecalcStyleCount - a.RecalcStyleCount) * per), layoutPerMin: Math.round((b.LayoutCount - a.LayoutCount) * per) }));
  await browser.close();
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
