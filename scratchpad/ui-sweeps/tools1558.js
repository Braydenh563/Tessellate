// INBOX 1558: the Clock and the Calculator as dashboard widgets. Adds each from
// Customise, Widgets (remove first if present, so the Add path always runs), uses
// it, reloads and checks it persists. W=1440|390, THEME=dark|light, BASE=url.
const { boot } = require('./lib.js');
const W = Number(process.env.W || 1440);
const H = W < 600 ? 780 : 900;
const log = (k, v) => console.log(k.padEnd(34), v);

async function addWidget(page, id) {
  await page.evaluate(() => { for (const el of [document.scrollingElement, ...document.querySelectorAll('main, .tab-panel, #tab-dashboard')]) if (el) el.scrollTop = 0; });
  await page.waitForTimeout(400);
  await page.click('#dash-customise button');
  await page.waitForTimeout(400);
  await page.click('button.menu-item:has-text("Widgets")');
  await page.waitForSelector('#dash-widgets-dialog[open]');
  await page.fill('#dash-widgets-search', '');
  const row = `.dash-widget-row[data-widget="${id}"]`;
  await page.waitForSelector(row);
  const remove = await page.$(`${row} button[aria-label^="Remove this widget"]`);
  if (remove) { await remove.click(); await page.waitForTimeout(500); }
  log(`${id} in picker`, (await page.textContent(`${row} .dash-widget-row-title`)).trim() + ' | ' + (await page.textContent(`${row} .dash-widget-row-desc`)).trim().slice(0, 50));
  await page.click(`${row} button[aria-label^="Add this widget"]`);
  await page.waitForTimeout(1500);
  await page.click('#dash-widgets-dialog [data-close-dialog]');
  await page.waitForSelector(`.dash-widget[data-widget="${id}"]:not(.dash-hidden)`, { state: 'attached', timeout: 8000 });
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  //: An empty notebook shows its empty state, not the widget grid: seed three notes once.
  const seeded = await page.evaluate(async () => {
    if (allEntries.length) return 0;
    for (const t of ['Buy milk and eggs', 'Plan the trip to the coast in May', 'Ideas for the garden bed']) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: t, defer_filing: true }) });
    return 3;
  });
  if (seeded) { await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForSelector('#lock-password', { timeout: 4000 }).then(async () => { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }).catch(() => {}); await page.waitForTimeout(3000); }
  await page.waitForSelector('#dash-customise button');
  const card = (id) => `.dash-widget[data-widget="${id}"]`;
  await page.evaluate(() => (typeof utilityClocks !== 'undefined') && utilityClocks.splice(0));

  // Clock
  await addWidget(page, 'clock');
  await page.waitForSelector(`${card('clock')} .clock-tabs`, { timeout: 8000 });
  await page.fill(`${card('clock')} input[data-clock-focus="timer"]`, '10s');
  await page.press(`${card('clock')} input[data-clock-focus="timer"]`, 'Enter');
  await page.waitForSelector(`${card('clock')} .clock-row`);
  const t0 = await page.textContent(`${card('clock')} .clock-row .clock-time`);
  await page.waitForTimeout(3000);
  const t1 = await page.textContent(`${card('clock')} .clock-row .clock-time`);
  log('timer 10s: now, +3s', `${t0} -> ${t1}`);
  await page.click(`${card('clock')} .clock-tabs [data-tab="stopwatch"]`);
  await page.click(`${card('clock')} [data-clock-focus="stopwatch"]`);
  await page.waitForTimeout(2500);
  const sw = await page.$$eval(`${card('clock')} .clock-row`, (rows) => rows.map((r) => r.querySelector('.clock-name').textContent + ' ' + r.querySelector('.clock-time').textContent));
  log('rows', JSON.stringify(sw));
  const noPopup = await page.$('[data-sheet="clock"]');
  log('popup opened (want false)', !!noPopup);
  const m = await page.$eval(`${card('clock')}`, (el) => { const r = el.getBoundingClientRect(); const b = el.querySelector('.dash-body').getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), bodyScrollW: el.querySelector('.dash-body').scrollWidth, bodyW: Math.round(b.width), docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth }; });
  log('clock card box', JSON.stringify(m));
  await page.screenshot({ path: `${process.env.SCRATCH || '.'}/shots/tools1558-clock-${W}-${process.env.THEME || 'light'}.png` });

  // Calculator
  await addWidget(page, 'calculator');
  await page.waitForSelector(`${card('calculator')} .calc-input`, { timeout: 8000 });
  await page.fill(`${card('calculator')} .calc-input`, '2+2');
  await page.press(`${card('calculator')} .calc-input`, 'Enter');
  await page.waitForTimeout(1200);
  const sum = await page.$eval(`${card('calculator')} .calc-pane:not(.hidden) .calc-result`, (el) => el.textContent.trim().replace(/\s+/g, ' '));
  log('2+2', sum);
  await page.click(`${card('calculator')} .calc-modes [data-tab="convert"]`);
  await page.fill(`${card('calculator')} .calc-amount`, '1');
  await page.waitForTimeout(1500);
  const conv = await page.$$eval(`${card('calculator')} .calc-convert .calc-result`, (els) => els.map((el) => el.textContent.trim().replace(/\s+/g, ' ')));
  const sel = await page.$eval(`${card('calculator')} .calc-from`, (el) => el.value) + ' -> ' + await page.$eval(`${card('calculator')} .calc-to`, (el) => el.value);
  log('1 km to miles', `${sel} | ${JSON.stringify(conv)}`);
  log('tabs (no Equation)', JSON.stringify(await page.$$eval(`${card('calculator')} .calc-modes [role="tab"]`, (t) => t.map((x) => x.textContent))));
  log('Insert visible (want false)', await page.$eval(`${card('calculator')} .calc-actions-buttons .primary`, (el) => el.offsetParent !== null));
  const cm = await page.$eval(`${card('calculator')}`, (el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth }; });
  log('calc card box', JSON.stringify(cm));
  await page.screenshot({ path: `${process.env.SCRATCH || '.'}/shots/tools1558-calc-${W}-${process.env.THEME || 'light'}.png` });

  // Reload: both widgets and the running clocks come back.
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { timeout: 5000 }).then(async () => { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }).catch(() => {});
  await page.waitForSelector(`${card('clock')} .clock-tabs`, { timeout: 20000 });
  await page.waitForSelector(`${card('calculator')} .calc-input`, { timeout: 20000 });
  await page.waitForTimeout(1500);
  const after = await page.$$eval(`${card('clock')} .clock-row`, (rows) => rows.map((r) => r.querySelector('.clock-name').textContent + ' ' + r.querySelector('.clock-time').textContent));
  log('after reload: widgets present', 'clock + calculator');
  log('after reload: clocks', JSON.stringify(after));
  const ids = await page.evaluate(() => { const all = [...document.querySelectorAll('[id]')].map((e) => e.id); return all.filter((id, i) => all.indexOf(id) !== i); });
  log('duplicate ids (want none)', JSON.stringify(ids));
  // Clean up the clocks so a later run starts clear.
  await page.evaluate(() => { for (const c of [...utilityClocks]) stopUtilityClock(c); });
  log('page errors (want 0)', errs.length + (errs.length ? ' ' + errs.join(' | ') : ''));
  await browser.close();
})().catch((e) => { console.log('SWEEP FAILED', e.message); process.exit(1); });
