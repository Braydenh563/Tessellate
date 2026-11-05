// diagram-edge-pick.js: the picture answers to more than a double click (INBOX 1679, slices 3 and 4). Lazy:
// `LAZY_MODULES.diagramEdgePick`, registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's
// `show` for a flowchart, after the edges (diagram-edges.js, whose rename it opens). On the picture:
//  - a right-click or a long press opens the block's menu on a box and the connector's menu on an arrow, the same rows the
//    list opens;
//  - a click within 8 px of an arrow's drawn path picks it: a 2 px accent line over it (`.dgm-edge-on`), Enter opens its
//    words, Delete removes it (one undo step), Escape lets go. The old 16 px disc round the midpoint stays for the double click.
(() => {
  const REACH = 8;
  const NS = "http://www.w3.org/2000/svg";
  const math = {
    //: The distance from a point to a polyline (points as `[x, y]`), in the points' own units.
    near: (pts, x, y) => {
      let best = Infinity;
      for (let i = 0; i < pts.length; i++) {
        const [ax, ay] = pts[i];
        const [bx, by] = pts[i + 1] || pts[i];
        const len = (bx - ax) ** 2 + (by - ay) ** 2;
        const t = len ? Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / len)) : 0;
        best = Math.min(best, Math.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay)));
      }
      return best;
    },
    //: The arrow whose drawn path passes within `reach` client pixels of a point, or "": the nearest of them.
    at: (hit, img, px, py, reach = REACH) => {
      if (!hit?.edges || !img.width || !img.height) return "";
      const [vx, vy, vw, vh] = hit.vb;
      const sx = img.width / vw;
      const sy = img.height / vh;
      let best = "";
      let far = reach;
      for (const e of hit.edges) {
        const d = math.near((e.pts || []).map(([x, y]) => [img.left + (x - vx) * sx, img.top + (y - vy) * sy]), px, py);
        if (d <= far) (far = d), (best = e.id);
      }
      return best;
    },
    //: How far to push two handle centres from each other so they sit at least `gap` apart: a short arrow on a phone would stack its two
    //: 44 px handles (1679, slice 4 review). Along the line between them, or sideways when they coincide. Two `[dx, dy]` offsets.
    apart: (a, b, gap) => {
      const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (d >= gap) return [[0, 0], [0, 0]];
      const [ux, uy] = d ? [(b[0] - a[0]) / d, (b[1] - a[1]) / d] : [1, 0];
      const k = (gap - d) / 2;
      return [[-ux * k, -uy * k], [ux * k, uy * k]];
    },
    //: Moves one end (`"from"` or `"to"`) of an arrow to the block or group `to`, keeping its words, line and arrow. The new arrow is
    //: joined before the old one is taken out, so a refusal leaves the old one where it was. The new arrow, or why not.
    reconnect: (ops, m, edge, end, to) => {
      if (to === edge[end]) return "same";
      const [from, dest] = end === "from" ? [to, edge.to] : [edge.from, to];
      if (from === dest) return "self";
      const next = ops.join(m, from, dest, { label: edge.label, style: edge.style, arrow: edge.arrow });
      return next ? (ops.unjoin(m, edge), next) : "twin";
    },
  };

  function wire(S, h) {
    const fig = S?.fig;
    const layer = fig?.parentElement?.querySelector(".dgm-overlay");
    if (!layer || S.k || fig.dataset.pick) return;
    fig.dataset.pick = "1";
    const overlay = diagramModel.overlay.math;
    const edgeId = diagramModel.edges.math.edgeId;
    const img = () => fig.querySelector(".md-mermaid-img");
    const rect = () => img()?.getBoundingClientRect();
    const nodeAt = (x, y) => (S.hit && rect() ? overlay.at(S.hit, rect(), x, y) : "");
    const arrowAt = (x, y) => (S.hit && rect() ? math.at(S.hit, rect(), x, y) : "");
    const edgeOf = (id) => S.m.edges.find((e) => edgeId(S.m, e) === id);
    const nameOf = (id) => h.ops.node(S.m, id)?.text || h.ops.group(S.m, id)?.title || id;

    //: The picked arrow's line: the drawn path itself, scaled onto the overlay, so a curve is followed and not approximated.
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "dgm-edge-svg");
    svg.setAttribute("aria-hidden", "true");
    const line = document.createElementNS(NS, "path");
    line.setAttribute("class", "dgm-edge-on");
    svg.append(line);
    layer.append(svg);
    //: The two ends of the picked arrow, a dot each: drag one to another block or a group to move that end there (slice 4).
    const ends = ["from", "to"].map((end) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "dgm-end hidden";
      dot.dataset.end = end;
      dot.tabIndex = -1;
      dot.setAttribute("aria-label", `Drag to move the ${end === "from" ? "start" : "end"} of this connector to another block`);
      layer.append(dot);
      return dot;
    });
    //: The picked arrow's Mermaid id (`L_<from>_<to>_<n>`): looked up again on every draw, since an undo rebuilds the model.
    let picked = "";

    const draw = () => {
      const mine = picked && S.hit?.edges?.find((e) => e.id === picked);
      const r = rect();
      if (!mine || !r || !edgeOf(picked)) return line.removeAttribute("d"), ends.forEach((dot) => dot.classList.add("hidden"));
      const home = layer.getBoundingClientRect();
      const [vx, vy, vw, vh] = S.hit.vb;
      const sx = r.width / vw;
      const sy = r.height / vh;
      const spot = (pt) => [r.left - home.left + (pt[0] - vx) * sx, r.top - home.top + (pt[1] - vy) * sy];
      const here = [mine.pts[0], mine.pts[mine.pts.length - 1]].map(spot);
      //: A touch handle is 44 px: two ends closer than that are pushed apart so each can be taken.
      const off = math.apart(here[0], here[1], matchMedia("(pointer: coarse)").matches ? 48 : 0);
      ends.forEach((dot, i) => ((dot.style.transform = `translate(${here[i][0] + off[i][0]}px, ${here[i][1] + off[i][1]}px)`), dot.classList.remove("hidden")));
      line.setAttribute("d", mine.d);
      line.setAttribute("transform", `matrix(${sx} 0 0 ${sy} ${r.left - home.left - vx * sx} ${r.top - home.top - vy * sy})`);
    };
    const pick = (id) => {
      picked = id;
      draw();
      const edge = id && edgeOf(id);
      if (edge) h.say(S, `Connector from ${nameOf(edge.from)} to ${nameOf(edge.to)} picked. Enter changes its words, Delete removes it.`);
    };
    (fig.onpaint ||= []).push(draw);
    (fig.onzoom ||= []).push(draw);
    fig.addEventListener("scroll", draw, { passive: true });
    fig.addEventListener("load", draw, true);
    //: A click anywhere in the pane but on the picture lets go (the list, its bar).
    S.root.addEventListener("click", (event) => picked && !fig.contains(event.target) && !event.target.closest?.(".dgm-end") && pick(""));

    fig.addEventListener("click", (event) => {
      if (!S.hit || !rect() || event.target.closest(".dock, .dgm-handle, .dgm-rename")) return;
      pick(nodeAt(event.clientX, event.clientY) ? "" : arrowAt(event.clientX, event.clientY));
    });

    //: The menu for what is under a point: a box (the list's rows), an arrow (the connector's rows), or nothing (the browser's).
    async function menu(event, x, y) {
      if (!S.hit || !rect() || event.target.closest?.(".dock, .dgm-handle, .dgm-rename")) return;
      const node = nodeAt(x, y);
      const id = !node && arrowAt(x, y);
      if (node) {
        const key = h.ops.key("n", node);
        h.select(S, key);
        openMenuAtPoint(h.items(S, key), "Block menu", x, y, fig);
      } else if (id && (await ensureModule("diagramJoins"))) {
        pick(id);
        const edge = edgeOf(id);
        if (edge) openMenuAtPoint(diagramModel.joins.items(S, edge, h), "Connector menu", x, y, fig);
      } else return;
      event.preventDefault?.();
    }
    fig.addEventListener("contextmenu", (event) => {
      //: Decided before the module call can answer: the browser's own menu is cancelled for a box or an arrow only.
      if (nodeAt(event.clientX, event.clientY) || arrowAt(event.clientX, event.clientY)) event.preventDefault();
      //: A long press on a phone sends this too, after `wireLongPress` has opened the menu: the finger's is that one.
      if (event.pointerType !== "touch") menu(event, event.clientX, event.clientY);
    });
    wireLongPress(fig, (event, point) => menu(event, point.x, point.y));

    let drag = null;
    const targetAt = (x, y) => nodeAt(x, y) || (S.hit && rect() ? overlay.clusterAt(S.hit, rect(), x, y) : "");
    //: The block or group a drop would land on takes the accent outline (`dgm-target`, as the connect drag does).
    const mark = (id) => {
      for (const box of layer.querySelectorAll(".dgm-box")) box.classList.toggle("dgm-target", Boolean(id) && (box.dataset.node || box.dataset.group) === id);
    };
    //: A function of its own, so the loop below holds no write that its move handler's reads would follow (test_css_invalidation).
    const hold = (dot, on) => dot.classList.toggle("dgm-held", on);
    const drop = () => ((drag = null), mark(""), ends.forEach((dot) => hold(dot, false)), draw());
    for (const dot of ends) {
      dot.addEventListener("pointerdown", (event) => {
        if (event.button) return;
        event.preventDefault();
        dot.setPointerCapture?.(event.pointerId);
        drag = { end: dot.dataset.end, id: event.pointerId };
        //: Held, the handle shrinks to its 12 px dot (the finger covers the 44 px one over the block it aims at).
        hold(dot, true);
      });
      dot.addEventListener("pointermove", (event) => {
        if (!drag || event.pointerId !== drag.id) return;
        const home = layer.getBoundingClientRect();
        const to = targetAt(event.clientX, event.clientY);
        mark(to);
        dot.style.transform = `translate(${event.clientX - home.left}px, ${event.clientY - home.top}px)`;
      });
      dot.addEventListener("pointerup", (event) => {
        if (!drag || event.pointerId !== drag.id) return;
        const { end } = drag;
        const to = targetAt(event.clientX, event.clientY);
        const edge = edgeOf(picked);
        drop();
        if (!edge || !to) return;
        const next = math.reconnect(h.ops, S.m, edge, end, to);
        if (next === "twin") return h.say(S, `${nameOf(end === "from" ? to : edge.from)} is already connected to ${nameOf(end === "from" ? edge.to : to)}.`);
        if (next === "self") return h.say(S, "A block cannot connect to itself.");
        if (next === "same") return;
        picked = "";
        h.commit(S, `Moved the connector: ${nameOf(next.from)} to ${nameOf(next.to)}.`);
      });
      dot.addEventListener("pointercancel", drop);
    }
    //: Escape in the middle of a drag puts the end back and leaves the arrow picked. Captured and stopped, so the builder's own
    //: Escape (close without keeping) never sees it, and the release that follows finds no drag to commit. It goes with the picture.
    const escape = (event) => {
      if (!fig.isConnected) return window.removeEventListener("keydown", escape, true);
      if (event.key !== "Escape" || !drag) return;
      event.stopPropagation();
      event.preventDefault();
      drop();
    };
    window.addEventListener("keydown", escape, true);

    fig.addEventListener("keydown", (event) => {
      const edge = picked && edgeOf(picked);
      if (!edge || drag || event.target !== fig || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "Escape") pick("");
      else if (event.key === "Enter") S.renameEdge?.(edge);
      else if (event.key === "Delete" || event.key === "Backspace") {
        h.ops.unjoin(S.m, edge);
        picked = "";
        h.commit(S, `Removed the connector to ${nameOf(edge.to)}.`);
      } else return;
      event.preventDefault();
    });
  }

  diagramModel.edgepick = { wire, math };
})();
