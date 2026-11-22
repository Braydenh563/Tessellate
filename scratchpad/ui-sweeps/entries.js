// Brief 88, the owner: "screen entries". Brings the companion in
// (`nameMarkBuddyEnter`) ROUNDS times at three kinds of place: standing
// mid-window, standing near the left side, on the bottom bar. Records the
// way it came each time, where it was first drawn (off the window for a
// fall or a tumble), and that it ends on its perch, upright and opaque.
// PASS when each place shows three ways or more with no way twice running,
// and every entrance ends on its perch. KIND (atlas, me).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.waitForTimeout(4000);
  const top = await page.evaluate(() => document.getElementById('status-bar').getBoundingClientRect().top);
  const rounds = Number(process.env.ROUNDS || 6);
  let bad = 0;
  for (const [name, x, y] of [['mid', 640, 300], ['left', 60, 300], ['bar', 900, Math.round(top - 92 + 1)]]) {
    const ways = [];
    for (let i = 0; i < rounds; i += 1) {
      const r = await page.evaluate(async ([x, y, bar]) => {
        const b = document.getElementById('nm-buddy');
        DOMTokenList.prototype.remove.call(b.classList, 'nmb-sleep', 'nmb-drowsy');
        const spot = { kind: bar ? 'bar' : 'yours', pose: 'stand', legs: '', x, y: bar ? Math.round(document.getElementById('status-bar').getBoundingClientRect().top - NMB_FEET + 1) : y };
        nameMarkBuddyMoveTo(b, spot, true);
        await new Promise((r) => requestAnimationFrame(() => r()));
        const how = nameMarkBuddyEnter(b, spot);
        const first = b.getBoundingClientRect();
        // Settled: every finite animation on it done, then two frames.
        const t0 = performance.now();
        while (performance.now() - t0 < 6000 && b.getAnimations({ subtree: true }).some((a) => a.playState === 'running' && Number.isFinite(a.effect?.getComputedTiming().endTime))) {
          await new Promise((r) => setTimeout(r, 50));
        }
        await new Promise((r) => setTimeout(r, 120));
        const last = b.getBoundingClientRect();
        const char = getComputedStyle(b.querySelector('.nm-buddy-char'));
        return { how, first: [Math.round(first.left), Math.round(first.top)], at: [Math.round(last.left - nmb.x), Math.round(last.top - nmb.y)], rot: char.rotate, op: getComputedStyle(b).opacity };
      }, [x, y, name === 'bar']);
      ways.push(r.how);
      const settled = Math.abs(r.at[0]) <= 1 && Math.abs(r.at[1]) <= 1 && Number(r.op) > 0.99 && (r.rot === 'none' || /^-?0(\.0+)?deg$/.test(r.rot) || Math.abs(parseFloat(r.rot)) < 1);
      if (!settled) bad += 1;
      console.log(`${settled ? 'ok  ' : 'BAD '} ${name} ${r.how}: first drawn at ${r.first}, ended ${r.at} off its perch, turn ${r.rot}, opacity ${r.op}`);
    }
    const distinct = new Set(ways).size;
    const repeats = ways.filter((w, i) => i && w === ways[i - 1]).length;
    if (distinct < 3 || repeats) bad += 1;
    console.log(`${distinct >= 3 && !repeats ? 'ok  ' : 'BAD '} ${name}: ${distinct} ways, ${repeats} repeats (${ways.join(' ')})`);
  }
  console.log(bad ? 'FAIL' : 'PASS');
  await browser.close();
})();
