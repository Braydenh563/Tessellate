(() => {
  // whiteboard-effects.js: the Format panel's finishing effects (WHITEBOARD_PLAN, LEDGER L-whiteboard-37, 38, 40 and 47):
  // a shadow under words, a glass gloss on a shape, a picture as a shape's fill, a mirror for a sticky, a picture or a
  // frame, and a small status bar. Held on `wbFmtState.effects`, so no new global name; whiteboard.js calls it from
  // one-line hooks (`paintShape`, `paintObject`, `refreshStatus`), whiteboard-format.js from `sync`, `flipObjects`.
  // Nothing here builds HTML from a string: every node is made with createElementNS and an attribute, which the CSP allows.
  const NS = "http://www.w3.org/2000/svg";
  const MEDIA = /^\/media\/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;

  // --- Text shadow (L-whiteboard-38) ------------------------------------------------------------------------
  //: Pure: what a label's inline style is. A box's words take CSS `text-shadow`; an SVG label (a shape's) takes a
  //: `drop-shadow` filter, which every browser draws on SVG text. Both are inline, so an export of the DOM keeps them.
  function textShadowStyle(svg, on) {
    if (!on) return { textShadow: "", filter: "" };
    return svg ? { textShadow: "", filter: "drop-shadow(1px 1px 1px rgb(0 0 0 / 0.5))" } : { textShadow: "1px 1px 2px rgb(0 0 0 / 0.5)", filter: "" };
  }
  function paintTextShadow(el, on) {
    if (!el?.style) return;
    const style = textShadowStyle(Boolean(el.namespaceURI?.endsWith("/svg")), on === true);
    el.style.textShadow = style.textShadow;
    el.style.filter = style.filter;
  }

  // --- A shape's gloss and picture fill (L-whiteboard-37 and 40) --------------------------------------------
  const make = (tag, attrs, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, String(value));
    parent?.appendChild(el);
    return el;
  };
  const own = (group, selector) => group.querySelector(`:scope > ${selector}`);

  //: A glass gloss: a white sheen over the top half of the shape, fading to a faint one below, drawn over the fill and
  //: line as a second path with the same outline. It takes no pointer, so the shape is picked as it was.
  function paintGlass(group, on, pathData, id) {
    let overlay = own(group, "path.wb-glass");
    let defs = own(group, "defs.wb-glass-defs");
    if (!on || !pathData) {
      overlay?.remove();
      defs?.remove();
      return;
    }
    const paint = `wbgl-${id}`;
    if (!defs) {
      defs = make("defs", { class: "wb-glass-defs" }, null);
      const gradient = make("linearGradient", { id: paint, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
      for (const [offset, opacity] of [[0, 0.62], [0.5, 0.2], [0.5, 0], [1, 0.1]]) {
        make("stop", { offset, "stop-color": "#ffffff", "stop-opacity": opacity }, gradient);
      }
      group.prepend(defs);
    }
    if (!overlay) {
      overlay = make("path", { class: "wb-glass", fill: `url(#${paint})`, stroke: "none", "pointer-events": "none", "aria-hidden": "true" }, null);
      (own(group, ".sketch-path") || group).after(overlay);
    }
    if (overlay.getAttribute("d") !== pathData) overlay.setAttribute("d", pathData);
  }

  //: A picture in the shape: an `<image>` under the outline, cut to it by a clip path of the same `d`, over the fill
  //: colour, which is switched off so the picture shows. Only a saved `/media/` address is drawn.
  function paintFillImage(group, url, pathData, id) {
    const pathEl = own(group, ".sketch-path");
    let image = own(group, "image.wb-fill-image");
    let defs = own(group, "defs.wb-fillimg-defs");
    const href = typeof url === "string" && MEDIA.test(url) ? url : "";
    if (!href || !pathEl || !pathData) {
      image?.remove();
      defs?.remove();
      return;
    }
    let box = null;
    try {
      box = pathEl.getBBox();
    } catch {
      box = null;
    }
    if (!box || !(box.width > 0) || !(box.height > 0)) return;
    const clipId = `wbfi-${id}`;
    if (!defs) {
      defs = make("defs", { class: "wb-fillimg-defs" }, null);
      make("path", {}, make("clipPath", { id: clipId }, defs));
      group.prepend(defs);
    }
    const clipPath = defs.querySelector("clipPath > path");
    if (clipPath.getAttribute("d") !== pathData) clipPath.setAttribute("d", pathData);
    if (!image) {
      image = make("image", { class: "wb-fill-image", preserveAspectRatio: "xMidYMid slice", "clip-path": `url(#${clipId})`, "pointer-events": "none", "aria-hidden": "true" }, null);
      pathEl.before(image);
    }
    const src = mediaSrc(href);
    for (const [name, value] of [["href", src], ["x", box.x], ["y", box.y], ["width", box.width], ["height", box.height]]) {
      if (image.getAttribute(name) !== String(value)) image.setAttribute(name, String(value));
    }
    pathEl.setAttribute("fill", "none");
  }

  //: The hook in the shape's paint (whiteboard.js, after the label): `parsed` is the shape's own data, null for a connector.
  function paintShape(group, parsed, pathData, id) {
    paintFillImage(group, parsed?.fill_image, pathData, id);
    paintGlass(group, parsed?.glass === true, pathData, id);
    paintTextShadow(own(group, ".sketch-label"), parsed?.label_shadow === true);
  }

  // --- A sticky's, picture's or frame's mirror (L-whiteboard-47) --------------------------------------------
  //: Pure: the data's flips as the word the stylesheet reads ("x", "y", "xy" or "").
  const flipWord = (data) => `${data?.flip_x === true ? "x" : ""}${data?.flip_y === true ? "y" : ""}`;
  //: Pure: how far an item's box moves to sit where its mirror image about the frame's box would.
  function mirrorShift(box, frame, axis) {
    return axis === "h"
      ? { dx: frame.minX + frame.maxX - box.maxX - box.minX, dy: 0 }
      : { dx: 0, dy: frame.minY + frame.maxY - box.maxY - box.minY };
  }

  //: The hook in a board object's paint (whiteboard.js, after the kind's own paint): a sticky's fold side, the words'
  //: shadow. The words themselves are never mirrored: a flipped note keeps its text readable, the card is what turns.
  function paintObject(node, d) {
    const data = d.data || {};
    if (d.kind === "text") {
      const word = flipWord(data);
      if (word) node.dataset.flip = word;
      else delete node.dataset.flip;
      paintTextShadow(node.querySelector(".wb-text-content"), data.text_shadow === true);
    }
  }

  //: Mirror the selected pictures, notes and frames: a picture or a note toggles its own flip (a picture's pixels, a
  //: note's fold corner); a frame mirrors what it holds about its own middle, so the words inside keep reading the same
  //: way round. Returns the rows to save, for `wbFmtFlip`'s one gesture.
  function flipObjects(axis, entries) {
    const rows = [];
    const field = axis === "h" ? "flip_x" : "flip_y";
    for (const entry of entries) {
      const item = entry.item;
      if (item.kind === "text" || item.kind === "image") {
        const next = { ...item.data };
        if (next[field] === true) delete next[field];
        else next[field] = true;
        item.data = next;
        rows.push({ kind: "object", item });
      } else if (item.kind === "frame") {
        const frame = wbItemBBox("object", item);
        for (const key of wbFrameContents(item)) {
          const sep = key.indexOf(":");
          const kind = key.slice(0, sep);
          const held = wbFindItem(kind, Number(key.slice(sep + 1)));
          const box = held && wbItemBBox(kind, held);
          if (!box) continue;
          if (kind === "sketch") {
            const parsed = wbSketchParsedData(held);
            if (typeof parsed?.d !== "string") continue;
            wbSketchSetD(held, wbTransformPathD(parsed.d, {
              sx: axis === "h" ? -1 : 1,
              sy: axis === "v" ? -1 : 1,
              anchorX: (frame.minX + frame.maxX) / 2,
              anchorY: (frame.minY + frame.maxY) / 2,
            }));
          } else {
            const { dx, dy } = mirrorShift(box, frame, axis);
            held.x += dx;
            held.y += dy;
          }
          rows.push({ kind, item: held });
        }
      }
    }
    return rows;
  }

  // --- The status bar (L-whiteboard-47) ---------------------------------------------------------------------
  //: Pure: the three facts the bar says, in order: zoom, the tool in hand and how much is selected.
  function statusParts(percent, tool, count) {
    return [`${Math.round(percent)}%`, tool || "Select", count > 0 ? `${count} selected` : "Nothing selected"];
  }
  const STATUS_PREF = "wb-view-status";
  function toolName() {
    const pressed = document.querySelector("#wb-tool-group [data-tool].active");
    const title = pressed?.getAttribute("aria-label") || pressed?.dataset.tool || "";
    return title.replace(/\s*\([^)]*\)\s*$/, "");
  }
  function refreshStatus() {
    const bar = document.getElementById("wb-status-bar");
    if (!bar || bar.classList.contains("hidden")) return;
    const count = wbMultiSelection.size || (wbSelectedItem ? 1 : 0);
    const parts = statusParts(wbShowZoomLevel.state?.pct ?? 100, toolName(), count);
    ["wb-status-zoom", "wb-status-tool", "wb-status-count"].forEach((id, i) => {
      const el = document.getElementById(id);
      if (el && el.textContent !== parts[i]) el.textContent = parts[i];
    });
  }

  // --- The panel's own controls --------------------------------------------------------------------------------
  //: Read by `wbFmtValue` for the panel's rows; a text box's words and a shape's label are both "the words".
  function value(entry, field) {
    const raw = entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data || {};
    if (field === "tshadow") return raw[entry.kind === "sketch" ? "label_shadow" : "text_shadow"] === true;
    if (field === "glass") return raw.glass === true;
    if (field === "fillimg") return typeof raw.fill_image === "string" ? raw.fill_image : "";
    return null;
  }
  //: Keeps the switches in step with the selection (called from the panel's sync with the fields it shows).
  function sync(takes, sharing) {
    const mixed = (field) => new Set(sharing.map((e) => JSON.stringify(value(e, field)))).size > 1;
    for (const [id, field] of [["wb-fmt-tshadow", "tshadow"], ["wb-fmt-glass", "glass"]]) {
      const box = document.getElementById(id);
      if (!takes.has(field) || !box || document.activeElement === box) continue;
      box.checked = value(sharing[0], field) === true;
      box.indeterminate = mixed(field);
    }
    const clear = document.getElementById("wb-fmt-fillimg-clear");
    if (clear && takes.has("fillimg")) clear.disabled = !sharing.some((e) => value(e, "fillimg"));
  }

  async function uploadPicture(file) {
    if (!file || !file.type?.startsWith("image/")) return null;
    if (file.size > 50 * 1024 * 1024) {
      toast("That picture is over 50 MB. Pick a smaller one.");
      return null;
    }
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("board", "true");
      return (await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body }))?.url || null;
    } catch (err) {
      toast(err?.message || "The picture could not be uploaded.");
      return null;
    }
  }

  function wire() {
    const on = (id, type, fn) => document.getElementById(id)?.addEventListener(type, fn);
    on("wb-fmt-tshadow", "change", (e) => wbFmtApply("text", (entry, kind) => ({ [kind === "shape" ? "label_shadow" : "text_shadow"]: e.target.checked || undefined }), e.target.checked ? "Text shadow on." : "Text shadow off."));
    on("wb-fmt-glass", "change", (e) => wbFmtApply("glass", () => ({ glass: e.target.checked || undefined }), e.target.checked ? "Glass on." : "Glass off."));
    on("wb-fmt-fillimg", "click", () => document.getElementById("wb-fmt-fillimg-file")?.click());
    on("wb-fmt-fillimg-file", "change", async (e) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      const url = await uploadPicture(file);
      if (url) await wbFmtApply("fillimg", () => ({ fill_image: url }), "Picture fills the shape.");
    });
    on("wb-fmt-fillimg-clear", "click", () => wbFmtApply("fillimg", () => ({ fill_image: undefined }), "Picture fill removed."));
    const bar = document.getElementById("wb-status-bar");
    const box = document.getElementById("wb-view-status");
    if (bar && box) {
      const show = (shown) => {
        box.checked = shown;
        bar.classList.toggle("hidden", !shown);
        refreshStatus();
      };
      show(prefs.get(STATUS_PREF, null) === "on");
      box.addEventListener("change", () => {
        prefs.set(STATUS_PREF, box.checked ? "on" : "off");
        show(box.checked);
      });
    }
  }
  onSurface("board", wire);

  wbFmtState.effects = { textShadowStyle, paintTextShadow, paintShape, paintObject, flipWord, mirrorShift, flipObjects, statusParts, refreshStatus, value, sync };
})();
