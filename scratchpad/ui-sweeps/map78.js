// Brief 78 (MINDMAP_PLAN 15, rows 1 to 5 and 9): the mind map's trust pass,
// measured. Clicks from the dashboard to a new map with its root in edit,
// Create to the first topic, add a child (three runs each, performance.now in
// the page), overlapping and unnamed controls on a selected topic, the map
// palette's commands with a phone path, and top bar and grip controls with
// no help popover or palette row.
// Usage: BASE=http://127.0.0.1:8828 VW=1440|390 [THEME=dark] node map78.js
const { boot } = require("./lib.js");
const VW = Number(process.env.VW || 1440);
const phone = VW < 600;
const OVERLAPS = `window.__ovl = (root) => {
  const vis = (e) => { if (e.closest('[hidden]')) return false; const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const ctrls = [...root.querySelectorAll('button, select, input, textarea, [role=button], [role=menuitem], [role=tab], a[href]')].filter((c) => !c.closest('.select-menu') && !c.classList.contains('select-opener') && vis(c));
  const rs = ctrls.map((c) => c.getBoundingClientRect());
  const pairs = [];
  for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
    if (ctrls[i].contains(ctrls[j]) || ctrls[j].contains(ctrls[i])) continue;
    const a = rs[i], b = rs[j];
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left), iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    const nm = (c) => (c.getAttribute('aria-label') || c.title || c.textContent).trim().slice(0, 28) || c.className.toString().slice(0, 24);
    const rr = (r) => [r.left, r.top, r.width, r.height].map(Math.round).join(',');
    if (ix > 2 && iy > 2) pairs.push(nm(ctrls[i]) + ' | ' + nm(ctrls[j]) + (window.__RECTS ? ' @' + rr(a) + ' / ' + rr(b) : ''));
  }
  const unnamed = ctrls.filter((c) => !(c.getAttribute('aria-label') || c.textContent.trim() || c.title)).length;
  return { controls: ctrls.length, overlaps: pairs.length, pairs: pairs.slice(0, 8), unnamed };
};`;
const until = (page, cond, ms = 15000) => page.waitForFunction(cond, null, { timeout: ms });
async function landing(page) {
  await page.evaluate(async () => { await switchTab("library"); await ensureModule("library"); document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click(); });
  await page.waitForTimeout(1200);
  await page.evaluate(() => { if (typeof wbShowBoardsLanding === "function") wbShowBoardsLanding(); });
  await page.waitForTimeout(600);
}
// Press New, Mind map; answer the dialog when there is one. Returns ms from
// the press to the first topic painted, and whether the root opened in edit.
async function newMap(page, name) {
  return page.evaluate(async (nm) => {
    const before = window.currentBoardId;
    const t0 = performance.now();
    document.getElementById("wb-boards-new-map").click();
    let answered = false;
    const end = performance.now() + 15000;
    while (performance.now() < end) {
      await new Promise((r) => requestAnimationFrame(r));
      const dlg = document.getElementById("wb-template-create");
      if (!answered && dlg && dlg.offsetParent) { document.getElementById("wb-template-name").value = nm; dlg.click(); answered = true; }
      if (window.currentBoardId && window.currentBoardId !== before && document.querySelector('#whiteboard-container .wb-object .wb-map-text')) {
        const ms = Math.round(performance.now() - t0);
        await new Promise((r) => setTimeout(r, 400));
        const ed = document.activeElement;
        return { ms, dialog: answered, rootInEdit: Boolean(ed && ed.classList.contains('wb-map-text') && ed.isContentEditable), name: (document.querySelector('#whiteboard-container .wb-map-text')?.textContent || '').trim() };
      }
    }
    return { ms: -1, dialog: answered };
  }, name);
}
(async () => {
  const opts = phone ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1440, height: 900 } };
  const { browser, page } = await boot(opts);
  await page.evaluate(OVERLAPS);
  if (process.env.RECTS) await page.evaluate(() => { window.__RECTS = 1; });
  await page.evaluate(() => { const d = document.getElementById("recovery-key-dialog"); if (d && d.open) d.close(); });
  const out = { VW };
  // 1. Clicks from the dashboard (desktop only, as deepen72a counts them).
  if (!phone) {
    await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(600);
    let clicks = 0;
    await page.click('[data-tab="library"]'); clicks++; await page.waitForTimeout(800);
    await page.click('#library-subtabs [data-target="library-view-whiteboard"]'); clicks++; await page.waitForTimeout(1500);
    await page.evaluate(() => { if (typeof wbShowBoardsLanding === "function") wbShowBoardsLanding(); }); await page.waitForTimeout(500);
    await page.click('#wb-boards-new-more'); clicks++;
    await page.waitForTimeout(200);
    const r = await newMap(page, "Clicked map"); clicks++;
    if (r.dialog) clicks += 2; // the kind segment was preset; the name typed and Create pressed
    out.clicks = { clicks, ...r };
    if (r.rootInEdit) {
      await page.keyboard.type("Biology"); await page.keyboard.press("Escape"); await page.waitForTimeout(1200);
      out.clicks.mapTitleAfterTyping = await page.evaluate(async () => (await apiJson(`/whiteboard/boards`)).find((b) => b.id === window.currentBoardId)?.title);
      out.clicks.rootText = await page.evaluate(() => wbMapIndex().roots.map((r) => r.data?.content));
    }
    await page.keyboard.press("Escape"); await page.waitForTimeout(400);
  }
  // 2. Create to first topic, three runs.
  out.create = [];
  for (let i = 0; i < (process.env.FAST ? 1 : 3); i++) { await landing(page); out.create.push(await newMap(page, "Run map " + i)); await page.evaluate(() => document.activeElement?.blur()); await page.waitForTimeout(500); }
  // 3. Add a child, 3 runs of 10.
  out.addChild = [];
  for (let i = 0; i < (process.env.FAST ? 1 : 3); i++) {
    out.addChild.push(await page.evaluate(async () => {
      const root = wbMapIndex().roots[0]; const t = []; const e = [];
      for (let k = 0; k < 10; k++) { const t0 = performance.now(); const p = wbMapAddChild(root.id); e.push(performance.now() - t0); await p; t.push(performance.now() - t0); if (document.activeElement?.isContentEditable) document.activeElement.blur(); }
      t.sort((a, b) => a - b); e.sort((a, b) => a - b);
      // median: the press to the server's id (deepen72a's number); editable: the press to the editor open on the new topic.
      return { median: Math.round(t[5]), max: Math.round(t[9]), editable: Math.round(e[5]), editableMax: Math.round(e[9]) };
    }));
    await page.evaluate(() => document.activeElement?.blur()); await page.waitForTimeout(800);
  }
  // 4. A selected topic: overlaps and names, in the canvas view.
  await page.evaluate(() => wbZoomToFit?.()); await page.waitForTimeout(600);
  const box = await page.evaluate(() => { const els = [...document.querySelectorAll('#whiteboard-container .wb-object')].filter((e) => e.querySelector('.wb-map-text')); const e = els[Math.min(2, els.length - 1)]; const r = e.querySelector('.wb-map-text').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  if (phone) await page.touchscreen.tap(box.x, box.y); else await page.mouse.click(box.x, box.y);
  await page.waitForTimeout(700);
  out.selected = await page.evaluate(() => Boolean(wbSelectedMapNode()));
  out.view = await page.evaluate(() => __ovl(document.getElementById('library-view-whiteboard')));
  out.topic = await page.evaluate(() => { const s = document.querySelector('#whiteboard-container .wb-object.selected, #whiteboard-container .wb-object.wb-selected') || document.querySelector('#whiteboard-container .wb-object'); return __ovl(s); });
  // 5. Map palette commands with a phone path (or, at 1440, a visible path).
  out.phonePath = await page.evaluate(async () => {
    const cmds = mapPaletteCommands();
    const strip = (l) => l.replace(/^ph:[\w-]+\s+/, '').replace(/…$/, '').replace(/\s*\(.*\)\s*$/, '').trim().toLowerCase();
    const toggle = document.getElementById('wb-more-toggle');
    if (toggle) { toggle.click(); await new Promise((r) => setTimeout(r, 300)); }
    const vis = (e) => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]');
    const labels = new Set();
    for (const e of document.querySelectorAll('#wb-topbar button, #wb-topbar [role=menuitem], .wb-board-menu [role=menuitem], .wb-board-menu button, #wb-more-menu .menu-item, .sheet .menu-item')) {
      if (!vis(e) && !e.closest('.wb-board-menu')) continue;
      for (const s of [e.getAttribute('aria-label'), e.title, e.textContent]) if (s) labels.add(strip(s));
    }
    const miss = cmds.filter((c) => !labels.has(strip(c.label)));
    // One row pressed from the sheet: Number the topics.
    const before = Boolean(window.wbMapState?.numbered);
    const row = [...document.querySelectorAll('#wb-more-menu .menu-item')].find((e) => /Number the topics|Stop numbering/.test(e.textContent));
    if (row) { row.click(); await new Promise((r) => setTimeout(r, 1200)); }
    const pressed = { found: Boolean(row), toggled: Boolean(window.wbMapState?.numbered) !== before };
    if (pressed.toggled) { await wbMapSetNumbered(before); }
    const sheetRows = document.querySelectorAll('#wb-more-menu .menu-item:not([hidden])').length;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    if (typeof closeActionMenus === 'function') closeActionMenus();
    if (typeof closeSheet === 'function') try { closeSheet(); } catch (e) {}
    return { pressed, sheetRows, commands: cmds.length, withPath: cmds.length - miss.length, missing: miss.slice(0, 40).map((c) => strip(c.label)) };
  });
  // 9. Top bar and grip controls: named in the board help's '?' popover
  // (#wb-help-about, by the control's own name), and a palette row (a menu's
  // opener counts when every row of its menu has one).
  await page.evaluate(() => { const t = wbMapIndex().nodes.find((n) => n.parent_id != null); if (t) selectWbItem("object", t.id); });
  await page.waitForTimeout(500);
  out.help = await page.evaluate(() => {
    const vis = (e) => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
    const sel = document.querySelector('#whiteboard-container .wb-map-node.wb-selected') || document.querySelector('#whiteboard-container .wb-object.wb-selected');
    const ctrls = [...document.querySelectorAll('#wb-topbar button'), ...(sel ? sel.querySelectorAll('button') : [])].filter(vis).filter((b) => !b.closest('.action-menu, .wb-board-menu'));
    const norm = (t) => String(t || '').replace(/\s*\(.*\)\s*$/, '').split(':')[0].replace(/…$/, '').trim().toLowerCase();
    const pal = (typeof paletteCommands === 'function' ? paletteCommands() : []).concat(mapPaletteCommands()).map((c) => c.label.replace(/^ph:[\w-]+\s+/, '').replace(/…$/, '').trim().toLowerCase());
    const about = (document.getElementById('wb-help-about')?.textContent || '').replace(/\s+/g, ' ').toLowerCase();
    const named = (b) => (b.getAttribute('aria-label') || b.title || b.textContent).trim();
    const inPal = (n) => n && pal.some((l) => l === n || l.includes(n) || n.includes(l));
    const noHelp = ctrls.filter((b) => !about.includes(norm(named(b))));
    const noPal = [];
    for (const b of ctrls) {
      const menu = b.getAttribute('aria-haspopup') && b.getAttribute('aria-controls') && document.getElementById(b.getAttribute('aria-controls'));
      if (b.classList.contains('kebab-opener')) {
        const rows = [...document.querySelectorAll('#wb-more-menu .menu-item')];
        const miss = rows.filter((r) => !r.dataset.wbCmd && !r.classList.contains('wb-more-map'));
        if (miss.length) noPal.push(named(b) + ' > ' + miss.length + ' rows');
      } else if (menu && menu.classList.contains('wb-board-menu')) {
        const rows = [...menu.querySelectorAll('button')].filter((r) => !r.hidden && !r.closest('[hidden]') && !r.classList.contains('select-opener') && named(r));
        const word = (r) => { const c = r.cloneNode(true); c.querySelectorAll('kbd, .dock-menu-item-hint').forEach((k) => k.remove()); return c.textContent.trim(); };
        const miss = rows.filter((r) => !r.dataset.wbCmd && !inPal(norm(word(r))) && !inPal(norm(named(r))));
        if (miss.length) noPal.push(named(b) + ' > ' + miss.slice(0, 8).map(word).join(' / '));
      } else if (!inPal(norm(named(b)))) noPal.push(named(b));
    }
    return { controls: ctrls.length, noHelp: noHelp.length, noHelpList: noHelp.slice(0, 12).map(named), noPalette: noPal.length, noPaletteList: noPal.slice(0, 20) };
  });
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
