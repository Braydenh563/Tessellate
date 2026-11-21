// WHITEBOARD_PLAN ink rows measured on a live board: hollow line ends, smoothed pen and marker, pressure, clean-up of a
// rough shape, replay and GIF export.
//   BASE=http://127.0.0.1:8898 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbink3.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 1440 });
  const { check, summary } = checker();
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  const at = (dx, dy) => [box.x + box.w / 2 + dx, box.y + box.h / 2 + dy];
  const sketches = () => page.evaluate(() => wbState.sketches.length);
  const lastParsed = () => page.evaluate(() => wbSketchParsedData(wbState.sketches[wbState.sketches.length - 1]));
  const tool = (name) => page.evaluate((n) => wbSelectToolRef(n), name);

  // --- L277: the shaft stops at a hollow end ---------------------------------------------------------------
  const lineId = await page.evaluate(async () => {
    const d = "M 100 100 L 400 100";
    const r = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: window.currentBoardId, x: 0, y: 0, z: 1, data: JSON.stringify({ d, color: "#333", width: 3, shape: "line", startCap: "none", endCap: "circle" }) }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return r.id;
  });
  await page.waitForTimeout(500);
  const hollow = await page.evaluate((id) => {
    const g = document.querySelector(`.sketch-group[data-id="${id}"]`);
    return { drawn: g.querySelector(".sketch-path").getAttribute("d"), hit: g.querySelector(".sketch-hitbox").getAttribute("d") };
  }, lineId);
  const shaftEnd = Number((hollow.drawn.match(/^M [\d.]+ [\d.]+ L ([\d.]+)/) || [])[1]);
  check("L277: the drawn shaft stops short of a hollow circle end (x < 400)", shaftEnd > 380 && shaftEnd < 395, hollow.drawn);
  check("L277: the hit band keeps the whole line to x = 400", /L 400 100/.test(hollow.hit), hollow.hit);

  // --- Smoothed pen (mouse) --------------------------------------------------------------------------------
  await tool("draw");
  const before = await sketches();
  const [px, py] = at(-200, 100);
  await page.mouse.move(px, py);
  await page.mouse.down();
  for (let i = 1; i <= 30; i++) await page.mouse.move(px + i * 8, py + Math.sin(i / 4) * 30);
  const live = await page.evaluate(() => { const p = document.querySelector("#wb-overlay-zoom-group > path"); return p && { fill: p.getAttribute("fill"), stroke: p.getAttribute("stroke") }; });
  check("pen: the live stroke is filled ink with no outline stroke", live && live.stroke === "none" && live.fill && live.fill !== "none", live);
  await page.mouse.up();
  await page.waitForTimeout(700);
  const pen = await lastParsed();
  check("pen: one sketch saved, flagged ink, an outline of M and L points", (await sketches()) === before + 1 && pen.ink === 1 && /^M [\d. -]+( L [\d. -]+)+$/.test(pen.d), pen.d?.slice(0, 80));
  const drawnPen = await page.evaluate(() => { const g = [...document.querySelectorAll(".sketch-group")].pop(); const p = g.querySelector(".sketch-path"); const cs = getComputedStyle(p); return { fill: cs.fill, stroke: cs.stroke, n: (p.getAttribute("d").match(/L/g) || []).length }; });
  check("pen: drawn filled in the stroke colour, stroke none", drawnPen.fill !== "none" && drawnPen.stroke === "none", drawnPen);
  check("pen: smoothing leaves a bounded point count (outline of 30 samples under 200 points)", drawnPen.n > 20 && drawnPen.n < 200, drawnPen.n);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(500);
  check("pen: one Undo takes the stroke back", (await sketches()) === before);

  // --- Pressure: a synthetic pen's width follows pressure ---------------------------------------------------
  const widthAt = async (pressure) => {
    await page.evaluate(async ([x, y, pr]) => {
      const c = document.getElementById("whiteboard-container");
      const fire = (type, dx, p) => c.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x + dx, clientY: y, pointerId: 7, pointerType: "pen", pressure: p, isPrimary: true, buttons: type === "pointerup" ? 0 : 1 }));
      fire("pointerdown", 0, pr);
      for (let i = 1; i <= 25; i++) fire("pointermove", i * 8, pr);
      fire("pointerup", 200, pr);
    }, [...at(-200, 200), pressure]);
    await page.waitForTimeout(700);
    const ys = (await lastParsed()).d.match(/[ML] [-\d.]+ ([-\d.]+)/g).map((m) => parseFloat(m.split(" ")[2]));
    const h = Math.max(...ys) - Math.min(...ys);
    await page.evaluate(() => wbUndo());
    await page.waitForTimeout(400);
    return h;
  };
  const light = await widthAt(0.15);
  const hard = await widthAt(0.9);
  check("pressure: a pen stroke at 0.9 is more than twice as thick as at 0.15", hard / light > 2, { light, hard });

  // --- Marker ------------------------------------------------------------------------------------------------
  await tool("highlighter");
  const [mx, my] = at(-200, -150);
  await page.mouse.move(mx, my);
  await page.mouse.down();
  for (let i = 1; i <= 20; i++) await page.mouse.move(mx + i * 10, my + i * 2);
  await page.mouse.up();
  await page.waitForTimeout(700);
  const marker = await lastParsed();
  const markerDrawn = await page.evaluate(() => { const p = [...document.querySelectorAll(".sketch-group")].pop().querySelector(".sketch-path"); const cs = getComputedStyle(p); return { fillOpacity: cs.fillOpacity, blend: cs.mixBlendMode, stroke: cs.stroke }; });
  check("marker: ink with the highlighter's translucency and blend", marker.ink === 1 && marker.shape === "highlighter" && Number(markerDrawn.fillOpacity) < 1 && markerDrawn.stroke === "none", { markerDrawn, marker: { ...marker, d: marker.d?.slice(0, 30) } });
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(400);


  // --- Clean up: a rough box becomes a rectangle, one Undo step ---------------------------------------------
  await tool("draw");
  const corners = [[-150, -120], [50, -125], [55, -20], [-145, -15], [-150, -118]];
  const [bx, by] = at(corners[0][0], corners[0][1]);
  await page.mouse.move(bx, by);
  await page.mouse.down();
  for (let k = 1; k < corners.length; k++) {
    const [ax, ay] = corners[k - 1], [cx, cy] = corners[k];
    for (let i = 1; i <= 14; i++) { const [x, y] = at(ax + ((cx - ax) * i) / 14, ay + ((cy - ay) * i) / 14); await page.mouse.move(x + Math.sin(i) * 2, y + Math.cos(i * 2) * 2); }
  }
  await page.mouse.up();
  await page.waitForTimeout(700);
  const rough = await lastParsed();
  check("clean up: the rough box was saved as ink that kept its points", rough.ink === 1 && rough.pts.length > 40 && rough.pbox.length === 4, { pts: rough.pts?.length, pbox: rough.pbox });
  const roughId = await page.evaluate(() => wbState.sketches[wbState.sketches.length - 1].id);
  await tool("select");
  await page.evaluate((id) => selectWbItem("sketch", id), roughId);
  await page.waitForTimeout(300);
  const offered = await page.evaluate(() => { const c = WB_COMMAND_BY_ID.get("cleanup-ink"); return { has: Boolean(c), applies: Boolean(c && wbCommandNeeds[c.needs]()) }; });
  check("clean up: the Edit command is offered for a selected pen stroke", offered.has && offered.applies, offered);
  const menuRow = await page.evaluate(() => Boolean(document.querySelector('[data-wb-cmd="cleanup-ink"]')));
  check("clean up: the command is in the board's menus", menuRow);
  //: Move it first, so the points have to follow the stroke.
  const movedBy = 120;
  await page.evaluate(async ([id, dx]) => { const sk = wbState.sketches.find((x) => x.id === id); const p = wbSketchParsedData(sk); await wbSaveSketchD(sk, wbTransformPathD(p.d, { dx })); wbScheduleRender(); }, [roughId, movedBy]);
  await page.waitForTimeout(300);
  const boxBefore = await page.evaluate((id) => wbPathBBox(wbSketchParsedData(wbState.sketches.find((x) => x.id === id)).d), roughId);
  const undoBefore = await page.evaluate(() => wbUndoStack?.length ?? null);
  await page.evaluate(() => WB_COMMAND_BY_ID.get("cleanup-ink").run());
  await page.waitForTimeout(700);
  const cleaned = await page.evaluate((id) => { const sk = wbState.sketches.find((x) => x.id === id); const p = wbSketchParsedData(sk); return { shape: p.shape, ink: p.ink, pts: p.pts, d: p.d, box: wbPathBBox(p.d) }; }, roughId);
  check("clean up: it is now a rectangle (h and v moves, closed), not ink", cleaned.shape === "rect" && !cleaned.ink && !cleaned.pts && /^M [\d. -]+ h [\d. -]+ v [\d. -]+ h [\d. -]+ Z$/.test(cleaned.d), cleaned);
  check("clean up: the clean rectangle sits where the moved stroke was (within 8 units of its box)", Math.abs(cleaned.box.minX - boxBefore.minX) < 8 && Math.abs(cleaned.box.maxX - boxBefore.maxX) < 8, { cleaned: cleaned.box, boxBefore });
  const undoAfter = await page.evaluate(() => wbUndoStack?.length ?? null);
  check("clean up: exactly one Undo step", undoBefore === null || undoAfter === undoBefore + 1, { undoBefore, undoAfter });
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(600);
  const back = await page.evaluate((id) => { const p = wbSketchParsedData(wbState.sketches.find((x) => x.id === id)); return { ink: p.ink, shape: p.shape }; }, roughId);
  check("clean up: Undo brings the ink stroke back", back.ink === 1 && back.shape === "draw", back);
  //: A scribble is told no.
  await tool("draw");
  const [sx0, sy0] = at(-100, 150);
  await page.mouse.move(sx0, sy0);
  await page.mouse.down();
  for (let i = 1; i <= 40; i++) await page.mouse.move(sx0 + ((i * 37) % 90), sy0 + ((i * 53) % 80));
  await page.mouse.up();
  await page.waitForTimeout(600);
  const scribbleId = await page.evaluate(() => wbState.sketches[wbState.sketches.length - 1].id);
  await tool("select");
  await page.evaluate((id) => selectWbItem("sketch", id), scribbleId);
  const said = await page.evaluate(async () => { const ok = await WB_COMMAND_BY_ID.get("cleanup-ink").run(); return ok; });
  const scribble = await page.evaluate((id) => wbSketchParsedData(wbState.sketches.find((x) => x.id === id)).ink, scribbleId);
  check("clean up: a scribble stays ink", scribble === 1);
  // --- Replay and the GIF -------------------------------------------------------------------------------------
  const strokeCount = await page.evaluate(() => wbFmtState.inkReplay.strokes().length);
  check("replay: the board's pen strokes are found (two or more)", strokeCount >= 2, strokeCount);
  const rowShown = await page.evaluate(() => { const c = WB_COMMAND_BY_ID.get("replay-ink"); return Boolean(c && wbCommandNeeds[c.needs]()); });
  check("replay: the command is offered on a board with pen strokes", rowShown);
  await page.evaluate(() => WB_COMMAND_BY_ID.get("replay-ink").run());
  await page.waitForTimeout(120);
  const during = await page.evaluate(() => wbFmtState.inkReplay.strokes().map((s) => document.querySelector(`.sketch-group[data-id="${s.id}"]`)?.style.visibility));
  check("replay: the strokes start hidden", during.every((v) => v === "hidden"), during);
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => wbFmtState.inkReplay.strokes().map((s) => document.querySelector(`.sketch-group[data-id="${s.id}"]`)?.style.visibility));
  check("replay: every stroke is back at the end", after.every((v) => v === ""), after);
  const gif = await page.evaluate(async () => {
    let saved = null;
    const real = window.saveFile;
    window.saveFile = async (name, blob) => { saved = { name, size: blob.size, head: new TextDecoder().decode(new Uint8Array(await blob.arrayBuffer()).slice(0, 6)), type: blob.type }; };
    try { await WB_EXPORT_FORMATS.find((f) => f.value === "gif").run("whole"); } finally { window.saveFile = real; }
    return saved;
  });
  check("GIF: a .gif file of GIF89a bytes, over 1 KB, is written", gif && /\.gif$/.test(gif.name) && gif.head === "GIF89a" && gif.size > 1000 && gif.type === "image/gif", gif);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
