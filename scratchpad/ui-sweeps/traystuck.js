// INBOX 1603: a tray popup left open after a drag, and whether anything closes it.
//   BASE=http://127.0.0.1:8781 SEED=1 node traystuck.js
const { boot } = require('./lib.js');
const say = (k, v) => console.log(k.padEnd(44), JSON.stringify(v));
const rect = (page, sel) => page.evaluate((sel) => { const e = [...document.querySelectorAll(sel)].find((e) => e.getClientRects().length); const r = e?.getBoundingClientRect(); return r && { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, w: r.width }; }, sel);
const state = (page) => page.evaluate(() => ({ expanded: $('status-tray').getAttribute('aria-expanded'), hidden: $('obj-tray').classList.contains('hidden'), visible: !!$('obj-tray').getClientRects().length && getComputedStyle($('obj-tray')).visibility !== 'hidden' && getComputedStyle($('obj-tray')).opacity !== '0', held: objTray.length, open: openHelpPopovers.size, close: !!$('obj-tray').querySelector('.popover-close, [data-close]') }));
async function drag(page, from, to, opts = {}) {
  await page.mouse.move(from.x, from.y); await page.mouse.down(); await page.waitForTimeout(320);
  await page.mouse.move(from.x + 8, from.y + 8, { steps: 3 });
  await page.mouse.move(to.x, to.y, { steps: 16 }); await page.waitForTimeout(opts.dwell || 150);
  if (opts.then) { await page.mouse.move(opts.then.x, opts.then.y, { steps: 16 }); await page.waitForTimeout(150); }
  await page.mouse.up(); await page.waitForTimeout(500);
}
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  page.on('pageerror', (e) => console.log('PAGEERROR', String(e).slice(0, 300)));
  if (process.env.SEED) await page.evaluate(async () => { if (!document.querySelector('#entry-list > li[data-id]')) for (let i = 1; i <= 6; i++) await api('/entries', { method: 'POST', body: JSON.stringify({ content: `Seed note ${i}: ${'compost and garden beds, '.repeat(6)}`, defer_filing: true }) }); });
  await page.reload(); await page.waitForTimeout(2500); if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(2500); } await page.evaluate("switchTab('notes')"); await page.waitForTimeout(1500); say('cards', await page.evaluate(() => document.querySelectorAll('#entry-list > li[data-id]').length));
  const reset = () => page.evaluate(() => { objTray = []; sessionStorage.removeItem('obj-tray'); objTrayPaint(); closeHelpPopovers(); });
  const card = async () => { const c = await rect(page, '#entry-list > li[data-id]'); return { x: c.left + Math.min(60, c.w / 4), y: c.y }; };
  const tray = await rect(page, '#status-tray');
  // A: card into the tray (spring opens it), then the row out to the notes list
  await reset();
  await drag(page, await card(), tray, { dwell: 700 });
  say('A1 after landing in tray', await state(page));
  const row = await rect(page, '#obj-tray .obj-tray-use');
  if (row) { await drag(page, row, { x: 700, y: 400 }); say('A2 row dragged out to the page', await state(page)); }
  await page.mouse.click(700, 300); await page.waitForTimeout(500);
  say('A3 after a click outside', await state(page));
  // B: spring open, then off and dropped on nothing
  await reset();
  await drag(page, await card(), tray, { dwell: 700, then: { x: 700, y: 120 } });
  say('B after spring then off', await state(page));
  // C: open by click, drag the row out and drop it on a note card
  await reset(); await page.evaluate(() => objTrayAdd({ kind: 'note', id: [...document.querySelectorAll('#entry-list > li[data-id]')][1].dataset.id, title: 'x' }));
  await page.mouse.click(tray.x, tray.y); await page.waitForTimeout(400);
  say('C1 opened by click', await state(page));
  const r2 = await rect(page, '#obj-tray .obj-tray-use');
  if (r2) { await drag(page, r2, await card()); say('C2 row dropped on a card', await state(page)); }
  await page.mouse.click(700, 300); await page.waitForTimeout(500);
  say('C3 after a click outside', await state(page));
  await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  say('C4 after Escape', await state(page));
  // D: a native drag whose dragend never reached the document, then a press outside
  await page.mouse.click(tray.x, tray.y); await page.waitForTimeout(400);
  await page.evaluate(() => document.dispatchEvent(new Event('dragstart')));
  await page.mouse.click(700, 300); await page.waitForTimeout(500);
  say('D lost dragend, then a press outside', await state(page));
  // E: the close x
  if ((await state(page)).hidden) await page.mouse.click(tray.x, tray.y); await page.waitForTimeout(400);
  const x = await page.evaluate(() => { const b = document.querySelector('#obj-tray .popover-close'); const r = b?.getBoundingClientRect(); const p = $('obj-tray').getBoundingClientRect(); return r && { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, insetRight: Math.round(p.right - r.right), insetTop: Math.round(r.top - p.top), label: b.getAttribute('aria-label') }; });
  say('E1 tray close x', x);
  if (x) { await page.mouse.click(x.x, x.y); await page.waitForTimeout(400); say('E2 after the x', { ...(await state(page)), focus: await page.evaluate(() => document.activeElement.id) }); }
  // F: the palette x
  await page.evaluate(() => openPalette()); await page.waitForTimeout(600);
  const px = await page.evaluate(() => { const b = $('palette-close'); const r = b.getBoundingClientRect(); const i = $('palette-input').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, inputW: Math.round(i.width), bt: Math.round(r.top), bh: r.height, it: Math.round(i.top), ih: i.height, head: getComputedStyle(document.querySelector('.palette-head')).display, sameRow: Math.abs((r.top + r.height / 2) - (i.top + i.height / 2)) < 2 }; });
  say('F1 palette x', px);
  await page.mouse.click(px.x, px.y); await page.waitForTimeout(400);
  say('F2 palette after x', await page.evaluate(() => $('palette-overlay').classList.contains('hidden')));
  // G: Other devices
  const lan = await page.evaluate(() => { const b = $('status-lan'); return b && !b.classList.contains('hidden') && b.getClientRects().length; });
  if (lan) { await page.click('#status-lan'); await page.waitForTimeout(1500); say('G other devices x', await page.evaluate(() => !!document.querySelector('#lan-popover .popover-close'))); } else say('G other devices', 'button not shown');
  await browser.close();
})();
