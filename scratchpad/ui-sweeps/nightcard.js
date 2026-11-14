// Dashboard, While you were away: the morning card over GET /night/latest.
//
//   BASE=http://127.0.0.1:8847 node scratchpad/ui-sweeps/nightcard.js   (W=390 for a phone)
//
// Seeds three notes with claims and questions, runs one night pass, shows the
// widget alone on the dashboard, and measures: the summary line, one line per
// kind with its count, a line opens its review list (aria-expanded, rows
// with open and dismiss), Show more pages, dismiss removes the row and lowers
// the count, and nothing in the card overflows it.
const { boot } = require('./lib.js');
const fs = require('fs');

(async () => {
  const W = Number(process.env.W || 1440);
  const shots = process.env.SHOTS || '.';
  fs.mkdirSync(shots, { recursive: true });
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  const out = [];
  const check = (name, ok, detail = '') => out.push(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ': ' + detail : ''}`);
  await page.evaluate(async () => {
    const notes = [
      'The launch should move to the fourth of October. Who owns the rollback plan? Should we tell the beta group first? What does support need from us?',
      'The pump is too small for the pond. Does the filter need replacing this year? The fish have always done better in spring.',
      'The budget must stay under ten thousand. Is the second contractor cheaper? When do we need the quote by? Who signs it off?',
    ];
    for (const content of notes) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content }) });
    await apiJson('/night/run', { method: 'POST', body: JSON.stringify({ budget: 20000, force: true }) });
    const hidden = Object.keys(DASH_WIDGETS).filter((n) => n !== 'night');
    await setPreference('dashboard_layout', { order: ['night', ...hidden], hidden, wide: [] });
    prefsCache.dashboard_layout = { order: ['night', ...hidden], hidden, wide: [] };
    switchTab('dashboard');
    await renderDashboard();
  });
  await page.waitForTimeout(1500);
  const card = await page.evaluate(() => {
    const body = document.querySelector('.night-summary')?.parentElement;
    return {
      summary: document.querySelector('.night-summary')?.textContent || '',
      lines: [...document.querySelectorAll('.night-kind-toggle')].map((b) => b.textContent.trim()),
      body: !!body,
    };
  });
  check('summary line', /Read \d+ notes?/.test(card.summary), card.summary);
  check('a line per kind', card.lines.length >= 2, JSON.stringify(card.lines));
  const q = await page.$('.night-kind-toggle:has-text("open question")');
  if (!q) {
    console.log(out.join('\n'));
    console.log('DEBUG', await page.evaluate(() => ({ layout: dashLayout(), widgets: [...document.querySelectorAll('[data-widget]')].map((w) => w.dataset.widget), tab: document.querySelector('.tab-page:not(.hidden)')?.id })));
    await browser.close();
    return;
  }
  await q.click();
  await page.waitForTimeout(800);
  const opened = await page.evaluate(() => {
    const t = [...document.querySelectorAll('.night-kind-toggle')].find((b) => b.textContent.includes("open question"));
    const list = document.getElementById(t.getAttribute('aria-controls'));
    return { expanded: t.getAttribute('aria-expanded'), rows: list.querySelectorAll('li').length, more: !list.nextElementSibling.classList.contains('hidden') };
  });
  check('opens its review list', opened.expanded === 'true' && opened.rows === 5, JSON.stringify(opened));
  if (opened.more) {
    await page.click('.night-more:not(.hidden)');
    await page.waitForTimeout(800);
  }
  const paged = await page.evaluate(() => document.querySelectorAll('.night-facts:not(.hidden) li').length);
  check('show more pages', paged > 5, String(paged));
  const layout = await page.evaluate(() => {
    const card = document.querySelector('.night-summary').closest('.dash-widget, .card, section');
    const r = card.getBoundingClientRect();
    const over = [...card.querySelectorAll('*')].filter((el) => el.getClientRects().length && el.getBoundingClientRect().right > r.right + 1);
    const btn = document.querySelector('.night-fact-actions button').getBoundingClientRect();
    return { over: over.map((el) => el.className).slice(0, 4), button: [Math.round(btn.width), Math.round(btn.height)] };
  });
  check('nothing overflows the card', layout.over.length === 0, JSON.stringify(layout));
  //: The widget grows to fit the review list it opened rather than scrolling
  //: inside a fixed-height body (the cap in 01-forms-settings.css).
  const grown = await page.evaluate(() => {
    const body = document.querySelector('.night-summary').parentElement;
    const cs = getComputedStyle(body);
    return { scroll: body.scrollHeight, client: body.clientHeight, maxHeight: cs.maxHeight, overflowY: cs.overflowY };
  });
  check('the card grows to fit its list, no inner scroll', grown.scroll <= grown.client + 1 && grown.maxHeight === 'none', JSON.stringify(grown));
  await page.screenshot({ path: `${shots}/night-${W}.png` });
  const before = await page.evaluate(() => [...document.querySelectorAll('.night-kind-toggle')].find((b) => b.textContent.includes("open question")).textContent.trim());
  await page.click('.night-facts:not(.hidden) li .night-fact-actions button[aria-label^="Dismiss"]');
  await page.waitForTimeout(800);
  const after = await page.evaluate(() => [...document.querySelectorAll('.night-kind-toggle')].find((b) => b.textContent.includes("open question")).textContent.trim());
  check('dismiss lowers the count', before !== after, `${before} -> ${after}`);
  console.log(out.join('\n'));
  await browser.close();
})();
