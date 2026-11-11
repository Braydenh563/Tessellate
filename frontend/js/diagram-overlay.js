// diagram-overlay.js: the canvas's overlay (INBOX 1621, DOCUMENTS_PLAN 22.3 and R8a). Lazy: `LAZY_MODULES.diagramOverlay`,
// registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show` for a flowchart, after the
// zoom (diagram-view.js) has made the stage. One box per drawn node sits over the picture, placed from `S.hit` (the node
// boxes `diagramModel.picture.boxes` read off the SVG) through the image's rectangle, so it follows every zoom, pan and
// redraw. It is a child of the figure, in the picture's own scrolled coordinates (INBOX 1661 g): a scroll of the pane moves the
// boxes, rings, handles and the name field with the picture itself, with no redraw to lag or to miss a scroll that resets after a
// redraw. `mermaidShow` keeps it when it swaps the image; the empty and failure states drop it and `draw` puts it back.
// The boxes never take a press (the picture still pans and a click still selects through the builder); hover and
// selection are drawn on them. The selection is read from the blocks list's `aria-selected`, which `S.sel` and `S.picked`
// already write, so the two stay in step with no hook in the builder.
(() => {
  //: The pure half (tested under node). `img` is the image's rectangle, `origin` the overlay's, both client coordinates.
  const math = {
    //: A handle's side: the full size, or half the smaller side of the block it leaves, never under `least` (1679 m).
    handleSize: (at, full, least) => Math.max(least, Math.min(full, Math.round(Math.min(at.w, at.h) / 2))),
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
    //: The innermost group whose border (BAND px either side) or title strip (the top STRIP px) is under a client point, or "":
    //: the parts of a group that select it and rename it (a group's body is empty space, so a press there is not a pick).
    clusterEdgeAt: (hit, img, px, py, band = 6, strip = 32) => {
      if (!hit?.clusters || !img.width || !img.height) return "";
      const [vx, vy, vw, vh] = hit.vb;
      const sx = img.width / vw;
      const sy = img.height / vh;
      const x = px - img.left;
      const y = py - img.top;
      const near = hit.clusters.filter((b) => {
        const l = (b.x - b.w / 2 - vx) * sx;
        const t = (b.y - b.h / 2 - vy) * sy;
        const r = l + b.w * sx;
        const d = t + b.h * sy;
        if (x < l - band || x > r + band || y < t - band || y > d + band) return false;
        return y <= t + strip || x <= l + band || x >= r - band || y >= d - band;
      });
      return near.sort((a, b) => a.w * a.h - b.w * b.h)[0]?.id || "";
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
    //: A flowchart's, and another kind's once its picture file (diagram-seq-canvas.js, diagram-tree-canvas.js) names its parts (`S.hitAt`).
    if (!fig || (S.k && !S.hitAt) || !stage?.classList.contains("dgm-stage") || fig.dataset.overlay) return;
    //: Once per figure, not once per layer in it: a picture that went away (every block deleted) took the layer out, and the next draw made a second one while the first still painted (6 boxes for 3 blocks).
    fig.dataset.overlay = "1";
    const layer = document.createElement("div");
    layer.className = "dgm-overlay";
    layer.setAttribute("aria-hidden", "true");
    fig.append(layer);
    const boxes = new Map();
    const groups = new Map();
    let hover = "";
    let seen = false;

    //: The picked ids: the primary block and every block of the pick, as the list marks them.
    const chosen = () => {
      const ids = new Set();
      //: A flowchart box is named by its node id ("n:" off the row key); another kind's part by the row key itself.
      for (const row of S.tree.querySelectorAll('.dgm-block[aria-selected="true"]')) if (S.hitAt) ids.add(row.dataset.key);
      else if (row.dataset.key.startsWith("n:")) ids.add(row.dataset.key.slice(2));
      else if (row.dataset.key.startsWith("g:")) ids.add(row.dataset.key);
      return ids;
    };
    //: A pick shows in both halves (1702): the box the list picked is brought into the picture and the row the picture picked
    //: into the list, once per change of pick (`nearest`: nothing moves when it is already in view). A hover never moves either.
    let revealed = "";
    const reveal = () => {
      const key = S.sel || "";
      if (key === revealed) return;
      revealed = key;
      if (!key) return;
      const id = S.hitAt ? key : key.slice(2);
      (boxes.get(id) || groups.get(id))?.scrollIntoView({ block: "nearest", inline: "nearest" });
      S.tree.querySelector('.dgm-block[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    };
    const mark = () => {
      const ids = chosen();
      for (const [id, box] of boxes) {
        box.classList.toggle("on", ids.has(id));
        box.classList.toggle("hover", id === hover);
      }
      //: A picked group shows the same ring, drawn on its border (the CSS keeps its body clear).
      for (const [id, box] of groups) box.classList.toggle("on", ids.has(`g:${id}`));
      reveal();
    };
    S.mark = () => mark();
    //: One element per box of a list, kept by id; a group's lies under the nodes' (styled lower).
    //: `born` collects the ids that got a box on this draw, so a new box can be brought into view.
    const sync = (found, kept, attr, extra, born = []) => {
      const live = new Set(found.map((b) => b.id));
      for (const [id, box] of kept) if (!live.has(id)) box.remove(), kept.delete(id);
      for (const b of found) {
        let box = kept.get(b.id);
        if (!box) {
          born.push(b.id);
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
      //: A note or the empty hint replaced the figure's children: the layer comes back with the next picture.
      if (layer.parentElement !== fig) fig.append(layer);
      //: Two boxes read once, before the first write (it read the picture's twice and the layer's twice).
      const rect = img && S.hit ? img.getBoundingClientRect() : null;
      const lay = rect ? layer.getBoundingClientRect() : null;
      const found = rect ? math.place(S.hit, rect, lay) : [];
      sync(rect ? math.place(S.hit, rect, lay, S.hit.clusters) : [], groups, "group", " dgm-cluster");
      const born = [];
      sync(found, boxes, "node", "", born);
      mark();
      //: A box just added and picked is scrolled into view (an add off the visible part of a zoomed picture was out of
      //: sight unless its name field took the focus). Not on the first picture, whose boxes are all new.
      const ids = chosen();
      const fresh = seen && born.find((id) => ids.has(id));
      if (found.length) seen = true;
      if (fresh) boxes.get(fresh).scrollIntoView({ block: "nearest", inline: "nearest" });
    };

    //: After every draw (including one that leaves no picture), and from the zoom (diagram-view.js) after a zoom, a fit or a resize of the pane.
    (fig.onpaint ||= []).push(draw);
    (fig.onzoom ||= []).push(draw);
    //: An image that decodes after its width was set has its height only now.
    fig.addEventListener("load", draw, true);
    //: A pick changes on a press, a key or a focus move inside the pane (the list, its bar); any other change comes with a redraw.
    for (const type of ["click", "keyup", "focusin"]) S.root.addEventListener(type, mark);
    //: Hover outlines the box under the pointer; a touch has no hover.
    //: **The box under the pointer is found in the task after a drawn frame** (INBOX 1766, the owner's lag log: forced
    //: layout in `diagram-overlay.js`). A move read the picture's box in the event, after whatever had been written since
    //: the last draw (a keystroke's redraw, a pan), and so laid the page out for each of them. The event keeps the
    //: pointer and asks once per frame; the read finds layout settled, and the outline follows a frame late.
    let at = null;
    let looking = 0;
    const look = () => {
      looking = 0;
      const img = fig.querySelector(".md-mermaid-img");
      const id = img && at ? math.at(S.hit, img.getBoundingClientRect(), at[0], at[1]) : "";
      if (at && id !== hover) hover = id, mark();
    };
    fig.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" || event.buttons) return;
      at = [event.clientX, event.clientY];
      if (!looking) looking = 1, afterFrames(() => setTimeout(look), 1);
    });
    fig.addEventListener("pointerleave", () => {
      at = null;
      if (hover) hover = "", mark();
    });
    draw();
  }

  diagramModel.overlay = { wire, math };
})();
