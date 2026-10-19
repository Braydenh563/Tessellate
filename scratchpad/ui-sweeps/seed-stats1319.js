// INBOX 1319: seed a notebook with shape for the Statistics sweeps.
//   BASE=http://127.0.0.1:8798 node seed-stats1319.js   (then back-date with seed-stats1319.py)
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(2500);
  const tags = ['work', 'idea', 'travel', 'health'];
  const SKIP = !!process.env.SKIPNOTES;
  const res = await page.evaluate(async ([tags, SKIP]) => {
    const out = { made: 0 };
    for (let i = 0; i < (SKIP ? 0 : 88); i++) {
      await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Seed note ${i} about ${tags[i % 4]} planning and a few more words to count`, tags: [tags[i % 4]] }) });
      out.made++;
    }
    const day = (n) => new Date(Date.now() + n * 86400000).toISOString();
    for (const [text, n] of [['Late one', 1], ['Late two', 1], ['Open soon', 2], ['Open later', 9]]) {
      await apiJson('/reminders', { method: 'POST', body: JSON.stringify({ text, due_at: day(n) }) });
    }
    return out;
  }, [tags, SKIP]);
  console.log(JSON.stringify(res));
  for (const tab of ['notes', 'notes', 'notes', 'chat', 'graph', 'notes', 'timeline', 'notes']) {
    await page.evaluate((t) => switchTab(t), tab);
    await page.waitForTimeout(400);
  }
  await page.evaluate(() => usageFlush()); await page.waitForTimeout(800);
  await browser.close();
})();
