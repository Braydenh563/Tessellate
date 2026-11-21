// The companion's menu, with the companion low (the owner, again: "the right
// click companion popup still doesnt appear next to the companion and
// instead at the top of the screen or somwhwere eles", with it perched near
// the status bar on the dashboard). companionmenu.js passes; this one runs
// the same opening under every motion setting, which is what it never did:
// the OS hint (reduced motion), the app's own Still switch, and neither.
//
// Each case: the companion sat on the status bar's ledge, floating at the
// bottom left, and riding a low dashboard panel that is then scrolled; the
// menu opened by a right-click and from the keyboard; at 1440x900 and at a
// short 1440x600. The menu's box must touch the companion's (8px at most
// between them) and sit inside the window.
//
//   BASE=http://127.0.0.1:8830 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/companionmenulow.js   (exits 1 on a miss)
//   MOTIONS=reduce,app,full  SIZES=1440x900,1440x600
const { boot } = require('./lib.js');
const MOTIONS = (process.env.MOTIONS || 'reduce,app,full').split(',');
const SIZES = (process.env.SIZES || '1440x900,1440x600').split(',');
(async () => {
  const fails = [];
  let count = 0;
  for (const motion of MOTIONS) {
    for (const size of SIZES) {
      const [w, h] = size.split('x').map(Number);
      const { browser, page } = await boot({ viewport: { width: w, height: h }, reducedMotion: motion === 'reduce' ? 'reduce' : 'no-preference' });
      try {
        await page.evaluate(async (m) => {
          prefs.set("avatar-buddy", "atlas"); await ensureModule("characters"); syncNameMarkBuddy();
          //: Appearance, Reduce motion: the app's own switch.
          const still = document.getElementById('reduce-motion-toggle');
          if (m === 'app' && still && !still.checked) still.click();
          localStorage.removeItem('nm-buddy-spots');
        }, motion);
        await page.evaluate(() => revealTab('dashboard'));
        await page.waitForTimeout(2500);
        const motionNow = await page.evaluate(() => document.documentElement.dataset.motion);
        if (motion === 'app' && motionNow !== 'reduced') fails.push(`app ${size}: the Reduce motion switch did not take (${motionNow})`);
        const put = {
          ledge: () => page.evaluate(() => {
            const l = nameMarkBuddyDrop(300, innerHeight - 45);
            nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), l, true);
            return true;
          }),
          'bottom left': () => page.evaluate(() => {
            nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'air', pose: 'float', x: 4, y: innerHeight - 130 }, true);
            return true;
          }),
          //: INBOX 430 (the owner's screenshot: the menu at the window's top
          //: left, the companion at the bottom right on the Dashboard).
          'bottom right': () => page.evaluate(() => {
            nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'air', pose: 'float', x: innerWidth - 80, y: innerHeight - 130 }, true);
            return true;
          }),
          //: Where it goes by itself since round 7 (a panel of the page, which
          //: it rides): placed by its own choice, then the page scrolled.
          'its own perch, page scrolled': async () => {
            await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); nmb.placeTimer = 0; nmb.placedAt = 0; placeNameMarkBuddy(document.getElementById('nm-buddy'), true); });
            await page.waitForTimeout(1500);
            return page.evaluate(() => { const pg = document.getElementById('tab-dashboard'); pg.scrollTop += 120; return true; });
          },
          'riding a low panel, scrolled': () => page.evaluate(() => {
            const pg = document.getElementById('tab-dashboard');
            pg.scrollTop = pg.scrollHeight;
            const panels = [...pg.querySelectorAll('.card, .dash-widget')].filter((el) => {
              const r = el.getBoundingClientRect();
              return r.width > 200 && r.top > innerHeight * 0.45 && r.top < innerHeight - 80;
            });
            const panel = panels[panels.length - 1];
            if (!panel) return false;
            const r = panel.getBoundingClientRect();
            const l = nameMarkBuddyDrop(Math.round(r.left + 100), Math.round(r.top - 60));
            nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), l, true);
            pg.scrollTop -= 40;
            return Boolean(nmb.ride);
          }),
        };
        for (const [where, go] of Object.entries(put)) {
          for (const how of ['right-click', 'keyboard']) {
            await page.keyboard.press('Escape');
            await page.waitForTimeout(80);
            const placed = await go();
            await page.evaluate(() => { clearTimeout(nmb.timer); clearTimeout(nmb.placeTimer); nmb.placeTimer = 1; });
            if (!placed) { fails.push(`${motion} ${size} ${where}: could not be placed`); break; }
            await page.waitForTimeout(350);
            const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height * 0.45]; });
            if (how === 'right-click') await page.mouse.click(face[0], face[1], { button: 'right' });
            else { await page.focus('#nm-buddy .nm-buddy-face'); await page.keyboard.press('Shift+F10'); }
            await page.waitForTimeout(350);
            count += 1;
            const m = await page.evaluate(() => {
              const f = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect();
              const menu = nmb.menu && nmb.menu.isConnected && !nmb.menu.classList.contains('hidden') ? nmb.menu.getBoundingClientRect() : null;
              return { W: innerWidth, H: innerHeight, face: [f.left, f.top, f.right, f.bottom].map(Math.round), menu: menu ? [menu.left, menu.top, menu.right, menu.bottom].map(Math.round) : null };
            });
            const tag = `${motion} ${size} ${where} by ${how}`;
            if (!m.menu) { fails.push(`${tag}: no menu`); continue; }
            const [ml, mt, mr, mb] = m.menu;
            const [fl, ft, fr, fb] = m.face;
            const gap = Math.max(ml > fr ? ml - fr : fl > mr ? fl - mr : 0, mt > fb ? mt - fb : ft > mb ? ft - mb : 0);
            const inside = ml >= 7 && mt >= 7 && mr <= m.W - 7 && mb <= m.H - 7;
            const line = `${tag}: menu ${m.menu} face ${m.face} gap ${gap}`;
            console.log(`${gap <= 8 && inside ? 'ok  ' : 'FAIL'} ${line}`);
            if (gap > 8 || !inside) fails.push(line);
          }
        }
      } finally {
        //: The switch is kept with the notebook, so it is put back.
        if (motion === 'app') {
          await page.evaluate(() => {
            const still = document.getElementById('reduce-motion-toggle');
            if (!still) return;
            still.checked = false;
            still.dispatchEvent(new Event('change', { bubbles: true }));
          }).catch(() => null);
          await page.waitForTimeout(500);
        }
        await browser.close();
      }
    }
  }
  for (const f of fails) console.log('  miss: ' + f);
  console.log(`${count} menus opened, ${fails.length ? `FAIL ${fails.length}` : 'PASS'}`);
  process.exitCode = fails.length ? 1 : 0;
})();
