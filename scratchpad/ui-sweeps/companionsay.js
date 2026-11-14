// The companion's speech line (INBOX 481): the bubble must hold its text.
// Measures `.nm-say` on #nm-buddy (box vs scrollWidth, padding on both sides,
// a background behind the whole line) per look, width and pose, and writes a
// PNG per case to OUT_DIR. Env: BASE, THEME=dark, OUT_DIR.
const fs = require('fs');
const { boot } = require('./lib.js');
const OUT = process.env.OUT_DIR || '/tmp/companionsay';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  let bad = 0;
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const mobile = w < 600 ? { hasTouch: true, isMobile: true } : {};
    const { browser, page } = await boot({ viewport: { width: w, height: h }, ...mobile });
    for (const look of ['masculine', 'feminine']) {
      await page.evaluate(async ([look]) => {
        localStorage.setItem('atlas-look', look);
        prefs.set('avatar-buddy', 'me'); await ensureModule('characters'); syncNameMarkBuddy();
      }, [look]);
      await page.waitForTimeout(400);
      await page.evaluate(async () => { prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
      await page.waitForTimeout(2500);
      await page.evaluate(() => {
        clearTimeout(nmb.timer);
        window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
        window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
      });
      for (const pose of ['stand', 'sit', 'hang', 'lie']) {
        const r = await page.evaluate(([pose, w]) => {
          const buddy = document.getElementById('nm-buddy');
          const x = Math.round(w / 2), y = 420;
          nameMarkBuddyRide(null, x, y);
          nameMarkBuddyMoveTo(buddy, { kind: 'card', pose, legs: '', x, y }, true);
          nameMarkSay(buddy, "I'm not talking to you.");
          const s = buddy.querySelector(':scope > .nm-say');
          const b = s.getBoundingClientRect();
          const cs = getComputedStyle(s);
          const range = document.createRange(); range.selectNodeContents(s);
          const t = range.getBoundingClientRect();
          return { pose, box: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
            text: [Math.round(t.left), Math.round(t.top), Math.round(t.width), Math.round(t.height)],
            scrollW: s.scrollWidth, clientW: s.clientWidth, display: cs.display, width: cs.width, ws: cs.whiteSpace,
            padL: Math.round(t.left - b.left), padR: Math.round(b.right - t.right), inWin: b.left >= 0 && b.right <= innerWidth };
        }, [pose, w]);
        const ok = r.padL >= 4 && r.padR >= 4 && r.scrollW <= r.clientW + 1 && r.text[3] <= r.box[3] && r.inWin;
        if (!ok) bad += 1;
        console.log(ok ? 'ok ' : 'BAD', w, look, JSON.stringify(r));
        const c = { x: Math.max(0, r.box[0] - 60), y: Math.max(0, Math.min(r.box[1], r.text[1]) - 60) };
        await page.screenshot({ path: `${OUT}/${w}-${look}-${pose}.png`, clip: { ...c, width: Math.min(w - c.x, Math.max(r.box[2], r.text[2]) + 120), height: 260 } });
      }
      // The large view (a double-click): the companion's own element moves
      // into the viewer's stage, and says its lines there. This is where the
      // owner's screenshot came from: the stage's rule set `right` and the
      // figure's set `left: 100%`, so the box was the 8px between them.
      for (const pose of ['stand', 'hang']) {
        await page.evaluate(([pose, w]) => {
          const buddy = document.getElementById('nm-buddy');
          const x = Math.round(w / 2), y = 420;
          nameMarkBuddyRide(null, x, y);
          nameMarkBuddyMoveTo(buddy, { kind: 'card', pose, legs: '', x, y }, true);
          buddy.querySelector('.nm-buddy-face').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
        }, [pose, w]);
        await page.waitForTimeout(900);
        const r = await page.evaluate(() => {
          const buddy = document.getElementById('nm-buddy');
          nameMarkSay(buddy, "I'm not talking to you.");
          const s = buddy.querySelector(':scope > .nm-say');
          const b = s.getBoundingClientRect();
          const range = document.createRange(); range.selectNodeContents(s);
          const t = range.getBoundingClientRect();
          const card = document.querySelector('.nm-viewer-card').getBoundingClientRect();
          return { pose: 'view-' + buddy.dataset.pose, inView: !!buddy.closest('.nm-viewer-figure'),
            box: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
            text: [Math.round(t.left), Math.round(t.top), Math.round(t.width), Math.round(t.height)],
            scrollW: s.scrollWidth, clientW: s.clientWidth,
            padL: Math.round(t.left - b.left), padR: Math.round(b.right - t.right),
            inWin: b.left >= 0 && b.right <= innerWidth, inCard: b.left >= card.left && b.right <= card.right && b.top >= card.top };
        });
        const ok = r.inView && r.padL >= 4 && r.padR >= 4 && r.scrollW <= r.clientW + 1 && r.text[3] <= r.box[3] && r.inWin && r.inCard;
        if (!ok) bad += 1;
        console.log(ok ? 'ok ' : 'BAD', w, look, JSON.stringify(r));
        const card = await page.evaluate(() => { const c = document.querySelector('.nm-viewer-card').getBoundingClientRect(); return [c.left, c.top, c.width, c.height]; });
        await page.screenshot({ path: `${OUT}/${w}-${look}-view-${pose}.png`, clip: { x: Math.max(0, card[0] - 10), y: Math.max(0, card[1] - 10), width: Math.min(w, card[2] + 20), height: card[3] + 20 } });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      }
    }
    await browser.close();
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS');
  process.exitCode = bad ? 1 : 0;
})();
