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

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
