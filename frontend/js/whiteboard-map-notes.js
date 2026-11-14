(() => {
  // whiteboard-map-notes.js: map note topics, the note behind a topic and folding.
  // Moved out of whiteboard-map.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: A note node's text, read from the notebook (never the clipped list row) and put
  //: in the box; until it arrives the box is read-only so nothing typed is lost.
  wbMapOpenNote.load = async (state, box) => {
    box.readOnly = true;
    box.placeholder = "Loading the note…";
    try {
      const entry = await apiJson(`/entries/${state.entryId}`);
      if (wbMapNoteState !== state) return;
      box.value = String(entry.content || "");
      state.before = box.value;
      state.loaded = true;
      box.readOnly = false;
      box.placeholder = "";
    } catch (err) {
      state.panel.remove();
      document.removeEventListener("pointerdown", state.outside, true);
      wbMapNoteState = null;
      toast(err.message || "That note could not be opened here.", true);
    }
  };

  //: Save a note node's text to the notebook: one Undo step on the notebook's
  //: history, the cards refreshed, and the map's labels re-read so the node
  //: carries the note's new first line.
  wbMapOpenNote.save = async (entryId, before, after) => {
    //: On the board's own history, where Ctrl+Z is read while a board is open.
    const write = (content) => async () => {
      await apiJson(`/entries/${entryId}`, { method: "PUT", body: JSON.stringify({ content }) });
      await refreshEntries([entryId]);
      await wbRefreshMapState();
      renderWhiteboardNow();
    };
    try {
      await write(after)();
      wbPushCall("Edited a note from the map", write(before), write(after));
      wbAnnounce("Note saved.");
    } catch (err) {
      toast(err.message || "That note could not be saved.", true);
    }
  };

  function wbMapCloseNote({ restoreFocus = false } = {}) {
    const state = wbMapNoteState;
    if (!state) return;
    wbMapNoteState = null;
    document.removeEventListener("pointerdown", state.outside, true);
    const value = state.panel.querySelector("textarea")?.value ?? state.before;
    state.panel.remove();
    if (state.anchor.classList.contains("wb-map-note")) state.anchor.setAttribute("aria-expanded", "false");
    const node = (wbState.objects || []).find((o) => o.id === state.id);
    const next = value.trim();
    if (state.entryId != null) {
      //: A note's own text keeps its spacing; an emptied one is left (a note is not deleted from here).
      if (node && state.loaded && value !== state.before && value.trim()) wbMapOpenNote.save(state.entryId, state.before, value);
    } else if (node && next !== state.before.trim()) {
      wbMapSetNodeStyle(node, { note: next || null }).then(() => {
        renderWhiteboardNow();
        wbAnnounce(next ? "Note saved." : "Note removed.");
      });
    }
    if (restoreFocus) {
      const mark = document.querySelector(`.wb-object[data-id="${state.id}"] .wb-map-note`);
      if (mark && !mark.hidden) mark.focus({ preventScroll: true });
      else document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
    }
  }

  //: Makes a topic a task, takes the box away (`null`), or ticks it. Through
  //: `wbMapSetNodeStyle` for its one undo step and its save, then a render,
  //: because the counts on every topic above this one change with it.
  async function wbMapSetTask(node, value) {
    if (!node) return;
    await wbMapSetNodeStyle(node, { task: value });
    renderWhiteboardNow();
    wbAnnounce(
      value === "done" ? "Done." : value === "open" ? "A task, not done yet." : "No longer a task."
    );
  }

  function wbMapToggleTaskDone(id) {
    const node = (wbState.objects || []).find((o) => o.id === id);
    const task = node?.data?.task;
    if (task !== "open" && task !== "done") return;
    wbMapSetTask(node, task === "done" ? "open" : "done");
  }

  //: What the node edit strip sets, drawn on the node (§12.1 item 2).
  //:
  //: Split out of `wbPaintMapNode` rather than inlined into it because the
  //: strip changes one node at a time and a full render is the wrong price for
  //: a bold toggle: `wbMapSetNodeStyle` calls this directly for the node it
  //: just changed, and the render calls it for every node, and both get the
  //: same result by construction rather than by two lists of properties being
  //: kept in step.
  function wbPaintMapNodeStyle(node, d) {
    //: The map's theme underneath the node's own choices (§13e): this is the
    //: one place a topic's look is turned into classes and attributes, so it is
    //: the one place the theme has to be resolved for a topic to inherit it.
    const data = wbMapThemedData(d);
    node.classList.toggle("wb-map-bold", Boolean(data.bold));
    node.classList.toggle("wb-map-italic", Boolean(data.italic));
    //: A core idea (MINDMAP_PLAN.md item 177). A class rather than a data
    //: attribute because it is not one of a set of exclusive values the way the
    //: shape and the alignment are: it is on or it is off, and it composes with
    //: whichever shape the node is wearing.
    node.classList.toggle("wb-map-core", Boolean(data.core));
    //: The shape is a data attribute rather than four classes for the same
    //: reason `align` is: they are exclusive, and a class per value is a class
    //: somebody forgets to remove. The stylesheet holds the four looks; an
    //: unset shape is the rounded card this map has always drawn.
    //: The rounded pin is drawn as itself, unlike every other pin: a core
    //: topic with no shape is the ellipse (the stylesheet's
    //: `:not([data-shape])`), so "Rounded" chosen on one has to say so.
    const shape = wbMapDrawn(data, "shape") || (data.shape === WB_MAP_APP_DEFAULT_PINS.shape ? "rounded" : undefined);
    if (shape) node.dataset.shape = shape;
    else delete node.dataset.shape;
    //: The bar down the node's leading edge (MINDMAP_PLAN.md item 177), an
    //: attribute for the same reason the shape is: three exclusive values, and
    //: an unset one is the solid bar every map has always drawn.
    const spine = wbMapDrawn(data, "spine");
    if (spine) node.dataset.spine = spine;
    else delete node.dataset.spine;
    //: Its effect (MINDMAP_PLAN §14.4): its own, else its level's; `none` is
    //: one topic kept plain on a level that has one, drawn as no attribute.
    if (data.effect === "shadow" || data.effect === "glow") node.dataset.effect = data.effect;
    else delete node.dataset.effect;
    //: A downward tree's siblings sit in a row, so the far-zoom + hangs under
    //: the topic instead of on its left over the sibling (L360).
    const downward = wbMapLayout() === "tree-down" || wbMapLayout() === "org";
    if (downward) node.dataset.flow = "down";
    else delete node.dataset.flow;
    const align = wbMapDrawn(data, "align");
    if (align) node.dataset.align = align;
    else delete node.dataset.align;
    //: A task (decision 15): its box, and a done task's label struck through.
    //: Read off the node's own data, never the theme's: a task is content.
    const task = d.data?.task === "open" || d.data?.task === "done" ? d.data.task : null;
    node.classList.toggle("wb-map-task-done", task === "done");
    const box = wbMapCache.part(node, "task", Boolean(task));
    if (box) {
      box.hidden = !task;
      if (task) {
        box.setAttribute("aria-checked", task === "done" ? "true" : "false");
        box.title = task === "done" ? "Done: press to mark it not done" : "Press to mark it done";
        box.setAttribute("aria-label", task === "done" ? "Done" : "Not done");
        const glyph = box.querySelector("i");
        if (glyph) glyph.className = task === "done" ? "ph ph-check-square" : "ph ph-square";
      }
    }
    //: Its markers (decision 34): content, read off the node's own data.
    const markers = wbMapCache.part(node, "markers", Boolean(wbMapMarkerWords(wbMapMarkerParts(d.data || {}))));
    if (markers) wbMapPaintMarkers(markers, d.data || {});
    // Px through CSSOM, which is what a text box's own `font_size` already
    // does (`renderWbObjects`): the value is per node and arbitrary, so it
    // cannot be a token, and the stylesheet's own `var(--text-md)` is the
    // default this replaces only when there is something to replace it with.
    if (data.font_size) node.style.fontSize = `${data.font_size}px`;
    else node.style.removeProperty("font-size");

    //: A hand-resized topic's height, as a floor (see `wbMapStartResizeDrag`).
    //: The width needs nothing here: `renderWbObjects` already writes every
    //: object's own `width`, and a map node is the one kind whose *height* it
    //: deliberately leaves to the text.
    if (data.sized && d.height) node.style.minHeight = `${d.height}px`;
    else node.style.removeProperty("min-height");

    {
      // A topic wears what it was given; a reference node falls back to the
      // icon for its kind, which is what says "this is a note, not a topic".
      //: **A star before the label on a core idea** (INBOX 201, the fourth of the
      //: four ways: shape, weight, size and a glyph). It is the icon element the
      //: node already has rather than a fifth child, so a core node that was
      //: given an icon of its own keeps that one: an explicit choice beats a
      //: mark, the same rule bold already follows against core's own weight.
      const core = Boolean(data.core) && !WB_MAP_REFERENCE_KINDS.has(d.kind);
      const chosen = data.icon || (core ? "star" : (WB_MAP_REFERENCE_KINDS.has(d.kind) ? null : ""));
      const name = chosen || (WB_MAP_REFERENCE_KINDS.has(d.kind)
        ? (WB_MAP_ICONS[d.kind] || WB_MAP_ICONS.topic).replace(/^ph-/, "")
        : "");
      const icon = wbMapCache.part(node, "icon", Boolean(name));
      if (icon) {
      icon.hidden = !name;
      //: **An emoji is drawn as text** (MINDMAP_PLAN.md decision 45): one slot,
      //: a Phosphor name or one emoji, told apart by the name's own pattern.
      if (name && !WB_MAP_ICON_NAME.test(name)) {
        icon.className = "wb-map-node-icon wb-map-node-emoji";
        if (icon.textContent !== name) icon.textContent = name;
      } else {
        if (icon.textContent) icon.textContent = "";
        icon.className = name ? `ph ph-${name} wb-map-node-icon` : "wb-map-node-icon";
      }
      }
    }

    //: The picture, and the node shape that goes with it (§12.1 item 2's
    //: fourth). `data-body` rather than a class for the same reason `shape` and
    //: `align` are attributes: it is one of a set of exclusive body layouts, and
    //: the absence of the attribute is the label-only node this map has always
    //: drawn. The stylesheet turns the body from a row into a column on it, so a
    //: picture node is a second node *shape*, not a label with a thumbnail
    //: wedged in beside it.
    const url = typeof data.image === "string" ? data.image : "";
    const picture = wbMapCache.part(node, "picture", Boolean(url));
    if (picture) {
      picture.hidden = !url;
      if (url) {
        // `mediaSrc`, never the raw url: media is served behind the unlock, so
        // the token has to ride on the query string exactly as it does for a
        // board image and a note's own attachment.
        const src = mediaSrc(url);
        if (picture.getAttribute("src") !== src) picture.setAttribute("src", src);
        node.dataset.body = "picture";
      } else {
        picture.removeAttribute("src");
        delete node.dataset.body;
      }
    }

    wbMapPaintExtras(node, d.data || {});
    wbMapLazy.paintAudio(node, d.data || {});
    wbMapLazy.paintGrammar(node, d);
    //: A note (decision 18): read off the topic's own data, never the theme's.
    const note = typeof d.data?.note === "string" ? d.data.note.trim() : "";
    const noteMark = wbMapCache.part(node, "note", Boolean(note));
    if (noteMark) {
      noteMark.hidden = !note;
      if (note) {
        noteMark.title = `Note: ${noteNamePlain(note, 80)}`;
        noteMark.setAttribute("aria-label", "Open the note behind this topic");
      }
    }
    const href = typeof data.link === "string" ? data.link : "";
    const link = wbMapCache.part(node, "link", Boolean(href));
    if (link) {
      link.hidden = !href;
      if (href) {
        link.title = `Open ${href}`;
        link.setAttribute("aria-label", `Open the page this topic links to`);
      }
    }
  }

  //: The three schemes a topic's link may have, checked again at the click.
  //:
  //: The schema validator (`_safe_link_scheme`) refuses anything else on the
  //: way in, so this is the second of two doors, and it is here because a value
  //: stored before that validator existed, or written by a tool that talks to
  //: the database another way, would otherwise reach `window.open` unexamined.
  //: CLAUDE.md's own rule for the map's delete policy says it plainly: a rule
  //: enforced at one of two doors is not a rule.
  const WB_MAP_LINK_SCHEMES = /^(https?:\/\/|mailto:)/i;

  function wbMapOpenLink(d) {
    const href = d.data?.link;
    if (!href || !WB_MAP_LINK_SCHEMES.test(String(href).trim())) {
      toast("That topic's link is not a web address.", "info");
      return;
    }
    window.open(String(href).trim(), "_blank", "noopener,noreferrer");
  }

  //: How small a topic may be dragged. Narrower than this is a box too small to
  //: hold the grip that is resizing it, which is a node you cannot get back.
  const WB_MAP_NODE_MIN_W = 72;
  const WB_MAP_NODE_MIN_H = 40;
  //: The least height the server stores for an object (`WhiteboardObjectBase.height`
  //: is `ge=20`). Below the drag's own floor on purpose: a one-line topic in a
  //: small face is drawn shorter than 40, and the reset that records that height
  //: must not be refused for it (INBOX 716).
  const WB_MAP_HEIGHT_FLOOR = 20;

  //: **A topic's own resize**, from pointerdown to drop.
  //:
  //: **It writes width and height and never x or y.** The map's layout owns the
  //: positions (§12.0: auto-arrange is a command, so a hand-placed node stays
  //: put), so a resize that also moved the node would fight the thing that put
  //: it there. The siblings make room at the next tidy, not during the drag,
  //: which is the same bargain every other edit on a map makes.
  //:
  //: **The height is a floor, not a ceiling.** A map node is deliberately
  //: `height: auto` (`objectHeight`): its own text decides how tall it is, so a
  //: long topic can never be sliced by `overflow`. Writing the dragged height as
  //: `height` would take that guarantee away the first time somebody dragged a
  //: node shorter than its own words. `min-height` keeps both promises: the node
  //: is as tall as it was asked to be, or as tall as its text, whichever is
  //: more, and `wbMapNodeSize` reads the answer off the DOM either way.
  //:
  //: `data.sized` is what says a person chose these numbers. Every topic is
  //: created with a width and a height already (`WB_MAP_NODE_W`/`_H`), so the
  //: stored values cannot say by themselves whether anybody meant them, and a
  //: `min-height` applied to every node on every map would pin the whole map to
  //: a default that was only ever a starting guess.
  function wbMapStartResizeDrag(grip, event, d) {
    const node = grip.closest(".wb-object");
    if (!node) return;
    const container = document.getElementById("whiteboard-container");
    const k = container ? d3.zoomTransform(container).k : 1;
    const startX = event.clientX;
    const startY = event.clientY;
    const startW = d.width || WB_MAP_NODE_W;
    // The *drawn* height, not the stored one: an unresized node's stored height
    // is the creation default and its real height is whatever its text needs,
    // so starting from the stored number would jump the node on the first pixel.
    const startH = node.offsetHeight || d.height || WB_MAP_NODE_H;
    const before = WB_KIND_INFO.object.payload(d);
    // Collected once, before the drag: the two ends of an edge move with the
    // box, so the lines have to be redrawn per frame or they detach from the
    // node being resized, which is INBOX 42's report in a different gesture.
    const edges = wbMapEdgesFor(d.id);
    let width = startW;
    let height = startH;
    //: **Shift scales the words with the box** (INBOX 610), by the width's
    //: ratio, inside the same bounds the four named sizes sit in. Read on every
    //: move, so pressing or letting go of Shift mid-drag does what it says.
    //: The size the words are *drawn* at, which is the topic's own, else its
    //: level's or the map theme's (the render pass writes it inline), else the
    //: stylesheet's. Starting from the default instead cleared the inline size
    //: on the first pixel of the drag, so a topic of 17px dropped to 13.6px
    //: while it was resized and snapped back on release (measured 2026-10-18).
    const startInline = node.style.fontSize;
    const startFont = d.data?.font_size || parseFloat(startInline) || parseFloat(getComputedStyle(node).fontSize) || WB_MAP_TEXT_DEFAULT;
    let font = startFont;
    grip.setPointerCapture?.(event.pointerId);
    const move = (moveEvent) => {
      width = Math.max(WB_MAP_NODE_MIN_W, startW + (moveEvent.clientX - startX) / k);
      height = Math.max(WB_MAP_NODE_MIN_H, startH + (moveEvent.clientY - startY) / k);
      width = Math.round(width);
      height = Math.round(height);
      font = moveEvent.shiftKey
        ? Math.round(Math.min(WB_MAP_TEXT_MAX, Math.max(WB_MAP_TEXT_MIN, startFont * (width / startW))))
        : startFont;
      node.style.fontSize = font === startFont ? startInline : `${font}px`;
      node.style.width = `${width}px`;
      node.style.minHeight = `${height}px`;
      d.width = width;
      d.height = height;
      //: This gesture is the one thing that changes a node's measured box
      //: without a render, so it drops that node's cached size itself; without
      //: this the edges would follow the size the node had when the grip was
      //: taken hold of. See `wbMapNodeSize`.
      wbForgetMapNodeSize(d.id);
      wbUpdateMapEdges(edges);
    };
    const done = async () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", done);
      grip.removeEventListener("pointercancel", done);
      if (width === startW && height === startH) return;
      // One write for both halves: `wbMapSetNodeStyle` saves the whole object,
      // and `width`/`height` are already on it.
      // `undo: false`: the size was already live on `d`, so the helper's own
      // snapshot would hold the new size; `before` below is the true one.
      await wbMapSetNodeStyle(d, font === startFont ? { sized: true } : { sized: true, font_size: font }, { undo: false });
      wbPushUndo({ action: "move", kind: "object", id: d.id, before });
      wbScheduleRender();
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", done);
    grip.addEventListener("pointercancel", done);
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbMapCloseNote, wbMapSetTask, wbMapToggleTaskDone, wbPaintMapNodeStyle, WB_MAP_LINK_SCHEMES, wbMapOpenLink, WB_MAP_HEIGHT_FLOOR, wbMapStartResizeDrag });
})();
