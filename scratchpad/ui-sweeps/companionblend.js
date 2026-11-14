// Acts and walks end without a snap (INBOX 497, the owner: "make the atlas
// behaviour more smooth and less sudden beginning and stopping of actions").
// Starts an act on Atlas, cuts it off part way (the next act, or none), and
// samples every animation frame the screen box of each moving part under
// #nm-buddy (the arms, the character, the lower layers); reports the fastest
// any part moved (px per ms, so a slow frame is not a jump) from the act
// coming off until 300ms later, against the fastest while it ran. A cut that
// snaps moves a part further in one frame than the act ever does.
// Env: BASE, LOOK (feminine), ACTS (wave,hop,stretch,scratch,yawn),
// AT (fraction of the act, 0.4). Exits 1 when the cut moves faster than
// 1.5 times the act's own fastest, plus 0.05px/ms.
// Measured (2026-10-04, feminine): before the fix the cut jumped 7 to 22px
// in a frame against 2 to 4px a frame while the act ran.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (look) => {
    localStorage.setItem('atlas-look', look);
    prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy();
  }, process.env.LOOK || 'feminine');
  await page.waitForTimeout(3000);
  await page.evaluate(() => {
    clearTimeout(nmb.timer);
    window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
    window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyRide(null, 700, 420);
    nameMarkBuddyMoveTo(buddy, { kind: 'card', pose: 'stand', legs: '', x: 700, y: 420 }, true);
  });
  await page.waitForTimeout(800);
  let bad = 0;
  const at = Number(process.env.AT || 0.4);
  for (const act of (process.env.ACTS || 'wave,hop,stretch,scratch,yawn').split(',')) {
    const r = await page.evaluate(([act, at]) => new Promise((done) => {
      const buddy = document.getElementById('nm-buddy');
      const parts = [...buddy.querySelectorAll('.nmb-arm, .nm-buddy-char, .atl-lw-lower, .atl-layer-body')];
      const read = () => parts.map((el) => { const b = el.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; });
      const jump = (a, b) => Math.max(...a.map((x, i) => Math.max(...x.map((v, k) => Math.abs(v - b[i][k])))));
      nameMarkBuddyAct(act);
      const ms = (NAME_MARK_BUDDY_ACTS[act] || { ms: 1500 }).ms;
      const cutAt = performance.now() + ms * at;
      let last = read();
      let lastAt = performance.now();
      let run = 0;
      let cut = 0;
      let after = 0;
      let frames = 0;
      const step = () => {
        const now = performance.now();
        if (!cut && now >= cutAt) {
          cut = now;
          nameMarkBuddyAct('');
          const next = read();
          after = Math.max(after, jump(last, next) / Math.max(8, now - lastAt));
          last = next;
          lastAt = now;
          requestAnimationFrame(step);
          return;
        }
        const next = read();
        const d = jump(last, next) / Math.max(8, now - lastAt);
        if (cut) after = Math.max(after, d); else run = Math.max(run, d);
        last = next;
        lastAt = now;
        frames += 1;
        if (cut && now - cut > 300) { done({ act, run: +run.toFixed(3), cut: +after.toFixed(3), frames }); return; }
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }), [act, at]);
    const ok = r.cut <= r.run * 1.5 + 0.05;
    if (!ok) bad += 1;
    console.log(ok ? 'ok ' : 'BAD', JSON.stringify(r));
    await page.waitForTimeout(900);
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS');
  await browser.close();
  process.exitCode = bad ? 1 : 0;
})();
