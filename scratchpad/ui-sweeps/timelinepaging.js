// TIMELINE_PLAN.md Phase 3's gate: "a 2,000-note seed scrolls without a
// horizontal bar and without a > 100ms frame during paging (Playwright
// `requestAnimationFrame` counter)", plus what the phase adds around it: the
// cap is gone (every note is reachable by scrolling, not 1,500 of them), the
// density strip draws the whole range and a click on it jumps.
//
// Seed a data dir with `seed-timeline-bulk.py` first, and serve THAT dir:
//   .venv/bin/python scratchpad/ui-sweeps/seed-timeline-bulk.py /tmp/mm-timeline-big/memorymap.db 2000
//   bash scratchpad/ui-sweeps/serve.sh 8937 /tmp/mm-timeline-big
//   BASE=http://127.0.0.1:8937 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     SCRATCH=/tmp/claude-0 timeout 110 node timelinepaging.js
const { boot } = require('./lib.js');

let failures = 0;
const check = (label, ok, detail) => {
  if (!ok) failures += 1;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}  ${detail}`);
};

(async () => {
  const { browser, page, OUT } = await boot();
  let requests = 0;
  page.on('request', (r) => {
    if (r.url().includes('/timeline?')) requests += 1;
  });
  await page.click('[data-tab="timeline"]');
  await page.waitForTimeout(1500);
  // Everything, so the range really is the whole notebook.
  await page.evaluate(() => {
    const days = document.getElementById('timeline-days');
    days.value = '0';
    days.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(2500);

  const first = await page.evaluate(() => ({
    rows: document.querySelectorAll('.timeline-row').length,
    strip: !document.getElementById('timeline-scrubber').classList.contains('hidden'),
    path: (document.getElementById('timeline-density-path').getAttribute('d') || '').length,
    overflowX: document.getElementById('timeline-scroll').scrollWidth
      - document.getElementById('timeline-scroll').clientWidth,
  }));
  check('the first page is a page, not the notebook', first.rows > 0 && first.rows <= 300,
    `${first.rows} rows drawn`);
  check('the density strip is showing with a path', first.strip && first.path > 200,
    `strip ${first.strip ? 'shown' : 'hidden'}, path ${first.path} characters`);
  check('no horizontal scroll with 2,000 notes', first.overflowX <= 0, `${first.overflowX}px`);

  // Paging, with a frame counter running across it. `requestAnimationFrame`
  // deltas are what a person feels: one long frame is a visible stall, and the
  // plan's line is 100ms.
  const paging = await page.evaluate(async () => {
    const box = document.getElementById('timeline-scroll');
    const frames = [];
    let last = performance.now();
    let running = true;
    const tick = (now) => {
      frames.push(now - last);
      last = now;
      if (running) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    const before = timelineRows.length;
    // Four pages: scroll to the end, wait for the rows, again.
    for (let i = 0; i < 4; i++) {
      box.scrollTop = box.scrollHeight;
      await new Promise((r) => setTimeout(r, 1200));
    }
    running = false;
    const after = timelineRows.length;
    // The first frame after the counter starts includes whatever the page was
    // already doing, so it is dropped: what is being measured is the paging.
    const measured = frames.slice(1);
    return {
      before,
      after,
      worst: Math.round(Math.max(...measured)),
      frames: measured.length,
      over100: measured.filter((f) => f > 100).length,
      overflowX: box.scrollWidth - box.clientWidth,
    };
  });
  check('scrolling pages more rows in', paging.after > paging.before,
    `${paging.before} rows to ${paging.after}`);
  check('no frame over 100ms while paging', paging.over100 === 0,
    `worst frame ${paging.worst}ms over ${paging.frames} frames`);
  check('still no horizontal scroll after paging', paging.overflowX <= 0, `${paging.overflowX}px`);

  // The strip jumps, and the marker follows. Two clicks, because the strip
  // spans the whole range while the feed holds the pages loaded so far, and
  // both answers are right: inside the loaded range it lands on a row, past it
  // it goes to the end and asks for the next page.
  const near = await page.evaluate(async () => {
    const strip = document.getElementById('timeline-scrubber');
    const box = strip.getBoundingClientRect();
    document.getElementById('timeline-scroll').scrollTop = 0;
    await new Promise((r) => setTimeout(r, 400));
    const before = document.getElementById('timeline-scroll').scrollTop;
    strip.dispatchEvent(new PointerEvent('pointerdown', {
      clientX: box.left + box.width / 2,
      clientY: box.top + box.height * 0.2,
      bubbles: true,
      pointerId: 1,
    }));
    await new Promise((r) => setTimeout(r, 600));
    const focused = document.activeElement?.closest?.('.timeline-row');
    const when = focused?.querySelector('.timeline-row-when');
    return {
      before,
      after: document.getElementById('timeline-scroll').scrollTop,
      landedOn: when ? when.getAttribute('datetime') : null,
      window: Number(document.getElementById('timeline-scrubber-window').getAttribute('y')),
    };
  });
  check('a click on the strip lands on a row from that part of the range',
    near.landedOn !== null && near.after > near.before,
    `scrollTop ${Math.round(near.before)} to ${Math.round(near.after)}, landed on ${near.landedOn}`);
  check('the window marker follows the reader', near.window > 0,
    `marker at y=${near.window} of 1000`);

  const far = await page.evaluate(async () => {
    const strip = document.getElementById('timeline-scrubber');
    const box = strip.getBoundingClientRect();
    const rowsBefore = timelineRows.length;
    strip.dispatchEvent(new PointerEvent('pointerdown', {
      clientX: box.left + box.width / 2,
      clientY: box.top + box.height * 0.98,
      bubbles: true,
      pointerId: 1,
    }));
    await new Promise((r) => setTimeout(r, 1500));
    const scroll = document.getElementById('timeline-scroll');
    return {
      rowsBefore,
      rowsAfter: timelineRows.length,
      atEnd: scroll.scrollTop + scroll.clientHeight > scroll.scrollHeight - 1200,
    };
  });
  // Loaded rows (timelineRows), not DOM rows: the feed is windowed, so the DOM
  // holds a moving slice whatever was fetched.
  // The page arriving is the answer, not where the scroll ended up: appending
  // 300 rows moves the end of the feed further away than the scroll that asked
  // for them, which is the whole point of fetching early.
  check('dragging past the loaded rows asks for the next page',
    far.rowsAfter > far.rowsBefore,
    `${far.rowsBefore} rows to ${far.rowsAfter}`);

  await page.screenshot({ path: `${OUT}/timeline-paging.png` });
  await browser.close();
  console.log(`\n${requests} /timeline requests in all`);
  console.log(failures ? `${failures} check(s) failed` : 'all checks passed');
  process.exit(failures ? 1 : 0);
})();
