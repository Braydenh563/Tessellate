// INBOX 1316: the density strip's span reaches the newest row, so a future
// reminder moves the window up rather than pinning it at the top.
//   BASE=http://127.0.0.1:8781 node timeline1316.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(2500);
  const due = new Date(Date.now() + 90 * 86400000).toISOString();
  await page.evaluate(async (due) => {
    await apiJson('/reminders', { method: 'POST', body: JSON.stringify({ text: 'Strip check 1316', due_at: due }) });
  }, due);
  await page.evaluate(() => switchTab('timeline'));
  await page.waitForTimeout(3000);
  const out = await page.evaluate(() => {
    const span = timelineDensitySpan();
    const head = timelineRows[0];
    const days = Object.keys(timelineDensity).sort();
    return {
      head: head && head.when.toISOString().slice(0, 10),
      densityNewest: days[days.length - 1],
      spanNewest: span && new Date(span.newest).toISOString().slice(0, 10),
      stripHidden: document.getElementById('timeline-scrubber').classList.contains('hidden'),
      path: (document.getElementById('timeline-density-path').getAttribute('d') || '').length,
    };
  });
  // The strip shows only on a large notebook; shown by hand to read the window.
  const ys = [];
  for (const top of [0, 500, 1500]) {
    ys.push(await page.evaluate(async (top) => {
      const box = document.getElementById('timeline-scroll');
      box.scrollTop = top;
      await new Promise((r) => setTimeout(r, 400));
      document.getElementById('timeline-scrubber').classList.remove('hidden');
      drawTimelineWindow();
      return Number(document.getElementById('timeline-scrubber-window').getAttribute('y'));
    }, top));
  }
  out.windowY = ys;
  console.log(JSON.stringify(out));
  await browser.close();
})();
