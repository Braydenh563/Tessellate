// Boot, list and search at 2,000 notes, as numbers (audit 1031 PF7, ranked row 52).
//
// The server half is `tests/test_perf_2000.py` (statements, ms and bytes per
// route, every push). This is the browser's half, run on the 2,000-note data
// before a release; the audit had the list, search and boot at 545 notes only.
//
//   bash scratchpad/ui-sweeps/serve.sh 8874 <dir>
//   BASE=http://127.0.0.1:8874 node scratchpad/graph-fixture.js 2000 4000   # once per dir
//   BASE=http://127.0.0.1:8874 CPU=4 node scratchpad/ui-sweeps/perf2000.js
//
// Each step reports long tasks over 50 ms (count, total, longest), requests
// made, and the time to what the person waits for. CPU=<rate> throttles the
// main thread (4 is the phone profile the audits use); unset is 1x.
const { boot } = require('./lib.js');

const RATE = Number(process.env.CPU || 1);
const r0 = (x) => Math.round(x);

// Recorded from the first byte of every document (an init script survives the
// reload the boot step makes): long tasks, and the requests the page makes.
const RECORD = () => {
  window.__lt = [];
  window.__req = 0;
  try { new PerformanceObserver((list) => { for (const e of list.getEntries()) window.__lt.push(e.duration); }).observe({ type: 'longtask' }); } catch (e) {}
  const fetch0 = window.fetch;
  window.fetch = function (...a) { window.__req++; return fetch0.apply(this, a); };
};

async function watch(page, label, step, ready) {
  await page.evaluate(() => { window.__lt = []; window.__req = 0; });
  const began = Date.now();
  await step();
  await page.waitForFunction(ready, null, { timeout: 60000 });
  const ms = Date.now() - began;
  await page.waitForTimeout(1500);
  const seen = await page.evaluate(() => ({ lt: window.__lt, req: window.__req }));
  const total = seen.lt.reduce((a, b) => a + b, 0);
  console.log(`${label}: ready ${ms} ms, ${seen.lt.length} long tasks totalling ${r0(total)} ms (longest ${r0(Math.max(0, ...seen.lt))}), ${seen.req} requests`);
}

(async () => {
  const { browser, ctx, page } = await boot();
  await ctx.addInitScript(RECORD);
  const cdp = await ctx.newCDPSession(page);
  if (RATE > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const rows = () => document.querySelectorAll('#entry-list > li[data-id]').length > 20;

  // Boot: a reload, to the first screenful of notes.
  await watch(page, 'boot to the notes list', () => page.reload({ waitUntil: 'domcontentloaded' }).then(async () => {
    await page.waitForTimeout(1500);
    if (await page.isVisible('#lock-password').catch(() => false)) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
    await page.waitForSelector('#tab-btn-notes', { state: 'visible', timeout: 30000 });
    await page.click('#tab-btn-notes');
  }), rows);

  // The rest of the list: scroll to the bottom of the notes scroller.
  await watch(page, 'scroll the list to its end', () => page.evaluate(() => {
    let el = document.getElementById('entry-list');
    while (el && el.scrollHeight <= el.clientHeight + 1) el = el.parentElement;
    (el || document.scrollingElement).scrollTop = 1e9;
  }), () => document.querySelectorAll('#entry-list > li[data-id]').length > 20);

  // Search: type a word the fixture's notes share, wait for the rows to change.
  const box = await page.$('#note-search');
  if (box) {
    await watch(page, 'type a search', async () => { await box.click(); await box.type('Topic 123', { delay: 40 }); }, () => { const rows = document.querySelectorAll('#entry-list > li[data-id]'); return rows.length > 0 && rows.length < 200 && /123/.test(rows[0].textContent); });
  } else {
    console.log('type a search: no search box found on this tab');
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
