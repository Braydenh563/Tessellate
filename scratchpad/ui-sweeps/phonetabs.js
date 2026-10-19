// The bottom tab bar at phone widths (UI_MODERNISATION_PLAN Phase 11, item 1).
//
// The bar itself was built in Phase 9, and the measurement that matters here is
// not whether it is pinned (it is) but whether it says anything: at 360 and 390
// every one of the seven captions was hidden, so which tab you are on was
// carried by colour alone on seven identical glyphs.
//
// Four questions, per width, and per tab, because the answer changes with which
// tab is selected (the selected one is the one that keeps its caption):
//
//   1. Is the strip on one row, not scrolling sideways? A caption that grows a
//      column is how a seven-column bar starts scrolling.
//   2. Does the selected tab show its whole caption, unclipped?
//   3. Are the other six captions off?
//   4. Is every column still a 44px target, and the bar still flush to the
//      bottom edge?
//
//   BASE=http://127.0.0.1:8961 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node phonetabs.js
//
// Non-zero on any of the four. 320 is in the set because it is the narrowest
// width the shell is held to (Phase 11 item 10).
const { boot } = require('./lib.js');

const WIDTHS = [320, 360, 390, 430];
const MIN_TARGET = 44;
// Every tab, because "Dashboard" and "Reminders" are the two captions the
// blanket-hide rule was written for and they are the two that decide this.
const TABS = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];

(async () => {
  const { browser, page } = await boot({ viewport: { width: WIDTHS[0], height: 844 } });
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  page.on('pageerror', (e) => errs.push(`pageerror: ${e.message}`));
  let failures = 0;

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForTimeout(500);
    console.log(`\n--- ${width}x844`);
    for (const tab of TABS) {
      await page.evaluate((t) => switchTab(t), tab);
      await page.waitForTimeout(350);
      const r = await page.evaluate((min) => {
        // Since the five-column bar landed, `#tab-bar` is the strip and
        // `#phone-tab-dock` is the bar around it, holding the strip and the
        // More button. The questions below are about the bar, and the columns
        // are the ones actually on screen: the three tabs that moved into the
        // More sheet are `display: none` here and have no box to measure.
        const dock = document.getElementById('phone-tab-dock');
        const bar = dock && getComputedStyle(dock).display !== 'none' ? dock : document.getElementById('tab-bar');
        const box = bar.getBoundingClientRect();
        const buttons = [...bar.querySelectorAll('button')]
          .filter((b) => b.getBoundingClientRect().width > 0);
        const active = buttons.find((b) => b.classList.contains('active') && b.dataset.tab);
        const label = active?.querySelector('.tab-label');
        const shown = buttons.filter((b) => {
          const l = b.querySelector('.tab-label');
          return l && getComputedStyle(l).display !== 'none';
        }).length;
        const small = buttons.filter((b) => {
          const r = b.getBoundingClientRect();
          return r.width + 0.5 < min || r.height + 0.5 < min;
        }).map((b) => `${b.id} ${b.getBoundingClientRect().width.toFixed(1)}x${b.getBoundingClientRect().height.toFixed(1)}`);
        return {
          active: active ? active.id.replace('tab-btn-', '') : null,
          caption: label ? (label.textContent || '').trim() : null,
          captionClipped: label ? label.scrollWidth > label.clientWidth + 0.5 : false,
          captionWidth: label ? +label.getBoundingClientRect().width.toFixed(1) : 0,
          shownCaptions: shown,
          columns: buttons.length,
          activeWidth: active ? +active.getBoundingClientRect().width.toFixed(1) : 0,
          widest: Math.max(...buttons.map((b) => +b.getBoundingClientRect().width.toFixed(1))),
          narrowest: Math.min(...buttons.map((b) => +b.getBoundingClientRect().width.toFixed(1))),
          scrolls: bar.scrollWidth > bar.clientWidth + 1,
          needs: bar.scrollWidth,
          has: bar.clientWidth,
          atBottom: Math.abs(box.bottom - innerHeight) < 1.5,
          pageSlides: document.documentElement.scrollWidth > document.documentElement.clientWidth + 0.5,
          small,
        };
      }, MIN_TARGET);

      const bad = [];
      if (!r.active) {
        // One of the three the More sheet holds: the strip has no column for
        // it, More is lit instead, and `phonemore.js` owns that claim.
        console.log(`  ${tab.padEnd(10)} (in the More sheet; More lit, see phonemore.js)`);
        continue;
      }
      if (r.scrolls) bad.push(`the strip scrolls sideways (${r.needs} in ${r.has})`);
      if (r.pageSlides) bad.push('the page scrolls sideways');
      if (!r.atBottom) bad.push('the bar is not flush to the bottom edge');
      // **Below 360 no caption is the right answer, and it is arithmetic rather
      // than a concession**: seven columns at the 44px floor need 308px, which
      // fits 320, and one of them carrying "Reminders" needs 344.2px, which does
      // not. So the narrowest band trades the caption for the hit target, and a
      // sweep that demanded a caption there would be demanding a 40px tab.
      //
      // **Five columns changed the answer, and the arithmetic is the reason.**
      // Seven captions need 476px and five need 340, so at 360 and above every
      // column keeps its word rather than only the selected one. At 320 five
      // columns are 64px each and the words still fit, which is what
      // `phonemore.js` measured; this sweep holds the floor rather than the
      // ceiling, so it asks for all of them from 320 up.
      const wantsCaption = true;
      if (wantsCaption && r.shownCaptions !== r.columns) bad.push(`${r.shownCaptions} of ${r.columns} columns show a caption`);
      if (wantsCaption && !r.caption) bad.push('the selected tab has no caption');
      if (wantsCaption && r.captionClipped) bad.push(`the selected caption is clipped ("${r.caption}")`);
      if (r.small.length) bad.push(`under ${MIN_TARGET}px: ${r.small.join(', ')}`);
      failures += bad.length;
      console.log(`  ${String(r.active).padEnd(10)} "${r.caption}" ${r.captionWidth}px in a ${r.activeWidth}px column`
        + `  others ${r.narrowest}..${r.widest}  strip ${r.needs}/${r.has}  captions shown ${r.shownCaptions}`);
      for (const line of bad) console.log(`      ${line}`);
    }
  }

  // --- the recede on scroll down (INBOX 104) -------------------------------
  // Liquid Glass rule 10, and both halves of it: the bar gives its captions
  // back on the way down and takes them again on the way up, and it is never
  // hidden. Driven by scrolling a real region rather than by setting the
  // attribute, because what is being gated is the listener as much as the CSS.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1500);

  const barState = () =>
    page.evaluate(() => {
      const dock = document.getElementById('phone-tab-dock');
      const box = dock.getBoundingClientRect();
      const labels = [...dock.querySelectorAll('.tab-label')];
      return {
        h: Math.round(box.height * 10) / 10,
        bottom: Math.round(box.bottom * 10) / 10,
        shown: labels.filter((l) => l.getBoundingClientRect().height > 0).length,
        receded: dock.hasAttribute('data-receded'),
        icons: [...dock.querySelectorAll('.tab-icon')].filter((i) => i.getBoundingClientRect().height > 0).length,
      };
    });

  // The region that actually scrolls on Notes, found by measuring rather than
  // by name, the same way the listener does.
  const scrollBy = async (dy) => {
    await page.evaluate((dy) => {
      const page_ = document.querySelector('.tab-page:not(.hidden)');
      const region = [...page_.querySelectorAll('*')]
        .find((el) => el.scrollHeight - el.clientHeight > 200 && getComputedStyle(el).overflowY !== 'visible')
        || document.scrollingElement;
      region.scrollTop += dy;
    }, dy);
    await page.waitForTimeout(450);
  };

  const rest = await barState();
  await scrollBy(400);
  const down = await barState();
  await scrollBy(-300);
  const up = await barState();

  const recedeBad = [];
  if (rest.receded) recedeBad.push('the bar starts receded');
  if (!down.receded) recedeBad.push(`scrolling down did not recede it (${JSON.stringify(down)})`);
  if (down.shown !== 0) recedeBad.push(`${down.shown} captions still shown while receded`);
  if (down.icons !== 5) recedeBad.push(`${down.icons} icons while receded, expected 5: a receded bar is never a hidden one`);
  if (!(down.h < rest.h)) recedeBad.push(`receded height ${down.h} is not under the resting ${rest.h}`);
  if (down.h < 44) recedeBad.push(`receded to ${down.h}px, under the 44px target floor`);
  if (Math.abs(down.bottom - rest.bottom) > 0.5) recedeBad.push('the bar left the bottom edge while receding');
  if (up.receded) recedeBad.push(`scrolling back up did not restore it (${JSON.stringify(up)})`);
  if (up.shown !== 5) recedeBad.push(`${up.shown} captions back after scrolling up, expected 5`);
  failures += recedeBad.length;
  console.log(`\n  recede  rest ${rest.h}px/${rest.shown} captions  down ${down.h}px/${down.shown}/${down.icons} icons`
    + `  up ${up.h}px/${up.shown}`);
  for (const line of recedeBad) console.log(`      ${line}`);

  // Two taps to anything (Phase 11 item 11): every tab the bar does not show
  // is one tap on More and one on its row.
  const taps = await page.evaluate(async () => {
    const out = {};
    //: The three behind More since INBOX 1314 (Dashboard took Graph's column).
    for (const tab of ['graph', 'timeline', 'reminders']) {
      document.getElementById('phone-more-btn').click();
      //: The sheet is a lazy file on the first press (phone-more.js).
      await new Promise((r) => setTimeout(r, 700));
      const rows = [...document.querySelectorAll('.sheet-overlay[data-sheet="more"] .sheet-row')];
      const want = document.querySelector(`#tab-bar button[data-tab="${tab}"] .tab-label`)?.textContent.trim();
      //: Less a count badge (Reminders carries the due count).
      const row = rows.find((r) => r.textContent.replace(r.querySelector('.tab-badge')?.textContent || '', '').trim() === want);
      if (!row) { out[tab] = 'no row in the sheet'; continue; }
      row.click();
      await new Promise((r) => setTimeout(r, 400));
      const page_ = document.getElementById(`tab-${tab}`);
      out[tab] = page_ && !page_.classList.contains('hidden') ? 2 : 'did not open';
    }
    return out;
  });
  const tapBad = Object.entries(taps).filter(([, v]) => v !== 2).map(([k, v]) => `${k}: ${v}`);
  failures += tapBad.length;
  console.log(`  two taps  ${JSON.stringify(taps)}`);
  for (const line of tapBad) console.log(`      ${line}`);

  for (const line of errs) console.log(`    console: ${line}`);
  failures += errs.length;
  console.log(failures ? `\nFAIL: ${failures} findings` : '\nPASS: 0 findings');
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
