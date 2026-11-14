// INBOX 610: "utility and usability for the mindmap is unintuitive like with
// resizing the mindmap nodes, resizing the text, changing various features
// ... with the individual nodes themselves and the popup tool menus (not the
// radials)". A task sweep: one map, one topic clicked, then every property
// of a topic changed through the UI the way a person would, counting the
// clicks each takes from the selected topic and checking the stored field
// really changed. Also measures the topic's own grips: where they sit, how
// big, whether they show on select, and whether dragging them works.
// Pass: every task done in at most 2 steps, every grip at least 20px and on
// the topic's own edge or corner, the resize drag grows the box, the text
// drag grows the text.
const { boot, openBoardsTab } = require('./lib.js');
(async () => {
  const W = +(process.env.W || 1440);
  const { page, browser } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  // The Boards sub-tab, picked and waited for (lib.js `openBoardsTab`): the Library
  // reopens on its last sub-tab, and `wbFormatSyncSoon` is not loaded at open any more.
  await openBoardsTab(page, ['initWhiteboard', 'wbMapTidyFresh', 'wbWireMapChoices']);
  const ids = await page.evaluate(async () => {
    await initWhiteboard();
    const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: `tasks ${Date.now()}`, type: 'map', layout: 'tree-right' }) });
    const root = await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: 'Centre' }) });
    const kid = await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: 'A branch', parent_id: root.id }) });
    await apiJson(`/whiteboard/boards/${board.id}/nodes`, { method: 'POST', body: JSON.stringify({ kind: 'topic', text: 'Another', parent_id: root.id }) });
    await openWhiteboardBoard(board.id);
    await wbMapTidyFresh();
    await new Promise((r) => setTimeout(r, 500));
    return { board: board.id, kid: kid.id };
  });
  const sel = `.wb-object[data-id="${ids.kid}"]`;
  const select = async () => {
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    const b = await (await page.$(sel)).boundingBox();
    await page.mouse.click(b.x + b.width * 0.5, b.y + b.height * 0.5);
    await page.waitForTimeout(350);
  };
  const field = (name) => page.evaluate(([id, name]) => wbState.objects.find((o) => o.id === id)?.data?.[name] ?? null, [ids.kid, name]);
  await select();
  // ---- the bar itself
  const bar = await page.evaluate(() => {
    const s = document.getElementById('wb-map-strip');
    const r = s.getBoundingClientRect();
    const visible = (el) => el.offsetParent !== null && el.getBoundingClientRect().width > 0;
    const direct = [...s.querySelectorAll('button, input, select, .select-shell')].filter((el) => visible(el) && !el.closest('.wb-board-menu'));
    return { shown: !s.classList.contains('hidden') && r.width > 0, width: Math.round(r.width), controls: direct.length, doors: s.querySelectorAll('[data-wb-menu-toggle]').length };
  });
  console.log(`W${W} bar: shown ${bar.shown}, ${bar.width}px wide, ${bar.controls} controls on it, ${bar.doors} menus`);
  // ---- grips
  const grips = await page.evaluate((sel) => {
    const node = document.querySelector(sel);
    const n = node.getBoundingClientRect();
    return [...node.querySelectorAll('.wb-map-size-grip, .wb-map-resize-grip, .wb-map-corner-grip, .wb-map-text-grip')].map((g) => {
      const r = g.getBoundingClientRect();
      const op = getComputedStyle(g.closest('.wb-map-grips') || g).opacity;
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const onEdge = Math.min(Math.abs(cx - n.right), Math.abs(cx - n.left)) <= 12 || Math.min(Math.abs(cy - n.bottom), Math.abs(cy - n.top)) <= 12;
      const atCorner = (Math.abs(cx - n.right) <= 12 || Math.abs(cx - n.left) <= 12) && (Math.abs(cy - n.bottom) <= 12 || Math.abs(cy - n.top) <= 12);
      return { cls: g.className.baseVal ?? g.className, w: Math.round(r.width), h: Math.round(r.height), opacity: op, onEdge, atCorner, dx: Math.round(cx - n.left), dy: Math.round(cy - n.top), nodeW: Math.round(n.width), nodeH: Math.round(n.height) };
    });
  }, sel);
  for (const g of grips) console.log(`grip ${g.cls}: ${g.w}x${g.h}px, opacity on select ${g.opacity}, centre at ${g.dx},${g.dy} of a ${g.nodeW}x${g.nodeH} topic, on its edge ${g.onEdge}, at a corner ${g.atCorner}`);
  // drag each grip and see what changes
  // the grip takes the press at its own centre (nothing drawn over it)
  const onTop = await page.evaluate((sel) => {
    const g = document.querySelector(`${sel} .wb-map-resize-grip`);
    if (!g) return null;
    const r = g.getBoundingClientRect();
    if (!r.width) return 'hidden';
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return hit === g || g.contains(hit) ? 'grip' : (hit?.className?.baseVal ?? hit?.className ?? String(hit));
  }, sel);
  console.log(`resize grip under the pointer at its centre: ${onTop} ${onTop === 'grip' ? 'PASS' : 'FAIL'}`);
  const dragGrip = async (cls, dx, dy, shift = false) => {
    await select();
    const g = await page.$(`${sel} .${cls}`);
    if (!g) return null;
    const b = await g.boundingBox();
    if (!b) return null;
    const before = await page.evaluate((sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { w: r.width, h: r.height, f: parseFloat(getComputedStyle(document.querySelector(sel)).fontSize) }; }, sel);
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    if (shift) await page.keyboard.down('Shift');
    await page.mouse.down();
    for (let i = 1; i <= 8; i += 1) await page.mouse.move(b.x + b.width / 2 + dx * i / 8, b.y + b.height / 2 + dy * i / 8);
    await page.mouse.up();
    if (shift) await page.keyboard.up('Shift');
    await page.waitForTimeout(600);
    const after = await page.evaluate((sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { w: r.width, h: r.height, f: parseFloat(getComputedStyle(document.querySelector(sel)).fontSize) }; }, sel);
    return { dw: Math.round(after.w - before.w), dh: Math.round(after.h - before.h), df: +(after.f - before.f).toFixed(1) };
  };
  const r1 = await dragGrip('wb-map-resize-grip', 60, 30);
  if (r1) console.log(`drag the resize grip +60,+30: box ${r1.dw >= 0 ? '+' : ''}${r1.dw}w ${r1.dh >= 0 ? '+' : ''}${r1.dh}h, text ${r1.df}px ${r1.dw > 20 && r1.df === 0 ? 'PASS' : 'FAIL'}`);
  const r2 = await dragGrip('wb-map-resize-grip', 80, 0, true);
  if (r2) console.log(`Shift-drag the resize grip +80: box ${r2.dw >= 0 ? '+' : ''}${r2.dw}w, text ${r2.df >= 0 ? '+' : ''}${r2.df}px ${r2.df > 0 ? 'PASS' : 'FAIL'}`);
  for (const cls of ['wb-map-size-grip']) {
    const r = await dragGrip(cls, 0, -40);
    if (r) console.log(`drag ${cls} up 40: text ${r.df >= 0 ? '+' : ''}${r.df}px ${r.df > 0 ? 'PASS' : 'FAIL'}`);
  }
  // put the text size back so the tasks below start from M
  await page.evaluate(async (id) => { const n = wbState.objects.find((o) => o.id === id); await wbMapSetNodeStyle(n, { font_size: null }); }, ids.kid);
  // ---- the tasks. Each: the clicks a person makes, from the selected topic.
  // A click is a press on a visible control; picking a row in an open list
  // is a click too. `find` locates a control by its visible words or label.
  // A step names a control by its exact words: its title, its text, or its
  // label. Only a visible control counts, wherever it is (a door's panel can
  // be moved to <body> when the canvas would clip it).
  const clickText = async (words) => {
    const ok = await page.evaluate((words) => {
      const els = [...document.querySelectorAll('button, [role="menuitem"], [role="option"]')]
        .filter((el) => el.offsetParent !== null && el.getBoundingClientRect().width > 0);
      const hit = els.find((el) => [el.title, el.textContent.trim(), el.getAttribute('aria-label')].includes(words));
      if (!hit) return false;
      hit.click();
      return true;
    }, words);
    await page.waitForTimeout(250);
    return ok;
  };
  // [task, field, the words of each press in order]. A door named first is
  // pressed only if the choice is not already on the bar.
  const tasks = [
    ['bold', 'bold', ['Text', 'Bold']],
    ['text bigger', 'font_size', ['Text', 'L']],
    ['align left', 'align', ['Text', 'Left']],
    ['icon', 'icon', ['Text', 'Star']],
    ['shape', 'shape', ['Shape', 'Pill']],
    ['core idea', 'core', ['Shape', 'Mark this topic as a core idea']],
    ['fill', 'fill', ['Shape', 'Fill this topic']],
    ['edge bar', 'spine', ['Shape', 'Dashed bar']],
    ['line thickness', 'edge_width', ['Branch line', 'Thick line']],
    ['line shape', 'edge_style', ['Branch line', 'Straight line']],
    ['dashed', 'edge_dashed', ['Branch line', 'Dash the line into this topic']],
  ];
  let worst = 0;
  for (const [name, f, steps] of tasks) {
    await select();
    const before = JSON.stringify(await field(f));
    let used = 0;
    let done = false;
    // the choice itself first: if it is on the bar, one press does it
    const direct = await clickText(steps[steps.length - 1]);
    if (direct) {
      used = 1;
      done = JSON.stringify(await field(f)) !== before;
    }
    if (!done) {
      used = 0;
      for (const words of steps) {
        const ok = await clickText(words);
        if (!ok) break;
        used += 1;
        if (JSON.stringify(await field(f)) !== before) { done = true; break; }
      }
    }
    await page.keyboard.press('Escape');
    worst = Math.max(worst, done ? used : 99);
    console.log(`task ${name}: ${done ? `${used} press${used === 1 ? '' : 'es'}` : `unfinished in ${used} presses`} ${done && used <= 2 ? 'PASS' : 'FAIL'}`);
  }
  // colour, reset, rename are on the bar or the topic itself
  console.log(`worst task: ${worst === 99 ? 'some not done' : worst + ' steps'}`);
  // inline edit: double-click the label, type, Enter
  await select();
  const b = await (await page.$(sel)).boundingBox();
  await page.mouse.dblclick(b.x + b.width / 2, b.y + b.height / 2);
  await page.waitForTimeout(300);
  await page.keyboard.press('Control+A');
  await page.keyboard.type('Renamed here');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  const text = await page.evaluate((id) => wbState.objects.find((o) => o.id === id)?.data?.content, ids.kid);
  console.log(`inline edit: "${text}" ${text === 'Renamed here' ? 'PASS' : 'FAIL'}`);
  await select();
  await page.screenshot({ path: `${process.env.SCRATCH || '.'}/bm1005-nodetasks-${W}.png` });
  // each door open: its panel inside the window, no segment spilling out of it
  for (const door of ['Text', 'Shape', 'Branch line']) {
    await select();
    await clickText(door);
    const fit = await page.evaluate(() => {
      const menu = [...document.querySelectorAll('.wb-map-strip-menu')].find((m) => !m.classList.contains('hidden'));
      if (!menu) return null;
      const r = menu.getBoundingClientRect();
      const spill = [...menu.querySelectorAll('.wb-map-choices button')].filter((b) => { const q = b.getBoundingClientRect(); return q.right > r.right + 0.5 || q.left < r.left - 0.5; }).length;
      return { w: Math.round(r.width), h: Math.round(r.height), inWindow: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, spill };
    });
    console.log(`door ${door}: ${fit ? `${fit.w}x${fit.h}px, inside the window ${fit.inWindow}, segments spilling ${fit.spill}` : 'did not open'} ${fit && fit.inWindow && !fit.spill ? 'PASS' : 'FAIL'}`);
    await page.screenshot({ path: `${process.env.SCRATCH || '.'}/bm1005-door-${door.replace(' ', '')}-${W}.png` });
    await page.keyboard.press('Escape');
  }
  console.log(`page errors: ${errors.length}${errors.length ? ' ' + errors.slice(0, 3).join(' | ') : ''}`);
  await browser.close();
})();
