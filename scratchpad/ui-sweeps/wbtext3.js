// WHITEBOARD_PLAN rows measured on a live board: Insert, Polygon; subscript and superscript; maths in board words;
// the JS-drawn shape table.
//   BASE=http://127.0.0.1:8897 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbtext3.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 1440 });
  const { check, summary } = checker();
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  const at = (dx, dy) => [box.x + box.w / 2 + dx, box.y + box.h / 2 + dy];
  const count = () => page.evaluate(() => wbState.sketches.length);

  // --- Insert, Polygon -------------------------------------------------------------------------------------
  const inMenu = await page.evaluate(() => Boolean(document.querySelector('#wb-insert-menu [data-wb-cmd="insert-polygon"]')));
  check("the Insert menu has a Polygon row", inMenu);
  await page.evaluate(() => wbFmtState.shapesJs.polygonStart());
  for (const [dx, dy] of [[-120, -80], [100, -90], [140, 60]]) { const [x, y] = at(dx, dy); await page.mouse.click(x, y); }
  const live = await page.evaluate(() => document.querySelector("#wb-overlay-zoom-group path[stroke-dasharray]")?.getAttribute("d"));
  check("the corners are previewed while they are placed", /^M .* L .* L /.test(live || ""), live);
  const [lx, ly] = at(-60, 90);
  await page.mouse.dblclick(lx, ly);
  await page.waitForTimeout(600);
  const made = await page.evaluate(() => { const s = wbState.sketches[wbState.sketches.length - 1]; const p = wbSketchParsedData(s); return { n: wbState.sketches.length, d: p.d, ports: wbPortsForPath(p.d, true)?.length, sel: wbSelectedItem?.id === s.id }; });
  check("a double-click closes four corners into one closed path, selected", made.n === 1 && /^M (\S+ \S+ L ){3}\S+ \S+ Z$/.test(made.d) && made.sel, made);
  check("the closed path has corner and side-middle ports", made.ports === 8, made.ports);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(500);
  check("one Undo takes the polygon back", (await count()) === 0);
  await page.evaluate(() => wbFmtState.shapesJs.polygonStart());
  for (const [dx, dy] of [[-50, -50], [50, -50], [0, 50]]) { const [x, y] = at(dx, dy); await page.mouse.click(x, y); }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const gone = await page.evaluate(() => ({ n: wbState.sketches.length, preview: Boolean(document.querySelector("#wb-overlay-zoom-group path[stroke-dasharray]")), on: document.getElementById("whiteboard-container").classList.contains("wb-polygon-on") }));
  check("Escape cancels: nothing saved, preview and cursor gone", gone.n === 0 && !gone.preview && !gone.on, gone);
  await page.evaluate(() => wbFmtState.shapesJs.polygonStart());
  for (const [dx, dy] of [[-50, -50], [50, -50], [0, 50]]) { const [x, y] = at(dx, dy); await page.mouse.click(x, y); }
  await page.keyboard.press("Enter");
  await page.waitForTimeout(600);
  check("Enter closes three corners into a shape", (await count()) === 1);

  // --- Subscript and superscript ---------------------------------------------------------------------------
  const ids = await page.evaluate(async () => {
    const b = window.currentBoardId;
    const out = {};
    out.t = (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Water is H~2~O and x^2^ is ~~gone~~ `a~b~c`", md: true }, board_id: b, x: 100, y: 100, z: 1, width: 360, height: 80 }) })).id;
    out.s = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 1, data: JSON.stringify({ d: "M 100 300 L 360 300 L 360 400 L 100 400 Z", color: "#333", width: 2, shape: "rectangle", label: "CO~2~ and m^2^" }) }) })).id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return out;
  });
  await page.waitForTimeout(700);
  const rich = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"] .wb-text-content`);
    const sub = el.querySelector("sub"), sup = el.querySelector("sup");
    const base = el.querySelector("p, div") || el;
    return { sub: sub?.textContent, sup: sup?.textContent, del: Boolean(el.querySelector("del, s")), code: el.querySelector("code")?.textContent, subTop: sub?.getBoundingClientRect().bottom, supTop: sup?.getBoundingClientRect().top, rowTop: base.getBoundingClientRect().top, text: el.textContent };
  }, ids.t);
  check("H~2~O gives a <sub> 2 and x^2^ a <sup> 2 in a text box", rich.sub === "2" && rich.sup === "2", rich);
  check("strikethrough and code keep their markers (no sub inside code)", rich.del && rich.code === "a~b~c", rich);
  check("no marker characters are left around the raised or lowered ones", !/H~2~O|x\^2\^/.test(rich.text), rich.text);
  const label = await page.evaluate((id) => {
    const lab = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-label`);
    const spans = [...lab.querySelectorAll("tspan tspan")];
    return { text: lab.textContent, n: spans.length, sizes: spans.map((s) => s.getAttribute("font-size")), dys: spans.map((s) => s.getAttribute("dy")) };
  }, ids.s);
  check("a shape label draws CO2 and m2 with the 2 lowered and raised", label.text.replace(/\s/g, "") === "CO2andm2" && label.dys.includes("7") === false && label.sizes.length >= 2 && label.sizes.every((s) => Number(s) < 16), label);
  const exported = await page.evaluate(() => wbBuildExportSvg("whole").svg);
  check("the SVG export keeps the raised and lowered label characters", /<tspan[^>]*dy="-?\d[^"]*"[^>]*font-size/.test(exported) || /font-size="[\d.]+"[^>]*dy=/.test(exported), exported.slice(exported.indexOf("sketch-label"), exported.indexOf("sketch-label") + 400));
  check("the SVG export writes the text box's 2 as a smaller, shifted tspan", /<tspan x="[\d.]+" y="[\d.]+" font-size="11\.2"/.test(exported), (exported.match(/<tspan[^>]*font-size="11[^>]*>/g) || []).slice(0, 2));

  // --- Maths in words --------------------------------------------------------------------------------------
  const m = await page.evaluate(async () => {
    const b = window.currentBoardId;
    const mk = (data) => apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 1, data: JSON.stringify(data) }) });
    const shape = await mk({ d: "M 500 300 L 800 300 L 800 420 L 500 420 Z", color: "#333", width: 2, shape: "rectangle", label: "Area $x^2 + \\frac{a}{b}$ and $5 or $10" });
    const prose = await mk({ d: "M 500 460 L 800 460 L 800 540 L 500 540 Z", color: "#333", width: 2, shape: "rectangle", label: "costs $5 or $10" });
    const text = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Sum $\\sum_{i=1}^n i$", md: true }, board_id: b, x: 100, y: 500, z: 1, width: 300, height: 60 }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 700));
    const g = (id) => document.querySelector(`.sketch-group[data-id="${id}"]`);
    const fo = g(shape.id).querySelector(":scope > .sketch-label-math");
    const lab = g(shape.id).querySelector(":scope > .sketch-label");
    const path = g(shape.id).querySelector(".sketch-path").getBBox();
    const foBox = fo && fo.getBoundingClientRect();
    const pBox = g(shape.id).querySelector(".sketch-path").getBoundingClientRect();
    return {
      math: fo ? fo.querySelectorAll("math").length : 0,
      opacity: lab.style.opacity,
      inside: Boolean(fo) && foBox.left >= pBox.left - 1 && foBox.right <= pBox.right + 1 && foBox.top >= pBox.top - 1 && foBox.bottom <= pBox.bottom + 1,
      mathH: fo?.querySelector("math")?.getBoundingClientRect().height,
      proseFo: Boolean(g(prose.id).querySelector(":scope > .sketch-label-math")),
      proseOpacity: g(prose.id).querySelector(":scope > .sketch-label").style.opacity,
      boxMath: document.querySelectorAll(`.wb-object[data-id="${text.id}"] math`).length,
      svg: wbBuildExportSvg("whole").svg,
    };
  });
  check("a shape label draws $x^2 + \\frac{a}{b}$ as MathML over the shape", m.math === 1 && m.opacity === "0" && m.mathH > 8, { math: m.math, opacity: m.opacity, mathH: m.mathH });
  check("the maths stays inside the shape's box", m.inside);
  check("prose with two dollar amounts is not maths", !m.proseFo && m.proseOpacity === "", { fo: m.proseFo, op: m.proseOpacity });
  check("a text box that shows markdown draws $\\sum$ as MathML", m.boxMath === 1, m.boxMath);
  check("the SVG export falls back to the source words, no foreignObject", !/foreignObject/.test(m.svg) && m.svg.includes("x^2 + \\frac{a}{b}"), m.svg.includes("foreignObject"));
  const vis = await page.evaluate(() => /opacity:\s*0/.test(wbBuildExportSvg("whole").svg));
  check("the exported label is visible (the live hiding style is not cloned)", !vis);
  await page.evaluate(() => wbUndo());


  // --- The JS-drawn shape table ---------------------------------------------------------------------------
  const rows = await page.evaluate(async () => { await wbLoadLibrary({ force: true }); return wbLibEntries().filter((e) => e.set === "Drawn shapes").map((e) => e.name); });
  check("the shape picker's rows include 20 or more drawn shapes", rows.length >= 20 && rows.includes("Step") && rows.includes("Cylinder"), rows.length);
  const placed = await page.evaluate(async () => {
    const entry = wbLibEntries().find((e) => e.ref === "builtin:shapes-js/step");
    await wbLibPlace(entry, [300, 700]);
    await new Promise((r) => setTimeout(r, 600));
    const s = wbState.sketches[wbState.sketches.length - 1];
    const p = wbSketchParsedData(s);
    wbSelectedItem = null;
    selectWbItem("sketch", s.id);
    return { id: s.id, kind: p.shapeKind, shape: p.shape, box: wbPathBBox(p.d) };
  });
  check("a placed Step keeps its kind in shapeKind and is a fillable custom shape", placed.kind === "step" && placed.shape === "custom", placed);
  await page.waitForTimeout(400);
  const grip = await page.evaluate((id) => {
    const h = document.querySelector('.wb-sketch-resize-handle[data-handle="e"]');
    if (!h) return null;
    const r = h.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, placed.id);
  if (grip) {
    await page.mouse.move(grip.x, grip.y);
    await page.mouse.down();
    await page.mouse.move(grip.x + 120, grip.y, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(700);
  }
  const grown = await page.evaluate((id) => { const p = wbSketchParsedData(wbState.sketches.find((x) => x.id === id)); const box = wbPathBBox(p.d); const t = wbFmtState.shapeTable; return { w: box.maxX - box.minX, h: box.maxY - box.minY, same: p.d === t.shapePathAt("step", box.minX, box.minY, box.maxX - box.minX, box.maxY - box.minY) }; }, placed.id);
  check("dragging the east grip widens the Step by about 120 and draws the outline again (the notch keeps its size)", Boolean(grip) && grown.w > (placed.box.maxX - placed.box.minX) + 80 && grown.same, { grip: Boolean(grip), grown, was: placed.box });
  const out = await page.evaluate(() => {
    const t = wbFmtState.shapeTable;
    return t.kinds.map((k) => t.toDrawio(k));
  });
  check("every kind has a draw.io shape word", out.every((w) => /^shape=[A-Za-z0-9.]+;/.test(w)), out.slice(0, 3));
  const rt = await page.evaluate(async () => {
    const made = wbBoardToDrawio(wbState, { title: "t", box: wbItemBBox, hidden: wbItemHidden });
    const hasStep = /style="shape=step;/.test(made.xml);
    const cells = (await wbDrawioCells(made.xml)).all[0].cells;
    const plan = wbDrawioPlan(cells);
    const item = plan.items.find((i) => i.shape === "step");
    const data = item ? wbDrawioStyle.more.shapeData(item, 0, 0, "#333333") : null;
    const file = '<mxfile><diagram name="p"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" value="db" style="shape=cylinder3;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="80" height="120" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>';
    const cyl = wbDrawioPlan((await wbDrawioCells(file)).all[0].cells);
    return { hasStep, kind: item?.shape, shapeKind: data?.shapeKind, closed: /Z/.test(data?.d || ""), cyl: cyl.items[0]?.shape, skipped: made.skipped, dropped: cyl.dropped };
  });
  check("the draw.io export writes the Step as shape=step and reading it back gives the Step", rt.hasStep && rt.kind === "step" && rt.shapeKind === "step" && rt.closed, rt);
  check("shape=cylinder3 from draw.io becomes the table's cylinder, not a dropped box", rt.cyl === "cylinder" && !Object.keys(rt.dropped || {}).some((k) => /cylinder/.test(k)), rt);

  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
