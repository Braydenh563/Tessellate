// diagram-view.js: zoom, pan and fit for the diagram builder's picture (INBOX 1614, DOCUMENTS_PLAN 22.3). Lazy:
// `LAZY_MODULES.diagramView`, registered at the foot of documents-mermaid.js and asked for by diagram-builder.js's `show`
// for every pane (a flowchart's and the kinds'). It replaces the phone-only `zoomable` of diagram-touch.js and keeps
// its technique: the zoom is a width on the <img> plus the figure's own scroll, not a transform, so the picture's boxes
// stay where `getBoundingClientRect` says they are.
//
// Fit is the default: the whole diagram inside the pane with an 8px margin, never above its drawn size. The zoom is then
// 0.25 to 5 times that fit. It is kept as a scale (px per drawing unit), so an edit that redraws the picture leaves it
// where it was; a change of diagram kind starts at Fit again. Reached by a corner bar (`.dock`), Ctrl+wheel and pinch
// about the pointer, + - 0 and the arrow keys when the picture has focus, and a drag or one finger to pan.
(() => {
  const MIN = 0.25;
  const MAX = 5;
  const STEP = 1.25;
  const MARGIN = 8;
  const PAN = 48;

  //: The pure half (tested under node). `fit` is px per drawing unit.
  const math = {
    MIN,
    MAX,
    STEP,
    MARGIN,
    fitScale: (w, h, pw, ph) => Math.max(0.01, Math.min(1, (pw - 2 * MARGIN) / w, (ph - 2 * MARGIN) / h)),
    clamp: (scale, fit) => Math.min(MAX * fit, Math.max(MIN * fit, scale)),
    //: The drawing's size from its viewBox (the <img> may not have decoded yet).
    size: (svg) => {
      const m = /viewBox="\s*[-\d.e]+[ ,]+[-\d.e]+[ ,]+([\d.e]+)[ ,]+([\d.e]+)\s*"/i.exec(String(svg || ""));
      return m && Number(m[1]) > 0 && Number(m[2]) > 0 ? { w: Number(m[1]), h: Number(m[2]) } : null;
    },
    //: The readout: px per drawing unit as a percent, so 100% is the drawing's own size (a Fit that shrinks a big diagram reads under 100).
    percent: (scale) => Math.max(1, Math.round(scale * 100)),
    //: A wheel notch (100) is one step; a trackpad's small deltas are smaller steps.
    wheel: (dy) => Math.pow(STEP, -Math.max(-100, Math.min(100, dy)) / 100),
  };

  const kindWord = (source) => {
    const rest = diagramModel.front(String(source || "").replace(/\r/g, "")).rest;
    const line = rest.split("\n").map((l) => l.trim()).find((l) => l && !l.startsWith("%%")) || "";
    const word = (/^[A-Za-z-]+/.exec(line) || [""])[0].toLowerCase();
    return word === "graph" ? "flowchart" : word;
  };

  function wire(S) {
    const fig = S?.fig;
    if (!fig || fig.dataset.view) return;
    fig.dataset.view = "1";
    const state = { fit: true, scale: 1, kind: "" };
    const points = new Map();
    let start = null;
    let lastTap = 0;
    let travel = 0;
    let f = 1;

    const stage = document.createElement("div");
    stage.className = "dgm-stage";
    fig.replaceWith(stage);
    stage.append(fig);
    fig.tabIndex = 0;
    fig.setAttribute("aria-label", "Diagram picture. Plus and minus zoom, 0 fits it to the pane, the arrow keys move it.");

    const image = () => fig.querySelector(".md-mermaid-img");
    const dims = (img) => math.size(img.mermaidSvg) || (img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null);
    //: Put the width back after every draw, every resize and every gesture.
    const paint = () => {
      const img = image();
      stage.classList.toggle("dgm-zoomable", Boolean(img));
      if (!img) return;
      const d = dims(img);
      if (!d) return;
      const kind = kindWord(fig.mermaidSource);
      if (state.kind && kind !== state.kind) state.fit = true;
      state.kind = kind;
      //: The box less its border, not `clientWidth`: that is rounded and loses a scrollbar's width, so Fit would move with the zoom.
      const box = fig.getBoundingClientRect();
      f = math.fitScale(d.w, d.h, box.width - 2 * fig.clientLeft, box.height - 2 * fig.clientTop);
      if (state.fit) state.scale = f;
      else state.scale = math.clamp(state.scale, f);
      img.draggable = false;
      img.style.maxWidth = "none";
      img.style.width = `${d.w * state.scale}px`;
      fig.dataset.zoom = state.fit ? "fit" : (state.scale / f).toFixed(2);
      //: The 100% button is also the live readout (INBOX 1652): it names the zoom now and a press goes to 100%.
      const now = `${math.percent(state.scale)}%`;
      if (buttons.actual.textContent !== now) {
        buttons.actual.textContent = now;
        buttons.actual.setAttribute("aria-label", `Zoom ${now}. Show the diagram at its drawn size, 100%`);
      }
      buttons.out.disabled = state.scale <= math.MIN * f * 1.001;
      buttons.in.disabled = state.scale >= math.MAX * f * 0.999;
      for (const after of fig.onzoom || []) after();
    };
    //: Zoom to `next` keeping the point under (cx, cy) where it is.
    const zoomTo = (next, cx, cy) => {
      const img = image();
      if (!img || !dims(img)) return;
      paint();
      const before = img.getBoundingClientRect();
      const fx = (cx - before.left) / (before.width || 1);
      const fy = (cy - before.top) / (before.height || 1);
      state.scale = math.clamp(next, f);
      state.fit = Math.abs(state.scale / f - 1) < 0.01;
      paint();
      const after = img.getBoundingClientRect();
      fig.scrollLeft += after.left + fx * after.width - cx;
      fig.scrollTop += after.top + fy * after.height - cy;
    };
    const centre = () => {
      const r = fig.getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2];
    };
    const fitTo = () => {
      state.fit = true;
      paint();
      fig.scrollLeft = fig.scrollTop = 0;
    };
    const by = (factor) => zoomTo(state.scale * factor, ...centre());
    const actual = () => {
      const img = image();
      if (img && dims(img)) zoomTo(1, ...centre());
    };

    //: The corner bar: a plain `.dock` (DESIGN.md, "A zoom control on a picture").
    const bar = document.createElement("div");
    bar.className = "dock dgm-zoom";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Zoom the picture");
    const group = document.createElement("div");
    group.className = "dock-group";
    const buttons = {
      out: smallButton("ph:minus", "Zoom out", () => by(1 / STEP)),
      in: smallButton("ph:plus", "Zoom in", () => by(STEP)),
      fit: smallButton("Fit", "Fit the diagram to the pane", fitTo),
      actual: smallButton("100%", "Zoom now. Press for the drawn size, 100%", actual),
    };
    group.append(buttons.out, buttons.in, buttons.fit, buttons.actual);
    bar.append(group);
    stage.append(bar);

    (fig.onpaint ||= []).push(paint);
    new ResizeObserver(paint).observe(fig);

    fig.addEventListener("wheel", (event) => {
      if (!event.ctrlKey || !image()) return;
      event.preventDefault();
      zoomTo(state.scale * math.wheel(event.deltaY), event.clientX, event.clientY);
    }, { passive: false });
    fig.addEventListener("keydown", (event) => {
      if (event.target !== fig || event.ctrlKey || event.metaKey || event.altKey) return;
      const move = { ArrowLeft: [-PAN, 0], ArrowRight: [PAN, 0], ArrowUp: [0, -PAN], ArrowDown: [0, PAN] }[event.key];
      if (move) fig.scrollBy(move[0], move[1]);
      else if (event.key === "+" || event.key === "=") by(STEP);
      else if (event.key === "-" || event.key === "_") by(1 / STEP);
      else if (event.key === "0") fitTo();
      else return;
      event.preventDefault();
    });

    //: Touch and mouse: two fingers pinch; one finger or the mouse drags the picture when it is bigger than the pane;
    //: a double tap fits it, or opens it to twice the fit.
    const span = () => {
      const [a, b] = [...points.values()];
      return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    };
    const roomy = () => fig.scrollWidth > fig.clientWidth + 1 || fig.scrollHeight > fig.clientHeight + 1;
    fig.addEventListener("pointerdown", (event) => {
      if (event.button) return;
      if (!points.size) travel = 0;
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2) start = { d: span().d, scale: state.scale };
    });
    fig.addEventListener("pointermove", (event) => {
      const last = points.get(event.pointerId);
      if (!last) return;
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2 && start) {
        const now = span();
        zoomTo(start.scale * (now.d / start.d), now.x, now.y);
        travel = 99;
      } else if (points.size === 1 && (roomy() || travel > 12)) {
        const dx = event.clientX - last.x;
        const dy = event.clientY - last.y;
        travel += Math.abs(dx) + Math.abs(dy);
        fig.scrollLeft -= dx;
        fig.scrollTop -= dy;
        if (travel > 12 && event.pointerType !== "touch") fig.setPointerCapture?.(event.pointerId);
      }
    });
    const lift = (event) => {
      if (!points.delete(event.pointerId)) return;
      start = null;
      if (event.pointerType !== "touch" || event.type !== "pointerup" || points.size) return;
      const now = event.timeStamp;
      if (travel > 12) lastTap = 0;
      else if (now - lastTap < 320) {
        if (state.fit) zoomTo(f * 2, event.clientX, event.clientY);
        else fitTo();
        lastTap = 0;
      } else lastTap = now;
    };
    fig.addEventListener("pointerup", lift);
    fig.addEventListener("pointercancel", lift);
    //: A pan or a pinch is not a press on a block.
    fig.addEventListener("click", (event) => {
      if (travel > 12) event.stopPropagation(), (travel = 0);
    }, true);

    paint();
  }

  diagramModel.view = { wire, math };
})();
