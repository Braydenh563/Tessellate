(() => {
  // whiteboard-ink-recognise.js: turn a rough hand-drawn stroke into a clean shape (L-whiteboard-3). The recogniser is pure
  // (node-tested in tests/test_wb_ink_recognise.py); the command that applies it is `wbFmtState.inkRecognise.cleanup`.
  // It reads the stroke's own points (`pts` in the sketch's data, kept by the pen) and answers one of: a line, an
  // arrow (a line with a head drawn at its far end), a rectangle, an ellipse, a triangle or a diamond. Anything it is not
  // sure of is `null`: a scribble stays a scribble.
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const r1 = (n) => Math.round(n * 10) / 10;

  //: Perpendicular distance from `p` to the line through `a` and `b`.
  function offLine(p, a, b) {
    const len = dist(a, b);
    if (!len) return dist(p, a);
    return Math.abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / len;
  }

  //: Douglas-Peucker on the points from index `lo` to `hi`, the kept indexes in order (both ends included).
  function simplifyRange(pts, lo, hi, eps) {
    let far = -1, farD = eps;
    for (let i = lo + 1; i < hi; i++) {
      const d = offLine(pts[i], pts[lo], pts[hi]);
      if (d > farD) { far = i; farD = d; }
    }
    if (far < 0) return [lo, hi];
    return [...simplifyRange(pts, lo, far, eps).slice(0, -1), ...simplifyRange(pts, far, hi, eps)];
  }

  //: The corners of a closed ring: split at the point farthest from the start so each half has a chord, simplify both,
  //: then drop near-straight vertices and vertices that crowd the one before.
  function corners(pts, eps, crowd) {
    let far = 1;
    for (let i = 2; i < pts.length - 1; i++) if (dist(pts[i], pts[0]) > dist(pts[far], pts[0])) far = i;
    const a = simplifyRange(pts, 0, far, eps);
    const b = simplifyRange(pts, far, pts.length - 1, eps);
    let ring = [...a.slice(0, -1), ...b.slice(0, -1)].map((i) => pts[i]);
    const turn = (p, q, r) => {
      const v1 = [q[0] - p[0], q[1] - p[1]], v2 = [r[0] - q[0], r[1] - q[1]];
      const dot = v1[0] * v2[0] + v1[1] * v2[1];
      return Math.abs(Math.atan2(v1[0] * v2[1] - v1[1] * v2[0], dot)) * 180 / Math.PI;
    };
    for (let changed = true; changed && ring.length > 3;) {
      changed = false;
      for (let i = 0; i < ring.length; i++) {
        const p = ring[(i + ring.length - 1) % ring.length], q = ring[i], r = ring[(i + 1) % ring.length];
        if (turn(p, q, r) < 28 || dist(p, q) < crowd) { ring.splice(i, 1); changed = true; break; }
      }
    }
    return ring;
  }

  const angleAt = (p, q, r) => {
    const v1 = [p[0] - q[0], p[1] - q[1]], v2 = [r[0] - q[0], r[1] - q[1]];
    const c = (v1[0] * v2[0] + v1[1] * v2[1]) / ((Math.hypot(...v1) * Math.hypot(...v2)) || 1);
    return Math.acos(Math.max(-1, Math.min(1, c))) * 180 / Math.PI;
  };

  //: An open stroke: a straight line, or a straight shaft with a head drawn back from its far end.
  function openShape(pts, pathLen, diag) {
    const first = pts[0], last = pts[pts.length - 1];
    const chord = dist(first, last);
    if (chord >= 20 && pathLen < chord * 1.25 && Math.max(...pts.map((p) => offLine(p, first, last))) < Math.max(6, chord * 0.07)) {
      return { kind: "line", d: `M ${r1(first[0])} ${r1(first[1])} L ${r1(last[0])} ${r1(last[1])}` };
    }
    //: The tip is the point farthest from the start; the shaft is the way there, the head is what is drawn after.
    //: Found by climbing to the first peak (not the overall farthest point, which is the second visit to the tip once the head's wings are drawn).
    let far = 0;
    for (let i = 1; i < pts.length; i++) if (dist(pts[i], first) > dist(pts[far], first)) far = i;
    let tip = pts.findIndex((p) => dist(p, first) >= dist(pts[far], first) * 0.9);
    while (tip + 1 < pts.length && dist(pts[tip + 1], first) >= dist(pts[tip], first) - 0.2) tip += 1;
    const shaft = dist(pts[tip], first);
    if (shaft < Math.max(30, diag * 0.6) || tip === pts.length - 1) return null;
    const before = pts.slice(0, tip + 1), after = pts.slice(tip);
    let beforeLen = 0, afterLen = 0;
    for (let i = 1; i < before.length; i++) beforeLen += dist(before[i - 1], before[i]);
    for (let i = 1; i < after.length; i++) afterLen += dist(after[i - 1], after[i]);
    const straight = Math.max(...before.map((p) => offLine(p, first, pts[tip]))) < Math.max(6, shaft * 0.1);
    const reach = Math.max(...after.map((p) => dist(p, pts[tip])));
    const wing = after.reduce((best, p) => (dist(p, pts[tip]) > dist(best, pts[tip]) ? p : best), pts[tip]);
    const back = angleAt(first, pts[tip], wing);
    if (straight && beforeLen < shaft * 1.25 && afterLen >= shaft * 0.15 && afterLen <= shaft * 1.6 && reach <= shaft * 0.5 && reach >= shaft * 0.08 && back < 55) {
      return { kind: "arrow", d: `M ${r1(first[0])} ${r1(first[1])} L ${r1(pts[tip][0])} ${r1(pts[tip][1])}` };
    }
    return null;
  }

  //: A closed stroke: an ellipse by how evenly it sits on its box's ellipse, else by its corners.
  function closedShape(pts, box, diag) {
    const { x, y, w, h } = box;
    if (w < 14 || h < 14) return null;
    const cx = x + w / 2, cy = y + h / 2;
    const radii = pts.map((p) => Math.hypot((p[0] - cx) / (w / 2), (p[1] - cy) / (h / 2)));
    const mean = radii.reduce((a, b) => a + b, 0) / radii.length;
    const spread = Math.sqrt(radii.reduce((a, b) => a + (b - mean) ** 2, 0) / radii.length);
    if (mean > 0.88 && mean < 1.12 && spread < 0.085) {
      const rx = w / 2, ry = h / 2;
      return { kind: "ellipse", d: `M ${r1(x)} ${r1(y + ry)} a ${r1(rx)} ${r1(ry)} 0 1 0 ${r1(w)} 0 a ${r1(rx)} ${r1(ry)} 0 1 0 ${r1(-w)} 0` };
    }
    const ring = corners(pts, diag * 0.07, diag * 0.12);
    const poly = (ps) => `M ${ps.map((p) => `${r1(p[0])} ${r1(p[1])}`).join(" L ")} Z`;
    if (ring.length === 3) {
      const sides = ring.map((p, i) => dist(p, ring[(i + 1) % 3]));
      if (Math.min(...sides) < diag * 0.25) return null;
      return { kind: "triangle", d: poly(ring) };
    }
    if (ring.length === 4) {
      const angles = ring.map((q, i) => angleAt(ring[(i + 3) % 4], q, ring[(i + 1) % 4]));
      if (angles.some((a) => a < 62 || a > 118)) return null;
      //: A diamond has a corner at the middle of each side of its box; a rectangle has its corners at the box's.
      const nearMid = ring.every((p) => (Math.abs(p[0] - cx) < w * 0.18 && (Math.abs(p[1] - y) < h * 0.18 || Math.abs(p[1] - (y + h)) < h * 0.18))
        || (Math.abs(p[1] - cy) < h * 0.18 && (Math.abs(p[0] - x) < w * 0.18 || Math.abs(p[0] - (x + w)) < w * 0.18)));
      if (nearMid) return { kind: "diamond", d: poly(ring) };
      const tilt = ring.map((p, i) => {
        const q = ring[(i + 1) % 4];
        const a = Math.abs(Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI) % 90;
        return Math.min(a, 90 - a);
      });
      if (Math.max(...tilt) > 14) return null;
      return { kind: "rect", d: `M ${r1(x)} ${r1(y)} h ${r1(w)} v ${r1(h)} h ${r1(-w)} Z` };
    }
    return null;
  }

  //: Pure: `points` ([x, y] pairs in the order drawn) as `{ kind, d }` or null. `kind` is "line", "arrow", "rect", "ellipse",
  //: "triangle" or "diamond"; `d` is the clean path (an arrow's is the shaft only: the caller adds the head).
  function recognise(points) {
    const pts = [];
    for (const p of points || []) if (!pts.length || dist(p, pts[pts.length - 1]) > 0.5) pts.push([Number(p[0]), Number(p[1])]);
    if (pts.length < 5) return null;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const box = { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
    const diag = Math.hypot(box.w, box.h);
    if (diag < 24) return null;
    let pathLen = 0;
    for (let i = 1; i < pts.length; i++) pathLen += dist(pts[i - 1], pts[i]);
    const closed = dist(pts[0], pts[pts.length - 1]) < pathLen * 0.18 && pathLen > diag * 1.6;
    return closed ? closedShape(pts, box, diag) : openShape(pts, pathLen, diag);
  }

  //: The sketch kinds the board draws each answer as (the tool names `wbClosedShapeD` and the saved `shape` use).
  const SHAPE_OF = { line: "line", arrow: "arrow", rect: "rect", ellipse: "circle", triangle: "triangle", diamond: "diamond" };

  //: The selected pen stroke, if it is solid ink that kept its points (a marker stroke keeps its look, so it is left out).
  function target() {
    const sketch = wbCommandOneSketch();
    const parsed = sketch && wbSketchParsedData(sketch);
    return parsed?.ink && parsed.shape === "draw" && Array.isArray(parsed.pts) ? { sketch, parsed } : null;
  }

  //: **Clean up** (the Edit menu and the palette): the selected pen stroke becomes the line, arrow, rectangle, ellipse,
  //: triangle or diamond it was drawn as, in the same colour and width, as one Undo step. A stroke that is not one of those is
  //: left alone and the board says so.
  async function cleanup() {
    const got = target();
    if (!got) return false;
    const { sketch, parsed } = got;
    const pts = wbFmtState.inkMore.placePoints(parsed.pts, parsed.pbox, wbPathBBox(parsed.d));
    const found = recognise(pts);
    if (!found) {
      toast("That does not look like a line or a simple shape.");
      return false;
    }
    const width = parsed.width || 3;
    const patch = { d: found.d, shape: SHAPE_OF[found.kind], ink: undefined, pts: undefined, pbox: undefined, prs: undefined };
    if (found.kind === "line") Object.assign(patch, { startCap: "none", endCap: "none" });
    if (found.kind === "arrow") {
      Object.assign(patch, { startCap: "none", endCap: "arrow", d: wbRegenerateShapeCaps(found.d, "none", "arrow", width * 4 + 6) });
    }
    wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before: WB_KIND_INFO.sketch.payload(sketch) });
    await wbSaveSketchProps(sketch, patch);
    wbScheduleRender();
    return true;
  }

  Object.assign(wbFmtState.inkRecognise ||= {}, { recognise, corners, cleanup, target });
})();
