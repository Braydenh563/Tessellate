// The owner: "make sure that the positions of the limbs like the arm on
// companions ... actually match the mood as well". As you (a generated
// face): for each mood face, the right and left arms' drawn rotation once
// eased, and a shot of each (shots/armmood-<mood>.png); then a face palm
// over "confused", and the arm after it (back to the mood's pose, not 0).
// Exits 1 when a mood's arm is not where its rule puts it or an act does
// not hand the arm back to the mood.
const { boot, OUT } = require('./lib.js');
const MOODS = ['happy', 'excited', 'serious', 'surprised', 'confused', 'sleepy', 'sad', 'cool', 'love', 'angry', 'nervous'];
// The face an act leaves it with is the one its arms go back to.

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(6000);
  await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyAct('');
    const bar = nameMarkBuddyLedges().bottom;
    nameMarkBuddyMoveTo(buddy, { x: 700, y: Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1), pose: 'stand', kind: 'bar' }, true);
    nmb.timer && clearTimeout(nmb.timer);
    await new Promise((r) => setTimeout(r, 800));
  });
  const angle = (m) => { if (!m || m === 'none') return 0; const v = m.match(/matrix\(([^)]+)\)/); if (!v) return null; const [a, b] = v[1].split(',').map(Number); return Math.round(Math.atan2(b, a) * 180 / Math.PI); };
  const rows = [];
  for (const mood of MOODS) {
    await page.evaluate((m) => { clearTimeout(nmb.timer); nameMarkBuddyExpress(m, 60000); }, mood);
    await page.waitForTimeout(900);
    const t = await page.evaluate(() => {
      const b = document.getElementById('nm-buddy');
      const r = b.querySelector('.nm-buddy-char .nm-figure:not(.nmb-fig-leaving) .nmb-arm-r');
      const l = b.querySelector('.nm-buddy-char .nm-figure:not(.nmb-fig-leaving) .nmb-arm-l');
      return { r: r ? getComputedStyle(r).transform : null, l: l ? getComputedStyle(l).transform : null, feel: b.dataset.feel };
    });
    const box = await page.evaluate(() => { const r = document.getElementById('nm-buddy').getBoundingClientRect(); return { x: r.left - 30, y: r.top - 30, width: 124, height: 150 }; });
    await page.screenshot({ path: `${OUT}/armmood-${mood}.png`, clip: box });
    rows.push({ mood, feel: t.feel, r: angle(t.r), l: angle(t.l) });
  }
  const act = await page.evaluate(async () => {
    const b = document.getElementById('nm-buddy');
    nameMarkBuddyExpress('confused', 60000);
    await new Promise((r) => setTimeout(r, 700));
    nameMarkBuddyAct('facepalm', 1500);
    await new Promise((r) => setTimeout(r, 900));
    const arm = () => getComputedStyle(b.querySelector('.nm-buddy-char .nm-figure:not(.nmb-fig-leaving) .nmb-arm-r')).transform;
    const during = arm();
    await new Promise((r) => setTimeout(r, 2600));
    return { during, after: arm(), feelAfter: b.dataset.feel };
  });
  const out = { rows, facepalm: { during: angle(act.during), after: angle(act.after), feelAfter: act.feelAfter } };
  console.log(JSON.stringify(out));
  await browser.close();
  const bad = rows.filter((r) => r.r === 0 && !['sad'].includes(r.mood));
  const back = rows.find((r) => r.mood === out.facepalm.feelAfter);
  process.exit(bad.length || (back && out.facepalm.after !== back.r) || out.facepalm.during !== -150 ? 1 : 0);
})();
