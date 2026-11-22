// Round 5, interactions: petted (the pointer resting on it), tossed (let go
// while moving fast: it flies on and lands on a perch near where it would
// come down; a slow let-go is an ordinary drop), and its eyes on a near
// pointer (tracking as it moves, and not at all with Faces follow the
// pointer off). Env: KIND (me), SCRATCH (a shot mid-toss). Exits 1 on any
// of them not happening, or happening when it should not.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const fails = [];
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'me');
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); document.documentElement.dataset.avatarFollow = 'on'; });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3000);
  // INBOX 1640: the companion always ends on a perch, so an open-air pin is dropped on refit; it stands on the bottom bar at x (y is unused).
  const put = (x, _y) => page.evaluate(([px, py]) => { const b = document.getElementById('nm-buddy'); const bar = nameMarkBuddyLedges().bottom; nameMarkBuddyMoveTo(b, { kind: 'bar', pose: 'stand', x: px, y: Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1) }, true); clearTimeout(nmb.timer); nmb.placeTimer = 1; nameMarkBuddyAct(''); clearTimeout(nmb.timer); }, [x, _y]);
  const faceMid = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  // Petted.
  await put(700, 420);
  await page.mouse.move(100, 100);
  let f = await faceMid();
  await page.mouse.move(f[0], f[1], { steps: 4 });
  await page.waitForTimeout(1400);
  const pet = await page.evaluate(() => ({ act: nmb.act, expr: document.getElementById('nm-buddy').dataset.expr || '' }));
  if (pet.act !== 'wiggle' || pet.expr !== 'happy') fails.push(`petted: ${JSON.stringify(pet)}`);
  await page.mouse.move(100, 100);
  await page.waitForTimeout(1200);
  await page.mouse.move(f[0], f[1], { steps: 3 });
  await page.waitForTimeout(1400);
  const again = await page.evaluate(() => nmb.act);
  if (again === 'wiggle') fails.push('petted twice inside 15s');
  await page.mouse.move(100, 100);
  // Eyes: near and moving, they track; with the setting off, they do not.
  await put(700, 420);
  await page.evaluate(() => { nameMarkBuddyRelease(); nmb.target = null; nmb.lastMove = null; });
  f = await faceMid();
  const eyes = [];
  for (const dx of [-120, -60, 60, 120]) {
    await page.mouse.move(f[0] + dx, f[1] - 40, { steps: 2 });
    await page.waitForTimeout(160);
    eyes.push(await page.evaluate(() => Number(getComputedStyle(document.getElementById('nm-buddy')).getPropertyValue('--nmb-ex')) || parseFloat(getComputedStyle(document.querySelector('#nm-buddy .nm-eyes, #nm-buddy .atl-iris')).translate) || 0));
  }
  const tracked = eyes[0] < 0 && eyes[3] > 0;
  if (!tracked) fails.push(`eyes near: ${eyes}`);
  await page.mouse.move(100, 100);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { document.documentElement.dataset.avatarFollow = 'off'; nameMarkBuddyRelease(); nmb.target = null; nmb.lastMove = null; });
  const off = [];
  // Slowly (a pointer passing, not a sudden flick, which still catches it).
  for (const dx of [-120, 120]) {
    // A real slow pass: a Playwright move is instant, and a fast pointer inside 400px is loud (avatars.js: speed over 1800), which it follows whatever the setting says.
    for (let i = 1; i <= 24; i += 1) { await page.mouse.move(f[0] + dx * (i / 24), f[1] - 40); await page.waitForTimeout(30); }
    await page.waitForTimeout(200);
    // Its eyes move only while it attends (the CSS keys the look on nmb-attend).
    off.push(await page.evaluate(() => document.getElementById('nm-buddy').classList.contains('nmb-attend')));
  }
  if (off.some(Boolean)) fails.push(`eyes with the setting off: ${off}`);
  await page.evaluate(() => { document.documentElement.dataset.avatarFollow = 'on'; });
  await page.mouse.move(100, 100);
  // Tossed: a fast pull to the right and let go at speed.
  await put(300, 420);
  f = await faceMid();
  await page.mouse.move(f[0], f[1]);
  await page.mouse.down();
  for (let i = 1; i <= 6; i += 1) { await page.mouse.move(f[0] + i * 30, f[1] - i * 6); await page.waitForTimeout(12); }
  await page.mouse.up();
  await page.waitForTimeout(150);
  // The throw (companion-throw.js) keeps `nmb.thrown` (its `to` is set when it comes down) and `nmb.flight` while it flies.
  const flying = await page.evaluate(() => ({ thrown: !!nmb.thrown, running: !!nmb.flight }));
  if (process.env.SCRATCH) await page.screenshot({ path: `${process.env.SCRATCH}/toss-midflight.png`, clip: { x: 250, y: 200, width: 900, height: 450 } });
  await page.waitForTimeout(1200);
  const landed = await page.evaluate(() => ({ at: [Math.round(nmb.x), Math.round(nmb.y)], to: nmb.thrown?.to || null, perch: nmb.perch, pose: nmb.pose, spots: localStorage.getItem('nm-buddy-spots') }));
  const toss = { flying, landed };
  const far = landed.to ? Math.hypot(landed.at[0] - landed.to[0], landed.at[1] - landed.to[1]) : Infinity;
  if (!flying.thrown || !flying.running || landed.at[0] <= 300 || far > 200 || !landed.spots || landed.spots === '{}') fails.push(`toss: ${JSON.stringify(toss)} far ${Math.round(far)}`);
  // A slow let-go is a drop, not a toss.
  await page.evaluate(() => { nmb.thrown = null; });
  await put(700, 420);
  f = await faceMid();
  await page.mouse.move(f[0], f[1]);
  await page.mouse.down();
  for (let i = 1; i <= 6; i += 1) { await page.mouse.move(f[0] + i * 10, f[1]); await page.waitForTimeout(40); }
  await page.waitForTimeout(250);
  await page.mouse.up();
  await page.waitForTimeout(900);
  const slow = await page.evaluate(() => nmb.thrown || null);
  if (slow) fails.push('a slow let-go was tossed');
  // Reduce motion: no petting. The companion reads MOTION.cause (theme-boot.js), not the attribute, so the switch goes through MOTION.apply.
  await page.mouse.move(100, 100);
  await page.evaluate(() => { MOTION.apply('off'); nmb.pettedAt = 0; nameMarkBuddyAct(''); nmb.sweep.nameMarkBuddyPet(); });
  const stillPet = await page.evaluate(() => nmb.act);
  await page.evaluate(() => { MOTION.apply('follow'); });
  if (stillPet === 'wiggle') fails.push('petted under Reduce motion');
  console.log(JSON.stringify({ pet, again, eyes, off, toss: { ...toss, far: Math.round(far) }, slow }));
  await browser.close();
  for (const x of fails) console.log(x);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
