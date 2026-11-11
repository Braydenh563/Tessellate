// diagram-canvas.js: the canvas's gestures (INBOX 1621, DOCUMENTS_PLAN 22.4 R8b). Lazy: `LAZY_MODULES.diagramCanvas`,
// registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for a flowchart, after the
// overlay (diagram-overlay.js). Three things, all on the overlay and none asking for a new picture:
//  - a palette tile or a node dropped on the picture (`over`, called by diagram-pointer.js's drop mode, which draws the
//    target on the overlay box and applies the drop to the model once);
//  - a press on a node starts that mode's drag (`node`), as a press on a block's grip does;
//  - A mouse drag on empty space is the marquee (`wire`, as the whiteboard's box select): it picks the nodes it touches through
//    the multi pane, Shift or Ctrl adds to the pick, Escape clears. The picture pans on Space and drag, the middle button, the wheel
//    and the arrows; a finger keeps its one-finger pan. Ctrl and an arrow extend the pick to the next box.
// The picture is redrawn once, after the drop, by the builder's commit.
(() => {
  const overlay = () => diagramModel.overlay.math;
  const math = {
    nodeAt: (hit, img, x, y) => overlay().at(hit, img, x, y),
    groupAt: (hit, img, x, y) => overlay().clusterAt(hit, img, x, y),
    //: The node whose centre is nearest a client point and within `within` px of it, or "" (blind test 1108: a tile dropped
    //: beside a box was added unconnected). `ok` filters the ids the model knows.
    nearest: (hit, img, x, y, within = 120, ok = () => true) => {
      let best = "";
      let far = within;
      for (const n of overlay().place(hit, img, { left: 0, top: 0 })) {
        const d = Math.hypot(n.x + n.w / 2 - x, n.y + n.h / 2 - y);
        if (d <= far && ok(n.id)) (best = n.id), (far = d);
      }
      return best;
    },
    //: The ids of the nodes a client rectangle touches (corners in any order), in drawing order.
    sweep: (hit, img, rect) => {
      const l = Math.min(rect.left, rect.right);
      const r = Math.max(rect.left, rect.right);
      const t = Math.min(rect.top, rect.bottom);
      const b = Math.max(rect.top, rect.bottom);
      return overlay()
        .place(hit, img, { left: 0, top: 0 })
        .filter((n) => n.x < r && n.x + n.w > l && n.y < b && n.y + n.h > t)
        .map((n) => n.id);
    },
    //: The new pick: the keys a marquee touched, or those added to `base` (in order, no repeats) when the press held Shift or Ctrl.
    merge: (base, hits, add) => (add ? [...base, ...hits.filter((k) => !base.includes(k))] : hits),
    //: A press is a drag, not a click, once it has moved 4 px.
    dragged: (x0, y0, x1, y1) => Math.hypot(x1 - x0, y1 - y0) >= 4,
  };

  const imageOf = (S) => S.fig.querySelector(".md-mermaid-img");
  const groupBox = (S, id) => [...S.root.querySelectorAll(".dgm-cluster")].find((b) => b.dataset.group === id) || null;
  const boxOf = (S, id) => [...S.root.querySelectorAll(".dgm-box")].find((b) => b.dataset.node === id) || null;

  //: The node under a press on the picture, for the drag seed: `{ S, id, box }`, or null (a modified press, a press off a node).
  function node(event, h) {
    const img = event.target.closest?.(".dgm-stage .md-mermaid-img");
    const S = img && h.panes.get(img.closest(".dgm"));
    if (!S || S.k || !S.hit || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return null;
    const id = math.nodeAt(S.hit, img.getBoundingClientRect(), event.clientX, event.clientY);
    const box = id && h.ops.node(S.m, id) ? boxOf(S, id) : null;
    return box ? { S, id, box } : null;
  }

  //: The drop target for a pointer over the stage, in the shape diagram-pointer.js applies: over a node, "after it" (a tile
  //: also connects from it); over empty space, the end of the top level. Null when the pointer is off the picture or on
  //: the dragged blocks themselves.
  function over(g, h) {
    const { S, key } = g;
    const stage = S.fig.parentElement;
    const at = document.elementFromPoint(g.x, g.y);
    //: A dock (the zoom bar, the shelf) over the picture is not a dead spot: every point of the stage takes a drop.
    if (!at || !stage?.contains(at)) return null;
    const img = imageOf(S);
    const id = img && S.hit ? math.nodeAt(S.hit, img.getBoundingClientRect(), g.x, g.y) : "";
    //: Over a group's box and no node: into that group (R8c). Not into a dragged group, or into one inside it.
    const cl = !id && img && S.hit ? math.groupAt(S.hit, img.getBoundingClientRect(), g.x, g.y) : "";
    if (cl && h.ops.group(S.m, cl)) {
      const held = key && S.picked?.size > 1 && S.picked.has(key) ? [...S.picked] : key ? [key] : [];
      if (held.some((p) => p[0] === "g" && h.ops.inside(S.m, cl, p.slice(2)))) return null;
      return { canvas: true, op: "into", key: h.ops.key("g", cl), group: cl, before: null, card: groupBox(S, cl), word: `Into ${h.ops.group(S.m, cl).title}` };
    }
    if (!id || !h.ops.node(S.m, id)) {
      //: Empty space: a palette tile adds there, a group lifts to the top level, a box is not moved by a drop that names nowhere (1679 slice 12).
      if (key?.[0] === "n" && !g.tile) return null;
      //: A tile on empty picture joins the box nearest the drop by rendered centres, however far (the help says so; a 120 px reach joined the
      //: selected box from beside the last one), else the selected box, else stands alone.
      const ok = (n) => Boolean(h.ops.node(S.m, n));
      const lone = !g.tile || g.tile.dataset.shape === "group";
      const near = lone || !img || !S.hit ? "" : math.nearest(S.hit, img.getBoundingClientRect(), g.x, g.y, Infinity, ok);
      const picked = S.sel?.[0] === "n" ? S.sel.slice(2) : "";
      const from = near || (picked && !lone && ok(picked) ? picked : "");
      if (!from) return { canvas: true, op: "into", group: null, before: null, card: S.fig, word: g.tile ? "Add here" : "To the top level" };
      return { canvas: true, op: "into", group: null, before: null, card: boxOf(S, from) || S.fig, word: `Add, joined from ${h.ops.node(S.m, from).text}`, from };
    }
    const target = h.ops.key("n", id);
    const set = key && S.picked?.size > 1 && S.picked.has(key) ? [...S.picked] : key ? [key] : [];
    const group = h.ops.node(S.m, id)?.group;
    if (set.some((p) => p === target || (p[0] === "g" && h.ops.inside(S.m, group, p.slice(2))))) return null;
    const sis = h.ops.sisters(S.m, target);
    const before = sis.keys.slice(sis.keys.indexOf(target) + 1).find((k) => k[0] !== "k") || null;
    return { canvas: true, op: "after", key: target, group: sis.parent, before, card: boxOf(S, id), word: `After ${h.ops.node(S.m, id).text}`, ...(g.tile && g.tile.dataset.shape !== "group" ? { from: id } : {}) };
  }

  function wire(S, h) {
    const fig = S?.fig;
    const stage = fig?.parentElement;
    const layer = fig?.querySelector(":scope > .dgm-overlay");
    if (!layer || S.k || fig.dataset.canvas) return;
    fig.dataset.canvas = "1";
    let sweep = null;
    let sweptAt = -1e3;

    const end = () => {
      sweep?.rect?.remove();
      for (const b of layer.querySelectorAll(".dgm-box.swept")) b.classList.remove("swept");
      sweep = null;
    };
    const touched = (event) => {
      const img = imageOf(S);
      return img && S.hit ? math.sweep(S.hit, img.getBoundingClientRect(), { left: sweep.x, top: sweep.y, right: event.clientX, bottom: event.clientY }) : [];
    };
    //: Space held is the hand: the zoom's pan takes the press (diagram-view.js), as the whiteboard's does.
    S.hand = false;
    const hand = (on) => ((S.hand = on), fig.classList.toggle("dgm-hand", on));
    const typing = (t) => t.isContentEditable || t.closest?.("input, textarea, select, button, .menu-wrap");
    window.addEventListener("keydown", (event) => {
      if (event.key !== " " || event.repeat || typing(event.target) || !(fig.matches(":hover") || event.target === fig)) return;
      hand(true);
      if (event.target === fig) event.preventDefault();
    });
    window.addEventListener("keyup", (event) => event.key === " " && hand(false));
    window.addEventListener("blur", () => hand(false));
    //: In the capture phase and ahead of the zoom's pan (diagram-view.js): a mouse press on empty space is not a pan. The box
    //: shows once the pointer has moved 4 px, so a plain click on empty space still lets go of the pick.
    fig.addEventListener("pointerdown", (event) => {
      const img = imageOf(S);
      if (event.button !== 0 || event.pointerType === "touch" || S.hand || event.altKey || !img || !S.hit || event.target.closest(".dock, .dgm-overlay > *, .dgm-zoom")) return;
      if (math.nodeAt(S.hit, img.getBoundingClientRect(), event.clientX, event.clientY)) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      fig.focus({ preventScroll: true });
      fig.setPointerCapture?.(event.pointerId);
      sweep = { id: event.pointerId, x: event.clientX, y: event.clientY, rect: null, add: event.shiftKey || event.ctrlKey || event.metaKey };
    }, true);
    fig.addEventListener("pointermove", (event) => {
      if (!sweep || event.pointerId !== sweep.id) return;
      if (!sweep.rect) {
        if (!math.dragged(sweep.x, sweep.y, event.clientX, event.clientY)) return;
        sweep.rect = document.createElement("span");
        sweep.rect.className = "dgm-marquee";
        layer.append(sweep.rect);
      }
      const home = layer.getBoundingClientRect();
      const [l, r] = [sweep.x, event.clientX].sort((a, b) => a - b);
      const [t, b] = [sweep.y, event.clientY].sort((a, b) => a - b);
      Object.assign(sweep.rect.style, { left: `${l - home.left}px`, top: `${t - home.top}px`, width: `${r - l}px`, height: `${b - t}px` });
      const ids = new Set(touched(event));
      for (const box of layer.querySelectorAll(".dgm-box")) box.classList.toggle("swept", ids.has(box.dataset.node));
    });
    fig.addEventListener("pointerup", (event) => {
      if (!sweep || event.pointerId !== sweep.id) return;
      const { rect, add } = sweep;
      if (rect) sweptAt = event.timeStamp;
      const hits = rect ? touched(event).map((id) => h.ops.key("n", id)) : null;
      end();
      //: Not dragged: the click that follows decides (it clears the pick on empty space).
      if (!hits) return;
      const base = add ? (S.picked?.size ? [...S.picked] : S.sel ? [S.sel] : []) : [];
      const keys = math.merge(base, hits, add);
      if (keys.length) S.pick?.(keys, hits[0] || keys[0]);
      else S.clear();
    });
    fig.addEventListener("pointercancel", end);
    window.addEventListener("keydown", (event) => {
      if (sweep && event.key === "Escape") end();
    });

    //: Nothing picked (INBOX 1661 h): a press on empty canvas or empty list, and Escape, let go of the pick, so the list, the
    //: boxes and the handles read as no selection. An armed handle goes back first. True when something changed.
    S.clear = () => {
      if (S.cancelArm?.()) return true;
      if (!S.sel && !S.picked?.size) return false;
      S.pick ? S.pick([], null) : (S.sel = null);
      h.stops(S, S.tree.querySelector(".dgm-block"));
      S.mark?.();
      S.handles?.();
      return true;
    };
    fig.addEventListener("click", (event) => {
      const img = imageOf(S);
      //: A marquee ends in a click on the figure; a pan's click is swallowed by the zoom (diagram-view.js).
      if (!img || !S.hit || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey || event.timeStamp - sweptAt < 400 || event.target.closest(".dock, .dgm-overlay > *, .dgm-zoom")) return;
      const at = img.getBoundingClientRect();
      if (math.nodeAt(S.hit, at, event.clientX, event.clientY) || overlay().clusterEdgeAt(S.hit, at, event.clientX, event.clientY) || diagramModel.edges?.math.edgeAt(S.hit, at, event.clientX, event.clientY)) return;
      S.clear();
    });
    S.pane.addEventListener("click", (event) => event.target.closest(".dgm-block, button, a, input, label") || S.clear());
    //: Ctrl or Cmd and an arrow on the picture adds the box in that direction to the pick (the arrows alone move the pick).
    fig.addEventListener("keydown", (event) => {
      const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (!dir || event.target !== fig || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || !S.hit?.boxes?.length || !S.pick) return;
      const from = S.sel?.startsWith("n:") ? S.sel.slice(2) : "";
      const to = diagramModel.view.math.reach(S.hit.boxes, from, ...dir);
      event.preventDefault();
      if (!to || !h.ops.node(S.m, to.id)) return;
      const base = S.picked?.size ? [...S.picked] : S.sel ? [S.sel] : [];
      S.pick(math.merge(base, [h.ops.key("n", to.id)], true), h.ops.key("n", to.id));
      S.mark?.();
    });
    S.root.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || event.defaultPrevented || event.target.closest?.("input, textarea, [contenteditable]") || document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden)")) return;
      if (S.clear()) event.preventDefault(), event.stopPropagation();
    });
  }

  diagramModel.canvas = { wire, over, node, math };
})();
