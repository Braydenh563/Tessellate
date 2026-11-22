// Three owner reports about three surfaces, measured rather than looked at.
//
//   INBOX 289  "in the files subtab, I want the expanded text box to be
//              slightly taller as it is quite short vertically"
//   INBOX 296  "improve the ui of the hero section in the dashboard when on
//              focused mode"
//   INBOX 307  "I feel like the navigation and undo/redo buttons keep getting
//              pushed further and further to the left on the bottom bar, is
//              there a better way to restructure the right side of the bottom
//              bar??"
//
// One probe rather than three because all three are geometry read off one
// booted app, and booting is most of the cost.
//
// Seed first, or the Files half has an empty state to measure and the numbers
// mean nothing:
//
//   node scratchpad/ui-sweeps/seed-libtext.js
//   python scratchpad/ui-sweeps/seed-libtext.py <data dir>/memorymap.db
//
//   BASE=http://127.0.0.1:8806 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules SCRATCH=/tmp/mm-uitrio \
//     timeout 115 node scratchpad/ui-sweeps/uitrio.js
const { boot, seedLibtextIfEmpty } = require('./lib.js');

let failures = 0;
const check = (label, ok, detail) => {
  if (!ok) failures += 1;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}  ${detail}`);
};
const round = (n) => Math.round(n * 10) / 10;

// --- 289: the Files sub-tab's extracted-text box ------------------------------
//
// The number the report is about is *lines shown*, not pixels: "quite short
// vertically" is a person counting the lines they can read before they have to
// scroll. So the box's own height is divided by its computed line height, and
// the second number is what the row below costs, because a taller box that
// pushes the next row off the screen is a worse answer than a short one.
async function filesBox(page, width) {
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(900);
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('#library-subtabs button, [data-subtab]')].find(
      (e) => /file/i.test(e.textContent || e.dataset.subtab || '')
    );
    if (b) b.click();
  });
  await page.waitForTimeout(1600);
  await page.evaluate(() => {
    const d = document.querySelector('.library-image-tile .library-image-reading');
    if (d) d.open = true;
  });
  await page.waitForTimeout(500);
  return page.evaluate((w) => {
    const r = (n) => Math.round(n * 10) / 10;
    const box = document.querySelector('.library-file-reading-text');
    if (!box) return { width: w, missing: true };
    const cs = getComputedStyle(box);
    const rect = box.getBoundingClientRect();
    // The line box, resolved: `line-height: 1.5` computes to a pixel string in
    // Chromium, but "normal" would not, so fall back to the font size rather
    // than write NaN into a division (CLAUDE.md's "invalid where it is used").
    const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5;
    const tiles = [...document.querySelectorAll('.library-image-tile')];
    const mine = box.closest('.library-image-tile');
    const next = tiles[tiles.indexOf(mine) + 1] || null;
    const scroller =
      document.querySelector('#tab-library .library-file-rows')?.closest('[class]') || document.scrollingElement;
    return {
      width: w,
      boxH: r(rect.height),
      maxH: cs.maxHeight,
      lineH: r(lh),
      lines: Math.round((rect.height / lh) * 100) / 100,
      scrollH: box.scrollHeight,
      clipped: box.scrollHeight > box.clientHeight + 1,
      tileH: r(mine.getBoundingClientRect().height),
      // Where the row below starts, against the viewport: the "pushed out of
      // view" half of the brief.
      nextTop: next ? r(next.getBoundingClientRect().top) : null,
      viewportH: window.innerHeight,
      nextVisible: next ? next.getBoundingClientRect().top < window.innerHeight : null,
      scrollerTag: scroller ? scroller.tagName : null,
    };
  }, width);
}

// --- 296: the dashboard's focused hero ----------------------------------------
//
// Not "is focused shorter" (it is), but **what focused puts in front of you**.
// Every band is listed shown or dropped at each density, so the three levels
// can be read as one sequence, and the hero's own controls are counted: a hero
// that shows least has to still be the one thing you came for.
const BANDS = [
  ['emblem', '#dash-hero-emblem'],
  ['wordmark', '.dash-wordmark'],
  ['greeting', '#dash-greeting'],
  ['submessage', '#dash-submessage'],
  ['clock', '.dash-clock'],
  ['find', '#dash-find'],
  ['quicklinks', '#dash-quicklinks'],
  ['stats', '#dash-stats'],
];

async function hero(page, density) {
  return page.evaluate(async (args) => {
    const { density, BANDS } = args;
    applyDashDensity(density);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const r = (n) => Math.round(n * 10) / 10;
    const heroEl = document.getElementById('dash-hero');
    const grid = document.getElementById('dash-grid');
    const pageEl = document.getElementById('tab-dashboard');
    const top = pageEl.getBoundingClientRect().top;
    const bands = {};
    for (const [name, sel] of BANDS) {
      const el = document.querySelector(sel);
      if (!el) { bands[name] = 'absent'; continue; }
      const box = el.getBoundingClientRect();
      const shown = box.height > 0 && getComputedStyle(el).display !== 'none';
      bands[name] = shown ? r(box.height) : 'off';
    }
    const heroBox = heroEl.getBoundingClientRect();
    const findEl = document.getElementById('dash-find');
    const findBox = findEl ? findEl.getBoundingClientRect() : null;
    return {
      density,
      hero: r(heroBox.height),
      chrome: grid ? r(grid.getBoundingClientRect().top - top) : null,
      bands,
      // The head, as one number: the top of the banner to the bottom of the
      // search doorway, whether those are one row or two bands.
      head: findBox ? r(findBox.bottom - heroBox.top) : null,
      // On one line, or one above the other. A tolerance of a pixel, not zero:
      // stretch aligns the boxes, sub-pixel layout does the rest.
      oneRow: findBox ? Math.abs(findBox.top - heroBox.top) < 1.5 : null,
      findH: findBox ? r(findBox.height) : null,
      heroRadius: getComputedStyle(heroEl).borderTopLeftRadius,
      findRadius: findEl ? getComputedStyle(findEl).borderTopLeftRadius : null,
      // Every control a person can press inside the hero, which is the measure
      // of "the one thing you came here for" against "a banner".
      heroControls: [...heroEl.querySelectorAll('button, a, input')]
        .filter((e) => e.offsetParent)
        .map((e) => (e.id || e.className || e.tagName).toString().split(' ')[0]),
      greetingSize: getComputedStyle(document.getElementById('dash-greeting')).fontSize,
    };
  }, { density, BANDS });
}

// --- 307: the right end of the status bar -------------------------------------
//
// The drift complaint, as a list: every drawn item in the bar in DOM order,
// with its left edge, so "pushed further to the left" is a coordinate. The
// items right of `.status-spacer` are the run the report is about.
async function statusBar(page) {
  return page.evaluate(() => {
    const r = (n) => Math.round(n * 10) / 10;
    const bar = document.getElementById('status-bar');
    const cs = getComputedStyle(bar);
    const barBox = bar.getBoundingClientRect();
    // The bar's *content* edge, not its border edge: the page gutter is the
    // bar's own padding, so a control flush against the end of the run still
    // measures a gutter's width from `right`.
    const contentRight = barBox.right - parseFloat(cs.paddingRight);
    const items = [];
    const zones = [];
    let side = 'left';
    for (const el of bar.children) {
      const box = el.getBoundingClientRect();
      const shown = box.width > 0 && getComputedStyle(el).display !== 'none';
      if (el.classList.contains('status-spacer')) { side = 'right'; continue; }
      if (!shown) continue;
      const zone = el.dataset.statusZone || null;
      if (zone) {
        zones.push({
          zone,
          side,
          left: r(box.left),
          right: r(box.right),
          order: getComputedStyle(el).order,
          items: [...el.children]
            .filter((c) => c.getBoundingClientRect().width > 0)
            .map((c) => c.id || c.className.toString().split(' ')[0]),
        });
      }
      items.push({
        id: el.id || el.className.toString().split(' ')[0],
        side,
        left: r(box.left),
        right: r(box.right),
        w: r(box.width),
        zone,
      });
    }
    const nav = document.querySelector('.status-nav');
    const redo = document.getElementById('status-redo');
    const control = document.querySelector('[data-status-zone="control"]');
    return {
      barW: r(barBox.width),
      items,
      zones,
      // DOM order of the zones, which is the order the lint holds.
      zoneOrder: [...bar.querySelectorAll('[data-status-zone]')].map((e) => e.dataset.statusZone),
      // The two numbers the report is about, against the content edge.
      navFromRight: nav ? r(contentRight - nav.getBoundingClientRect().right) : null,
      redoFromRight: redo ? r(contentRight - redo.getBoundingClientRect().right) : null,
      // On a phone the bar scrolls sideways by design, so what matters is not
      // where the run ends but whether these are reachable without a drag.
      overflow: bar.scrollWidth > bar.clientWidth + 1,
      scrollW: bar.scrollWidth,
      clientW: bar.clientWidth,
      controlInView: control
        ? control.getBoundingClientRect().right <= window.innerWidth + 1 &&
          control.getBoundingClientRect().left >= -1
        : null,
      rightCount: items.filter((i) => i.side === 'right').length,
    };
  });
}

(async () => {
  const widths = [1440, 390];
  const out = {};
  for (const width of widths) {
    const { browser, page } = await boot({ viewport: { width, height: width === 390 ? 844 : 950 } });
    // Seeded here, on a fresh data dir, so the Files half has a reading to measure (lib.js).
    await seedLibtextIfEmpty(page);

    console.log(`\n=== ${width} ===`);
    const files = await filesBox(page, width);
    out[`files${width}`] = files;
    if (files.missing) console.log('files: no reading box on screen (seed first)');
    else
      console.log(
        `289 files box: ${files.boxH}px (max-height ${files.maxH}), line ${files.lineH}px, ` +
          `${files.lines} lines, content ${files.scrollH}px, tile ${files.tileH}px, ` +
          `next row top ${files.nextTop} of ${files.viewportH}`
      );

    const bar = await statusBar(page);
    out[`bar${width}`] = bar;
    console.log(
      `307 bar ${bar.barW}px, zones [${bar.zoneOrder.join(', ')}], ` +
        `nav ends ${bar.navFromRight}px from the content edge, redo ${bar.redoFromRight}px, ` +
        `overflowing ${bar.overflow} (${bar.scrollW} of ${bar.clientW})`
    );
    for (const z of bar.zones)
      console.log(
        `      ${z.zone.padEnd(8)} left ${String(z.left).padStart(7)} right ${String(z.right).padStart(7)} ` +
          `order ${z.order}  [${z.items.join(', ')}]`
      );

    {
      await page.evaluate(() => switchTab('dashboard'));
      await page.waitForTimeout(900);
      // At 390 only the level the report is about: the question down there is
      // whether the head row wraps back into two bands rather than squeezing
      // a banner and a field into 390px.
      for (const d of width === 1440 ? ['full', 'compact', 'focused'] : ['focused']) {
        const h = await hero(page, d);
        out[`hero-${d}${width === 1440 ? '' : width}`] = h;
        console.log(
          `296 hero ${d.padEnd(8)} ${String(h.hero).padStart(6)}px, chrome ${h.chrome}px, ` +
            `head ${h.head}px, one row ${h.oneRow}, find ${h.findH}px ` +
            `(radius ${h.heroRadius} / ${h.findRadius}), greeting ${h.greetingSize}`
        );
        console.log(`      bands ${JSON.stringify(h.bands)}`);
      }
    }
    await browser.close();
  }

  // --- the checks ------------------------------------------------------------
  //
  // 289: the box shows at least four lines of the reading. Three was the
  // measured complaint; the cap is still a cap, so the row below has to stay on
  // screen with the box open.
  const f = out.files1440;
  check(
    '289: the Files reading box shows at least four lines',
    !f.missing && f.lines >= 3.9,
    `${f.lines} lines (${f.boxH}px at ${f.lineH}px)`
  );
  check(
    '289: and the row below the open one is still on screen',
    f.missing || f.nextTop === null || f.nextVisible,
    `next row top ${f.nextTop} of ${f.viewportH}`
  );
  const fp = out.files390;
  check(
    '289: the same box on a phone is not taller than half the screen',
    fp.missing || fp.boxH <= fp.viewportH / 2,
    `${fp.boxH}px of ${fp.viewportH}`
  );

  // 296: the levels. What the owner decided since the report (07-whiteboard-misc.css, the
  // focused head): INBOX 425 "Two rows again ... Do not remake the one-row head", and INBOX 675
  // "The Focused hero is a hero again" (a two-column banner with today's glance), so focused is
  // the TALLEST banner, and its search doorway is a full-width band beneath it, not a row beside it.
  // What stays asserted: full is taller than compact, focused keeps the identity and the one
  // number, and the doorway is its own band under the banner, one step apart.
  const [full, compact, focused] = [out['hero-full'], out['hero-compact'], out['hero-focused']];
  check(
    '296: compact is a shorter banner than full',
    full.hero > compact.hero,
    `${full.hero} / ${compact.hero}`
  );
  check(
    '296: focused keeps the greeting and the one number',
    focused.bands.greeting !== 'off' && focused.bands.submessage !== 'off',
    JSON.stringify(focused.bands)
  );
  check(
    '296: focused puts the search doorway on its own band under the banner',
    focused.oneRow === false,
    `one row ${focused.oneRow}, head ${focused.head}px`
  );
  const gap = Math.round((focused.head - focused.hero - focused.findH) * 10) / 10;
  check(
    '296: and the two bands are one step apart, not touching and not far',
    gap > 0 && gap <= 24,
    `${gap}px between the banner and the doorway`
  );
  check(
    '296: full and compact keep the banner and the doorway as two bands',
    full.oneRow === false && compact.oneRow === false,
    `full ${full.oneRow}, compact ${compact.oneRow}`
  );
  // A phone is 390px of line: the head row has to give up and stack, or the
  // banner and the field share a line neither of them fits on.
  const focused390 = out['hero-focused390'];
  check(
    '296: the focused head row wraps back into two bands on a phone',
    focused390.oneRow === false,
    `one row ${focused390.oneRow}, head ${focused390.head}px`
  );

  // 307: the right end has an owner. The zones are in one order at every
  // width; on a bar wide enough to show all of it, the control zone ends the
  // run, so nothing added later can push it. On a phone the bar scrolls and
  // the order flips on purpose, so what is checked there is reachability.
  for (const width of widths) {
    const b = out[`bar${width}`];
    check(
      `307 at ${width}: every item right of the spacer declares its zone`,
      b.items.filter((i) => i.side === 'right').every((i) => i.zone),
      b.items.filter((i) => i.side === 'right' && !i.zone).map((i) => i.id).join(', ') || 'all zoned'
    );
    check(
      `307 at ${width}: the zones are state, tools, control in the markup`,
      b.zoneOrder.join(',') === 'state,tools,control',
      `[${b.zoneOrder.join(', ')}]`
    );
  }
  const wide = out.bar1440;
  check(
    '307 at 1440: the control zone ends the bar',
    wide.redoFromRight !== null && Math.abs(wide.redoFromRight) <= 1,
    `redo ends ${wide.redoFromRight}px from the content edge (was 391px behind four doorways)`
  );
  const phone = out.bar390;
  check(
    '307 at 390: the controls are reachable without dragging the bar',
    phone.controlInView === true,
    `control zone in view ${phone.controlInView}, bar ${phone.scrollW} of ${phone.clientW}`
  );

  console.log(failures ? `\nFAILURES ${failures}` : '\nall checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
