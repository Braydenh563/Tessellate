// An opened Notes row's first line: ::first-line line-height and the content's
// box, for rows with and without a title, old CSS against new (OLD=1 serves
// the stylesheet from OLD08). Prints how many rows of each kind it measured.
//
//   OUT=/tmp/n.json BASE=... node firstlinedump.js
//   OLD=1 OLD08=old.css OUT=/tmp/o.json BASE=... node firstlinedump.js
//   node firstlinedump.js --diff o.json n.json
const fs = require('fs');
if (process.argv[2] === '--diff') {
  const a = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  let n = 0;
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) if (a[k] !== b[k]) { n++; console.log(k, a[k], '->', b[k]); }
  console.log(`${Object.keys(a).length} rows, ${n} differences`);
  process.exit(0);
}
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 }, serviceWorkers: 'block' });
  if (process.env.OLD) {
    await ctx.route('**/css/08-consistency.css*', (route) => route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(process.env.OLD08, 'utf8') }));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.fill('#lock-password', 'testpassword123').catch(() => {});
    await page.click('#lock-submit').catch(() => {});
  }
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  await page.click('#tab-bar button[data-tab="notes"]', { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.evaluate(() => document.getElementById('notes-view-rows')?.click());
  await page.waitForTimeout(1500);
  // Open up to 40 rows, as the owner would: the chevron of each.
  const res = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll('#entry-list.is-rows > li')].slice(0, 60);
    for (const li of rows) li.querySelector(':scope > .row-expand')?.click();
    // Rows 0 to 9 are measured with a title put in front of the content (the
    // notebook's notes carry none), so both branches of the rule are read.
    rows.slice(0, 10).forEach((li, i) => {
      if (i % 2) return;
      const p = document.createElement('p');
      p.className = 'entry-title';
      p.textContent = 'A title';
      li.insertBefore(p, li.querySelector(':scope > .entry-content'));
    });
    await new Promise((r) => setTimeout(r, 800));
    const out = {};
    let titled = 0, untitled = 0;
    rows.forEach((li, i) => {
      const c = li.querySelector(':scope > .entry-content');
      if (!c || !li.classList.contains('row-expanded')) return;
      const t = !!li.querySelector(':scope > .entry-title');
      t ? titled++ : untitled++;
      const fl = getComputedStyle(c, '::first-line').lineHeight;
      const r = c.getBoundingClientRect();
      out[`${i} ${t ? 'titled' : 'untitled'}`] = `${fl} ${Math.round(r.height * 100) / 100}`;
    });
    return { out, titled, untitled, has: rows.filter((li) => li.classList.contains('row-expanded')).length };
  });
  console.log(res.titled, 'titled,', res.untitled, 'untitled,', res.has, 'expanded');
  fs.writeFileSync(process.env.OUT, JSON.stringify(res.out));
  await browser.close();
})();
