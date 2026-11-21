(() => {
  // whiteboard-map-edges.js: map line geometry, ribbons, edge paths and their paint.
  // Moved out of whiteboard-map.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: **A line's end pinned to a side** (K31, the owner: "I want to be able to
  //: have more say in which sides the connections come from and to"). On the
  //: child, like the rest of the line: `edge_from` is the parent's side the
  //: line leaves, `edge_to` the child's side it enters. Each side is its
  //: midpoint as two fractions of the box and its outward normal; a midpoint
  //: is on the boundary of every topic shape (ellipse, diamond, hexagon,
  //: circle and cloud touch their box there), so a pinned end meets the shape.
  const WB_MAP_SIDES = Object.freeze({
    top: [0.5, 0, 0, -1],
    right: [1, 0.5, 1, 0],
    bottom: [0.5, 1, 0, 1],
    left: [0, 0.5, -1, 0],
  });

  function wbMapSidePoint(node, size, side) {
    const [fx, fy] = WB_MAP_SIDES[side];
    return { x: node.x + size.w * fx, y: node.y + size.h * fy };
  }

  //: The side of `node` that faces a point: the larger of the two offsets
  //: from its centre, each over the box's own size, so a wide topic is not
  //: read as facing up for a point only a little above its end.
  function wbMapFacingSide(node, size, x, y) {
    const dx = (x - (node.x + size.w / 2)) / (size.w || 1);
    const dy = (y - (node.y + size.h / 2)) / (size.h || 1);
    if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? "left" : "right";
    return dy < 0 ? "top" : "bottom";
  }

  function wbMapEdgeAnchors(parent, child, mapLayout) {
    const p = wbMapNodeSize(parent);
    const c = wbMapNodeSize(child);
    const from = WB_MAP_SIDES[child?.data?.edge_from] ? child.data.edge_from : null;
    const to = WB_MAP_SIDES[child?.data?.edge_to] ? child.data.edge_to : null;
    if (from || to) {
      //: Both ends with at least one pinned. The end left on Auto faces the
      //: pinned one's point, so a line pinned to a parent's top still arrives at
      //: whichever side of the child looks back at it.
      let s1 = from;
      let s2 = to;
      if (!s1) {
        const b = wbMapSidePoint(child, c, s2);
        s1 = wbMapFacingSide(parent, p, b.x, b.y);
      }
      if (!s2) {
        const a = wbMapSidePoint(parent, p, s1);
        s2 = wbMapFacingSide(child, c, a.x, a.y);
      }
      const a = wbMapSidePoint(parent, p, s1);
      const b = wbMapSidePoint(child, c, s2);
      return { horizontal: s1 === "left" || s1 === "right", pinned: true, s1, s2, x1: a.x, y1: a.y, x2: b.x, y2: b.y };
    }
    //: Inside a branch with its own structure, that structure's lines, and its
    //: top topic is the "root" the column layouts measure from.
    const layout = child._bl || mapLayout;
    //: Every sideways layout is horizontal, whichever way it grows: the
    //: `leftward` test below already reads the direction off the two boxes, so
    //: tree-left and both-sides need nothing of their own here.
    let horizontal = layout === "tree-right" || layout === "tree-left" || layout === "tree-both" || layout === "logic-right";
    const fromRoot = child._blTop != null ? parent.id === child._blTop : parent.parent_id == null;
    //: A timeline's events sit on the axis through the centre; their branches
    //: hang below or above them.
    if (layout === "timeline") horizontal = fromRoot;
    //: A tree table's rows: down from the parent's left, then into the row.
    if (layout === "tree-table" && !fromRoot) {
      return { horizontal: true, x1: parent.x + WB_MAP_INDENT / 2, y1: parent.y + p.h, x2: child.x, y2: child.y + c.h / 2 };
    }
    //: A fishbone's rib leaves the spine at the head's left edge
    //: (`wbMapEdgePathD` runs it along the spine to the rib's foot). It meets the
    //: main topic at its spine-side corner, not its middle: the causes stand
    //: between the topic and the spine in its own column, and a rib to the middle
    //: ran behind them (L358).
    if (layout === "fishbone" && fromRoot) {
      const up = child.y + c.h / 2 < parent.y + p.h / 2;
      //: A branch's fishbone faces away from its parent, so its bones may run
      //: right of the head (`wbMapStructuredPositions`).
      const right = child.x + c.w / 2 > parent.x + p.w;
      return { horizontal: false, rib: true, right, x1: right ? parent.x + p.w : parent.x, y1: parent.y + p.h / 2, x2: right ? child.x : child.x + c.w, y2: up ? child.y + c.h : child.y };
    }
    //: A cause under a fishbone's main topic (or a cause under a cause) stands
    //: one indent in. Its line drops from the parent's edge half an indent in,
    //: left of every cause above it, whichever side the bones are turned to.
    if (layout === "fishbone") {
      const half = WB_MAP_INDENT / 2;
      const near = (a, b) => Math.abs(a - b) < 1.5;
      const down = child.y + c.h / 2 > parent.y + p.h / 2;
      const y1 = down ? parent.y + p.h : parent.y;
      const y2 = child.y + c.h / 2;
      if (near(child.x, parent.x + WB_MAP_INDENT)) return { horizontal: true, x1: parent.x + half, y1, x2: child.x, y2 };
      if (near(child.x + c.w, parent.x + p.w - WB_MAP_INDENT)) return { horizontal: true, x1: parent.x + p.w - half, y1, x2: child.x + c.w, y2 };
    }
    if (layout === "radial" || layout === "free" || layout === "fishbone") {
      horizontal = Math.abs(child.x - parent.x) >= Math.abs(child.y - parent.y);
    } else if (!horizontal && layout !== "timeline" && wbMapBesideParent(parent, p, child, c)) {
      horizontal = true;
    }
    if (horizontal) {
      const leftward = child.x + c.w / 2 < parent.x + p.w / 2;
      return {
        horizontal,
        x1: leftward ? parent.x : parent.x + p.w,
        y1: parent.y + p.h / 2,
        x2: leftward ? child.x + c.w : child.x,
        y2: child.y + c.h / 2,
      };
    }
    const upward = child.y + c.h / 2 < parent.y + p.h / 2;
    return {
      horizontal,
      x1: parent.x + p.w / 2,
      y1: upward ? parent.y : parent.y + p.h,
      x2: child.x + c.w / 2,
      y2: upward ? child.y + c.h : child.y,
    };
  }

  //: **Where the line into a topic bends** (MINDMAP_PLAN.md §12.1 item 5's
  //: third, "the control points on a curve drag to reshape it").
  //:
  //: A tree edge has no row of its own (it *is* `parent_id`), so the waypoint
  //: lives on the child, in `edge_slide` and `edge_bend`, as two fractions of
  //: the line's own length: along it from the halfway mark, and across it. The
  //: frame is rebuilt from the anchors every time it is read, which is what
  //: makes the stored pair survive a tidy, a drag, a zoom and a layout switch:
  //: two board coordinates would be right until either end moved, which on a
  //: map that lays itself out is about one gesture later.
  //:
  //: `bent` is what an unset pair means: the point is the anchors' own midpoint,
  //: every shape below is the shape it has always drawn, and the `d` string a
  //: plain map produces is the same string character for character.
  function wbMapEdgeWaypoint(a, child) {
    const slide = Number(child?.data?.edge_slide) || 0;
    const bend = Number(child?.data?.edge_bend) || 0;
    const mx = (a.x1 + a.x2) / 2;
    const my = (a.y1 + a.y2) / 2;
    const dx = a.x2 - a.x1;
    const dy = a.y2 - a.y1;
    const len = Math.hypot(dx, dy) || 1;
    // Along the line, and the normal to it: the pair (ux, uy), (-uy, ux).
    const ux = dx / len;
    const uy = dy / len;
    return {
      bent: Boolean(slide || bend),
      x: mx + (ux * slide - uy * bend) * len,
      y: my + (uy * slide + ux * bend) * len,
    };
  }

  //: The same frame read the other way: a board point back into the two
  //: fractions the drag stores. Held to the same bounds the schema enforces, so
  //: a drag can never compose a value the PUT would then refuse (a gesture that
  //: works until you let go is the worst shape a control can have).
  const WB_MAP_BEND_MAX = 4;
  const WB_MAP_SLIDE_MAX = 0.45;

  function wbMapEdgeFractions(a, x, y) {
    const mx = (a.x1 + a.x2) / 2;
    const my = (a.y1 + a.y2) / 2;
    const dx = a.x2 - a.x1;
    const dy = a.y2 - a.y1;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len;
    const uy = dy / len;
    const vx = x - mx;
    const vy = y - my;
    const hold = (value, limit) => Math.max(-limit, Math.min(limit, value));
    //: Three decimals, which at the 45-degree worst case is under a hundredth
    //: of a pixel on the longest branch this canvas allows: enough that the
    //: line lands where it was dropped, and short enough that the number in an
    //: exported file is a number a person can read.
    const round = (value) => Math.round(value * 1000) / 1000;
    return {
      edge_slide: round(hold((vx * ux + vy * uy) / len, WB_MAP_SLIDE_MAX)),
      edge_bend: round(hold((vx * -uy + vy * ux) / len, WB_MAP_BEND_MAX)),
    };
  }

  //: The cubic a curved edge is drawn from, as four points, so the stroke and
  //: the ribbon are two drawings of one curve rather than two curves that drift
  //: (the same bargain `wbMapEdgePathD`'s own comment makes about the render and
  //: the per-frame drag follow).
  //:
  //: **The bend is 4/3 of the distance the point moved, and the number is the
  //: whole trick.** A cubic's own midpoint is `(p0 + 3c0 + 3c1 + p1) / 8`, so
  //: shifting *both* control points by d moves that midpoint by 6d/8: to put the
  //: curve through a point the pointer is holding, the control points move 4/3
  //: as far. Which means the handle is not near the line, it is exactly on it,
  //: at t = 0.5, at every zoom and in both orientations, and the probe can say
  //: so with a number rather than a screenshot.
  function wbMapEdgeCubic(a, child) {
    const mx = (a.x1 + a.x2) / 2;
    const my = (a.y1 + a.y2) / 2;
    const p0 = { x: a.x1, y: a.y1 };
    const p1 = { x: a.x2, y: a.y2 };
    // Control points on the axis the edge leaves by, at half the span: the
    // curve leaves the parent square to its own edge and arrives square to
    // the child's, which is what makes a column of siblings read as one
    // branch rather than a fan of straight lines crossing each other.
    let c0 = a.horizontal ? { x: mx, y: a.y1 } : { x: a.x1, y: my };
    let c1 = a.horizontal ? { x: mx, y: a.y2 } : { x: a.x2, y: my };
    //: A pinned end leaves square to its own side, whichever pair of sides
    //: it joins (right to top is a quarter turn, not an S).
    if (a.pinned) {
      const reach = Math.max(24, Math.hypot(a.x2 - a.x1, a.y2 - a.y1) / 2);
      const [, , ux1, uy1] = WB_MAP_SIDES[a.s1];
      const [, , ux2, uy2] = WB_MAP_SIDES[a.s2];
      c0 = { x: a.x1 + ux1 * reach, y: a.y1 + uy1 * reach };
      c1 = { x: a.x2 + ux2 * reach, y: a.y2 + uy2 * reach };
    }
    const w = wbMapEdgeWaypoint(a, child);
    if (w.bent) {
      const dx = (w.x - mx) * (4 / 3);
      const dy = (w.y - my) * (4 / 3);
      c0.x += dx;
      c0.y += dy;
      c1.x += dx;
      c1.y += dy;
    }
    return { p0, c0, c1, p1 };
  }

  //: Where an elbow turns, which is the one thing a right-angled line has to
  //: give a waypoint. Held between the two anchors on both axes: a turn outside
  //: the span is a line that doubles back on itself, and the point it returns is
  //: then guaranteed to sit on the elbow's own crossing leg, which is what lets
  //: the handle be drawn on the line for this shape as well as the other two.
  function wbMapEdgeElbowTurn(a, w) {
    const hold = (value, p, q) => Math.max(Math.min(p, q), Math.min(Math.max(p, q), value));
    return { x: hold(w.x, a.x1, a.x2), y: hold(w.y, a.y1, a.y2) };
  }

  //: An elbow as its corner points, every leg on an axis (K31). Unpinned, the
  //: three legs it has always drawn. Pinned, each end leaves along its own
  //: side: two sides across one another meet at one corner; two sides on
  //: one axis cross at the turn, or, both facing the same way (right to
  //: right), run out past the further end first so the line never cuts back
  //: through a topic.
  const WB_MAP_ELBOW_STUB = 20;

  function wbMapElbowPoints(a, w) {
    const p0 = { x: a.x1, y: a.y1 };
    const p1 = { x: a.x2, y: a.y2 };
    const turn = wbMapEdgeElbowTurn(a, w);
    if (!a.pinned) {
      return a.horizontal
        ? [p0, { x: turn.x, y: a.y1 }, { x: turn.x, y: a.y2 }, p1]
        : [p0, { x: a.x1, y: turn.y }, { x: a.x2, y: turn.y }, p1];
    }
    const [, , ux1, uy1] = WB_MAP_SIDES[a.s1];
    const [, , ux2, uy2] = WB_MAP_SIDES[a.s2];
    const h1 = ux1 !== 0;
    const h2 = ux2 !== 0;
    if (h1 !== h2) return h1 ? [p0, { x: a.x2, y: a.y1 }, p1] : [p0, { x: a.x1, y: a.y2 }, p1];
    if (h1) {
      let x = turn.x;
      if (ux1 === ux2) x = ux1 > 0 ? Math.max(a.x1, a.x2) + WB_MAP_ELBOW_STUB : Math.min(a.x1, a.x2) - WB_MAP_ELBOW_STUB;
      return [p0, { x, y: a.y1 }, { x, y: a.y2 }, p1];
    }
    let y = turn.y;
    if (uy1 === uy2) y = uy1 > 0 ? Math.max(a.y1, a.y2) + WB_MAP_ELBOW_STUB : Math.min(a.y1, a.y2) - WB_MAP_ELBOW_STUB;
    return [p0, { x: a.x1, y }, { x: a.x2, y }, p1];
  }

  //: The elbow's `d`: straight legs (`L`) with each corner rounded by a
  //: quarter of a curve (`Q`, the corner as its control), the radius held to
  //: half of the shorter leg so a short leg is never overshot.
  const WB_MAP_ELBOW_RADIUS = 10;

  function wbMapElbowD(points) {
    const pts = points.filter((pt, i) => i === 0 || pt.x !== points[i - 1].x || pt.y !== points[i - 1].y);
    let d = `M${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i += 1) {
      const prev = pts[i - 1];
      const at = pts[i];
      const next = pts[i + 1];
      const inLen = Math.hypot(at.x - prev.x, at.y - prev.y);
      const outLen = Math.hypot(next.x - at.x, next.y - at.y);
      const r = Math.min(WB_MAP_ELBOW_RADIUS, inLen / 2, outLen / 2);
      if (!r) continue;
      const ax = at.x - ((at.x - prev.x) / inLen) * r;
      const ay = at.y - ((at.y - prev.y) / inLen) * r;
      const bx = at.x + ((next.x - at.x) / outLen) * r;
      const by = at.y + ((next.y - at.y) / outLen) * r;
      d += ` L${ax} ${ay} Q${at.x} ${at.y} ${bx} ${by}`;
    }
    const end = pts[pts.length - 1];
    return `${d} L${end.x} ${end.y}`;
  }

  //: Where the elbow's handle sits: on its crossing leg, at the turn.
  function wbMapElbowHandle(a, w) {
    const pts = wbMapElbowPoints(a, w);
    if (pts.length === 3) return pts[1];
    const turn = wbMapEdgeElbowTurn(a, w);
    const sideways = a.pinned ? WB_MAP_SIDES[a.s1][2] !== 0 : a.horizontal;
    return sideways
      ? { x: pts[1].x, y: turn.y }
      : { x: turn.x, y: pts[1].y };
  }

  //: How far apart a line's two controls sit, in board units. The `+` is 24
  //: units across and the handle 14, so 26 is the first number at which neither
  //: covers the other at any zoom (both live in the zoomed layer and scale
  //: together). They were on the same point in the first build of this, and the
  //: `+` is HTML above the SVG: `elementFromPoint` at the handle's centre
  //: returned the button, and the drag could not start at all.
  const WB_MAP_EDGE_CONTROL_GAP = 26;

  //: The point on the drawn line where the handle belongs, per line shape
  //: (§12.1 item 5's third has to compose with item 4's three shapes). The curve
  //: and the straight line pass through the waypoint itself by construction; the
  //: elbow passes through its turn.
  function wbMapEdgeHandlePoint(parent, child, layout) {
    const a = wbMapEdgeAnchors(parent, child, layout);
    const w = wbMapEdgeWaypoint(a, child);
    const style = wbMapEdgeStyle(child);
    if (style === "elbow") return wbMapElbowHandle(a, w);
    //: A pinned curve need not pass through the anchors' midpoint (a quarter
    //: turn bows away from it), so its handle is the curve's own middle.
    if (a.pinned && style !== "straight") {
      const c = wbMapEdgeCubic(a, child);
      const mid = wbMapCubicAt(0.5, c.p0, c.c0, c.c1, c.p1);
      return { x: mid.x, y: mid.y };
    }
    return { x: w.x, y: w.y };
  }

  //: One tree edge's `d`, from the two nodes' live `x`/`y` and their rendered
  //: sizes. Factored out of `wbRenderMapEdges` below so the per-frame drag
  //: follow (`wbUpdateMapEdges`) recomputes an edge with exactly the maths the
  //: render uses: two copies of a cubic drifted apart is precisely the bug
  //: `wbUpdateLinkedSketches` warns about for link sketches.
  function wbMapEdgePathD(parent, child, layout) {
    const a = wbMapEdgeAnchors(parent, child, layout);
    //: The line's own shape, from the link radial (§12.1 item 4). Read from the
    //: *child*, which is the end of a tree edge that has exactly one incoming
    //: line, and defaulting to the curve, so a map made before this existed
    //: draws exactly as it did.
    //:
    //: All three share the anchors above, so switching between them cannot move
    //: where a line meets a node: the difference is only what happens between
    //: the two points. The elbow turns at the same midpoint the curve's control
    //: points sit on, which is what keeps a column of siblings reading as one
    //: branch in either style.
    const style = wbMapEdgeStyle(child);
    //: The waypoint composes with all three shapes rather than only the curve
    //: (§12.1 item 5's third: "it now has to compose with the three line shapes
    //: item 4 added"). Each shape bends in the way that shape can: the curve
    //: passes through the point, the straight line kinks at it, and the elbow
    //: moves its turn to it. An unbent line is the same string it always was.
    const w = wbMapEdgeWaypoint(a, child);
    if (a.rib && !w.bent) {
      const slant = Math.abs(a.y2 - a.y1) * 0.5;
      const foot = a.right ? Math.max(a.x1, a.x2 - slant) : Math.min(a.x1, a.x2 + slant);
      return `M${a.x1} ${a.y1} L${foot} ${a.y1} L${a.x2} ${a.y2}`;
    }
    if (style === "straight") {
      return w.bent
        ? `M${a.x1} ${a.y1} L${w.x} ${w.y} L${a.x2} ${a.y2}`
        : `M${a.x1} ${a.y1} L${a.x2} ${a.y2}`;
    }
    if (style === "elbow") return wbMapElbowD(wbMapElbowPoints(a, w));
    const c = wbMapEdgeCubic(a, child);
    return `M${c.p0.x} ${c.p0.y} C${c.c0.x} ${c.c0.y} ${c.c1.x} ${c.c1.y} ${c.p1.x} ${c.p1.y}`;
  }

  //: **A branch is a shape, not a line** (INBOX 180: "can you give the direction
  //: connectors a better and more modern professional look??", after 177 asked
  //: for Coggle's refined thick branches).
  //:
  //: Coggle's branches are not strokes: each one is a filled ribbon, wide where
  //: it leaves the parent and narrow where it reaches the child, which is what
  //: makes a map read as a tree growing outwards rather than as a diagram of
  //: boxes joined by wires. It also carries the direction the earlier report
  //: asked for without an arrowhead on every line: thick end to thin end says
  //: which way the branch runs, at every zoom, with nothing extra drawn.
  //:
  //: Sampled rather than solved: the offset curve of a cubic is not itself a
  //: cubic, so the honest way to draw one is to walk the curve, take the normal
  //: at each step, and push out by half the width wanted there. Twenty-four
  //: steps is smooth at every zoom this canvas allows (the curve is at most a
  //: few hundred units across and the error between samples is well under a
  //: pixel at 4x), and the whole ribbon is one closed path either way.
  //:
  //: Only the default curve is drawn this way. An edge explicitly set to
  //: straight, elbow or dashed through the link ring keeps its stroke: a dash
  //: is a property of a stroke and has no meaning on a fill, and a person who
  //: chose a plain line asked for a plain line.
  const WB_MAP_RIBBON_STEPS = 24;
  const WB_MAP_RIBBON_WIDE = 6.5;
  const WB_MAP_RIBBON_THIN = 2;

  //: **Per-branch thickness** (MINDMAP_PLAN.md item 177, "connection line
  //: styles: per-branch thickness, dash and arrowhead"). A multiplier rather
  //: than a width, because the same value has to scale two different drawings:
  //: the ribbon, whose two ends are 6.5 and 2 units apart, and the stroke the
  //: other three line shapes keep, which is 3px in the stylesheet. A number of
  //: pixels would have to be written twice and would drift.
  //:
  //: Three steps and not a slider: a map's lines are read against each other, so
  //: what matters is that one branch is heavier than its neighbour, and a
  //: continuum of widths nobody can tell apart is a control that only makes
  //: maps inconsistent. Medium is stored as nothing at all, like every other
  //: default this strip writes.
  const WB_MAP_EDGE_WEIGHTS = { thin: 0.55, thick: 1.7 };

  function wbMapEdgeWeight(child) {
    return WB_MAP_EDGE_WEIGHTS[wbMapThemedData(child).edge_width] || 1;
  }

  //: Whether *this* line ends in an arrowhead.
  //:
  //: The default differs by drawing, which is why this is a function and not a
  //: boolean field: a ribbon carries its direction in the taper and gets no
  //: head (a marker on a closed outline would be placed at the end of the
  //: outline, back at the parent), while a plain stroke has no taper and has
  //: had a head since the branch-direction report. `edge_arrow` overrides
  //: whichever default applies, so the strip's toggle can add a head to a
  //: ribbon and take one off a straight line.
  function wbMapEdgeHasArrow(child) {
    const set = wbMapThemedData(child).edge_arrow;
    if (set === "on") return true;
    if (set === "off") return false;
    return !wbMapEdgeIsRibbon(child);
  }

  function wbMapCubicAt(t, p0, c0, c1, p1) {
    const u = 1 - t;
    const x = u * u * u * p0.x + 3 * u * u * t * c0.x + 3 * u * t * t * c1.x + t * t * t * p1.x;
    const y = u * u * u * p0.y + 3 * u * u * t * c0.y + 3 * u * t * t * c1.y + t * t * t * p1.y;
    //: The derivative, for the normal. Taken analytically because a difference
    //: between two samples is wrong at exactly the two places it matters most,
    //: the ends, where there is no sample on one side.
    const dx = 3 * u * u * (c0.x - p0.x) + 6 * u * t * (c1.x - c0.x) + 3 * t * t * (p1.x - c1.x);
    const dy = 3 * u * u * (c0.y - p0.y) + 6 * u * t * (c1.y - c0.y) + 3 * t * t * (p1.y - c1.y);
    return { x, y, dx, dy };
  }

  function wbMapRibbonD(parent, child, layout) {
    const a = wbMapEdgeAnchors(parent, child, layout);
    //: The same four points the stroked curve is drawn from, waypoint and all
    //: (`wbMapEdgeCubic`): a ribbon that ignored the bend would be the default
    //: line shape on this map quietly refusing the control, which is the one
    //: way a feature can be "built" and do nothing on most of a map.
    const { p0, c0, c1, p1 } = wbMapEdgeCubic(a, child);
    const weight = wbMapEdgeWeight(child);
    //: An arrowhead on a ribbon is part of the ribbon, not a marker: the shape
    //: is closed, so a `marker-end` would be placed at the end of the outline,
    //: which is back at the parent. The body therefore stops short and the last
    //: sixth of the run becomes a barb and a tip, which is also the only way the
    //: head can taper out of a shape whose width is already varying.
    const arrow = wbMapEdgeHasArrow(child);
    const bodyEnd = arrow ? 0.84 : 1;
    const left = [];
    const right = [];
    const halfAt = (t) => weight * (WB_MAP_RIBBON_THIN
      + (WB_MAP_RIBBON_WIDE - WB_MAP_RIBBON_THIN) * (1 - t) * (1 - t)) / 2;
    //: More samples on a longer branch (INBOX 609): one per 40 units of chord
    //: past the 24 a short branch has always had, so the spline below is never
    //: asked to bridge a long stretch of a changing width on two points.
    const steps = Math.min(96, Math.max(WB_MAP_RIBBON_STEPS, Math.ceil(Math.hypot(p1.x - p0.x, p1.y - p0.y) / 40)));
    for (let i = 0; i <= steps; i += 1) {
      //: Eased rather than linear, so the branch keeps its weight for the first
      //: part of its run and tapers over the second, which is how a real branch
      //: (and Coggle's) looks; a straight ramp reads as a wedge.
      const t = (i / steps) * bodyEnd;
      const point = wbMapCubicAt(t, p0, c0, c1, p1);
      const length = Math.hypot(point.dx, point.dy) || 1;
      const nx = -point.dy / length;
      const ny = point.dx / length;
      const half = halfAt(t);
      left.push([point.x + nx * half, point.y + ny * half]);
      right.push([point.x - nx * half, point.y - ny * half]);
    }
    let tip = null;
    if (arrow) {
      const barb = wbMapCubicAt(bodyEnd, p0, c0, c1, p1);
      const length = Math.hypot(barb.dx, barb.dy) || 1;
      const nx = -barb.dy / length;
      const ny = barb.dx / length;
      // Wide enough to read as a head against the body it grew out of, and
      // scaled with the branch so a thin line does not get a fat point.
      const wide = Math.max(halfAt(bodyEnd) * 2.4, 3.4 * weight);
      left.push([barb.x + nx * wide, barb.y + ny * wide]);
      right.push([barb.x - nx * wide, barb.y - ny * wide]);
      const end = wbMapCubicAt(1, p0, c0, c1, p1);
      tip = [end.x, end.y];
    }
    const at = ([x, y]) => `${Math.round(x * 10) / 10} ${Math.round(y * 10) / 10}`;
    const forward = `M${at(left[0])}${wbMapSmoothThrough(left, at)}`;
    const point = tip ? `L${at(tip)}` : "";
    right.reverse();
    const back = `L${at(right[0])}${wbMapSmoothThrough(right, at)}`;
    return `${forward}${point}${back}Z`;
  }

  //: **Each side of a ribbon is a curve, not a polyline** (INBOX 609: "on
  //: longer mind map links, I can actually see the hard bends in the line and
  //: it isnt a smooth curve"). The sides used to be the samples joined by `L`,
  //: which is smooth while a segment is a few pixels long and shows every
  //: corner once a branch runs a thousand units and the view zooms in: the
  //: sweep (`bm1005-curve.js`) measured 4.5 to 8 degrees of turn inside one
  //: unit of outline, at every sample, on four long branches.
  //:
  //: A Catmull-Rom spline through the same samples, written as one cubic per
  //: span: each span's two controls sit a sixth of the way along the chord
  //: between its neighbours, so the tangent is shared at every sample and the
  //: outline has no corner anywhere along a side (only the three it means to
  //: have: the parent end, the barb and the tip). The ends reflect their
  //: neighbour rather than repeat themselves, so the first and last spans keep
  //: their slope instead of flattening into the node.
  function wbMapSmoothThrough(points, at) {
    const n = points.length;
    let d = "";
    for (let i = 0; i + 1 < n; i += 1) {
      const p1 = points[i];
      const p2 = points[i + 1];
      const p0 = i > 0 ? points[i - 1] : [2 * p1[0] - p2[0], 2 * p1[1] - p2[1]];
      const p3 = i + 2 < n ? points[i + 2] : [2 * p2[0] - p1[0], 2 * p2[1] - p1[1]];
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += `C${at(c1)} ${at(c2)} ${at(p2)}`;
    }
    return d;
  }

  //: Which of the two drawings this edge gets. One place, because the render,
  //: the per-frame drag update and the class that styles it all have to agree:
  //: a ribbon painted with a stroke rule is a blob, and a stroke painted with a
  //: fill rule is invisible.
  function wbMapEdgeIsRibbon(child) {
    const themed = wbMapThemedData(child);
    return (themed.edge_style || WB_MAP_LAYOUT_EDGE[child._bl || wbMapLayout()] || "curve") === "curve" && !themed.edge_dashed;
  }

  //: The tree edges touching `id` (its own edge up to its parent, and one per
  //: child), each with the `<path>` that drew it, collected once per drag.
  //:
  //: **This is the single-node half of the "connections get left behind when i
  //: move the notes/nodes around" report** (INBOX 42, with a screenshot of a
  //: curve attached to neither node). A tree edge is not a link sketch, so
  //: `wbUpdateLinkedSketches` never touched one, and nothing else ran between
  //: `dragStart` and the drop: measured before this fix, the edge sat 155.6px
  //: from the node it joins through a single-node drag, and stayed there after
  //: the drop for any node already pinned (`wbMapPinOnDrag` returns early once
  //: `data.pinned` is set, so its `wbScheduleRender` never fired a second
  //: time). Precomputed for the same reason `wbLinkedSketchesFor` is: a node
  //: gains or loses a parent between drags, never during one.
  //:
  //: **The three lines an edge is drawn from, found in one pass over the edge
  //: group rather than by three document-wide attribute queries per edge**
  //: (MINDMAP_PLAN.md §13a). `wbCaptureBulkMoveOrigin` calls `wbMapEdgesFor`
  //: once per topic in a dragged branch, so on a 500-topic map the old shape
  //: ran several thousand `document.querySelector` calls, and rebuilt the map
  //: index and read the layout once per topic on top of them, all before the
  //: pointer had moved. Passing one context in makes the whole capture linear
  //: in the branch rather than quadratic in the board.
  function wbMapEdgeContext() {
    const els = new Map();
    const group = document.querySelector(".wb-map-edges");
    if (group) {
      for (const el of group.querySelectorAll(
        ".wb-map-edge, .wb-map-edge-hit, .wb-map-edge-handle, .wb-map-edge-label"
      )) {
        const key = `${el.dataset.parent}:${el.dataset.child}`;
        let slot = els.get(key);
        if (!slot) els.set(key, (slot = {}));
        // `wb-map-edge` is the visible path's own token; the ribbon, dash and
        // thickness classes ride alongside it on the same element, and the twin
        // and the handle carry neither it nor each other.
        if (el.classList.contains("wb-map-edge")) slot.el = el;
        else if (el.classList.contains("wb-map-edge-hit")) slot.hit = el;
        else if (el.classList.contains("wb-map-edge-label")) slot.label = el;
        else slot.grip = el;
      }
    }
    return { index: wbMapIndex(), layout: wbMapLayout(), els };
  }

  function wbMapEdgesFor(id, ctx) {
    if (!wbIsMap()) return [];
    const { index, layout, els } = ctx || wbMapEdgeContext();
    const self = index.byId.get(id);
    if (!self) return [];
    const found = [];
    const add = (parent, child) => {
      const slot = els.get(`${parent.id}:${child.id}`);
      // No element means the edge is not drawn right now (a collapsed or
      // filtered branch), which is not an error: there is simply nothing to
      // follow the drag.
      if (!slot || !slot.el) return;
      // The invisible twin has to follow the drag as well, or the line you can
      // point at stays where the line used to be: a target that is right until
      // the first time anything moves is worse than no target.
      if (slot.hit) slot.el._wbHitTwin = slot.hit;
      // And the waypoint handle (§12.1 item 5's third), for the same reason the
      // hit twin is here: a handle that stays where the line used to be is a
      // control pointing at nothing the moment either end of the line moves.
      if (slot.grip) slot.el._wbHandle = slot.grip;
      //: And the line's label (INBOX 818, the owner: "labels on mind map links
      //: dont move with the links"): it was left at the old place for the whole
      //: of a drag and only caught up at the drop's full render.
      slot.el._wbLabel = slot.label || null;
      found.push({ parent, child, el: slot.el, layout });
    };
    const parent = self.parent_id != null ? index.byId.get(self.parent_id) : null;
    if (parent) add(parent, self);
    for (const child of index.childrenOf.get(id) || []) add(self, child);
    return found;
  }

  //: Redraws the edges `wbMapEdgesFor` collected, without a full render. Same
  //: bargain as `wbUpdateLinkedSketches`: a full `renderWhiteboardNow()` on
  //: every mousemove frame re-binds every card, sketch and object on the board
  //: for the sake of two curves, which is the "glitchy and slow to update"
  //: report this file already carries.
  function wbUpdateMapEdges(edges) {
    for (const { parent, child, el, layout } of edges || []) {
      const d = wbMapEdgePathD(parent, child, layout);
      //: Drawn by hand: the render's cache no longer holds what is on screen.
      el._wbMoved = true;
      // The visible path is the ribbon where the edge has one; the hit twin is
      // always the centreline, which is what a person is actually pointing at.
      el.setAttribute("d", wbMapEdgeIsRibbon(child) ? wbMapRibbonD(parent, child, layout) : d);
      if (el._wbHitTwin) el._wbHitTwin.setAttribute("d", d);
      if (el._wbEnds) wbMapPlaceEdgeEnds(el, wbMapEdgeEndPoints(parent, child, layout));
      if (el._wbHandle) {
        const point = wbMapEdgeHandlePoint(parent, child, layout);
        el._wbHandle.setAttribute("cx", String(point.x));
        el._wbHandle.setAttribute("cy", String(point.y));
      }
      if (el._wbLabel) {
        const point = wbMapEdgeHandlePoint(parent, child, layout);
        el._wbLabel.setAttribute("x", String(point.x + (Number(child.data?.edge_label_dx) || 0)));
        el._wbLabel.setAttribute("y", String(point.y + (Number(child.data?.edge_label_dy) || 0)));
      }
    }
  }

  //: Every tree line that is drawn, as its two topics and its key, in the
  //: tree's own order: the one walk the lines and the mid-line `+` buttons
  //: share, so their orders cannot disagree.
  function wbMapVisibleEdges(index, hidden) {
    const edges = [];
    for (const parent of index.nodes) {
      if (hidden.has(parent.id) || parent.data?.collapsed) continue;
      for (const child of index.childrenOf.get(parent.id) || []) {
        if (!hidden.has(child.id)) edges.push({ parent, child, key: `${parent.id}:${child.id}` });
      }
    }
    return edges;
  }

  //: Take out of a keyed cache (`{ wrap }` or an element) every entry whose key
  //: is no longer wanted.
  function wbMapDropStale(cache, wanted) {
    for (const [key, held] of cache) {
      if (wanted.has(key)) continue;
      (held.wrap || held).remove();
      cache.delete(key);
    }
  }

  //: The parent→child edges, drawn as cubic curves into their own group.
  //:
  //: A tree edge is deliberately **not** a link sketch. A sketch is a row in the
  //: database that has to be created, moved and deleted alongside the node it
  //: joins, and `parent_id` already says everything an edge means, so the edge
  //: is derived on every render and there is no second thing to keep in step.
  //: Cross-links stay real sketches, because they are the edges `parent_id`
  //: cannot express (§9.1).
  //:
  //: The group is the first child of the zoom group so edges sit *under* every
  //: sketch and node, which is the only z-order a tree reads correctly in.
  function wbRenderMapEdges({ only = null } = {}) {
    const zoomGroup = document.getElementById("wb-zoom-group");
    if (!zoomGroup) return;
    let group = zoomGroup.querySelector(".wb-map-edges");
    if (!wbIsMap()) {
      group?.remove();
      return;
    }
    if (!group) {
      group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "wb-map-edges");
      group.setAttribute("aria-hidden", "true");
      zoomGroup.insertBefore(group, zoomGroup.firstChild);
    }
    const index = wbMapIndex();
    const colors = wbMapNodeColors(index);
    const hidden = wbMapConcealed(index);
    const layout = wbMapLayout();
    //: **A line is keyed by its two ends and updated in place**
    //: (MINDMAP_PLAN.md §13a, the render pass). This loop used to build four
    //: SVG elements per edge and `replaceChildren` the lot on every render: at
    //: 500 topics that is two thousand elements created, wired and thrown away
    //: because one of them moved, and it measured 122.2ms of a 527ms render.
    //:
    //: The old note here said an edge has no identity of its own, it *is* its
    //: two endpoints, so there was nothing for a join to key on. The first half
    //: is still true and the conclusion was wrong: those two endpoints are a
    //: perfectly good key, and `wbMapEdgesFor` has been finding a line by them
    //: mid-drag ever since. What an edge does not have is a *row*, which is why
    //: this is a hand-rolled cache rather than a d3 data join.
    //:
    //: The cache hangs off the group element, not off the module: a board that
    //: is not a map removes the group above, which takes the cache with it, so
    //: a stale element can never be handed to the next board.
    const cache = group._wbMapEdges instanceof Map ? group._wbMapEdges : (group._wbMapEdges = new Map());
    const edges = wbMapVisibleEdges(index, hidden);
    //: **Lines whose two ends are no longer joined go first** (OPEN 813): a
    //: re-parent, a delete, a folded branch, and the line a new topic's
    //: provisional id drew. Left until after the placing pass below, a stale
    //: line kept its slot and every later line looked out of place and was
    //: moved (84 nodes removed from layout on a 20-topic map).
    wbMapDropStale(cache, new Set(edges.map((edge) => edge.key)));
    //: **The group stays in the tree's own order**, which is what rebuilding it
    //: gave for free. Two things read that order: SVG paints in document order,
    //: so it decides which of two overlapping lines is on top, and
    //: `mapstrip.js` pairs the first line with the first mid-line `+` (the
    //: pluses are still rebuilt in index order). Appending new lines at the end
    //: instead cost that sweep its insert check, which is the order saying out
    //: loud that it is load-bearing. Nothing moves while the tree is unchanged:
    //: this compares first and writes only when a line is out of place.
    edges.forEach(({ parent, child, key }, slot) => {
      let held = cache.get(key);
      //: `isConnected`, because something else can take the element out from
      //: under this cache: `group.remove()` above on a board that stopped
      //: being a map, and an export that clones and replaces the layer.
      const drawn = Boolean(held && held.wrap.isConnected);
      //: **`only`: the topics whose lines are drawn again** (OPEN 813). The render
      //: after the server's answer to an add changes one topic's id and nothing's
      //: place; it drew every line again (22ms of 49 on 200 topics).
      if (!(only && drawn && !only.has(parent.id) && !only.has(child.id))) {
        //: **A line is worked out only when something it reads has changed**
        //: (wbp2): the geometry is 75us a line (15ms at 200 topics) and the key
        //: over its inputs is a string. A hand-drawn line (`wbUpdateMapEdges`
        //: writes the path per drag frame and marks it) forgets what it holds.
        if (drawn && held.path._wbMoved) {
          held.path._wbMoved = false;
          held.key = held.paint = null;
        }
        const geomKey = wbMapEdgeKey(parent, child, layout, colors);
        if (!drawn) {
          const wrap = wbMapEdgeElement(parent.id, child.id);
          cache.set(key, (held = { wrap, path: wrap.querySelector("path.wb-map-edge"), key: null, paint: null }));
        }
        if (held.key !== geomKey) {
          const geom = wbMapEdgeGeometry(parent, child, layout, colors);
          held.key = geomKey;
          if (held.paint !== geom.paint) {
            wbMapEdgeApply(held.wrap, geom);
            held.paint = geom.paint;
          }
        }
      }
      const wrap = held.wrap;
      if (group.childNodes[slot] !== wrap) group.insertBefore(wrap, group.childNodes[slot] || null);
    });
    wbRenderMapEdgePluses(edges, layout, only);
    wbSyncMapEdgeHandles();
  }

  //: **Everything `wbMapEdgeGeometry` reads, as one string** (wbp2): both ends'
  //: place and rendered box, the layout and the branch's own, which end is the
  //: tree's root, the four themed fields the line's look resolves (the topic's
  //: own, its level's, the map's), the topic's own bend, pinned sides and label,
  //: and its branch colour. `tests/test_map_edge_cache.py` changes each in turn
  //: and fuzzes them together: an input the geometry starts reading goes here,
  //: or that test fails. Cheaper than the geometry by a factor of thirty, which
  //: is the whole of why it exists.
  function wbMapEdgeKey(parent, child, layout, colors) {
    const p = wbMapNodeSize(parent);
    const c = wbMapNodeSize(child);
    const themed = wbMapThemedData(child);
    const own = child.data || WB_MAP_NO_THEME;
    return `${layout}|${child._bl}|${child._blTop}|${parent.id}|${parent.parent_id == null}|${parent.x},${parent.y},${p.w},${p.h}|${child.x},${child.y},${c.w},${c.h}|${themed.edge_style}|${themed.edge_dashed}|${themed.edge_width}|${themed.edge_arrow}|${own.edge_from}|${own.edge_to}|${own.edge_slide}|${own.edge_bend}|${own.edge_label}|${own.edge_label_dx}|${own.edge_label_dy}|${own.edge_label_size}|${own.edge_label_bold}|${own.edge_label_color}|${own.edge_label_chip}|${colors.get(child.id)}`;
  }

  //: Everything one tree edge draws, worked out from the two topics it joins,
  //: plus `paint`: the same values as one string, which is what decides whether
  //: the line already on screen is the line this render wants. A property this
  //: function starts reading goes into `paint` too, exactly as it does for a
  //: node's own `wbObjectPaintKey`.
  function wbMapEdgeGeometry(parent, child, layout, colors) {
    const ribbon = wbMapEdgeIsRibbon(child);
    //: The line's own classes (MINDMAP_PLAN.md item 177). Thickness is a class
    //: rather than a `stroke-width` attribute for the same reason the colour is
    //: a custom property: a presentation attribute sits below every author
    //: rule, so `.wb-map-edge`'s own `stroke-width` would win and the control
    //: would do nothing. The ribbon needs no thickness class, since its width
    //: is in the path it is drawn from, and no arrow class, since its head is
    //: too.
    const classes = ["wb-map-edge"];
    if (ribbon) classes.push("wb-map-edge-ribbon");
    else {
      const themedEdge = wbMapThemedData(child);
      if (themedEdge.edge_dashed) classes.push("wb-map-edge-dashed");
      const width = wbMapDrawn(themedEdge, "edge_width");
      if (width) classes.push(`wb-map-edge-${width}`);
      if (!wbMapEdgeHasArrow(child)) classes.push("wb-map-edge-headless");
    }
    //: The centreline, which is both the plain line's own path and, for a
    //: ribbon, the hit target underneath it: a stroke around a closed shape is
    //: a hit area shaped like a hoop, with a hole down the middle of the very
    //: line it is supposed to catch.
    const line = wbMapEdgePathD(parent, child, layout);
    const className = classes.join(" ");
    const d = ribbon ? wbMapRibbonD(parent, child, layout) : line;
    const grip = wbMapEdgeHandlePoint(parent, child, layout);
    const ends = wbMapEdgeEndPoints(parent, child, layout);
    const colour = colors.get(child.id) || "";
    //: What the line says (§12.1 items 3 and 4), at the curve's own middle.
    //: `wbMapEdgeHandlePoint` rather than the anchors' own midpoint: for an
    //: unbent line the two are the same point (the curve passes through it at
    //: t = 0.5, worked out in `wbMapEdgeCubic`), and for a bent one this is the
    //: one that is still on the line.
    const label = child.data?.edge_label ? String(child.data.edge_label) : "";
    const ldx = Number(child.data?.edge_label_dx) || 0;
    const ldy = Number(child.data?.edge_label_dy) || 0;
    const lx = grip.x + ldx;
    const ly = grip.y + ldy;
    //: The label's look is the board connector's (size, bold, colour, chip;
    //: `wbPaintLinkLabel`), kept on the topic beside the label itself.
    const own = child.data || WB_MAP_NO_THEME;
    const look = `${Number(own.edge_label_size) > 0 ? Number(own.edge_label_size) : ""}|${own.edge_label_bold ? 1 : ""}|${typeof own.edge_label_color === "string" ? own.edge_label_color : ""}|${own.edge_label_chip ? 1 : ""}`;
    return {
      className, d, line, grip, ends, colour, label, lx, ly, look,
      paint: `${className}|${d}|${line}|${grip.x},${grip.y}|${ends.from.x},${ends.from.y},${ends.to.x},${ends.to.y}|${colour}|${label}|${lx},${ly}|${look}`,
    };
  }

  //: One edge's elements, with no geometry on them yet: built once per edge and
  //: then kept, which is what `wbRenderMapEdges`'s cache is for.
  //:
  //: **One `<g>` per edge**, so the whole line is one hover target: the stroke,
  //: the target twin and the handle together. That is what lets the handle be
  //: revealed by pointing at the line (§12.1 item 5's third, and Coggle's own
  //: gesture) rather than only by selecting a topic, and it matters for a
  //: reason the first build of this measured: the map strip opens 44px above
  //: the selected topic and is several hundred pixels wide, so for a child laid
  //: out a little below its parent the strip lands exactly on the middle of the
  //: line into it. Measured on a child 200 units below its trunk:
  //: `elementFromPoint` at the handle's own centre returned the strip, and the
  //: drag never started. Hover needs no selection, so it needs no strip.
  //:
  //: Nothing keys off the group's own shape: every selector in this file and in
  //: the sweeps reaches an edge by class under `.wb-map-edges`.
  function wbMapEdgeElement(parentId, childId) {
    const NS = "http://www.w3.org/2000/svg";
    const wrap = document.createElementNS(NS, "g");
    wrap.setAttribute("class", "wb-map-edge-group");
    const path = document.createElementNS(NS, "path");
    path.setAttribute("class", "wb-map-edge");
    // The two ends' ids, so a drag can find *this* edge again and redraw it per
    // frame (`wbMapEdgesFor`), and so this render can find it again next time.
    path.setAttribute("data-parent", String(parentId));
    path.setAttribute("data-child", String(childId));
    wrap.appendChild(path);
    //: The same curve again, transparent and wide enough to grab (§12.1 item
    //: 4). Appended *after* the visible path so it sits above it in the group,
    //: which is what an SVG hit test needs; it is invisible either way, and the
    //: visible line is inert.
    const hit = document.createElementNS(NS, "path");
    hit.setAttribute("class", "wb-map-edge-hit");
    hit.setAttribute("data-parent", String(parentId));
    hit.setAttribute("data-child", String(childId));
    wrap.appendChild(hit);
    //: **The waypoint handle** (§12.1 item 5's third): the third target on a
    //: line, after the visible stroke and the invisible one you can point at. A
    //: circle rather than a button because it has to sit *on* the line at a
    //: board coordinate and scale with the zoom, which is what the edge group
    //: already is; the mid-line `+` is HTML for the opposite reason (it is a
    //: button from the app's own ramp).
    //:
    //: Drawn for every line and shown only for the selected topic's own
    //: (`wbSyncMapEdgeHandles`), so a map of two hundred lines is not a map of
    //: two hundred grab dots, which is the same rule the `+` follows.
    const handle = document.createElementNS(NS, "circle");
    handle.setAttribute("class", "wb-map-edge-handle");
    handle.setAttribute("r", "7");
    handle.setAttribute("data-parent", String(parentId));
    handle.setAttribute("data-child", String(childId));
    //: The same sentence the link's own bend grip carries, because it is the
    //: same control: a `<title>` is the tooltip an SVG shape gets, and it is
    //: the only place either gesture is written down on the thing itself.
    const gripTitle = document.createElementNS(NS, "title");
    gripTitle.textContent = "Drag to bend this line · double-click to straighten";
    handle.appendChild(gripTitle);
    wbWireMapEdgeHandle(handle, parentId, childId);
    wrap.appendChild(handle);
    //: **The line's two ends** (K31): shown with the waypoint, dragged round a
    //: topic to pin the side the line leaves or enters, double-clicked to put
    //: that end back on Auto. Kept on the path so a drag frame moves them with
    //: no lookup.
    path._wbEnds = ["from", "to"].map((end) => {
      const grip = document.createElementNS(NS, "circle");
      grip.setAttribute("class", "wb-map-edge-end");
      grip.setAttribute("r", "6");
      grip.dataset.end = end;
      const tip = document.createElementNS(NS, "title");
      tip.textContent = end === "from"
        ? "Drag round the topic above to choose the side this line leaves · double-click for Auto"
        : "Drag round this topic to choose the side this line enters · double-click for Auto";
      grip.appendChild(tip);
      wbWireMapEdgeEnd(grip, parentId, childId, end);
      wrap.appendChild(grip);
      return grip;
    });
    //: On the group, not on the hit stroke: a right-click and a hold belong to
    //: the *line*, and the line now has two targets in it. Wired on the stroke
    //: alone, the ring stopped opening wherever the handle was, since the
    //: handle is a sibling of the stroke and the event never reached it
    //: (measured by `mapstrip.js`, which caught it the moment the handle
    //: landed: "right-click on a line opens the line's own ring" came back
    //: `open: false`). This is the same fault the mid-line `+` already carries
    //: its own forwarding for, and the same fix one level up: every part of the
    //: line answers the line's own gestures.
    wbWireMapEdgeGestures(wrap, childId);
    return wrap;
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { WB_MAP_SIDES, wbMapFacingSide, wbMapEdgeAnchors, wbMapEdgeWaypoint, wbMapEdgeFractions, wbMapEdgeCubic, wbMapElbowPoints, WB_MAP_EDGE_CONTROL_GAP, wbMapEdgeHandlePoint, wbMapEdgePathD, wbMapEdgeWeight, wbMapEdgeHasArrow, wbMapCubicAt, wbMapRibbonD, wbMapEdgeIsRibbon, wbMapEdgeContext, wbMapEdgesFor, wbUpdateMapEdges, wbMapDropStale, wbRenderMapEdges });
})();
