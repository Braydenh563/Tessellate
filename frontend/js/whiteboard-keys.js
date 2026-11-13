(() => {
  // whiteboard-keys.js: Home, Shift+Home and Shift+Delete on a board (WHITEBOARD_PLAN, draw.io section 12,
  // "Keyboard shortcuts"). Home goes back to the top left of what is drawn at the zoom you have, Shift+Home
  // resets the view to 100% there, and Shift+Delete clears the words from the selected shapes and connectors
  // and keeps the things themselves. Ctrl+Delete ("delete with connections") is not a key here: Delete already
  // takes a card's or shape's connectors with it (INBOX 537), so the two would do the same thing.
  const PAD = 48;

  //: Where the view sits for zoom `k`: the content's top left (the origin on an empty board, where the first
  //: card lands) a little inside the free canvas's top left.
  function viewAt(k, bounds, free) {
    const x = bounds ? bounds.minX : 0;
    const y = bounds ? bounds.minY : 0;
    return { k, x: free.left + PAD - k * x, y: free.top + PAD - k * y };
  }

  function go(reset) {
    const el = document.getElementById("whiteboard-container");
    if (!el) return null;
    const at = viewAt(reset ? 1 : d3.zoomTransform(el).k, wbContentBounds(), wbFreeArea(el));
    d3.select(el).transition().duration(240).call(wbZoom.transform, d3.zoomIdentity.translate(at.x, at.y).scale(at.k));
    wbAnnounce(reset ? "View reset to 100%." : "Back at the top left.");
    return at;
  }

  //: The words a shape or a connector carries. One list, so a later label field joins it here.
  const LABEL_FIELDS = ["label", "label2"];

  //: Shift+Delete: the words off every selected shape and connector, one undo step. Locked and hidden items keep theirs.
  async function clearLabels() {
    const items = [];
    for (const key of wbSelectedKeys()) {
      const [kind, id] = key.split(":");
      if (kind !== "sketch") continue;
      const item = (wbState.sketches || []).find((s) => s.id === Number(id));
      const data = item && wbSketchData(item);
      if (!data || wbItemHidden("sketch", item) || wbIsLocked("sketch", item)) continue;
      if (LABEL_FIELDS.some((f) => typeof data[f] === "string" && data[f])) items.push(item);
    }
    if (!items.length) {
      toast("The selection has no labels to clear.", "info");
      return 0;
    }
    const patch = Object.fromEntries(LABEL_FIELDS.map((f) => [f, undefined]));
    await wbRecordGesture(async () => {
      const rows = [];
      for (const item of items) if (wbSketchSetProps(item, patch)) rows.push({ kind: "sketch", item });
      await wbSaveMany(rows);
    });
    wbScheduleRender();
    const said = `Cleared the label on ${items.length === 1 ? "1 item" : `${items.length} items`}.`;
    wbAnnounce(said);
    toast(said);
    return items.length;
  }

  //: **Repeat last** (the owner's open-work sweep, "repeat the last move, rotate or scale"): the board keeps
  //: the last move, turn or size change as a delta, and the command (Ctrl+Alt+Y; Ctrl+Alt+R is the app's reload)
  //: does it again to whatever is selected now. A repeat does not record itself, so it never drifts.
  let last = null;
  let replaying = false;

  //: Called from the places a move, turn or size change ends. A null or zero delta keeps the one before it.
  //: How far the item under the pointer moved, for Repeat last (whiteboard-keys.js): its box now against the
  //: payload the undo step keeps. Null for a drag that went nowhere or an item that is gone.
  function dragDelta(primary) {
    const before = primary?.before;
    const item = before && wbFindItem(primary.kind, primary.id);
    if (!item) return null;
    let dx = 0, dy = 0;
    if (primary.kind === "sketch") {
      let was = null;
      try { was = wbPathBBox(JSON.parse(before.data).d); } catch { return null; }
      const now = was && wbItemBBox("sketch", item);
      if (!now) return null;
      [dx, dy] = [now.minX - was.minX, now.minY - was.minY];
    } else {
      [dx, dy] = [(item.x || 0) - (before.x || 0), (item.y || 0) - (before.y || 0)];
    }
    return dx || dy ? { kind: "move", dx: Math.round(dx), dy: Math.round(dy) } : null;
  }

  function record(delta) {
    if (replaying || !delta) return;
    if (delta.kind === "move" && !delta.dx && !delta.dy) return;
    if (delta.kind === "turn" && !(delta.deg % 360)) return;
    if (delta.kind === "scale" && !(delta.factor > 0 && Math.abs(delta.factor - 1) > 0.001)) return;
    last = { ...delta };
  }

  //: Says what Repeat last would do, for the menu's disabled reason and the announcement.
  function describe(delta = last) {
    if (!delta) return "";
    if (delta.kind === "move") return `Moved ${Math.round(delta.dx)} across and ${Math.round(delta.dy)} down.`;
    if (delta.kind === "turn") return `Turned ${Math.round(delta.deg)} degrees.`;
    return `${delta.axis === "w" ? "Width" : "Height"} scaled by ${Math.round(delta.factor * 100)}%.`;
  }

  async function repeat() {
    if (!last) {
      toast("Move, turn or resize something first, then repeat it.", "info");
      return false;
    }
    if (!wbSelectedKeys().size) {
      toast("Select something to repeat the last change on.", "info");
      return false;
    }
    const delta = last;
    replaying = true;
    try {
      if (delta.kind === "move") wbNudgeSelection(delta.dx, delta.dy);
      else if (delta.kind === "turn") await wbTurnSelection(delta.deg);
      else {
        const box = wbFmtBox(wbFmtEntries().filter((e) => !wbIsLocked(e.kind, e.item)));
        const size = box && (delta.axis === "w" ? box.maxX - box.minX : box.maxY - box.minY);
        if (size > 0) await wbRecordGesture(() => wbFmtSizeAxis(delta.axis, Math.max(8, Math.round(size * delta.factor))));
      }
    } finally {
      replaying = false;
    }
    wbScheduleRender();
    wbAnnounce(`Repeated. ${describe(delta)}`);
    return true;
  }

  //: True when the key is for the canvas: a board is open (not a map, whose Home and Delete walk the tree),
  //: no field is being typed in and no list, tab row, menu or the tool rail has the focus (they take Home themselves).
  function forCanvas(e, mapToo = false) {
    const view = document.getElementById("library-view-whiteboard");
    if (!view || view.classList.contains("hidden") || (wbIsMap() && !mapToo)) return false;
    const active = document.activeElement;
    const tag = (active?.tagName || "").toLowerCase();
    if (active && (tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable) && active.offsetParent !== null) return false;
    return !e.target?.closest?.("[role=tablist], [role=listbox], [role=menu], [role=grid], [role=dialog], dialog, #wb-tool-group");
  }

  //: **The keys draw.io has that the board lacked** (WHITEBOARD_PLAN section 11, 2026-11-12). Each command's
  //: own `keys` in `WB_COMMANDS` is the chord, so the palette, the menus and this reader never disagree; a
  //: second chord for a command (`ALSO`) is listed on the help sheet. Taken in the capture phase. draw.io's
  //: Ctrl+Shift+A, E, R and Y stay the app's (Atlas from anywhere, selection actions, record, the companion:
  //: the settings key registry), so select none, select connectors, clear default style and autosize keep no
  //: key, as the plan's table already said for select none (Esc). A key with a meaning of its own when it would do nothing
  //: (Ctrl+R reloads, Ctrl+Shift+Plus zooms) goes on to that meaning unless the command applies.
  const BOUND = ["edit-data", "select-shapes", "turn-90",
    "copy-image", "copy-svg", "copy-size", "paste-size", "copy-data", "paste-data", "clear-waypoints", "enter-group", "font-bigger", "font-smaller",
    "item-link", "edit-tooltip", "comment", "edit-tags"];
  const ALSO = { ungroup: "Ctrl+Shift+U", "leave-group": "Ctrl+Shift+Home" };
  const PASS_WHEN_IDLE = new Set(["turn-90", "font-bigger", "font-smaller", "enter-group", "leave-group", "ungroup"]);
  //: Words in a chord that name a key's code: the rest is a letter.
  const CODES = { Plus: ["Equal", "NumpadAdd"], Minus: ["Minus", "NumpadSubtract"], Home: ["Home"], End: ["End"] };

  function chordMatches(e, chord) {
    const parts = chord.split("+");
    const key = parts.pop();
    const mods = new Set(parts);
    if (Boolean(e.ctrlKey || e.metaKey) !== mods.has("Ctrl") || Boolean(e.altKey) !== mods.has("Alt") || Boolean(e.shiftKey) !== mods.has("Shift")) return false;
    if (CODES[key]) return CODES[key].includes(e.code);
    return e.code ? e.code === `Key${key}` : e.key.toLowerCase() === key.toLowerCase();
  }

  //: The command id this keydown is for, or "".
  function commandFor(e) {
    if (!e.code && !e.key) return "";
    const ids = [...BOUND, ...Object.keys(ALSO)];
    for (const id of ids) {
      const chord = ALSO[id] || WB_COMMAND_BY_ID.get(id)?.keys;
      if (chord && chordMatches(e, chord)) return id;
    }
    return "";
  }

  function boardKey(e) {
    const id = commandFor(e);
    const command = id && WB_COMMAND_BY_ID.get(id);
    if (!command || !forCanvas(e, command.surface === "both") || !wbBoardHasFocus()) return false;
    if (PASS_WHEN_IDLE.has(id) && !wbCommandApplies(command)) return false;
    e.preventDefault();
    e.stopImmediatePropagation();
    wbRunCommand(id);
    return true;
  }

  function onKey(e) {
    if (typeof e.key !== "string") return;
    if ((e.ctrlKey || e.metaKey) && e.altKey && !e.shiftKey && e.key.toLowerCase() === "y" && forCanvas(e)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      repeat();
      return;
    }
    if ((e.ctrlKey || e.metaKey || e.altKey) && boardKey(e)) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const home = e.key === "Home";
    const clear = e.key === "Delete" && e.shiftKey;
    if ((!home && !clear) || !forCanvas(e)) return;
    //: Taken before the board's own Delete (which does not look at Shift) and before the browser's scroll.
    e.preventDefault();
    e.stopImmediatePropagation();
    if (home) go(e.shiftKey);
    else clearLabels();
  }
  window.addEventListener("keydown", onKey, true);

  wbFmtState.keys = { viewAt, home: () => go(false), reset: () => go(true), clearLabels, onKey, record, recordDrag: (primary) => record(dragDelta(primary)), repeat, describe, commandFor, canRepeat: () => Boolean(last) };
})();
