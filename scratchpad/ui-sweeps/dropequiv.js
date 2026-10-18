// companion-1018: where a carried companion lands (drop: slow let-go; throw: a flick) at fixed points, for
// the code as it is and, with BEFORE_DIR, as it was: the two must agree (reads moved before writes, same spots).
const { boot, routeBefore } = require('./lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await routeBefore(ctx, page);
  const out = [];
  for (const kind of (process.env.KINDS || 'atlas,me').split(',')) {
    await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, kind);
    await page.evaluate(() => revealTab('notes'));
    await page.waitForTimeout(3000);
    for (const [sx, sy, tx, ty, flick] of [[180, 380, 600, 300, 0], [180, 380, 900, 600, 0], [300, 200, 200, 700, 0], [180, 380, 700, 380, 1], [900, 500, 300, 420, 1]]) {
      await page.evaluate(([x, y]) => { nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'float', legs: '', x, y }, true); nmb.placedAt = Date.now(); }, [sx, sy]);
      await sleep(700);
      const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
      await page.mouse.move(f[0], f[1]); await page.mouse.down();
      for (let i = 1; i <= 20; i += 1) { await page.mouse.move(f[0] + (tx - sx) * i / 20, f[1] + (ty - sy) * i / 20); await sleep(16); }
      if (flick) for (let i = 1; i <= 4; i += 1) { await page.mouse.move(f[0] + (tx - sx) + (tx > sx ? 1 : -1) * i * 60, f[1] + (ty - sy) - i * 4); await sleep(16); } else await sleep(250);
      await page.mouse.up();
      await sleep(2800);
      out.push(kind + ' ' + JSON.stringify(await page.evaluate(() => ({ x: Math.round(nmb.x), y: Math.round(nmb.y), perch: nmb.perch, pose: nmb.pose, legs: nmb.legs, thrown: !!nmb.thrown }))));
    }
  }
  console.log(out.join('\n'));
  await browser.close();
})();
