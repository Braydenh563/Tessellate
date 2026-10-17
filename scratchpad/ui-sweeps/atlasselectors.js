// Which CSS selectors the restyles of a carried and thrown Atlas spend their
// time in: Chromium's selector stats (the "SelectorStats" trace event,
// category disabled-by-default-blink.debug), summed over the carry and the
// flight of atlasrecalc.js, top selectors by elapsed time and match attempts.
// Env: BASE, RATE (4), KIND (atlas), TOP (25).
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const TOP = Number(process.env.TOP || 25);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await page.evaluate(() => nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 }, true));
  await sleep(900);
  const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const events = [];
  cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
  const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
  await cdp.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-blink.debug', transferMode: 'ReportEvents' });
  await page.mouse.move(f[0], f[1]);
  await page.mouse.down();
  for (let i = 1; i <= 40; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
  for (let i = 1; i <= 5; i += 1) { await page.mouse.move(f[0] + 480 + i * 70, f[1] - 40 - i * 6); await sleep(16); }
  await page.mouse.up();
  await sleep(1300);
  await cdp.send('Tracing.end');
  await done;
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const sel = new Map();
  let n = 0;
  for (const e of events) {
    if (e.name !== 'SelectorStats') continue;
    n += 1;
    for (const s of e.args?.selector_stats?.selector_timings || []) {
      const k = s.selector;
      const o = sel.get(k) || { us: 0, attempts: 0, matches: 0 };
      o.us += s['elapsed (us)'] || 0;
      o.attempts += s.match_attempts || 0;
      o.matches += s.match_count || 0;
      sel.set(k, o);
    }
  }
  const total = [...sel.values()].reduce((a, o) => a + o.us, 0);
  console.log(JSON.stringify({ statsEvents: n, selectors: sel.size, totalMs: Math.round(total / 1000) }));
  for (const [k, o] of [...sel.entries()].sort((a, b) => b[1].us - a[1].us).slice(0, TOP)) console.log(`${Math.round(o.us / 1000)}ms ${o.attempts}x ${o.matches}m ${k.slice(0, 200)}`);
  await browser.close();
})();
