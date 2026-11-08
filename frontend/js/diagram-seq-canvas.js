// diagram-seq-canvas.js: a sequence diagram edited on its picture (INBOX 1661 l). Lazy: fetched with `lazyScript` by
// diagram-builder.js's `show` for a sequence pane, before the overlay. Mermaid tags every part of a sequence drawing
// (`data-et` participant, life-line, message, note, control-structure, with `data-id`), so the parts are read off the SVG
// rather than guessed from positions. `boxes` turns them into the overlay's `S.hit` (`{vb, boxes}`, centre-based, one box
// per row of the blocks list, keyed by the row's key); `order` names a row for each of Mermaid's statement ids. With
// `S.hit` set, diagram-overlay.js draws the rings and the hover as it does for a flowchart. On the picture: a press picks a
// part, a double press, Enter or F2 renames it in place, Delete removes it and Alt+Up or Alt+Down moves it.
(() => {
  const num = (tag, name) => Number((new RegExp(`\\s${name}="(-?[\\d.]+)"`).exec(tag) || [])[1]);
  const attr = (tag, name) => (new RegExp(`\\s${name}="([^"]*)"`).exec(tag) || [])[1];
  //: A message's box is its line and the words above it: Mermaid writes the words about 38 units over the line.
  const ABOVE = 38;
  const BELOW = 6;
  //: A box's head strip (alt, loop) and a divider's (else, and) are what a press takes, so the frame never hides the steps inside it.
  const STRIP = 32;

  //: The inside of the `<g>` whose opening tag ends at `at`, up to its first closing tag (a part holds no nested group).
  const inner = (svg, at) => svg.slice(at, svg.indexOf("</g>", at) + 1 || at + 2000);

  function participants(svg, out) {
    const life = {};
    for (const m of svg.matchAll(/<line\b[^>]*data-et="life-line"[^>]*>/g)) life[attr(m[0], "data-id")] = { x: num(m[0], "x1"), y1: num(m[0], "y1") };
    for (const m of svg.matchAll(/<g\b[^>]*data-et="participant"[^>]*>/g)) {
      const id = attr(m[0], "data-id");
      if (!life[id] || out.some((p) => p.ref === `p:${id}`)) continue;
      const rect = /<rect\b[^>]*>/.exec(inner(svg, m.index + m[0].length))?.[0];
      const w = rect ? num(rect, "width") : 80;
      const h = rect ? num(rect, "height") : life[id].y1;
      out.push({ et: "participant", ref: `p:${id}`, who: id, x: life[id].x, y: life[id].y1 - h / 2, w, h });
    }
  }

  function messages(svg, out) {
    for (const m of svg.matchAll(/<(line|path)\b[^>]*data-et="message"[^>]*>/g)) {
      const t = m[0];
      let x1 = num(t, "x1");
      let x2 = num(t, "x2");
      let y = num(t, "y1");
      //: A message to itself is a path that loops out to the right of its lifeline.
      if (m[1] === "path") {
        const p = /M\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/.exec(attr(t, "d") || "");
        if (!p) continue;
        [x1, x2, y] = [Number(p[1]), Number(p[1]) + 60, Number(p[2]) + 20];
      }
      const w = Math.max(Math.abs(x2 - x1), 40);
      out.push({ et: "message", ref: attr(t, "data-id"), from: attr(t, "data-from"), to: attr(t, "data-to"), x: (x1 + x2) / 2, y: y - (ABOVE - BELOW) / 2, w, h: ABOVE + BELOW });
    }
  }

  function notes(svg, out) {
    for (const m of svg.matchAll(/<g\b[^>]*data-et="note"[^>]*>/g)) {
      const rect = /<rect\b[^>]*>/.exec(inner(svg, m.index + m[0].length))?.[0];
      if (!rect) continue;
      const [x, y, w, h] = ["x", "y", "width", "height"].map((n) => num(rect, n));
      out.push({ et: "note", ref: attr(m[0], "data-id"), x: x + w / 2, y: y + h / 2, w, h });
    }
  }

  //: A box (alt, loop, par) is four outer lines; any other level line inside it is a divider (else, and), top to bottom.
  function frames(svg, out) {
    for (const m of svg.matchAll(/<g\b[^>]*data-et="control-structure"[^>]*>/g)) {
      const level = [...inner(svg, m.index + m[0].length).matchAll(/<line\b[^>]*class="loopLine"[^>]*>/g)].map((l) => l[0]).filter((l) => num(l, "y1") === num(l, "y2"));
      if (!level.length) continue;
      const ys = level.map((l) => num(l, "y1"));
      const xs = level.flatMap((l) => [num(l, "x1"), num(l, "x2")]);
      const [top, bottom, left, right] = [Math.min(...ys), Math.max(...ys), Math.min(...xs), Math.max(...xs)];
      const ref = attr(m[0], "data-id");
      const strip = (y) => ({ x: (left + right) / 2, y: y + STRIP / 2, w: right - left, h: STRIP });
      out.push({ et: "frame", ref, ...strip(top) });
      ys.filter((y) => y > top && y < bottom).sort((a, b) => a - b).forEach((y, i) => out.push({ et: "divider", ref: `${ref}/${i}`, ...strip(y) }));
    }
  }

  //: The pure half: every tagged part of a drawn sequence diagram, in its own units. Frames last, so a press finds a step first.
  function parts(svg) {
    const vb = (/viewBox="([^"]+)"/.exec(svg || "")?.[1] || "").trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(Number.isNaN)) return null;
    const out = [];
    participants(svg, out);
    messages(svg, out);
    notes(svg, out);
    frames(svg, out);
    return { vb, parts: out };
  }

  //: Mermaid's statement ids walk the steps in order: a message (and its `+` or `-` activation after it), a note, a box's
  //: start, its steps and dividers, its end (the id the box is drawn with), and an `activate` line. A `%%` line is no statement.
  function order(m, key) {
    const map = new Map(m.participants.map((p) => [`p:${p.id}`, key(p)]));
    let i = 0;
    const walk = (steps, divs) => {
      for (const s of steps) {
        if (s.type === "k") i += /^(?:de)?activate\b/i.test(s.line.trim()) ? 1 : 0;
        else if (s.type === "d") divs?.push(key(s)), i++;
        else if (s.type === "b") {
          i++;
          const mine = [];
          walk(s.steps, mine);
          map.set(`i${i}`, key(s));
          mine.forEach((k, n) => map.set(`i${i}/${n}`, k));
          i++;
        } else {
          map.set(`i${i}`, key(s));
          i += s.type === "m" && s.act ? 2 : 1;
        }
      }
    };
    walk(m.steps, null);
    return map;
  }

  //: The overlay's `S.hit`: each part under its row's key. A part with no row (a model the drawing ran ahead of) is left out.
  function boxes(svg, m, key) {
    const read = parts(svg);
    if (!read) return null;
    const names = order(m, key);
    const found = read.parts.filter((p) => names.has(p.ref)).map((p) => ({ ...p, id: names.get(p.ref) }));
    return found.length ? { vb: read.vb, boxes: found, clusters: [] } : null;
  }

  // --- gaps and heads: where a drag or a "+" would put a part (pure, in drawing units) -------------
  const ROWS = new Set(["message", "note", "divider", "frame"]);
  //: Where a row is for ordering (its line) and the strip of height it takes up.
  function span(b) {
    if (b.et === "message") {
      const line = b.y + (ABOVE - BELOW) / 2;
      return { pivot: line, top: line - ABOVE, bottom: line + BELOW };
    }
    if (b.et === "note") return { pivot: b.y, top: b.y - b.h / 2, bottom: b.y + b.h / 2 };
    return { pivot: b.y - STRIP / 2, top: b.y - STRIP / 2, bottom: b.y + STRIP / 2 };
  }
  const heads = (hit) => hit.boxes.filter((b) => b.et === "participant").sort((a, b) => a.x - b.x);

  //: The gap at drawing height `vy`: the row a new step goes before (null: the end), and the height of its marker.
  function gap(hit, vy) {
    const list = hit.boxes.filter((b) => ROWS.has(b.et)).map((b) => ({ b, ...span(b) })).sort((a, b) => a.pivot - b.pivot);
    const i = list.findIndex((r) => r.pivot > vy);
    const next = list[i] || null;
    const prev = i < 0 ? list.at(-1) : list[i - 1];
    const top = prev ? prev.bottom : Math.max(0, ...heads(hit).map((p) => p.y + p.h / 2));
    return { key: next?.b.id || null, y: next ? (top + next.top) / 2 : top + 24, index: i < 0 ? list.length : i };
  }

  //: The head gap at drawing x `vx`, not counting the head being dragged: the head it goes before (null: last) and the line's place.
  function headGap(hit, vx, skip = "") {
    const ps = heads(hit).filter((p) => p.id !== skip);
    const i = ps.filter((p) => p.x < vx).length;
    const [a, b] = [ps[i - 1], ps[i]];
    const x = a && b ? (a.x + a.w / 2 + b.x - b.w / 2) / 2 : b ? b.x - b.w / 2 - 10 : a ? a.x + a.w / 2 + 10 : vx;
    return { key: b?.id || null, x, y: ps[0]?.y ?? 0, h: ps[0]?.h ?? 0 };
  }

  //: The lifeline nearest drawing x `vx`.
  const near = (hit, vx) => heads(hit).reduce((best, p) => (!best || Math.abs(p.x - vx) < Math.abs(best.x - vx) ? p : best), null);
  //: A message dropped at `vx` runs from the nearest lifeline to its right-hand neighbour (the last: from its left-hand one).
  function pair(hit, vx) {
    const ps = heads(hit);
    const n = near(hit, vx);
    const at = ps.indexOf(n);
    const [from, to] = ps[at + 1] ? [n, ps[at + 1]] : [ps[at - 1] || n, n];
    return { from: from?.who, to: to?.who, near: n };
  }

  // --- marks and drops: what the picture shows while a part is dragged ---------------------------
  const layerOf = (S) => S.fig.querySelector(".dgm-overlay");
  //: The picture's drawing units and the screen, both ways, for the SVG as it sits now.
  function frameOf(S) {
    const r = S.fig.querySelector(".md-mermaid-img").getBoundingClientRect();
    const [vx, vy, vw, vh] = S.hit.vb;
    const [kx, ky] = [r.width / vw, r.height / vh];
    return { r, kx, ky, ux: (px) => vx + (px - r.left) / kx, uy: (py) => vy + (py - r.top) / ky, px: (x) => r.left + (x - vx) * kx, py: (y) => r.top + (y - vy) * ky };
  }
  //: One mark at a time, in the overlay: a 2 px line in a gap or a head gap, or the rubber line of a message.
  function mark(S, cls) {
    let el = S.seqMark;
    if (!el?.isConnected || el.dataset.kind !== cls) {
      el?.remove();
      el = document.createElement("span");
      el.className = `dgm-seqmark ${cls}`;
      el.dataset.kind = cls;
      layerOf(S).append(el);
      S.seqMark = el;
    }
    return el;
  }
  const clear = (S) => (S.seqMark?.remove(), (S.seqMark = null));
  function put(S, el, x, y, w, h) {
    const o = layerOf(S).getBoundingClientRect();
    el.style.transform = `translate(${x - o.left}px, ${y - o.top}px)`;
    el.style.width = `${w}px`;
    el.style.height = `${h}px`;
    return el;
  }
  //: The line across all lifelines at the gap's height, and the head gap's line down the heads.
  function gapLine(S, f, g) {
    const ps = heads(S.hit);
    const [a, b] = [f.px(ps[0].x - ps[0].w / 2), f.px(ps.at(-1).x + ps.at(-1).w / 2)];
    return put(S, mark(S, "gap"), a, f.py(g.y) - 1, b - a, 2);
  }
  function headLine(S, f, g) {
    return put(S, mark(S, "head"), f.px(g.x) - 1, f.py(g.y), 2, g.h * f.ky);
  }
  //: A message from `from` to `to` at the gap: a rubber line with its arrow, or a small loop back to the same lifeline.
  function rubber(S, f, from, to, g) {
    const [a, b] = [f.px(from.x), f.px(to.x)];
    const same = from === to;
    const el = mark(S, same ? "rubber self" : b < a ? "rubber back" : "rubber");
    return same ? put(S, el, a, f.py(g.y) - 10, 40, 20) : put(S, el, Math.min(a, b), f.py(g.y) - 1, Math.abs(b - a), 2);
  }
  //: Where a step goes: before the row `key` (null: the end of the top level).
  function spotOf(S, key) {
    const f = key && diagramModel.kinds.ops.find(S.k, S.m, key);
    return f ? { parent: f.parent, before: f.node } : { parent: null, before: null };
  }

  //: A shelf tile dragged over the picture (diagram-kinds.js `dropAt` asks): a participant names a head gap, a step a gap
  //: between rows (a message between the lifeline nearest the pointer and the next), a Loop or an Alt over a message wraps it.
  function over(g) {
    const { S, tile } = g;
    const at = document.elementFromPoint(g.x, g.y);
    if (!S.hit || !S.fig.querySelector(".md-mermaid-img") || !at || !S.fig.contains(at) || at.closest(".dock, .dgm-zoom")) return clear(S), null;
    const f = frameOf(S);
    const [vx, vy] = [f.ux(g.x), f.uy(g.y)];
    const name = (key) => diagramModel.kinds.act.name(S, key);
    if (tile.type === "a") {
      const h = headGap(S.hit, vx);
      return { canvas: true, op: "into", ...spotOf(S, h.key), add: {}, card: headLine(S, f, h), word: h.key ? `Before ${name(h.key)}` : "After the last participant" };
    }
    const row = diagramModel.overlay.math.at(S.hit, f.r, g.x, g.y);
    if (tile.type === "b" && S.hit.boxes.find((b) => b.id === row)?.et === "message") {
      clear(S);
      const card = layerOf(S).querySelector(`.dgm-box[data-node="${CSS.escape(row)}"]`);
      return { canvas: true, op: "into", ...spotOf(S, row), add: { wrap: row }, card, word: `Around ${name(row)}` };
    }
    const gp = gap(S.hit, vy);
    const p = pair(S.hit, vx);
    const [from, to] = tile.id === "reply" ? [p.to, p.from] : [p.from, p.to];
    const fields = tile.type === "m" ? { from, to } : tile.type === "t" ? { who: [p.near?.who] } : {};
    return { canvas: true, op: "into", ...spotOf(S, gp.key), add: { fields }, card: gapLine(S, f, gp), word: gp.key ? `Before ${name(gp.key)}` : "At the end" };
  }

  // --- the picture, in the page ------------------------------------------------------
  function wire(S) {
    const fig = S?.fig;
    if (!fig || S.k?.name !== "sequence" || fig.dataset.seq) return;
    fig.dataset.seq = "1";
    S.seq = true;
    const ops = diagramModel.kinds.ops;
    const act = diagramModel.kinds.act;
    const img = () => fig.querySelector(".md-mermaid-img");
    const at = (event) => (img() && S.hit ? diagramModel.overlay.math.at(S.hit, img().getBoundingClientRect(), event.clientX, event.clientY) : "");
    let editing = null;

    //: One field over the part, as the flowchart's (diagram-edges.js); Enter keeps, Escape leaves it as it was.
    function rename(key) {
      const box = S.hit?.boxes.find((b) => b.id === key);
      const layer = fig.querySelector(".dgm-overlay");
      if (!box || !layer || key[0] === "k") return false;
      editing?.();
      const [spot] = diagramModel.overlay.math.place(S.hit, img().getBoundingClientRect(), layer.getBoundingClientRect(), [box]);
      if (!spot) return false;
      const input = document.createElement("input");
      input.className = "dgm-rename";
      input.value = act.name(S, key);
      input.setAttribute("aria-label", "Name");
      input.maxLength = 120;
      const width = Math.max(120, Math.min(spot.w, 320));
      input.style.width = `${width}px`;
      layer.append(input);
      //: Centred on the part by its own height, which the theme sets (a fixed 16 put it 5 px high).
      input.style.transform = `translate(${spot.x + spot.w / 2 - width / 2}px, ${spot.y + spot.h / 2 - input.offsetHeight / 2}px)`;
      let over = false;
      const end = (keep) => {
        if (over) return;
        over = true;
        editing = null;
        input.remove();
        if (keep && input.value.trim()) act.rename(S, key, input.value.trim());
        fig.focus({ preventScroll: true });
      };
      editing = () => end(false);
      input.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Enter" || event.key === "Escape") event.preventDefault(), end(event.key === "Enter");
      });
      input.addEventListener("blur", () => end(true));
      input.scrollIntoView({ block: "nearest", inline: "nearest" });
      input.focus();
      input.select();
      return true;
    }
    S.seqRename = rename;

    // --- drags and the "+" ---------------------------------------------------------------------
    let drag = null;
    let dragged = -1e3;
    let plusAt = null;
    let btn = null;
    const hidePlus = () => btn?.classList.add("hidden");

    //: What a mouse press at the event is the start of: a head (reorder) or a lifeline below its head (a new message).
    function grab(event) {
      if (!img() || !S.hit) return null;
      const f = frameOf(S);
      const key = at(event);
      const box = key && S.hit.boxes.find((b) => b.id === key);
      if (box?.et === "participant") return { mode: "head", box };
      const n = near(S.hit, f.ux(event.clientX));
      const below = n && event.clientY > f.py(n.y + n.h / 2);
      return below && Math.abs(f.px(n.x) - event.clientX) <= 8 ? { mode: "line", box: n } : null;
    }
    //: The drag so far at the event: draws its mark and says where it would land.
    function aim(d, event) {
      const f = frameOf(S);
      const vx = f.ux(event.clientX);
      if (d.mode === "head") {
        const g = headGap(S.hit, vx, d.box.id);
        headLine(S, f, g);
        return g;
      }
      const to = near(S.hit, vx);
      const g = gap(S.hit, f.uy(event.clientY));
      rubber(S, f, d.box, to, g);
      return { ...g, to };
    }
    function land(d, res) {
      if (d.mode === "head") return act.shift(S, d.box.id, res.key);
      const tile = S.k.tiles.find((t) => t.id === "message");
      const key = act.add(S, tile, { spot: spotOf(S, res.key), fields: { from: d.box.who, to: res.to.who }, edit: false, sel: null });
      if (typeof key === "string") S.seqOpen = key;
    }
    function release(event) {
      if (!drag || event.pointerId !== drag.id) return;
      const d = drag;
      drag = null;
      fig.releasePointerCapture?.(event.pointerId);
      if (!d.live) return;
      dragged = event.timeStamp;
      const res = event.type === "pointerup" ? aim(d, event) : null;
      clear(S);
      if (res) land(d, res);
    }
    //: Ahead of the zoom's pan (diagram-view.js), as the flowchart's marquee is: a press on a head or a lifeline is not a pan.
    fig.addEventListener("pointerdown", (event) => {
      if (event.button || event.pointerType === "touch" || event.target.closest?.("input, button, .dock, .dgm-zoom")) return;
      const hold = grab(event);
      if (!hold) return;
      event.stopImmediatePropagation();
      fig.setPointerCapture?.(event.pointerId);
      drag = { ...hold, id: event.pointerId, x: event.clientX, y: event.clientY, live: false };
    }, true);
    fig.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      if (!drag.live && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 6) return;
      drag.live = true;
      hidePlus();
      aim(drag, event);
    });
    fig.addEventListener("pointerup", release);
    fig.addEventListener("pointercancel", release);

    //: The "+" (24 px) in the left margin of the gap under the pointer: the kind's Add menu, grouped, for that gap.
    function addAt(tile) {
      const key = act.add(S, tile, { spot: spotOf(S, plusAt), edit: false, sel: null });
      if (typeof key === "string") S.seqOpen = key;
    }
    function plusMenu() {
      const rows = S.k.tiles.filter((t) => t.type !== "a").map((t) => ({ label: `ph:${t.icon} ${t.name}`, group: t.group, title: `Adds ${t.about}.`, run: () => addAt(t) }));
      const r = btn.getBoundingClientRect();
      openMenuAtPoint(rows, "Add at this gap", r.right, r.bottom, btn);
    }
    function showPlus(event) {
      const layer = layerOf(S);
      if (!layer || !img() || !S.hit) return;
      const f = frameOf(S);
      const first = Math.max(0, ...heads(S.hit).map((p) => p.y + p.h / 2));
      const inside = event.clientX >= f.r.left && event.clientX <= f.r.right && event.clientY <= f.r.bottom && f.uy(event.clientY) > first;
      if (!inside) return hidePlus();
      if (!btn?.isConnected) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dgm-gap-plus hidden";
        btn.tabIndex = -1;
        btn.title = "Add a step here";
        btn.setAttribute("aria-label", "Add at this gap");
        btn.setAttribute("aria-haspopup", "menu");
        btn.innerHTML = '<i class="ph ph-plus" aria-hidden="true"></i>';
        btn.addEventListener("click", plusMenu);
        layer.append(btn);
      }
      const g = gap(S.hit, f.uy(event.clientY));
      plusAt = g.key;
      put(S, btn, f.r.left + 4, f.py(g.y) - 12, 24, 24);
      btn.classList.remove("hidden");
    }
    fig.addEventListener("pointermove", (event) => {
      if (event.pointerType !== "touch" && !event.buttons && !drag && !event.target.closest?.(".dgm-gap-plus, input")) showPlus(event);
    });
    fig.addEventListener("pointerleave", (event) => {
      if (!event.relatedTarget?.closest?.(".dgm-gap-plus")) hidePlus();
    });
    (fig.onzoom ||= []).push(hidePlus);


    //: First of the paint hooks, so the overlay that follows draws from this picture's boxes; run once now, for a picture drawn before this file loaded.
    const paint = () => {
      S.hit = img()?.mermaidSvg ? boxes(img().mermaidSvg, S.m, ops.key) : null;
      hidePlus();
      later();
    };
    //: A part just added by a drag or a "+" opens its name once its box can be placed: not before the image has its width (a
    //: dark picture decodes after the hooks ran), so the image's load and the zoom's paint ask again until it opens.
    const later = () => {
      const open = S.seqOpen;
      if (open && S.hit?.boxes.some((b) => b.id === open)) setTimeout(() => S.seqOpen === open && rename(open) && (S.seqOpen = null), 0);
    };
    (fig.onpaint ||= []).unshift(paint);
    (fig.onzoom ||= []).push(later);
    fig.addEventListener("load", later, true);
    paint();

    fig.addEventListener("click", (event) => {
      if (event.target.closest?.("input, button, .dgm-zoom") || event.timeStamp - dragged < 400) return;
      const key = at(event);
      if (key) act.select(S, key), S.mark?.();
    });
    fig.addEventListener("dblclick", (event) => {
      const key = at(event);
      if (key) event.preventDefault(), act.select(S, key), rename(key);
    });
    fig.addEventListener("keydown", (event) => {
      if (drag && event.key === "Escape") return (drag = null), clear(S);
      if (event.target !== fig || !S.sel || event.ctrlKey || event.metaKey) return;
      const key = S.sel;
      const run = event.altKey
        ? { ArrowUp: () => act.step(S, key, -1), ArrowDown: () => act.step(S, key, 1) }[event.key]
        : { Enter: () => rename(key), F2: () => rename(key), Delete: () => act.remove(S, key), Backspace: () => act.remove(S, key) }[event.key];
      if (!run) return;
      event.preventDefault();
      event.stopPropagation();
      run();
    });
  }

  diagramModel.seqCanvas = { wire, parts, order, boxes, gap, headGap, pair, near, over, clear };
})();
