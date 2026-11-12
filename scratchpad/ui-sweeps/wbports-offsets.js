// Port offsets and the connection-point rows (L-whiteboard-13). A .drawio file whose shapes carry
// `points=[[x,y,perimeter,dx,dy],...]` comes in with those ports; a perimeter port lies on every shape's outline
// (ellipse, diamond, triangle, hexagon, rounded box), before and after a resize, with dx/dy added on top; the export
// writes the same points back; Format's rows list, nudge, hold on the outline, add and remove, one Undo step each.
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbports-offsets.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

const PORTS = "[[0.5,-0.15,1,0,0],[1.15,0.5,1,6,-3],[0.3,0.3,0,5,5]]";
const cell = (id, style, x) => `<mxCell id="${id}" value="" style="${style}points=${PORTS};" vertex="1" parent="1"><mxGeometry x="${x}" y="40" width="120" height="80" as="geometry"/></mxCell>`;
const XML = `<mxfile><diagram name="P"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>` +
  [["e", "ellipse;"], ["d", "rhombus;"], ["t", "triangle;"], ["h", "hexagon;"], ["r", "rounded=1;"]].map(([id, s], i) => cell(id, s, i * 200)).join("") +
  `</root></mxGraphModel></diagram></mxfile>`;

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (xml) => { await wbImportDrawio(xml, [500, 300]); await fetchWhiteboardState(); renderWhiteboardNow(); }, XML);
  await page.waitForTimeout(800);

  // How far a point is from the nearest point of a path, found at 4000 steps.
  const probe = `(d, px, py) => {
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", d);
    const L = p.getTotalLength(); let best = Infinity;
    for (let i = 0; i <= 4000; i++) { const q = p.getPointAtLength((L * i) / 4000); best = Math.min(best, Math.hypot(q.x - px, q.y - py)); }
    return best;
  }`;
  const measure = () => page.evaluate((src) => {
    const dist = eval(src);
    return wbState.sketches.filter((s) => { try { return JSON.parse(s.data).ports; } catch { return false; } }).map((s) => {
      const data = JSON.parse(s.data), box = wbItemBBox("sketch", s), w = box.maxX - box.minX, h = box.maxY - box.minY;
      const ports = wbPortFractions("sketch", s);
      // A point's place before the offset is added: the stored offset is taken back off.
      const off = ports.map((q, i) => {
        const x = box.minX + q.x * w, y = box.minY + q.y * h;
        return { perimeter: Boolean(data.ports[i].perimeter), d: dist(data.d, x, y), dx: q.dx || 0, dy: q.dy || 0, shown: wbAnchorPositions("sketch", s)[i] };
      });
      return { id: s.id, shape: data.shape, n: ports.length, off, box: [Math.round(w), Math.round(h)] };
    });
  }, probe);

  const first = await measure();
  check("five shapes came in with their three ports each", first.length === 5 && first.every((s) => s.n === 3), first.map((s) => [s.shape, s.n]));
  const worst = (list) => Math.max(0, ...list.flatMap((s) => s.off.filter((o) => o.perimeter).map((o) => o.d)));
  check("every perimeter port lies on its outline (max distance under 0.5 px)", worst(first) < 0.5, { worst: worst(first) });
  check("the free port is where its fractions put it (not forced to the outline)", first.every((s) => s.off[2].d > 2), first.map((s) => s.off[2].d));
  check("the offsets arrived (6, -3 on the second port; 5, 5 on the third)", first.every((s) => s.off[1].dx === 6 && s.off[1].dy === -3 && s.off[2].dx === 5 && s.off[2].dy === 5));
  const shownGap = await page.evaluate(() => wbState.sketches.filter((s) => JSON.parse(s.data).ports).map((s) => {
    const box = wbItemBBox("sketch", s), q = wbPortFractions("sketch", s)[1], at = wbAnchorPositions("sketch", s)[1];
    return Math.hypot(at.x - (box.minX + q.x * (box.maxX - box.minX) + q.dx), at.y - (box.minY + q.y * (box.maxY - box.minY) + q.dy));
  }));
  check("the board position of a port is its place plus (dx, dy), measured", Math.max(...shownGap) < 0.01, shownGap);

  // Resize every shape: stretch the drawn path to 1.8 x 1.4 of its box.
  await page.evaluate(async () => {
    for (const s of wbState.sketches.filter((q) => { try { return JSON.parse(q.data).ports; } catch { return false; } })) {
      const data = JSON.parse(s.data), box = wbPathBBox(data.d);
      data.d = wbTransformPathD(data.d, { sx: 1.8, sy: 1.4, anchorX: box.minX, anchorY: box.minY });
      s.data = JSON.stringify(data);
    }
    renderWhiteboardNow();
  });
  const stretched = await measure();
  check("after a resize the boxes are larger", stretched.every((s, i) => s.box[0] > first[i].box[0] * 1.7 && s.box[1] > first[i].box[1] * 1.3), stretched.map((s) => s.box));
  check("after a resize every perimeter port still lies on its outline (max under 0.5 px)", worst(stretched) < 0.5, { worst: worst(stretched) });

  // Round trip: the export carries the same points.
  const back = await page.evaluate(() => {
    const out = wbBoardToDrawio(wbState, { title: "T", box: (k, i) => wbItemBBox(k, i) });
    const doc = new DOMParser().parseFromString(out.xml.replace(/^<\?xml[^>]*\?>\s*/, "").replace(/^<!--[\s\S]*?-->/, ""), "text/xml");
    return [...doc.getElementsByTagName("mxCell")].map((c) => /points=(\[\[.*?\]\])/.exec(c.getAttribute("style") || "")?.[1]).filter(Boolean);
  });
  const want = JSON.stringify(JSON.parse(PORTS));
  check("the export writes the five shapes' points back, equal to what came in", back.length === 5 && back.every((b) => JSON.stringify(JSON.parse(b)) === want), back);

  // The rows.
  const id = await page.evaluate(() => wbState.sketches.find((s) => JSON.parse(s.data).ports).id);
  await page.evaluate((sid) => { selectWbItem("sketch", sid); }, id);
  await page.waitForTimeout(400);
  await page.keyboard.press("Control+Shift+P");
  await page.waitForTimeout(500);
  await page.click("#wb-format-tab-arrange");
  await page.waitForTimeout(500);
  const rows = await page.evaluate(() => {
    const panel = document.getElementById("wb-format").getBoundingClientRect();
    const r = [...document.querySelectorAll('[data-fmt="ports"]')];
    return {
      shown: r.map((e) => !e.hidden && e.getBoundingClientRect().height > 0), options: document.getElementById("wb-fmt-port").options.length,
      inside: r.every((e) => e.getBoundingClientRect().right <= panel.right + 0.5 && e.scrollWidth <= e.clientWidth + 1),
      widest: Math.max(...r.map((e) => Math.round(e.getBoundingClientRect().width))), panel: Math.round(panel.width),
    };
  });
  check("the three rows show for one shape and list its three ports", rows.shown.every(Boolean) && rows.options === 3, rows);
  check("the rows sit inside the panel with no sideways overflow", rows.inside, rows);

  const undoLen = () => page.evaluate(() => wbUndoStack.length);
  const stored = () => page.evaluate((sid) => JSON.parse(wbFindItem("sketch", sid).data).ports, id);
  const u0 = await undoLen();
  // Wait for the step itself, not a fixed time: an edit made while the last save is running joins its Undo step.
  const settle = (n) => page.waitForFunction(([base, k]) => wbUndoStack.length >= base + k, [u0, n], { timeout: 8000 }).catch(() => {});
  await page.selectOption("#wb-fmt-port", "2");
  await page.fill("#wb-fmt-port-dx", "12");
  await page.dispatchEvent("#wb-fmt-port-dx", "change");
  await settle(1);
  let p = await stored();
  check("typing 12 in the nudge writes dx on the chosen port, one Undo step", p[2].dx === 12 && p[2].dy === 5 && (await undoLen()) === u0 + 1, { p2: p[2], undo: (await undoLen()) - u0 });
  await page.check("#wb-fmt-port-perim");
  await settle(2);
  p = await stored();
  check("On outline writes perimeter, one more Undo step", p[2].perimeter === true && (await undoLen()) === u0 + 2, { p2: p[2], undo: (await undoLen()) - u0 });
  const after = await measure();
  const target = after.find((s) => s.id === id);
  check("the port just held on the outline now lies on it (under 0.5 px)", target.off[2].d < 0.5, target.off[2]);
  await page.selectOption("#wb-fmt-port", "0");
  await page.click("#wb-fmt-port-del");
  await settle(3);
  p = await stored();
  check("Remove takes the chosen port out, one more Undo step", p.length === 2 && (await undoLen()) === u0 + 3, { n: p.length, undo: (await undoLen()) - u0 });
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(600);
  p = await stored();
  check("Undo brings the removed port back", p.length === 3, p.length);

  // Add: press the outline with the editor on.
  await page.click("#wb-fmt-port-add");
  await page.waitForTimeout(200);
  const spot = await page.evaluate((sid) => {
    const s = wbFindItem("sketch", sid), box = wbItemBBox("sketch", s);
    const at = (x, y) => { const pt = document.getElementById("wb-svg-layer").createSVGPoint(); pt.x = x; pt.y = y; const q = pt.matrixTransform(document.getElementById("wb-zoom-group").getScreenCTM()); return { x: q.x, y: q.y }; };
    return at((box.minX + box.maxX) / 2 + 20, box.minY);
  }, id);
  const u1 = await undoLen();
  const before = (await stored()).length;
  await page.mouse.click(spot.x, spot.y);
  await page.waitForTimeout(800);
  p = await stored();
  check("pressing the outline adds a port, one Undo step, and the list grows", p.length === before + 1 && (await undoLen()) === u1 + 1, { before, after: p.length });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const opts = await page.evaluate(() => document.getElementById("wb-fmt-port").options.length);
  check("the list shows the added port", opts === before + 1, opts);

  // Add from the keyboard (review 5883430964): Enter on Add puts a point on the outline after the chosen one.
  await page.selectOption("#wb-fmt-port", "0");
  const u2 = await undoLen();
  const n2 = (await stored()).length;
  await page.focus("#wb-fmt-port-add");
  await page.keyboard.press("Enter");
  await page.waitForFunction(([base]) => wbUndoStack.length >= base + 1, [u2], { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(300);
  p = await stored();
  const keyed = await measure();
  const shape = keyed.find((s) => s.id === id);
  const focused = await page.evaluate(() => document.activeElement && document.activeElement.id);
  check("Enter on Add adds one point after the chosen one, one Undo step, on the outline (under 0.5 px)",
    p.length === n2 + 1 && (await undoLen()) === u2 + 1 && shape.off[1].d < 0.5, { before: n2, after: p.length, d: shape.off[1].d });
  check("the new point is chosen and the nudge field has the keys", focused === "wb-fmt-port-dx" && (await page.inputValue("#wb-fmt-port")) === "1", { focused });

  // A multi-selection hides the rows.
  const hidden = await page.evaluate(() => {
    const ids = wbState.sketches.map((s) => s.id);
    wbMultiSelection.clear(); for (const sid of ids.slice(0, 2)) wbMultiSelection.add(`sketch:${sid}`);
    wbFormatSync();
    return [...document.querySelectorAll('[data-fmt="ports"]')].every((e) => e.hidden);
  });
  check("with two shapes selected the rows are hidden", hidden);

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  summary();
})();
