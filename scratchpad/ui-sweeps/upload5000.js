// L979: a browser upload of 5,000 files through the Obsidian folder import,
// headless, with setInputFiles. Measures: did all land, wall time, errors,
// and main-thread responsiveness (long tasks, timer drift) while it ran.
//   BASE=http://127.0.0.1:8792 N=5000 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node upload5000.js
const { boot } = require('./lib.js');
const N = Number(process.env.N || 5000);
(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('response', (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
  await page.evaluate(() => {
    window.__long = []; window.__drift = []; window.__marks = {};
    new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__long.push([Math.round(e.startTime), Math.round(e.duration)]))).observe({ entryTypes: ['longtask'] });
    let last = performance.now();
    setInterval(() => { const now = performance.now(); window.__drift.push(Math.round(now - last - 100)); last = now; }, 100);
  });
  const dir = process.env.VAULT || require('path').join(process.env.SCRATCH || '.', 'vault');
  const fs = require('fs'); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir + '/sub', { recursive: true });
  for (let i = 0; i < N; i++) {
    fs.writeFileSync(`${dir}/${i % 2 ? 'sub/' : ''}n${String(i).padStart(5, '0')}.md`,
      `---\ntags: [bulk]\n---\n# Bulk note ${i}\n\nBody of bulk note ${i} about topic${i % 50}. ` + 'lorem ipsum dolor sit amet '.repeat(12) + '\n');
  }
  await page.evaluate(() => openSettingsModal('data'));
  await page.waitForSelector('#import-obsidian-file', { state: 'attached' });
  await page.waitForTimeout(1500);
  await page.evaluate(() => { window.__marks.set = performance.now(); });
  const t0 = Date.now();
  await page.setInputFiles('#import-obsidian-file', dir);
  const tSet = Date.now() - t0;
  await page.waitForSelector('.import-report-card button.accent', { timeout: 300000 });
  const tPreview = Date.now() - t0;
  await page.evaluate(() => { window.__marks.preview = performance.now(); });
  const rows = await page.evaluate(() => document.querySelectorAll('.import-report-list li').length);
  const sub = await page.evaluate(() => document.querySelector('[name=import-preview], .sheet-sub, .import-report-card')?.parentElement?.innerText.slice(0, 160));
  // responsiveness of the open preview: a click on Select none must answer fast
  const tc = Date.now();
  await page.click('.import-report-card button:has-text("Select all")');
  const tClick = Date.now() - tc;
  await page.evaluate(() => { window.__marks.go = performance.now(); });
  await page.click('.import-report-card button.accent');
  const t1 = Date.now();
  await page.waitForFunction(() => /Imported \d+|Couldn|No Obsidian/.test(document.getElementById('import-app-status')?.textContent || ''), null, { timeout: 600000, polling: 500 });
  const tDone = Date.now() - t0;
  const status = await page.evaluate(() => document.getElementById('import-app-status').textContent);
  const stats = await page.evaluate(() => ({ long: window.__long, drift: window.__drift, marks: window.__marks }));
  const mx = (a) => a.length ? Math.max(...a) : 0;
  console.log(JSON.stringify({ N, setInputFilesMs: tSet, previewShownMs: tPreview, previewRows: rows, selectAllClickMs: tClick,
    importMs: Date.now() - t1, totalMs: tDone, status, longTasks: stats.long.length, longTaskMaxMs: mx(stats.long.map((l) => l[1])), longTaskList: stats.long, marks: stats.marks,
    driftMaxMs: mx(stats.drift), driftOver200: stats.drift.filter((d) => d > 200).length, errors }, null, 1));
  await browser.close();
})().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
