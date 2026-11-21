(() => {
  // whiteboard-caps.js: shape paths and arrow heads, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: Every cap kind a line/arrow/link end can wear, asked for directly ("a
  //: full line/arrow end-cap system... circle/square/multi-line ends,
  //: independently per end"), the shared arrowhead control only ever grew
  //: from Arrow-only to Line-and-Arrow, still one shape. Each is its own
  //: closed subpath appended to the shaft's own `d`, same convention
  //: `wbArrowHeadPath` already established (a stroked path, no separate SVG
  //: element, so hit-testing/move/resize/export keep treating the whole
  //: sketch as the one path they already know how to handle), "arrow" here
  //: is exactly `wbArrowHeadPath`'s own two-line V, kept for a single call
  //: site to switch on.
  //: **The plain ends, drawn closed or open** (INBOX 792, the owner: "there is
  //: only one actual arrow option for the links"): `arrow` is the open V,
  //: `triangle` the solid arrowhead, `diamond` and `diamond-filled` the UML
  //: aggregation and composition marks, `bar` a stop line at the tip. A filled
  //: end is a closed outline with smaller copies of itself inside it, a stroke's
  //: width apart: the end stays one more subpath of the shaft's own `d`, so a
  //: line with a solid head is still one stroked path (hit-testing, move,
  //: resize and every export read it as before) and no end needs a fill.
  //: `triangle-open` (UML's inheritance mark) and `circle-filled` were added for
  //: the owner's "more arrow options" (2026-10-11): the hollow triangle stops the
  //: shaft at its base like the other hollow ends; the filled circle is rings
  //: stepping in by a stroke width, the solid ends' own trick.
  //: The plan's decision E2 (WHITEBOARD_PLAN, INBOX 826) added `stealth` (the
  //: concave arrow), `cross`, `half-arrow` and `double-arrow`; its "dot" is the
  //: filled circle already here. E3 added `memorymap`, the signature end.
  const WB_CAP_KINDS = ["none", "memorymap", "arrow", "triangle", "triangle-open", "stealth", "diamond", "diamond-filled", "bar", "circle", "circle-filled", "square", "multiline", "cross", "half-arrow", "double-arrow", "er-one", "er-one-only", "er-zero-one", "er-many", "er-one-many", "er-zero-many"];

  //: The entity-relationship ends (the features audit W4): what is nearest the
  //: line's body, then what is at the tip. `null` near: one mark only.
  const WB_ER_CAPS = {
    "er-one": [null, "one"],
    "er-one-only": ["one", "one"],
    "er-zero-one": ["zero", "one"],
    "er-many": [null, "many"],
    "er-one-many": ["one", "many"],
    "er-zero-many": ["zero", "many"],
  };

  //: Two head-stroke subpaths meeting at `(tipX, tipY)`, angled back from
  //: `approachAngle` (the direction the shaft arrives *from*, in radians), 
  //: factored out so both ends of an arrow can draw one (`currentArrowEndStyle`,
  //: reported directly: "can't change arrow heads").
  //: The box a shape tool draws from the press `(sx, sy)` to the pointer: corner
  //: to corner; Shift makes it square, grown towards the pointer so a drag up
  //: and left still ends under it (it straddled the press, INBOX 1352 gap 1);
  //: Alt draws it from its centre, as Alt resizes from the centre (decision
  //: 40). One model for every closed shape, the ellipse included.
  function wbDragBox(sx, sy, x, y, mods = {}) {
    let dx = x - sx, dy = y - sy;
    if (mods.shiftKey) {
      const side = Math.max(Math.abs(dx), Math.abs(dy));
      dx = Math.sign(dx || 1) * side;
      dy = Math.sign(dy || 1) * side;
    }
    const w = Math.abs(dx), h = Math.abs(dy);
    if (mods.altKey) return { x: sx - w, y: sy - h, w: 2 * w, h: 2 * h };
    return { x: Math.min(sx, sx + dx), y: Math.min(sy, sy + dy), w, h };
  }

  //: The ellipse in the box `wbDragBox` gives the same drag (dogfood
  //: 2026-10-25 item 7: it used to centre on the press by default).
  function wbEllipseDrawD(sx, sy, x, y, mods = {}) {
    const { x: left, y: top, w, h } = wbDragBox(sx, sy, x, y, mods);
    const rx = w / 2, ry = h / 2;
    return `M ${left} ${top + ry} a ${rx} ${ry} 0 1 0 ${w} 0 a ${rx} ${ry} 0 1 0 ${-w} 0`;
  }

  //: Shift snaps a line's far end to the nearest 45 degrees, keeping its
  //: length (INBOX 1352 gap 3).
  function wbSnap45(sx, sy, x, y) {
    const step = Math.PI / 4;
    const angle = Math.round(Math.atan2(y - sy, x - sx) / step) * step;
    const d = Math.hypot(x - sx, y - sy);
    return [sx + Math.round(Math.cos(angle) * d * 100) / 100, sy + Math.round(Math.sin(angle) * d * 100) / 100];
  }

  //: A closed shape's path in its drawn box. Plain `L` commands for the
  //: triangle and diamond, as the pen and line tools use, so
  //: wbTransformPathD and wbPathBBox have no new command to learn.
  function wbClosedShapeD(tool, { x, y, w, h }) {
    if (tool === "rect") return `M ${x} ${y} h ${w} v ${h} h ${-w} Z`;
    if (tool === "triangle") return `M ${x + w / 2} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
    if (tool === "diamond") return `M ${x + w / 2} ${y} L ${x + w} ${y + h / 2} L ${x + w / 2} ${y + h} L ${x} ${y + h / 2} Z`;
    const more = WB_MORE_SHAPES[tool];
    return more ? more.d(x, y, Math.max(w, 1), Math.max(h, 1)) : "";
  }

  function wbArrowHeadPath(tipX, tipY, approachAngle, headLen) {
    const h1x = tipX - headLen * Math.cos(approachAngle - Math.PI / 6);
    const h1y = tipY - headLen * Math.sin(approachAngle - Math.PI / 6);
    const h2x = tipX - headLen * Math.cos(approachAngle + Math.PI / 6);
    const h2y = tipY - headLen * Math.sin(approachAngle + Math.PI / 6);
    return `M ${tipX} ${tipY} L ${h1x} ${h1y} M ${tipX} ${tipY} L ${h2x} ${h2y}`;
  }
  //: **An end's size** (decision E2): small, medium or large, beside each end
  //: menu, stored per end as `startCapSize`/`endCapSize` ("s" or "l"; absent
  //: is medium, so every saved line keeps its look). It scales the end's
  //: length, never the stroke the solid ends step in by.
  const WB_CAP_SIZE_SCALE = { s: 0.7, l: 1.45 };
  const WB_SOLID_CAPS = new Set(["triangle", "diamond-filled"]);
  function wbCapScale(size) {
    return WB_CAP_SIZE_SCALE[size] || 1;
  }
  //: The stored fields for caps read by `wbLinkCaps`/`wbSketchCaps`: medium
  //: (or anything unknown) clears the field.
  function wbCapSizeFields(caps) {
    const keep = (v) => (WB_CAP_SIZE_SCALE[v] ? v : undefined);
    return { startCapSize: keep(caps.startSize), endCapSize: keep(caps.endSize) };
  }
  //: **A hollow end stops the shaft at its own edge.** An outline diamond,
  //: circle or square drew the shaft on through its middle to the tip (the
  //: owner: the shaft shows through the shape). How far back from the tip the
  //: shape reaches along the line is the inset: the diamond's rear point, the
  //: circle's and the square's diameter. Solid ends and open marks need none.
  const WB_HOLLOW_INSET = { diamond: (h) => h * 1.1, "triangle-open": (h) => h, circle: (h) => (h * 2) / 3, square: (h) => (h * 2) / 2.6 };
  function wbHollowInset(kind, headLen) {
    return WB_HOLLOW_INSET[kind]?.(headLen) || 0;
  }

  //: `pt` moved toward `toward` by the cap's inset (never past 90% of the way, so
  //: a short segment keeps a stub), or `pt` itself under any other cap.
  function wbShaftEnd(pt, toward, cap, headLen, size) {
    const inset = wbHollowInset(cap, headLen * wbCapScale(size));
    const dist = Math.hypot(toward.x - pt.x, toward.y - pt.y);
    if (!inset || !dist) return pt;
    const share = Math.min(inset, dist * 0.9) / dist;
    return { x: pt.x + (toward.x - pt.x) * share, y: pt.y + (toward.y - pt.y) * share };
  }

  function wbCapPath(kind, tipX, tipY, approachAngle, headLen, size) {
    if (!kind || kind === "none") return "";
    //: The solid ends step in by the line's own width, read before the size
    //: scales the length (the head is `width * 4 + 6` long at medium).
    const stroke = Math.max(1, (headLen - 6) / 4);
    headLen *= wbCapScale(size);
    if (kind === "arrow") return wbArrowHeadPath(tipX, tipY, approachAngle, headLen);
    const extra = wbCapPathMore(kind, tipX, tipY, approachAngle, headLen, stroke);
    if (extra !== null) return extra;
    // The entity-relationship ends (the features audit W4, draw.io's ER set):
    // a bar for "one", a ring for "zero" and the crow's foot for "many", read
    // from the shape outward, so "zero-many" is a ring nearest the line's body
    // and the foot at the tip. Each part is drawn back from the tip by a fixed
    // share of the head length, so the marks keep apart at every line width.
    if (WB_ER_CAPS[kind]) {
      const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
      const perpX = -sin, perpY = cos;
      const half = headLen * 0.45;
      const at = (back) => ({ x: tipX - cos * back, y: tipY - sin * back });
      const bar = (back) => {
        const p = at(back);
        return `M ${p.x - perpX * half} ${p.y - perpY * half} L ${p.x + perpX * half} ${p.y + perpY * half}`;
      };
      const ring = (back) => {
        const r = headLen * 0.22, p = at(back + r);
        return `M ${p.x - r} ${p.y} A ${r} ${r} 0 1 0 ${p.x + r} ${p.y} A ${r} ${r} 0 1 0 ${p.x - r} ${p.y} Z`;
      };
      const foot = () => {
        const root = at(headLen * 0.7);
        return `M ${root.x} ${root.y} L ${tipX + perpX * half} ${tipY + perpY * half} M ${root.x} ${root.y} L ${tipX - perpX * half} ${tipY - perpY * half}`;
      };
      const [near, far] = WB_ER_CAPS[kind];
      const tip = far === "many" ? foot() : bar(headLen * 0.3);
      const inner = near === "zero" ? ring(headLen * 0.85) : bar(headLen * 0.85);
      return near ? `${inner} ${tip}` : tip;
    }
    if (kind === "bar") {
      const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
      const half = headLen * 0.5;
      return `M ${tipX - sin * half} ${tipY + cos * half} L ${tipX + sin * half} ${tipY - cos * half}`;
    }
    if (kind === "triangle" || kind === "triangle-open" || kind === "diamond" || kind === "diamond-filled") {
      const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
      //: Points in the line's own frame: along (back from the tip) and across.
      const shape = kind === "triangle" || kind === "triangle-open"
        ? [[0, 0], [headLen, headLen * 0.4], [headLen, -headLen * 0.4]]
        : [[0, 0], [headLen * 0.55, headLen * 0.34], [headLen * 1.1, 0], [headLen * 0.55, -headLen * 0.34]];
      const mid = [shape.reduce((n, p) => n + p[0], 0) / shape.length, 0];
      const draw = (scale) => {
        const pts = shape.map(([back, across]) => {
          const b = mid[0] + (back - mid[0]) * scale, a = across * scale;
          return `${+(tipX - cos * b - sin * a).toFixed(2)} ${+(tipY - sin * b + cos * a).toFixed(2)}`;
        });
        return `M ${pts.join(" L ")} Z`;
      };
      if (!WB_SOLID_CAPS.has(kind)) return draw(1);
      //: The copies step in by a stroke width, until one would be thinner than
      //: the stroke itself.
      const reach = Math.min(...shape.map(([back, across]) => Math.hypot(back - mid[0], across))) || headLen / 2;
      const step = (stroke * 0.8) / reach;
      const out = [];
      for (let scale = 1; scale > step * 0.5; scale -= step) out.push(draw(scale));
      return out.join(" ");
    }
    if (kind === "circle" || kind === "circle-filled") {
      const r = headLen / 3;
      // Centred a radius back from the tip along the shaft, so the circle
      // sits *at* the end rather than half hanging past it.
      const cx = tipX - r * Math.cos(approachAngle), cy = tipY - r * Math.sin(approachAngle);
      const ring = (q) => `M ${+(cx - q).toFixed(2)} ${+cy.toFixed(2)} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(cx + q).toFixed(2)} ${+cy.toFixed(2)} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(cx - q).toFixed(2)} ${+cy.toFixed(2)} Z`;
      if (kind === "circle") return `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
      //: Filled: rings a stroke's width apart down to the centre.
      const step = Math.max(0.8, stroke * 0.8);
      const out = [];
      for (let q = r; q > step * 0.25; q -= step) out.push(ring(q));
      return out.join(" ");
    }
    if (kind === "square") {
      const s = headLen / 2.6;
      const cx = tipX - s * Math.cos(approachAngle), cy = tipY - s * Math.sin(approachAngle);
      const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
      const corner = (dx, dy) => `${cx + dx * cos - dy * sin} ${cy + dx * sin + dy * cos}`;
      return `M ${corner(-s, -s)} L ${corner(s, -s)} L ${corner(s, s)} L ${corner(-s, s)} Z`;
    }
    // "multiline": two short perpendicular ticks near the tip, the
    // ER-diagram "many" mark, and a visually distinct third option from a
    // filled dot or square rather than a second arrow variant.
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    const perpX = -sin, perpY = cos;
    const half = headLen * 0.4;
    const tick = (back) => {
      const bx = tipX - cos * back, by = tipY - sin * back;
      return `M ${bx - perpX * half} ${by - perpY * half} L ${bx + perpX * half} ${by + perpY * half}`;
    };
    return `${tick(headLen * 0.35)} ${tick(headLen * 0.75)}`;
  }

  //: The two end-size menus show the selection's sizes, and sit dimmed beside
  //: an end with no mark (a size there would change nothing).
  function wbShowCapSizes(caps) {
    for (const which of ["start", "end"]) {
      const el = document.getElementById(`wb-prop-${which}size`);
      if (!el) continue;
      el.value = caps[`${which}Size`] || "m";
      const none = caps[`${which}Cap`] === "none";
      el.disabled = none;
      //: **No size for an end with no mark** (the 22-10 bug doc, the bar "too
      //: long and wide"): a greyed "Medium" beside "None" said nothing and was
      //: two of the line bar's widest controls. The size comes back with a mark.
      (el.closest(".select-shell") || el).classList.toggle("hidden", none);
    }
  }

  //: A filled triangle as copies of itself scaled about its centroid, a
  //: stroke's width apart (the solid ends' trick), until the next copy would be
  //: thinner than the stroke. `pts` are [x, y] board points.
  function wbFilledTriangle(pts, stroke) {
    const cx = (pts[0][0] + pts[1][0] + pts[2][0]) / 3, cy = (pts[0][1] + pts[1][1] + pts[2][1]) / 3;
    const side = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    const area = Math.abs((pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) - (pts[2][0] - pts[0][0]) * (pts[1][1] - pts[0][1])) / 2;
    const inradius = (2 * area) / (side(pts[0], pts[1]) + side(pts[1], pts[2]) + side(pts[2], pts[0]) || 1);
    //: At most half a step, so a slim triangle still gets a middle copy.
    const step = Math.min(0.5, (stroke * 0.8) / (inradius || 1));
    const out = [];
    for (let scale = 1; scale > 0 && (out.length === 0 || scale > step * 0.5); scale -= step) {
      out.push("M " + pts.map(([x, y]) => `${+(cx + (x - cx) * scale).toFixed(2)} ${+(cy + (y - cy) * scale).toFixed(2)}`).join(" L ") + " Z");
    }
    return out.join(" ");
  }

  //: The ends decisions E2 and E3 added, or null for any other kind. Each is
  //: drawn in the line's own frame: `at(back, across)` is a point `back` from
  //: the tip along the line and `across` to its side.
  function wbCapPathMore(kind, tipX, tipY, approachAngle, headLen, stroke) {
    const cos = Math.cos(approachAngle), sin = Math.sin(approachAngle);
    const at = (back, across) => [+(tipX - cos * back - sin * across).toFixed(2), +(tipY - sin * back + cos * across).toFixed(2)];
    const line = (a, b) => `M ${a[0]} ${a[1]} L ${b[0]} ${b[1]}`;
    const L = headLen;
    if (kind === "stealth") {
      //: The concave arrow: two filled halves meeting at the notch.
      const tip = at(0, 0), notch = at(L * 0.62, 0);
      return `${wbFilledTriangle([tip, at(L, L * 0.42), notch], stroke)} ${wbFilledTriangle([tip, notch, at(L, -L * 0.42)], stroke)}`;
    }
    if (kind === "cross") {
      const c = L * 0.45, h = L * 0.3;
      return `${line(at(c - h, -h), at(c + h, h))} ${line(at(c - h, h), at(c + h, -h))}`;
    }
    if (kind === "half-arrow") {
      return line(at(0, 0), at(L * Math.cos(Math.PI / 6), -L * Math.sin(Math.PI / 6)));
    }
    if (kind === "double-arrow") {
      const v = (back) => `${line(at(back, 0), at(back + L * 0.82, L * 0.44))} ${line(at(back, 0), at(back + L * 0.82, -L * 0.44))}`;
      return `${v(0)} ${v(L * 0.5)}`;
    }
    if (kind === "memorymap") {
      //: **The signature end** (decision E3): the brand mark's node, a dot at
      //: the end of a spoke a quarter its length across (favicon.svg: r 7.5 on
      //: a 30-unit spoke), sitting at the tip, with an open chevron behind it
      //: whose arms are the mark's spokes. Candidate A of three (C3).
      const r = L * 0.25;
      const centre = at(r, 0);
      const out = [];
      for (let q = r; q > Math.max(0.8, stroke * 0.8) * 0.25; q -= Math.max(0.8, stroke * 0.8)) {
        out.push(`M ${+(centre[0] - q).toFixed(2)} ${centre[1]} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(centre[0] + q).toFixed(2)} ${centre[1]} A ${+q.toFixed(2)} ${+q.toFixed(2)} 0 1 0 ${+(centre[0] - q).toFixed(2)} ${centre[1]} Z`);
      }
      const gap = r * 2 + stroke;
      out.push(`${line(at(gap, 0), at(gap + L * 0.8, L * 0.46))} ${line(at(gap, 0), at(gap + L * 0.8, -L * 0.46))}`);
      return out.join(" ");
    }
    return null;
  }

  function wbCursorForTool(tool, strokeColor, strokeWidth) {
    const color = /^#[0-9a-fA-F]{3,8}$/.test(strokeColor || "") ? strokeColor : "#ffffff";
    if (WB_BRUSH_TOOLS.has(tool)) {
      // A crosshair with a dot in the actual stroke colour at its centre, a
      // plain crosshair can't say what colour is about to land. The dot's own
      // radius now tracks the stroke-width slider too (asked for directly:
      // "the size should be represented on the cursor tip"), clamped to what
      // a 32x32 cursor image can actually show and still stay a browser-legal
      // cursor size cross-platform (Safari caps well below Chrome/Firefox).
      const size = 32, c = size / 2;
      const r = Math.max(3, Math.min(13, Math.round((Number(strokeWidth) || 3) / 2) + 2));
      const inner =
        `<line x1="${c}" y1="1" x2="${c}" y2="${c - r - 2}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
        `<line x1="${c}" y1="${c + r + 2}" x2="${c}" y2="${size - 1}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
        `<line x1="1" y1="${c}" x2="${c - r - 2}" y2="${c}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
        `<line x1="${c + r + 2}" y1="${c}" x2="${size - 1}" y2="${c}" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
        `<circle cx="${c}" cy="${c}" r="${r}" fill="${color}" stroke="#000" stroke-opacity=".45"/>`;
      return `${wbCursorUrl(inner, { size, hx: c, hy: c })}, crosshair`;
    }
    if (tool === "eraser") {
      const inner =
        `<g transform="rotate(-30 13 13)">` +
        `<rect x="4" y="9" width="16" height="10" rx="2" fill="#f4d9d9" stroke="#8a4a4a" stroke-width="1.5"/>` +
        `<rect x="4" y="9" width="7" height="10" rx="2" fill="#e7bcbc"/>` +
        `</g>`;
      return `${wbCursorUrl(inner, { hx: 6, hy: 20 })}, cell`;
    }
    if (tool === "delete") {
      const inner =
        `<path d="M6 7h14M11 7V4h4v3M9 7l1 15h6l1-15" fill="none" stroke="#d9534f" ` +
        `stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
      return `${wbCursorUrl(inner, { hx: 13, hy: 3 })}, not-allowed`;
    }
    if (tool === "link-straight" || tool === "link-curved") return "crosshair";
    if (tool === "lasso") return "crosshair";
    // Bucket, sticky and text had no case here, so all three fell through to
    // the `""` Pan returns, and `""` means "whatever the CSS says", which for
    // `.whiteboard-container` is `cursor: grab`: measured, three of the app's
    // eighteen board tools showed the open hand that means "drag the canvas"
    // while a click would have filled a shape, dropped a sticky or placed a
    // text box. Same fall-through that Select was fixed for, three tools later.
    if (tool === "bucket") {
      // A tipped bucket with a drip in the colour that is about to land, the
      // same "the cursor says what colour" idea the brush crosshair carries.
      const inner =
        `<g transform="rotate(-35 13 12)">` +
        `<path d="M6 8h12l-1.6 9.5a2 2 0 0 1-2 1.7h-4.8a2 2 0 0 1-2-1.7Z" fill="${color}" ` +
        `stroke="#000" stroke-opacity=".55" stroke-width="1.5" stroke-linejoin="round"/>` +
        `<path d="M6 8h12" fill="none" stroke="#000" stroke-opacity=".55" stroke-width="1.5"/>` +
        `</g>` +
        `<path d="M20 16c1.6 2 2.4 3.2 2.4 4.1a2.4 2.4 0 0 1-4.8 0c0-.9.8-2.1 2.4-4.1Z" ` +
        `fill="${color}" stroke="#000" stroke-opacity=".45" stroke-width="1"/>`;
      return `${wbCursorUrl(inner, { hx: 4, hy: 4 })}, crosshair`;
    }
    // `copy` and `text` rather than two more drawn images: both are system
    // cursors that already mean exactly this ("this click makes a new thing"
    // and "text goes here"), and a system cursor is the one that stays legible
    // over any board colour on any platform.
    if (tool === "sticky" || tool === "frame") return "copy";
    if (tool === "text") return "text";
    // Reported directly: "the cursor on the selection tool is wrong, it should
    // be a mouse pointer." Select had no case here, so it fell through to the
    // same `""` Pan returns: and `""` means "whatever the CSS says", which for
    // `.whiteboard-container` is `cursor: grab`. So the one tool whose whole
    // job is clicking things showed the open hand that means "drag the canvas",
    // and the two modes were indistinguishable from the pointer alone. `default`
    // (the plain arrow) is what every drawing app shows for select.
    if (tool === "select") return "default";
    return ""; // pan: the CSS grab/grabbing pair already says it
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { WB_CAP_KINDS, wbDragBox, wbEllipseDrawD, wbSnap45, wbClosedShapeD, wbCapSizeFields, wbShaftEnd, wbCapPath, wbShowCapSizes, wbCursorForTool });
})();
