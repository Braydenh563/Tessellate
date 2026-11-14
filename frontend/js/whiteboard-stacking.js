(() => {
  // whiteboard-stacking.js: the stacking order, layer order and the bulk move of a selection.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  // --- The board's one stacking order (wbz-1026) ----------------------------
  //
  //: **One answer to "what is on top"** (the layer-order pair sweep, wbz-1026:
  //: four sites each decided it their own way, so what was seen on top was not
  //: always what a click hit, what Bring to front changed or what the export
  //: drew). The render (the drawings' sort and the cards' z-index), the hit
  //: tests, the order commands, the Layers tab and the export all read this.
  //: Bottom to top:
  //:   0  frames (decision 14: under everything they hold);
  //:   1  everything else: drawings (shapes, lines, connectors, pen strokes)
  //:      and cards (notes, text boxes, stickies, tables, pictures) in one
  //:      band, so a stroke sits over or under a card by its z (decision 43,
  //:      the owner 2026-10-27: "each stroke stacks"; drawings were one band
  //:      under every card before). `wbSketchBands` paints it.
  //: Within a band, `z`; a tie (a fresh board has many items at one z) goes
  //: the way a reload paints it: drawings, then notes, then objects, then id.
  const WB_STACK_KIND_RANK = { sketch: 0, node: 1, object: 2 };

  function wbStackBand(kind, item) {
    return kind === "object" && item?.kind === "frame" ? 0 : 1;
  }

  function wbStackCompare(a, b) {
    return wbStackBand(a.kind, a.item) - wbStackBand(b.kind, b.item)
      || (Number(a.item.z) || 0) - (Number(b.item.z) || 0)
      || WB_STACK_KIND_RANK[a.kind] - WB_STACK_KIND_RANK[b.kind]
      //: An item still waiting for its id holds a negative one and is the newest
      //: of its tie, not the oldest: by its own number a new map topic moved every
      //: sibling's rank up by one, and back on the server's answer (L-mindmap-13).
      || (a.item.id < 0) - (b.item.id < 0)
      || (a.item.id < 0 ? b.item.id - a.item.id : a.item.id - b.item.id);
  }

  //: Every item on the board, bottom first, as `{ kind, item, key }`.
  function wbStackOrder(state = wbState) {
    const all = [];
    for (const [kind, list] of [["sketch", state.sketches], ["node", state.nodes], ["object", state.objects]]) {
      for (const item of list || []) all.push({ kind, item, key: `${kind}:${item.id}` });
    }
    return all.sort(wbStackCompare);
  }

  //: The z a new item is made with: on top of its own band, so what was just
  //: made is what is seen, clicked and exported on top. A frame is the one
  //: exception: it goes under the frames already there, since a frame drawn
  //: later is usually drawn around them.
  function wbStackNewZ(kind, item = null, state = wbState) {
    const band = wbStackBand(kind, item);
    const zs = wbStackOrder(state).filter((e) => wbStackBand(e.kind, e.item) === band).map((e) => Number(e.item.z) || 0);
    if (band === 0) return zs.length ? Math.min(...zs) - 1 : 0;
    return Math.max(0, ...zs) + 1;
  }

  //: Each item's place in the stack, 1 at the bottom: the z-index the card
  //: layer paints by, so two items at one z never fall back on DOM order.
  function wbStackRanks(state = wbState) {
    return new Map(wbStackOrder(state).map((e, i) => [e.key, i + 1]));
  }

  //: **Where each stroke paints** (decision 43). SVG children take no
  //: z-index, so a stroke can only go between two cards inside an `<svg>` of
  //: its own in the card layer. One per stroke would be 300 roots on a busy
  //: board; one per *run* of strokes with no card between them is at most one
  //: more than the cards. The run under every HTML item stays in the base
  //: layer (`#wb-zoom-group`), which is every stroke on a board migrated from
  //: the old one-layer order, so such a board pays nothing new. Each band's
  //: z-index is the stack rank of its first stroke, a rank no card holds.
  function wbSketchBands(order) {
    const base = [];
    const bands = [];
    let overCard = false;
    let run = null;
    order.forEach((e, i) => {
      if (e.kind !== "sketch") {
        overCard = true;
        run = null;
        return;
      }
      if (!overCard) {
        base.push(e.item.id);
        return;
      }
      if (!run) {
        run = { rank: i + 1, ids: [] };
        bands.push(run);
      }
      run.ids.push(e.item.id);
    });
    return { base, bands };
  }

  //: Moves each stroke's group to its band, in stack order, touching only the
  //: groups out of place, so a render with no order change moves nothing (a
  //: pan never renders). A map keeps every line in the base layer: its lines
  //: run under the topics they join. Returns the groups in paint order, which
  //: the line jumps read.
  function wbPlaceSketchBands(groups, order = wbStackOrder()) {
    const base = document.getElementById("wb-zoom-group");
    const layer = document.getElementById("wb-html-layer");
    const sketches = order.filter((e) => e.kind === "sketch");
    const plan = wbIsMap() ? { base: sketches.map((e) => e.item.id), bands: [] } : wbSketchBands(order);
    const nodes = (ids) => ids.map((id) => groups.get(id)).filter(Boolean);
    //: The base run, the way d3's `order` does it: from the last up, each
    //: before the one after it, so the base layer's other children stay put.
    let next = null;
    for (const node of nodes(plan.base).reverse()) {
      if (next) {
        if (node.nextSibling !== next) base.insertBefore(node, next);
      } else if (node.parentNode !== base) {
        base.appendChild(node);
      }
      next = node;
    }
    const hosts = [...layer.querySelectorAll(":scope > svg.wb-sketch-band")];
    plan.bands.forEach((band, k) => {
      let host = hosts[k];
      if (!host) {
        host = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        host.setAttribute("class", "wb-sketch-band");
        host.setAttribute("width", "1");
        host.setAttribute("height", "1");
        layer.appendChild(host);
        hosts.push(host);
      }
      if (host.style.zIndex !== String(band.rank)) host.style.zIndex = String(band.rank);
      nodes(band.ids).forEach((node, j) => {
        const at = host.childNodes[j] || null;
        if (at !== node) host.insertBefore(node, at);
      });
    });
    for (const extra of hosts.slice(plan.bands.length)) extra.remove();
    return nodes(sketches.map((e) => e.item.id));
  }

  // --- Layer order: bring to front / send to back (asked for directly) ------
  //
  // `z` is on every kind's own row and the stack above (`wbStackOrder`) turns
  // it into paint order, so these commands only change the number. Strokes,
  // notes and objects are one band (decision 43), so a mixed selection moves
  // past cards and strokes alike; `wbPlaceSketchBands` paints a stroke between
  // two cards. Frames move among frames only (decision 14).

  //: An item's peers for an order command: its own band of the stack, bottom
  //: first, as `{ kind, item, key }`.
  function wbZOrderPeers(kind, item) {
    const band = wbStackBand(kind, item);
    return wbStackOrder().filter((e) => wbStackBand(e.kind, e.item) === band);
  }

  //: Moves one item to the front/back of its own layer and returns a "move"
  //: undo entry (`wbMoveItemBy`'s shape, so it plugs into the same undo/redo
  //: stack without a new action type). It does not save: the item goes onto
  //: `rows`, which the caller saves once for the whole selection (BD2).
  function wbSetZOrder(kind, item, toFront, rows) {
    //: Within its band (`wbStackBand`): a frame to the front of the frames,
    //: never over the cards it holds (decision 14).
    const zs = wbZOrderPeers(kind, item).map((e) => Number(e.item.z) || 0);
    const next = toFront ? Math.max(0, ...zs) + 1 : Math.min(0, ...zs) - 1;
    return wbWriteZ(kind, item, next, rows);
  }

  //: **One step, not the whole way** (FEAT-07, the features audit 2026-10-05:
  //: "Bring forward" wrote `max + 1`, so one press took the bottom item over
  //: everything). draw.io, Figma, Miro and PowerPoint all mean one step by
  //: `]` and `[`, and to the front or back by a modified key, so this is the
  //: step and `wbSetZOrder` above stays the front and back.
  //:
  //: The step passes the next peer that actually overlaps the item, because a
  //: step past something on the far side of the board changes nothing anyone
  //: can see; with nothing overlapping it passes the adjacent peer. Peers
  //: marked `skip` (hidden ones) are passed over rather than stepped past.
  //: Ties are real (a fresh board has every item at z 0, painted in array
  //: order), so the plan orders by z then by array index, places the item
  //: beside its target and writes the fewest rows that keep the order strict.
  function wbBoxesOverlap(a, b) {
    return Boolean(a && b) && a.minX < b.maxX && b.minX < a.maxX && a.minY < b.maxY && b.minY < a.maxY;
  }

  function wbZOrderStepPlan(peers, key, dir) {
    const order = peers
      .map((p, i) => ({ key: p.key, z: Number(p.z) || 0, box: p.box, skip: Boolean(p.skip), i }))
      .sort((a, b) => a.z - b.z || a.i - b.i);
    const at = order.findIndex((p) => p.key === key);
    if (at < 0) return [];
    const me = order[at];
    let target = -1;
    for (let j = at + dir; j >= 0 && j < order.length; j += dir) {
      if (!order[j].skip && wbBoxesOverlap(me.box, order[j].box)) { target = j; break; }
    }
    if (target < 0) {
      for (let j = at + dir; j >= 0 && j < order.length; j += dir) {
        if (!order[j].skip) { target = j; break; }
      }
    }
    if (target < 0) return [];
    const before = new Map(order.map((p) => [p.key, p.z]));
    const seq = order.filter((p) => p !== me);
    const pos = seq.indexOf(order[target]) + (dir > 0 ? 1 : 0);
    seq.splice(pos, 0, me);
    if (dir > 0) {
      me.z = seq[pos - 1].z + 1;
      let floor = me.z + 1;
      for (let k = pos + 1; k < seq.length && seq[k].z < floor; k += 1) {
        seq[k].z = floor;
        floor += 1;
      }
    } else {
      me.z = seq[pos + 1].z - 1;
      let ceil = me.z - 1;
      for (let k = pos - 1; k >= 0 && seq[k].z > ceil; k -= 1) {
        seq[k].z = ceil;
        ceil -= 1;
      }
    }
    return seq.filter((p) => p.z !== before.get(p.key)).map((p) => [p.key, p.z]);
  }

  //: The peers of one item for a step, with the boxes the overlap test reads.
  //: A frame is stacked below everything (decision 14), so a frame steps
  //: among frames and nothing else steps past one.
  //: In stack order, so the plan's tie-break (array index) is the paint's.
  function wbZOrderStepPeers(kind, item) {
    return wbZOrderPeers(kind, item).map((e) => ({
      key: e.key, z: Number(e.item.z) || 0, box: wbItemBBox(e.kind, e.item),
      skip: wbItemHidden(e.kind, e.item), row: e.item, kind: e.kind,
    }));
  }

  //: Whether an item is hidden from the board (the Layers tab's eye). A card
  //: has no data blob, so its flag is a field of its own.
  function wbItemHidden(kind, item, { ignoreFold = false } = {}) {
    if (!item) return false;
    if (kind === "node") return Boolean(item.hidden);
    const data = kind === "sketch" ? wbSketchData(item) : item.data;
    //: Out of sight inside a folded frame too (whiteboard-structure-more.js), so export, present and Select all skip it.
    return Boolean(data && (data.hidden || wbNamedLayerFlag(data.layer, "hidden"))) || (!ignoreFold && Boolean(typeof wbFmtState !== "undefined" && wbFmtState.structure?.folded(kind, item)));
  }

  //: A named layer's flag (canvasdepth): an item on a hidden layer is hidden,
  //: on a locked one locked, whatever its own flag says.
  function wbNamedLayerFlag(id, flag) {
    if (!id || !wbState.layers?.length) return false;
    return Boolean(wbState.layers.find((l) => l.id === id)?.[flag]);
  }

  //: One step for every selected item, one undo step for the lot. Forward
  //: walks the selection from the top down (backward from the bottom up) so
  //: two selected items never leapfrog each other.
  async function wbStepSelectionZOrder(dir) {
    const targets = wbZOrderTargets();
    if (!targets.length) return;
    targets.sort((a, b) => ((b.item.z || 0) - (a.item.z || 0)) * dir);
    const entries = [];
    const rows = [];
    for (const { kind, item } of targets) {
      const peers = wbZOrderStepPeers(kind, item);
      const byKey = new Map(peers.map((p) => [p.key, p]));
      for (const [key, z] of wbZOrderStepPlan(peers, wbMultiKey(kind, item.id), dir)) {
        const peer = byKey.get(key);
        const entry = peer && wbWriteZ(peer.kind, peer.row, z, rows);
        if (entry) entries.push(entry);
      }
    }
    await wbCommitMoves(rows, entries);
    wbAnnounce(entries.length
      ? (dir > 0 ? "Brought forward one step." : "Sent backward one step.")
      : (dir > 0 ? "Already in front of what it overlaps." : "Already behind what it overlaps."));
  }

  //: One z change with its undo entry, for a value chosen elsewhere; the item
  //: goes onto `rows` to be saved with the rest of its selection.
  function wbWriteZ(kind, item, z, rows) {
    if ((item.z || 0) === z) return null;
    const before = WB_KIND_INFO[kind].payload(item);
    item.z = z;
    rows.push({ kind, item });
    return { action: "move", kind, id: item.id, before };
  }

  //: What the order commands act on: the multi-selection, or the one item.
  function wbZOrderTargets() {
    const targets = [];
    if (wbMultiSelection.size > 0) {
      for (const key of wbMultiSelection) {
        const sep = key.indexOf(":");
        const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
        const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
        if (item) targets.push({ kind, item });
      }
    } else if (wbSelectedItem) {
      const { kind, id } = wbSelectedItem;
      const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
      if (item) targets.push({ kind, item });
    }
    return targets;
  }

  //: To the front or the back (Ctrl+] and Ctrl+[), one item or several.
  async function wbSendSelectionZOrder(toFront) {
    const targets = wbZOrderTargets();
    if (!targets.length) return;
    const entries = [];
    const rows = [];
    for (const { kind, item } of targets) {
      const entry = wbSetZOrder(kind, item, toFront, rows);
      if (entry) entries.push(entry);
    }
    await wbCommitMoves(rows, entries);
    wbAnnounce(toFront ? "Brought to the front." : "Sent to the back.");
  }

  // --- Bulk move: dragging one member of a multi-selection moves all of them
  // together: the reason to select more than one thing in the first place.
  // Three per-kind drag handlers (node/object/sketch) each call these three
  // functions at start/drag/end rather than reimplementing the same
  // fixed-baseline-per-frame maths three times (see wbSaveSketchD's own
  // comment on why re-deriving from a live-mutated value drifts).

  function wbDragIsBulkMove(kind, id) {
    return wbMultiSelection.size > 1 && wbMultiSelection.has(wbMultiKey(kind, id));
  }

  //: Every other multi-selected member's position/shape at the *start* of a
  //: bulk drag, so each frame recomputes from one fixed baseline instead of
  //: compounding a per-frame delta onto an already-moved value (the exact bug
  //: `wbSnap`'s own accumulation fix above exists to avoid, here for a whole
  //: set instead of one item).
  function wbCaptureBulkMoveOrigin(excludeKey, keys = wbMultiSelection) {
    const origin = new Map();
    //: **One lookup table per capture, not one scan per member**
    //: (MINDMAP_PLAN.md §13a). The line this replaces was
    //: `list.find((i) => i.id === id)`, which is the whole board walked once
    //: for every item being picked up: fine for a marquee of six, quadratic for
    //: a branch drag, which hands this every topic under the one grabbed. Built
    //: lazily per kind so a selection of one kind never touches the others.
    const itemsByKind = new Map();
    const itemFor = (kind, id) => {
      let byId = itemsByKind.get(kind);
      if (!byId) {
        byId = new Map((wbState[WB_LIST_BY_KIND[kind]] || []).map((i) => [i.id, i]));
        itemsByKind.set(kind, byId);
      }
      return byId.get(id);
    };
    //: The map index, the layout and the drawn edge elements, read once for the
    //: whole capture rather than rebuilt inside `wbMapEdgesFor` per member.
    const edgeCtx = wbIsMap() ? wbMapEdgeContext() : null;
    //: Both of the things every member of this capture is about to be asked
    //: for, taken in one pass rather than one lookup per member per frame.
    const objectEls = wbIsMap() ? wbIndexMapNodeElements() : null;
    //: The link sketches, parsed once for the whole capture rather than the
    //: whole board re-parsed for each member (see `wbLinkSketchIndex`). Built
    //: unconditionally, because a board with no sketches costs an empty loop
    //: and an empty Map, while the case it saves is the one that hurts.
    const linkIndex = wbLinkSketchIndex();
    //: **An edge belongs to one end, not to both.** A tree edge joins two
    //: topics, so when both are in the same dragged branch it appeared in two
    //: members' lists and was recomputed and rewritten twice on every frame of
    //: the drag. Claiming it for whichever member reaches it first halves the
    //: per-frame edge work on any branch drag, and changes nothing about what
    //: is drawn: both ends move by the same delta.
    const claimed = new Set();
    for (const key of keys) {
      if (key === excludeKey) continue; // the dragged item's own handler already moves it
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
      const item = itemFor(kind, id);
      if (!item) continue;
      if (kind === "sketch") {
        const parsed = wbSketchParsedData(item);
        if (parsed) origin.set(key, { kind, id, item, d: parsed.d });
      } else {
        // **Precomputed here, for the same reason `dragStart` precomputes it
        // for the one card you actually grabbed** (`wbLinkedSketchesFor`'s own
        // comment): every other member of a marquee-selected group also moves
        // this drag, and without its own linked-sketch list, nothing was ever
        // going to update *its* edges frame by frame - only the primary
        // dragged card's `d._linkedSketches` existed at all. Reported: "the
        // connections/edges get left behind when i move the notes/nodes
        // around", which is exactly the shape of a bug that only shows on a
        // multi-card drag, a single card was always fine.
        // `mapEdges` only for an object: a map node *is* an object, and a card
        // and an object can share an id, so asking for a card's tree edges
        // would follow the wrong node's branch.
        const mapEdges = [];
        if (kind === "object" && edgeCtx) {
          for (const edge of wbMapEdgesFor(id, edgeCtx)) {
            const edgeKey = `${edge.parent.id}:${edge.child.id}`;
            if (claimed.has(edgeKey)) continue;
            claimed.add(edgeKey);
            mapEdges.push(edge);
          }
        }
        origin.set(key, {
          kind, id, item, x: item.x, y: item.y,
          linked: wbLinkedSketchesFor(id, kind, linkIndex),
          mapEdges,
          //: Resolved here when the board is a map (one pass for the whole
          //: capture, above) and on the first frame that needs it otherwise;
          //: kept for the rest of the gesture either way, see
          //: `wbApplyBulkMove`.
          el: (kind === "object" && objectEls?.get(id)) || null,
        });
      }
    }
    //: The selection's box as the gesture found it, for the bar above it to
    //: ride along on (`wbBulkBarBounds`).
    if (keys === wbMultiSelection && wbMultiSelection.size > 1) origin.boundsAtStart = wbSelectionBounds();
    return origin;
  }


  //: **The selection chrome travels with the drag** (INBOX 262: "if I drag the
  //: selected group, the group selection box doesnt move with the selected
  //: objects when actively draging them around"). Measured before the fix: the
  //: cards moved 410px across a drag and the outline's left edge moved 0.
  //:
  //: A transform on the `<g>`, not a re-layout of its parts, for the reason the
  //: resize handles' own comment gives at length: every one of these groups has
  //: a live `d3.drag` bound to elements inside it, and anything that rebuilds
  //: them mid-gesture kills the gesture. The rotate handle already moves its
  //: group this way, so this is the shape the file already uses.
  //:
  //: Every handle group, not only the multi-selection's: a shape caught in the
  //: same sweep carries its own box and anchors in a `.wb-sketch-handle-group`
  //: of its own (`wbDrawSketchHandles`), and those were left behind by exactly
  //: the same amount.
  function wbTranslateSelectionChrome(dx, dy, origin = null) {
    //: Both layers, for the reason `wbClearSketchHandles` sweeps both: a
    //: shape's own handles are in the base SVG and the group's box is in the
    //: overlay, and a translate that missed either would leave half the chrome
    //: behind.
    //:
    //: **Found once per gesture** (INBOX 424a), kept on the drag's own origin
    //: map: this runs on every move of a group drag, and the query was a
    //: document-wide walk each time (300ms of a 40-move drag at 4x CPU) for
    //: handle groups nothing re-renders mid-drag. The `isConnected` test is
    //: the same safety `wbBulkMoveElement` uses: a render that replaced one
    //: sends the next frame back to the query.
    //: **"Found none" is an answer too** (INBOX 445). The test was `!groups ||
    //: !groups.length`, so a drag with no handle groups at all, which is every
    //: map topic and every card drag, cached an empty list and then read it as
    //: "not looked yet" and walked the document again on every move: measured
    //: on a 61-topic branch drag, 47ms of `querySelectorAll` in 40 moves.
    let groups = origin?.chromeGroups;
    if (!groups || groups.some((group) => !group.isConnected)) {
      groups = [...document.querySelectorAll(
        "#wb-zoom-group > .wb-sketch-handle-group, #wb-overlay-zoom-group > .wb-sketch-handle-group"
      )];
      if (origin) origin.chromeGroups = groups;
    }
    for (const group of groups) {
      if (dx || dy) group.setAttribute("transform", `translate(${dx} ${dy})`);
      else group.removeAttribute("transform");
    }
  }

  //: **The element each member is drawn as, found once per gesture**
  //: (MINDMAP_PLAN.md §13a). This runs for every moved item on every frame, and
  //: it used to open with a document-wide attribute query per item: on a
  //: 500-topic branch drag that is 500 queries a frame for elements that cannot
  //: have changed, and it was the largest single cost left on the drag path
  //: after the topic measurements were cached. `isConnected` is a flag read, so
  //: the re-lookup still happens for real (a render between frames replaces the
  //: element) without paying for it when nothing has.
  function wbBulkMoveElement(entry, selector) {
    if (entry.el && entry.el.isConnected) return entry.el;
    entry.el = document.querySelector(selector);
    return entry.el;
  }

  function wbApplyBulkMove(origin, dx, dy) {
    wbBulkBarBounds = origin.boundsAtStart ? { box: origin.boundsAtStart, dx, dy, origin } : null;
    wbTranslateSelectionChrome(dx, dy, origin);
    //: A branch carried into view from off screen is drawn on the next frame.
    wbScheduleCull();
    for (const entry of origin.values()) {
      if (entry.kind === "sketch") {
        const newD = wbTransformPathD(entry.d, { dx, dy });
        const el = wbBulkMoveElement(entry, `.sketch-group[data-id="${entry.id}"]`);
        //: The group's two paths, found once per gesture like the group itself
        //: (INBOX 445): two queries per shape per frame were 37ms of a 40-move
        //: drag of 80 items, 40 of them shapes.
        if (el && (!entry.pathEl || !entry.pathEl.isConnected)) {
          entry.pathEl = el.querySelector(".sketch-path");
          entry.hitEl = el.querySelector(".sketch-hitbox");
          entry.labelEl = el.querySelector(":scope > .sketch-label");
          entry.labelBgEl = el.querySelector(":scope > .sketch-label-bg");
        }
        entry.pathEl?.setAttribute("d", newD);
        entry.hitEl?.setAttribute("d", newD);
        // A shape's text rides along (decision 12; `wbNudgeShapeLabel`).
        entry.labelEl?.setAttribute("transform", `translate(${dx} ${dy})`);
        entry.labelBgEl?.setAttribute("transform", `translate(${dx} ${dy})`);
        entry.labelEl?.parentNode?.querySelector(":scope > .sketch-label-math")?.setAttribute("transform", `translate(${dx} ${dy})`);
        entry.item._liveD = newD;
      } else {
        entry.item.x = entry.x + dx;
        entry.item.y = entry.y + dy;
        const el = wbBulkMoveElement(entry, WB_SELECTOR_BY_KIND[entry.kind](entry.id));
        if (el) el.style.transform = wbItemTransform(entry.item);
      }
    }
    //: **Every line after every move, never between them.** The lines were
    //: redrawn inside the loop above, member by member, and a tree line is
    //: claimed by whichever of its two ends the capture reached first
    //: (`wbCaptureBulkMoveOrigin`), which in a branch is the parent: so each
    //: line was drawn to a child that had not moved yet this frame, and every
    //: line inside a dragged branch trailed its topic by one frame's travel.
    //: Measured on a 195-topic branch, every animation frame of a real drag
    //: (MINDMAP_PLAN 13a-view): 77 of 81 frames had a line up to 12px from
    //: where its two topics were, and none after this.
    for (const entry of origin.values()) {
      if (entry.kind === "sketch") continue;
      // See this entry's own comment in `wbCaptureBulkMoveOrigin`: without
      // this, only the card the pointer is actually on kept its edges live
      // during a multi-select drag.
      wbUpdateLinkedSketches(entry.id, entry.linked);
      // Same for a map's tree edges, which are not sketches at all: a marquee
      // drag of half a branch left every one of its curves behind.
      if (entry.mapEdges?.length) wbUpdateMapEdges(entry.mapEdges);
    }
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbStackBand, wbStackCompare, wbStackOrder, wbStackNewZ, wbStackRanks, wbPlaceSketchBands, wbSetZOrder, wbZOrderStepPeers, wbItemHidden, wbNamedLayerFlag, wbStepSelectionZOrder, wbWriteZ, wbSendSelectionZOrder, wbDragIsBulkMove, wbCaptureBulkMoveOrigin, wbBulkMoveElement, wbApplyBulkMove });
})();
