// INBOX 1301 D2/D3: the first-steps card and the Get started menu.
// Measures the card's top and height and the first widget's top as each
// step completes (name, note, ask), at 1440x900 and 390x844, then the
// Get started menu's Hide and Mark all done, and the Customise restore row.
//   BASE=http://127.0.0.1:8799 node scratchpad/ui-sweeps/getstarted1301.js
const { boot } = require('./lib.js');
const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
const phone = W < 600;

async function measure(page, label) {
  await page.waitForTimeout(900);
  const m = await page.evaluate(() => {
    const r = (el) => (el ? el.getBoundingClientRect() : null);
    const card = document.querySelector('#dash-first-steps .first-steps');
    const grid = document.getElementById('dash-grid');
    const first = grid?.querySelector('.dash-widget');
    const c = r(card), g = r(first), opener = document.getElementById('dash-start-menu');
    return {
      cardTop: c ? Math.round(c.top + scrollY) : null,
      cardH: c ? Math.round(c.height) : null,
      widgetTop: g ? Math.round(g.top + scrollY) : null,
      opener: opener ? opener.textContent.trim() : null,
      openerShown: opener ? opener.getBoundingClientRect().width > 0 : false,
      progress: document.querySelector('.first-steps-progress')?.getAttribute('aria-valuenow') ?? null,
      tiles: [...document.querySelectorAll('#dash-first-steps .start-step')].map((t) => Math.round(t.getBoundingClientRect().height)).join(','),
      overflowX: document.documentElement.scrollWidth > innerWidth,
      above: [...document.querySelectorAll('#tab-dashboard > *, #tab-dashboard > * > *')].filter((e) => e.getBoundingClientRect().height).slice(0, 6).map((e) => (e.id || e.className.split(' ')[0]) + ':' + Math.round(e.getBoundingClientRect().height)).join(' '),
    };
  });
  console.log(label.padEnd(14), JSON.stringify(m));
  return m;
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  const api = (path, method, body) => page.evaluate(([p, m, b]) => apiJson(p, { method: m, body: b ? JSON.stringify(b) : undefined }), [path, method, body]);
  await page.evaluate(() => { localStorage.removeItem('firstStepsHidden'); localStorage.removeItem('getStartedHidden'); localStorage.removeItem('getStartedDone'); });
  // A clean start on a used data dir: no name, every note in the bin.
  await page.evaluate(async () => {
    await apiJson('/preferences', { method: 'PUT', body: JSON.stringify({ display_name: '' }) });
    prefsCache = await apiJson('/preferences');
    for (const e of allEntries) await apiJson(`/entries/${e.id}`, { method: 'DELETE' }).catch(() => {});
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3500);
  const go = async () => { await page.evaluate(() => { renderDashboard?.(); }); };
  await go();
  await measure(page, '0 done');
  await api('/preferences', 'PUT', { display_name: 'Sam' });
  await page.evaluate(async () => { prefsCache = await apiJson('/preferences'); });
  await go();
  await measure(page, '1 name');
  const made = await api('/entries', 'POST', { content: 'A first note about the garden #home' }).catch((e) => ({ err: String(e) }));
  await page.evaluate(async () => { await refreshEntries?.(); }).catch(() => {});
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await go();
  await measure(page, '2 note');
  if (process.env.D3) {
    // D3: Mark all done from the Get started menu, then Hide, then restore.
    await page.click('#dash-start-menu');
    await page.waitForTimeout(300);
    const rows = await page.evaluate(() => [...document.querySelectorAll('.kebab-menu [role=menuitem], .kebab-menu button')].map((b) => b.textContent.trim()).filter(Boolean));
    console.log('menu rows', JSON.stringify(rows));
    await page.getByRole('menuitem', { name: /Mark all as done/ }).click();
    await measure(page, 'marked done');
    await page.click('#dash-start-menu');
    await page.waitForTimeout(300);
    await page.getByRole('menuitem', { name: /Hide Get started/ }).click();
    await measure(page, 'hidden');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    await measure(page, 'after reload');
    await page.click('#dash-customise button');
    await page.waitForTimeout(300);
    await page.getByRole('menuitem', { name: /Show Get started/ }).click();
    await measure(page, 'restored');
  }
  console.log('note', JSON.stringify(made).slice(0, 80));
  await browser.close();
})();
