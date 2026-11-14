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
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'me');
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); document.documentElement.dataset.avatarFollow = 'on'; });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3000);
  const put = (x, y) => page.evaluate(([px, py]) => { const b = document.getElementById('nm-buddy'); nameMarkBuddyMoveTo(b, { kind: 'air', pose: 'stand', x: px, y: py }, true); clearTimeout(nmb.timer); nmb.placeTimer = 1; nameMarkBuddyAct(''); clearTimeout(nmb.timer); }, [x, y]);
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
    // The look is written on the elements that read it (`nameMarkBuddyAim.readers`), not on #nm-buddy (avatars.js, 'The look is written on what reads it').
    eyes.push(await page.evaluate(() => { const r = document.querySelector('#nm-buddy').querySelector(nameMarkBuddyAim.readers); return Number(r && r.style.getPropertyValue('--nmb-ex')) || 0; }));
  }
  const tracked = eyes[0] < 0 && eyes[3] > 0;
  if (!tracked) fails.push(`eyes near: ${eyes}`);
  await page.mouse.move(100, 100);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { document.documentElement.dataset.avatarFollow = 'off'; nameMarkBuddyRelease(); nmb.target = null; nmb.lastMove = null; });
  const off = [];
  // Slowly (a pointer passing, not a sudden flick, which still catches it).
  for (const dx of [-120, 120]) {
    // 24 steps in a few ms is a flick (past 1800px/s and near it is `loud`, which still catches its eye, avatars.js nameMarkBuddyNotice), so each step waits.
    const from = await page.evaluate(() => nmb.lastMove || [0, 0]);
    for (let i = 1; i <= 24; i += 1) { await page.mouse.move(from[0] + ((f[0] + dx - from[0]) * i) / 24, from[1] + ((f[1] - 40 - from[1]) * i) / 24); await page.waitForTimeout(40); }
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
  const flying = await page.evaluate(() => ({ thrown: !!(nmb.thrown && nmb.thrown.v), running: !!nmb.flight }));
  if (process.env.SCRATCH) await page.screenshot({ path: `${process.env.SCRATCH}/toss-midflight.png`, clip: { x: 250, y: 200, width: 900, height: 450 } });
  await page.waitForFunction(() => !nmb.flight, null, { timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(600);
  const landed = await page.evaluate(() => ({ to: nmb.thrown && nmb.thrown.to ? nmb.thrown.to : null, at: [Math.round(nmb.x), Math.round(nmb.y)], perch: nmb.perch, pose: nmb.pose, spots: localStorage.getItem('nm-buddy-spots') }));
  const toss = { flying, landed };
  // A throw's flight is `nmb.flight` and its plan `nmb.thrown` (companion-throw.js `nameMarkBuddyThrow`; `to` is set where it lands).
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
  const slow = await page.evaluate(() => nmb.thrown && nmb.thrown.v ? nmb.thrown.v : null);
  if (slow) fails.push('a slow let-go was tossed');
  // Still: no petting. `data-motion="reduced"` alone no longer stills it (avatars.js nameMarkBuddyMotion: its own setting decides), so use Avatar animation off.
  await page.mouse.move(100, 100);
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'off'; nmb.pettedAt = 0; nameMarkBuddyAct(''); nmb.pet(); });
  const stillPet = await page.evaluate(() => nmb.act);
  await page.evaluate(() => { delete document.documentElement.dataset.avatarMotion; });
  if (stillPet === 'wiggle') fails.push('petted while still');
  console.log(JSON.stringify({ pet, again, eyes, off, toss: { ...toss, far: Math.round(far) }, slow }));
  await browser.close();
  for (const x of fails) console.log(x);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
