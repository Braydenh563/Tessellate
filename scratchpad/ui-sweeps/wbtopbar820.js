// The board's top bar at 820, the width this app calls a tablet.
//
// Phase 11 item 7 raised `#wb-topbar` to the 44px floor below 600 and said,
// in its own decision block, that a phone-shaped board bar is WHITEBOARD_PLAN's
// rather than that item's. What it did not answer is 820: the floor is
// redeclared on `:root` below 819.98 (07-whiteboard-misc.css, "below 820 the
// pointer is a finger"), so 820 itself is the first width where it is not, and
// 820x1180 is an iPad in portrait.
//
// This measures the bar with a board actually open: its height, its rows, and
// every control in it, so whichever way the question is answered it is
// answered with numbers.
//
//   BASE=http://127.0.0.1:8994 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules node scratchpad/ui-sweeps/wbtopbar820.js
const { boot } = require('./lib.js');

const WIDTH = Number(process.env.WIDTH || 820);
const HEIGHT = Number(process.env.HEIGHT || 1180);
// The app's own line: below 820 a hit target is 44px. At 820 and above the
// global floor is 28px, so that is what a pass means here unless the band is
// changed; the report prints both counts either way.
const FLOOR = Number(process.env.FLOOR || (WIDTH < 820 ? 44 : 28));

(async () => {
  const { page, browser } = await boot({
    viewport: { width: WIDTH, height: HEIGHT },
    hasTouch: WIDTH <= 1024,
    isMobile: WIDTH < 600,
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(1800);

  const opened = await page.evaluate(async () => {
    switchTab('library');
    await new Promise((r) => setTimeout(r, 900));
    document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click();
    await new Promise((r) => setTimeout(r, 1200));
    const card = document.querySelector('.library-board-card');
    if (!card) return 'no board in this notebook';
    card.click();
    await new Promise((r) => setTimeout(r, 2500));
    return document.getElementById('wb-topbar')?.offsetParent ? 'open' : 'it would not open';
  });
  console.log('board:', opened);
  if (opened !== 'open') {
    console.log('FAIL: nothing to measure');
    await browser.close();
    process.exit(1);
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  const m = await page.evaluate(({ floor }) => {
    const bar = document.getElementById('wb-topbar');
    const b = bar.getBoundingClientRect();
    const visible = (e) => e.checkVisibility
      && e.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true });
    const controls = [...bar.querySelectorAll('button, summary, select, input:not([type="hidden"])')]
      .filter(visible)
      .filter((e) => !e.closest('.dock-native-hidden, .visually-hidden, .sr-only'));
    const rows = new Set();
    const each = controls.map((el) => {
      const r = el.getBoundingClientRect();
      rows.add(Math.round(r.top));
      return {
        name: el.id || el.tagName.toLowerCase() + '.' + [...el.classList].slice(0, 2).join('.'),
        h: Math.round(r.height * 10) / 10,
        w: Math.round(r.width * 10) / 10,
      };
    });
    return {
      bar: { w: Math.round(b.width), h: Math.round(b.height) },
      rows: rows.size,
      rowTops: [...rows].sort((x, y) => x - y),
      controls: each.length,
      heights: [...new Set(each.map((c) => c.h))].sort((x, y) => x - y),
      under: each.filter((c) => c.h < floor || c.w < floor),
      targetMin: getComputedStyle(document.documentElement).getPropertyValue('--target-min').trim(),
      overflow: Math.round(bar.scrollWidth) - Math.round(bar.clientWidth),
      canvasTop: Math.round((document.querySelector('#wb-canvas, .wb-canvas, #wb-stage')?.getBoundingClientRect().top) || 0),
      windowH: innerHeight,
    };
  }, { floor: FLOOR });

  console.log(JSON.stringify(m, null, 1));
  console.log(`at ${WIDTH}: --target-min ${m.targetMin}, bar ${m.bar.w}x${m.bar.h} in ${m.rows} row(s), ` +
    `${m.controls} controls at heights ${m.heights.join(', ')}, ${m.under.length} under ${FLOOR}px`);
  const findings = [];
  // Reported at every width, failed only above 600. Below 600 the bar runs
  // 5px past itself at 390 and 75px at 320, which is recorded in
  // 07-whiteboard-misc.css and in WHITEBOARD_PLAN rather than fixed here:
  // the only fix that does not redesign the bar is letting its halves wrap,
  // and that costs a row (152px at 390, 200px at 320) over a 604px canvas,
  // which is the trade Phase 11 item 7 deliberately left to that plan.
  console.log(`bar overflow at ${WIDTH}: ${m.overflow}px`);
  if (m.overflow > 0 && WIDTH >= 600) findings.push(`the bar scrolls sideways by ${m.overflow}px`);
  if (m.under.length) findings.push(`${m.under.length} control(s) under ${FLOOR}px: ${JSON.stringify(m.under.slice(0, 12))}`);
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? `FAIL (${WIDTH}): ` + findings.join('\n  ') : `PASS (${WIDTH}): 0 findings against a ${FLOOR}px floor`);
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
