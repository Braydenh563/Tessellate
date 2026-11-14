// No shipped Atlas look draws legs (`legs: false`), so the leg layers are
// switched on here (the masculine spec's flag, in the page) to check the
// layers a look with legs gets: for ROUTE (leap by default) it prints the
// style recalcs and ms of one move, and with OUT_DIR it writes frames of the
// move paused at fixed times (AT, ms, comma list) so a base and a change can
// be diffed with `companionshots.js diff`. Env: BASE, ROUTE, OUT_DIR, AT, REPS.
const fs = require('fs');
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const metric = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
  await page.evaluate(async () => {
    localStorage.setItem('atlas-look', 'masculine'); localStorage.removeItem('nm-buddy-spots');
    const spec = ATLAS_LOOKS.masculine; spec.legs = true; delete spec.legPaths;
    prefs.set('avatar-buddy', 'me'); await ensureModule('characters'); syncNameMarkBuddy();
  });
  await page.waitForTimeout(500);
  await page.evaluate(async () => { prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.waitForTimeout(3000);
  const route = process.env.ROUTE || 'leap';
  const info = await page.evaluate((route) => {
    clearTimeout(nmb.timer);
    window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
    window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
    window.nameMarkBuddyRoute = () => route;
    window.nameMarkBuddyPickVariant = () => 0;
    const buddy = document.getElementById('nm-buddy');
    return { legRoots: buddy.querySelectorAll('svg.nmb-leg').length, legBoxes: buddy.querySelectorAll('.atl-lw-leg-l, .atl-lw-leg-r').length };
  }, route);
  console.log('legs', JSON.stringify(info));
  const rows = [];
  for (let i = 0; i < Number(process.env.REPS || 4); i += 1) {
    const from = i % 2 ? [560, 380] : [400, 420]; const to = i % 2 ? [400, 420] : [560, 380];
    await page.evaluate(([f]) => { const b = document.getElementById('nm-buddy'); nameMarkBuddyRide(null, f[0], f[1]); nameMarkBuddyMoveTo(b, { kind: 'card', pose: 'stand', legs: '', x: f[0], y: f[1] }, true); }, [from]);
    await page.waitForTimeout(900);
    const a = await metric();
    await page.evaluate(async ([t]) => { nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'card', pose: 'stand', legs: '', x: t[0], y: t[1] }); await new Promise((r) => setTimeout(r, 2000)); }, [to]);
    const b = await metric();
    rows.push({ recalcMs: +((b.RecalcStyleDuration - a.RecalcStyleDuration) * 1000).toFixed(1), recalcs: b.RecalcStyleCount - a.RecalcStyleCount });
  }
  const mean = (k) => +(rows.reduce((s, r) => s + r[k], 0) / rows.length).toFixed(1);
  console.log(route, 'move 2s: recalcMs', mean('recalcMs'), 'recalcs', mean('recalcs'), JSON.stringify(rows));
  if (process.env.OUT_DIR) {
    fs.mkdirSync(process.env.OUT_DIR, { recursive: true });
    for (const at of (process.env.AT || '200,450,700').split(',').map(Number)) {
      await page.evaluate(() => { const b = document.getElementById('nm-buddy'); nameMarkBuddyRide(null, 400, 420); nameMarkBuddyMoveTo(b, { kind: 'card', pose: 'stand', legs: '', x: 400, y: 420 }, true); });
      await page.waitForTimeout(1500);
      await page.evaluate(([at]) => {
        window.nameMarkBuddyTempo = () => {}; clearTimeout(nmbTempo.timer); nmbTempo.anims = [];
        const buddy = document.getElementById('nm-buddy');
        nameMarkBuddyMoveTo(buddy, { kind: 'card', pose: 'stand', legs: '', x: 560, y: 380 });
        for (const a of buddy.getAnimations({ subtree: true })) { a.pause(); a.currentTime = at; }
      }, [at]);
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${process.env.OUT_DIR}/legs-${route}-${at}.png`, clip: { x: 330, y: 330, width: 330, height: 220 } });
      console.log('shot', route, at);
    }
  }
  await browser.close();
})();
