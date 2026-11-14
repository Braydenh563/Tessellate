// The owner, 2026-09-27: "the companion was sleeping but then when I clicked
// a different tab, for a split second I saw it shoot back up look alive
// suddenly and look surprised". Puts the companion to sleep (its own tick,
// lying down if there is room), switches tab, stays for it to follow, and
// comes back, sampling every animation frame: it must be asleep (its sleep
// class or a nap or lie act), its eyes shut, never walking, and must be
// carried across (nameMarkBuddyMoveTo's "Carried asleep" crossfade: neither
// nameMarkBuddyEnter nor the walking entry runs, so `nmb.enteredBy` is not
// written; the old check `enteredBy === "asleep"` read a value the sleeper
// path no longer sets). Then pokes it three times, 1.5s apart, and reads each
// answer 700ms after the click (a poke waits 280ms for a second click, so
// 150ms read the one before): a slow wake, a pout, then a gentle answer.
// Grumpy is no longer the third poke: it needs five pokes in twenty seconds
// and then one time in four (INBOX 705, `nameMarkBuddyClickReaction`).
// Env: KIND (atlas), BASE. Exits 1 on any awake frame across the switches,
// an entry run for the sleeper, or a poke sequence other than wake, pout,
// then neither of those nor grumpy.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (k) => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'atlas');
  await page.evaluate(() => switchTab('dashboard'));
  await page.waitForTimeout(4500);
  await page.evaluate(() => {
    nmb.lastInput = Date.now() - 9 * 60 * 1000;
    nmb.awakeUntil = 0;
    nmb.tick();
  });
  await page.waitForTimeout(3500);
  console.log('asleep as:', JSON.stringify(await page.evaluate(() => ({ sleep: document.getElementById('nm-buddy').classList.contains('nmb-sleep'), act: nmb.act, pose: nmb.pose }))));
  //: Frames sampled in the page, every animation frame, so nothing is
  //: missed between two evaluates.
  await page.evaluate(() => {
    window.__frames = [];
    const buddy = document.getElementById('nm-buddy');
    const look = () => {
      const cs = getComputedStyle(buddy);
      const eye = buddy.querySelector('.atl-eye-open');
      window.__frames.push({
        t: Math.round(performance.now()),
        shown: cs.visibility !== 'hidden' && Number(cs.opacity) > 0.02,
        asleep: buddy.classList.contains('nmb-sleep') || nmb.act === 'nap' || nmb.act === 'lie',
        open: eye ? Number(getComputedStyle(eye).opacity) : 0,
        walking: buddy.classList.contains('nmb-walking'),
        startle: buddy.classList.contains('nmb-act-startle'),
        tab: nmb.tab,
      });
      if (window.__frames.length < 2400) requestAnimationFrame(look);
    };
    requestAnimationFrame(look);
  });
  await page.evaluate(() => {
    window.__entries = 0;
    for (const n of ['nameMarkBuddyEnter', 'nameMarkBuddyWalkEnter']) {
      const o = window[n];
      window[n] = function () { window.__entries += 1; return o.apply(this, arguments); };
    }
  });
  await page.click('[data-tab="notes"]');
  await page.waitForTimeout(3800);
  await page.click('[data-tab="dashboard"]');
  await page.waitForTimeout(3800);
  const entries = await page.evaluate(() => window.__entries);
  const frames = await page.evaluate(() => window.__frames);
  const awake = frames.filter((f) => f.shown && (!f.asleep || f.open > 0.2 || f.walking || f.startle));
  console.log(`tab switches: ${frames.length} frames, ${awake.length} shown awake, walking or startled; entry runs ${entries}`, awake[0] ? JSON.stringify(awake[0]) : '');
  let bad = awake.length > 0 || entries > 0;
  // The pokes.
  const got = [];
  for (let i = 0; i < 3; i += 1) {
    const at = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    await page.mouse.click(at.x, at.y);
    await page.waitForTimeout(700);
    //: What it answered is `nmb.lastHow`: a pout's class lasts three seconds, so it would
    //: still show on the poke after it.
    got.push(await page.evaluate(() => nmb.lastHow || 'none'));
    await page.waitForTimeout(800);
  }
  console.log('three pokes:', got.join(', '));
  if (got[0] !== 'wake' || got[1] !== 'pout' || ['grumpy', 'pout', 'none'].includes(got[2])) bad = true;
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
