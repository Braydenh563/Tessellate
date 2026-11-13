(() => {
  // whiteboard-shapes-js.js: Insert, Polygon (click the corners, double-click or Enter to close, Escape to cancel) and the
  // JS-drawn shape classes (WHITEBOARD_PLAN section 11). Held on `wbFmtState.shapesJs`, so no new global name is added.

  // --- Insert, Polygon -------------------------------------------------------------------------------------
  const NS = "http://www.w3.org/2000/svg";
  const MIN_STEP = 3; // board units: a double-click's two presses are one corner
  const poly = { on: false, pts: [], el: null, cursor: null };
  // The pen width lives in a closure of whiteboard.js, so it is read from its slider.
  const penWidth = () => Number(document.getElementById("wb-stroke-width")?.value) || 3;

  //: Pure (node-tested): the points as one closed `d`, a corner dropped when it sits on the one before it.
  function polygonD(points) {
    const kept = [];
    for (const p of points || []) {
      const last = kept[kept.length - 1];
      if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) >= MIN_STEP) kept.push([p[0], p[1]]);
    }
    if (kept.length > 1 && Math.hypot(kept[0][0] - kept[kept.length - 1][0], kept[0][1] - kept[kept.length - 1][1]) < MIN_STEP) kept.pop();
    if (kept.length < 3) return null;
    const r = (n) => Math.round(n * 100) / 100;
    return `M ${kept.map((p) => `${r(p[0])} ${r(p[1])}`).join(" L ")} Z`;
  }

  function paint() {
    if (!poly.el) return;
    const live = poly.cursor ? [...poly.pts, poly.cursor] : poly.pts;
    poly.el.setAttribute("d", live.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" "));
  }

  const onDown = (event) => {
    if (event.button) return;
    if (window.currentTool !== "select") return polygonCancel();
    event.preventDefault();
    event.stopPropagation();
    poly.pts.push(wbClientToBoard(event.clientX, event.clientY));
    poly.cursor = null;
    paint();
    wbAnnounce(`${poly.pts.length} corner${poly.pts.length === 1 ? "" : "s"}. Double-click or press Enter to close the shape, Escape to cancel.`);
  };
  const onMove = (event) => {
    poly.cursor = wbClientToBoard(event.clientX, event.clientY);
    paint();
  };
  const onDouble = (event) => {
    event.preventDefault();
    event.stopPropagation();
    polygonClose();
  };
  const onKey = (event) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); polygonCancel(); }
    else if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); polygonClose(); }
    else if (event.key === "Backspace" && poly.pts.length) { event.preventDefault(); event.stopPropagation(); poly.pts.pop(); paint(); }
  };

  function polygonStart() {
    if (poly.on) return;
    const container = document.getElementById("whiteboard-container");
    const group = document.getElementById("wb-overlay-zoom-group");
    if (!container || !group) return;
    wbSelectToolRef?.("select");
    clearWbSelection();
    poly.on = true;
    poly.pts = [];
    poly.cursor = null;
    poly.el = document.createElementNS(NS, "path");
    poly.el.setAttribute("fill", "none");
    poly.el.setAttribute("stroke", window.currentStrokeColor || "#4f8cff");
    poly.el.setAttribute("stroke-width", String(penWidth()));
    poly.el.setAttribute("stroke-dasharray", "6 4");
    poly.el.setAttribute("pointer-events", "none");
    group.appendChild(poly.el);
    container.classList.add("wb-polygon-on");
    container.addEventListener("pointerdown", onDown, true);
    container.addEventListener("pointermove", onMove, true);
    container.addEventListener("dblclick", onDouble, true);
    document.addEventListener("keydown", onKey, true);
    wbAnnounce("Polygon: click each corner, then double-click or press Enter to close it. Escape cancels.");
  }

  function polygonEnd() {
    const container = document.getElementById("whiteboard-container");
    container?.classList.remove("wb-polygon-on");
    container?.removeEventListener("pointerdown", onDown, true);
    container?.removeEventListener("pointermove", onMove, true);
    container?.removeEventListener("dblclick", onDouble, true);
    document.removeEventListener("keydown", onKey, true);
    poly.el?.remove();
    poly.el = null;
    poly.on = false;
    poly.pts = [];
    poly.cursor = null;
  }

  function polygonCancel() {
    if (!poly.on) return;
    polygonEnd();
    wbAnnounce("Polygon cancelled.");
  }

  //: Writes the closed `d` as one shape (one Undo step; its corner ports come from `wbPortsForPath`) and selects it.
  async function polygonClose() {
    if (!poly.on) return null;
    const d = polygonD(poly.pts);
    polygonEnd();
    if (!d) { wbAnnounce("A polygon needs three corners."); return null; }
    const blob = { d, color: window.currentStrokeColor, width: penWidth(), shape: "custom" };
    if (window.currentDashStyle && window.currentDashStyle !== "solid") blob.dash = window.currentDashStyle;
    if (window.currentStrokeNone) blob.noStroke = true;
    if (!window.currentFillNone) {
      blob.fill = window.currentFillColor;
      blob.fillOpacity = window.currentFillOpacity / 100;
    }
    const data = wbFmtState.board?.withDefaults("shape", blob, { fillable: true }) ?? blob;
    try {
      const res = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId }),
      });
      wbState.sketches.push(res);
      wbPushUndo({ action: "create", kind: "sketch", id: res.id });
      renderWhiteboardNow();
      selectWbItem("sketch", res.id);
      wbAnnounce("Polygon added.");
      return res;
    } catch (err) {
      toast(voiceLine("failed", { what: "save that shape", why: err.message }), true);
      return null;
    }
  }

  wbFmtState.shapesJs = { polygonD, polygonStart, polygonClose, polygonCancel };
})();
