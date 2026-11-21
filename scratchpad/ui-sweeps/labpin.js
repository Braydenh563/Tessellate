// The owner: "on the avatar lab, it keeps reverting my selected motion and
// goes to sleep standing with a night cap". Opens tools/avatar-lab.html,
// asks every Atlas on the page for the sleepy mood as atlas.js's own idle
// clock would (setAtlasMood), clicks the page (a start while sleepy), and
// reads each specimen's mood after; then turns Live behaviour on and does
// the same. Also reads the night cap on the standing and sitting sleep
// cards. Exits 1 when a specimen's mood moves with Live off, or a standing
// card wears the cap.
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8781';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await page.goto(`${BASE}/tools/avatar-lab.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const moods = () => page.evaluate(() => [...new Set([...document.querySelectorAll('.nm-atlas')].map((s) => s.dataset.atlasMood || ''))].join(','));
  const before = await moods();
  await page.evaluate(() => setAtlasMood('sleepy'));
  await page.mouse.click(5, 5);
  await page.waitForTimeout(600);
  const pinned = await moods();
  const caps = await page.evaluate(() => [...document.querySelectorAll('#nm-buddy')].map((h) => ({ pose: h.dataset.pose, cls: h.className, cap: getComputedStyle(h.querySelector('.nm-atlas') || h).getPropertyValue('--atl-nightcap').trim() })).filter((c) => /sleep|drowsy|night/.test(c.cls)));
  await page.click('#live');
  await page.evaluate(() => setAtlasMood('sleepy'));
  await page.waitForTimeout(400);
  const live = await moods();
  console.log(JSON.stringify({ before, pinnedAfterSleepyAndClick: pinned, live, caps }));
  await browser.close();
  const standingCap = caps.some((c) => c.pose !== 'sit' && c.cap === '1');
  process.exit(pinned !== before || !live.includes('sleepy') || standingCap ? 1 : 0);
})();
