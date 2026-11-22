(() => {
  // whiteboard-shape-table.js: draw.io's JS-drawn shape classes (`Shapes.js` `redrawPath`: cylinder3, cube, callout, step,
  // umlActor, umlLifeline, folder, note, tape, document, process...) as one table of parametric outlines
  // (WHITEBOARD_PLAN section 11). `shapePath(kind, w, h)` returns M, L, C and Z only, at the origin, so the ports, the hit test
  // and the box all read it. `data.shapeKind` names the table entry (`data.shape` stays `custom`, the fillable kind), so a resize
  // draws the outline again for the new box and keeps the corner sizes (a scaled path would stretch them). Held on
  // `wbFmtState.shapeTable`, so no global name is added; the picker and the library panel read the set `shapes-js.json` it
  // makes (`setFile`), and the draw.io import and export name the kinds in `drawio`.

  const K = 0.5523; // a quarter of a circle as one cubic
  const r2 = (n) => Math.round(n * 100) / 100;
  const P = (pts) => pts.map(([x, y]) => `${r2(x)} ${r2(y)}`).join(" L ");
  const poly = (pts) => `M ${P(pts)} Z`;
  const seg = (a, b, c, d) => `C ${r2(a[0])} ${r2(a[1])} ${r2(b[0])} ${r2(b[1])} ${r2(c)} ${r2(d)}`;
  //: A full ellipse inside (x, y, w, h) as four cubics; every extreme is a point on the curve.
  const ellipse = (x, y, w, h) => {
    const rx = w / 2, ry = h / 2, cx = x + rx, cy = y + ry;
    return `M ${r2(cx)} ${r2(y)} ${seg([cx + rx * K, y], [x + w, cy - ry * K], x + w, cy)} ${seg([x + w, cy + ry * K], [cx + rx * K, y + h], cx, y + h)} ` +
      `${seg([cx - rx * K, y + h], [x, cy + ry * K], x, cy)} ${seg([x, cy - ry * K], [cx - rx * K, y], cx, y)} Z`;
  };
  //: A half ellipse's rim (open): from (x, y) through the bottom to (x + w, y), the front edge of a can's top.
  const rim = (w, y, ry, dir) => `M 0 ${r2(y)} ${seg([0, y + dir * ry * K], [w / 2 - (w / 2) * K, y + dir * ry], w / 2, y + dir * ry)} ${seg([w / 2 + (w / 2) * K, y + dir * ry], [w, y + dir * ry * K], w, y)}`;

  function cylinder(w, h) {
    const ry = Math.min(h / 4, Math.max(2, h * 0.13)), rx = w / 2;
    const top = `M 0 ${r2(ry)} ${seg([0, ry - ry * K], [rx - rx * K, 0], rx, 0)} ${seg([rx + rx * K, 0], [w, ry - ry * K], w, ry)}`;
    const body = `L ${r2(w)} ${r2(h - ry)} ${seg([w, h - ry + ry * K], [rx + rx * K, h], rx, h)} ${seg([rx - rx * K, h], [0, h - ry + ry * K], 0, h - ry)} Z`;
    return `${top} ${body} ${rim(w, ry, ry, 1)}`;
  }
  function tube(w, h) {
    const rx = Math.min(w / 4, Math.max(2, w * 0.13)), ry = h / 2;
    const left = `M ${r2(rx)} 0 ${seg([rx - rx * K, 0], [0, ry - ry * K], 0, ry)} ${seg([0, ry + ry * K], [rx - rx * K, h], rx, h)}`;
    const body = `L ${r2(w - rx)} ${r2(h)} ${seg([w - rx + rx * K, h], [w, ry + ry * K], w, ry)} ${seg([w, ry - ry * K], [w - rx + rx * K, 0], w - rx, 0)} Z`;
    const front = `M ${r2(w - rx)} 0 ${seg([w - rx - rx * K, 0], [w - 2 * rx, ry - ry * K], w - 2 * rx, ry)} ${seg([w - 2 * rx, ry + ry * K], [w - rx - rx * K, h], w - rx, h)}`;
    return `${left} ${body} ${front}`;
  }

  //: Each kind: `name`, `drawio` (the `shape=` key; `extra` style written beside it), `size` (the library tile), `area` (the
  //: words, as fractions of the box) and `d(w, h)`.
  const T = [
    { kind: "cylinder", name: "Cylinder", drawio: "cylinder3", tags: ["database", "storage"], size: [100, 130], area: { x: 0, y: 0.25, w: 1, h: 0.65 }, d: cylinder },
    { kind: "tube", name: "Tube", drawio: "cylinder3", extra: "direction=south;", tags: ["pipe", "queue"], size: [160, 90], area: { x: 0.2, y: 0, w: 0.7, h: 1 }, d: tube },
    {
      kind: "cube", name: "Cube", drawio: "cube", tags: ["box", "3d"], size: [140, 120], area: { x: 0, y: 0.25, w: 0.75, h: 0.75 },
      d: (w, h) => { const e = Math.min(w, h) * 0.25; return `${poly([[0, e], [e, 0], [w, 0], [w, h - e], [w - e, h], [0, h]])} M 0 ${r2(e)} L ${r2(w - e)} ${r2(e)} L ${r2(w)} 0 M ${r2(w - e)} ${r2(e)} L ${r2(w - e)} ${r2(h)}`; },
    },
    {
      kind: "callout", name: "Callout", drawio: "callout", tags: ["speech", "bubble"], size: [160, 110], area: { x: 0, y: 0, w: 1, h: 0.75 },
      d: (w, h) => { const t = Math.min(h * 0.25, 30), b = h - t; return poly([[0, 0], [w, 0], [w, b], [0.35 * w, b], [0.2 * w, h], [0.25 * w, b], [0, b]]); },
    },
    {
      kind: "step", name: "Step", drawio: "step", tags: ["chevron", "process"], size: [160, 80], area: { x: 0.18, y: 0, w: 0.64, h: 1 },
      d: (w, h) => { const n = Math.min(h / 2, w / 4); return poly([[0, 0], [w - n, 0], [w, h / 2], [w - n, h], [0, h], [n, h / 2]]); },
    },
    {
      kind: "actor", name: "Actor", drawio: "umlActor", tags: ["uml", "person", "stick figure"], size: [50, 110], area: { x: 0, y: 0.6, w: 1, h: 0.4 },
      d: (w, h) => {
        const ry = h * 0.17, rx = Math.min(w / 2, ry), cx = w / 2, neck = 2 * ry, hip = h * 0.62;
        return `${ellipse(cx - rx, 0, 2 * rx, 2 * ry)} M ${r2(cx)} ${r2(neck)} L ${r2(cx)} ${r2(hip)} M 0 ${r2(h * 0.36)} L ${r2(w)} ${r2(h * 0.36)} M ${r2(cx)} ${r2(hip)} L 0 ${r2(h)} M ${r2(cx)} ${r2(hip)} L ${r2(w)} ${r2(h)}`;
      },
    },
    {
      kind: "lifeline", name: "Lifeline", drawio: "umlLifeline", tags: ["uml", "sequence"], size: [100, 180], area: { x: 0, y: 0, w: 1, h: 0.2 },
      d: (w, h) => { const hb = Math.min(h * 0.2, 40); return `${poly([[0, 0], [w, 0], [w, hb], [0, hb]])} M ${r2(w / 2)} ${r2(hb)} L ${r2(w / 2)} ${r2(h)}`; },
    },
    {
      kind: "folder", name: "Folder", drawio: "folder", tags: ["directory", "package"], size: [160, 110], area: { x: 0, y: 0.2, w: 1, h: 0.8 },
      d: (w, h) => { const tw = Math.min(w * 0.4, 70), th = Math.min(h * 0.15, 18); return poly([[0, 0], [tw, 0], [tw + th, th], [w, th], [w, h], [0, h]]); },
    },
    {
      kind: "note", name: "Note", drawio: "note", tags: ["page", "sticky", "dog ear"], size: [130, 110], area: { x: 0, y: 0.15, w: 1, h: 0.85 },
      d: (w, h) => { const f = Math.min(w, h) * 0.2; return `${poly([[0, 0], [w - f, 0], [w, f], [w, h], [0, h]])} M ${r2(w - f)} 0 L ${r2(w - f)} ${r2(f)} L ${r2(w)} ${r2(f)}`; },
    },
    {
      kind: "tape", name: "Tape", drawio: "tape", tags: ["scroll", "banner"], size: [160, 90], area: { x: 0, y: 0.2, w: 1, h: 0.6 },
      d: (w, h) => {
        const a = Math.min(h * 0.1, 16);
        return `M 0 ${r2(a)} ${seg([w / 8, a], [w / 8, 0], w / 4, 0)} ${seg([3 * w / 8, 0], [3 * w / 8, a], w / 2, a)} ${seg([5 * w / 8, a], [5 * w / 8, 2 * a], 3 * w / 4, 2 * a)} ${seg([7 * w / 8, 2 * a], [7 * w / 8, a], w, a)} ` +
          `L ${r2(w)} ${r2(h - a)} ${seg([7 * w / 8, h - a], [7 * w / 8, h], 3 * w / 4, h)} ${seg([5 * w / 8, h], [5 * w / 8, h - a], w / 2, h - a)} ${seg([3 * w / 8, h - a], [3 * w / 8, h - 2 * a], w / 4, h - 2 * a)} ${seg([w / 8, h - 2 * a], [w / 8, h - a], 0, h - a)} Z`;
      },
    },
    {
      kind: "document", name: "Document", drawio: "document", tags: ["page", "file", "flowchart"], size: [140, 110], area: { x: 0, y: 0, w: 1, h: 0.8 },
      d: (w, h) => {
        const a = Math.min(h * 0.12, 16);
        return `M 0 0 L ${r2(w)} 0 L ${r2(w)} ${r2(h - a)} ${seg([7 * w / 8, h - a], [7 * w / 8, h], 3 * w / 4, h)} ${seg([5 * w / 8, h], [5 * w / 8, h - a], w / 2, h - a)} ${seg([3 * w / 8, h - a], [3 * w / 8, h - 2 * a], w / 4, h - 2 * a)} ${seg([w / 8, h - 2 * a], [w / 8, h - a], 0, h - a)} Z`;
      },
    },
    {
      kind: "process", name: "Process", drawio: "process", tags: ["predefined process", "flowchart"], size: [160, 90], area: { x: 0.12, y: 0, w: 0.76, h: 1 },
      d: (w, h) => { const i = Math.min(w * 0.125, 22); return `${poly([[0, 0], [w, 0], [w, h], [0, h]])} M ${r2(i)} 0 L ${r2(i)} ${r2(h)} M ${r2(w - i)} 0 L ${r2(w - i)} ${r2(h)}`; },
    },
    {
      kind: "internal-storage", name: "Internal storage", drawio: "internalStorage", tags: ["memory", "flowchart"], size: [140, 100], area: { x: 0.12, y: 0.15, w: 0.88, h: 0.85 },
      d: (w, h) => { const i = Math.min(w * 0.1, 20), j = Math.min(h * 0.12, 20); return `${poly([[0, 0], [w, 0], [w, h], [0, h]])} M ${r2(i)} 0 L ${r2(i)} ${r2(h)} M 0 ${r2(j)} L ${r2(w)} ${r2(j)}`; },
    },
    {
      kind: "trapezoid", name: "Trapezoid", drawio: "trapezoid", tags: ["manual operation", "flowchart"], size: [160, 90], area: { x: 0.2, y: 0, w: 0.6, h: 1 },
      d: (w, h) => poly([[Math.min(w * 0.2, h), 0], [w - Math.min(w * 0.2, h), 0], [w, h], [0, h]]),
    },
    {
      kind: "card", name: "Card", drawio: "card", tags: ["punched card", "flowchart"], size: [140, 100], area: { x: 0, y: 0.2, w: 1, h: 0.8 },
      d: (w, h) => { const c = Math.min(w, h) * 0.2; return poly([[c, 0], [w, 0], [w, h], [0, h], [0, c]]); },
    },
    {
      kind: "loop-limit", name: "Loop limit", drawio: "loopLimit", tags: ["flowchart", "loop"], size: [150, 80], area: { x: 0, y: 0.15, w: 1, h: 0.85 },
      d: (w, h) => { const c = Math.min(w, h) * 0.2; return poly([[c, 0], [w - c, 0], [w, c], [w, h], [0, h], [0, c]]); },
    },
    { kind: "or", name: "Or", drawio: "or", tags: ["flowchart", "junction"], size: [70, 70], area: { x: 0.15, y: 0.15, w: 0.7, h: 0.7 }, d: (w, h) => `${ellipse(0, 0, w, h)} M ${r2(w / 2)} 0 L ${r2(w / 2)} ${r2(h)} M 0 ${r2(h / 2)} L ${r2(w)} ${r2(h / 2)}` },
    {
      kind: "sum", name: "Summing junction", drawio: "sumEllipse", tags: ["flowchart", "junction"], size: [70, 70], area: { x: 0.15, y: 0.15, w: 0.7, h: 0.7 },
      d: (w, h) => { const o = (1 - Math.SQRT1_2) / 2; return `${ellipse(0, 0, w, h)} M ${r2(o * w)} ${r2(o * h)} L ${r2(w - o * w)} ${r2(h - o * h)} M ${r2(w - o * w)} ${r2(o * h)} L ${r2(o * w)} ${r2(h - o * h)}`; },
    },
    {
      kind: "cross", name: "Cross", drawio: "cross", tags: ["plus", "add"], size: [100, 100], area: { x: 0.33, y: 0.33, w: 0.34, h: 0.34 },
      d: (w, h) => { const a = Math.min(w, h) / 3, x1 = (w - a) / 2, x2 = (w + a) / 2, y1 = (h - a) / 2, y2 = (h + a) / 2; return poly([[x1, 0], [x2, 0], [x2, y1], [w, y1], [w, y2], [x2, y2], [x2, h], [x1, h], [x1, y2], [0, y2], [0, y1], [x1, y1]]); },
    },
    { kind: "offpage", name: "Off-page connector", drawio: "offPageConnector", tags: ["flowchart", "pentagon"], size: [90, 100], area: { x: 0, y: 0, w: 1, h: 0.75 }, d: (w, h) => poly([[0, 0], [w, 0], [w, 0.75 * h], [w / 2, h], [0, 0.75 * h]]) },
    { kind: "manual-input", name: "Manual input", drawio: "manualInput", tags: ["flowchart", "keyboard"], size: [150, 90], area: { x: 0, y: 0.2, w: 1, h: 0.8 }, d: (w, h) => poly([[0, 0.2 * h], [w, 0], [w, h], [0, h]]) },
    {
      kind: "delay", name: "Delay", drawio: "delay", tags: ["flowchart", "wait"], size: [140, 90], area: { x: 0, y: 0, w: 0.8, h: 1 },
      d: (w, h) => `M 0 0 L ${r2(w / 2)} 0 ${seg([w / 2 + (w / 2) * K, 0], [w, h / 2 - (h / 2) * K], w, h / 2)} ${seg([w, h / 2 + (h / 2) * K], [w / 2 + (w / 2) * K, h], w / 2, h)} L 0 ${r2(h)} Z`,
    },
    { kind: "pentagon", name: "Pentagon", drawio: "mxgraph.basic.pentagon", tags: ["polygon"], size: [110, 105], area: { x: 0.2, y: 0.3, w: 0.6, h: 0.6 }, d: (w, h) => poly([[w / 2, 0], [w, 0.382 * h], [0.809 * w, h], [0.191 * w, h], [0, 0.382 * h]]) },
    { kind: "octagon", name: "Octagon", drawio: "mxgraph.basic.octagon", tags: ["polygon", "stop"], size: [110, 110], area: { x: 0.1, y: 0.1, w: 0.8, h: 0.8 }, d: (w, h) => { const c = Math.min(w, h) * 0.29; return poly([[c, 0], [w - c, 0], [w, c], [w, h - c], [w - c, h], [c, h], [0, h - c], [0, c]]); } },
    {
      kind: "uml-frame", name: "UML frame", drawio: "umlFrame", tags: ["uml", "frame", "diagram"], size: [200, 140], area: { x: 0, y: 0.15, w: 1, h: 0.85 },
      d: (w, h) => { const tw = Math.min(w * 0.35, 90), th = Math.min(h * 0.15, 26), s = th / 3; return `${poly([[0, 0], [w, 0], [w, h], [0, h]])} M 0 ${r2(th)} L ${r2(tw - s)} ${r2(th)} L ${r2(tw)} ${r2(th - s)} L ${r2(tw)} 0`; },
    },
    //: L-whiteboard-29: the last fifteen of the plan's forty, each a `Shapes.js` class (or its mxgraph stencil) by its draw.io name.
    {
      kind: "data-storage", name: "Data storage", drawio: "dataStorage", tags: ["flowchart", "stored data"], size: [150, 90], area: { x: 0.1, y: 0, w: 0.75, h: 1 },
      d: (w, h) => { const a = Math.min(w * 0.1, 18); return `M ${r2(a)} 0 L ${r2(w)} 0 ${seg([w - a * 2 * K, 0], [w - a, h / 2 - (h / 2) * K], w - a, h / 2)} ${seg([w - a, h / 2 + (h / 2) * K], [w - a * 2 * K, h], w, h)} L ${r2(a)} ${r2(h)} ${seg([a - a * K, h], [0, h / 2 + (h / 2) * K], 0, h / 2)} ${seg([0, h / 2 - (h / 2) * K], [a - a * K, 0], a, 0)} Z`; },
    },
    {
      kind: "display", name: "Display", drawio: "display", tags: ["flowchart", "screen"], size: [150, 90], area: { x: 0.15, y: 0, w: 0.7, h: 1 },
      d: (w, h) => { const a = Math.min(w * 0.15, 30); return `M 0 ${r2(h / 2)} L ${r2(a)} 0 L ${r2(w - a)} 0 ${seg([w - a + a * K, 0], [w, h / 2 - (h / 2) * K], w, h / 2)} ${seg([w, h / 2 + (h / 2) * K], [w - a + a * K, h], w - a, h)} L ${r2(a)} ${r2(h)} Z`; },
    },
    {
      kind: "corner", name: "Corner", drawio: "corner", tags: ["l shape", "wall"], size: [100, 100], area: { x: 0.2, y: 0.2, w: 0.8, h: 0.8 },
      d: (w, h) => { const a = Math.min(w, h) * 0.2; return poly([[0, 0], [w, 0], [w, a], [a, a], [a, h], [0, h]]); },
    },
    {
      kind: "tee", name: "Tee", drawio: "tee", tags: ["t shape"], size: [120, 100], area: { x: 0, y: 0, w: 1, h: 0.25 },
      d: (w, h) => { const a = Math.min(h * 0.25, h), b = Math.min(w * 0.2, w), x1 = (w - b) / 2; return poly([[0, 0], [w, 0], [w, a], [x1 + b, a], [x1 + b, h], [x1, h], [x1, a], [0, a]]); },
    },
    {
      kind: "single-arrow", name: "Arrow", drawio: "singleArrow", tags: ["arrow", "direction"], size: [160, 80], area: { x: 0, y: 0.3, w: 0.75, h: 0.4 },
      d: (w, h) => { const hw = Math.min(w * 0.3, h), s = h * 0.3; return poly([[0, s], [w - hw, s], [w - hw, 0], [w, h / 2], [w - hw, h], [w - hw, h - s], [0, h - s]]); },
    },
    {
      kind: "double-arrow", name: "Double arrow", drawio: "doubleArrow", tags: ["arrow", "both ways"], size: [180, 80], area: { x: 0.25, y: 0.3, w: 0.5, h: 0.4 },
      d: (w, h) => { const hw = Math.min(w * 0.25, h), s = h * 0.3; return poly([[0, h / 2], [hw, 0], [hw, s], [w - hw, s], [w - hw, 0], [w, h / 2], [w - hw, h], [w - hw, h - s], [hw, h - s], [hw, h]]); },
    },
    {
      kind: "xor", name: "Exclusive or", drawio: "xor", tags: ["flowchart", "logic gate"], size: [100, 80], area: { x: 0.3, y: 0.2, w: 0.5, h: 0.6 },
      d: (w, h) => { const b = w * 0.1; return `M 0 0 ${seg([w * 0.5, 0], [w * 0.8, h * 0.2], w, h / 2)} ${seg([w * 0.8, h * 0.8], [w * 0.5, h], 0, h)} ${seg([b * 2, h * 0.7], [b * 2, h * 0.3], 0, 0)} Z`; },
    },
    {
      kind: "tape-data", name: "Tape data", drawio: "tapeData", tags: ["flowchart", "sequential data"], size: [100, 100], area: { x: 0.15, y: 0.15, w: 0.7, h: 0.7 },
      d: (w, h) => { const rx = w / 2, ry = h / 2; return `M ${r2(rx)} ${r2(h)} ${seg([rx - rx * K, h], [0, ry + ry * K], 0, ry)} ${seg([0, ry - ry * K], [rx - rx * K, 0], rx, 0)} ${seg([rx + rx * K, 0], [w, ry - ry * K], w, ry)} ${seg([w, ry + ry * K], [rx + rx * K, h], rx, h)} Z M ${r2(rx)} ${r2(h)} L ${r2(w)} ${r2(h)}`; },
    },
    {
      kind: "iso-rectangle", name: "Isometric square", drawio: "isoRectangle", tags: ["isometric", "tile"], size: [140, 80], area: { x: 0.25, y: 0.25, w: 0.5, h: 0.5 },
      d: (w, h) => poly([[w / 2, 0], [w, h / 2], [w / 2, h], [0, h / 2]]),
    },
    {
      kind: "iso-cube", name: "Isometric cube", drawio: "isoCube2", tags: ["isometric", "box", "3d"], size: [100, 115], area: { x: 0.1, y: 0.35, w: 0.8, h: 0.5 },
      d: (w, h) => { const a = Math.min(h * 0.25, w * 0.29); return `${poly([[w / 2, 0], [w, a], [w, h - a], [w / 2, h], [0, h - a], [0, a]])} M 0 ${r2(a)} L ${r2(w / 2)} ${r2(2 * a)} L ${r2(w)} ${r2(a)} M ${r2(w / 2)} ${r2(2 * a)} L ${r2(w / 2)} ${r2(h)}`; },
    },
    {
      kind: "crossbar", name: "Crossbar", drawio: "crossbar", tags: ["dimension", "span"], size: [160, 40], area: { x: 0, y: 0, w: 1, h: 0.4 },
      d: (w, h) => `${poly([[0, 0], [Math.min(2, w), 0], [Math.min(2, w), h], [0, h]])} M 0 ${r2(h / 2)} L ${r2(w)} ${r2(h / 2)} ${poly([[Math.max(w - 2, 0), 0], [w, 0], [w, h], [Math.max(w - 2, 0), h]])}`,
    },
    {
      kind: "curly-bracket", name: "Curly bracket", drawio: "curlyBracket", tags: ["brace", "group"], size: [30, 140], area: { x: 0, y: 0, w: 1, h: 1 },
      d: (w, h) => `M ${r2(w)} 0 ${seg([w / 2, 0], [w / 2, 0], w / 2, h * 0.1)} L ${r2(w / 2)} ${r2(h * 0.4)} ${seg([w / 2, h / 2], [w / 2, h / 2], 0, h / 2)} ${seg([w / 2, h / 2], [w / 2, h / 2], w / 2, h * 0.6)} L ${r2(w / 2)} ${r2(h * 0.9)} ${seg([w / 2, h], [w / 2, h], w, h)} Z`,
    },
    {
      kind: "module", name: "Module", drawio: "module", tags: ["uml", "component", "package"], size: [150, 100], area: { x: 0.15, y: 0, w: 0.85, h: 1 },
      d: (w, h) => { const a = Math.min(w * 0.2, 20), t = Math.min(h * 0.12, 12); return `${poly([[a / 2, 0], [w, 0], [w, h], [a / 2, h]])} ${poly([[0, t], [a, t], [a, 2 * t], [0, 2 * t]])} ${poly([[0, 3 * t], [a, 3 * t], [a, 4 * t], [0, 4 * t]])}`; },
    },
    {
      kind: "component", name: "Component", drawio: "component", tags: ["uml", "module"], size: [150, 90], area: { x: 0, y: 0, w: 0.8, h: 1 },
      d: (w, h) => { const a = Math.min(w * 0.12, 20), b = Math.min(h * 0.15, 12); return `${poly([[0, 0], [w, 0], [w, h], [0, h]])} ${poly([[w - 2 * a, b], [w - a, b], [w - a, 2 * b], [w - 2 * a, 2 * b]])}`; },
    },
    {
      kind: "lollipop", name: "Provided interface", drawio: "lollipop", tags: ["uml", "interface", "ball"], size: [80, 40], area: { x: 0, y: 0, w: 1, h: 1 },
      d: (w, h) => { const rx = Math.min(w / 2, h / 2); return `M 0 ${r2(h / 2)} L ${r2(w - 2 * rx)} ${r2(h / 2)} ${ellipse(w - 2 * rx, 0, 2 * rx, h)}`; },
    },
  ];

  const byKind = new Map(T.map((t) => [t.kind, t]));
  //: draw.io's `shape=` words to the table's kinds (`cylinder` and `cylinder2` are the older cans, `actor` the fat figure).
  const FROM = new Map([["cylinder", "cylinder"], ["cylinder2", "cylinder"], ["cylinder3", "cylinder"], ["actor", "actor"]]);
  for (const t of T) if (!t.extra) FROM.set(t.drawio, t.kind);

  //: Pure (node-tested): the outline of `kind` in a w by h box at the origin, or null for a kind the table does not hold.
  function shapePath(kind, w, h) {
    const t = byKind.get(kind);
    if (!t) return null;
    return t.d(Math.max(Number(w) || 0, 1), Math.max(Number(h) || 0, 1));
  }
  //: The outline with its top-left corner at (x, y): plain numbers, so a path of M, L, C and Z shifts by token.
  function shapePathAt(kind, x, y, w, h) {
    const d = shapePath(kind, w, h);
    if (!d) return null;
    let at = 0;
    return d.replace(/-?\d*\.?\d+/g, (n) => r2(Number(n) + (at++ % 2 ? y : x)));
  }
  //: Pure: the table's kind for a draw.io style (as `wbDrawioStyle` parsed it), or "".
  function fromDrawio(style) {
    const word = style?.shape || style?._kind || "";
    if (word === "cylinder3" && /^(south|north)$/.test(style?.direction || "")) return "tube";
    return FROM.get(word) || "";
  }
  //: Pure: the style words that draw `kind` in draw.io, or "".
  const toDrawio = (kind) => (byKind.has(kind) ? `shape=${byKind.get(kind).drawio};${byKind.get(kind).extra || ""}` : "");

  const nums = (d) => String(d).match(/-?\d*\.?\d+/g)?.map(Number) || [];
  //: After a resize: when the shape's old outline is still exactly what the table draws for its old box (it was not edited
  //: point by point or turned), the table's outline for the new box, placed at the new corner; else null and the board keeps
  //: the stretched path. `bbox` reads a path's box; `moved` is the stretched path.
  function afterResize(kind, oldD, moved, bbox, move) {
    if (!byKind.has(kind) || !oldD || !moved) return null;
    const was = bbox(oldD), now = bbox(moved);
    if (!was || !now) return null;
    const w = was.maxX - was.minX, h = was.maxY - was.minY;
    const same = shapePath(kind, w, h);
    const a = nums(oldD), b = nums(same);
    if (!same || a.length !== b.length || a.some((n, i) => Math.abs(n - (b[i] + (i % 2 ? was.minY : was.minX))) > 0.6)) return null;
    return move(shapePath(kind, now.maxX - now.minX, now.maxY - now.minY), { dx: now.minX, dy: now.minY });
  }

  //: A path resized by `t` (the board's stretch: `transform(d, t)`): the stretched path, or, for a table kind that was not turned,
  //: the table's outline for the new box.
  function resized(d, t, kind, transform, bbox) {
    const stretched = transform(d, t);
    if (!kind || t.rotate) return stretched;
    return afterResize(kind, d, stretched, bbox, (shape, o) => transform(shape, o)) || stretched;
  }

  //: The built-in library set `frontend/board-library/shapes-js.json` (the server places built-ins from files, so the picker and the
  //: panel read this set like any other); `tests/test_wb_shape_table.py` fails when the file is not what this table makes.
  function setFile() {
    const items = T.map((t) => {
      const [w, h] = t.size;
      const data = { d: t.d(w, h), shape: "custom", shapeKind: t.kind, label_area: t.area, color: "ink", width: 2, fill: "ink", fillOpacity: 0.12 };
      return { key: t.kind, kind: "element", name: t.name, tags: [...t.tags, "drawn"], payload: { box: { w, h }, items: [{ key: "s", kind: "sketch", data, z: 5 }], links: [] } };
    });
    return { format: "memorymap-library-set", version: 1, key: "shapes-js", name: "Drawn shapes", items };
  }

  wbFmtState.shapeTable = { kinds: T.map((t) => t.kind), shapePath, shapePathAt, fromDrawio, toDrawio, afterResize, resized, setFile, area: (kind) => byKind.get(kind)?.area || null };
})();
