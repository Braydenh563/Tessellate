// diagram-touch.js: the block pane on a phone (1546 P2 leftovers). Lazy: `LAZY_MODULES.diagramTouch`,
// asked for by diagram-builder.js's `show` on a narrow window or a touch screen, so a desktop never loads it.
//
// Two things and nothing else. The palette becomes one "Add" button that opens a sheet of the shapes
// (the tiles stay in the page, hidden, and the sheet presses them, so there is one way a block is added).
// And the picture takes a pinch to zoom and a double tap to fit; one finger pans it as the browser does.
(() => {
  const MAX_ZOOM = 5;

  //: The sheet: one row per tile, the tile's own glyph and name. A tile is pressed, so its handler adds the block.
  function addSheet(root, opener) {
    const tiles = [...root.querySelectorAll(".dgm-palette .dgm-tile")];
    openSheet({
      label: "Add a block",
      name: "diagram-add",
      returnFocus: opener,
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "dgm-add-list";
        for (const tile of tiles) {
          const name = tile.querySelector(".dgm-tile-name")?.textContent || tile.dataset.title || tile.getAttribute("aria-label");
          const row = sheetRow("ph ph-square", name, () => {
            close();
            tile.click();
          });
          row.firstElementChild.replaceWith(tile.firstElementChild.cloneNode(true));
          list.append(row);
        }
        card.append(list);
      },
    });
  }

  //: Pinch and double tap on the picture. The zoom is a width on the image, put back by `onpaint`, which the
  //: builder calls whenever the picture is drawn again after an edit.
  function zoomable(fig) {
    const points = new Map();
    let scale = 1;
    let start = null;
    let lastTap = 0;
    let travel = 0;
    let fit = 0;
    const paint = () => {
      const img = fig.querySelector(".md-mermaid-img");
      if (!img) return;
      img.style.maxWidth = scale > 1.01 ? "none" : "";
      img.style.margin = scale > 1.01 ? "0" : "";
      img.style.width = scale > 1.01 ? `${fit * scale}px` : "";
    };
    fig.onpaint = paint;
    const apply = (next, cx, cy) => {
      const img = fig.querySelector(".md-mermaid-img");
      if (!img) return;
      const before = img.getBoundingClientRect();
      if (scale === 1) fit = before.width;
      const fx = (cx - before.left) / (before.width || 1);
      const fy = (cy - before.top) / (before.height || 1);
      scale = Math.min(MAX_ZOOM, Math.max(1, next));
      paint();
      const after = img.getBoundingClientRect();
      fig.scrollLeft += after.left + fx * after.width - cx;
      fig.scrollTop += after.top + fy * after.height - cy;
    };
    const span = () => {
      const [a, b] = [...points.values()];
      return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    };
    fig.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "touch") return;
      if (!points.size) travel = 0;
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2) start = { d: span().d, scale };
    });
    fig.addEventListener("pointermove", (event) => {
      const last = points.get(event.pointerId);
      if (!last) return;
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2 && start) {
        const now = span();
        apply(start.scale * (now.d / start.d), now.x, now.y);
        travel = 99;
      } else if (points.size === 1) {
        //: One finger pans: the picture asks for every touch (touch-action: none), so it scrolls itself.
        fig.scrollLeft -= event.clientX - last.x;
        fig.scrollTop -= event.clientY - last.y;
        travel += Math.abs(event.clientX - last.x) + Math.abs(event.clientY - last.y);
      }
    });
    const lift = (event) => {
      if (!points.delete(event.pointerId)) return;
      start = null;
      if (event.type !== "pointerup" || points.size) return;
      //: A second tap close in time and place fits the picture again, or opens it to twice its size.
      const now = event.timeStamp;
      if (travel > 12) lastTap = 0;
      else if (now - lastTap < 320) {
        apply(scale > 1.01 ? 1 : 2, event.clientX, event.clientY);
        lastTap = 0;
      } else lastTap = now;
    };
    //: A pan or a pinch is not a press on a block.
    fig.addEventListener("click", (event) => {
      if (travel > 12) event.stopPropagation(), (travel = 0);
    }, true);
    fig.addEventListener("pointerup", lift);
    fig.addEventListener("pointercancel", lift);
  }

  //: Wires one pane, once. `root` is `.dgm`, `fig` the picture; the kinds' panes have the same two.
  function wire(S) {
    if (!S?.root || S.root.dataset.touch) return;
    S.root.dataset.touch = "1";
    S.root.classList.add("dgm-compact");
    const actions = S.root.querySelector(".dgm-dock .dock-actions");
    if (actions) {
      const add = smallButton("ph:plus Add", "Choose a shape to add as a block", () => addSheet(S.root, add), false);
      add.classList.add("dgm-add");
      add.setAttribute("aria-haspopup", "dialog");
      actions.prepend(add);
    }
    if (S.fig) zoomable(S.fig);
  }

  diagramModel.touch = { wire };
})();
