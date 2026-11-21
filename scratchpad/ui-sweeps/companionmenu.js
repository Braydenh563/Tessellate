// INBOX 426 x (84.png): "the right-click menu still opens away from it or
// off screen". The companion is put at each corner, the edges and the
// middle of the window, at several window sizes and scales, riding a scroll
// area and not, and its menu is opened by a right-click and from the
// keyboard (Shift+F10). Each time: the menu's box against the window (8px
// margin) and against the companion (beside it, 12px at most away, its top
// level with the companion's unless the window's edge moves it).
// Env: KIND (atlas), THEME. Exits 1 on a menu outside the window or away
// from the companion.
const { boot } = require('./lib.js');
const SIZES = (process.env.SIZES || '1440x900@1,1024x700@1.25,800x600@1.5,390x844@3').split(',');
(async () => {
  const fails = [];
  let count = 0;
  for (const size of SIZES) {
    const [wh, dpr] = size.split('@');
    const [w, h] = wh.split('x').map(Number);
    const { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: Number(dpr || 1), ...(w < 600 ? { isMobile: true, hasTouch: true } : {}) });
    await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'atlas');
    await page.evaluate(() => revealTab('dashboard'));
    await page.waitForTimeout(3000);
    const spots = await page.evaluate(() => {
      const W = innerWidth; const H = innerHeight;
      return [[4, 60], [W - 68, 60], [4, H - 130], [W - 68, H - 130], [Math.round(W / 2 - 32), Math.round(H / 2 - 46)], [W - 68, Math.round(H / 2)], [Math.round(W / 2), H - 130]];
    });
    for (const [x, y] of spots) {
      for (const how of ['right-click', 'keyboard']) {
        count += 1;
        await page.keyboard.press('Escape');
        await page.evaluate(([px, py]) => {
          const buddy = document.getElementById('nm-buddy');
          nameMarkBuddyMoveTo(buddy, { kind: 'air', pose: 'float', x: px, y: py }, true);
          clearTimeout(nmb.timer);
          clearTimeout(nmb.placeTimer);
          nmb.placeTimer = 1;
        }, [x, y]);
        await page.waitForTimeout(120);
        const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
        if (how === 'right-click') await page.mouse.click(face.x, face.y, { button: 'right' });
        else { await page.focus('#nm-buddy .nm-buddy-face'); await page.keyboard.press('Shift+F10'); }
        await page.waitForTimeout(260);
        const m = await page.evaluate(() => {
          const f = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect();
          const menu = nmb.menu && nmb.menu.isConnected && !nmb.menu.classList.contains('hidden') ? nmb.menu.getBoundingClientRect() : null;
          return { W: innerWidth, H: innerHeight, face: [f.left, f.top, f.right, f.bottom].map(Math.round), menu: menu ? [menu.left, menu.top, menu.right, menu.bottom].map(Math.round) : null, focusIn: !!(nmb.menu && nmb.menu.contains(document.activeElement)) };
        });
        const tag = `${size} at ${x},${y} by ${how}`;
        if (!m.menu) { fails.push(`${tag}: no menu`); continue; }
        const [ml, mt, mr, mb] = m.menu;
        const [fl, ft, fr, fb] = m.face;
        const inside = ml >= 7 && mt >= 7 && mr <= m.W - 7 && mb <= m.H - 7;
        const gapX = ml >= fr ? ml - fr : fl >= mr ? fl - mr : 0;
        const gapY = mt >= fb ? mt - fb : ft >= mb ? ft - mb : 0;
        // Beside it (or, where the window is too narrow for beside, over or
        // under it), never further than 12px from its box.
        const near = Math.max(gapX, gapY) <= 12;
        if (!inside || !near) fails.push(`${tag}: menu ${m.menu} face ${m.face} window ${m.W}x${m.H} gap ${gapX},${gapY}`);
        if (how === 'keyboard' && !m.focusIn) fails.push(`${tag}: focus not in the menu`);
      }
    }
    // With its menu open, everything that moves it on its own is asked to
    // (a behaviour, an errand, its beat, a check, leaving an edge): the
    // companion stays where it was and the menu stays at it (84.png).
    if (w >= 1000) {
      await page.keyboard.press('Escape');
      await page.evaluate(() => {
        const buddy = document.getElementById('nm-buddy');
        nameMarkBuddyMoveTo(buddy, { kind: 'air', pose: 'float', x: innerWidth - 90, y: 70 }, true);
        nmb.placeTimer = 0;
        nmb.placedAt = 0;
      });
      await page.waitForTimeout(150);
      const face0 = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + 20, r.top + 30]; });
      await page.mouse.click(face0[0], face0[1], { button: 'right' });
      await page.waitForTimeout(250);
      const held = await page.evaluate(async () => {
        const before = [nmb.x, nmb.y];
        if (typeof nmb.inner.nameMarkBuddyBellErrand === "function") nmb.inner.nameMarkBuddyBellErrand();
        nmb.lastInput = Date.now();
        nmb.tick();
        nmb.inner.nameMarkBuddyBeat();
        nmb.inner.nameMarkBuddyCheck();
        await new Promise((r) => setTimeout(r, 2500));
        const f = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect();
        const m = nmb.menu && !nmb.menu.classList.contains('hidden') ? nmb.menu.getBoundingClientRect() : null;
        return { before, after: [nmb.x, nmb.y], face: [f.left, f.top, f.right, f.bottom].map(Math.round), menu: m ? [m.left, m.top, m.right, m.bottom].map(Math.round) : null };
      });
      count += 1;
      const moved = Math.hypot(held.after[0] - held.before[0], held.after[1] - held.before[1]);
      // The gap between the two boxes (0 when they overlap, as a menu
      // opened at the pointer does).
      const gap = held.menu ? Math.max(held.menu[0] > held.face[2] ? held.menu[0] - held.face[2] : held.face[0] > held.menu[2] ? held.face[0] - held.menu[2] : 0, held.menu[1] > held.face[3] ? held.menu[1] - held.face[3] : held.face[1] > held.menu[3] ? held.face[1] - held.menu[3] : 0) : Infinity;
      if (moved > 2 || gap > 24) fails.push(`${size} menu open: moved ${moved.toFixed(0)}px, menu ${held.menu} face ${held.face}`);
    }
    await browser.close();
  }
  // The owner's conditions for 84.png (round 4): 1.25 and 1.5 scale, dark,
  // the dashboard scrolled, the companion riding a panel's scroll (inside
  // its clipped, fixed band), and every way in: a right-click on its middle
  // and on a picture inside its drawing, a right-click mid-walk and
  // mid-poof, Shift+F10, and a touch long-press. The menu must be within
  // 24px of the companion's box and inside the window.
  const HARD = (process.env.HARD_SIZES || '1440x900@1.25,1280x800@1.5').split(',');
  for (const size of HARD) {
    const [wh, dpr] = size.split('@');
    const [w, h] = wh.split('x').map(Number);
    const { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: Number(dpr), hasTouch: true });
    await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'atlas');
    await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); document.documentElement.dataset.theme = 'dark'; });
    await page.evaluate(() => revealTab('dashboard'));
    await page.waitForTimeout(3000);
    const cdp = await page.context().newCDPSession(page);
    await page.evaluate(() => {
      window.__menuCloses = [];
      const orig = window.closeActionMenus;
      window.closeActionMenus = function (...a) {
        window.__menuCloses.push(`${Math.round(performance.now())} ${new Error().stack.split('\n').slice(2, 4).map((l) => l.trim().split(' ')[1]).join('<')}`);
        if (window.__menuCloses.length > 6) window.__menuCloses.shift();
        return orig.apply(this, a);
      };
    });
    // On a dashboard panel that scrolls, the page scrolled a little.
    const ride = async () => page.evaluate(() => {
      const page = document.getElementById('tab-dashboard');
      page.scrollTop = 0;
      const panel = [...page.querySelectorAll('.card, .dash-widget, .dash-quicklinks')].find((el) => { const r = el.getBoundingClientRect(); return r.width > 250 && r.top > 250 && r.top < innerHeight - 250; });
      if (!panel) return { riding: false };
      const r = panel.getBoundingClientRect();
      nameMarkBuddyIndexReset();
      const landed = nameMarkBuddyDrop(Math.round(r.left + 140), Math.round(r.top - 80));
      nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), landed, true);
      page.scrollTop = 60;
      clearTimeout(nmb.timer);
      nmb.placeTimer = 1;
      return { riding: !!nmb.ride };
    });
    const measure = async (tag) => {
      await page.waitForTimeout(280);
      const m = await page.evaluate(() => {
        const f = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect();
        const menu = nmb.menu && nmb.menu.isConnected && !nmb.menu.classList.contains('hidden') ? nmb.menu.getBoundingClientRect() : null;
        return { W: innerWidth, H: innerHeight, face: [f.left, f.top, f.right, f.bottom].map(Math.round), menu: menu ? [menu.left, menu.top, menu.right, menu.bottom].map(Math.round) : null };
      });
      count += 1;
      if (!m.menu) { fails.push(`${size} ${tag}: no menu; closed by ${await page.evaluate(() => JSON.stringify(window.__menuCloses || []))}`); return; }
      const [ml, mt, mr, mb] = m.menu;
      const [fl, ft, fr, fb] = m.face;
      const gap = Math.max(ml > fr ? ml - fr : fl > mr ? fl - mr : 0, mt > fb ? mt - fb : ft > mb ? ft - mb : 0);
      const inside = ml >= 0 && mt >= 0 && mr <= m.W && mb <= m.H;
      if (gap > 24 || !inside) fails.push(`${size} ${tag}: menu ${m.menu} face ${m.face} gap ${gap} window ${m.W}x${m.H}`);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(120);
    };
    const faceAt = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height * 0.45]; });
    const riding = await ride();
    if (!riding.riding) fails.push(`${size}: not riding a panel`);
    // Its middle.
    let p = await faceAt();
    await page.mouse.click(p[0], p[1], { button: 'right' });
    await measure('right-click, riding, scrolled');
    // A picture inside its drawing (an img or an svg part).
    p = await page.evaluate(() => {
      const part = [...document.querySelectorAll('#nm-buddy .nm-buddy-char img, #nm-buddy .nm-buddy-char svg *')].map((el) => el.getBoundingClientRect()).find((r) => r.width > 4 && r.height > 4);
      return part ? [part.left + part.width / 2, part.top + part.height / 2] : null;
    });
    if (p) {
      await page.mouse.click(p[0], p[1], { button: 'right' });
      await measure('right-click on a part of its drawing');
    }
    // Mid-walk and mid-poof: set going, then right-clicked where it is.
    for (const [tag, dx, dy] of [['mid-walk', -260, 0], ['mid-poof', -700, 200]]) {
      await ride();
      await page.evaluate(([ddx, ddy]) => { nmb.placeTimer = 0; nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'air', pose: 'float', x: nmb.x + ddx, y: nmb.y + ddy }, false); }, [dx, dy]);
      await page.waitForTimeout(tag === 'mid-walk' ? 180 : 60);
      p = await faceAt();
      await page.mouse.click(p[0], p[1], { button: 'right' });
      await measure(`right-click ${tag}`);
    }
    // The keyboard.
    await ride();
    await page.focus('#nm-buddy .nm-buddy-face');
    await page.keyboard.press('Shift+F10');
    await measure('Shift+F10, riding');
    // A touch long-press.
    await ride();
    p = await faceAt();
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: p[0], y: p[1] }] });
    await page.waitForTimeout(750);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await measure('long-press');
    await browser.close();
  }
  console.log(`${count} menus opened`);
  for (const f of fails) console.log(f);
  console.log(fails.length ? `FAIL ${fails.length}` : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
