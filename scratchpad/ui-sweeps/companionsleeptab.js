// The owner, 2026-09-27: "the companion was sleeping but then when I clicked
// a different tab, for a split second I saw it shoot back up look alive
// suddenly and look surprised". Puts the companion to sleep (its own tick,
// lying down if there is room), switches tab, stays for it to follow, and
// comes back, sampling every animation frame: it must be asleep (its sleep
// class or a nap or lie act), its eyes shut, never walking, and must come
// in by the sleeping fade ("asleep"). Then pokes it three times, 1.5s
// apart: a slow wake, a pout, then grumpy (the state machine the owner
// asked for), and reports what each poke gave.
// Env: KIND (atlas), BASE. Exits 1 on any awake frame across the switches
// or a poke sequence other than wake, pout, grumpy.
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
  await page.click('[data-tab="notes"]');
  await page.waitForTimeout(3800);
  const how = await page.evaluate(() => nmb.enteredBy);
  await page.click('[data-tab="dashboard"]');
  await page.waitForTimeout(3800);
  const how2 = await page.evaluate(() => nmb.enteredBy);
  const frames = await page.evaluate(() => window.__frames);
  const awake = frames.filter((f) => f.shown && (!f.asleep || f.open > 0.2 || f.walking || f.startle));
  console.log(`tab switches: ${frames.length} frames, ${awake.length} shown awake, walking or startled; entered by ${how}, then ${how2}`, awake[0] ? JSON.stringify(awake[0]) : '');
  let bad = awake.length > 0 || how !== 'asleep' || how2 !== 'asleep';
  // The pokes.
  const got = [];
  for (let i = 0; i < 3; i += 1) {
    const at = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    await page.mouse.click(at.x, at.y);
    await page.waitForTimeout(150);
    got.push(await page.evaluate(() => {
      const b = document.getElementById('nm-buddy');
      return b.classList.contains('nmb-grumpy') ? 'grumpy' : b.classList.contains('nmb-pout') ? 'pout' : b.classList.contains('nmb-groggy') ? 'wake' : [...b.classList].filter((c) => c.startsWith('nmb-act-')).join(' ') || 'none';
    }));
    await page.waitForTimeout(1350);
  }
  console.log('three pokes:', got.join(', '));
  if (got.join(',') !== 'wake,pout,grumpy') bad = true;
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
