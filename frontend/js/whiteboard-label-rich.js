(() => {
  // whiteboard-label-rich.js: rich words in a drawn shape's label (L-whiteboard-46; WHITEBOARD_PLAN section 2, formatted
  // text). A shape's label stays plain text unless its data says `label_md: true` (the Format panel's Rich text tick);
  // old labels are never read as markdown, so no board migrates. The words are stored as markdown and drawn by the
  // text box's own renderer (`renderMarkdown`: lists, nested lists by indent, links, bold, italic, code), as a
  // foreignObject over the shape beside the hidden SVG <text>, the way maths is (whiteboard-text-more.js, `mathLabel`).
  // Nothing here builds HTML from the words: `renderMarkdown` makes elements, and `inert` then takes out everything a
  // label has no use for (scripts, frames, pictures, handlers) and lets a link keep only an http, https, mailto or tel
  // address, opening in a new tab with `rel="noopener noreferrer"`. Held on `wbFmtState.richLabel`, no new global name.
  const NS = "http://www.w3.org/2000/svg";
  const KEY = "label_md";
  const SAFE_LINK = /^(https?:|mailto:|tel:)/i;
  //: Elements a label never keeps: anything that runs, loads or submits. MathML (`math`) stays for `$x^2$`.
  const DROP = "script,style,iframe,frame,object,embed,applet,link,meta,base,form,input,button,textarea,select,img,picture,video,audio,source,track,svg,foreignobject,canvas";

  //: Pure (node-tested): the address a label link may keep, else "". Controls and spaces are dropped before the scheme
  //: test, as a browser reads it, so `java\nscript:` and ` javascript:` are refused.
  function cleanHref(url) {
    const value = String(url ?? "").trim();
    const probe = value.replace(/[\0- \x7f]/g, "");
    return SAFE_LINK.test(probe) ? value : "";
  }

  //: Pure (node-tested): each list item in the markdown, in order, outside code fences, as `{ line, depth }`. `renderMarkdown`
  //: draws an indented item flat inside its list, so the label carries the depth itself: a deeper indent than the item
  //: above opens a level, a shallower one closes back to the level it matches (a tab counts as four spaces).
  function listEntries(text) {
    const out = [];
    const stack = [];
    let fenced = false;
    String(text ?? "").split("\n").forEach((line, at) => {
      if (/^\s*(```|~~~)/.test(line)) {
        fenced = !fenced;
        return;
      }
      const hit = !fenced && /^([ \t]*)([-*+]|\d{1,9}[.)])\s+\S/.exec(line);
      if (!hit) {
        if (!fenced && line.trim() && !/^\s/.test(line)) stack.length = 0;
        return;
      }
      const width = hit[1].replace(/\t/g, "    ").length;
      while (stack.length && stack[stack.length - 1] > width) stack.pop();
      if (!stack.length || stack[stack.length - 1] < width) stack.push(width);
      out.push({ line: at, depth: stack.length - 1 });
    });
    return out;
  }

  const listDepths = (text) => listEntries(text).map((entry) => entry.depth);

  //: Puts each item's depth on the rendered list as a left margin (set through the style object: the CSP refuses a style
  //: attribute). Each list is matched to the items from its own source line (`data-src-line`), so a list the renderer
  //: draws differently (inside a quote, say) never shifts the depths of the lists around it.
  function indentItems(box, text) {
    const entries = listEntries(text);
    if (!entries.some((entry) => entry.depth)) return;
    for (const list of box.querySelectorAll("ul, ol")) {
      const from = entries.findIndex((entry) => entry.line === Number(list.dataset.srcLine));
      const items = [...list.children].filter((child) => child.localName === "li");
      if (from < 0 || from + items.length > entries.length) continue;
      items.forEach((li, i) => {
        const depth = entries[from + i].depth;
        if (depth) {
          li.dataset.depth = String(depth);
          li.style.marginLeft = `${depth * 1.2}em`;
        }
      });
    }
  }

  const isRich = (parsed) => parsed?.[KEY] === true;

  //: The rendered label made inert, in place. Elements the label cannot use are removed with what they hold; every
  //: `on...` attribute and every script-scheme value goes; a link with no safe address becomes its own words.
  function inert(root) {
    for (const el of [...root.querySelectorAll(DROP)]) el.remove();
    for (const el of [...root.querySelectorAll("*")]) {
      for (const attr of [...el.attributes]) {
        const name = attr.name.toLowerCase();
        if (name.startsWith("on") || name === "srcdoc" || name === "formaction" || name === "style" || (name !== "href" && /^\s*(javascript|vbscript|data):/i.test(attr.value))) {
          el.removeAttribute(attr.name);
        }
      }
      if (el.localName !== "a") continue;
      const href = cleanHref(el.getAttribute("href"));
      if (!href) {
        el.replaceWith(...el.childNodes);
        continue;
      }
      //: A link alone on its line is drawn by the renderer as a card with an icon and a host; a label keeps its words only.
      if (el.classList.contains("link-card")) {
        el.textContent = el.querySelector(".link-card-title")?.textContent || href;
        el.removeAttribute("class");
        el.removeAttribute("title");
      }
      el.setAttribute("href", href);
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    }
    return root;
  }

  //: The painter calls this as the label is made: remembers whether the words are rich on the element.
  function mark(label, parsed) {
    label.__wbRich = isRich(parsed);
  }

  //: After `mathLabel` in the layout: draws the rich words over the shape, or takes them away. Rich words hide the SVG
  //: text (which keeps the source and the layout) the same way maths does; an export clone drops the foreignObject
  //: and so carries the markdown source as plain words.
  function paint(groupEl, label, area, fontSize) {
    let fo = groupEl.querySelector(":scope > .sketch-label-rich");
    const text = label.__wbText;
    if (!label.__wbRich || !area || typeof renderMarkdown !== "function" || label.dataset.dir === "vertical" || !String(text ?? "").trim()) {
      fo?.remove();
      return;
    }
    groupEl.querySelector(":scope > .sketch-label-math")?.remove();
    if (!fo) {
      fo = document.createElementNS(NS, "foreignObject");
      fo.setAttribute("class", "sketch-label-rich");
      fo.setAttribute("pointer-events", "none");
      label.after(fo);
      const box = document.createElement("div");
      box.className = "wb-label-rich";
      fo.append(box);
    }
    fo.setAttribute("x", String(area.cx - area.w / 2));
    fo.setAttribute("y", String(area.cy - area.h / 2));
    fo.setAttribute("width", String(area.w));
    fo.setAttribute("height", String(area.h));
    const box = fo.firstElementChild;
    const align = label.dataset.align;
    box.style.textAlign = align || "center";
    box.style.fontSize = `${fontSize}px`;
    box.style.color = getComputedStyle(label).fill;
    box.dataset.valign = label.dataset.valign || "middle";
    //: Redrawn only when the words changed: a resize or a move paints the same markdown again.
    if (box.__wbSource !== text) {
      renderMarkdown(box, text);
      wbFmtState.textMore?.paintScripts(box);
      inert(box);
      indentItems(box, text);
      box.__wbSource = text;
    }
    label.style.opacity = "0";
  }

  //: The rendered label as lines for a picture: `{ depth, mark, runs: [{ t, b, i }] }`. A block is one line; a list
  //: item carries its bullet or number and its depth; a link is its words. Reads the DOM the board shows.
  function linesOf(box) {
    const lines = [];
    const runs = (node, flags, into) => {
      for (const child of node.childNodes) {
        if (child.nodeType === 3) {
          if (child.textContent) into.push({ t: child.textContent.replace(/\s+/g, " "), b: flags.b, i: flags.i });
        } else if (child.nodeType === 1) {
          const tag = child.localName;
          if (tag === "br") into.push({ br: true });
          else runs(child, { b: flags.b || /^(strong|b|h[1-6]|th)$/.test(tag), i: flags.i || /^(em|i)$/.test(tag) }, into);
        }
      }
    };
    const push = (node, extra) => {
      const into = [];
      runs(node, { b: /^h[1-6]$/.test(node.localName), i: false }, into);
      let line = { ...extra, runs: [] };
      for (const run of into) {
        if (run.br) {
          lines.push(line);
          line = { depth: extra.depth, mark: "", runs: [] };
        } else line.runs.push(run);
      }
      if (line.runs.some((run) => run.t.trim()) || line.mark) lines.push(line);
    };
    for (const block of box.children) {
      if (/^(ul|ol)$/.test(block.localName)) {
        let n = Number(block.getAttribute("start")) || 1;
        for (const li of block.children) {
          if (li.localName === "li") push(li, { depth: Number(li.dataset.depth) || 0, mark: block.localName === "ol" ? `${n++}. ` : "• " });
        }
      } else push(block, { depth: 0, mark: "" });
    }
    return lines;
  }

  //: The picture clone of a shape: its rich label becomes SVG text in the same box (a foreignObject does not travel into
  //: an SVG, PNG or PDF), so the picture shows the lists, bold, italic and link words, not the markdown source.
  function exportInto(el, clone) {
    const fo = el.querySelector(":scope > .sketch-label-rich");
    const copy = clone.querySelector(":scope > .sketch-label-rich");
    const label = el.querySelector(":scope > .sketch-label");
    const box = fo?.firstElementChild;
    if (!copy || !label || !box) return;
    const look = getComputedStyle(label);
    const size = parseFloat(box.style.fontSize) || parseFloat(look.fontSize) || 14;
    const lh = size * 1.3;
    const x0 = Number(fo.getAttribute("x"));
    const y0 = Number(fo.getAttribute("y"));
    const w = Number(fo.getAttribute("width"));
    const h = Number(fo.getAttribute("height"));
    const align = box.style.textAlign || "center";
    const lines = linesOf(box);
    const top = y0 + (box.dataset.valign === "top" ? 0 : box.dataset.valign === "bottom" ? h - lines.length * lh : (h - lines.length * lh) / 2);
    const text = document.createElementNS(NS, "text");
    text.setAttribute("fill", box.style.color || look.fill);
    text.setAttribute("font-size", String(size));
    text.setAttribute("font-family", look.fontFamily);
    text.setAttribute("dominant-baseline", "central");
    text.setAttribute("text-anchor", align === "left" || align === "start" ? "start" : align === "right" || align === "end" ? "end" : "middle");
    const x = align === "left" || align === "start" ? x0 : align === "right" || align === "end" ? x0 + w : x0 + w / 2;
    lines.forEach((line, row) => {
      const indent = line.depth * 1.2 * size;
      const lead = document.createElementNS(NS, "tspan");
      lead.setAttribute("x", String(x + (text.getAttribute("text-anchor") === "start" ? indent : text.getAttribute("text-anchor") === "middle" ? indent / 2 : 0)));
      lead.setAttribute("y", String(top + (row + 0.5) * lh));
      lead.textContent = line.mark;
      text.append(lead);
      for (const run of line.runs) {
        const span = document.createElementNS(NS, "tspan");
        if (run.b) span.setAttribute("font-weight", "700");
        if (run.i) span.setAttribute("font-style", "italic");
        span.textContent = run.t;
        text.append(span);
      }
    });
    clone.querySelectorAll(":scope > .sketch-label").forEach((node) => node.remove());
    copy.replaceWith(text);
  }

  //: The Format panel's Rich text tick, from the selected shapes (Mixed when they differ).
  function richSync(shapes) {
    const box = document.getElementById("wb-fmt-lmd");
    if (!box || !shapes.length) return;
    const rich = shapes.map((entry) => isRich(wbFmtSketch(entry)));
    box.checked = rich[0];
    box.indeterminate = new Set(rich).size > 1;
  }

  function bind() {
    document.getElementById("wb-fmt-lmd")?.addEventListener("change", (e) => {
      const on = e.target.checked;
      wbFmtApply("shapelabel", (entry, kind) => (kind === "shape" ? { [KEY]: on ? true : undefined } : null), on ? "Rich text on." : "Rich text off.");
    });
  }

  //: The key joins the lists the panel and Reset style walk (the same step `whiteboard-label.js` takes for its own).
  WB_TEXT_LOOK_KEYS.shape.push(KEY);
  WB_SKETCH_RESET_KEYS.push(KEY);
  onSurface("board", bind);

  wbFmtState.richLabel = { cleanHref, isRich, listDepths, indentItems, inert, mark, paint, sync: richSync, linesOf, exportInto, KEY };
})();
