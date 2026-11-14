// INBOX 426 (l): "when I press the option to stay in the same spot across
// pages for the companion, it still moves sometimes". Pins it from its own
// menu, standing on a dashboard panel, then puts it through everything that
// might move it: six tab switches, a scroll, a panel collapsing and the
// panel it stood on removed, three minutes of simulated idle with every
// timer of its own called by hand (its tick, beat, check, errands, leaving
// an edge, out of sight), a window resize and back, and a reload. Every
// 100ms, and around each step, its place in the window (its host's box and
// `nmb.x`, `nmb.y`) is read; any change is a move.
// Resizes: a pinned place keeps its distance from the window's nearest
// corner (it is a place on the window, as a desktop icon is), so while
// resized that distance is checked, and back at the old size its place is.
// Env: KIND (me), SIZES. Exits 1 on any move of its own.
const { boot, PW } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const fails = [];
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'me');
  await page.evaluate(() => localStorage.removeItem('nm-buddy-spots'));
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(3000);
  // Onto a panel, the way a drag drops it, then pinned from its menu.
  const setup = await page.evaluate(() => {
    const panel = [...document.querySelectorAll('#tab-dashboard .card, #tab-dashboard .dash-widget, #tab-dashboard .dash-quicklinks')].find((el) => { const r = el.getBoundingClientRect(); return r.width > 250 && r.top > 200 && r.top < 600; });
    if (!panel) return { error: 'no panel' };
    panel.dataset.pinPanel = '1';
    const r = panel.getBoundingClientRect();
    nameMarkBuddyIndexReset();
    const landed = nameMarkBuddyDrop(Math.round(r.left + 120), Math.round(r.top - 80));
    nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), landed, true);
    return { panel: panel.className, landed: [landed.kind, landed.pose, Math.round(landed.x), Math.round(landed.y)] };
  });
  if (setup.error) { console.log(setup.error); await browser.close(); process.exitCode = 1; return; }
  const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + 32, r.top + 40]; });
  await page.mouse.click(face[0], face[1], { button: 'right' });
  await page.waitForTimeout(250);
  await page.evaluate(() => [...nmb.menu.querySelectorAll('button')].find((b) => /Stay here/.test(b.textContent)).click());
  await page.waitForTimeout(300);
  const where = () => page.evaluate(() => {
    const r = document.getElementById('nm-buddy')?.getBoundingClientRect();
    return r ? { x: Math.round(r.left), y: Math.round(r.top), nx: Math.round(nmb.x), ny: Math.round(nmb.y), pinned: nmb.pinned, W: innerWidth, H: innerHeight } : null;
  });
  const home = await where();
  console.log('pinned', JSON.stringify({ setup, home }));
  if (!home?.pinned) fails.push('not pinned by its menu');
  // A watch every 100ms, and every move it is asked to make.
  await page.evaluate(() => {
    window.__pinMoves = [];
    const orig = window.nameMarkBuddyMoveTo;
    window.nameMarkBuddyMoveTo = function (b, spot, instant) {
      window.__pinMoves.push({ t: Math.round(performance.now()), kind: spot.kind, x: Math.round(spot.x), y: Math.round(spot.y), from: new Error().stack.split('\n').slice(2, 5).map((l) => l.trim().split(' ')[1]).join('<') });
      return orig.call(this, b, spot, instant);
    };
  });
  const same = (a, b, what) => {
    if (!a || !b) { fails.push(`${what}: no companion`); return; }
    if (Math.abs(a.x - b.x) > 1 || Math.abs(a.y - b.y) > 1 || Math.abs(a.nx - b.nx) > 1 || Math.abs(a.ny - b.ny) > 1) fails.push(`${what}: moved from ${a.x},${a.y} to ${b.x},${b.y}`);
    if (!b.pinned) fails.push(`${what}: no longer pinned`);
  };
  // 1. Six tab switches, a beat's worth apart.
  for (const tab of ['notes', 'chat', 'graph', 'reminders', 'timeline', 'dashboard']) {
    await page.evaluate((t) => revealTab(t), tab);
    await page.waitForTimeout(1500);
    same(home, await where(), `tab ${tab}`);
  }
  // 2. A scroll of the page under it.
  await page.mouse.move(720, 500);
  for (let i = 0; i < 10; i += 1) { await page.mouse.wheel(0, 60); await page.waitForTimeout(30); }
  await page.waitForTimeout(2500);
  same(home, await where(), 'scroll');
  for (let i = 0; i < 10; i += 1) { await page.mouse.wheel(0, -60); await page.waitForTimeout(30); }
  await page.waitForTimeout(800);
  // 3. A panel collapsing, then the panel it stood on gone.
  await page.evaluate(() => {
    const other = [...document.querySelectorAll('#tab-dashboard .card, #tab-dashboard .dash-widget')].find((el) => !el.dataset.pinPanel && el.getBoundingClientRect().height > 80);
    if (other) other.style.display = 'none';
  });
  await page.waitForTimeout(2500);
  same(home, await where(), 'panel collapsed');
  await page.evaluate(() => document.querySelector('[data-pin-panel]')?.remove());
  await page.waitForTimeout(3000);
  same(home, await where(), 'its panel removed');
  // 4. Three minutes of idle, simulated: every timer of its own, by hand.
  await page.evaluate(() => {
    const was = nmb.lastInput;
    nmb.lastInput = Date.now() - 3.5 * 60 * 1000;
    nmb.placedAt = 0;
    for (let i = 0; i < 6; i += 1) {
      nmb.lastAct = '';
      nmb.cool = {};
      nmb.tick();
    }
    nmb.inner.nameMarkBuddyBeat();
    nmb.inner.nameMarkBuddyCheck();
    if (typeof nmb.inner.nameMarkBuddyBellErrand === "function") nmb.inner.nameMarkBuddyBellErrand();
    if (typeof nmb.inner.nameMarkBuddyChatErrand === "function") nmb.inner.nameMarkBuddyChatErrand();
    nmb.inner.nameMarkBuddySeen(false);
    nameMarkBuddyQueuePlace();
    nameMarkBuddyCue('cheer');
    nameMarkBuddyCue('bell');
    nmb.lastInput = was;
  });
  await page.waitForTimeout(5000);
  same(home, await where(), 'three minutes idle');
  // 5. A resize and back: a place away from the edges does not move at
  // all while it fits (it used to jump by the whole change in size).
  await page.setViewportSize({ width: 1000, height: 700 });
  await page.waitForTimeout(1500);
  same(home, await where(), 'resized smaller');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1500);
  same(home, await where(), 'resized and back');
  // 6. A reload.
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (await page.$('#lock-password') && await page.isVisible('#lock-password')) {
    await page.fill('#lock-password', PW);
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(5000);
  const reloaded = await where();
  same(home, reloaded, 'reload');
  // 7. Pinned by the bottom-right corner: it keeps its distance from those
  // two edges as the window changes, and is back where it was after.
  const pinAt = async (x, y, walk) => {
    await page.keyboard.press('Escape');
    await page.evaluate(([px, py, w]) => {
      const b = document.getElementById('nm-buddy');
      localStorage.removeItem('nm-buddy-spots');
      nmb.pinned = false;
      // A real perch near the point, as a drag drops it: a pin in the open air is dropped onto one when it is next placed (`nameMarkBuddyNextSpot`, INBOX 1640), so a float is not a place anyone can pin.
      nameMarkBuddyIndexReset();
      const dd = nameMarkBuddyDrop(px, py);
      nameMarkBuddyMoveTo(b, dd, !w);
    }, [x, y, walk]);
    await page.waitForTimeout(walk ? 120 : 200);
    const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + 32, r.top + 40]; });
    const drawn = await page.evaluate(() => { const r = document.getElementById('nm-buddy').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; });
    await page.mouse.click(f[0], f[1], { button: 'right' });
    await page.evaluate(() => [...nmb.menu.querySelectorAll('button')].find((b) => /Stay here/.test(b.textContent)).click());
    await page.waitForTimeout(200);
    return { drawn, pinned: await where() };
  };
  const corner = (await pinAt(1440 - 100, 900 - 150, false)).pinned;
  await page.setViewportSize({ width: 1100, height: 760 });
  await page.waitForTimeout(1500);
  const cornerSmall = await where();
  if (Math.abs((1440 - corner.x) - (1100 - cornerSmall.x)) > 1 || Math.abs((900 - corner.y) - (760 - cornerSmall.y)) > 1) fails.push(`corner pin: ${JSON.stringify({ corner, cornerSmall })}`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1500);
  same(corner, await where(), 'corner pin, resized and back');
  // 8. Pinned while it walks: it stays where it is drawn at that moment,
  // not where it was going. The box is read, the menu opened and Stay here
  // pressed in one task, so nothing moves in between.
  await page.keyboard.press('Escape');
  const mid = await page.evaluate(async () => {
    const b = document.getElementById('nm-buddy');
    localStorage.removeItem('nm-buddy-spots');
    nmb.pinned = false;
    nameMarkBuddyMoveTo(b, { kind: 'air', pose: 'float', x: nmb.x - 300, y: nmb.y - 120 }, false);
    const going = [Math.round(nmb.x), Math.round(nmb.y)];
    await new Promise((r) => setTimeout(r, 200));
    const r0 = b.getBoundingClientRect();
    nameMarkBuddyMenu(b);
    [...nmb.menu.querySelectorAll('button')].find((x) => /Stay here/.test(x.textContent)).click();
    const r1 = b.getBoundingClientRect();
    return { going, drawn: [Math.round(r0.left), Math.round(r0.top)], pinned: [Math.round(r1.left), Math.round(r1.top)], walking: !!(nmb.anim && nmb.anim.playState === 'running') };
  });
  if (Math.abs(mid.pinned[0] - mid.drawn[0]) > 2 || Math.abs(mid.pinned[1] - mid.drawn[1]) > 2) fails.push(`pinned mid-walk: ${JSON.stringify(mid)}`);
  console.log('corner', JSON.stringify({ corner, cornerSmall }), 'mid-walk', JSON.stringify(mid));
  const moves = await page.evaluate(() => window.__pinMoves || []).catch(() => []);
  console.log('moves', JSON.stringify(moves.filter((m) => m.kind !== 'pinned' || Math.abs(m.x - home.nx) > 1 || Math.abs(m.y - home.ny) > 1)));
  await browser.close();
  for (const f of fails) console.log(f);
  console.log(fails.length ? `FAIL ${fails.length}` : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
