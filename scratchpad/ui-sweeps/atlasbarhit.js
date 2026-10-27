// Companion hit test (brief item 3, 2026-10-27): Atlas standing on the status
// bar, its tail (6px under the soles standing) counts as hitting the bar's
// buttons. Per x along the bar: nameMarkBuddyHits for a stand on the bar's
// top (y = bar.top - NMB_FEET), and whether any bar button box is hit.
//   BASE=http://127.0.0.1:8789 node scratchpad/ui-sweeps/atlasbarhit.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 720 } });
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    const b = document.getElementById('avatar-buddy');
    b.value = 'atlas';
    b.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(2500);
  const out = await page.evaluate(() => {
    const bar = document.getElementById('status-bar').getBoundingClientRect();
    const obstacles = nameMarkBuddyObstacles(nameMarkBuddyTab());
    const onBar = obstacles.filter((o) => o.top >= bar.top);
    const y = bar.top - NMB_FEET;
    const tail = !!document.querySelector('#nm-buddy .atl-figure-box');
    const rows = [];
    for (let x = 0; x <= innerWidth - NMB_W; x += 40) {
      rows.push({ x, stand: nameMarkBuddyHits(x, y, 'stand', obstacles, ''), sit: nameMarkBuddyHits(x, bar.top - NMB_SEAT, 'sit', obstacles, '') });
    }
    const hitBy = (xx) => obstacles.filter((o) => nameMarkBuddyHits(xx, y, 'stand', [o], '')).map((o) => [Math.round(o.left), Math.round(o.top), Math.round(o.right), Math.round(o.bottom)]);
    return { hitAt1160: hitBy(1160), hitAt1200: hitBy(1200), tail, barTop: bar.top, btnTops: [...new Set(onBar.map((o) => o.top))], n: onBar.length, standHits: rows.filter((r) => r.stand).length, total: rows.length, firstHit: rows.find((r) => r.stand)?.x };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
