(() => {
  // whiteboard-pointer.js: drawing, erasing, marquee and lasso select, edge pan and port hover on the board; a section of initWhiteboard (L634).
  // Wrapped: initWhiteboard calls it once, passing the names it shares; nothing here runs at load.
  let selectWbTool, boardEl;
  let svgCanvas;
  //: Every sample the browser coalesced into this event is hit-tested, so a fast finger or pen stroke between two
  //: events erases what it crossed (audit B21); `pointerenter` alone never fires reliably on touch or pen. One swipe,
  //: one Undo step (L-whiteboard-35): each delete pushes its own entry as it lands, and the swipe's end folds them
  //: into one batch.
  let wbEraseHad = null;
  let wbMarqueeStart = null;
  //: One-shot, the placing twin of `wbMarqueeJustSelected`: a drawn text box
  //: or sticky spends the canvas click its own release makes.
  let wbPlaceJustDrawn = false;
  let wbMarqueeEl = null;
  let wbMarqueeJustSelected = false;
  //: The latest pointer position (board units) and the frame that will draw
  //: it, so a burst of moves inside one frame is one write (`wbDrawMarquee`).
  let wbMarqueeAt = null;
  let wbMarqueeFrame = 0;
  let wbMarqueeInk = "";
  let wbEdgePan;
  let openMapCanvasMenu;
  let openBoardCanvasMenu;
  let wbCanvasMenuWanted;
  let openCanvasMenu;
  //: **Right-drag pans, a plain right-click opens the menu** (C03, the owner:
  //: "hard to move around the whiteboard with a mouse, copy draw.io and have
  //: right click hold down drag panning"). The browser sends `contextmenu`
  //: on the press (Linux) or the release (Windows), so "suppress it only
  //: when the drag moved" cannot be written (wbrightpan.js header). Instead
  //: the native event on bare canvas is always swallowed while a right press
  //: is in flight or just ended, and the app's own menu opens on the
  //: release when the pointer stayed inside the slop. A `contextmenu` with
  //: no press behind it (the menu key) still opens the menu.
  const WB_RIGHT_SLOP = 4;
  let wbRightPress = null;
  let wbRightOwns;
  let port;
  let zoomK;
  let portTarget;
  let portEnd;
  let portHints;
  let wbLassoPoints = null;
  let wbLassoEl = null;
  let wbLassoShift = false;
  let wbPictureCap;
  let imageFileInput;
  let mapPictureInput;

  function getLogicalMouse(e) {
    return wbClientToBoard(e.clientX, e.clientY);
  }

  function wbEraseSettle() {
    if (!wbEraseHad) return;
    const had = wbEraseHad;
    wbEraseHad = null;
    const mine = wbStacks.undo.filter((entry) => !had.has(entry) && entry.action === "delete");
    if (mine.length < 2) return;
    for (const entry of mine) wbStacks.undo.splice(wbStacks.undo.indexOf(entry), 1);
    wbPushUndo({ action: "batch", entries: mine });
  }

  function wbEraseAt(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    const sketchEl = el?.closest(".sketch-group");
    if (sketchEl) {
      const item = wbState.sketches.find((s) => s.id === Number(sketchEl.dataset.id));
      if (item) wbDeleteSketch(item);
      return;
    }
    const cardEl = el?.closest(".node-card");
    if (cardEl) {
      const item = wbState.nodes.find((n) => n.id === Number(cardEl.dataset.id));
      if (item) wbDeleteNode(item);
      return;
    }
    const objEl = el?.closest(".wb-object");
    if (objEl) {
      const item = (wbState.objects || []).find((o) => o.id === Number(objEl.dataset.id));
      if (item) wbDeleteObject(item);
    }
  }

  // Rectangle marquee select: reported directly ("area select... missing").
  // Only engages when the pointerdown target is genuinely empty canvas: a
  // card/sketch/object's own drag already claims the gesture otherwise (the
  // node/object drags' `.filter()`, the sketch drag's own tool check), so
  // checking the target here is enough without a second stopPropagation
  // dance.
  //
  // **The handle layer has to be in this list, and stopPropagation cannot
  // stand in for it.** Reported: "when I adjust things like links, the area
  // select happens too", dragging a link's endpoint drew a selection
  // marquee across the board at the same time. The endpoint handles are not
  // inside `.sketch-group`; they live in their own `.wb-sketch-handle-group`
  // over in `#wb-overlay-zoom-group`, precisely so a card can sit above the
  // base layer without burying them. So they passed this test as empty
  // canvas.
  //
  // Their drag does call `stopPropagation` on d3-drag's "start", and that is
  // why this looked correct. It fires on the wrong event: d3-drag listens for
  // `mousedown`, this listens for `pointerdown`, and a pointerdown is
  // dispatched *before* the compatibility mousedown it generates. By the time
  // the handle stops propagation the marquee has already begun. Two event
  // families cannot cancel each other, so the target check is the only place
  // this can be fixed.
  function wbIsEmptyCanvasTarget(target) {
    // `.sketch-group:not(.wb-link-sketch)`: see the class's own note in the sketch render. A drawn shape claims the
    // gesture (it can be moved by its body); a link cannot be, and its 20px hit band was swallowing the marquee
    // wherever a connector crossed the canvas.
    return wbIsBareCanvas(target);
  }

  function rectsIntersect(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }

  //: End the marquee gesture and take its rectangle off the canvas. Every exit from the drag goes through here, the
  //: completed one, the cancelled one, and the sweep `wbClearSelectionOverlays` runs, so there is exactly one place
  //: that can forget to remove the element.
  function wbEndMarqueeDrag() {
    if (wbMarqueeStart?.place) wbClearAlignmentGuides();
    //: A selection drag cut off (cancelled, capture lost) goes back where it
    //: was; one that ended normally cleared `wbMarqueeStart` first.
    if (wbMarqueeStart?.move && wbMarqueeStart.origin) {
      wbApplyBulkMove(wbMarqueeStart.origin, 0, 0);
      for (const entry of wbMarqueeStart.origin.values()) delete entry.item._liveD;
    }
    wbMarqueeEl?.remove();
    wbMarqueeEl = null;
    wbMarqueeStart = null;
    if (wbMarqueeFrame) cancelAnimationFrame(wbMarqueeFrame);
    wbMarqueeFrame = 0;
    wbMarqueeAt = null;
  }

  //: The rectangle itself, made on the first movement past the threshold the
  //: completed gesture is judged by anyway. Split out so both the press and
  //: the move can read it.
  //: **Drawn on the compositor, once a frame** (INBOX 410: "drag selection on
  //: the whiteboard and mindmap is laggy as well"). The rectangle was an SVG
  //: `<rect>` in the overlay layer whose four attributes were rewritten on
  //: every pointermove. Each rewrite changed a paint chunk's bounds, and a
  //: changed chunk makes Chrome re-layerize the whole page, whose cost grows
  //: with everything on the board: traced over one 80-move drag
  //: (`scratchpad/ui-sweeps/marqueeperf.js`), Layerize took 1275ms on a board
  //: of 200 text boxes and 616ms on a map of 200 topics, with frames of 50ms
  //: at the 95th percentile and 83ms at worst.
  //:
  //: **Not a DOM change at all: a canvas.** The obvious fix, five 1px boxes
  //: moved by `transform` on layers of their own, was measured first and
  //: is not one: on a map of 200 topics, 60 frames of transform writes cost
  //: 419ms of Layerize, the same as 60 frames of `<rect>` attribute writes
  //: (445ms), because any style or attribute change re-layerizes a page this
  //: size. 60 frames of drawing on a canvas cost 8.7ms. So the rectangle is
  //: drawn on a canvas the size of the container, made when the drag starts
  //: and removed when it ends, redrawn at most once a frame from the last
  //: pointer position of that frame. It keeps the dashed accent edge and the
  //: 12% accent wash the SVG rectangle had.
  //: **A box being placed is drawn as what it will be** (the owner,
  //: 2026-10-10: "dragging to create any object should ghost preview that
  //: object, not be the drag selection", and "I tried dragging to create a
  //: frame and it randomly visually cut off half way on the screen"). The
  //: frame, sticky and text tools drew the selection marquee, a dashed
  //: accent wash on a canvas the size of the container as it was when the
  //: drag began, which said "select" rather than "a frame goes here" and was
  //: cut wherever that canvas ended. The ghost is an element of the card
  //: layer in board units, drawn in the placed kind's own look (a frame's
  //: edge and title, a sticky's paper, a text box's dashed field), so it pans
  //: and zooms with the board and covers the whole box the release makes.
  //: The selection marquee keeps its canvas (INBOX 410's cost).
  function wbBeginPlaceGhost(pointerId, place) {
    const layer = wbInstances.layer("wb-html-layer");
    if (!layer) return wbBeginMarqueeRect(pointerId);
    wbMarqueeEl = document.createElement("div");
    wbMarqueeEl.className = "wb-place-ghost";
    wbMarqueeEl.dataset.kind = place;
    wbMarqueeEl.dataset.label = place === "frame" ? "Frame" : place === "sticky" ? "" : "Text";
    wbMarqueeEl.setAttribute("aria-hidden", "true");
    layer.appendChild(wbMarqueeEl);
    wbBoardState.capture(boardEl(), pointerId);
  }

  function wbBeginMarqueeRect(pointerId) {
    wbMarqueeEl = document.createElement("canvas");
    wbMarqueeEl.className = "wb-marquee";
    wbMarqueeEl.setAttribute("aria-hidden", "true");
    const ratio = window.devicePixelRatio || 1;
    const w = boardEl().clientWidth, h = boardEl().clientHeight;
    wbMarqueeEl.width = Math.max(1, Math.round(w * ratio));
    wbMarqueeEl.height = Math.max(1, Math.round(h * ratio));
    wbMarqueeEl.style.width = `${w}px`;
    wbMarqueeEl.style.height = `${h}px`;
    //: Through `wbExportColour`, because a canvas cannot read a `var()` and
    //: the accent may be a `color-mix()` the canvas does not parse either.
    const accent = wbExportColour(getComputedStyle(boardEl()).getPropertyValue("--accent").trim());
    wbMarqueeInk = accent && accent !== "none" ? accent : "#3b82f6";
    boardEl().appendChild(wbMarqueeEl);
    // **The capture is the fix.** Without it every pointermove and pointerup
    // outside the container went to whatever element was under the cursor,
    // so a drag that ended over the top bar, over the left rail or off the
    // window simply never finished, and left its rectangle behind.
    wbBoardState.capture(boardEl(), pointerId);
  }

  //: The selection drag's frames: the same 4-unit threshold as the marquee,
  //: then the whole selection by the pointer's travel from the press, Shift on
  //: one axis, grid-snapped by distance like a card's own drag.
  function wbSelectionDragMove(e) {
    const start = wbMarqueeStart;
    const [x, y] = getLogicalMouse(e);
    if (start.pending) {
      if (Math.abs(x - start.x) < 4 && Math.abs(y - start.y) < 4) return;
      start.origin = wbSelectionDragOrigin();
      if (!start.origin) return wbEndMarqueeDrag();
      start.pending = false;
      wbBoardState.capture(boardEl(), start.pointerId);
    }
    const lock = wbAxisLock(x - start.x, y - start.y, e.shiftKey);
    wbApplyBulkMove(start.origin, lock === "y" ? 0 : wbSnap(x - start.x, e.altKey), lock === "x" ? 0 : wbSnap(y - start.y, e.altKey));
    wbQueueSelectionBar();
  }

  function wbEndSelectionDrag() {
    const { origin, pending } = wbMarqueeStart;
    wbMarqueeStart = null;
    wbEndMarqueeDrag();
    //: The release's own click lands on the canvas: it is not a clear.
    wbMarqueeJustSelected = true;
    if (pending || !origin) return;
    wbFinishDrag(null, origin, false);
  }

  //: The board point under the pointer, to the container's own pixels: the
  //: inverse of `getLogicalMouse`, so the box is where the selection is.
  function wbDrawMarquee() {
    wbMarqueeFrame = 0;
    if (!wbMarqueeEl || !wbMarqueeStart || !wbMarqueeAt) return;
    const t = d3.zoomTransform(boardEl());
    //: A box being placed is drawn at the size it will be made, minimum and
    //: all, so what the ghost shows is what the release creates.
    const box = wbMarqueeStart.place ? wbPlaceBox(wbMarqueeStart, wbMarqueeAt[0], wbMarqueeAt[1]) : null;
    if (box && wbMarqueeEl.classList.contains("wb-place-ghost")) return wbMoveSizeGhost(box);
    const x0 = t.applyX(box ? box.x : wbMarqueeStart.x), y0 = t.applyY(box ? box.y : wbMarqueeStart.y);
    const x1 = t.applyX(box ? box.x + box.w : wbMarqueeAt[0]), y1 = t.applyY(box ? box.y + box.h : wbMarqueeAt[1]);
    const l = Math.round(Math.min(x0, x1)), top = Math.round(Math.min(y0, y1));
    const w = Math.round(Math.abs(x1 - x0)), h = Math.round(Math.abs(y1 - y0));
    const ratio = window.devicePixelRatio || 1;
    //: **The canvas follows the container, every frame** (the owner,
    //: 2026-10-10: a drag preview "randomly visually cut off half way on the
    //: screen"). It was sized once, when the drag began; a container that
    //: grew during the drag (a panel closing, the window maximised, a rail
    //: still animating when the press landed) left the rest of the rectangle
    //: past the canvas's edge, undrawn. Two reads and a compare per frame.
    wbFitMarqueeCanvas(ratio);
    const g = wbMarqueeEl.getContext("2d");
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, wbMarqueeEl.width, wbMarqueeEl.height);
    if (!w || !h) return;
    g.fillStyle = wbMarqueeInk;
    g.strokeStyle = wbMarqueeInk;
    g.globalAlpha = 0.12;
    g.fillRect(l, top, w, h);
    g.globalAlpha = 1;
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.strokeRect(l + 0.5, top + 0.5, Math.max(0, w - 1), Math.max(0, h - 1));
  }

  //: The placing ghost is a box in board space, not the marquee canvas: it
  //: moves by transform (its layer, `will-change`) and takes the size the
  //: release will create, so the only per-move layout is its own.
  function wbMoveSizeGhost(box) {
    wbMarqueeEl.style.transform = `translate(${box.x}px, ${box.y}px)`;
    wbMarqueeEl.style.width = `${box.w}px`;
    wbMarqueeEl.style.height = `${box.h}px`;
  }

  //: The canvas's bitmap and box follow the container's size, compared
  //: before written: a style write on every move would re-layerize the
  //: page (tests/test_marquee_cost.py), so this is a resize, not a draw.
  function wbFitMarqueeCanvas(ratio) {
    const cw = boardEl().clientWidth, ch = boardEl().clientHeight;
    const bw = Math.max(1, Math.round(cw * ratio)), bh = Math.max(1, Math.round(ch * ratio));
    if (wbMarqueeEl.width === bw && wbMarqueeEl.height === bh) return;
    wbMarqueeEl.width = bw;
    wbMarqueeEl.height = bh;
    wbMarqueeEl.style.width = `${cw}px`;
    wbMarqueeEl.style.height = `${ch}px`;
  }

  function wbEdgePanWanted() {
    if (!(wbEdgePan.buttons & 1) || WB_BRUSH_TOOLS.has(window.currentTool) || window.currentTool === "pan") return false;
    const wanted = (wbMarqueeEl && wbMarqueeStart && !wbMarqueeStart.pending) || Boolean(wbGesture && !wbGesture.cancelled && !wbGesture.overTrash && !wbEdgePan.turn);
    return wanted && !wbCompanionHeld(null, "edge pan");
  }

  //: Screen pixels a frame along one axis: positive moves the board's
  //: content towards the far edge (so the near side comes into view).
  function wbEdgePanSpeed(near, far, band) {
    const depth = near > 0 ? near : far > 0 ? -far : 0;
    if (!depth) return 0;
    const share = Math.min(1, Math.abs(depth) / band);
    return Math.sign(depth) * Math.max(1, Math.round(wbEdgePan.max * share * share));
  }

  function wbEdgePanTick() {
    wbEdgePan.frame = 0;
    if (!wbEdgePanWanted() || !document.body.contains(boardEl())) return;
    //: The gesture's own box (`wbCanvasOriginRect`, measured at the press):
    //: this frame runs after the move wrote every moved item, and a fresh
    //: measure here forced a restyle of the board each frame (L-mindmap-17,
    //: 1.3s of a 2.7s 200-topic branch drag).
    const r = wbCanvasOriginRect();
    if (!r) return;
    const band = Math.min(wbEdgePan.band, r.width / 5, r.height / 5);
    const vx = wbEdgePanSpeed(r.left + band - wbEdgePan.x, wbEdgePan.x - (r.right - band), band);
    const vy = wbEdgePanSpeed(r.top + band - wbEdgePan.y, wbEdgePan.y - (r.bottom - band), band);
    if (!vx && !vy) return;
    const k = d3.zoomTransform(boardEl()).k || 1;
    d3.select(boardEl()).call(wbZoom.translateBy, vx / k, vy / k);
    const at = { clientX: wbEdgePan.x, clientY: wbEdgePan.y, buttons: wbEdgePan.buttons, bubbles: true, cancelable: true, view: window };
    if (wbMarqueeEl && wbMarqueeStart) {
      wbMarqueeAt = getLogicalMouse(at);
      wbDrawMarquee();
    } else {
      //: d3-drag's own move listener, called directly: a broadcast
      //: mousemove re-entered the right-press, hover and marquee listeners
      //: with coordinates nobody moved to (audit B16).
      d3.select(window).on("mousemove.drag")?.call(window, new MouseEvent("mousemove", at));
    }
    wbEdgePan.frame = requestAnimationFrame(wbEdgePanTick);
  }

  function portHover(e) {
    if (e.pointerType === "touch" || port.drag) return;
    const [x, y] = getLogicalMouse(e);
    const hit = portTarget(x, y);
    if (!hit) {
      if (port.item) wbClearAnchorHints();
      port.kind = null;
      port.item = null;
      return;
    }
    [port.kind, port.item] = hit;
    wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y, WB_PORT_HIT_PX / zoomK()));
  }

  // Freeform lasso select: asked for directly ("all the selection tools
  // (e.g. rectangle select and lasso)"). Same shape as the marquee just
  // above (empty-canvas-only pointerdown, shift to add, `wbMarqueeJustSelected`
  // shared so the trailing native "click" doesn't wipe the result) but hit-
  // tests each item's *centre point* against the traced polygon rather than
  // rectangle-intersecting its bounding box, a lasso is a freeform loop, so
  // "is this item's middle inside the loop" is the one test that stays
  // cheap (one ray-cast per item, not a polygon-clip against every edge) and
  // still matches what a user visually circled.
  function wbPointInPolygon(px, py, points) {
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const [xi, yi] = points[i], [xj, yj] = points[j];
      const crosses = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
      if (crosses) inside = !inside;
    }
    return inside;
  }

  //: The lasso's half of `wbEndMarqueeDrag`, and it exists for the same
  //: reported bug: a loop released outside the container left its polyline
  //: on the canvas with nothing holding a reference to it.
  function wbEndLassoDrag() {
    wbLassoEl?.remove();
    wbLassoEl = null;
    wbLassoPoints = null;
  }

  function wbPictureTooBig() {
    toast("That picture is over 50 MB, the most the notebook keeps. Shrink it and try again.", "info");
  }

  //: A picture pasted as an address or as markup, not as a file (audit 1028 B28): `text/uri-list`
  //: naming a picture, or the first `<img>` of `text/html` when the plain text is empty or just
  //: that address (a paragraph with a picture in it is still a paragraph).
  function wbPastedPictureAddress(data, html) {
    const plain = (data?.getData("text/plain") || "").trim();
    const listed = (data?.getData("text/uri-list") || "").split(/\r?\n/).map((line) => line.trim()).find((line) => line && !line.startsWith("#"));
    if (listed && /^data:image\/|\.(?:png|jpe?g|gif|webp|avif|bmp|svg)(?:[?#]|$)/i.test(listed)) return listed;
    if (!html) return "";
    const src = new DOMParser().parseFromString(html, "text/html").querySelector("img[src]")?.getAttribute("src") || "";
    return src && (!plain || plain === src) ? src : "";
  }

  //: A `data:` picture is decoded to a file; one already in the notebook is placed as it is; a web
  //: address is refused with the reason, since the page may not fetch the web (`connect-src 'self'`).
  async function wbPlacePastedAddress(src, x, y) {
    const inline = /^data:(image\/[\w.+-]+);base64,([\s\S]*)$/i.exec(src);
    if (inline) {
      if (inline[2].length * 0.75 > wbPictureCap) return wbPictureTooBig();
      const bytes = Uint8Array.from(atob(inline[2]), (char) => char.charCodeAt(0));
      //: The upload route reads the type from the name's extension.
      const ext = inline[1].slice(6).toLowerCase().replace("jpeg", "jpg").replace("svg+xml", "svg");
      return wbPlaceUploadedImage(new File([bytes], `pasted-picture.${ext}`, { type: inline[1] }), x, y);
    }
    const local = src.startsWith(`${location.origin}/media/`) ? src.slice(location.origin.length) : src;
    if (local.startsWith("/media/")) return wbPlaceImageUrl(local, x, y);
    toast("This notebook works offline, so a picture from the web is not fetched. Save the picture, then paste or drop the file.");
  }

  async function wbPlaceUploadedImage(file, x, y) {
    if (wbFmtState.pdf?.isPdf(file)) return wbFmtState.pdf.place(file, x, y);
    if (!file) return;
    //: Said, not dropped silently (L-whiteboard-36): a board takes pictures and PDFs.
    if (!file.type?.startsWith("image/")) return toast(`A board takes pictures and PDFs; ${file.name || "that file"} is neither.`, "info");
    if (file.size > wbPictureCap) return wbPictureTooBig();
    try {
      const formData = new FormData();
      formData.append("file", file);
      //: Board-only until Save to Library: not listed, not read, not captioned (K18).
      formData.append("board", "true");
      const uploaded = await apiJson("/media/upload", {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      await wbPlaceImageUrl(uploaded.url, x, y);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that image" }), true);
    }
  }

  async function wbPlaceImageUrl(url, x, y) {
    try {
      const img = new Image();
      const naturalSize = await new Promise((resolve) => {
        img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
        img.onerror = () => resolve({ w: 300, h: 200 });
        img.src = mediaSrc(url);
      });
      //: Its own size, shrunk only to sit inside the view (wbpaste-1026).
      const view = wbVisibleCanvasRect();
      const [vx0, vy0] = wbClientToBoard(view.left, view.top);
      const [vx1, vy1] = wbClientToBoard(view.right, view.bottom);
      const { width, height } = wbPasteImageSize(naturalSize.w, naturalSize.h, vx1 - vx0, vy1 - vy0);
      await wbCreateObject("image", { url }, x - width / 2, y - height / 2, width, height);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that image" }), true);
    }
  }

  function wbInitDrawPointer() {
    // Opens in Select, like every whiteboard app, panning is always
    // available on held space and the middle mouse button regardless.
    selectWbTool("select"); // the initial state

    // Drawing event handlers on the SVG itself or container
    svgCanvas = wbInstances.layer("wb-svg-layer");

    // The eraser doesn't draw: it deletes whatever the pointer crosses while
    // held, which is renderWhiteboard's job (it owns the sketch/node elements
    // this has to hit-test against). All this needs to track is "is the
    // button currently down", on the container so it works over both the SVG
    // sketch layer and the HTML card layer.
    // Pointer events, not mouse events: they unify mouse/touch/pen into one
    // stream, which is what lets a finger draw, erase and pan here at all, 
    // touch never dispatches "mouse*" events reliably, and never dispatches
    // them for a stylus. `touch-action: none` on .whiteboard-container (CSS)
    // is the other half of this: without it the browser eats the gesture for
    // page-scroll before a single pointer event reaches here.
    wbInstances.on("pointerdown", (e) => {
      if (window.currentTool === "eraser") {
        wbErasing = true;
        wbEraseHad = new Set(wbStacks.undo);
        // Reported directly: "with the eraser, I can't touch and drag to
        // delete items" (the pen works fine touch-dragged the same way).
        // Touch, unlike a mouse, implicitly captures the pointer to
        // whatever element received this pointerdown, so a dragging finger
        // never fires `pointerenter` on the *other* sketches/cards it passes
        // over; the eraser's per-element `pointerenter` handlers (below) can
        // only ever catch the one thing first touched. Releasing capture
        // explicitly restores normal per-element pointer events for the rest
        // of the gesture, and `pointermove` here (coordinate-based, not
        // target-based) is the second half, it doesn't depend on capture
        // behaving correctly at all, so it also covers browsers/pens where
        // pointerenter is delivered unreliably during a fast drag.
        e.target.releasePointerCapture?.(e.pointerId);
      }
    });

    window.addEventListener("pointerup", () => {
      wbErasing = false;
      wbEraseSettle();
    });

    wbInstances.on("pointermove", (e) => {
      if (window.currentTool !== "eraser" || !wbErasing) return;
      const samples = e.getCoalescedEvents?.() ?? [];
      for (const p of samples.length ? samples : [e]) wbEraseAt(p.clientX, p.clientY);
    });

    // Clicking empty canvas with Select active clears the selection, every
    // card/sketch's own click handler calls stopPropagation() under Select,
    // so a click that reaches here was never on an item. A completed marquee
    // drag (below) also ends on empty canvas, which fires this same native
    // `click` right afterward (unlike d3.drag, a plain addEventListener drag
    // gets no automatic click-suppression), `wbMarqueeJustSelected` is the
    // one-shot flag that stops it from wiping out the selection the marquee
    // just made.
    wbInstances.on("click", (e) => {
      //: A press on a shape's own grip that did not move is not a click on
      //: the canvas. The grips live in their own handle group rather than in
      //: the shape (see `wbIsEmptyCanvasTarget`), so nothing stopped this
      //: click, and it deselected the shape: the grips vanished under the
      //: pointer, and the second half of a double-click on the rotate grip
      //: landed on bare canvas (measured: the reset never ran).
      if (e.target.closest?.(".wb-sketch-handle-group")) return;
      if (window.currentTool === "select" || window.currentTool === "lasso") {
        if (wbMarqueeJustSelected) {
          wbMarqueeJustSelected = false;
        } else if (window.currentTool === "select" && wbSelectFrameAt(...getLogicalMouse(e), 8 / (d3.zoomTransform(boardEl()).k || 1))) {
          // A click on a panel's body or a frame's edge selected that frame.
        } else if (window.currentTool === "select" && wbPointInSelectionBounds(...getLogicalMouse(e))) {
          // A click inside the selection's box is on the selection: it stays.
        } else {
          clearWbSelection();
          // The other half of the Escape fix: a click on empty canvas is the
          // first thing anyone tries on a rectangle that will not go away.
          wbClearSelectionOverlays();
        }
      }
      // A text box is placed by clicking, not dragged like a shape, it has
      // no natural "size while dragging" the way a rect does, so click-to-drop
      // at a sensible default size (typed into afterward) is the same model
      // OneNote and every sticky-note tool already use.
      // No `e.target` check: like the Select-clear branch above, this relies
      // on an item's own click handler having already called stopPropagation()
      // if the click actually landed on a card/sketch/object, a click that
      // reaches here bubbled up from truly empty canvas either way.
      if (wbPlaceJustDrawn) {
        wbPlaceJustDrawn = false;
        return;
      }
      if (window.currentTool === "text") {
        const [x, y] = getLogicalMouse(e);
        wbCreateTextBox(x, y);
      }
      if (window.currentTool === "sticky") {
        const [x, y] = getLogicalMouse(e);
        wbCreateSticky(x, y);
      }
      if (window.currentTool === "frame") {
        const [x, y] = getLogicalMouse(e);
        wbCreateFrame(x, y);
      }
    });
  }

  function wbInitMarqueePointer() {
    wbInstances.on("pointerdown", (e) => {
      //: A new press is a new gesture: a one-shot left by a drag released off the board (no click ever reached the
      //: canvas to spend it) must not swallow this press's click.
      wbMarqueeJustSelected = false;
      wbPlaceJustDrawn = false;
      //: **The text and sticky tools draw their box too** (the owner,
      //: 2026-09-24: "I cant drag to create a custom sized textbox on the
      //: whiteboard when selected on the textbox tool", "same with the sticky
      //: notes"). A click still drops the default size (the canvas `click`
      //: below); a press that travels draws the box it will make, with the
      //: marquee's own dashed rectangle and the same 4-unit threshold, so the
      //: two gestures cannot disagree about where a click ends and a drag
      //: begins.
      //: And the frame tool (decision 14), the same two gestures.
      const place = ["text", "sticky", "frame"].includes(window.currentTool) ? window.currentTool : null;
      if ((window.currentTool !== "select" && !place) || !wbIsEmptyCanvasTarget(e.target)) return;
      //: A finger on bare canvas with Select pans (`wbZoomFilter`), so it is not also the start of an area select.
      if (!place && e.pointerType === "touch") return;
      // Primary button only. A right-click opens the context menu and a middle
      // click pans; neither ends with the pointerup this drag is waiting for,
      // so both used to start a rectangle that nothing would ever remove.
      if (e.button !== 0 || !e.isPrimary) return;
      // A gesture already in flight loses its rectangle rather than orphaning
      // it: `wbMarqueeEl` is one variable, so a second pointerdown overwrote
      // the reference to the first rect and left it on the canvas forever.
      wbEndMarqueeDrag();
      const [x, y] = getLogicalMouse(e);
      //: **Nothing is claimed until the pointer actually travels.** The
      //: rectangle and the pointer capture used to be taken here, on the press,
      //: and a capture re-targets the compatibility `click` at the capturing
      //: element: harmless while this only ever began over bare canvas, fatal
      //: the moment it also begins over a link (see `wbIsEmptyCanvasTarget`),
      //: because the link's own click, which is what selects it, was delivered
      //: to the container instead and a connector could no longer be clicked.
      //: Deferring both to the first real movement keeps the press a press: a
      //: click reaches whatever was under it, and a drag is still a drag from
      //: the point it started at.
      //: A press inside the selection's box drags the selection (Shift adds to
      //: it, so that press stays a marquee).
      const move = !place && !e.shiftKey && window.currentTool === "select" && wbPointInSelectionBounds(x, y);
      wbMarqueeStart = { x, y, shiftKey: e.shiftKey, pointerId: e.pointerId, pending: true, place, move };
      //: **The overlay layer, above the cards.** INBOX 84: "whiteboard
      //: rectangle selection draws behind objects." `#wb-zoom-group` lives in
      //: `#wb-svg-layer`, which is *under* `#wb-html-layer` by DOM order, on
      //: purpose, so a pen stroke passes behind a card. A marquee is the
      //: opposite case: it says what you are about to select, and a rectangle
      //: hidden behind the very things it is selecting says nothing. The lasso
      //: has always gone to `#wb-overlay-zoom-group` for exactly this reason
      //: (see its own append below); the rectangle never did.
    });

    window.addEventListener("pointermove", (e) => {
      if (!wbMarqueeStart) return;
      if (wbMarqueeStart.move) return wbSelectionDragMove(e);
      let [x, y] = getLogicalMouse(e);
      //: Shift makes a drawn box square, read live rather than from the press
      //: (on the marquee the press's Shift means "add to the selection").
      if (wbMarqueeStart.place && e.shiftKey) [x, y] = wbSquareCorner(wbMarqueeStart, x, y);
      else if (wbMarqueeStart.place && !wbMarqueeStart.pending) [x, y] = wbDrawOutSnap(wbMarqueeStart.x, wbMarqueeStart.y, x, y, e);
      if (wbMarqueeStart.pending) {
        // The same 4 units the completed gesture is measured against below, so
        // a press that never becomes a drag draws nothing and claims nothing.
        if (Math.abs(x - wbMarqueeStart.x) < 4 && Math.abs(y - wbMarqueeStart.y) < 4) return;
        wbMarqueeStart.pending = false;
        if (wbMarqueeStart.place) wbBeginPlaceGhost(wbMarqueeStart.pointerId, wbMarqueeStart.place);
        else wbBeginMarqueeRect(wbMarqueeStart.pointerId);
        // Placed now, before its first paint, so it never shows as a dot at
        // the container's corner for a frame.
        wbMarqueeAt = [x, y];
        wbDrawMarquee();
        return;
      }
      wbMarqueeAt = [x, y];
      if (!wbMarqueeFrame) wbMarqueeFrame = requestAnimationFrame(wbDrawMarquee);
    });
  }

  function wbInitEdgePanPointer() {
    //: **A drag past the edge moves the board** (INBOX 608, the owner: "when I
    //: drag select off the screen on the whiteboard and mind map ... it doesnt
    //: scroll down or up or the way I am dragging"). A marquee, an item or a
    //: branch carried to the edge of the canvas used to stop there: the board
    //: did not move, so anything past the edge could not be reached without
    //: letting go. Every whiteboard app pans here (Miro, FigJam, draw.io).
    //:
    //: A band inside each edge of the canvas; the deeper the pointer is in it
    //: (or past it, off the canvas, which the pointer capture still reports),
    //: the faster the board moves, up to `max` screen pixels a frame. Eased
    //: (squared), so the first few pixels of the band creep and a pointer held
    //: at the very edge travels. One frame loop while the pointer is in a band,
    //: none otherwise.
    //:
    //: After each step the pointer is replayed where it is: the marquee is
    //: redrawn from it, and an item drag gets a synthetic move at the same
    //: screen point, which d3-drag measures against its container (a layer
    //: that moved with the pan), so the item travels exactly as far as the
    //: board did and stays under the pointer. A rotation is excluded (an
    //: angle does not need room), and so are the pen tools and the hand.
    wbEdgePan = { x: 0, y: 0, buttons: 0, frame: 0, turn: false, band: 56, max: 22 };

    window.addEventListener("pointerdown", (e) => {
      wbEdgePan.turn = Boolean(e.target?.closest?.(".wb-rotate-handle, .wb-sketch-rotate-handle"));
    }, true);

    window.addEventListener("pointermove", (e) => {
      if (e.pointerType === "touch") return;
      wbEdgePan.x = e.clientX;
      wbEdgePan.y = e.clientY;
      wbEdgePan.buttons = e.buttons;
      if (!wbEdgePan.frame && wbEdgePanWanted()) wbEdgePan.frame = requestAnimationFrame(wbEdgePanTick);
    });

    window.addEventListener("pointerup", () => {
      wbEdgePan.buttons = 0;
      if (wbEdgePan.frame) cancelAnimationFrame(wbEdgePan.frame);
      wbEdgePan.frame = 0;
    }, true);
  }

  function wbInitCanvasDblclick() {
    // Anchor points weren't discoverable until a link drag was already under
    // way: asked for directly: "when I hover over objects, their anchor
    // points should display... so I can connect them." A plain hover with a
    // link-type tool selected, no drag started yet, now shows the same 8
    // fixed-point hints the in-progress drag already draws (`wbShowAnchorHints`,
    // shared so the two can't drift visually apart). Skips while an actual
    // link drag is running (`wbLinkDragActive`), that path already redraws
    // hints every frame from the live pointer position, and this would just
    // be a second, slightly-stale write to the same DOM nodes.
    //: On the container, not on each handle: the handles are rebuilt by the
    //: render on every change, and a listener bound per handle is a listener
    //: lost on the next repaint (the mistake `wbWireContextMenu` documents).
    wbInstances.on("dblclick", (e) => {
      const turn = e.target.closest?.(".wb-rotate-handle, .wb-sketch-rotate-handle");
      if (turn) {
        e.preventDefault();
        e.stopPropagation();
        wbResetRotation(turn, e.ctrlKey || e.metaKey);
        return;
      }
      const handle = e.target.closest?.(".wb-resize-handle, .wb-map-resize-grip");
      if (!handle) return;
      e.preventDefault();
      e.stopPropagation();
      //: A frame fits what it holds, not its own text: the edge named by the
      //: handle, or the two of a corner (INBOX 821).
      const frameEl = handle.closest(".wb-object-frame");
      if (frameEl && handle.dataset.handle) {
        wbFrameFit((wbState.objects || []).find((o) => o.id === Number(frameEl.dataset.id)), handle.dataset.handle);
        return;
      }
      const owner = handle.closest(".wb-object, .node-card");
      if (owner?.classList.contains("wb-object-image")) wbFitImage(owner);
      else wbFitToText(owner);
    });

    //: **The two gestures a map has to answer on its own canvas** (MINDMAP_PLAN
    //: §13, the owner: the tools "dont show themselves how id expect"). Both
    //: were measured doing nothing at all before this: a right-click on empty
    //: map canvas opened no menu, and a double-click added no topic, so the
    //: first two things anybody tries on a blank part of a mind map were dead.
    //: Neither adds a resting affordance to the canvas (§13's decision 5); both
    //: are the app's own recipes, `openMenuAtPoint` for the menu and the map's
    //: own create for the topic.
    //:
    //: **A board answers the double-click too** (the conventions pass,
    //: 2026-09-23): a text box where you pressed, ready to type, which is what
    //: Excalidraw and tldraw do on bare canvas. Measured doing nothing before.
    //: A sticky is one key away (N) and in the canvas menu below; the text box
    //: is the plainer of the two, and the one both of those apps make.
    //:
    //: A branch line is not bare canvas here, whatever `wbIsEmptyCanvasTarget`
    //: says for a marquee: a double-click on a line asks for its label (see
    //: `wbWireMapEdgeGestures`), and it used to fall through to this and make a
    //: new trunk on top of the line.
    wbInstances.on("dblclick", (e) => {
      if (window.currentTool !== "select") return;
      if (!wbIsEmptyCanvasTarget(e.target) || wbIsEditingTarget(e.target)) return;
      if (e.target.closest?.(".wb-map-edge-group, .sketch-group")) return;
      e.preventDefault();
      const [x, y] = getLogicalMouse(e);
      if (wbIsMap()) wbMapAddRootAt(x, y);
      else wbCreateTextBox(x, y);
    });
  }

  function wbInitCanvasMenus() {
    //: One builder for the canvas menu, because the right-click and the hold
    //: are the same menu and a second copy is how the two come to disagree
    //: (DESIGN.md: every `contextmenu` listener is counted against a
    //: `wireLongPress` call in the same file, and `tests/test_ui_recipes.py`
    //: fails a right-click menu with no long-press twin).
    openMapCanvasMenu = (clientX, clientY) => {
      const [x, y] = getLogicalMouse({ clientX, clientY });
      const index = wbMapIndex();
      const folded = index.nodes.filter((n) => n.data?.collapsed).length;
      const open = wbMapFoldToLevel.open(index);
      //: One more or one less level, each greyed unless it changes something (INBOX 1774).
      const hiddenByFold = wbMapHidden(index);
      const moreLevel = makeMenuItem("ph:plus-circle Show one more level", "Open the shallowest folded branches (Alt+=)", () => wbMapFoldToLevel({ by: 1 }));
      const lessLevel = makeMenuItem("ph:minus-circle Show one less level", "Fold the deepest open branches (Alt+-)", () => wbMapFoldToLevel({ by: -1 }));
      moreLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, 1).ids.length;
      lessLevel.disabled = !wbMapBuild.ring(index, hiddenByFold, -1).ids.length;
      const items = [
        makeMenuItem("ph:plus-circle Add a topic here", "A new trunk, where you pressed: or double-click the canvas", () => wbMapAddRootAt(x, y)),
        makeMenuItem("ph:broom Tidy the map", "Lay every unpinned topic out again", () => wbMapTidy()),
        makeMenuItem(
          folded ? `ph:arrows-out-line-vertical Open every folded branch (${folded})` : "ph:arrows-out-line-vertical Open every folded branch",
          folded ? "This map has folded branches" : "Nothing is folded on this map",
          () => wbMapExpandAll()
        ),
        makeMenuItem(
          `ph:arrows-in-line-vertical Fold every branch${open ? ` (${open})` : ""}`,
          open ? "Show the trunks only (Alt+1)" : "Every branch is already folded",
          () => wbMapFoldToLevel(1)
        ),
        moreLevel,
        lessLevel,
        makeMenuItem("ph:frame-corners Fit everything", "Show the whole map (Shift+1)", () =>
          document.getElementById("wb-zoom-fit")?.click()
        ),
      ];
      openMenuAtPoint(items, "This map", clientX, clientY);
    };

    //: **And a board's canvas has its own menu** (the conventions pass): the
    //: browser's page menu is what a right-click on bare board canvas used to
    //: open, where Figma, Miro and tldraw all give paste, select all and the
    //: zoom. Each row names its key, so the menu is also where the keys are
    //: learnt.
    openBoardCanvasMenu = (clientX, clientY) => {
      const [x, y] = getLogicalMouse({ clientX, clientY });
      const items = [];
      if (wbClipboard) {
        const count = wbClipboard.things;
        items.push(makeMenuItem(
          count > 1 ? `ph:clipboard-text Paste ${nounCount(count, "item")} here` : "ph:clipboard-text Paste here",
          "Ctrl+V pastes beside the original, Ctrl+Shift+V in place", () => wbPasteClipboard({ at: [x, y] })
        ));
        items.push(makeMenuItem("ph:clipboard Paste here without comments", "Ctrl+Alt+Shift+V", () => wbPasteClipboard({ at: [x, y], noComments: true })));
      }
      items.push(makeMenuItem("ph:clipboard-text Paste special", "Choose how the clipboard lands", () => wbPasteSpecialMenu()));
      items.push(
        makeMenuItem("ph:text-t Add a text box here", "Or double-click the canvas", () => wbCreateTextBox(x, y)),
        makeMenuItem("ph:note Add a sticky note here", "N", () => wbCreateSticky(x, y)),
        makeMenuItem("ph:frame-corners Add a frame here", "F", () => wbCreateFrame(x, y)),
        makeMenuItem("ph:selection-all Select all", "Ctrl+A", () => wbSelectAllItems()),
        makeMenuItem("ph:magnifying-glass Zoom to 100%", "Ctrl+1", wbZoomTo100),
        makeMenuItem("ph:frame-corners Fit everything", "Shift+1", () => wbZoomToFit()),
      );
      //: The way back to a locked item (decision 15): it lets the pointer
      //: through, so a right-click on it lands here, on the board.
      //: Right-click on the locked item itself unlocks that one, first.
      const lockedHere = wbLockedItemAt(x, y);
      if (lockedHere) {
        items.unshift(makeMenuItem(
          "ph:lock-simple-open Unlock this item", "It is locked, so the pointer passes through it",
          () => wbSetLocked([[lockedHere.kind, lockedHere.item]], false)
        ));
      }
      const locked = wbLockedItems().length;
      if (locked) {
        items.push(makeMenuItem(
          `ph:lock-simple-open Unlock ${locked} locked item${locked === 1 ? "" : "s"}`,
          "Ctrl+Shift+L with nothing selected", () => wbUnlockAll()
        ));
      }
      openMenuAtPoint(items, "This board", clientX, clientY);
    };

    //: The first press on a locked item, which lets the pointer through, says how to unlock it.
    wbInstances.on("pointerdown", wbOnLockPress, true);

    wbCanvasMenuWanted = (target) =>
      wbIsEmptyCanvasTarget(target) && !wbIsEditingTarget(target)
      && !target.closest?.(".wb-map-edge-group, .sketch-group");

    openCanvasMenu = (clientX, clientY) => (wbIsMap()
      ? openMapCanvasMenu(clientX, clientY)
      : openBoardCanvasMenu(clientX, clientY));
  }

  function wbInitRightPress() {
    wbRightOwns = () => wbRightPress && (!wbRightPress.up || Date.now() - wbRightPress.upAt < 400);

    window.addEventListener("mousedown", (e) => {
      if (e.button !== 2) return;
      wbRightPress = boardEl().contains(e.target) && wbCanvasMenuWanted(e.target)
        ? { x: e.clientX, y: e.clientY, moved: false, up: false, upAt: 0 } : null;
    }, true);

    window.addEventListener("mousemove", (e) => {
      if (!wbRightPress || wbRightPress.up) return;
      if ((e.buttons & 2) !== 2) { wbRightPress = null; return; }
      if (wbRightPress.moved) return;
      if (Math.hypot(e.clientX - wbRightPress.x, e.clientY - wbRightPress.y) < WB_RIGHT_SLOP) {
        //: Hold the zoom's own move listener (capture, on the window, added
        //: after this one) until the press is a drag.
        e.stopImmediatePropagation();
      } else {
        wbRightPress.moved = true;
      }
    }, true);

    window.addEventListener("mouseup", (e) => {
      if (e.button !== 2 || !wbRightPress || wbRightPress.up) return;
      wbRightPress.up = true;
      wbRightPress.upAt = Date.now();
      if (!wbRightPress.moved) {
        const { clientX, clientY } = e;
        setTimeout(() => openCanvasMenu(clientX, clientY), 0);
      }
    }, true);

    wbInstances.on("contextmenu", (e) => {
      //: A topic and a line have rings of their own, and both stop the event
      //: before it reaches here; this is the canvas itself, which had nothing.
      if (!wbCanvasMenuWanted(e.target)) return;
      e.preventDefault();
      if (wbRightOwns()) return;
      openCanvasMenu(e.clientX, e.clientY);
    });

    //: The same menu from a hold, which is the right-click a phone has.
    wireLongPress({ addEventListener: (type, fn, opts) => wbInstances.on(type, fn, opts) }, (event, point) => {
      if (!wbCanvasMenuWanted(event.target)) return;
      openCanvasMenu(point.x, point.y);
    });

    //: Where a keyboard paste lands (`wbPointerOnBoard`).
    wbInstances.on("pointermove", (e) => {
      wbPointerClient = { clientX: e.clientX, clientY: e.clientY };
    }, { passive: true });

    wbInstances.on("pointerleave", () => { wbPointerClient = null; });

    wbInstances.on("pointermove", wbOnFrame((e) => {
      if (wbLinkDragActive) return;
      //: Off a link tool there are no dots to show, and any left over go (INBOX
      //: 573: the cross-link tool's dots stayed on a topic after switching back
      //: to Select, through Escape, a press on the canvas, Undo and a tab switch).
      if (window.currentTool === "select" && !e.buttons) {
        portHover(e);
        return;
      }
      if (!window.currentTool || !window.currentTool.startsWith("link-")) {
        wbClearAnchorHints();
        return;
      }
      const [x, y] = getLogicalMouse(e);
      // Every linkable thing, in its rotated frame, this was cards only, on
      // their unrotated box (reported: stickies "light up" wrong).
      const hit = wbLinkCandidateAt(x, y);
      if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y));
      else wbClearAnchorHints();
    }, true), { passive: true });
  }

  function wbInitPortHover() {
    // --- Connection points with Select (wb-phase2 step 5; draw.io's ports) ---
    //
    // With Select, pointing at a shape, card or text box shows its connection
    // points (`wbAnchorPositions`: a polygon's corners and side middles, an
    // ellipse's compass points), and a press on one draws a connector from it
    // (an elbow with an arrow, as clone-and-connect makes) to the item it is
    // let go on, at that item's nearest point, or to a free end on empty board.
    // Not on what is selected (its resize grips sit where its ports are), a
    // locked item, a map (whose lines are its tree), or touch (no hover).
    port = { kind: null, item: null, drag: null };

    zoomK = () => d3.zoomTransform(boardEl()).k || 1;

    portTarget = (x, y) => {
      let hit = wbLinkCandidateAt(x, y);
      if (!hit && port.item) {
        //: Keep the points while the pointer is just outside the outline,
        //: which is where it is on its way to one of them.
        const box = wbItemBBox(port.kind, port.item);
        const pad = 14 / zoomK();
        if (box && x >= box.minX - pad && x <= box.maxX + pad && y >= box.minY - pad && y <= box.maxY + pad) hit = [port.kind, port.item];
      }
      if (!hit || wbIsMap() || wbIsLocked(hit[0], hit[1]) || wbSelectedKeys().has(wbMultiKey(hit[0], hit[1].id))) return null;
      return hit;
    };

    portEnd = () => {
      port.drag?.path?.remove();
      port.drag = null;
      wbLinkDragActive = false;
      wbClearAnchorHints();
      wbFmtState.linkEdge?.cue(null);
    };

    wbInstances.on("pointerdown", (e) => {
      if (e.button !== 0 || e.pointerType === "touch" || window.currentTool !== "select" || !port.item || e.altKey || e.shiftKey) return;
      //: A selected connector's end grip wins over a port beneath it (INBOX
      //: 1328: dragging the end of an arrow drew a second arrow instead,
      //: because the grip sits on the very edge point the item's port is).
      if (e.target?.closest?.(".wb-link-endpoint-handle, .wb-resize-handle, .wb-rotate-handle")) return;
      const [x, y] = getLogicalMouse(e);
      if (!portTarget(x, y)) return;
      //: Near enough to a point, and never so far that a small shape on screen
      //: is all points: at most a fifth of its shorter side, so its middle is
      //: still the shape (measured at a phone's fitted zoom: a 36px-tall box
      //: was a connector from its middle at a flat 9px).
      const box = wbItemBBox(port.kind, port.item);
      const side = box ? Math.min(box.maxX - box.minX, box.maxY - box.minY) * zoomK() : 0;
      const anchor = wbNearestAnchor(port.kind, port.item, x, y, Math.min(WB_PORT_HIT_PX, side * 0.2) / zoomK());
      if (!anchor) return;
      //: Before d3-drag's mousedown: a pointerdown's default prevented is
      //: the mouse events it would have made, so the item does not move.
      e.preventDefault();
      e.stopPropagation();
      const start = wbAnchorPoint(port.kind, port.item, anchor);
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", "wb-port-preview");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", window.currentStrokeColor || "#888888");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-dasharray", "6 4");
      path.setAttribute("pointer-events", "none");
      wbInstances.layer("wb-zoom-group")?.appendChild(path);
      port.drag = { kind: port.kind, item: port.item, anchor, start, path, moved: false, id: e.pointerId };
      wbLinkDragActive = true;
      wbBoardState.capture(boardEl(), e.pointerId);
    }, true);

    //: The line and `moved` follow every event (release reads `moved`); only
    //: the anchor hit test waits for the frame.
    portHints = wbOnFrame(({ drag, x, y }) => {
      if (port.drag !== drag) return;
      const hit = wbLinkCandidateAt(x, y, drag.kind, drag.item.id);
      if (hit) wbShowAnchorHints(hit[0], hit[1], wbNearestAnchor(hit[0], hit[1], x, y));
      else wbShowAnchorHints(drag.kind, drag.item, drag.anchor);
      wbFmtState.linkEdge?.cue(hit ? null : [x, y]);
    });

    wbInstances.on("pointermove", (e) => {
      const drag = port.drag;
      if (!drag) return;
      const [x, y] = getLogicalMouse(e);
      drag.moved = drag.moved || Math.hypot(x - drag.start.x, y - drag.start.y) * zoomK() > 4;
      drag.path.setAttribute("d", `M ${drag.start.x} ${drag.start.y} L ${x} ${y}`);
      portHints({ drag, x, y });
    });
  }

  function wbInitPortRelease() {
    wbInstances.on("keydown", (e) => {
      if (port.drag && e.key === "Escape") {
        e.stopPropagation();
        portEnd();
      }
    }, true);

    wbInstances.on("pointerup", async (e) => {
      const drag = port.drag;
      if (!drag) return;
      const [x, y] = getLogicalMouse(e);
      portEnd();
      //: The click the release makes lands on the container (the pointer was
      //: captured there), which reads it as a click on empty board and clears
      //: the selection this is about to make: swallowed, for this task only.
      const swallow = (ev) => {
        ev.stopPropagation();
        ev.preventDefault();
      };
      window.addEventListener("click", swallow, true);
      setTimeout(() => window.removeEventListener("click", swallow, true), 0);
      if (!drag.moved) {
        //: A press that did not travel is a click on the item it is on.
        selectWbItem(drag.kind, drag.item.id);
        return;
      }
      const hit = wbLinkCandidateAt(x, y, drag.kind, drag.item.id);
      const data = {
        type: "link-straight",
        route: "elbow",
        sourceId: drag.item.id,
        sourceKind: drag.kind === "node" ? undefined : drag.kind,
        sourceAnchor: drag.anchor,
        color: window.currentStrokeColor || "#888888",
        width: 2,
        endCap: "arrow",
      };
      if (hit) {
        data.targetId = hit[1].id;
        data.targetKind = hit[0] === "node" ? undefined : hit[0];
        data.targetAnchor = wbNearestAnchor(hit[0], hit[1], x, y) || undefined;
      } else {
        const edge = wbFmtState.linkEdge?.hitAt(x, y);
        data.targetPoint = edge ? { x: edge.x, y: edge.y } : { x: Math.round(x), y: Math.round(y) };
        if (edge) data.targetEdge = { id: edge.id, t: edge.t };
      }
      try {
        const made = await apiJson("/whiteboard/sketches", {
          method: "POST",
          body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }),
        });
        wbState.sketches.push(made);
        wbPushUndo({ action: "create", kind: "sketch", id: made.id });
        renderWhiteboardNow();
        selectWbItem("sketch", made.id);
        wbAnnounce(hit || data.targetEdge ? "Connected." : "Connector drawn to a free end.");
      } catch (error) {
        toast(error.message || "The connector could not be made.", true);
      }
    });
  }

  function wbInitMarqueeRelease() {
    // On `window`, not on the container, and for three event names rather than
    // one. The container's own pointerup is not enough: a capture can be lost
    // (`lostpointercapture`), a gesture can be taken over by the browser
    // (`pointercancel`), and a synthetic pointerdown was never captured at all.
    // Every one of those used to leave the rectangle on the board.
    wbBoardState.onGestureLost(() => wbEndMarqueeDrag());

    window.addEventListener("pointerup", (e) => {
      if (!wbMarqueeStart) return;
      if (wbMarqueeStart.move) return wbEndSelectionDrag();
      let [x, y] = getLogicalMouse(e);
      const start = wbMarqueeStart;
      if (start.place && e.shiftKey) [x, y] = wbSquareCorner(start, x, y);
      else if (start.place) [x, y] = wbDrawOutSnap(start.x, start.y, x, y, e);
      wbClearAlignmentGuides();
      const mx = Math.min(start.x, x), my = Math.min(start.y, y);
      const mw = Math.abs(x - start.x), mh = Math.abs(y - start.y);
      //: Shift at the press or at the release adds (the owner, 2026-10-07).
      const shiftKey = start.shiftKey || e.shiftKey;
      wbEndMarqueeDrag();
      // Too small to be a deliberate drag, the plain "click" listener above
      // already handles this as a click-to-clear-selection instead (or, with
      // the text and sticky tools, as a click that drops the default size).
      if (mw < 4 && mh < 4) return;
      if (start.place) {
        //: The release makes a `click` on the canvas as well, which would drop
        //: a second, default-sized box where the drag ended.
        wbPlaceJustDrawn = true;
        const box = wbPlaceBox(start, x, y);
        if (start.place === "sticky") wbCreateSticky(x, y, box);
        else if (start.place === "frame") wbCreateFrame(x, y, box);
        else wbCreateTextBox(x, y, box);
        return;
      }
      if (!shiftKey) wbMultiSelection.clear();
      //: The one item selected before a Shift-drag stays in: it lives in
      //: `wbSelectedItem`, not the set, and was dropped (the owner, 2026-10-07).
      else if (wbSelectedItem) wbMultiSelection.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
      for (const node of wbState.nodes) {
        if (node.locked || wbFmtState.isolate?.outside("node", node)) continue; // decision 15: out of reach until unlocked
        const el = document.querySelector(WB_SELECTOR_BY_KIND.node(node.id));
        const w = el?.offsetWidth || 250, h = el?.offsetHeight || 150;
        if (rectsIntersect(mx, my, mw, mh, node.x, node.y, w, h)) {
          wbMultiSelection.add(wbMultiKey("node", node.id));
        }
      }
      for (const obj of wbState.objects || []) {
        if (wbIsLocked("object", obj) || wbFmtState.isolate?.outside("object", obj)) continue;
        //: A frame only when the sweep holds all of it (decision 14): a sweep
        //: drawn inside a frame is about what is in it, and taking the frame
        //: along would make the next drag carry the frame and everything else.
        const hit = obj.kind === "frame"
          ? mx <= obj.x && my <= obj.y && mx + mw >= obj.x + obj.width && my + mh >= obj.y + obj.height
          : rectsIntersect(mx, my, mw, mh, obj.x, obj.y, obj.width, obj.height);
        if (hit) {
          wbMultiSelection.add(wbMultiKey("object", obj.id));
        }
      }
      for (const sketch of wbState.sketches) {
        const parsed = wbSketchParsedData(sketch);
        if (!parsed) continue; // a link sketch: nothing here to select as a shape
        if (parsed.locked || wbFmtState.isolate?.outside("sketch", sketch)) continue;
        const bbox = wbPathBBox(parsed.d);
        if (bbox && rectsIntersect(mx, my, mw, mh, bbox.minX, bbox.minY, bbox.width, bbox.height)) {
          wbMultiSelection.add(wbMultiKey("sketch", sketch.id));
        }
      }
      //: **A sweep that caught one thing selects that thing properly.**
      //: Reported: "shapes like circles and lines dont visibly select and show
      //: anchor points when I highlight select over them". A drawn shape is a
      //: sketch, and a sketch's selection box and its eight anchors are drawn
      //: by `wbRenderSketchHandles`, which only ever runs for the *single*
      //: selection: a marquee cleared that and put the id in the multi set
      //: instead, where a sketch had no decoration of any kind. So sweeping
      //: over a circle really did select it and really did show nothing.
      //: Promoting a one-item sweep is the honest fix rather than a second
      //: decoration: one item selected by a sweep and the same item selected by
      //: a click are the same selection, and should look and behave the same.
      //: (A sweep over several still has no one box to hang anchors off, which
      //: is why the class also has a visible style of its own now.)
      wbSelectedItem = null;
      if (wbMultiSelection.size === 1) {
        const key = [...wbMultiSelection][0];
        const sep = key.indexOf(":");
        wbMultiSelection.clear();
        wbSelectedItem = { kind: key.slice(0, sep), id: Number(key.slice(sep + 1)) };
      }
      wbMarqueeJustSelected = true;
      wbApplySelectionHighlight();
    });

    //: Both drags, from anywhere in the file, see `wbCancelSelectionDragRef`.
    wbCancelSelectionDragRef = () => {
      //: In flight means drawn: a press that has not travelled yet is still a
      //: click (see the marquee's `pending`), and Escape then means what it
      //: means with nothing in hand.
      const inFlight = Boolean((wbMarqueeStart && !wbMarqueeStart.pending) || wbLassoEl);
      wbEndMarqueeDrag();
      wbEndLassoDrag();
      //: The release that ends a taken-back drag still makes a `click` on the
      //: canvas, and a canvas click clears the selection: the same one-shot a
      //: finished marquee uses keeps what Escape kept.
      if (inFlight) {
        wbMarqueeJustSelected = true;
        //: And a text or sticky box taken back is not then dropped at its
        //: default size by the same release.
        wbPlaceJustDrawn = true;
      }
      return inFlight;
    };
  }

  function wbInitLasso() {
    wbInstances.on("pointerdown", (e) => {
      // Unlike the marquee (`wbIsEmptyCanvasTarget`, above: empty canvas
      // only, since a drag starting *on* a card there means "move it"), a
      // lasso loop is drawn freeform and routinely starts right at the edge
      // of the first thing it means to circle, reported directly as "the
      // lasso tool doesn't work properly". Still excludes an actual handle,
      // which needs its own drag gesture to keep working.
      if (window.currentTool !== "lasso" || e.target.closest?.(".wb-resize-handle, .wb-rotate-handle, .wb-object-grip, .wb-link-endpoint-handle")) return;
      if (e.button !== 0 || !e.isPrimary) return;
      wbEndLassoDrag();
      const [x, y] = getLogicalMouse(e);
      wbLassoPoints = [[x, y]];
      wbLassoShift = e.shiftKey;
      wbLassoEl = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      wbLassoEl.setAttribute("class", "wb-lasso");
      wbLassoEl.setAttribute("points", `${x},${y}`);
      // The overlay layer, which paints above the HTML card layer, in the
      // base SVG the loop was drawn *under* every card and sticky (reported:
      // "the lasso select tool is behind everything").
      wbInstances.layer("wb-overlay-zoom-group").appendChild(wbLassoEl);
      wbBoardState.capture(boardEl(), e.pointerId);
    });

    wbBoardState.onGestureLost(() => wbEndLassoDrag());

    window.addEventListener("pointermove", (e) => {
      if (!wbLassoPoints) return;
      const [x, y] = getLogicalMouse(e);
      wbLassoPoints.push([x, y]);
      wbLassoEl.setAttribute("points", wbLassoPoints.map(([px, py]) => `${px},${py}`).join(" "));
    });

    window.addEventListener("pointerup", () => {
      if (!wbLassoPoints) return;
      const points = wbLassoPoints, shiftKey = wbLassoShift;
      wbEndLassoDrag();
      if (points.length < 3) return; // a tap, not a loop, nothing to select
      if (!shiftKey) wbMultiSelection.clear();
      //: The one item selected before a Shift-drag stays in: it lives in
      //: `wbSelectedItem`, not the set, and was dropped (the owner, 2026-10-07).
      else if (wbSelectedItem) wbMultiSelection.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
      for (const node of wbState.nodes) {
        if (node.locked || wbFmtState.isolate?.outside("node", node)) continue; // decision 15: out of reach until unlocked
        const el = document.querySelector(WB_SELECTOR_BY_KIND.node(node.id));
        const w = el?.offsetWidth || 250, h = el?.offsetHeight || 150;
        if (wbPointInPolygon(node.x + w / 2, node.y + h / 2, points)) {
          wbMultiSelection.add(wbMultiKey("node", node.id));
        }
      }
      for (const obj of wbState.objects || []) {
        if (wbIsLocked("object", obj) || wbFmtState.isolate?.outside("object", obj)) continue;
        if (wbPointInPolygon(obj.x + obj.width / 2, obj.y + obj.height / 2, points)) {
          wbMultiSelection.add(wbMultiKey("object", obj.id));
        }
      }
      for (const sketch of wbState.sketches) {
        const parsed = wbSketchParsedData(sketch);
        if (!parsed) continue; // a link sketch: nothing here to select as a shape
        if (parsed.locked || wbFmtState.isolate?.outside("sketch", sketch)) continue;
        const bbox = wbPathBBox(parsed.d);
        if (bbox && wbPointInPolygon(bbox.minX + bbox.width / 2, bbox.minY + bbox.height / 2, points)) {
          wbMultiSelection.add(wbMultiKey("sketch", sketch.id));
        }
      }
      //: **A sweep that caught one thing selects that thing properly.**
      //: Reported: "shapes like circles and lines dont visibly select and show
      //: anchor points when I highlight select over them". A drawn shape is a
      //: sketch, and a sketch's selection box and its eight anchors are drawn
      //: by `wbRenderSketchHandles`, which only ever runs for the *single*
      //: selection: a marquee cleared that and put the id in the multi set
      //: instead, where a sketch had no decoration of any kind. So sweeping
      //: over a circle really did select it and really did show nothing.
      //: Promoting a one-item sweep is the honest fix rather than a second
      //: decoration: one item selected by a sweep and the same item selected by
      //: a click are the same selection, and should look and behave the same.
      //: (A sweep over several still has no one box to hang anchors off, which
      //: is why the class also has a visible style of its own now.)
      wbSelectedItem = null;
      if (wbMultiSelection.size === 1) {
        const key = [...wbMultiSelection][0];
        const sep = key.indexOf(":");
        wbMultiSelection.clear();
        wbSelectedItem = { kind: key.slice(0, sep), id: Number(key.slice(sep + 1)) };
      }
      wbMarqueeJustSelected = true;
      wbApplySelectionHighlight();
    });
  }

  function wbInitPicturePaste() {
    // Images: paste, drag-and-drop, or the upload button, asked for
    // directly, and all three funnel through the same upload+place path
    // `handleFileUpload` already established for notes (POST /media/upload,
    // then a placed reference, a board object here instead of markdown text).
    //: The most the notebook keeps of one upload (`routes_files.MAX_FILE_BYTES`), said before the
    //: upload starts and not after a 50 MB request fails (audit 1028 B28).
    wbPictureCap = 50 * 1024 * 1024;

    wbInstances.on("dragover", (e) => {
      if (e.dataTransfer?.types?.includes("Files")) e.preventDefault();
    });

    wbInstances.on("drop", (e) => {
      if (!e.dataTransfer?.files?.length) return;
      e.preventDefault();
      const [x, y] = getLogicalMouse(e);
      for (const file of e.dataTransfer.files) wbPlaceUploadedImage(file, x, y);
    });

    // Paste has no drop coordinate to place at, the centre of whatever's
    // currently in view reads better than always the same fixed board
    // position, which would stack every pasted image on top of the last one.
    //: On the document, not the canvas: a paste goes to whatever has the
    //: focus, which after a click on a rail tool is not the canvas. Taken only
    //: while a board is on screen and nothing that takes typing has the focus.
    document.addEventListener("paste", (e) => {
      if (!wbCommandsLive() || wbIsEditingTarget(e.target) || e.target.closest?.("input, textarea, select, .modal-overlay, .sheet-overlay")) return;
      wbBoardState.pasteArrived = true;
      const data = e.clipboardData;
      const html = data?.getData("text/html") || "";
      if (wbClipboard?.stamp && html.includes(`content="${wbClipboard.stamp}"`)) {
        e.preventDefault();
        wbPasteClipboard();
        return;
      }
      const files = [...(data?.items || [])].filter((i) => i.kind === "file").map((i) => i.getAsFile()).filter(Boolean);
      if (files.length) {
        e.preventDefault();
        const [x, y] = wbViewCentre();
        files.forEach((file, i) => wbPlaceUploadedImage(file, x + i * WB_GRID_SPACING, y + i * WB_GRID_SPACING));
        return;
      }
      const address = wbPastedPictureAddress(data, html);
      if (address) {
        e.preventDefault();
        const [x, y] = wbViewCentre();
        wbPlacePastedAddress(address, x, y);
        return;
      }
      const text = data?.getData("text/plain") || "";
      //: A map's paste of an outline under a topic is the map's own (MINDMAP
      //: §12.2, the map half of FEAT-09); here a map keeps its own clipboard.
      if (text.trim()) {
        //: Text on a map is the map's alone: falling through to the board's own
        //: clipboard pasted a stale copy beside the outline (wbpaste-1026 sweep).
        if (wbIsMap()) return;
        e.preventDefault();
        wbPasteText(text, wbPointerOnBoard());
        return;
      }
      if (wbClipboard) {
        e.preventDefault();
        wbPasteClipboard();
      }
    });

    document.addEventListener("copy", (e) => {
      if (wbCommandsLive() && !wbIsEditingTarget(e.target) && !e.target.closest?.("input, textarea, select")) wbOnBoardCopy(e);
    });

    document.addEventListener("cut", (e) => {
      if (wbCommandsLive() && !wbIsEditingTarget(e.target) && !e.target.closest?.("input, textarea, select")) wbOnBoardCopy(e);
    });
  }

  function wbInitPictureInputs() {
    imageFileInput = document.getElementById("wb-image-file-input");

    document.getElementById("wb-add-image")?.addEventListener("click", () => imageFileInput?.click());

    //: The map topic's own picture input (§12.1 item 2's fourth), beside the
    //: board's: the same recipe, a different destination. `wbMapEditPicture`
    //: says which topic it was opened for.
    mapPictureInput = document.getElementById("wb-map-picture-input");

    mapPictureInput?.addEventListener("change", async () => {
      const file = mapPictureInput.files && mapPictureInput.files[0];
      mapPictureInput.value = "";
      await wbMapTakePicture(file);
    });

    imageFileInput?.addEventListener("change", () => {
      const [x, y] = wbViewCentre();
      for (const file of imageFileInput.files) wbPlaceUploadedImage(file, x, y);
      imageFileInput.value = "";
    });
  }

  function wbInitPointer(args) {
    ({ selectWbTool, boardEl } = args);
    wbInitDrawPointer();
    wbInitMarqueePointer();
    wbInitEdgePanPointer();
    wbInitCanvasDblclick();
    wbInitCanvasMenus();
    wbInitRightPress();
    wbInitPortHover();
    wbInitPortRelease();
    wbInitMarqueeRelease();
    wbInitLasso();
    wbInitPicturePaste();
    wbInitPictureInputs();
    return { getLogicalMouse, zoomK };
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbInitPointer });
})();
