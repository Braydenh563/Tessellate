// INBOX 882 (the owner: "I try throwing the companion across the screen and
// it just goes back to the same side"). Flicks the companion across the
// window with a real pointer, both ways, on the desktop (mouse) and the phone
// (touch, through CDP), and records: where it started, the release speed the
// pointer had, where it came to rest, where it is 10 s later and after a tab
// switch away and back. A throw passes when it rests at least a third of the
// window from where it started, on the side it was thrown to, and stays there.
// Env: BASE, PHONE=1 for the phone only, DESK=1 for the desktop only,
// STEP, RISE (px a move across and up), REDUCED=1 to run with Reduce motion (a crossfade to the same landing).
const { boot, setBuddy } = require('./lib.js');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function run(phone) {
  const opts = phone ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1440, height: 900 } };
  if (process.env.REDUCED) opts.reducedMotion = 'reduce';
  const { browser, page, ctx } = await boot(opts);
  const W = opts.viewport.width;
  const fails = [];
  await setBuddy(page, 'me');
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); revealTab('notes'); });
  await page.waitForTimeout(3000);
  const cdp = phone ? await ctx.newCDPSession(page) : null;
  const faceMid = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  // Real pointer input, mouse or touch: down, moves (`gap` ms apart), and
  // up straight after the last move (let go while still moving) or after
  // `hold` ms still.
  const press = async (pts, gap, hold = 0) => {
    if (phone) {
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: pts[0][0], y: pts[0][1] }] });
      for (const [i, p] of pts.slice(1).entries()) { if (i && gap) await sleep(gap); await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: p[0], y: p[1] }] }); }
      if (hold) await sleep(hold);
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    } else {
      await page.mouse.move(pts[0][0], pts[0][1]);
      await page.mouse.down();
      for (const [i, p] of pts.slice(1).entries()) { if (i && gap) await sleep(gap); await page.mouse.move(p[0], p[1]); }
      if (hold) await sleep(hold);
      await page.mouse.up();
    }
  };
  // Until it has stopped moving (its beat may walk it to a perch first):
  // the face read three times 150 ms apart, the same each time.
  const still = async () => {
    let was = '';
    let same = 0;
    for (let i = 0; i < 40 && same < 2; i += 1) {
      await page.waitForTimeout(150);
      const now = JSON.stringify((await faceMid()).map(Math.round));
      same = now === was ? same + 1 : 0;
      was = now;
    }
  };
  // Set there as a drop sets it: a place of yours, kept as the tab's spot,
  // so its beat leaves it there (a real drag to the start was taken by the
  // phone's New note button, or fell to the bar and stepped aside).
  const put = async (x, y) => {
    await page.evaluate(([px, py]) => {
      const spot = { kind: 'yours', pose: 'float', legs: '', x: px, y: py };
      nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true);
      nmb.placedAt = Date.now();
      const spots = nameMarkBuddySpots();
      spots[nameMarkBuddyTab()] = nameMarkBuddySpotFor(spot);
      nameMarkBuddyKeepSpots(spots);
    }, [x, y]);
    await still();
  };
  await page.evaluate(() => { window.__ev = []; document.addEventListener('pointermove', (e) => __ev.push([e.clientX, e.clientY, performance.now()]), true); document.addEventListener('pointerup', () => { window.__up = performance.now(); }, true); document.addEventListener('pointerdown', () => { window.__ev = []; if (typeof nmb !== 'undefined') nmb.thrown = null; }, true); });
  const where = () => page.evaluate(() => { const r = document.getElementById('nm-buddy').getBoundingClientRect(); return { x: Math.round(nmb.x), y: Math.round(nmb.y), drawn: Math.round(r.left), perch: nmb.perch }; });
  const results = [];
  for (const dir of [1, -1]) {
    const sx = dir > 0 ? Math.round(W * 0.12) : Math.round(W * 0.88 - 60);
    const sy = Math.round(opts.viewport.height * 0.45);
    await put(sx, sy);
    const start = await where();
    const f = await faceMid();
    // A short flick, let go while still moving: five moves of 70px (45 on
    // the phone) a frame apart. The pointer itself travels 350px (225).
    // STEP and RISE (px a move, across and up) for a harder or higher throw.
    const step = Number(process.env.STEP) || (phone ? 45 : 70);
    const rise = Number(process.env.RISE) || 6;
    const pts = [f];
    for (let i = 1; i <= 5; i += 1) pts.push([f[0] + dir * i * step, f[1] - i * rise]);
    await press(pts, 16);
    // [vx, vy, ms measured over, ms from the last move to the let-go]:
    // the speed the pointer had over its last 80 ms (or its last two moves,
    // on a machine slower than that), measured in the page; and what the
    // app made of it (`nmb.thrown`, unset on a build without the flight).
    const release = await page.evaluate(() => { const s = __ev; const last = s[s.length - 1]; if (!last) return null; let i = s.length - 1; while (i > 0 && last[2] - s[i - 1][2] <= 80) i -= 1; if (i === s.length - 1 && i > 0) i -= 1; const first = s[i]; const dt = last[2] - first[2]; return dt > 0 ? [+((last[0] - first[0]) / dt).toFixed(2), +((last[1] - first[1]) / dt).toFixed(2), Math.round(dt), Math.round((window.__up || 0) - last[2])] : null; });
    await page.waitForTimeout(50);
    const thrown = await page.evaluate(() => (typeof nmb !== 'undefined' && nmb.thrown ? nmb.thrown.v : null));
    const path = [];
    for (let i = 0; i < 8; i += 1) { await page.waitForTimeout(200); path.push((await where()).drawn); }
    const rest = await where();
    await page.waitForTimeout(10000);
    const later = await where();
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(1500);
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(2500);
    const back = await where();
    const r = { dir: dir > 0 ? 'right' : 'left', startX: start.x, release, thrown, path, restX: rest.x, restPerch: rest.perch, after10sX: later.x, afterTabX: back.x };
    results.push(r);
    const travelled = (x) => dir * (x - start.x);
    for (const [k, x] of [['rest', rest.x], ['after 10s', later.x], ['after tab switch', back.x]]) {
      if (travelled(x) < W / 3) fails.push(`${phone ? 'phone' : 'desk'} ${r.dir}: ${k} x ${x} from ${start.x}`);
    }
  }
  await browser.close();
  return { phone, results, fails };
}
(async () => {
  const all = [];
  if (!process.env.PHONE) all.push(await run(false));
  if (!process.env.DESK) all.push(await run(true));
  const fails = all.flatMap((a) => a.fails);
  for (const a of all) for (const r of a.results) console.log(a.phone ? 'phone' : 'desk', JSON.stringify(r));
  for (const x of fails) console.log(x);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
