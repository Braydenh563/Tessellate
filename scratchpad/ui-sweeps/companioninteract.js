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
  await page.evaluate(async (k) => { await ensureModule('settingsControls'); const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'me');
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); document.documentElement.dataset.avatarFollow = 'on'; });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3000);
  // Placed where it would land when dropped there: left floating over a page it is walked off by its own look for
  // controls under it, and the pointer is then no longer on it.
  const put = (x, y) => page.evaluate(([px, py]) => { const b = document.getElementById('nm-buddy'); nameMarkBuddyIndexReset(); nameMarkBuddyMoveTo(b, nameMarkBuddyDrop(px, py), true); clearTimeout(nmb.timer); nmb.placeTimer = 1; nameMarkBuddyAct(''); clearTimeout(nmb.timer); }, [x, y]);
  const faceMid = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  // Petted.
  await put(700, 420);
  await page.mouse.move(100, 100);
  let f = await faceMid();
  await page.mouse.move(f[0], f[1], { steps: 4 });
  // Until the pat has landed (its wiggle is short, so a fixed wait can miss it on a loaded machine).
  await page.waitForFunction(() => nmb.act === 'wiggle', null, { timeout: 3000 }).catch(() => {});
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
    // The look is written on the elements that read it (nameMarkBuddyAim.readers), not on #nm-buddy.
    eyes.push(await page.evaluate(() => Number(getComputedStyle(document.querySelector(`#nm-buddy :is(${nameMarkBuddyAim.readers})`)).getPropertyValue('--nmb-ex')) || 0));
  }
  const tracked = eyes[0] < 0 && eyes[3] > 0;
  if (!tracked) fails.push(`eyes near: ${eyes}`);
  await page.mouse.move(100, 100);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { document.documentElement.dataset.avatarFollow = 'off'; nameMarkBuddyRelease(); nmb.target = null; nmb.lastMove = null; });
  const off = [];
  // Slowly (a pointer passing, not a sudden flick, which still catches it).
  for (const dx of [-120, 120]) {
    // Slowly: a pointer passing at under 400px a second, paced by the clock (24 steps in one burst on a fast
    // machine is a flick of thousands of px a second, which still catches its eye).
    const from = await page.evaluate(() => [window.__mx ?? 100, window.__my ?? 100]);
    for (let i = 1; i <= 24; i += 1) { await page.mouse.move(from[0] + ((f[0] + dx) - from[0]) * i / 24, from[1] + ((f[1] - 40) - from[1]) * i / 24); await page.waitForTimeout(30); }
    await page.evaluate(([mx, my]) => { window.__mx = mx; window.__my = my; }, [f[0] + dx, f[1] - 40]);
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
  // The let-go is read from the pointer's last 80ms and is null when it had stopped 100ms before: no wait after the last
  // move, or a loaded machine's round trip (the app saw 100ms+ on a four-core box running other sweeps) read as a slow drop.
  for (let i = 1; i <= 6; i += 1) { await page.mouse.move(f[0] + i * 30, f[1] - i * 6); if (i < 6) await page.waitForTimeout(12); }
  await page.mouse.up();
  await page.waitForTimeout(150);
  const flying = await page.evaluate(() => ({ thrown: nmb.thrown || null, running: !!nmb.flight }));
  if (process.env.SCRATCH) await page.screenshot({ path: `${process.env.SCRATCH}/toss-midflight.png`, clip: { x: 250, y: 200, width: 900, height: 450 } });
  // Until it has come down (the flight ends and its landing is recorded), not a fixed time on a loaded machine.
  await page.waitForFunction(() => !nmb.flight && nmb.thrown && nmb.thrown.to, null, { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(300);
  const landed = await page.evaluate(() => ({ at: [Math.round(nmb.x), Math.round(nmb.y)], perch: nmb.perch, pose: nmb.pose, spots: localStorage.getItem('nm-buddy-spots'), to: (nmb.thrown && nmb.thrown.to) || null }));
  const toss = { flying, landed };
  // The throw is now a gravity flight (companion-throw.js): `nmb.thrown` holds its release speed, and it comes down
  // where its plan lands it (`nmb.thrown.to`, set at the landing): it must be where it was told to land.
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
  // Reduce motion: no petting.
  await page.mouse.move(100, 100);
  await page.evaluate(() => { MOTION.apply('off'); nmb.pettedAt = 0; nameMarkBuddyAct(''); });
  // The pet itself is private to avatars.js (one closure): the pointer resting on the face is what calls it.
  f = await faceMid();
  await page.mouse.move(f[0], f[1], { steps: 4 });
  await page.waitForTimeout(1400);
  const stillPet = await page.evaluate(() => nmb.act);
  await page.evaluate(() => { MOTION.apply('follow'); });
  if (stillPet === 'wiggle') fails.push('petted under Reduce motion');
  console.log(JSON.stringify({ pet, again, eyes, off, toss: { ...toss, far: Math.round(far) }, slow }));
  await browser.close();
  for (const x of fails) console.log(x);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
