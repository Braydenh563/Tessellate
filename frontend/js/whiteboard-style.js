(() => {
  // whiteboard-style.js: tool settings, copied styles and the context menu rows, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  function wbShowToolSettings(tool) {
    const wanted = new Set(WB_TOOL_SETTINGS[tool] || []);
    for (const el of document.querySelectorAll("#wb-context [data-wb-tool-setting]")) {
      // An enhanced <select> is drawn by its shell; hiding the native one alone
      // would leave the opener showing (`enhanceSelect`, sheets-selects.js).
      const shown = el.closest(".select-shell") || el;
      shown.classList.toggle("hidden", !wanted.has(el.dataset.wbToolSetting));
    }
    return wanted;
  }

  //: The two "what is selected, if it is of this kind" lookups. Module-level
  //: because both the properties panel's own controls and the copy-style
  //: actions below need them, and they close over nothing but module state.
  function wbSelectedSketchOrNull() {
    if (!wbSelectedItem || wbSelectedItem.kind !== "sketch") return null;
    return wbState.sketches.find((s) => s.id === wbSelectedItem.id) || null;
  }

  function wbSelectedTextObjectOrNull() {
    if (!wbSelectedItem || wbSelectedItem.kind !== "object") return null;
    const obj = wbState.objects?.find((o) => o.id === wbSelectedItem.id);
    return obj && obj.kind === "text" ? obj : null;
  }

  function wbPickStyle(source, keys) {
    const out = {};
    for (const key of keys) if (source?.[key] !== undefined) out[key] = source[key];
    return out;
  }

  //: A sticker's glyph size: most of its box's shorter side (decision 44).
  function wbStickerSize(obj) {
    return Math.max(12, Math.round(Math.min(obj.width || 96, obj.height || 96) * 0.72));
  }

  function wbCopySelectedStyle() {
    //: A map topic's look (MINDMAP_PLAN.md decision 42): pasted onto topics
    //: only, refused on a shape the way a shape's is refused on a text box.
    const topic = wbSelectedMapNode();
    if (topic) {
      wbCopiedStyle = { kind: "topic", style: wbMapTopicStyle(topic) };
      return toast("Style copied. Select topics and press Ctrl+Alt+V.");
    }
    const sketch = wbSelectedSketchOrNull();
    if (sketch) {
      let parsed = null;
      try { parsed = JSON.parse(sketch.data); } catch { parsed = null; }
      if (!parsed) return toast("That item has no style to copy.");
      wbCopiedStyle = { kind: "sketch", style: wbPickStyle(parsed, WB_SKETCH_STYLE_KEYS) };
      return toast("Style copied. Select a shape or link and press Ctrl+Alt+V.");
    }
    const obj = wbSelectedTextObjectOrNull();
    if (obj) {
      wbCopiedStyle = { kind: "object", style: wbPickStyle(obj.data, WB_OBJECT_STYLE_KEYS) };
      return toast("Style copied. Select a text box and press Ctrl+Alt+V.");
    }
    toast("Select a shape, link, text box or topic first.");
  }

  async function wbPasteCopiedStyle() {
    if (!wbCopiedStyle) return toast("Copy a style first (Ctrl+Alt+C).");
    // Every item in a multi-selection, so restyling a diagram is one action
    // rather than one per shape, the same reach `wbApplyBulkMove` already has.
    const entries = wbMultiSelection.size > 0
      ? wbSelectionEntries()
      : (wbSelectedItem ? [wbSelectedItem] : []);
    if (!entries.length) return toast("Select something to paste the style onto.");

    let applied = 0;
    let skipped = 0;
    const rows = [];
    for (const entry of entries) {
      const list = wbState[WB_LIST_BY_KIND[entry.kind]] || [];
      const item = list.find((i) => i.id === entry.id);
      if (!item) continue;
      if (wbCopiedStyle.kind === "topic") {
        if (entry.kind === "object" && WB_MAP_KINDS.has(item.kind)) {
          await wbMapSetNodeStyle(item, { ...wbCopiedStyle.style }, { rows });
          applied += 1;
        } else {
          skipped += 1;
        }
      } else if (entry.kind === "sketch" && wbCopiedStyle.kind === "sketch") {
        if (wbSketchSetProps(item, { ...wbCopiedStyle.style })) rows.push({ kind: "sketch", item });
        applied += 1;
      } else if (entry.kind === "object" && wbCopiedStyle.kind === "object" && item.kind === "text") {
        item.data = { ...item.data, ...wbCopiedStyle.style };
        rows.push({ kind: "object", item });
        applied += 1;
      } else {
        skipped += 1;
      }
    }
    await wbSaveMany(rows);
    wbScheduleRender();
    wbUpdateContextBar();
    if (!applied) return toast("That style does not fit what you selected.");
    toast(skipped
      ? `Style pasted onto ${applied}. ${skipped} skipped: a different kind of item.`
      : `Style pasted onto ${applied}.`);
  }

  //: The reset fields for one sketch, or null for a drawing with nothing to
  //: reset (a highlighter's look is its tool). A line whose ends are drawn in
  //: its own path has them redrawn at the default width.
  function wbSketchStyleReset(parsed) {
    if (!parsed || parsed.shape === "highlighter") return null;
    const patch = Object.fromEntries(WB_SKETCH_RESET_KEYS.map((key) => [key, undefined]));
    if (typeof parsed.d === "string" && wbSketchTakesCaps(parsed)) {
      const caps = wbSketchCaps(parsed);
      if (caps.startCap !== "none" || caps.endCap !== "none") {
        patch.d = wbRegenerateShapeCaps(parsed.d, caps.startCap, caps.endCap, 3 * 4 + 6, null);
      }
    }
    return patch;
  }

  //: The data an object keeps after a reset, or null for one with no look of
  //: its own here (a card follows the board; a map topic is reset by its map).
  function wbObjectStyleReset(obj) {
    if (!obj?.data || WB_MAP_KINDS.has(obj.kind)) return null;
    const data = { ...obj.data };
    for (const key of WB_OBJECT_RESET_KEYS) delete data[key];
    if (wbIsSticky(obj)) Object.assign(data, { sticky: true, bg: WB_STICKY_PAPERS[0].value, color: "#2a2a1f", font_size: 16 });
    return data;
  }

  async function wbResetSelectedStyle() {
    const entries = wbMultiSelection.size > 0 ? wbSelectionEntries() : (wbSelectedItem ? [wbSelectedItem] : []);
    if (!entries.length) return toast("Select something to reset its style.");
    let reset = 0;
    await wbRecordGesture(async () => {
      const rows = [];
      for (const entry of entries) {
        const item = (wbState[WB_LIST_BY_KIND[entry.kind]] || []).find((i) => i.id === entry.id);
        if (!item || wbIsLocked(entry.kind, item)) continue;
        if (entry.kind === "object" && WB_MAP_KINDS.has(item.kind)) {
          const patch = {};
          for (const key of WB_MAP_STYLE_KEYS) patch[key] = null;
          await wbMapSetNodeStyle(item, patch, { undo: false, rows });
          reset += 1;
        } else if (entry.kind === "sketch") {
          let parsed = null;
          try { parsed = JSON.parse(item.data); } catch { parsed = null; }
          const patch = wbSketchStyleReset(parsed);
          if (!patch) continue;
          wbSketchSetProps(item, patch);
          rows.push({ kind: "sketch", item });
          reset += 1;
        } else if (entry.kind === "object") {
          const data = wbObjectStyleReset(item);
          if (!data) continue;
          item.data = data;
          rows.push({ kind: "object", item });
          reset += 1;
        }
      }
      await wbSaveMany(rows);
    });
    wbScheduleRender();
    wbUpdateContextBar();
    if (typeof wbFormatSyncSoon === "function") wbFormatSyncSoon();
    if (!reset) return toast("Nothing selected has a style of its own to reset.");
    wbAnnounce(reset === 1 ? "Style reset." : `Style reset on ${reset} items.`);
  }
  const WB_CONTEXT_MENU_SECTIONS = ["more-style", "more-card", "more-guides", "more-notes", "more-mindmap", "more-tidy", "more-shape", "more-link"];

  //: Which row of the table a selection reads. Returns null when the bar has
  //: nothing to say, which is what closes it.
  function wbContextKindOf(sel, item) {
    if (!sel || !item) return null;
    if (sel.kind === "sketch") {
      let parsedLink = null;
      try {
        const candidate = JSON.parse(item.data);
        if (candidate && (candidate.type || "").startsWith("link-")) parsedLink = candidate;
      } catch { /* not JSON: not a link either */ }
      //: **A cross-link on a map has no board bar** (§13c). Its whole control
      //: surface is the map's own link ring now, and the board's bar was the
      //: second vocabulary for the same object that §13.2 measured (ink, caps
      //: and stroke, against the ring's own words). A link between a topic and a
      //: card, or any link on an ordinary board, still gets the bar: it is not
      //: one of the map's two kinds of connection and the ring has nothing to
      //: say about it.
      if (parsedLink && wbMapCrossLinkInfo(item.id)) return null;
      if (parsedLink) return "link";
      const parsed = wbSketchParsedData(item);
      if (!parsed) return null;
      return WB_FILLABLE_SHAPES.has(parsed.shape) ? "shape" : "line";
    }
    if (sel.kind === "node") return "note";
    //: A frame has no style to set and no order to change: it stays below
    //: what it holds (decision 14), so the bar has nothing to offer it.
    if (sel.kind === "object" && item.kind === "frame") return null;
    if (sel.kind === "object") return item.kind === "text" ? "text" : "image";
    return null;
  }

  //: Shows exactly the groups a row names and hides the rest, in one pass, so
  //: a control can never be left over from the last selection.
  function wbApplyContextRow(row) {
    const bar = new Set(row?.bar || []);
    const more = new Set(row?.more || []);
    for (const name of WB_CONTEXT_GROUPS) {
      for (const el of document.querySelectorAll(`#wb-context [data-wb-ctx="${name}"]`)) {
        el.classList.toggle("hidden", !bar.has(name));
      }
    }
    for (const name of WB_CONTEXT_MENU_SECTIONS) {
      for (const el of document.querySelectorAll(`#wb-context-menu [data-wb-ctx="${name}"]`)) {
        el.classList.toggle("hidden", !more.has(name));
      }
    }
    // The rows inside the Style section that only some kinds can use.
    for (const id of ["wb-prop-nostroke-row", "wb-prop-md-row", "wb-prop-bullets-row", "wb-fill-opacity-row", "wb-stroke-none-row"]) {
      document.getElementById(id)?.classList.add("hidden");
    }
    // What acts on a selection, back for every row that has one; the held-tool
    // row takes them away again (`wbHideSelectionActions`).
    for (const id of WB_SELECTION_ONLY_CONTROLS) document.getElementById(id)?.classList.remove("hidden");
    wbContextMoreWrap()?.classList.remove("hidden");
  }

  //: **With a tool held and nothing selected, the bar has no selection to act
  //: on** (INBOX 445). Duplicate, Delete and the More menu's copy and paste of
  //: a style stayed on it and did nothing when pressed; the More menu itself is
  //: kept only for a shape tool, whose fill opacity and stroke live there.
  const WB_SELECTION_ONLY_CONTROLS = ["wb-selbar-duplicate", "wb-selbar-delete", "wb-copy-style-row"];

  function wbContextMoreWrap() {
    return document.querySelector("#wb-context [data-wb-menu-toggle]")?.closest(".wb-board-menu-wrap") || null;
  }

  function wbHideSelectionActions(keepMore) {
    for (const id of WB_SELECTION_ONLY_CONTROLS) document.getElementById(id)?.classList.add("hidden");
    wbContextMoreWrap()?.classList.toggle("hidden", !keepMore);
  }

  //: **The bar with nothing selected sits over the rail.** Placed here rather
  //: than in `wbUpdateSelectionBar` for one measured reason: that function runs
  //: on every frame of every pan (`handleWbZoom`), and this position depends on
  //: the rail and the host, neither of which a pan moves. `data-wb-anchor` is
  //: how the pan frame knows to leave it alone without asking any question that
  //: costs a DOM walk; the same lesson the text-editing query above records.
  function wbParkContextOnRail(on) {
    const bar = document.getElementById("wb-context");
    const host = document.getElementById("library-view-whiteboard");
    if (!bar || !host) return;
    if (!on) {
      bar.classList.add("hidden");
      delete bar.dataset.wbAnchor;
      return;
    }
    bar.dataset.wbAnchor = "rail";
    bar.classList.remove("hidden");
    // One bar over this canvas, never two (the map strip's own rule).
    document.getElementById("wb-map-strip")?.classList.add("hidden");
    const hostRect = host.getBoundingClientRect();
    const rail = document.getElementById("wb-tools-panel")?.getBoundingClientRect();
    const w = bar.offsetWidth;
    const h = bar.offsetHeight;
    const left = Math.max(8, Math.min(Math.max(8, hostRect.width - w - 8), hostRect.width / 2 - w / 2));
    // Ten pixels over the rail, and never off the top: on a short window the
    // rail's own top edge can be less than the bar's height from the top bar.
    const railTop = rail && rail.height ? rail.top - hostRect.top : hostRect.height - 72;
    const topBar = document.getElementById("wb-topbar")?.getBoundingClientRect();
    const floor = topBar ? topBar.bottom - hostRect.top + 8 : 56;
    bar.style.left = `${Math.round(left)}px`;
    bar.style.top = `${Math.round(Math.max(floor, railTop - h - 10))}px`;
  }

  //: Filled first, placed second, never the other way round: the bar is centred
  //: on the selection from its own measured width, and a bar still holding the
  //: last selection's controls is a different width. The map strip's own comment
  //: a few hundred lines down records exactly the same trap for the same reason.
  function wbUpdateContextBar() {
    const bar = document.getElementById("wb-context");
    if (!bar) return;
    wbFormatSyncSoon();
    wbFmtState.effects?.refreshStatus();
    if (wbFillContextBar() === "rail") wbParkContextOnRail(true);
    else wbUpdateSelectionBar();
  }

  //: What the bar holds, from `WB_CONTEXT_CONTROLS`. Returns "rail" when it is
  //: showing a held tool's own settings and so belongs over the rail rather than
  //: over a selection it does not have.
  function wbFillContextBar() {
    const bar = document.getElementById("wb-context");
    WB_CTX_FOLD.sig = null;
    if (!bar) return null;
    const show = (...ids) => ids.forEach((id) => document.getElementById(id)?.classList.remove("hidden"));

    // A multi-selection has no one fill or stroke to edit (mixed kinds), but it
    // does have arrange, which only means anything here.
    if (wbMultiSelection.size > 0) {
      //: Only topics, on a map: the map's group, and neither Duplicate (a copy
      //: of several topics lands as loose roots) nor the More menu, whose
      //: format, style and guides rows are all the board's.
      const mapTopics = wbMapMultiTopics();
      if (mapTopics) {
        wbApplyContextRow(WB_CONTEXT_CONTROLS.mapmulti);
        document.getElementById("wb-selbar-duplicate")?.classList.add("hidden");
        wbContextMoreWrap()?.classList.add("hidden");
        wbSyncMapMulti(mapTopics);
        delete bar.dataset.wbAnchor;
        return null;
      }
      wbApplyContextRow(WB_CONTEXT_CONTROLS.multi);
      wbSyncGroupButtons();
      // Extract notes (BACKLOG.md §62) only makes sense once the selection
      // actually includes a note card's content to extract from; a selection of
      // pure shapes has no "notes-in-context".
      const hasNoteCard = wbSelectionEntries().some((e) => e.kind === "node");
      document.querySelector('#wb-context-menu [data-wb-ctx="more-notes"]')?.classList.toggle("hidden", !hasNoteCard);
      //: Tidy only once the selection holds a connector to lay out along.
      document.querySelector('#wb-context-menu [data-wb-ctx="more-tidy"]')?.classList.toggle("hidden", !wbTidyEdges(wbSelectionEntries()).length);
      delete bar.dataset.wbAnchor;
      return null;
    }

    // The bar is also where a drawing tool's own settings live, so it opens for
    // a held tool with nothing selected: otherwise picking the pen would hide
    // the pen's own thickness. This is the split every whiteboard app makes,
    // tools in the rail, their properties in the context surface.
    if (!wbSelectedItem) {
      const settings = wbShowToolSettings(window.currentTool);
      const toolDraws = settings.size > 0;
      wbApplyContextRow(toolDraws ? WB_CONTEXT_CONTROLS.tool : null);
      // The More menu's two shape rows, for the tools that draw a shape.
      if (settings.has("fill")) show("wb-fill-opacity-row", "wb-stroke-none-row");
      if (toolDraws) wbHideSelectionActions(settings.has("fill"));
      if (!toolDraws) wbParkContextOnRail(false);
      return toolDraws ? "rail" : null;
    }
    delete bar.dataset.wbAnchor;

    const { kind, id } = wbSelectedItem;
    const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
    const which = wbContextKindOf(wbSelectedItem, item);
    wbApplyContextRow(which ? WB_CONTEXT_CONTROLS[which] : null);
    if (!which) return;

    //: The ink swatch's word says what it colours (the owner, 2026-10-11).
    const inkWord = { link: "Line", line: "Line", shape: "Border", text: "Text" }[which];
    const inkWordEl = document.getElementById("wb-prop-color-word");
    if (inkWordEl && inkWord) inkWordEl.textContent = inkWord;
    document.getElementById("wb-prop-color")?.setAttribute("aria-label", `${inkWord || "Line"} colour`);
    if (which === "link") {
      const parsed = JSON.parse(item.data);
      document.getElementById("wb-prop-color").value = parsed.color || "#ffffff";
      document.getElementById("wb-prop-width").value = parsed.width || 3;
      const caps = wbLinkCaps(parsed);
      document.getElementById("wb-prop-startcap").value = caps.startCap;
      document.getElementById("wb-prop-endcap").value = caps.endCap;
      wbShowCapSizes(caps);
      document.getElementById("wb-prop-dash").value = parsed.dash || "solid";
      document.getElementById("wb-prop-route").value = wbLinkRouteName(parsed);
      //: The Label button is for a board connector (a map's cross-link is
      //: worded through its ring); it says "Edit" once there are words.
      const labelButton = document.getElementById("wb-prop-label");
      if (labelButton) {
        labelButton.classList.toggle("hidden", !wbLinkTakesLabel(item, parsed));
        labelButton.title = parsed.label ? "Change this connector's label (Enter)" : "Add a label to this connector (Enter)";
      }
      return;
    }

    if (which === "line" || which === "shape") {
      const parsed = wbSketchParsedData(item);
      document.getElementById("wb-prop-color").value = parsed.color || "#000000";
      document.getElementById("wb-prop-width").value = parsed.width || 3;
      document.getElementById("wb-prop-dash").value = parsed.dash || "solid";
      show("wb-prop-nostroke-row");
      document.getElementById("wb-prop-nostroke").checked = Boolean(parsed.noStroke);
      // **The caps come off the object, never off the tool's default** (the
      // plan's section 2 item 4, and a live report before it): a drawn line
      // reported "Arrow" at both ends because the control was showing
      // `window.currentArrowStyle` rather than what was on the shape.
      const isArrow = wbSketchTakesCaps(parsed);
      document.querySelector('#wb-context [data-wb-ctx="caps"]')?.classList.toggle("hidden", !isArrow);
      if (isArrow) {
        const caps = wbSketchCaps(parsed);
        document.getElementById("wb-prop-startcap").value = caps.startCap;
        document.getElementById("wb-prop-endcap").value = caps.endCap;
        wbShowCapSizes(caps);
      }
      if (which === "shape") {
        document.getElementById("wb-prop-shapefill").value = parsed.fill || "#3355ff";
        const filled = wbColour.fillIsOn("sketch", parsed);
        document.getElementById("wb-prop-shapefill-on").checked = filled;
        //: Dimmed, not disabled: a fill picked from its well turns it on.
        document.getElementById("wb-prop-shapefill").classList.toggle("wb-colour-off", !filled);
      }
      return;
    }

    if (which === "text") {
      //: A sticky's papers, first on its bar, the current one pressed.
      const paper = document.querySelector('#wb-context [data-wb-ctx="paper"]');
      if (paper) {
        const sticky = wbIsSticky(item);
        paper.classList.toggle("hidden", !sticky);
        if (sticky) wbFillPaperPicker(paper, item);
      }
      for (const button of document.querySelectorAll("#wb-prop-align button")) {
        button.classList.toggle("active", button.dataset.align === (item.data.align || "left"));
      }
      show("wb-prop-md-row", "wb-prop-bullets-row");
      document.getElementById("wb-prop-md").checked = Boolean(item.data.md);
      document.getElementById("wb-prop-color").value = item.data.color || "#1f2430";
      document.getElementById("wb-prop-bg").value = item.data.bg === "transparent" ? "#ffffff" : (item.data.bg || "#ffffff");
      document.getElementById("wb-prop-bg-none").checked = item.data.bg === "transparent";
      document.getElementById("wb-prop-border").value = item.data.border_color === "transparent" ? "#8888aa" : (item.data.border_color || "#8888aa");
      document.getElementById("wb-prop-border-none").checked = item.data.border_color === "transparent";
      document.getElementById("wb-prop-fontsize").value = item.data.font_size || 16;
      // A text box has no line ends and no drawn width; the ink group's width
      // field is a stroke thickness, which a box does not have either.
      document.getElementById("wb-prop-width").parentElement?.classList.add("hidden");
      return;
    }

    if (which === "note") {
      // Mind-mapping (item 25): only worth offering once the card actually has
      // something to arrange; a card with no links is already exactly where a
      // "mind map of one" would put it.
      const hasLink = wbState.sketches.some((s) => {
        try {
          const p = JSON.parse(s.data);
          return p.type && p.type.startsWith("link-") && (p.sourceId === item.id || p.targetId === item.id);
        } catch {
          return false;
        }
      });
      document.querySelector('#wb-context-menu [data-wb-ctx="more-mindmap"]')?.classList.toggle("hidden", !hasLink);
    }
  }

  //: The file's surface: what other files call (L634).
  //: For the sweeps: which context-bar kind a selection reads as (maptwokinds, wb1005-library).
  wbUpdateContextBar.sweep = { wbContextKindOf };
  Object.assign(window, { wbSelectedSketchOrNull, wbSelectedTextObjectOrNull, wbPickStyle, wbStickerSize, wbCopySelectedStyle, wbPasteCopiedStyle, wbResetSelectedStyle, wbContextMoreWrap, wbUpdateContextBar });
})();
