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
  //: 16 px text x 0.69 = 11 px: Fit stops shrinking there and the figure scrolls (1679, slice 7; Swimlanes fitted to 0.48, 7.7 px).
  const FLOOR = 0.69;

  //: The pure half (tested under node). `fit` is px per drawing unit.
  const math = {
    MIN,
    MAX,
    STEP,
    MARGIN,
    FLOOR,
    fitScale: (w, h, pw, ph) => Math.max(0.01, Math.min(1, Math.max(FLOOR, Math.min((pw - 2 * MARGIN) / w, (ph - 2 * MARGIN) / h)))),
    //: A tall drawing (over 1.6 times its width) in a stage wider than tall, flowing down or up: worth offering a turn.
    sideways: (d, box, dir) => (dir === "TD" || dir === "BT") && d.h > 1.6 * d.w && box.width > box.height,
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
    //: The ladder a button climbs: Fit times STEP to a whole power, so every press is the same ratio (1679 l: 1.25, 1.25, ... then 1.049 at the top).
    //: A scale a wheel left between two rungs joins the ladder on the next press.
    rung: (scale, fit, dir) => {
      const r = Math.log(scale / fit) / Math.log(STEP);
      const next = dir > 0 ? Math.floor(r + 1e-6) + 1 : Math.ceil(r - 1e-6) - 1;
      return Math.min(MAX * fit, Math.max(MIN * fit, fit * Math.pow(STEP, next)));
    },
    //: True where a press in that direction would not be a whole step (a button goes grey there).
    atEnd: (scale, fit, dir) => {
      const r = Math.log(scale / fit) / Math.log(STEP);
      return dir > 0 ? r >= Math.floor(Math.log(MAX) / Math.log(STEP)) - 1e-6 : r <= Math.ceil(Math.log(MIN) / Math.log(STEP)) + 1e-6;
    },
    //: A mouse notch (whole, 50 or more), a line-mode wheel and a pinch (Ctrl) zoom; a trackpad's two-finger scroll (small, fractional, sideways) and Shift pan natively.
    zooms: (e) => !e.shiftKey && (e.ctrlKey || e.deltaMode === 1 || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50 && Number.isInteger(e.deltaY))),
    //: The scale factor of one wheel event: a notch is STEP, a pinch's small deltas are continuous.
    factor: (e) => (e.ctrlKey && e.deltaMode === 0 && Math.abs(e.deltaY) < 50 ? Math.exp(-e.deltaY * 0.01) : e.deltaMode === 1 ? STEP ** -Math.sign(e.deltaY) : math.wheel(e.deltaY)),
    //: px per ms over the last 100 ms of `[{t, x, y}]`; a pause leaves nothing.
    velocity: (samples) => {
      const last = samples[samples.length - 1];
      const run = last ? samples.filter((p) => last.t - p.t <= 100) : [];
      const first = run[0];
      if (run.length < 2 || last.t === first.t) return { x: 0, y: 0 };
      return { x: (last.x - first.x) / (last.t - first.t), y: (last.y - first.y) / (last.t - first.t) };
    },
    decay: (v, dt) => v * Math.pow(0.94, dt / 16),
    settled: (vx, vy) => Math.hypot(vx, vy) < 0.02,
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
    let trail = [];
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
      diagramModel.outline?.offer(S, math.sideways(d, box, S.m?.dir));
      if (state.fit) state.scale = f;
      else state.scale = math.clamp(state.scale, f);
      img.draggable = false;
      img.style.maxWidth = "none";
      img.style.width = `${d.w * state.scale}px`;
      fig.dataset.zoom = state.fit ? "fit" : (state.scale / f).toFixed(2);
      readout(state.scale);
      for (const after of fig.onzoom || []) after();
    };
    //: The 100% button is also the live readout (INBOX 1652): it names the zoom now and a press goes to 100%.
    const readout = (scale) => {
      //: A button is grey where a press would not be a whole step; the aimed scale decides while a gesture is in motion.
      buttons.out.disabled = math.atEnd(scale, f, -1);
      buttons.in.disabled = math.atEnd(scale, f, 1);
      const words = `${math.percent(scale)}%`;
      if (buttons.actual.textContent === words) return;
      buttons.actual.textContent = words;
      buttons.actual.setAttribute("aria-label", `Zoom ${words}. Show the diagram at its drawn size, 100%`);
    };
    //: Zoom to `next` keeping the point that was under (ax, ay) at (cx, cy): the same point for a wheel, the fingers' first and latest middle for a pinch.
    const zoomTo = (next, cx, cy, ax = cx, ay = cy) => {
      const img = image();
      if (!img || !dims(img)) return;
      paint();
      const before = img.getBoundingClientRect();
      const fx = (ax - before.left) / (before.width || 1);
      const fy = (ay - before.top) / (before.height || 1);
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
    //: A gesture (1679 l): each zoom input aims a scale; the next frame paints it as a transform on the picture (no layout, the
    //: overlay hidden), and the real width, the overlay and the scroll follow once the input has been quiet for 140 ms.
    //: The one frame request of this file: asked for by an input (a wheel, a pinch, a drag, a glide), never at rest.
    const nextFrame = (run) => requestAnimationFrame(run);
    let g = null;
    let glideFrame = 0;
    const cancelGlide = () => {
      if (glideFrame) cancelAnimationFrame(glideFrame);
      glideFrame = 0;
    };
    const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
    const show = () => {
      if (!g) return;
      g.frame = 0;
      const k = g.want / g.base;
      if (!g.shown) {
        g.shown = true;
        stage.classList.add("dgm-gesturing");
        g.img.style.willChange = "transform";
        g.img.style.transformOrigin = "0 0";
      }
      g.img.style.transform = `translate(${g.cx - g.r.left - g.px * k}px, ${g.cy - g.r.top - g.py * k}px) scale(${k})`;
      readout(g.want);
    };
    //: Drop the transform without committing; the gesture, or null when there was none.
    const drop = () => {
      const d = g;
      g = null;
      if (!d) return null;
      cancelAnimationFrame(d.frame);
      clearTimeout(d.timer);
      d.img.style.transform = d.img.style.transformOrigin = d.img.style.willChange = "";
      stage.classList.remove("dgm-gesturing");
      return d;
    };
    const settle = () => {
      const d = drop();
      if (d) zoomTo(d.want, d.cx, d.cy, d.r.left + d.px, d.r.top + d.py);
    };
    const aim = (next, cx, cy) => {
      const img = image();
      if (!img || !dims(img)) return;
      cancelGlide();
      if (!g) {
        paint();
        const r = img.getBoundingClientRect();
        g = { img, r, base: state.scale, px: cx - r.left, py: cy - r.top, want: state.scale, cx, cy, frame: 0, timer: 0, shown: false };
      }
      g.want = math.clamp(next, f);
      g.cx = cx;
      g.cy = cy;
      g.frame ||= nextFrame(show);
      clearTimeout(g.timer);
      g.timer = setTimeout(settle, 140);
    };
    const glide = (v) => {
      cancelGlide();
      let [vx, vy, then] = [-v.x, -v.y, performance.now()];
      const tick = (at) => {
        const dt = Math.min(48, at - then);
        then = at;
        const [x0, y0] = [fig.scrollLeft, fig.scrollTop];
        fig.scrollLeft = x0 + vx * dt;
        fig.scrollTop = y0 + vy * dt;
        //: An edge stops that axis.
        vx = fig.scrollLeft === x0 ? 0 : math.decay(vx, dt);
        vy = fig.scrollTop === y0 ? 0 : math.decay(vy, dt);
        glideFrame = math.settled(vx, vy) ? 0 : nextFrame(tick);
      };
      glideFrame = nextFrame(tick);
    };
    const now = () => (g ? g.want : state.scale);
    const fitTo = () => {
      drop();
      cancelGlide();
      state.fit = true;
      paint();
      fig.scrollLeft = fig.scrollTop = 0;
    };
    const step = (dir) => aim(math.rung(now(), f, dir), ...centre());
    const actual = () => {
      const img = image();
      if (img && dims(img)) aim(1, ...centre());
    };

    //: The corner bar: a plain `.dock` (DESIGN.md, "A zoom control on a picture").
    const bar = document.createElement("div");
    bar.className = "dock dgm-zoom";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Zoom the picture");
    const group = document.createElement("div");
    group.className = "dock-group";
    const buttons = {
      out: smallButton("ph:minus", "Zoom out", () => step(-1)),
      in: smallButton("ph:plus", "Zoom in", () => step(1)),
      fit: smallButton("Fit", "Fit the diagram to the pane", fitTo),
      actual: smallButton("100%", "Zoom now. Press for the drawn size, 100%", actual),
    };
    group.append(buttons.out, buttons.in, buttons.fit, buttons.actual);
    bar.append(group);
    stage.append(bar);

    (fig.onpaint ||= []).push(paint);
    new ResizeObserver(paint).observe(fig);

    fig.addEventListener("wheel", (event) => {
      if (!image() || !math.zooms(event)) return;
      event.preventDefault();
      aim(now() * math.factor(event), event.clientX, event.clientY);
    }, { passive: false });
    fig.addEventListener("keydown", (event) => {
      if (event.target !== fig || event.ctrlKey || event.metaKey || event.altKey) return;
      const move = { ArrowLeft: [-PAN, 0], ArrowRight: [PAN, 0], ArrowUp: [0, -PAN], ArrowDown: [0, PAN] }[event.key];
      cancelGlide();
      //: Shift is five times as far; the move glides unless the person asked for less motion.
      const far = event.shiftKey ? 5 : 1;
      if (move) fig.scrollBy({ left: move[0] * far, top: move[1] * far, behavior: reduced() ? "auto" : "smooth" });
      else if (event.key === "+" || event.key === "=") step(1);
      else if (event.key === "-" || event.key === "_") step(-1);
      else if (event.key === "0") fitTo();
      else if (event.key === "1") actual();
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
      cancelGlide();
      trail = [{ t: event.timeStamp, x: event.clientX, y: event.clientY }];
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2) start = { d: span().d, scale: now() };
    });
    fig.addEventListener("pointermove", (event) => {
      const last = points.get(event.pointerId);
      //: A node being moved (obj-drag.js) is not a pan.
      if (!last || document.documentElement.classList.contains("obj-dragging")) return;
      points.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (points.size === 2 && start) {
        const mid = span();
        aim(start.scale * (mid.d / start.d), mid.x, mid.y);
        travel = 99;
      } else if (points.size === 1 && (roomy() || travel > 12)) {
        const dx = event.clientX - last.x;
        const dy = event.clientY - last.y;
        travel += Math.abs(dx) + Math.abs(dy);
        fig.scrollLeft -= dx;
        fig.scrollTop -= dy;
        trail.push({ t: event.timeStamp, x: event.clientX, y: event.clientY });
        if (trail.length > 8) trail.shift();
        if (travel > 12 && event.pointerType !== "touch") fig.setPointerCapture?.(event.pointerId);
      }
    });
    const lift = (event) => {
      if (!points.delete(event.pointerId)) return;
      start = null;
      //: A drag that is let go while moving glides on and slows (a pause before the lift, or less motion asked for, does not).
      if (event.type === "pointerup" && !points.size && travel > 12 && trail.length > 1 && event.timeStamp - trail[trail.length - 1].t < 80 && !reduced()) glide(math.velocity(trail));
      if (event.pointerType !== "touch" || event.type !== "pointerup" || points.size) return;
      const tapped = event.timeStamp;
      if (travel > 12) lastTap = 0;
      else if (tapped - lastTap < 320) {
        if (state.fit) aim(f * 2, event.clientX, event.clientY);
        else fitTo();
        lastTap = 0;
      } else lastTap = tapped;
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
