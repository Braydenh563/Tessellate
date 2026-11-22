(() => {
  // Pen strokes: the pointer handlers that draw, finish and abandon a stroke, carved from initWhiteboard (L634).
  // Wrapped: initWhiteboard calls it once, passing the names it shares; nothing here runs at load.
  function wbInitStrokes({ wbPen, getLogicalMouse, zoomK }) {
    // On the container, not `svgCanvas`, the same reasoning the eraser
    // listener above already follows. `svgCanvas` only ever sees a
    // pointerdown that lands directly on it or on something inside it; a
    // click that starts on a card (`#wb-html-layer`, a sibling painted on
    // top) never reaches it at all, which is the exact mechanism behind
    // "drawing over a note just moves the note". the container is an
    // ancestor of both layers, so it sees every pointerdown either way, 
    // and, with the card/object drags above now filtered out while a brush
    // tool is active, nothing else claims the gesture first.
    wbInstances.on("pointerdown", (e) => {
      if (!WB_BRUSH_TOOLS.has(window.currentTool)) return;
      e.stopPropagation();
      wbPen.drawing = true;
      const [x, y] = getLogicalMouse(e);
      
      wbPen.data = [[x, y, e.pressure]];
      wbPen.path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      // Fill only applies to the four closed shapes, and only when "no fill"
      // isn't checked: asked for directly ("fill colour/transparency...
      // options for no border/stroke or background").
      if ((WB_FILLABLE_SHAPES.has(window.currentTool) || WB_MORE_SHAPES[window.currentTool]) && !window.currentFillNone) {
        wbPen.path.setAttribute("fill", window.currentFillColor);
        wbPen.path.setAttribute("fill-opacity", String(window.currentFillOpacity / 100));
      } else {
        wbPen.path.setAttribute("fill", "none");
      }
      wbPen.path.setAttribute("stroke", window.currentStrokeNone ? "none" : window.currentStrokeColor);
      // A highlighter needs to be visibly wider and translucent, or it isn't a
      // highlighter: the sketch pad's own version of this exact control had
      // its opacity so low it was reported as invisible (HISTORY.md §46).
      wbPen.path.setAttribute(
        "stroke-width",
        String(window.currentTool === "highlighter" ? wbHighlighterWidth(wbPen.width) : wbPen.width)
      );
      if (window.currentTool === "highlighter") {
        wbPen.path.setAttribute("stroke-opacity", String(WB_HIGHLIGHTER_ALPHA));
        wbPen.path.setAttribute("stroke-linecap", HIGHLIGHTER_STYLE.lineCap);
        // An inline style, not a class: the export clones these elements into a
        // standalone SVG where a stylesheet does not follow them, and
        // `el.style.x = ...` is the form this app's CSP allows (an inline
        // `style=` attribute in the markup is refused). The class beside it is
        // only a handle for `wbRefreshHighlighterBlend`.
        wbPen.path.classList.add("wb-live-highlighter");
        wbPen.path.style.mixBlendMode = wbHighlighterBlend();
      } else {
        wbPen.path.setAttribute("stroke-linecap", "round");
      }
      wbPen.path.setAttribute("stroke-linejoin", HIGHLIGHTER_STYLE.lineJoin);
      const dashArray = wbDashArray(window.currentDashStyle, wbPen.width);
      if (dashArray) wbPen.path.setAttribute("stroke-dasharray", dashArray);
      wbPen.path.setAttribute("d", `M ${x} ${y}`);
      //: A solid pen or marker stroke is smoothed ink (whiteboard-ink-more.js): filled, its width following pressure.
      if ((window.currentTool === "draw" || window.currentTool === "highlighter") && wbFmtState.inkMore?.takesInk(window.currentDashStyle)) {
        wbPen.path.__ink = { pointer: e.pointerType };
        wbFmtState.inkMore.liveStyle(wbPen.path, window.currentStrokeNone ? "none" : window.currentStrokeColor, window.currentTool === "highlighter" ? WB_HIGHLIGHTER_ALPHA : null);
      }
      //: Over the cards while it is drawn: it lands on top (decision 43).
      wbInstances.layer("wb-overlay-zoom-group").appendChild(wbPen.path);
    });
    
    //: The live stroke's outline when it is smoothed ink, "" when it is a plain stroke.
    function wbInkLiveD(last) {
      const ink = wbPen.path?.__ink;
      if (!ink) return "";
      const tool = window.currentTool;
      const width = tool === "highlighter" ? wbHighlighterWidth(wbPen.width) : wbPen.width;
      return wbFmtState.inkMore.outline(wbPen.data, tool, width, ink.pointer, last);
    }
    wbInstances.on("pointermove", (e) => {
      if (!wbPen.drawing || !WB_BRUSH_TOOLS.has(window.currentTool)) return;
      e.stopPropagation();
      let [x, y] = getLogicalMouse(e);
      const tool = window.currentTool;
      if (tool !== "draw" && tool !== "highlighter" && tool !== "line" && tool !== "arrow") {
        [x, y] = wbDrawOutSnap(wbPen.data[0][0], wbPen.data[0][1], x, y, e);
      }
      
      if (window.currentTool === "draw" || window.currentTool === "highlighter") {
        // **Shift draws a straight run** (decision 7). Held mid-stroke it
        // replaces whatever has been drawn since the start point with one
        // segment, and letting go carries on freehand from there, which is how
        // a straightedge behaves and how every app that offers this does it.
        // The pen as well as the highlighter (INBOX 1352 gap 4).
        if (e.shiftKey) {
          const [sx0, sy0] = wbPen.data[0];
          wbPen.data.length = 1;
          wbPen.data.push([x, y, e.pressure]);
          wbPen.path.setAttribute("d", wbInkLiveD(false) || `M ${sx0} ${sy0} L ${x} ${y}`);
          return;
        }
        wbPen.data.push([x, y, e.pressure]);
        const d = wbInkLiveD(false) || wbPen.data.map((pt, i) => (i === 0 ? `M ${pt[0]} ${pt[1]}` : `L ${pt[0]} ${pt[1]}`)).join(" ");
        wbPen.path.setAttribute("d", d);
      } else {
        // Shape tools: only start and current point matter
        const [sx, sy] = wbPen.data[0];
        if (window.currentTool === "line" || window.currentTool === "arrow") {
          // One path, one or more subpaths, a plain SVG `d` string can hold
          // more than one `M`, and every subpath in it shares the same
          // stroke, so this is the shaft plus whichever head strokes the
          // *active tool's own* end-style calls for in a single element,
          // rather than several sketches that would each need their own undo
          // entry and could drift apart. Asked for directly: "regular lines
          // should also get line end options... arrow heads", the Line and
          // Arrow tools share the same "Line ends" control, so a plain line
          // *can* carry an arrowhead, but each tool keeps its own remembered
          // default (Line: none, Arrow: end): see the live-reported bug fix
          // on `currentLineEndStyle`/`currentArrowEndStyle` in `initWhiteboard`.
          const caps = wbToolCaps();
          const [ex, ey] = e.shiftKey ? wbSnap45(sx, sy, x, y) : [x, y];
          const liveHead = wbPen.width * 4 + 6;
          const liveD = wbRegenerateShapeCaps(`M ${sx} ${sy} L ${ex} ${ey}`, caps.startCap, caps.endCap, liveHead);
          wbPen.path.setAttribute("d", wbFmtState.inkMore?.trimShaft(liveD, caps.startCap, caps.endCap, liveHead, null, wbShaftEnd) || liveD);
        } else if (window.currentTool === "circle") {
          wbPen.path.setAttribute("d", wbEllipseDrawD(sx, sy, x, y, e));
        } else {
          const d = wbClosedShapeD(window.currentTool, wbDragBox(sx, sy, x, y, e));
          if (d) wbPen.path.setAttribute("d", d);
        }
      }
    });
    
    //: A stroke whose gesture is taken away (a tool switch, the browser's pointercancel, a release
    //: outside the board, which the container's own pointerup never hears) is dropped, not left
    //: as a live path with `isDrawing` still true (sm-1111 row 27).
    function wbAbandonStroke() {
      if (!wbPen.drawing) return;
      wbPen.drawing = false;
      wbPen.path?.remove();
      wbPen.path = null;
      wbPen.data = [];
      wbClearAlignmentGuides();
    }
    //: **A drag whose pointer is taken away is put back and let go** (sm-1111 row 27; this is the
    //: card, object, shape and link drags' half of `wbAbandonStroke`). A pointercancel, a window
    //: blur, a tool switch or a mouse move with no button held (the `mouseup` went to a native drag,
    //: another window or the OS) all mean the hand is gone. Measured before in Chromium, a card and a
    //: text box with a lost `mouseup`: the gesture stayed live, the item followed a buttonless hover
    //: and the delete target stayed up. d3-drag lets go of its window listeners only on `mouseup`,
    //: so one is sent after the cancel; the cancelled gesture's own handlers then save nothing.
    function wbDropLostGesture() {
      if (!wbCancelGesture()) return;
      window.dispatchEvent(new MouseEvent("mouseup", { view: window }));
    }
    window.addEventListener("pointercancel", wbDropLostGesture, true);
    window.addEventListener("blur", wbDropLostGesture);
    window.addEventListener("pointermove", (e) => {
      if (wbGesture && e.pointerType === "mouse" && e.buttons === 0) wbDropLostGesture();
    }, true);
    window.addEventListener("pointercancel", wbAbandonStroke);
    window.addEventListener("pointerup", wbAbandonStroke);
    wbInstances.on("pointerup", async (e) => {
      if (!wbPen.drawing || !WB_BRUSH_TOOLS.has(window.currentTool)) return;
      e.stopPropagation();
      wbPen.drawing = false;
      wbClearAlignmentGuides();
      
      const [x, y] = getLogicalMouse(e);
      const [sx, sy] = wbPen.data[0];
      
      // A plain click with no drag, reported directly: the pen tool "doesn't
      // respond to a single click, only a drag", which the sketch pad's own
      // pen never had wrong (see `sketchEnd`'s own `!sketchMoved` branch, the
      // same fix mirrored here). A `moveto` with no `lineto` after it draws
      // nothing at all, so a stationary click has to add a near-zero-length
      // segment, round linecaps turn that into a visible dot, rather than
      // being discarded as "no shape to save".
      const isFreehand = window.currentTool === "draw" || window.currentTool === "highlighter";
      if (isFreehand && wbPen.data.length < 2) {
        wbPen.path.setAttribute("d", wbInkLiveD(true) || `M ${sx} ${sy} L ${sx} ${sy + 0.1}`);
      } else if (isFreehand) {
        const settled = wbInkLiveD(true);
        if (settled) wbPen.path.setAttribute("d", settled);
      } else if (!isFreehand && Math.abs(x - sx) < 2 && Math.abs(y - sy) < 2) {
        // Shape tools (line/arrow/rect/circle) need an actual drag to have a
        // size: a zero-size shape isn't a reasonable click-to-draw default
        // the way a pen dot is, so these are still discarded.
        if (wbPen.path) wbPen.path.remove();
        wbPen.path = null;
        return;
      }
      
      // Save sketch to API. The backend schema has no width/opacity/fill/dash
      // columns, so all of it has to travel inside `data`, otherwise a saved
      // stroke reloads at the hardcoded 3px default regardless of what
      // #wb-stroke-width was actually set to when it was drawn (a real bug,
      // caught while wiring that control up: only the highlighter branch here
      // ever saved its own width; a plain pen/line/shape stroke silently lost
      // whatever size it was actually drawn at the moment the page reloaded).
      const d = wbPen.path.getAttribute("d");
      const isHighlighter = window.currentTool === "highlighter";
      const more = WB_MORE_SHAPES[window.currentTool];
      const isFillable = WB_FILLABLE_SHAPES.has(window.currentTool) || Boolean(more);
      const blob = {
        d,
        color: currentStrokeColor,
        width: isHighlighter ? wbHighlighterWidth(wbPen.width) : wbPen.width,
        shape: more ? "custom" : window.currentTool,
      };
      if (more?.area) blob.label_area = more.area;
      if (wbPen.path.__ink) Object.assign(blob, { ink: 1 }, wbFmtState.inkMore.keepPoints(wbPen.data, wbPathBBox(d)));
      //: The ends are stored by kind, so the bar and the Format panel read
      //: what was drawn rather than sniffing it out of the path.
      if (window.currentTool === "line" || window.currentTool === "arrow") Object.assign(blob, wbToolCaps());
      if (isHighlighter) {
        blob.opacity = WB_HIGHLIGHTER_ALPHA;
      } else {
        if (window.currentDashStyle !== "solid") blob.dash = window.currentDashStyle;
        if (window.currentStrokeNone) blob.noStroke = true;
        if (isFillable && !window.currentFillNone) {
          blob.fill = window.currentFillColor;
          blob.fillOpacity = window.currentFillOpacity / 100;
        }
      }
      //: An arrow or a line that starts or ends on a shape is a connector bound
      //: to it (the wb ledger, 10-25: the Line tool stayed a loose path). Its
      //: ends are the tool's own, so a line binds with none.
      const bound = window.currentTool === "arrow" || window.currentTool === "line" ? wbBoundArrowData(sx, sy, x, y, 10 / zoomK(), blob) : null;
      //: The board's default style starts every drawn shape, line, pen stroke and highlighter stroke, each under its own kind.
      const group = isFreehand ? (isHighlighter ? "highlighter" : "pen") : "shape";
      const drawn = wbFmtState.board?.withDefaults(group, blob, { fillable: isFillable }) ?? blob;
      const sketchData = {
        data: JSON.stringify(bound || drawn),
        x: 0,
        y: 0,
        z: wbStackNewZ("sketch"),
        board_id: window.currentBoardId
      };

      try {
        const res = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify(sketchData) });
        wbState.sketches.push(res);
        wbPushUndo({ action: "create", kind: "sketch", id: res.id });
        // Hand off to renderWhiteboard's own data-bound element for this
        // sketch: a real bug found while adding the eraser: this raw `<path>`
        // is not part of the `g.sketch-group` selection renderWhiteboard binds
        // wbState.sketches to, so a stroke just drawn had no way to be deleted
        // or erased until a full reload re-fetched it from the server and
        // rendered it "properly" the first time.
        wbPen.path.remove();
        //: A drawn shape is selected and the tool returns to Select (decision
        //: 44); the pen and highlighter keep their tool so strokes continue.
        if (!isFreehand) {
          renderWhiteboardNow();
          wbSelectToolRef?.("select");
          selectWbItem("sketch", res.id);
        } else {
          wbScheduleRender();
        }
      } catch (err) {
        //: Said on screen, not only in a console nobody has open (audit 1028 B22).
        toast(voiceLine("failed", "save that drawing", err.message), true);
        if (wbPen.path) wbPen.path.remove();
      }

      wbPen.path = null;
      wbPen.data = [];
    });

    wbPen.abandon = wbAbandonStroke;
    wbPen.dropLost = wbDropLostGesture;
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbInitStrokes });
})();
