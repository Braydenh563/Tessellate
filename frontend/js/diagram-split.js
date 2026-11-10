// diagram-split.js: the divider between the blocks list and the picture of the diagram builder (INBOX 1615 e,
// DOCUMENTS_PLAN 22.4 R3). Lazy: `LAZY_MODULES.diagramSplit`, registered at the foot of documents-mermaid.js and asked
// for by diagram-builder.js's `show`. It is the sidebars' handle (`.sidebar-resize`: role separator, tabindex 0,
// `trackSeparatorValue`, arrows 12 px, Shift 40 px, `prefs` for the width) on a grid, so it sets a column variable
// (`--dgm-list` on `.dgm-body`) instead of a panel's width. The picture side keeps at least 240 px.
// Each side folds to a 32 px rail (INBOX 1661 m): a labelled toggle on the panel, `[` for the list and `]` for the picture,
// one kept choice (`diagram.fold`), and one of the two always showing. Not below 600, where there is one column.
(() => {
  const KEY = "diagramListWidth";
  //: Picture and List each keep their own dragged width (1702): one shared width made the two views the same, and the seg said nothing.
  const keyOf = (body) => (body.closest("[data-dgm-layout]")?.dataset.dgmLayout === "blocks" ? `${KEY}.blocks` : KEY);
  const MIN = 224; // 14rem: the least the blocks list has always had
  const KEEP = 240; // what the picture keeps
  const STEP = 12;
  const BIG = 40;
  const TIGHT = 304; // 19rem: under it a row has no room for "Connect to…" beside the name

  //: The pure half (tested under node): the list column for a wish, in a body `total` wide of which the handle is `grip`.
  const math = {
    MIN,
    KEEP,
    // A body not laid out yet (total 0) has no ceiling to measure: keep the wish rather than the least.
    clamp: (want, total, grip = 0) =>
      Math.round(Math.min(Math.max(want, MIN), total > 0 ? Math.max(MIN, total - grip - KEEP) : Infinity)),
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
          prefs.set(keyOf(body), String(px));
        } catch {
          /* private mode: it just will not be remembered */
        }
      }
      return px;
    };
    trackSeparatorValue(handle, S.pane, MIN, Math.max(MIN, Math.round(room() - KEEP)) || 640);
    //: A view's own width, or (none dragged) the width its layout gives in CSS.
    const load = () => {
      let saved = 0;
      try {
        saved = Number(prefs.get(keyOf(body), null)) || 0;
      } catch {
        /* storage blocked */
      }
      if (saved) apply(saved, false);
      else body.style.removeProperty("--dgm-list");
      return saved;
    };
    load();
    //: A list too narrow for the words on its rows says so with a class (CSS cannot ask a grid column its width).
    const tight = () => {
      if (!body.isConnected) return window.removeEventListener("resize", tight); // the pane was remounted
      body.classList.toggle("dgm-tight", S.pane.getBoundingClientRect().width < TIGHT);
      handle.setAttribute("aria-valuemax", Math.max(MIN, Math.round(room() - KEEP)) || 640);
    };
    window.addEventListener("resize", tight);
    tight();
    //: The dialog's Picture / List / Source (diagram-embed.js `view`) tells its host; the pane is read again for that view.
    const host = body.closest("[data-dgm-layout]");
    const relayout = () => {
      if (!body.isConnected) return host?.removeEventListener("dgmlayout", relayout);
      load();
      tight();
    };
    host?.addEventListener("dgmlayout", relayout);

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
        tight(); // the words on the rows come back with the default width
        try {
          prefs.set(keyOf(body), "");
        } catch {
          /* storage blocked */
        }
      } else return;
      event.preventDefault();
    });
    handle.addEventListener("dblclick", () => handle.dispatchEvent(new KeyboardEvent("keydown", { key: "Home" })));
    wireFold(S, body, handle);
  }

  //: The fold: "" (both open), "left" (the list is a rail) or "right" (the picture is). One value, so both can never fold.
  const FOLD = "diagram.fold";
  const SIDES = { left: ["list", "[", "BracketLeft"], right: ["picture", "]", "BracketRight"] };
  const PHONE = "(max-width: 599.98px)";
  const fold = {
    //: The toolbar's old Blocks list button kept "0" in `diagram.outline`; it is read once as a folded list.
    get() {
      try {
        if (prefs.get("diagram.outline") === "0") prefs.set(FOLD, "left"), prefs.set("diagram.outline", "");
        const v = prefs.get(FOLD, "");
        return v === "left" || v === "right" ? v : "";
      } catch {
        return "";
      }
    },
    set(v) {
      try {
        prefs.set(FOLD, v);
      } catch {
        /* storage blocked: it holds for this window only */
      }
    },
    //: What a press on one side's toggle leaves: that side folds, or opens if it was folded (the other then opens too).
    next: (now, side) => (now === side ? "" : side),
  };

  //: One toggle: on the open panel it folds it, on the rail it opens it.
  function toggle(side, folded) {
    const [noun, key] = SIDES[side];
    const b = document.createElement("button");
    b.type = "button";
    b.className = folded ? `ghost dgm-rail` : "ghost small icon-only dgm-fold";
    b.dataset.side = side;
    b.setAttribute("aria-expanded", String(!folded));
    b.setAttribute("aria-keyshortcuts", key);
    const say = `${folded ? "Open" : "Fold"} the ${noun} (${key})`;
    b.title = say;
    b.setAttribute("aria-label", say);
    const icon = document.createElement("i");
    icon.className = `ph ph-sidebar-simple${side === "right" ? " dgm-flip" : ""}`;
    icon.setAttribute("aria-hidden", "true");
    b.append(icon);
    if (folded) b.append(Object.assign(document.createElement("span"), { className: "dgm-rail-word", textContent: noun[0].toUpperCase() + noun.slice(1) }));
    return b;
  }

  //: Paints the kept fold on `body`, and wires the toggles, the rails and the two keys once.
  function wireFold(S, body, handle) {
    const stage = S.fig?.parentElement?.classList.contains("dgm-stage") ? S.fig.parentElement : S.fig;
    if (!stage) return;
    const head = document.createElement("div");
    head.className = "dgm-panehead";
    //: Select all while nothing is picked (1708); diagram-multi.js hides it once there is a pick and the bar's own takes over.
    const leftToggle = toggle("left", false);
    const all = smallButton("Select all", "Pick every block (Ctrl+A on the picture)", () => S.pickAll?.());
    all.classList.add("dgm-head-all");
    head.append(Object.assign(document.createElement("span"), { className: "muted", textContent: "List" }), ...(S.pickAll ? [all] : []), leftToggle);
    S.pane.prepend(head);
    const right = toggle("right", false);
    stage.append(right);
    //: The picture's own scrollbar takes layout width, and this button sits on it (1702): its offset adds the bar's measured width after every draw and zoom.
    const clear = () => {
      const bar = Math.max(0, S.fig.offsetWidth - S.fig.clientWidth - 2 * S.fig.clientLeft);
      right.style.insetInlineEnd = `calc(var(--space-2) + ${bar}px)`;
    };
    (S.fig.onzoom ||= []).push(clear);
    (S.fig.onpaint ||= []).push(clear);
    clear();
    const rails = { left: toggle("left", true), right: toggle("right", true) };
    body.prepend(rails.left);
    body.append(rails.right);
    const paint = (v) => {
      for (const side of ["left", "right"]) body.classList.toggle(`dgm-fold-${side}`, v === side);
      handle.hidden = Boolean(v);
    };
    const press = (side) => {
      //: What is painted, not what is stored: a New diagram is folded without being kept (below), and its rail must open it.
      const was = body.classList.contains("dgm-fold-left") ? "left" : body.classList.contains("dgm-fold-right") ? "right" : "";
      const v = fold.next(was, side);
      fold.set(v);
      paint(v);
      const [noun, key] = SIDES[side];
      if (S.live) S.live.textContent = v ? `The ${noun} is folded. ${key} opens it.` : `The ${noun} is open.`;
      (v ? rails[side] : side === "left" ? leftToggle : right).focus();
    };
    for (const b of [leftToggle, right, rails.left, rails.right]) b.addEventListener("click", () => press(b.dataset.side));
    S.root.addEventListener("keydown", (event) => {
      const side = event.code === "BracketLeft" ? "left" : event.code === "BracketRight" ? "right" : "";
      const t = event.target;
      if (!side || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || t.isContentEditable || t.closest?.("input, textarea, select")) return;
      if (matchMedia(PHONE).matches) return;
      event.preventDefault();
      press(side);
    });
    //: A New diagram opens with its list folded (INBOX 1720, decided 2026-11-10): the picture is the way in. Only while the person has never chosen a fold and the source is the starter or blank, and not kept, so an existing diagram opens as it was left.
    const fresh = !S.k && !prefs.has(FOLD) && ["", diagramModel.starter, diagramModel.print(diagramModel.parse(diagramModel.starter))].includes(S.source.trim());
    paint(fresh ? "left" : fold.get());
  }

  diagramModel.split = { wire, math, fold };
})();
