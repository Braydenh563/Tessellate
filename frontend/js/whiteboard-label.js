// whiteboard-label.js: where a shape's words sit and what is behind them
// (WHITEBOARD_PLAN, "Placed from INBOX, 2026-11-01", rows 1, 4, 5 and 7; draw.io's
// Text tab: label background and border colour, label position, label width
// and word wrap, spacing per side).
//
// Five optional values on a drawn shape's data, each stored only when set:
// `label_bg` and `label_border` (a plain hex colour: a rounded box behind the
// words), `label_pos` (above, below, left or right of the shape; none is
// inside), `label_width` (the words wrap at this many board pixels, whatever
// the shape's width), `label_wrap` (false: only a typed line break ends a
// line) and `label_pad` ([top, right, bottom, left] pixels kept clear of the
// words, on top of the shape's own 8). A connector's label already has its
// chip (`label chip` in the link row), so these are for shapes.
//
// The painting and layout stay in whiteboard.js (`wbPaintShapeLabel`,
// `wbLayoutShapeLabel`, `wbEditShapeLabel`); they call this file through
// `wbFmtState.label` at run time, so a board without it draws the words as
// before. Loaded in the `boards` bundle after whiteboard-format.js, whose
// panel rows (index.html, `data-fmt="shapelabel"`) it wires.

(() => {
  const NS = "http://www.w3.org/2000/svg";
  const POSITIONS = ["above", "below", "left", "right"];
  //: The gap between a shape's edge and words set outside it, and how wide words set beside it wrap.
  const OUT_GAP = 6;
  const SIDE_WIDTH = 120;
  const MIN_OUTSIDE_WIDTH = 96;
  //: The band words outside a shape sit in: far taller than any label, so the first line
  //: (below) or the last (above) is what lands on the gap.
  const BAND = 1000;
  const KEYS = ["label_bg", "label_border", "label_pos", "label_width", "label_wrap", "label_pad"];

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const whole = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? 0 : Number(v));

  //: What a shape's data says about its label's place, as plain numbers: nothing set reads as
  //: the all-default look, so a caller never branches on undefined.
  function look(parsed) {
    const pad = Array.isArray(parsed?.label_pad) ? [0, 1, 2, 3].map((i) => clamp(Math.round(whole(parsed.label_pad[i])), 0, 80)) : [0, 0, 0, 0];
    const width = whole(parsed?.label_width);
    return {
      pos: POSITIONS.includes(parsed?.label_pos) ? parsed.label_pos : "",
      pad,
      width: width > 0 ? clamp(Math.round(width), 24, 2000) : 0,
      wrap: parsed?.label_wrap !== false,
      bg: wbHexColour(parsed?.label_bg) || "",
      border: wbHexColour(parsed?.label_border) || "",
    };
  }

  //: The band the words are written in, from the one the shape gives (`wbShapeLabelArea`):
  //: words outside get a band beside the shape, a width overrides the band's, and the spacing
  //: per side pulls the band in. `align` and `valign` come back when the place forces them
  //: (words beside a shape hug it; words above sit on it).
  function area(lk, given, bbox) {
    if (!lk) return given;
    let out = { ...given };
    if (lk.pos) {
      const cx = bbox.minX + bbox.width / 2;
      const cy = bbox.minY + bbox.height / 2;
      const across = lk.width || Math.max(bbox.width, MIN_OUTSIDE_WIDTH);
      if (lk.pos === "above") out = { cx, cy: bbox.minY - OUT_GAP - BAND / 2, w: across, h: BAND, valign: "bottom" };
      else if (lk.pos === "below") out = { cx, cy: bbox.maxY + OUT_GAP + BAND / 2, w: across, h: BAND, valign: "top" };
      else {
        const wide = lk.width || SIDE_WIDTH;
        out = lk.pos === "left"
          ? { cx: bbox.minX - OUT_GAP - wide / 2, cy, w: wide, h: bbox.height, align: "right" }
          : { cx: bbox.maxX + OUT_GAP + wide / 2, cy, w: wide, h: bbox.height, align: "left" };
      }
    } else if (lk.width) {
      out.w = lk.width;
    }
    const [t, r, b, l] = lk.pad;
    if (t + r + b + l) {
      out = { ...out, cx: out.cx + (l - r) / 2, cy: out.cy + (t - b) / 2, w: Math.max(24, out.w - l - r), h: Math.max(0, out.h - t - b) };
    }
    return out;
  }

  //: Where the in-place editor opens, in board units: over the band for words inside, and in a
  //: strip beside the shape for words outside.
  function editBox(lk, given, bbox) {
    const placed = area(lk, given, bbox);
    if (!lk?.pos) return { x: placed.cx - placed.w / 2, y: placed.cy - Math.max(bbox.height, 24) / 2, w: placed.w, h: Math.max(bbox.height, 24) };
    const strip = 48;
    const w = placed.w;
    const x = placed.cx - w / 2;
    if (lk.pos === "above") return { x, y: bbox.minY - OUT_GAP - strip - lk.pad[2], w, h: strip };
    if (lk.pos === "below") return { x, y: bbox.maxY + OUT_GAP + lk.pad[0], w, h: strip };
    return { x, y: bbox.minY + bbox.height / 2 - strip / 2, w, h: strip };
  }

  //: Called as the label is painted: remembers the look on the element (the layout reads it), and
  //: picks the ink for the colour behind the words when the shape's own colour is not the ground.
  function paint(label, parsed) {
    const lk = look(parsed);
    label.__wbLook = lk;
    if (lk.bg && !parsed.label_color) label.style.fill = wbCoreInkFor(lk.bg);
    return lk;
  }

  function drop(groupEl) {
    groupEl?.querySelector?.(":scope > .sketch-label-bg")?.remove();
  }

  //: The box behind the words, from where they were laid out. Attributes rather than a
  //: stylesheet, because the export clones the group into a standalone SVG.
  function backdrop(groupEl, label) {
    const lk = label.__wbLook;
    let rect = groupEl.querySelector(":scope > .sketch-label-bg");
    if (!lk || (!lk.bg && !lk.border)) {
      rect?.remove();
      return;
    }
    const words = label.getBBox();
    if (!words.width || !words.height) {
      rect?.remove();
      return;
    }
    if (!rect) {
      rect = document.createElementNS(NS, "rect");
      rect.setAttribute("class", "sketch-label-bg");
      rect.setAttribute("pointer-events", "none");
      rect.setAttribute("rx", "4");
      groupEl.insertBefore(rect, label);
    }
    const gapX = 6;
    const gapY = 3;
    rect.setAttribute("x", String(words.x - gapX));
    rect.setAttribute("y", String(words.y - gapY));
    rect.setAttribute("width", String(words.width + gapX * 2));
    rect.setAttribute("height", String(words.height + gapY * 2));
    rect.setAttribute("fill", lk.bg || "none");
    if (lk.border) {
      rect.setAttribute("stroke", lk.border);
      rect.setAttribute("stroke-width", "1");
    } else {
      rect.removeAttribute("stroke");
      rect.removeAttribute("stroke-width");
    }
    const turn = label.getAttribute("transform");
    if (turn) rect.setAttribute("transform", turn);
    else rect.removeAttribute("transform");
  }

  const entryLook = (entry) => look(wbFmtSketch(entry));

  //: The panel's rows show the first shape's values; a value the selection does not share reads Mixed.
  function sync(takes, entries) {
    if (!takes.has("shapelabel")) return;
    const shapes = entries.filter((e) => wbFmtKind(e) === "shape");
    if (!shapes.length) return;
    const looks = shapes.map(entryLook);
    const first = looks[0];
    const mixed = (pick) => new Set(looks.map((l) => JSON.stringify(pick(l)))).size > 1;
    const put = (id, value, prop = "value") => {
      const el = document.getElementById(id);
      if (el && document.activeElement !== el) el[prop] = value;
      return el;
    };
    for (const [id, onId, key] of [["wb-fmt-lbg", "wb-fmt-lbg-on", "bg"], ["wb-fmt-lborder", "wb-fmt-lborder-on", "border"]]) {
      const box = put(onId, Boolean(first[key]), "checked");
      if (box) box.indeterminate = mixed((l) => Boolean(l[key]));
      const colour = document.getElementById(id);
      if (colour && document.activeElement !== colour) colour.value = first[key] || colour.dataset.seed || colour.value;
      colour?.classList.toggle("wb-colour-off", !mixed((l) => Boolean(l[key])) && !first[key]);
    }
    const pos = document.getElementById("wb-fmt-lpos");
    if (pos && document.activeElement !== pos) wbFmtShowMixed(pos, mixed((l) => l.pos), first.pos);
    const width = document.getElementById("wb-fmt-lwidth");
    if (width && document.activeElement !== width) wbFmtShowMixed(width, mixed((l) => l.width), first.width || "");
    const wrap = put("wb-fmt-lwrap", first.wrap, "checked");
    if (wrap) wrap.indeterminate = mixed((l) => l.wrap);
    wbFmtState.richLabel?.sync(shapes);
    for (const [i, id] of ["wb-fmt-lpad0", "wb-fmt-lpad1", "wb-fmt-lpad2", "wb-fmt-lpad3"].entries()) {
      const el = document.getElementById(id);
      if (el && document.activeElement !== el) wbFmtShowMixed(el, mixed((l) => l.pad[i]), first.pad[i] || "");
    }
  }

  const shapesOnly = (patch) => (entry, kind) => (kind === "shape" ? patch(entry) : null);

  function bind() {
    const on = (id, type, fn) => document.getElementById(id)?.addEventListener(type, fn);
    const setColour = (key, id) => (e) => {
      const hex = wbHexColour(e.target.value) || undefined;
      wbFmtApply("shapelabel", shapesOnly(() => ({ [key]: hex })), hex ? "Label colour set." : "Label colour taken off.");
      document.getElementById(id)?.classList.remove("wb-colour-off");
    };
    for (const [key, id, onId, word] of [["label_bg", "wb-fmt-lbg", "wb-fmt-lbg-on", "Label background"], ["label_border", "wb-fmt-lborder", "wb-fmt-lborder-on", "Label outline"]]) {
      on(onId, "change", (e) => {
        const hex = e.target.checked ? wbHexColour(document.getElementById(id)?.value) || undefined : undefined;
        wbFmtApply("shapelabel", shapesOnly(() => ({ [key]: hex })), hex ? `${word} on.` : `${word} off.`);
      });
      on(id, "change", setColour(key, id));
    }
    on("wb-fmt-lpos", "change", (e) => {
      const pos = POSITIONS.includes(e.target.value) ? e.target.value : undefined;
      wbFmtApply("shapelabel", shapesOnly(() => ({ label_pos: pos })), pos ? `Text ${pos} the shape.` : "Text inside the shape.");
    });
    on("wb-fmt-lwidth", "change", (e) => {
      const raw = e.target.value === "" ? 0 : clamp(Math.round(Number(e.target.value) || 0), 24, 2000);
      wbFmtApply("shapelabel", shapesOnly(() => ({ label_width: raw || undefined })), raw ? `Text width ${raw}px.` : "Text width automatic.");
    });
    on("wb-fmt-lwrap", "change", (e) => {
      const wrap = e.target.checked;
      wbFmtApply("shapelabel", shapesOnly(() => ({ label_wrap: wrap ? undefined : false })), wrap ? "Words wrap." : "Words stay on one line.");
    });
    for (const i of [0, 1, 2, 3]) {
      on(`wb-fmt-lpad${i}`, "change", () => {
        const sides = [0, 1, 2, 3].map((k) => {
          const el = document.getElementById(`wb-fmt-lpad${k}`);
          return el && el.value !== "" ? clamp(Math.round(Number(el.value) || 0), 0, 80) : 0;
        });
        const set = sides.some(Boolean);
        wbFmtApply("shapelabel", shapesOnly(() => ({ label_pad: set ? sides : undefined })), set ? "Text spacing set." : "Text spacing default.");
      });
    }
  }

  //: The look keys join the lists the panel and Reset style walk, so no list in another file needs
  //: a second copy of them. (The group itself is in `WB_FMT_FIELDS.shape`, beside the other rows.)
  WB_TEXT_LOOK_KEYS.shape.push(...KEYS);
  WB_SKETCH_RESET_KEYS.push(...KEYS);
  onSurface("board", bind);

  wbFmtState.label = { look, area, editBox, paint, drop, backdrop, sync, KEYS };
})();
