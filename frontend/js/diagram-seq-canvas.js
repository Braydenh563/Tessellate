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
    return found.length ? { vb: read.vb, boxes: found } : null;
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
    //: First of the paint hooks, so the overlay that follows draws from this picture's boxes.
    (fig.onpaint ||= []).unshift(() => (S.hit = img()?.mermaidSvg ? boxes(img().mermaidSvg, S.m, ops.key) : null));
    const at = (event) => (img() && S.hit ? diagramModel.overlay.math.at(S.hit, img().getBoundingClientRect(), event.clientX, event.clientY) : "");
    let editing = null;

    //: One field over the part, as the flowchart's (diagram-edges.js); Enter keeps, Escape leaves it as it was.
    function rename(key) {
      const box = S.hit?.boxes.find((b) => b.id === key);
      const layer = fig.querySelector(".dgm-overlay");
      if (!box || !layer || key[0] === "k") return;
      editing?.();
      const [spot] = diagramModel.overlay.math.place(S.hit, img().getBoundingClientRect(), layer.getBoundingClientRect(), [box]);
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
    }
    S.seqRename = rename;

    fig.addEventListener("click", (event) => {
      if (event.target.closest?.("input, button, .dgm-zoom")) return;
      const key = at(event);
      if (key) act.select(S, key), S.mark?.();
    });
    fig.addEventListener("dblclick", (event) => {
      const key = at(event);
      if (key) event.preventDefault(), act.select(S, key), rename(key);
    });
    fig.addEventListener("keydown", (event) => {
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

  diagramModel.seqCanvas = { wire, parts, order, boxes };
})();
