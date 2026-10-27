// INBOX 1301 D6: what can happen to a thrown companion on the way, in the
// app, on the page's own panels (companion-throw.js). Seeded throws
// (`companionThrowSeed`) from set places at set speeds, for the companion
// as "You" and as Atlas, until each outcome has been seen: caught the top
// bar and hangs; caught a panel's edge and climbed on; splatted on a side
// and slid down; went off one side and came back on the other; fell past a
// ledge's end and caught it (grab); slid off its end and caught on (slip,
// K12). For each it
// measures the moment (the class seen, the slide, the x range), where it
// ended (pose, inside the window, over no control: `nameMarkBuddyHits`),
// that its frame loop has stopped, and the companion's box size. Then one
// real-pointer flick (the lazy file arrives with the carry) and, with
// REDUCED=1 or always as a second pass, Reduce motion: no moments at all.
// Env: BASE, BUDDY (me|atlas, default both), ONLY (outcomes, comma list). Prints one JSON line each.
const { boot } = require('./lib.js');

async function pass(buddyKind, reduced) {
  const opts = { viewport: { width: 1440, height: 900 } };
  if (reduced) opts.reducedMotion = 'reduce';
  const { browser, page } = await boot(opts);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  await page.evaluate((kind) => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = kind; b.dispatchEvent(new Event('change', { bubbles: true })); } }, buddyKind);
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); revealTab('dashboard'); });
  await page.waitForTimeout(2500);
  // A real flick first: the lazy file arrives with the carry.
  const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await page.mouse.move(face[0], face[1]);
  await page.mouse.down();
  for (let i = 1; i <= 5; i += 1) { await page.waitForTimeout(16); await page.mouse.move(face[0] - i * 60, face[1] - i * 20); }
  await page.mouse.up();
  await page.waitForTimeout(2500);
  const flick = await page.evaluate(() => ({ loaded: typeof companionThrowStep === 'function', thrown: !!(nmb.thrown && nmb.thrown.v), fate: nmb.thrown && nmb.thrown.fate }));
  const world = await page.evaluate(() => { nameMarkBuddyIndexReset(); const w = nameMarkBuddyWorld(nameMarkBuddyTab()); return { top: w.top, floor: w.floor, right: w.right, ledges: w.ledges }; });
  // The ledge to climb: the highest one at least 300px under the bar.
  const ledge = world.ledges.filter((l) => l.y > world.top + 40).sort((a, b) => a.y - b.y)[0];
  const configs = {
    hang: { x: 700, y: 520, vx: 0.2, vy: -3.6 },
    climb: ledge ? { x: Math.round((ledge.left + ledge.right) / 2), y: Math.min(world.floor - 10, ledge.y + 84 + 260), vx: 0.05, vy: -2.4 } : null,
    splat: { x: world.right - 420, y: 280, vx: 3.4, vy: -0.4 },
    wrap: { x: world.right - 420, y: 280, vx: 4.4, vy: -0.5 },
    // K12: falling 15px past the ledge's right end; landed near that end and sliding off it.
    // (the dashboard's tiles sit 10px apart, so a hand past one end is over
    // the next: the throw's room keeps only that ledge, `solo`)
    grab: ledge && ledge.right + 15 < world.right ? { x: Math.round(ledge.right + 15), y: Math.round(ledge.y - 40), vx: 0, vy: 0.1, solo: Math.round(ledge.y) } : null,
    slip: ledge && ledge.right < world.right ? { x: Math.round(ledge.right - 40), y: Math.round(ledge.y - 20), vx: 0.4, vy: 0.05 } : null,
  };
  const out = { buddy: buddyKind, reduced, flick, ledge, ledges: world.ledges.map((l) => [l.left, l.right, l.y].map(Math.round)), seen: {} };
  for (const [want, c] of Object.entries(configs)) {
    if (process.env.ONLY && !process.env.ONLY.split(',').includes(want)) continue;
    if (!c) { out.seen[want] = { skipped: 'no ledge' }; continue; }
    const tally = {};
    let found = null;
    for (let seed = 1; seed <= 40 && !found; seed += 1) {
      const r = await page.evaluate(async ([cfg, sd]) => {
        await ensureModule('companionThrow');
        const buddy = document.getElementById('nm-buddy');
        nmb.flight?.stop();
        nmb.act && nameMarkBuddyAct('');
        nameMarkBuddyMoveTo(buddy, { kind: 'yours', pose: 'float', legs: '', x: cfg.x, y: cfg.y }, true);
        companionThrowSeed.seed = sd;
        nameMarkBuddyIndexReset();
        const w = nameMarkBuddyWorld(nameMarkBuddyTab());
        if (cfg.solo) w.ledges = w.ledges.filter((l) => Math.round(l.y) === cfg.solo && l.right < cfg.x && l.right > cfg.x - 40);
        const rec = { classes: new Set(), minX: Infinity, maxX: -Infinity, splatYs: [], frames: 0, boxMax: 0 };
        const mo = new MutationObserver(() => { for (const c of ['nmb-splat', 'nmb-climb', 'nmb-slip']) if (buddy.classList.contains(c)) rec.classes.add(c); });
        mo.observe(buddy, { attributes: true, attributeFilter: ['class'] });
        let raf = 0;
        const sample = () => {
          rec.frames += 1;
          rec.minX = Math.min(rec.minX, nmb.x); rec.maxX = Math.max(rec.maxX, nmb.x);
          if (buddy.classList.contains('nmb-splat')) rec.splatYs.push(Math.round(nmb.y));
          const b = buddy.getBoundingClientRect(); rec.boxMax = Math.max(rec.boxMax, Math.round(b.width), Math.round(b.height));
          raf = requestAnimationFrame(sample);
        };
        raf = requestAnimationFrame(sample);
        nmb.thrown = null;
        nameMarkBuddyThrow(buddy, cfg.vx, cfg.vy, w);
        const t0 = performance.now();
        while ((nmb.flight || !nmb.thrown?.to) && performance.now() - t0 < 8000) await new Promise((d) => setTimeout(d, 50));
        const restMs = Math.round(performance.now() - t0);
        await new Promise((d) => setTimeout(d, 1300));
        cancelAnimationFrame(raf); mo.disconnect();
        const tab = nameMarkBuddyTab();
        const spot = nmb.spot || {};
        const hits = nameMarkBuddyHits(nmb.x, nmb.y, spot.pose, nameMarkBuddyYoursObstacles(nameMarkBuddyObstacles(tab), spot), spot.legs);
        const ys = rec.splatYs;
        return {
          fate: nmb.thrown?.fate, classes: [...rec.classes], restMs, flightOff: !nmb.flight,
          minX: Math.round(rec.minX), maxX: Math.round(rec.maxX), slidePx: ys.length ? ys[ys.length - 1] - ys[0] : 0,
          end: { x: Math.round(nmb.x), y: Math.round(nmb.y), pose: buddy.dataset.pose, act: nmb.act || '' }, inside: nmb.x >= 0 && nmb.x <= innerWidth - 64 && nmb.y >= 0 && nmb.y <= innerHeight,
          coversControl: !!hits, boxMax: rec.boxMax, topBarBottom: Math.round(document.getElementById('top-bar')?.getBoundingClientRect().bottom || 0),
        };
      }, [c, seed]);
      tally[r.fate] = (tally[r.fate] || 0) + 1;
      if (r.fate === want) found = { seed, ...r };
    }
    out.seen[want] = { found, tally };
  }
  // At rest, nothing of the throw runs: no flight, and the page's frames
  // over a second counted against the same second before any throw.
  out.idle = await page.evaluate(() => new Promise((done) => { let n = 0; const f = () => { n += 1; if (performance.now() - t0 < 1000) requestAnimationFrame(f); else done({ flight: !!nmb.flight, splat: document.getElementById('nm-buddy').classList.contains('nmb-splat') }); }; const t0 = performance.now(); requestAnimationFrame(f); }));
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
}

(async () => {
  const kinds = process.env.BUDDY ? [process.env.BUDDY] : ['me', 'atlas'];
  for (const k of kinds) await pass(k, !!process.env.REDUCED);
  if (!process.env.REDUCED) await pass(kinds[0], true);
})();
