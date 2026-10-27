// INBOX 1402 (the owner, 2026-10-27): "ill trow the companions sometimes but
// then it tll fly back to some position someitmes across the screen".
// Real pointer flicks of the companion (Atlas and "You") in several
// directions and speeds, at 1280x720, 1440x900 and 390x844, on the
// dashboard and the notes tab. For each: where the flight came to rest
// (`nmb.thrown.to`), where it settled once the landing's move was over,
// and where it is 5s and 15s later; the furthest it went from where it
// settled in those 15s; every `nameMarkBuddyMoveTo` after the flight with
// the caller that asked for it; and, after a reload, how far the restored
// place is from where it settled.
// Env: BASE, SIZES ("1280x720,1440x900,390x844"), KINDS ("atlas,me"),
// TABS ("dashboard,notes"), HOLD (ms after settling, 15000), RELOAD (1).
const { boot } = require('./lib.js');
const SIZES = (process.env.SIZES || '1280x720,1440x900,390x844').split(',').map((s) => s.split('x').map(Number));
const KINDS = (process.env.KINDS || 'atlas,me').split(',');
const TABS = (process.env.TABS || 'dashboard,notes').split(',');
const HOLD = Number(process.env.HOLD || 15000);
// DIRECT=1 (the default): `nameMarkBuddyThrow` at each flick's speed with
// seeded rolls, the same throw before and after; DIRECT=0: real mouse flicks.
const DIRECT = process.env.DIRECT !== '0';
// [name, dx, dy] per 16ms step for five steps: the flick's direction and speed.
const FLICKS = [
  ['up-left fast', -50, -40], ['up-right fast', 50, -40], ['up slow', 0, -22],
  ['left fast', -70, -6], ['right fast', 70, -6], ['down-right', 30, 25], ['left slow', -20, -4],
];

async function face(page) {
  return page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face')?.getBoundingClientRect(); return r ? [r.left + r.width / 2, r.top + r.height / 2] : null; });
}

async function one(page, flick, from) {
  await page.evaluate(([x, y]) => {
    const buddy = document.getElementById('nm-buddy');
    nmb.flight?.stop();
    if (nmb.act) nameMarkBuddyAct('');
    nameMarkBuddyMoveTo(buddy, { kind: 'yours', pose: 'float', legs: '', x, y }, true);
    nmb.thrown = null;
    window.__moves = [];
  }, from);
  await page.waitForTimeout(700);
  const f = await face(page);
  if (!f) return { error: 'no face' };
  await page.evaluate(() => { window.__moves = []; });
  if (DIRECT) {
    // The same throw every run: the flick's speed in px per ms, its rolls
    // seeded (companion-throw.js's `companionThrowSeed`).
    await page.evaluate(([vx, vy, seed]) => {
      companionThrowSeed.seed = seed;
      nameMarkBuddyThrow(document.getElementById('nm-buddy'), vx, vy, nameMarkBuddyWorld(nameMarkBuddyTab()));
    }, [flick[1] / 16, flick[2] / 16, flick.seed]);
  } else {
    await page.mouse.move(f[0], f[1]);
    await page.mouse.down();
    let [x, y] = f;
    for (let i = 0; i < 5; i += 1) {
      await page.waitForTimeout(16);
      x = Math.max(2, Math.min(x + flick[1], page.viewportSize().width - 2));
      y = Math.max(2, Math.min(y + flick[2], page.viewportSize().height - 2));
      await page.mouse.move(x, y);
    }
    await page.mouse.up();
  }
  await page.mouse.move(5, page.viewportSize().height - 5);
  // The flight (or, let go too slowly to fly, the drop), then its landing's
  // move. Where it came down: the flight's rest, or where it was let go.
  const settled = await page.evaluate(async () => {
    const t0 = performance.now();
    while ((nmb.flight || (nmb.thrown && !nmb.thrown.to)) && performance.now() - t0 < 10000) await new Promise((d) => setTimeout(d, 50));
    while (nmb.anim && nmb.anim.playState === 'running' && performance.now() - t0 < 14000) await new Promise((d) => setTimeout(d, 50));
    await new Promise((d) => setTimeout(d, 300));
    const rest = nmb.thrown?.to || window.__moves[0]?.from;
    window.__settleT = performance.now();
    return { thrown: !!nmb.thrown, fate: nmb.thrown?.fate || (nmb.thrown ? '' : 'drop'), v: nmb.thrown?.v, rest, at: [Math.round(nmb.x), Math.round(nmb.y)], pose: nmb.pose, kind: nmb.spot?.kind || '' };
  });
  const track = await page.evaluate(async (hold) => {
    const [sx, sy] = [nmb.x, nmb.y];
    let far = 0;
    const at = {};
    const t0 = performance.now();
    while (performance.now() - t0 < hold) {
      far = Math.max(far, Math.hypot(nmb.x - sx, nmb.y - sy));
      const e = performance.now() - t0;
      if (!at[5] && e >= 5000) at[5] = [Math.round(nmb.x), Math.round(nmb.y)];
      await new Promise((d) => setTimeout(d, 100));
    }
    at[15] = [Math.round(nmb.x), Math.round(nmb.y)];
    return { far: Math.round(far), at, moves: window.__moves.filter((m) => m.t >= window.__settleT).map((m) => ({ ...m, t: Math.round(m.t - window.__settleT) })) };
  }, HOLD);
  const d = (a, b) => (a && b ? Math.round(Math.hypot(a[0] - b[0], a[1] - b[1])) : null);
  return { flick: flick[0], from, ...settled, restToSettled: d(settled.rest, settled.at), at5: track.at[5], at15: track.at[15], d5: d(settled.at, track.at[5]), d15: d(settled.at, track.at[15]), far15: track.far, moves: track.moves };
}

(async () => {
  for (const [w, h] of SIZES) {
    for (const kind of KINDS) {
      const { browser, page } = await boot({ viewport: { width: w, height: h } });
      await page.evaluate((k) => {
        localStorage.removeItem('nm-buddy-spots');
        const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true }));
      }, kind);
      for (const tab of TABS) {
        await page.evaluate((t) => revealTab(t), tab);
        await page.waitForTimeout(2500);
        // Every move after the flight, and who asked for it.
        await page.evaluate(() => {
          if (window.__wrapped) return;
          window.__wrapped = true;
          window.__moves = [];
          const orig = nameMarkBuddyMoveTo;
          // eslint-disable-next-line no-global-assign
          nameMarkBuddyMoveTo = function (buddy, spot, instant) {
            const stack = (new Error().stack || '').split('\n').slice(2, 6).map((l) => l.trim().replace(/^at /, '').replace(/\(?https?:\/\/[^/]+\/[^ )]*\/([^/ )]+?)(\?[^:]*)?:(\d+):\d+\)?/, '$1:$3')).join(' < ');
            window.__moves.push({ t: performance.now(), kind: spot?.kind || '', x: Math.round(spot?.x ?? -1), y: Math.round(spot?.y ?? -1), from: [Math.round(nmb.x), Math.round(nmb.y)], stack });
            return orig.call(this, buddy, spot, instant);
          };
        });
        const rows = [];
        if (DIRECT) {
          await page.evaluate(() => ensureModule('companionThrow'));
          await page.waitForFunction(() => typeof nameMarkBuddyThrow === 'function' && typeof companionThrowSeed !== 'undefined', null, { timeout: 15000 });
        }
        for (const [i, flick] of FLICKS.entries()) {
          const from = [Math.round(w / 2 - 32), Math.round(h * 0.55)];
          flick.seed = 1402 + i;
          rows.push(await one(page, flick, from));
        }
        let reload = null;
        if (process.env.RELOAD !== '0') {
          const before = await page.evaluate(() => [Math.round(nmb.x), Math.round(nmb.y)]);
          await page.reload({ waitUntil: 'domcontentloaded' });
          await page.waitForTimeout(6000);
          await page.evaluate((t) => revealTab(t), tab).catch(() => {});
          await page.waitForTimeout(3000);
          const after = await page.evaluate(() => (typeof nmb !== 'undefined' ? [Math.round(nmb.x), Math.round(nmb.y)] : null)).catch(() => null);
          reload = { before, after, d: after ? Math.round(Math.hypot(after[0] - before[0], after[1] - before[1])) : null };
          await page.evaluate(() => { window.__wrapped = false; }).catch(() => {});
        }
        const far = rows.filter((r) => r.far15 > 40 || r.restToSettled > 120);
        const sum = (k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
        console.log(JSON.stringify({ size: `${w}x${h}`, kind, tab, throws: rows.length, farAfter: far.length, maxFar15: Math.max(...rows.map((r) => r.far15 || 0)), maxRestToSettled: Math.max(...rows.map((r) => r.restToSettled || 0)), sumRestToSettled: sum('restToSettled'), sumFar15: sum('far15'), reload, rows }));
      }
      await browser.close();
    }
  }
})().catch((e) => { console.error(e); process.exit(1); });
