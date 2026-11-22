(() => {
  // whiteboard-groups.js: groups, item boxes and zoom to fit, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  function wbGroupChain(item) {
    return item?.group_id ? String(item.group_id).split(WB_GROUP_SEP).filter(Boolean) : [];
  }

  function wbTopGroup(item) {
    return wbGroupChain(item)[0] || null;
  }

  function wbNewGroupId() {
    const bytes = crypto.getRandomValues ? crypto.getRandomValues(new Uint8Array(6)) : Array.from({ length: 6 }, () => Math.random() * 256);
    return Array.from(bytes, (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("");
  }

  //: The chain every item in `items` starts with (empty when they share none).
  function wbCommonGroupPrefix(items) {
    const chains = items.map(wbGroupChain);
    if (!chains.length) return [];
    const prefix = [];
    for (let i = 0; i < chains[0].length; i += 1) {
      const seg = chains[0][i];
      if (!chains.every((c) => c[i] === seg)) break;
      prefix.push(seg);
    }
    return prefix;
  }

  //: Each board item whose chain starts with `prefix` (all of them for none).
  function wbItemsWithGroupPrefix(prefix) {
    const out = [];
    for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
      for (const item of wbState[list] || []) {
        const chain = wbGroupChain(item);
        if (prefix.every((seg, i) => chain[i] === seg)) out.push({ kind, item });
      }
    }
    return out;
  }

  //: An id too long to nest under (a 36-character one from before chains) is
  //: swapped for a short one on every item that carries it.
  function wbShortenGroupIds(entries, rows) {
    const long = new Set();
    for (const e of entries) for (const seg of wbGroupChain(e.item)) if (seg.length > 8) long.add(seg);
    for (const seg of long) {
      const short = wbNewGroupId();
      for (const { kind, item } of wbItemsWithGroupPrefix([])) {
        const chain = wbGroupChain(item);
        if (!chain.includes(seg)) continue;
        item.group_id = chain.map((c) => (c === seg ? short : c)).join(WB_GROUP_SEP);
        rows.push({ kind, item });
      }
    }
  }

  async function wbGroupSelection() {
    const entries = wbSelectionEntries();
    if (entries.length < 2) {
      toast("Select more than one item to group them.");
      return;
    }
    const groupId = wbNewGroupId();
    await wbRecordGesture(async () => {
      const rows = [];
      wbShortenGroupIds(entries, rows);
      const chains = entries.map((e) => [groupId, ...wbGroupChain(e.item)].join(WB_GROUP_SEP));
      if (chains.some((c) => c.length > WB_GROUP_MAX_LEN)) {
        //: The shortened ids above are already on the items; they are saved
        //: even when the group is refused, or the board and the server differ.
        if (rows.length) await wbSaveMany(rows);
        toast("Groups nest five deep at most.");
        return;
      }
      for (let i = 0; i < entries.length; i += 1) {
        entries[i].item.group_id = chains[i];
        rows.push({ kind: entries[i].kind, item: entries[i].item });
      }
      await wbSaveMany(rows);
      toast("Grouped.");
    });
    wbUpdateContextBar();
  }

  //: **Which of Group and Ungroup the selection can use** (B29: "the ungroup
  //: button on the popup tools doesn't change"). Both buttons stayed on the bar
  //: through every selection, so grouping changed nothing the eye could see.
  //: One or the other, never both (the owner, 10-25: "the group and ungroup
  //: button show at the same time"): a selection that shares a group ungroups
  //: it; anything else of two or more groups (a group with loose items, or two
  //: groups, makes a group of groups).
  function wbGroupButtonState(items) {
    const shared = items.length > 0 && wbCommonGroupPrefix(items).length > 0;
    return { canGroup: items.length > 1 && !shared, canUngroup: shared };
  }

  function wbSyncGroupButtons() {
    const state = wbGroupButtonState(wbSelectionEntries().map((e) => e.item));
    document.getElementById("wb-multi-group")?.classList.toggle("hidden", !state.canGroup);
    document.getElementById("wb-multi-ungroup")?.classList.toggle("hidden", !state.canUngroup);
  }

  //: Takes the innermost group the selection shares off each member, so the
  //: groups inside it stay groups. One Undo step.
  async function wbUngroupSelection() {
    const lone = wbSelectedItem && (wbState[WB_LIST_BY_KIND[wbSelectedItem.kind]] || []).find((i) => i.id === wbSelectedItem.id);
    const entries = wbMultiSelection.size ? wbSelectionEntries() : lone ? [{ kind: wbSelectedItem.kind, item: lone }] : [];
    const prefix = wbCommonGroupPrefix(entries.map((e) => e.item));
    if (!prefix.length) return;
    const depth = prefix.length - 1;
    await wbRecordGesture(async () => {
      for (const { item } of entries) {
        const chain = wbGroupChain(item);
        chain.splice(depth, 1);
        item.group_id = chain.length ? chain.join(WB_GROUP_SEP) : null;
      }
      await wbSaveMany(entries);
    });
    toast("Ungrouped.");
    wbUpdateContextBar();
  }

  function wbItemElIndexed(key, retry = true) {
    const layer = wbInstances.layer("wb-html-layer");
    if (!layer) return null;
    const index = wbItemElIndex;
    if (index.count !== layer.childElementCount || index.last !== layer.lastElementChild) {
      index.byKey.clear();
      for (const child of layer.children) {
        const kind = child.classList.contains("node-card") ? "node" : child.classList.contains("wb-object") ? "object" : "";
        if (kind) index.byKey.set(`${kind}:${child.dataset.id}`, child);
      }
      index.count = layer.childElementCount;
      index.last = layer.lastElementChild;
    }
    const el = index.byKey.get(key);
    if (!el || el.isConnected) return el || null;
    index.count = -1;
    return retry ? wbItemElIndexed(key, false) : null;
  }

  function wbItemElement(kind, id) {
    const key = `${kind}:${id}`;
    const cached = wbItemElCache.get(key);
    if (cached && cached.isConnected) return cached;
    const el = wbItemElIndexed(key);
    if (el) wbItemElCache.set(key, el);
    else wbItemElCache.delete(key);
    return el;
  }

  //: A kind-agnostic bounding box (board coordinates, top-left/bottom-right)
  //: for alignment/distribute/nudge math, which all need to compare items of
  //: different kinds against each other. A sketch has no width/height of its
  //: own, its path data *is* its shape, so its box comes from
  //: `wbPathBBox`, while a card/object's box is just its x/y plus whichever
  //: width/height it currently has (falling back to the same defaults their
  //: own resize code uses).
  function wbItemBBox(kind, item) {
    if (kind === "sketch") {
      // Mid-drag the moving path lives in `_dragLiveD`; the stored `data` is
      // still where the shape started, and a link following it would lag a
      // whole gesture behind.
      if (typeof item._dragLiveD === "string") return wbPathBBox(item._dragLiveD);
      //: A resize in flight keeps its path in `_liveD` until release; the
      //: Format panel's numbers read this box while the grip is held.
      if (typeof item._liveD === "string") return wbPathBBox(item._liveD);
      const parsed = wbSketchParsedData(item);
      if (!parsed) return null; // a link sketch: no shape of its own to align
      return wbPathBBox(parsed.d);
    }
    let w = item.width, h = item.height;
    // A card with no stored size (never manually resized) grows to fit its own
    // text: reported directly, with a screenshot: link anchor points sat well
    // inside a tall card's real border, because every unresized card was
    // assumed to be exactly WB_CARD_DEFAULT_SIZE.h (150px) regardless of how
    // much taller its actual content rendered it. Measured from the live DOM
    // instead, converted to board space with the same zoom-transform division
    // every drag handler already uses (`transform.k`), falls back to the
    // fixed default below only when the element genuinely isn't rendered.
    if (kind === "node") {
      const el = wbItemElement("node", item.id);
      if (el && el.offsetWidth && el.offsetHeight) {
        // Rendered size wins over a stored one for the same reason as
        // objects below: a card's text can push it taller than the height it
        // was last resized to.
        w = el.offsetWidth;
        h = el.offsetHeight;
      } else if (el) {
        // `offsetWidth/Height`, not `getBoundingClientRect()`: the rect is the
        // axis-aligned box of the *rotated* card, wider and taller than the
        // card itself, so a rotated note's links landed on a box that does
        // not exist (reported: "I rotated a note and the connection didn't
        // stick to the edge"). Layout size is unrotated and unscaled.
        w = w || el.offsetWidth;
        h = h || el.offsetHeight;
      }
    }
    // A text box or sticky can render taller than its stored height once its
    // text wraps (the element grows; the row does not), so the rendered size
    // wins when the element is on screen, a link aimed at the stored box
    // stopped short of the visible one.
    if (kind === "object") {
      //: **The measurement the render already took, when there is one**
      //: (MINDMAP_PLAN.md §13a). `wbContentBounds` asks this of every item on
      //: the board, so on a 500-topic map the fit that runs on open was 500
      //: document walks and 500 layout reads: 127.2ms of the open, for boxes
      //: `renderWbObjects` had just measured in one pass. The cache holds
      //: exactly those numbers (`offsetWidth`/`offsetHeight`, same reads, same
      //: elements) and is dropped by every render and at the end of every
      //: gesture, so a hit here cannot be older than what is on screen.
      const measured = wbMapNodeSizeCache?.get(item.id);
      if (measured) {
        w = measured.w;
        h = measured.h;
      } else {
        const el = wbItemElement("object", item.id);
        if (el && el.offsetWidth && el.offsetHeight) {
          w = el.offsetWidth;
          h = el.offsetHeight;
        }
      }
    }
    w = w || (kind === "node" ? WB_CARD_DEFAULT_SIZE.w : WB_OBJECT_MIN_SIZE);
    h = h || (kind === "node" ? WB_CARD_DEFAULT_SIZE.h : WB_OBJECT_MIN_SIZE);
    return { minX: item.x, minY: item.y, maxX: item.x + w, maxY: item.y + h };
  }

  // --- Getting around a board bigger than the screen -------------------------
  //
  // Three things any canvas needs once it holds more than one screenful, none
  // of which this board had. Measured on a live board before building, rather
  // than assumed:
  //
  //   * **There was no overview at all.** `board-minimap` in this file is the
  //     *library thumbnail* drawn on a board's card in Boards & maps, it never
  //     rendered on the canvas and has no viewport rectangle. Searching the DOM
  //     of an open board for `.wb-minimap`/`#wb-minimap` found nothing.
  //   * **There was no way to find a card by its words.** A board is made of
  //     notes, and the notebook can full-text search every note in it, except
  //     when they are laid out on a board, where the only way to find one was
  //     to pan around looking.
  //   * **"Fit to Screen" did not fit.** It was
  //     `wbZoom.transform(d3.zoomIdentity)`, a reset to 100% at the origin. On
  //     a board whose content sits at x=2000 that shows blank canvas, which
  //     reads as the board having been wiped rather than as a navigation bug.
  //
  // All three are answered here, and all three share `wbContentBounds()`.

  /** The bounding box of everything on the board, in board coordinates. */
  function wbContentBounds() {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    const grow = (box) => {
      if (!box) return;
      if (box.minX < minX) minX = box.minX;
      if (box.minY < minY) minY = box.minY;
      if (box.maxX > maxX) maxX = box.maxX;
      if (box.maxY > maxY) maxY = box.maxY;
    };
    // `wbItemBBox` already knows every kind's quirks: a link sketch has no
    // shape of its own and returns null, an unresized card is measured from
    // the live DOM. Reusing it is what keeps the navigator, the fit and the
    // search agreeing with the alignment guides about where things are.
    for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
      for (const item of wbState[list] || []) grow(wbItemBBox(kind, item));
    }
    if (!Number.isFinite(minX)) return null;
    return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
  }

  function wbFreeArea(container) {
    const box = container.getBoundingClientRect();
    const area = { left: 0, top: 0, right: box.width, bottom: box.height };
    const sides = { left: 0, top: 0, right: box.width, bottom: box.height };
    for (const selector of WB_FIT_OCCLUDERS) {
      const el = document.querySelector(selector);
      if (!el || el.hidden || el.closest(".hidden")) continue;
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") continue;
      const r = el.getBoundingClientRect();
      const x0 = r.left - box.left, x1 = r.right - box.left, y0 = r.top - box.top, y1 = r.bottom - box.top;
      if (r.width < 4 || r.height < 4 || x1 <= 0 || x0 >= box.width || y1 <= 0 || y0 >= box.height) continue;
      const tall = r.height >= box.height * 0.5 && r.width < box.width * 0.6;
      if (tall) {
        if (x0 + x1 < box.width) sides.left = Math.max(sides.left, x1);
        else sides.right = Math.min(sides.right, x0);
      } else if (y0 + y1 < box.height) sides.top = Math.max(sides.top, y1);
      else sides.bottom = Math.min(sides.bottom, y0);
    }
    area.top = sides.top;
    area.bottom = sides.bottom;
    if (sides.right - sides.left >= box.width / 3) {
      area.left = sides.left;
      area.right = sides.right;
    }
    if (area.bottom - area.top < box.height / 3) {
      area.top = 0;
      area.bottom = box.height;
    }
    return area;
  }

  function wbSameView(a, b) {
    return Boolean(a && b) && Math.abs(a.k - b.k) < 0.001 && Math.abs(a.x - b.x) < 1 && Math.abs(a.y - b.y) < 1;
  }

  //: A panel opening, closing or the window changing size refits a view that
  //: is still where the last fit put it, and leaves any other view alone.
  function wbRefitIfFitted() {
    const container = wbInstances.container();
    if (!wbFit.on || !container || !container.offsetParent || !container.clientWidth) return;
    wbZoomToFit({ padding: wbFit.padding });
  }

  /**
   * Put everything on the board on screen at once.
   *
   * Never zooms *in* past 1: `scaleExtent` allows 4x, but magnifying two cards
   * until they fill a 1440px window is not what anyone means by "fit".
   */
  function wbZoomToFit({ animate = true, padding = 64, bounds = wbContentBounds(), maxScale = 1, refit = true } = {}) {
    const container = wbInstances.container();
    if (!container) return;
    const sel = d3.select(container);
    if (!bounds) {
      // An empty board genuinely has nothing to fit, and the origin at 100% is
      // where the first card will land, so that is the honest destination.
      (animate ? sel.transition().duration(300) : sel).call(wbZoom.transform, d3.zoomIdentity);
      return;
    }
    const free = wbFreeArea(container);
    const k = Math.max(
      0.1,
      Math.min(
        maxScale,
        (free.right - free.left - padding * 2) / Math.max(bounds.width, 1),
        (free.bottom - free.top - padding * 2) / Math.max(bounds.height, 1),
      ),
    );
    const cx = bounds.minX + bounds.width / 2;
    const cy = bounds.minY + bounds.height / 2;
    const target = d3.zoomIdentity
      .translate((free.left + free.right) / 2 - k * cx, (free.top + free.bottom) / 2 - k * cy)
      .scale(k);
    //: Only Fit everything keeps fitting while the board settles; a zoom to
    //: the selection is a place, and the next layout must not pull it back out.
    wbFit.on = refit;
    wbFit.padding = padding;
    wbFit.target = target;
    wbFit.until = Date.now() + (animate ? 600 : 100);
    if (!animate) {
      sel.call(wbZoom.transform, target);
      return;
    }
    //: **The cull draws the destination once, then holds** (INBOX 431: the
    //: overview's Fit "reallllly glitchy and laggy"). A fit ends with
    //: everything on screen, so everything has to be drawn by its last frame
    //: whatever happens on the way. Culled frame by frame, a fit that zooms
    //: out brought a few more items in on every frame of its 350ms, so every
    //: frame restyled, laid out and painted, and on a 150-topic map at a 4x
    //: throttle the animation managed 12 frames, p95 233ms. Drawn against the
    //: destination first, the frames between restyle nothing (the zoom still
    //: re-rasters the board at each scale); the hold lifts when the animation
    //: ends or anything interrupts it. Measured against culling every frame,
    //: with everything else equal: the map's heavy frames went from five
    //: (100 to 233ms) to one at the press and a run of 50 to 83ms.
    //:
    //: The hold is this fit's own: a fit started over a running one
    //: interrupts it, and that one's release must not lift the new hold.
    wbCullHeld = 0;
    wbCullNow(target);
    const hold = ++wbCullHoldCount;
    wbCullHeld = hold;
    const release = () => {
      if (wbCullHeld !== hold) return;
      wbCullHeld = 0;
      wbScheduleCull();
    };
    //: A backstop: a transition whose element went away (the board closed
    //: mid-fit) may fire neither event, and a hold left on would stop culling
    //: for every later pan.
    setTimeout(release, 700);
    sel
      .transition()
      .duration(350)
      .on("end.cullhold", release)
      .on("interrupt.cullhold", release)
      .call(wbZoom.transform, target);
  }

  //: **Zoom steps (Ctrl+=, Ctrl+-, the zoom buttons) keep one point still**
  //: (the owner, 2026-10-26: "does control +/- zoom in on the selection?"). The
  //: selection's centre when something is selected, else the pointer when it is
  //: over the board, else the view's centre. One read of the pointer per step,
  //: none per frame.
  function wbZoomAnchor({ usePointer = true } = {}) {
    const container = wbInstances.container();
    const rect = container.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const bounds = wbSelectionBounds();
    if (bounds) return [t.applyX(bounds.minX + bounds.width / 2), t.applyY(bounds.minY + bounds.height / 2)];
    const p = usePointer ? wbPointerClient : null;
    if (p && p.clientX >= rect.left && p.clientX <= rect.right && p.clientY >= rect.top && p.clientY <= rect.bottom) {
      return [p.clientX - rect.left, p.clientY - rect.top];
    }
    return [rect.width / 2, rect.height / 2];
  }

  function wbZoomStep(factor, { duration = 160, usePointer = true } = {}) {
    const container = wbInstances.container();
    if (!container) return;
    d3.select(container).transition().duration(duration).call(wbZoom.scaleBy, factor, wbZoomAnchor({ usePointer }));
  }

  function wbBoardHasFocus() {
    const view = document.getElementById("library-view-whiteboard");
    if (!view || view.classList.contains("hidden") || !view.getClientRects().length) return false;
    if (document.querySelector("dialog[open]")) return false;
    const active = document.activeElement;
    if (!active || active === document.body) return true;
    if (!view.contains(active)) return false;
    const tag = active.tagName.toLowerCase();
    return !(tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable);
  }

  function wbZoomKey(e) {
    if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
    const run = WB_ZOOM_KEYS[e.code];
    if (!run || (e.shiftKey && /[01]$/.test(e.code)) || !wbBoardHasFocus()) return;
    e.preventDefault();
    e.stopPropagation();
    run();
  }

  function wbZoomTo100() {
    const container = wbInstances.container();
    if (!container) return;
    d3.select(container).transition().duration(160).call(wbZoom.scaleTo, 1, wbZoomAnchor({ usePointer: false }));
  }

  //: **Zoom to the selection** (Shift+2, draw.io's and Figma's key): the
  //: selected items fill the free canvas, magnified up to 2x so one small
  //: shape is readable, never past it.
  function wbZoomToSelection() {
    const bounds = wbSelectionBounds();
    if (!bounds) {
      toast("Select something to zoom to.");
      return;
    }
    wbZoomToFit({ bounds, padding: 32, maxScale: 2, refit: false });
  }

  function wbMapFrameScales(container) {
    const phone = container.clientWidth <= WB_MAP_PHONE_MAX_WIDTH;
    return phone
      ? { min: WB_MAP_PHONE_SCALE, open: WB_MAP_PHONE_SCALE, pad: 16, centre: true }
      : { min: WB_MAP_OPEN_MIN_SCALE, open: 1, pad: 64, centre: false };
  }

  //: **Frame a map when it opens**, rather than leaving the canvas wherever the
  //: last board left it.
  //:
  //: Reported (mindmap.md H item 2, measured while reproducing report B): a map
  //: whose root sits at the board origin opens with that root under
  //: `#wb-topbar`, and a double-click on its text hits the top bar instead of
  //: the node. Measured before this: the root's box was (16, 128)-(216, 172)
  //: against a top bar of (24, 136)-(1416, 182), and `elementFromPoint` at the
  //: root's own centre returned a top-bar button.
  //:
  //: Fit first, because a map is a tree and its shape is the point; but a fit
  //: that lands under `WB_MAP_OPEN_MIN_SCALE` is a picture of a map rather than
  //: a map, so a big one opens on its root at 1:1 instead. Only maps: an
  //: ordinary board is a place you arrange by hand, and re-framing one on every
  //: open would throw away the view its owner left it in.
  function wbFrameMapOnOpen() {
    if (!wbIsMap()) return;
    const container = wbInstances.container();
    if (!container) return;
    const scales = wbMapFrameScales(container);
    wbZoomToFit({ animate: false, padding: scales.pad });
    if (d3.zoomTransform(container).k >= scales.min) return;
    const root = wbMapIndex().roots[0];
    const bounds = wbContentBounds();
    if (!root || !bounds) return;
    //: Not a fit any more: a panel opening must not refit this view back to the
    //: illegible one (`wbRefitIfFitted` did exactly that 50ms after open on a
    //: wide window, so the same map opened at 0.4 there and at 1:1 on a narrow
    //: one).
    wbFit.on = false;
    const target = wbMapOpenTarget(bounds, wbItemBBox("object", root), wbFreeArea(container), scales.open, 48, scales.centre);
    d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(target.x, target.y).scale(target.k));
  }

  //: **Where a map too big to fit opens at 1:1.** Owner, 2026-10-19: "when I go
  //: onto the mindmap it doesnt focus me on the content and puts me down and to
  //: the right where nothing is." The old fallback centred the root in the free
  //: area, which for a map that grows right and down from its root (every
  //: import, every ladder) leaves the top-left half of the screen empty and the
  //: topics off the bottom-right. Per axis: start the view at the content's own
  //: edge, so the empty space is on the far side; if that would push the root
  //: out of view (a root in the middle of a radial map), centre on the root
  //: instead.
  function wbMapOpenTarget(bounds, rootBox, free, k, pad = 48, centre = false) {
    const axis = (lo, rLo, rHi, a0, a1) => {
      const span = (a1 - a0) / k;
      let start = lo - pad / k;
      if (centre || rLo < start || rHi > start + span) start = (rLo + rHi) / 2 - span / 2;
      return a0 - start * k;
    };
    return {
      k,
      x: axis(bounds.minX, rootBox.minX, rootBox.maxX, free.left, free.right),
      y: axis(bounds.minY, rootBox.minY, rootBox.maxY, free.top, free.bottom),
    };
  }

  /** Does this view show the content well enough to keep (INBOX 1428)?
   *  Any overlap used to count, so a board opened on a view showing only its
   *  corner stayed there ("it didnt fit the content to my screen at all"). Kept
   *  when half the content is on screen, or what is on screen fills a third of
   *  the canvas (a big board zoomed in on one part). */
  function wbViewShowsContent(view, bounds, free) {
    if (!view || !bounds) return false;
    const x0 = view.x + view.k * bounds.minX, x1 = view.x + view.k * bounds.maxX;
    const y0 = view.y + view.k * bounds.minY, y1 = view.y + view.k * bounds.maxY;
    const seenW = Math.min(x1, free.right) - Math.max(x0, free.left);
    const seenH = Math.min(y1, free.bottom) - Math.max(y0, free.top);
    if (seenW <= 0 || seenH <= 0) return false;
    const seen = seenW * seenH;
    const whole = Math.max(1, (x1 - x0) * (y1 - y0));
    const room = Math.max(1, (free.right - free.left) * (free.bottom - free.top));
    return seen / whole >= 0.5 || seen / room >= 0.33;
  }

  //: Whether a view puts a whole board-space box inside the free canvas.
  function wbViewHoldsBox(view, box, free) {
    const x0 = view.x + view.k * box.minX, x1 = view.x + view.k * box.maxX;
    const y0 = view.y + view.k * box.minY, y1 = view.y + view.k * box.maxY;
    return x0 >= free.left && x1 <= free.right && y0 >= free.top && y1 <= free.bottom;
  }

  /** Put a board's remembered view back, or frame it when it has none to give. */
  function wbRestoreOrFrameBoard(boardId, restore = false) {
    const container = wbInstances.container();
    if (!container) return;
    const saved = boardId == null ? null : wbBoardViews.get(boardId) || wbRememberBoardView.stored(boardId);
    //: `restore`: the caller is putting a board back (a document's board panel closing, documents-board.js), so the camera it had is
    //: kept as it was whatever the room to measure it by.
    if (saved && restore) {
      wbFit.on = false;
      d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(saved.x, saved.y).scale(saved.k));
      return;
    }
    const bounds = wbContentBounds();
    const free = wbFreeArea(container);
    //: **A map's remembered view must show its centre topic clear of the
    //: chrome** (dog2 item 12: at 700 the root opened 54px under the left rail,
    //: the view kept from a Tab that had panned to its child). A board keeps
    //: any view that shows some of it; a map whose root is hidden is framed.
    const mapRoot = wbIsMap() ? wbMapIndex().roots[0] : null;
    const rootBox = mapRoot ? wbItemBBox("object", mapRoot) : null;
    const rootShown = !rootBox || (saved && wbViewHoldsBox(saved, rootBox, free));
    if (saved && rootShown && wbViewShowsContent(saved, bounds, free)) {
      wbFit.on = false;
      d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(saved.x, saved.y).scale(saved.k));
      return;
    }
    if (wbIsMap()) return wbFrameMapOnOpen();
    //: With no view of its own the camera on screen is the last board's, so
    //: it is never kept: the board is framed (INBOX 1428).
    if (bounds) wbZoomToFit({ animate: false });
  }

  //: **The canvas is panned by its transform and never by scrolling** (mapdeeppan.js:
  //: Tab under "Cells" at 1440x900 moved the whole map 351px with the zoom
  //: transform unchanged, because the browser scrolls an `overflow: hidden` box
  //: to bring a newly focused editor into view and centres it, 627px in the
  //: report). Any such scroll (a focus, a caret, a find) is folded into the zoom
  //: transform at once, so the view the saved camera, Fit and the reveal rules
  //: read is the view on screen; the editors also focus with `preventScroll`.
  function wbFoldNativeScroll(event) {
    const el = event.currentTarget;
    const dx = el.scrollLeft, dy = el.scrollTop;
    if (!dx && !dy) return;
    el.scrollLeft = 0;
    el.scrollTop = 0;
    const t = d3.zoomTransform(el);
    d3.select(el).call(wbZoom.transform, d3.zoomIdentity.translate(t.x - dx, t.y - dy).scale(t.k));
  }

  /** Centre the viewport on one board-space rectangle, keeping the current zoom. */
  function wbCenterOn(box, { animate = true, minScale = 0.55 } = {}) {
    const container = wbInstances.container();
    if (!container || !box) return;
    const sel = d3.select(container);
    const free = wbFreeArea(container);
    const current = d3.zoomTransform(container);
    // Jumping to a match at 0.12x would land on a card too small to read, so
    // ease the zoom up to something legible, but never zoom *out* to get
    // there, because that would undo a deliberate close-up.
    const k = Math.max(current.k, Math.min(minScale, 1));
    const cx = (box.minX + box.maxX) / 2;
    const cy = (box.minY + box.maxY) / 2;
    const target = d3.zoomIdentity
      .translate((free.left + free.right) / 2 - k * cx, (free.top + free.bottom) / 2 - k * cy)
      .scale(k);
    (animate ? sel.transition().duration(300) : sel).call(wbZoom.transform, target);
  }

  //: **A selection is kept clear of the bottom docks** (wb4's found-not-fixed:
  //: a shape low on the board had its lower grips under the zoom pill and the
  //: tool row, 3 of 8 at 390x844 and 3 of 8 at 1440x900, so the edge that
  //: resizes it could not be pressed). Figma and Miro move the view; a grip
  //: cannot sit above a dock, which is a sibling of the canvas. Once the
  //: selection has settled (350 ms with no press, so a double-click is never
  //: interrupted), the view slides up just far enough that the selection's
  //: bottom edge and its grips clear the docks it overlaps, and never so far
  //: that its top meets the bar above it. A pan afterwards is the person's own:
  //: the signature of the selection (what and where, in board units) has to
  //: change before the view moves again.
  const WB_REVEAL_DOCKS = "#wb-tools-panel, .whiteboard-floating-panel[data-panel-id=\"zoom\"]";

  function wbQueueReveal() {
    clearTimeout(wbRevealTimer);
    wbRevealTimer = setTimeout(wbRevealSelection, 350);
  }

  function wbRevealSelection() {
    const container = wbInstances.container();
    let b = null;
    try {
      b = container?.offsetParent && wbSelectionBounds();
    } catch {
      // The selected item went (deleted, or the board changed) while the timer ran.
    }
    if (!b || document.activeElement?.matches?.("input, textarea, [contenteditable]")) return;
    const sig = [...wbSelectedKeys()].join(",") + `|${Math.round(b.minX)},${Math.round(b.minY)},${Math.round(b.width)},${Math.round(b.height)}`;
    if (sig === wbRevealSig) return;
    wbRevealSig = sig;
    const t = d3.zoomTransform(container), r = container.getBoundingClientRect();
    const pad = 40; // wbSelectionBounds' own margin
    const left = r.left + t.x + (b.minX + pad) * t.k, right = left + (b.width - 2 * pad) * t.k;
    const top = r.top + t.y + (b.minY + pad) * t.k, bottom = top + (b.height - 2 * pad) * t.k;
    let dockTop = Infinity;
    for (const el of document.querySelectorAll(WB_REVEAL_DOCKS)) {
      const d = el.getBoundingClientRect();
      if (d.width < 4 || d.right < left - 8 || d.left > right + 8 || d.bottom < top || d.top > bottom + 10) continue;
      dockTop = Math.min(dockTop, d.top);
    }
    const shift = Math.min(bottom + 14 - dockTop, top - (r.top + wbFreeArea(container).top + 56));
    if (!(shift >= 4)) return;
    d3.select(container).transition().duration(200).call(wbZoom.transform, d3.zoomIdentity.translate(t.x, t.y - shift).scale(t.k));
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbGroupChain, wbTopGroup, wbNewGroupId, wbCommonGroupPrefix, wbItemsWithGroupPrefix, wbGroupSelection, wbGroupButtonState, wbSyncGroupButtons, wbUngroupSelection, wbItemElement, wbItemBBox, wbContentBounds, wbFreeArea, wbSameView, wbRefitIfFitted, wbZoomToFit, wbZoomAnchor, wbZoomStep, wbBoardHasFocus, wbZoomKey, wbZoomTo100, wbZoomToSelection, wbMapFrameScales, wbFrameMapOnOpen, wbRestoreOrFrameBoard, wbFoldNativeScroll, wbCenterOn, wbQueueReveal });
})();
