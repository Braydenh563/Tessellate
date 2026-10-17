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
const wbFmtState = { fmtTab: "style", fmtSyncQueued: false, fmtLiveQueued: false, fmtFrameQueued: false };

function wbFmtEntries() {
  if (wbMultiSelection.size) return wbSelectionEntries();
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
    return k === "text" || k === "image" || k === "frame" || k === "table" ? k : null;
  }
  let parsed = null;
  try {
    parsed = JSON.parse(entry.item.data);
  } catch {
    return null;
  }
  if (String(parsed?.type || "").startsWith("link-")) return wbLinkTakesLabel(entry.item, parsed) ? "link" : null;
  if (typeof parsed?.d !== "string") return null;
  if (wbShapeLabelKind(parsed)) return "shape";
  return wbSketchTakesCaps(parsed) ? "arrow" : "line";
}

//: The fields each kind takes, by the `data-fmt` names in index.html.
const WB_FMT_FIELDS = {
  shape: ["stroke", "width", "dash", "fill", "alpha", "shadow", "rough", "text", "geometry", "flip", "style-lib", "props"],
  line: ["stroke", "width", "dash", "alpha", "shadow", "rough", "geometry", "flip", "style-lib", "props"],
  //: A straight line or arrow: a line that takes ends.
  arrow: ["stroke", "width", "dash", "caps", "alpha", "shadow", "rough", "geometry", "flip", "style-lib", "props"],
  link: ["stroke", "width", "dash", "alpha", "rough", "route", "jumps", "caps", "label-t", "props"],
  text: ["stroke", "fill", "alpha", "shadow", "fold", "text", "geometry", "angle", "style-lib", "props"],
  image: ["alpha", "shadow", "geometry", "angle", "props"],
  frame: ["geometry", "props"],
  table: ["alpha", "shadow", "geometry", "props"],
  note: ["geometry", "angle"],
};

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
    case "fill-on": return s ? Boolean(s.fill) : Boolean(o.bg && o.bg !== "transparent");
    case "fill": return s ? s.fill || "#3355ff" : (o.bg && o.bg !== "transparent" ? o.bg : "#ffffff");
    case "alpha": return Math.round(((s ? s.alpha : o?.alpha) ?? 1) * 100);
    case "shadow": return Boolean(s ? s.shadow : o?.shadow);
    case "rough": return wbDrawsRough(s, false);
    case "route": return wbLinkRouteName(s);
    case "jumps": return WB_JUMP_STYLES.includes(s?.jumps) ? s.jumps : "none";
    case "startcap": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).startCap;
    case "endcap": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).endCap;
    case "startsize": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).startSize || "m";
    case "endsize": return (kind === "arrow" ? wbSketchCaps(s) : wbLinkCaps(s)).endSize || "m";
    case "label-t": return Math.round(wbLinkLabelT(s) * 100);
    case "size": return kind === "shape" ? s.label_size || 16 : o.font_size || 16;
    case "bold": return Boolean(kind === "shape" ? s.label_bold : o.bold);
    case "italic": return Boolean(kind === "shape" ? s.label_italic : o.italic);
    case "align": return (kind === "shape" ? s.label_align : o.align) || (kind === "shape" ? "center" : "left");
    //: Words in a shape sit in its middle and a text box's at its top unless
    //: told otherwise (the owner, 2026-10-10: "there's no way to vertically
    //: centre text").
    case "valign": return (kind === "shape" ? s.label_valign : o.valign) || (kind === "shape" ? "middle" : "top");
    case "ink": return (kind === "shape" ? s.label_color : o.color) || "#1f2430";
    default: return null;
  }
}

//: **One edit to every selected item that takes it, as one undo step.**
//: `patch(entry, kind)` returns a partial for a sketch's data, an object's
//: data, or `{row: {...}}` for a row's own columns; null skips the entry.
async function wbFmtApply(field, patch, said) {
  const entries = wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item));
  if (!entries.length) return;
  await wbRecordGesture(async () => {
    for (const entry of entries) {
      const kind = wbFmtKind(entry);
      if (!kind || !(WB_FMT_FIELDS[kind] || []).includes(field)) continue;
      const partial = patch(entry, kind);
      if (!partial) continue;
      if (entry.kind === "sketch") {
        await wbSaveSketchProps(entry.item, partial);
      } else if (partial.row) {
        Object.assign(entry.item, partial.row);
        if (entry.kind === "node") await wbSaveNode(entry.item);
        else await wbSaveObject(entry.item);
      } else if (entry.kind === "object") {
        entry.item.data = { ...entry.item.data, ...partial };
        for (const [key, value] of Object.entries(partial)) if (value === undefined) delete entry.item.data[key];
        await wbSaveObject(entry.item);
      }
    }
  });
  wbScheduleRender();
  if (said) wbAnnounce(said);
  wbFormatSyncSoon();
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
      for (const e of entries) {
        if (wbFmtKind(e) === "link") continue;
        await wbMoveItemBy(e.kind, e.id, e.item, dx, dy);
      }
      return;
    }
    const target = Math.max(8, value);
    //: Several items (a group): the set is sized as one box about its top
    //: left, each member scaling with it (B29: "I cant widen objects on one
    //: axis when grouped").
    if (entries.length !== 1) {
      await wbFmtScaleSelection(entries, box, axis, target);
      wbScheduleRender();
      wbAnnounce(`${axis === "w" ? "Width" : "Height"} ${Math.round(value)}.`);
      wbFormatSyncSoon();
      return;
    }
    const [e] = entries;
    const dim = axis === "w" ? "width" : "height";
    const size = axis === "w" ? e.bbox.maxX - e.bbox.minX : e.bbox.maxY - e.bbox.minY;
    if (size > 0 && Math.abs(size - target) >= 0.5) await wbSizeItemTo(e, dim, target, target / size);
  });
  wbScheduleRender();
  wbAnnounce(`${{ x: "X", y: "Y", w: "Width", h: "Height" }[axis]} ${Math.round(value)}.`);
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
  for (const e of entries) {
    if (wbFmtKind(e) === "link" || !e.bbox) continue;
    if (e.kind === "sketch") {
      const parsed = wbSketchParsedData(e.item);
      if (!parsed) continue;
      await wbSaveSketchD(e.item, wbTransformPathD(parsed.d, {
        sx: horizontal ? f : 1, sy: horizontal ? 1 : f, anchorX: ax, anchorY: ay,
      }));
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
    if (e.kind === "node") await wbSaveNode(item);
    else await wbSaveObject(item);
  }
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
    for (const e of entries) {
      const parsed = wbSketchParsedData(e.item);
      if (!parsed) continue;
      const d = wbTransformPathD(parsed.d, {
        sx: axis === "h" ? -1 : 1,
        sy: axis === "v" ? -1 : 1,
        anchorX: (e.bbox.minX + e.bbox.maxX) / 2,
        anchorY: (e.bbox.minY + e.bbox.maxY) / 2,
      });
      await wbSaveSketchD(e.item, d);
    }
  });
  wbScheduleRender();
  wbAnnounce(axis === "h" ? "Flipped left to right." : "Flipped top to bottom.");
}

//: A connector's line shape: curved, straight, or elbow (a straight link
//: with `route: "elbow"`, see `wbLinkRouteName`). Its bends go with it, as
//: draw.io keeps an edge's waypoints across styles: every style takes them
//: (wb-phase2 step 1), and an old link's single `bend` becomes one.
async function wbSetLinkRoute(value) {
  await wbFmtApply("route", (entry) => {
    const parsed = wbFmtSketch(entry);
    if (wbLinkRouteName(parsed) === value) return null;
    const points = wbLinkWaypoints(parsed, wbResolveLinkEndpoints(parsed));
    return {
      type: value === "curved" ? "link-curved" : "link-straight",
      route: value === "elbow" ? "elbow" : undefined,
      points: points.length ? points.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) })) : undefined,
      bend: undefined,
    };
  }, `Line shape: ${value}.`);
}

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
  wbFormatSync();
  if (focus) panel.querySelector(`[data-format-tab="${wbFmtState.fmtTab}"]`)?.focus();
}

function wbFormatClose({ restoreFocus = true } = {}) {
  const panel = wbFormatPanel();
  if (!panel || panel.classList.contains("hidden")) return;
  const hadFocus = panel.contains(document.activeElement);
  panel.classList.add("hidden");
  try {
    prefs.remove(WB_FMT_KEY);
  } catch {
    /* nothing to forget */
  }
  if (restoreFocus && hadFocus) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
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
  } else if (el.type === "number") {
    el.value = isMixed ? "" : value;
    el.placeholder = isMixed ? "Mixed" : "";
  } else {
    el.value = value;
  }
}

function wbFormatSync() {
  const panel = wbFormatPanel();
  if (!panel || panel.classList.contains("hidden")) return;
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
  if (fields.has("props")) wbFmtSyncProps(entries);
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
    ["wb-fmt-fill", "fill", "fill"], ["wb-fmt-route", "route", "route"], ["wb-fmt-jumps", "jumps", "jumps"], ["wb-fmt-startcap", "startcap", "caps"],
    ["wb-fmt-endcap", "endcap", "caps"], ["wb-fmt-startsize", "startsize", "caps"], ["wb-fmt-endsize", "endsize", "caps"], ["wb-fmt-label-t", "label-t", "label-t"], ["wb-fmt-size", "size", "text"],
    ["wb-fmt-ink", "ink", "text"], ["wb-fmt-alpha", "alpha", "alpha"],
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
  for (const [id, field] of [["wb-fmt-shadow", "shadow"], ["wb-fmt-rough", "rough"]]) {
    const box = document.getElementById(id);
    if (!takes.has(field) || !box || document.activeElement === box) continue;
    box.checked = wbFmtValue(first, field);
    box.indeterminate = mixed(field);
  }
  const sticky = entries.find((e) => e.kind === "object" && wbIsSticky(e.item));
  if (sticky) set("wb-fmt-fold", wbStickyFolds(sticky.item), "checked");
  const alphaOut = document.getElementById("wb-fmt-alpha-out");
  if (alphaOut && takes.has("alpha")) alphaOut.textContent = mixed("alpha") ? "Mixed" : `${wbFmtValue(first, "alpha")}%`;
  if (takes.has("text")) {
    const pressed = (field, value) => {
      const some = sharing.map((e) => wbFmtValue(e, field) === value);
      return some.every(Boolean) ? "true" : some.some(Boolean) ? "mixed" : "false";
    };
    for (const button of panel.querySelectorAll("#wb-fmt-align [data-align]")) button.setAttribute("aria-pressed", pressed("align", button.dataset.align));
    for (const button of panel.querySelectorAll("#wb-fmt-valign [data-valign]")) button.setAttribute("aria-pressed", pressed("valign", button.dataset.valign));
    document.getElementById("wb-fmt-bold")?.setAttribute("aria-pressed", pressed("bold", true));
    document.getElementById("wb-fmt-italic")?.setAttribute("aria-pressed", pressed("italic", true));
  }
  const box = wbFmtBox(entries);
  if (!box) return;
  set("wb-fmt-x", Math.round(box.minX));
  set("wb-fmt-y", Math.round(box.minY));
  set("wb-fmt-w", Math.round(box.maxX - box.minX));
  set("wb-fmt-h", Math.round(box.maxY - box.minY));
  set("wb-fmt-angle", Math.round(first.item.rotation || 0));
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
  set("wb-fmt-x", Math.round(box.minX));
  set("wb-fmt-y", Math.round(box.minY));
  set("wb-fmt-w", Math.round(box.maxX - box.minX));
  set("wb-fmt-h", Math.round(box.maxY - box.minY));
}

//: --- Edit data (draw.io's custom properties; canvasdepth2) ----------------
//:
//: `data.props {name: value}` on one selected item, as rows of two fields
//: and a remove button. A change is read off every row at once and written
//: as one Undo step; a row with no name is not kept.
const WB_PROP_NAME = /^[A-Za-z][\w .-]{0,39}$/;

function wbFmtProps(entry) {
  const data = entry.kind === "sketch" ? wbFmtSketch(entry) : entry.item.data || {};
  return data.props && typeof data.props === "object" ? data.props : {};
}

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
  list.replaceChildren(...(one ? Object.entries(wbFmtProps(one)).map(([k, v]) => wbFmtPropRow(k, String(v))) : []));
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
    ["Align", ["align-left", "align-hcenter", "align-right", "align-top", "align-vcenter", "align-bottom"]],
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

onDomReady(() => {
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
  on("wb-fmt-dash", "change", (e) => wbFmtApply("dash", () => ({ dash: e.target.value === "solid" ? undefined : e.target.value }), `Line ${e.target.value}.`));
  on("wb-fmt-fill-on", "change", (e) => {
    const colour = document.getElementById("wb-fmt-fill")?.value || "#3355ff";
    wbFmtApply("fill", (entry) => (entry.kind === "sketch"
      ? { fill: e.target.checked ? colour : undefined, fillOpacity: e.target.checked ? 1 : undefined }
      : { bg: e.target.checked ? colour : "transparent" }), e.target.checked ? "Filled." : "Fill taken off.");
  });
  on("wb-fmt-fill", "change", (e) => wbFmtApply("fill", (entry) => (entry.kind === "sketch" ? { fill: e.target.value, fillOpacity: 1 } : { bg: e.target.value }), "Fill colour changed."));
  on("wb-fmt-alpha", "input", (e) => {
    const out = document.getElementById("wb-fmt-alpha-out");
    if (out) out.textContent = `${e.target.value}%`;
  });
  on("wb-fmt-alpha", "change", (e) => {
    const pct = Math.max(10, Math.min(100, Number(e.target.value) || 100));
    wbFmtApply("alpha", () => ({ alpha: pct >= 100 ? undefined : pct / 100 }), `Opacity ${pct}%.`);
  });
  on("wb-fmt-fold", "change", (e) => wbFmtApply("fold", (entry) => (entry.kind === "object" && wbIsSticky(entry.item) ? { fold: e.target.checked } : null), e.target.checked ? "Corner folded." : "Corner flat."));
  on("wb-fmt-shadow", "change", (e) => wbFmtApply("shadow", () => ({ shadow: e.target.checked || undefined }), e.target.checked ? "Shadow on." : "Shadow off."));
  //: An item that matches the board's look stores nothing, so it follows the
  //: board when the board's look changes.
  on("wb-fmt-rough", "change", (e) => {
    const board = wbBoardBackground().rough === true;
    wbFmtApply("rough", () => ({ rough: e.target.checked === board ? undefined : e.target.checked }), e.target.checked ? "Hand-drawn." : "Drawn plain.");
  });
  on("wb-fmt-route", "change", (e) => wbSetLinkRoute(e.target.value));
  on("wb-fmt-jumps", "change", (e) => {
    const style = WB_JUMP_STYLES.includes(e.target.value) ? e.target.value : "none";
    wbFmtApply("jumps", () => ({ jumps: style === "none" ? undefined : style }), `Line jumps: ${e.target.selectedOptions[0]?.textContent || style}.`);
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
  const textPatch = (shapeKey, objectKey, value) => (entry, kind) => (kind === "shape" ? { [shapeKey]: value } : { [objectKey]: value });
  on("wb-fmt-size", "change", (e) => {
    const size = Math.max(8, Math.min(200, Math.round(Number(e.target.value) || 16)));
    wbFmtApply("text", textPatch("label_size", "font_size", size), `Text size ${size}.`);
  });
  on("wb-fmt-ink", "change", (e) => wbFmtApply("text", textPatch("label_color", "color", e.target.value), "Text colour changed."));
  for (const [id, shapeKey, objectKey, word] of [["wb-fmt-bold", "label_bold", "bold", "Bold"], ["wb-fmt-italic", "label_italic", "italic", "Italic"]]) {
    on(id, "click", (e) => {
      const next = e.currentTarget.getAttribute("aria-pressed") !== "true";
      e.currentTarget.setAttribute("aria-pressed", String(next));
      wbFmtApply("text", textPatch(shapeKey, objectKey, next || undefined), `${word} ${next ? "on" : "off"}.`);
    });
  }
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
  for (const axis of ["x", "y", "w", "h"]) {
    on(`wb-fmt-${axis}`, "change", (e) => wbFmtGeometry(axis, Number(e.target.value)));
  }
  on("wb-fmt-angle", "change", (e) => wbFmtAngle(Number(e.target.value) || 0));
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
const WB_TABLE_ROW_H = 40;
const WB_TABLE_COL_W = 120;

function wbTableCells(d) {
  const cells = Array.isArray(d.data?.cells) && d.data.cells.length ? d.data.cells : [[""]];
  return cells.map((row) => (Array.isArray(row) ? row.map((c) => String(c ?? "")) : [""]));
}

function wbBuildTable(el, d) {
  el.append("div").attr("class", "wb-table-grid").attr("role", "grid").attr("aria-label", "Table")
    .on("pointerdown", (event) => {
      const cell = event.target.closest(".wb-table-cell");
      if (cell) wbFmtState.tableCell = { id: d.id, r: Number(cell.dataset.r), c: Number(cell.dataset.c) };
      if (cell?.isContentEditable) event.stopPropagation();
    })
    .on("dblclick", (event) => {
      const cell = event.target.closest(".wb-table-cell");
      if (!cell) return;
      event.stopPropagation();
      wbEditTableCell(d.id, Number(cell.dataset.r), Number(cell.dataset.c));
    });
}

//: Rebuilt only when the cells or the header change, and never under a
//: cell being typed in.
function wbPaintTable(node, d) {
  const grid = node.querySelector(".wb-table-grid");
  if (!grid || grid.querySelector("[contenteditable='true']")) return;
  const cells = wbTableCells(d);
  const key = JSON.stringify([cells, Boolean(d.data?.header)]);
  if (grid.dataset.key === key) return;
  grid.dataset.key = key;
  grid.style.gridTemplateColumns = `repeat(${cells[0].length}, minmax(0, 1fr))`;
  grid.style.gridTemplateRows = `repeat(${cells.length}, minmax(0, 1fr))`;
  grid.classList.toggle("has-header", Boolean(d.data?.header));
  grid.replaceChildren(...cells.flatMap((row, r) => row.map((text, c) => {
    const cell = document.createElement("div");
    cell.className = "wb-table-cell";
    cell.setAttribute("role", r === 0 && d.data?.header ? "columnheader" : "gridcell");
    cell.dataset.r = String(r);
    cell.dataset.c = String(c);
    cell.textContent = text;
    return cell;
  })));
}

async function wbInsertTable(rows = 3, cols = 3) {
  const [cx, cy] = wbViewCentre();
  const w = cols * WB_TABLE_COL_W;
  const h = rows * WB_TABLE_ROW_H;
  const cells = Array.from({ length: rows }, () => Array.from({ length: cols }, () => ""));
  const made = await wbCreateObject("table", { cells, header: true }, cx - w / 2, cy - h / 2, w, h, 2);
  if (!made) return null;
  clearWbSelection();
  wbHandleItemClick("object", made.id, { shiftKey: false });
  wbAnnounce(`Table added, ${rows} rows by ${cols} columns. Double-click a cell to type in it.`);
  return made;
}

//: Writes new cells (and a new size) as one Undo step.
async function wbSetTable(d, cells, size = null, said = "") {
  if (!d || wbIsLocked("object", d)) return;
  wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
  d.data = { ...d.data, cells };
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
      const at = r * cols + c + (event.shiftKey ? -1 : 1);
      if (at >= 0 && at < cells.length * cols) moveTo = [Math.floor(at / cols), at % cols];
      cell.blur();
    }
  };
  cell.addEventListener("keydown", onKey);
  cell.addEventListener("blur", onBlur);
}

//: Insert or remove a row or column at `at` (`axis` "row" or "col"); the
//: table grows or shrinks by one row's or column's share, so the others keep
//: their size.
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
  const share = axis === "row" ? d.height / rows : d.width / cols;
  const size = axis === "row" ? { height: Math.max(WB_TABLE_ROW_H / 2, d.height + (remove ? -share : share)) } : { width: Math.max(WB_TABLE_COL_W / 2, d.width + (remove ? -share : share)) };
  const word = axis === "row" ? "Row" : "Column";
  return wbSetTable(d, next, size, `${word} ${remove ? "removed" : "added"}.`);
}

//: The table's rows for the item menu: around the cell last pressed when it
//: is this table's, else at the ends.
function wbTableMenuRows(d) {
  const cells = wbTableCells(d);
  const at = wbFmtState.tableCell?.id === d.id ? wbFmtState.tableCell : null;
  const r = at ? Math.min(at.r, cells.length - 1) : cells.length - 1;
  const c = at ? Math.min(at.c, cells[0].length - 1) : cells[0].length - 1;
  const here = at ? "this cell's" : "the last";
  return [
    ["Add a row below", `Under ${here} row`, () => wbTableReshape(d, "row", r + 1, false)],
    ["Add a row above", `Over ${here} row`, () => wbTableReshape(d, "row", r, false)],
    ["Add a column to the right", `Beside ${here} column`, () => wbTableReshape(d, "col", c + 1, false)],
    ["Add a column to the left", `Before ${here} column`, () => wbTableReshape(d, "col", c, false)],
    [at ? "Delete this row" : "Delete the last row", at ? "The row of the cell you pressed" : "Press a cell first to pick another", () => wbTableReshape(d, "row", r, true)],
    [at ? "Delete this column" : "Delete the last column", at ? "The column of the cell you pressed" : "Press a cell first to pick another", () => wbTableReshape(d, "col", c, true)],
    [d.data?.header ? "Plain first row" : "First row as a header", "Bold on a tint, or like the rest", async () => {
      wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
      d.data = { ...d.data, header: !d.data?.header || undefined };
      if (!d.data.header) delete d.data.header;
      await wbSaveObject(d);
      wbScheduleRender();
    }],
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
//: colours; take a colour from the board; and More colours, which is the
//: browser's dialog. A pick is written by the field's own `change` handler,
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
    for (const entry of entries) {
      const kind = wbFmtKind(entry);
      if (kind !== "shape" && kind !== "text") continue;
      if (how !== "fill-from-border" && !wbFmtValue(entry, "fill-on")) continue;
      const { fill, border } = pick(wbFmtValue(entry, "fill"), wbFmtValue(entry, "stroke"));
      for (const colour of [fill, border]) if (colour) used.add(colour);
      if (entry.kind === "sketch") {
        await wbSaveSketchProps(entry.item, { ...(fill ? { fill, fillOpacity: 1 } : {}), ...(border ? { color: border } : {}) });
      } else {
        entry.item.data = { ...entry.item.data, ...(fill ? { bg: fill } : {}), ...(border ? { border_color: border } : {}) };
        await wbSaveObject(entry.item);
      }
    }
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
        el.setAttribute("aria-expanded", "false");
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

//: The popover, built for one field each time it opens (the recent row and
//: the pair's two colours change between opens).
async function wbOpenColourMenu(input) {
  if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) {
    try { input.showPicker(); } catch { /* no picker: the field stays as it is */ }
    return;
  }
  const menu = wbColourMenu();
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
  const tools = document.createElement("div");
  tools.className = "wb-colour-actions";
  const dropper = wbColourButton("eyedropper", "Pick from the board",
    "Take a colour from a shape, a line, a text box or any colour button: Alt takes a shape's border", () => {
      if (wbColourState.eyedrop) wbStopEyedrop();
      else wbStartEyedrop();
    });
  dropper.id = "wb-colour-eyedrop";
  dropper.setAttribute("aria-pressed", "false");
  const more = wbColourButton("palette", "More colours", "Any colour, by number or from the screen", () => {
    closeActionMenus();
    try { input.showPicker(); } catch { /* the browser has no dialog here */ }
  });
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
  tools.append(dropper, more);
  rows.push(tools, take);
  menu.replaceChildren(...rows);
  closeActionMenus();
  window._menuOpenedAt = performance.now();
  menu._escapedOpener = input;
  menu.classList.add("action-menu-escaped");
  menu.classList.remove("hidden");
  input.setAttribute("aria-expanded", "true");
  input.classList.add("wb-colour-target");
  placeEscapedMenu(menu, input);
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
  const swatch = target.closest(".swatch-picker [role='radio'], .wb-paper-swatch, .wb-swatch-dot");
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
onDomReady(() => {
  for (const input of document.querySelectorAll('input[type="color"].wb-color-picker')) {
    if (input.dataset.wbColourWell) continue;
    input.dataset.wbColourWell = "1";
    input.setAttribute("aria-haspopup", "dialog");
    input.setAttribute("aria-expanded", "false");
    input.addEventListener("click", (e) => {
      if (wbColourState.eyedrop) return;
      e.preventDefault();
      wbOpenColourMenu(input);
    });
  }
  document.addEventListener("change", (e) => {
    if (e.target instanceof HTMLInputElement && e.target.matches('input[type="color"].wb-color-picker')) wbRememberColour(e.target.value);
  }, true);
});
