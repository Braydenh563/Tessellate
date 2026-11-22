// search.js sweep (Brief 47, WORLD_CLASS_PLAN decision 46): the search box.
// Seeds one of each kind (search-seed.py, through the ORM), opens the box by
// its shortcut, finds each kind by one query and checks the row wears that
// kind's chip; walks it by keyboard (Down, Enter opens, Escape closes); saves
// a search and finds its row in the Notes sidebar; measures the route and
// the box's render apart; checks the card and the rows fit the viewport;
// runs axe-core on the open box. Console errors and page errors counted.
//
//   BASE=http://127.0.0.1:8816 DATA=<data dir> WIDTH=390 THEME=dark node scratchpad/ui-sweeps/search.js
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { boot } = require('./lib');

const WIDTH = Number(process.env.WIDTH || 1440);
const ROOT = path.join(__dirname, '../..');
const AXE_JS = process.env.AXE_JS || '/tmp/axe-core/package/axe.min.js';
const KINDS = {
  note: 'quillnote', document: 'quilldoc', board: 'quillboard', map: 'quillmap', file: 'quillfile',
  bookmark: 'quillmark', reminder: 'quillremind', chat: 'quillchat',
};
const CHIP = { note: 'Note', document: 'Document', board: 'Board', map: 'Mind map', file: 'File', bookmark: 'Bookmark', reminder: 'Reminder', chat: 'Chat' };

(async () => {
  if (process.env.DATA) {
    execFileSync(require('./lib.js').venvPython(), [path.join(__dirname, 'search-seed.py')], {
      env: { ...process.env, TESSELLATE_DATA_DIR: process.env.DATA, PYTHONPATH: path.join(ROOT, 'src') },
      stdio: 'ignore',
    });
  }
  const { browser, page } = await boot({ viewport: { width: WIDTH, height: WIDTH < 600 ? 844 : 900 }, ...(WIDTH < 600 ? { hasTouch: true, isMobile: true } : {}) });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  const out = { width: WIDTH, theme: process.env.THEME || 'light', found: {}, problems: [] };


  // Open by the shortcut (Ctrl+P), the way a keyboard user does.
  await page.keyboard.press('Control+p');
  await page.waitForSelector('#finder-input', { state: 'visible', timeout: 10000 });
  await page.waitForFunction(() => typeof saveFinderSearch === 'function', null, { timeout: 10000 });

  for (const [kind, word] of Object.entries(KINDS)) {
    await page.fill('#finder-input', '');
    await page.type('#finder-input', word, { delay: 20 });
    const t0 = Date.now();
    const ok = await page.waitForFunction((w) => [...document.querySelectorAll('#finder-results .finder-row')]
      .some((r) => r.textContent.toLowerCase().includes(w)), word, { timeout: 8000 }).then(() => true).catch(() => false);
    const row = await page.evaluate((w) => {
      const rowEl = [...document.querySelectorAll('#finder-results .finder-row')].find((r) => r.textContent.toLowerCase().includes(w));
      if (!rowEl) return null;
      const chipEl = rowEl.querySelector('.finder-kind');
      const box = rowEl.getBoundingClientRect();
      return { chip: chipEl ? chipEl.textContent.trim() : '', chipH: chipEl ? chipEl.getBoundingClientRect().height : 0, right: box.right, overflow: rowEl.scrollWidth - rowEl.clientWidth };
    }, word);
    out.found[kind] = ok && row && row.chip === CHIP[kind] ? `ok ${Date.now() - t0}ms` : `MISSING ${JSON.stringify(row)}`;
    if (row && (row.right > WIDTH + 0.5 || row.overflow > 1)) out.problems.push(`${kind} row overflows: ${JSON.stringify(row)}`);
  }

  // The route and the render, measured apart (render: `finderRender` on the hits in hand).
  out.timing = await page.evaluate(async () => {
    const route = [];
    for (let i = 0; i < 20; i += 1) {
      const t = performance.now();
      await apiJson('/search?q=quillnote&limit=30&page=1', { silent: true });
      route.push(performance.now() - t);
    }
    finderQuery = 'quill';
    document.getElementById('finder-input').value = 'quill';
    await finderSearch();
    const render = [];
    for (let i = 0; i < 20; i += 1) {
      const t = performance.now();
      finderRender();
      render.push(performance.now() - t);
    }
    const pct = (xs, p) => xs.sort((a, b) => a - b)[Math.min(xs.length - 1, Math.floor(xs.length * p))].toFixed(1);
    return { routeP50: pct(route, 0.5), routeP90: pct(route, 0.9), renderP50: pct(render, 0.5), renderP90: pct(render, 0.9), rows: document.querySelectorAll('#finder-results .finder-row').length };
  });

  // The card inside the viewport.
  out.card = await page.evaluate(() => {
    const r = document.querySelector('.finder-card').getBoundingClientRect();
    return { left: Math.round(r.left), right: Math.round(r.right), bottom: Math.round(r.bottom), vw: innerWidth, vh: innerHeight };
  });
  if (out.card.left < 0 || out.card.right > out.card.vw || out.card.bottom > out.card.vh) out.problems.push(`card outside the viewport ${JSON.stringify(out.card)}`);

  // axe on the open box.
  if (fs.existsSync(AXE_JS)) {
    await page.evaluate(fs.readFileSync(AXE_JS, 'utf8'));
    const axe = await page.evaluate(async () => {
      const r = await axe.run('#finder-overlay', { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] });
      return r.violations.map((v) => `${v.id} x${v.nodes.length}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ') + ' ' + (n.any[0]?.message || '').slice(0, 90)).join(' | ')}`);
    });
    out.axe = axe;
  }

  // Keyboard only: Down lights the first row, Enter opens it and closes the box.
  await page.fill('#finder-input', '');
  await page.type('#finder-input', 'quillnote', { delay: 20 });
  await page.waitForSelector('#finder-results .finder-row', { timeout: 8000 });
  await page.waitForTimeout(400);
  await page.keyboard.press('ArrowDown');
  out.keyboard = { lit: await page.evaluate(() => document.querySelectorAll('#finder-results .finder-row.is-active[aria-selected="true"]').length) };
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  out.keyboard.enterClosed = await page.evaluate(() => document.getElementById('finder-overlay').classList.contains('hidden'));
  await page.keyboard.press('Control+p');
  await page.waitForSelector('#finder-input', { state: 'visible' });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  out.keyboard.escapeClosed = await page.evaluate(() => document.getElementById('finder-overlay').classList.contains('hidden'));

  // A saved search is a row in the Notes sidebar, and the row opens the box with it.
  await page.keyboard.press('Control+p');
  await page.waitForSelector('#finder-input', { state: 'visible' });
  await page.fill('#finder-input', 'tag:ink quill');
  await page.click('#finder-save');
  await page.waitForSelector('.prompt-card input', { timeout: 5000 });
  await page.fill('.prompt-card input', `Ink ${WIDTH}`);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(800);
  out.saved = await page.evaluate((name) => {
    const rows = [...document.querySelectorAll('#saved-finds li')];
    const row = rows.find((li) => li.textContent.includes(name));
    return { rows: rows.length, found: Boolean(row), boxShown: !document.getElementById('saved-finds-box').classList.contains('hidden') };
  }, `Ink ${WIDTH}`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  out.saved.opens = await page.evaluate(async (name) => {
    const row = [...document.querySelectorAll('#saved-finds li')].find((li) => li.textContent.includes(name));
    row.click();
    await new Promise((r) => setTimeout(r, 400));
    return document.getElementById('finder-input').value;
  }, `Ink ${WIDTH}`);
  // Leave the notebook as it was found: forget the row this run saved.
  await page.evaluate(async (name) => {
    closeFinder();
    await persistSavedFinds(savedFinds().filter((s) => s.name !== name));
  }, `Ink ${WIDTH}`);

  out.errors = errors;
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
