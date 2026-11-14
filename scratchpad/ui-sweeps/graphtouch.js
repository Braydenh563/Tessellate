// The graph on a phone, and the world constant, the two lines
// `docs/roadmap/archive/agent-remaining/graph.md` carried under "Not verified":
// "touch and pinch on the map are still untested, and so is the graph at a
// phone width beyond the panel", and "the world constant in `gcWorldFor` (1.6
// to 1.25) is not exercised at 35 or 300 notes, where the viewport floor
// decides the world".
//
// Its own browser context rather than `lib.js`'s, for the reason `touch.js`
// gives: `hasTouch` plus `isMobile` is what makes `(pointer: coarse)` match and
// what makes d3-zoom bind its touch handlers at all, so a desktop context in a
// narrow window would measure a different page with a different gesture set.
// The gestures go through CDP `Input.dispatchTouchEvent`, because Playwright's
// own touchscreen API taps and does not pinch.
//
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/graphtouch.js
const { chromium } = require('playwright');
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);

const findings = [];
const check = (ok, what) => { if (!ok) findings.push(what); return ok; };

async function touch(cdp, type, points) {
  await cdp.send('Input.dispatchTouchEvent', {
    type,
    touchPoints: points.map((p, i) => ({ x: p.x, y: p.y, id: i })),
  });
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 2,
  });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      localStorage.setItem('onboardingDone', '1');
    } catch (e) {}
  }, process.env.THEME || 'light');
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => {
    const o = document.getElementById('onboarding-overlay');
    if (o) o.classList.add('hidden');
  });
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(4000);

  const box = await page.evaluate(() => {
    const canvas = document.getElementById('graph-canvas');
    const r = canvas.getBoundingClientRect();
    return {
      rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
      touchAction: getComputedStyle(canvas).touchAction,
      nodes: gcNodes.length,
      hidden: canvas.classList.contains('hidden'),
      // The page itself must not scroll sideways at a phone width.
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  console.log('map at ' + WIDTH + '        ', JSON.stringify(box));
  check(!box.hidden, 'the canvas renderer is not the one drawing at this width');
  check(box.rect[2] > 200 && box.rect[3] > 200, `the map is ${box.rect[2]}x${box.rect[3]} at ${WIDTH}`);
  check(
    box.touchAction === 'none',
    `the canvas has touch-action ${box.touchAction}: the browser will take the gesture as a page scroll`
  );
  check(box.overflow <= 0, `the page scrolls ${box.overflow}px sideways at ${WIDTH}`);
  check(box.nodes > 0, 'nothing is on the map, so no gesture proves anything');

  const cdp = await ctx.newCDPSession(page);
  const camera = () =>
    page.evaluate(() => {
      const t = d3.zoomTransform(graphSvg.node());
      return { k: +t.k.toFixed(4), x: +t.x.toFixed(1), y: +t.y.toFixed(1) };
    });

  const cx = box.rect[0] + box.rect[2] / 2;
  const cy = box.rect[1] + box.rect[3] / 2;

  // --- one finger: a pan ----------------------------------------------------
  //: **Where the finger goes down is the whole experiment.** The first version
  //: of this started 24px inside the canvas's own top-left corner and measured
  //: a pan of exactly 0.0px, which reads as "touch panning is broken". It was
  //: not: `elementFromPoint` there is the dock, which floats over the map, so
  //: no touch event reached the canvas at all (instrumented: zero touchstarts
  //: on the element). A point is chosen here by asking the page for one that
  //: is really on the canvas and really has no note under it, because a drag
  //: that starts on a note moves the note, which is also the gesture working.
  const before = await camera();
  const start = await page.evaluate((rect) => {
    const canvas = document.getElementById('graph-canvas');
    for (let fy = 0.75; fy >= 0.3; fy -= 0.05) {
      for (let fx = 0.15; fx <= 0.85; fx += 0.05) {
        const x = rect[0] + rect[2] * fx;
        const y = rect[1] + rect[3] * fy;
        if (document.elementFromPoint(x, y) !== canvas) continue;
        const [wx, wy] = gcRequestDraw.inspect.gcWorldPoint({ clientX: x, clientY: y });
        if (gcRequestDraw.inspect.gcNodeAtWorld(wx, wy)) continue;
        return [Math.round(x), Math.round(y)];
      }
    }
    return null;
  }, box.rect);
  console.log('pan starts at    ', JSON.stringify(start));
  check(Boolean(start), 'no point on the map is both uncovered and free of notes');
  const startX = start ? start[0] : box.rect[0] + 24;
  const startY = start ? start[1] : box.rect[1] + 24;
  await touch(cdp, 'touchStart', [{ x: startX, y: startY }]);
  for (let step = 1; step <= 8; step++) {
    await touch(cdp, 'touchMove', [{ x: startX + step * 12, y: startY + step * 6 }]);
    await page.waitForTimeout(20);
  }
  await touch(cdp, 'touchEnd', []);
  await page.waitForTimeout(400);
  const panned = await camera();
  const moved = Math.hypot(panned.x - before.x, panned.y - before.y);
  console.log('one-finger pan   ', JSON.stringify({ before, after: panned, moved: +moved.toFixed(1) }));
  check(moved > 20, `a 96x48px one-finger drag moved the camera ${moved.toFixed(1)}px`);
  check(
    Math.abs(panned.k - before.k) < 0.001,
    `a one-finger drag also changed the zoom, ${before.k} to ${panned.k}`
  );

  // --- two fingers: a pinch -------------------------------------------------
  const beforePinch = await camera();
  let gap = 40;
  await touch(cdp, 'touchStart', [
    { x: cx - gap, y: cy },
    { x: cx + gap, y: cy },
  ]);
  for (let step = 1; step <= 10; step++) {
    gap = 40 + step * 10;
    await touch(cdp, 'touchMove', [
      { x: cx - gap, y: cy },
      { x: cx + gap, y: cy },
    ]);
    await page.waitForTimeout(20);
  }
  await touch(cdp, 'touchEnd', []);
  await page.waitForTimeout(400);
  const pinched = await camera();
  const ratio = pinched.k / beforePinch.k;
  console.log('two-finger pinch ', JSON.stringify({ before: beforePinch, after: pinched, ratio: +ratio.toFixed(3) }));
  check(ratio > 1.5, `a pinch from 80px to 280px between the fingers scaled the map by ${ratio.toFixed(3)}`);

  // --- the world constant, at the two counts it was never exercised at ------
  // `gcWorldFor` is arithmetic with no side effects, so it is read straight
  // rather than inferred from a layout: what the line in graph.md wanted to
  // know is whether 1.25 or 1.6 decides the world at these sizes, and the
  // answer is a comparison between the count term and the viewport floor.
  const world = await page.evaluate(() => {
    const out = {};
    for (const count of [35, 300, 1000]) {
      const w = gcWorldFor(count, graphDims.w, graphDims.h);
      const perNode = 2 * 18 + 56;
      out[count] = {
        side: Math.round(w.right - w.left),
        roomy125: Math.round(Math.sqrt(count) * perNode * 1.25),
        roomy160: Math.round(Math.sqrt(count) * perNode * 1.6),
        floor: Math.round(Math.max(graphDims.w, graphDims.h) * 1.8),
      };
    }
    return out;
  });
  console.log('gcWorldFor       ', JSON.stringify(world));
  for (const count of [35, 300, 1000]) {
    const w = world[count];
    const decides = w.roomy125 > w.floor ? 'the count' : 'the viewport floor';
    console.log(`  ${count} notes: ${decides} decides (${w.side}); 1.6 would give ${Math.max(w.roomy160, w.floor)}`);
    check(
      w.side === Math.max(w.roomy125, w.floor),
      `at ${count} notes the world is ${w.side}, neither the count term ${w.roomy125} nor the floor ${w.floor}`
    );
    //: The change from 1.6 to 1.25 can only ever shrink the world. A version of
    //: it that grew one would be the opposite of what it was made for (a wall a
    //: reheated layout cannot push past, close enough that a node cannot get
    //: lost between the notes and it).
    check(
      w.side <= Math.max(w.roomy160, w.floor),
      `at ${count} notes 1.25 gives a world of ${w.side} against 1.6's ${Math.max(w.roomy160, w.floor)}: the constant grew it`
    );
  }
  //: The line this closes, from graph.md: "the world constant in `gcWorldFor`
  //: (1.6 to 1.25) is not exercised at 35 or 300 notes, where the viewport
  //: floor decides the world". At 35 it is exactly that, at every width. At 300
  //: it depends on the width, and the code's own comment did not say so: the
  //: floor is 2531 on a 1440 desktop and 1168 here, so 1.25's 1992 is under the
  //: first and over the second. This asserts the part that is width-independent.
  check(
    world[35].side === world[35].floor,
    `at 35 notes the world is ${world[35].side}, not the floor ${world[35].floor}`
  );
  check(
    world[1000].roomy125 > world[1000].floor,
    `at 1000 notes the floor ${world[1000].floor} still decides, so the constant is untested at every size this sweep covers`
  );

  console.log('page errors      ', errors.length, errors.slice(0, 2).join(' | '));
  check(errors.length === 0, `${errors.length} page errors: ${errors.slice(0, 2).join(' | ')}`);

  console.log(findings.length ? `FAIL: ${findings.length}\n  ` + findings.join('\n  ') : 'PASS');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
