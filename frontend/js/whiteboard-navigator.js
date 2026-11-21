(() => {
  // whiteboard-navigator.js: the live minimap: its paint, cost gate and drag.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  // --- The navigator (a live minimap) ----------------------------------------
  //
  // Deliberately *not* a fifth always-on floating panel. The canvas already
  // carries four, and this file's own CSS comments record two separate reports
  // of them colliding with each other and running off narrow screens. It opens
  // from a button in the zoom cluster, where fit and full screen already live,
  // so it sits with the other "where am I" controls: and closes again.

  const WB_NAV_W = 208;
  const WB_NAV_H = 132;
  const WB_NAV_PAD = 6;

  function wbNavigatorOpen() {
    const panel = document.getElementById("wb-navigator");
    return !!panel && !panel.classList.contains("hidden");
  }

  //: **What the overview costs, and when** (INBOX 431, the owner: "the fit drag
  //: mini fit map on the whiteboard and mindmap is reallllly glitchy and
  //: laggy"). Measured on a 150-card board at a 4x CPU throttle
  //: (`scratchpad/ui-sweeps/minimapdrag.js`) before this: a one-second drag of
  //: the viewport rectangle took 9.7 seconds to deliver, with 9,222 forced
  //: layouts and a p95 frame of 183ms. Two of the causes were in the drawing:
  //:
  //:   * The full redraw read each card's size (`offsetWidth`, inside
  //:     `wbItemBBox`) *between* appends to this SVG, and an append dirties
  //:     layout, so every item forced a layout of the page: 151 layouts for
  //:     one redraw of 150 items. `wbNavigatorSnapshot` now takes every
  //:     measurement in one pass, and the redraw writes once, a fragment.
  //:   * That redraw ran on every pan and zoom frame. The items cannot move
  //:     during a pan; only the rectangle can, and the mapping, when the view
  //:     leaves the content and the map rescales to keep it in. So a pan frame
  //:     runs `wbNavigatorUpdateViewport`: the rectangle's four attributes,
  //:     and one `transform` on the items group when the mapping changed. The
  //:     items are redrawn after a board render (`wbNavState.stale`), which is
  //:     what moves them.
  const wbNavState = {
    //: What the items were last drawn from: `bounds` (board space) and
    //: `drawn`, the mapping they were drawn with.
    content: null,
    //: A render since the last redraw: the items may have moved.
    stale: true,
    //: The live drag on the overview, or null (see `wbNavigatorDragStart`).
    drag: null,
    //: The selection the items were last classed for.
    selectionKey: "",
  };

  //: Every item's box and the content bounds, in one pass of reads. Nothing in
  //: here writes, so the layout the first read flushes serves all the rest.
  function wbNavigatorSnapshot() {
    const items = [];
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
      for (const item of wbState[list] || []) {
        const box = wbItemBBox(kind, item);
        if (!box) continue;
        items.push({ kind, id: item.id, box });
        if (box.minX < minX) minX = box.minX;
        if (box.minY < minY) minY = box.minY;
        if (box.maxX > maxX) maxX = box.maxX;
        if (box.maxY > maxY) maxY = box.maxY;
      }
    }
    const bounds = Number.isFinite(minX)
      ? { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY }
      : null;
    return { bounds, items };
  }

  /**
   * Board coordinates -> navigator coordinates, from the content bounds, a zoom
   * transform and the canvas size; null on an empty board.
   */
  function wbNavigatorProjectionFor(bounds, t, width, height) {
    if (!bounds) return null;
    // The navigator shows the content *and* wherever the viewport currently is,
    // so a viewport panned off into empty space still draws a rectangle you can
    // drag back: union the two before scaling, or the rectangle silently
    // clamps to the edge and stops telling the truth about where you are.
    const view = {
      minX: (0 - t.x) / t.k,
      minY: (0 - t.y) / t.k,
      maxX: (width - t.x) / t.k,
      maxY: (height - t.y) / t.k,
    };
    const minX = Math.min(bounds.minX, view.minX);
    const minY = Math.min(bounds.minY, view.minY);
    const maxX = Math.max(bounds.maxX, view.maxX);
    const maxY = Math.max(bounds.maxY, view.maxY);
    const w = Math.max(maxX - minX, 1);
    const h = Math.max(maxY - minY, 1);
    const k = Math.min((WB_NAV_W - WB_NAV_PAD * 2) / w, (WB_NAV_H - WB_NAV_PAD * 2) / h);
    const offX = WB_NAV_PAD + ((WB_NAV_W - WB_NAV_PAD * 2) - w * k) / 2;
    const offY = WB_NAV_PAD + ((WB_NAV_H - WB_NAV_PAD * 2) - h * k) / 2;
    return wbNavigatorMapping({ k, minX, minY, offX, offY }, view);
  }

  //: A projection from its five numbers and the viewport it shows.
  function wbNavigatorMapping({ k, minX, minY, offX, offY }, view) {
    return {
      k,
      minX,
      minY,
      offX,
      offY,
      view,
      toNav: (x, y) => [offX + (x - minX) * k, offY + (y - minY) * k],
      toBoard: (nx, ny) => [minX + (nx - offX) / k, minY + (ny - offY) / k],
    };
  }

  //: The drag's projection: the mapping frozen at the press, the viewport live.
  function wbNavigatorFrozenProjection(drag, t) {
    return wbNavigatorMapping(drag.mapping, {
      minX: (0 - t.x) / t.k,
      minY: (0 - t.y) / t.k,
      maxX: (drag.width - t.x) / t.k,
      maxY: (drag.height - t.y) / t.k,
    });
  }

  function wbNavigatorSelectionKey() {
    const one = wbSelectedItem ? wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id) : "";
    return wbMultiSelection.size ? `${one}|${[...wbMultiSelection].join(",")}` : one;
  }

  function wbNavigatorIsSelected(kind, id) {
    return wbMultiSelection.has(wbMultiKey(kind, id))
      || (!!wbSelectedItem && wbSelectedItem.kind === kind && String(wbSelectedItem.id) === String(id));
  }

  function wbRenderNavigator() {
    const svg = document.getElementById("wb-navigator-map");
    const empty = document.getElementById("wb-navigator-empty");
    if (!svg || !wbNavigatorOpen()) return;
    const container = document.getElementById("whiteboard-container");
    if (!container) return;
    // Reads, all of them, before the first write.
    const snap = wbNavigatorSnapshot();
    const t = d3.zoomTransform(container);
    const proj = wbNavigatorProjectionFor(snap.bounds, t, container.clientWidth, container.clientHeight);
    const NS = "http://www.w3.org/2000/svg";
    const frag = document.createDocumentFragment();
    // Attributes, never a `style` string: this app's CSP rejects inline
    // styles outright, and thirty-five of them once shipped as silently dead
    // markup (CLAUDE.md, "a policy silently refusing the work").
    const make = (tag, attrs) => {
      const el = document.createElementNS(NS, tag);
      for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
      return el;
    };
    if (proj) {
      const group = make("g", { class: "wb-nav-items" });
      for (const { kind, id, box } of snap.items) {
        const [x, y] = proj.toNav(box.minX, box.minY);
        const w = Math.max((box.maxX - box.minX) * proj.k, 2);
        const h = Math.max((box.maxY - box.minY) * proj.k, 2);
        const rect = make("rect", {
          x, y, width: w, height: h, rx: 1,
          class: `wb-nav-item wb-nav-item-${kind}${wbNavigatorIsSelected(kind, id) ? " is-selected" : ""}`,
          "data-key": wbMultiKey(kind, id),
        });
        group.append(rect);
      }
      frag.append(group, make("rect", { class: "wb-nav-viewport" }));
    }
    svg.replaceChildren(frag);
    if (empty) empty.classList.toggle("hidden", !!snap.bounds);
    svg.classList.toggle("hidden", !snap.bounds);
    wbNavState.content = proj
      ? { bounds: snap.bounds, drawn: { k: proj.k, minX: proj.minX, minY: proj.minY, offX: proj.offX, offY: proj.offY } }
      : null;
    wbNavState.stale = false;
    wbNavState.selectionKey = wbNavigatorSelectionKey();
    if (proj) wbNavigatorPlaceViewport(svg, proj);
  }

  //: The rectangle for `proj`, and the items group's mapping from the one they
  //: were drawn with to `proj`. Writes only.
  function wbNavigatorPlaceViewport(svg, proj) {
    const rect = svg.lastElementChild;
    if (!rect || !rect.classList.contains("wb-nav-viewport")) return;
    const [vx, vy] = proj.toNav(proj.view.minX, proj.view.minY);
    rect.setAttribute("x", vx);
    rect.setAttribute("y", vy);
    rect.setAttribute("width", Math.max((proj.view.maxX - proj.view.minX) * proj.k, 4));
    rect.setAttribute("height", Math.max((proj.view.maxY - proj.view.minY) * proj.k, 4));
    const drawn = wbNavState.content?.drawn;
    const group = svg.firstElementChild;
    if (!drawn || !group || !group.classList.contains("wb-nav-items")) return;
    // nav = off + (board - min) * k, so going from the drawn mapping to this
    // one is a scale by k / k0 and a translate: identity when nothing rescaled.
    const s = proj.k / drawn.k;
    const tx = proj.offX - proj.minX * proj.k - s * (drawn.offX - drawn.minX * drawn.k);
    const ty = proj.offY - proj.minY * proj.k - s * (drawn.offY - drawn.minY * drawn.k);
    const same = Math.abs(s - 1) < 1e-6 && Math.abs(tx) < 0.01 && Math.abs(ty) < 0.01;
    const value = same ? "" : `translate(${tx} ${ty}) scale(${s})`;
    if ((group.getAttribute("transform") || "") !== value) {
      if (value) group.setAttribute("transform", value);
      else group.removeAttribute("transform");
    }
  }

  /**
   * The per-frame update from a pan or a zoom: the rectangle and the mapping,
   * never the items, and no measurement of the board. The bounds are the ones
   * the items were drawn from; the canvas size is `size`, which the zoom frame
   * read before it wrote anything (a read here only without it).
   */
  function wbNavigatorUpdateViewport(t, size) {
    const svg = document.getElementById("wb-navigator-map");
    if (!svg || !wbNavigatorOpen()) return;
    const drag = wbNavState.drag;
    // A render since the items were drawn: redraw them. Not mid-drag, where
    // the pointer is aiming with the mapping the items were drawn in; the
    // drag's end redraws.
    if (!drag && (wbNavState.stale || !wbNavState.content)) {
      wbRenderNavigator();
      return;
    }
    if (!wbNavState.content) return;
    const container = document.getElementById("whiteboard-container");
    if (!container) return;
    const transform = t || d3.zoomTransform(container);
    const proj = drag
      ? wbNavigatorFrozenProjection(drag, transform)
      : wbNavigatorProjectionFor(
        wbNavState.content.bounds,
        transform,
        size ? size.width : container.clientWidth,
        size ? size.height : container.clientHeight,
      );
    if (!proj) return;
    const key = wbNavigatorSelectionKey();
    if (key !== wbNavState.selectionKey) {
      wbNavState.selectionKey = key;
      for (const el of svg.firstElementChild?.children || []) {
        const itemKey = el.getAttribute("data-key") || "";
        const cut = itemKey.indexOf(":");
        const on = cut > 0 && wbNavigatorIsSelected(itemKey.slice(0, cut), itemKey.slice(cut + 1));
        if (el.classList.contains("is-selected") !== on) el.classList.toggle("is-selected", on);
      }
    }
    wbNavigatorPlaceViewport(svg, proj);
  }

  //: **Dragging the overview** (INBOX 431: "glitchy and laggy"). What a drag
  //: did before, on every pointer event: measured the content bounds from the
  //: DOM (a size read per card), measured the overview's own box and the
  //: canvas, built a projection that could rescale under the pointer whenever
  //: the view crossed the content's edge, and set the transform, whose frame
  //: then redrew the whole overview. And a press on the rectangle jumped its
  //: centre to the pointer, so picking it up by a corner moved the board
  //: before the hand did.
  //:
  //: Now the press measures, once: the overview's box, the canvas size and the
  //: mapping (frozen, so the map under the pointer holds still until the
  //: release, which redraws it). A press on the rectangle keeps the grab point;
  //: a press elsewhere still jumps the view there, which is what a click on an
  //: overview means. Moves are coalesced into one animation frame, which sets
  //: the transform and runs the zoom frame's work at once (`wbFlushZoomFrame`),
  //: so the board, the grid, the cull and the rectangle all land in that frame.
  //: Pointer capture keeps the drag when the pointer leaves the small box; the
  //: drag ends on up, cancel and a lost capture alike.
  function wbNavigatorDragStart(event) {
    const svg = event.currentTarget;
    const container = document.getElementById("whiteboard-container");
    if (!svg || !container) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    // A second pointer pressing mid-drag (a second finger) takes the drag over.
    if (wbNavState.drag) wbNavigatorDragEnd();
    if (wbNavState.stale || !wbNavState.content) wbRenderNavigator();
    if (!wbNavState.content) return;
    const t = d3.zoomTransform(container);
    const width = container.clientWidth;
    const height = container.clientHeight;
    const proj = wbNavigatorProjectionFor(wbNavState.content.bounds, t, width, height);
    if (!proj) return;
    // The SVG is laid out at exactly WB_NAV_W x WB_NAV_H, but a browser zoom or
    // a future responsive tweak could scale it: divide through by the real
    // rendered size rather than trusting the constants.
    const box = svg.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const nx = ((event.clientX - box.left) / box.width) * WB_NAV_W;
    const ny = ((event.clientY - box.top) / box.height) * WB_NAV_H;
    const [x0, y0] = proj.toNav(proj.view.minX, proj.view.minY);
    const [x1, y1] = proj.toNav(proj.view.maxX, proj.view.maxY);
    const onRect = nx >= x0 && nx <= x1 && ny >= y0 && ny <= y1;
    const grab = onRect ? { x: nx - (x0 + x1) / 2, y: ny - (y0 + y1) / 2 } : { x: 0, y: 0 };
    wbNavState.drag = {
      pointerId: event.pointerId,
      svg,
      box,
      width,
      height,
      k: t.k,
      mapping: { k: proj.k, minX: proj.minX, minY: proj.minY, offX: proj.offX, offY: proj.offY },
      grab,
      pending: { x: event.clientX, y: event.clientY },
      frame: 0,
    };
    wbBoardState.capture(svg, event.pointerId);
    svg.classList.add("is-dragging");
    event.preventDefault();
    wbNavigatorDragFrame();
  }

  function wbNavigatorDragMove(event) {
    const drag = wbNavState.drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.pending = { x: event.clientX, y: event.clientY };
    if (!drag.frame) drag.frame = requestAnimationFrame(wbNavigatorDragFrame);
  }

  function wbNavigatorDragFrame() {
    const drag = wbNavState.drag;
    if (!drag) return;
    drag.frame = 0;
    const p = drag.pending;
    drag.pending = null;
    const container = document.getElementById("whiteboard-container");
    if (!p || !container) return;
    const nx = ((p.x - drag.box.left) / drag.box.width) * WB_NAV_W - drag.grab.x;
    const ny = ((p.y - drag.box.top) / drag.box.height) * WB_NAV_H - drag.grab.y;
    const m = drag.mapping;
    const bx = m.minX + (nx - m.offX) / m.k;
    const by = m.minY + (ny - m.offY) / m.k;
    // The zoom is kept: the overview moves the view, it never rescales it.
    const target = d3.zoomIdentity
      .translate(drag.width / 2 - drag.k * bx, drag.height / 2 - drag.k * by)
      .scale(drag.k);
    d3.select(container).call(wbZoom.transform, target);
    wbFlushZoomFrame();
  }

  function wbNavigatorDragEnd(event) {
    const drag = wbNavState.drag;
    if (!drag || (event && event.pointerId !== undefined && event.pointerId !== drag.pointerId)) return;
    // The last move lands before the drag ends, rather than being dropped.
    if (drag.frame) {
      cancelAnimationFrame(drag.frame);
      wbNavigatorDragFrame();
    }
    wbNavState.drag = null;
    drag.svg.classList.remove("is-dragging");
    try {
      if (drag.svg.hasPointerCapture(drag.pointerId)) drag.svg.releasePointerCapture(drag.pointerId);
    } catch {
      /* the pointer was already gone */
    }
    // The mapping was frozen for the gesture; let it follow the view again.
    wbRenderNavigator();
  }

  function wbToggleNavigator(force) {
    const panel = document.getElementById("wb-navigator");
    if (!panel) return;
    const open = force === undefined ? panel.classList.contains("hidden") : force;
    // Shift+N mid-drag: the drag ends with the panel, not with a later pointer.
    if (!open && wbNavState.drag) wbNavigatorDragEnd();
    panel.classList.toggle("hidden", !open);
    try {
      prefs.set("wb-navigator-open", open ? "1" : "0");
    } catch {
      /* private mode: the navigator just won't be remembered */
    }
    if (open) wbRenderNavigator();
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbNavState, wbRenderNavigator, wbNavigatorUpdateViewport, wbNavigatorDragStart, wbNavigatorDragMove, wbNavigatorDragEnd, wbToggleNavigator });
})();
