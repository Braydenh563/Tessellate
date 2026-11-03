// INBOX 1603 rest: drop into the open popup, row body drag, edge scroll over the tray, button padding.
const { boot } = require('./lib.js');
const say = (k, v) => console.log(k.padEnd(40), JSON.stringify(v));
const rect = (page, sel) => page.evaluate((sel) => { const e = [...document.querySelectorAll(sel)].find((e) => e.getClientRects().length); const r = e?.getBoundingClientRect(); return r && { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, top: r.top, w: r.width, h: r.height }; }, sel);
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  page.on('pageerror', (e) => console.log('PAGEERROR', String(e).slice(0, 300)));
  await page.reload(); await page.waitForTimeout(2500);
  if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(2500); }
  await page.evaluate("switchTab('notes')"); await page.waitForTimeout(1500);
  const ids = await page.evaluate(() => [...document.querySelectorAll('#entry-list > li[data-id]')].map((e) => e.dataset.id));
  await page.evaluate((id) => { objTray = []; objTrayAdd({ kind: 'note', id: Number(id), title: 'first' }); }, ids[0]);
  const tray = await rect(page, '#status-tray');
  say('button', await page.evaluate(() => { const b = $('status-tray'); const r = b.getBoundingClientRect(); const i = b.querySelector('.ph').getBoundingClientRect(); const c = b.querySelector('.status-tray-count').getBoundingClientRect(); const cs = getComputedStyle(b); return { w: r.width, h: r.height, pad: cs.paddingLeft + ' ' + cs.paddingRight, iconLeftGap: Math.round(i.left - r.left), countRightGap: Math.round(r.right - c.right) }; }));
  await page.mouse.click(tray.x, tray.y); await page.waitForTimeout(500);
  say('panel', await page.evaluate(() => { const p = $('obj-tray').getBoundingClientRect(); const row = document.querySelector('#obj-tray .obj-tray-item').getBoundingClientRect(); const cs = getComputedStyle($('obj-tray')); return { pad: cs.padding, rowLeftGap: Math.round(row.left - p.left), rowRightGap: Math.round(p.right - row.right) }; }));
  // drag a card into the open panel's list area
  const card = await page.evaluate(() => { const c = [...document.querySelectorAll('#entry-list > li[data-id]')][3].getBoundingClientRect(); return { x: c.left + 60, y: c.top + c.height / 2 }; });
  const pr = await rect(page, '#obj-tray .obj-tray-list');
  await page.mouse.move(card.x, card.y); await page.mouse.down(); await page.waitForTimeout(320);
  await page.mouse.move(card.x + 8, card.y + 8, { steps: 3 });
  await page.mouse.move(pr.x, pr.y, { steps: 16 }); await page.waitForTimeout(200);
  const before = await page.evaluate(() => ({ marked: [...document.querySelectorAll('.obj-target')].map((e) => e.id || e.className.slice(0, 30)), scroll: document.scrollingElement.scrollTop, list: $('entry-list').closest('.tab-panel, main')?.scrollTop }));
  await page.waitForTimeout(800);
  const after = await page.evaluate(() => ({ scroll: document.scrollingElement.scrollTop, list: $('entry-list').closest('.tab-panel, main')?.scrollTop }));
  await page.mouse.up(); await page.waitForTimeout(500);
  say('drop into open panel', { before, after, held: await page.evaluate(() => objTray.length), open: await page.evaluate(() => $('status-tray').getAttribute('aria-expanded')) });
  // row body drag: press on the row's words, move, see a ghost
  const row = await rect(page, '#obj-tray .obj-tray-use');
  await page.mouse.move(row.left + 30, row.y); await page.mouse.down(); await page.waitForTimeout(50);
  await page.mouse.move(row.left + 60, row.y - 60, { steps: 6 }); await page.waitForTimeout(200);
  say('row drag ghost', await page.evaluate(() => !!document.querySelector('.obj-ghost')));
  await page.mouse.move(700, 300, { steps: 10 }); await page.mouse.up(); await page.waitForTimeout(400);
  await page.evaluate(() => closeHelpPopovers()); await page.waitForTimeout(300);
  await page.mouse.click(5, 5); await page.keyboard.press('t'); await page.keyboard.press('y'); await page.waitForTimeout(500);
  say('t then y', await page.evaluate(() => $('status-tray').getAttribute('aria-expanded')));
  // a click on a row without moving still pastes (no drag): count stays, no ghost
  const r3 = await rect(page, '#obj-tray .obj-tray-use');
  await page.mouse.click(r3.x, r3.y); await page.waitForTimeout(300);
  say('row click no ghost', await page.evaluate(() => !document.querySelector('.obj-ghost')));
  await browser.close();
})();
