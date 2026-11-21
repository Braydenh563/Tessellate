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
    //: True where a press in that direction has nowhere to go: the same ends the wheel and a pinch clamp to, so + and Ctrl+wheel stop at one number (1679 m: the last press is a short step, where the button used to go grey at 477% and the wheel went on to 500%).
    atEnd: (scale, fit, dir) => (dir > 0 ? scale >= MAX * fit * (1 - 1e-6) : scale <= MIN * fit * (1 + 1e-6)),
    //: A mouse notch (a whole multiple of 100 or 120: what a wheel reports at 100% or 125% display scaling), a line-mode wheel and a pinch (Ctrl) zoom.
    //: A trackpad's two-finger scroll (small, fractional, sideways, or a flick of any other whole number) and Shift pan natively (1679 review).
    zooms: (e) => !e.shiftKey && (e.ctrlKey || e.deltaMode === 1 || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50 && (Math.abs(e.deltaY) % 100 === 0 || Math.abs(e.deltaY) % 120 === 0))),
    //: The scale factor of one wheel event: a notch is STEP, a pinch's small deltas are continuous.
    factor: (e) => (e.ctrlKey && e.deltaMode === 0 && Math.abs(e.deltaY) < 50 ? Math.exp(-e.deltaY * 0.01) : e.deltaMode === 1 ? STEP ** -Math.sign(e.deltaY) : math.wheel(e.deltaY)),
    //: The box a press of an arrow key reaches (DD-8a, 1107): the nearest one in that direction, a sideways miss counting double, or the
    //: top-left one when nothing is picked. `boxes` are the picture's `{id, x, y}`; `dx` and `dy` are -1, 0 or 1.
    reach: (boxes, from, dx, dy) => {
      const here = boxes.find((b) => b.id === from);
      if (!here) return [...boxes].sort((a, b) => a.y - b.y || a.x - b.x)[0] || null;
      let best = null;
      let least = Infinity;
      for (const b of boxes) {
        const [ax, ay] = [b.x - here.x, b.y - here.y];
        const ahead = ax * dx + ay * dy;
        const score = ahead + 2 * (Math.abs(ax * dy) + Math.abs(ay * dx));
        if (b !== here && ahead > 0 && score < least) [best, least] = [b, score];
      }
      return best;
    },
    //: The picture said in words, for its alt text and description (DD-8a): every box, then every arrow.
    summary: (m) => {
      const name = (id) => m.nodes.find((n) => n.id === id)?.text ?? id;
      const list = (items, cap = 12) => items.slice(0, cap).join(", ") + (items.length > cap ? `, and ${items.length - cap} more` : "");
      const n = m.nodes.length;
      const e = m.edges.length;
      if (!n) return "Flowchart, empty";
      return `Flowchart, ${n} ${n === 1 ? "box" : "boxes"} (${list(m.nodes.map((x) => x.text))}), ${e} ${e === 1 ? "arrow" : "arrows"}${e ? `: ${list(m.edges.map((x) => `${name(x.from)} to ${name(x.to)}`))}` : ""}`;
    },
    //: What the live region reads when a box is picked in the picture: its name, its kind and where its arrows go.
    said: (m, id) => {
      const node = m.nodes.find((n) => n.id === id);
      if (!node) return "";
      const name = (i) => m.nodes.find((n) => n.id === i)?.text ?? i;
      const into = m.edges.filter((x) => x.to === id).map((x) => name(x.from));
      const out = m.edges.filter((x) => x.from === id).map((x) => name(x.to));
      const kind = { rect: "box", round: "rounded box", stadium: "pill", circle: "circle", diamond: "decision", hexagon: "hexagon", cylinder: "database", parallelogram: "input or output" }[node.shape] || "box";
      return `${node.text}, ${kind}.${into.length ? ` In from ${into.join(", ")}.` : ""}${out.length ? ` Out to ${out.join(", ")}.` : ""}${into.length || out.length ? "" : " No arrows."}`;
    },
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
    //: A drag on a picture that already fits moves nothing; a line says why (1679 m), once a drag has gone 24 px.
    let wasted = 0;
    let noteTimer = 0;
    const note = document.createElement("p");
    note.className = "dgm-pan-note muted hidden";
    note.setAttribute("role", "status");
    note.textContent = "The whole diagram is in view, so there is nothing to move. Zoom in to pan.";
    let f = 1;

    const stage = document.createElement("div");
    stage.className = "dgm-stage";
    fig.replaceWith(stage);
    stage.append(fig);
    fig.tabIndex = 0;
    fig.setAttribute("aria-label", "Diagram picture. Arrow keys pick a box, Shift and an arrow move the picture, plus and minus zoom, 0 fits it.");
    //: The picture says what it holds, and the arrow keys walk its boxes (DD-8a, 1107). A kind's pane has no boxes: its arrows pan.
    const boxes = () => (!S.k && S.m && S.hit?.boxes?.length ? S.hit.boxes : null);
    //: One pending message: a quick run of arrows leaves the last box's words, not an earlier one that landed after.
    let told = 0;
    const tell = (text) => {
      if (!S.live) return;
      S.live.textContent = "";
      clearTimeout(told);
      told = setTimeout(() => (S.live.textContent = text), 20);
    };
    //: The picked box brought into view when the picture is zoomed past the pane.
    const reveal = (b) => {
      const img = image();
      if (!img) return;
      const r = img.getBoundingClientRect();
      const [vx, vy, vw, vh] = S.hit.vb;
      const at = [r.left + ((b.x - vx) / vw) * r.width, r.top + ((b.y - vy) / vh) * r.height];
      const pane = fig.getBoundingClientRect();
      const nudge = (v, lo, hi) => (v < lo + 24 ? v - lo - 24 : v > hi - 24 ? v - hi + 24 : 0);
      fig.scrollBy({ left: nudge(at[0], pane.left, pane.right), top: nudge(at[1], pane.top, pane.bottom), behavior: "auto" });
    };
    const choose = (key) => {
      const list = boxes();
      if (!list) return false;
      const to = math.reach(list, S.sel?.startsWith("n:") ? S.sel.slice(2) : "", ...{ ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[key]);
      if (!to) return tell("No box that way."), true;
      diagramModel.builder.select(S, `n:${to.id}`);
      S.tree.querySelector(`.dgm-block[data-key="n:${to.id}"]`)?.scrollIntoView({ block: "nearest" });
      reveal(to);
      tell(math.said(S.m, to.id));
      return true;
    };

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
      //: A finger's handles lean out of a block, so a touch screen fits the drawing 16 px short of the pane's edge all round: a block at the
      //: edge had its handle pushed back over it (390: 227 and 236 px of two blocks under one), dgbt-1109 3.
      const gap = matchMedia("(pointer: coarse)").matches ? 32 : 0;
      f = math.fitScale(d.w, d.h, box.width - 2 * fig.clientLeft - gap, box.height - 2 * fig.clientTop - gap);
      //: Only when the drawing is shrunk to fit: a chart that fits whole has nothing to turn (the default three boxes asked).
      diagramModel.outline?.offer(S, f < 1 && math.sideways(d, box, S.m?.dir));
      if (state.fit) state.scale = f;
      else state.scale = math.clamp(state.scale, f);
      img.draggable = false;
      img.style.maxWidth = "none";
      img.style.width = `${d.w * state.scale}px`;
      //: A new picture (an edit redraws it) empties the pane and the browser clamps the scroll to 0: the place the person was reading comes back (INBOX 1661 g).
      if (img !== shown) fig.scrollTo(...(shown ? seen : [0, 0])), (shown = img);
      fig.dataset.zoom = state.fit ? "fit" : (state.scale / f).toFixed(2);
      readout(state.scale);
      for (const after of fig.onzoom || []) after();
      if (S.m && !S.k) fig.setAttribute("aria-description", (img.alt = math.summary(S.m)));
    };
    //: The 100% button is also the live readout (INBOX 1652): it names the zoom now and a press goes to 100%.
    const readout = (scale) => {
      //: A button is grey where a press has nowhere to go; the aimed scale decides while a gesture is in motion.
      buttons.out.disabled = math.atEnd(scale, f, -1);
      buttons.in.disabled = math.atEnd(scale, f, 1);
      //: The readout is a typeable number with a dropdown (INBOX 1694 b, value-field.js); `set` leaves a number being typed alone.
      level?.set(math.percent(scale));
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
    let level = null;
    let glideFrame = 0;
    const cancelGlide = () => {
      if (glideFrame) cancelAnimationFrame(glideFrame);
      glideFrame = 0;
    };
    const reduced = () => reducedMotionWanted();
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
    //: The commit puts the point that was under the pointer at the gesture's start back under it. A pan, a glide or a key that moved
    //: the scroll since would have made that start rectangle stale, so each of them settles a gesture first (1679 review).
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
      //: The position is kept as a fraction: a step under half a pixel rounds to no move, which must not read as an edge (a slow glide ended early).
      let [x, y] = [fig.scrollLeft, fig.scrollTop];
      const tick = (at) => {
        const dt = Math.min(48, at - then);
        then = at;
        x += vx * dt;
        y += vy * dt;
        fig.scrollLeft = x;
        fig.scrollTop = y;
        //: An edge (the scroll landed over a pixel from where it was sent) stops that axis.
        if (Math.abs(fig.scrollLeft - x) > 1) [vx, x] = [0, fig.scrollLeft];
        if (Math.abs(fig.scrollTop - y) > 1) [vy, y] = [0, fig.scrollTop];
        vx = math.decay(vx, dt);
        vy = math.decay(vy, dt);
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
    };
    //: 100% is the drawing's own size; type a number and Enter, or pick one from the chevron (the 1 key still goes to 100%).
    const levelHost = document.createElement("span");
    levelHost.className = "dgm-zoom-level";
    level = valueField(levelHost, {
      value: 100,
      min: 5,
      max: 500,
      label: "Zoom percent",
      format: (v) => `${Math.round(v)}%`,
      presets: [25, 50, 75, 100, 150, 200, 400].concat([{ label: "Fit", run: fitTo }]),
      onCommit: (pct) => {
        const img = image();
        if (img && dims(img)) aim(pct / 100, ...centre());
      },
    });
    group.append(buttons.out, buttons.in, buttons.fit, levelHost);
    bar.append(group);
    stage.append(bar);
    stage.append(note);
    //: The overview in the corner, for a picture larger than the pane (W18 R15); a diagram that fits never fetches it.
    lazyScript("/js/diagram-minimap.js").then(() => diagramModel.minimap?.wire(S, stage, fig));

    let shown = null;
    let seen = [0, 0];
    fig.addEventListener("scroll", () => (seen = [fig.scrollLeft, fig.scrollTop]), { passive: true });
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
      if (move && !event.shiftKey && choose(event.key)) return event.preventDefault();
      cancelGlide();
      //: With boxes, Shift and an arrow pan; the move glides unless the person asked for less motion.
      const far = event.shiftKey ? 5 : 1;
      if (move) settle();
      if (move) fig.scrollBy({ left: move[0] * far, top: move[1] * far, behavior: reduced() ? "auto" : "smooth" });
      else if (event.key === "+" || event.key === "=") step(1);
      else if (event.key === "-" || event.key === "_") step(-1);
      else if (event.key === "0") fitTo();
      else if (event.key === "1") actual();
      //: Enter or F2 names the picked box where it stands, as the blocks pane does; with no box picked the key passes on.
      else if ((event.key === "Enter" || event.key === "F2") && !event.shiftKey && boxes() && S.sel?.startsWith("n:") && S.renameNode?.(S.sel.slice(2))) event.preventDefault();
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
    //: The right button pans too (L-documents-1, as draw.io does): a press that stays put still opens its menu, a drag holds it back.
    let rightDrag = false;
    fig.addEventListener("pointerdown", (event) => {
      //: A handle, an arrow's end or the name field sits in the figure (diagram-overlay.js): its press is not a pan.
      if ((event.button && event.button !== 1 && event.button !== 2) || event.target.closest?.(".dgm-overlay > *")) return;
      //: The middle button pans (no autoscroll), as Space and drag does; a plain mouse drag on empty space is the marquee (diagram-canvas.js).
      if (event.button === 1) event.preventDefault();
      rightDrag = event.button === 2;
      if (!points.size) (travel = 0), (wasted = 0);
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
        settle();
        const dx = event.clientX - last.x;
        const dy = event.clientY - last.y;
        travel += Math.abs(dx) + Math.abs(dy);
        fig.scrollLeft -= dx;
        fig.scrollTop -= dy;
        trail.push({ t: event.timeStamp, x: event.clientX, y: event.clientY });
        if (trail.length > 8) trail.shift();
        if (travel > 12 && event.pointerType !== "touch") fig.setPointerCapture?.(event.pointerId);
        //: A menu that opened on the press (macOS and Linux send `contextmenu` then) goes when the press turns into a pan.
        if (rightDrag && travel > 12) closeActionMenus();
      } else if (points.size === 1 && image()) {
        wasted += Math.abs(event.clientX - last.x) + Math.abs(event.clientY - last.y);
        if (wasted > 24 && note.classList.contains("hidden")) {
          note.classList.remove("hidden");
          clearTimeout(noteTimer);
          noteTimer = setTimeout(() => note.classList.add("hidden"), 3500);
        }
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
    //: Windows sends `contextmenu` on release: after a right drag it is the end of a pan, not a request for a menu.
    fig.addEventListener("contextmenu", (event) => {
      if (rightDrag && travel > 12) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
    //: A pan or a pinch is not a press on a block.
    fig.addEventListener("click", (event) => {
      if (travel > 12) event.stopPropagation(), (travel = 0);
    }, true);

    paint();
  }

  diagramModel.view = { wire, math };
})();
