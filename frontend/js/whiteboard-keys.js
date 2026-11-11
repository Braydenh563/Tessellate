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

  //: True when the key is for the canvas: a board is open (not a map, whose Home and Delete walk the tree),
  //: no field is being typed in and no list, tab row or menu has the focus (they take Home themselves).
  function forCanvas(e) {
    const view = document.getElementById("library-view-whiteboard");
    if (!view || view.classList.contains("hidden") || wbIsMap()) return false;
    const active = document.activeElement;
    const tag = (active?.tagName || "").toLowerCase();
    if (active && (tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable) && active.offsetParent !== null) return false;
    return !e.target?.closest?.("[role=tablist], [role=listbox], [role=menu], [role=grid], [role=dialog], dialog");
  }

  function onKey(e) {
    if (typeof e.key !== "string" || e.ctrlKey || e.metaKey || e.altKey) return;
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

  wbFmtState.keys = { viewAt, home: () => go(false), reset: () => go(true), clearLabels, onKey };
})();
