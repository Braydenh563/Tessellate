(() => {
  // whiteboard-text-more.js: words on a board beyond plain text (WHITEBOARD_PLAN section 5): subscript and superscript
  // in pandoc's spelling, `H~2~O` and `x^2^`, in a text box that shows its markdown and in a shape's label, and (further
  // down) `$...$` maths. Board-only: a note keeps its own markdown. Held on `wbFmtState.textMore`, so no new global name.
  // Nothing here builds HTML from the words: a piece is a text node or an element made with createElement.
  const NS = "http://www.w3.org/2000/svg";

  // --- Subscript and superscript ---------------------------------------------------------------------------
  //: One run of up to 20 characters with no space between two like marks; a doubled `~~` (strikethrough) is not one.
  const SCRIPT = /(?<![~^\\])([~^])(?![~^])([^\s~^]{1,20})\1(?![~^])/g;

  //: Pure (node-tested): the text as pieces, `{ text, kind }` with kind "sub", "sup" or "" (plain).
  function splitScripts(text) {
    const out = [];
    const source = String(text ?? "");
    let cursor = 0;
    for (const hit of source.matchAll(SCRIPT)) {
      if (hit.index > cursor) out.push({ text: source.slice(cursor, hit.index), kind: "" });
      out.push({ text: hit[2], kind: hit[1] === "~" ? "sub" : "sup" });
      cursor = hit.index + hit[0].length;
    }
    if (cursor < source.length) out.push({ text: source.slice(cursor), kind: "" });
    return out;
  }
  const hasScripts = (text) => new RegExp(SCRIPT.source).test(String(text ?? ""));

  //: A text box's rendered words: every text node outside code turned into text, <sub> and <sup>.
  function paintScripts(root) {
    if (!root || !hasScripts(root.textContent)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.parentElement?.closest("code, pre, script, style, .katex, math") && hasScripts(n.nodeValue)) nodes.push(n);
    }
    for (const node of nodes) {
      const frag = document.createDocumentFragment();
      for (const piece of splitScripts(node.nodeValue)) {
        if (!piece.kind) frag.append(document.createTextNode(piece.text));
        else {
          const el = document.createElement(piece.kind);
          el.textContent = piece.text;
          frag.append(el);
        }
      }
      node.replaceWith(frag);
    }
  }

  //: A shape label's line (a <tspan> holding one string): split into plain and raised or lowered child tspans. A raised
  //: piece moves by `dy` and the piece after moves back, so the baseline returns without `baseline-shift` (Firefox and
  //: the exported image would not all honour it). Attributes, not styles: the export clones the node.
  function scriptSpans(line, fontSize) {
    const pieces = splitScripts(line.textContent);
    if (!pieces.some((p) => p.kind)) return;
    const small = Math.round(fontSize * 0.7 * 100) / 100;
    const lift = { sup: -fontSize * 0.35, sub: fontSize * 0.2 };
    line.replaceChildren();
    let carried = 0;
    for (const piece of pieces) {
      const span = document.createElementNS(NS, "tspan");
      span.textContent = piece.text;
      const shift = piece.kind ? lift[piece.kind] : 0;
      if (shift !== carried) span.setAttribute("dy", String(Math.round((shift - carried) * 100) / 100));
      if (piece.kind) span.setAttribute("font-size", String(small));
      carried = shift;
      line.append(span);
    }
  }

  //: The export's characters (`wbRunChars`): markers dropped and each marked character tagged `script`, so the run writer
  //: can lower or raise and shrink it.
  function markScripts(chars) {
    const text = chars.map((c) => c.ch).join("");
    if (!hasScripts(text)) return chars;
    const out = [];
    let cursor = 0;
    for (const hit of text.matchAll(SCRIPT)) {
      for (; cursor < hit.index; cursor += 1) out.push(chars[cursor]);
      const kind = hit[1] === "~" ? "sub" : "sup";
      for (let i = 0; i < hit[2].length; i += 1) out.push({ ...chars[hit.index + 1 + i], attrs: { ...chars[hit.index + 1 + i].attrs, script: kind } });
      cursor = hit.index + hit[0].length;
    }
    for (; cursor < chars.length; cursor += 1) out.push(chars[cursor]);
    return out;
  }

  // --- Maths in a shape's words ----------------------------------------------------------------------------
  //: A `$...$` span the document renderer accepts as maths (`docMathLooksLikeMath`: no space inside the dollars, so "$5 and
  //: $10" stays prose). A text box that shows its markdown already draws these through `renderMarkdown`.
  const DOLLARS = /(?<![\\$])\$([^$\n]+?)\$(?!\d)/g;
  const looksLikeMath = (body) => Boolean(window.docMathLooksLikeMath?.(body));

  //: Pure given the test: the text as `{ text }` and `{ math }` pieces.
  function mathPieces(text, looks = looksLikeMath) {
    const source = String(text ?? "");
    const out = [];
    let cursor = 0;
    for (const hit of source.matchAll(DOLLARS)) {
      if (!looks(hit[1])) continue;
      if (hit.index > cursor) out.push({ text: source.slice(cursor, hit.index) });
      out.push({ math: hit[1] });
      cursor = hit.index + hit[0].length;
    }
    if (cursor < source.length) out.push({ text: source.slice(cursor) });
    return out;
  }
  const hasMath = (text, looks) => mathPieces(text, looks).some((p) => p.math !== undefined);

  //: Draws a label that holds maths over the shape as a foreignObject of MathML (`docMathRender`, documents-math.js, in the
  //: Library bundle that the board bundle includes). The SVG <text> underneath keeps the source and the layout and is
  //: hidden by `opacity` on the live board; the export clone drops the style and the foreignObject, so a picture
  //: carries the source words (`$x^2$`) rather than a MathML island no image reader can draw. No maths, or no renderer:
  //: the object is taken away and the text shows as before.
  function mathLabel(groupEl, label, area, fontSize) {
    let fo = groupEl.querySelector(":scope > .sketch-label-math");
    const text = label.__wbText;
    if (!area || !window.docMathRender || label.dataset.dir === "vertical" || !hasMath(text)) {
      fo?.remove();
      label.style.opacity = "";
      return;
    }
    if (!fo) {
      fo = document.createElementNS(NS, "foreignObject");
      fo.setAttribute("class", "sketch-label-math");
      fo.setAttribute("pointer-events", "none");
      label.after(fo);
      const box = document.createElement("div");
      box.className = "wb-label-math";
      fo.append(box);
    }
    fo.removeAttribute("transform");
    fo.setAttribute("x", String(area.cx - area.w / 2));
    fo.setAttribute("y", String(area.cy - area.h / 2));
    fo.setAttribute("width", String(area.w));
    fo.setAttribute("height", String(area.h));
    const box = fo.firstElementChild;
    const align = label.dataset.align;
    box.style.justifyContent = align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center";
    box.style.textAlign = align || "center";
    box.style.fontSize = `${fontSize}px`;
    box.style.color = getComputedStyle(label).fill;
    const parts = [];
    for (const piece of mathPieces(text)) {
      if (piece.math === undefined) parts.push(document.createTextNode(piece.text));
      else {
        const span = document.createElement("span");
        span.className = "md-math-inline";
        span.append(window.docMathRender(piece.math, false));
        parts.push(span);
      }
    }
    box.replaceChildren(...parts);
    label.style.opacity = "0";
  }

  wbFmtState.textMore = { splitScripts, hasScripts, paintScripts, scriptSpans, markScripts, mathPieces, hasMath, mathLabel };
})();
