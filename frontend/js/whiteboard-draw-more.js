(() => {
  // whiteboard-draw-more.js: the last of draw.io's connector rows (WHITEBOARD_PLAN section 10). Two more line
  // shapes beside curved, straight and elbow, both drawn from the two ends alone (a bend dragged on either is not
  // used): Entity relation (`route: "er"`) and Isometric (`route: "iso"`). `wbLinkPathD` calls `routeStops` for them.
  // And the self-loop: a curved connector from a shape back to itself (`loop`: top, right, bottom or left, with the two
  // ends on that side) is drawn as a loop out of that side; `addLoop` makes one, `bindLoopRow` is Format's Loop side.
  // And a second label on a connector (`label2`, at `label2_t` along the line, 0.85 unless moved), set in Format and drawn
  // beside the first with the same look; `paintLabel2` and `layoutLabel2` are called from the connector label's own paint and layout.
  // And connection points beyond the eight: a port's pixel offset (`dx`, `dy`, read where a port is placed), a port flagged
  // `perimeter` held on the outline (`snapToOutline`) and a port's name beside its dot while it is lit (`nameBeside`).
  // And the ports editor (draw.io's Edit connection points): `editPorts` shows a closed shape's points, a press on the outline
  // adds one, a press on a point takes it out, Escape or a press elsewhere ends it; `resetPorts` goes back to the standard points.
  // And a link to a page of the board (draw.io's `data:page/id,`; here a frame is the page, decision 22): `link` is `frame:<id>`,
  // `frameOf` reads it, `pageLinkItem` is the Link menu's row, and the link's mark opens it with `wbPageGo`.

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

  //: A stencil port flagged `perimeter` (draw.io's `<constraint perimeter="1">`) is held on the outline: the nearest point of
  //: the shape's drawn path to where its fractions put it, so a box resized after the port was placed keeps it on the edge.
  function snapToOutline(port, d) {
    const box = wbPathBBox(d);
    if (!box) return port;
    const near = outlineNear(d, box.minX + port.x * (box.maxX - box.minX || 1), box.minY + port.y * (box.maxY - box.minY || 1));
    return near ? { ...port, x: near.x, y: near.y } : port;
  }

  //: **Edit connection points** (draw.io's `editConnectionPoints`): the points of the one selected closed shape are shown,
  //: a press on its outline adds a point there, a press on a point takes it out, and the list is saved as the shape's own
  //: `ports` (seeded from the points it has, so the standard ones stay until they are taken out). Taking out the last one
  //: gives the standard points back. Escape, or a press anywhere else, ends it.
  const editing = { id: null };
  const GRAB_PX = 8;

  function zoomK() {
    return d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1;
  }

  //: The nearest point of a drawn outline to a board point, as fractions of the shape's box, with its distance.
  function outlineNear(d, x, y) {
    const box = wbPathBBox(d);
    if (!box || !wbLinkMidpoint(d, 0) || !wbLinkMeasurePath) return null;
    let length = 0;
    try {
      length = wbLinkMeasurePath.getTotalLength();
    } catch {
      return null;
    }
    if (!length) return null;
    let best = null, bestDist = Infinity, bestAt = 0;
    const at = (n) => wbLinkMeasurePath.getPointAtLength(n);
    for (let i = 0; i <= 240; i++) {
      const q = at((length * i) / 240);
      const dist = Math.hypot(q.x - x, q.y - y);
      if (dist < bestDist) { bestDist = dist; best = q; bestAt = i; }
    }
    //: Then a narrowing search between the two samples either side of the best, so a long outline is not off by half a step.
    let lo = (length * Math.max(0, bestAt - 1)) / 240, hi = (length * Math.min(240, bestAt + 1)) / 240;
    for (let i = 0; i < 14; i++) {
      const a = lo + (hi - lo) / 3, b = hi - (hi - lo) / 3;
      const qa = at(a), qb = at(b);
      if (Math.hypot(qa.x - x, qa.y - y) < Math.hypot(qb.x - x, qb.y - y)) hi = b; else lo = a;
    }
    const fine = at((lo + hi) / 2);
    if (Math.hypot(fine.x - x, fine.y - y) <= bestDist) { best = fine; bestDist = Math.hypot(fine.x - x, fine.y - y); }
    const w = box.maxX - box.minX || 1, h = box.maxY - box.minY || 1;
    const round = (n) => Math.round(n * 1e4) / 1e4;
    return best ? { x: round((best.x - box.minX) / w), y: round((best.y - box.minY) / h), dist: bestDist } : null;
  }

  function stopEditing(say) {
    if (editing.id == null) return;
    editing.id = null;
    wbClearAnchorHints();
    if (say) wbAnnounce("Connection points done.");
  }

  function editPorts() {
    if (editing.id != null) {
      stopEditing(true);
      return;
    }
    const target = wbSwapTarget();
    if (!target) return;
    editing.id = target.item.id;
    wbShowAnchorHints("sketch", target.item, null);
    wbAnnounce("Editing connection points: press the outline to add one, press a point to take it out, Escape to finish.");
    toast("Press the outline to add a point, a point to take it out. Escape finishes.", "info");
  }

  async function savePorts(item, ports, said) {
    await wbRecordGesture(async () => {
      await wbSaveSketchProps(item, { ports: ports.length ? ports : undefined });
    });
    wbScheduleRender();
    wbShowAnchorHints("sketch", item, null);
    wbAnnounce(said);
  }

  async function resetPorts() {
    const target = wbSwapTarget();
    if (!target) return;
    if (!Array.isArray(target.parsed.ports) || !target.parsed.ports.length) {
      toast("This shape has its standard connection points.", "info");
      return;
    }
    await savePorts(target.item, [], "Connection points back to the standard ones.");
  }

  //: **Format's connection-point rows** (L-whiteboard-13; draw.io's `editConnectionPoints` and its `points` constraints): for
  //: the one selected closed shape, a list of its points, Add (the outline editor above), Remove, "On outline" (`perimeter`)
  //: and a pixel nudge (`dx`, `dy`) of the chosen point. Each edit is one `savePorts`, so one Undo step. A shape on its
  //: standard points shows them; the first edit makes them its own, as the outline editor does.
  const MAX_OFFSET = 2000;
  const portRow = { i: 0 };

  //: The points as stored (not slid to the outline), or the standard ones, as copies to change.
  function rawPorts(target) {
    const own = Array.isArray(target.parsed.ports) && target.parsed.ports.length ? target.parsed.ports : wbPortFractions("sketch", target.item);
    return own.map((q) => ({ ...q }));
  }

  function portWords(q, i) {
    const place = `${Math.round(q.x * 100)}%, ${Math.round(q.y * 100)}%`;
    return `${i + 1}: ${q.name ? `${q.name}, ` : ""}${place}${q.perimeter ? ", on outline" : ""}`;
  }

  function fillPortFields(q) {
    if (!q) return;
    document.getElementById("wb-fmt-port-perim").checked = Boolean(q.perimeter);
    for (const key of ["dx", "dy"]) {
      const el = document.getElementById(`wb-fmt-port-${key}`);
      if (document.activeElement !== el) el.value = Number(q[key]) ? String(q[key]) : "";
    }
  }

  function syncPortsRow(takes, entries) {
    if (!takes.has("ports")) return;
    const target = entries.length === 1 && entries[0].kind === "sketch" ? wbSwapTarget() : null;
    for (const row of document.querySelectorAll('[data-fmt="ports"]')) row.hidden = !target;
    const select = document.getElementById("wb-fmt-port");
    if (!target || !select || document.activeElement === select) return;
    const ports = rawPorts(target);
    portRow.i = Math.max(0, Math.min(ports.length - 1, portRow.i));
    select.replaceChildren(...ports.map((q, i) => {
      const option = document.createElement("option");
      option.value = String(i);
      option.textContent = portWords(q, i);
      return option;
    }));
    select.value = String(portRow.i);
    fillPortFields(ports[portRow.i]);
  }

  //: One edit of the chosen point: `change(port, ports)` may change it or the list (false: nothing changed); the list is
  //: saved in one step. Edits queue behind each other: a nudge's change fires on blur as the next control is pressed, and
  //: two saves in flight shared one Undo step and could land out of order, losing the second (sweep wbports-offsets.js).
  let portQueue = Promise.resolve();
  function editChosenPort(change, said) {
    portQueue = portQueue.then(async () => {
      const target = wbSwapTarget();
      if (!target) return;
      const ports = rawPorts(target);
      const q = ports[Math.max(0, Math.min(ports.length - 1, portRow.i))];
      if (!q || change(q, ports) === false) return;
      await savePorts(target.item, ports, said);
    }).catch((error) => console.error(error));
    return portQueue;
  }

  function bindPortsRows() {
    const field = (id) => document.getElementById(id);
    field("wb-fmt-port")?.addEventListener("change", (e) => {
      portRow.i = Math.max(0, Number(e.target.value) || 0);
      const target = wbSwapTarget();
      if (target) fillPortFields(rawPorts(target)[portRow.i]);
    });
    field("wb-fmt-port-add")?.addEventListener("click", () => editPorts());
    field("wb-fmt-port-del")?.addEventListener("click", () => editChosenPort((q, ports) => {
      ports.splice(portRow.i, 1);
      portRow.i = Math.max(0, portRow.i - 1);
    }, "Connection point taken out."));
    field("wb-fmt-port-perim")?.addEventListener("change", (e) => {
      const on = e.target.checked;
      return editChosenPort((q) => {
        if (on) q.perimeter = true; else delete q.perimeter;
      }, on ? "Connection point held on the outline." : "Connection point free of the outline.");
    });
    for (const key of ["dx", "dy"]) {
      field(`wb-fmt-port-${key}`)?.addEventListener("change", (e) => {
        const n = Math.round(Math.max(-MAX_OFFSET, Math.min(MAX_OFFSET, Number(e.target.value) || 0)) * 100) / 100;
        return editChosenPort((q) => {
          if ((Number(q[key]) || 0) === n) return false;
          if (n) q[key] = n; else delete q[key];
        }, `Connection point moved ${n} pixels ${key === "dx" ? "across" : "down"}.`);
      });
    }
  }

  onSurface("board", bindPortsRows);

  function bindPortEditor() {
    const container = document.getElementById("whiteboard-container");
    if (!container) return;
    container.addEventListener("pointerdown", (e) => {
      if (editing.id == null || e.button !== 0) return;
      const target = wbSwapTarget();
      if (!target || target.item.id !== editing.id) {
        stopEditing(false);
        return;
      }
      const [x, y] = wbClientToBoard(e.clientX, e.clientY);
      const grab = GRAB_PX / zoomK();
      const ports = rawPorts(target);
      const hit = wbAnchorPositions("sketch", target.item).findIndex((q) => Math.hypot(q.x - x, q.y - y) <= grab);
      const near = hit < 0 ? outlineNear(target.parsed.d, x, y) : null;
      if (hit < 0 && !(near && near.dist <= grab * 1.5)) {
        stopEditing(true);
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      if (hit >= 0) {
        ports.splice(hit, 1);
        savePorts(target.item, ports, ports.length ? "Connection point taken out." : "No points left of its own: the standard connection points are back.");
      } else {
        ports.push({ x: near.x, y: near.y });
        portRow.i = ports.length - 1;
        savePorts(target.item, ports, `Connection point added; the shape has ${ports.length}.`);
      }
    }, true);
    container.addEventListener("pointermove", (e) => {
      if (editing.id == null) return;
      const target = wbSwapTarget();
      if (!target || target.item.id !== editing.id) return;
      const [x, y] = wbClientToBoard(e.clientX, e.clientY);
      wbShowAnchorHints("sketch", target.item, wbNearestAnchor("sketch", target.item, x, y, GRAB_PX / zoomK()));
    }, { passive: true });
    document.addEventListener("keydown", (e) => {
      if (editing.id == null || e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      stopEditing(true);
    }, true);
  }

  onSurface("board", bindPortEditor);

  //: The lit port's name, drawn beside its dot at a readable size whatever the zoom.
  function nameBeside(layer, name, x, y) {
    const k = d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1;
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("class", "wb-port-name");
    text.setAttribute("x", String(x + 9 / k));
    text.setAttribute("y", String(y - 9 / k));
    text.setAttribute("font-size", String(12 / k));
    text.setAttribute("fill", "var(--ink)");
    text.setAttribute("stroke", "var(--card)");
    text.setAttribute("stroke-width", String(3 / k));
    text.setAttribute("paint-order", "stroke");
    text.textContent = name;
    layer.appendChild(text);
  }

  //: **A link to a frame** (decision 22: frames are the pages): a shape's `link` may be `frame:<id>`, the frame's own id.
  //: It counts only while that frame is on this board, so a link left behind by a deleted frame, or carried onto another
  //: board, shows no mark rather than one that opens nothing.
  function frameOf(link) {
    const id = /^frame:(\d+)$/.exec(link || "")?.[1];
    return id ? (wbState.objects || []).find((o) => o.kind === "frame" && o.id === Number(id)) || null : null;
  }

  //: The mark's words: the frame's title.
  function linkWords(link) {
    const frame = frameOf(link);
    return frame ? wbFrameTitle(frame) : "";
  }

  //: The Link menu's row for pages: one row per frame, in presentation order. None when the board has no frame.
  function pageLinkItem(set, x, y) {
    const frames = wbFramesInOrder();
    if (!frames.length) return null;
    return makeMenuItem("ph:presentation A page of this board…", "Link this to a frame: the mark scrolls and zooms to it", () => {
      setTimeout(() => openMenuAtPoint(frames.map((f) => makeMenuItem(`ph:frame-corners ${wbFrameTitle(f)}`, "", () => set(`frame:${f.id}`))), "Pages", x, y), 0);
    });
  }

  wbFmtState.drawMore = { routeStops, entityStops, isometricStops, loopSegs, addLoop, syncLoopRow, sameEnd, SIDES, label2T, paintLabel2, layoutLabel2, snapToOutline, nameBeside, editPorts, syncPortsRow, resetPorts, outlineNear, frameOf, linkWords, pageLinkItem };
})();
