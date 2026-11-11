(() => {
  // whiteboard-draw-more.js: the last of draw.io's connector rows (WHITEBOARD_PLAN section 10). Two more line
  // shapes beside curved, straight and elbow, both drawn from the two ends alone (a bend dragged on either is not
  // used): Entity relation (`route: "er"`) and Isometric (`route: "iso"`). `wbLinkPathD` calls `routeStops` for them.

  const STUB = 30;

  //: The way an end leaves its shape along x: its edge's outward normal when that points sideways, else toward the other end.
  function sideOf(pt, other) {
    if (pt.dir && Math.abs(pt.dir.x) > 0.5) return Math.sign(pt.dir.x);
    return Math.sign(other.x - pt.x) || 1;
  }

  //: Consecutive repeats go, so a cap's angle is never read off a run of no length, and a point in the middle of a
  //: straight run goes too.
  function clean(points) {
    const same = (a, b) => Math.abs(a - b) < 0.01;
    const apart = points.filter((p, i) => i === 0 || !same(p.x, points[i - 1].x) || !same(p.y, points[i - 1].y));
    return apart.filter((p, i) => i === 0 || i === apart.length - 1 || !((same(p.x, apart[i - 1].x) && same(p.x, apart[i + 1].x)) || (same(p.y, apart[i - 1].y) && same(p.y, apart[i + 1].y))));
  }

  //: draw.io's entity relation style: out along x a short stub from each end, then one run across between them.
  //: Facing ends with room between them meet halfway; with no room the line steps round through the middle row;
  //: ends facing the same way go out past both stubs and back.
  function entityStops(s, t) {
    const sd = sideOf(s, t), td = sideOf(t, s);
    const a = s.x + sd * STUB, b = t.x + td * STUB;
    const start = { x: s.x, y: s.y }, end = { x: t.x, y: t.y };
    if (sd === td) {
      const x = sd > 0 ? Math.max(a, b) : Math.min(a, b);
      return clean([start, { x, y: s.y }, { x, y: t.y }, end]);
    }
    if (sd * (b - a) >= 0) {
      const mid = (a + b) / 2;
      return clean([start, { x: mid, y: s.y }, { x: mid, y: t.y }, end]);
    }
    const row = (s.y + t.y) / 2;
    return clean([start, { x: a, y: s.y }, { x: a, y: row }, { x: b, y: row }, { x: b, y: t.y }, end]);
  }

  //: draw.io's isometric style, along the axes of an isometric drawing: two runs at 30 degrees (up or down and
  //: across at tan 30) while the other end is within that cone, and past it one run at 30 degrees across to the
  //: other end's column and then straight up or down, so the line never doubles back on itself.
  function isometricStops(s, t) {
    const dx = t.x - s.x, dy = t.y - s.y;
    const start = { x: s.x, y: s.y }, end = { x: t.x, y: t.y };
    const cos = Math.cos(Math.PI / 6), sin = Math.sin(Math.PI / 6);
    const across = dx / cos, down = dy / sin;
    if (Math.abs(down) <= Math.abs(across)) {
      const p = (across + down) / 2;
      return clean([start, { x: s.x + p * cos, y: s.y + p * sin }, end]);
    }
    return clean([start, { x: t.x, y: s.y + Math.sign(dy) * Math.abs(dx) * Math.tan(Math.PI / 6) }, end]);
  }

  function routeStops(route, s, t) {
    return route === "iso" ? isometricStops(s, t) : entityStops(s, t);
  }

  wbFmtState.drawMore = { routeStops, entityStops, isometricStops };
})();
