// The tour follows its control when the page moves under it without a
// scroll or a resize (INBOX 426 y). Two moves are made while a step is up:
//   1. content grows above the control (a 180px block inserted before its
//      group), which moves the control with no scroll event;
//   2. the frame the tour's layers are laid out in shifts and comes back
//      (a transform on <body>, the shape "asked for 336,275, drew at
//      1128,4" came from).
// After each, within 300ms, the ring must be back around the control and
// the card off it.
//
//   BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/tourfollow.js
const { boot } = require('./lib.js');

function measure() {
  const el = openTour.inspect.run?.el;
  const spot = document.getElementById('tour-spot').getBoundingClientRect();
  const card = document.getElementById('tour-card').getBoundingClientRect();
  const t = el.getBoundingClientRect();
  const ov = Math.max(0, Math.min(card.right, t.right) - Math.max(card.left, t.left)) * Math.max(0, Math.min(card.bottom, t.bottom) - Math.max(card.top, t.top));
  return { title: openTour.inspect.run.step.title, ringOff: Math.round(Math.max(Math.abs(spot.left + 6 - t.left), Math.abs(spot.top + 6 - t.top))), cover: Math.round(ov) };
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  let bad = 0;
  // The reader has "Atlas and faces" open, as the owner had: the companion
  // step is reachable whether or not the tour opens folds itself.
  await page.evaluate(() => localStorage.setItem('settingsFolds', JSON.stringify({ 'appearance-faces': true })));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  if (await page.isVisible('#lock-password').catch(() => false)) {
    await page.fill('#lock-password', 'testpassword123');
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(3000);
  await page.evaluate(() => openTour('settings'));
  await page.waitForTimeout(1500);
  // Walk to the companion step.
  for (let i = 0; i < 6; i++) {
    const t = await page.evaluate(() => openTour.inspect.run?.step?.title);
    if (/companion/i.test(t || '')) break;
    await page.evaluate(() => openTour.inspect.next());
    await page.waitForTimeout(1200);
  }
  const before = await page.evaluate(measure);
  console.log('shown', JSON.stringify(before));
  await page.evaluate(() => {
    const row = document.getElementById('avatar-buddy-row');
    const block = document.createElement('div');
    block.id = 'tourfollow-block';
    block.style.height = '180px';
    row.parentElement.insertBefore(block, row);
  });
  await page.waitForTimeout(300);
  const grown = await page.evaluate(measure);
  const g = grown.ringOff > 2 || grown.cover > 0;
  if (g) bad++;
  console.log(`${g ? 'FAIL' : 'ok  '} content grew above the control:`, JSON.stringify(grown));
  await page.evaluate(() => document.getElementById('tourfollow-block')?.remove());
  await page.waitForTimeout(300);
  await page.evaluate(() => { document.body.style.transform = 'translate(300px, 120px)'; });
  await page.waitForTimeout(300);
  await page.evaluate(() => { document.body.style.transform = ''; });
  await page.waitForTimeout(300);
  const frame = await page.evaluate(measure);
  const f = frame.ringOff > 2 || frame.cover > 0;
  if (f) bad++;
  console.log(`${f ? 'FAIL' : 'ok  '} the layers' frame moved and came back:`, JSON.stringify(frame));
  await browser.close();
  console.log(bad ? `${bad} failing` : 'the tour follows');
  process.exitCode = bad ? 1 : 0;
})();
