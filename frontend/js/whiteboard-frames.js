(() => {
  // whiteboard-frames.js: frames: create, fit, turn, title, draw (decision 14).
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: --- Frames (WHITEBOARD_PLAN decision 14) ----------------------------------
  //:
  //: A titled region of the board, the way tldraw, Excalidraw, Miro and FigJam
  //: divide one up ("Ideas", "Doing", "Done"). An object of its own kind, its
  //: title in `content`, drawn as an edge and a title with nothing in between,
  //: so the shapes under the card layer still show through it, and stacked
  //: below everything already on the board. Its inside lets the pointer
  //: through: a press inside a frame selects and draws as it would on bare
  //: board, and the frame is taken by its title or its edge handles. Moving it
  //: carries whatever lies wholly inside it (`wbFrameDragOrigin`), Ctrl held
  //: moves it alone, as Ctrl does a map topic; deleting it leaves what it held.
  //: Turning it by its grip turns what it holds too (`wbFrameTurnOrigin`).

  //: The default size: a third of a 1440 board, room for a handful of cards.
  const WB_FRAME_SIZE = { w: 480, h: 320 };

  function wbFrameTitle(frame) {
    return String(frame?.data?.content || "").trim() || "Frame";
  }

  async function wbCreateFrame(x, y, box = null) {
    //: Never wider than most of what is on screen: on a phone the default is a
    //: frame whose edges are off both sides, which reads as no frame at all.
    const container = document.getElementById("whiteboard-container");
    const k = container ? d3.zoomTransform(container).k : 1;
    const fit = container
      ? Math.min(1, (0.8 * container.clientWidth) / k / WB_FRAME_SIZE.w, (0.6 * container.clientHeight) / k / WB_FRAME_SIZE.h)
      : 1;
    const w = Math.round(WB_FRAME_SIZE.w * fit), h = Math.round(WB_FRAME_SIZE.h * fit);
    const at = box || { x: x - w / 2, y: y - h / 2, w, h };
    const count = (wbState.objects || []).filter((o) => o.kind === "frame").length;
    const created = await wbCreateObject("frame", { content: `Frame ${count + 1}` }, at.x, at.y, at.w, at.h);
    if (!created) return;
    wbSelectToolRef?.("select");
    selectWbItem("object", created.id);
  }

  //: Everything lying wholly inside a frame, as selection keys: what a drag of
  //: the frame carries. Read at the start of the drag, from where things are,
  //: so an item dragged out of a frame stops belonging to it with no bookkeeping.
  function wbFrameContents(frame, { withLocked = false } = {}) {
    //: A folded frame holds what lay inside its full height (`data.collapsed`), so a drag of the bar still carries it.
    const fx = frame.x, fy = frame.y, fr = frame.x + frame.width, fb = frame.y + ((frame.data?.collapsed && frame.data?.fold_h) || frame.height);
    const keys = [];
    for (const kind of ["node", "object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        if (kind === "object" && item.id === frame.id) continue;
        //: A locked item stays where it was put, frame or no frame.
        if (!withLocked && wbIsLocked(kind, item)) continue;
        const box = wbItemBBox(kind, item);
        if (box && box.minX >= fx && box.minY >= fy && box.maxX <= fr && box.maxY <= fb) keys.push(wbMultiKey(kind, item.id));
      }
    }
    return keys;
  }

  //: **Fit a frame to what it holds** (INBOX 821, the owner: "double tap a
  //: resize anchor to resize that edge or the whole frame to snugly fit all the
  //: content in it with a comfortable margin"). `edges` is any of "n", "e", "s",
  //: "w": the edge handle named fits that edge, a corner handle two, and the
  //: frame's menu all four. Each named edge moves to the bound of what the frame
  //: holds (`wbFrameContents`, the rule a drag of the frame uses) plus a margin
  //: of 32 board units (or the frame's own Padding). What a frame holds includes the links between two held
  //: items, by the curve they are drawn on rather than the straight line
  //: between their ends. A frame holding nothing stays where it is. One Undo
  //: step, and the move eases over 150ms (not at all under reduced motion).
  const WB_FRAME_FIT_MARGIN = 32;

  async function wbFrameFit(frame, edges = "nesw") {
    if (!frame || frame.kind !== "frame") return false;
    if (frame.data?.collapsed && frame.data?.fold_h) {
      toast("Expand the frame first.", "info");
      return false;
    }
    const boxes = [];
    const touching = new Map();
    for (const key of wbFrameContents(frame, { withLocked: true })) {
      const [kind, rawId] = key.split(":");
      const item = wbFindItem(kind, Number(rawId));
      if (!item) continue;
      const box = wbItemBBox(kind, item);
      if (box) boxes.push(box);
      if (kind === "sketch") continue;
      for (const link of wbLinkedSketchesFor(item.id, kind)) touching.set(link.id, (touching.get(link.id) || 0) + 1);
    }
    for (const [linkId, ends] of touching) {
      if (ends < 2) continue;
      const path = document.querySelector(`.sketch-group[data-id="${linkId}"] .sketch-hitbox`);
      const b = path?.getBBox?.();
      if (b && (b.width || b.height)) boxes.push({ minX: b.x, minY: b.y, maxX: b.x + b.width, maxY: b.y + b.height });
    }
    if (!boxes.length) {
      toast("This frame holds nothing to fit.");
      return false;
    }
    const minX = Math.min(...boxes.map((b) => b.minX));
    const minY = Math.min(...boxes.map((b) => b.minY));
    const maxX = Math.max(...boxes.map((b) => b.maxX));
    const maxY = Math.max(...boxes.map((b) => b.maxY));
    const right = frame.x + frame.width;
    const bottom = frame.y + frame.height;
    //: The frame's own Padding (Format panel, `data.pad`) replaces the 32 when it is set; 0 is a snug fit.
    const margin = frame.data?.pad ?? WB_FRAME_FIT_MARGIN;
    const nextLeft = edges.includes("w") ? Math.round(minX - margin) : frame.x;
    const nextTop = edges.includes("n") ? Math.round(minY - margin) : frame.y;
    const nextRight = edges.includes("e") ? Math.round(maxX + margin) : right;
    const nextBottom = edges.includes("s") ? Math.round(maxY + margin) : bottom;
    if (nextLeft === frame.x && nextTop === frame.y && nextRight === right && nextBottom === bottom) return true;
    const before = WB_KIND_INFO.object.payload(frame);
    frame.x = nextLeft;
    frame.y = nextTop;
    frame.width = nextRight - nextLeft;
    frame.height = nextBottom - nextTop;
    const el = document.querySelector(`.wb-object[data-id="${frame.id}"]`);
    const still = reducedMotionWanted();
    if (el && !still) {
      el.style.transition = "transform 150ms ease-out, width 150ms ease-out, height 150ms ease-out";
      el.style.transform = wbItemTransform(frame);
      el.style.width = `${frame.width}px`;
      el.style.height = `${frame.height}px`;
      setTimeout(() => {
        el.style.transition = "";
        wbScheduleRender();
      }, 170);
    } else {
      wbScheduleRender();
    }
    await wbSaveObject(frame);
    wbPushUndo({ action: "move", kind: "object", id: frame.id, before });
    wbUpdateSelectionBar();
    return true;
  }

  function wbFrameDragOrigin(d, alone) {
    if (alone || d.kind !== "frame") return null;
    const keys = wbFrameContents(d);
    return keys.length ? wbCaptureBulkMoveOrigin(null, keys) : null;
  }

  //: **Turning a frame turns what lies wholly inside it** (WHITEBOARD_PLAN
  //: decision 42, the owner 2026-10-19: "if I rotate a frame, should it also
  //: rotate all the elements in that frame??"). The contents are captured when
  //: the grip is taken, by the rule a title drag uses (`wbFrameContents`), so
  //: the set cannot change mid-gesture. Each one turns about the frame's centre
  //: by the frame's delta: its own centre point is carried round and its own
  //: rotation gains the same delta; a shape's path is turned about that point.
  //: Links follow their ends as they do for a move. Ctrl turns the frame alone.
  function wbTurnAbout(px, py, cx, cy, deg) {
    const t = (deg * Math.PI) / 180, c = Math.cos(t), s = Math.sin(t);
    const rx = cx - px, ry = cy - py;
    return [px + rx * c - ry * s, py + rx * s + ry * c];
  }

  function wbFrameTurnOrigin(frame, alone) {
    if (alone || frame.kind !== "frame") return null;
    const keys = wbFrameContents(frame);
    if (!keys.length) return null;
    const origin = wbCaptureBulkMoveOrigin(null, keys);
    for (const entry of origin.values()) {
      entry.before = WB_KIND_INFO[entry.kind].payload(entry.item);
      if (entry.kind === "sketch") continue;
      //: The drawn size, as `wbItemBBox` reads it: a card grows with its text.
      const el = wbBulkMoveElement(entry, WB_SELECTOR_BY_KIND[entry.kind](entry.id));
      entry.w = el?.offsetWidth || entry.item.width || 0;
      entry.h = el?.offsetHeight || entry.item.height || 0;
      entry.rot = entry.item.rotation || 0;
    }
    return origin;
  }

  function wbApplyFrameTurn(frame, origin, delta) {
    const px = frame.x + frame.width / 2, py = frame.y + frame.height / 2;
    for (const entry of origin.values()) {
      if (entry.kind === "sketch") {
        const turned = wbTransformPathD(entry.d, { rotate: delta, anchorX: px, anchorY: py });
        const el = wbBulkMoveElement(entry, `.sketch-group[data-id="${entry.id}"]`);
        for (const part of el?.querySelectorAll(".sketch-path, .sketch-hitbox") || []) part.setAttribute("d", turned);
        entry.item._liveD = delta ? turned : undefined;
        continue;
      }
      const [cx, cy] = wbTurnAbout(px, py, entry.x + entry.w / 2, entry.y + entry.h / 2, delta);
      entry.item.x = Math.round(cx - entry.w / 2);
      entry.item.y = Math.round(cy - entry.h / 2);
      entry.item.rotation = (((entry.rot + delta) % 360) + 360) % 360;
      const el = wbBulkMoveElement(entry, WB_SELECTOR_BY_KIND[entry.kind](entry.id));
      if (el) el.style.transform = wbItemTransform(entry.item);
    }
    for (const entry of origin.values()) if (entry.kind !== "sketch") wbUpdateLinkedSketches(entry.id, entry.linked);
  }

  function wbFrameTurnLive(d) {
    if (d._turnOrigin) wbApplyFrameTurn(d, d._turnOrigin, (d.rotation || 0) - d._turnFrom);
  }

  function wbFrameTurnRevert(d) {
    if (d._turnOrigin) wbApplyFrameTurn(d, d._turnOrigin, 0);
    delete d._turnOrigin;
  }

  //: Saves what the turn moved and pushes the one undo step for the frame and
  //: everything it carried.
  async function wbFrameTurnEnd(d, primary) {
    const origin = d._turnOrigin;
    delete d._turnOrigin;
    const delta = (d.rotation || 0) - d._turnFrom;
    const entries = [];
    const rows = [];
    for (const entry of origin?.values() || []) {
      if (entry.kind === "sketch") {
        const live = entry.item._liveD;
        delete entry.item._liveD;
        const parsed = wbSketchParsedData(entry.item);
        if (live && parsed) {
          entry.item.data = JSON.stringify({ ...parsed, d: live, turned: ((Number(parsed.turned) || 0) + delta) % 360 });
          rows.push({ kind: "sketch", item: entry.item });
        }
      } else rows.push({ kind: entry.kind, item: entry.item });
      entries.push({ action: "move", kind: entry.kind, id: entry.id, before: entry.before });
    }
    await wbSaveMany(rows);
    wbPushDragUndo([primary, ...entries]);
    if (entries.length) wbScheduleRender();
  }

  function wbRotateGripTitle(kind) {
    const base = "Drag to rotate: Shift snaps to 15°, double-click stands it upright";
    return kind === "frame" ? `${base}. What is inside the frame turns with it; Ctrl turns the frame alone` : base;
  }

  //: The title, renamed in place: double-click it, Enter or a click away keeps
  //: the new name, Escape puts the old one back. **A panel's hint line too**
  //: (INBOX 740, the owner: "I cant edit the text under the titles in these
  //: objects?"): `field` "hint", where an emptied line is taken away rather
  //: than refused, as a title's is.
  function wbEditFrameTitle(titleEl, frame, field = "content") {
    if (titleEl.isContentEditable) return;
    const isHint = field === "hint";
    const before = isHint ? frame.data?.hint || "" : wbFrameTitle(frame);
    //: The board's one way into an edit (DESIGN.md: `wbBeginTextEdit`).
    wbBeginTextEdit(titleEl, before);
    const range = document.createRange();
    range.selectNodeContents(titleEl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    let cancelled = false;
    const onKey = (event) => {
      event.stopPropagation();
      if (event.key === "Enter") { event.preventDefault(); titleEl.blur(); }
      if (event.key === "Escape") { event.preventDefault(); cancelled = true; titleEl.blur(); }
    };
    titleEl.addEventListener("keydown", onKey);
    titleEl.addEventListener("blur", () => {
      titleEl.removeEventListener("keydown", onKey);
      wbEndTextEdit(titleEl);
      const name = wbEditedText(titleEl).replace(/\s+/g, " ").trim().slice(0, isHint ? 120 : 80);
      if (cancelled || (!name && !isHint) || name === before) {
        titleEl.textContent = before;
        return;
      }
      wbPushUndo({ action: "move", kind: "object", id: frame.id, before: WB_KIND_INFO.object.payload(frame) });
      frame.data = { ...frame.data, [field]: name || undefined };
      if (isHint && !name) delete frame.data.hint;
      titleEl.textContent = name;
      if (isHint) titleEl.hidden = !name;
      //: C17: the text went straight into the element, so an undo matched the
      //: old paint key and repainted nothing.
      const objectEl = titleEl.closest(".wb-object");
      if (objectEl) objectEl._wbPaintKey = null;
      wbSaveObject(frame);
    }, { once: true });
  }

  function wbBuildFrame(el, d) {
    el.append("div")
      .attr("class", "wb-frame-title")
      .attr("title", "Drag to move the frame and what is in it; double-click to rename")
      .text(wbFrameTitle(d))
      .on("dblclick", function (event) {
        event.stopPropagation();
        wbEditFrameTitle(this, d);
      })
      .on("pointerdown", function (event) {
        if (this.isContentEditable) event.stopPropagation();
      });
    el.append("div")
      .attr("class", "wb-frame-hint")
      .attr("title", "Double-click to change this line")
      .on("dblclick", function (event) {
        event.stopPropagation();
        wbEditFrameTitle(this, d, "hint");
      })
      .on("pointerdown", function (event) {
        if (this.isContentEditable) event.stopPropagation();
      });
    wbPaintFrame(el.node(), d);
  }

  //: **A frame with a `tint` is a panel** (INBOX 715, the templates): a tinted
  //: ground on the theme's own mix, its title inside its top and a one-line
  //: hint under it, drawn by library-lazy.css from `data-tint`. A frame with
  //: none is the edge-and-title frame decision 14 describes.
  function wbPaintFrame(node, d) {
    const tint = d.data?.tint || "";
    if (tint) node.dataset.tint = tint;
    else delete node.dataset.tint;
    node.classList.toggle("wb-frame-panel", Boolean(tint));
    const hint = node.querySelector(".wb-frame-hint");
    if (hint) {
      hint.textContent = tint ? d.data?.hint || "" : "";
      hint.hidden = !tint || !d.data?.hint;
    }
  }

  //: **A click on a panel's body, or on a frame's edge, selects that frame**
  //: (INBOX 1327: "whiteboard panels sometimes dont select when I click on
  //: them"). A frame's own box lets the pointer through (decision 14) so shapes
  //: under it stay reachable, which left a tinted panel looking solid and
  //: answering only on its title. The press still reaches the board first, so
  //: shapes and cards win; only a click that found nothing lands here. A plain
  //: frame answers on its edge band (`slop` logical units), a panel anywhere
  //: inside; the smallest such frame wins, so a panel inside a panel selects.
  function wbSelectFrameAt(x, y, slop) {
    let best = null;
    for (const f of wbState.objects || []) {
      if (f.kind !== "frame" || wbIsLocked("object", f)) continue;
      const inside = x >= f.x && y >= f.y && x <= f.x + f.width && y <= f.y + f.height;
      const near = x >= f.x - slop && y >= f.y - slop && x <= f.x + f.width + slop && y <= f.y + f.height + slop;
      if (!near) continue;
      const onEdge = !inside || x - f.x <= slop || f.x + f.width - x <= slop || y - f.y <= slop || f.y + f.height - y <= slop;
      if (!(f.data?.tint && inside) && !onEdge) continue;
      if (!best || f.width * f.height < best.width * best.height) best = f;
    }
    if (!best) return false;
    selectWbItem("object", best.id);
    return true;
  }

  //: **The box a text or sticky drag draws** (the owner, 2026-09-24: a drag
  //: with either tool should make a box that size). From the press to the
  //: pointer, in board units, never smaller than `WB_PLACE_MIN` for its kind:
  //: a box smaller than one line of its own text is a box nobody can type into,
  //: so a short drag grows the box away from the press, in the direction the
  //: drag went, rather than refusing it.

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbFrameTitle, wbCreateFrame, wbFrameContents, wbFrameFit, wbFrameDragOrigin, wbFrameTurnOrigin, wbFrameTurnLive, wbFrameTurnRevert, wbFrameTurnEnd, wbRotateGripTitle, wbEditFrameTitle, wbBuildFrame, wbPaintFrame, wbSelectFrameAt });
})();
