// Boredom's wander and return, run for real: bored on its perch, it goes
// off to a nearby perch (not a few steps over), and half a minute later it
// walks back home, if home is free. Reports both moves and where it ended.
// Exits 1 when it does not leave, or does not come back to within 4px.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(6000);
  const out = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyAct('');
    clearTimeout(nmb.timer);
    const home = { x: nmb.x, y: nmb.y };
    nmb.perchAt = Date.now() - 20 * 60 * 1000; nmb.keyAt = 0; nmb.lastInput = Date.now() - 60000; nmb.home = null; nmb.pointer = null;
    // The gate's roll (under 0.35 to act), then the branch's (0.65 or over:
    // wander, not a few steps), then anything.
    const rolls = [0.1, 0.9]; const r = Math.random; Math.random = () => (rolls.length ? rolls.shift() : r());
    const left = nmb.sweep.nameMarkBuddyWander(Date.now());
    Math.random = r;
    const away = { x: nmb.x, y: nmb.y, why: nmb.moveWhy, walking: buddy.classList.contains('nmb-walking') || !!(nmb.anim && nmb.anim.playState === 'running') };
    await new Promise((res) => setTimeout(res, 2500));
    nmb.home && (nmb.home.at = Date.now() - 31000);
    nameMarkBuddyAct('');
    const back = nmb.sweep.nameMarkBuddyWander(Date.now());
    const backWhy = nmb.moveWhy;
    const backMoving = !!(nmb.anim && nmb.anim.playState === 'running');
    await new Promise((res) => setTimeout(res, 2500));
    return { home, left, away, back, backWhy, backMoving, end: { x: nmb.x, y: nmb.y } };
  });
  console.log(JSON.stringify(out));
  await browser.close();
  const ok = out.left && out.away.why === 'bored: wandering off' && out.back && out.backWhy === 'back from a wander' && Math.hypot(out.end.x - out.home.x, out.end.y - out.home.y) <= 4;
  process.exit(ok ? 0 : 1);
})();
