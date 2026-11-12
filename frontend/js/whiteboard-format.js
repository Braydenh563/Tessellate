// whiteboard-format.js: the board's Format panel (2026-10-05, the features
// audit's controls redesign, section 9.2 item 3; WHITEBOARD_PLAN decision 19).
//
// **Why a panel.** The context bar is the quick bar: at most seven controls
// per kind (decision 11), the ones a person reaches for while working. The
// long tail (a number for where a thing is and how big, its angle, a flip,
// how see-through it is, a shadow, the text in a shape, where a connector's
// label sits) had nowhere to go but more popovers. draw.io keeps all of it
// in one docked Format panel with three tabs, and so does this: Style, Text
// and Arrange, on the board's right edge, hidden until asked for (the "..."
// row on the bar, the View menu, Ctrl+Shift+P, the palette).
//
// **One change, one undo step.** Every field writes through `wbFmtApply`,
// which runs the edit inside `wbRecordGesture`, so a change to five selected
// shapes is one Ctrl+Z.
//
// **The arrange buttons are the command table's** (`WB_COMMANDS`,
// whiteboard-commands.js): order, align, distribute, same size, group and
// lock are built from the table's rows, so their names, icons and keys are
// the menus' and cannot drift.
//
// Loaded in the Library bundle after whiteboard-commands.js (`LAZY_MODULES`,
// app.js); its top level declares and wires, everything else is read at call
// time.

const WB_FMT_KEY = "wb-format";
const WB_FMT_TABS = ["style", "text", "arrange", "data"];

//: What is selected, as `{kind, id, item, bbox}` rows: the multi-selection
//: when there is one, else the one selected item.
//: The Format panel's open tab and its queued sync.
const wbFmtState = { sizeClip: null, fmtTab: "style", fmtSyncQueued: false, fmtLiveQueued: false, fmtFrameQueued: false, links: new Map() };

function wbFmtEntries() {
  //: A selection of many keeps its connectors (which have no box: "Select all
  //: connectors" then a colour has to reach them), where the arrange maths in
  //: `wbSelectionEntries` leaves them out.
  if (wbMultiSelection.size) {
    return [...wbMultiSelection].map((key) => {
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
      const item = wbFindItem(kind, id);
      return item ? { kind, id, item, bbox: wbItemBBox(kind, item) } : null;
    }).filter(Boolean);
  }
  if (!wbSelectedItem) return [];
  const item = wbFindItem(wbSelectedItem.kind, wbSelectedItem.id);
  //: A connector has no box of its own (its path is worked out from its
  //: ends), so it comes with none, and the geometry rows skip it.
  return item ? [{ kind: wbSelectedItem.kind, id: wbSelectedItem.id, item, bbox: wbItemBBox(wbSelectedItem.kind, item) }] : [];
}

//: What one entry is, for the panel: which fields it shows.
function wbFmtKind(entry) {
  if (entry.kind === "node") return "note";
  if (entry.kind === "object") {
    const k = entry.item.kind;
    if (WB_MAP_KINDS.has(k)) return "topic";
    return k === "text" || k === "image" || k === "frame" || k === "table" || k === "diagram" ? k : null;
  }
  let parsed = null;
  try {
    parsed = JSON.parse(entry.item.data);
  } catch {
    return null;
  }
  if (String(parsed?.type || "").startsWith("link-")) return wbLinkTakesLabel(entry.item, parsed) ? "link" : null;
  if (typeof parsed?.d !== "string") return null;
  //: Ends first (the 22-10 bug doc): a filled end mark closes its own
  //: subpath with a Z, which `wbShapeLabelKind` read as a closed shape, so a
  //: line given an End mark became a "shape" here, lost its Start and End
  //: rows, and could not be turned back into a plain line.
  if (wbSketchTakesCaps(parsed)) return "arrow";
  if (wbShapeLabelKind(parsed)) return "shape";
  return "line";
}

//: The fields each kind takes, by the `data-fmt` names in index.html.
const WB_FMT_FIELDS = {
  shape: ["stroke", "strokealpha", "width", "dash", "fill", "alpha", "shadow", "shadowset", "rough", "text", "fit", "geometry", "flip", "style-lib", "props", "rawstyle", "pattern", "round", "linestyle", "flow", "fillstyle", "fillalpha", "gradient", "tip", "shapelabel", "ports"],
  line: ["stroke", "strokealpha", "width", "dash", "alpha", "shadow", "shadowset", "rough", "geometry", "flip", "style-lib", "props", "rawstyle", "pattern", "round", "linestyle", "flow", "tip"],
  //: A straight line or arrow: a line that takes ends.
  arrow: ["stroke", "strokealpha", "width", "dash", "caps", "alpha", "shadow", "shadowset", "rough", "geometry", "flip", "style-lib", "props", "rawstyle", "pattern", "round", "linestyle", "flow", "tip"],
  link: ["stroke", "width", "dash", "alpha", "rough", "route", "edgeshape", "textpath", "jumps", "caps", "label-t", "linklook", "props", "rawstyle", "pattern", "round", "linestyle", "flow", "jumpsize", "gapstart", "gapend", "tip", "loop", "label2", "label2-t"],
  text: ["stroke", "fill", "fillalpha", "alpha", "shadow", "shadowset", "radii", "pad", "fold", "text", "geometry", "angle", "style-lib", "props", "rawstyle"],
  image: ["alpha", "shadow", "shadowset", "radii", "imageborder", "crop", "trim", "cropbox", "pixels", "replace", "geometry", "angle", "props"],
  frame: ["pad", "stack", "geometry", "props"],
  table: ["alpha", "shadow", "shadowset", "radii", "tableheader", "stripes", "geometry", "props"],
  note: ["geometry", "angle"],
  //: A Mermaid diagram object: the fill and the line it draws with (INBOX 1486).
  diagram: ["fill", "fillalpha", "strokealpha"],
};

//: Where an item keeps the opacity of its fill and of its line: a drawn shape's
//: own two numbers, a text box's and a diagram's `bg_alpha` and `line_alpha`.
function wbFmtAlphaKeys(entry) {
  return entry.kind === "sketch" ? { fill: "fillOpacity", line: "opacity" } : { fill: "bg_alpha", line: "line_alpha" };
}

//: What an item needs first so a fill opacity means something: a shape or a
//: text box with no fill is given one; a diagram always has its accent.
function wbFmtFillFirst(entry) {
  const colour = document.getElementById("wb-fmt-fill")?.value || "#3355ff";
  if (entry.kind === "sketch") return wbFmtSketch(entry).fill ? {} : { fill: colour };
  const bg = entry.item.data?.bg;
  return entry.item.kind === "diagram" || (bg && bg !== "transparent") ? {} : { bg: colour };
}

//: The fill's own opacity (draw.io's "Fill opacity", PaintZ's fill toggle) and
//: the line's: each a slider with its number and the five presets, the preset
//: that matches lit. The line and the words keep theirs.
function wbFmtShowAlpha(name, isMixed, value) {
  const slider = document.getElementById(`wb-fmt-${name}`);
  const out = document.getElementById(`wb-fmt-${name}-out`);
  if (slider && document.activeElement !== slider) slider.value = value;
  if (out) out.textContent = isMixed ? "Mixed" : `${value}%`;
  for (const button of document.querySelectorAll(`[data-alpha-for="${name}"]`)) {
    button.setAttribute("aria-pressed", !isMixed && Number(button.dataset.alphaPreset) === value ? "true" : "false");
  }
}

function wbFmtCanRound(entry) {
  if (entry.kind !== "sketch") return false;
  const parsed = wbFmtSketch(entry);
  if (typeof parsed.d === "string") return wbRoundedPathD(parsed.d, 1) !== parsed.d;
  return String(parsed.type || "").startsWith("link-") && wbLinkRouteName(parsed) === "elbow";
}

function wbFmtSketch(entry) {
  try {
    return JSON.parse(entry.item.data) || {};
  } catch {
    return {};
  }
}

//: A value read off the first entry that has it: what the field shows.
function wbFmtValue(entry, field) {
  const kind = wbFmtKind(entry);
  const s = entry.kind === "sketch" ? wbFmtSketch(entry) : null;
  const o = entry.kind === "object" ? entry.item.data || {} : null;
  switch (field) {
    case "stroke": return s ? s.color || "#888888" : (o.border_color && o.border_color !== "transparent" ? o.border_color : "#8888aa");
    case "width": return s?.width || 3;
    case "dash": return s?.dash || "solid";
    case "pattern": return s?.dashPattern || "";
    case "round": return Number(s?.round) || 0;
    case "linestyle": return s?.curve ? "curved" : s?.round ? "rounded" : "sharp";
    case "crop": return o?.crop || "";
    case "ibcolor": return o?.border_color && o.border_color !== "transparent" ? o.border_color : "#333333";
    case "ibwidth": return o?.border_width || "";
    case "turn": return Number(o?.turn) || 0;
    case "flipx": return o?.flip_x === true;
    case "flipy": return o?.flip_y === true;
    case "grey": return o?.grey === true;
    case "bright": return Number.isInteger(o?.bright) ? o.bright : "";
    case "contrast": return Number.isInteger(o?.contrast) ? o.contrast : "";
    case "trim0": case "trim1": case "trim2": case "trim3": return o?.trim?.[Number(field[4])] || "";
    case "flow": return Boolean(s?.flow);
    case "fillstyle": return WB_FILL_STYLES.includes(s?.fillStyle) ? s.fillStyle : "solid";
    case "gradient": return wbHexColour(s?.gradient?.to) || "#ffffff";
    case "gradient-dir": return s?.gradient && wbHexColour(s.gradient.to) && (s.gradient.dir === "radial" || wbGradientVector(s.gradient.dir)) ? s.gradient.dir : "none";
    case "fill-on": return wbColour.fillIsOn(s ? "sketch" : kind === "diagram" ? "diagram" : "object", s || o);
    case "fill": return s ? s.fill || "#3355ff" : kind === "diagram" ? wbDiagramFillColour(o) : (o.bg && o.bg !== "transparent" ? o.bg : "#ffffff");
    case "alpha": return Math.round(((s ? s.alpha : o?.alpha) ?? 1) * 100);
    case "shadow": return Boolean(s ? s.shadow : o?.shadow);
    //: Empty (not 0) when the item set none, so the field shows the default as a placeholder.
    case "shx": return (s || o)?.shadow_x ?? "";
    case "shy": return (s || o)?.shadow_y ?? "";
    case "shb": return (s || o)?.shadow_blur ?? "";
    case "r0": case "r1": case "r2": case "r3": return o?.radii?.[Number(field[1])] ?? "";
    case "pad": return o?.pad ?? "";
    case "rough": return wbDrawsRough(s, false);
    case "route": return wbLinkRouteName(s);
    case "jumps": return WB_JUMP_STYLES.includes(s?.jumps) ? s.jumps : "none";
    case "edgeshape": return wbFmtState.shapeMore?.CONNECTOR_SHAPES.includes(s?.shape) ? s.shape : "line";
    case "textpath": return Boolean(s?.label_path);
    //: Empty for "automatic", so the field shows its placeholder.
    case "jumpsize": return s?.jumpSize != null && s.jumpSize !== "" ? wbJumpSize(s) : "";
    case "tip": return typeof s?.tip === "string" ? s.tip : "";
    case "gapstart": return wbLinkGap(s)?.start || 0;
    case "gapend": return wbLinkGap(s)?.end || 0;
    case "startcap": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).startCap;
    case "endcap": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).endCap;
    case "startsize": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).startSize || "m";
    case "endsize": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).endSize || "m";
    case "label-t": return Math.round(wbLinkLabelT(s) * 100);
    case "label2": return typeof s?.label2 === "string" ? s.label2 : "";
    case "label2-t": return Math.round(wbFmtState.drawMore.label2T(s) * 100);
    case "lsize": return Number(s?.label_size) || 16;
    case "lcolor": return s?.label_color || "#1f2430";
    case "lbold": return Boolean(s?.label_bold);
    case "lchip": return Boolean(s?.label_chip);
    case "size": return kind === "shape" ? s.label_size || 16 : o.font_size || 16;
    case "bold": return Boolean(kind === "shape" ? s.label_bold : o.bold);
    case "italic": return Boolean(kind === "shape" ? s.label_italic : o.italic);
    case "underline": return Boolean(kind === "shape" ? s.label_underline : o.underline);
    case "strike": return Boolean(kind === "shape" ? s.label_strike : o.strike);
    case "fit": return Boolean(s?.label_fit);
    case "font": return (kind === "shape" ? s.label_font : o.font_family) || "default";
    case "align": return (kind === "shape" ? s.label_align : o.align) || (kind === "shape" ? "center" : "left");
    //: Words in a shape sit in its middle and a text box's at its top unless
    //: told otherwise (the owner, 2026-10-10: "there's no way to vertically
    //: centre text").
    case "valign": return (kind === "shape" ? s.label_valign : o.valign) || (kind === "shape" ? "middle" : "top");
    case "ink": return (kind === "shape" ? s.label_color : o.color) || "#1f2430";
    case "lh": return (kind === "shape" ? s.label_lh : o.line_height) || "";
    case "ls": return (kind === "shape" ? s.label_ls : o.letter_spacing) || "";
    case "dir": return (kind === "shape" ? s.label_dir : o.text_dir) || "";
    case "inkalpha": return Math.round(((kind === "shape" ? s.label_alpha : o.text_alpha) ?? 1) * 100);
    case "fillalpha": return Math.round((s ? s.fillOpacity ?? 1 : o?.bg_alpha ?? (kind === "diagram" ? wbDiagramFillShare() : 1)) * 100);
    case "strokealpha": return Math.round(((s ? s.opacity : o?.line_alpha) ?? 1) * 100);
    default: return null;
  }
}

//: **One edit to every selected item that takes it, as one undo step.**
//: `patch(entry, kind)` returns a partial for a sketch's data, an object's
//: data, or `{row: {...}}` for a row's own columns; null skips the entry.
async function wbFmtApply(field, patch, said) {
  //: One apply at a time (INBOX 1685): a pasted rgba() sets the colour and then
  //: the opacity, and the second must read what the first saved, not the data
  //: from before it.
  const run = async () => {
    const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
    if (!entries.length) return;
    await wbRecordGesture(async () => {
      //: Rows and objects are saved together at the end, in one request (perf
      //: 1031 row 20); a drawn shape still saves as it is changed.
      const saves = [];
      for (const entry of entries) {
        const kind = wbFmtKind(entry);
        if (!kind || !(WB_FMT_FIELDS[kind] || []).includes(field)) continue;
        const partial = patch(entry, kind);
        if (!partial) continue;
        if (entry.kind === "sketch") {
          if (wbSketchSetProps(entry.item, partial)) saves.push({ kind: "sketch", item: entry.item });
        } else if (partial.row) {
          Object.assign(entry.item, partial.row);
          saves.push({ kind: entry.kind, item: entry.item });
        } else if (entry.kind === "object") {
          entry.item.data = { ...entry.item.data, ...partial };
          for (const [key, value] of Object.entries(partial)) if (value === undefined) delete entry.item.data[key];
          saves.push({ kind: "object", item: entry.item });
        }
      }
      await wbSaveMany(saves);
    });
    wbScheduleRender();
    if (said) wbAnnounce(said);
    wbFormatSyncSoon();
  };
  const turn = (wbFmtState.applyChain || Promise.resolve()).then(run);
  wbFmtState.applyChain = turn.catch((err) => console.error("format apply", err));
  return turn;
}

//: The selection's box, in board units: one item's, or the whole set's.
function wbFmtBox(entries) {
  entries = entries.filter((e) => e.bbox);
  if (!entries.length) return null;
  return {
    minX: Math.min(...entries.map((e) => e.bbox.minX)),
    minY: Math.min(...entries.map((e) => e.bbox.minY)),
    maxX: Math.max(...entries.map((e) => e.bbox.maxX)),
    maxY: Math.max(...entries.map((e) => e.bbox.maxY)),
  };
}

//: X and Y move the selection to the number; W and H size one item to it.
//: The W/H link, remembered per selection: `{ratio}` is width over height at
//: the moment it was switched on, so editing one side scales the other by
//: that ratio rather than by whatever the box has drifted to.
function wbFmtLinkKey(entries) {
  return entries.map((e) => `${e.kind}:${e.id}`).sort().join(",");
}

function wbFmtLinkRatio(entries) {
  const stored = wbFmtState.links.get(wbFmtLinkKey(entries))?.ratio;
  if (stored) return stored;
  //: A shape that keeps its proportions as a property carries its link with
  //: it: the ratio is the one it has now.
  const [only] = entries;
  if (entries.length === 1 && only.bbox && wbKeepsRatio(only.kind, only.item)) {
    const h = only.bbox.maxY - only.bbox.minY;
    return h > 0 ? (only.bbox.maxX - only.bbox.minX) / h : 0;
  }
  return 0;
}

function wbFmtToggleLink() {
  const entries = wbFmtEntries();
  const box = wbFmtBox(entries);
  if (!box) return;
  const key = wbFmtLinkKey(entries);
  //: One object or drawn shape: the link is its own saved property, so the
  //: corner handles keep the ratio too, without Shift.
  const [only] = entries;
  if (entries.length === 1 && (only.kind === "object" || only.kind === "sketch")) {
    wbFmtState.links.delete(key);
    wbSetKeepRatio(only.kind, only.item, !wbKeepsRatio(only.kind, only.item)).then(wbFmtShowLink);
    return;
  }
  if (wbFmtState.links.has(key)) wbFmtState.links.delete(key);
  else if (box.maxY > box.minY) wbFmtState.links.set(key, { ratio: (box.maxX - box.minX) / (box.maxY - box.minY) });
  wbFmtShowLink();
}

function wbFmtShowLink() {
  const button = document.getElementById("wb-fmt-link");
  if (!button) return;
  button.setAttribute("aria-pressed", wbFmtLinkRatio(wbFmtEntries()) ? "true" : "false");
}

//: One axis of the selection sized to a number: one item by its own size,
//: several (a group) as one box about its top left.
async function wbFmtSizeAxis(axis, target) {
  const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
  const box = wbFmtBox(entries);
  if (!entries.length || !box) return;
  const was = axis === "w" ? box.maxX - box.minX : box.maxY - box.minY;
  if (was > 0 && target > 0 && Math.abs(was - target) >= 0.5) wbFmtState.keys?.record({ kind: "scale", axis, factor: target / was });
  if (entries.length !== 1) {
    await wbFmtScaleSelection(entries, box, axis, target);
    return;
  }
  const [e] = entries;
  if (!e.bbox) return;
  const dim = axis === "w" ? "width" : "height";
  const size = axis === "w" ? e.bbox.maxX - e.bbox.minX : e.bbox.maxY - e.bbox.minY;
  const rows = [];
  if (size > 0 && Math.abs(size - target) >= 0.5) wbSizeItemTo(e, dim, target, target / size, rows);
  await wbSaveMany(rows);
}

//: X and Y move the selection to the number; W and H size one item to it.
async function wbFmtGeometry(axis, value) {
  const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
  if (!entries.length || !Number.isFinite(value)) return;
  const box = wbFmtBox(entries);
  if (!box) return;
  await wbRecordGesture(async () => {
    if (axis === "x" || axis === "y") {
      const dx = axis === "x" ? value - box.minX : 0;
      const dy = axis === "y" ? value - box.minY : 0;
      if (!dx && !dy) return;
      const rows = [];
      for (const e of entries) if (wbFmtKind(e) !== "link") wbMoveItemBy(e.kind, e.id, e.item, dx, dy, rows);
      await wbSaveMany(rows);
      return;
    }
    const target = Math.max(8, value);
    //: Several items (a group): the set is sized as one box about its top
    //: left, each member scaling with it (B29: "I cant widen objects on one
    //: axis when grouped").
    await wbFmtSizeAxis(axis, target);
    const ratio = wbFmtLinkRatio(wbFmtEntries());
    if (ratio) await wbFmtSizeAxis(axis === "w" ? "h" : "w", Math.max(8, axis === "w" ? target / ratio : target * ratio));
  });
  wbScheduleRender();
  wbAnnounce(`${{ x: "X", y: "Y", w: "Width", h: "Height" }[axis]} ${Math.round(value)}.`);
  wbFormatSyncSoon();
}

//: **A size preset** (draw.io's Arrange tab, INBOX 1510(a)): the height
//: set from the width to a common ratio, one undo step, and a kept ratio
//: moves to the new one so a later W or H change keeps it. The menu goes
//: back to its prompt: a preset is an action, not a state.
async function wbFmtAspect(ratio) {
  const select = document.getElementById("wb-fmt-aspect");
  const name = select?.selectedOptions?.[0]?.textContent || "chosen";
  if (select) select.value = "";
  const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
  const box = wbFmtBox(entries);
  if (!(ratio > 0) || !box) return;
  const key = wbFmtLinkKey(entries);
  const kept = wbFmtState.links.has(key);
  wbFmtState.links.delete(key);
  await wbRecordGesture(() => wbFmtSizeAxis("h", Math.max(8, Math.round((box.maxX - box.minX) / ratio))));
  if (kept) wbFmtState.links.set(key, { ratio });
  wbScheduleRender();
  wbAnnounce(`Height set for ${name}.`);
  wbFormatSyncSoon();
}

//: One axis of a selection's box set to a number: every member's position
//: on that axis and its size scale by the same factor about the box's top
//: left, the arithmetic the group's own edge grips use. A connector follows
//: its ends, so it is skipped.
async function wbFmtScaleSelection(entries, box, axis, target) {
  const horizontal = axis === "w";
  const size = horizontal ? box.maxX - box.minX : box.maxY - box.minY;
  if (!(size > 0) || Math.abs(size - target) < 0.5) return;
  const f = target / size;
  const ax = box.minX, ay = box.minY;
  const saves = [];
  for (const e of entries) {
    if (wbFmtKind(e) === "link" || !e.bbox) continue;
    if (e.kind === "sketch") {
      const parsed = wbSketchParsedData(e.item);
      if (!parsed) continue;
      wbSketchSetD(e.item, wbTransformPathD(parsed.d, {
        sx: horizontal ? f : 1, sy: horizontal ? 1 : f, anchorX: ax, anchorY: ay,
      }));
      saves.push({ kind: "sketch", item: e.item });
      continue;
    }
    const item = e.item;
    if (horizontal) {
      item.x = Math.round(ax + ((item.x || 0) - ax) * f);
      item.width = Math.round(Math.max(WB_OBJECT_MIN_SIZE, (e.bbox.maxX - e.bbox.minX) * f));
    } else {
      item.y = Math.round(ay + ((item.y || 0) - ay) * f);
      item.height = Math.round(Math.max(WB_OBJECT_MIN_SIZE, (e.bbox.maxY - e.bbox.minY) * f));
    }
    saves.push({ kind: e.kind, item });
  }
  await wbSaveMany(saves);
}

//: A card, text box or picture turns about its centre (`rotation`). A drawn
//: shape has its turn baked into its path and keeps its rotate grip.
async function wbFmtAngle(value) {
  const angle = ((Math.round(value) % 360) + 360) % 360;
  await wbFmtApply("angle", () => ({ row: { rotation: angle || null } }), `Angle ${angle} degrees.`);
}

//: A flip mirrors a drawn path about its own centre.
async function wbFmtFlip(axis) {
  const entries = wbFmtEntries().filter((e) => e.kind === "sketch" && !wbIsLocked(e.kind, e.item));
  if (!entries.length) return;
  await wbRecordGesture(async () => {
    const rows = [];
    for (const e of entries) {
      const parsed = wbSketchParsedData(e.item);
      if (!parsed) continue;
      wbSketchSetD(e.item, wbTransformPathD(parsed.d, {
        sx: axis === "h" ? -1 : 1,
        sy: axis === "v" ? -1 : 1,
        anchorX: (e.bbox.minX + e.bbox.maxX) / 2,
        anchorY: (e.bbox.minY + e.bbox.maxY) / 2,
      }));
      rows.push({ kind: "sketch", item: e.item });
    }
    await wbSaveMany(rows);
  });
  wbScheduleRender();
  wbAnnounce(axis === "h" ? "Flipped left to right." : "Flipped top to bottom.");
}

//: A connector's line shape: curved, straight, elbow, entity relation or isometric (a straight link
//: with `route: "elbow"`, `"er"` or `"iso"`, see `wbLinkRouteName`). Its bends go with it, as
//: draw.io keeps an edge's waypoints across styles: every style takes them
//: (wb-phase2 step 1), and an old link's single `bend` becomes one.
async function wbSetLinkRoute(value) {
  await wbFmtApply("route", (entry) => {
    const parsed = wbFmtSketch(entry);
    if (wbLinkRouteName(parsed) === value) return null;
    const points = wbLinkWaypoints(parsed, wbResolveLinkEndpoints(parsed));
    return {
      type: value === "curved" ? "link-curved" : "link-straight",
      route: ["elbow", "er", "iso"].includes(value) ? value : undefined,
      points: points.length ? points.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) })) : undefined,
      bend: undefined,
    };
  }, `Line shape: ${value}.`);
}

//: (A method of `wbFmtState`, not a global of its own: the shared scope is counted.)
//: A saved picture's caption as one muted line under it, on a board's picture or a map topic's (K18). Off until Show captions is pressed; the
//: caption is read once per picture (`GET /media/meta`) and a picture still on the board only has none.
wbFmtState.paintCaptions = function () {
  const show = prefs.get("wb-show-captions", null) === "1";
  if (!show && !wbFmtState.captionsDrawn) return;
  wbFmtState.captionsDrawn = show;
  const cache = wbFmtState.captions || (wbFmtState.captions = new Map());
  for (const o of wbState.objects || []) {
    //: A board picture, or a map topic that carries one.
    const url = (o.kind === "image" ? o.data?.url : WB_MAP_KINDS.has(o.kind) ? o.data?.image : "") || "";
    if (!url) continue;
    const el = document.querySelector(`#wb-html-layer .wb-object[data-id="${o.id}"]`);
    if (!el) continue;
    let line = el.querySelector(":scope > .wb-object-caption");
    if (show && url && !cache.has(url)) {
      cache.set(url, "");
      apiJson(`/media/meta/${encodeURIComponent(url.split("/").pop())}`, { headers: authHeaders() })
        .then((meta) => {
          cache.set(url, meta.caption || "");
          wbFmtState.paintCaptions();
        })
        .catch(() => {});
    }
    const text = show ? cache.get(url) || "" : "";
    if (!text) {
      line?.remove();
      continue;
    }
    if (!line) {
      line = document.createElement("div");
      line.className = "wb-object-caption";
      el.append(line);
    }
    if (line.textContent !== text) line.textContent = text;
    line.style.color = wbDefaultInk("#000000");
  }
};

function wbFormatPanel() {
  return document.getElementById("wb-format");
}

function wbFormatIsOpen() {
  const panel = wbFormatPanel();
  return Boolean(panel && !panel.classList.contains("hidden"));
}

function wbFormatOpen(tab = null, { focus = true } = {}) {
  const panel = wbFormatPanel();
  if (!panel) return;
  if (tab && WB_FMT_TABS.includes(tab)) wbFmtState.fmtTab = tab;
  panel.classList.remove("hidden");
  try {
    prefs.set(WB_FMT_KEY, "1");
  } catch {
    /* a private window: the panel still opens, it is just not remembered */
  }
  wbFmtMarkButton(true);
  wbFormatSync();
  if (focus) panel.querySelector(`[data-format-tab="${wbFmtState.fmtTab}"]`)?.focus();
}

function wbFormatClose({ restoreFocus = true } = {}) {
  const panel = wbFormatPanel();
  if (!panel || panel.classList.contains("hidden")) return;
  const hadFocus = panel.contains(document.activeElement);
  panel.classList.add("hidden");
  wbFmtMarkButton(false);
  try {
    prefs.remove(WB_FMT_KEY);
  } catch {
    /* nothing to forget */
  }
  if (restoreFocus && hadFocus) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
}

//: The top bar's Format button mirrors the panel, as Library's does.
function wbFmtMarkButton(on) {
  const btn = document.getElementById("wb-format-btn");
  if (!btn) return;
  btn.classList.toggle("is-on", on);
  btn.setAttribute("aria-pressed", String(on));
}

function wbFormatToggle(tab = null) {
  if (wbFormatIsOpen() && (!tab || tab === wbFmtState.fmtTab)) wbFormatClose();
  else wbFormatOpen(tab);
}

//: Coalesced: a selection change fires the context bar several times in a
//: frame, and the panel is read once.
function wbFormatSyncSoon() {
  if (wbFmtState.fmtSyncQueued || !wbFormatIsOpen()) return;
  wbFmtState.fmtSyncQueued = true;
  wbFmtFrameSoon();
}

//: The panel's one frame callback: the full read and the four live numbers
//: below share it (a second `requestAnimationFrame` was a second wake source).
function wbFmtFrameSoon() {
  if (wbFmtState.fmtFrameQueued) return;
  wbFmtState.fmtFrameQueued = true;
  requestAnimationFrame(() => {
    wbFmtState.fmtFrameQueued = false;
    //: Both flags drop first so a throw in a read cannot leave one stuck.
    const full = wbFmtState.fmtSyncQueued;
    const live = wbFmtState.fmtLiveQueued;
    wbFmtState.fmtSyncQueued = false;
    wbFmtState.fmtLiveQueued = false;
    //: The full read also writes x, y, w and h, so it covers the live one.
    if (full) wbFormatSync();
    else if (live) wbFormatLiveRead();
  });
}

//: The panel, read off the selection: which tab, which rows, what values.
//: One field showing a value, or that the selection holds several: a
//: colour striped and titled, a list reading Mixed (a hidden option, so it
//: is never offered), a number empty with Mixed as its hint. Picking or
//: typing a value sets it on every selected item.
function wbFmtShowMixed(el, isMixed, value) {
  if (el.type === "color") {
    el.value = value;
    el.classList.toggle("wb-mixed", isMixed);
    el.dataset.title ??= el.title;
    el.title = isMixed ? `${el.dataset.title}: mixed` : el.dataset.title;
  } else if (el.tagName === "SELECT") {
    let option = el.querySelector("option[data-mixed]");
    if (isMixed && !option) {
      option = document.createElement("option");
      option.value = "";
      option.hidden = true;
      option.dataset.mixed = "true";
      option.textContent = "Mixed";
      el.append(option);
    }
    el.value = isMixed ? "" : value;
  } else if (el.type === "number" || el.type === "text") {
    //: The field's own hint (Jump size's "Auto", the tooltip's words) comes
    //: back when the selection stops being mixed.
    el.dataset.hint ??= el.placeholder;
    el.value = isMixed ? "" : value;
    el.placeholder = isMixed ? "Mixed" : el.dataset.hint;
  } else {
    el.value = value;
  }
}

//: A group's head shows while one of its rows does (INBOX 1510(a)): a
//: line's Style tab has no Fill head over nothing.
function wbFmtShowGroups(panel) {
  for (const group of panel.querySelectorAll(".wb-fmt-group")) {
    group.hidden = !group.querySelector("[data-fmt]:not([hidden]), .wb-fmt-commands:not([hidden])");
  }
}

function wbFormatSync() {
  const panel = wbFormatPanel();
  if (!panel || panel.classList.contains("hidden")) return;
  //: The crop box belongs to the one picture it was opened on: another selection, or a repaint that
  //: dropped its element, ends it.
  const cropping = wbFmtState.cropEdit;
  if (cropping && (wbFmtEntries().length !== 1 || wbFmtEntries()[0].id !== cropping.id || !document.querySelector(".wb-crop-frame"))) cropping.close();
  for (const tab of panel.querySelectorAll("[data-format-tab]")) {
    const on = tab.dataset.formatTab === wbFmtState.fmtTab;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
  }
  const body = document.getElementById("wb-format-body");
  body?.setAttribute("aria-labelledby", `wb-format-tab-${wbFmtState.fmtTab}`);
  for (const section of panel.querySelectorAll("[data-format-panel]")) section.hidden = section.dataset.formatPanel !== wbFmtState.fmtTab;
  const entries = wbFmtEntries();
  const kinds = new Set(entries.map(wbFmtKind).filter(Boolean));
  //: **What the selection shares** (the owner, 2026-10-11: "if I highlight
  //: and select multiple objects, cna I cnahge the properties they share"):
  //: a row shows when every selected kind takes it, so a shape and a line
  //: show line colour, width and pattern but no fill. Position and size are
  //: the selection's box, so they show while anything has one.
  const fieldSets = [...kinds].map((k) => new Set(WB_FMT_FIELDS[k] || []));
  const fields = new Set(fieldSets.length ? [...fieldSets[0]].filter((f) => fieldSets.every((s) => s.has(f))) : []);
  if (fieldSets.some((s) => s.has("geometry"))) fields.add("geometry");
  //: The folded corner is a sticky note's, not a plain text box's.
  if (!entries.some((e) => e.kind === "object" && wbIsSticky(e.item))) fields.delete("fold");
  //: The Corners row is for a path of straight sides; an ellipse has none.
  if (fields.has("round") && !entries.some(wbFmtCanRound)) {
    fields.delete("round");
    fields.delete("linestyle");
  }
  const boardStyle = document.getElementById("wb-board-style");
  if (boardStyle) wbFmtState.board.show(boardStyle, !entries.length && wbFmtState.fmtTab === "style");
  const boardOptions = document.getElementById("wb-board-options");
  if (boardOptions) boardOptions.hidden = entries.length > 0 || wbFmtState.fmtTab !== "style" || wbIsMap();
  const empty = document.getElementById("wb-format-empty");
  const map = kinds.has("topic");
  if (empty) {
    empty.hidden = Boolean(entries.length) && !map;
    empty.textContent = map
      ? "A topic is styled from its ring: right-click it, or press Shift+F10."
      : "Select something on the board to format it.";
  }
  const section = panel.querySelector(`[data-format-panel="${wbFmtState.fmtTab}"]`);
  let shown = 0;
  for (const row of panel.querySelectorAll("[data-fmt]")) {
    const on = fields.has(row.dataset.fmt) && !map;
    row.hidden = !on;
    if (on && section?.contains(row)) shown += 1;
  }
  const none = document.getElementById("wb-format-none");
  if (none) none.hidden = !entries.length || map || shown > 0;
  const arrange = document.getElementById("wb-format-commands");
  if (arrange) arrange.hidden = !entries.length || map;
  wbSyncCommandRows(arrange);
  wbFmtShowGroups(panel);
  if (fields.has("props")) wbFmtSyncProps(entries);
  if (fields.has("rawstyle")) wbFmtState.raw.sync(entries);
  const first = entries.find((e) => wbFmtKind(e) && wbFmtKind(e) !== "topic");
  if (!first) return;
  const set = (id, value, prop = "value") => {
    const el = document.getElementById(id);
    if (el && document.activeElement !== el) el[prop] = value;
  };
  const takes = fields;
  //: A value the selection does not agree on says Mixed rather than
  //: showing the first item's as if it were everyone's.
  const sharing = entries.filter((e) => wbFmtKind(e) && wbFmtKind(e) !== "topic");
  const mixed = (field) => new Set(sharing.map((e) => JSON.stringify(wbFmtValue(e, field)))).size > 1;
  //: A shape's or a text box's line is its border, and says so.
  const bordered = [...kinds].every((k) => k === "shape" || k === "text");
  const strokeWord = document.getElementById("wb-fmt-stroke-word");
  if (strokeWord) strokeWord.textContent = bordered ? "Border" : "Line";
  const strokeField = document.getElementById("wb-fmt-stroke");
  if (strokeField) {
    strokeField.setAttribute("aria-label", bordered ? "Border colour" : "Line colour");
    strokeField.dataset.title = bordered ? "Border colour" : "Line colour";
  }
  for (const [id, field, row] of [
    ["wb-fmt-stroke", "stroke", "stroke"], ["wb-fmt-width", "width", "width"], ["wb-fmt-dash", "dash", "dash"],
    ["wb-fmt-fill", "fill", "fill"], ["wb-fmt-route", "route", "route"], ["wb-fmt-edgeshape", "edgeshape", "edgeshape"], ["wb-fmt-jumps", "jumps", "jumps"], ["wb-fmt-startcap", "startcap", "caps"],
    ["wb-fmt-fillstyle", "fillstyle", "fillstyle"], ["wb-fmt-gradient-dir", "gradient-dir", "gradient"], ["wb-fmt-gradient", "gradient", "gradient"],
    ["wb-fmt-jumpsize", "jumpsize", "jumpsize"], ["wb-fmt-gapstart", "gapstart", "gapstart"], ["wb-fmt-gapend", "gapend", "gapend"], ["wb-fmt-tip", "tip", "tip"], ["wb-fmt-label2", "label2", "label2"], ["wb-fmt-label2-t", "label2-t", "label2-t"],
    ["wb-fmt-pattern", "pattern", "pattern"], ["wb-fmt-round", "round", "round"], ["wb-fmt-linestyle", "linestyle", "linestyle"], ["wb-fmt-crop", "crop", "crop"], ["wb-fmt-endcap", "endcap", "caps"], ["wb-fmt-startsize", "startsize", "caps"], ["wb-fmt-endsize", "endsize", "caps"], ["wb-fmt-label-t", "label-t", "label-t"], ["wb-fmt-lsize", "lsize", "linklook"], ["wb-fmt-lcolor", "lcolor", "linklook"], ["wb-fmt-size", "size", "text"],
    ["wb-fmt-shx", "shx", "shadowset"], ["wb-fmt-shy", "shy", "shadowset"], ["wb-fmt-shb", "shb", "shadowset"], ["wb-fmt-pad", "pad", "pad"],
    ["wb-fmt-bright", "bright", "pixels"], ["wb-fmt-contrast", "contrast", "pixels"], ["wb-fmt-trim0", "trim0", "trim"], ["wb-fmt-trim1", "trim1", "trim"], ["wb-fmt-trim2", "trim2", "trim"], ["wb-fmt-trim3", "trim3", "trim"],
    ["wb-fmt-ibcolor", "ibcolor", "imageborder"], ["wb-fmt-ibwidth", "ibwidth", "imageborder"],
    ["wb-fmt-r0", "r0", "radii"], ["wb-fmt-r1", "r1", "radii"], ["wb-fmt-r2", "r2", "radii"], ["wb-fmt-r3", "r3", "radii"],
    ["wb-fmt-ink", "ink", "text"], ["wb-fmt-alpha", "alpha", "alpha"], ["wb-fmt-lh", "lh", "text"], ["wb-fmt-ls", "ls", "text"], ["wb-fmt-dir", "dir", "text"], ["wb-fmt-inkalpha", "inkalpha", "text"],
  ]) {
    if (!takes.has(row)) continue;
    const el = document.getElementById(id);
    if (!el || document.activeElement === el) continue;
    wbFmtShowMixed(el, mixed(field), wbFmtValue(first, field));
  }
  if (takes.has("fill")) {
    const fillField = document.getElementById("wb-fmt-fill");
    const fillOn = document.getElementById("wb-fmt-fill-on");
    if (fillOn && document.activeElement !== fillOn) {
      fillOn.checked = wbFmtValue(first, "fill-on");
      fillOn.indeterminate = mixed("fill-on");
    }
    if (fillField) fillField.classList.toggle("wb-colour-off", !mixed("fill-on") && !wbFmtValue(first, "fill-on"));
  }
  // The second colour is dimmed while there is no gradient for it to belong to.
  document.getElementById("wb-fmt-gradient")?.classList.toggle("wb-colour-off", !mixed("gradient-dir") && wbFmtValue(first, "gradient-dir") === "none");
  for (const [id, field] of [["wb-fmt-shadow", "shadow"], ["wb-fmt-rough", "rough"], ["wb-fmt-flow", "flow"], ["wb-fmt-textpath", "textpath"]]) {
    const box = document.getElementById(id);
    if (!takes.has(field) || !box || document.activeElement === box) continue;
    box.checked = wbFmtValue(first, field);
    box.indeterminate = mixed(field);
  }
  const sticky = entries.find((e) => e.kind === "object" && wbIsSticky(e.item));
  if (sticky) set("wb-fmt-fold", wbStickyFolds(sticky.item), "checked");
  const lane = entries.find((e) => e.kind === "object" && e.item.kind === "frame");
  if (lane) set("wb-fmt-stack", Boolean(lane.item.data?.stack), "checked");
  const table = entries.find((e) => e.kind === "object" && e.item.kind === "table");
  if (table) {
    set("wb-fmt-tableheader", Boolean(table.item.data?.header), "checked");
    set("wb-fmt-stripes", Boolean(table.item.data?.stripes), "checked");
  }
  if (takes.has("pixels")) {
    for (const [id, field] of [["wb-fmt-flipx", "flipx"], ["wb-fmt-flipy", "flipy"], ["wb-fmt-grey", "grey"]]) {
      document.getElementById(id)?.setAttribute("aria-pressed", mixed(field) ? "mixed" : String(wbFmtValue(first, field)));
    }
  }
  const alphaOut = document.getElementById("wb-fmt-alpha-out");
  if (alphaOut && takes.has("alpha")) alphaOut.textContent = mixed("alpha") ? "Mixed" : `${wbFmtValue(first, "alpha")}%`;
  if (takes.has("fillalpha")) wbFmtShowAlpha("fillalpha", mixed("fillalpha"), wbFmtValue(first, "fillalpha"));
  if (takes.has("strokealpha")) wbFmtShowAlpha("strokealpha", mixed("strokealpha"), wbFmtValue(first, "strokealpha"));
  if (takes.has("linklook")) {
    for (const [id, field] of [["wb-fmt-lbold", "lbold"], ["wb-fmt-lchip", "lchip"]]) {
      document.getElementById(id)?.setAttribute("aria-pressed", mixed(field) ? "mixed" : String(wbFmtValue(first, field)));
    }
  }
  wbFmtState.label?.sync(takes, sharing);
  wbFmtState.drawMore?.syncLoopRow(takes, sharing);
  wbFmtState.drawMore?.syncPortsRow(takes, sharing);
  if (takes.has("text")) {
    const pressed = (field, value) => {
      const some = sharing.map((e) => wbFmtValue(e, field) === value);
      return some.every(Boolean) ? "true" : some.some(Boolean) ? "mixed" : "false";
    };
    for (const button of panel.querySelectorAll("#wb-fmt-align [data-align]")) button.setAttribute("aria-pressed", pressed("align", button.dataset.align));
    for (const button of panel.querySelectorAll("#wb-fmt-valign [data-valign]")) button.setAttribute("aria-pressed", pressed("valign", button.dataset.valign));
    document.getElementById("wb-fmt-bold")?.setAttribute("aria-pressed", pressed("bold", true));
    document.getElementById("wb-fmt-italic")?.setAttribute("aria-pressed", pressed("italic", true));
    document.getElementById("wb-fmt-underline")?.setAttribute("aria-pressed", pressed("underline", true));
    document.getElementById("wb-fmt-strike")?.setAttribute("aria-pressed", pressed("strike", true));
    if (takes.has("fit")) document.getElementById("wb-fmt-fit")?.setAttribute("aria-pressed", pressed("fit", true));
    const fontField = document.getElementById("wb-fmt-font");
    if (fontField && document.activeElement !== fontField) wbFmtShowMixed(fontField, mixed("font"), wbFmtValue(first, "font"));
  }
  const box = wbFmtBox(entries);
  if (!box) return;
  set("wb-fmt-x", wbFmtState.opts?.show(box.minX) ?? Math.round(box.minX));
  set("wb-fmt-y", wbFmtState.opts?.show(box.minY) ?? Math.round(box.minY));
  set("wb-fmt-w", wbFmtState.opts?.show(box.maxX - box.minX) ?? Math.round(box.maxX - box.minX));
  set("wb-fmt-h", wbFmtState.opts?.show(box.maxY - box.minY) ?? Math.round(box.maxY - box.minY));
  set("wb-fmt-angle", Math.round(first.item.rotation || 0));
  wbFmtShowLink();
}

//: **The numbers follow the hand** (B29: "resizing or moving objects doesn't
//: update their xywh values in the format panel in real time"). The panel was
//: read on selection and after a save, so x/y/w/h held the start of a drag
//: until it was released. A held pointer over the board now re-reads just
//: those four fields, once a frame, and only while the Arrange tab shows them.
function wbFormatLiveSoon(event) {
  if (wbFmtState.fmtLiveQueued || !(event.buttons & 1) || !wbFormatIsOpen() || wbFmtState.fmtTab !== "arrange") return;
  wbFmtState.fmtLiveQueued = true;
  wbFmtFrameSoon();
}

function wbFormatLiveRead() {
  const box = wbFmtBox(wbFmtEntries());
  if (!box) return;
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el && document.activeElement !== el) el.value = value;
  };
  set("wb-fmt-x", wbFmtState.opts?.show(box.minX) ?? Math.round(box.minX));
  set("wb-fmt-y", wbFmtState.opts?.show(box.minY) ?? Math.round(box.minY));
  set("wb-fmt-w", wbFmtState.opts?.show(box.maxX - box.minX) ?? Math.round(box.maxX - box.minX));
  set("wb-fmt-h", wbFmtState.opts?.show(box.maxY - box.minY) ?? Math.round(box.maxY - box.minY));
}

//: --- Edit data (draw.io's custom properties; canvasdepth2) ----------------
//:
//: `data.props {name: value}` on one selected item, as rows of two fields
//: and a remove button. A change is read off every row at once and written
//: as one Undo step; a row with no name is not kept.
const WB_PROP_NAME = /^[A-Za-z][\w .-]{0,39}$/;

function wbFmtPropRow(name = "", value = "") {
  const li = document.createElement("li");
  li.className = "wb-fmt-prop";
  const key = document.createElement("input");
  key.className = "wb-fmt-prop-name";
  key.value = name;
  key.maxLength = 40;
  key.placeholder = "Name";
  key.setAttribute("aria-label", "Property name");
  const val = document.createElement("input");
  val.className = "wb-fmt-prop-value";
  val.value = value;
  val.maxLength = 200;
  val.placeholder = "Value";
  val.setAttribute("aria-label", name ? `Value of ${name}` : "Property value");
  const remove = smallButton("ph:x", name ? `Remove ${name}` : "Remove this property", () => {
    li.remove();
    wbFmtSaveProps();
  });
  remove.classList.add("wb-fmt-prop-remove");
  li.append(key, val, remove);
  return li;
}

function wbFmtSyncProps(entries) {
  const list = document.getElementById("wb-fmt-props");
  if (!list || list.contains(document.activeElement)) return;
  const add = document.getElementById("wb-fmt-prop-add");
  const one = entries.length === 1 && WB_FMT_FIELDS[wbFmtKind(entries[0])]?.includes("props") ? entries[0] : null;
  if (add) add.hidden = !one;
  list.dataset.item = one ? `${one.kind}:${one.id}` : "";
  //: The item's own properties: a sketch's data, an object's data, or none.
  const props = one ? ((one.kind === "sketch" ? wbFmtSketch(one) : one.item.data || {}).props) : null;
  list.replaceChildren(...(one ? Object.entries(props && typeof props === "object" ? props : {}).map(([k, v]) => wbFmtPropRow(k, String(v))) : []));
  if (!one && entries.length > 1) {
    const li = document.createElement("li");
    li.className = "muted wb-lib-note";
    li.textContent = "Select one item to see and change its data.";
    list.append(li);
  }
}

//: One save at a time, each reading the rows when it runs: a name and then
//: its value typed straight on are two changes, and two PUTs in flight can
//: land in either order.
function wbFmtSaveProps() {
  wbFmtState.propsChain = (wbFmtState.propsChain || Promise.resolve()).then(wbFmtWriteProps, wbFmtWriteProps);
  return wbFmtState.propsChain;
}

function wbFmtWriteProps() {
  const list = document.getElementById("wb-fmt-props");
  if (!list) return;
  const props = {};
  let refused = "";
  for (const row of list.querySelectorAll(".wb-fmt-prop")) {
    const name = row.querySelector(".wb-fmt-prop-name").value.trim();
    if (!name) continue;
    if (!WB_PROP_NAME.test(name)) {
      refused = name;
      continue;
    }
    props[name] = row.querySelector(".wb-fmt-prop-value").value.slice(0, 200);
  }
  if (refused) toast(`"${refused}" cannot be a name: start with a letter, then letters, digits, spaces, dots, dashes or underscores.`, "info");
  const keys = Object.keys(props).slice(0, 30);
  const value = keys.length ? Object.fromEntries(keys.map((k) => [k, props[k]])) : undefined;
  return wbFmtApply("props", () => ({ props: value }), "Data saved.");
}

//: The arrange buttons, from the command table: icon-only, named by the
//: table's label and key, greyed (`aria-disabled`) by `wbSyncCommandRows`
//: when they do not apply.
function wbFormatCommandButtons() {
  const host = document.getElementById("wb-format-commands");
  if (!host || host.childElementCount) return;
  const groups = [
    ["Order", ["order-front", "order-forward", "order-backward", "order-back"]],
    //: Three a row, so every run fits the field column beside its name
    //: (INBOX 1510(a), one grid): six in one run wrapped under the label.
    ["Align across", ["align-left", "align-hcenter", "align-right"]],
    ["Align down", ["align-top", "align-vcenter", "align-bottom"]],
    ["Space and size", ["distribute-h", "distribute-v", "same-width", "same-height"]],
    ["Group and lock", ["group", "ungroup", "lock"]],
  ];
  for (const [name, ids] of groups) {
    const row = document.createElement("div");
    row.className = "wb-fmt-row";
    const label = document.createElement("span");
    label.className = "wb-fmt-label";
    label.textContent = name;
    const buttons = document.createElement("span");
    buttons.className = "wb-fmt-buttons";
    buttons.setAttribute("role", "group");
    buttons.setAttribute("aria-label", name);
    for (const id of ids) {
      const command = WB_COMMAND_BY_ID.get(id);
      if (!command) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ghost small icon-only";
      button.dataset.wbCmd = id;
      const words = command.keys ? `${command.label} (${command.keys})` : command.label;
      button.title = words;
      button.setAttribute("aria-label", command.label);
      if (command.keys) button.setAttribute("aria-keyshortcuts", command.keys.replace(/Ctrl/g, "Control"));
      const icon = document.createElement("i");
      icon.className = `ph ph-${command.icon.replace(/^ph:/, "")}`;
      icon.setAttribute("aria-hidden", "true");
      button.append(icon);
      buttons.append(button);
    }
    row.append(label, buttons);
    host.append(row);
  }
}

//: The fields a change of either end (its mark or its size) writes.
function wbFmtCapFields(kind, parsed, caps) {
  if (kind === "arrow") {
    const d = wbRegenerateShapeCaps(parsed.d, caps.startCap, caps.endCap, (parsed.width || 3) * 4 + 6, caps);
    return { d, startCap: caps.startCap, endCap: caps.endCap, ...wbCapSizeFields(caps) };
  }
  return { startCap: caps.startCap, endCap: caps.endCap, endStyle: undefined, ...wbCapSizeFields(caps) };
}

onSurface("board", () => {
  const panel = wbFormatPanel();
  if (!panel) return;
  wbFormatCommandButtons();
  //: Capture phase: a drag's own handlers stop the event, and the read waits
  //: for the next frame, after they have moved the item.
  document.addEventListener("pointermove", wbFormatLiveSoon, true);
  //: The panel's two end lists are the bar's, groups and drawn examples
  //: included (the row label says which end).
  for (const which of ["start", "end"]) {
    const from = document.getElementById(`wb-prop-${which}cap`);
    const to = document.getElementById(`wb-fmt-${which}cap`);
    if (!from || !to || to.options.length) continue;
    for (const node of from.children) to.append(node.cloneNode(true));
  }
  const on = (id, type, fn) => document.getElementById(id)?.addEventListener(type, fn);
  on("wb-format-close", "click", () => wbFormatClose());
  on("wb-format-btn", "click", () => wbFormatToggle());
  panel.addEventListener("click", (e) => {
    const tab = e.target.closest("[data-format-tab]");
    if (tab) {
      wbFmtState.fmtTab = tab.dataset.formatTab;
      wbFormatSync();
      return;
    }
    const cmd = e.target.closest("[data-wb-cmd]");
    //: A greyed button still runs, so the table's toast says why it did not.
    if (cmd && panel.contains(cmd)) Promise.resolve(wbRunCommand(cmd.dataset.wbCmd)).then(() => wbFormatSyncSoon());
  });
  //: The tabs are one Tab stop; Left and Right (and Home, End) walk them.
  panel.querySelector(".wb-format-tabs")?.addEventListener("keydown", (e) => {
    const i = WB_FMT_TABS.indexOf(wbFmtState.fmtTab);
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: WB_FMT_TABS.length - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    wbFmtState.fmtTab = WB_FMT_TABS[(next + WB_FMT_TABS.length) % WB_FMT_TABS.length];
    wbFormatSync();
    panel.querySelector(`[data-format-tab="${wbFmtState.fmtTab}"]`)?.focus();
  });
  panel.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !e.defaultPrevented) {
      e.preventDefault();
      wbFormatClose();
    } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.key.toLowerCase() === "p") {
      e.preventDefault();
      e.stopPropagation();
      wbFormatClose();
    }
  });

  on("wb-fmt-stroke", "change", (e) => wbFmtApply("stroke", (entry) => (entry.kind === "sketch" ? { color: e.target.value } : { border_color: e.target.value }), "Line colour changed."));
  on("wb-fmt-width", "change", (e) => {
    const width = Math.max(1, Math.min(40, Number(e.target.value) || 3));
    wbFmtApply("width", () => ({ width }), `Line width ${width}.`);
  });
  on("wb-fmt-pattern", "change", (e) => {
    const typed = e.target.value.trim();
    const numbers = typed ? wbDashPatternOf(typed) : null;
    if (typed && !numbers) {
      toast("Dashes are numbers like 8 4, up to six, each at most 200.");
      //: The sync leaves a focused field alone, so put the saved pattern back here.
      const first = wbFmtEntries().find((entry) => wbFmtKind(entry));
      e.target.value = first ? wbFmtValue(first, "pattern") : "";
      return;
    }
    wbFmtApply("pattern", () => ({ dashPattern: numbers ? numbers.join(" ") : undefined }), numbers ? "Custom dashes set." : "Custom dashes cleared.");
  });
  on("wb-fmt-crop", "change", (e) => {
    const crop = e.target.value;
    wbFmtApply("crop", () => ({ crop: crop || undefined }), crop ? `Picture cropped to ${e.target.selectedOptions[0].textContent.toLowerCase()}.` : "Picture crop taken off.");
  });
  //: Save to Library and Show captions (owner-1026b K18). A picture on a board stays on the board: it is
  //: not in the Library, not searched, not read. Save to Library files it (and starts its readers); Show
  //: captions draws a saved picture's caption as one muted line under it, off until asked for.
  on("wb-fmt-tolibrary", "click", async () => {
    const urls = wbFmtEntries().filter((e) => e.kind === "object" && e.item.kind === "image").map((e) => e.item.data?.url).filter(Boolean);
    let saved = 0;
    try {
      for (const url of urls) {
        const meta = await apiJson(`/media/meta/${encodeURIComponent(url.split("/").pop())}`, { headers: authHeaders() });
        if (!meta.board_only) continue;
        await apiJson(`/media/${meta.id}/library`, { method: "POST", headers: authHeaders() });
        wbFmtState.captions?.delete(url);
        saved += 1;
      }
    } catch (err) {
      return toast(err?.message || "The picture could not be saved to the Library.", true, { action: ["Try again", () => document.getElementById("wb-fmt-tolibrary")?.click()] });
    }
    toast(saved ? "Saved to the Library. Its caption is written in the background." : "That picture is already in the Library.");
  });
  on("wb-fmt-showcaption", "click", (e) => {
    const next = prefs.get("wb-show-captions", null) !== "1";
    prefs.set("wb-show-captions", next ? "1" : "0");
    e.currentTarget.setAttribute("aria-pressed", String(next));
    wbFmtState.captions = new Map();
    wbFmtState.paintCaptions();
    //: The same pref draws under a note's pictures in a card and a graph popup.
    if (typeof imageLayout === "function") imageLayout.paintCaptions();
  });
  document.getElementById("wb-fmt-showcaption")?.setAttribute("aria-pressed", String(prefs.get("wb-show-captions", null) === "1"));
  //: Replace picture: the button opens the file box; the new file is uploaded and the picture's address
  //: swapped in one Undo step, so its place, size, crop and style stay.
  on("wb-fmt-replace", "click", () => document.getElementById("wb-fmt-replace-file")?.click());
  on("wb-fmt-replace-file", "change", async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !file.type?.startsWith("image/")) return;
    if (file.size > 50 * 1024 * 1024) return toast("That picture is over 50 MB. Pick a smaller one.");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("board", "true");
      const uploaded = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body });
      await wbFmtApply("replace", () => ({ url: uploaded.url }), "Picture replaced.");
    } catch (err) {
      toast(err?.message || "The picture could not be uploaded.");
    }
  });
  //: Edit image: a quarter turn, two flips, greyscale and two sliders, all kept as the picture's style
  //: (the file is untouched), each one Undo step; Reset clears them together.
  const PIX_KEYS = ["turn", "flip_x", "flip_y", "grey", "bright", "contrast"];
  on("wb-fmt-turn", "click", () => wbFmtApply("pixels", (entry) => ({ turn: ((Number(wbFmtValue(entry, "turn")) + 90) % 360) || undefined }), "Picture turned a quarter."));
  on("wb-fmt-flipx", "click", () => wbFmtApply("pixels", (entry) => ({ flip_x: wbFmtValue(entry, "flipx") ? undefined : true }), "Picture flipped left to right."));
  on("wb-fmt-flipy", "click", () => wbFmtApply("pixels", (entry) => ({ flip_y: wbFmtValue(entry, "flipy") ? undefined : true }), "Picture flipped top to bottom."));
  on("wb-fmt-grey", "click", () => wbFmtApply("pixels", (entry) => ({ grey: wbFmtValue(entry, "grey") ? undefined : true }), "Greyscale toggled."));
  for (const [id, key, word] of [["wb-fmt-bright", "bright", "Brightness"], ["wb-fmt-contrast", "contrast", "Contrast"]]) {
    on(id, "change", (e) => {
      const pct = boxNumber(e.target, 20, 200);
      wbFmtApply("pixels", () => ({ [key]: pct === undefined || pct === 100 ? undefined : pct }), pct === undefined ? `${word} as shot.` : `${word} ${pct}.`);
    });
  }
  on("wb-fmt-pixreset", "click", () => wbFmtApply("pixels", () => Object.fromEntries(PIX_KEYS.map((k) => [k, undefined])), "Picture edits cleared."));
  //: **Crop on the picture**: a box with eight handles over the picture, in the picture's own (turned)
  //: frame; dragging a handle moves that edge and writes the same `trim` the four numbers write, so
  //: the numbers stay as the exact path. The box keeps its place: only the edges you drag move.
  //: Arrow keys on a focused handle nudge it a percent. Escape or the button again ends it.
  const cropBox = { frame: null };
  const cropKey = (e) => {
    if (e.key === "Escape" && cropBox.frame) {
      e.preventDefault();
      e.stopPropagation();
      cropClose();
    }
  };
  const cropClose = () => {
    cropBox.frame?.remove();
    cropBox.frame = null;
    wbFmtState.cropEdit = null;
    document.getElementById("wb-fmt-cropbox")?.setAttribute("aria-pressed", "false");
    document.removeEventListener("keydown", cropKey, true);
  };
  const cropOpen = () => {
    const entry = wbFmtEntries().find((e) => e.kind === "object" && e.item.kind === "image");
    const el = entry && document.querySelector(`#wb-html-layer .wb-object[data-id="${entry.id}"]`);
    if (!el) return;
    const frame = document.createElement("div");
    frame.className = "wb-crop-frame";
    const rect = document.createElement("div");
    rect.className = "wb-crop-rect";
    frame.append(rect);
    for (const name of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
      const grip = document.createElement("button");
      grip.type = "button";
      grip.className = "wb-crop-grip";
      grip.dataset.grip = name;
      grip.setAttribute("aria-label", `Crop handle ${name.toUpperCase()}`);
      rect.append(grip);
    }
    el.append(frame);
    cropBox.frame = frame;
    wbFmtState.cropEdit = { id: entry.id, close: cropClose };
    document.getElementById("wb-fmt-cropbox")?.setAttribute("aria-pressed", "true");
    document.addEventListener("keydown", cropKey, true);
    let trim = [0, 1, 2, 3].map((i) => Number(entry.item.data?.trim?.[i]) || 0);
    const place = () => {
      const pix = wbPixel(entry.item.data, el.offsetWidth, el.offsetHeight);
      frame.style.width = `${pix.w}px`;
      frame.style.height = `${pix.h}px`;
      frame.style.transform = `translate(-50%, -50%) ${pix.transform.replace("translate(-50%, -50%)", "").trim()}`.trim();
      rect.style.inset = `${trim[0]}% ${trim[1]}% ${trim[2]}% ${trim[3]}%`;
      const img = el.querySelector("img");
      if (img) img.style.clipPath = wbCropClip(entry.item.data?.crop, trim.some(Boolean) ? trim : undefined) || "";
    };
    place();
    const fits = (t) => t[0] + t[2] < 95 && t[1] + t[3] < 95;
    const commit = () => {
      const whole = trim.map((v) => Math.round(v));
      const set = whole.some(Boolean) && fits(whole);
      trim = set ? whole : [0, 0, 0, 0];
      wbFmtApply("trim", () => ({ trim: set ? whole : undefined }), set ? "Picture trimmed." : "Picture trim taken off.");
      place();
    };
    const move = (name, from, dx, dy) => {
      const next = from.slice();
      const w = frame.offsetWidth || 1, h = frame.offsetHeight || 1;
      if (name.includes("n")) next[0] = from[0] + (dy / h) * 100;
      if (name.includes("s")) next[2] = from[2] - (dy / h) * 100;
      if (name.includes("w")) next[3] = from[3] + (dx / w) * 100;
      if (name.includes("e")) next[1] = from[1] - (dx / w) * 100;
      const clamped = next.map((v) => Math.max(0, Math.min(90, v)));
      return fits(clamped) ? clamped : from;
    };
    for (const grip of frame.querySelectorAll(".wb-crop-grip")) {
      grip.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        e.preventDefault();
        grip.setPointerCapture(e.pointerId);
        const from = trim.slice();
        //: Screen pixels to the picture's own frame: the frame's turn and flips are an orthogonal matrix, so
        //: its inverse is its transpose, and the board's zoom is the box's drawn size over its layout size.
        const m = new DOMMatrix(getComputedStyle(frame).transform);
        const drawn = frame.getBoundingClientRect();
        const turned = Math.abs(m.b) > 0.5;
        const scale = (turned ? drawn.width / (frame.offsetHeight || 1) : drawn.width / (frame.offsetWidth || 1)) || 1;
        const at = [e.clientX, e.clientY];
        const drag = (ev) => {
          const sx = (ev.clientX - at[0]) / scale, sy = (ev.clientY - at[1]) / scale;
          trim = move(grip.dataset.grip, from, m.a * sx + m.b * sy, m.c * sx + m.d * sy);
          place();
        };
        const stop = () => {
          grip.removeEventListener("pointermove", drag);
          grip.removeEventListener("pointerup", stop);
          grip.removeEventListener("pointercancel", stop);
          commit();
        };
        grip.addEventListener("pointermove", drag);
        grip.addEventListener("pointerup", stop);
        grip.addEventListener("pointercancel", stop);
      });
      grip.addEventListener("keydown", (e) => {
        const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
        if (!step) return;
        e.preventDefault();
        e.stopPropagation();
        trim = move(grip.dataset.grip, trim, (step[0] * frame.offsetWidth) / 100, (step[1] * frame.offsetHeight) / 100);
        commit();
      });
    }
  };
  on("wb-fmt-cropbox", "click", () => (cropBox.frame ? cropClose() : cropOpen()));
  //: A rectangle crop: percent cut from the top, right, bottom and left; all empty is no trim.
  for (const edge of [0, 1, 2, 3]) {
    on(`wb-fmt-trim${edge}`, "change", () => {
      const trim = [0, 1, 2, 3].map((i) => boxNumber(document.getElementById(`wb-fmt-trim${i}`), 0, 90) || 0);
      const set = trim.some(Boolean) && trim[0] + trim[2] < 95 && trim[1] + trim[3] < 95;
      wbFmtApply("trim", () => ({ trim: set ? trim : undefined }), set ? "Picture trimmed." : "Picture trim taken off.");
    });
  }
  on("wb-fmt-raw-apply", "click", () => wbFmtState.raw.apply());
  on("wb-fmt-linestyle", "change", (e) => {
    const style = e.target.value;
    //: Rounded keeps the radius an item already has, else 12.
    wbFmtApply("linestyle", (entry) => ({ round: style === "rounded" ? Number(wbFmtValue(entry, "round")) || 12 : undefined, curve: style === "curved" ? true : undefined }), `Line style: ${style}.`);
  });
  on("wb-fmt-round", "change", (e) => {
    const radius = Math.max(0, Math.min(80, Math.round(Number(e.target.value) || 0)));
    wbFmtApply("round", () => ({ round: radius || undefined }), radius ? `Corners rounded by ${radius}.` : "Corners sharp.");
  });
  //: A blank box is the default and clears the value; a number is clamped to the
  //: server's bound. Setting a shadow's shape turns the shadow on, since an
  //: offset on an item with no shadow shows nothing.
  const boxNumber = (el, min, max) => (el.value === "" ? undefined : Math.max(min, Math.min(max, Math.round(Number(el.value) || 0))));
  for (const [id, key, min, max, word] of [["wb-fmt-shx", "shadow_x", -60, 60, "across"], ["wb-fmt-shy", "shadow_y", -60, 60, "down"], ["wb-fmt-shb", "shadow_blur", 0, 60, "blur"]]) {
    on(id, "change", (e) => {
      const value = boxNumber(e.target, min, max);
      wbFmtApply("shadowset", () => ({ [key]: value, shadow: true }), value === undefined ? `Shadow ${word} default.` : `Shadow ${word} ${value}.`);
    });
  }
  on("wb-fmt-pad", "change", (e) => {
    const value = boxNumber(e.target, 0, 80);
    wbFmtApply("pad", () => ({ pad: value }), value === undefined ? "Padding default." : `Padding ${value}px.`);
  });
  //: A picture's border: the width turns it on (the colour defaults to a dark grey), a blank width takes it off.
  on("wb-fmt-ibwidth", "change", (e) => {
    const value = boxNumber(e.target, 0, 40);
    const colour = document.getElementById("wb-fmt-ibcolor")?.value || "#333333";
    wbFmtApply("imageborder", (entry) => ({ border_width: value || undefined, ...(value && !entry.item.data?.border_color ? { border_color: colour } : {}) }), value ? `Border ${value}px.` : "Border taken off.");
  });
  on("wb-fmt-ibcolor", "change", (e) => wbFmtApply("imageborder", () => ({ border_color: e.target.value }), "Border colour changed."));
  for (const corner of [0, 1, 2, 3]) {
    on(`wb-fmt-r${corner}`, "change", () => {
      const radii = [0, 1, 2, 3].map((i) => boxNumber(document.getElementById(`wb-fmt-r${i}`), 0, 200));
      const set = radii.some((r) => r !== undefined);
      wbFmtApply("radii", () => ({ radii: set ? radii.map((r) => r ?? 0) : undefined }), set ? "Corner radii set." : "Corner radii default.");
    });
  }
  on("wb-fmt-flow", "change",(e) => wbFmtApply("flow", () => ({ flow: e.target.checked || undefined }), e.target.checked ? "Flow on." : "Flow off."));
  on("wb-fmt-dash", "change", (e) => wbFmtApply("dash", () => ({ dash: e.target.value === "solid" ? undefined : e.target.value }), `Line ${e.target.value}.`));
  on("wb-fmt-fill-on", "change", (e) => {
    const colour = document.getElementById("wb-fmt-fill")?.value || "#3355ff";
    wbFmtApply("fill", (entry) => wbColour.fillToggle(entry.kind === "sketch" ? "sketch" : entry.item.kind === "diagram" ? "diagram" : "object",
      entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data, e.target.checked, colour), e.target.checked ? "Filled." : "Fill taken off.");
  });
  //: A gradient or a fill style needs a colour to start from, so choosing one
  //: on an unfilled shape fills it first. The two are alternatives: one choice
  //: clears the other.
  const fillBase = (entry) => {
    const s = wbFmtSketch(entry);
    return { fill: s.fill || document.getElementById("wb-fmt-fill")?.value || "#3355ff", fillOpacity: s.fillOpacity ?? 1 };
  };
  on("wb-fmt-fillstyle", "change", (e) => {
    const style = WB_FILL_STYLES.includes(e.target.value) ? e.target.value : "solid";
    wbFmtApply("fillstyle", (entry) => (entry.kind === "sketch"
      ? (style === "solid" ? { fillStyle: undefined } : { ...fillBase(entry), fillStyle: style, gradient: undefined })
      : null), style === "solid" ? "Plain fill." : `Fill style: ${e.target.selectedOptions[0]?.textContent || style}.`);
  });
  on("wb-fmt-gradient-dir", "change", (e) => {
    const dir = e.target.value;
    const to = wbHexColour(document.getElementById("wb-fmt-gradient")?.value) || "#ffffff";
    wbFmtApply("gradient", (entry) => (entry.kind === "sketch"
      ? (dir === "none" ? { gradient: undefined } : { ...fillBase(entry), gradient: { to, dir }, fillStyle: undefined })
      : null), dir === "none" ? "Gradient off." : `Gradient: ${e.target.selectedOptions[0]?.textContent || dir}.`);
  });
  on("wb-fmt-gradient", "change", (e) => {
    const to = wbHexColour(e.target.value) || "#ffffff";
    wbFmtApply("gradient", (entry) => {
      if (entry.kind !== "sketch") return null;
      const dir = wbFmtValue(entry, "gradient-dir");
      return { ...fillBase(entry), gradient: { to, dir: dir === "none" ? "s" : dir }, fillStyle: undefined };
    }, "Gradient colour changed.");
  });
  on("wb-fmt-fill", "change", (e) => wbFmtApply("fill", (entry) => wbColour.fillColour(entry.kind === "sketch" ? "sketch" : entry.item.kind === "diagram" ? "diagram" : "object",
    entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data, e.target.value), "Fill colour changed."));
  on("wb-fmt-alpha", "input", (e) => {
    const out = document.getElementById("wb-fmt-alpha-out");
    if (out) out.textContent = `${e.target.value}%`;
  });
  on("wb-fmt-alpha", "change", (e) => {
    const pct = Math.max(10, Math.min(100, Number(e.target.value) || 100));
    wbFmtApply("alpha", () => ({ alpha: pct >= 100 ? undefined : pct / 100 }), `Opacity ${pct}%.`);
  });
  //: A fill's opacity on a shape with no fill yet fills it first, so the
  //: slider and the presets always do what they say. 0 is a real answer.
  const alphaSetters = { fillalpha: (pct) => wbColour.setAlpha("fillalpha", pct), strokealpha: (pct) => wbColour.setAlpha("strokealpha", pct) };
  const alphaPct = (value) => Math.max(0, Math.min(100, Number.isFinite(Number(value)) && value !== "" ? Number(value) : 100));
  for (const name of Object.keys(alphaSetters)) {
    on(`wb-fmt-${name}`, "input", (e) => {
      const out = document.getElementById(`wb-fmt-${name}-out`);
      if (out) out.textContent = `${e.target.value}%`;
    });
    on(`wb-fmt-${name}`, "change", (e) => alphaSetters[name](alphaPct(e.target.value)));
  }
  panel.addEventListener("click", (e) => {
    const button = e.target.closest?.("[data-alpha-preset]");
    if (button) alphaSetters[button.dataset.alphaFor]?.(alphaPct(button.dataset.alphaPreset));
  });
  on("wb-fmt-fold", "change", (e) => wbFmtApply("fold", (entry) => (entry.kind === "object" && wbIsSticky(entry.item) ? { fold: e.target.checked } : null), e.target.checked ? "Corner folded." : "Corner flat."));
  on("wb-fmt-tableheader", "change", (e) => wbFmtApply("tableheader", (entry) => (entry.item.kind === "table" ? { header: e.target.checked || undefined } : null), e.target.checked ? "First row is a header." : "First row is plain."));
  //: A frame marked Stack keeps what it holds in a column; turning it on stacks at once, as one Undo step with the switch
  //: (wbFmtApply's gesture settles the lane before it closes, `wbRecordGesture`).
  on("wb-fmt-stack", "change", (e) => wbFmtApply("stack", (entry) => (entry.item.kind === "frame" ? { stack: e.target.checked || undefined } : null), e.target.checked ? "Frame stacks what it holds." : "Frame stacks nothing."));
  on("wb-fmt-stripes", "change", (e) => wbFmtApply("stripes", (entry) => (entry.item.kind === "table" ? { stripes: e.target.checked || undefined } : null), e.target.checked ? "Rows striped." : "Rows plain."));
  on("wb-fmt-shadow", "change", (e) => wbFmtApply("shadow", () => ({ shadow: e.target.checked || undefined }), e.target.checked ? "Shadow on." : "Shadow off."));
  //: An item that matches the board's look stores nothing, so it follows the
  //: board when the board's look changes.
  on("wb-fmt-rough", "change", (e) => {
    const board = wbBoardBackground().rough === true;
    wbFmtApply("rough", () => ({ rough: e.target.checked === board ? undefined : e.target.checked }), e.target.checked ? "Hand-drawn." : "Drawn plain.");
  });
  on("wb-fmt-route", "change", (e) => wbSetLinkRoute(e.target.value));
  on("wb-fmt-edgeshape", "change", (e) => {
    const shape = wbFmtState.shapeMore?.CONNECTOR_SHAPES.includes(e.target.value) ? e.target.value : "line";
    wbFmtApply("edgeshape", () => ({ shape: shape === "line" ? undefined : shape }), `Connector shape: ${wbFmtState.shapeMore.CONNECTOR_SHAPE_WORDS[shape]}.`);
  });
  on("wb-fmt-textpath", "change", (e) => wbFmtApply("textpath", () => ({ label_path: e.target.checked || undefined }), e.target.checked ? "Label set along the line." : "Label flat again."));
  on("wb-fmt-jumps", "change", (e) => {
    const style = WB_JUMP_STYLES.includes(e.target.value) ? e.target.value : "none";
    wbFmtApply("jumps", () => ({ jumps: style === "none" ? undefined : style }), `Line jumps: ${e.target.selectedOptions[0]?.textContent || style}.`);
  });
  //: Empty is automatic, so it stores nothing.
  on("wb-fmt-jumpsize", "change", (e) => {
    const size = e.target.value === "" ? null : Math.max(2, Math.min(40, Math.round(Number(e.target.value) || 0)));
    wbFmtApply("jumpsize", () => ({ jumpSize: size || undefined }), size ? `Jump size ${size}.` : "Jump size automatic.");
  });
  on("wb-fmt-gapstart", "change", (e) => {
    const gap = Math.max(0, Math.min(60, Math.round(Number(e.target.value) || 0)));
    wbFmtApply("gapstart", () => ({ gapStart: gap || undefined }), gap ? `Start gap ${gap}.` : "Start touches the shape.");
  });
  on("wb-fmt-tip", "change", (e) => {
    const tip = e.target.value.trim().slice(0, 200);
    wbFmtApply("tip", () => ({ tip: tip || undefined }), tip ? "Tooltip set." : "Tooltip removed.");
  });
  on("wb-fmt-gapend", "change", (e) => {
    const gap = Math.max(0, Math.min(60, Math.round(Number(e.target.value) || 0)));
    wbFmtApply("gapend", () => ({ gapEnd: gap || undefined }), gap ? `End gap ${gap}.` : "End touches the shape.");
  });
  for (const which of ["start", "end"]) {
    on(`wb-fmt-${which}cap`, "change", (e) => wbFmtApply("caps", (entry, kind) => {
      const parsed = wbFmtSketch(entry);
      //: A drawn line carries its ends in its path, so the path is redrawn;
      //: a connector's are drawn from the two fields at render time.
      const caps = kind === "arrow" ? wbSketchCaps(parsed) : wbLinkCaps(parsed);
      caps[`${which}Cap`] = e.target.value;
      return wbFmtCapFields(kind, parsed, caps);
    }, `${which === "start" ? "Start" : "End"}: ${e.target.selectedOptions[0]?.textContent || e.target.value}.`));
    on(`wb-fmt-${which}size`, "change", (e) => wbFmtApply("caps", (entry, kind) => {
      const parsed = wbFmtSketch(entry);
      const caps = kind === "arrow" ? wbSketchCaps(parsed) : wbLinkCaps(parsed);
      caps[`${which}Size`] = e.target.value;
      return wbFmtCapFields(kind, parsed, caps);
    }, `${which === "start" ? "Start" : "End"} size: ${e.target.selectedOptions[0]?.textContent || e.target.value}.`));
  }
  on("wb-fmt-label-t", "change", (e) => {
    const pct = Math.max(5, Math.min(95, Number(e.target.value) || 50));
    wbFmtApply("label-t", () => ({ label_t: pct === 50 ? undefined : pct / 100 }), `Label at ${pct}% along the line.`);
  });
  //: A connector's label look (audit t20#12): size, colour, bold and a chip
  //: behind the words, saved beside `label_t` and painted by `wbPaintLinkLabel`.
  on("wb-fmt-lsize", "change", (e) => {
    const size = Math.max(8, Math.min(72, Math.round(Number(e.target.value) || 16)));
    wbFmtApply("linklook", () => ({ label_size: size === 16 ? undefined : size }), `Label size ${size}.`);
  });
  on("wb-fmt-lcolor", "change", (e) => wbFmtApply("linklook", () => ({ label_color: e.target.value }), "Label colour changed."));
  for (const [id, key, word] of [["wb-fmt-lbold", "label_bold", "Label bold"], ["wb-fmt-lchip", "label_chip", "Label chip"]]) {
    on(id, "click", (e) => {
      const next = e.currentTarget.getAttribute("aria-pressed") !== "true";
      e.currentTarget.setAttribute("aria-pressed", String(next));
      wbFmtApply("linklook", () => ({ [key]: next || undefined }), `${word} ${next ? "on" : "off"}.`);
    });
  }
  const textPatch = (shapeKey, objectKey, value) => (entry, kind) => (kind === "shape" ? { [shapeKey]: value } : { [objectKey]: value });
  on("wb-fmt-size", "change", (e) => {
    const size = Math.max(8, Math.min(200, Math.round(Number(e.target.value) || 16)));
    wbFmtApply("text", textPatch("label_size", "font_size", size), `Text size ${size}.`);
  });
  on("wb-fmt-ink", "change", (e) => wbFmtApply("text", textPatch("label_color", "color", e.target.value), "Text colour changed."));
  on("wb-fmt-font", "change", (e) => {
    const face = e.target.value && e.target.value !== "default" ? e.target.value : undefined;
    wbFmtApply("text", textPatch("label_font", "font_family", face), face ? `Font: ${e.target.selectedOptions[0]?.textContent}.` : "Font back to the default.");
  });
  for (const [id, shapeKey, objectKey, word] of [
    ["wb-fmt-bold", "label_bold", "bold", "Bold"], ["wb-fmt-italic", "label_italic", "italic", "Italic"],
    ["wb-fmt-underline", "label_underline", "underline", "Underline"], ["wb-fmt-strike", "label_strike", "strike", "Strikethrough"],
  ]) {
    on(id, "click", (e) => {
      const next = e.currentTarget.getAttribute("aria-pressed") !== "true";
      e.currentTarget.setAttribute("aria-pressed", String(next));
      wbFmtApply("text", textPatch(shapeKey, objectKey, next || undefined), `${word} ${next ? "on" : "off"}.`);
    });
  }
  on("wb-fmt-lh", "change", (e) => {
    const raw = Number(e.target.value);
    const lh = raw > 0 ? Math.max(0.8, Math.min(3, Math.round(raw * 20) / 20)) : undefined;
    wbFmtApply("text", textPatch("label_lh", "line_height", lh), lh ? `Line spacing ${lh}.` : "Line spacing automatic.");
  });
  on("wb-fmt-ls", "change", (e) => {
    const raw = Number(e.target.value);
    const ls = raw ? Math.max(-5, Math.min(30, Math.round(raw * 2) / 2)) : undefined;
    wbFmtApply("text", textPatch("label_ls", "letter_spacing", ls), ls ? `Letter spacing ${ls}px.` : "Letter spacing normal.");
  });
  //: Direction and text opacity (draw.io's Text tab, INBOX 1510(a)): the
  //: default is stored as no value, so a reset box and an untouched one match.
  on("wb-fmt-dir", "change", (e) => {
    const dir = e.target.value || undefined;
    wbFmtApply("text", textPatch("label_dir", "text_dir", dir), dir ? `Text ${e.target.selectedOptions[0]?.textContent.toLowerCase()}.` : "Text left to right.");
  });
  on("wb-fmt-inkalpha", "change", (e) => {
    const pct = Math.max(10, Math.min(100, Math.round(Number(e.target.value) || 100)));
    wbFmtApply("text", textPatch("label_alpha", "text_alpha", pct === 100 ? undefined : pct / 100), `Text opacity ${pct}%.`);
  });
  on("wb-fmt-fit", "click", () => wbToggleLabelFit());
  on("wb-fmt-align", "click", (e) => {
    const button = e.target.closest("[data-align]");
    if (!button) return;
    wbFmtApply("text", textPatch("label_align", "align", button.dataset.align), `Text aligned ${button.dataset.align}.`);
  });
  on("wb-fmt-valign", "click", (e) => {
    const button = e.target.closest("[data-valign]");
    if (!button) return;
    const at = button.dataset.valign;
    //: The kind's own default is stored as no value, so a reset style and a
    //: box never touched read the same.
    wbFmtApply("text", (entry, kind) => {
      const plain = kind === "shape" ? "middle" : "top";
      return kind === "shape" ? { label_valign: at === plain ? undefined : at } : { valign: at === plain ? undefined : at };
    }, `Text at the ${at}.`);
  });
  on("wb-fmt-link", "click", wbFmtToggleLink);
  for (const axis of ["x", "y", "w", "h"]) {
    on(`wb-fmt-${axis}`, "change", (e) => wbFmtGeometry(axis, wbFmtState.opts?.read(e.target.value) ?? Number(e.target.value)));
  }
  on("wb-fmt-angle", "change", (e) => wbFmtAngle(Number(e.target.value) || 0));
  on("wb-fmt-aspect", "change", (e) => wbFmtAspect(Number(e.target.value)));
  on("wb-fmt-flip-h", "click", () => wbFmtFlip("h"));
  on("wb-fmt-flip-v", "click", () => wbFmtFlip("v"));
  on("wb-fmt-save-style", "click", () => wbRunCommand("save-style"));
  on("wb-fmt-props", "change", () => wbFmtSaveProps());
  on("wb-fmt-prop-add", "click", () => {
    const row = wbFmtPropRow();
    document.getElementById("wb-fmt-props")?.append(row);
    row.querySelector("input")?.focus();
  });
  on("wb-fmt-copy-style", "click", () => document.getElementById("wb-copy-style")?.click());
  on("wb-fmt-paste-style", "click", () => document.getElementById("wb-paste-style")?.click());
});

//: --- Text commands (draw.io's "Clear formatting", and its font size steps) ---
//:
//: Both go through `wbFmtApply("text", ...)`, so a selection of a shape and a
//: text box is one step on the stack and an item with no text of its own is
//: skipped.
const WB_TEXT_LOOK_KEYS = {
  shape: ["label_size", "label_color", "label_bold", "label_italic", "label_underline", "label_strike", "label_font", "label_align", "label_valign", "label_fit", "label_lh", "label_ls", "label_dir", "label_alpha"],
  text: ["font_size", "color", "bold", "italic", "underline", "strike", "font_family", "align", "valign", "line_height", "letter_spacing", "text_dir", "text_alpha"],
};

//: Shrink to fit, on or off for every selected shape as one step: on unless
//: every one of them already shrinks.
function wbToggleLabelFit() {
  const shapes = wbFmtEntries().filter((e) => wbFmtKind(e) === "shape");
  const next = !shapes.length || !shapes.every((e) => wbFmtValue(e, "fit"));
  return wbFmtApply("fit", () => ({ label_fit: next || undefined }), next ? "The text shrinks to fit the shape." : "The text keeps its size.");
}

function wbClearTextFormat() {
  return wbFmtApply("text", (entry, kind) => {
    const keys = WB_TEXT_LOOK_KEYS[kind];
    return keys ? Object.fromEntries(keys.map((key) => [key, undefined])) : null;
  }, "Text formatting cleared.");
}

function wbStepFontSize(delta) {
  return wbFmtApply("text", (entry, kind) => {
    const size = Math.max(8, Math.min(200, Math.round(Number(wbFmtValue(entry, "size")) + delta)));
    return kind === "shape" ? { label_size: size } : { font_size: size };
  }, delta > 0 ? "Text larger." : "Text smaller.");
}

//: --- draw.io's arrange and edit commands (whiteboard-1018) ---
//:
//: Each is one `wbRecordGesture`, so a selection of many is one undo step.

//: Turn 90 degrees: a card, text box or picture takes 90 more on its
//: `rotation`; a drawn shape has its turn baked into its path, so the path is
//: turned about its own centre. Each item turns about its own centre, and a
//: connector follows its ends.
function wbTurnSelection(degrees = 90) {
  wbFmtState.keys?.record({ kind: "turn", deg: degrees });
  return wbRecordGesture(async () => {
    const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item) && e.bbox);
    let turned = 0;
    const saves = [];
    for (const e of entries) {
      if (e.kind === "sketch") {
        const parsed = wbSketchParsedData(e.item);
        if (typeof parsed?.d !== "string") continue;
        wbSketchSetD(e.item, wbTransformPathD(parsed.d, {
          rotate: degrees, anchorX: (e.bbox.minX + e.bbox.maxX) / 2, anchorY: (e.bbox.minY + e.bbox.maxY) / 2,
        }));
        saves.push({ kind: "sketch", item: e.item });
      } else {
        if (wbFmtKind(e) === "topic") continue;
        e.item.rotation = ((Math.round((e.item.rotation || 0) + degrees) % 360) + 360) % 360 || null;
        saves.push({ kind: e.kind, item: e.item });
      }
      turned += 1;
    }
    await wbSaveMany(saves);
    if (turned) wbAnnounce(`Turned ${degrees} degrees.`);
    else toast("Select a shape, note or picture to turn it.");
  }).then(() => wbScheduleRender());
}

//: Remove from group: the selected members leave the innermost group they
//: are in (groups nest, `wbGroupChain`), and a group left with one member is
//: no group (a lone member would still pull a click onto itself alone).
function wbRemoveFromGroup() {
  return wbRecordGesture(async () => {
    const leaving = wbFmtEntries().filter((e) => e.item.group_id);
    if (!leaving.length) return;
    const rows = [];
    for (const e of leaving) {
      const chain = wbGroupChain(e.item);
      chain.pop();
      e.item.group_id = chain.length ? chain.join(WB_GROUP_SEP) : null;
      rows.push({ kind: e.kind, item: e.item });
    }
    wbDropLoneGroups(rows);
    await wbSaveMany(rows);
    wbAnnounce("Removed from the group.");
    wbUpdateContextBar();
  });
}

//: Each group id held by one item only is taken off it; the items it changed
//: go onto `rows`, which the caller saves once with the rest.
function wbDropLoneGroups(rows) {
  const all = wbItemsWithGroupPrefix([]);
  const count = new Map();
  for (const { item } of all) for (const seg of wbGroupChain(item)) count.set(seg, (count.get(seg) || 0) + 1);
  for (const { kind, item } of all) {
    const chain = wbGroupChain(item);
    const kept = chain.filter((seg) => count.get(seg) > 1);
    if (kept.length === chain.length) continue;
    item.group_id = kept.length ? kept.join(WB_GROUP_SEP) : null;
    rows.push({ kind, item });
  }
}

//: Copy size and Paste size (draw.io's Alt+Shift+F and V): the width and height
//: of one item, put on every selected one. A connector has no box.

function wbCopySize() {
  const [entry] = wbFmtEntries();
  if (!entry?.bbox) {
    toast("Select a shape, note or picture to copy its size.");
    return;
  }
  wbFmtState.sizeClip = { w: Math.round(entry.bbox.maxX - entry.bbox.minX), h: Math.round(entry.bbox.maxY - entry.bbox.minY) };
  wbAnnounce(`Size ${wbFmtState.sizeClip.w} by ${wbFmtState.sizeClip.h} copied.`);
}

function wbPasteSize() {
  if (!wbFmtState.sizeClip) {
    toast("Copy a size first.");
    return Promise.resolve();
  }
  const clip = wbFmtState.sizeClip;
  return wbRecordGesture(async () => {
    const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item) && e.bbox && wbFmtKind(e) !== "topic");
    const rows = [];
    for (const e of entries) {
      for (const [dim, target, size] of [["width", Math.max(8, clip.w), e.bbox.maxX - e.bbox.minX], ["height", Math.max(8, clip.h), e.bbox.maxY - e.bbox.minY]]) {
        if (size > 0 && Math.abs(size - target) >= 0.5) wbSizeItemTo(e, dim, target, target / size, rows);
      }
    }
    await wbSaveMany(rows);
    wbAnnounce(`Size ${clip.w} by ${clip.h} pasted.`);
  }).then(() => wbScheduleRender());
}

//: Copy data and Paste data (draw.io's Alt+Shift+B and E): the custom properties
//: (`data.props`) of one item put on every selected one, as one Undo step. A
//: paste replaces what the target had, as the Data tab does when you retype it.
wbFmtState.dataClip = null;
wbFmtState.dataKeys = (() => {
  function copy() {
    const [entry] = wbFmtEntries();
    const props = entry && (entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data || {}).props;
    if (!props || typeof props !== "object" || !Object.keys(props).length) {
      toast("That item has no data to copy.");
      return;
    }
    wbFmtState.dataClip = { ...props };
    const n = Object.keys(props).length;
    wbAnnounce(`Data copied: ${n === 1 ? "1 property" : `${n} properties`}.`);
  }
  function paste() {
    if (!wbFmtState.dataClip) {
      toast("Copy an item's data first.");
      return Promise.resolve();
    }
    const clip = wbFmtState.dataClip;
    return wbFmtApply("props", () => ({ props: { ...clip } }), "Data pasted.");
  }
  return { copy, paste };
})();

//: How much a shape must grow for its words to fit: the factor on each axis,
//: 1 when they already fit. The words' area scales with the shape, so the
//: factor is the words' size over the area they have.
function wbAutoSizeFactors(text, area) {
  const grow = (need, have) => (have > 0 && need > have + 0.5 ? need / have : 1);
  return { sx: grow(text.w, area.w), sy: grow(text.h, area.h) };
}

//: One shape grown until its words fit (never shrinks), from its top-left
//: corner, keeping its proportions: the words wrap to the shape's width, so
//: growing only the height made a diamond 733px tall for one sentence; both
//: sides grow by the root of what is missing and the fit is measured again
//: (a few rounds at most). Returns whether it changed. Run by the command
//: and, on its own, when a label is typed into a shape: 80 characters in a
//: 100x60 rectangle used to be drawn 160px tall across the border.
async function wbGrowShapeToLabel(sketch) {
  //: Words set outside a shape (`label_pos`) are not inside it to be fitted.
  if (wbSketchParsedData(sketch)?.label_pos) return false;
  let changed = false;
  for (let round = 0; round < 4; round += 1) {
    const group = document.querySelector(`.sketch-group[data-id="${sketch.id}"]`);
    const label = group?.querySelector(":scope > .sketch-label");
    const placed = label ? wbShapeLabelPlace(group, label) : null;
    const parsed = wbSketchParsedData(sketch);
    const bbox = parsed?.d ? wbPathBBox(parsed.d) : null;
    if (!placed || !bbox) break;
    const words = label.getBBox();
    const { sx, sy } = wbAutoSizeFactors({ w: words.width, h: words.height }, placed.area);
    if (sx === 1 && sy === 1) break;
    const f = Math.max(sx, Math.sqrt(sy), 1.05);
    await wbSaveSketchD(sketch, wbTransformPathD(parsed.d, { sx: f, sy: f, anchorX: bbox.minX, anchorY: bbox.minY }));
    changed = true;
    renderWhiteboardNow();
  }
  return changed;
}

//: Grow to fit: a shape taller (or wider, for one long word) until its words
//: fit; a text box or a note card taller until its text does. Never shrinks.
function wbAutoSizeSelection() {
  return wbRecordGesture(async () => {
    let grown = 0;
    const saves = [];
    for (const e of wbFmtEntries().filter((x) => !wbIsLocked(x.kind, x.item) && x.bbox)) {
      const kind = wbFmtKind(e);
      if (kind === "shape") {
        if (await wbGrowShapeToLabel(e.item)) grown += 1;
      } else if (kind === "text" || kind === "note") {
        const el = wbItemElement(e.kind, e.id);
        if (!el) continue;
        const current = e.item.height || el.offsetHeight;
        //: A text box's words are clipped inside their own element, so the
        //: element's height is the box's, not the words': the words' own
        //: scroll height plus the box's chrome. (`wbCardFitHeight` opens a
        //: note card up the same way; at phone width its answer for a text
        //: box was the clipped height.)
        const fit = el.querySelector(".wb-text-content") ? wbTextFitHeight(el) : wbCardFitHeight(el);
        if (!(fit > current + 1)) continue;
        e.item.height = Math.round(fit);
        saves.push({ kind: e.kind, item: e.item });
        grown += 1;
      }
    }
    await wbSaveMany(saves);
    wbAnnounce(grown ? "Grown to fit the words." : "Everything already fits.");
  }).then(() => wbScheduleRender());
}

//: Clear waypoints: a connector's bends (`points`, and the old single `bend`)
//: go, and it runs the way its shape would on its own.
function wbClearWaypoints() {
  return wbFmtApply("route", (entry) => {
    const parsed = wbFmtSketch(entry);
    return parsed?.points?.length || parsed?.bend ? { points: undefined, bend: undefined } : null;
  }, "Bends cleared.");
}

//: Reverse: a connector points the other way, a drawn arrow's heads swap ends.
//: The patch for a connector, pure: both ends, their anchors and free points,
//: the two cap marks and their sizes, the bends in the other order, a curve's
//: bow to the other side and the label's place along the line mirrored.
function wbReversedLinkFields(parsed) {
  const caps = wbLinkCaps(parsed);
  const bend = Number(parsed.bend);
  return {
    sourceId: parsed.targetId, targetId: parsed.sourceId,
    sourceKind: parsed.targetKind, targetKind: parsed.sourceKind,
    sourceAnchor: parsed.targetAnchor, targetAnchor: parsed.sourceAnchor,
    sourcePoint: parsed.targetPoint, targetPoint: parsed.sourcePoint,
    startCap: caps.endCap, endCap: caps.startCap, endStyle: undefined,
    startCapSize: caps.endSize || undefined, endCapSize: caps.startSize || undefined,
    points: parsed.points ? [...parsed.points].reverse() : undefined,
    bend: Number.isFinite(bend) && bend ? -bend : parsed.bend,
    label_t: parsed.label_t != null ? Math.round((1 - wbLinkLabelT(parsed)) * 100) / 100 : undefined,
  };
}

function wbReverseSelection() {
  return wbRecordGesture(async () => {
    let turned = 0;
    const rows = [];
    for (const e of wbFmtEntries().filter((x) => x.kind === "sketch" && !wbIsLocked(x.kind, x.item))) {
      const kind = wbFmtKind(e);
      const parsed = wbFmtSketch(e);
      let patch = null;
      if (kind === "link") {
        patch = wbReversedLinkFields(parsed);
      } else if (kind === "arrow") {
        const caps = wbSketchCaps(parsed);
        patch = wbFmtCapFields("arrow", parsed, { startCap: caps.endCap, endCap: caps.startCap, startSize: caps.endSize, endSize: caps.startSize });
      }
      if (!patch || !wbSketchSetProps(e.item, patch)) continue;
      rows.push({ kind: "sketch", item: e.item });
      turned += 1;
    }
    await wbSaveMany(rows);
    if (turned) wbAnnounce("Reversed.");
    else toast("Select a connector or an arrow to reverse it.");
  }).then(() => wbScheduleRender());
}

//: --- The hand-drawn look (Excalidraw's; canvasdepth2) ---------------------
//:
//: A board option (`background.rough`) or an item's own `rough`, over it.
//: Each line is sampled along its length, given a slow wobble from a
//: generator seeded by the item's id, and drawn twice, so a shape looks the
//: same on every render and every machine. The freehand pen and the
//: highlighter are already by hand; a map's lines keep the map's look.
const WB_ROUGH_CACHE = new Map();
const WB_ROUGH_STEP = 6;

function wbDrawsRough(data, mapLine) {
  if (!data || mapLine || data.shape === "draw" || data.shape === "highlighter" || wbIsMap()) return false;
  return typeof data.rough === "boolean" ? data.rough : wbBoardBackground().rough === true;
}

//: mulberry32: small, fast and the same everywhere.
function wbRoughRandom(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function wbRoughProbe() {
  let probe = document.getElementById("wb-rough-probe");
  if (!probe) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("wb-rough-probe");
    probe = document.createElementNS("http://www.w3.org/2000/svg", "path");
    probe.id = "wb-rough-probe";
    svg.append(probe);
    document.body.append(svg);
  }
  return probe;
}

//: Points through a Catmull-Rom spline, as cubic Béziers.
function wbRoughSpline(points) {
  const f = (n) => Math.round(n * 10) / 10;
  let d = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d;
}

function wbRoughD(d, seed) {
  if (!d) return d;
  const key = `${seed}|${d}`;
  const hit = WB_ROUGH_CACHE.get(key);
  if (hit) return hit;
  const probe = wbRoughProbe();
  const rand = wbRoughRandom(Number(seed) * 2654435761 || 1);
  //: Each subpath on its own, or the sampler would join them; a relative
  //: `m` cannot be split safely, so such a path is sampled whole.
  const parts = /m/.test(d) ? [d] : d.split(/(?=M)/).filter((part) => part.trim());
  let out = "";
  for (const part of parts) {
    probe.setAttribute("d", part);
    const total = probe.getTotalLength();
    if (!(total > 1)) {
      out += part;
      continue;
    }
    const n = Math.max(6, Math.min(240, Math.round(total / WB_ROUGH_STEP)));
    const points = [];
    for (let i = 0; i <= n; i += 1) {
      const p = probe.getPointAtLength((total * i) / n);
      points.push([p.x, p.y]);
    }
    for (let pass = 0; pass < 2; pass += 1) {
      const amp = Math.min(2.4, 0.9 + total / 700) * (pass ? 1.25 : 1);
      const knots = Array.from({ length: Math.ceil(n / 5) + 2 }, () => [(rand() - 0.5) * 2 * amp, (rand() - 0.5) * 2 * amp]);
      out += wbRoughSpline(points.map(([x, y], i) => {
        const at = i / 5;
        const k = Math.floor(at);
        const t = at - k;
        const s = t * t * (3 - 2 * t);
        return [x + knots[k][0] + (knots[k + 1][0] - knots[k][0]) * s, y + knots[k][1] + (knots[k + 1][1] - knots[k][1]) * s];
      }));
    }
  }
  if (WB_ROUGH_CACHE.size > 4000) WB_ROUGH_CACHE.clear();
  WB_ROUGH_CACHE.set(key, out);
  return out;
}

//: --- Tables (draw.io's; canvasdepth2) -------------------------------------
//:
//: An object of kind `table`: `data.cells`, rows of text, and `data.header`
//: for a bold first row. The grid fills the object's box, so resizing the
//: table is the object's own resize; each row and column takes an equal
//: share. Double-click a cell to type in it; Tab and Shift+Tab walk the
//: cells, Enter keeps the words, Escape drops them. The cell last pressed is
//: where the menu's rows and columns go in or come out.
//: table-core-begin (pure; tests/test_wb_table_merge.py runs this block under node)
const WB_TABLE_ROW_H = 40;
const WB_TABLE_COL_W = 120;

function wbTableCells(d) {
  const cells = Array.isArray(d.data?.cells) && d.data.cells.length ? d.data.cells : [[""]];
  return cells.map((row) => (Array.isArray(row) ? row.map((c) => String(c ?? "")) : [""]));
}

//: **A table's column widths** (wb5): `data.col_widths`, one relative weight
//: per column with a mean of 1, so the box's width times a weight over the
//: column count is that column's width. Absent, or not one weight per column,
//: reads as equal, so a table made before this is unchanged.
const WB_TABLE_WEIGHT_MIN = 0.25;
const WB_TABLE_WEIGHT_MAX = 6;

function wbTableWeights(d) {
  const cols = wbTableCells(d)[0].length;
  const w = d.data?.col_widths;
  const ok = Array.isArray(w) && w.length === cols && w.every((n) => Number.isFinite(n) && n > 0);
  return ok ? w : Array(cols).fill(1);
}

//: The weights with column `c` scaled by `factor`, held to the least and most
//: a column may take and scaled back to a mean of 1 (so the others give way
//: and the table keeps its width). `null` when nothing would change.
function wbTableResizeColumn(weights, c, factor) {
  const next = weights.map((n, i) => (i === c ? Math.min(WB_TABLE_WEIGHT_MAX, Math.max(WB_TABLE_WEIGHT_MIN, n * factor)) : n));
  const mean = next.reduce((a, n) => a + n, 0) / next.length;
  const out = next.map((n) => Math.round((n / mean) * 1000) / 1000);
  return out.every((n, i) => Math.abs(n - weights[i]) < 0.001) ? null : out;
}

//: Where each column (or row) starts, as a share of the whole: [0, ..., 1].
function wbTableColumnEdges(weights) {
  const sum = weights.reduce((a, n) => a + n, 0);
  let at = 0;
  return [0, ...weights.map((n) => (at += n / sum))];
}

const wbTableRules = (() => {
  //: **A table's row heights**, the same kind of weights as the columns' (mean 1,
  //: `data.row_heights`, absent or the wrong length reads as equal).
  function wbTableRowWeights(d) {
    const rows = wbTableCells(d).length;
    const h = d.data?.row_heights;
    const ok = Array.isArray(h) && h.length === rows && h.every((n) => Number.isFinite(n) && n > 0);
    return ok ? h : Array(rows).fill(1);
  }

  //: Weights after a drag of the line between track `i` and the next: the two
  //: trade `shift` (in weight units), each held to the least and most a track
  //: may take, so the others and the table's size are untouched. `null` when
  //: nothing would change.
  function wbTableDragWeights(weights, i, shift) {
    const a = weights[i];
    const b = weights[i + 1];
    if (a === undefined || b === undefined || !Number.isFinite(shift)) return null;
    const lo = Math.max(WB_TABLE_WEIGHT_MIN - a, b - WB_TABLE_WEIGHT_MAX);
    const by = Math.max(lo, Math.min(WB_TABLE_WEIGHT_MAX - a, b - WB_TABLE_WEIGHT_MIN, shift));
    const out = weights.map((n, k) => Math.round((k === i ? a + by : k === i + 1 ? b - by : n) * 1000) / 1000);
    return out.every((n, k) => Math.abs(n - weights[k]) < 0.001) ? null : out;
  }

  //: Weights after a row or column goes in or out at `at` (a new track takes an
  //: average share), back to a mean of 1.
  function wbTableAxisWeights(weights, at, remove) {
    const total = weights.reduce((a, n) => a + n, 0);
    const grown = remove ? weights.filter((_, i) => i !== at) : [...weights.slice(0, at), total / weights.length, ...weights.slice(at)];
    const mean = grown.reduce((a, n) => a + n, 0) / grown.length;
    return grown.map((n) => Math.round((n / mean) * 1000) / 1000);
  }

  //: **Merged cells**: `data.merges`, each `{r, c, rs, cs}`, the cell at row r,
  //: column c spanning rs rows and cs columns. Only those inside the grid,
  //: covering two cells or more and clear of the ones before them are kept, so a
  //: hand-edited or stale list cannot break the grid.
  function wbTableCleanMerges(list, rows, cols) {
    const taken = new Set();
    const out = [];
    for (const m of Array.isArray(list) ? list : []) {
      const ok = [m?.r, m?.c, m?.rs, m?.cs].every(Number.isInteger) && m.r >= 0 && m.c >= 0 && m.rs >= 1 && m.cs >= 1 && m.rs * m.cs > 1 && m.r + m.rs <= rows && m.c + m.cs <= cols;
      if (!ok) continue;
      const spots = [];
      for (let r = m.r; r < m.r + m.rs; r += 1) for (let c = m.c; c < m.c + m.cs; c += 1) spots.push(r * 1000 + c);
      if (spots.some((k) => taken.has(k))) continue;
      spots.forEach((k) => taken.add(k));
      out.push({ r: m.r, c: m.c, rs: m.rs, cs: m.cs });
    }
    return out;
  }

  function wbTableMerges(d) {
    const cells = wbTableCells(d);
    return wbTableCleanMerges(d.data?.merges, cells.length, cells[0].length);
  }

  //: The merge that holds the cell at (r, c), its origin or a cell under it.
  function wbTableMergeAt(merges, r, c) {
    return merges.find((m) => r >= m.r && r < m.r + m.rs && c >= m.c && c < m.c + m.cs) || null;
  }

  //: A cell hidden under another one's span (not the origin).
  function wbTableCovered(merges, r, c) {
    const m = wbTableMergeAt(merges, r, c);
    return Boolean(m) && (m.r !== r || m.c !== c);
  }

  //: A picked range as {r0, c0, r1, c1}, corners in order.
  function wbTableRect(a, b) {
    return { r0: Math.min(a.r, b.r), c0: Math.min(a.c, b.c), r1: Math.max(a.r, b.r), c1: Math.max(a.c, b.c) };
  }

  //: The range grown until no merge is cut by its edge (a merge half inside joins it whole).
  function wbTableGrowRect(merges, rect) {
    let now = { ...rect };
    for (let again = true; again;) {
      again = false;
      for (const m of merges) {
        const hit = m.r <= now.r1 && m.r + m.rs - 1 >= now.r0 && m.c <= now.c1 && m.c + m.cs - 1 >= now.c0;
        const grown = { r0: Math.min(now.r0, m.r), c0: Math.min(now.c0, m.c), r1: Math.max(now.r1, m.r + m.rs - 1), c1: Math.max(now.c1, m.c + m.cs - 1) };
        if (hit && JSON.stringify(grown) !== JSON.stringify(now)) {
          now = grown;
          again = true;
        }
      }
    }
    return now;
  }

  //: The cells and merges after the range becomes one cell: its words (the
  //: non-empty ones, in reading order) go to the top-left, the rest are emptied.
  //: `null` when the range is one cell.
  function wbTableMergeRect(cells, merges, rect) {
    const now = wbTableGrowRect(merges, rect);
    if (now.r0 === now.r1 && now.c0 === now.c1) return null;
    const words = [];
    const next = cells.map((row, r) => row.map((text, c) => {
      const inside = r >= now.r0 && r <= now.r1 && c >= now.c0 && c <= now.c1;
      if (inside && text.trim()) words.push(text.trim());
      return inside ? "" : text;
    }));
    next[now.r0][now.c0] = words.join(" ").slice(0, 500);
    const kept = merges.filter((m) => !(m.r >= now.r0 && m.r <= now.r1 && m.c >= now.c0 && m.c <= now.c1));
    return { cells: next, merges: [...kept, { r: now.r0, c: now.c0, rs: now.r1 - now.r0 + 1, cs: now.c1 - now.c0 + 1 }], rect: now };
  }

  //: The merges left once every one touching the range is split.
  function wbTableSplitRect(merges, rect) {
    return merges.filter((m) => !(m.r <= rect.r1 && m.r + m.rs - 1 >= rect.r0 && m.c <= rect.c1 && m.c + m.cs - 1 >= rect.c0));
  }

  //: The merges after a row or column goes in or out at `at`: one below moves
  //: down, one the new track lands inside grows, one that loses a track shrinks
  //: and one left covering a single cell is dropped.
  function wbTableReshapeMerges(merges, axis, at, remove) {
    const [start, span] = axis === "row" ? ["r", "rs"] : ["c", "cs"];
    const out = [];
    for (const m of merges) {
      const next = { ...m };
      if (remove) {
        if (at < m[start]) next[start] -= 1;
        else if (at < m[start] + m[span]) next[span] -= 1;
      } else if (at <= m[start]) next[start] += 1;
      else if (at < m[start] + m[span]) next[span] += 1;
      if (next.rs * next.cs > 1) out.push(next);
    }
    return out;
  }

  //: Whether row `r` wears the stripe tint: every other body row, the first body row plain.
  function wbTableStripe(d, r) {
    const first = d.data?.header ? 1 : 0;
    return Boolean(d.data?.stripes) && r >= first && (r - first) % 2 === 1;
  }

  //: Where a grip may sit along the line after track `i` of `axis` ("col" or
  //: "row"): runs of [from, to) over the other axis's tracks, leaving out the
  //: stretches a merged cell crosses (its inside is not a border, and a grip
  //: there would be on top of the cell's own words).
  function wbTableGripRuns(merges, axis, i, along) {
    const col = axis === "col";
    const crossed = (k) => merges.some((m) => (col
      ? m.c <= i && i < m.c + m.cs - 1 && m.r <= k && k < m.r + m.rs
      : m.r <= i && i < m.r + m.rs - 1 && m.c <= k && k < m.c + m.cs));
    const out = [];
    let from = -1;
    for (let k = 0; k <= along; k += 1) {
      const free = k < along && !crossed(k);
      if (free && from < 0) from = k;
      if (!free && from >= 0) {
        out.push([from, k]);
        from = -1;
      }
    }
    return out;
  }

  //: Every drawn cell of a table in the box's own pixels (the covered ones left
  //: out, a merged one spanning its rows and columns): what the SVG and the
  //: draw.io file are drawn from, so both agree with the board.
  function wbTableCellBoxes(d, width, height) {
    const cells = wbTableCells(d);
    const merges = wbTableMerges(d);
    const xs = wbTableColumnEdges(wbTableWeights(d));
    const ys = wbTableColumnEdges(wbTableRowWeights(d));
    const out = [];
    cells.forEach((row, r) => row.forEach((text, c) => {
      if (wbTableCovered(merges, r, c)) return;
      const m = wbTableMergeAt(merges, r, c);
      const c2 = c + (m ? m.cs : 1);
      const r2 = r + (m ? m.rs : 1);
      out.push({
        r, c, text, head: r === 0 && Boolean(d.data?.header), stripe: wbTableStripe(d, r),
        x: xs[c] * width, y: ys[r] * height, w: (xs[c2] - xs[c]) * width, h: (ys[r2] - ys[r]) * height,
      });
    }));
    return out;
  }
  return { wbTableRowWeights, wbTableDragWeights, wbTableAxisWeights, wbTableCleanMerges, wbTableMerges, wbTableMergeAt, wbTableCovered, wbTableRect, wbTableGrowRect, wbTableMergeRect, wbTableSplitRect, wbTableReshapeMerges, wbTableStripe, wbTableGripRuns, wbTableCellBoxes };
})();
//: table-core-end

//: **A text box, a sticky or a table, as the export draws it.** The export
//: drew a text box as its words alone and left a table out of the file, so a
//: yellow sticky came out as dark text on the board's white and a table as
//: nothing (SVG, PNG and PDF all read the one SVG). Paint is read off the
//: drawn element, as a map topic's is, so the theme, the paper and the corners
//: it really wears travel; an item culled off screen falls back to its data.
function wbSvgRoundedPath(w, h, radii) {
  const [a, b, c, d] = radii.map((r) => Math.max(0, Math.min(Number(r) || 0, w / 2, h / 2)));
  return `M${a} 0H${w - b}A${b} ${b} 0 0 1 ${w} ${b}V${h - c}A${c} ${c} 0 0 1 ${w - c} ${h}H${d}A${d} ${d} 0 0 1 0 ${h - d}V${a}A${a} ${a} 0 0 1 ${a} 0Z`;
}

function wbSvgBoxRadii(el, data, w, h) {
  if (!el) return Array.isArray(data?.radii) ? data.radii : [6, 6, 6, 6];
  const style = getComputedStyle(el);
  const px = (v, side) => (/%$/.test(v) ? (parseFloat(v) / 100) * side : parseFloat(v) || 0);
  return ["TopLeft", "TopRight", "BottomRight", "BottomLeft"].map((corner) => px(style[`border${corner}Radius`], Math.min(w, h)));
}

function wbSvgBoxBackdrop(el, data, w, h) {
  const paper = data?.bg && data.bg !== "transparent" ? (wbExportColour(wbPaperPaint(data)) || data.bg) : "none";
  const paint = el ? wbExportPaint(el) : { fill: paper, edge: data?.border_color || null };
  //: A sticky's paper can be a gradient, which has no background colour to read.
  const fill = paint.fill !== "none" ? paint.fill : paper;
  if (fill === "none" && !paint.edge) return "";
  const edge = paint.edge ? ` stroke="${wbSvgEscape(paint.edge)}" stroke-width="1.5"` : "";
  return `<path d="${wbSvgRoundedPath(w, h, wbSvgBoxRadii(el, data, w, h))}" fill="${wbSvgEscape(fill)}"${edge} />`;
}

//: **A sticky's folded corner, as the export draws it.** The board paints
//: it as `::after` (a square in the bottom-right, a hard-stopped gradient:
//: the board's ground on the outer half, the paper a shade darker on the
//: inner), so the file had a square-cornered sheet. The two colours are read
//: off the gradient the browser computed, so the theme and the paper travel;
//: a sticky with the fold turned off draws none.
function wbSvgFoldColours(gradient) {
  const stops = [...String(gradient || "").matchAll(/(rgba?\([^)]*\)|color\([^)]*\))\s+50%/g)].map((m) => m[1]);
  return stops.length === 2 ? stops : null;
}

function wbSvgStickyFold(el, w, h) {
  if (!el?.classList.contains("wb-sticky") || el.classList.contains("wb-no-fold")) return "";
  const fold = getComputedStyle(el, "::after");
  const size = parseFloat(fold.width) || 0;
  const colours = size > 0 && fold.content !== "none" ? wbSvgFoldColours(fold.backgroundImage) : null;
  const [cut, paper] = (colours || []).map((c) => wbSvgEscape(wbExportColour(c) || c));
  if (!colours || size > w || size > h) return "";
  return `<path d="M${w - size} ${h}H${w}V${h - size}Z" fill="${cut}" />` +
    `<path d="M${w - size} ${h - size}V${h}L${w} ${h - size}Z" fill="${paper}" />`;
}

function wbSvgTableCell(paint, text, box, size) {
  const edge = wbSvgEscape(paint.edge || "#9aa3b5");
  const rect = `<rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" fill="${wbSvgEscape(paint.fill)}" stroke="${edge}" stroke-width="1" />`;
  if (!text) return rect;
  const lines = wbSvgWrapLines(text, box.w - 12, Math.max(1, Math.floor(box.h / (size * 1.25))), size * 0.55);
  return rect + wbSvgText(lines, box.x + 6, box.y + size + 4, { fontSize: size, fill: paint.ink, lineHeight: size * 1.25 });
}

function wbSvgTable(el, obj) {
  const plain = { fill: "#ffffff", edge: "#9aa3b5", ink: "#1f2430" };
  const paintOf = (sel, fallback) => {
    const node = el?.querySelector(sel);
    return (node && wbExportPaint(node)) || fallback;
  };
  const body = paintOf(".wb-table-cell:not([data-head]):not([data-stripe])", plain);
  const head = paintOf(".wb-table-cell[data-head]", { ...plain, fill: "#eef1f6" });
  const stripe = paintOf(".wb-table-cell[data-stripe]", { ...plain, fill: "#f4f6fa" });
  const sample = el?.querySelector(".wb-table-cell:not([data-head])");
  const size = parseFloat(sample && getComputedStyle(sample).fontSize) || 14;
  return wbTableRules.wbTableCellBoxes(obj, obj.width, obj.height)
    .map((cell) => wbSvgTableCell(cell.head ? head : cell.stripe ? stripe : body, cell.text, cell, size)).join("");
}

function wbBuildTable(el, d) {
  const selectedHere = () => wbSelectedItem?.kind === "object" && wbSelectedItem.id === d.id && wbMultiSelection.size <= 1;
  el.append("div").attr("class", "wb-table-grid").attr("role", "grid").attr("aria-label", "Table")
    .on("pointerdown", (event) => {
      const cell = event.target.closest(".wb-table-cell");
      const here = wbFmtState.tableCell;
      //: Shift on a second cell picks the range between it and the cell last pressed.
      if (cell && event.shiftKey && selectedHere() && here?.id === d.id) {
        wbFmtState.tableRange = { id: d.id, ...wbTableRules.wbTableRect(here, { r: Number(cell.dataset.r), c: Number(cell.dataset.c) }) };
      } else if (cell) {
        wbFmtState.tableCell = { id: d.id, r: Number(cell.dataset.r), c: Number(cell.dataset.c) };
        wbFmtState.tableRange = null;
      }
      wbTableRules.wbTableShowRange(el.node(), d);
      if (cell?.isContentEditable) event.stopPropagation();
    })
    //: A shift-click that picked a range is not a multi-select toggle of the table.
    .on("click", (event) => {
      if (event.shiftKey && selectedHere() && wbFmtState.tableCell?.id === d.id && event.target.closest(".wb-table-cell")) event.stopPropagation();
    })
    .on("dblclick", (event) => {
      const cell = event.target.closest(".wb-table-cell");
      if (!cell) return;
      event.stopPropagation();
      wbEditTableCell(d.id, Number(cell.dataset.r), Number(cell.dataset.c));
    });
}

//: The cells of the picked range wear `is-picked`; cheap when nothing changed.
wbTableRules.wbTableShowRange = function wbTableShowRange(node, d) {
  const grid = node?.querySelector(".wb-table-grid");
  if (!grid) return;
  const pick = wbFmtState.tableRange?.id === d.id ? wbFmtState.tableRange : null;
  const marker = pick ? JSON.stringify(pick) : "";
  if ((grid.dataset.range || "") === marker) return;
  grid.dataset.range = marker;
  for (const cell of grid.querySelectorAll(".wb-table-cell")) {
    const r = Number(cell.dataset.r);
    const c = Number(cell.dataset.c);
    cell.classList.toggle("is-picked", Boolean(pick) && r >= pick.r0 && r <= pick.r1 && c >= pick.c0 && c <= pick.c1);
  }
};

//: The grid's tracks from the weights, and each grip on the stretch of line it drags.
wbTableRules.wbTableTracks = function wbTableTracks(grid, colWeights, rowWeights) {
  grid.style.gridTemplateColumns = colWeights.map((n) => `minmax(0, ${n}fr)`).join(" ");
  grid.style.gridTemplateRows = rowWeights.map((n) => `minmax(0, ${n}fr)`).join(" ");
  const cols = wbTableColumnEdges(colWeights);
  const rows = wbTableColumnEdges(rowWeights);
  const pct = (n) => `${n * 100}%`;
  for (const grip of grid.querySelectorAll(".wb-table-grip")) {
    const at = Number(grip.dataset.i) + 1;
    const [from, to] = [Number(grip.dataset.from), Number(grip.dataset.to)];
    if (grip.dataset.axis === "col") {
      grip.style.left = pct(cols[at]);
      grip.style.top = pct(rows[from]);
      grip.style.height = pct(rows[to] - rows[from]);
    } else {
      grip.style.top = pct(rows[at]);
      grip.style.left = pct(cols[from]);
      grip.style.width = pct(cols[to] - cols[from]);
    }
  }
};

//: **A line dragged to size a row or column** (`data.col_widths`, `data.row_heights`):
//: the two tracks either side of the line trade width, so the table keeps its size.
//: The grid follows the pointer; the weights are written once, on release, as
//: one Undo step. The menu's Widen, Taller and the like are the keyboard's way.
wbTableRules.wbTableGripDrag = function wbTableGripDrag(event, d, grip) {
  const grid = grip.parentElement;
  if (event.button > 0 || !grid || wbIsLocked("object", d)) return;
  event.preventDefault();
  event.stopPropagation();
  const col = grip.dataset.axis === "col";
  const i = Number(grip.dataset.i);
  const box = grid.getBoundingClientRect();
  const before = col ? wbTableWeights(d) : wbTableRules.wbTableRowWeights(d);
  const unit = (col ? box.width : box.height) / before.length;
  const from = col ? event.clientX : event.clientY;
  let next = null;
  grip.setPointerCapture?.(event.pointerId);
  grip.classList.add("is-dragging");
  const show = (weights) => wbTableRules.wbTableTracks(grid, col ? weights : wbTableWeights(d), col ? wbTableRules.wbTableRowWeights(d) : weights);
  const move = (e) => {
    next = unit > 0 ? wbTableRules.wbTableDragWeights(before, i, ((col ? e.clientX : e.clientY) - from) / unit) : null;
    show(next || before);
  };
  const end = async (e) => {
    grip.removeEventListener("pointermove", move);
    grip.removeEventListener("pointerup", end);
    grip.removeEventListener("pointercancel", end);
    grip.classList.remove("is-dragging");
    if (!next || e.type === "pointercancel") return show(before);
    await wbSetTable(d, wbTableCells(d), null, col ? "Column resized." : "Row resized.", { [col ? "col_widths" : "row_heights"]: next });
  };
  grip.addEventListener("pointermove", move);
  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
};

//: Rebuilt only when the cells, the header, the stripes, the merges or the
//: tracks change, and never under a cell being typed in.
function wbPaintTable(node, d) {
  const grid = node.querySelector(".wb-table-grid");
  if (!grid || grid.querySelector("[contenteditable='true']")) return;
  const cells = wbTableCells(d);
  const weights = wbTableWeights(d);
  const heights = wbTableRules.wbTableRowWeights(d);
  const merges = wbTableRules.wbTableMerges(d);
  const key = JSON.stringify([cells, Boolean(d.data?.header), Boolean(d.data?.stripes), weights, heights, merges]);
  if (grid.dataset.key === key) return wbTableRules.wbTableShowRange(node, d);
  grid.dataset.key = key;
  grid.dataset.range = "";
  grid.classList.toggle("has-header", Boolean(d.data?.header));
  const out = [];
  cells.forEach((row, r) => row.forEach((text, c) => {
    if (wbTableRules.wbTableCovered(merges, r, c)) return;
    const m = wbTableRules.wbTableMergeAt(merges, r, c);
    const cell = document.createElement("div");
    cell.className = "wb-table-cell";
    cell.setAttribute("role", r === 0 && d.data?.header ? "columnheader" : "gridcell");
    cell.dataset.r = String(r);
    cell.dataset.c = String(c);
    if (r === 0 && d.data?.header) cell.dataset.head = "1";
    else if (wbTableRules.wbTableStripe(d, r)) cell.dataset.stripe = "1";
    cell.style.gridRow = `${r + 1} / span ${m ? m.rs : 1}`;
    cell.style.gridColumn = `${c + 1} / span ${m ? m.cs : 1}`;
    if (m) {
      cell.dataset.rs = String(m.rs);
      cell.dataset.cs = String(m.cs);
    }
    cell.textContent = text;
    out.push(cell);
  }));
  const grip = (axis, i, from, to) => {
    const g = document.createElement("div");
    g.className = `wb-table-grip wb-table-grip-${axis}`;
    Object.assign(g.dataset, { axis, i: String(i), from: String(from), to: String(to) });
    g.title = axis === "col" ? "Drag to size the columns either side" : "Drag to size the rows either side";
    //: The object's own drag listens for mouse and touch as well as pointer events.
    for (const type of ["mousedown", "touchstart"]) g.addEventListener(type, (event) => event.stopPropagation(), { passive: true });
    g.addEventListener("pointerdown", (event) => wbTableRules.wbTableGripDrag(event, d, g));
    return g;
  };
  for (let c = 0; c < weights.length - 1; c += 1) for (const [from, to] of wbTableRules.wbTableGripRuns(merges, "col", c, heights.length)) out.push(grip("col", c, from, to));
  for (let r = 0; r < heights.length - 1; r += 1) for (const [from, to] of wbTableRules.wbTableGripRuns(merges, "row", r, weights.length)) out.push(grip("row", r, from, to));
  grid.replaceChildren(...out);
  wbTableRules.wbTableTracks(grid, weights, heights);
  wbTableRules.wbTableShowRange(node, d);
}

async function wbInsertTable(rows = 3, cols = 3) {
  const [cx, cy] = wbViewCentre();
  const w = cols * WB_TABLE_COL_W;
  const h = rows * WB_TABLE_ROW_H;
  const cells = Array.from({ length: rows }, () => Array.from({ length: cols }, () => ""));
  const made = await wbCreateObject("table", { cells, header: true }, cx - w / 2, cy - h / 2, w, h);
  if (!made) return null;
  clearWbSelection();
  wbHandleItemClick("object", made.id, { shiftKey: false });
  wbAnnounce(`Table added, ${rows} rows by ${cols} columns. Double-click a cell to type in it.`);
  return made;
}

//: Writes new cells (and a new size) as one Undo step. `patch` is the table's
//: other data keys (`col_widths`, `row_heights`, `merges`, `stripes`): a value
//: of `null` (or an empty list) clears the key, `undefined` leaves it.
async function wbSetTable(d, cells, size = null, said = "", patch = {}) {
  if (!d || wbIsLocked("object", d)) return;
  wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
  d.data = { ...d.data, cells };
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) continue;
    if (value === null || value === false || (Array.isArray(value) && !value.length)) delete d.data[key];
    else d.data[key] = value;
  }
  if (size) Object.assign(d, size);
  await wbSaveObject(d);
  wbScheduleRender();
  if (said) wbAnnounce(said);
}

function wbEditTableCell(id, r, c) {
  const d = (wbState.objects || []).find((o) => o.id === id);
  const node = document.querySelector(`.wb-object[data-id="${id}"]`);
  const cell = node?.querySelector(`.wb-table-cell[data-r="${r}"][data-c="${c}"]`);
  if (!d || !cell || wbIsLocked("object", d)) return;
  wbFmtState.tableCell = { id, r, c };
  const before = cell.textContent;
  cell.contentEditable = "true";
  cell.focus();
  document.getSelection()?.selectAllChildren(cell);
  let moveTo = null;
  //: The next cell takes the keyboard before this one is saved, so typing
  //: straight on after Tab loses nothing; a cell being typed in is never
  //: redrawn under it (`wbPaintTable`).
  const done = (keep) => {
    cell.removeEventListener("keydown", onKey);
    cell.removeEventListener("blur", onBlur);
    cell.contentEditable = "false";
    const text = cell.innerText.replace(/\n+$/, "").slice(0, 500);
    if (!keep) cell.textContent = before;
    if (moveTo) wbEditTableCell(id, moveTo[0], moveTo[1]);
    if (keep && text !== before) {
      const cells = wbTableCells(d);
      cells[r][c] = text;
      wbSetTable(d, cells);
    }
  };
  const onBlur = () => done(true);
  const onKey = (event) => {
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      cell.removeEventListener("blur", onBlur);
      done(false);
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      cell.blur();
    } else if (event.key === "Tab") {
      event.preventDefault();
      const cells = wbTableCells(d);
      const cols = cells[0].length;
      const merges = wbTableRules.wbTableMerges(d);
      //: A cell under a merged one has no box to type in, so Tab steps over it.
      let at = r * cols + c;
      do at += event.shiftKey ? -1 : 1;
      while (at >= 0 && at < cells.length * cols && wbTableRules.wbTableCovered(merges, Math.floor(at / cols), at % cols));
      if (at >= 0 && at < cells.length * cols) moveTo = [Math.floor(at / cols), at % cols];
      cell.blur();
    }
  };
  cell.addEventListener("keydown", onKey);
  cell.addEventListener("blur", onBlur);
}

//: Insert or remove a row or column at `at` (`axis` "row" or "col"); the
//: table grows or shrinks by one row's or column's share, so the others keep
//: their size. Merged cells and a set row height or column width follow.
function wbTableReshape(d, axis, at, remove) {
  const cells = wbTableCells(d);
  const rows = cells.length;
  const cols = cells[0].length;
  if (remove && (axis === "row" ? rows : cols) <= 1) {
    toast(`A table keeps at least one ${axis === "row" ? "row" : "column"}; delete the table instead.`, "info");
    return;
  }
  if (!remove && (axis === "row" ? rows >= 50 : cols >= 20)) {
    toast(axis === "row" ? "A table holds up to 50 rows." : "A table holds up to 20 columns.", "info");
    return;
  }
  let next;
  if (axis === "row") {
    next = remove ? cells.filter((_, i) => i !== at) : [...cells.slice(0, at), Array(cols).fill(""), ...cells.slice(at)];
  } else {
    next = cells.map((row) => (remove ? row.filter((_, i) => i !== at) : [...row.slice(0, at), "", ...row.slice(at)]));
  }
  //: A track takes the size it has (a removed one gives up its own), a new one
  //: an average share; the weights go back to a mean of 1 so the others keep
  //: their pixels.
  const row = axis === "row";
  const weights = row ? wbTableRules.wbTableRowWeights(d) : wbTableWeights(d);
  const total = weights.reduce((a, n) => a + n, 0);
  const extent = row ? d.height : d.width;
  const share = remove ? (extent * weights[at]) / total : extent / weights.length;
  const grown = Math.max(row ? WB_TABLE_ROW_H / 2 : WB_TABLE_COL_W / 2, extent + (remove ? -share : share));
  const size = row ? { height: grown } : { width: grown };
  const kept = Array.isArray(d.data?.[row ? "row_heights" : "col_widths"]);
  const patch = {
    merges: wbTableRules.wbTableReshapeMerges(wbTableRules.wbTableMerges(d), axis, at, remove),
    [row ? "row_heights" : "col_widths"]: kept ? wbTableRules.wbTableAxisWeights(weights, at, remove) : undefined,
  };
  const word = row ? "Row" : "Column";
  const said = `${word} ${remove ? "removed" : "added"}.`;
  //: A connector joined to a row stays on that row (whiteboard-shape-more.js), in the same Undo step.
  const carry = row ? wbFmtState.shapeMore?.carryRowPorts(d, at, remove, rows) : null;
  if (!carry) return wbSetTable(d, next, size, said, patch);
  return wbRecordGesture(async () => {
    await wbSetTable(d, next, size, said, patch);
    await carry();
  });
}

//: The size rows of the item menu: a quarter wider or taller, or a fifth
//: narrower or shorter, at the cell last pressed (the others give way, the
//: table keeps its size), and back to equal once any has been set.
wbTableRules.wbTableSizeRows = function wbTableSizeRows(d, cells, r, c, at) {
  const sizes = [
    ["column", "col_widths", c, wbTableWeights, ["Widen this column", "Narrow this column", "Equal column widths"]],
    ["row", "row_heights", r, wbTableRules.wbTableRowWeights, ["Taller row", "Shorter row", "Equal row heights"]],
  ];
  return sizes.flatMap(([word, key, index, weightsOf, [more, less, equal]]) => {
    const here = at ? `The ${word} of the cell you pressed` : `The last ${word}; press a cell first to pick another`;
    const set = (factor, said) => () => {
      const next = wbTableResizeColumn(weightsOf(d), index, factor);
      if (next) wbSetTable(d, wbTableCells(d), null, said, { [key]: next });
    };
    const rows = [
      [more, `${here}, a quarter bigger`, set(1.25, `${word[0].toUpperCase()}${word.slice(1)} enlarged.`)],
      [less, `${here}, a fifth smaller`, set(0.8, `${word[0].toUpperCase()}${word.slice(1)} reduced.`)],
    ];
    if (Array.isArray(d.data?.[key])) rows.push([equal, `Every ${word} the same share again`, () => wbSetTable(d, cells, null, `${word[0].toUpperCase()}${word.slice(1)}s equal.`, { [key]: null })]);
    return rows;
  });
};

//: The merge rows of the item menu. With a range picked (Shift and click a
//: second cell) it merges that range; with none, the pressed cell joins the one
//: to its right or below, which is also the way without a shift key. Split
//: undoes every merge the pressed cell or the range touches.
wbTableRules.wbTableMergeRows = function wbTableMergeRows(d, cells, r, c, at) {
  const merges = wbTableRules.wbTableMerges(d);
  const pick = wbFmtState.tableRange?.id === d.id ? wbFmtState.tableRange : null;
  const range = pick && (pick.r1 > pick.r0 || pick.c1 > pick.c0) ? pick : null;
  const merge = (rect, said) => {
    const out = wbTableRules.wbTableMergeRect(cells, merges, rect);
    if (!out) return;
    wbFmtState.tableRange = null;
    wbFmtState.tableCell = { id: d.id, r: out.rect.r0, c: out.rect.c0 };
    return wbSetTable(d, out.cells, null, said, { merges: out.merges });
  };
  const rows = [];
  const here = wbTableRules.wbTableMergeAt(merges, r, c);
  const [r1, c1] = here ? [here.r + here.rs - 1, here.c + here.cs - 1] : [r, c];
  const top = here ? here.r : r;
  const left = here ? here.c : c;
  if (range) rows.push(["Merge cells", "The cells you picked become one; the words are joined", () => merge(range, "Cells merged.")]);
  else if (at) {
    if (c1 + 1 < cells[0].length) rows.push(["Merge with the cell on the right", "This cell and the next one become one", () => merge({ r0: top, c0: left, r1, c1: c1 + 1 }, "Cells merged.")]);
    if (r1 + 1 < cells.length) rows.push(["Merge with the cell below", "This cell and the next one down become one", () => merge({ r0: top, c0: left, r1: r1 + 1, c1 }, "Cells merged.")]);
  }
  const rect = range || { r0: r, c0: c, r1: r, c1: c };
  const split = wbTableRules.wbTableSplitRect(merges, rect);
  if (split.length !== merges.length) {
    rows.push(["Split cell", range ? "Every merged cell in the range goes back to single cells" : "The merged cell goes back to single cells", () => {
      wbFmtState.tableRange = null;
      return wbSetTable(d, cells, null, "Cells split.", { merges: split });
    }]);
  }
  return rows;
};

//: The table's rows for the item menu: around the cell last pressed when it
//: is this table's, else at the ends.
function wbTableMenuRows(d) {
  const cells = wbTableCells(d);
  const at = wbFmtState.tableCell?.id === d.id ? wbFmtState.tableCell : null;
  const r = at ? Math.min(at.r, cells.length - 1) : cells.length - 1;
  const c = at ? Math.min(at.c, cells[0].length - 1) : cells[0].length - 1;
  const here = at ? "this cell's" : "the last";
  //: Past a merged cell's far edge, so a row or column lands beside it, not inside it.
  const span = wbTableRules.wbTableMergeAt(wbTableRules.wbTableMerges(d), r, c);
  const below = r + (span ? span.rs : 1);
  const right = c + (span ? span.cs : 1);
  const toggle = (key, said) => async () => {
    wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
    d.data = { ...d.data, [key]: !d.data?.[key] || undefined };
    if (!d.data[key]) delete d.data[key];
    await wbSaveObject(d);
    wbScheduleRender();
    wbAnnounce(said(Boolean(d.data[key])));
  };
  return [
    ["Add a row below", `Under ${here} row`, () => wbTableReshape(d, "row", below, false)],
    ["Add a row above", `Over ${here} row`, () => wbTableReshape(d, "row", r, false)],
    ["Add a column to the right", `Beside ${here} column`, () => wbTableReshape(d, "col", right, false)],
    ["Add a column to the left", `Before ${here} column`, () => wbTableReshape(d, "col", c, false)],
    [at ? "Delete this row" : "Delete the last row", at ? "The row of the cell you pressed" : "Press a cell first to pick another", () => wbTableReshape(d, "row", r, true)],
    [at ? "Delete this column" : "Delete the last column", at ? "The column of the cell you pressed" : "Press a cell first to pick another", () => wbTableReshape(d, "col", c, true)],
    ...wbTableRules.wbTableMergeRows(d, cells, r, c, at),
    ...wbTableRules.wbTableSizeRows(d, cells, r, c, at),
    [d.data?.header ? "Plain first row" : "First row as a header", "Bold on a tint, or like the rest", toggle("header", (on) => (on ? "First row is a header." : "First row is plain."))],
    [d.data?.stripes ? "Plain rows" : "Striped rows", "Every other row on a tint, or all alike", toggle("stripes", (on) => (on ? "Rows striped." : "Rows plain."))],
  ];
}

//: --- The colour well (the owner, 2026-10-11) ------------------------------
//:
//: "it is difficult to change the border and fill colour to the same colour
//: or a different one. can there be like a recent colours set in the colour
//: picker popups?" Every board colour field (`.wb-color-picker`: a shape's
//: fill and border, a line's ink, a text box's, the drawing colour on the
//: rail) opens this popover instead of the browser's dialog: what it is
//: setting at the top; for a fill and its border, the two side by side with
//: Same as and Swap; the last eight colours picked on this device; the board
//: colours; a hex box and R, G, B boxes; an Opacity row; and take a colour
//: from the board or the screen. The browser's dialog is not used. A pick is written by the field's own `change` handler,
//: so it is the one Undo step it always was.
const WB_RECENT_COLOURS_KEY = "wb-recent-colours";
const WB_RECENT_COLOURS_MAX = 8;
//: The twelve category hues (each reads on both themes) with ink, two greys
//: and white, as two rows of eight.
const WB_COLOUR_SWATCHES = {
  ink: "#1f2430", grey: "#8a8f98", silver: "#d0d4dc", white: "#ffffff",
  red: "#da5252", orange: "#ba6d36", amber: "#9e7c17", lime: "#6d8a14",
  green: "#15952b", teal: "#159172", cyan: "#178ca3", blue: "#387fe3",
  indigo: "#6a74ea", violet: "#9b63e9", magenta: "#d332e2", pink: "#ce5591",
};
//: A fill and the border it sits in: wherever one is edited, the other is
//: one press away. `on` is the field saying the fill is on at all.
const WB_COLOUR_PAIRS = [
  { fill: "wb-prop-shapefill", border: "wb-prop-color", on: "wb-prop-shapefill-on", selection: true, shape: true },
  { fill: "wb-fmt-fill", border: "wb-fmt-stroke", on: "wb-fmt-fill-on", selection: true },
  { fill: "wb-prop-bg", border: "wb-prop-border", selection: true },
  { fill: "wb-fill-color", border: "wb-rail-ink", on: "wb-fill-on" },
];
const wbColourState = { menu: null, input: null, eyedrop: false, swallowClick: false, takeBorder: false };

function wbRecentColours() {
  try {
    const list = prefs.json(WB_RECENT_COLOURS_KEY, []);
    return Array.isArray(list) ? list.filter((c) => /^#[0-9a-f]{6}$/.test(c)).slice(0, WB_RECENT_COLOURS_MAX) : [];
  } catch {
    return [];
  }
}

function wbRememberColour(colour) {
  const hex = wbHexOf(colour);
  if (!hex) return;
  const list = [hex, ...wbRecentColours().filter((c) => c !== hex)].slice(0, WB_RECENT_COLOURS_MAX);
  try {
    prefs.set(WB_RECENT_COLOURS_KEY, JSON.stringify(list));
  } catch {
    /* a private window: the row starts empty next time */
  }
}

//: Any CSS colour as `#rrggbb`, or null: the canvas reads it the way the
//: browser paints it, names and `rgb()` included.
function wbHexOf(colour) {
  const text = String(colour || "").trim().toLowerCase();
  if (/^#[0-9a-f]{6}$/.test(text)) return text;
  if (/^#[0-9a-f]{3}$/.test(text)) return `#${[...text.slice(1)].map((c) => c + c).join("")}`;
  if (!text || text === "transparent" || text === "none") return null;
  const m = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+%?))?\s*\)$/.exec(text);
  if (m) {
    if (m[4] !== undefined && parseFloat(m[4]) === 0) return null;
    return `#${[m[1], m[2], m[3]].map((n) => Number(n).toString(16).padStart(2, "0")).join("")}`;
  }
  const ctx = (wbHexOf.ctx ||= document.createElement("canvas").getContext("2d"));
  ctx.fillStyle = "#000001";
  ctx.fillStyle = text;
  return ctx.fillStyle === "#000001" ? null : wbHexOf(ctx.fillStyle);
}

//: What a field sets, in words, read off the selection where the field is
//: shared (the bar's ink is a border on a shape and a line's colour on a line).
function wbColourName(input) {
  if (input.id === "wb-prop-color" || input.id === "wb-fmt-stroke") {
    const kinds = new Set(wbFmtEntries().map(wbFmtKind));
    if (input.id === "wb-prop-color" && kinds.has("text")) return "Text colour";
    return kinds.size && [...kinds].every((k) => k === "shape" || k === "text") ? "Border colour" : "Line colour";
  }
  return { "wb-prop-shapefill": "Fill colour", "wb-fmt-fill": "Fill colour", "wb-prop-bg": "Fill colour", "wb-prop-border": "Border colour",
    "wb-fill-color": "Fill for new shapes", "wb-rail-ink": "Drawing colour", "wb-fmt-ink": "Text colour" }[input.id]
    || input.getAttribute("aria-label") || "Colour";
}

function wbColourPairOf(input) {
  const pair = WB_COLOUR_PAIRS.find((p) => p.fill === input.id || p.border === input.id);
  if (!pair) return null;
  //: The bar's ink is a border only when a shape is what is selected.
  if (pair.shape && wbFmtEntries().some((e) => wbFmtKind(e) !== "shape")) return null;
  if (pair.selection && !wbFmtEntries().length) return null;
  const fill = document.getElementById(pair.fill), border = document.getElementById(pair.border);
  return fill && border ? { ...pair, fillEl: fill, borderEl: border } : null;
}

//: `aria-expanded` belongs to a button; a colour field (`input[type=color]`) is not
//: allowed it or `aria-haspopup` (axe aria-allowed-attr, BD4), so only a button gets it.
function wbWellExpanded(el, open) {
  if (el.type !== "color") el.setAttribute("aria-expanded", String(open));
}

//: Writes a colour into a field as a pick would: its own handlers save it.
function wbSetColourField(input, colour) {
  const hex = wbHexOf(colour);
  if (!hex || !input) return;
  input.value = hex;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

//: **Fill and border together, as one Undo step** (Same as, Swap): on the
//: selection the pair belongs to, every shape and text box in it at once,
//: each from its own colours (two shapes made "same as fill" keep their two
//: fills). `how` is "border-from-fill", "fill-from-border" or "swap"; an
//: item with no fill has nothing to give its border, so those two pass it.
async function wbWriteColourPair(pair, how) {
  const pick = (fill, border) => ({
    "border-from-fill": { border: fill },
    "fill-from-border": { fill: border },
    swap: { fill: border, border: fill },
  })[how];
  if (!pair.selection) {
    const { fill, border } = pick(pair.fillEl.value, pair.borderEl.value);
    if (fill) wbSetColourField(pair.fillEl, fill);
    if (border) wbSetColourField(pair.borderEl, border);
    return;
  }
  const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
  const used = new Set();
  await wbRecordGesture(async () => {
    const saves = [];
    for (const entry of entries) {
      const kind = wbFmtKind(entry);
      if (kind !== "shape" && kind !== "text") continue;
      if (how !== "fill-from-border" && !wbFmtValue(entry, "fill-on")) continue;
      const { fill, border } = pick(wbFmtValue(entry, "fill"), wbFmtValue(entry, "stroke"));
      for (const colour of [fill, border]) if (colour) used.add(colour);
      if (entry.kind === "sketch") {
        if (wbSketchSetProps(entry.item, { ...(fill ? { fill, fillOpacity: 1 } : {}), ...(border ? { color: border } : {}) })) saves.push({ kind: "sketch", item: entry.item });
      } else {
        entry.item.data = { ...entry.item.data, ...(fill ? { bg: fill } : {}), ...(border ? { border_color: border } : {}) };
        saves.push({ kind: "object", item: entry.item });
      }
    }
    await wbSaveMany(saves);
  });
  for (const colour of used) wbRememberColour(colour);
  wbScheduleRender();
  wbUpdateContextBar();
  wbFormatSyncSoon();
}

function wbColourMenu() {
  if (wbColourState.menu) return wbColourState.menu;
  const menu = document.createElement("div");
  menu.className = "action-menu wb-colour-menu hidden";
  menu.id = "wb-colour-menu";
  menu.setAttribute("role", "dialog");
  menu.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    if (wbColourState.eyedrop) wbStopEyedrop();
    else closeActionMenus();
  });
  //: Closed by anything (a pick, outside, Escape, another menu): the
  //: eyedropper goes with it.
  new MutationObserver(() => {
    if (menu.classList.contains("hidden")) {
      wbStopEyedrop();
      for (const el of document.querySelectorAll(".wb-colour-target")) {
        el.classList.remove("wb-colour-target");
        wbWellExpanded(el, false);
      }
    }
  }).observe(menu, { attributes: true, attributeFilter: ["class"] });
  document.body.appendChild(menu);
  wbColourState.menu = menu;
  return menu;
}

function wbColourButton(icon, words, title, run) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost small";
  button.title = title;
  const glyph = document.createElement("i");
  glyph.className = `ph ph-${icon} ph-lead`;
  glyph.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = words;
  button.append(glyph, label);
  button.addEventListener("click", run);
  return button;
}

function wbColourHeading(words) {
  const head = document.createElement("p");
  head.className = "wb-colour-section";
  head.textContent = words;
  return head;
}

//: **The colour kit** (INBOX 1685): what the colour popover and the Filled
//: switch share, behind one name so the shared scope grows by one rather than
//: nine. `parse` reads a pasted colour, `fillIsOn`, `fillToggle` and
//: `fillColour` are the one rule for a fill (bar and Format panel alike),
//: `setAlpha` the one opacity setter, `opacity` and `fields` the popover's rows.
const wbColour = (() => {
  //: What a person may paste into the popover's colour field, as `{hex, alpha}`
  //: (alpha null when the text carries none) or null: #rgb, #rgba, #rrggbb,
  //: #rrggbbaa (the # optional), rgb()/rgba() and hsl()/hsla() in the comma or
  //: the space form, three bare numbers, and any name the browser knows.
  function wbColourParse(text) {
    const t = String(text || "").trim().toLowerCase();
    if (!t) return null;
    const two = (n) => Math.round(n * 100) / 100;
    const byte = (n) => Math.max(0, Math.min(255, Math.round(n)));
    const hexOf = (r, g, b) => `#${[r, g, b].map((n) => byte(n).toString(16).padStart(2, "0")).join("")}`;
    const hexForm = /^#?([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/.exec(t);
    if (hexForm) {
      const h = hexForm[1].length <= 4 ? [...hexForm[1]].map((c) => c + c).join("") : hexForm[1];
      return { hex: `#${h.slice(0, 6)}`, alpha: h.length === 8 ? two(parseInt(h.slice(6), 16) / 255) : null };
    }
    const call = /^(rgba?|hsla?)\(\s*([^)]*?)\s*\)$/.exec(t);
    const bare = /^\d+(?:\.\d+)?[\s,]+\d+(?:\.\d+)?[\s,]+\d+(?:\.\d+)?$/.test(t);
    if (call || bare) {
      const parts = (call ? call[2] : t).split(/[\s,/]+/).filter(Boolean);
      const num = (p, scale) => (p.endsWith("%") ? (parseFloat(p) / 100) * scale : parseFloat(p));
      if (parts.length < 3 || parts.length > 4 || parts.slice(0, 3).some((p) => !Number.isFinite(parseFloat(p)))) return null;
      let alpha = null;
      if (parts[3] !== undefined) {
        alpha = num(parts[3], 1);
        if (!Number.isFinite(alpha)) return null;
        alpha = two(Math.max(0, Math.min(1, alpha)));
      }
      if (call && call[1].startsWith("hsl")) {
        const h = (((parseFloat(parts[0]) % 360) + 360) % 360) / 60;
        const s = Math.max(0, Math.min(1, num(parts[1], 1)));
        const l = Math.max(0, Math.min(1, num(parts[2], 1)));
        const c = (1 - Math.abs(2 * l - 1)) * s;
        const x = c * (1 - Math.abs((h % 2) - 1));
        const [r, g, b] = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][Math.min(5, Math.floor(h))];
        const m = l - c / 2;
        return { hex: hexOf((r + m) * 255, (g + m) * 255, (b + m) * 255), alpha };
      }
      return { hex: hexOf(num(parts[0], 255), num(parts[1], 255), num(parts[2], 255)), alpha };
    }
    const named = wbHexOf(t);
    return named ? { hex: named, alpha: null } : null;
  }

  //: **Is the fill showing, and what flips it** (INBOX 1685: "I unticked filled
  //: and it switched to blue"). Filled off used to delete the colour, so the
  //: swatch fell back to the default and Filled on took that. Now off only makes
  //: the fill see-through (opacity 0, the colour kept) and on brings the same
  //: colour back, for a drawn shape (`fill`/`fillOpacity`), a text box
  //: (`bg`/`bg_alpha`) and a diagram (its accent, `bg_alpha`) alike.
  function wbFillIsOn(kind, data) {
    const d = data || {};
    if (kind === "sketch") return Boolean(d.fill) && d.fillOpacity !== 0;
    if (kind === "diagram") return d.bg_alpha !== 0;
    return Boolean(d.bg) && d.bg !== "transparent" && d.bg_alpha !== 0;
  }

  function wbFillTogglePatch(kind, data, on, fallback) {
    const d = data || {};
    if (kind === "diagram") return { bg_alpha: on ? undefined : 0 };
    const hasColour = kind === "sketch" ? Boolean(d.fill) : Boolean(d.bg) && d.bg !== "transparent";
    if (!on) return hasColour ? (kind === "sketch" ? { fillOpacity: 0 } : { bg_alpha: 0 }) : {};
    if (kind === "sketch") return { fill: d.fill || fallback, fillOpacity: d.fillOpacity > 0 ? d.fillOpacity : 1 };
    return { bg: hasColour ? d.bg : fallback, bg_alpha: d.bg_alpha > 0 ? d.bg_alpha : undefined };
  }

  //: A new fill colour keeps the opacity the fill already had (a 50% fill stays
  //: 50% when its colour changes) and only brings a hidden fill (opacity 0) back.
  function wbFillColourPatch(kind, data, colour) {
    const d = data || {};
    if (kind === "sketch") return { fill: colour, fillOpacity: d.fillOpacity > 0 ? d.fillOpacity : 1 };
    if (kind === "diagram") return { bg: colour };
    return { bg: colour, bg_alpha: d.bg_alpha > 0 ? d.bg_alpha : undefined };
  }

  //: **One setter for the three opacities** a colour can have: the fill's, the
  //: line's and the text's. The Format panel's sliders and the colour popover's
  //: Opacity row both call it, so the two cannot disagree. A fill's opacity on a
  //: shape with no fill yet fills it first; 0 is a real answer.
  function wbFmtSetAlpha(field, pct) {
    if (field === "inkalpha") {
      const v = Math.max(10, pct);
      return wbFmtApply("text", (entry, kind) => (kind === "shape" ? { label_alpha: v >= 100 ? undefined : v / 100 } : { text_alpha: v >= 100 ? undefined : v / 100 }), `Text opacity ${v}%.`);
    }
    if (field === "fillalpha") return wbFmtApply("fillalpha", (entry) => ({ ...wbFmtFillFirst(entry), [wbFmtAlphaKeys(entry).fill]: pct / 100 }), `Fill ${pct}% solid.`);
    return wbFmtApply("strokealpha", (entry) => {
      const key = wbFmtAlphaKeys(entry).line;
      return { [key]: key === "opacity" && pct >= 100 ? undefined : pct / 100 };
    }, `Line ${pct}% solid.`);
  }

  //: **Which opacity a colour field owns** (INBOX 1685: "I cant find where to
  //: change the transparency in the colours"). A fill colour has the fill's, a
  //: line or border colour the line's, a text colour the text's, the tool's fill
  //: the new shapes'. A field with none (the pen's ink, a gradient's end) shows
  //: no Opacity row rather than a dead one.
  const WB_COLOUR_ALPHA = {
    "wb-fmt-fill": "fillalpha", "wb-prop-shapefill": "fillalpha", "wb-prop-bg": "fillalpha",
    "wb-fmt-stroke": "strokealpha", "wb-prop-color": "strokealpha", "wb-prop-border": "strokealpha",
    "wb-fmt-ink": "inkalpha", "wb-fill-color": "toolfill",
  };

  function wbColourAlphaOf(input) {
    let field = WB_COLOUR_ALPHA[input.id];
    if (field === "strokealpha" && input.id === "wb-prop-color" && wbColourName(input) === "Text colour") field = "inkalpha";
    if (field === "toolfill") return document.getElementById("wb-fill-opacity") ? { field, value: () => Number(window.currentFillOpacity ?? 100) } : null;
    if (!field) return null;
    const takes = field === "inkalpha" ? "text" : field;
    const [first] = wbFmtEntries().filter((e) => (WB_FMT_FIELDS[wbFmtKind(e)] || []).includes(takes));
    return first ? { field, value: () => wbFmtValue(first, field) } : null;
  }

  //: The Opacity row: a slider and a number box that move together, named where
  //: the colour is set. Dragging previews in the number; letting go saves, as
  //: the Format panel's sliders do.
  function wbColourOpacity(input) {
    const own = wbColourAlphaOf(input);
    if (!own) return null;
    const row = document.createElement("div");
    row.className = "wb-colour-opacity";
    const label = document.createElement("span");
    label.className = "wb-colour-label";
    label.textContent = "Opacity";
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.step = "5";
    slider.setAttribute("aria-label", "Opacity");
    const box = document.createElement("input");
    box.type = "number";
    box.min = "0";
    box.max = "100";
    box.step = "1";
    box.setAttribute("aria-label", "Opacity percent");
    const unit = document.createElement("span");
    unit.className = "wb-colour-label";
    unit.textContent = "%";
    const show = (pct) => {
      slider.value = String(pct);
      box.value = String(pct);
    };
    const save = (raw) => {
      //: A cleared box is "no answer", not 0%: put the shown value back.
      if (String(raw).trim() === "") return show(slider.value);
      const pct = Math.max(own.field === "inkalpha" ? 10 : 0, Math.min(100, Math.round(Number(raw))));
      if (!Number.isFinite(pct)) return show(slider.value);
      show(pct);
      if (own.field === "toolfill") {
        const tool = document.getElementById("wb-fill-opacity");
        tool.value = String(pct);
        tool.dispatchEvent(new Event("input", { bubbles: true }));
      } else {
        wbFmtSetAlpha(own.field, pct);
      }
    };
    slider.addEventListener("input", () => {
      box.value = slider.value;
    });
    slider.addEventListener("change", () => save(slider.value));
    box.addEventListener("change", () => save(box.value));
    show(Math.max(0, Math.min(100, Math.round(own.value() ?? 100))));
    row.append(label, slider, box, unit);
    row.setValue = save;
    return row;
  }

  //: **Type or paste a colour** (INBOX 1685: "easier to enter custom rgb or hex
  //: codes"): a hex box that takes anything `wbColourParse` does, and R, G, B
  //: boxes. A change sets the field as a pick does and keeps the popover open,
  //: so the next number can follow; `onAlpha` is called when the paste carried
  //: an opacity (#rrggbbaa, rgba(), hsla()). Bad text is said, never ignored.
  function wbColourFields(input, onAlpha) {
    const wrap = document.createElement("div");
    wrap.className = "wb-colour-fields";
    const chip = document.createElement("span");
    chip.className = "wb-colour-chip";
    chip.setAttribute("aria-hidden", "true");
    const box = (word, full, extra) => {
      const label = document.createElement("label");
      label.className = `wb-colour-field ${extra}`;
      const text = document.createElement("span");
      text.className = "wb-colour-label";
      text.textContent = word;
      const field = document.createElement("input");
      field.setAttribute("aria-label", full);
      label.append(text, field);
      return { label, field };
    };
    const hex = box("Hex", "Hex", "wb-colour-hex");
    hex.field.type = "text";
    hex.field.placeholder = "#3355ff";
    hex.field.spellcheck = false;
    hex.field.autocomplete = "off";
    hex.field.title = "Paste #rgb, #rrggbb, #rrggbbaa, rgb() or hsl()";
    const channels = [box("R", "Red", "wb-colour-num"), box("G", "Green", "wb-colour-num"), box("B", "Blue", "wb-colour-num")];
    for (const channel of channels) {
      Object.assign(channel.field, { type: "number", min: "0", max: "255", step: "1" });
    }
    const hint = document.createElement("p");
    hint.className = "muted empty-line wb-colour-hint hidden";
    hint.setAttribute("role", "status");
    hint.textContent = "Not a colour. Try #3355ff, rgb(51 85 255) or hsl(228 100% 60%).";
    const paint = (colour) => {
      chip.style.setProperty("--swatch", colour);
      hex.field.value = colour;
      colour.slice(1).match(/../g).forEach((pair, i) => {
        channels[i].field.value = String(parseInt(pair, 16));
      });
      hex.field.removeAttribute("aria-invalid");
      hint.classList.add("hidden");
    };
    wrap.commit = (colour, alpha) => {
      const ok = wbHexOf(colour);
      if (!ok) return;
      wbSetColourField(input, ok);
      paint(ok);
      if (alpha != null) onAlpha?.(alpha);
    };
    hex.field.addEventListener("change", () => {
      const parsed = wbColourParse(hex.field.value);
      if (!parsed) {
        hex.field.setAttribute("aria-invalid", "true");
        hint.classList.remove("hidden");
        return;
      }
      wrap.commit(parsed.hex, parsed.alpha);
    });
    //: A paste is complete when it lands: no Enter needed.
    hex.field.addEventListener("paste", () => setTimeout(() => hex.field.dispatchEvent(new Event("change")), 0));
    for (const channel of channels) {
      channel.field.addEventListener("change", () => {
        //: A blank or non-number box puts the colour back; it is not 0.
        const raw = channels.map((c) => c.field.value.trim());
        if (raw.some((v) => v === "" || !Number.isFinite(Number(v)))) return paint(wbHexOf(input.value) || "#000000");
        const parts = raw.map((v) => Math.max(0, Math.min(255, Math.round(Number(v)))));
        wrap.commit(`#${parts.map((n) => n.toString(16).padStart(2, "0")).join("")}`);
      });
    }
    paint(wbHexOf(input.value) || "#000000");
    wrap.append(chip, hex.label, ...channels.map((c) => c.label), hint);
    return wrap;
  }

  //: The notebook's saved palettes ("Save these colours as a palette") as `{name, colours}`: real
  //: hex colours only, lower-cased, no repeats, none empty, at most eight (the popover is not a library).
  function wbColourPaletteList(entries) {
    const out = [];
    for (const entry of entries || []) {
      if (entry?.kind !== "palette" || out.length >= 8) continue;
      const colours = [...new Set((entry.payload?.colours || []).filter((c) => /^#[0-9a-f]{6}$/i.test(c)).map((c) => c.toLowerCase()))];
      if (colours.length) out.push({ name: String(entry.name || "").trim() || "Palette", colours });
    }
    return out;
  }

  //: A box the popover holds for the saved palettes, one labelled row of swatches each. The library
  //: index is fetched here when the Library panel has not (`/board-library`, one small request), and
  //: the rows fill in when it lands, if the popover is still open.
  function wbColourPalettes(pick, current) {
    const box = document.createElement("div");
    box.className = "wb-colour-palettes";
    const fill = () => {
      for (const { name, colours } of wbColourPaletteList(wbLibState.lib?.items)) {
        const row = swatchPicker({ label: `${name} palette`, value: colours.includes(current) ? current : null, palette: Object.fromEntries(colours.map((c) => [c, c])), none: null, onChoose: pick });
        row.title = name;
        box.append(wbColourHeading(name), row);
      }
    };
    //: `swatchPicker` lives in the categories bundle, which a board may open before.
    const lib = wbLibState.lib ? Promise.resolve(wbLibState.lib) : apiJson("/board-library").then((got) => (wbLibState.lib = wbLibState.lib || got));
    Promise.all([ensureModule("categories"), lib]).then(fill).catch(() => {}).then(() => seeds(box, pick, current));
    return box;
  }

  //: draw.io's two seed sets for the swatch box, under the saved palettes: its 24 preset colours and a
  //: 40-colour grid (ten greys, then pastel, mid and strong rings), hex without the hash.
  const SEEDS = {
    "Preset colours": "e6d0de cda2be b5739d e1d5e7 c3abd0 a680b8 d4e1f5 a9c4eb 7ea6e0 d5e8d4 9ac7bf 67ab9f b9e0a5 97d077 fff2cc ffe599 ffd966 fff4c3 ffce9f ffb570 f8cecc f19c99 ea6b66 b85450",
    "More colours": "ffffff e6e6e6 cccccc b3b3b3 999999 808080 666666 4d4d4d 333333 000000 ffcccc ffe6cc ffffcc e6ffcc ccffcc ccffff cce5ff ccccff e5ccff ffcce6 ff9999 ffcc99 ffff99 ccff99 99ff99 99ffff 99ccff 9999ff cc99ff ff99cc ff6666 ffb366 ffff66 b3ff66 66ff66 66ffff 66b2ff 6666ff b266ff ff66b3",
  };

  function seeds(box, pick, current) {
    if (typeof swatchPicker !== "function") return;
    for (const [name, list] of Object.entries(SEEDS)) {
      const colours = list.split(" ").map((c) => `#${c}`);
      const row = swatchPicker({ label: name, value: colours.includes(current) ? current : null, palette: Object.fromEntries(colours.map((c) => [c, c])), none: null, onChoose: pick });
      box.append(wbColourHeading(name), row);
    }
    //: The rows landed after the popover was placed: pull it back inside the window if they pushed it out.
    const menu = box.closest("#wb-colour-menu");
    const over = menu ? menu.getBoundingClientRect().bottom - (window.innerHeight - 8) : 0;
    if (over > 0) menu.style.top = `${Math.max(8, Math.round(menu.getBoundingClientRect().top - over))}px`;
  }

  return {
    parse: wbColourParse, fillIsOn: wbFillIsOn, fillToggle: wbFillTogglePatch, fillColour: wbFillColourPatch,
    setAlpha: wbFmtSetAlpha, opacity: wbColourOpacity, fields: wbColourFields, palettes: wbColourPalettes,
  };
})();

//: The popover, built for one field each time it opens (the recent row and
//: the pair's two colours change between opens).
async function wbOpenColourMenu(input) {
  if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) {
    try { input.showPicker(); } catch { /* no picker: the field stays as it is */ }
    return;
  }
  const menu = wbColourMenu();
  //: **A Fill or Border tab keeps the panel where it is** (the 22-10 bug doc,
  //: "it moved the popup panel"). The tabs reopen the menu on the other
  //: field, and placing it against that field moved it: 310px left from the
  //: rail's ink to the tool's fill, and to the top left when the other well
  //: had no box (wb1025-colourtabs.js). The 0.6.1 fallback only caught the
  //: second case. A press on some other well still places it there.
  const open = !menu.classList.contains("hidden");
  const partner = open && wbColourState.input ? wbColourPairOf(wbColourState.input) : null;
  const own = input.getBoundingClientRect();
  //: And a field with no box (hidden with its group) never anchors it: that
  //: is a panel at 0,0.
  const keepAt = open && ((partner && (partner.fillEl === input || partner.borderEl === input)) || !(own.width || own.height))
    ? menu.getBoundingClientRect() : null;
  wbStopEyedrop();
  wbColourState.input = input;
  const name = wbColourName(input);
  menu.setAttribute("aria-label", name);
  const pick = (colour) => {
    wbSetColourField(input, colour);
    closeActionMenus();
  };
  const head = document.createElement("p");
  head.className = "wb-colour-head";
  head.id = "wb-colour-head";
  head.textContent = input.classList.contains("wb-mixed") ? `${name}: mixed, a pick sets them all` : name;
  const rows = [head];
  const pair = wbColourPairOf(input);
  if (pair) {
    //: Which of the two is being set, and the other one press away.
    const seg = document.createElement("div");
    seg.className = "tabs-line popup-kinds wb-colour-pair";
    seg.setAttribute("role", "tablist");
    seg.setAttribute("aria-label", "Which colour");
    for (const [el, words] of [[pair.fillEl, "Fill"], [pair.borderEl, "Border"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(el === input));
      button.tabIndex = el === input ? 0 : -1;
      button.title = `Set the ${words.toLowerCase()} colour (${el.value})`;
      const dot = document.createElement("span");
      dot.className = "wb-swatch-dot";
      dot.setAttribute("aria-hidden", "true");
      dot.style.setProperty("--swatch", el.value);
      const label = document.createElement("span");
      label.textContent = words;
      button.append(dot, label);
      button.addEventListener("click", () => {
        if (el !== input) wbOpenColourMenu(el);
      });
      seg.append(button);
    }
    seg.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      wbOpenColourMenu(input === pair.fillEl ? pair.borderEl : pair.fillEl).then(() => document.querySelector('#wb-colour-menu [role="tab"][aria-selected="true"]')?.focus());
    });
    const onBox = pair.on ? document.getElementById(pair.on) : null;
    const fillOff = Boolean(onBox && !onBox.checked && !onBox.indeterminate);
    const isFill = input === pair.fillEl;
    const match = wbColourButton("equals", isFill ? "Same as border" : "Same as fill",
      isFill ? "Make the fill the border's colour" : "Make the border the fill's colour", () => {
        closeActionMenus();
        wbWriteColourPair(pair, isFill ? "fill-from-border" : "border-from-fill");
      });
    match.classList.add("wb-colour-match");
    if (!isFill && fillOff) {
      match.disabled = true;
      match.title = "The shape has no fill to match: pick a fill first";
    }
    const swap = wbColourButton("arrows-left-right", "Swap", "Swap the fill and border colours", () => {
      closeActionMenus();
      wbWriteColourPair(pair, "swap");
    });
    swap.classList.add("wb-colour-swap");
    if (pair.selection && fillOff) {
      swap.disabled = true;
      swap.title = "The shape has no fill to swap: pick a fill first";
    }
    const actions = document.createElement("div");
    actions.className = "wb-colour-actions";
    actions.append(match, swap);
    rows.push(seg, actions);
  }
  const current = wbHexOf(input.value);
  const recent = wbRecentColours();
  rows.push(wbColourHeading("Recent"));
  if (recent.length) {
    const row = swatchPicker({ label: "Recent colours", value: current, palette: Object.fromEntries(recent.map((c) => [c, c])), none: null, onChoose: pick });
    row.classList.add("wb-colour-recent");
    rows.push(row);
  } else {
    const empty = document.createElement("p");
    empty.className = "muted empty-line wb-colour-recent-empty";
    empty.textContent = "Colours you pick show here.";
    rows.push(empty);
  }
  rows.push(wbColourHeading("Colours"));
  const byHex = Object.fromEntries(Object.entries(WB_COLOUR_SWATCHES).map(([k, v]) => [v, k]));
  const board = swatchPicker({ label: "Board colours", value: byHex[current] || null, palette: WB_COLOUR_SWATCHES, none: null, onChoose: (key) => pick(WB_COLOUR_SWATCHES[key]) });
  rows.push(board);
  if (typeof wbLibState !== "undefined") rows.push(wbColour.palettes(pick, current));
  let opacityRow = null;
  const custom = wbColour.fields(input, (alpha) => opacityRow?.setValue(Math.round(alpha * 100)));
  opacityRow = wbColour.opacity(input);
  rows.push(wbColourHeading("Custom"), custom);
  if (opacityRow) rows.push(opacityRow);
  const tools = document.createElement("div");
  tools.className = "wb-colour-actions";
  const dropper = wbColourButton("eyedropper", "Pick from the board",
    "Take a colour from a shape, a line, a text box or any colour button: Alt takes a shape's border", () => {
      if (wbColourState.eyedrop) wbStopEyedrop();
      else wbStartEyedrop();
    });
  dropper.id = "wb-colour-eyedrop";
  dropper.setAttribute("aria-pressed", "false");
  //: The browser's own eyedropper reads any pixel on the screen; where it
  //: does not exist the board one above is all there is.
  const screen = "EyeDropper" in window ? wbColourButton("eyedropper", "From screen", "Take any colour on the screen", async () => {
    try {
      const picked = await new window.EyeDropper().open();
      custom.commit(picked.sRGBHex);
    } catch {
      /* cancelled with Escape: nothing to take */
    }
  }) : null;
  //: What a press on a shape takes, said rather than only held under Alt
  //: (a touch screen has no Alt); shown while the eyedropper is on.
  const take = document.createElement("label");
  take.className = "wb-snap-label wb-colour-take hidden";
  take.id = "wb-colour-take";
  take.title = "Take a shape's border colour rather than its fill (Alt does the same)";
  const takeBox = document.createElement("input");
  takeBox.type = "checkbox";
  takeBox.checked = wbColourState.takeBorder;
  takeBox.addEventListener("change", () => {
    wbColourState.takeBorder = takeBox.checked;
  });
  const takeWords = document.createElement("span");
  takeWords.textContent = "Take a shape's border";
  take.append(takeBox, takeWords);
  tools.append(dropper);
  if (screen) tools.append(screen);
  rows.push(tools, take);
  menu.replaceChildren(...rows);
  closeActionMenus();
  window._menuOpenedAt = performance.now();
  menu._escapedOpener = input;
  menu.classList.add("action-menu-escaped");
  menu.classList.remove("hidden");
  wbWellExpanded(input, true);
  input.classList.add("wb-colour-target");
  if (keepAt) {
    //: The same corner, pulled back inside the window if the other field's
    //: rows made the panel taller.
    const box = menu.getBoundingClientRect();
    menu.style.left = `${Math.round(Math.max(8, Math.min(keepAt.left, window.innerWidth - 8 - box.width)))}px`;
    menu.style.top = `${Math.round(Math.max(8, Math.min(keepAt.top, window.innerHeight - 8 - box.height)))}px`;
  } else {
    placeEscapedMenu(menu, input);
  }
  (menu.querySelector('[role="radio"][tabindex="0"]') || menu.querySelector("button"))?.focus({ preventScroll: true });
}

//: A sticky note's paper in the same popover as the colour wells (INBOX 1300
//: C18): one row of the seven papers, the current one checked, arrow keys
//: moving along it, Escape closing and returning focus to the button.
async function wbOpenPaperMenu(button) {
  if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) return;
  const menu = wbColourMenu();
  wbStopEyedrop();
  wbColourState.input = null;
  menu.setAttribute("aria-label", "Note colour");
  const head = document.createElement("p");
  head.className = "wb-colour-head";
  head.textContent = "Note colour";
  const byKey = Object.fromEntries(WB_STICKY_PAPERS.map((p) => [p.label.toLowerCase(), p.value]));
  const now = (button.dataset.paper || "").toLowerCase();
  const row = swatchPicker({
    label: "Note colours",
    value: Object.keys(byKey).find((k) => byKey[k] === now) || null,
    palette: byKey,
    none: null,
    onChoose: (key) => {
      closeActionMenus();
      wbSetStickyPaper(byKey[key]);
      button.focus({ preventScroll: true });
    },
  });
  menu.replaceChildren(head, row);
  closeActionMenus();
  window._menuOpenedAt = performance.now();
  menu._escapedOpener = button;
  menu.classList.add("action-menu-escaped");
  menu.classList.remove("hidden");
  button.setAttribute("aria-expanded", "true");
  button.classList.add("wb-colour-target");
  placeEscapedMenu(menu, button);
  (menu.querySelector('[role="radio"][tabindex="0"]') || menu.querySelector("button"))?.focus({ preventScroll: true });
}

//: **The eyedropper** (the owner: "I tried to click the colour circle on the
//: fill colour circle in the tools popup above the shape but it just opened
//: that colour picker menu instead of getting the colour"). While it is on,
//: the next press anywhere takes a colour instead of doing what it would:
//: a colour button gives its colour, a shape its fill (its border with Alt),
//: a line its ink, a text box its fill or, with Alt, its edge. The press
//: never reaches what is under it. A press on nothing with a colour, or
//: Escape, puts it away.
function wbStartEyedrop() {
  const menu = wbColourState.menu;
  if (!menu || !wbColourState.input) return;
  wbColourState.eyedrop = true;
  document.documentElement.classList.add("wb-eyedropping");
  const button = document.getElementById("wb-colour-eyedrop");
  button?.setAttribute("aria-pressed", "true");
  document.getElementById("wb-colour-take")?.classList.remove("hidden");
  const head = document.getElementById("wb-colour-head");
  if (head) head.textContent = `${wbColourName(wbColourState.input)}: click a shape or a colour`;
  wbAnnounce(`Picking a colour for the ${wbColourName(wbColourState.input).toLowerCase()}. Click a shape or a colour button; Alt takes a border. Escape stops.`);
}

function wbStopEyedrop() {
  if (!wbColourState.eyedrop) return;
  wbColourState.eyedrop = false;
  document.documentElement.classList.remove("wb-eyedropping");
  document.getElementById("wb-colour-eyedrop")?.setAttribute("aria-pressed", "false");
  document.getElementById("wb-colour-take")?.classList.add("hidden");
  const head = document.getElementById("wb-colour-head");
  if (head && wbColourState.input) head.textContent = wbColourName(wbColourState.input);
}

//: The colour a press would take, or null.
function wbSampleColour(target, border) {
  if (!(target instanceof Element)) return null;
  const field = target.closest('input[type="color"]');
  if (field) return wbHexOf(field.value);
  const swatch = target.closest(".swatch-picker [role='radio'], .wb-paper-trigger, .wb-swatch-dot");
  if (swatch) {
    const style = getComputedStyle(swatch);
    return wbHexOf(style.getPropertyValue("--swatch") || swatch.dataset.paper || style.backgroundColor);
  }
  const sketchEl = target.closest(".sketch-group[data-id]");
  if (sketchEl) {
    const sketch = wbFindItem("sketch", Number(sketchEl.dataset.id));
    const parsed = sketch ? wbSketchParsedData(sketch) || JSON.parse(sketch.data || "{}") : null;
    if (parsed) return wbHexOf(border || !parsed.fill ? parsed.color : parsed.fill);
  }
  const objectEl = target.closest(".wb-object[data-id]");
  if (objectEl) {
    const object = wbFindItem("object", Number(objectEl.dataset.id));
    const d = object?.data || {};
    const picked = border ? d.border_color : (d.bg && d.bg !== "transparent" ? d.bg : d.color);
    const hex = wbHexOf(picked);
    if (hex) return hex;
    const style = getComputedStyle(objectEl);
    return wbHexOf(border ? style.borderTopColor : style.backgroundColor) || wbHexOf(style.color);
  }
  const card = target.closest(".node-card");
  if (card) return wbHexOf(getComputedStyle(card)[border ? "borderTopColor" : "backgroundColor"]);
  return null;
}

window.addEventListener("pointerdown", (e) => {
  if (!wbColourState.eyedrop) return;
  const menu = wbColourState.menu;
  if (!menu || menu.classList.contains("hidden")) {
    wbStopEyedrop();
    return;
  }
  if (menu.contains(e.target)) return;
  const colour = wbSampleColour(e.target, e.altKey || wbColourState.takeBorder);
  if (!colour) {
    wbStopEyedrop();
    return;
  }
  e.preventDefault();
  e.stopImmediatePropagation();
  wbColourState.swallowClick = true;
  const input = wbColourState.input;
  wbStopEyedrop();
  wbAnnounce(`${wbColourName(input)} ${colour}.`);
  wbSetColourField(input, colour);
  closeActionMenus();
}, true);

//: The click that follows a taken press is the press's: it must not open
//: the menu of the colour button it was taken from.
window.addEventListener("click", (e) => {
  if (!wbColourState.swallowClick) return;
  wbColourState.swallowClick = false;
  e.preventDefault();
  e.stopImmediatePropagation();
}, true);

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && wbColourState.eyedrop) {
    e.preventDefault();
    e.stopImmediatePropagation();
    wbStopEyedrop();
  }
}, true);

//: Every board colour field opens the popover; a colour set any way at all
//: (the popover, the browser's dialog, the eyedropper) joins the recent row.
//: The fields are in the board template, so they are wired when it is stamped.
onSurface("board", () => {
  for (const input of document.querySelectorAll('input[type="color"].wb-color-picker')) {
    if (input.dataset.wbColourWell) continue;
    input.dataset.wbColourWell = "1";
    input.addEventListener("click", (e) => {
      if (wbColourState.eyedrop) return;
      e.preventDefault();
      wbOpenColourMenu(input);
    });
  }
});
onDomReady(() => {
  document.addEventListener("change", (e) => {
    if (e.target instanceof HTMLInputElement && e.target.matches('input[type="color"].wb-color-picker')) wbRememberColour(e.target.value);
  }, true);
});

//: **Board style presets** (draw.io's Diagram style panel): with nothing selected, the Format panel's
//: Style tab lists twelve colour schemes (fill, line, text); one press writes them across every shape,
//: line, connector, sticky and text box on the board in one undo step. A shape with no fill stays
//: unfilled, a text box with no background gets no background, pictures and frames are left alone.
//: Hung on `wbFmtState` so the shared scope does not grow (test_global_scope_ratchet).
wbFmtState.board = (() => {
  const PRESETS = [
    { name: "Blue", fill: "#dae8fc", stroke: "#6c8ebf", ink: "#1f2430" },
    { name: "Green", fill: "#d5e8d4", stroke: "#82b366", ink: "#1f2430" },
    { name: "Yellow", fill: "#fff2cc", stroke: "#d6b656", ink: "#1f2430" },
    { name: "Orange", fill: "#ffe6cc", stroke: "#d79b00", ink: "#1f2430" },
    { name: "Red", fill: "#f8cecc", stroke: "#b85450", ink: "#1f2430" },
    { name: "Purple", fill: "#e1d5e7", stroke: "#9673a6", ink: "#1f2430" },
    { name: "Teal", fill: "#d0f0ec", stroke: "#2f8f83", ink: "#1f2430" },
    { name: "Pink", fill: "#fbe4ef", stroke: "#c2538a", ink: "#1f2430" },
    { name: "Grey", fill: "#f5f5f5", stroke: "#666666", ink: "#1f2430" },
    { name: "Paper", fill: "#ffffff", stroke: "#000000", ink: "#000000" },
    { name: "Slate", fill: "#23445d", stroke: "#10202c", ink: "#ffffff" },
    { name: "Night", fill: "#1f2430", stroke: "#8a8f98", ink: "#f0f0f0" },
  ];

  //: What the preset writes into one item, from `{kind, fmt, filled, data}`; null for an item it leaves alone.
  function patchFor(preset, { kind, fmt, filled, data }) {
    if (kind === "sketch") {
      if (fmt === "shape") return { color: preset.stroke, ...(filled ? { fill: preset.fill, fillOpacity: 1 } : {}), label_color: preset.ink };
      return fmt === "line" || fmt === "arrow" || fmt === "link" ? { color: preset.stroke } : null;
    }
    if (kind !== "object" || fmt !== "text") return null;
    const sticky = data.bg && data.bg !== "transparent";
    return {
      ...(sticky ? { bg: preset.fill } : {}),
      ...(sticky && data.border_color && data.border_color !== "transparent" ? { border_color: preset.stroke } : {}),
      color: preset.ink,
    };
  }

  function describe(entry) {
    const fmt = wbFmtKind(entry);
    const data = entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data || {};
    return { kind: entry.kind, fmt, filled: fmt === "shape" && Boolean(wbFmtValue(entry, "fill-on")), data };
  }

  async function apply(preset) {
    const entries = ["sketch", "object"]
      .flatMap((kind) => (wbState?.[WB_LIST_BY_KIND[kind]] || []).map((item) => ({ kind, id: item.id, item })))
      .filter((entry) => !wbIsLocked(entry.kind, entry.item));
    let changed = 0;
    await wbRecordGesture(async () => {
      const saves = [];
      for (const entry of entries) {
        const patch = patchFor(preset, describe(entry));
        if (!patch) continue;
        if (entry.kind === "sketch") {
          if (!wbSketchSetProps(entry.item, patch)) continue;
        } else {
          entry.item.data = { ...entry.item.data, ...patch };
        }
        saves.push({ kind: entry.kind, item: entry.item });
      }
      changed = saves.length;
      await wbSaveMany(saves);
    });
    wbScheduleRender();
    wbFormatSyncSoon();
    toast(changed ? `Board style ${preset.name} applied to ${changed} ${changed === 1 ? "item" : "items"}.` : "Nothing on the board takes a board style yet.");
  }

  //: The section shows on the Style tab when nothing is selected; its buttons are built the first time.
  function show(section, visible) {
    section.hidden = !visible;
    const list = document.getElementById("wb-board-style-list");
    if (!visible || !list || list.childElementCount) return;
    for (const preset of PRESETS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ghost wb-board-style-btn";
      button.title = `${preset.name}: fill, line and text colours across the board`;
      button.setAttribute("aria-label", `Board style ${preset.name}`);
      button.style.setProperty("--swatch", preset.fill);
      button.style.color = preset.stroke;
      button.addEventListener("click", () => apply(preset));
      list.append(button);
    }
  }

  //: The board's default style (draw.io's Set as default style): the selected item's look, kept on the
  //: board under its kind (`shape`, `link`, `text`, `pen`, `highlighter`) so the tools start new items with it.
  const FILL_KEYS = ["fill", "fillOpacity", "gradient", "fillStyle"];

  function groupOf() {
    const sketch = wbSelectedSketchOrNull();
    if (sketch) {
      //: Plain parse: the shape reader wants a drawn path (`d`), which a connector does not have.
      let data = null;
      try {
        data = JSON.parse(sketch.data);
      } catch {
        return null;
      }
      if (!data || typeof data !== "object") return null;
      const group = String(data.type || "").startsWith("link-") ? "link" : { draw: "pen", highlighter: "highlighter" }[data.shape] || "shape";
      return { group, style: wbPickStyle(data, WB_SKETCH_STYLE_KEYS) };
    }
    const object = wbSelectedTextObjectOrNull();
    return object ? { group: "text", style: wbPickStyle(object.data, WB_OBJECT_STYLE_KEYS) } : null;
  }

  async function setDefault() {
    const picked = groupOf();
    if (!picked || !Object.keys(picked.style).length) return toast("Select a shape, connector, text box or stroke to take its style.");
    const kept = wbBoardBackground().defaults || {};
    if (await wbSetBackground({ defaults: { ...kept, [picked.group]: picked.style } })) {
      toast(`Default ${{ shape: "shape", link: "connector", text: "text box", pen: "pen stroke", highlighter: "highlighter stroke" }[picked.group]} style set. New ones on this board start with it.`);
    }
  }

  async function clearDefault() {
    if (!wbBoardBackground().defaults) return toast("This board has no default style.");
    if (await wbSetBackground({ defaults: null })) toast("Default style cleared.");
  }

  //: `data` as a new item of `group` should start: the defaults win for a shape or a connector (the board's
  //: style is explicit), the caller's values win for a text box (a sticky's own paper). A line takes no fill.
  function withDefaults(group, data, { fillable = true } = {}) {
    //: The board's Shadow switch (Format > Board): a new shape or text box starts with a shadow, unless its style says otherwise.
    const bg = wbBoardBackground();
    const style = bg.shadow_default && (group === "shape" || group === "text") ? { shadow: true, ...bg.defaults?.[group] } : bg.defaults?.[group];
    if (!style) return data;
    const own = { ...style };
    if (!fillable) for (const key of FILL_KEYS) delete own[key];
    return group === "text" ? { ...own, ...data } : { ...data, ...own };
  }

  return { PRESETS, patchFor, apply, show, setDefault, clearDefault, withDefaults };
})();
//: --- end board style

//: **Edit style as text** (draw.io's Edit Style): one item's style as JSON in the Data tab; Apply checks
//: it and writes it in one undo step. What is not style stays out of the text and out of the write: a
//: sketch's path, type, label, ends and properties, a text box's words. `parse` returns `{patch}` (a key
//: taken out of the text is `null`, which the apply turns into a removal) or `{error}`.
//: Hung on `wbFmtState` so the shared scope does not grow (test_global_scope_ratchet).
wbFmtState.raw = (() => {
  const SKETCH_HIDDEN = /^(?:d|type|label|props|comments|library_ref|bends|waypoints|points|via|group_id|groupId|layer|locked|url|link)$|^(?:source|target)/;
  const OBJECT_KEYS = new Set([...WB_OBJECT_STYLE_KEYS, "font_family", "bold", "italic", "underline", "strike", "align", "valign", "line_height", "letter_spacing", "text_dir"]);
  const MAX_CHARS = 8000;

  const allowed = (kind, key) => (kind === "sketch" ? !SKETCH_HIDDEN.test(key) : OBJECT_KEYS.has(key));

  function show(kind, data) {
    const out = {};
    for (const [key, value] of Object.entries(data || {})) if (allowed(kind, key) && value !== undefined) out[key] = value;
    return JSON.stringify(out, null, 2);
  }

  //: Values are words, numbers, switches or one small group of those (a gradient).
  const plain = (v) => v === null || ["string", "number", "boolean"].includes(typeof v);
  const valid = (v) => plain(v) || (v && typeof v === "object" && !Array.isArray(v) && Object.values(v).every(plain));

  function parse(kind, data, text) {
    if (String(text).length > MAX_CHARS) return { error: "That is too long for a style." };
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      return { error: `Not valid JSON: ${err.message.replace(/^JSON\.parse: /, "")}` };
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return { error: "The style is an object in braces, like {\"color\": \"#ff0000\"}." };
    const bad = Object.entries(parsed).find(([, v]) => !valid(v));
    if (bad) return { error: `"${bad[0]}" has to be a word, a number, a switch or one small group of those.` };
    const patch = {};
    for (const key of Object.keys(data || {})) if (allowed(kind, key)) patch[key] = null;
    for (const [key, value] of Object.entries(parsed)) if (allowed(kind, key)) patch[key] = value;
    return { patch };
  }

  function sync(entries) {
    const row = document.getElementById("wb-fmt-raw");
    if (!row || document.activeElement === row) return;
    const one = entries.length === 1 && ["sketch", "object"].includes(entries[0].kind) ? entries[0] : null;
    row.value = one ? show(one.kind, one.kind === "sketch" ? wbFmtSketch(one) : one.item.data) : "";
    row.dataset.item = one ? `${one.kind}:${one.id}` : "";
    const status = document.getElementById("wb-fmt-raw-status");
    if (status) status.textContent = "";
  }

  function apply() {
    const box = document.getElementById("wb-fmt-raw");
    const status = document.getElementById("wb-fmt-raw-status");
    const entry = wbFmtEntries().find((e) => `${e.kind}:${e.id}` === box?.dataset.item);
    if (!entry) return;
    const data = entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data || {};
    const result = parse(entry.kind, data, box.value);
    if (result.error) {
      status.textContent = result.error;
      status.classList.add("error");
      return;
    }
    status.classList.remove("error");
    status.textContent = "";
    const patch = Object.fromEntries(Object.entries(result.patch).map(([key, value]) => [key, value === null ? undefined : value]));
    wbFmtApply("rawstyle", () => patch, "Style applied.");
  }

  //: Ctrl+E and the command: the Data tab, with the box under the caret.
  function open() {
    wbFormatOpen("data");
    document.getElementById("wb-fmt-raw")?.focus();
  }

  return { show, parse, sync, apply, open };
})();
//: --- end edit style
