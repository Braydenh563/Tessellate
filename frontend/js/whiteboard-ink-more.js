(() => {
  // whiteboard-ink-more.js: ink beyond the plain pen (WHITEBOARD_PLAN section 3): the shaft of a free line or arrow
  // stopping at a hollow end. Held on `wbFmtState.inkMore`, so no new global name. Pure parts are node-tested
  // (tests/test_wb_ink_more.py); the browser half is scratchpad/ui-sweeps/wbink3.js.
  const NUM = "(-?[\\d.]+(?:e-?\\d+)?)";
  const SHAFT = new RegExp(`^M\\s*${NUM}\\s+${NUM}\\s+L\\s*${NUM}\\s+${NUM}`);

  //: **A free line's shaft stops at a hollow end's edge** (L277), as a link's does (`wbShaftEnd`): an outline
  //: diamond, circle or square drew the shaft on through its middle. `d` stays whole in storage (every handle and
  //: drag reads its two tips from the first `M..L..`); only the drawn path is trimmed, so the hit band keeps the
  //: full length. `shaftEnd(pt, toward, cap, headLen, size)` is the board's `wbShaftEnd`, passed in because it
  //: lives in whiteboard.js. Returns `d` itself when no end is hollow.
  function trimShaft(d, startCap, endCap, headLen, sizes, shaftEnd) {
    const m = typeof d === "string" ? d.match(SHAFT) : null;
    if (!m || (!startCap && !endCap)) return d;
    const start = { x: parseFloat(m[1]), y: parseFloat(m[2]) };
    const end = { x: parseFloat(m[3]), y: parseFloat(m[4]) };
    const s = shaftEnd(start, end, startCap, headLen, sizes?.startSize);
    const e = shaftEnd(end, start, endCap, headLen, sizes?.endSize);
    if (s === start && e === end) return d;
    return `M ${s.x} ${s.y} L ${e.x} ${e.y}` + d.slice(m[0].length);
  }

  // --- Smoothed, pressure-aware strokes (L-whiteboard-1 and -5) -------------------------------------------------
  //: **The pen and the marker draw through perfect-freehand** (MIT, vendored in frontend/vendor/perfect-freehand): the
  //: points the hand made are smoothed and become the outline of a stroke whose width follows pressure. A pen
  //: (`pointerType` "pen") reports real pressure; a mouse or a finger has none, so the library simulates it from speed.
  //: The saved `d` is that outline as plain `M`/`L` points (no `Z`, so it is not a closed shape), drawn filled with the
  //: stroke's colour (`ink: 1` in the data), which keeps move, scale, turn and export working on it unchanged.
  const round1 = (n) => Math.round(n * 10) / 10;

  //: Pure: the library's options for one kind of stroke at one pen width.
  function inkOptions(kind, width, pointerType, last) {
    if (kind === "highlighter") return { size: width, thinning: 0, smoothing: 0.6, streamline: 0.5, simulatePressure: false, last };
    return { size: width * 1.4, thinning: 0.55, smoothing: 0.5, streamline: 0.45, simulatePressure: pointerType !== "pen", last };
  }

  //: The outline of `points` ([x, y, pressure?]) as a path, or "" without the library or without points.
  function outline(points, kind, width, pointerType, last, lib = window.perfectFreehand) {
    if (!lib || !points?.length) return "";
    const ring = lib.getStroke(points, inkOptions(kind, width, pointerType, last));
    if (!ring.length) return "";
    return ring.map(([x, y], i) => `${i ? "L" : "M"} ${round1(x)} ${round1(y)}`).join(" ");
  }

  //: A solid pen or marker is ink; a dashed one keeps the plain stroke, which a fill cannot dash.
  const takesInk = (dash, lib = window.perfectFreehand) => Boolean(lib) && (!dash || dash === "solid");

  //: The live path while drawing: filled with the colour, no outline stroke.
  function liveStyle(path, colour, opacity) {
    path.setAttribute("fill", colour);
    path.setAttribute("stroke", "none");
    path.removeAttribute("stroke-dasharray");
    if (opacity != null) path.setAttribute("fill-opacity", String(opacity));
  }

  //: What a saved ink stroke keeps of the hand's own points, for Clean up (whiteboard-ink-recognise.js) and Replay: the
  //: points thinned to one every 2 units (at most 600), flat as x, y, x, y, and the outline's box when they were taken, so
  //: a stroke that was moved or resized later maps its points onto where it is now.
  function keepPoints(points, bbox) {
    const flat = [];
    let last = null;
    const step = Math.max(1, Math.ceil(points.length / 600));
    points.forEach((p, i) => {
      if (i % step && i !== points.length - 1) return;
      if (last && Math.hypot(p[0] - last[0], p[1] - last[1]) < 2 && i !== points.length - 1) return;
      flat.push(round1(p[0]), round1(p[1]));
      last = p;
    });
    const pbox = bbox ? [round1(bbox.minX), round1(bbox.minY), round1(bbox.width), round1(bbox.height)] : null;
    return pbox ? { pts: flat, pbox } : {};
  }

  //: The kept points [x, y] where the stroke is now: `pbox` (then) mapped onto `bbox` (now), moved and scaled per axis.
  function placePoints(flat, pbox, bbox) {
    if (!Array.isArray(flat) || !Array.isArray(pbox) || !bbox) return [];
    const sx = pbox[2] > 0.5 ? bbox.width / pbox[2] : 1, sy = pbox[3] > 0.5 ? bbox.height / pbox[3] : 1;
    const out = [];
    for (let i = 0; i + 1 < flat.length; i += 2) out.push([bbox.minX + (flat[i] - pbox[0]) * sx, bbox.minY + (flat[i + 1] - pbox[1]) * sy]);
    return out;
  }

  //: **The width control rebuilds the outline** (L-whiteboard-31): a smoothed stroke is a fixed filled outline, so a new
  //: width has to come from the hand's own points again. The kept points (where the stroke is now) go back through the
  //: library at the new size; the saved points and their box follow the new outline. Pure; `{}` for a stroke that kept no
  //: points (drawn before they were kept), which keeps its outline and only changes the number.
  function rebuild(parsed, width, bboxOf, lib = window.perfectFreehand) {
    if (!parsed?.ink || !Array.isArray(parsed.pts) || !lib) return {};
    const now = bboxOf(parsed.d);
    const pts = placePoints(parsed.pts, parsed.pbox, now);
    const d = outline(pts, parsed.opacity != null ? "highlighter" : "pen", width, "mouse", true, lib);
    const box = d && bboxOf(d);
    return box ? { d, ...keepPoints(pts, box) } : {};
  }

  //: **A turn or a flip turns the kept points too.** `placePoints` maps the points by the outline's box, which is right for a
  //: move or a resize and wrong for a turn. The outline's points keep their order through any transform, so the one
  //: (affine) map from the old outline to the new one is read off three of them and applied to the kept points; the new
  //: points are then in the new outline's frame. `{}` when the map is only a move or a stretch (the box mapping already
  //: holds) or the two paths do not correspond.
  const coordsOf = (d) => (String(d).match(/-?\d*\.?\d+(?:[eE]-?\d+)?/g) || []).map(Number);
  function carry(oldD, newD, flat, pbox, bboxOf) {
    const a = coordsOf(oldD), b = coordsOf(newD);
    if (a.length !== b.length || a.length < 12 || !Array.isArray(flat) || !Array.isArray(pbox)) return {};
    const n = a.length / 2;
    const at = (c, i) => [c[i * 2], c[i * 2 + 1]];
    let best = null;
    for (const [i, j, k] of [[0, Math.floor(n / 3), Math.floor((2 * n) / 3)], [0, Math.floor(n / 2), n - 1], [0, 1, n - 1]]) {
      const [p, q, r] = [at(a, i), at(a, j), at(a, k)];
      const area = Math.abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
      if (!best || area > best.area) best = { area, ids: [i, j, k] };
    }
    if (best.area < 1e-6) return {};
    const [P, Q, R] = best.ids.map((i) => at(a, i)), [P2, Q2, R2] = best.ids.map((i) => at(b, i));
    const det = (Q[0] - P[0]) * (R[1] - P[1]) - (R[0] - P[0]) * (Q[1] - P[1]);
    const solve = (u, v, w) => {
      const gx = ((v - u) * (R[1] - P[1]) - (w - u) * (Q[1] - P[1])) / det;
      const gy = ((w - u) * (Q[0] - P[0]) - (v - u) * (R[0] - P[0])) / det;
      return [gx, gy, u - gx * P[0] - gy * P[1]];
    };
    const [m00, m01, tx] = solve(P2[0], Q2[0], R2[0]);
    const [m10, m11, ty] = solve(P2[1], Q2[1], R2[1]);
    if (Math.abs(m01) < 1e-3 && Math.abs(m10) < 1e-3 && m00 > 0 && m11 > 0) return {};
    const box = bboxOf(newD);
    if (!box) return {};
    const out = [];
    for (let i = 0; i + 1 < flat.length; i += 2) out.push([m00 * flat[i] + m01 * flat[i + 1] + tx, m10 * flat[i] + m11 * flat[i + 1] + ty]);
    return keepPoints(out, box);
  }

  //: Called as a sketch's path is replaced (`wbSketchSetD`, `wbSketchSetProps`, `wbSaveSketchProps`): a smoothed stroke's kept
  //: points follow a turn or a flip. The old points are first put where the stroke is (box to box) so a move before the
  //: turn is not lost.
  function follow(parsed, newD, bboxOf) {
    if (!parsed?.ink || !Array.isArray(parsed.pts) || typeof newD !== "string" || newD === parsed.d) return;
    const here = Array.isArray(parsed.pbox) && bboxOf(parsed.d) ? placePoints(parsed.pts, parsed.pbox, bboxOf(parsed.d)).flat() : parsed.pts;
    const turned = carry(parsed.d, newD, here, parsed.pbox, bboxOf);
    if (turned.pts) Object.assign(parsed, turned);
  }

  wbFmtState.inkMore = { trimShaft, inkOptions, outline, takesInk, liveStyle, keepPoints, placePoints, rebuild, carry, follow };
})();
