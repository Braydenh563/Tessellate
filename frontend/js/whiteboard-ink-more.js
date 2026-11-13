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

  wbFmtState.inkMore = { trimShaft };
})();
