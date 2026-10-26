// The whiteboard and the mind map on a phone: UI_MODERNISATION_PLAN.md
// Phase 11 item 7, "view and light edit only on a phone (pan, zoom, select,
// move, edit text); creation tools in a sheet; the mind map's + handles are
// touch-sized".
//
// Its own browser context rather than `lib.js`'s, and that is not a
// preference: `lib.js` passes only the viewport to `newContext`, so a sweep
// that asks it for `hasTouch` gets a desktop context at a phone's width, and
// half of this band's rules are behind `(pointer: coarse)`.
//
//   BASE=http://127.0.0.1:8971 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules node scratchpad/ui-sweeps/wbphone.js
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);

const findings = [];
const check = (ok, what) => { if (!ok) findings.push(what); return ok; };

async function touch(cdp, type, points) {
  await cdp.send('Input.dispatchTouchEvent', {
    type,
    touchPoints: points.map((p, i) => ({ x: p.x, y: p.y, id: i })),
  });
}

// A fresh data dir shows two first-run prompts after unlock: the recovery-key
// dialog, and the update-check confirm ("Don't check"). Both sit over the
// tabs, so each is answered the way a person would before the sweep starts.
async function dismissRecovery(page) {
  await page.evaluate(() => {
    const d = document.getElementById('recovery-key-dialog');
    if (d && d.open) d.close();
    for (const b of document.querySelectorAll('.confirm-overlay:not(.hidden) button')) {
      if (b.textContent.trim() === "Don't check") { b.click(); break; }
    }
  });
  await page.waitForTimeout(300);
}

async function newBoard(page, name, type) {
  await dismissRecovery(page);
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(600);
  // On a phone an open board hides the Library's sub-tabs (INBOX 392); its
  // own "Boards" is the way back to them, as it is for a person.
  if (await page.isVisible('#wb-back-to-boards')) {
    await page.click('#wb-back-to-boards');
    await page.waitForTimeout(600);
  }
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(800);
  // `wb-boards-new` is now "Whiteboard", which makes an empty board at once
  // with no dialog. The template dialog is the menu's "From a template" row.
  // The library's scripts load lazily and bind this button when they arrive,
  // so a click that lands before that does nothing (seen on 1 run in ~5).
  // Click until the gallery opens, rather than sleep for a fixed time.
  for (let attempt = 0; attempt < 5; attempt++) {
    await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
    try {
      await page.waitForSelector('#wb-template-dialog[open]', { timeout: 4000 });
      break;
    } catch (e) {
      if (attempt === 4) throw e;
    }
  }
  await dismissRecovery(page);
  await page.fill('#wb-template-name', name);
  if (type === 'map') await page.click('#wb-template-kind button[data-value="map"]');
  await page.click('#wb-template-create');
  await page.waitForTimeout(2800);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 2,
  });
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light');
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
    } catch (e) {}
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden'));
  await dismissRecovery(page);
  const cdp = await ctx.newCDPSession(page);

  await newBoard(page, 'Phone board ' + Date.now(), 'board');

  // --- the shape of the board at 390 ----------------------------------------
  const shape = await page.evaluate(() => {
    const r = (el) => {
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)];
    };
    const canvas = document.getElementById('whiteboard-container');
    const rail = document.getElementById('wb-tools-panel');
    const cb = canvas.getBoundingClientRect();
    const rb = rail ? rail.getBoundingClientRect() : null;
    const over = rb
      ? Math.max(0, Math.min(rb.right, cb.right) - Math.max(rb.left, cb.left))
        * Math.max(0, Math.min(rb.bottom, cb.bottom) - Math.max(rb.top, cb.top))
      : 0;
    const visible = (el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true });
    const tools = rail ? [...rail.querySelectorAll('button')].filter(visible) : [];
    const small = tools
      .filter((el) => { const b = el.getBoundingClientRect(); return b.width + 0.5 < 44 || b.height + 0.5 < 44; })
      .map((el) => `${el.dataset.tool || el.id || el.className.split(' ')[0]} ${Math.round(el.getBoundingClientRect().width)}x${Math.round(el.getBoundingClientRect().height)}`);
    return {
      canvas: r(canvas),
      rail: r(rail),
      railCoverPct: cb.width * cb.height ? Math.round((over / (cb.width * cb.height)) * 100) : 0,
      groupHidden: !visible(document.getElementById('wb-tool-group')),
      tools: tools.length,
      smallTools: small.length,
      smallSample: small.slice(0, 5),
      topbar: r(document.getElementById('wb-topbar')),
      sheetOpener: Boolean(document.getElementById('wb-tools-opener')),
      pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  console.log('board at ' + WIDTH + '   ', JSON.stringify(shape));
  check(shape.pageOverflow <= 0, `the page scrolls ${shape.pageOverflow}px sideways at ${WIDTH}`);
  check(shape.groupHidden, 'the 31-button tool group is still on the board at phone width');
  check(shape.rail[3] <= 60, `the tools panel is ${shape.rail[3]}px tall`);
  check(shape.sheetOpener, 'there is no opener for the tools sheet');

  // --- two fingers navigate, whatever the tool is ---------------------------
  const before = await page.evaluate(() => {
    const t = d3.zoomTransform(d3.select('#whiteboard-container').node());
    return { k: +t.k.toFixed(4), x: +t.x.toFixed(1), y: +t.y.toFixed(1), tool: window.currentTool };
  });
  const cx = shape.canvas[0] + shape.canvas[2] / 2;
  const cy = shape.canvas[1] + shape.canvas[3] / 2;
  let gap = 40;
  await touch(cdp, 'touchStart', [{ x: cx - gap, y: cy }, { x: cx + gap, y: cy }]);
  for (let step = 1; step <= 10; step++) {
    gap = 40 + step * 10;
    await touch(cdp, 'touchMove', [{ x: cx - gap, y: cy }, { x: cx + gap, y: cy }]);
    await page.waitForTimeout(20);
  }
  await touch(cdp, 'touchEnd', []);
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => {
    const t = d3.zoomTransform(d3.select('#whiteboard-container').node());
    return { k: +t.k.toFixed(4), x: +t.x.toFixed(1), y: +t.y.toFixed(1) };
  });
  const ratio = after.k / before.k;
  console.log('two-finger pinch', JSON.stringify({ before, after, ratio: +ratio.toFixed(3) }));
  check(ratio > 1.3, `a pinch from 80px to 280px with the ${before.tool} tool scaled the board by ${ratio.toFixed(3)}`);

  // --- the tools sheet ------------------------------------------------------
  if (shape.sheetOpener) {
    await page.click('#wb-tools-opener');
    await page.waitForTimeout(600);
    const sheet = await page.evaluate(() => {
      const overlay = document.querySelector('.sheet-overlay[data-sheet="wb-tools"]');
      if (!overlay) return null;
      const card = overlay.querySelector('.sheet-card');
      const r = card.getBoundingClientRect();
      // Only what is on screen: the shape menu's own rows are inside a
      // closed docked menu and measure 0x0, and a control nobody can see is
      // not a target anybody can miss (`phone.js`'s own exclusion).
      const vis = (el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && el.getBoundingClientRect().width > 0;
      const buttons = [...card.querySelectorAll('button[data-tool]')].filter(vis);
      const small = buttons
        .filter((el) => { const b = el.getBoundingClientRect(); return b.width + 0.5 < 44 || b.height + 0.5 < 44; })
        .map((el) => `${el.dataset.tool} ${Math.round(el.getBoundingClientRect().width)}x${Math.round(el.getBoundingClientRect().height)}`);
      // dog3 item 18: stacked sections share one left edge and draw no row divider.
      const lefts = [...card.querySelectorAll('.wb-tool-section')].filter(vis).map((el) => Math.round(el.getBoundingClientRect().left));
      const rules = [...card.querySelectorAll('.wb-tool-section')].filter((el) => parseFloat(getComputedStyle(el).borderLeftWidth) > 0).length;
      const opener = document.getElementById('wb-tools-opener').textContent.trim();
      return { rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], tools: buttons.length, small, lefts, rules, opener };
    });
    console.log('tools sheet     ', JSON.stringify(sheet));
    check(Boolean(sheet), 'the tools opener opened no sheet');
    if (sheet) {
      check(sheet.tools >= 10, `the sheet holds ${sheet.tools} tools`);
      check(!sheet.small.length, 'tools under 44px in the sheet: ' + sheet.small.join(', '));
      check(new Set(sheet.lefts).size === 1, 'the sheet sections start at different x: ' + sheet.lefts.join(','));
      check(sheet.rules === 0, `${sheet.rules} sections draw a row divider in the stacked sheet`);
      check(!/\(/.test(sheet.opener), `the opener shows a key hint: ${sheet.opener}`);
      // Picking a tool closes the sheet and selects it.
      await page.evaluate(() => {
        const vis = (el) => el.checkVisibility && el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && el.getBoundingClientRect().width > 0;
        const pick = [...document.querySelectorAll('.sheet-overlay[data-sheet="wb-tools"] button[data-tool]')]
          .filter(vis)
          .find((b) => b.dataset.tool !== window.currentTool);
        window.__picked = pick?.dataset.tool;
        pick?.click();
      });
      await page.waitForTimeout(500);
      const picked = await page.evaluate(() => ({
        tool: window.currentTool,
        open: Boolean(document.querySelector('.sheet-overlay[data-sheet="wb-tools"]')),
      }));
      console.log('picked a tool   ', JSON.stringify(picked));
      const wanted = await page.evaluate(() => window.__picked);
      check(picked.tool === wanted, `picking ${wanted} left the tool as ${picked.tool}`);
      check(!picked.open, 'the sheet stayed open after a tool was picked');
      await page.evaluate(() => wbSelectToolRef('select'));
      await page.waitForTimeout(300);
    }
  }

  // --- the mind map's handles ----------------------------------------------
  await newBoard(page, 'Phone map ' + Date.now(), 'map');
  // dog3 item 21: the template offer never runs under the selected topic's bar.
  const offer = await page.evaluate(() => {
    const box = (el) => (el && el.offsetParent ? el.getBoundingClientRect() : null);
    const t = box(document.getElementById('wb-map-templates'));
    const bar = box(document.getElementById('wb-map-strip'));
    return t && bar ? Math.round(t.bottom - bar.top) : null;
  });
  console.log('offer vs bar    ', JSON.stringify(offer));
  if (offer !== null) check(offer <= 0, `the template offer runs ${offer}px under the topic's bar`);
  // dog3 item 19: renaming swaps a field for the picker without moving the bar.
  const rename = await page.evaluate(async () => {
    const h = () => Math.round(document.getElementById('wb-topbar').getBoundingClientRect().height);
    const before = h();
    setTimeout(renameCurrentBoard, 0);
    await new Promise((r) => setTimeout(r, 300));
    const during = h();
    document.getElementById('wb-name-field')?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return { before, during };
  });
  console.log('rename bar      ', JSON.stringify(rename));
  check(rename.before === rename.during, `the bar was ${rename.before}px and ${rename.during}px while renaming`);
  // The camera is shared between boards in one visit, and the pinch above
  // left it at 3.5x: a handle measured through it would read 154x154 and say
  // nothing about its size. Reset, then bring the root into the middle of the
  // canvas with the board's own `wbCenterOn`, because a new map's root can
  // sit under the floating top bar, where nothing can tap it.
  await page.evaluate(() => {
    d3.select('#whiteboard-container').call(wbZoom.transform, d3.zoomIdentity);
    const el = document.querySelector('.wb-map-node');
    const id = el ? Number(el.dataset.id) : null;
    const item = (wbState.objects || []).find((o) => o.id === id);
    if (item) wbCenterOn(wbItemBBox('object', item), { animate: false });
  });
  await page.waitForTimeout(600);
  const node = await page.evaluate(() => {
    const el = document.querySelector('.wb-map-node');
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2) };
  });
  check(Boolean(node), 'the new map has no node to press');
  if (node) {
    // A fresh map opens its root for typing, so the tap has to land on a
    // node that is not already an open text box.
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    const at = await page.evaluate(() => {
      const b = document.querySelector('.wb-map-node').getBoundingClientRect();
      return { x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2), top: Math.round(b.top) };
    });
    console.log('map node at     ', JSON.stringify(at));
    await touch(cdp, 'touchStart', [{ x: at.x, y: at.y }]);
    await page.waitForTimeout(80);
    await touch(cdp, 'touchEnd', []);
    await page.waitForTimeout(900);
    const handles = await page.evaluate(() => {
      const el = document.querySelector('.wb-map-node');
      const out = {};
      for (const cls of ['wb-map-add', 'wb-map-ref']) {
        const b = el.querySelector('.' + cls);
        if (!b) continue;
        const r = b.getBoundingClientRect();
        out[cls] = [Math.round(r.width), Math.round(r.height), Math.round(Number(getComputedStyle(b.parentElement).opacity) * 100)];
      }
      out.selected = el.classList.contains('wb-selected');
      return out;
    });
    console.log('map handles     ', JSON.stringify(handles));
    check(handles.selected, 'a tap did not select the map node');
    for (const cls of ['wb-map-add', 'wb-map-ref']) {
      const h = handles[cls];
      if (!h) { findings.push(`no .${cls} on the node`); continue; }
      check(h[0] >= 44 && h[1] >= 44, `.${cls} is ${h[0]}x${h[1]}`);
      check(h[2] > 0, `.${cls} is invisible on a selected node (opacity ${h[2]}%)`);
    }
  }

  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL:\n  ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
