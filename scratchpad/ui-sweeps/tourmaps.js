// The mind maps section of the tour on a notebook with or without a map
// (INBOX 426 y): with none, its first card says so and the map's own cards
// are not in the count; with one, the map's cards are walked.
//
//   BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/tourmaps.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  //: openTour is a stand-in until tour.js loads (lazy); load it before reading inspect.
  await page.evaluate(() => ensureModule("tour"));
  const hasMap = await page.evaluate(async () => (await openTour.inspect.context()).map != null);
  await page.evaluate(() => openTour('maps'));
  await page.waitForTimeout(2500);
  const first = await page.evaluate(() => ({
    title: document.getElementById('tour-title').textContent,
    text: document.getElementById('tour-text').textContent,
    count: document.getElementById('tour-count').textContent,
  }));
  const saysNone = /no mind map yet/.test(first.text);
  const ok = hasMap ? !saysNone : saysNone && / of 1$/.test(first.count);
  console.log(`${ok ? 'ok  ' : 'FAIL'} notebook ${hasMap ? 'has' : 'has no'} map:`, JSON.stringify(first));
  await browser.close();
  process.exitCode = ok ? 0 : 1;
})();
