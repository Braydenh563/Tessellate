// L979: the folder export round trip through a real browser, and a 5,000-file folder upload.
//
//   bash scratchpad/ui-sweeps/serve.sh 8791 <dir A>    # seeded and exported (API only)
//   bash scratchpad/ui-sweeps/serve.sh 8792 <dir B>    # fresh notebook, driven in the browser
//   A=http://127.0.0.1:8791 BASE=http://127.0.0.1:8792 SCRATCH=<dir> node folder5000.js
//
// Parts: 1 seed 3 spaces and private notes on A, export GET /export/folder;
// 2 import that zip into B through #import-memorymap-file, first with the
// private notes locked (expect the 409 words), then unlocked, and compare;
// 3 upload 5,000 nested .md files through #import-md-folder, timed, with
// long tasks over 200 ms counted. Fresh data dirs each run.
const fs = require('fs');
const path = require('path');
const { boot, PW, BASE } = require('./lib.js');
const A = process.env.A || 'http://127.0.0.1:8791';
const SCRATCH = process.env.SCRATCH || '.';
const N = Number(process.env.FILES || 5000);

async function call(base, token, method, url, body, space) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['X-Auth-Token'] = token;
  if (space) headers['X-Workspace-ID'] = space;
  const res = await fetch(base + url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  let json; try { json = JSON.parse(text); } catch (e) { json = text; }
  if (!res.ok) throw new Error(`${method} ${url} ${res.status} ${text.slice(0, 200)}`);
  return json;
}
async function setup(base) {
  const r = await call(base, null, 'POST', '/auth/setup', { password: PW });
  return r.token;
}
async function counts(base, token, spaces) {
  const out = {};
  for (const s of spaces) out[s] = await call(base, token, 'GET', '/entries/count', undefined, s).then((r) => r.count, () => 'no such space');
  return out;
}
async function readAll(base, token, space) {
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    const page = await call(base, token, 'GET', `/entries?limit=100&offset=${offset}`, undefined, space);
    rows.push(...page);
    if (page.length < 100) break;
  }
  return rows;
}

(async () => {
  const report = {};
  // ---- 1. seed A
  const tokA = await setup(A);
  const names = ['Garden', 'Trips', 'Office'];
  const ids = ['default'];
  for (const n of names) ids.push((await call(A, tokA, 'POST', '/spaces', { name: n })).id);
  const want = { default: 4, [ids[1]]: 5, [ids[2]]: 6, [ids[3]]: 3 };
  for (const [space, n] of Object.entries(want)) {
    for (let i = 0; i < n; i++) await call(A, tokA, 'POST', '/entries', { content: `Plain note ${i} in ${space}\n\nBody ${i} of ${space}` }, space);
  }
  const secrets = [];
  for (const [i, space] of [ids[0], ids[1], ids[2]].entries()) {
    const e = await call(A, tokA, 'POST', '/entries', { content: `Private note ${i} SECRETWORD${i}` }, space);
    await call(A, tokA, 'POST', `/entries/${e.id}/privacy`, { private: true }, space);
    secrets.push({ space, word: `SECRETWORD${i}` });
    want[space] += 1;
  }
  report.A_counts = await counts(A, tokA, ids);
  report.A_private = (await call(A, tokA, 'GET', '/entries?limit=100', undefined, 'all')).filter((e) => e.is_private).length;
  const zipPath = path.join(SCRATCH, 'notebook-export.zip');
  const z = await fetch(A + '/export/folder', { headers: { 'X-Auth-Token': tokA } });
  fs.writeFileSync(zipPath, Buffer.from(await z.arrayBuffer()));
  report.zip_bytes = fs.statSync(zipPath).size;

  // ---- 2. B: fresh notebook, sign-in off, vault locked, then the browser
  const B = BASE;
  const tokB = await setup(B);
  await call(B, tokB, 'POST', '/auth/password-on-open', { enabled: false, current_password: PW });
  await call(B, tokB, 'POST', '/auth/lock');
  const { browser, page } = await boot();
  const bt = await page.evaluate(() => localStorage.getItem('token'));
  const status = '#import-app-status';
  await page.evaluate(() => openSettingsModal('data'));
  await page.waitForSelector('#import-memorymap-file', { state: 'attached', timeout: 30000 });
  await page.waitForFunction(() => typeof importFromApp === 'function' && typeof importMarkdown === 'function', null, { timeout: 30000 });
  async function importZip() {
    await page.setInputFiles('#import-memorymap-file', zipPath);
    await page.waitForSelector('.import-report-card button.accent', { timeout: 60000 }).catch(() => {});
    const preview = await page.$('.import-report-card button.accent');
    if (preview) { await preview.click(); }
    await page.waitForFunction((s) => { const t = document.querySelector(s)?.textContent || ''; return /Imported|private|wrong|No Tessellate|Couldn/.test(t); }, status, { timeout: 120000 });
    return page.textContent(status);
  }
  report.locked_import_text = await importZip();
  report.B_after_locked = await counts(B, bt, ids);
  // unlock the vault in this session, then import again
  await call(B, bt, 'POST', '/auth/unlock-vault', { password: PW });
  const t0 = Date.now();
  report.unlocked_import_text = await importZip();
  report.import_ms = Date.now() - t0;
  const spacesB = await call(B, bt, 'GET', '/spaces');
  report.B_space_names = spacesB.map((s) => s.name);
  const idB = {};
  for (const s of spacesB) idB[s.name] = s.id;
  const mapped = ['default', idB.Garden, idB.Trips, idB.Office];
  report.B_counts = await counts(B, bt, mapped);
  report.counts_match = JSON.stringify(Object.values(report.A_counts)) === JSON.stringify(Object.values(report.B_counts));
  const all = await call(B, bt, 'GET', '/entries?limit=100', undefined, 'all');
  report.B_private_flagged = all.filter((e) => e.is_private).length;
  let readable = 0;
  for (const e of all.filter((x) => x.is_private)) {
    const full = await call(B, bt, 'GET', `/entries/${e.id}`);
    if (/SECRETWORD\d/.test(full.content || '')) readable++;
  }
  report.B_private_readable_unlocked = readable;
  // ---- 3. 5,000 nested files
  const root = path.join(SCRATCH, 'vault5000');
  fs.rmSync(root, { recursive: true, force: true });
  for (let i = 0; i < N; i++) {
    const dir = path.join(root, `area${i % 10}`, `topic${i % 50}`);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, `note${i}.md`), `# Note ${i}\n\nUnique body ${i} about subject${i % 97}.\n`);
  }
  const before = (await call(B, bt, 'GET', '/entries/count', undefined, 'default')).count;
  await page.evaluate(() => {
    window.__long = [];
    new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__long.push([Math.round(e.startTime), Math.round(e.duration)]))).observe({ type: 'longtask', buffered: false });
  });
  const t1 = Date.now();
  await page.setInputFiles('#import-md-folder', root);
  await page.waitForSelector('.import-report-card button.accent', { timeout: 120000 }).catch(() => {});
  report.preview_ms = Date.now() - t1;
  const go = await page.$('.import-report-card button.accent');
  const clickedAt = await page.evaluate(() => Math.round(performance.now()));
  if (go) await go.click();
  await page.waitForFunction(() => /Imported|did not work|Nothing|No markdown|more than/.test(document.getElementById('import-md-status')?.textContent || ''), null, { timeout: 600000 });
  report.folder_wall_ms = Date.now() - t1;
  report.folder_status = await page.textContent('#import-md-status');
  const afterN = (await call(B, bt, 'GET', '/entries/count', undefined, 'default')).count;
  report.folder_notes_added = afterN - before;
  const long = await page.evaluate(() => window.__long);
  const big = long.filter(([, d]) => d > 200);
  report.long_tasks_over_200ms = big.length;
  report.long_tasks_in_preview = big.filter(([at]) => at < clickedAt).map(([, d]) => d);
  report.long_tasks_in_import = big.filter(([at]) => at >= clickedAt).map(([, d]) => d);
  report.long_task_max_ms = Math.max(0, ...long.map(([, d]) => d));
  const sample = (await call(B, bt, 'GET', '/entries?limit=100', undefined, 'default')).filter((e) => (e.source_path || '').startsWith('vault5000/')).slice(0, 3);
  report.sample_paths = sample.map((e) => [e.source_path, e.category]);
  // locked again: the words must not come back
  await call(B, bt, 'POST', '/auth/lock');
  const bt2 = (await call(B, null, 'POST', '/auth/auto-session')).token;
  let leaked = 0;
  for (const e of all.filter((x) => x.is_private)) {
    try { const full = await call(B, bt2, 'GET', `/entries/${e.id}`); if (/SECRETWORD\d/.test(full.content || '')) leaked++; } catch (err) { /* refused: sealed */ }
  }
  report.B_private_leaked_when_locked = leaked;

  console.log(JSON.stringify(report, null, 1));
  await browser.close();
})().catch((e) => { console.log('FAIL', e.stack); process.exit(1); });
