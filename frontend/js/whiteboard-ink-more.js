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

  wbFmtState.inkMore = { trimShaft, inkOptions, outline, takesInk, liveStyle, keepPoints, placePoints };
})();
