// diagram-minimap.js: a corner overview of a diagram that is larger than its pane (W18 R15, INBOX 1661 B). Lazy: fetched
// with `lazyScript` by diagram-view.js's `wire`, so a diagram that fits never loads it. Measured at 1440 x 900 on the 24
// bundled templates at Fit: 12 overflow the stage (up to 733 px of picture in 420), so this is not a rare case.
//
// A plain `.dock` in the stage's bottom-left corner (the zoom bar has the right): the picture again at thumbnail size and a
// frame over the part in view. A press or a drag on it moves the figure's scroll, so the picture, the overlay and the
// boxes follow with nothing redrawn. Shown only while the picture is larger than the pane, and not on a phone, where a
// finger pans and the zoom bar has its own row (diagram-lazy.css).
(() => {
  const SIDE = 120;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  //: The pure half (tested under node). `pic` is the picture's box in the figure's scroll coordinates, `view` the pane's.
  const math = {
    thumb: (d) => {
      const k = SIDE / Math.max(d.w, d.h);
      return { w: Math.max(1, Math.round(d.w * k)), h: Math.max(1, Math.round(d.h * k)) };
    },
    //: One pixel of rounding is not an overflow.
    over: (scroll, client) => scroll.w > client.w + 1 || scroll.h > client.h + 1,
    //: The part in view as fractions of the picture, never past its edges.
    window: (pic, view) => ({
      x: clamp((view.left - pic.x) / pic.w, 0, 1),
      y: clamp((view.top - pic.y) / pic.h, 0, 1),
      w: Math.min(1, view.w / pic.w),
      h: Math.min(1, view.h / pic.h),
    }),
    //: The scroll that puts the picture's (fx, fy) in the middle of the pane, inside the picture.
    scrollFor: (pic, view, fx, fy) => ({
      left: clamp(pic.x + fx * pic.w - view.w / 2, 0, Math.max(0, pic.x + pic.w - view.w)),
      top: clamp(pic.y + fy * pic.h - view.h / 2, 0, Math.max(0, pic.y + pic.h - view.h)),
    }),
  };

  function wire(S, stage, fig) {
    if (stage.querySelector(":scope > .dgm-minimap")) return;
    const bar = document.createElement("div");
    bar.className = "dock dgm-minimap hidden";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Overview of the diagram");
    bar.title = "Overview: press or drag to move the picture";
    const thumb = document.createElement("img");
    thumb.alt = "";
    thumb.draggable = false;
    const frame = document.createElement("div");
    frame.className = "dgm-minimap-view";
    const holder = document.createElement("div");
    holder.className = "dgm-minimap-pic";
    holder.append(thumb, frame);
    bar.append(holder);
    stage.append(bar);

    const image = () => fig.querySelector(".md-mermaid-img");
    const pic = (img) => ({ x: img.offsetLeft, y: img.offsetTop, w: img.offsetWidth, h: img.offsetHeight });
    const view = () => ({ left: fig.scrollLeft, top: fig.scrollTop, w: fig.clientWidth, h: fig.clientHeight });
    //: What a scroll needs, measured when the picture or the pane changes (a zoom, a redraw, a resize), not on every scroll
    //: event of a pan: the picture's box, the pane's size and the thumbnail's.
    let geo = null;
    const refresh = () => {
      const img = image();
      const p = img && img.offsetWidth ? pic(img) : null;
      const show = Boolean(p) && math.over({ w: fig.scrollWidth, h: fig.scrollHeight }, { w: fig.clientWidth, h: fig.clientHeight });
      bar.classList.toggle("hidden", !show);
      geo = null;
      if (!show) return;
      if (thumb.src !== img.src) thumb.src = img.src;
      const t = math.thumb({ w: p.w, h: p.h });
      holder.style.width = `${t.w}px`;
      holder.style.height = `${t.h}px`;
      const w = math.window(p, view());
      Object.assign(frame.style, { left: "0px", top: "0px", width: `${w.w * t.w}px`, height: `${w.h * t.h}px` });
      geo = { p, t, w: fig.clientWidth, h: fig.clientHeight };
      pan();
    };
    //: A scroll moves the frame by a transform from the stored boxes: it reads the scroll position only and writes no
    //: layout property, so a pan costs the picture's move and nothing more (L-documents-89).
    const pan = () => {
      if (!geo) return;
      //: A pane that changed size is measured again (these two reads are free: nothing in a pan dirties the layout).
      if (fig.clientWidth !== geo.w || fig.clientHeight !== geo.h) return refresh();
      const w = math.window(geo.p, { left: fig.scrollLeft, top: fig.scrollTop, w: geo.w, h: geo.h });
      frame.style.transform = `translate(${w.x * geo.t.w}px, ${w.y * geo.t.h}px)`;
    };

    //: Press, and drag with the pointer held: the pane is centred on the spot under the pointer.
    const go = (event) => {
      const img = image();
      if (!img) return;
      const r = holder.getBoundingClientRect();
      const to = math.scrollFor(pic(img), view(), clamp((event.clientX - r.left) / r.width, 0, 1), clamp((event.clientY - r.top) / r.height, 0, 1));
      fig.scrollTo({ left: to.left, top: to.top, behavior: "auto" });
    };
    holder.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      holder.setPointerCapture(event.pointerId);
      go(event);
    });
    holder.addEventListener("pointermove", (event) => holder.hasPointerCapture(event.pointerId) && go(event));

    fig.addEventListener("scroll", pan, { passive: true });
    (fig.onzoom ||= []).push(refresh);
    refresh();
  }

  diagramModel.minimap = { math, wire };
})();
