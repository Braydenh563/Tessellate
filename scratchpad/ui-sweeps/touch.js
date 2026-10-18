// Touch targets, on a real touch context (UI_MODERNISATION_PLAN.md Phase 9).
//
// A `hasTouch` + `isMobile` browser context is not decoration here: it is what
// makes `(hover: none)` and `(pointer: coarse)` match, so the page under test
// is the page a phone gets rather than a desktop page in a narrow window.
//
// Three questions per control, and the third is the one a size check alone
// cannot answer:
//
//   1. Is the hit target at least 44 CSS px on both sides? That is the figure
//      Phase 9's `--target-min` steps up to below 820, and the figure both
//      platform guidelines give.
//   2. Does a tap at its centre actually reach it? A control can be the right
//      size and still be covered by a sheet, a sticky strip or a floating
//      button, and `elementFromPoint` is the only thing that knows.
//   3. Does any tap land on two controls? Two targets whose 44px boxes overlap
//      means one of them takes taps meant for the other, and the person doing
//      the tapping has no way to tell which.
//
//   BASE=http://127.0.0.1:8802 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node touch.js
//
// Prints one line per surface and a non-zero exit if anything fails, so it can
// gate a commit. No screenshots.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);
// **The floor is the band's own, not a constant.** `--target-min` steps up to
// 2.75rem below 820 and is 1.75rem above it (00-tokens-shell.css,
// 07-whiteboard-misc.css), so a 44px floor asserted at 1024 is asserting
// something the design has never promised there: measured, this sweep reported
// 130 findings at 820 and 129 at 1024 against 0 at 390, and every one of them
// was a control sized exactly as its band says. Reading the floor off the band
// makes the sweep say something true at every width instead of only below 820.
const MIN = WIDTH < 820 ? 44 : 28;

// Every dock the app has, plus the three control surfaces that are docks by
// any other name (the chat composer, the dashboard's own widgets, the
// settings sheet). This list used to be three rows, which is how the Notes
// categories overflow at 390 stayed unseen for a session: a sweep only knows
// about what it is pointed at, so "touch PASS" over three surfaces is a
// statement about three surfaces and nothing else.
//
// `open` is a selector clicked after the tab switch, for a surface that lives
// behind a sub-tab; `close` is clicked after the surface has been measured,
// for the ones that are modal and would otherwise cover everything measured
// next.
const SURFACES = [
  { tab: 'notes', label: 'Notes dock', sel: '[data-dock-name="notes"]' },
  { tab: 'notes', label: 'Notes sub-tabs', sel: '#notes-subtabs' },
  { tab: 'chat', label: 'Chat composer', sel: '.chat-dock' },
  { tab: 'dashboard', label: 'Dashboard', sel: '#tab-dashboard' },
  // Find anything (Brief 90, row 7): its field was 22px tall.
  { tab: 'dashboard', label: 'Find anything', sel: '#finder-overlay', openFn: 'openFinder()', close: '#finder-close' },
  { tab: 'graph', label: 'Graph dock', sel: '[data-dock-name="graph"]' },
  { tab: 'timeline', label: 'Timeline dock', sel: '[data-dock-name="timeline"]' },
  { tab: 'reminders', label: 'Reminders dock', sel: '[data-dock-name="reminders"]' },
  { tab: 'library', label: 'Library sub-tabs', sel: '#library-subtabs' },
  { tab: 'library', label: 'Library dock', sel: '[data-dock-name="library"]' },
  { tab: 'library', label: 'Lib Documents', sel: '[data-dock-name="library-docs"]',
    open: '#library-subtabs button[data-target="library-view-docs"]' },
  { tab: 'library', label: 'Lib Boards', sel: '[data-dock-name="library-boards"]',
    open: '#library-subtabs button[data-target="library-view-whiteboard"]' },
  { tab: 'library', label: 'Lib Images', sel: '[data-dock-name="library-media"]',
    open: '#library-subtabs button[data-media-kind="images"]' },
  { tab: 'library', label: 'Lib skills', sel: '[data-dock-name="library-skills"]',
    open: '#library-subtabs button[data-target="library-view-skills"]' },
  { tab: 'library', label: 'Lib Links', sel: '[data-dock-name="library-links"]',
    open: '#library-subtabs button[data-target="library-view-links"]' },
  { tab: 'library', label: 'Lib Contents', sel: '[data-dock-name="library-contents"]',
    open: '#library-subtabs button[data-target="library-view-contents"]' },
  // One row per section worth a finger: the sheet shows a single section at a
  // time, so "Settings" measured one section's controls and said nothing of the
  // rest.
  // The code editor's run panel (Brief 69): a .js document run once, so the
  // panel's head, its grip (`extra`: a separator is a control a finger drags)
  // and its Input box are measured. Run only by name (ONLY=Run), since it
  // creates a document.
  { tab: 'library', label: 'Run panel', sel: '.cm-run-panel', extra: '[role="separator"]', wait: 7000, byName: true,
    openFn: "(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1200)); const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'touch-run.js', content: 'console.log(1)', file_type: 'js' }) }); await loadDocuments(d.id); await new Promise((r) => setTimeout(r, 800)); await docRunCode(); })()" },
  // Brief 71 (I3): the panel on its Console tab (the tabs, the console's
  // line), the editor's palette (Ctrl+Shift+P) and the keys sheet, at 390.
  { tab: 'library', label: 'Run panel console', sel: '.cm-run-panel', extra: '[role="separator"]', wait: 7000, byName: true,
    openFn: "(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1200)); const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'touch-console.js', content: 'console.log(1)', file_type: 'js' }) }); await loadDocuments(d.id); await new Promise((r) => setTimeout(r, 800)); await docRunCode(); docRunShowTab('console'); })()" },
  { tab: 'library', label: 'Editor palette', sel: '#palette-card', wait: 6000, byName: true, closeFn: 'closePalette()',
    openFn: "(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1200)); const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'touch-palette.js', content: 'let a = 1;', file_type: 'js' }) }); await loadDocuments(d.id); for (let i = 0; i < 40 && typeof docIdeOpenPalette !== 'function'; i++) await new Promise((r) => setTimeout(r, 250)); await docIdeOpenPalette(); })()" },
  { tab: 'library', label: 'Editor keys sheet', sel: '#doc-keys-overlay .modal-card', wait: 6000, byName: true, closeFn: 'docIdeCloseKeys()',
    openFn: "(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1200)); const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'touch-keys.js', content: 'let a = 1;', file_type: 'js' }) }); await loadDocuments(d.id); for (let i = 0; i < 40 && typeof docIdeOpenKeys !== 'function'; i++) await new Promise((r) => setTimeout(r, 250)); docIdeOpenKeys(); })()" },
  // The Debug tab (Brief 70): the same panel paused on a breakpoint inside a
  // call, with a watch, so the five actions, the stack and breakpoint rows,
  // the watch's remove and its field are all there to measure. ONLY=Debug.
  { tab: 'library', label: 'Debug tab', sel: '.cm-run-panel', wait: 7000, byName: true,
    openFn: "(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1200)); const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'touch-debug.js', content: 'function f(n) {\\n  return n * 2;\\n}\\nvar x = f(1);\\n', file_type: 'js' }) }); await loadDocuments(d.id); await new Promise((r) => setTimeout(r, 800)); docDebugToggleAt(docCmView, docCmView.state.doc.line(2).from); DOC_DEBUG.watches.push('n'); await docRunCode({ mode: 'debug' }); })()" },
  ...['general', 'models', 'appearance', 'preferences', 'data', 'privacy', 'account'].map((section) => ({
    tab: 'notes', label: `Settings ${section}`, sel: `#settings-modal #settings-${section}`,
    //: The first open loads settings-controls.js and the section's own bundle;
    //: 900 ms was not always enough, and a section still loading measured as "did
    //: not open" (INBOX 1308 named appearance and privacy, then general, models,
    //: preferences and data on a loaded machine).
    openFn: `openSettingsModal('${section}')`, wait: 4000, close: '#settings-close' })),
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
    hasTouch: true,
    isMobile: true,
  });
  // The companion's one-time nudge is a toast that lands over the bottom of
  // whatever is open (it read as "covered" on six Settings controls); lib.js
  // marks it seen for every other sweep, and so does this one.
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light');
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      localStorage.setItem('nm-buddy-hint', 'done');
    } catch (e) {}
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW); await page.click('#lock-submit'); await page.waitForTimeout(2500);
  //: The opening curtain (lib.js, INBOX 577): the lock stays up, "Opening…",
  //: while the first tab draws; read as a failed unlock, the field was
  //: filled again as it faded and the fill timed out (qa-1005, light 390).
  await page.waitForFunction(() => !document.documentElement.classList.contains('shell-curtain')
    && !document.querySelector('#lock-overlay.lock-leaving'), null, { timeout: 15000, polling: 100 }).catch(() => {});
  if (await page.$('#lock-password') && await page.isVisible('#lock-password')) {
    await page.fill('#lock-password', PW); await page.click('#lock-submit'); await page.waitForTimeout(2500);
  }
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  await page.waitForTimeout(800);

  const media = await page.evaluate(() => ({
    hoverNone: matchMedia('(hover: none)').matches,
    coarse: matchMedia('(pointer: coarse)').matches,
    targetMin: getComputedStyle(document.documentElement).getPropertyValue('--target-min').trim(),
  }));
  console.log(`context ${WIDTH}x${HEIGHT}  hover:none=${media.hoverNone}  pointer:coarse=${media.coarse}  --target-min=${media.targetMin}`);
  if (!media.hoverNone) errors.push('the context is not reporting (hover: none) — the hover gating is not being exercised');

  let failures = 0;
  // ONLY="Settings|Dashboard" runs the rows whose label matches, for a quick pass.
  const only = process.env.ONLY ? new RegExp(process.env.ONLY, 'i') : null;
  for (const surface of SURFACES) {
    if (only && !only.test(surface.label)) continue;
    if (surface.byName && !only) continue;
    // A tab with no visible button in the bar (Dashboard, Timeline and
    // Reminders live behind the phone's More sheet below 600) cannot be
    // clicked, and the old `.catch(() => {})` swallowed that: the page stayed on
    // the previous tab, the surface was `display: none`, and the row measured
    // "0 controls" and passed. A visible button is clicked as a finger would;
    // otherwise the app's own `switchTab` is what the More sheet calls.
    const viaBar = await page.isVisible(`#tab-bar [data-tab="${surface.tab}"]`).catch(() => false);
    if (viaBar) await page.click(`#tab-bar [data-tab="${surface.tab}"]`);
    else await page.evaluate((name) => switchTab(name), surface.tab);
    await page.waitForTimeout(600);
    if (surface.openFn) {
      // The settings sheet's opener (#settings-btn) is inside the phone's
      // header kebab below 600, so it is opened through the function the kebab
      // row calls.
      await page.evaluate((src) => { (0, eval)(src); }, surface.openFn);
      await page.waitForTimeout(surface.wait || 900);
    } else if (surface.open) {
      await page.click(surface.open).catch(() => {});
      await page.waitForTimeout(700);
    }

    // A tab's first visit loads its lazy module: 750 to 1470ms measured on a
    // loaded machine against the 600ms above, which read "did not open" for
    // the Graph and Library rows in dark, then light, at random (uxfix3 item 3).
    await page.waitForSelector(surface.sel, { state: 'visible', timeout: 6000 }).catch(() => {});
    const result = await page.evaluate(({ sel, MIN, extra }) => {
      const root = document.querySelector(sel);
      if (!root) return { missing: true };
      const visible = (e) => e.checkVisibility
        && e.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true });
      const controls = [...root.querySelectorAll(`button, select, summary, input:not([type="hidden"]), .seg${extra ? ', ' + extra : ''}`)]
        .filter(visible)
        // Three kinds of element are deliberately unreachable and each has a
        // visible control standing for it: a `<select>` kept only as the value
        // a handler reads (`.dock-native-hidden`), the app's clipped
        // screen-reader recipes (`.visually-hidden`, `.sr-only` — the chat
        // composer's file input is one, driven by a visible paperclip), and a
        // `.seg` group, whose own buttons are what a finger lands on.
        .filter((e) => !e.closest('.dock-native-hidden, .select-native-hidden, .visually-hidden, .sr-only'))
        .filter((e) => !e.classList.contains('seg'))
        .filter((e) => !e.closest('.dock-menu-list'));

      const name = (e) => `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : '.' + [...e.classList].slice(0, 2).join('.')}`;

      // A switch and a radio are deliberately small, and the app's
      // own decision (06-timeline-dialogs.css, the `.checkbox-label` note) is
      // that the *label* around them is the hit area: a global floor on the
      // input itself turned every switch into a slab with its knob adrift,
      // and was reported with a screenshot within the hour. So measure what a
      // person actually aims at. Only these two: every other control is its
      // own target, and substituting a label for a button would hide a real
      // finding behind a roomy row. A *slider* is its own target too: a tap on
      // its label focuses it and moves nothing, and measuring the label let a
      // 6.8x16px Settings slider pass as "How alike", 71x22.
      const target = (e) => {
        const kind = (e.getAttribute('type') || '').toLowerCase();
        if (e.tagName !== 'INPUT' || !['checkbox', 'radio'].includes(kind)) return e;
        return e.closest('label') || document.querySelector(`label[for="${CSS.escape(e.id)}"]`) || e;
      };

      const small = [];
      const covered = [];
      const shared = [];

      // Two passes, and the order matters. Every box is measured first, at one
      // scroll position, so the size and overlap answers are all in the same
      // frame of reference; only then does the reachability pass scroll things
      // about. Doing both in one pass compared a control measured at the top of
      // the page with one measured after a scroll, and invented collisions
      // between controls a screen apart.
      const boxes = controls.map((control) => target(control).getBoundingClientRect());

      const seen = new Map();
      controls.forEach((control, index) => {
        const box = boxes[index];
        if (box.width + 0.5 < MIN || box.height + 0.5 < MIN) {
          small.push(`${name(control)} ${box.width.toFixed(1)}x${box.height.toFixed(1)}`);
        }
        const key = `${Math.round(box.left + box.width / 2)},${Math.round(box.top + box.height / 2)}`;
        if (seen.has(key)) shared.push(`${name(control)} shares ${key} with ${seen.get(key)}`);
        else seen.set(key, name(control));
      });

      for (const raw of controls) {
        const control = target(raw);
        let box = control.getBoundingClientRect();
        // Bring it into view before asking what is on top of it. Without this
        // every control below the fold, and every one in a sideways-scrolling
        // strip (the sub-tab segs, the dashboard's quick links), reported
        // "hits nothing" - which is true of a point outside the viewport and
        // says nothing at all about whether a finger can reach the control.
        // Fifteen such lines in one run were all this, and a sweep that cries
        // wolf fifteen times is a sweep nobody reads.
        if (box.top < 0 || box.left < 0
            || box.bottom > innerHeight || box.right > innerWidth) {
          control.scrollIntoView({ block: 'center', inline: 'center' });
          box = control.getBoundingClientRect();
        }
        const x = Math.round(box.left + box.width / 2);
        const y = Math.round(box.top + box.height / 2);
        // Still outside after scrolling: a control its own scroll container
        // cannot reach. That is a finding, not a pass.
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) {
          covered.push(`${name(control)} cannot be scrolled into view (centre ${x},${y})`);
          continue;
        }
        let hit = document.elementFromPoint(x, y);
        let reached = hit && (control.contains(hit) || hit.contains(control));
        const firstHit = hit ? name(hit) : 'nothing';
        if (!reached) {
          // Second chance, and it is not a weakening: a control near the end
          // of a scroll container cannot be centred, so `scrollIntoView` puts
          // it wherever the remaining scroll allows, which at the bottom of
          // the dashboard is under the *fixed* tab bar. A person scrolls a
          // little less far and taps it. Asking again from a scroll position
          // the person could actually choose is the honest question; a
          // control that is covered at every position still fails here.
          control.scrollIntoView({ block: 'start', inline: 'center' });
          const again = control.getBoundingClientRect();
          const ax = Math.round(again.left + again.width / 2);
          const ay = Math.round(again.top + again.height / 2);
          if (ax >= 0 && ay >= 0 && ax <= innerWidth && ay <= innerHeight) {
            hit = document.elementFromPoint(ax, ay);
            reached = hit && (control.contains(hit) || hit.contains(control));
          }
        }
        if (!reached) {
          // Third and last chance: a *sticky* strip (the settings sheet's
          // section tabs) is not part of `innerHeight`, so a control inside the
          // viewport can sit under it at its first position, and `block: 'start'`
          // above scrolls it straight under that same strip. Centred is where a
          // person's own scroll leaves it, clear of a header at the top and
          // the bottom bar alike; a control covered here too is covered for real.
          control.scrollIntoView({ block: 'center', inline: 'center' });
          const mid = control.getBoundingClientRect();
          const mx = Math.round(mid.left + mid.width / 2);
          const my = Math.round(mid.top + mid.height / 2);
          if (mx >= 0 && my >= 0 && mx <= innerWidth && my <= innerHeight) {
            hit = document.elementFromPoint(mx, my);
            reached = hit && (control.contains(hit) || hit.contains(control));
          }
        }
        if (!reached) {
          covered.push(`${name(control)} at ${x},${y} hits ${firstHit}, then ${hit ? name(hit) : 'nothing'} then centred (on top: ${(hit && (hit.closest('.toast, [role=status], dialog, .modal-overlay, nav, .dock') || hit).textContent || '').trim().replace(/\s+/g, ' ').slice(0, 50)})`);
        }
      }
      return { count: controls.length, small, covered, shared };
    }, { sel: surface.sel, MIN, extra: surface.extra || "" });

    if (surface.close) {
      await page.click(surface.close).catch(() => {});
      await page.waitForTimeout(400);
    }
    //: An overlay with no close button of its own (the palette) shuts by its
    //: own function, so the next row's tab is not under it.
    if (surface.closeFn) {
      await page.evaluate((src) => { (0, eval)(src); }, surface.closeFn);
      await page.waitForTimeout(400);
    }

    if (result.missing) {
      console.log(`${surface.label.padEnd(16)} NOT FOUND (${surface.sel})`);
      failures += 1;
      continue;
    }
    // A row that measured nothing is a failure, not a pass: that is how
    // Dashboard, Timeline, Reminders and Settings sat at "0 controls" green.
    if (result.count === 0) {
      console.log(`${surface.label.padEnd(16)} 0 controls MEASURED (the surface did not open or is hidden)`);
      if (process.env.DEBUG_OPEN) console.log(JSON.stringify(await page.evaluate((sel) => { const e = document.querySelector(sel); const cs = e && getComputedStyle(e); return { active: document.querySelector('.tab-page:not(.hidden)')?.id, hash: location.hash, el: !!e, display: cs && cs.display, vis: cs && cs.visibility, op: cs && cs.opacity, hidden: e && e.closest('.hidden,[hidden]')?.id, overlays: [...document.querySelectorAll('.modal-overlay:not(.hidden)')].map((o) => o.id) }; }, surface.sel)));
      failures += 1;
      continue;
    }
    const bad = result.small.length + result.covered.length + result.shared.length;
    failures += bad;
    console.log(`${surface.label.padEnd(16)} ${result.count} controls  under-${MIN}px: ${result.small.length}  covered: ${result.covered.length}  overlapping taps: ${result.shared.length}`);
    for (const line of [...result.small, ...result.covered, ...result.shared]) console.log(`    ${line}`);
  }

  // And the bottom tab bar, which is the one control row every tab shares.
  //
  // The bar is `#phone-tab-dock` below 600 (UI_MODERNISATION_PLAN Phase 11):
  // the strip is inside it and More is its second child, because a
  // `role="tablist"` may not hold a button that is not a tab. So the box to
  // measure is the dock where there is one, and the columns to measure are
  // the strip's buttons *plus* More.
  //
  // A button with no box at all is skipped rather than reported. Three of the
  // seven tabs are `display: none` in that band and are reached through the
  // More sheet instead: a control that is not on screen is not a target that
  // is too small, and reporting it as one (0.0x0.0, three times) is the
  // cry-wolf shape this sweep's own comment above warns about.
  const tabs = await page.evaluate((MIN) => {
    const strip = document.getElementById('tab-bar');
    const dock = document.getElementById('phone-tab-dock');
    const bar = dock && dock.getClientRects().length ? dock : strip;
    const more = document.getElementById('phone-more-btn');
    const columns = [...strip.querySelectorAll('button')];
    if (more && bar === dock) columns.push(more);
    const out = [];
    for (const button of columns) {
      if (!button.getClientRects().length) continue;
      const box = button.getBoundingClientRect();
      if (box.width + 0.5 < MIN || box.height + 0.5 < MIN) {
        out.push(`${button.id} ${box.width.toFixed(1)}x${box.height.toFixed(1)}`);
      }
    }
    const b = bar.getBoundingClientRect();
    return { small: out, atBottom: Math.abs(b.bottom - window.innerHeight) < 1.5, scrolls: bar.scrollWidth > bar.clientWidth + 1 };
  }, MIN);
  failures += tabs.small.length;
  // The bottom tab bar is a rule of the phone band (< 600) alone: between
  // 600 and 1100 the strip takes a row of its own inside the header, on
  // purpose, and asserting the phone's shape at 800 reported a failure for
  // a layout that is behaving exactly as its band says it should.
  if (WIDTH < 600 && !tabs.atBottom) { failures += 1; console.log('tab bar          NOT pinned to the bottom edge'); }
  if (tabs.scrolls) { failures += 1; console.log('tab bar          scrolls sideways — a tab is out of reach'); }
  console.log(`tab bar          under-${MIN}px: ${tabs.small.length}  pinned to bottom: ${tabs.atBottom}  scrolls: ${tabs.scrolls}`);
  for (const line of tabs.small) console.log(`    ${line}`);

  // The page itself must not slide sideways. This is the check that found the
  // 7px the header was over at 390 on all seven tabs: every individual
  // surface passed its own measurements while the whole application moved
  // under the finger, because nothing was asking the one question a phone
  // makes obvious.
  const slide = await page.evaluate(() => {
    const out = [];
    for (const tab of ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders']) {
      const button = document.querySelector(`[data-tab="${tab}"]`);
      if (button) button.click();
      const root = document.documentElement;
      if (root.scrollWidth > root.clientWidth + 0.5) {
        out.push(`${tab}: page scrolls sideways, ${root.scrollWidth} in ${root.clientWidth}`);
      }
    }
    return out;
  });
  failures += slide.length;
  console.log(`sideways scroll   ${slide.length ? slide.length + ' tabs' : 'none'}`);
  for (const line of slide) console.log(`    ${line}`);

  for (const line of errors) console.log(`    ${line}`);
  failures += errors.length;

  console.log(failures ? `FAIL: ${failures} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
