// diagram-canvas.js: the canvas's gestures (INBOX 1621, DOCUMENTS_PLAN 22.4 R8b). Lazy: `LAZY_MODULES.diagramCanvas`,
// registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for a flowchart, after the
// overlay (diagram-overlay.js). Three things, all on the overlay and none asking for a new picture:
//  - a palette tile or a node dropped on the picture (`over`, called by diagram-pointer.js's drop mode, which draws the
//    target on the overlay box and applies the drop to the model once);
//  - a press on a node starts that mode's drag (`node`), as a press on a block's grip does;
//  - Shift and drag on empty space is the marquee (`wire`): it picks the nodes it touches through the multi pane.
// The picture is redrawn once, after the drop, by the builder's commit.
(() => {
  const overlay = () => diagramModel.overlay.math;
  const math = {
    nodeAt: (hit, img, x, y) => overlay().at(hit, img, x, y),
    groupAt: (hit, img, x, y) => overlay().clusterAt(hit, img, x, y),
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
    if (!at || !stage?.contains(at) || at.closest(".dock")) return null;
    const layer = stage.querySelector(".dgm-overlay");
    const img = imageOf(S);
    const id = img && S.hit ? math.nodeAt(S.hit, img.getBoundingClientRect(), g.x, g.y) : "";
    //: Over a group's box and no node: into that group (R8c). Not into a dragged group, or into one inside it.
    const cl = !id && img && S.hit ? math.groupAt(S.hit, img.getBoundingClientRect(), g.x, g.y) : "";
    if (cl && h.ops.group(S.m, cl)) {
      const held = key && S.picked?.size > 1 && S.picked.has(key) ? [...S.picked] : key ? [key] : [];
      if (held.some((p) => p[0] === "g" && h.ops.inside(S.m, cl, p.slice(2)))) return null;
      return { canvas: true, op: "into", key: h.ops.key("g", cl), group: cl, before: null, card: groupBox(S, cl) };
    }
    if (!id || !h.ops.node(S.m, id)) return { canvas: true, op: "into", group: null, before: null, card: layer };
    const target = h.ops.key("n", id);
    const set = key && S.picked?.size > 1 && S.picked.has(key) ? [...S.picked] : key ? [key] : [];
    const group = h.ops.node(S.m, id)?.group;
    if (set.some((p) => p === target || (p[0] === "g" && h.ops.inside(S.m, group, p.slice(2))))) return null;
    const sis = h.ops.sisters(S.m, target);
    const before = sis.keys.slice(sis.keys.indexOf(target) + 1).find((k) => k[0] !== "k") || null;
    return { canvas: true, op: "after", key: target, group: sis.parent, before, card: boxOf(S, id), ...(g.tile && g.tile.dataset.shape !== "group" ? { from: id } : {}) };
  }

  function wire(S, h) {
    const fig = S?.fig;
    const stage = fig?.parentElement;
    const layer = stage?.querySelector(".dgm-overlay");
    if (!layer || S.k || fig.dataset.canvas) return;
    fig.dataset.canvas = "1";
    let sweep = null;

    const end = () => {
      sweep?.rect.remove();
      for (const b of layer.querySelectorAll(".dgm-box.swept")) b.classList.remove("swept");
      sweep = null;
    };
    const touched = (event) => {
      const img = imageOf(S);
      return img && S.hit ? math.sweep(S.hit, img.getBoundingClientRect(), { left: sweep.x, top: sweep.y, right: event.clientX, bottom: event.clientY }) : [];
    };
    //: In the capture phase and ahead of the zoom's pan (diagram-view.js): the press on empty space is not a pan.
    fig.addEventListener("pointerdown", (event) => {
      const img = imageOf(S);
      if (event.button || !event.shiftKey || !img || !S.hit || event.target.closest(".dock")) return;
      if (math.nodeAt(S.hit, img.getBoundingClientRect(), event.clientX, event.clientY)) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      fig.setPointerCapture?.(event.pointerId);
      const rect = document.createElement("span");
      rect.className = "dgm-marquee";
      layer.append(rect);
      sweep = { id: event.pointerId, x: event.clientX, y: event.clientY, rect };
    }, true);
    fig.addEventListener("pointermove", (event) => {
      if (!sweep || event.pointerId !== sweep.id) return;
      const home = layer.getBoundingClientRect();
      const [l, r] = [sweep.x, event.clientX].sort((a, b) => a - b);
      const [t, b] = [sweep.y, event.clientY].sort((a, b) => a - b);
      Object.assign(sweep.rect.style, { left: `${l - home.left}px`, top: `${t - home.top}px`, width: `${r - l}px`, height: `${b - t}px` });
      const ids = new Set(touched(event));
      for (const box of layer.querySelectorAll(".dgm-box")) box.classList.toggle("swept", ids.has(box.dataset.node));
    });
    fig.addEventListener("pointerup", (event) => {
      if (!sweep || event.pointerId !== sweep.id) return;
      const keys = touched(event).map((id) => h.ops.key("n", id));
      end();
      if (keys.length) S.pick?.(keys, keys[0]);
    });
    fig.addEventListener("pointercancel", end);
    window.addEventListener("keydown", (event) => {
      if (sweep && event.key === "Escape") end();
    });
  }

  diagramModel.canvas = { wire, over, node, math };
})();
