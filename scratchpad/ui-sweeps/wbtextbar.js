// The whiteboard's context bar with one text box selected (owner report,
// 2026-09-23): "the Size number input clips its number, the icon groups do
// not share a baseline, and its kebab menu lands away from the bar".
//
// Pass means, at 1184x760: the Size input shows its whole number
// (scrollWidth <= clientWidth, at 16 and at 128), every visible control in
// the bar has the same centre line within 1px, and the "More" menu opens
// with its top within 8px of the bar's bottom (or its bottom within 8px of
// the bar's top when it flips above). Exit 1 on any failure.
//
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/wbtextbar.js
const {boot, OUT, newBoard: libNewBoard } = require('./lib.js');

async function newBoard(page, name) {
  await libNewBoard(page, name, 'board');
  await page.keyboard.press('Escape');
}

(async () => {
  // VW, VH and DSF for a zoomed or scaled desktop window (DSF=1.25 is
  // Windows at 125%).
  const {browser, page} = await boot({viewport: {width: Number(process.env.VW || 1184), height: Number(process.env.VH || 760)},
    deviceScaleFactor: Number(process.env.DSF || 1)});
  const fails = [];
  await newBoard(page, `Text bar ${Date.now()}`);
  const TX = process.env.TX || 200, TY = process.env.TY || 220;
  const id = await page.evaluate(async ([TX, TY]) => {
    const board = window.currentBoardId;
    const made = await (await api('/whiteboard/objects', {method: 'POST', body: JSON.stringify(
      {kind: 'text', board_id: board, x: Number(TX), y: Number(TY), width: 220, height: 90, data: {content: 'A text box', fontSize: 16}})})).json();
    await fetchWhiteboardState();
    renderWhiteboard();
    return made.id;
  }, [TX, TY]);
  await page.waitForTimeout(600);
  await page.evaluate((i) => selectWbItem('object', i), id);
  await page.waitForTimeout(500);
  // EDIT=1: the same bar while the box is being typed into.
  if (process.env.EDIT) {
    await page.dblclick(`.wb-object[data-id="${id}"]`);
    await page.waitForTimeout(500);
  }
  const measure = () => page.evaluate(() => {
    const bar = document.getElementById('wb-context');
    const b = bar.getBoundingClientRect();
    const input = document.getElementById('wb-prop-fontsize');
    const controls = [...bar.querySelectorAll('.wb-context-group:not(.hidden) > button, .wb-context-group:not(.hidden) > label, .wb-context-group:not(.hidden) > .seg, .wb-context-group:not(.hidden) > .wb-board-menu-wrap > button, .wb-context-group:not(.hidden) input')]
      .filter((el) => el.getBoundingClientRect().width > 0 && getComputedStyle(el).visibility !== 'hidden')
      .map((el) => { const r = el.getBoundingClientRect(); return {id: el.id || el.getAttribute('aria-label') || el.className, cy: +((r.top + r.bottom) / 2).toFixed(1), h: +r.height.toFixed(1), top: +r.top.toFixed(1)}; });
    const cs = getComputedStyle(input);
    return {bar: {top: +b.top.toFixed(1), bottom: +b.bottom.toFixed(1), h: +b.height.toFixed(1), l: +b.left.toFixed(1), r: +b.right.toFixed(1)},
      input: {value: input.value, sw: input.scrollWidth, cw: input.clientWidth, w: +input.getBoundingClientRect().width.toFixed(1), pad: cs.padding, fs: cs.fontSize},
      controls};
  });
  let m = await measure();
  console.log(JSON.stringify(m));
  const spread = (cs) => { const ys = cs.map((c) => c.cy); return +(Math.max(...ys) - Math.min(...ys)).toFixed(1); };
  if (m.input.sw > m.input.cw) fails.push(`Size input clips ${m.input.value}: ${m.input.sw} > ${m.input.cw}`);
  // Every control, not only the Size field (INBOX 317: "the menu items are
  // cut off"): nothing in the bar is narrower than what it holds, and nothing
  // runs past the bar's own box.
  const cut = await page.evaluate(() => {
    const bar = document.getElementById('wb-context');
    const b = bar.getBoundingClientRect();
    return [...bar.querySelectorAll('.wb-context-group:not(.hidden) :is(button, label, input, select, .seg)')]
      .filter((el) => el.getBoundingClientRect().width > 0 && getComputedStyle(el).visibility !== 'hidden')
      .map((el) => { const r = el.getBoundingClientRect(); return {id: el.id || el.getAttribute('aria-label') || el.className, sw: el.scrollWidth, cw: el.clientWidth, out: r.left < b.left - 0.5 || r.right > b.right + 0.5}; })
      .filter((c) => c.sw > c.cw + 1 || c.out);
  });
  console.log('cut', JSON.stringify(cut));
  if (cut.length) fails.push(`controls cut: ${cut.map((c) => `${c.id} ${c.sw}>${c.cw}${c.out ? ' outside the bar' : ''}`).join(', ')}`);
  if (spread(m.controls) > 1) fails.push(`control centres spread ${spread(m.controls)}px: ${m.controls.map((c) => c.id + '@' + c.cy).join(', ')}`);
  // Three digits: the widest value the field allows.
  await page.evaluate(() => { const i = document.getElementById('wb-prop-fontsize'); i.value = '128'; });
  const wide = await page.evaluate(() => { const i = document.getElementById('wb-prop-fontsize'); return {sw: i.scrollWidth, cw: i.clientWidth}; });
  console.log('128', JSON.stringify(wide));
  if (wide.sw > wide.cw) fails.push(`Size input clips 128: ${wide.sw} > ${wide.cw}`);
  await page.evaluate(() => { const i = document.getElementById('wb-prop-fontsize'); i.value = '16'; });
  await page.screenshot({path: OUT + '/wbtextbar.png', clip: {x: Math.max(0, m.bar.l - 20), y: Math.max(0, m.bar.top - 20), width: Math.min(1184, m.bar.r - m.bar.l + 40), height: 360}});
  // The kebab: pressed with the mouse, then measured against the bar.
  const toggle = await page.$('#wb-context .wb-context-group[data-wb-ctx="common"] [data-wb-menu-toggle]');
  await toggle.click();
  await page.waitForTimeout(400);
  const menu = await page.evaluate(() => {
    const el = document.getElementById('wb-context-menu');
    const r = el.getBoundingClientRect();
    const bar = document.getElementById('wb-context').getBoundingClientRect();
    const t = document.querySelector('#wb-context [data-wb-menu-toggle]').getBoundingClientRect();
    return {open: !el.classList.contains('hidden') && r.height > 0, top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1), l: +r.left.toFixed(1), r: +r.right.toFixed(1),
      barTop: +bar.top.toFixed(1), barBottom: +bar.bottom.toFixed(1), toggleL: +t.left.toFixed(1), toggleR: +t.right.toFixed(1)};
  });
  console.log('menu', JSON.stringify(menu));
  if (!menu.open) fails.push('menu did not open');
  else {
    const below = Math.abs(menu.top - menu.barBottom);
    const above = Math.abs(menu.barTop - menu.bottom);
    if (Math.min(below, above) > 8) fails.push(`menu ${Math.min(below, above)}px from the bar`);
    if (menu.bottom > 760 || menu.top < 0) fails.push(`menu off screen ${menu.top}..${menu.bottom}`);
  }
  await page.screenshot({path: OUT + '/wbtextbar-menu.png'});
  console.log(fails.length ? 'FAIL ' + fails.join('; ') : 'OK text context bar');
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
