// L-world-class-13: the five whiteboard top-bar menus (Insert, Edit, Arrange, View, Board) at 1440 and 390: open, on top, in the window, no clipped text, touch heights, labels, Escape closes and returns focus. Waits for initWhiteboard (wb1005-lib openBoard).
//   BASE=http://127.0.0.1:8801 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbmenus5.js
const { openBoard, checker } = require('./wb1005-lib.js');
const { check, summary } = checker();
const MENUS = ['wb-insert-menu', 'wb-edit-menu', 'wb-arrange-menu', 'wb-view-menu', 'wb-board-menu'];
(async () => {
  for (const [W, H] of [[1440, 900], [390, 844]]) {
    const phone = W < 600;
    const { browser, page, errors } = await openBoard({ viewport: { width: W, height: H }, boot: phone ? { hasTouch: true, isMobile: true } : {} });
    for (const id of MENUS) {
      const tag = `${W} ${id}`;
      const toggle = `[aria-controls="${id}"]`;
      const vis = await page.evaluate((t) => { const e = document.querySelector(t); if (!e) return 'missing'; const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 ? 'shown' : 'hidden'; }, toggle);
      if (vis !== 'shown') { console.log(`SKIP  ${tag} toggle ${vis}`); continue; }
      await page.click(toggle).catch((e) => console.log('click fail', tag, e.message.split('\n')[0]));
      await page.waitForTimeout(450);
      const m = await page.evaluate(([id, t]) => {
        const menu = document.getElementById(id); const tg = document.querySelector(t);
        const r = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), r: Math.round(b.right), b: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height) }; };
        const open = !menu.classList.contains('hidden') && menu.getBoundingClientRect().width > 0;
        const items = [...menu.querySelectorAll('button, [role=menuitem], [role=menuitemcheckbox]')].filter((e) => e.getClientRects().length);
        const clipped = items.filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => (e.textContent || '').trim().slice(0, 24));
        const small = items.filter((e) => { const b = e.getBoundingClientRect(); return b.height < (matchMedia('(pointer: coarse)').matches ? 40 : 24); }).map((e) => (e.id || e.className || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height) + ' ' + (e.title || e.getAttribute('aria-label') || '').slice(0, 30));
        const mb = menu.getBoundingClientRect(); const cx = mb.x + mb.width / 2, cy = Math.min(mb.y + 20, innerHeight - 2);
        const top = document.elementFromPoint(cx, cy);
        return { open, expanded: tg.getAttribute('aria-expanded'), menu: r(menu), n: items.length, clipped, small, covered: !!top && !menu.contains(top), inView: mb.x >= -1 && mb.right <= innerWidth + 1 && mb.y >= -1 && mb.bottom <= innerHeight + 1, scrolls: menu.scrollHeight > menu.clientHeight + 1, hasRole: menu.getAttribute('role'), unlabeled: items.filter((e) => !(e.textContent || '').trim() && !e.getAttribute('aria-label') && !e.title).length };
      }, [id, toggle]);
      console.log(tag, JSON.stringify(m));
      check(`${tag} opens, aria-expanded true`, m.open && m.expanded === 'true', { open: m.open, exp: m.expanded });
      check(`${tag} on top at its middle`, !m.covered);
      check(`${tag} inside window or scrolls`, m.inView || m.scrolls, m.menu);
      check(`${tag} no clipped item text`, m.clipped.length === 0, m.clipped);
      check(`${tag} item heights`, m.small.length === 0, m.small);
      check(`${tag} items labelled`, m.unlabeled === 0, m.unlabeled);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
      const after = await page.evaluate(([id, t]) => ({ closed: document.getElementById(id).classList.contains('hidden'), exp: document.querySelector(t).getAttribute('aria-expanded'), focus: document.activeElement === document.querySelector(t) }), [id, toggle]);
      check(`${tag} Escape closes`, after.closed && after.exp === 'false', after);
      check(`${tag} Escape returns focus to the button`, after.focus, after);
    }
    check(`${W} no page errors`, errors.length === 0, errors.slice(0, 3));
    await browser.close();
  }
  summary();
})();
