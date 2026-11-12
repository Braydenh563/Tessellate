// The companion's pupils stay in its eyes (INBOX 497, the owner: "when I
// have my cursor to the top right of the companion or atlas, the pupils
// basically go off the head and you can only see white eyes"). Atlas at
// each pose and both looks, its gaze aimed at the 8 compass points around
// it (60 and 160px away, by the real pointer) and at the window's four
// corners (by `nameMarkBuddyAim`, which is what the pointer calls); for
// every eye the pupil (`.atl-ink`) must sit inside its white (`.atl-sclera`),
// all of it, carried through every transform by the screen matrices and
// asked of the white's own fill. Env: BASE, THEME, MOODS (calm,thinking,...).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  let bad = 0;
  let worst = 0;
  const moods = (process.env.MOODS || 'calm,thinking,happy,curious').split(',');
  for (const look of ['masculine', 'feminine']) {
    await page.evaluate(async ([look]) => {
      localStorage.setItem('atlas-look', look);
      prefs.set('avatar-buddy', 'me'); await ensureModule('characters'); syncNameMarkBuddy();
    }, [look]);
    await page.waitForTimeout(300);
    await page.evaluate(async () => { prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
    await page.waitForTimeout(2200);
    await page.evaluate(() => {
      clearTimeout(nmb.timer);
      window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
      window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
    });
    for (const pose of ['stand', 'sit', 'hang', 'lie']) {
      for (const mood of moods) {
        const head = await page.evaluate(([pose, mood]) => {
          const buddy = document.getElementById('nm-buddy');
          nameMarkBuddyRide(null, 700, 420);
          nameMarkBuddyMoveTo(buddy, { kind: 'card', pose, legs: '', x: 700, y: 420 }, true);
          setAtlasMood(mood, 0, { quiet: true });
          const [cx, cy] = nmb.inner.nameMarkBuddyHeadAt();
          return [cx, cy];
        }, [pose, mood]);
        await page.waitForTimeout(400);
        const targets = [];
        for (const r of [60, 160]) {
          for (let k = 0; k < 8; k += 1) {
            const a = (k * Math.PI) / 4;
            targets.push(['ptr', Math.round(head[0] + r * Math.cos(a)), Math.round(head[1] - r * Math.sin(a))]);
          }
        }
        for (const [x, y] of [[0, 0], [1439, 0], [0, 899], [1439, 899]]) targets.push(['aim', x, y]);
        for (const [how, x, y] of targets) {
          if (how === 'ptr') await page.mouse.move(x, y, { steps: 2 });
          else await page.evaluate(([x, y]) => nameMarkBuddyAim([x, y], false), [x, y]);
          await page.waitForTimeout(how === 'ptr' ? 420 : 520);
          const eyes = await page.evaluate(() => {
            const out = [];
            for (const eye of document.querySelectorAll('#nm-buddy .atl-layer-body .atl-eye')) {
              const s = eye.querySelector('.atl-sclera');
              const i = eye.querySelector('.atl-ink');
              if (!s || !i) continue;
              if (!s.getBoundingClientRect().width) continue;
              //: Sixteen points round the pupil at 90% of its radius, carried
              //: through every transform on the way (the screen matrices),
              //: into the white's own space and asked whether they are in
              //: it: the share outside, 0 when the pupil is in its eye. A
              //: tilted head or a lying figure is measured as drawn.
              const toScreen = i.getScreenCTM();
              const toWhite = s.getScreenCTM().inverse();
              const cx = i.cx.baseVal.value;
              const cy = i.cy.baseVal.value;
              const rx = i.rx.baseVal.value * 0.9;
              const ry = i.ry.baseVal.value * 0.9;
              let outside = 0;
              for (let k = 0; k < 16; k += 1) {
                const t = (k * Math.PI) / 8;
                const p = new DOMPoint(cx + rx * Math.cos(t), cy + ry * Math.sin(t)).matrixTransform(toScreen).matrixTransform(toWhite);
                if (!s.isPointInFill(p)) outside += 1;
              }
              out.push(outside / 16);
            }
            return out;
          });
          for (const e of eyes) {
            worst = Math.max(worst, e);
            if (e > 0) { bad += 1; console.log('BAD', look, pose, mood, how, x, y, e.toFixed(2)); }
          }
        }
        await page.evaluate(() => nameMarkBuddyRelease && nameMarkBuddyRelease());
      }
    }
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS', 'worst', worst.toFixed(2));
  await browser.close();
  process.exitCode = bad ? 1 : 0;
})();
