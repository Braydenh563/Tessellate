// The graph hover card's close X reached at a human pace, at desktop and touch size
// (L-graph hovercard). BASE=http://127.0.0.1:8876 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/graph-hovercard-close.js
// Needs a notebook with a few linked notes; seeds six when the map has fewer than four.
const { boot, PW } = require('./lib.js');
let failed = 0;
const say = (ok, name, detail) => { if (!ok) failed += 1; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`); };

async function seed(page) {
  await page.evaluate(async () => {
    const names = ['Gym plan', 'Sleep log', 'Budget notes', 'Trip to Kyoto', 'Recipe ideas', 'Reading list'];
    if ((await apiJson('/entries')).length >= 4) return;
    for (let i = 0; i < 6; i++) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `${names[i]} about plans. [[${names[(i + 1) % 6]}]] [[${names[(i + 2) % 6]}]]` }) });
  });
}
const card = (page) => page.evaluate(() => { const c = document.getElementById('graph-hovercard'); return { hidden: c ? c.hidden : true, popup: !document.getElementById('graph-popup').classList.contains('hidden') }; });
const dot = (page) => page.evaluate(() => {
  const s = gcTab; const r = s.canvas.getBoundingClientRect(); const t = s.transform;
  const n = s.nodes.filter((n) => !n.isGroup && Number.isFinite(n.x)).sort((a, b) => a.x - b.x)[0];
  return { x: r.left + n.x * t.k + t.x, y: r.top + n.y * t.k + t.y };
});
const xBtn = (page) => page.evaluate(() => { const r = document.querySelector('.graph-hovercard-close').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
async function show(page, d) {
  await page.mouse.move(d.x - 50, d.y - 50); await page.waitForTimeout(200);
  await page.mouse.move(d.x, d.y, { steps: 4 }); await page.waitForTimeout(500);
}
// Travel from a to b in `ms`, one move per ~16 ms, each step held until its own time is due
// (a move costs ~17 ms of round trip, so a plain wait would halve the speed).
async function travel(page, a, b, ms) {
  const n = Math.max(1, Math.round(ms / 16));
  const t0 = Date.now();
  for (let i = 1; i <= n; i++) {
    await page.mouse.move(a.x + (b.x - a.x) * i / n, a.y + (b.y - a.y) * i / n);
    const wait = t0 + i * ms / n - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
  }
  return Date.now() - t0;
}

(async () => {
  const errs = [];
  const { browser, page } = await boot();
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push(e.message));
  await seed(page); await page.waitForTimeout(1200);
  await page.evaluate(() => switchTab('graph')); await page.waitForTimeout(4000);
  await page.evaluate(() => { document.getElementById('graph-card-on').checked = true; prefs.set('graph-card-on', '1'); });
  const d = await dot(page);
  await show(page, d);
  const x = await xBtn(page);
  const dist = Math.round(Math.hypot(x.x - d.x, x.y - d.y));
  const walk = async (name, ms, leaveFirst) => {
    await page.mouse.move(d.x + 400 > 1400 ? d.x - 300 : d.x + 300, d.y + 300); await page.waitForTimeout(900);
    await show(page, d);
    const xb = await xBtn(page);
    let took = 0;
    if (leaveFirst) {
      // out of the dot into empty map, a short pause, then on to the X
      const away = { x: d.x + (xb.x > d.x ? 6 : -6) * 3, y: d.y - 18 };
      took += await travel(page, d, away, 80);
      took += await travel(page, away, xb, ms - 80);
    } else took = await travel(page, d, xb, ms);
    const arrived = await card(page);
    await page.mouse.click(xb.x, xb.y); await page.waitForTimeout(250);
    const after = await card(page);
    say(!arrived.hidden && after.hidden && !after.popup, name, `${dist}px in ${took}ms (${Math.round(dist / took * 1000)}px/s): on arrival hidden=${arrived.hidden}, after click hidden=${after.hidden}, popup open=${after.popup}`);
  };
  await walk('desktop 300px/s', Math.round(dist / 300 * 1000), false);
  await walk('desktop paced 550ms', 550, false);
  await walk('desktop 700ms leaving the dot into empty map first', 700, true);
  // touch
  const ctxT = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, serviceWorkers: 'block' });
  const tp = await ctxT.newPage();
  tp.on('console', (m) => { if (m.type() === 'error') errs.push('touch ' + m.text()); });
  tp.on('pageerror', (e) => errs.push('touch ' + e.message));
  await tp.addInitScript(() => { localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); });
  await tp.goto((process.env.BASE || 'http://127.0.0.1:8781') + '/', { waitUntil: 'domcontentloaded' });
  await tp.waitForTimeout(2500);
  const pw = await tp.$('#lock-password');
  if (pw && await pw.isVisible()) { await pw.fill(PW); await tp.click('#lock-submit'); await tp.waitForTimeout(2500); }
  await tp.evaluate(() => switchTab('graph')); await tp.waitForTimeout(4000);
  const td = await dot(tp);
  await tp.touchscreen.tap(td.x, td.y); await tp.waitForTimeout(700);
  const first = await tp.evaluate(() => { const c = document.getElementById('graph-hovercard'); return { shown: !!c && !c.hidden, popup: !document.getElementById('graph-popup').classList.contains('hidden') }; });
  // A touch has no hover, so no card: the tap opens the note's popup and the card (hover and keyboard only) stays hidden.
  say(!first.shown && first.popup, 'touch tap on a dot', `card shown=${first.shown}, popup open=${first.popup}`);
  say(errs.length === 0, 'console errors', `${errs.length} ${JSON.stringify(errs.slice(0, 3))}`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
