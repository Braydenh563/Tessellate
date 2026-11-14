(() => {
  // whiteboard-export.js: the board and map export (SVG, PNG, PDF, copy as image, the Export dialog), the outline import and the
  // map-from-notes review, moved out of whiteboard.js whole (L286). Wrapped whole: only what other files call goes on `window`.
  // Names whiteboard.js's state, `toast` and the selection helpers at run time only; nothing here runs at load.
  // --- Whiteboard export (asked for directly: "a way to screen clip a or a
  // selected area and export as an image/pdf/svg etc") -----------------------
  //
  // No marquee/multi-select exists yet (HANDOVER's own open list), so "a
  // selected area" becomes two concrete scopes instead: what's currently
  // framed on screen (the literal "screen clip" reading), or the whole board
  // regardless of pan/zoom. Both are built the same way, as a real SVG
  // string, sized to board-space coordinates, which then serves all three
  // formats: written out directly for .svg, rasterized through an off-screen
  // <canvas> for .png, and for PDF, handed to the browser's own Print →
  // "Save as PDF" rather than hand-rolling PDF bytes, which is what every
  // pure-client web app already does for this and needs no library to do.
  function wbSvgEscape(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // A rough character-count wrap, no live font metrics are available while
  // building a string that isn't in the DOM yet. Good enough for a legible
  // label in an export, not typeset text. `maxLines` caps height (a card's
  // own export label is deliberately short; a text box gets more room).
  function wbSvgWrapLines(text, maxWidth, maxLines = 6, charWidth = 7) {
    const charsPerLine = Math.max(10, Math.floor(maxWidth / charWidth));
    const words = String(text).split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    for (const word of words) {
      const next = (line + " " + word).trim();
      if (next.length > charsPerLine && line) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
      if (lines.length >= maxLines) break;
    }
    if (line && lines.length < maxLines) lines.push(line);
    return lines;
  }

  function wbSvgText(lines, x, y, { fontSize = 13, fill = "#1f2430", lineHeight, fontFamily = "sans-serif", fontWeight, fontStyle } = {}) {
    const dy = lineHeight || fontSize + 3;
    const tspans = lines
      .map((l, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : dy}">${wbSvgEscape(l)}</tspan>`)
      .join("");
    return `<text x="${x}" y="${y}" font-family="${wbSvgEscape(fontFamily)}" font-size="${fontSize}"${Object.entries({
      "font-weight": fontWeight && fontWeight !== "400" && fontWeight !== "normal" ? String(fontWeight) : "",
      "font-style": fontStyle === "italic" ? "italic" : "",
    }).filter(([, v]) => v).map(([k, v]) => ` ${k}="${wbSvgEscape(v)}"`).join("")} fill="${fill}">${tspans}</text>`;
  }


  //: A text box's words with their runs, as SVG (INBOX 1403): wrapped by the
  //: same rough character count as `wbSvgWrapLines` but per word, each word a
  //: run of pieces, and every piece its own `<tspan>` with its own size, face
  //: and fill; a highlight is a rect behind it, at the position that count
  //: gives. `x`, `y` are the first line's left and baseline.
  function wbSvgRunLines(text, { x, y, maxWidth, maxLines, fontSize, fill, lineHeight, charWidth }) {
    const words = [];
    let word = null;
    for (const c of wbFmtState.textMore?.markScripts(wbRunChars(text)) ?? wbRunChars(text)) {
      if (/\s/.test(c.ch)) {
        word = null;
      } else {
        if (!word) words.push((word = []));
        const last = word[word.length - 1];
        if (last && JSON.stringify(last.attrs) === JSON.stringify(c.attrs)) last.text += c.ch;
        else word.push({ text: c.ch, attrs: c.attrs });
      }
    }
    const wide = (piece) => piece.text.length * charWidth * ((piece.attrs.size || fontSize) / fontSize) * (piece.attrs.script ? 0.7 : 1);
    const lines = [];
    let line = [];
    let used = 0;
    for (const pieces of words) {
      const w = pieces.reduce((sum, piece) => sum + wide(piece), 0);
      const gap = line.length ? charWidth : 0;
      if (line.length && used + gap + w > maxWidth) {
        lines.push(line);
        line = [];
        used = 0;
      }
      if (lines.length >= maxLines) break;
      line.push(pieces);
      used += (line.length > 1 ? charWidth : 0) + w;
    }
    if (line.length && lines.length < maxLines) lines.push(line);
    const rects = [];
    const spans = [];
    let top = y;
    lines.forEach((words, row) => {
      const tallest = Math.max(fontSize, ...words.flat().map((p) => p.attrs.size || 0));
      if (row) top += lineHeight * (tallest / fontSize);
      let at = x;
      words.forEach((pieces, index) => {
        if (index) at += charWidth;
        for (const piece of pieces) {
          const size = (piece.attrs.size || fontSize) * (piece.attrs.script ? 0.7 : 1);
          const rise = piece.attrs.script === "sup" ? -fontSize * 0.35 : piece.attrs.script === "sub" ? fontSize * 0.2 : 0;
          const w = wide(piece);
          if (piece.attrs.hl) {
            rects.push(`<rect x="${at}" y="${top - size * 0.85}" width="${w}" height="${size * 1.15}" rx="2" fill="${WB_RUN_SWATCHES[piece.attrs.hl]}" fill-opacity="0.25"/>`);
          }
          const face = piece.attrs.font ? ` font-family="${wbSvgEscape(MD_RUN_FONTS[piece.attrs.font])}"` : "";
          const ink = piece.attrs.ink ? WB_RUN_INK[piece.attrs.ink] : fill;
          spans.push(`<tspan x="${at}" y="${top + rise}" font-size="${size}"${face} fill="${ink}">${wbSvgEscape(piece.text)}</tspan>`);
          at += w;
        }
      });
    });
    return `${rects.join("")}<text font-family="sans-serif" font-size="${fontSize}" fill="${fill}">${spans.join("")}</text>`;
  }

  //: **An export is painted in the colours on screen** (the owner, 2026-09-24:
  //: "I exported a mindmap selection as an image to the library, the mindmap
  //: nodes turned white??"). The node and card fills below were hard-coded
  //: `#ffffffee` with `#1f2430` ink, which is the light theme's look: in dark
  //: mode, and on any map whose look was changed, the export drew white boxes
  //: on the board's dark ground. So each box reads its fill, edge and ink off
  //: the live element's computed style, which is what the renderer painted.
  //:
  //: Through a 1px canvas rather than passed on as the computed string: a
  //: surface here is a `color-mix()`, which a computed style reports in the
  //: `color(srgb ...)` form, and whether a rasterised SVG's `fill` attribute
  //: takes that form is the browser's business. A canvas pixel is plain sRGB
  //: in every engine, and it is what the picture ends up as anyway.
  let wbExportColourCtx = null;
  function wbExportColour(value) {
    if (!value) return null;
    const srgb = /^color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.e-]+))?\)$/.exec(value.trim());
    if (srgb) {
      const [r, g, b] = srgb.slice(1, 4).map((v) => Math.round(Math.min(1, Math.max(0, Number(v))) * 255));
      const a = srgb[4] == null ? 1 : Math.min(1, Math.max(0, Number(srgb[4])));
      if (a === 0) return "none";
      return a === 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${a.toFixed(3)})`;
    }
    if (!wbExportColourCtx) {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      wbExportColourCtx = canvas.getContext("2d", { willReadFrequently: true });
    }
    const ctx = wbExportColourCtx;
    ctx.clearRect(0, 0, 1, 1);
    //: A value the canvas cannot parse leaves `fillStyle` unchanged, so a
    //: sentinel says "not understood" rather than painting the sentinel.
    ctx.fillStyle = "#010203";
    ctx.fillStyle = value;
    if (ctx.fillStyle === "#010203" && !/^#010203$/i.test(value)) return null;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    if (a === 0) return "none";
    return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`;
  }

  //: The fill, edge and ink of one drawn box. `inkEl` is the element that holds
  //: its words, which is not the box itself on a map topic. `null` for an
  //: element that is not drawn (a topic culled off screen), so the caller can
  //: fall back to one that is.
  //: A text box's, sticky's or card's fill as painted: its `bg` at its `bg_alpha`
  //: (INBOX 1486). "" leaves the stylesheet's own paper; 0 is a real answer (the
  //: fill is see-through) and an absent value is solid, as it always was.
  function wbPaperPaint(data) {
    const bg = data?.bg || "";
    const alpha = data?.bg_alpha;
    if (!bg || bg === "transparent" || alpha == null || alpha >= 1) return bg;
    return `color-mix(in srgb, ${bg} ${Math.round(Math.max(0, alpha) * 100)}%, transparent)`;
  }

  function wbExportPaint(el, inkEl) {
    if (!el) return null;
    const style = getComputedStyle(el);
    const edgeWidth = parseFloat(style.borderTopWidth) || 0;
    return {
      fill: wbExportColour(style.backgroundColor) || "none",
      edge: edgeWidth > 0 ? wbExportColour(style.borderTopColor) : null,
      ink: wbExportColour(getComputedStyle(inkEl || el).color) || "#1f2430",
    };
  }

  //: A map topic's effect in the exported picture: a filter attribute for its
  //: box, with the filter defined once in `parts`. The glow's ring is a rect
  //: drawn under the box. Nothing for a topic drawn without a box.
  function wbExportTopicEffect(effect, colour, rx, ry, size, parts) {
    if (effect === "shadow") {
      return wbExportShadow(parts, null);
    }
    if (effect !== "glow") return "";
    const ink = wbSvgEscape(colour);
    const id = `wb-export-glow-${String(colour).replace(/[^a-z0-9]/gi, "")}`;
    const def = `<defs><filter id="${id}" x="-40%" y="-40%" width="180%" height="180%">` +
      `<feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="${ink}" flood-opacity="0.45"/></filter></defs>`;
    if (!parts.includes(def)) parts.push(def);
    parts.push(`<rect x="-3" y="-3" width="${size.w + 6}" height="${size.h + 6}" rx="${Math.round((rx + 3) * 10) / 10}" ry="${Math.round((ry + 3) * 10) / 10}" fill="${ink}" fill-opacity="0.22" />`);
    return ` filter="url(#${id})"`;
  }

  //: A topic's Phosphor icon as a PNG data URL, drawn from the glyph the
  //: topic shows (its `::before` in the icon font), in the colour it is drawn
  //: in; null for no icon, an emoji (that travels as text) or a font not ready.
  function wbExportTopicGlyph(topicEl) {
    const iconEl = topicEl?.querySelector(".wb-map-node-icon.ph");
    if (!iconEl || iconEl.hidden) return null;
    const before = getComputedStyle(iconEl, "::before");
    const glyph = (before.content || "").replace(/^["']|["']$/g, "");
    if (!glyph || glyph === "none") return null;
    const canvas = document.createElement("canvas");
    canvas.width = 48;
    canvas.height = 48;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.font = `40px ${before.fontFamily}`;
    ctx.fillStyle = getComputedStyle(iconEl).color || "#1f2430";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(glyph, 24, 26);
    return canvas.toDataURL("image/png");
  }

  //: **The export's one reader of the live page** (LEDGER L272). The picture used
  //: to be built with `getComputedStyle`, `querySelector` and `getBoundingClientRect`
  //: calls scattered through `wbBuildExportSvg`, so what the builder knew about a
  //: board and what it read off the screen could not be told apart. Now every
  //: read of the drawn page is a method here, each answering in plain data (a
  //: colour, a size, a box, a string of markup); `wbBuildExportSvg` takes the
  //: board's data from `wbState` and the look from this, and touches no element.
  //: An item the page is not drawing (culled off screen) answers with the
  //: fallback the data gives, as it did when the reads were inline.
  function wbExportLook() {
    //: **Each item's element is found once** (W30 B23): a `querySelector` per item walked the
    //: whole page for every one of them, 28 of the 40 ms an export of 500 objects took. One walk per
    //: kind builds the index; the first element with an id wins, as the lookups did.
    const idIndex = (selector) => {
      const found = new Map();
      for (const el of document.querySelectorAll(selector)) if (!found.has(el.dataset.id)) found.set(el.dataset.id, el);
      return found;
    };
    const objectEls = idIndex("#wb-html-layer .wb-object");
    const sketchEls = idIndex(".sketch-group");
    const cardEls = idIndex(".node-card");
    const container = document.getElementById("whiteboard-container");
    //: A card or topic that is not in the DOM (culled off screen) takes the
    //: paint of one that is, which is the theme's own card look. The last topic
    //: in the layer rather than the first, because the first is usually the
    //: trunk, which wears its branch colour as a fill.
    const cardFallback = wbExportPaint(document.querySelector("#wb-html-layer .node-card"));
    const topics = document.querySelectorAll("#wb-html-layer .wb-object.wb-map-node");
    const lastTopic = topics[topics.length - 1];
    const topicFallback = wbExportPaint(lastTopic, lastTopic?.querySelector(".wb-map-text"));
    const elOf = (obj) => objectEls.get(String(obj.id));
    //: **A callout and labels travel as drawn** (L377; the export left both out):
    //: each is placed from its live box inside the card, as the picture is, and
    //: the words move down to where the card really sets them under a callout.
    function topicExtras(cardEl, size) {
      if (!cardEl) return { callout: null, tags: [] };
      const cardBox = cardEl.getBoundingClientRect();
      const k = cardBox.width ? size.w / cardBox.width : 1;
      const inCard = (el) => { const b = el.getBoundingClientRect(); return { x: (b.left - cardBox.left) * k, y: (b.top - cardBox.top) * k, w: b.width * k, h: b.height * k }; };
      const fill = (el) => wbExportColour(getComputedStyle(el).backgroundColor);
      const c = cardEl.querySelector(".wb-map-callout");
      const words = cardEl.querySelector(".wb-map-text");
      const callout = c && !c.hidden && c.textContent.trim()
        ? { box: inCard(c), fill: fill(c), text: c.textContent.trim(), wordsY: words ? inCard(words).y : null } : null;
      const tags = [...cardEl.querySelectorAll(".wb-map-tags .wb-map-tag")].map((tag) => ({ box: inCard(tag), fill: fill(tag), text: tag.textContent }));
      return { callout, tags };
    }
    return {
      //: The board's ground, as the stylesheet resolved the chosen colour.
      background: container ? getComputedStyle(container).backgroundColor : "#1b1f2c",
      //: A frame's edge and title ink, as drawn; null for either when it is not.
      frame(frame) {
        const frameEl = elOf(frame);
        const titleEl = frameEl?.querySelector(".wb-frame-title");
        return {
          edge: frameEl ? wbExportColour(getComputedStyle(frameEl).borderTopColor) : null,
          ink: titleEl ? wbExportColour(getComputedStyle(titleEl).color) : null,
        };
      },
      //: A map's boundaries or summaries, one markup string each, the paint on as attributes.
      structure(selector) {
        const out = [];
        for (const el of document.querySelectorAll(selector)) {
          const clone = el.cloneNode(true);
          const look = getComputedStyle(el);
          for (const attr of ["class", "style", "data-topic"]) clone.removeAttribute(attr);
          clone.setAttribute("fill", wbExportColour(look.fill) || "none");
          clone.setAttribute("stroke", wbExportColour(look.stroke) || "none");
          clone.setAttribute("stroke-width", look.strokeWidth || "1");
          if (look.fillOpacity && look.fillOpacity !== "1") clone.setAttribute("fill-opacity", look.fillOpacity);
          if (look.strokeDasharray && look.strokeDasharray !== "none") clone.setAttribute("stroke-dasharray", look.strokeDasharray);
          if (el.tagName === "text") {
            clone.setAttribute("font-size", look.fontSize);
            clone.setAttribute("font-family", look.fontFamily);
            clone.setAttribute("paint-order", "stroke");
          }
          out.push(clone.outerHTML);
        }
        return out;
      },
      //: The map's tree edges, already real SVG paths in board coordinates (that is
      //: the whole reason `wbRenderMapEdges` draws them as SVG instead of on a
      //: canvas), cloned rather than recomputed so they cannot disagree with the
      //: screen. Painted as drawn: a branch is a filled, tapered ribbon in its
      //: branch's colour (a stylesheet rule over an inline custom property), and
      //: the export used to force `fill="none"` and a grey stroke, so every branch
      //: came out as a pair of thin grey outlines. The class and the custom
      //: property do not survive the clone, so the computed paint goes on as attributes.
      mapEdges() {
        const out = [];
        for (const edge of document.querySelectorAll(".wb-map-edges .wb-map-edge")) {
          const clone = edge.cloneNode(true);
          clone.removeAttribute("class");
          const look = getComputedStyle(edge);
          const paint = (value) => (value && !value.startsWith("url(") ? wbExportColour(value) : null);
          clone.removeAttribute("style");
          clone.setAttribute("fill", paint(look.fill) || "none");
          clone.setAttribute("stroke", paint(look.stroke) || "none");
          clone.setAttribute("stroke-width", look.strokeWidth || "2");
          if (look.opacity && look.opacity !== "1") clone.setAttribute("opacity", look.opacity);
          if (look.strokeDasharray && look.strokeDasharray !== "none") clone.setAttribute("stroke-dasharray", look.strokeDasharray);
          out.push(clone.outerHTML);
        }
        return out;
      },
      //: A sketch already exists as real SVG, cloned as-is rather than
      //: reinterpreted, so a stroke's colour/width/opacity (including the
      //: highlighter's own translucency) survives untouched. A shape's text
      //: (decision 12) is painted by the stylesheet, which does not travel into a
      //: standalone SVG: its ink, size and face go on as attributes, read off the
      //: label as drawn. Null when the sketch is not on the page.
      sketch(sketch) {
        const el = sketchEls.get(String(sketch.id));
        if (!el) return null;
        const clone = el.cloneNode(true);
        clone.removeAttribute("class");
        //: Maths in a label (whiteboard-text-more.js) is a live overlay; the picture keeps the label's source words.
        clone.querySelectorAll(":scope > .sketch-label-math").forEach((node) => node.remove());
        const labels = el.querySelectorAll(":scope > .sketch-label, :scope > .wb-link-label");
        const copies = clone.querySelectorAll(":scope > .sketch-label, :scope > .wb-link-label");
        labels.forEach((label, i) => {
          const look = getComputedStyle(label);
          const copy = copies[i];
          if (!copy) return;
          copy.removeAttribute("class");
          copy.removeAttribute("style");
          wbFmtState.effects?.keepShadow(label, copy);
          copy.removeAttribute("data-kind");
          copy.setAttribute("fill", wbExportColour(look.fill) || "#1f2430");
          copy.setAttribute("font-size", look.fontSize);
          copy.setAttribute("font-family", look.fontFamily);
          if (look.fontWeight && look.fontWeight !== "400") copy.setAttribute("font-weight", look.fontWeight);
          if (look.fontStyle === "italic") copy.setAttribute("font-style", "italic");
          //: A connector's label is haloed in the card colour (decision 13).
          if (look.paintOrder && look.paintOrder.startsWith("stroke") && look.stroke !== "none") {
            copy.setAttribute("stroke", wbExportColour(look.stroke) || "none");
            copy.setAttribute("stroke-width", look.strokeWidth);
            copy.setAttribute("paint-order", "stroke");
          }
        });
        //: A rich label (whiteboard-label-rich.js) becomes real SVG text, so the picture shows its words as drawn.
        wbFmtState.richLabel?.exportInto(el, clone);
        return clone.outerHTML;
      },
      //: A note card's measured size and paint. `h` is `el.offsetHeight`, the live
      //: card, so an expanded card exports what it shows and a collapsed one what
      //: it shows.
      card(node) {
        const el = cardEls.get(String(node.id));
        return { w: el ? el.offsetWidth : 250, h: el ? el.offsetHeight : 150, paint: wbExportPaint(el) || cardFallback };
      },
      //: A picture's corners (Format > Corners), read off the drawn element as a box's are.
      radii(obj) {
        return wbSvgBoxRadii(elOf(obj), obj.data, obj.width, obj.height);
      },
      //: A map topic as drawn: its size, paint, corner, effect, picture box and icon glyph.
      topic(obj) {
        const size = wbMapNodeSize(obj);
        const el = elOf(obj);
        //: The box is measured off the live node rather than recomputed from the
        //: stylesheet's padding: two rects in the same units give the picture's
        //: place inside the card exactly, at any zoom, without this having to
        //: know what `--space-2` is today.
        const picture = obj.data.image ? el?.querySelector(".wb-map-node-picture") : null;
        const card = picture ? picture.closest(".wb-object") : null;
        let pictureBox = null;
        if (picture && card && !picture.hidden) {
          const cardBox = card.getBoundingClientRect();
          const picBox = picture.getBoundingClientRect();
          const scale = cardBox.width ? size.w / cardBox.width : 1;
          pictureBox = {
            x: (picBox.left - cardBox.left) * scale, y: (picBox.top - cardBox.top) * scale,
            w: picBox.width * scale, h: picBox.height * scale,
          };
        }
        return {
          size,
          paint: wbExportPaint(el, el?.querySelector(".wb-map-text")) || topicFallback,
          corner: el ? getComputedStyle(el).borderTopLeftRadius : "8px",
          effect: el?.dataset.shape === "none" ? null : el?.dataset.effect,
          //: A cut shape paints its face on `::after` and its rim on `::before` (L365).
          shape: el?.dataset.shape,
          //: Its level's type, read off the drawn label (L365).
          type: el ? (({ fontSize, fontWeight, fontStyle }) => ({ fontSize, fontWeight, fontStyle }))(getComputedStyle(el.querySelector(".wb-map-text") || el)) : null,
          face: /^(diamond|hexagon|chevron)$/.test(el?.dataset.shape || "") ? wbExportColour(getComputedStyle(el, "::after").backgroundColor) : null,
          rim: /^(diamond|hexagon|chevron)$/.test(el?.dataset.shape || "") ? wbExportColour(getComputedStyle(el, "::before").backgroundColor) : null,
          pictureBox,
          glyph: wbExportTopicGlyph(el),
          ...topicExtras(el, size),
        };
      },
      //: A text box, sticky or sticker's paper, fold and ink. A box with no colour
      //: of its own writes in the theme's ink, which is near-white on a dark board.
      text(obj) {
        const el = elOf(obj);
        const textEl = obj.data.color ? null : el?.querySelector(".wb-text-content");
        return {
          ink: textEl ? wbExportColour(getComputedStyle(textEl).color) : null,
          backdrop: wbSvgBoxBackdrop(el, obj.data, obj.width, obj.height),
          fold: wbSvgStickyFold(el, obj.width, obj.height),
        };
      },
      //: A table's cells, as markup.
      table(obj) {
        return wbSvgTable(elOf(obj), obj);
      },
    };
  }

  function wbBuildExportSvg(scope, { transparent = false, pad = 0, skipSketches = null } = {}) {
    //: A selection export is the selection plus 24px, not the bar's 40.
    const bounds = scope === "selection" ? wbSelectionBounds(24)
      : scope === "visible" ? wbVisibleBounds() : wbBoardBounds();
    //: `pad`: the PNG dialog's border, board units of ground all round the content.
    const box = bounds || wbBoardBounds();
    const minX = box.minX - pad, minY = box.minY - pad, width = box.width + pad * 2, height = box.height + pad * 2;
    const onlyKeys = scope === "selection" ? wbSelectedKeys() : null;
    //: Everything read off the drawn page comes through this one object.
    const look = wbExportLook();
    const bgColor = look.background;

    const parts = [
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${width} ${height}" ` +
        `width="${Math.round(width)}" height="${Math.round(height)}">`,
      //: No ground at all for a transparent PNG (FEAT-14), so the picture
      //: sits on whatever it is pasted onto.
      transparent ? "" : `<rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="${bgColor}" />`,
    ];

    //: Frames first (decision 14): they sit under everything they hold, in the
    //: file as on the board. The edge and title ink are read off the frame as
    //: drawn, since the stylesheet does not travel into a standalone SVG.
    const drawFrame = (frame) => {
      if (frame.kind !== "frame") return;
      if ((onlyKeys && !onlyKeys.has(wbMultiKey("object", frame.id))) || wbItemHidden("object", frame)) return;
      const { edge, ink } = look.frame(frame);
      parts.push(
        `<rect x="${frame.x}" y="${frame.y}" width="${frame.width}" height="${frame.height}" rx="6" fill="none" ` +
          `stroke="${wbSvgEscape(edge || "#8a90a0")}" stroke-width="1.5" />`
      );
      parts.push(wbSvgText([wbFrameTitle(frame)], frame.x, frame.y - 6, { fontSize: 12, fill: ink || "#8a90a0" }));
    };
    //: **One order for the file and the board** (wbz-1026): frames, then the
    //: map's structure, then every other item in `wbStackOrder`, so what is
    //: on top on the board is on top in the file.
    const stack = wbStackOrder();
    for (const e of stack) if (wbStackBand(e.kind, e.item) === 0) drawFrame(e.item);

    // A map's branch colours, and its tree edges, both computed once for the
    // whole export. The edges are cloned out of the live DOM rather than
    // recomputed: they are already real SVG paths in board coordinates (that is
    // the whole reason `wbRenderMapEdges` draws them as SVG instead of on a
    // canvas), so cloning them is exact and cannot disagree with what is on
    // screen. First in the list, so they sit under every node.
    const exportMapIndex = wbIsMap() ? wbMapIndex() : null;
    const exportMapColors = exportMapIndex ? wbMapNodeColors(exportMapIndex) : null;
    //: A map's boundaries (decision 19) under its lines, its summaries over
    //: them, as drawn, the paint read off each one like the lines below.
    const structure = (selector) => parts.push(...look.structure(selector));
    if (exportMapIndex) structure(".wb-map-boundaries > *");
    if (exportMapIndex) parts.push(...look.mapEdges());

    if (exportMapIndex) structure(".wb-map-summaries > *");

    // Sketches already exist as real SVG, cloned as-is rather than
    // reinterpreted, so a stroke's colour/width/opacity (including the
    // highlighter's own translucency) survives into the export untouched.
    const drawSketch = (sketch) => {
      if ((onlyKeys && !onlyKeys.has(wbMultiKey("sketch", sketch.id))) || wbSketchHiddenOnBoard(sketch) || skipSketches?.has(sketch.id)) return;
      const markup = look.sketch(sketch);
      if (markup) parts.push(markup);
    };

    // Cards are the HTML layer, which doesn't survive SVG rasterization the
    // way real SVG does, a simplified rect + label stands in for the live
    // card, matching what the live card itself shows (raw content, truncated;
    // it has no private-note masking of its own to match either).
    const exportEntriesById = new Map(allEntries.map((e) => [String(e.id), e]));
    const drawNode = (node) => {
      if ((onlyKeys && !onlyKeys.has(wbMultiKey("node", node.id))) || wbItemHidden("node", node)) return;
      const entry = exportEntriesById.get(String(node.entry_id));
      const { w, h, paint: cardPaint } = look.card(node);
      const label = entry ? notePreviewText(entry.content || "") : `Note ${node.entry_id}`;
      parts.push(`<g transform="translate(${node.x}, ${node.y})">`);
      parts.push(
        `<rect width="${w}" height="${h}" rx="10" fill="${cardPaint?.fill || "#ffffffcc"}" ` +
          `stroke="${cardPaint?.edge || "#8888aa"}" stroke-width="1.5" />`
      );
      //: **As many lines as the card itself is showing**, from the card's own
      //: measured height. This used to take the first 160 characters and then
      //: wrap them into at most six lines, which was two fixed answers to a
      //: question the box already answers: a card someone had dragged to 700px
      //: and expanded to show the whole note still exported six lines of it.
      //: `h` is `el.offsetHeight`, the live card, so an expanded card exports
      //: what it shows and a collapsed one exports what it shows.
      //: 24 is the text's own baseline offset, 16 the line height `wbSvgText`
      //: uses at font size 13, and 12 leaves the last line clear of the rounded
      //: bottom edge.
      const cardLines = Math.max(1, Math.floor((h - 24 - 12) / 16));
      parts.push(wbSvgText(wbSvgWrapLines(label || "Empty note", w - 28, cardLines), 14, 24,
        { fill: cardPaint?.ink || "#1f2430" }));
      parts.push("</g>");
    };

    // Images and text boxes, the two new object kinds, neither tied to a
    // note. An <image> element rasterizes cleanly since the URL is always
    // same-origin (isRenderableUrl already guarantees that server-side); a
    // text box gets the same simplified rect+label treatment a card does,
    // but honours the colour/size it was actually given rather than a fixed
    // look, since those are the whole point of a text box.
    const drawObject = (obj) => {
      if ((onlyKeys && !onlyKeys.has(wbMultiKey("object", obj.id))) || wbItemHidden("object", obj)) return;
      //: Drawn before the sketches, above.
      if (obj.kind === "frame") return;
      const alpha = obj.data?.alpha != null && obj.data.alpha < 1 ? ` opacity="${obj.data.alpha}"` : "";
      //: An SVG filter, not a `style` attribute: the CSP refuses inline style
      //: (tests/test_security_boundaries.py). Defined once, before its first use.
      let shadow = "";
      if (obj.data?.shadow) {
        shadow = wbExportShadow(parts, obj.data);
      }
      parts.push(`<g transform="translate(${obj.x}, ${obj.y})"${alpha}${shadow}>`);
      if (obj.kind === "image" && obj.data.url) {
        // `mediaSrc`, not the bare url: rasterizing this SVG loads it through
        // a plain `<img>` (see `wbRasterizeSvg`), which never attaches
        // X-Auth-Token: the same gap that made the image never render on the
        // board itself, here too.
        //: A picture with rounded corners (Format > Corners) is clipped to the
        //: same path the board draws, read off the drawn element as a box's is.
        const radii = look.radii(obj);
        //: A crop to a shape wins over rounded corners, as it does on the board.
        const pix = wbPixel(obj.data, obj.width, obj.height);
        const cropPath = wbCropPath(obj.data.crop, pix.w, pix.h, obj.data.trim);
        const clip = cropPath || radii.some((r) => r > 0) ? `wb-export-clip-${obj.id}` : "";
        if (clip) parts.push(`<clipPath id="${clip}"><path d="${cropPath || wbSvgRoundedPath(pix.w, pix.h, radii)}" /></clipPath>`);
        const turn = pix.svg;
        const filter = pix.filter;
        parts.push(
          `<image href="${wbSvgEscape(mediaSrc(obj.data.url))}" width="${pix.w}" height="${pix.h}" ` +
            `preserveAspectRatio="xMidYMid slice"${clip ? ` clip-path="url(#${clip})"` : ""}` +
            `${turn ? ` transform="${turn}"` : ""}${filter ? ` filter="${filter}"` : ""} />`
        );
        //: The picture's border (Format > Border), stroked inside the box over the picture.
        const edge = obj.data.border_width > 0 ? obj.data.border_width : 0;
        if (edge) {
          const inner = wbSvgRoundedPath(Math.max(1, obj.width - edge), Math.max(1, obj.height - edge), radii);
          parts.push(`<path d="${inner}" transform="translate(${edge / 2}, ${edge / 2})" fill="none" stroke="${wbSvgEscape(obj.data.border_color && obj.data.border_color !== "transparent" ? obj.data.border_color : "#333333")}" stroke-width="${edge}" />`);
        }
      } else if (obj.kind === "diagram") {
        //: What the board shows, already drawn (`wbDiagramDataUrl`); an edge
        //: while it has not been drawn yet, never an empty gap.
        const url = wbDiagramDataUrl(obj);
        parts.push(url ? `<image href="${wbSvgEscape(url)}" width="${obj.width}" height="${obj.height}" preserveAspectRatio="xMidYMid meet" />`
          : `<rect width="${obj.width}" height="${obj.height}" fill="none" stroke="#9aa3b5" stroke-dasharray="6 4" />`);
      } else if (WB_MAP_KINDS.has(obj.kind)) {
        // A map node exports as what it looks like: a rounded box with the
        // branch's colour down its leading edge and its label inside. Without
        // this branch a map exported as an empty `<g>` per node: every PNG and
        // SVG of a mind map came out blank, which is the same "stored, served
        // and not drawn" gap this whole section exists to close, one layer down.
        const topic = look.topic(obj);
        const size = topic.size;
        const colour = exportMapColors?.get(obj.id) || "#8888aa";
        const topicPaint = topic.paint;
        //: **Its own shape, not always the rounded box** (MINDMAP_PLAN, the
        //: owner's list 2026-10-10: the rounded rectangle "its export"): the
        //: corner the topic is drawn with, read off the drawn topic, so a
        //: pill, an ellipse, a box and the rounded rectangle each export as
        //: themselves. A percentage is of the box (the ellipse's 50%).
        const corner = topic.corner;
        const pct = /%$/.test(corner) ? parseFloat(corner) / 100 : null;
        const rx = pct != null ? size.w * pct : Math.min(parseFloat(corner) || 0, size.h / 2, size.w / 2);
        const ry = pct != null ? size.h * pct : rx;
        //: **Its effect travels too** (MINDMAP_PLAN 15, row 8): the shadow as
        //: the board's own export shadow, the glow as a ring and a blur in the
        //: branch colour, read off the drawn topic as the shape is.
        //: **The cut shapes are polygons, as the canvas clips them** (L365): a
        //: diamond, hexagon or chevron paints its face on `::after` and its
        //: rim on `::before`, with the topic's own background off, so the rect
        //: path read "none" for all three and drew them as bare boxes. Same
        //: outlines as library-lazy.css's clip-paths; a cloud keeps its ellipse.
        const cut = topic.shape;
        const fx = wbExportTopicEffect(topic.effect, colour, rx, ry, size, parts);
        const fill = topicPaint?.fill || "#ffffffee";
        const edge = wbSvgEscape(topicPaint?.edge || colour);
        const sw = size.w, sh = size.h;
        const slant = Math.min(20, sw * 0.22);
        const outline = cut === "diamond" ? `M ${sw / 2} 0 L ${sw} ${sh / 2} L ${sw / 2} ${sh} L 0 ${sh / 2} Z`
          : cut === "hexagon" ? `M ${slant} 0 L ${sw - slant} 0 L ${sw} ${sh / 2} L ${sw - slant} ${sh} L ${slant} ${sh} L 0 ${sh / 2} Z`
          : cut === "chevron" ? `M 0 0 L ${sw - slant} 0 L ${sw} ${sh / 2} L ${sw - slant} ${sh} L 0 ${sh} Z` : "";
        if (outline) {
          const face = topic.face || fill;
          const rim = topic.rim || colour;
          parts.push(`<path d="${outline}" fill="${face}" stroke="${wbSvgEscape(rim)}" stroke-width="1.5"${fx} />`);
        } else if (cut === "underline") {
          parts.push(`<path d="M 0 ${sh} L ${sw} ${sh}" stroke="${wbSvgEscape(colour)}" stroke-width="2"${fx} />`);
        } else if (cut !== "none") {
          parts.push(
            `<rect width="${sw}" height="${sh}" rx="${Math.round(rx * 10) / 10}" ry="${Math.round(ry * 10) / 10}" fill="${fill}" ` +
              `stroke="${edge}" stroke-width="1.5"${fx} />`
          );
        }
        parts.push(
          `<rect width="4" height="${size.h}" rx="2" fill="${wbSvgEscape(colour)}" />`
        );
        //: **A topic that is a picture exports as the picture** (§12.1 item 2's
        //: fourth). Without this a map of photographs came out as a page of
        //: empty boxes with captions, which is the same "stored, served and not
        //: drawn" gap the branch above this one exists to close.
        //:
        //: The box is measured off the live node rather than recomputed from the
        //: stylesheet's padding: the element is on screen (`wbMapNodeSize` has
        //: just read it for the card's own size), and two rects in the same
        //: units give the picture's place inside the card exactly, at any zoom,
        //: without this function having to know what `--space-2` is today.
        //: `mediaSrc`, for the reason the image object above gives: the raster
        //: pass loads the SVG through a plain `<img>`, which sends no header, so
        //: the token has to be in the url.
        let labelTop = 22;
        if (topic.pictureBox) {
          const { x: px, y: py, w: pw, h: ph } = topic.pictureBox;
          parts.push(
            `<image href="${wbSvgEscape(mediaSrc(obj.data.image))}" x="${px}" y="${py}" ` +
              `width="${pw}" height="${ph}" preserveAspectRatio="xMidYMid slice" />`
          );
          labelTop = py + ph + 16;
        }
        //: **A callout and labels travel as drawn** (L377; the export left both out): each is
        //: placed from its live box inside the card, as the picture above is, and the words
        //: move down to where the card really sets them when a callout sits over them.
        const { callout, tags } = topic;
        if (callout) {
          const c = callout.box;
          parts.push(
            `<rect x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" rx="6" fill="${wbSvgEscape(callout.fill || "#eef1fb")}" stroke="${wbSvgEscape(colour)}" />` +
            wbSvgText(wbSvgWrapLines(callout.text, c.w - 16, 4, 6.2), c.x + 8, c.y + 15, { fontSize: 12, fill: topicPaint?.ink || "#1f2430", lineHeight: 15 })
          );
          if (callout.wordsY != null) labelTop = callout.wordsY + 15;
        }
        for (const tag of tags) {
          const t = tag.box;
          parts.push(
            `<rect x="${t.x}" y="${t.y}" width="${t.w}" height="${t.h}" rx="${t.h / 2}" fill="${wbSvgEscape(tag.fill || "#eef1fb")}" stroke="${wbSvgEscape(colour)}" />` +
            wbSvgText([tag.text], t.x + t.w / 2, t.y + t.h / 2 + 4, { fontSize: 11, fill: topicPaint?.ink || "#1f2430" }).replace("<text ", '<text text-anchor="middle" ')
          );
        }
        //: A task's box travels as the ballot-box glyph (MINDMAP_PLAN.md
        //: decision 15): the icon font does not follow the topic into the file.
        const box = obj.data?.task === "done" ? "☑ " : obj.data?.task === "open" ? "☐ " : "";
        //: And its number on a numbered map (decision 17), as the canvas
        //: draws it: after the box, before the label.
        const place = wbMapNumberOf(exportMapIndex, obj.id);
        //: An emoji icon is a character, so it travels (decision 46); a
        //: Phosphor one is the icon font's, which does not.
        const icon = obj.data?.icon && !/^[a-z0-9-]+$/.test(obj.data.icon) ? `${obj.data.icon} ` : "";
        //: A Phosphor icon travels as its own picture (row 8): the glyph drawn
        //: once from the font the topic is showing it in, before the label.
        const glyph = topic.glyph;
        const textLeft = glyph ? 34 : 14;
        if (glyph) {
          parts.push(`<image href="${glyph}" x="14" y="${labelTop - 13}" width="16" height="16" />`);
        }
        const lines = wbSvgWrapLines(box + (place ? `${place} ` : "") + icon + wbMapLabel(obj), size.w - 28 - (textLeft - 14), 4, 7.5);
        //: In the map's own face when it has one (§13e's remainder): the file is
        //: the second place a map's text is drawn, and a serif map exported in
        //: sans-serif is two pictures of one map.
        //: **Its level's type**, read off the drawn label (L365): a main topic
        //: is larger and bolder than a leaf, a core topic bolder again; the
        //: export drew every topic at 14px regular. Line height follows.
        const textStyle = topic.type;
        const level = textStyle ? Math.min(40, Math.max(9, parseFloat(textStyle.fontSize) || 14)) : 14;
        parts.push(wbSvgText(lines, textLeft, labelTop, {
          fontSize: level, fill: topicPaint?.ink || "#1f2430", lineHeight: Math.round(level * 1.2),
          fontFamily: wbMapFontStack() || "sans-serif",
          fontWeight: textStyle?.fontWeight, fontStyle: textStyle?.fontStyle,
        }));
      } else if (obj.kind === "text" && obj.data.sticker) {
        //: A sticker exports as its glyph, centred, at the size it is drawn.
        const size = wbStickerSize(obj);
        parts.push(
          `<text x="${obj.width / 2}" y="${obj.height / 2}" font-size="${size}" text-anchor="middle" ` +
            `dominant-baseline="central">${wbSvgEscape(obj.data.content || "")}</text>`
        );
      } else if (obj.kind === "text") {
        const fontSize = obj.data.font_size || 16;
        const pad = obj.data.pad ?? 10;
        const lines = wbSvgWrapLines(obj.data.content || "", obj.width - 2 * pad, 20, fontSize * 0.55);
        //: A text box with no colour of its own writes in the theme's ink, which
        //: is near-white on a dark board: read it off the box, as above.
        const paper = look.text(obj);
        parts.push(paper.backdrop);
        parts.push(paper.fold);
        const inkFill = obj.data.color || paper.ink || "#1f2430";
        parts.push(
          new RegExp(MD_RUN.source).test(obj.data.content || "") || (obj.data.md && wbFmtState.textMore?.hasScripts(obj.data.content))
            ? wbSvgRunLines(obj.data.content, {
                x: pad, y: fontSize + pad - 2, maxWidth: obj.width - 2 * pad, maxLines: 20,
                fontSize, fill: inkFill, lineHeight: fontSize * 1.25, charWidth: fontSize * 0.55,
              })
            : wbSvgText(lines, pad, fontSize + pad - 2, { fontSize, fill: inkFill, lineHeight: fontSize * 1.25 })
        );
      } else if (obj.kind === "table") {
        parts.push(look.table(obj));
      }
      if (obj.data?.votes) parts.push(wbSvgVotes(obj));
      if (obj.data?.stamps) parts.push(wbMapLazy.svgStamps(obj));
      parts.push("</g>");
    };
    for (const e of stack) {
      if (wbStackBand(e.kind, e.item) === 0) continue;
      if (e.kind === "sketch") drawSketch(e.item);
      else if (e.kind === "node") drawNode(e.item);
      else drawObject(e.item);
    }

    parts.push("</svg>");
    return { svg: parts.join(""), width, height };
  }

  //: **A picture on a board has to travel inside the file that shows it.** The
  //: export SVG names each picture by its `/media/...` url, and an SVG loaded
  //: through `<img>` (how `wbRasterizeSvg` draws it) never fetches anything
  //: outside itself, so every PNG, PDF and library copy of a board came out
  //: with an empty space where its pictures were (OPEN.md; reproduced with
  //: `scratchpad/ui-sweeps/wbexportimage.js`: the pixel in the middle of a red
  //: picture read the board's white). The same file saved as .svg pointed at an
  //: address that only means something inside this app. Each distinct url is
  //: fetched once, with the cookie the page already holds, and written back as
  //: a data URL; one that cannot be fetched keeps its address, so a missing
  //: picture costs that picture and never the export.
  async function wbInlineSvgImages(svg) {
    const unescapeAttr = (s) => s.replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    const urls = [...new Set([...svg.matchAll(/<image href="([^"]+)"/g)].map((m) => m[1]))].filter((u) => !u.startsWith("data:"));
    let out = svg;
    for (const escaped of urls) {
      try {
        // `api()` (F5), silent: a picture that will not load keeps its address.
        const res = await api(unescapeAttr(escaped), { silent: true });
        const blob = await res.blob();
        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result));
          reader.onerror = () => reject(reader.error);
          reader.readAsDataURL(blob);
        });
        out = out.split(`<image href="${escaped}"`).join(`<image href="${dataUrl}"`);
      } catch {
        // Keep the address: this picture is missing from the export, the rest is not.
      }
    }
    return out;
  }

  //: `quality` (0 to 1) only means something to the lossy types; PNG ignores it.
  async function wbRasterizeSvg(svgInput, width, height, mime, quality) {
    //: The root's own size set to the canvas's, so a 2x or 3x export
    //: (FEAT-14) is drawn at that size from the vectors rather than drawn at
    //: 1x and stretched.
    const svgString = (await wbInlineSvgImages(svgInput)).replace(
      /^(<svg\b[^>]*?) width="[^"]*" height="[^"]*"/,
      `$1 width="${Math.max(1, Math.round(width))}" height="${Math.max(1, Math.round(height))}"`
    );
    return new Promise((resolve, reject) => {
      const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width));
        canvas.height = Math.max(1, Math.round(height));
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob(
          (result) => (result ? resolve(result) : reject(new Error("Couldn't rasterize the board."))),
          mime,
          quality
        );
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Couldn't rasterize the board."));
      };
      img.src = url;
    });
  }

  //: Markdown outline / OPML, straight from `GET /boards/{id}/export` (§9.3).
  //:
  //: The **server** renders both, and that is deliberate: the same two formats
  //: are what `import_board` reads back and what the AI's `read_mindmap` builds
  //: its outline from, so a second renderer here would be a third opinion of
  //: what this map says, and the one nobody would think to keep in step.
  //:
  //: `api()` rather than `apiJson()` because the response is a text file with a
  //: `Content-Disposition`, not JSON; `saveFile` is the app's own download
  //: helper and is what makes this work in the desktop shell, where a browser
  //: download has nowhere to land.
  async function wbExportMapText(format) {
    const boardId = window.currentBoardId;
    if (!boardId) {
      toast("The default board isn't a map: outlines come from a map.");
      return;
    }
    const res = await api(`/whiteboard/boards/${boardId}/export?format=${encodeURIComponent(format)}`);
    const blob = await res.blob();
    // The board picker's own label, minus the "(3 items)" it appends: the same
    // strip `renameCurrentBoard` already does, and the only place the open
    // board's title exists on the client.
    const title = document.getElementById("wb-board-select")?.selectedOptions?.[0]
      ?.dataset.title || "mindmap";
    // The extension the format actually is, a `.md` file holding OPML is a
    // file nothing will open. The name is reduced to word characters, spaces and
    // hyphens because a map may be called anything at all and this becomes a
    // filename on someone's disk.
    const safe = title.replace(/[^\w -]+/g, "").trim() || "mindmap";
    //: One table, so the extension and the sentence can never disagree about
    //: which format was actually asked for: which is what a pair of ternaries
    //: here would have turned into the moment a third format arrived.
    const formats = {
      markdown: { suffix: "md", said: "a Markdown outline" },
      opml: { suffix: "opml", said: "OPML" },
      freemind: { suffix: "mm", said: "a FreeMind map" },
      text: { suffix: "txt", said: "a plain-text outline" },
      xmind: { suffix: "xmind", said: "an XMind map" },
    };
    const chosen = formats[format] || formats.markdown;
    await saveFile(`${safe}.${chosen.suffix}`, blob);
    toast(`Map exported as ${chosen.said}.`);
  }

  //: **Make a map of these notes** (MINDMAP_PLAN.md §5 item 15).
  //:
  //: Three steps, in the order a person would say them: pick the notes, look at
  //: what came back, then create it. The middle step is the whole point, and it
  //: is `generate_diagram`'s and the note extractor's own preview-before-commit
  //: convention: `POST /boards/propose` writes nothing at all, so a proposal
  //: that is wrong costs a Cancel rather than a board to go and delete.
  //:
  //: The proposal is shown as **the outline itself, editable**, rather than as a
  //: rendered tree with controls to rearrange it. It is the same indented text
  //: the Markdown export writes and the import reads, a person can retype a line
  //: or delete three of them faster than any node editor would let them, and the
  //: map is one keystroke from being editable properly anyway once it exists.
  //:
  //: `source` says who wrote it. A local 4B model asked for an outline answers
  //: with a paragraph often enough that the server falls back to the notebook's
  //: own filing, and a proposal that quietly claimed to be the model's when it
  //: was not would make the model look better than it is, which is exactly the
  //: kind of thing this app does not do.
  async function wbGenerateMapFromNotes() {
    const chosen = await pickNotesDialog("Which notes should the map be built from?", {
      confirmLabel: "Propose a map",
    });
    if (!chosen || !chosen.length) return;

    toast("Working out a shape for those notes…");
    let proposal = null;
    try {
      proposal = await apiJson("/whiteboard/boards/propose", {
        method: "POST",
        body: JSON.stringify({ note_ids: chosen.map((note) => note.id) }),
      });
    } catch (error) {
      toast(error.message || voiceLine("failed", { what: "propose a map from those notes" }), true);
      return;
    }

    const accepted = await wbReviewMapProposal(proposal);
    if (!accepted) return;
    try {
      const board = await apiJson("/whiteboard/boards/generate", {
        method: "POST",
        body: JSON.stringify({
          name: accepted.name,
          outline: accepted.outline,
          note_ids: proposal.note_ids,
        }),
      });
      window.wbLastCreatedBoard = board;
      toast(`Made “${board.title}”: ${nounCount(board.object_count, "node")}.`);
      // Straight into the map, for the same reason the import opens what it
      // imported: landing back on an unchanged-looking list is how a thing that
      // worked reads as a thing that did not.
      await openWhiteboardBoard(board.id);
      wbBoardMadeStep(board);
      await wbMapTidyFresh();
    } catch (error) {
      toast(error.message || voiceLine("failed", { what: "create that map" }), true);
    }
  }

  //: The middle step: the proposal, as text, with a name beside it.
  //:
  //: Its own dialog rather than `promptDialog` because the thing being reviewed
  //: is a block of lines, not a value: a single-line input for a twenty-line
  //: outline would make the one step that exists for reading it the one step
  //: that cannot show it.
  function wbReviewMapProposal(proposal) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay confirm-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-label", "Review the proposed map");

      const card = document.createElement("div");
      card.className = "card modal-card confirm-card wb-proposal-card";

      const said = document.createElement("p");
      said.className = "muted";
      //: Three fallbacks, three sentences. "Your model is not running" is
      //: something the reader can go and fix; "the model answered with a
      //: paragraph" is something about the model they chose; and reporting
      //: either as the other is the kind of small dishonesty that teaches
      //: people not to read these lines at all.
      const because = {
        model: "Proposed by your local model",
        offline: "Grouped by how they are filed, because no local model is running",
        unusable: "Grouped by how they are filed, because the model did not answer with an outline",
        failed: "Grouped by how they are filed, because the model could not be reached",
      };
      const counted = nounCount(proposal.notes, "note");
      said.textContent = `${because[proposal.reason] || because.offline}, from ${counted}. Edit anything here before it is created.`;

      const name = document.createElement("input");
      name.type = "text";
      name.value = proposal.name || "";
      name.setAttribute("aria-label", "What to call the map");

      const outline = document.createElement("textarea");
      outline.className = "wb-proposal-outline";
      outline.value = proposal.outline || "";
      outline.rows = 12;
      outline.spellcheck = false;
      outline.setAttribute("aria-label", "The proposed outline, one node per line");

      const returnFocus = document.activeElement;
      let settled = false;
      const close = (answer) => {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
        returnFocus?.focus?.();
        resolve(answer);
      };
      // Escape only. Enter is a newline in a textarea, which is the whole point
      // of this dialog being one.
      const onKey = (event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        event.stopPropagation();
        close(null);
      };

      const row = document.createElement("div");
      row.className = "row confirm-actions";
      row.append(
        smallButton("Cancel", "Cancel", () => close(null)),
        smallButton("Create the map", "Create the map", () => {
          const text = outline.value.trim();
          if (!text) {
            toast("There is nothing in the outline to build.", "info");
            return;
          }
          close({ name: name.value.trim() || proposal.name || "Generated map", outline: text });
        }, false)
      );
      card.append(dialogHead("Review the map before it is made", () => close(null)), said, name, outline, row);
      overlay.appendChild(card);
      wireBackdropClose(overlay, () => close(null));
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(overlay);
      outline.focus();
    });
  }

  //: How much of a file this will send. Matches `MAX_IMPORT_CHARS` in
  //: routes_whiteboard.py exactly: the server refuses anything longer with a
  //: 422, and finding that out after uploading 4MB and waiting is a worse way to
  //: learn it than a sentence naming the number.
  const WB_MAX_IMPORT_CHARS = 400000;

  //: Import a mind map from an OPML or Markdown outline (§5 item 17).
  //:
  //: **The extension picks the format**, and nothing asks the user to confirm
  //: it. `POST /whiteboard/boards/import` takes `{format, content, name?}` and
  //: only knows the two, and a `.opml` file is not ambiguous, a second dialog
  //: to repeat what the filename already said is exactly the shape CLAUDE.md
  //: records as the real bug behind five bookmark-URL reports.
  //:
  //: `name` is deliberately not sent: the server takes the title out of the
  //: document itself (an OPML `<head><title>`, a Markdown `#` heading) and falls
  //: back to "Imported map". A filename is a worse name than the one the author
  //: wrote inside the file.
  function wbBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let text = "";
    for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(text);
  }

  async function wbImportOutlineFile(event) {
    const input = event.target;
    const file = input.files && input.files[0];
    // Cleared immediately so importing the *same* file twice in a row still
    // fires `change` the second time: the one thing this pattern gets wrong
    // when it is written without it.
    input.value = "";
    if (!file) return;
    // FreeMind first: a `.mm` file is XML too, so an extension test that asked
    // "is it XML?" first would send every FreeMind map to the OPML parser and
    // import it as an empty map, since OPML's nodes are `<outline>` and
    // FreeMind's are `<node>`, and neither parser finds the other's.
    const format = /\.xmind$/i.test(file.name)
      ? "xmind"
      : /\.mm$/i.test(file.name)
        ? "freemind"
        : /\.(opml|xml)$/i.test(file.name)
          ? "opml"
          : /\.txt$/i.test(file.name)
            ? "text"
            : "markdown";
    let content = "";
    try {
      //: An XMind file is a zip: it travels as base64 and the server unpacks
      //: it (W5). Everything else is text.
      content = format === "xmind" ? wbBase64(await file.arrayBuffer()) : await file.text();
    } catch {
      toast(voiceLine("failed", { what: "read that file" }), true);
      return;
    }
    if (!content.trim()) {
      toast("That file is empty.", "info");
      return;
    }
    if (content.length > WB_MAX_IMPORT_CHARS) {
      toast(
        `That outline is ${content.length.toLocaleString()} characters: the limit is ${WB_MAX_IMPORT_CHARS.toLocaleString()}.`,
        "info"
      );
      return;
    }
    try {
      const board = await apiJson("/whiteboard/boards/import", {
        method: "POST",
        //: A plain-text outline has no title line (§12.2 item 10): the
        //: file's name is the map's, as the export wrote it.
        body: JSON.stringify(format === "text"
          ? { format, content, name: file.name.replace(/\.txt$/i, "").slice(0, 100) || undefined }
          : { format, content }),
      });
      // The gallery is refreshed *and* the new map is opened, because an import
      // is a thing you then want to look at, landing back on an unchanged-
      // looking list is how an import that worked reads as one that did not.
      window.wbLastCreatedBoard = board;
      renderLibraryBoardsGallery();
      toast(
        `Imported “${board.title}”: ${nounCount(board.object_count, "node")}.`
      );
      await openWhiteboardBoard(board.id);
      wbBoardMadeStep(board);
      await wbMapTidyFresh();
    } catch (error) {
      // The server's own message, not a generic one: it names the actual
      // refusal ("Unknown import format", a DOCTYPE in the OPML, a parse
      // failure), and those are the only things a person can act on.
      toast(error.message || voiceLine("failed", { what: "import that outline" }), true);
    }
  }

  async function wbExportSvg(scope) {
    let { svg } = wbBuildExportSvg(scope);
    //: **The board rides inside the picture** (W5, draw.io's re-editable SVG):
    //: its rows in `<metadata>`, which Insert, Diagram, Mermaid, draw.io or board SVG brings back
    //: as shapes and connectors. A map's topics are a tree, not rows to drop.
    if (!wbIsMap()) svg = svg.replace(/(<svg[^>]*>)/, `$1${wbBoardSvgMetadata(wbExportRows(scope))}`);
    await saveFile(wbExportFileName(scope, "svg"), new Blob([await wbInlineSvgImages(svg)], { type: "image/svg+xml" }));
    toast("Board exported as SVG.");
  }

  // Shared with the background-image picker above, which inlines the same
  // three lines: pulled out here because this is the second call site and a
  // third (this one) is exactly when a copy-pasted upload stops being fine.
  //: **The board's own title, on the picture it made** (INBOX 184: "my exported
  //: png from the mindmap straight to the whiteboard still doesnt have anything
  //: at the bottom of its card, its just blank").
  //:
  //: Reproduced first (`scratchpad/ui-sweeps/mapexportcard.js`): the card is
  //: there and its foot is 32px of nothing, 0 of 1 blocks shown and no text.
  //: That is not a bug in the card. A description block is on a card only once
  //: it holds something (INBOX 115's decision, and it is the right one: three
  //: rows that all say nothing is here is worse than a short card), and the
  //: describe pass that would have filled it needs a vision model, which an
  //: offline notebook may simply not have. So the card had nothing to show and
  //: showed nothing.
  //:
  //: What it can always show is what the app itself knows: this picture is a
  //: named board, exported on a known day, by this app. That is a real
  //: description rather than a placeholder standing in for one, it makes the
  //: image findable by the board's name in search, and `caption_and_store` is
  //: write-once, so a vision model run later leaves it alone while the card's
  //: own Describe button (which forces) still replaces it.
  //: The board's own name, off the picker's `<kind> · <title> (N items)`.
  function wbBoardTitleForExport() {
    return document.getElementById("wb-board-select")?.selectedOptions?.[0]
      ?.textContent.replace(/\s*\(\d+ items?\)$/, "")
      .replace(/^(Mind map|Board|Whiteboard) \u00b7 /, "").trim() || "";
  }

  //: **A file named after the board** (FEAT-14): `Launch plan.png`, or
  //: `Launch plan (selection).png`, never `whiteboard-whole.png` for every
  //: board anyone exports. Characters a file system refuses are dropped.
  function wbExportFileName(scope, extension) {
    const title = wbBoardTitleForExport().replace(/[\\/:*?"<>|\u0000-\u001f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 80)
      || (wbIsMap() ? "Mind map" : "Whiteboard");
    const part = scope === "selection" ? " (selection)" : scope === "visible" ? " (view)" : "";
    return `${title}${part}.${extension}`;
  }

  //: The PNG's size and ground, remembered per device (FEAT-14: the export was
  //: 1x, board units as pixels, always on the board's colour).
  const WB_EXPORT_SCALES = [1, 2, 3];
  function wbExportPngPrefs() {
    const saved = prefs.json("wb-export-png", {});
    return {
      scale: WB_EXPORT_SCALES.includes(saved.scale) ? saved.scale : 2,
      transparent: saved.transparent === true,
      //: Off until asked (1031 BD12: every PNG export also added a copy to the
      //: image library, two exports, two copies); "Save to the library" is its
      //: own row for a copy on purpose.
      library: saved.library === true,
      //: The border round the picture (board units), the resolution written into the file, and whether the file
      //: carries a copy of the board so it can be opened again (whiteboard-export-more.js).
      border: Number.isInteger(saved.border) && saved.border >= 0 && saved.border <= 100 ? saved.border : 0,
      dpi: wbFmtState.exporters.dpis.includes(saved.dpi) ? saved.dpi : 96,
      embed: saved.embed === true,
    };
  }

  function wbSetExportPngPrefs(choice) {
    try {
      prefs.set("wb-export-png", JSON.stringify(choice));
    } catch {
      // Private mode: the choice holds for this export.
    }
  }

  function wbExportDescription(scope) {
    //: The picker's label is `<kind> · <title> (N items)` (`refreshBoardList`),
    //: and both halves of that have to come off or the sentence reads "the mind
    //: map \"Mind map · Export map\"", which is what the first run of the sweep
    //: measured.
    const title = document.getElementById("wb-board-select")?.selectedOptions?.[0]
      ?.dataset.title?.trim() || "";
    const kind = wbIsMap() ? "mind map" : "whiteboard";
    const part = scope === "selection" ? "Part of the " : "The ";
    const named = title ? ` "${title}"` : "";
    return `${part}${kind}${named}, exported from Tessellate.`;
  }

  async function uploadToLibrary(filename, blob, description = "") {
    const formData = new FormData();
    formData.append("file", new File([blob], filename, { type: blob.type }));
    //: **A board export is a commit, not a staged upload** (INBOX 174: an
    //: exported board in the Library has "no metadata area below for image and
    //: ocr captioning"). `POST /media/upload` runs captioning, Tesseract and
    //: vision OCR only for `direct`; everything else is staged, on the
    //: assumption that a note or document save will commit it later and
    //: `media_process` will run then. Nothing ever commits a board export: the
    //: picture *is* finished the moment it is made, which is the same case as
    //: the Library's own upload button. Without this the card arrived with no
    //: description and no reading, so the card's description and "Text in this
    //: image" blocks, which are on a card only once they hold something, were
    //: both absent, which is the missing metadata area exactly.
    formData.append("direct", "true");
    const uploaded = await apiJson("/media/upload", {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
    //: Only when the upload came back with nothing: a caption written by a model
    //: that did run says more than this one does, and this must never be the
    //: thing that displaced it.
    if (description && uploaded?.id && !uploaded.caption) {
      await apiJson(`/media/${uploaded.id}/caption`, {
        method: "POST",
        //: `source: "app"` (the owner, 2026-09-24): the app wrote this line, nobody typed
        //: it, so it is stored as written by Tessellate rather than as a hand
        //: edit, and the lightbox and the card say so.
        body: JSON.stringify({ text: description, source: "app" }),
      }).catch(() => {
        // Best effort, exactly like the upload itself: an export that produced a
        // file and a card has not failed because its description did not land.
      });
      //: The gallery redraws on the upload, which is before this description
      //: exists, so the card it drew had an empty foot until the next visit
      //: (INBOX 196: "still missing all the metadata"). Once more, now that
      //: the description is on the row.
      if (typeof renderLibraryImagesGallery === "function") {
        renderLibraryImagesGallery().catch(() => {});
      }
    }
    return uploaded;
  }

  async function wbExportPng(scope) {
    const { scale, transparent, library, border, dpi, embed } = wbExportPngPrefs();
    const { svg, width, height } = wbBuildExportSvg(scope, { transparent, pad: border });
    const raster = await wbRasterizeSvg(svg, width * scale, height * scale, "image/png");
    //: A map's topics are a tree, not rows to bring back, so only a free board carries its copy (as an SVG does).
    const rows = embed && !wbIsMap() ? wbExportRows(scope) : null;
    const blob = new Blob([wbFmtState.exporters.pngWith(new Uint8Array(await raster.arrayBuffer()), { dpi, rows })], { type: "image/png" });
    const filename = wbExportFileName(scope, "png");
    await saveFile(filename, blob);
    if (!library) {
      toast("Board exported as PNG.");
      return;
    }
    // Asked for directly: an exported board should show up in the Library's
    // Images gallery, not only as a file on disk that the app has no record
    // of. Best-effort: a failed upload must not make the export itself look
    // like it failed, since the download above already succeeded.
    try {
      await uploadToLibrary(filename, blob, wbExportDescription(scope));
      toast("Board exported as PNG, and added to your image library.");
    } catch {
      toast("Board exported as PNG.");
    }
  }

  //: **Straight into the image library, with no file on disk.** Asked for
  //: directly: "maybe I should be able to highlight a rectangular section
  //: and/or select a bunch of things in a whiteboard and export it to a png
  //: which can then appear in the image library."
  //:
  //: `wbExportPng` above already uploads a copy, but it downloads the file
  //: first, and "put this drawing in my library" and "save this file to my
  //: computer" are different intentions that should not be one button. The
  //: marquee and shift-click already produce the selection this exports; this
  //: is the missing half that turns a region of the board into a real image
  //: the gallery, the captioner and semantic search can all see.
  async function wbSaveToLibrary(scope) {
    const { scale, transparent } = wbExportPngPrefs();
    const { svg, width, height } = wbBuildExportSvg(scope, { transparent });
    const blob = await wbRasterizeSvg(svg, width * scale, height * scale, "image/png");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    await uploadToLibrary(`whiteboard-${scope}-${stamp}.png`, blob, wbExportDescription(scope));
    toast("Added to your image library.");
  }

  //: The raster types beyond PNG (draw.io's export formats). JPEG has no alpha,
  //: so it always draws the board's ground; WebP keeps a transparent one.
  const WB_EXPORT_PICTURES = Object.freeze({
    jpg: Object.freeze({ mime: "image/jpeg", extension: "jpg", quality: 0.92, alpha: false }),
    webp: Object.freeze({ mime: "image/webp", extension: "webp", quality: 0.92, alpha: true }),
  });

  async function wbExportPicture(scope, kind) {
    const spec = WB_EXPORT_PICTURES[kind];
    const { scale, transparent } = wbExportPngPrefs();
    const { svg, width, height } = wbBuildExportSvg(scope, { transparent: transparent && spec.alpha });
    const blob = await wbRasterizeSvg(svg, width * scale, height * scale, spec.mime, spec.quality);
    //: A browser that cannot encode a type hands back a PNG; a ".webp" that is
    //: really a PNG would open nowhere, so say so instead.
    if (blob.type !== spec.mime) throw new Error(`This browser cannot write ${kind.toUpperCase()} files. Export a PNG instead.`);
    await saveFile(wbExportFileName(scope, spec.extension), blob);
    toast(`Board exported as ${kind.toUpperCase()}.`);
  }

  //: **Copy as an image** (draw.io's): the same picture as the PNG, put on the
  //: clipboard to paste into a chat, a document or another app. The blob is
  //: handed over as a promise so the browser's click permission is spent at the
  //: write, not lost while the board is drawn.
  async function wbExportCopyImage(scope) {
    const { scale, transparent } = wbExportPngPrefs();
    const { svg, width, height } = wbBuildExportSvg(scope, { transparent });
    const picture = wbRasterizeSvg(svg, width * scale, height * scale, "image/png");
    //: No clipboard for pictures (an older browser, or a refused permission):
    //: the same PNG is downloaded instead, and the toast says so.
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") throw new Error("no clipboard");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": picture })]);
      toast("Copied the picture. Paste it into another app.");
    } catch {
      await saveFile(wbExportFileName(scope, "png"), await picture);
      toast("This browser would not copy a picture, so it was saved as a PNG instead.");
    }
  }

  //: The command row's entry: the selection if there is one, else what the
  //: canvas shows, and any refusal said rather than thrown into the console.
  async function wbCopyAsImage() {
    const scope = wbMultiSelection.size > 0 || wbSelectedItem ? "selection" : "visible";
    try {
      await wbExportCopyImage(scope);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "copy the picture" }), true);
    }
  }

  //: **Copy as SVG** (draw.io's, the other half of Copy as an image): the same
  //: picture as the SVG export, as text on the clipboard, so it pastes into a
  //: code editor or a vector tool. Plain text, so any browser allows it.
  async function wbCopyAsSvg() {
    const scope = wbMultiSelection.size > 0 || wbSelectedItem ? "selection" : "visible";
    try {
      if (!navigator.clipboard?.writeText) throw new Error("This browser cannot copy text. Export an SVG instead.");
      const { svg } = wbBuildExportSvg(scope, { transparent: wbExportPngPrefs().transparent });
      await navigator.clipboard.writeText(svg);
      toast("Copied the SVG. Paste it into an editor.");
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "copy the SVG" }), true);
    }
  }

  async function wbExportPdf(scope) {
    const pages = await wbPdf.pictures(scope, wbPdf.boardChoice(wbBoardBackground(), wbPdf.savedChoice()));
    await saveFile(wbExportFileName(scope, "pdf"), new Blob([wbPdf.build(pages)], { type: "application/pdf" }));
    toast(pages.length === 1 ? "Board exported as a PDF." : `Board exported as a PDF of ${pages.length} pages.`);
  }

  //: **Export is a dialog, not a popover** (WHITEBOARD_PLAN.md decision 4).
  //:
  //: It was a list: five headings of two or three options each, built as a
  //: floating menu anchored to whichever button opened it, which is how it came
  //: to be reported as "a full-height list in the wrong place" (INBOX 12, with a
  //: screenshot of it running off the bottom of the window). The choices are a
  //: matrix, scope by format, and a list of every cell of a matrix is as long as
  //: the product of its sides. Two segmented rows are as long as the sum.
  //:
  //: Excalidraw's export dialog is exactly this shape (a scope toggle plus
  //: format buttons), which is the research note in §8 of the plan.
  const WB_EXPORT_SCOPES = [
    { value: "selection", label: "Selection", title: "Just what is selected" },
    { value: "visible", label: "On screen", title: "Exactly what the canvas is showing now" },
    { value: "whole", label: "Whole board", title: "Everything on the board" },
  ];

  //: Each format says which scopes it can answer, rather than the dialog
  //: knowing: SVG has no meaning for "on screen" (it is the board's vectors, not
  //: a screenshot), and an outline is the whole tree or nothing. `map: true`
  //: marks the three that only exist on a mind map, for the reason the old menu
  //: gave in the same words: an outline of a whiteboard is not a thing.
  const WB_EXPORT_FORMATS = [
    {
      //: `picture: true` rows share the dialog's Size and ground rows.
      value: "png", label: "PNG", scopes: ["selection", "visible", "whole"], picture: true,
      note: "An image file, and a copy in your image library.",
      run: (scope) => wbExportPng(scope),
    },
    {
      value: "jpg", label: "JPG", scopes: ["selection", "visible", "whole"], picture: true, noAlpha: true,
      note: "A smaller image file, on the board's colour (it cannot be transparent).",
      run: (scope) => wbExportPicture(scope, "jpg"),
    },
    {
      value: "webp", label: "WebP", scopes: ["selection", "visible", "whole"], picture: true,
      note: "A small image file for the web; it can be transparent.",
      run: (scope) => wbExportPicture(scope, "webp"),
    },
    {
      value: "copy", label: "Copy image", scopes: ["selection", "visible", "whole"], picture: true,
      note: "Puts the picture on the clipboard, to paste into another app.",
      run: (scope) => wbExportCopyImage(scope),
    },
    {
      value: "library", label: "Image library", scopes: ["selection", "visible", "whole"], picture: true,
      note: "Straight into the gallery, with no file saved to disk.",
      run: (scope) => wbSaveToLibrary(scope),
    },
    {
      //: The pen strokes drawn back in order, one frame per step (whiteboard-ink-replay.js; the writer is whiteboard-gif.js).
      value: "gif", label: "GIF", scopes: ["selection", "whole"], board: true,
      note: "An animated picture of the pen drawing, stroke by stroke.",
      run: (scope) => wbFmtState.inkReplay.exportGif(scope),
    },
    {
      //: One file for anyone with a browser: the board's SVG in a page that pans and zooms (whiteboard-export-more.js).
      value: "html", label: "HTML", scopes: ["selection", "whole"],
      note: "One web page that opens in any browser, offline: the board to zoom and drag.",
      run: async (scope) => {
        const { svg } = wbBuildExportSvg(scope);
        const name = wbExportFileName(scope, "html");
        await saveFile(name, new Blob([wbFmtState.exporters.htmlPage(await wbInlineSvgImages(svg), name.replace(/\.html$/, ""))], { type: "text/html" }));
        toast("Board exported as an HTML page.");
      },
    },
    {
      value: "svg", label: "SVG", scopes: ["selection", "whole"],
      note: "Vector, so it stays sharp at any size.",
      run: (scope) => wbExportSvg(scope),
    },
    {
      //: A free board's own text formats (W5). `board: true`, the mirror of
      //: `map`: a map has its own outline below.
      value: "outline", label: "Outline", scopes: ["whole"], board: true, drawsCards: false,
      note: "Markdown: each frame a heading over what is in it, in reading order.",
      run: () => wbExportOutline(),
    },
    {
      value: "mermaid", label: "Mermaid", scopes: ["whole"], board: true, drawsCards: false,
      note: "A flowchart of what the connectors join, for docs and other diagram apps.",
      run: () => wbExportMermaid(),
    },
    {
      value: "drawio", label: "draw.io", scopes: ["whole"], board: true, drawsCards: false,
      note: "Shapes, text, frames and connectors as a .drawio file; pictures, tables, notes and drawn lines are left out.",
      run: () => wbExportDrawio(),
    },
    {
      value: "pdf", label: "PDF", scopes: ["selection", "visible", "whole"],
      note: "A PDF file: pick the page size, the direction and how the board is cut into pages.",
      run: (scope) => wbExportPdf(scope),
    },
    {
      //: `drawsCards: false`: these three read the notes themselves rather
      //: than drawing the cards, so nothing is clipped out of them and the
      //: export dialog's collapsed-notes warning would be a warning about
      //: nothing. Named for what the dialog asks rather than inferred from
      //: `map`, which happens to select the same three today and means
      //: something else.
      value: "markdown", label: "Markdown", scopes: ["whole"], map: true, drawsCards: false,
      note: "The map as an indented outline.",
      run: () => wbExportMapText("markdown"),
    },
    {
      value: "opml", label: "OPML", scopes: ["whole"], map: true, drawsCards: false,
      note: "The interchange format every mind mapper reads.",
      run: () => wbExportMapText("opml"),
    },
    {
      value: "freemind", label: "FreeMind", scopes: ["whole"], map: true, drawsCards: false,
      note: "For FreeMind and Freeplane.",
      run: () => wbExportMapText("freemind"),
    },
    {
      value: "xmind", label: "XMind", scopes: ["whole"], map: true, drawsCards: false,
      note: "For XMind: topics, notes, labels, callouts and each branch's structure.",
      run: () => wbExportMapText("xmind"),
    },
    {
      value: "text", label: "Plain text", scopes: ["whole"], map: true, drawsCards: false,
      note: "One topic per line, a tab per level, for anything that reads plain text.",
      run: () => wbExportMapText("text"),
    },
  ];

  //: One `.seg` on the app's own recipe (`promptDialog`'s, down to the
  //: `aria-pressed` pair), built twice here rather than once in app.js because
  //: this pair talk to each other: picking a format that cannot answer the
  //: current scope has to move the scope.
  function wbExportSegment(label, options, chosen, onPick) {
    const seg = document.createElement("div");
    seg.className = "seg seg-compact wb-export-seg";
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", label);
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option.label;
      button.dataset.value = option.value;
      if (option.title) button.title = option.title;
      button.addEventListener("click", () => onPick(option.value));
      seg.appendChild(button);
    }
    return seg;
  }

  function wbSyncExportSeg(seg, chosen, allowed) {
    for (const button of seg.querySelectorAll("button")) {
      const on = button.dataset.value === chosen;
      button.classList.toggle("active", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
      // Disabled, not hidden: a scope that vanishes and comes back as the format
      // changes makes the row jump under the pointer, and "SVG cannot do what is
      // on screen" is worth saying rather than hiding.
      const usable = !allowed || allowed.has(button.dataset.value);
      button.disabled = !usable;
    }
  }

  //: How many note cards in this scope are hiding text behind their clamp.
  //:
  //: Asked for directly: "when exporting a whiteboard and/or mindmap, the user
  //: should be warned if any of their notes arent expanded and that not all
  //: their contents will be shown" (INBOX 238). Counted from the live cards
  //: rather than from the notes, because the question is whether *this card*
  //: is clipping, which depends on the box it was dragged to and not on how
  //: long the note is.
  function wbClippedCardCount(scope) {
    const onlyKeys = scope === "selection" ? wbSelectedKeys() : null;
    let clipped = 0;
    for (const node of wbState.nodes) {
      if (onlyKeys && !onlyKeys.has(wbMultiKey("node", node.id))) continue;
      const content = document.querySelector(
        `.node-card[data-id="${node.id}"] .wb-card-content`
      );
      if (!content || !content.classList.contains("wb-card-content-clamped")) continue;
      if (content.scrollHeight > content.clientHeight + 1) clipped += 1;
    }
    return clipped;
  }

  //: The frame and everything wholly inside it (locked or not) as the
  //: selection, then the export dialog, which opens on "Selection" for it.
  function wbExportFrame(frame) {
    clearWbSelection();
    wbMultiSelection.add(wbMultiKey("object", frame.id));
    for (const key of wbFrameContents(frame, { withLocked: true })) wbMultiSelection.add(key);
    wbApplySelectionHighlight();
    wbUpdateSelectionBar();
    wbExportBoard();
  }

  function wbExportBoard({ branch = false } = {}) {
    //: Opened from a map branch's menu (the branch is the selection): the dialog says so.
    const heading = branch ? "Export this branch" : "Export this board";
    const hasSelection = wbMultiSelection.size > 0 || Boolean(wbSelectedItem);
    const isMap = wbIsMap();
    const formats = WB_EXPORT_FORMATS.filter((f) => (!f.map || isMap) && (!f.board || !isMap));
    let format = formats[0];
    //: The whole board when nothing is selected (audit 1028 U48): "On screen" put "(view)" in a first export's
    //: file name and cut off what was past the edge; it stays one press away.
    let scope = hasSelection ? "selection" : "whole";

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay wb-export-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", heading);

    const card = document.createElement("div");
    card.className = "card modal-card confirm-card wb-export-card";

    const formatLabel = document.createElement("span");
    formatLabel.className = "wb-export-label";
    formatLabel.textContent = "Format";
    const scopeLabel = document.createElement("span");
    scopeLabel.className = "wb-export-label";
    scopeLabel.textContent = "How much";
    //: The picture's size and ground (FEAT-14), shown only while the format
    //: is a picture: an outline has neither.
    const pngPrefs = wbExportPngPrefs();
    const sizeLabel = document.createElement("span");
    sizeLabel.className = "wb-export-label";
    sizeLabel.textContent = "Size";
    const sizeSeg = wbExportSegment(
      "Picture size",
      WB_EXPORT_SCALES.map((n) => ({ value: String(n), label: `${n}x`, title: n === 1 ? "One pixel per board unit" : `${n} pixels per board unit, sharper on a high-resolution screen or in print` })),
      String(pngPrefs.scale),
      (value) => {
        pngPrefs.scale = Number(value);
        wbSetExportPngPrefs(pngPrefs);
        sync();
      }
    );
    //: A PDF's page size, direction and cut (L270), one labelled row each.
    const pdfPrefs = wbPdf.boardChoice(wbBoardBackground(), wbPdf.savedChoice());
    const pdfRows = ["size", "orientation", "layout"].map((key) => {
      const label = document.createElement("span");
      label.className = "wb-export-label";
      label.textContent = { size: "Page size", orientation: "Direction", layout: "Pages" }[key];
      const seg = wbExportSegment(label.textContent, wbPdf.choices[key], pdfPrefs[key], (value) => {
        pdfPrefs[key] = value;
        wbPdf.saveChoice(pdfPrefs);
        sync();
      });
      return { key, label, seg };
    });
    const clearRow = document.createElement("label");
    clearRow.className = "setting-check wb-export-clear";
    const clearBox = document.createElement("input");
    clearBox.type = "checkbox";
    clearBox.id = "wb-export-transparent";
    clearBox.checked = pngPrefs.transparent;
    clearBox.addEventListener("change", () => {
      pngPrefs.transparent = clearBox.checked;
      wbSetExportPngPrefs(pngPrefs);
    });
    const clearText = document.createElement("span");
    clearText.textContent = "Transparent background";
    clearRow.append(clearBox, clearText);
    const libraryRow = document.createElement("label");
    libraryRow.className = "setting-check wb-export-clear";
    const libraryBox = document.createElement("input");
    libraryBox.type = "checkbox";
    libraryBox.id = "wb-export-library";
    libraryBox.checked = pngPrefs.library;
    libraryBox.addEventListener("change", () => {
      pngPrefs.library = libraryBox.checked;
      wbSetExportPngPrefs(pngPrefs);
    });
    const libraryText = document.createElement("span");
    libraryText.textContent = "Also add to the image library";
    libraryRow.append(libraryBox, libraryText);
    //: The PNG's border, resolution and embedded copy (wbformat2); shown for a PNG only.
    const borderLabel = document.createElement("span");
    borderLabel.className = "wb-export-label";
    borderLabel.textContent = "Border";
    const borderInput = document.createElement("input");
    borderInput.type = "number";
    borderInput.id = "wb-export-border";
    borderInput.min = "0";
    borderInput.max = "100";
    borderInput.step = "1";
    borderInput.value = String(pngPrefs.border);
    borderInput.setAttribute("aria-label", "Border width, board units, round the picture");
    borderInput.title = "Space round the picture, in board units; 0 is none";
    borderInput.addEventListener("change", () => {
      pngPrefs.border = Math.max(0, Math.min(100, Math.round(Number(borderInput.value) || 0)));
      borderInput.value = String(pngPrefs.border);
      wbSetExportPngPrefs(pngPrefs);
    });
    const dpiLabel = document.createElement("span");
    dpiLabel.className = "wb-export-label";
    dpiLabel.textContent = "Resolution";
    const dpiSeg = wbExportSegment(
      "Resolution, dots per inch",
      wbFmtState.exporters.dpis.map((n) => ({ value: String(n), label: String(n), title: `${n} dots per inch written into the file, for the size it prints at` })),
      String(pngPrefs.dpi),
      (value) => {
        pngPrefs.dpi = Number(value);
        wbSetExportPngPrefs(pngPrefs);
        sync();
      }
    );
    const embedRow = document.createElement("label");
    embedRow.className = "setting-check wb-export-clear";
    const embedBox = document.createElement("input");
    embedBox.type = "checkbox";
    embedBox.id = "wb-export-embed";
    embedBox.checked = pngPrefs.embed;
    embedBox.addEventListener("change", () => {
      pngPrefs.embed = embedBox.checked;
      wbSetExportPngPrefs(pngPrefs);
    });
    const embedText = document.createElement("span");
    embedText.textContent = "Include a copy of the diagram";
    embedRow.append(embedBox, embedText);
    const note = document.createElement("p");
    note.className = "confirm-text wb-export-note";
    const warning = document.createElement("p");
    warning.className = "confirm-text wb-export-note status wb-export-warning";
    warning.hidden = true;

    const scopeSeg = wbExportSegment("How much to export", WB_EXPORT_SCOPES, scope, (value) => {
      scope = value;
      sync();
    });
    const formatSeg = wbExportSegment("Format", formats, format.value, (value) => {
      format = formats.find((f) => f.value === value) || formats[0];
      // The scope follows the format when the format cannot answer it, rather
      // than the Export button refusing a pair the dialog let you make.
      if (!format.scopes.includes(scope)) scope = format.scopes.find((s) => s !== "selection" || hasSelection) || format.scopes[0];
      sync();
    });

    function sync() {
      const allowed = new Set(format.scopes.filter((s) => s !== "selection" || hasSelection));
      if (!allowed.has(scope)) scope = [...allowed][0];
      wbSyncExportSeg(formatSeg, format.value, null);
      wbSyncExportSeg(scopeSeg, scope, allowed);
      const picture = Boolean(format.picture);
      sizeLabel.hidden = !picture;
      sizeSeg.hidden = !picture;
      //: A JPEG has no alpha, so the ground choice is not offered for it.
      clearRow.hidden = !picture || Boolean(format.noAlpha);
      libraryRow.hidden = format.value !== "png";
      borderLabel.hidden = borderInput.hidden = dpiLabel.hidden = dpiSeg.hidden = format.value !== "png";
      embedRow.hidden = format.value !== "png" || wbIsMap();
      wbSyncExportSeg(dpiSeg, String(pngPrefs.dpi), null);
      for (const row of pdfRows) {
        row.label.hidden = row.seg.hidden = format.value !== "pdf";
        wbSyncExportSeg(row.seg, pdfPrefs[row.key], null);
      }
      if (picture) wbSyncExportSeg(sizeSeg, String(pngPrefs.scale), null);
      const chosenScope = WB_EXPORT_SCOPES.find((s) => s.value === scope);
      // Two sentences, the format's and the scope's, so the line reads the same
      // way round whichever of the two was changed last.
      note.textContent = [format.note, chosenScope ? `${chosenScope.title}.` : ""].filter(Boolean).join(" ");
      //: Only for the formats that draw the cards. A mind map's outline and its
      //: text exports read the notes themselves, so nothing is clipped out of
      //: those and saying otherwise would be a warning about nothing.
      const clipped = format.drawsCards === false ? 0 : wbClippedCardCount(scope);
      warning.hidden = clipped === 0;
      warning.textContent = clipped
        ? `${clipped} note${clipped === 1 ? " is" : "s are"} collapsed, so only the ` +
          `text you can see on ${clipped === 1 ? "it" : "them"} will be in the picture. ` +
          `Open ${clipped === 1 ? "it" : "them"} with "Show more" first to export the whole note.`
        : "";
    }

    let settled = false;
    const close = () => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close();
      } else if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        go();
      }
    };
    const go = async () => {
      const chosen = format;
      const where = scope;
      close();
      try {
        await chosen.run(where);
      } catch (err) {
        toast(err.message || voiceLine("failed", { what: "export the board" }), true);
      }
    };

    const returnFocus = document.activeElement;
    const row = document.createElement("div");
    row.className = "row confirm-actions";
    const exportBtn = smallButton("Export", "Export", go, false);
    exportBtn.id = "wb-export-go";
    row.append(smallButton("Cancel", "Cancel", close), exportBtn);
    card.append(dialogHead(heading, close), formatLabel, formatSeg, scopeLabel, scopeSeg, sizeLabel, sizeSeg, borderLabel, borderInput, dpiLabel, dpiSeg, clearRow, embedRow, libraryRow, ...pdfRows.flatMap((r) => [r.label, r.seg]), note, warning, row);
    overlay.appendChild(card);
    wireBackdropClose(overlay, close);
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    sync();
    exportBtn.focus();
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbSvgEscape, wbSvgWrapLines, wbSvgText, wbExportColour, wbPaperPaint, wbExportPaint, wbBuildExportSvg, wbInlineSvgImages, wbRasterizeSvg, wbExportMapText, wbGenerateMapFromNotes, wbImportOutlineFile, wbBoardTitleForExport, wbExportFileName, wbCopyAsImage, wbCopyAsSvg, wbExportFrame, wbExportBoard });
})();
