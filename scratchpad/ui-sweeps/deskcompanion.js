// The desktop companion's page (desktop-companion.html) at its window sizes.
//   BASE=http://127.0.0.1:8806 node scratchpad/ui-sweeps/deskcompanion.js
// Measures: the figure's box inside the 160x160 window, each state's panel
// inside the size the script asks the window for (SIZES in desk-companion.js),
// a note saved and a search answered while open, and the locked page showing
// Open Tessellate only. The window itself (transparency, on top, the taskbar)
// is a real Windows check this cannot make.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8806';
const PW = 'testpassword123';
const SIZES = { rest: [112, 152], menu: [208, 312], context: [208, 268], note: [320, 376], search: [340, 440] };
const out = [];
const say = (k, v) => { out.push(`${k}: ${JSON.stringify(v)}`); };
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 112, height: 152 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  const res = await ctx.request.post(BASE + '/auth/unlock', { data: { password: PW } });
  const token = (await res.json()).token;
  const open = async (tok, query = '') => {
    await page.goto(BASE + '/desktop-companion.html' + query, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { if (t) localStorage.setItem('token', t); else localStorage.removeItem('token'); }, tok);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
  };
  const box = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; }, sel);
  const fit = async (state) => {
    const [w, h] = SIZES[state];
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(150);
    //: The page and the open panel: a panel that scrolls inside its window is as wrong as a page that does.
    return page.evaluate(() => {
      const panel = [...document.querySelectorAll('.desk-panel')].find((e) => !e.classList.contains('hidden'));
      return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight, panelScroll: panel ? panel.scrollHeight - panel.clientHeight : null };
    });
  };

  await open(token);
  say('rest figure box', await box('.nm-figure'));
  say('rest pet box', await box('#desk-pet'));
  say('rest overflow', await fit('rest'));
  await page.screenshot({ path: (process.env.SCRATCH || '/tmp') + '/desk-rest.png' });

  await page.click('#desk-pet');
  await page.waitForTimeout(400);
  say('menu state/size', await page.evaluate(() => [document.body.dataset.state, document.body.dataset.size, document.body.dataset.locked]));
  say('menu items', await page.$$eval('#desk-menu button', (b) => b.map((x) => x.textContent.trim())));
  say('menu overflow', await fit('menu'));
  say('menu pet box', await box('#desk-pet'));

  await page.click('text=Quick note');
  await page.waitForTimeout(300);
  say('note state', await page.evaluate(() => document.body.dataset.state));
  say('note overflow', await fit('note'));
  const stamp = 'deskcompanion sweep ' + Date.now();
  await page.fill('#desk-note-text', stamp);
  await page.press('#desk-note-text', 'Enter');
  await page.waitForTimeout(1500);
  say('note status', await page.textContent('#desk-note-status'));
  const list = await (await ctx.request.get(BASE + '/entries?limit=5', { headers: { 'X-Auth-Token': token } })).json();
  say('note saved', JSON.stringify(list).includes(stamp));

  await page.keyboard.press('Escape');
  await page.click('#desk-pet');
  await page.waitForTimeout(300);
  await page.click('text=Quick search');
  await page.waitForTimeout(300);
  say('search overflow', await fit('search'));
  await page.fill('#desk-search-text', 'deskcompanion');
  await page.waitForTimeout(1500);
  say('search hits', await page.$$eval('#desk-search-hits .desk-hit-title', (n) => n.map((x) => x.textContent.slice(0, 40))));
  say('search status', await page.textContent('#desk-search-status'));

  await page.keyboard.press('Escape');
  await page.click('#desk-pet', { button: 'right' });
  await page.waitForTimeout(300);
  say('context items', await page.$$eval('#desk-menu button', (b) => b.map((x) => x.textContent.trim())));
  say('context overflow', await fit('context'));

  await page.setViewportSize({ width: 112, height: 152 });
  await open('');
  await page.click('#desk-pet');
  await page.waitForTimeout(400);
  say('locked: data-locked', await page.evaluate(() => document.body.dataset.locked));
  say('locked: menu items', await page.$$eval('#desk-menu button', (b) => b.map((x) => x.textContent.trim())));
  say('locked: note/search in menu', await page.$$eval('#desk-menu button', (b) => b.some((x) => /note|search/i.test(x.textContent))));
  await page.evaluate(() => document.getElementById('desk-search-text').value = 'deskcompanion');
  say('locked: search hits drawn', await page.$$eval('#desk-search-hits li', (n) => n.length));

  await open(token, '?card=1');
  say('card class', await page.evaluate(() => [document.body.classList.contains('desk-card'), getComputedStyle(document.body).backgroundColor]));
  await open(token);
  say('transparent bg', await page.evaluate(() => getComputedStyle(document.body).backgroundColor));
  say('errors', errors);
  console.log(out.join('\n'));
  await browser.close();
})();
