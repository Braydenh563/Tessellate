// INBOX 1595: real mouse drags to the tray button, landed or not, for the hold, a
// failed try then a retry, and the grip; and the grip's own geometry.
//   BASE=http://127.0.0.1:8854 [SEED=1] [OVERRIDE_JS=obj-drag.js=/path/old.js] node objgrip.js [label]
const { boot } = require('./lib.js');
const LABEL = process.argv[2] || 'run';
const say = (k, v) => console.log(`${LABEL} ${k}`.padEnd(54), JSON.stringify(v));

const KINDS = {
  note: { tab: "switchTab('notes')", sel: '#entry-list > li[data-id]' },
  library: { tab: "switchTab('library')", sel: '.library-card.library-note' },
  document: { tab: "switchTab('library')", sel: '.library-card.library-document' },
  board: { tab: "switchTab('library')", sel: '.library-card.library-board' },
};
const rect = (page, sel, i = 0) => page.evaluate(([sel, i]) => {
  const r = [...document.querySelectorAll(sel)].filter((e) => e.getClientRects().length)[i]?.getBoundingClientRect();
  return r && { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height };
}, [sel, i]);
const held = (page) => page.evaluate(() => objTray.length);

async function prepare(page, kind) {
  const k = KINDS[kind];
  await page.evaluate(k.tab); await page.waitForTimeout(1500);
  await page.evaluate((sel) => { [...document.querySelectorAll(sel)].find((e) => e.getClientRects().length)?.scrollIntoView({ block: 'center' }); }, k.sel);
  await page.waitForTimeout(800);
  await page.evaluate(() => { objTray = []; sessionStorage.removeItem('obj-tray'); objTrayPaint(); closeHelpPopovers(); getSelection().removeAllRanges(); });
  await page.waitForTimeout(300);
  return k;
}

//: how: 'hold' | 'retry' | 'grip' | 'gripFast'
async function attempt(page, kind, how) {
  const k = await prepare(page, kind);
  const card = await rect(page, k.sel);
  if (!card) return { kind, how, error: 'no card' };
  const dest = await rect(page, '#status-tray');
  // a spot on the card's own words, left of its middle, clear of its controls
  const px = card.left + Math.min(60, card.w / 4), py = card.y;
  await page.mouse.move(px, py);
  let note = {};
  if (how === 'hold') {
    await page.mouse.down(); await page.waitForTimeout(320);
    await page.mouse.move(px + 8, py + 8, { steps: 3 });
  } else if (how === 'retry') {
    // the failed try: press, move before the hold is over, let go
    await page.mouse.down(); await page.waitForTimeout(100);
    await page.mouse.move(px + 90, py, { steps: 6 }); await page.mouse.up();
    await page.waitForTimeout(150);
    note.selected = await page.evaluate(() => String(getSelection()).length);
    // retry on the selection: a point inside its first rect
    const spot = await page.evaluate(() => { const r = getSelection().rangeCount ? [...getSelection().getRangeAt(0).getClientRects()][0] : null; return r && { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    if (!spot) return { kind, how, note, error: 'no selection to retry on' };
    await page.mouse.move(spot.x, spot.y);
    await page.mouse.down(); await page.waitForTimeout(320);
    await page.mouse.move(spot.x + 8, spot.y + 8, { steps: 3 });
  } else {
    await page.mouse.move(px, py, { steps: 2 }); await page.waitForTimeout(350);
    const g = await rect(page, '.obj-grip');
    note.grip = g && await page.evaluate((sel) => { const gr = document.querySelector('.obj-grip'); const c = [...document.querySelectorAll(sel)].find((e) => e.getClientRects().length).getBoundingClientRect(); const r = gr.getBoundingClientRect(); return { on: gr.classList.contains('is-on'), opacity: getComputedStyle(gr).opacity, w: r.width, h: r.height, leftOfCard: Math.round(c.left - r.left), cardMid: Math.round((r.top + r.height / 2) - (c.top + c.height / 2)), onScreen: r.left >= 0 && r.right <= innerWidth }; }, k.sel);
    if (!g) return { kind, how, note, error: 'no grip' };
    await page.mouse.move(g.x, g.y, { steps: 4 });
    await page.mouse.down();
    if (how === 'grip') await page.waitForTimeout(0);
    await page.mouse.move(g.x + 8, g.y + 8, { steps: 2 });
  }
  await page.mouse.move(dest.x, dest.y, { steps: 16 });
  await page.waitForTimeout(150);
  const ghost = await page.evaluate(() => !!document.querySelector('.obj-ghost'));
  await page.mouse.up(); await page.waitForTimeout(400);
  return { kind, how, ghost, landed: (await held(page)) === 1, ...note };
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  if (process.env.SEED) await page.evaluate(async () => {
    const post = async (path, body) => { try { await api(path, { method: 'POST', body: JSON.stringify(body) }); } catch (e) { console.log('seed failed', path, String(e).slice(0, 80)); } };
    if (!document.querySelector('#entry-list > li[data-id]')) for (let i = 1; i <= 12; i++) await post('/entries', { content: `Seed note ${i}: ${'compost and garden beds, '.repeat(8)}`, defer_filing: true });
    for (let i = 1; i <= 3; i++) await post('/documents', { title: `Seed document ${i}`, content: `Words in document ${i}. `.repeat(10) });
    for (let i = 1; i <= 3; i++) await post('/boards', { name: `Seed board ${i}` });
  });
  page.on('pageerror', (e) => console.log('PAGEERROR', String(e).slice(0, 300)));
  const hows = (process.env.HOWS || 'hold,retry,grip').split(',');
  const kinds = (process.env.KINDS || Object.keys(KINDS).join(',')).split(',');
  const all = [];
  for (const how of hows) for (const kind of kinds) { const r = await attempt(page, kind, how); all.push(r); say(`${how} ${kind}`, r); }
  for (const how of hows) say(`landed ${how}`, `${all.filter((r) => r.how === how && r.landed).length}/${all.filter((r) => r.how === how).length}`);
  // keyboard focus shows the grip
  await prepare(page, 'note');
  const kb = await page.evaluate(async () => {
    const li = [...document.querySelectorAll('#entry-list > li[data-id]')].find((e) => e.getClientRects().length);
    const target = li.matches('[tabindex]') ? li : (li.querySelector('a[href],button,[tabindex]') || li);
    target.focus({ focusVisible: true });
    await new Promise((r) => setTimeout(r, 400));
    const g = document.querySelector('.obj-grip');
    return { focused: document.activeElement === target, focusVisible: target.matches(':focus-visible'), on: g?.classList.contains('is-on') ?? null, tag: target.tagName };
  });
  say('keyboard focus shows the grip', kb);
  await browser.close();
})();
