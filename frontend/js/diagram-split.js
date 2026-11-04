// diagram-split.js: the divider between the blocks list and the picture of the diagram builder (INBOX 1615 e,
// DOCUMENTS_PLAN 22.4 R3). Lazy: `LAZY_MODULES.diagramSplit`, registered at the foot of documents-mermaid.js and asked
// for by diagram-builder.js's `show`. It is the sidebars' handle (`.sidebar-resize`: role separator, tabindex 0,
// `trackSeparatorValue`, arrows 12 px, Shift 40 px, `prefs` for the width) on a grid, so it sets a column variable
// (`--dgm-list` on `.dgm-body`) instead of a panel's width. The picture side keeps at least 240 px.
(() => {
  const KEY = "diagramListWidth";
  const MIN = 224; // 14rem: the least the blocks list has always had
  const KEEP = 240; // what the picture keeps
  const STEP = 12;
  const BIG = 40;
  const TIGHT = 304; // 19rem: under it a row has no room for "Connect to…" beside the name

  //: The pure half (tested under node): the list column for a wish, in a body `total` wide of which the handle is `grip`.
  const math = {
    MIN,
    KEEP,
    clamp: (want, total, grip = 0) => Math.round(Math.min(Math.max(want, MIN), Math.max(MIN, total - grip - KEEP))),
  };

  function wire(S) {
    const body = S?.pane?.parentElement;
    if (!body || !body.classList.contains("dgm-body") || body.dataset.split) return;
    body.dataset.split = "1";
    const handle = document.createElement("div");
    handle.className = "sidebar-resize dgm-split-handle";
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", "vertical");
    handle.setAttribute("tabindex", "0");
    handle.setAttribute("aria-label", "Resize the blocks list: arrow keys, or drag");
    handle.title = "Drag to resize, double-click to reset";
    S.pane.after(handle);
    body.classList.add("dgm-split");

    const room = () => body.getBoundingClientRect().width - handle.getBoundingClientRect().width;
    const apply = (want, remember = true) => {
      const px = math.clamp(want, body.getBoundingClientRect().width, handle.getBoundingClientRect().width);
      body.style.setProperty("--dgm-list", `${px}px`);
      body.classList.toggle("dgm-tight", px < TIGHT);
      if (remember) {
        try {
          prefs.set(KEY, String(px));
        } catch {
          /* private mode: it just will not be remembered */
        }
      }
      return px;
    };
    trackSeparatorValue(handle, S.pane, MIN, Math.max(MIN, Math.round(room() - KEEP)) || 640);
    let saved = 0;
    try {
      saved = Number(prefs.get(KEY, null)) || 0;
    } catch {
      /* storage blocked */
    }
    if (saved) apply(saved, false);
    //: A list too narrow for the words on its rows says so with a class (CSS cannot ask a grid column its width).
    const tight = () => {
      if (!body.isConnected) return window.removeEventListener("resize", tight); // the pane was remounted
      body.classList.toggle("dgm-tight", S.pane.getBoundingClientRect().width < TIGHT);
    };
    window.addEventListener("resize", tight);
    tight();

    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const start = S.pane.getBoundingClientRect().width;
      document.body.classList.add("resizing-sidebar");
      const move = (e) => apply(start + (e.clientX - startX));
      const stop = () => {
        document.body.classList.remove("resizing-sidebar");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
    });
    handle.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? BIG : STEP;
      const now = S.pane.getBoundingClientRect().width;
      if (event.key === "ArrowLeft") apply(now - step);
      else if (event.key === "ArrowRight") apply(now + step);
      else if (event.key === "Home") {
        body.style.removeProperty("--dgm-list");
        try {
          prefs.set(KEY, "");
        } catch {
          /* storage blocked */
        }
      } else return;
      event.preventDefault();
    });
    handle.addEventListener("dblclick", () => handle.dispatchEvent(new KeyboardEvent("keydown", { key: "Home" })));
  }

  diagramModel.split = { wire, math };
})();
