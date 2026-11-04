// diagram-overlay.js: the canvas's overlay (INBOX 1621, DOCUMENTS_PLAN 22.3 and R8a). Lazy: `LAZY_MODULES.diagramOverlay`,
// registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for a flowchart, after the
// zoom (diagram-view.js) has made the stage. One box per drawn node sits over the picture, placed from `S.hit` (the node
// boxes `diagramModel.picture.boxes` read off the SVG) through the image's rectangle, so it follows every zoom, pan and
// redraw. It is a sibling of the figure, not a child: `mermaidFill` and the empty state replace the figure's children.
// The boxes never take a press (the picture still pans and a click still selects through the builder); hover and
// selection are drawn on them. The selection is read from the blocks list's `aria-selected`, which `S.sel` and `S.picked`
// already write, so the two stay in step with no hook in the builder.
(() => {
  //: The pure half (tested under node). `img` is the image's rectangle, `origin` the overlay's, both client coordinates.
  const math = {
    //: Each node's box in the overlay's own pixels, from its drawing units.
    place: (hit, img, origin, list = hit?.boxes) => {
      if (!hit || !list || !img.width || !img.height) return [];
      const [vx, vy, vw, vh] = hit.vb;
      const sx = img.width / vw;
      const sy = img.height / vh;
      return list.map((b) => ({
        id: b.id,
        x: img.left - origin.left + (b.x - vx - b.w / 2) * sx,
        y: img.top - origin.top + (b.y - vy - b.h / 2) * sy,
        w: b.w * sx,
        h: b.h * sy,
      }));
    },
    //: The innermost group under a client point, or "" (a group inside a group is the smaller box).
    clusterAt: (hit, img, px, py) => {
      if (!hit?.clusters || !img.width || !img.height) return "";
      const [vx, vy, vw, vh] = hit.vb;
      const x = vx + ((px - img.left) / img.width) * vw;
      const y = vy + ((py - img.top) / img.height) * vh;
      const over = hit.clusters.filter((b) => Math.abs(x - b.x) <= b.w / 2 && Math.abs(y - b.y) <= b.h / 2);
      return over.sort((a, b) => a.w * a.h - b.w * b.h)[0]?.id || "";
    },
    //: The id of the node under a client point, or "".
    at: (hit, img, px, py) => {
      if (!hit || !img.width || !img.height) return "";
      const [vx, vy, vw, vh] = hit.vb;
      const x = vx + ((px - img.left) / img.width) * vw;
      const y = vy + ((py - img.top) / img.height) * vh;
      return hit.boxes.find((b) => Math.abs(x - b.x) <= b.w / 2 && Math.abs(y - b.y) <= b.h / 2)?.id || "";
    },
  };

  function wire(S) {
    const fig = S?.fig;
    const stage = fig?.parentElement;
    if (!fig || S.k || !stage?.classList.contains("dgm-stage") || stage.querySelector(".dgm-overlay")) return;
    const layer = document.createElement("div");
    layer.className = "dgm-overlay";
    layer.setAttribute("aria-hidden", "true");
    stage.append(layer);
    const boxes = new Map();
    const groups = new Map();
    let hover = "";

    //: The picked ids: the primary block and every block of the pick, as the list marks them.
    const chosen = () => {
      const ids = new Set();
      for (const row of S.tree.querySelectorAll('.dgm-block[aria-selected="true"]')) if (row.dataset.key.startsWith("n:")) ids.add(row.dataset.key.slice(2));
      return ids;
    };
    const mark = () => {
      const ids = chosen();
      for (const [id, box] of boxes) {
        box.classList.toggle("on", ids.has(id));
        box.classList.toggle("hover", id === hover);
      }
    };
    //: One element per box of a list, kept by id; a group's lies under the nodes' (styled lower).
    const sync = (found, kept, attr, extra) => {
      const live = new Set(found.map((b) => b.id));
      for (const [id, box] of kept) if (!live.has(id)) box.remove(), kept.delete(id);
      for (const b of found) {
        let box = kept.get(b.id);
        if (!box) {
          box = document.createElement("span");
          box.className = "dgm-box" + extra;
          box.dataset[attr] = b.id;
          layer.append(box);
          kept.set(b.id, box);
        }
        box.style.transform = `translate(${b.x}px, ${b.y}px)`;
        box.style.width = `${b.w}px`;
        box.style.height = `${b.h}px`;
      }
    };
    const draw = () => {
      const img = fig.querySelector(".md-mermaid-img");
      //: Over the figure's padding box, so a box that scrolls out of the pane is clipped with the picture.
      layer.style.left = `${fig.offsetLeft + fig.clientLeft}px`;
      layer.style.top = `${fig.offsetTop + fig.clientTop}px`;
      layer.style.width = `${fig.clientWidth}px`;
      layer.style.height = `${fig.clientHeight}px`;
      const found = img && S.hit ? math.place(S.hit, img.getBoundingClientRect(), layer.getBoundingClientRect()) : [];
      const rect = img && S.hit ? img.getBoundingClientRect() : null;
      sync(rect ? math.place(S.hit, rect, layer.getBoundingClientRect(), S.hit.clusters) : [], groups, "group", " dgm-cluster");
      sync(found, boxes, "node", "");
      mark();
    };

    //: After every draw (including one that leaves no picture), and from the zoom (diagram-view.js) after a zoom, a fit or a resize of the pane.
    (fig.onpaint ||= []).push(draw);
    (fig.onzoom ||= []).push(draw);
    //: An image that decodes after its width was set has its height only now.
    fig.addEventListener("load", draw, true);
    fig.addEventListener("scroll", draw, { passive: true });
    //: A pick changes on a press, a key or a focus move inside the pane (the list, its bar); any other change comes with a redraw.
    for (const type of ["click", "keyup", "focusin"]) S.root.addEventListener(type, mark);
    //: Hover outlines the box under the pointer; a touch has no hover.
    fig.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" || event.buttons) return;
      const img = fig.querySelector(".md-mermaid-img");
      const id = img ? math.at(S.hit, img.getBoundingClientRect(), event.clientX, event.clientY) : "";
      if (id !== hover) hover = id, mark();
    });
    fig.addEventListener("pointerleave", () => {
      if (hover) hover = "", mark();
    });
    draw();
  }

  diagramModel.overlay = { wire, math };
})();
