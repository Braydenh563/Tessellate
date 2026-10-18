// C12: a modal card's head stays at the card's top edge after a 400px scroll,
// on an opaque ground. Statistics, Keyboard shortcuts, Whiteboard help, Earlier versions.
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node dialogheadsticky.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({});
  if (process.env.THEME === 'dark') await page.evaluate(() => { window.__dark = true; });
  await page.waitForTimeout(1500);
  const cases = [
    ['Statistics', 'openStatistics()'],
    ['Keyboard shortcuts', 'openShortcuts()'],
    ['Whiteboard help', "(()=>{document.getElementById('wb-help-overlay').classList.remove('hidden');})()"],
    ['Earlier versions', "(()=>{document.getElementById('history-overlay').classList.remove('hidden');})()"],
  ];
  let bad = 0;
  for (const [name, open] of cases) {
    const r = await page.evaluate(async (open) => {
      if (window.__dark) document.documentElement.dataset.theme = 'dark';
      await eval(open);
      await new Promise((r) => setTimeout(r, 900));
      const overlay = [...document.querySelectorAll('.modal-overlay')].filter((o) => o.getClientRects().length && !o.classList.contains('hidden')).pop();
      const card = overlay.querySelector('.modal-card');
      const head = card.querySelector(':scope > .dialog-head');
      if (card.scrollHeight - card.clientHeight < 410) { const sp = document.createElement('div'); sp.style.height = '1200px'; card.appendChild(sp); }
      const theme = document.documentElement.dataset.theme || '';
      const rest = head.getBoundingClientRect().top - card.getBoundingClientRect().top;
      card.scrollTop = 400;
      await new Promise((r) => setTimeout(r, 200));
      const after = head.getBoundingClientRect().top - card.getBoundingClientRect().top;
      const cs = getComputedStyle(head);
      return { rest: +rest.toFixed(1), after: +after.toFixed(1), st: card.scrollTop, bg: cs.backgroundColor, pos: cs.position + ' ' + theme + ' card ' + getComputedStyle(card).backgroundColor + ' opaque ' + getComputedStyle(card).getPropertyValue('--modal-bg-opaque') };
    }, open);
    const ok = r.st < 399 ? null : r.st >= 399 && Math.abs(r.after - r.rest) < 1.5 && !/rgba\(.*, 0\)|transparent/.test(r.bg);
    if (ok === false) bad++;
    console.log(`${name}: head top ${r.rest} at rest, ${r.after} after scrollTop ${r.st}; ${r.pos}, ${r.bg} ${ok === null ? 'skip, an inner pane scrolls' : ok ? 'ok' : 'FAIL'}`);
    await page.keyboard.press('Escape'); await page.evaluate(() => document.querySelectorAll('.modal-overlay:not(.hidden)').forEach((o) => o.classList.contains('stats-overlay') ? o.remove() : o.classList.add('hidden')));
  }
  await browser.close();
  console.log(bad ? 'FAIL' : 'PASS'); process.exit(bad ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
