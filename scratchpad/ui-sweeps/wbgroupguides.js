// INBOX 267 (2), verbatim: "Alignment bars don't appear for group selections",
// and INBOX 278, verbatim: "the rotate line and circle dont sit at the top
// center of a group selection in the whiteboard and instead sit off to the top
// left or right, or below the top border".
//
// The second half is measured at the bottom of this file, at 0.5x, 1x and 2x:
// the group's knob against `(box.x + box.w / 2, box.y - stem)`, and how many
// rotate handles are on screen at all, which is what makes one look like it is
// in the wrong place.
//
// A previous session recorded this as built (`5273bae`, `wbBulkGroupBox`), so
// this measures rather than believes either way: select two cards, drag them
// until the group's own edge is within the snap distance of a third card's
// edge, and count the guide lines actually in the document.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(800);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForTimeout(1500);
  //: **Its own board, not the default one.** Read on a fresh data dir this
  //: check passed; on one with history in it, whatever card a previous run
  //: (or the app's own seed data) left under the pointer showed its grip in
  //: the group's guide reading and check B misfired on a leftover, not on the
  //: group logic. A board this sweep makes and opens itself has nothing on
  //: it until the setup below puts something there.
  await page.evaluate(async () => {
    const v = document.getElementById('library-view-whiteboard');
    if (v.classList.contains('hidden') || !v.offsetParent) {
      for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle('hidden', s !== v);
    }
    await initWhiteboard();
    const board = await apiJson('/whiteboard/boards', { method: 'POST', body: JSON.stringify({ name: 'Group guides check' }) });
    await openWhiteboardBoard(board.id);
    wbShowCanvasView();
    await fetchWhiteboardState();
    await new Promise((r) => setTimeout(r, 600));
  });

  // Three cards. Two are the group; the third is what the group lines up with.
  // Its left edge is the target, set a long way below so nothing overlaps.
  const setup = await page.evaluate(async () => {
    const at = [[120, 140], [420, 140], [123, 520]];
    const ids = [];
    for (const [x, y] of at) {
      const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `guide card at ${x}`, category: 'General' }) });
      const n = await apiJson('/whiteboard/nodes', { method: 'POST', body: JSON.stringify({ entry_id: e.id, board_id: window.currentBoardId ?? null, x, y, z: 1 }) });
      wbState.nodes.push(n);
      ids.push(n.id);
    }
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 500));
    if (window.currentTool !== 'select' && typeof setWbTool === 'function') setWbTool('select');
    wbMultiSelection.clear();
    for (const id of ids.slice(0, 2)) wbMultiSelection.add(wbMultiKey('node', id));
    wbApplySelectionHighlight();
    await new Promise((r) => setTimeout(r, 400));
    const card = document.querySelector(`.node-card[data-id="${ids[0]}"]`);
    const r = card.getBoundingClientRect();
    return { ids, grab: { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + 12) } };
  });
  console.log('setup', JSON.stringify(setup));

  // Drag the group by one of its members. The group's left edge starts at 120
  // and the lone card's is at 123, so a drag of +3 puts them level, which is
  // inside the snap distance and must draw a vertical guide.
  await page.mouse.move(setup.grab.x, setup.grab.y);
  await page.mouse.down();
  for (const dx of [20, 40, 30, 10, 3]) {
    await page.mouse.move(setup.grab.x + dx, setup.grab.y + 2, { steps: 4 });
    await page.waitForTimeout(120);
  }
  await page.waitForTimeout(400);
  const mid = await page.evaluate(() => {
    // A class on the open board's overlay group now (L-whiteboard-73: an embed's guides are a group of their own).
    const g = document.querySelector('.wb-align-guides');
    const lines = [...(g?.querySelectorAll('line') || [])].map((l) => ({
      x1: Math.round(+l.getAttribute('x1')), y1: Math.round(+l.getAttribute('y1')),
      x2: Math.round(+l.getAttribute('x2')), y2: Math.round(+l.getAttribute('y2')),
      kind: l.getAttribute('class'),
      visible: l.getBoundingClientRect().width > 0 || l.getBoundingClientRect().height > 0,
    }));
    return { group: !!g, lines, selected: wbMultiSelection.size };
  });
  await page.mouse.up();
  await page.waitForTimeout(300);
  console.log('mid-drag', JSON.stringify(mid, null, 1));

  //: And the case the report was actually about: a group dragged **by a
  //: sketch**. Cards have had guides since `wbBulkGroupBox`; the sketch drag
  //: handler never asked for them at all, solo or in a group, so a marquee
  //: that caught a sketch and was dragged by it was the one selection on the
  //: board with none.
  const sketchCase = await page.evaluate(async () => {
    //: On screen, deliberately. Board y=800 lands at screen y=968 in a 900px
    //: viewport, and a first version put the sketch there: every mouse event
    //: missed it, the sketch never moved, and the probe reported the feature
    //: broken when it had never been exercised.
    const path = 'M 300 300 L 460 300 L 460 380 L 300 380 Z';
    const sk = await apiJson('/whiteboard/sketches', {
      method: 'POST',
      body: JSON.stringify({
        board_id: window.currentBoardId ?? null,
        //: `data` is a JSON *string* holding `{d, color, width}`: the route's
        //: field is `data`, and a flat `{d: ...}` body is rejected, which is
        //: why an earlier run silently made no sketch at all.
        data: JSON.stringify({ d: path, color: '#888888', width: 3, shape: 'rect' }),
        x: 0, y: 0, z: 1,
      }),
    }).catch(() => null);
    if (!sk) return { made: false };
    wbState.sketches.push(sk);
    //: A partner well to the right, so the group is genuinely a group and its
    //: left edge is the sketch's own.
    const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'sketch group partner', category: 'General' }) });
    const n = await apiJson('/whiteboard/nodes', { method: 'POST', body: JSON.stringify({ entry_id: e.id, board_id: window.currentBoardId ?? null, x: 600, y: 300, z: 1 }) });
    wbState.nodes.push(n);
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 600));
    wbMultiSelection.clear();
    wbMultiSelection.add(wbMultiKey('sketch', sk.id));
    wbMultiSelection.add(wbMultiKey('node', n.id));
    wbApplySelectionHighlight();
    await new Promise((r) => setTimeout(r, 400));
    const el = document.querySelector(`.sketch-group[data-id="${sk.id}"] .sketch-hitbox`);
    if (!el) return { made: true, grabbed: false };
    const r = el.getBoundingClientRect();
    return {
      made: true, grabbed: true, id: sk.id,
      x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
      k: d3.zoomTransform(document.getElementById('whiteboard-container')).k,
    };
  });
  console.log('sketch case', JSON.stringify(sketchCase));
  let sketchLines = null;
  let snapped = null;
  if (sketchCase.grabbed) {
    //: The group's left edge is the sketch's, 300; the target card's is 123.
    //: So the drag that can line them up is 177 board pixels to the left.
    const need = Math.round(-177 * (sketchCase.k || 1));
    await page.mouse.move(sketchCase.x, sketchCase.y);
    await page.mouse.down();
    for (const f of [0.3, 0.6, 0.9, 1, 1]) {
      await page.mouse.move(sketchCase.x + Math.round(need * f), sketchCase.y, { steps: 5 });
      await page.waitForTimeout(150);
    }
    await page.waitForTimeout(400);
    const read = await page.evaluate((id) => ({
      lines: [...(document.querySelector('.wb-align-guides')?.querySelectorAll('line') || [])].length,
      d: document.querySelector(`.sketch-group[data-id="${id}"] .sketch-path`)?.getAttribute('d') || '',
    }), sketchCase.id);
    sketchLines = read.lines;
    snapped = read.d.startsWith('M 123 ');
    await page.mouse.up();
    await page.waitForTimeout(300);
    console.log('guide lines while dragging by the sketch:', sketchLines, 'snapped to the edge:', snapped);
  }

  //: --- INBOX 278: where the group's rotate handle actually sits -----------
  //: The second screenshot's selection: a note card, an image and a line. The
  //: group's own knob belongs at the top centre of the group box; what the
  //: report shows is a knob at a *member's* centre, and one below the top
  //: border, which is a member's own handle sitting inside the group.
  const setZoom = async (k) => {
    await page.evaluate((scale) => {
      const container = document.getElementById('whiteboard-container');
      d3.select(container).call(wbZoom.transform, d3.zoomIdentity.scale(scale));
    }, k);
    await page.waitForTimeout(300);
  };

  const built = await page.evaluate(async () => {
    const board = window.currentBoardId ?? null;
    const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'rotate group note', category: 'General' }) });
    const note = await apiJson('/whiteboard/nodes', { method: 'POST', body: JSON.stringify({ entry_id: e.id, board_id: board, x: 80, y: 700, z: 1 }) });
    const image = await apiJson('/whiteboard/objects', { method: 'POST', body: JSON.stringify({ kind: 'image', board_id: board, x: 420, y: 760, width: 180, height: 140, data: { url: '/media/none.png' } }) });
    const line = await apiJson('/whiteboard/sketches', {
      method: 'POST',
      body: JSON.stringify({ board_id: board, data: JSON.stringify({ d: 'M 120 960 L 520 1010', color: '#333333', width: 3, shape: 'line' }), x: 0, y: 0, z: 1 }),
    });
    wbState.nodes.push(note); wbState.objects.push(image); wbState.sketches.push(line);
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 500));
    wbMultiSelection.clear();
    wbMultiSelection.add(wbMultiKey('node', note.id));
    wbMultiSelection.add(wbMultiKey('object', image.id));
    wbMultiSelection.add(wbMultiKey('sketch', line.id));
    wbApplySelectionHighlight();
    await new Promise((r) => setTimeout(r, 400));
    return { note: note.id, image: image.id, line: line.id };
  });

  //: Read in board units off the SVG itself, so the check is the arithmetic
  //: the report names rather than a screen coordinate that the zoom could
  //: explain away, and again in screen pixels, which is where a wrong layer or
  //: a stale transform would show up.
  const readRotate = () => page.evaluate(() => {
    const g = document.querySelector('.wb-multi-handle-group');
    const boxEl = g?.querySelector('.wb-sketch-selection-box');
    const knobEl = g?.querySelector('.wb-sketch-rotate-handle');
    const stemEl = g?.querySelector('.wb-rotate-handle-stem');
    const num = (el, a) => (el ? Number(el.getAttribute(a)) : null);
    //: `width > 0 || height > 0`: a stem is a vertical line, so its box has no
    //: width at all and an `&&` here counted zero stems on a board that was
    //: drawing one.
    const seen = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') return false;
      //: **And opacity.** A card keeps its eight handles and its rotate grip
      //: in the DOM at all times and hides them with `opacity: 0` until it is
      //: hovered or selected (07-whiteboard-misc.css), so a count that reads
      //: only `display` reports every card on the board as showing grips: this
      //: probe said eleven rotate knobs for a three-item group on a board that
      //: was drawing one.
      if (Number(cs.opacity) === 0) return false;
      return r.width > 0 || r.height > 0;
    };
    //: Every rotate affordance on the board, not just the group's: a card and
    //: a text box carry `.wb-rotate-handle` as a child revealed by
    //: `.wb-selected`, a sketch gets `.wb-sketch-rotate-handle` drawn by
    //: `wbDrawSketchHandles`, and the group draws one of its own.
    const knobs = [...document.querySelectorAll('.wb-rotate-handle, .wb-sketch-rotate-handle')].filter(seen);
    const stems = [...document.querySelectorAll('.wb-rotate-handle-stem')].filter(seen);
    const box = boxEl ? { x: num(boxEl, 'x'), y: num(boxEl, 'y'), w: num(boxEl, 'width'), h: num(boxEl, 'height') } : null;
    const knob = knobEl ? { cx: num(knobEl, 'cx'), cy: num(knobEl, 'cy') } : null;
    const boxScreen = boxEl ? boxEl.getBoundingClientRect() : null;
    const knobScreen = knobEl ? knobEl.getBoundingClientRect() : null;
    return {
      box,
      knob,
      stemTop: stemEl ? num(stemEl, 'y2') : null,
      //: The recipe's own expression, in board units: the box is drawn at
      //: `minX - 2` and `width + 4`, so its centre is the group's centre.
      want: box ? { cx: box.x + box.w / 2, cy: box.y + 2 - 28 } : null,
      knobs: knobs.length,
      stems: stems.length,
      memberHandles: [...document.querySelectorAll('.node-card.wb-selected .wb-resize-handle, .wb-object.wb-selected .wb-resize-handle')].filter(seen).length,
      screen: boxScreen && knobScreen
        ? {
            wantX: Math.round(boxScreen.left + boxScreen.width / 2),
            gotX: Math.round(knobScreen.left + knobScreen.width / 2),
            boxTop: Math.round(boxScreen.top),
            gotY: Math.round(knobScreen.top + knobScreen.height / 2),
          }
        : null,
      k: d3.zoomTransform(document.getElementById('whiteboard-container')).k,
    };
  });

  //: **And the selection of one, which must keep everything.** Hiding a
  //: member's grips inside a group is only right if a thing selected on its
  //: own still has all of them: the report that put them there in the first
  //: place ("the shapes and lines arent selected visually and individually")
  //: is answered by the outline in a group and by the full set when the thing
  //: is the selection.
  const alone = await page.evaluate(async (ids) => {
    const count = () => {
      const seen = (el) => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return cs.visibility !== 'hidden' && cs.display !== 'none' && Number(cs.opacity) !== 0 && (r.width > 0 || r.height > 0);
      };
      return {
        cardResize: [...document.querySelectorAll('.node-card.wb-selected .wb-resize-handle')].filter(seen).length,
        cardRotate: [...document.querySelectorAll('.node-card.wb-selected .wb-rotate-handle')].filter(seen).length,
        sketchResize: [...document.querySelectorAll('.wb-sketch-resize-handle')].filter(seen).length,
        sketchRotate: [...document.querySelectorAll('.wb-sketch-rotate-handle')].filter(seen).length,
        outlines: [...document.querySelectorAll('.wb-sketch-selection-box')].filter(seen).length,
      };
    };
    wbMultiSelection.clear();
    selectWbItem('node', ids.note);
    await new Promise((r) => setTimeout(r, 300));
    const card = count();
    wbMultiSelection.clear();
    selectWbItem('sketch', ids.line);
    await new Promise((r) => setTimeout(r, 300));
    const sketch = count();
    //: Back to the group for the rows below.
    wbSelectedItem = null;
    wbMultiSelection.clear();
    wbMultiSelection.add(wbMultiKey('node', ids.note));
    wbMultiSelection.add(wbMultiKey('object', ids.image));
    wbMultiSelection.add(wbMultiKey('sketch', ids.line));
    wbApplySelectionHighlight();
    await new Promise((r) => setTimeout(r, 300));
    const group = count();
    return { card, sketch, group };
  }, built);
  console.log('alone', JSON.stringify(alone));

  const rotateRows = [];
  for (const k of [0.5, 1, 2]) {
    await setZoom(k);
    const row = await readRotate();
    rotateRows.push([k, row]);
    console.log(
      `rotate at ${k}x: box ${JSON.stringify(row.box)} knob ${JSON.stringify(row.knob)} want ${JSON.stringify(row.want)}`
      + ` | on screen knob x ${row.screen?.gotX} against box centre ${row.screen?.wantX}, knob y ${row.screen?.gotY} against box top ${row.screen?.boxTop}`
      + ` | rotate knobs on screen ${row.knobs}, stems ${row.stems}, member resize handles ${row.memberHandles}`,
    );
  }
  await setZoom(1);

  //: **And while the box is being resized**, which is the one path that moves
  //: the box without a re-render: `layoutGroupChrome` is called on every frame
  //: of the drag and is where the anchor is set, so a knob that stayed put
  //: here would mean the anchor was set once at creation instead.
  const drag = await page.evaluate(async () => {
    const g = document.querySelector('.wb-multi-handle-group');
    const north = g?.querySelector('.wb-sketch-resize-handle[data-handle="n"]');
    if (!north) return null;
    const r = north.getBoundingClientRect();
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
  });
  let midResize = null;
  if (drag) {
    await page.mouse.move(drag.x, drag.y);
    await page.mouse.down();
    await page.mouse.move(drag.x, drag.y - 60, { steps: 6 });
    await page.waitForTimeout(200);
    midResize = await readRotate();
    await page.mouse.up();
    await page.waitForTimeout(400);
    console.log(`mid-resize: box ${JSON.stringify(midResize.box)} knob ${JSON.stringify(midResize.knob)} want ${JSON.stringify(midResize.want)}`
      + ` | on screen knob x ${midResize.screen?.gotX} against box centre ${midResize.screen?.wantX}, knob y ${midResize.screen?.gotY} against box top ${midResize.screen?.boxTop}`);
  }

  const findings = [];
  if (midResize && midResize.knob && midResize.want) {
    if (Math.abs(midResize.knob.cx - midResize.want.cx) > 0.5 || Math.abs(midResize.knob.cy - midResize.want.cy) > 0.5) {
      findings.push(`mid-resize the knob is at (${midResize.knob.cx}, ${midResize.knob.cy}) where the box's top centre wants (${midResize.want.cx}, ${midResize.want.cy})`);
    }
    if (midResize.screen && (Math.abs(midResize.screen.gotX - midResize.screen.wantX) > 1 || midResize.screen.gotY > midResize.screen.boxTop)) {
      findings.push(`mid-resize the knob is ${midResize.screen.gotX - midResize.screen.wantX}px off the box's centre on screen`);
    }
  } else if (drag) {
    findings.push('the group box was not measurable during a resize drag');
  }
  for (const [k, row] of rotateRows) {
    if (!row.box || !row.knob) { findings.push(`no group rotate handle at ${k}x`); continue; }
    if (Math.abs(row.knob.cx - row.want.cx) > 0.5 || Math.abs(row.knob.cy - row.want.cy) > 0.5) {
      findings.push(`at ${k}x the group knob is at (${row.knob.cx}, ${row.knob.cy}) where the box's top centre wants (${row.want.cx}, ${row.want.cy})`);
    }
    if (row.screen && (Math.abs(row.screen.gotX - row.screen.wantX) > 1 || row.screen.gotY > row.screen.boxTop)) {
      findings.push(`at ${k}x the knob is ${row.screen.gotX - row.screen.wantX}px off the box's centre on screen and ${row.screen.gotY <= row.screen.boxTop ? 'above' : 'below'} its top edge`);
    }
    //: One rotate affordance for one selection. Two or more is the report:
    //: whichever one the eye lands on is "the" handle, and the others are in
    //: the wrong place by definition.
    if (row.knobs !== 1 || row.stems !== 1) {
      findings.push(`at ${k}x a three-item group shows ${row.knobs} rotate knobs and ${row.stems} stems, not one of each`);
    }
    if (row.memberHandles) {
      findings.push(`at ${k}x ${row.memberHandles} member resize handles are on screen inside a group selection`);
    }
  }

  //: A card on its own keeps its eight and its grip; a line on its own keeps
  //: its eight and its knob; the group of three draws one outline per member
  //: plus the group's own, and no member grips.
  if (alone.card.cardResize !== 8 || alone.card.cardRotate !== 1) {
    findings.push(`a card selected on its own shows ${alone.card.cardResize} resize handles and ${alone.card.cardRotate} rotate grips, not 8 and 1`);
  }
  if (alone.sketch.sketchResize !== 8 || alone.sketch.sketchRotate !== 1) {
    findings.push(`a line selected on its own shows ${alone.sketch.sketchResize} resize handles and ${alone.sketch.sketchRotate} rotate knobs, not 8 and 1`);
  }
  if (alone.group.cardResize || alone.group.cardRotate) {
    findings.push(`a card inside a group still shows ${alone.group.cardResize} resize handles and ${alone.group.cardRotate} rotate grips`);
  }
  if (alone.group.outlines < 2) {
    findings.push(`a group of three draws ${alone.group.outlines} outlines: each member must still be visibly selected`);
  }

  if (sketchCase.grabbed && !sketchLines) {
    findings.push('a group dragged by a sketch drew no alignment guide');
  } else if (sketchCase.grabbed && !snapped) {
    findings.push('the guide was drawn but the sketch did not snap to the edge it named');
  }
  if (mid.selected < 2) findings.push(`the group selection did not survive the drag (${mid.selected} selected)`);
  if (!mid.lines.length) findings.push('no alignment guide was drawn while a group was dragged into line');
  else if (!mid.lines.some((l) => l.visible)) findings.push(`${mid.lines.length} guide line(s) exist but none has any extent on screen`);
  if (errors.length) findings.push(`${errors.length} page error(s): ${errors.slice(0, 2)}`);
  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
