(() => {
  // whiteboard-bar.js: the selection bar and context strip over a map or board.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  // --- maps -------------------------------------------------------------------
  // The mind map layer (a board with a real tree on it, MINDMAP_PLAN.md §5) is
  // in whiteboard-map.js, which the Library bundle loads before this file. See
  // its header.

  function wbApplySelectionHighlight() {
    //: The elements marked so far, kept on the function (no new global). The class is written nowhere
    //: else, so this is what the page would be asked for with a `querySelectorAll` (1.2 ms a render).
    const marked = (wbApplySelectionHighlight.marked ??= new Set());
    //: After this frame's selection is settled (see `renderWbGestureHints`).
    requestAnimationFrame(renderWbGestureHints);
    //: **Only what changed is touched** (INBOX 410, the release of a marquee).
    //: This took the class off every selected element and put it back on every
    //: one still selected, so a sweep that grew a selection of 200 restyled all
    //: 200 twice. The wanted set is worked out first; then an element loses the
    //: class only if it is leaving and gains it only if it is arriving.
    const inGroup = wbMultiSelection.size > 1;
    const wanted = new Map();
    for (const key of wbMultiSelection) {
      const sep = key.indexOf(":");
      const el = document.querySelector(WB_SELECTOR_BY_KIND[key.slice(0, sep)](Number(key.slice(sep + 1))));
      if (el) wanted.set(el, inGroup);
    }
    if (wbSelectedItem) {
      const el = document.querySelector(WB_SELECTOR_BY_KIND[wbSelectedItem.kind](wbSelectedItem.id));
      if (el && !wanted.has(el)) wanted.set(el, false);
    }
    //: One that left the page (a render's exit) is not wanted either, so it is dropped here too.
    for (const el of marked) {
      if (!wanted.has(el)) el.classList.remove("wb-selected", "wb-in-group");
      if (!wanted.has(el)) marked.delete(el);
    }
    // A sketch's resize handles have nowhere else to live between renders
    // (unlike a card/object, which always has 8 handle children of its own), 
    // recomputed here so they track a fresh selection or a just-finished move.
    // Only for the single-item selection, a multi-selection has no one
    // bounding box to hang 8 handles off, and resizing a set isn't built.
    wbRenderSketchHandles();
    //: And the box round a sweep that caught more than one thing, which is the
    //: same affordance for the same gesture (see `wbRenderMultiSelectionHandles`).
    wbRenderMultiSelectionHandles();
    wbRenderCloneGrips();
    wbUpdateContextBar();
    // The map dock's own buttons act on the selected topic, so they follow the
    // selection for the same reason the properties panel above does.
    wbSyncMapToolState();
    //: And the waypoint handle on the selected topic's own lines, which is the
    //: other control that follows the selection without a re-render.
    wbSyncMapEdgeHandles();
    //: The dimmed rest follows the selected branch.
    if (typeof wbMapDim !== "undefined" && wbMapDim.on) wbMapPaintMarkerFilter();
    //: A card and a text box keep their eight handles and their rotate grip as
    //: children, revealed by `.wb-selected`, so a *group* member is marked a
    //: second way and 07-whiteboard-misc.css hides the grips on that class. The
    //: outline stays: the member is still visibly one of the selected things
    //: (INBOX 278, and the earlier report it has to keep answering).
    for (const [el, grouped] of wanted) {
      if (!grouped) wbEnsureHandles(el);
      //: A topic's resize grip is made when it is first selected or pointed at (`wbMapCache.part`).
      if (el.classList.contains("wb-map-node")) wbMapCache.part(el, "grip");
      marked.add(el);
      if (!el.classList.contains("wb-selected")) el.classList.add("wb-selected");
      if (el.classList.contains("wb-in-group") !== grouped) el.classList.toggle("wb-in-group", grouped);
    }
  }

  //: Never moves focus: a map add (`wbMapAddChild`) opens the new topic's editor
  //: first and selects it after, so a focus here would take the typing away.
  function selectWbItem(kind, id) {
    if (kind !== "node" || id !== wbAddGate.cardRetypeId) wbAddGate.cardRetypeId = null;
    wbSelectedItem = { kind, id };
    //: Choosing a topic, by pointer, arrow, new map or a topic just made, is
    //: working in the map, so Tab adds under it (see `wbMapKeysArmed`).
    if (wbIsMap()) wbMapKeysArmed = true;
    wbApplySelectionHighlight();
    //: **The chrome that depends on the selection, updated where the selection
    //: changes.** Both of these used to wait for the next render or the next
    //: pan frame, which is why the map dock's own controls were re-synced by
    //: hand at half a dozen call sites and why the node edit strip would
    //: otherwise appear a frame late (or not at all, for a selection made
    //: without a render behind it: `wbHandleItemClick` ends here and renders
    //: nothing). One call site rather than every caller remembering two.
    wbSyncMapToolState();
    wbUpdateSelectionBar();
    wbQueueReveal();
  }

  //: Select everything on the board (Edit → Select all, Ctrl+A on the
  //: canvas), connectors too (L-whiteboard-21).
  function wbSelectAllItems() {
    wbSelectExactly(wbSelectableItems());
  }

  //: The selection becomes exactly these `[kind, item]` pairs.
  function wbSelectExactly(pairs) {
    wbSelectedItem = null;
    wbMultiSelection.clear();
    for (const [kind, item] of pairs) wbMultiSelection.add(wbMultiKey(kind, item.id));
    wbApplySelectionHighlight();
    wbUpdateContextBar();
    wbUpdateSelectionBar();
  }

  //: draw.io's "Select vertices" and "Select edges": every closed shape, text
  //: box, note and picture (never a line, a pen stroke or a connector), or
  //: every connector. A locked or hidden item is out of reach, as in Select all.
  function wbSelectAllOfKind(which) {
    // `wbSketchParsedData` is for a drawn path and answers null for a link.
    const connector = (sk) => {
      try {
        return String(JSON.parse(sk.data)?.type || "").startsWith("link-");
      } catch {
        return false;
      }
    };
    const pairs = which === "connectors"
      ? (wbState.sketches || []).filter((sk) => connector(sk) && !wbIsLocked("sketch", sk) && !wbSketchHiddenOnBoard(sk)).map((sk) => ["sketch", sk])
      : wbSelectableItems().filter(([kind, item]) => kind !== "sketch" || wbFmtKind({ kind, item }) === "shape");
    if (!pairs.length) {
      toast(which === "connectors" ? "No connectors on this board." : "No shapes on this board.");
      return;
    }
    wbSelectExactly(pairs);
    wbAnnounce(`${pairs.length} ${which === "connectors" ? "connectors" : "shapes"} selected.`);
  }

  //: "Select similar" (Excalidraw and Miro both have it, draw.io only by
  //: style): every item of the same kind with the same fill and line colour as
  //: the first one selected, so a board's blue shapes can be recoloured at once.
  function wbSelectSimilar() {
    const [ref] = wbFmtEntries();
    if (!ref) {
      toast("Select an item first.");
      return;
    }
    const kind = wbFmtKind(ref);
    const same = (entry) => wbFmtKind(entry) === kind
      && wbFmtValue(entry, "fill") === wbFmtValue(ref, "fill") && wbFmtValue(entry, "stroke") === wbFmtValue(ref, "stroke");
    const pairs = wbSelectableItems().filter(([k, item]) => same({ kind: k, id: item.id, item }));
    if (pairs.length < 2) {
      toast("Nothing else looks like it.");
      return;
    }
    wbSelectExactly(pairs);
    wbAnnounce(`${pairs.length} similar items selected.`);
  }

  //: Everything a selection can hold: what a link can join, plus pictures.
  //: Select all read `wbLinkCandidates`, which leaves an image object out
  //: because a link cannot land on one, so Ctrl+A then Delete left every
  //: picture on the board (INBOX 445).
  function wbSelectableItems() {
    const out = wbLinkCandidates();
    for (const o of wbState.objects || []) if (o.kind === "image" || o.kind === "frame" || o.kind === "diagram") out.push(["object", o]);
    //: A board's connectors (L-whiteboard-21: Select all and the Tab walk skipped them); a map's cross-link has no box of its own.
    for (const sk of wbState.sketches || []) if (wbIsLinkSketch(sk) && wbLinkSelectionBox(sk)) out.push(["sketch", sk]);
    //: A locked item is out of reach until it is unlocked (decision 15): not
    //: in Select all, not in the Tab walk.
    return out.filter(([kind, item]) => !wbIsLocked(kind, item) && !wbHiddenOnBoard(kind, item) && !wbFmtState.isolate?.outside(kind, item) /* L-whiteboard-7: dimmed outside an open group */);
  }

  //: **Tab walks the board's items, and the board says which one** (INBOX
  //: 445). Nothing on a board could be reached from the keyboard: an item was
  //: selected by pointing at it or not at all, and a shape is an SVG path no
  //: screen reader names. With the canvas focused, Tab and Shift+Tab select
  //: the next or previous item in reading order (rows top to bottom, then left
  //: to right), bring it on screen when it is off it, and announce it in
  //: `#wb-announcer`; past the last item Tab leaves the canvas as it would any
  //: other control, so the walk is never a trap (WCAG 2.1.2). A map keeps its
  //: own keys: Tab adds a topic there, and the arrows walk the tree.
  const WB_SHAPE_NAMES = {
    rect: "Rectangle", circle: "Ellipse", triangle: "Triangle", diamond: "Diamond",
    line: "Line", arrow: "Arrow", draw: "Pen stroke", highlighter: "Highlighter stroke",
  };

  function wbItemSpokenName(kind, item) {
    if (kind === "sketch" && wbIsLinkSketch(item)) {
      let label = "";
      try {
        label = String(JSON.parse(item.data)?.label || "").slice(0, 60);
      } catch {
        /* a damaged connector is still a connector */
      }
      return label ? `Connector: ${label}` : "Connector";
    }
    if (kind === "sketch") {
      const parsed = wbSketchParsedData(item);
      return WB_SHAPE_NAMES[parsed?.shape] || "Drawing";
    }
    if (kind === "node") {
      const entry = (typeof allEntries !== "undefined" ? allEntries : []).find((e) => String(e.id) === String(item.entry_id));
      //: Plain words, not the note's markdown: a layer row read "**Current Commit..." (INBOX 820).
      const title = entry ? noteNamePlain(entry.content, 60) : "";
      return title ? `Note card: ${title}` : "Note card";
    }
    if (item.kind === "image") return "Picture";
    if (item.kind === "diagram") return "Mermaid diagram";
    if (item.kind === "frame") return `Frame: ${wbFrameTitle(item)}`;
    const isTopic = WB_MAP_KINDS.has(item.kind);
    const raw = isTopic ? wbMapLabel(item) : item.data?.content;
    const text = noteNamePlain(raw, 60);
    const what = isTopic ? "Topic" : item.data?.bg ? "Sticky note" : "Text box";
    return text ? `${what}: ${text}` : what;
  }

  function wbAnnounce(text) {
    const el = document.getElementById("wb-announcer");
    if (!el) return;
    // Emptied first, so the same words twice (two stickies saying "Idea") are
    // still read twice.
    el.textContent = "";
    requestAnimationFrame(() => {
      el.textContent = text;
    });
  }

  function wbWalkItems(dir) {
    const rowOf = (box) => Math.round(box.minY / 60);
    const items = wbSelectableItems()
      .map(([kind, item]) => ({ kind, item, box: wbItemBBox(kind, item) || (kind === "sketch" ? wbLinkSelectionBox(item) : null) }))
      .filter((e) => e.box)
      .sort((a, b) => rowOf(a.box) - rowOf(b.box) || a.box.minX - b.box.minX || a.box.minY - b.box.minY);
    if (!items.length) return false;
    const at = wbSelectedItem
      ? items.findIndex((e) => e.kind === wbSelectedItem.kind && e.item.id === wbSelectedItem.id)
      : -1;
    const next = at === -1 ? (dir > 0 ? 0 : items.length - 1) : at + dir;
    if (next < 0 || next >= items.length) return false;
    const { kind, item, box } = items[next];
    wbMultiSelection.clear();
    selectWbItem(kind, item.id);
    const container = document.getElementById("whiteboard-container");
    if (container) {
      const t = d3.zoomTransform(container);
      const view = container.getBoundingClientRect();
      const left = box.minX * t.k + t.x;
      const top = box.minY * t.k + t.y;
      const right = box.maxX * t.k + t.x;
      const bottom = box.maxY * t.k + t.y;
      if (left < 0 || top < 0 || right > view.width || bottom > view.height) {
        wbCenterOn(box, { animate: !reducedMotionWanted() });
      }
    }
    //: Name and place only (1031 BD9: "Text box: Card 3, 4 of 362, selected" said
    //: the selection twice), and the board's active descendant is the item, so a
    //: screen reader has an object rather than only a region.
    const lock = wbIsLocked(kind, item) ? ", locked" : "";
    wbAnnounce(`${wbItemSpokenName(kind, item)}${lock}, ${next + 1} of ${items.length}`);
    const el = document.querySelector(WB_SELECTOR_BY_KIND[kind]?.(item.id) || "#none");
    if (el && container) {
      el.id ||= `wb-item-${kind}-${item.id}`;
      container.setAttribute("aria-activedescendant", el.id);
    }
    return true;
  }

  function clearWbSelection() {
    wbAddGate.cardRetypeId = null;
    //: Deselecting clears every overlay, the link tool's dots included (INBOX 573).
    if (!wbLinkDragActive) wbClearAnchorHints();
    wbRevealSig = ""; // choosing the same item again is a new selection to keep clear of the docks
    if (!wbSelectedItem && wbMultiSelection.size === 0) return;
    wbSelectedItem = null;
    wbMultiSelection.clear();
    document.getElementById("whiteboard-container")?.removeAttribute("aria-activedescendant");
    wbApplySelectionHighlight();
    wbSyncMapToolState();
    wbUpdateSelectionBar();
  }

  //: **A selection never outlives its items.** Undo of a paste, a redo of a
  //: delete, another tab's change or the history panel can take away what is
  //: selected without a deselect behind it; the board kept the dead id, and
  //: Export > Selection then threw "Cannot read properties of undefined
  //: (reading 'width')" and wrote nothing, with a selection bar over nothing.
  //: Run at the top of every render, so no path has to remember it.
  function wbPruneSelection() {
    let changed = false;
    if (wbSelectedItem && !wbFindItem(wbSelectedItem.kind, wbSelectedItem.id)) {
      wbSelectedItem = null;
      changed = true;
    }
    for (const key of [...wbMultiSelection]) {
      const at = key.indexOf(":");
      const list = wbState[WB_LIST_BY_KIND[key.slice(0, at)]] || [];
      if (!list.some((i) => String(i.id) === key.slice(at + 1))) {
        wbMultiSelection.delete(key);
        changed = true;
      }
    }
    if (!changed) return;
    wbApplySelectionHighlight();
    wbSyncMapToolState();
    wbUpdateSelectionBar();
  }

  //: **Where the context bar goes.** Above the selection, in the view's own
  //: coordinates, from the item's board bbox through the live zoom transform,
  //: re-placed on every render and every pan/zoom frame. What it *contains* is
  //: `wbUpdateContextBar`'s job; this only decides the two numbers.
  //:
  //: One more case than the bar it replaced: with nothing selected and a
  //: drawing tool held, the bar carries that tool's own settings and has no
  //: selection to sit above, so it sits centred just over the tool rail, which
  //: is where the thing it is about is. Excalidraw and tldraw both park the
  //: style panel against the rail for the same reason.
  //: The app's phone band, held once rather than asked per frame: this is read
  //: from `wbUpdateSelectionBar`, which runs on every pan and zoom frame. A
  //: `MediaQueryList` keeps itself current across a resize, so there is nothing
  //: to invalidate.
  const WB_PHONE = window.matchMedia("(max-width: 599.98px)");

  //: **The strip's three doors, opened and closed from here** (MINDMAP_PLAN
  //: §13b). Text, Shape and Branch line are `.wb-board-menu-wrap`s like the top
  //: bar's five, so opening, the outside click, Escape and the arrow keys are
  //: all the board menus' own wiring and there is no second popover here. What
  //: that wiring has no way to know is that this bar *moves*: it is placed on
  //: the selected topic and re-placed on every pan and zoom frame, and a menu
  //: that `escapeAndCapMenu` has parked in the window's own coordinates would
  //: otherwise stay where the topic used to be. So the open door is re-placed
  //: with the bar, and every door is shut when the bar goes away or when the
  //: selection moves to another topic, which is the one case where a menu about
  //: the old topic would still be on screen over the new one.
  function wbMapStripToggles() {
    const strip = document.getElementById("wb-map-strip");
    if (!strip) return [];
    const out = [];
    for (const toggle of strip.querySelectorAll("[data-wb-menu-toggle]")) {
      const menu = document.getElementById(toggle.getAttribute("aria-controls") || "");
      if (menu) out.push({ toggle, menu });
    }
    return out;
  }

  function wbCloseMapStripMenus() {
    for (const { toggle, menu } of wbMapStripToggles()) {
      if (menu.classList.contains("hidden")) continue;
      menu.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
      //: Back inside its wrap and off the inline cap, the same two steps the
      //: top bar's own close takes: a menu left escaped is a menu the next
      //: `wrap.querySelector` cannot find.
      restoreEscapedMenu(menu);
      menu.style.maxHeight = "";
    }
  }

  function wbTrackMapStripMenu() {
    for (const { toggle, menu } of wbMapStripToggles()) {
      if (menu.classList.contains("hidden")) continue;
      escapeAndCapMenu(menu, toggle);
      wbMapStripMenuOffTopic(menu, toggle);
    }
  }

  //: **A door never opens on the topic it edits** (INBOX 814, the owner: "when
  //: I change stuff in the tools for a mindmap node, I cant actually see what
  //: the difference is until I click off it"). Measured at 1440x560, 390x844
  //: and 1440x420 (`scratchpad/ui-sweeps/mapfixmenu.js`): the strip sits above
  //: a topic that has room above it, the door hangs under the strip, and a
  //: topic in the middle of the canvas is under a 336px by 210px door, so a
  //: change painted at once and was covered at once. The door is moved to the
  //: first place that has room, in this order: where it already is, above the
  //: strip, beside the topic (right, then left), under the topic, over it.
  //: When none is clear it takes the one that covers least. The topic's own
  //: buttons (+ and link) count as the topic, since they hang off it.
  function wbMapStripMenuOffTopic(menu, toggle) {
    const el = wbMapStripNodeId != null && document.querySelector(`.wb-object[data-id="${wbMapStripNodeId}"]`);
    if (!el) return;
    //: Back to its natural place first when an earlier frame moved it, so the
    //: door follows the bar on a pan and the answer is never stale.
    if (menu.classList.contains("action-menu-escaped")) {
      menu.style.maxHeight = "none";
      placeEscapedMenu(menu, toggle);
      const at = menu.getBoundingClientRect().top;
      menu.style.maxHeight = `${Math.max(120, Math.round(window.innerHeight - at - 8))}px`;
    }
    const rects = [el.getBoundingClientRect()];
    const actions = el.querySelector(".wb-map-actions");
    if (actions) rects.push(actions.getBoundingClientRect());
    const pad = 6;
    const T = {
      left: Math.min(...rects.map((r) => r.left)) - pad,
      top: Math.min(...rects.map((r) => r.top)) - pad,
      right: Math.max(...rects.map((r) => r.right)) + pad,
      bottom: Math.max(...rects.map((r) => r.bottom)) + pad,
    };
    const area = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
      * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    const rectAt = (left, top, w, h) => ({ left, top, right: left + w, bottom: top + h });
    const box = menu.getBoundingClientRect();
    if (!box.width || !area(rectAt(box.left, box.top, box.width, box.height), T)) return;
    const stripRect = document.getElementById("wb-map-strip").getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const m = 8;
    const w = box.width;
    const natural = menu.scrollHeight || box.height;
    const clampLeft = (x) => Math.max(m, Math.min(x, vw - m - w));
    const clampTop = (y, h) => Math.max(m, Math.min(y, vh - m - h));
    const spots = [
      [box.left, stripRect.top - 4 - natural],
      [T.right + m, T.top],
      [T.left - m - w, T.top],
      [box.left, T.bottom + m],
      [box.left, T.top - m - natural],
    ];
    let best = null;
    for (const [x, y] of spots) {
      const left = clampLeft(x);
      const room = vh - m - Math.max(m, y);
      const h = Math.min(natural, room);
      const top = clampTop(y, h);
      const r = rectAt(left, top, w, h);
      const covered = area(r, T);
      //: A spot that needed the cap to fit is worse than one that did not.
      const score = covered * 1000 + area(r, stripRect) + (h < natural ? (natural - h) * 4 : 0);
      if (!best || score < best.score) best = { score, left, top, h, covered };
      if (!covered && h >= natural && !area(r, stripRect)) break;
    }
    if (!best) return;
    escapeMenuToBody(menu, toggle);
    menu.classList.add("action-menu-escaped");
    menu.classList.remove("action-menu-flip");
    menu.style.left = `${Math.round(best.left)}px`;
    menu.style.top = `${Math.round(best.top)}px`;
    menu.style.maxHeight = `${Math.max(120, Math.round(best.h))}px`;
  }

  //: Which topic the strip is currently describing, so a move of the selection
  //: can be told from the sixty frames a pan asks about the same topic.
  let wbMapStripNodeId = null;



  function wbQueueSelectionBar() {
    if (wbSelectionBarFrame) return;
    wbSelectionBarFrame = requestAnimationFrame(() => {
      wbSelectionBarFrame = 0;
      wbUpdateSelectionBar();
      wbPaintCommentMarks();
      wbLayoutCloneGrips();
      if (wbIsMap()) wbRenderMapStructure();
    });
  }

  //: **The strip keeps off the handle of the line into its own topic**
  //: (MINDMAP_PLAN §13b's remainder). §12.1 found the strip on that handle once
  //: and §13b took the strip to a third of its width without measuring it
  //: again; `mapstripcover.js` then found 4 of 48 handles still under it at
  //: 1440 (a radial map's inner rings, and a tree's last branch, whose line
  //: bends up into the strip's band). The handle is the only way to bend that
  //: line, so a strip over it takes the gesture away while it is the topic
  //: being styled.
  //:
  //: Tried in order, and the first that leaves the handle uncovered wins: the
  //: place already chosen, the same height slid clear to the handle's left,
  //: then to its right, then under the topic. If none fits (a very narrow
  //: canvas), the first place stands: covering is then the lesser cost, since
  //: the strip is what was asked for. One rect read, and not during a drag
  //: (`held`), where nothing about the line changes against the bar.
  function wbMapStripClearOfHandle(node, { left, y, w, h, hostRect, gapBelow, bottom, minY, maxY }) {
    const handle = node && document.querySelector(`.wb-map-edges .wb-map-edge-handle[data-child="${node.id}"]`);
    if (!handle) return [left, y];
    const hb = handle.getBoundingClientRect();
    if (!hb.width) return [left, y];
    const margin = 6;
    const hx0 = hb.left - hostRect.left - margin;
    const hx1 = hb.right - hostRect.left + margin;
    const hy0 = hb.top - hostRect.top - margin;
    const hy1 = hb.bottom - hostRect.top + margin;
    const covers = (x, top) => x < hx1 && x + w > hx0 && top < hy1 && top + h > hy0;
    if (!covers(left, y)) return [left, y];
    const maxX = hostRect.width - w - 8;
    const under = Math.min(Math.max(bottom + gapBelow, minY), maxY);
    const candidates = [
      [hx0 - w, y],
      [hx1, y],
      [left, under],
      //: Below the handle itself: a line that comes in under the topic's own row
      //: (a short label at 820 wide, where the sides have no room for 412px).
      [left, hy1],
    ];
    for (const [x, top] of candidates) {
      if (x < 8 || x > maxX || top > maxY) continue;
      if (!covers(x, top)) return [x, top];
    }
    return [left, y];
  }

  //: **A selected connector's box, for the bar to sit over** (found with
  //: Phase B, 2026-10-05). A link has no path of its own (`wbItemBBox` is null
  //: for it), so the bar measured nothing and hid: the connector row (its
  //: colour, width, ends, pattern and now its line shape) had never been on
  //: screen for anyone. The box round its two ends and its bends.
  function wbLinkSelectionBox(sketch) {
    let parsed = null;
    try {
      parsed = JSON.parse(sketch.data);
    } catch {
      return null;
    }
    //: A map's cross-link has the map's ring, never the board's bar
    //: (`maptwokinds.js`): only a board connector (`wbLinkTakesLabel`) earns one.
    if (!String(parsed?.type || "").startsWith("link-") || !wbLinkTakesLabel(sketch, parsed)) return null;
    const ends = wbResolveLinkEndpoints(parsed);
    if (!ends) return null;
    const pts = [ends.source, ends.target, ...(Array.isArray(parsed.points) ? parsed.points : [])];
    return {
      minX: Math.min(...pts.map((p) => p.x)), minY: Math.min(...pts.map((p) => p.y)),
      maxX: Math.max(...pts.map((p) => p.x)), maxY: Math.max(...pts.map((p) => p.y)),
    };
  }

  //: Where the selection bar may sit across the board's host, in its own
  //: units: inside 8px of either edge, and clear of whichever side panel is
  //: showing.
  function wbBarSideEdges(hostRect) {
    let left = 8, right = hostRect.width - 8;
    const side = document.getElementById("wb-sidebar");
    if (side && side.offsetParent !== null) left = Math.max(left, side.getBoundingClientRect().right - hostRect.left + 8);
    const format = document.getElementById("wb-format");
    if (format && !format.classList.contains("hidden")) right = Math.min(right, format.getBoundingClientRect().left - hostRect.left - 8);
    //: A board too narrow for both (a phone with a panel open) keeps the bar
    //: on the board rather than squeezing it to nothing.
    if (right - left < 160) return { left: 8, right: hostRect.width - 8 };
    return { left, right };
  }

  //: **What a render may leave until the new topic's editor is open**
  //: (FEAT-02's 100ms gate): the transforms of the topics that only moved, and
  //: the lines. Opening the editor focuses it, which makes the browser bring
  //: every pending style up to date first; with a tidy's two hundred moves and
  //: three hundred lines pending, that was 37 to 86ms (traced, 1,550 elements)
  //: between the key and a topic you can type in. Written right after the
  //: editor opens, in the same task, so the first frame painted shows all of
  //: it; only the order of the work changes. `wbRenderRelease` writes them.

  function wbRenderRelease() {
    const held = wbAddGate.renderHold;
    wbAddGate.renderHold = null;
    if (!held) return;
    for (const [el, place] of held.moves) el.style.transform = place;
    if (held.edges) {
      wbRenderMapEdges();
      wbRenderMapStructure();
    }
  }

  //: **Set while an add opens its topic for typing** (FEAT-02's 100ms gate):
  //: the bar's placement reads layout, and read in the middle of the add it
  //: restyled the whole moved map before the editor could open (traced: 33 to
  //: 60ms, 2,100 elements, on every Tab at 301 topics). Placed two frames on
  //: instead, after the editor, from the same selection.

  //: **A bar that would wrap folds its least-used groups into More** (the
  //: wb ledger, 10-25: two rows at 720, where the controls are 44px for a
  //: finger). draw.io and Figma do the same: the row stays one row, and the
  //: order pair, the dash pattern and the arrange runs (last first) move into
  //: the "..." menu's own section, the same controls with the same handlers.
  //: Every placement puts them back first, so a wider window or a smaller
  //: selection gets them on the bar again.
  //: The groups a wrapped bar folds into More, first to last. Fill and text go
  //: last: they are what a shape or a text box is selected for, but a phone's
  //: text bar was four rows tall without them (INBOX 1354, 198px at 390).
  const WB_CTX_FOLD = { order: ["order", "stroke", "arrange", "caps", "route", "fill", "text"], home: new Map(), sig: null, size: null };

  function wbFoldContextBar(bar) {
    const menu = document.getElementById("wb-context-menu");
    const more = wbContextMoreWrap();
    if (!menu || !more) return;
    let shelf = document.getElementById("wb-context-overflow");
    if (shelf) {
      //: Back where each was: its old neighbour, or that one's, when the
      //: neighbour was folded too.
      for (const g of [...shelf.children].reverse()) {
        let ref = WB_CTX_FOLD.home.get(g);
        while (ref && ref.parentElement !== bar) ref = WB_CTX_FOLD.home.get(ref);
        bar.insertBefore(g, ref || more.closest(".wb-context-group"));
      }
      shelf.classList.add("hidden");
    }
    if (bar.offsetHeight <= 60 || more.classList.contains("hidden")) return;
    if (!shelf) {
      shelf = document.createElement("div");
      shelf.id = "wb-context-overflow";
      shelf.className = "wb-menu-section wb-context-overflow";
      shelf.setAttribute("role", "group");
      shelf.setAttribute("aria-label", "More controls for this selection");
      menu.insertBefore(shelf, menu.firstChild);
    }
    const candidates = WB_CTX_FOLD.order.flatMap((name) =>
      [...bar.querySelectorAll(`:scope > .wb-context-group[data-wb-ctx="${name}"]:not(.hidden)`)].reverse());
    const fold = (g) => {
      WB_CTX_FOLD.home.set(g, g.nextElementSibling);
      shelf.insertBefore(g, shelf.firstChild);
      shelf.classList.remove("hidden");
    };
    //: **Planned from one measurement, then checked once** (the owner,
    //: 10-26: "make everything lightweight"). Reading the bar's height after
    //: every move was one layout per folded group: 31 ms of a 63 ms bar open at
    //: 390. The plan folds what the widths say must go; the loop after it only
    //: runs when a group that wrapped inside itself made the plan short.
    const planned = wbFoldPlan(bar, candidates);
    planned.forEach(fold);
    for (const g of candidates.slice(planned.length)) {
      if (bar.offsetHeight <= 60) return;
      fold(g);
    }
  }

  //: The leading run of `candidates` that has to leave for the rest of the bar
  //: to fit one row, from one read of every width (no layout between reads).
  function wbFoldPlan(bar, candidates) {
    const cs = getComputedStyle(bar);
    const room = bar.clientWidth - wbNum(cs.paddingLeft) - wbNum(cs.paddingRight);
    const gap = wbNum(cs.columnGap);
    const span = (el) => {
      const st = getComputedStyle(el);
      return el.getBoundingClientRect().width + wbNum(st.marginLeft) + wbNum(st.marginRight) + gap;
    };
    const shown = [...bar.children].filter((el) => !el.classList.contains("hidden") && el.getClientRects().length);
    let need = shown.reduce((sum, el) => sum + span(el), -gap);
    const out = [];
    for (const g of candidates) {
      if (need <= room) break;
      need -= span(g);
      out.push(g);
    }
    return out;
  }

  //: What a pan keeps of the selection bar's measurements: a pan moves the
  //: canvas, not the bar, the host or the top bar, so one measure serves every
  //: frame until the pan ends (a zoom frame asks the same). Cleared by any
  //: placement that is not a pan frame, and at the pan's end, which then places
  //: the bar once more with real measurements.
  function wbUpdateSelectionBar(panning = false) {
    if (!panning) wbAddGate.panBarHold = null;
    if (wbAddGate.barDeferred) {
      if (!wbAddGate.barDeferredQueued) {
        wbAddGate.barDeferredQueued = true;
        requestAnimationFrame(() => {
          wbAddGate.barDeferredQueued = false;
          wbQueueSelectionBar();
        });
      }
      return;
    }
    //: A direct placement makes a queued one redundant: it would place the bar
    //: from the same state a frame later.
    if (wbSelectionBarFrame) {
      cancelAnimationFrame(wbSelectionBarFrame);
      wbSelectionBarFrame = 0;
    }
    const bar = document.getElementById("wb-context");
    if (!bar) return;
    const sel = wbSelectedItem;
    // `> 0`, not `> 1`: `wbUpdateContextBar` fills the bar for a selection of
    // one shift-clicked item and this hid it again, so that selection had an
    // arrange row nobody could see. `wbSelectionBounds` is happy with one.
    const multi = wbMultiSelection.size > 0;
    const container = document.getElementById("whiteboard-container");
    const host = document.getElementById("library-view-whiteboard");
    //: **A map node gets the map's own strip, in the board bar's place**
    //: (MINDMAP_PLAN.md §12.1 item 2). One bar above a node, never two: two
    //: absolutely-positioned bars computed from the same box is exactly how
    //: they come to overlap, and this file has already paid for that twice
    //: (see `.wb-map-count`). The board's bar offers duplicate, copy style and
    //: the z-order pair, none of which a topic in a tree has a use for, and
    //: the strip offers how the topic reads and what it points at, which is
    //: what the whiteboard has no equivalent of. Everything below places
    //: whichever of the two this selection earns; `other` is hidden every time
    //: so switching between a card and a topic cannot leave one behind.
    const strip = document.getElementById("wb-map-strip");
    const mapNode = wbMultiSelection.size > 1 ? null : wbSelectedMapNode();
    const active = mapNode ? strip : bar;
    const hideBoth = () => {
      bar.classList.add("hidden");
      if (strip && !strip.classList.contains("hidden")) wbCloseMapStripMenus();
      strip?.classList.add("hidden");
      wbMapStripNodeId = null;
      delete bar.dataset.wbAnchor;
    };
    if (!container || !host || wbLinkDragActive || !active) {
      hideBoth();
      return;
    }
    //: **The ring and the strip are never open at once** (MINDMAP_PLAN §12.5).
    //: They answer two different questions about the same topic, "what do I do
    //: with this" and "how should it look", and both of them are placed from
    //: the node's own box: what that produced was a strip shoved 136px clear of
    //: the ring, or drawn across it (INBOX 114). One at a time is the honest
    //: shape, and it costs nothing, the ring closes on the next click and the
    //: strip is back.
    if (mapNode && wbMapRadialFor === mapNode.id) {
      hideBoth();
      return;
    }
    if (!sel && !multi) {
      // Nothing selected. The bar may still be open on a held drawing tool, in
      // which case it is anchored to the rail and `wbUpdateContextBar` placed
      // it; leave it exactly where it is. This branch is the hot one: it runs on
      // every frame of every pan, which is why it does no work and asks no
      // question the DOM has to be walked to answer.
      if (bar.dataset.wbAnchor === "rail") {
        strip?.classList.add("hidden");
        return;
      }
      hideBoth();
      return;
    }
    delete bar.dataset.wbAnchor;
    // **The document-wide query runs last, not first.** This function is called
    // from the pan/zoom frame (`handleWbZoom`), so it runs at up to 60 Hz while
    // someone drags the canvas, and `querySelector(".wb-object.wb-text-editing")`
    // walks the whole document every time even though nothing is selected, which
    // is the common case during a pan. Measured on a 201-node map, 60 frames of
    // a drag pan: 0.46ms per call before this reorder against 0.013ms for the
    // grid sync and 0.02ms for the navigator beside it. The four checks above
    // are all constant-time and one of them is true whenever nothing is
    // selected, so putting them first skips the walk entirely.
    //: Asked of the board, not the document (INBOX 424a): every `.wb-object`
    //: lives in the container, and a drag places this bar once a frame, so a
    //: walk of the whole page's 49,000 nodes each time was the largest cost
    //: left on the drag after the element cache above.
    const panSig = `${active.id}:${sel ? `${sel.kind}:${sel.id}` : `multi${wbMultiSelection.size}`}`;
    const panHeld = panning && wbAddGate.panBarHold?.sig === panSig ? wbAddGate.panBarHold : null;
    if (!panHeld && container.querySelector(".wb-object.wb-text-editing")) {
      hideBoth();
      return;
    }
    // A multi-selection gets the bar above the whole group, that is where
    // Arrange's align/distribute and Export "just the selection" matter.
    let box = panHeld ? panHeld.box : null;
    const moving = multi ? wbBulkBarBounds : null;
    //: A pan moves the canvas, not the selection, so its box in board space is
    //: the one the first pan frame measured. Measuring it again reads the
    //: topic's rendered size (`wbItemBBox`: offsetWidth), which lays the whole
    //: board out once per frame: 940 ms a frame on a 120-topic map at a 4x
    //: throttle, measured 2026-10-12.
    if (!panHeld && multi) {
      const b = moving
        ? { ...moving.box, minX: moving.box.minX + moving.dx, minY: moving.box.minY + moving.dy }
        : wbSelectionBounds();
      if (b) box = { minX: b.minX, minY: b.minY, maxX: b.minX + b.width, maxY: b.minY + b.height };
    } else if (!panHeld) {
      const item = (wbState[WB_LIST_BY_KIND[sel.kind]] || []).find((i) => i.id === sel.id);
      box = item ? wbItemBBox(sel.kind, item) || (sel.kind === "sketch" ? wbLinkSelectionBox(item) : null) : null;
    }
    if (!box) {
      hideBoth();
      return;
    }
    const t = d3.zoomTransform(container);
    //: During a group drag nothing measured below can change: the drag moves
    //: the items, not the canvas, the host, the top bar or the bar itself. So
    //: the first frame measures and the rest reuse it, and no frame of the
    //: drag forces a layout here (`wbBulkBarBounds`, INBOX 445).
    const held = moving?.origin?.barMeasure || panHeld || null;
    const rect = held ? held.rect : container.getBoundingClientRect();
    const hostRect = held ? held.hostRect : host.getBoundingClientRect();
    const cx = rect.left - hostRect.left + t.applyX((box.minX + box.maxX) / 2);
    const top = rect.top - hostRect.top + t.applyY(box.minY);
    const bottom = rect.top - hostRect.top + t.applyY(box.maxY);
    (mapNode ? bar : strip)?.classList.add("hidden");
    // Filled before it is measured: the strip's controls take their values from
    // the node, and a select whose value changed is a different width, so
    // reading `offsetWidth` first would centre the bar on last node's size.
    if (mapNode && mapNode.id !== wbMapStripNodeId) {
      //: The selection moved to another topic: shut the doors before the bar is
      //: filled from the new one, or a menu about the topic just left is still
      //: open over the topic just chosen, writing to neither predictably.
      wbCloseMapStripMenus();
      wbMapStripNodeId = mapNode.id;
    }
    if (!mapNode) wbMapStripNodeId = null;
    if (mapNode && !panHeld) wbSyncMapStrip(mapNode);
    active.classList.remove("hidden");
    //: A bar that wraps to a second row is a panel, not a pill: the pill's
    //: radius cut the corners of its first and last rows (the 22-10 bug doc,
    //: "the two rows clash at a half window").
    //: **Folded once per fill, not once per frame** (the owner, 10-26: "not
    //: laggy"). A one-item drag places the bar every frame and refolded it
    //: each time: at 390 the fold and the reads after it were 945 ms of a 30-move
    //: drag, every frame a long task. The bar's groups change only when
    //: `wbFillContextBar` runs (it clears `sig`) or the host's width does,
    //: or the Format panel opens or shuts: the bar's room is the board less
    //: the panel (its CSS max-width), and a fold cached for the whole board
    //: left it three rows tall beside the panel at 768.
    const fmtOpen = document.getElementById("wb-format")?.classList.contains("hidden") === false;
    const foldSig = !held && active.id === "wb-context" ? `${panSig}:${Math.round(hostRect.width)}:${fmtOpen ? 1 : 0}` : null;
    const folded = foldSig && WB_CTX_FOLD.sig === foldSig ? WB_CTX_FOLD.size : null;
    if (foldSig && !folded) {
      active.classList.remove("wb-context-wrapped");
      wbFoldContextBar(active);
      const groups = [...active.querySelectorAll(":scope > .wb-context-group:not(.hidden)")];
      for (const g of groups) g.classList.remove("wb-row-start");
      const wrapped = active.offsetHeight > 60;
      active.classList.toggle("wb-context-wrapped", wrapped);
      //: And a row's first group loses the hairline that only separates it
      //: from a group beside it (one layout read for all of them).
      if (wrapped) {
        const tops = groups.map((g) => g.offsetTop);
        groups.forEach((g, i) => { if (i && tops[i] > tops[i - 1] + 2) g.classList.add("wb-row-start"); });
      }
    }
    const w = held ? held.w : folded ? folded.w : active.offsetWidth;
    const h = held ? held.h : folded ? folded.h : active.offsetHeight;
    if (foldSig && !folded) Object.assign(WB_CTX_FOLD, { sig: foldSig, size: { w, h } });
    // 44px above, not 10: the rotation handle sits 28px above a card or
    // text box (`.wb-rotate-handle`, 12px tall), and a bar placed just over
    // the item covered it, reported: "I can't rotate objects because that
    // panel appears."
    //: 72 while the clone arrows show: the top one stands past the rotation
    //: handle (56px up, 8px tall), and the bar over it hid it (the owner,
    //: 2026-10-10: "you cant even see the top one").
    const gapAbove = document.getElementById("wb-clone-grips") ? 72 : 44, gapBelow = 10;
    //: Clear of the board's two side panels (the sidebar's rail on the left,
    //: the Format panel on the right), which stand over the canvas: a shape
    //: near the left edge put the bar's first controls under the rail.
    const sideEdges = held ? held.sideEdges : wbBarSideEdges(hostRect);
    let left = Math.max(sideEdges.left, Math.min(sideEdges.right - w, cx - w / 2));
    // Above the item; below it when the top bar would cover the bar. The floor
    // is the bar's own clearance and not the ring's: a floor raised by the room
    // the ring takes *below* the node is what sent the strip down there.
    const topBar = held ? held.topBar : document.getElementById("wb-topbar")?.getBoundingClientRect();
    if (moving && !held) moving.origin.barMeasure = { rect, hostRect, w, h, topBar, sideEdges };
    else if (panning && !held) wbAddGate.panBarHold = { sig: panSig, rect, hostRect, w, h, topBar, sideEdges, box };
    const floor = topBar ? topBar.bottom - hostRect.top + gapBelow : 56;
    let y = top - h - gapAbove;
    //: Below a topic, clear of its add row too (MINDMAP_PLAN 15 row 3): the
    //: row hangs under the node, and the strip dropped there covered it
    //: (measured at 390: three overlaps, the add buttons under Text and Larger).
    const grips = mapNode && !held ? container.querySelector(`.wb-object[data-id="${mapNode.id}"] .wb-map-actions`) : null;
    const gripsBottom = grips ? grips.getBoundingClientRect().bottom - hostRect.top : bottom;
    if (y < floor) y = Math.max(bottom, gripsBottom) + gapBelow;
    //: **At phone width the board bar is pinned to the top of the canvas**
    //: (WHITEBOARD_PLAN section 7's open question, answered 2026-09-20 by
    //: building both and measuring them: `scratchpad/ui-sweeps/wbcontextphone.js`,
    //: five kinds high and low on the board, ten selections each way).
    //:
    //: What decided it was not the bar and the item, it was the bar and the
    //: rail. Floating at 390x844 in a 364x604 canvas, the bar never covered the
    //: item it edits (0px2 on all ten) but landed on the tool rail twice
    //: (7759px2 and 1122px2) and off the canvas once, because at this width it
    //: is a band and not a bar: 348px of a 364px canvas for a line, a shape, a
    //: text box and an arrow, 269px for an image, 6.6% to 25.3% of the whole
    //: board. A band that floats puts the controls in a different place every
    //: time (ten distinct tops spanning 452px) and, low on the board, puts them
    //: over the tools. A bar over the item can be panned out from under; a bar
    //: over the rail takes the drawing tools away.
    //:
    //: Pinned: one top for all ten, all ten inside the canvas, nothing on the
    //: rail or the top bar. Its cost, recorded rather than hidden, is that a
    //: selection in the top band is under it: two of the ten, an image entirely
    //: (8640px2) and a line (3519px2).
    //:
    //: Desktop keeps the floating bar and is untouched, measured by the same
    //: sweep at 1440x900: 0.7% to 2.6% of the canvas, nothing covered, which is
    //: what a contextual bar is for. `WB_PHONE` is the app's own phone band: the
    //: same `(max-width: 599.98px)` query `PHONE_TABS` and `PHONE_FAB` use in
    //: app.js and the same band `10-responsive.css` draws, rather than a number
    //: chosen here or an `innerWidth` compare that a scrollbar can put on the
    //: wrong side of the line. The map's node strip is left alone: it has its
    //: own measured narrow behaviour, two centred rows.
    const pinned = active === bar && WB_PHONE.matches;
    if (pinned) {
      bar.dataset.wbAnchor = "top";
      left = rect.left - hostRect.left + 8;
      y = floor;
      //: **Pinned to the other edge when the top band is where the selection
      //: is** (uipolish-0924 item C, `#wb-context`). The cost recorded above
      //: was still paid: 3 of the sweep's 10 selections, the ones high on the
      //: board, sat under the band that edits them (6080, 6719 and 319px2).
      //: Such a selection gets the band at the foot of the canvas instead,
      //: just above the rail, which is still one of two fixed places and
      //: never on the tools; a selection tall enough to meet both keeps the
      //: top, as before.
      const rail = document.getElementById("wb-tool-group")?.getBoundingClientRect();
      const foot = (rail && rail.height ? rail.top - hostRect.top : rect.bottom - hostRect.top) - h - gapBelow;
      //: The grips count as the selection (INBOX 1354, measured at 390: the
      //: band ended 10px over a shape's top and covered its rotation grip and
      //: up arrow, 28 and 56px above it, so a turn there was a press on the bar).
      const gripsTop = top - gapAbove + 12;
      const under = (at) => gripsTop < at + h && bottom > at;
      if (under(y) && foot > y && !under(foot)) {
        bar.dataset.wbAnchor = "bottom";
        y = foot;
      }
    } else {
      //: **And the bar stays on the canvas.** `left` has been clamped to the
      //: host since this bar was built; `y` never was, so a selection low on
      //: the board (or below the fold, which select-all and a shift-click can
      //: both produce) put its bar outside the canvas entirely: measured at
      //: 390x844, five of ten selections placed the bar from 843px to 1183px
      //: down an 844px window. The item is off screen in that case and nothing
      //: can point at it, so the bar goes to the nearest edge it can be read
      //: at rather than to a coordinate no one can see.
      const canvasTop = rect.top - hostRect.top;
      const canvasBottom = rect.bottom - hostRect.top;
      y = Math.min(y, canvasBottom - h - gapBelow);
      y = Math.max(y, Math.max(floor, canvasTop + gapBelow));
      if (active === strip && !held) {
        [left, y] = wbMapStripClearOfHandle(mapNode, {
          left, y, w, h, hostRect, gapBelow, bottom,
          minY: Math.max(floor, canvasTop + gapBelow), maxY: canvasBottom - h - gapBelow,
        });
      }
    }
    active.style.left = `${Math.round(left)}px`;
    active.style.top = `${Math.round(y)}px`;
    //: The open door goes where the bar goes. Cheap by construction: at most one
    //: menu is open, and with none open this walks three toggles and returns.
    if (active === strip) wbTrackMapStripMenu();
  }

  // Shared by every item's own click handler (sketch/node/object): a plain
  // click replaces whatever was selected, exactly as before; a shift-click
  // adds or removes just this one item from the multi-selection, first
  // folding any existing lone selection into it so "click one, then
  // shift-click another" and "shift-click two in a row" end up in the same
  // state.
  function wbHandleItemClick(kind, id, event) {
    if (event.shiftKey) {
      if (wbSelectedItem) {
        wbMultiSelection.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
        wbSelectedItem = null;
      }
      const key = wbMultiKey(kind, id);
      if (wbMultiSelection.has(key)) wbMultiSelection.delete(key);
      else wbMultiSelection.add(key);
      wbApplySelectionHighlight();
      return;
    }
    // A plain click on a *grouped* item selects the whole group, not just the
    // one thing clicked: the other half of Ctrl+G (`wbGroupSelection`).
    const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
    const chain = wbGroupChain(item);
    if (!chain.length) {
      wbMultiSelection.clear();
      selectWbItem(kind, id);
      return;
    }
    //: A click inside the group already selected keeps it (so a press to drag
    //: does not climb back out); a double-click goes one group further in, and
    //: past the innermost to the item itself (INBOX 1354).
    //: Inside an opened group (`base` ids deep) its own members are single items and only a deeper group is one.
    const base = wbFmtState.isolate?.depth() || 0;
    if (base && chain.length <= base) {
      wbMultiSelection.clear();
      selectWbItem(kind, id);
      return;
    }
    const found = wbSelectedGroupDepth(chain);
    const depth = found > base ? found : 0;
    if (depth && !(event.detail >= 2)) return;
    //: A double-click on a member goes into the group it was already in (L-whiteboard-7) and one level further.
    if (depth && event.detail >= 2) wbFmtState.isolate?.enter(chain.slice(0, depth));
    const want = depth ? depth + 1 : base + 1;
    wbMultiSelection.clear();
    if (want > chain.length) {
      wbDrilledAt = performance.now();
      selectWbItem(kind, id);
      return;
    }
    if (depth) wbDrilledAt = performance.now();
    for (const { kind: memberKind, item: candidate } of wbItemsWithGroupPrefix(chain.slice(0, want))) {
      //: A locked member stays put while its group moves (decision 15).
      if (!wbIsLocked(memberKind, candidate)) wbMultiSelection.add(wbMultiKey(memberKind, candidate.id));
    }
    wbSelectedItem = null;
    wbApplySelectionHighlight();
  }

  //: How deep into `chain` the current selection is: n when it is exactly the
  //: unlocked members of the chain's first n ids, 0 otherwise.
  function wbSelectedGroupDepth(chain) {
    if (!wbMultiSelection.size) return 0;
    for (let n = chain.length; n >= 1; n -= 1) {
      const members = wbItemsWithGroupPrefix(chain.slice(0, n)).filter((e) => !wbIsLocked(e.kind, e.item));
      if (members.length === wbMultiSelection.size && members.every((e) => wbMultiSelection.has(wbMultiKey(e.kind, e.item.id)))) return n;
    }
    return 0;
  }

  //: The double-click that went into a group is not also an edit of the item.
  let wbDrilledAt = 0;
  function wbJustDrilled() {
    return performance.now() - wbDrilledAt < 600;
  }

  //: Which `wbState` list a selection's item lives in, by kind, one place so
  //: it can't drift out of step with `WB_KIND_INFO`'s own list names.
  const WB_LIST_BY_KIND = { sketch: "sketches", node: "nodes", object: "objects" };

  // Delete/Backspace with something selected, the other half of "select as
  // a real tool": today, deleting anything meant switching to the Delete
  // tool first. Reuses `wbDeleteSketch`/`wbDeleteNode`/`wbDeleteObject`, so a
  // selection-delete gets undo/redo for free, the same as every other way of
  // deleting one. A non-empty multi-selection takes priority over the
  // single-item one: the two are mutually exclusive by construction
  // (`wbHandleItemClick`/marquee-select always clear one when populating the
  // other), but checking the set first is the honest way to say so.
  function deleteWbSelection() {
    if (wbMultiSelection.size > 0) {
      //: **One Undo step for the whole selection, deleted one at a time**
      //: (INBOX 537): it was one step per item, and the deletes ran at once, so a
      //: link already dropped with its card 404'd and took the wrong entry off.
      //: Links first, then shapes, cards and boxes.
      const rank = { sketch: 0, node: 1, object: 2 };
      const keys = [...wbMultiSelection].sort((a, b) => rank[a.split(":")[0]] - rank[b.split(":")[0]]);
      wbMultiSelection.clear();
      wbRecordGesture(async () => {
        for (const key of keys) {
          const sep = key.indexOf(":");
          const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
          const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
          if (!item) continue;
          if (kind === "sketch") await wbDeleteSketch(item);
          else if (kind === "node") await wbDeleteNode(item);
          else await wbDeleteObject(item);
        }
      });
      wbApplySelectionHighlight();
      return true;
    }
    if (!wbSelectedItem) return false;
    const { kind, id } = wbSelectedItem;
    const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
    clearWbSelection();
    if (!item) return false;
    if (kind === "sketch") wbDeleteSketch(item);
    else if (kind === "node") wbDeleteNode(item);
    else wbDeleteObject(item);
    return true;
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbApplySelectionHighlight, selectWbItem, wbSelectAllItems, wbSelectAllOfKind, wbSelectSimilar, wbSelectableItems, wbItemSpokenName, wbAnnounce, wbWalkItems, clearWbSelection, wbPruneSelection, WB_PHONE, wbMapStripMenuOffTopic, wbQueueSelectionBar, wbRenderRelease, WB_CTX_FOLD, wbUpdateSelectionBar, wbHandleItemClick, wbJustDrilled, WB_LIST_BY_KIND, deleteWbSelection });
})();
