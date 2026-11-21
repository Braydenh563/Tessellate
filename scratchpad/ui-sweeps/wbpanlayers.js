// A board's resting cards are one layer's worth of paint, and their grips
// still come back where they are used (INBOX 424 (a)).
//
// The board pan spent most of its time in `Layerize`: 1,680ms of a 40-move
// pan at 4x on a 250-object board. The cause was the nine grips every card
// and text box carries, invisible at rest but still in the tree, each scaled
// by `--wb-inv-zoom`: a scale is a transform the compositor cannot fold into
// the layer around it, so they split the board into one layer per card (256
// composited layers, 245 of them "Overlap"). They are `display: none` at rest
// now. This sweep holds both halves:
//
//   1. the composited layer count on the `GW perf` board (gwperf.js builds
//      it) is under 160 at rest, from 256;
//   2. no card grip is rendered at rest (getClientRects on every one);
//   3. a hovered card in the Select tool shows 8 resize grips and 1 rotate
//      grip, and they fade in (opacity below 1 on the first frame, 1 after);
//   4. a selected card keeps its 9 grips after the pointer leaves;
//   5. a card under the Pan tool shows none on hover.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/wbpanlayers.js
const { boot } = require('./lib.js');

const results = [];
const check = (label, ok, detail) => {
  results.push(Boolean(ok));
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
};

(async () => {
  const { browser, page } = await boot({});
  const cdp = await page.context().newCDPSession(page);
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  const found = await page.evaluate(async () => {
    const v = document.getElementById('library-view-whiteboard');
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle('hidden', s !== v);
    await initWhiteboard();
    const b = (await apiJson('/whiteboard/boards')).find((x) => x.title === 'GW perf');
    if (!b) return false;
    await openWhiteboardBoard(b.id);
    return true;
  });
  if (!found) {
    console.log('no GW perf board: run gwperf.js board once first');
    await browser.close();
    process.exit(1);
  }
  await page.waitForTimeout(2000);
  await page.evaluate(() => wbZoomToFit({ animate: false }));
  await page.waitForTimeout(800);

  // 1. Layers, read from the compositor after one small pan so the tree is sent.
  let layers = null;
  cdp.on('LayerTree.layerTreeDidChange', (p) => { if (p.layers) layers = p.layers; });
  await cdp.send('LayerTree.enable');
  await page.evaluate(() => {
    const c = document.getElementById('whiteboard-container');
    wbApplyZoomTransform(d3.zoomTransform(c).translate(2, 2));
  });
  await page.waitForTimeout(1200);
  await cdp.send('LayerTree.disable');
  const n = layers ? layers.length : -1;
  check('the board at rest is under 160 composited layers', n > 0 && n < 160, `${n} layers (256 before)`);

  // 2. No grip drawn at rest.
  const rest = await page.evaluate(() => {
    const all = document.querySelectorAll('#wb-html-layer .wb-resize-handle, #wb-html-layer .wb-rotate-handle');
    let drawn = 0;
    for (const el of all) if (el.getClientRects().length) drawn += 1;
    return { all: all.length, drawn };
  });
  check('no card grip is rendered at rest', rest.all > 0 && rest.drawn === 0, `${rest.drawn} of ${rest.all} rendered`);

  // 3. Hover a card in Select: the grips come back, fading in.
  await page.evaluate(() => document.querySelector('button[data-tool="select"]').click());
  await page.evaluate(() => wbZoomToFit({ animate: false }));
  await page.evaluate(() => {
    d3.select('#whiteboard-container').call(wbZoom.transform, d3.zoomIdentity.translate(80, 120).scale(1));
  });
  await page.waitForTimeout(400);
  const cardBox = await page.evaluate(() => {
    const cont = document.getElementById('whiteboard-container').getBoundingClientRect();
    for (const el of document.querySelectorAll('#wb-html-layer .node-card')) {
      const r = el.getBoundingClientRect();
      if (r.left > cont.left + 20 && r.top > cont.top + 60 && r.right < cont.right - 20 && r.bottom < cont.bottom - 80) {
        return { x: r.left + r.width / 2, y: r.top + r.height / 2, id: el.dataset.id };
      }
    }
    return null;
  });
  if (!cardBox) {
    check('a card is on screen to hover', false);
  } else {
    await page.mouse.move(cardBox.x, cardBox.y);
    const first = await page.evaluate((id) => new Promise((res) => requestAnimationFrame(() => {
      const el = document.querySelector(`#wb-html-layer .node-card[data-id="${id}"]`);
      const h = [...el.querySelectorAll('.wb-resize-handle, .wb-rotate-handle')];
      res(h.map((x) => parseFloat(getComputedStyle(x).opacity)));
    })), cardBox.id);
    await page.waitForTimeout(400);
    const settled = await page.evaluate((id) => {
      const el = document.querySelector(`#wb-html-layer .node-card[data-id="${id}"]`);
      const shown = (sel) => [...el.querySelectorAll(sel)].filter((x) => x.getClientRects().length && getComputedStyle(x).opacity === '1').length;
      const knob = el.querySelector('.wb-rotate-handle').getBoundingClientRect();
      return { resize: shown('.wb-resize-handle'), rotate: shown('.wb-rotate-handle'), knob: Math.round(knob.width) };
    }, cardBox.id);
    check('a hovered card shows 8 resize grips and 1 rotate grip', settled.resize === 8 && settled.rotate === 1, JSON.stringify(settled));
    check('the grips fade in rather than snap', first.length === 9 && Math.min(...first) < 1, `first-frame opacity ${Math.min(...first).toFixed(2)}`);

    // 4. Select it, then move away: the grips stay.
    await page.mouse.down();
    await page.mouse.up();
    await page.mouse.move(cardBox.x, cardBox.y + 400);
    await page.waitForTimeout(400);
    const sel = await page.evaluate((id) => {
      const el = document.querySelector(`#wb-html-layer .node-card[data-id="${id}"]`);
      return { selected: el.classList.contains('wb-selected'), shown: [...el.querySelectorAll('.wb-resize-handle, .wb-rotate-handle')].filter((x) => x.getClientRects().length).length };
    }, cardBox.id);
    check('a selected card keeps its 9 grips once the pointer leaves', sel.selected && sel.shown === 9, JSON.stringify(sel));

    // 5. Pan tool: hover shows nothing.
    await page.keyboard.press('Escape');
    await page.evaluate(() => document.querySelector('button[data-tool="pan"]').click());
    await page.waitForTimeout(200);
    await page.mouse.move(cardBox.x, cardBox.y);
    await page.waitForTimeout(400);
    const pan = await page.evaluate((id) => {
      const el = document.querySelector(`#wb-html-layer .node-card[data-id="${id}"]`);
      return [...el.querySelectorAll('.wb-resize-handle, .wb-rotate-handle')].filter((x) => x.getClientRects().length).length;
    }, cardBox.id);
    check('under the Pan tool a hovered card shows no grips', pan === 0, `${pan} rendered`);
    await page.evaluate(() => document.querySelector('button[data-tool="select"]').click());
  }
  await browser.close();
  const failed = results.filter((x) => !x).length;
  console.log(`${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.stack); process.exit(1); });
