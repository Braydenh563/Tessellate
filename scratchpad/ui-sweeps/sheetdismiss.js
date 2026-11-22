// The dismissal every sheet keeps (DESIGN.md, "A sheet"; UI_MODERNISATION_PLAN
// Phase 11). `openSheet` owns its own; the two in-place sheets go through
// `wireInPlaceSheetDismissal`, and this is what that has to mean on screen.
//
//   BASE=http://127.0.0.1:8792 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     timeout 110 node scratchpad/ui-sweeps/sheetdismiss.js
//
// At 390x844, for the Notes sidebar sheet and for the More sheet: it opens, a
// captured Escape closes it even with a page-level Escape handler that stops
// propagation bound after the app's, a press on the content behind closes it,
// and focus lands back on the control that opened it.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 } });
  const fails = [];
  const check = (label, ok, detail) => {
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}: ${detail}`);
    if (!ok) fails.push(label);
  };

  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1200);

  // The trap this sweep exists for, and the reason the listener is captured
  // rather than bubbling: a handler on an element *inside* the page that stops
  // an Escape. `document.body` is a descendant of `document`, so a bubbling
  // listener on `document` never sees the event at all, while a captured one
  // runs before body's on the way down. Bound here at runtime rather than
  // relying on whichever real handler happens to do this today.
  await page.evaluate(() => {
    document.body.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') e.stopPropagation();
    });
  });

  const opened = await page.evaluate(() => {
    const toggle = document.querySelector('#sidebar .sidebar-collapse-toggle');
    if (!toggle) return { ok: false, why: 'no sidebar toggle' };
    toggle.click();
    const aside = document.getElementById('sidebar');
    return {
      ok: aside.classList.contains('sidebar-sheet-open'),
      expanded: toggle.getAttribute('aria-expanded'),
    };
  });
  check('the sidebar sheet opens from its rail', opened.ok === true, JSON.stringify(opened));

  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  const afterEsc = await page.evaluate(() => ({
    open: document.getElementById('sidebar').classList.contains('sidebar-sheet-open'),
    focus: document.activeElement && document.activeElement.className,
    expanded: document.querySelector('#sidebar .sidebar-collapse-toggle')?.getAttribute('aria-expanded'),
  }));
  check(
    'a captured Escape closes it past a handler that swallows Escape',
    afterEsc.open === false,
    JSON.stringify(afterEsc)
  );
  check(
    'focus goes back to the opener, which says it is shut',
    // The rail's toggle, or below 600 the head's opener that stands for it.
    /sidebar-collapse-toggle|phone-sidebar-opener/.test(String(afterEsc.focus)) && afterEsc.expanded === 'false',
    JSON.stringify(afterEsc)
  );

  // And a press on the page behind it.
  await page.evaluate(() => document.querySelector('#sidebar .sidebar-collapse-toggle').click());
  await page.waitForTimeout(300);
  await page.mouse.click(360, 500);
  await page.waitForTimeout(300);
  const afterOutside = await page.evaluate(() =>
    document.getElementById('sidebar').classList.contains('sidebar-sheet-open')
  );
  check('a press outside closes it', afterOutside === false, `open: ${afterOutside}`);

  // The recipe's own sheet, for the same three things.
  const more = await page.evaluate(async () => {
    const btn = document.getElementById('phone-more-btn');
    if (!btn) return { skipped: 'no More button at this width' };
    btn.click();
    // The sheet is a lazy module now (phoneMore): it builds and takes focus a beat after the press.
    await new Promise((r) => setTimeout(r, 600));
    // The More sheet by name: the press-outside step above can land on a
    // note row, which opens the note page, a sheet of its own.
    const overlay = document.querySelector('.sheet-overlay[data-sheet="more"]');
    return {
      open: !!overlay,
      inside: overlay ? overlay.contains(document.activeElement) : null,
      modal: overlay ? overlay.getAttribute('aria-modal') : null,
    };
  });
  check('the More sheet opens with focus inside it', more.open === true && more.inside === true, JSON.stringify(more));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  const moreAfter = await page.evaluate(() => ({
    open: !!document.querySelector('.sheet-overlay[data-sheet="more"]'),
    focus: document.activeElement && document.activeElement.id,
  }));
  check(
    'Escape closes the More sheet and hands focus back',
    moreAfter.open === false && moreAfter.focus === 'phone-more-btn',
    JSON.stringify(moreAfter)
  );

  console.log(fails.length ? `FAILURES: ${fails.length}` : 'all clear');
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
