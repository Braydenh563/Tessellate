// measure-1010 items 1, 9 (WORLD_CLASS_PLAN 25.2 / 24.6b): interaction timings at 5,000 notes.
//
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/measure-interactions.js
//
// Phases (PHASE=boot,list,search,keybox): each prints one JSON line. Times are ms, p50 of RUNS runs.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8794';
const RUNS = +(process.env.RUNS || 10);
const PW = 'testpassword123';
const phases = (process.env.PHASE || 'boot,list,search,keybox').split(',');
const p50 = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
const mk = async (browser) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('theme', 'light'); localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); localStorage.setItem('nm-buddy-hint', 'done'); } catch (e) {} });
  return ctx;
};
const unlock = async (page) => {
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 30000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
};
(async () => {
  const browser = await chromium.launch();
  const out = {};
  if (phases.includes('boot')) {
    // Cold: new context (empty cache), from navigation to lock field, then from submit to the interactive app (lock overlay hidden, curtain gone, dashboard hero visible).
    const rows = [];
    for (let i = 0; i < 5; i++) {
      const ctx = await mk(browser); const page = await ctx.newPage();
      const t0 = Date.now();
      await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#lock-password', { state: 'visible' });
      const tLock = Date.now() - t0;
      await page.fill('#lock-password', PW);
      const t1 = Date.now();
      await page.click('#lock-submit');
      await page.waitForFunction(() => { const o = document.getElementById('lock-overlay'); const h = document.getElementById('dash-hero'); return o && o.classList.contains('hidden') && !document.documentElement.classList.contains('shell-curtain') && h && h.offsetParent !== null; }, null, { timeout: 60000, polling: 20 });
      const tRow = Date.now() - t1;
      const nav = await page.evaluate(() => {
        const n = performance.getEntriesByType('navigation')[0];
        const fcp = performance.getEntriesByName('first-contentful-paint')[0];
        return { dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd), fcp: fcp ? Math.round(fcp.startTime) : null };
      });
      // Warm reload with the stored token: nav to first visible row, no password typed.
      const t2 = Date.now();
      await page.reload({ waitUntil: 'domcontentloaded' });
      let warmRow = null;
      try {
        await page.waitForFunction(() => { const o = document.getElementById('lock-overlay'); const h = document.getElementById('dash-hero'); return o && o.classList.contains('hidden') && !document.documentElement.classList.contains('shell-curtain') && h && h.offsetParent !== null; }, null, { timeout: 8000, polling: 20 });
        warmRow = Date.now() - t2;
      } catch (e) { warmRow = 'needs password'; }
      rows.push({ ...nav, navToLockField: tLock, submitToFirstWidget: tRow, reloadToFirstWidget: warmRow });
      await ctx.close();
    }
    out.boot = rows;
    const nums = (k) => rows.map((r) => r[k]).filter((v) => typeof v === 'number');
    out.bootP50 = Object.fromEntries(['dcl', 'load', 'fcp', 'navToLockField', 'submitToFirstWidget', 'reloadToFirstWidget'].map((k) => [k, nums(k).length ? p50(nums(k)) : null]));
    console.log('BOOT', JSON.stringify(out.bootP50), JSON.stringify(rows));
  }
  let ctx, page;
  if (phases.some((p) => p !== 'boot')) {
    ctx = await mk(browser); page = await ctx.newPage();
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await unlock(page);
    // The list is built lazily on the Notes tab now, so open it once to warm.
    await page.waitForFunction(() => typeof switchTab === 'function', null, { timeout: 60000 });
    await page.evaluate(() => switchTab('notes'));
    await page.waitForFunction(() => document.querySelector('#entry-list li'), null, { timeout: 60000 });
    await page.waitForTimeout(4000);
    await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  }
  if (phases.includes('list')) {
    const t = []; const counts = [];
    for (let i = 0; i < RUNS; i++) {
      await page.evaluate(() => switchTab('dashboard'));
      await page.waitForTimeout(1200);
      const r = await page.evaluate(() => new Promise((resolve) => {
        const t0 = performance.now();
        switchTab('notes');
        const tick = () => {
          const n = document.querySelectorAll('#entry-list li').length;
          const vis = document.getElementById('tab-notes') && !document.getElementById('tab-notes').classList.contains('hidden');
          if (vis && n > 0) {
            // settled: same count on two consecutive frames
            requestAnimationFrame(() => { const m = document.querySelectorAll('#entry-list li').length; resolve({ ms: Math.round(performance.now() - t0), rows: m }); });
          } else requestAnimationFrame(tick);
        };
        tick();
      }));
      t.push(r.ms); counts.push(r.rows);
    }
    console.log('LIST p50', p50(t), 'all', JSON.stringify(t), 'rows rendered', JSON.stringify(counts));
  }
  if (phases.includes('search')) {
    const tok = await page.evaluate(() => localStorage.getItem('token') || sessionStorage.getItem('token'));
    for (const q of ['garden', 'dentist budget', 'Note 4242']) {
      for (const hybrid of ['true', 'false']) {
        const ts = []; let hits = 0;
        for (let i = 0; i < RUNS + 1; i++) {
          const t0 = performance.now();
          const r = await fetch(`${BASE}/search?q=${encodeURIComponent(q)}&hybrid=${hybrid}&limit=20`, { headers: { 'X-Auth-Token': tok } });
          const j = await r.json(); hits = (j.hits || []).length;
          ts.push(Math.round(performance.now() - t0));
        }
        const first = ts.shift();
        console.log('SEARCH', JSON.stringify(q), 'hybrid=' + hybrid, 'p50', p50(ts), 'first', first, 'hits', hits, JSON.stringify(ts));
      }
    }
  }
  if (phases.includes('keybox')) {
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(1500);
    await page.evaluate(() => {
      window.__mut = { last: 0 };
      new MutationObserver(() => { window.__mut.last = performance.now(); }).observe(document.getElementById('entry-list'), { childList: true, subtree: true });
    });
    for (const q of ['garden', 'dentist budget', 'Note 4242']) {
      const first = [], settle = [];
      for (let i = 0; i < RUNS; i++) {
        await page.fill('#note-search', '');
        await page.waitForTimeout(1500);
        const stem = q.slice(0, -1);
        await page.focus('#note-search');
        await page.keyboard.type(stem, { delay: 0 });
        await page.waitForTimeout(1500);
        const r = await page.evaluate(async (ch) => {
          const input = document.getElementById('note-search');
          window.__mut.last = 0;
          const t0 = performance.now();
          input.value += ch;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          let firstAt = 0;
          await new Promise((res) => {
            const tick = () => {
              if (window.__mut.last && !firstAt) firstAt = window.__mut.last;
              if (window.__mut.last && performance.now() - window.__mut.last > 250) res(); else if (performance.now() - t0 > 8000) res(); else setTimeout(tick, 10);
            };
            tick();
          });
          return { first: firstAt ? Math.round(firstAt - t0) : null, settle: Math.round(window.__mut.last - t0), rows: document.querySelectorAll('#entry-list li').length };
        }, q.slice(-1));
        if (r.first !== null) first.push(r.first); settle.push(r.settle);
      }
      console.log('KEYBOX', JSON.stringify(q), 'keystroke->first row change p50', first.length ? p50(first) : null, 'keystroke->settled p50', p50(settle), JSON.stringify(settle));
    }
  }
  await browser.close();
})();
