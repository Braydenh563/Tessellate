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

  //: Pure (node-tested): the depth of each list item in the markdown, in order, outside code fences. `renderMarkdown` draws
  //: an indented item flat inside its list, so the label carries the depth itself: a deeper indent than the item
  //: above opens a level, a shallower one closes back to the level it matches (a tab counts as four spaces).
  function listDepths(text) {
    const out = [];
    const stack = [];
    let fenced = false;
    for (const line of String(text ?? "").split("\n")) {
      if (/^\s*(```|~~~)/.test(line)) {
        fenced = !fenced;
        continue;
      }
      const hit = !fenced && /^([ \t]*)([-*+]|\d{1,9}[.)])\s+\S/.exec(line);
      if (!hit) {
        if (!fenced && !line.trim()) continue;
        if (!fenced && !/^\s/.test(line)) stack.length = 0;
        continue;
      }
      const width = hit[1].replace(/\t/g, "    ").length;
      while (stack.length && stack[stack.length - 1] > width) stack.pop();
      if (!stack.length || stack[stack.length - 1] < width) stack.push(width);
      out.push(stack.length - 1);
    }
    return out;
  }

  //: Puts each item's depth on the rendered list as a left margin (set through the style object: the CSP refuses a style attribute).
  function indentItems(box, text) {
    const depths = listDepths(text);
    const items = [...box.querySelectorAll("li")];
    if (!depths.some(Boolean) || depths.length !== items.length) return;
    items.forEach((li, i) => {
      if (depths[i]) {
        li.dataset.depth = String(depths[i]);
        li.style.marginLeft = `${depths[i] * 1.2}em`;
      }
    });
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

  //: The Format panel's Rich text tick, from the selected shapes (Mixed when they differ).
  function sync(shapes) {
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

  wbFmtState.richLabel = { cleanHref, isRich, listDepths, indentItems, inert, mark, paint, sync, KEY };
})();
