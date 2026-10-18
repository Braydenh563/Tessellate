// INBOX 1300 C01: a companion sent from a ledge to a peek over the bottom bar
// (a throw that lands, then falls to the bar) must travel whole and tuck in
// only when it arrives. Samples data-legs and the figure's sink every frame
// of the fall; BEFORE=1 replays the old order (tucked at the start).
// Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true })); } revealTab('notes'); });
  await page.waitForTimeout(3000);
  const out = await page.evaluate(async (before) => {
    if (before) nameMarkBuddyLegsNow = (s) => s.legs || '';
    const buddy = document.getElementById('nm-buddy');
    const bar = document.getElementById('status-bar').getBoundingClientRect();
    nameMarkBuddyMoveTo(buddy, { kind: 'yours', pose: 'sit', legs: '', x: 600, y: 300 }, true);
    await new Promise((r) => setTimeout(r, 400));
    const spot = { kind: 'yours', pose: 'sit', legs: 'peek', x: 600, y: bar.top - NMB_SEAT, falls: true, edge: { el: document.getElementById('status-bar'), type: 'top', kind: 'bar', y: bar.top } };
    nameMarkBuddyMoveTo(buddy, spot);
    const char = buddy.querySelector('.nm-buddy-char');
    const frames = [];
    const t0 = performance.now();
    while (performance.now() - t0 < 1600) {
      await new Promise((r) => requestAnimationFrame(r));
      const running = nmb.anim && nmb.anim.playState === 'running';
      frames.push({ t: Math.round(performance.now() - t0), running, legs: buddy.dataset.legs, sink: Number.parseFloat(String(getComputedStyle(char).translate).split(' ')[1]) || 0 });
    }
    const moving = frames.filter((f) => f.running);
    return {
      route: buddy.dataset.route,
      movingFrames: moving.length,
      tuckedWhileMoving: moving.filter((f) => f.legs === 'peek').length,
      maxSinkWhileMoving: Math.max(0, ...moving.map((f) => f.sink)),
      legsAtEnd: frames.at(-1).legs,
      sinkAtEnd: frames.at(-1).sink,
    };
  }, !!process.env.BEFORE);
  console.log(JSON.stringify(out));
  await browser.close();
})();
