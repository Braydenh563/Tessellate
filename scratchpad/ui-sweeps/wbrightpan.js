// INBOX 258: a right-drag pans the board, and does not eat a right-click
// that means something. As numbers.
//
//   BASE=http://127.0.0.1:8781 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node wbrightpan.js
//
// **Built (C03, 2026-10-18)** as the decision below: the native menu on bare
// canvas is swallowed and the app's own menu opens on release when the press
// stayed inside 4px. Menus are counted as visible `.pointer-menu-host` menus.
// Original header follows.
//
// It has been built and taken back out twice now, 2026-09-19 and 2026-09-20,
// and the second attempt found why. The pan half is four lines in
// `wbZoomFilter` and measures clean at 150px both times. The other half, not
// leaving a context menu open where somebody just finished panning, is not
// implementable as this file's second assertion is written, and that is a
// fact about the browser rather than about the code:
//
//     pointerdown@wb-svg-layer
//     mousedown@wb-svg-layer
//     contextmenu@wb-svg-layer      <- here, on the press
//     pointerup@wb-svg-layer
//     mouseup@wb-svg-layer
//     auxclick@wb-svg-layer
//
// **`contextmenu` is dispatched on the press, before the drag has moved a
// pixel**, so at the moment the decision has to be made nothing can know
// whether this gesture is going to become a drag or stay a click. "Suppress
// the menu only when the drag moved" cannot be written. (The 2026-09-19 note
// recorded the opposite, that the menu arrives at the end and at the
// `<section>` around the board; measured again on 2026-09-20 it arrives
// first, at `#wb-svg-layer`. Two runs that session disagreed about whether it
// arrived at all; six runs across two attempts this session agreed every
// time, so the earlier non-determinism is not reproducing and should not be
// planned around.)
//
// That leaves one shape that works, and it is a decision rather than a patch:
// suppress the native menu on the canvas outright and open the app's own
// pointer menu (`openMenuAtPoint`) in its place, so a right-click gives board
// actions and a right-drag gives a pan. What goes in that menu is a design
// question nobody has answered, which is why INBOX 258 is still an entry.
//
// Whoever builds it: make this file pass, on a board that has at least one
// card, and expect to change assertion 2 with the owner's agreement.
//
// Three things have to hold at once, and the second and third are why this
// was an INBOX entry rather than a patch. A right-drag on empty canvas pans,
// and the context menu that would open on its release does not. A right
// *click* on empty canvas, with no drag, still opens whatever it opened
// before. And a right-press on a card is not a pan at all, because that is
// where the board's own menus live.
const { boot } = require('./lib.js');

(async () => {
  const { page, browser } = await boot({});
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(800);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForTimeout(1500);
  const box = await page.evaluate(async () => {
    const view = document.getElementById('library-view-whiteboard');
    if (!view.offsetParent) {
      for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle('hidden', s !== view);
    }
    await initWhiteboard();
    wbShowCanvasView();
    await fetchWhiteboardState();
    await new Promise((r) => setTimeout(r, 400));
    // Check 3 needs a card to press, and a board that has none would report
    // it as "skipped", which is the case this test exists to cover.
    if (!document.querySelector('#whiteboard-container .node-card')) {
      const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'right-pan probe card', category: 'General' }) });
      const n = await apiJson('/whiteboard/nodes', { method: 'POST', body: JSON.stringify({ entry_id: e.id, board_id: window.currentBoardId ?? null, x: 90, y: 90, z: 1 }) });
      wbState.nodes.push(n);
      renderWhiteboardNow();
      await new Promise((r) => setTimeout(r, 500));
    }
    const container = document.getElementById('whiteboard-container');
    window.__menus = 0;
    //: Counted on the window in the *bubble* phase, which is where a menu
    //: that was not suppressed would arrive: the suppression runs on the
    //: container in the capture phase.
    window.addEventListener('contextmenu', (e) => { window.__menus += 1; e.preventDefault(); });
    const rect = container.getBoundingClientRect();
    const card = document.querySelector('#whiteboard-container .node-card');
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
      w: Math.round(rect.width),
      before: d3.zoomTransform(container).x,
      card: card ? (() => { const r = card.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })() : null,
    };
  });

  // 1. Right-drag on empty canvas: it pans, and eats its own menu.
  await page.mouse.move(box.x, box.y);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(box.x + 150, box.y + 60, { steps: 20 });
  await page.mouse.up({ button: 'right' });
  await page.waitForTimeout(300);
  const dragged = await page.evaluate(() => ({
    x: d3.zoomTransform(document.getElementById('whiteboard-container')).x,
    menus: document.querySelectorAll('.pointer-menu-anchor[aria-expanded="true"]').length,
  }));
  const moved = dragged.x - box.before;
  console.log(`258 right drag   container ${box.w}px wide, transform.x ${box.before} to ${dragged.x} (${moved.toFixed(0)}px), menus opened ${dragged.menus}`);

  // The app's own menu (opened on release) is what is counted; a drag leaves it closed.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);
  // 2. Right-click with no drag: the menu still opens.
  await page.evaluate(() => { window.__menus = 0; });
  await page.mouse.move(box.x, box.y);
  await page.mouse.down({ button: 'right' });
  await page.mouse.up({ button: 'right' });
  await page.waitForTimeout(300);
  const clicked = await page.evaluate(() => ({
    x: d3.zoomTransform(document.getElementById('whiteboard-container')).x,
    menus: document.querySelectorAll('.pointer-menu-anchor[aria-expanded="true"]').length,
  }));
  console.log(`258 right click  transform.x unchanged ${clicked.x === dragged.x}, menus opened ${clicked.menus}`);

  // 3. Right-press on a card is not a pan.
  //
  // The card's position is read *now*, not at setup: checks 1 and 2 pan the
  // board, and the card travels with it. Read once at the top, the recorded
  // coordinates pointed at empty canvas by the time this ran, and the check
  // reported "a right-drag on a card panned the board 120px" about a press
  // that never touched a card.
  const cardNow = await page.evaluate(() => {
    const el = document.querySelector('#whiteboard-container .node-card');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  let onCard = null;
  if (cardNow) {
    await page.evaluate(() => { window.__menus = 0; });
    await page.mouse.move(cardNow.x, cardNow.y);
    await page.mouse.down({ button: 'right' });
    await page.mouse.move(cardNow.x + 120, cardNow.y + 40, { steps: 16 });
    await page.mouse.up({ button: 'right' });
    await page.waitForTimeout(300);
    onCard = await page.evaluate(() => d3.zoomTransform(document.getElementById('whiteboard-container')).x);
    console.log(`258 on a card    transform.x ${clicked.x} to ${onCard}, moved ${(onCard - clicked.x).toFixed(0)}px`);
  } else {
    console.log('258 on a card    skipped: this board has no card to press');
  }

  await browser.close();
  const findings = [];
  if (!(moved > 140)) findings.push(`a right-drag moved the board ${moved.toFixed(0)}px, expected about 150`);
  if (dragged.menus !== 0) findings.push(`a right-drag opened ${dragged.menus} context menu(s)`);
  if (clicked.menus < 1) findings.push('a right-click with no drag opened no context menu');
  if (onCard !== null && Math.abs(onCard - clicked.x) > 2) {
    findings.push(`a right-drag on a card panned the board ${(onCard - clicked.x).toFixed(0)}px`);
  }
  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  process.exit(findings.length ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
