(() => {
  // whiteboard-sketch-text.js: text inside shapes, fit-to-shape, connector labels and the sketch label editor.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: **Text inside a shape** (WHITEBOARD_PLAN.md decision 12). A rectangle,
  //: ellipse, diamond or triangle carries `label` in its own data blob, drawn as
  //: an SVG `<text>` inside the shape's own group: so it moves, resizes, turns,
  //: exports and undoes with the shape because it *is* the shape, not a text
  //: box parked on top that a drag could leave behind. Double-click the shape
  //: (or Enter with it selected) to type; Enter or Escape ends, Shift+Enter
  //: breaks the line. tldraw, Excalidraw, Miro and FigJam all do exactly this,
  //: and a flowchart is the first thing anybody draws with these four tools.
  const WB_SHAPE_LABEL_MAX = 500;

  //: Which shape a sketch is, for its label: the tool that drew it, or a
  //: rectangle for a closed path drawn before `shape` was stored. `null` for
  //: anything open (a pen stroke, a line, an arrow), which takes no label.
  function wbShapeLabelKind(parsed) {
    if (!parsed || typeof parsed.d !== "string") return null;
    if (WB_FILLABLE_SHAPES.has(parsed.shape)) return parsed.shape;
    const trimmed = parsed.d.trim();
    return /[Zz]\s*$/.test(trimmed) ? "rect" : null;
  }

  //: The part of a shape's box a label is written in: the whole width of a
  //: rectangle, the inscribed band of an ellipse (cos 45), the middle half of
  //: a diamond, and the lower half of a triangle, centred on its centroid
  //: (two thirds of the way down from the apex) where it is widest enough to
  //: hold a word.
  function wbShapeLabelArea(kind, bbox, area = null) {
    const pad = 8;
    //: `h` is the band the words may sit in up and down (the Vertical row);
    //: a shape's own default is its middle, so `h` only matters when moved.
    if (area && Number.isFinite(area.w)) {
      return {
        cx: bbox.minX + bbox.width * ((area.x || 0) + area.w / 2),
        cy: bbox.minY + bbox.height * ((area.y || 0) + (area.h ?? 1) / 2),
        w: Math.max(24, bbox.width * area.w - pad * 2),
        h: Math.max(0, bbox.height * (area.h ?? 1) - pad * 2),
      };
    }
    const cx = bbox.minX + bbox.width / 2;
    if (kind === "triangle") {
      return { cx, cy: bbox.minY + (bbox.height * 2) / 3, w: Math.max(24, bbox.width * 0.5 - pad), h: Math.max(0, bbox.height / 3) };
    }
    const share = kind === "circle" ? 0.7 : kind === "diamond" ? 0.5 : 1;
    return { cx, cy: bbox.minY + bbox.height / 2, w: Math.max(24, bbox.width * share - pad * 2), h: Math.max(0, bbox.height * share - pad * 2) };
  }

  //: Greedy word wrap against the label's own rendered width
  //: (`getComputedTextLength`, in the shape's own units, so zoom never enters
  //: into it). A line break typed with Shift+Enter is kept. Where the text
  //: cannot be measured (the board is hidden), an average glyph of 0.55em
  //: stands in, which is the same estimate the export's own wrap uses.
  function wbWrapShapeLabel(textEl, text, width, fontSize) {
    const measure = (s) => {
      textEl.textContent = s;
      const w = textEl.getComputedTextLength();
      return w > 0 ? w : s.length * fontSize * 0.55;
    };
    const lines = [];
    for (const paragraph of String(text).split("\n")) {
      const words = paragraph.split(/\s+/).filter(Boolean);
      if (!words.length) {
        lines.push("");
        continue;
      }
      let line = "";
      for (const word of words) {
        const next = line ? `${line} ${word}` : word;
        if (line && measure(next) > width) {
          lines.push(line);
          line = word;
        } else {
          line = next;
        }
      }
      lines.push(line);
    }
    return lines;
  }

  //: The drawn shape's box and the area its words may use, read off the live
  //: path; null when there is no path to read.
  function wbShapeLabelPlace(groupEl, label) {
    const bbox = wbPathBBox(groupEl.querySelector(".sketch-path")?.getAttribute("d") || "");
    if (!bbox) return null;
    let labelArea = null;
    try {
      labelArea = label.dataset.area ? JSON.parse(label.dataset.area) : null;
    } catch {
      labelArea = null;
    }
    const area = wbShapeLabelArea(label.dataset.kind, bbox, labelArea);
    return { bbox, area: wbFmtState.label?.area(label.__wbLook, area, bbox) ?? area };
  }

  //: Lays the label out from the path the group is drawing *now*, so a resize
  //: or a turn in flight re-wraps it, and clears the translation a move puts on
  //: it (`wbNudgeShapeLabel`). The wrap is kept on the element against the text
  //: and the width it was made for, so a render that changed nothing about the
  //: shape measures nothing.
  function wbLayoutShapeLabel(groupEl) {
    // A connector's label is laid out from the same live path (decision 13).
    wbLayoutLinkLabel(groupEl);
    const label = groupEl?.querySelector?.(":scope > .sketch-label");
    if (!label) return;
    label.removeAttribute("transform");
    const placed = wbShapeLabelPlace(groupEl, label);
    if (!placed) return;
    const area = wbLabelBand(label, placed.area);
    const fontSize = label.dataset.fit ? wbFitShapeLabel(label, area) : parseFloat(getComputedStyle(label).fontSize) || 16;
    const lineHeight = fontSize * (Number(label.dataset.lh) || 1.25);
    //: The face, weight and letter spacing change the widths the wrap measures, so they key it.
    //: Word wrap off (`label_wrap`, whiteboard-label.js): only a typed line break ends a line.
    const wrapWidth = label.__wbLook?.wrap === false ? Infinity : area.w;
    const key = `${label.__wbText}|${Math.round(area.w / 4)}|${wrapWidth}|${fontSize}|${label.style.fontFamily}|${label.style.fontWeight}|${label.style.letterSpacing}`;
    if (label.__wbKey !== key) {
      label.__wbLines = wbWrapShapeLabel(label, label.__wbText, wrapWidth, fontSize);
      label.__wbKey = key;
      label.replaceChildren(
        ...label.__wbLines.map((line, i) => {
          const span = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
          // A blank line keeps its height: an empty tspan collapses to nothing.
          span.textContent = line || " ";
          span.setAttribute("dy", i === 0 ? "0" : String(lineHeight));
          wbFmtState.textMore?.scriptSpans(span, fontSize);
          return span;
        })
      );
    }
    const lines = label.__wbLines.length;
    //: Words set beside a shape hug it, and words above or below sit on it (`area.align`, `area.valign`).
    const align = area.align || label.dataset.align;
    const top = area.valign ? area.valign === "top" : label.dataset.valign === "top";
    const bottom = area.valign ? area.valign === "bottom" : label.dataset.valign === "bottom";
    if (area.align) label.setAttribute("text-anchor", align === "left" ? "start" : "end");
    const x = align === "left" ? area.cx - area.w / 2 : align === "right" ? area.cx + area.w / 2 : area.cx;
    label.setAttribute("x", String(x));
    const block = (lines - 1) * lineHeight;
    //: Top and bottom put the first or last line's middle half a line in from
    //: the band's edge; a block taller than the band stays centred.
    const room = (area.h || 0) - block - lineHeight;
    const y = room > 0 && top ? area.cy - area.h / 2 + lineHeight / 2
      : room > 0 && bottom ? area.cy + area.h / 2 - lineHeight / 2 - block
        : area.cy - block / 2;
    label.setAttribute("y", String(y));
    for (const span of label.children) span.setAttribute("x", String(x));
    if (label.dataset.dir === "vertical") label.setAttribute("transform", `rotate(-90 ${area.cx} ${area.cy})`);
    wbFmtState.label?.backdrop(groupEl, label);
    wbFmtState.textMore?.mathLabel(groupEl, label, area, fontSize);
    wbFmtState.richLabel?.paint(groupEl, label, area, fontSize);
  }

  //: **Text that shrinks to fit its shape** (`label_fit`; draw.io's autosize
  //: only grows the box): from the size the text was given, a tenth smaller at
  //: a time until every line is as wide as the area and the block as tall, down
  //: to 6px, never larger than it was given. Kept on the element against the
  //: text and the area, so a render that changed neither measures nothing.
  function wbFitShapeLabel(label, area) {
    label.style.fontSize = label.dataset.size || "";
    const given = parseFloat(getComputedStyle(label).fontSize) || 16;
    const key = `${label.__wbText}|${Math.round(area.w)}|${Math.round(area.h)}|${given}|${label.style.fontFamily}|${label.style.fontWeight}`;
    if (label.__wbFit?.key !== key) {
      let size = given;
      for (;;) {
        label.style.fontSize = `${size}px`;
        const lines = wbWrapShapeLabel(label, label.__wbText, area.w, size);
        const widest = Math.max(...lines.map((line) => {
          label.textContent = line;
          return label.getComputedTextLength();
        }));
        const fits = widest <= area.w + 0.5 && (!area.h || lines.length * size * 1.25 <= area.h + 0.5);
        if (fits || size <= 6) break;
        size = Math.max(6, Math.floor(size * 9) / 10);
      }
      label.__wbFit = { key, size };
      label.__wbKey = null;
    }
    label.style.fontSize = `${label.__wbFit.size}px`;
    return label.__wbFit.size;
  }

  //: A move is only a translation, so a drag frame moves the label by the
  //: same offset rather than re-reading the path: the next render lays it out
  //: again from the saved path and drops this.
  function wbNudgeShapeLabel(groupEl, dx, dy) {
    const label = groupEl?.querySelector?.(":scope > .sketch-label");
    if (label) label.setAttribute("transform", `translate(${dx} ${dy})`);
    groupEl?.querySelector?.(":scope > .sketch-label-bg")?.setAttribute("transform", `translate(${dx} ${dy})`);
    groupEl?.querySelector?.(":scope > .sketch-label-math")?.setAttribute("transform", `translate(${dx} ${dy})`);
  }

  //: The ink the label is written in: the theme's own text colour on an
  //: unfilled shape (the stylesheet's `var(--text)`), and black or white on a
  //: filled one, whichever reads on that fill (`wbCoreInkFor`, the same rule a
  //: core topic's label follows on its branch colour). A fill under half
  //: opacity is mostly board, so it keeps the theme's ink.
  function wbShapeLabelInk(parsed) {
    if (!parsed?.fill || (parsed.fillOpacity != null && parsed.fillOpacity < 0.5)) return null;
    // A hatch or dots is mostly board, and a gradient has two ends: the ink is
    // only forced when both ends agree on it.
    if (parsed.fillStyle) return null;
    const to = wbHexColour(parsed.gradient?.to);
    if (to) return wbCoreInkFor(parsed.fill) === wbCoreInkFor(to) ? wbCoreInkFor(parsed.fill) : null;
    return wbCoreInkFor(parsed.fill);
  }

  //: A shape's gradient (`gradient: {to, dir}`) and fill style (`fillStyle`),
  //: draw.io's Fill section. Both are paint servers, so they live in a `<defs>`
  //: kept inside the shape's own group: the export clones each group, and the
  //: picture then carries what the board shows without a second pass.
  const WB_FILL_STYLES = Object.freeze(["hatch", "cross", "dots", "dashed", "zigzag"]);

  //: A plain hex colour or nothing: what a stored colour must be before it is
  //: set on a paint server, so a hand-edited row cannot put anything else there.
  function wbHexColour(value) {
    return typeof value === "string" && /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value) ? value : null;
  }

  //: The linear gradient's line across the shape's box (0 to 1 each way), from
  //: the fill colour at the start to the second colour at the end. Radial and
  //: anything unknown have no vector.
  function wbGradientVector(dir) {
    const vectors = {
      s: { x1: 0, y1: 0, x2: 0, y2: 1 },
      n: { x1: 0, y1: 1, x2: 0, y2: 0 },
      e: { x1: 0, y1: 0, x2: 1, y2: 0 },
      w: { x1: 1, y1: 0, x2: 0, y2: 0 },
    };
    return vectors[dir] || null;
  }

  //: One tile of a fill style as plain data (a tag and attributes per element),
  //: so the DOM is built with `createElementNS` and the shape is testable.
  //: A faint tint of the colour under every tile keeps a hatch reading as a fill.
  function wbFillPatternSpec(style, colour) {
    if (!WB_FILL_STYLES.includes(style)) return null;
    const line = (x1, y1, x2, y2) => ({ tag: "line", attrs: { x1, y1, x2, y2, stroke: colour, "stroke-width": 1.5 } });
    const tint = (size) => ({ tag: "rect", attrs: { x: 0, y: 0, width: size, height: size, fill: colour, "fill-opacity": 0.1 } });
    const specs = {
      hatch: { size: 8, rotate: 45, els: [tint(8), line(0, 0, 0, 8)] },
      cross: { size: 8, rotate: 45, els: [tint(8), line(0, 0, 0, 8), line(0, 0, 8, 0)] },
      dots: { size: 8, rotate: 0, els: [tint(8), { tag: "circle", attrs: { cx: 4, cy: 4, r: 1.6, fill: colour } }] },
      dashed: { size: 10, rotate: 0, els: [tint(10), line(0, 5, 6, 5)] },
      zigzag: { size: 10, rotate: 0, els: [tint(10), { tag: "path", attrs: { d: "M0 7 L2.5 3 L5 7 L7.5 3 L10 7", fill: "none", stroke: colour, "stroke-width": 1.5 } }] },
    };
    return specs[style];
  }

  //: Keeps the group's `<defs>` in step with its data and returns the paint to
  //: fill the path with, or null when the fill is plain. Rebuilt only when the
  //: inputs change (a key on the element), so a render that changes nothing
  //: touches nothing.
  function wbSyncFillDefs(groupEl, id, parsed) {
    const NS = "http://www.w3.org/2000/svg";
    let defs = groupEl.querySelector(":scope > defs.wb-fill-defs");
    const colour = wbHexColour(parsed?.fill);
    const to = wbHexColour(parsed?.gradient?.to);
    const dir = parsed?.gradient?.dir;
    const gradient = colour && to && (dir === "radial" || wbGradientVector(dir)) ? dir : null;
    const style = colour && !gradient && WB_FILL_STYLES.includes(parsed?.fillStyle) ? parsed.fillStyle : null;
    if (!gradient && !style) {
      defs?.remove();
      return null;
    }
    const paintId = `wbg-${id}`;
    const key = JSON.stringify([colour, to, gradient, style]);
    if (!defs) {
      defs = document.createElementNS(NS, "defs");
      defs.setAttribute("class", "wb-fill-defs");
      groupEl.prepend(defs);
    }
    if (defs.dataset.key === key) return `url(#${paintId})`;
    defs.dataset.key = key;
    defs.replaceChildren();
    const make = (tag, attrs, parent) => {
      const el = document.createElementNS(NS, tag);
      for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, String(value));
      parent.appendChild(el);
      return el;
    };
    if (gradient) {
      const vec = wbGradientVector(gradient);
      const server = vec
        ? make("linearGradient", { id: paintId, ...vec }, defs)
        : make("radialGradient", { id: paintId, cx: 0.5, cy: 0.5, r: 0.5 }, defs);
      make("stop", { offset: 0, "stop-color": colour }, server);
      make("stop", { offset: 1, "stop-color": to }, server);
    } else {
      const spec = wbFillPatternSpec(style, colour);
      const pattern = make("pattern", {
        id: paintId, width: spec.size, height: spec.size, patternUnits: "userSpaceOnUse",
        ...(spec.rotate ? { patternTransform: `rotate(${spec.rotate})` } : {}),
      }, defs);
      for (const el of spec.els) make(el.tag, el.attrs, pattern);
    }
    return `url(#${paintId})`;
  }

  //: The faces a shape's words and a text box can be set in (the Format panel's
  //: Font row): the map's three stacks and a handwritten one, all faces the
  //: systems this app runs on already ship, by name so no CSS is ever stored.
  const WB_ITEM_FONTS = Object.freeze({
    ...WB_MAP_FONTS,
    hand: MD_RUN_FONTS.hand,
  });

  //: Pure (node-tested): `%name%` in a label shows the item's own value of
  //: that name (draw.io's placeholders, from its Edit data). An unknown name
  //: stays as typed, so "100% of %x%" is not mangled. The stored label keeps the
  //: marks; only what is drawn, and so exported, is expanded. `builtin(name)`
  //: answers `date` and `page` (WHITEBOARD_PLAN.md section 3): an item's own
  //: property of that name wins, then the built-in, then the text as typed.
  function wbExpandPlaceholders(text, props, builtin) {
    const source = String(text ?? "");
    if (!source.includes("%")) return source;
    const own = props && typeof props === "object" ? props : null;
    if (!own && !builtin) return source;
    return source.replace(/%([A-Za-z][\w .-]{0,39})%/g, (mark, name) => {
      if (own && Object.prototype.hasOwnProperty.call(own, name)) return String(own[name]);
      const value = builtin && /^(date|page|length|width|height)$/.test(name) ? builtin(name) : "";
      return value ? String(value) : mark;
    });
  }

  //: `%date%` is today in the reader's own locale; `%page%` is the title of the
  //: smallest frame holding the item's centre (decision 22: frames are the
  //: pages), none when it sits in no frame. `%length%` is a connector's drawn
  //: length (a dimension line, INBOX 1313 row 7), read from its element so a
  //: drag shows it live; `%width%` and `%height%` are the item's box, rounded.
  function wbPlaceholderBuiltins(kind, item, groupEl) {
    return (name) => {
      if (name === "date") return new Date().toLocaleDateString(undefined, { dateStyle: "medium" });
      if (name === "length") return wbLinkLength(groupEl?.querySelector(".sketch-hitbox")?.getAttribute("d")) || "";
      const box = wbItemBBox(kind, item);
      if (!box) return "";
      if (name === "width" || name === "height") return Math.round(name === "width" ? box.maxX - box.minX : box.maxY - box.minY);
      const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
      let best = null;
      for (const f of wbState.objects || []) {
        if (f.kind !== "frame" || cx < f.x || cy < f.y || cx > f.x + f.width || cy > f.y + f.height) continue;
        if (!best || f.width * f.height < best.width * best.height) best = f;
      }
      return best ? wbFrameTitle(best) : "";
    };
  }

  //: A shape's or connector's hover text (`data.tip`): a native SVG `<title>`,
  //: so a pointer, a screen reader and the exported SVG all carry it.
  function wbSyncSketchTip(groupEl, parsed) {
    const tip = typeof parsed?.tip === "string" ? parsed.tip.trim() : "";
    let el = groupEl.querySelector(":scope > title.wb-sketch-tip");
    if (!tip) {
      el?.remove();
      return;
    }
    if (!el) {
      el = document.createElementNS("http://www.w3.org/2000/svg", "title");
      el.setAttribute("class", "wb-sketch-tip");
      groupEl.prepend(el);
    }
    if (el.textContent !== tip) el.textContent = tip;
  }

  //: The label's line spacing (a multiple of its size; the layout reads it from
  //: `data-lh`) and letter spacing (inline, so an export keeps it).
  function wbPaintLabelSpacing(label, parsed) {
    if (parsed.label_lh > 0) label.dataset.lh = String(parsed.label_lh);
    else delete label.dataset.lh;
    label.style.letterSpacing = parsed.label_ls ? `${parsed.label_ls}px` : "";
    wbPaintTextDir(label, parsed.label_dir, parsed.label_alpha);
  }

  //: Right to left or set vertically, and the words' own opacity (draw.io's
  //: Text tab; INBOX 1510(a)): inline, so an export keeps them. Only the two
  //: named values reach a style. A box's HTML text turns with `writing-mode`; a
  //: shape's SVG label is laid out in lines, so it is turned as draw.io turns
  //: one (`horizontal=0`): wrapped to the shape's height, then rotated a quarter
  //: back (`wbLayoutShapeLabel`).
  function wbPaintTextDir(el, dir, alpha) {
    const svg = Boolean(el.namespaceURI?.endsWith("/svg"));
    el.style.direction = dir === "rtl" ? "rtl" : "";
    el.style.writingMode = dir === "vertical" && !svg ? "vertical-rl" : "";
    if (svg && dir === "vertical") el.dataset.dir = "vertical";
    else if (el.dataset) delete el.dataset.dir;
    el.style.opacity = alpha > 0 && alpha < 1 ? String(alpha) : "";
  }

  //: The band a label wraps in: a turned label's lines run up the shape, so its
  //: width is the band's height (a band with no height keeps its width).
  function wbLabelBand(label, area) {
    return label.dataset.dir === "vertical" ? { ...area, w: area.h || area.w, h: area.w } : area;
  }

  //: Adds, updates or removes a shape's label for one render.
  function wbPaintShapeLabel(groupEl, parsed, sketch) {
    const kind = wbShapeLabelKind(parsed);
    const text = kind && typeof parsed.label === "string" ? wbExpandPlaceholders(parsed.label, parsed.props, sketch && wbPlaceholderBuiltins("sketch", sketch)) : "";
    let label = groupEl.querySelector(":scope > .sketch-label");
    if (!text) {
      label?.remove();
      groupEl.querySelector(":scope > .sketch-label-math")?.remove();
      wbFmtState.label?.drop(groupEl);
      return;
    }
    if (!label) {
      label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "sketch-label");
      // Presentation attributes rather than stylesheet rules for the two that
      // place the text: the export clones this node into a standalone SVG,
      // where no stylesheet follows it.
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("dominant-baseline", "central");
      label.setAttribute("pointer-events", "none");
      groupEl.appendChild(label);
    }
    label.dataset.kind = kind;
    if (parsed?.label_area) label.dataset.area = JSON.stringify(parsed.label_area);
    else delete label.dataset.area;
    label.__wbText = text;
    label.style.fill = parsed.label_color || wbShapeLabelInk(parsed) || "";
    label.style.fontSize = parsed.label_size ? `${parsed.label_size}px` : "";
    label.dataset.size = label.style.fontSize;
    if (parsed.label_fit) label.dataset.fit = "1";
    else delete label.dataset.fit;
    label.style.fontWeight = parsed.label_bold ? "700" : "";
    label.style.fontStyle = parsed.label_italic ? "italic" : "";
    //: Underline and strikethrough, and a face by name (draw.io's Text tab;
    //: whiteboard-1018). Inline style, so the export's cloned SVG keeps them.
    label.style.textDecoration = [parsed.label_underline && "underline", parsed.label_strike && "line-through"].filter(Boolean).join(" ");
    label.style.fontFamily = WB_ITEM_FONTS[parsed.label_font] || "";
    wbPaintLabelSpacing(label, parsed);
    const align = ["left", "right"].includes(parsed.label_align) ? parsed.label_align : "center";
    label.dataset.align = align;
    if (parsed.label_valign === "top" || parsed.label_valign === "bottom") label.dataset.valign = parsed.label_valign;
    else delete label.dataset.valign;
    label.setAttribute("text-anchor", align === "left" ? "start" : align === "right" ? "end" : "middle");
    wbFmtState.label?.paint(label, parsed);
    wbFmtState.richLabel?.mark(label, parsed); // Rich text (whiteboard-label-rich.js)
    wbLayoutShapeLabel(groupEl);
  }

  //: Types into a shape (decision 12): an editor over the shape's label area,
  //: in the card layer so it takes the caret above the drawing, through the
  //: board's one in-place text recipe (`wbBeginTextEdit` / `wbEditedText`).
  function wbEditShapeLabel(sketch) {
    const parsed = wbSketchParsedData(sketch);
    const kind = wbShapeLabelKind(parsed);
    const bbox = kind ? wbPathBBox(parsed.d) : null;
    if (!bbox) return;
    const area = wbShapeLabelArea(kind, bbox, parsed.label_area || null);
    const kit = wbFmtState.label;
    wbOpenSketchLabelEditor(sketch, parsed, {
      box: kit ? kit.editBox(kit.look(parsed), area, bbox) : { x: area.cx - area.w / 2, y: area.cy - Math.max(bbox.height, 24) / 2, w: area.w, h: Math.max(bbox.height, 24) },
      ink: wbShapeLabelInk(parsed),
      multiline: true,
      max: WB_SHAPE_LABEL_MAX,
      name: "Text in this shape",
      said: ["Text added to the shape.", "Text taken off the shape."],
    });
  }

  //: **One editor for a sketch's words**, a shape's text (decision 12) or a
  //: connector's label (decision 13): placed over `box` in board units, one
  //: undo step and only for a real change, Enter or Escape to finish (Shift+Enter
  //: breaks the line where `multiline`), the board's keys kept off it.
  function wbOpenSketchLabelEditor(sketch, parsed, { box, ink, multiline, max, name, said, extraClass = "" }) {
    const layer = document.getElementById("wb-html-layer");
    if (!sketch || !parsed || !layer || document.querySelector(".wb-shape-label-editor")) return;
    const group = document.querySelector(`.sketch-group[data-id="${sketch.id}"]`);
    const editor = document.createElement("div");
    editor.className = `wb-shape-label-editor ${extraClass}`.trim();
    editor.setAttribute("role", "textbox");
    editor.setAttribute("aria-multiline", multiline ? "true" : "false");
    editor.setAttribute("aria-label", name);
    // Through CSSOM: the CSP refuses a `style=` attribute.
    editor.style.width = `${box.w}px`;
    editor.style.height = `${box.h}px`;
    editor.style.transform = `translate(${box.x}px, ${box.y}px)`;
    if (ink) editor.style.color = ink;
    editor.textContent = parsed.label || "";
    layer.appendChild(editor);
    group?.classList.add("wb-shape-label-editing");
    wbBeginTextEdit(editor);
    const range = document.createRange();
    range.selectNodeContents(editor);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);

    let done = false;
    const finish = async () => {
      if (done) return;
      done = true;
      let text = wbEditedText(editor);
      if (!multiline) text = text.replace(/\s*\n\s*/g, " ");
      text = text.replace(/^\s+|\s+$/g, "").slice(0, max);
      editor.remove();
      group?.classList.remove("wb-shape-label-editing");
      if (text === (parsed.label || "")) return;
      const before = WB_KIND_INFO.sketch.payload(sketch);
      await wbSaveSketchProps(sketch, { label: text || undefined });
      wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
      //: A shape's words that do not fit make the shape taller, as one step
      //: with the words (the same grow as "Grow to fit the words").
      if (text && wbShapeLabelKind(parsed) && !parsed.label_fit && !parsed.label_pos) {
        renderWhiteboardNow();
        await wbGrowShapeToLabel(sketch);
      }
      wbScheduleRender();
      wbAnnounce(text ? said[0] : said[1]);
    };
    editor.addEventListener("keydown", (event) => {
      // The board's keys must not act on what is being typed.
      event.stopPropagation();
      if (event.key === "Escape" || (event.key === "Enter" && (!event.shiftKey || !multiline))) {
        event.preventDefault();
        editor.blur();
      }
    });
    editor.addEventListener("pointerdown", (event) => event.stopPropagation());
    editor.addEventListener("dblclick", (event) => event.stopPropagation());
    editor.addEventListener("blur", finish);
  }

  //: **A label on a connector** (WHITEBOARD_PLAN.md decision 13): "yes" and
  //: "no" on the two arrows out of a diamond, which a flowchart cannot do
  //: without. `label` in the link's own data, one line, drawn at the middle of
  //: the line's shaft in the map's edge-label recipe (the ink, stroked in the
  //: card colour underneath so it reads where it crosses its own line). A link
  //: on a map between two topics is the map's (its ring, its words), so this is
  //: the board's links only.
  const WB_LINK_LABEL_MAX = 80;

  function wbLinkTakesLabel(sketch, parsed) {
    if (!parsed || !String(parsed.type || "").startsWith("link-")) return false;
    return !(sketch && wbMapCrossLinkInfo(sketch.id));
  }


  function wbLinkMidpoint(d, t = 0.5) {
    const shaft = String(d || "").split(/\s(?=M)/)[0];
    if (!shaft) return null;
    if (!wbLinkMeasurePath || !wbLinkMeasurePath.isConnected) {
      const host = document.getElementById("wb-svg-layer");
      if (!host) return null;
      wbLinkMeasurePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      wbLinkMeasurePath.setAttribute("class", "wb-link-measure");
      wbLinkMeasurePath.setAttribute("visibility", "hidden");
      wbLinkMeasurePath.setAttribute("aria-hidden", "true");
      host.appendChild(wbLinkMeasurePath);
    }
    wbLinkMeasurePath.setAttribute("d", shaft);
    try {
      const length = wbLinkMeasurePath.getTotalLength();
      const p = wbLinkMeasurePath.getPointAtLength(length * t);
      return { x: p.x, y: p.y };
    } catch {
      return null;
    }
  }

  //: A link's drawn length in board units, rounded: the same hidden path as
  //: `wbLinkMidpoint`, set to the line and measured whole.
  function wbLinkLength(d) {
    if (!wbLinkMidpoint(d, 0)) return null;
    try {
      return Math.round(wbLinkMeasurePath.getTotalLength());
    } catch {
      return null;
    }
  }

  function wbLayoutLinkLabel(groupEl) {
    wbFmtState.drawMore?.layoutLabel2(groupEl);
    const label = groupEl?.querySelector?.(":scope > .wb-link-label:not(.wb-link-label2)");
    if (!label) return;
    //: A label that shows the length is worded again on every layout, so a drag
    //: of either end shows the new number as it moves, not after the drop.
    const src = groupEl.__wbMeasured;
    if (src) {
      const text = wbExpandPlaceholders(src.parsed.label, src.parsed.props, wbPlaceholderBuiltins("sketch", src.sketch, groupEl));
      if (text && label.textContent !== text) label.textContent = text;
    }
    const t = groupEl.dataset.labelT ? Number(groupEl.dataset.labelT) : 0.5;
    //: The plain line (the hitbox): a jump's gap would cut the drawn shaft.
    const lineD = groupEl.querySelector(".sketch-hitbox")?.getAttribute("d");
    //: **Text on path** (`label_path`): the words are a `textPath` along a copy of the line, read left to right (the
    //: copy runs backwards when the line does), and `startOffset` is where along it they centre. The copy lives in the
    //: group's own `defs`, so the export's clone carries it.
    const run = groupEl.dataset.labelPath === "1" ? wbShaftPoints(lineD) : [];
    const own = label.querySelector("textPath");
    if (run.length < 2) {
      if (own) label.textContent = own.textContent;
      label.removeAttribute("dy");
    } else {
      const flip = run[run.length - 1].x < run[0].x;
      const path = flip ? run.slice().reverse() : run;
      const id = `wb-tp-${groupEl.dataset.id}`;
      let defs = groupEl.querySelector(":scope > defs.wb-tp-defs");
      if (!defs) {
        defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.setAttribute("class", "wb-tp-defs");
        defs.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "path")).setAttribute("id", id);
        groupEl.insertBefore(defs, groupEl.firstChild);
      }
      defs.firstChild.setAttribute("d", "M " + path.map((q) => `${Math.round(q.x * 100) / 100} ${Math.round(q.y * 100) / 100}`).join(" L "));
      let along = own;
      if (!along) {
        const words = label.textContent;
        label.textContent = "";
        along = label.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "textPath"));
        along.setAttribute("href", `#${id}`);
        along.textContent = words;
      }
      const share = Number.isFinite(t) ? t : 0.5;
      along.setAttribute("startOffset", `${Math.round((flip ? 1 - share : share) * 1000) / 10}%`);
      label.setAttribute("dy", "-0.6em");
      return;
    }
    const p = wbLinkMidpoint(lineD, Number.isFinite(t) ? t : 0.5);
    if (!p) return;
    label.setAttribute("x", String(p.x));
    label.setAttribute("y", String(p.y));
  }

  //: **A connector's label slides along its line by its own words** (INBOX
  //: 1404; Miro and Lucid do this; draw.io keeps the place as a share of the
  //: line's length). The drag moves the label to the nearest point of the
  //: drawn line and saves it as `label_t` (0 at the start, 1 at the end), so
  //: the label keeps its place when either end moves. A press that does not
  //: move is a click, which bubbles to the connector (select); a double-click
  //: edits the words. Only the Select tool drags, so the other tools still
  //: reach the connector under the label.
  function wbWireLinkLabelDrag(label, groupEl) {
    const sketchOf = () => d3.select(groupEl).datum();
    let t = 0.5, moved = false, before = null;
    d3.select(label)
      .on("dblclick", (event) => {
        if (window.currentTool !== "select") return;
        event.stopPropagation();
        event.preventDefault();
        const sketch = sketchOf();
        selectWbItem("sketch", sketch.id);
        wbEditLinkLabel(sketch);
      })
      .call(
        d3.drag()
          .clickDistance(WB_CLICK_SLOP)
          .filter((event) => !event.button && !wbIsSecondTouch(event) && window.currentTool === "select")
          .on("start", (event) => {
            event.sourceEvent.stopPropagation();
            moved = false;
            before = WB_KIND_INFO.sketch.payload(sketchOf());
            t = Number(groupEl.dataset.labelT) || 0.5;
          })
          .on("drag", (event) => {
            moved = true;
            const [px, py] = d3.pointer(event, groupEl);
            t = wbLinkNearestT(groupEl.querySelector(".sketch-hitbox")?.getAttribute("d"), { x: px, y: py });
            groupEl.dataset.labelT = String(t);
            wbLayoutLinkLabel(groupEl);
          })
          .on("end", async () => {
            if (!moved) return;
            moved = false;
            const sketch = sketchOf();
            const rounded = Math.round(t * 100) / 100;
            await wbSaveSketchProps(sketch, { label_t: Math.abs(rounded - 0.5) < 0.01 ? undefined : rounded });
            wbPushUndo({ action: "move", kind: "sketch", id: sketch.id, before });
            selectWbItem("sketch", sketch.id);
            wbScheduleRender();
          })
      );
  }

  function wbPaintLinkLabel(groupEl, sketch, parsed) {
    wbFmtState.drawMore?.paintLabel2(groupEl, sketch, parsed);
    const text = wbLinkTakesLabel(sketch, parsed) && typeof parsed.label === "string" ? wbExpandPlaceholders(parsed.label, parsed.props, wbPlaceholderBuiltins("sketch", sketch, groupEl)) : "";
    groupEl.__wbMeasured = text && parsed.label.includes("%length%") ? { sketch, parsed } : null;
    let label = groupEl.querySelector(":scope > .wb-link-label:not(.wb-link-label2)");
    if (!text) {
      label?.remove();
      return;
    }
    if (!label) {
      label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "wb-link-label");
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("dominant-baseline", "central");
      groupEl.appendChild(label);
      wbWireLinkLabelDrag(label, groupEl);
    }
    if (label.textContent !== text) label.textContent = text;
    //: The label's own look (size, colour, bold, chip); unset means the stylesheet's.
    label.style.fontSize = Number(parsed.label_size) > 0 ? `${Number(parsed.label_size)}px` : "";
    label.style.fontWeight = parsed.label_bold ? "700" : "";
    label.style.fill = typeof parsed.label_color === "string" ? parsed.label_color : "";
    label.classList.toggle("wb-link-label-chip", Boolean(parsed.label_chip));
    groupEl.dataset.labelT = String(wbLinkLabelT(parsed));
    groupEl.dataset.labelPath = parsed.label_path ? "1" : "";
    wbLayoutLinkLabel(groupEl);
  }

  function wbEditLinkLabel(sketch) {
    let parsed = null;
    try {
      parsed = JSON.parse(sketch?.data);
    } catch {
      parsed = null;
    }
    if (!wbLinkTakesLabel(sketch, parsed)) return;
    const group = document.querySelector(`.sketch-group[data-id="${sketch.id}"]`);
    const p = wbLinkMidpoint((group?.querySelector(".sketch-hitbox") || group?.querySelector(".sketch-path"))?.getAttribute("d"), wbLinkLabelT(parsed));
    if (!p) return;
    const w = 180;
    const h = 32;
    wbOpenSketchLabelEditor(sketch, parsed, {
      box: { x: p.x - w / 2, y: p.y - h / 2, w, h },
      ink: null,
      multiline: false,
      max: WB_LINK_LABEL_MAX,
      name: "Label on this connector",
      said: ["Label added to the connector.", "Label taken off the connector."],
      extraClass: "wb-link-label-editor",
    });
  }

  function wbSketchParsedData(sketch) {
    try {
      const parsed = JSON.parse(sketch.data);
      return parsed && typeof parsed.d === "string" ? parsed : null;
    } catch {
      return null;
    }
  }

  //: Merges `partial` into the sketch's own parsed data blob and saves the
  //: whole thing back: the general form `wbSaveSketchD` (move/resize) and
  //: the properties panel (colour/width/arrowhead) both reduce to. Unlike
  //: `wbSketchParsedData` (which deliberately stays strict to `.d`-shaped
  //: data for the move/resize code that assumes it), this also accepts a
  //: link sketch: asked for directly ("customisable links... colour"),
  //: which silently did nothing before this: the colour/width properties-
  //: panel rows already called this function for *any* selected sketch, but
  //: a link has no `.d`, so `wbSketchParsedData` returned null and the save
  //: was a silent no-op.
  async function wbSaveSketchProps(sketch, partial) {
    let parsed;
    try {
      const candidate = JSON.parse(sketch.data);
      if (candidate && (typeof candidate.d === "string" || (candidate.type || "").startsWith("link-"))) {
        parsed = candidate;
      }
    } catch {
      parsed = null;
    }
    if (!parsed) return;
    wbFmtState.inkMore?.follow(parsed, partial.d, wbPathBBox);
    Object.assign(parsed, partial);
    sketch.data = JSON.stringify(parsed);
    try {
      const saved = await apiJson(`/whiteboard/sketches/${sketch.id}`, {
        method: "PUT",
        body: JSON.stringify({
          data: sketch.data, board_id: sketch.board_id, x: sketch.x, y: sketch.y, z: sketch.z,
          group_id: sketch.group_id ?? null,
        }),
      });
      Object.assign(sketch, saved);
    } catch {
      recordBrowserLog("WARN", [`[Whiteboard] sketch ${sketch.id} is stale: reloading the board`]);
      await fetchWhiteboardState();
      wbScheduleRender();
    }
  }

  async function wbSaveSketchD(sketch, newD) {
    await wbSaveSketchProps(sketch, { d: newD });
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbShapeLabelKind, wbShapeLabelPlace, wbLayoutShapeLabel, wbNudgeShapeLabel, WB_FILL_STYLES, wbHexColour, wbGradientVector, wbSyncFillDefs, WB_ITEM_FONTS, wbExpandPlaceholders, wbPlaceholderBuiltins, wbSyncSketchTip, wbPaintTextDir, wbPaintShapeLabel, wbEditShapeLabel, wbLinkTakesLabel, wbLinkMidpoint, wbLayoutLinkLabel, wbPaintLinkLabel, wbEditLinkLabel, wbSketchParsedData, wbSaveSketchProps, wbSaveSketchD });
})();
