// Brief 77 row 2 (WORLD_CLASS 28.1 rules 2, 13): a new board from the
// dashboard, counted the way deepen72a.js counts (Library, Boards & maps,
// New's Whiteboard row), timed from that press to a canvas a pen stroke can
// land on, then renamed in place: Escape keeps the untitled name, Enter saves
// a typed one.
//
//   BASE=http://127.0.0.1:8823 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/wbnewboard77.js
const { boot } = require('./lib.js');
const WIDTH = Number(process.env.WIDTH || 1440);
(async () => {
  const touch = WIDTH < 600;
  const { browser, page } = await boot({ viewport: { width: WIDTH, height: touch ? 844 : 900 }, hasTouch: touch, isMobile: touch });
  const r = { clicks: 0 };
  await page.evaluate(() => switchTab('dashboard')); await page.waitForTimeout(600);
  await page.click('[data-tab="library"]'); r.clicks++; await page.waitForTimeout(800);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]'); r.clicks++;
  await page.waitForFunction(() => typeof wbNewUntitledBoard === 'function' && document.getElementById('wb-boards-new')?.getClientRects().length !== undefined, null, { timeout: 20000 });
  await page.waitForTimeout(1500);
  const before = await page.evaluate(() => window.currentBoardId || null);
  // The New menu's summary is the menu's opener, not a choice; counted apart.
  r.menuOpen = 0; // New is a split button: its press is the whole path (INBOX 1520)
  const t0 = Date.now();
  await page.click('#wb-boards-new'); r.clicks++;
  await page.waitForFunction((b) => window.currentBoardId && window.currentBoardId !== b
    && document.getElementById('whiteboard-container')?.getClientRects().length
    && document.activeElement?.id === 'wb-name-field', before, { timeout: 15000, polling: 16 });
  r.msToCanvas = Date.now() - t0;
  r.dialogShown = await page.evaluate(() => [...document.querySelectorAll('#wb-template-dialog, .confirm-overlay')].some((d) => d.getClientRects().length && getComputedStyle(d).visibility !== 'hidden'));
  r.field = await page.evaluate(() => { const f = document.getElementById('wb-name-field'); return { value: f.value, selected: f.selectionEnd - f.selectionStart === f.value.length }; });
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  r.afterEscape = await page.evaluate(() => ({ field: !!document.getElementById('wb-name-field'), title: document.getElementById('wb-board-select').selectedOptions[0]?.dataset.title }));
  // A pen stroke lands: the canvas is drawable.
  await page.evaluate(() => wbSelectToolRef('draw'));
  const box = await page.evaluate(() => { const b = document.getElementById('whiteboard-container').getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
  const n0 = await page.evaluate(() => (wbState.sketches || []).length);
  await page.mouse.move(box.x, box.y); await page.mouse.down(); await page.mouse.move(box.x + 60, box.y + 30, { steps: 6 }); await page.mouse.up();
  await page.waitForTimeout(800);
  r.strokeLanded = (await page.evaluate(() => (wbState.sketches || []).length)) > n0;
  await page.evaluate(() => wbSelectToolRef('select'));
  await page.evaluate(() => document.getElementById('wb-rename-board').click()); await page.waitForTimeout(300);
  r.renameField = await page.evaluate(() => document.activeElement?.id === 'wb-name-field');
  await page.keyboard.type('Sweep named ' + Date.now().toString(36)); await page.keyboard.press('Enter'); await page.waitForTimeout(900);
  r.afterEnter = await page.evaluate(() => document.getElementById('wb-board-select').selectedOptions[0]?.dataset.title);
  console.log(JSON.stringify(r));
  await browser.close();
})();
