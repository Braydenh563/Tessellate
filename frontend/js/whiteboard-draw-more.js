(() => {
  // whiteboard-draw-more.js: the last of draw.io's connector rows (WHITEBOARD_PLAN section 10). Two more line
  // shapes beside curved, straight and elbow, both drawn from the two ends alone (a bend dragged on either is not
  // used): Entity relation (`route: "er"`) and Isometric (`route: "iso"`). `wbLinkPathD` calls `routeStops` for them.
  // And the self-loop: a curved connector from a shape back to itself (`loop`: top, right, bottom or left, with the two
  // ends on that side) is drawn as a loop out of that side; `addLoop` makes one, `bindLoopRow` is Format's Loop side.
  // And a second label on a connector (`label2`, at `label2_t` along the line, 0.85 unless moved), set in Format and drawn
  // beside the first with the same look; `paintLabel2` and `layoutLabel2` are called from the connector label's own paint and layout.

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

  //: Where a loop's two ends sit on its side (fractions of the shape's box) and the way it leaves.
  const SIDES = {
    top: { out: { x: 0, y: -1 }, start: { x: 0.3, y: 0 }, end: { x: 0.7, y: 0 } },
    right: { out: { x: 1, y: 0 }, start: { x: 1, y: 0.3 }, end: { x: 1, y: 0.7 } },
    bottom: { out: { x: 0, y: 1 }, start: { x: 0.7, y: 1 }, end: { x: 0.3, y: 1 } },
    left: { out: { x: -1, y: 0 }, start: { x: 0, y: 0.7 }, end: { x: 0, y: 0.3 } },
  };
  const ORDER = ["top", "right", "bottom", "left"];

  const sameEnd = (parsed) => parsed && parsed.sourceId != null && parsed.sourceId === parsed.targetId && (parsed.sourceKind || "node") === (parsed.targetKind || "node");

  //: One cubic out of the side and back into it: both control points out by a reach that grows with the gap
  //: between the ends, so a wide shape gets a wide loop. Shaped for `wbCurvePathD`.
  function loopSegs(side, s, t) {
    const out = (SIDES[side] || SIDES.top).out;
    const reach = Math.max(36, Math.min(120, Math.hypot(t.x - s.x, t.y - s.y) * 1.25));
    return [{ a: { x: s.x, y: s.y }, c1: { x: s.x + out.x * reach, y: s.y + out.y * reach }, c2: { x: t.x + out.x * reach, y: t.y + out.y * reach }, b: { x: t.x, y: t.y } }];
  }

  //: The loop on the selected shape, on the first side that has none yet, joined from and to the shape itself.
  async function addLoop() {
    const source = wbCloneSource();
    if (!source) {
      toast("Select one shape or text box first.");
      return;
    }
    const used = new Set();
    for (const sk of wbState.sketches || []) {
      const p = wbIsLinkSketch(sk) ? wbSketchParsedData(sk) : null;
      if (sameEnd(p) && p.sourceId === source.id && (p.sourceKind || "node") === source.kind) used.add(p.loop || "top");
    }
    const side = ORDER.find((name) => !used.has(name)) || "top";
    const data = {
      type: "link-curved", color: window.currentStrokeColor || "#888888", width: 2, endCap: "arrow", loop: side,
      sourceId: source.id, targetId: source.id, sourceAnchor: SIDES[side].start, targetAnchor: SIDES[side].end,
    };
    if (source.kind !== "node") {
      data.sourceKind = source.kind;
      data.targetKind = source.kind;
    }
    let made = null;
    await wbRecordGesture(async () => {
      made = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }),
      });
      wbState.sketches.push(made);
    });
    wbScheduleRender();
    if (made) selectWbItem("sketch", made.id);
    wbAnnounce(`Loop added on the ${side}.`);
  }

  //: Format's Loop side: shown only when every selected connector is a loop, and writes the side with its two ends.
  function syncLoopRow(takes, entries) {
    const row = document.querySelector('[data-fmt="loop"]');
    if (!row || !takes.has("loop")) return;
    const loops = entries.filter((e) => e.kind === "sketch").map(wbFmtSketch);
    const all = loops.length > 0 && loops.every(sameEnd);
    row.hidden = !all;
    const select = document.getElementById("wb-fmt-loop");
    if (!all || !select || document.activeElement === select) return;
    wbFmtShowMixed(select, new Set(loops.map((l) => l.loop || "top")).size > 1, loops[0].loop || "top");
  }

  function bindLoopRow() {
    document.getElementById("wb-fmt-loop")?.addEventListener("change", (e) => {
      const side = ORDER.includes(e.target.value) ? e.target.value : "top";
      wbFmtApply("loop", (entry) => (sameEnd(wbFmtSketch(entry)) ? { loop: side, sourceAnchor: SIDES[side].start, targetAnchor: SIDES[side].end } : null), `Loop on the ${side}.`);
    });
  }

  onSurface("board", bindLoopRow);

  //: A connector's second label (draw.io lets an edge carry several; two cover the ends). Its words are `label2`, its
  //: place `label2_t` (0 at the start, 1 at the end), 0.85 until moved; the look (size, colour, bold, chip) is the first
  //: label's. The text carries both classes so the stylesheet and a standalone SVG export treat it as a connector label.
  const LABEL2_T = 0.85;

  function label2T(parsed) {
    const t = Number(parsed?.label2_t);
    return Number.isFinite(t) && t >= 0 && t <= 1 ? t : LABEL2_T;
  }

  function layoutLabel2(groupEl) {
    const el = groupEl?.querySelector?.(":scope > .wb-link-label2");
    if (!el) return;
    const t = Number(groupEl.dataset.label2T);
    const p = wbLinkMidpoint(groupEl.querySelector(".sketch-hitbox")?.getAttribute("d"), Number.isFinite(t) ? t : LABEL2_T);
    if (!p) return;
    el.setAttribute("x", String(p.x));
    el.setAttribute("y", String(p.y));
  }

  function paintLabel2(groupEl, sketch, parsed) {
    const words = wbLinkTakesLabel(sketch, parsed) && typeof parsed.label2 === "string" ? parsed.label2.trim() : "";
    let el = groupEl.querySelector(":scope > .wb-link-label2");
    if (!words) {
      el?.remove();
      return;
    }
    if (!el) {
      el = document.createElementNS("http://www.w3.org/2000/svg", "text");
      el.setAttribute("class", "wb-link-label wb-link-label2");
      el.setAttribute("text-anchor", "middle");
      el.setAttribute("dominant-baseline", "central");
      groupEl.appendChild(el);
    }
    const text = wbExpandPlaceholders(words, parsed.props, wbPlaceholderBuiltins("sketch", sketch, groupEl));
    if (el.textContent !== text) el.textContent = text;
    el.style.fontSize = Number(parsed.label_size) > 0 ? `${Number(parsed.label_size)}px` : "";
    el.style.fontWeight = parsed.label_bold ? "700" : "";
    el.style.fill = typeof parsed.label_color === "string" ? parsed.label_color : "";
    el.classList.toggle("wb-link-label-chip", Boolean(parsed.label_chip));
    groupEl.dataset.label2T = String(label2T(parsed));
    layoutLabel2(groupEl);
  }

  //: Format's two rows for it: the words, and the place along the line.
  function bindLabel2Rows() {
    document.getElementById("wb-fmt-label2")?.addEventListener("change", (e) => {
      const words = e.target.value.trim().slice(0, 120);
      wbFmtApply("label2", () => ({ label2: words || undefined }), words ? "Second label set." : "Second label removed.");
    });
    document.getElementById("wb-fmt-label2-t")?.addEventListener("change", (e) => {
      const pct = Math.max(5, Math.min(95, Number(e.target.value) || 85));
      wbFmtApply("label2-t", () => ({ label2_t: pct === 85 ? undefined : pct / 100 }), `Second label at ${pct}% along the line.`);
    });
  }

  onSurface("board", bindLabel2Rows);

  wbFmtState.drawMore = { routeStops, entityStops, isometricStops, loopSegs, addLoop, syncLoopRow, sameEnd, SIDES, label2T, paintLabel2, layoutLabel2 };
})();
