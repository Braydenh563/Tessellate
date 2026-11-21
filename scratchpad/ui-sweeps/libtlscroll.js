// Long lists on the Library and the Timeline (libtl-0926, step 1): with a
// thousand notes (seed-timeline-bulk.py), how long the list takes to draw,
// how many elements it puts on the page, and what a wheel scroll through it
// costs: frame times from requestAnimationFrame (median, 95th percentile,
// worst, frames over 32ms) and the main thread's style, layout, paint and
// script per second (CDP). Surfaces: the Library's All list, the Timeline's
// feed and its table, every page loaded.
// Env: SURFACES (library,feed,table), OUT (json), MAX95 (ms, default 20).
// Exits 1 when a surface's 95th percentile frame is over MAX95.
const fs = require('fs');
const os = require('os');
const { boot, seedBulkOnce } = require('./lib.js');
const SURFACES = (process.env.SURFACES || 'library,feed,table').split(',');
const OUT = process.env.OUT || `${os.tmpdir()}/libtl-scroll.json`;
const MAX95 = Number(process.env.MAX95 || 20);

async function metrics(cdp) {
  const { metrics: m } = await cdp.send('Performance.getMetrics');
  return Object.fromEntries(m.map((x) => [x.name, x.value]));
}

(async () => {
  seedBulkOnce(1000);
  const results = {};
  for (const surface of SURFACES) {
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    const t0 = Date.now();
    const setup = await page.evaluate(async (s) => {
      const t = performance.now();
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      if (s === 'library') {
        switchTab('library');
        document.querySelector('#library-subtabs [data-target="library-view-documents"]')?.click();
        await wait(4000);
      } else {
        switchTab('timeline');
        await wait(3500);
        document.querySelector(`[data-timeline-view="${s === 'table' ? 'table' : 'feed'}"]`)?.click();
        await wait(1200);
        // Every page: the feed loads the next as it nears the end.
        for (let i = 0; i < 12; i += 1) {
          if (typeof timelineNextCursor !== 'undefined' && !timelineNextCursor) break;
          if (typeof timelineLoadMore === 'function') await timelineLoadMore();
          else {
            const sc = document.querySelector('#tab-timeline .tab-page, #tab-timeline');
            sc.scrollTop = sc.scrollHeight;
          }
          await wait(600);
        }
      }
      const root = document.getElementById(s === 'library' ? 'tab-library' : 'tab-timeline');
      const rows = s === 'library' ? root.querySelectorAll('#library-view-documents li, #library-view-documents .library-card, #library-view-documents [data-id]').length
        : s === 'table' ? root.querySelectorAll('tbody tr').length : root.querySelectorAll('[data-id]').length;
      // The element that scrolls.
      let sc = null;
      for (const el of [root, ...root.querySelectorAll('*')]) {
        const cs = getComputedStyle(el);
        if (/(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 200 && el.clientHeight > 300) { sc = el; break; }
      }
      if (sc) sc.dataset.libtlScroller = '1';
      return { ms: Math.round(performance.now() - t), rows, elements: root.querySelectorAll('*').length, scroller: sc ? `${sc.tagName}#${sc.id}.${String(sc.className).split(' ')[0]}` : null, scrollH: sc?.scrollHeight || 0 };
    }, surface);
    if (!setup.scroller) { results[surface] = { setup, error: 'no scroller' }; console.log(surface, JSON.stringify(results[surface])); await browser.close(); continue; }
    const box = await page.evaluate(() => { const r = document.querySelector('[data-libtl-scroller]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + Math.min(r.height / 2, 300)]; });
    await page.mouse.move(box[0], box[1]);
    await page.evaluate(() => {
      window.__ft = []; window.__fstop = false; let last = 0;
      const tick = (t) => { if (last) window.__ft.push(t - last); last = t; if (!window.__fstop) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    });
    const a = await metrics(cdp);
    const s0 = Date.now();
    for (let i = 0; i < 120; i += 1) { await page.mouse.wheel(0, i < 60 ? 120 : -120); await page.waitForTimeout(16); }
    await page.waitForTimeout(300);
    const secs = (Date.now() - s0) / 1000;
    const b = await metrics(cdp);
    const ft = await page.evaluate(() => { window.__fstop = true; return window.__ft; });
    const sorted = [...ft].sort((x, y) => x - y);
    const q = (p) => +sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))].toFixed(1);
    const d = (k) => b[k] - a[k];
    results[surface] = {
      setup, frames: ft.length, median: q(0.5), p95: q(0.95), worst: +Math.max(...ft).toFixed(1), over32: ft.filter((x) => x > 32).length,
      scriptMsPerSec: +(d('ScriptDuration') * 1000 / secs).toFixed(1), layoutMsPerSec: +(d('LayoutDuration') * 1000 / secs).toFixed(1),
      styleMsPerSec: +(d('RecalcStyleDuration') * 1000 / secs).toFixed(1), taskMsPerSec: +(d('TaskDuration') * 1000 / secs).toFixed(1),
      layoutsPerSec: +(d('LayoutCount') / secs).toFixed(1), stylesPerSec: +(d('RecalcStyleCount') / secs).toFixed(1), loadSecs: +((Date.now() - t0) / 1000).toFixed(1),
    };
    console.log(surface, JSON.stringify(results[surface]));
    await browser.close();
  }
  fs.writeFileSync(OUT, JSON.stringify(results, null, 1));
  const bad = Object.entries(results).filter(([, r]) => r.error || r.p95 > MAX95);
  console.log(bad.length ? `FAIL ${bad.map(([k]) => k).join(',')}` : 'PASS');
  process.exitCode = bad.length ? 1 : 0;
})();
