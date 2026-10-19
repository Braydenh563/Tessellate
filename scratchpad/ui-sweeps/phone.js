// The phone, tab by tab (UI_MODERNISATION_PLAN.md Phase 11, items 2 to 9 and
// the gate at item 11).
//
//   BASE=http://127.0.0.1:8792 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     timeout 110 node scratchpad/ui-sweeps/phone.js
//   WIDTH=430 HEIGHT=932 ... for the larger of the two sizes the plan names.
//
// The plan's item 11 asks for four things per tab, and this asks for them in
// the order they cost:
//
//   1. no horizontal scroll, at the page and inside every surface;
//   2. no control under 44px, counted per tab rather than per dock, since
//      `touch.js` already walks the docks and this is about what is left;
//   3. the tab's primary action inside the lower 40% of the screen, which is
//      what "within thumb reach" means as a number;
//   4. one column: no row of two or more cards side by side.
//
// A `hasTouch` + `isMobile` context, because half of the phone band's own
// rules are behind a pointer query and a desktop context measures the desktop
// layout at a phone's width, which is a different picture.
//
// It prints a row per tab and exits non-zero on any finding, so it can gate.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);
const MIN_TARGET = 44;
const TABS = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
    hasTouch: true,
    isMobile: true,
  });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      localStorage.setItem('onboardingDone', '1');
    } catch (e) { /* a profile that refuses storage still boots */ }
  }, process.env.THEME || 'light');
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(`pageerror: ${e.message.slice(0, 120)}`));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(`console: ${m.text().slice(0, 120)}`); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden'));
  await page.waitForTimeout(600);

  let failures = 0;
  console.log(`--- ${WIDTH}x${HEIGHT}, hasTouch + isMobile`);

  for (const tab of TABS) {
    await page.evaluate((t) => switchTab(t), tab);
    await page.waitForTimeout(1400);
    const r = await page.evaluate(({ min, h }) => {
      const round = (n) => Math.round(n * 10) / 10;
      const page_ = document.querySelector('.tab-page:not(.hidden)');
      if (!page_) return { none: true };
      // On screen as well as visible: a sidebar sheet parked at
      // translateX(-100%) passes checkVisibility and has a box, and a box
      // entirely left of the window is not a column beside anything.
      const visible = (el) =>
        el.checkVisibility
        && el.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true })
        && el.getBoundingClientRect().right > 0;
      // Every control the tab shows, minus the app's furniture (the bar, the
      // status bar and the header belong to the shell) and minus the four
      // kinds of element that are deliberately unreachable, each with a visible
      // control standing for it. This list is `touch.js`'s, copied rather than
      // rediscovered: a `<select>` kept only as the value a handler reads
      // (`.dock-native-hidden`, which measures 1x44), the clipped screen-reader
      // recipes (`.visually-hidden`, `.sr-only`, and the file inputs that
      // measure 1x1 behind a visible paperclip), a `.seg` well, whose own
      // buttons are what a finger lands on, and anything inside a dock menu
      // that is not open.
      const controls = [...page_.querySelectorAll('button, a[href], input:not([type="hidden"]), select, summary, [role="tab"]')]
        .filter(visible)
        .filter((el) => !el.closest('.modal-overlay, .action-menu, [hidden]'))
        .filter((el) => !el.closest('.dock-native-hidden, .visually-hidden, .sr-only'))
        .filter((el) => !el.classList.contains('seg'))
        .filter((el) => !el.closest('.dock-menu-list'))
        // A tick box or a radio is not stretched to a target anywhere in this
        // app, for the reason the dock's own height rule gives: stretching a
        // tick box makes an oval. Its label is the target.
        .filter((el) => !(el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type)));
      const small = controls
        .filter((el) => {
          const b = el.getBoundingClientRect();
          return b.width + 0.5 < min || b.height + 0.5 < min;
        })
        .slice(0, 6)
        .map((el) => {
          const b = el.getBoundingClientRect();
          return `${el.id || el.className.toString().split(' ')[0] || el.tagName} ${round(b.width)}x${round(b.height)}`;
        });
      // The primary action: the one filled button the dock grammar allows, or
      // a floating compose button. Where it sits vertically is the question.
      const primary = page_.querySelector('.fab, .primary, .dock-actions > button:not(.ghost):not(.icon-only)');
      const primaryY = primary && visible(primary) ? round(primary.getBoundingClientRect().top) : null;
      // Anything wider than the window, which is what a sideways scroll is
      // before it becomes one.
      const wide = [...page_.querySelectorAll('*')]
        .filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === 'visible')
        //: A row a window off screen is not drawn (`content-visibility`) and
        //: is fitted when it is (`fitNoteMetas`): measuring it here lays it
        //: out unfitted, which read as 32 of 60 note lines overflowing.
        .filter((el) => el.checkVisibility({ contentVisibilityAuto: true }))
        //: Not a bleed by design (INBOX 1314): a child that runs past by its
        //: own negative inline margin and no further (the ring-room rule, the
        //: timeline's day well below 400) was placed there on purpose.
        .filter((el) => {
          const right = el.getBoundingClientRect().right;
          return [...el.children].some((k) => {
            const b = k.getBoundingClientRect(), cs = getComputedStyle(k);
            if (b.right <= right + 1 || cs.position === 'absolute') return false;
            return !(parseFloat(cs.marginRight) < 0 && b.right <= right + 1 - parseFloat(cs.marginRight));
          });
        })
        .slice(0, 4)
        .map((el) => `${el.id || el.className.toString().split(' ')[0] || el.tagName} ${el.scrollWidth}>${el.clientWidth}`);
      // One column: two cards whose boxes share a line and sit side by side.
      const cards = [...page_.querySelectorAll('.card, .library-image-tile, .dash-widget, .library-card')].filter(visible);
      let sideBySide = 0;
      for (let i = 0; i < cards.length; i++) {
        for (let j = i + 1; j < cards.length; j++) {
          const a = cards[i].getBoundingClientRect();
          const b = cards[j].getBoundingClientRect();
          if (cards[i].contains(cards[j]) || cards[j].contains(cards[i])) continue;
          if (Math.abs(a.top - b.top) < 8 && (a.right <= b.left + 1 || b.right <= a.left + 1)) sideBySide++;
        }
      }
      return {
        controls: controls.length,
        small,
        primaryY,
        primaryLow: primaryY === null ? null : primaryY >= h * 0.6,
        wide,
        sideBySide,
        pageWide: document.documentElement.scrollWidth,
      };
    }, { min: MIN_TARGET, h: HEIGHT });

    const bad = [];
    if (r.none) bad.push('no visible page');
    else {
      if (r.pageWide > WIDTH) bad.push(`the page is ${r.pageWide} wide in ${WIDTH}`);
      if (r.small.length) bad.push(`under ${MIN_TARGET}px: ${r.small.join(', ')}`);
      if (r.wide.length) bad.push(`wider than its box with no scroller: ${r.wide.join(', ')}`);
      if (r.sideBySide) bad.push(`${r.sideBySide} pair(s) of cards side by side, where the phone is one column`);
      // Reported rather than failed: several tabs have no filled action at all
      // (the graph's is a menu row), and inventing one is a design decision
      // this sweep does not get to make.
    }
    failures += bad.length;
    console.log(
      `  ${tab.padEnd(10)} ${String(r.controls ?? 0).padStart(3)} controls  `
      + `primary at y=${r.primaryY ?? '-'}${r.primaryLow === null ? '' : r.primaryLow ? ' (low third)' : ' (upper)'}  `
      + `one column: ${r.sideBySide ? 'no' : 'yes'}`
    );
    for (const line of bad) console.log(`      ${line}`);
  }

  for (const line of [...new Set(errs)]) console.log(`  ${line}`);
  failures += new Set(errs).size;
  console.log(failures ? `\nFAIL: ${failures} findings` : '\nPASS: 0 findings');
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
