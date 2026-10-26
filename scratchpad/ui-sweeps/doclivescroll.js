// Live-view scroll cost on a long document (docdog-1026: worst frame 132 ms in
// Live vs 29 ms in Source on 8,221 words). Builds a mixed Markdown document
// (headings, paragraphs with bold/italic/links/code, lists, a quote, a table),
// opens it, and scrolls the editor from top to bottom in 40 wheel-sized steps
// per view, recording rAF frame gaps and long tasks (>50 ms). Prints per view:
// frames, median, p95, worst, long tasks, total long-task ms.
// WORDS=8200 VIEWS=live,source BASE=http://127.0.0.1:8797 SCRATCH=<dir> node doclivescroll.js
const { boot } = require('./lib.js');
(async () => {
  const WORDS = +(process.env.WORDS || 8200);
  const views = (process.env.VIEWS || 'live,source').split(',');
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-docs"]')?.click());
  await page.waitForTimeout(800);
  const id = await page.evaluate(async (WORDS) => {
    const para = (i) => `Section ${i} paragraph with **bold words**, some *italic ones*, a [link](https://example.com/${i}) and \`inline code\` beside plain prose that keeps going for a good while so a line wraps more than once on a laptop screen, then more words about topic ${i}.`;
    let md = '# Scroll profile\n\n';
    let words = 0, i = 0;
    while (words < WORDS) {
      i++;
      md += `## Part ${i}\n\n${para(i)}\n\n- first point of ${i}\n- second point with **weight**\n- [ ] a task for ${i}\n\n> A quoted thought for part ${i}.\n\n${para(i + 1000)}\n\n`;
      if (i % 6 === 0) md += '| a | b | c |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n\n';
      words += 95;
    }
    const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Scroll ${Date.now()}`, content: md, file_type: 'md' }) });
    return d.id;
  }, WORDS);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const fill = page.locator('#lock-password');
  if (await fill.isVisible().catch(() => false)) { await fill.fill('testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(1500); }
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(400);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-docs"]')?.click());
  await page.waitForTimeout(800);
  await page.locator('.doc-list-item', { hasText: 'Scroll ' }).first().click();
  await page.waitForTimeout(1500);
  if (process.env.DEBUG) console.log(JSON.stringify(await page.evaluate(() => ({ id: typeof currentDocumentId !== 'undefined' ? currentDocumentId : null, tab: document.querySelector('.tab-content.active')?.id, scrollers: [...document.querySelectorAll('.cm-scroller')].map((e) => [e.offsetParent && e.offsetParent.id, e.clientHeight, e.closest('[id]')?.id]) }))));
  await page.waitForFunction(() => [...document.querySelectorAll('.cm-scroller')].some((e) => e.offsetParent && e.clientHeight > 100), null, { timeout: 20000 });
  await page.waitForTimeout(1500);
  const results = [];
  for (const v of views) {
    await page.evaluate((v) => document.querySelector(`[data-doc-view="${v}"]`)?.click(), v);
    await page.waitForTimeout(1500);
    let cdp = null;
    if (process.env.PROFILE) { cdp = await page.context().newCDPSession(page); await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 200 }); await cdp.send('Profiler.start'); }
    const info = await page.evaluate(async () => {
      const sc = [...document.querySelectorAll('.cm-scroller')].find((e) => e.offsetParent && e.clientHeight > 100);
      sc.scrollTop = 0;
      await new Promise((r) => setTimeout(r, 400));
      const gaps = [];
      const longs = [];
      const po = new PerformanceObserver((l) => { for (const e of l.getEntries()) longs.push(e.duration); });
      try { po.observe({ type: 'longtask', buffered: false }); } catch (e) { /* unsupported */ }
      let last = performance.now();
      let stop = false;
      const tick = (t) => { gaps.push(t - last); last = t; if (!stop) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
      const max = sc.scrollHeight - sc.clientHeight;
      const steps = 80;
      for (let s = 1; s <= steps; s++) {
        sc.scrollTop = Math.round((max * s) / steps);
        await new Promise((r) => setTimeout(r, 40));
      }
      await new Promise((r) => setTimeout(r, 200));
      stop = true;
      po.disconnect();
      gaps.sort((a, b) => a - b);
      const p = (q) => Math.round(gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))]);
      return { words: (sc.textContent || '').split(/\s+/).length, scrollH: sc.scrollHeight, lines: document.querySelectorAll('.cm-line').length, frames: gaps.length, median: p(0.5), p95: p(0.95), worst: Math.round(gaps[gaps.length - 1]), longTasks: longs.length, longMs: Math.round(longs.reduce((a, b) => a + b, 0)) };
    });
    results.push({ view: v, ...info });
    if (cdp) {
      const { profile } = await cdp.send('Profiler.stop');
      const self = new Map();
      const dt = profile.timeDeltas; const byId = new Map(profile.nodes.map((n) => [n.id, n]));
      profile.samples.forEach((sid, i) => { const n = byId.get(sid); const k = `${n.callFrame.functionName || '(anon)'} ${n.callFrame.url.split('/').pop()}:${n.callFrame.lineNumber + 1}`; self.set(k, (self.get(k) || 0) + (dt[i] || 0)); });
      console.log(v, 'top self time (ms):', [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 14).map(([k, t]) => `${Math.round(t / 1000)} ${k}`).join('\n  '));
    }
  }
  for (const r of results) console.log(JSON.stringify(r));
  console.log('errors', errors.length);
  await browser.close();
})();
