(() => {
  // whiteboard-ctxmenu.js: the right-click and long-press menu for a selection.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: Rebuilt on every open rather than cached with static buttons: a card
  //: can't be copied or cut at all (`wbCopySelection`'s own comment: POSTing
  //: a copy would silently move the original instead of duplicating it), and
  //: a menu offering two buttons guaranteed to fail is worse than one that
  //: only ever offers what this selection can actually do.
  function wbBuildContextMenu(kind) {
    if (!wbCtxMenuEl) {
      const menu = document.createElement("div");
      menu.className = "action-menu wb-ctx-menu hidden";
      menu.setAttribute("role", "menu");
      document.body.appendChild(menu);
      wbCtxMenuEl = menu;
    }
    const menu = wbCtxMenuEl;
    menu.replaceChildren();
    const mapNodeForMenu = wbIsMap() && wbMultiSelection.size <= 1 ? wbSelectedMapNode() : null;
    const item = (label, title, fn) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "menu-item";
      button.setAttribute("role", "menuitem");
      button.textContent = label;
      if (title) button.title = title;
      button.addEventListener("click", (e) => {
        e.stopPropagation();
        wbCloseContextMenu();
        if (mapNodeForMenu) wbCloseMapRadial();
        fn();
      });
      menu.appendChild(button);
    };
    //: **A long menu is grouped** (DESIGN.md, the recipe index: "past five rows
    //: it is grouped"). A group of two or more rows is one flyout row, on a
    //: board as on a map (1031 BD10: seventeen flat rows, 629 px): it opens
    //: beside the menu on click, hover or the arrow keys and expands in place on
    //: a phone, so touch and keyboard reach it. `label` is kept for the reader
    //: of this code.
    //: **On a map node the groups fold into flyouts** (owner, with a
    //: screenshot of the 18-row menu: "consolidate and group this more menu a
    //: bit?? it takes up majority of the screen in the mind map"). The same
    //: recipe the note card's menu uses (`buildMenuGroupButton`, app.js): a
    //: group is one row that opens beside the menu on click, hover or the
    //: arrow keys, and expands in place on a phone. Eight rows instead of
    //: eighteen. A group of one is just its row. On a plain board the menu is
    //: short already and keeps its hairline groups.
    const WB_MAP_GROUP_LABELS = {
      Add: "ph:plus Add",
      Content: "ph:note-pencil Topic",
      Lines: "ph:path Line",
      Branch: "ph:tree-structure Branch",
      Order: "ph:stack Order",
      Structure: "ph:tree-view Structure",
      Stamps: "ph:thumbs-up Stamps",
      //: The board's own long menu is grouped the same way (1031 BD10: seventeen
      //: flat rows, 629 px): export, save to the library, arrange and order.
      Library: "ph:books Save to the library",
      Arrange: "ph:align-left Arrange",
      Export: "ph:export Export",
    };
    const subItem = (label, buildSubItems) => {
      const rows = [];
      buildSubItems((subLabel, title, fn) => rows.push([subLabel, title, fn]));
      if (!rows.length) return;
      if (rows.length > 1 && typeof buildMenuGroupButton === "function") {
        menu.appendChild(buildMenuGroupButton(
          WB_MAP_GROUP_LABELS[label] || label,
          rows.map(([subLabel, title, fn]) => ({
            label: subLabel,
            title,
            run: () => {
              wbCloseContextMenu();
              wbCloseMapRadial();
              fn();
            },
          }))
        ));
        return;
      }
      //: Hairlines separate groups of rows; among flyout rows a lone row is just
      //: one more row, and a hairline above it split the list for nothing.
      if (menu.children.length && !mapNodeForMenu) {
        const sep = document.createElement("div");
        sep.className = "menu-sep";
        sep.setAttribute("role", "separator");
        menu.appendChild(sep);
      }
      for (const row of rows) item(...row);
    };
    if (kind !== "node") {
      item("Copy", "Ctrl/Cmd+C", () => wbCopySelection());
      item("Cut", "Ctrl/Cmd+X", () => wbCutSelection());
    }
    //: **The whole of what a topic can do, in words** (MINDMAP_PLAN §12.5, INBOX
    //: 200: "how the item radials are used is confusing and doesnt feel clean").
    //:
    //: A right-click on a map node opens the ring, so this menu used to be dead
    //: code on a map: the audit found all eight of its items unreachable there.
    //: It is now the ring's own "More" and the ContextMenu key, and it carries
    //: every action on a topic, the six in the ring included, because §12.5's
    //: rule is that the ring is a shortcut and never the only way. A list of
    //: words also beats a ring of icons for the things that are rarely wanted
    //: and hard to name in one glyph.
    const mapNode = wbSelectedMapNode();
    if (mapNode && wbMultiSelection.size <= 1) {
      const index = wbMapIndex();
      const folded = Boolean(mapNode.data?.collapsed);
      const kids = (index.childrenOf.get(mapNode.id) || []).length;
      const rooted = mapNode.parent_id == null || !index.byId.has(mapNode.parent_id);
    
      subItem("Add", sub => {
        sub("A child topic", "Tab", () => wbMapAddChild(mapNode.id));
        sub("A topic beside this one", "Enter", () => wbMapAddSibling(mapNode.id));
        if (!(rooted && wbMapLevels(index).get(mapNode.id) === 0)) sub("A parent topic", "Ctrl+Enter", () => wbMapInsertParent(mapNode.id));
        sub("From the library…", "Point a new child at a note, document, file or link", () =>
          wbMapAddReference(mapNode.id)
        );
        //: FEAT-13 (decision 36): children found in the notebook, each saying
        //: which note it came from; nothing is made until they are ticked.
        sub("Branches from my notes…", "Up to five, each from one of your notes; you tick which", () =>
          wbMapSuggestBranches(mapNode)
        );
        //: Phase G: a topic that is a note, grown from the note's own headings and links.
        if (wbMapIsNoteTopic(mapNode)) {
          sub("Expand from my notes…", "Its headings and the notes it links to; you tick which", () =>
            wbMapExpandFromNote(mapNode)
          );
        }
      });

      subItem("Content", sub => {
        //: A task (MINDMAP_PLAN.md decision 15): made here, ticked by its box.
        const task = mapNode.data?.task;
        if (task === "open" || task === "done") {
          sub(task === "done" ? "Mark as not done" : "Mark as done", "Or press the box on the topic", () =>
            wbMapToggleTaskDone(mapNode.id)
          );
          sub("Stop being a task", "The topic stays; its box goes", () => wbMapSetTask(mapNode, null));
        } else {
          sub("Make this a task", "A box to tick; the topics above count what is done", () =>
            wbMapSetTask(mapNode, "open")
          );
        }
        //: A note behind it (MINDMAP_PLAN.md decision 18): written and read in
        //: the popover its marker opens; a topic's only, since a note node
        //: already has the notebook's note behind it.
        if (mapNode.kind === "note" && Number.isInteger(mapNode.data?.ref_id)) {
          sub("Edit the note's text…", "Change the notebook's note from here; Ctrl+Z undoes it", () =>
            wbMapOpenNote(mapNode.id, document.querySelector(`.wb-object[data-id="${mapNode.id}"]`)));
        }
        if (!WB_MAP_REFERENCE_KINDS.has(mapNode.kind)) {
          const hasNote = Boolean(mapNode.data?.note);
          sub(hasNote ? "Open the note…" : "Add a note…",
            hasNote ? "Or press the note mark on the topic" : "Longer text behind the topic, shown when you open it",
            () => wbMapOpenNote(mapNode.id, document.querySelector(`.wb-object[data-id="${mapNode.id}"] .wb-map-note`)));
          if (hasNote) {
            sub("Remove the note", "The topic stays; Ctrl+Z brings the note back", async () => {
              await wbMapSetNodeStyle(mapNode, { note: null });
              renderWhiteboardNow();
              wbAnnounce("Note removed.");
            });
          }
        }
        //: A callout over the topic (XMind; canvasdepth2).
        sub(mapNode.data?.callout ? "Change the callout…" : "Add a callout…", "A few words in a bubble over this topic", () =>
          wbMapEditCallout(mapNode));
        if (mapNode.data?.callout) {
          sub("Remove the callout", "The topic stays; Ctrl+Z brings it back", () =>
            wbMapSetExtra(mapNode, { callout: null }, "Callout removed."));
        }
        //: Labels under the topic (XMind; canvasdepth2).
        const labelled = Boolean(mapNode.data?.labels?.length);
        sub(labelled ? "Change the labels…" : "Add labels…", "Short tags drawn under this topic", () => wbMapEditLabels(mapNode));
        if (labelled) {
          sub("Remove the labels", "The topic stays; Ctrl+Z brings them back", () =>
            wbMapSetExtra(mapNode, { labels: null }, "Labels removed."));
        }
        //: Markers (MINDMAP_PLAN decision 34): priority, progress, a flag, icons.
        sub(wbMapMarkerWords(wbMapMarkerParts(mapNode.data)) ? "Change the markers…" : "Markers…",
          "A priority, how far along it is, a flag and icons", () => wbMapOpenMarkers(mapNode.id));
        for (const fix of wbMapLazy.grammarFixes(mapNode)) sub(fix.label, fix.title, fix.run);
        const comments = wbItemComments("object", mapNode).length;
        sub(comments ? `Comments (${comments})…` : "Comment…", "A thread on this topic, behind the mark on its corner", () =>
          wbOpenComments("object", mapNode.id)
        );
        sub(mapNode.data?.link ? "Change where this topic points…" : "Link this topic to a page…",
          "An http, https or mailto address", () => wbMapEditLink(mapNode));
        if (!WB_MAP_REFERENCE_KINDS.has(mapNode.kind)) {
          sub(mapNode.data?.image ? "Change this topic's picture…" : "Put a picture in this topic…",
            "An image from this computer", () => wbMapEditPicture(mapNode));
          sub("Put a picture from a link…", "An address; fetched here and kept with the board", () => wbMapLazy.imageFromLink(mapNode));
          if (mapNode.data?.image) {
            sub("Take the picture out of this topic", "The upload stays in the library", () =>
              wbMapRemovePicture(mapNode)
            );
          }
        }
        //: **A words door to the colour well** (coordinator: the owner asked
        //: for a customisable node fill colour without knowing
        //: `#wb-map-strip-color` already exists, because nothing that opens by
        //: right-click ever named it: the ring's six slots and this menu's
        //: other rows are all verbs, and "carries every action on a topic"
        //: (§12.5, above) had quietly stopped being true the moment the strip
        //: grew a colour well of its own with no row here to match it).
        //: Opens the exact same picker the strip's swatch does
        //: (`showPicker()`, the `.click()` fallback documents-code.js's own
        //: colour swatch already uses for a browser that lacks it), never a
        //: second colour control: the strip is already showing (this menu only
        //: exists for the node that is selected, which is the strip's own
        //: condition), so there is always a live well to open.
        sub(rooted ? "Topic colour…" : "Branch colour…",
          rooted ? "Colours this topic's own card" : "Carries down to everything under this topic",
          () => {
            const well = document.getElementById("wb-map-strip-color");
            well?.click();
          });
      });

      //: **Its look as a thing to move about** (MINDMAP_PLAN.md decisions 41
      //: and 42): Miro's and Photoshop's copy and paste style, and
      //: Illustrator's Redefine, which hands this topic's look to its level.
      subItem("Look", sub => {
        sub("Copy this topic's style", "Ctrl+Alt+C", () => wbCopySelectedStyle());
        if (wbCopiedStyle?.kind === "topic") sub("Paste style onto this topic", "Ctrl+Alt+V", () => wbPasteCopiedStyle());
        const level = wbMapLevelOf(mapNode);
        if (level !== undefined) {
          sub(`Use this look for ${WB_MAP_LEVEL_NAMES[level]}`,
            "Every topic at this level that was never given its own look follows", () => wbMapUseLookForLevel(mapNode.id));
        }
        sub("How this map looks…", "The hierarchy and each level's look", () => wbMapThemeDialog());
      });

      subItem("Lines", sub => {
        if (!rooted && mapNode.data?.edge_label) {
          sub("Take the label off the line", "The line into this topic keeps its shape", async () => {
            await wbMapSetNodeStyle(mapNode, { edge_label: null, edge_label_dx: null, edge_label_dy: null });
            renderWhiteboardNow();
          });
        }
        if (!rooted && (mapNode.data?.edge_bend || mapNode.data?.edge_slide)) {
          sub("Straighten the line into this topic", "Or double-click the dot on the line", () =>
            wbMapStraightenEdge(mapNode)
          );
        }
        if (!rooted && (mapNode.data?.edge_from || mapNode.data?.edge_to)) {
          sub("Line ends: back to Auto", "Or double-click an end of the line", () =>
            wbMapAutoEdgeEnds(mapNode)
          );
        }
        sub("Connect this topic to another", "Shift+C, then drag to the other topic", () => {
          //: Through the module's handle: `selectWbTool` lives inside
          //: `initWhiteboard`, so a bare call from this top-level builder threw
          //: and the row did nothing (found by `maplinkcue.js`, 2026-10-04).
          wbSelectToolRef?.("link-straight");
          toast("Drag from this topic to the one it should join.");
        });
      });

      subItem("Branch", sub => {
        if (kids) sub(folded ? "Open this branch again" : "Fold this branch away", "C", () =>
          wbMapToggleCollapse(mapNode.id)
        );
        sub(wbMapFocusState && wbMapFocusState.id === mapNode.id ? "Show the whole map again" : "Focus here",
          "F", () => {
            if (wbMapFocusState && wbMapFocusState.id === mapNode.id) wbMapClearFocus();
            else wbMapSetFocus(mapNode.id);
          });
        if (kids) sub("Lay this branch out again", "Tidy this topic and everything under it", async () => {
          const moved = await wbMapTidy({ onlyBranch: mapNode.id, quiet: true });
          toast(moved
            ? `Laid out ${nounCount(moved, "topic")}.`
            : "This branch is already where the layout puts it.");
        });
        sub("Copy this branch", "This topic and everything under it, beside itself", () =>
          wbMapCopyBranch(mapNode.id)
        );
        sub("Copy this branch as an outline", "Markdown, to paste into a note or another app", () =>
          wbMapCopyBranchOutline(mapNode.id)
        );
        sub("Export this branch…", "A picture or PDF of this topic and everything under it", () =>
          wbMapExportBranch(mapNode.id)
        );
        sub("Save this branch as Markdown", "A .md file of this topic and everything under it", () => wbMapLazy.saveBranch(mapNode));
        sub("Copy this topic's shape", "Its look and branch layout, to paste onto another", () => wbMapLazy.copyShape(mapNode));
        sub("Paste the copied shape here", "One Undo step", () => wbMapLazy.pasteShape(mapNode));
        sub("Add a template branch…", "Pros and cons, SWOT, the five questions, a meeting agenda", () => wbMapLazy.pickTemplate(mapNode));
        sub("Add a second central topic…", "Joined to this one by a link that can carry words", () => wbMapLazy.secondRoot(mapNode));
        if (!(rooted && wbMapLevels(index).get(mapNode.id) === 0)) sub("Move under…", "M: pick the topic to put this branch under", () =>
          wbMapMoveUnder(mapNode.id)
        );
        if (!rooted) sub("Cut this topic free of its parent", "It becomes a trunk of its own", () =>
          wbMapSever(mapNode.id)
        );
        sub("Reset branch styling", "Drop this topic's own colour, size, weight, alignment, shape, icon, link and line", () =>
          wbMapResetToBranch(mapNode.id)
        );
        //: A boundary round the branch (MINDMAP_PLAN decision 19).
        const boundary = mapNode.data?.boundary;
        if (!boundary && wbMapLazy.boundaryTargets().length > 1) {
          sub("Draw a boundary round the selected topics", "One shape round just these topics, whichever branches they are on", () => wbMapLazy.boundaryDraw());
        }
        if (!boundary) {
          sub("Draw a boundary round this branch", "A shaded shape round this topic and everything under it, in the branch colour", () =>
            wbMapSetStructure(mapNode, { boundary: "rounded" }, "Boundary drawn."));
        } else {
          for (const [style, words] of [["rounded", "Make the boundary solid"], ["dashed", "Make the boundary dashed"], ["cloud", "Make the boundary a cloud"]]) {
            if (style !== boundary) sub(words, "Its colour is the branch colour", () => wbMapSetStructure(mapNode, { boundary: style }));
          }
          sub(mapNode.data?.boundary_label ? "Change the boundary's label…" : "Label the boundary…", "Words over its top edge", () =>
            wbMapAskStructureWords(mapNode, "boundary_label", "What should the boundary say?", "Label it"));
          sub("Remove the boundary", "The topics stay; Ctrl+Z brings it back", () =>
            wbMapSetStructure(mapNode, { boundary: null, boundary_label: null, boundary_set: null }, "Boundary removed."));
        }
        //: A summary beside a run of siblings (decision 20); a root takes none.
        if (!rooted && mapNode.data?.summary) {
          sub("Change the summary…", "The words beside the brace", () =>
            wbMapAskStructureWords(mapNode, "summary", "What do these topics come to? A few words beside them.", "Change the summary"));
          sub("Remove the summary", "The topics stay; Ctrl+Z brings it back", () =>
            wbMapSetStructure(mapNode, { summary: null, summary_span: null }, "Summary removed."));
        } else if (!rooted) {
          sub("Summarise this topic…", "A brace beside it with your words; select several side by side to summarise them together", () =>
            wbMapSummarise([mapNode]));
        }
      });
      //: Reaction stamps and votes (Miro; MINDMAP_PLAN 14.4): each a toggle for
      //: you (INBOX 1493), the chip's own menu takes a count down.
      subItem("Stamps", sub => {
        for (const [name, , said] of WB_MAP_STAMPS) {
          const count = mapNode.data?.stamps?.[name] || 0;
          const yours = Array.isArray(mapNode.data?.stamped) && mapNode.data.stamped.includes(name);
          sub(count ? `${said} (${count}${yours ? ", yours" : ""})` : said, yours ? "Takes yours back; or press it on the topic" : "Adds yours; or press it on the topic", () => wbMapStampSet(mapNode, name, "toggle"));
        }
        if (Object.keys(mapNode.data?.stamps || {}).length) {
          sub("Clear the stamps", "Every count on this topic; Ctrl+Z brings them back", () =>
            wbMapSetExtra(mapNode, { stamps: null, stamped: null }, "Stamps cleared."));
        }
      });
      //: A structure for this branch alone (XMind; canvasdepth2).
      if (kids) subItem("Structure", sub => {
        const own = mapNode.data?.branch_layout;
        if (own) sub("Follow the map's layout", "This branch is laid out as the rest of the map is", () => wbMapSetBranchLayout(mapNode, null));
        for (const [value, name] of WB_MAP_BRANCH_STRUCTURES) {
          if (value !== own) sub(name, "This topic's branch only; the map keeps its own layout", () => wbMapSetBranchLayout(mapNode, value));
        }
      });
    }
    //: A table's rows and columns (canvasdepth2), at the cell last pressed.
    if (kind === "object" && wbSelectedItem?.kind === "object" && wbMultiSelection.size <= 1) {
      const table = (wbState.objects || []).find((o) => o.id === wbSelectedItem.id && o.kind === "table");
      if (table) for (const [label, title, fn] of wbTableMenuRows(table)) item(label, title, fn);
    }
    //: The words for decision 12's gesture, so typing into a shape is found
    //: by someone who has not tried a double-click on it.
    if (kind === "sketch" && wbSelectedItem?.kind === "sketch" && wbMultiSelection.size <= 1) {
      const shape = (wbState.sketches || []).find((s) => s.id === wbSelectedItem.id);
      const parsed = shape ? wbSketchParsedData(shape) : null;
      if (wbShapeLabelKind(parsed)) {
        item(parsed.label ? "Edit the text" : "Add text", "Double-click the shape, or press Enter", () =>
          wbEditShapeLabel(shape)
        );
      }
      let linkParsed = null;
      try {
        linkParsed = shape ? JSON.parse(shape.data) : null;
      } catch {
        linkParsed = null;
      }
      if (wbLinkTakesLabel(shape, linkParsed)) {
        item(linkParsed.label ? "Edit the label" : "Add a label", "Or select the connector and press Enter", () =>
          wbEditLinkLabel(shape)
        );
      }
    }
    // Asked for directly. Available for every kind, a sketch reorders
    // against other sketches, a card/object against both (wbZOrderPeers'
    // own comment has the full reasoning for that split).
    //: **Several topics: the map's verbs, in words** (INBOX 617), the same
    //: five the bar's `mapmulti` group has, each a toggle over the whole
    //: selection (`WB_MAP_MULTI_ACTIONS`). A summary only over siblings
    //: (MINDMAP_PLAN 20).
    const mapTopics = wbMapMultiTopics();
    if (mapTopics) {
      const state = wbMapMultiState(mapTopics);
      subItem("Topics", (sub) => {
        sub(state.bold ? "Not bold" : "Bold", "Every topic picked", () => WB_MAP_MULTI_ACTIONS.bold(mapTopics));
        sub(state.tasks ? "Stop being tasks" : "Make these tasks", "A box to tick on each", () => WB_MAP_MULTI_ACTIONS.task(mapTopics));
        sub("Colour these…", "Carries down each one's branch", () => {
          const well = document.getElementById("wb-mapmulti-color");
          well?.click();
        });
        if (state.branches.length) {
          sub(state.folded ? "Open these branches" : "Fold these branches", "The topics picked that have anything under them", () =>
            WB_MAP_MULTI_ACTIONS.fold(mapTopics));
        }
        if (state.siblings) {
          sub("Summarise these topics…", "A brace beside them with your words", () => WB_MAP_MULTI_ACTIONS.summary(mapTopics));
        }
      });
    }
    //: Decision 15: held in place until unlocked from the board's own menu.
    //: Decision 17: one item's thread, from its menu as from its mark.
    const commentOn = !mapNode && wbMultiSelection.size <= 1 && wbSelectedItem ? wbSelectedItem : null;
    const commentItem = commentOn && wbFindItem(commentOn.kind, commentOn.id);
    if (wbTakesComments(commentOn?.kind, commentItem)) {
      const count = wbItemComments(commentOn.kind, commentItem).length;
      item(count ? `Comments (${count})…` : "Comment…", "A thread on this item, behind the mark on its corner", () =>
        wbOpenComments(commentOn.kind, commentOn.id)
      );
    }
    //: A shape's own link (draw.io Edit link): set, open or take off.
    const linkRow = wbCommandMenuRow("item-link");
    if (linkRow && commentOn) item(wbItemLink(commentOn.kind, commentItem) ? "Link: open, change or remove…" : "Link…", "Link this to a note or a web page", () => wbEditItemLink());
    //: A frame is an export scope (WHITEBOARD_PLAN decision 18).
    const frameOn = commentOn?.kind === "object" && commentItem?.kind === "frame" ? commentItem : null;
    if (frameOn) item("Fit to contents", "Snug the frame to what is inside it, with a margin all round", () => wbFrameFit(frameOn, "nesw"));
    if (frameOn) item("Export this frame…", "The frame and what is inside it, as a picture, PDF or SVG", () => wbExportFrame(frameOn));
    //: L-whiteboard-12: a frame bound to a note property is a kanban column; a
    //: card dropped inside sets that property on its note to the frame's title.
    if (frameOn) item(frameOn.data?.binds ? `Unbind from ${frameOn.data.binds.property}` : "Bind to a property…", "Cards dropped in this frame set a property on their note to the frame's title", async () => {
      const title = String(frameOn.data?.content || "").trim();
      let binds = null;
      if (!frameOn.data?.binds) {
        if (!title) return toast("Name the frame first: its title is the value cards take.", "info");
        const prop = (await promptDialog("Bind to which note property?", "status"))?.trim();
        if (!prop) return;
        if (prop.includes(":")) return toast("A property's name can't hold a colon.", "info");
        binds = { property: prop, value: title };
      }
      wbPushUndo({ action: "move", kind: "object", id: frameOn.id, before: WB_KIND_INFO.object.payload(frameOn) });
      frameOn.data = { ...frameOn.data, binds };
      await wbSaveObject(frameOn);
      toast(binds ? `Cards dropped here get ${binds.property}: ${binds.value}.` : "Unbound. Cards dropped here leave their notes alone.");
    });
    //: A selection leaves the board as a picture (K33): the dialog on its
    //: Selection scope, or straight to the clipboard as a PNG or as SVG text.
    if (wbMultiSelection.size > 0 || wbSelectedItem) {
      subItem("Export", (sub) => {
        sub("Export selection…", "The selection as a PNG or SVG, with its links", () => wbExportBoard());
        sub("Copy as image", "A PNG of the selection on the clipboard", () => wbCopyAsImage());
        sub("Copy as SVG", "The selection as SVG text on the clipboard", () => wbCopyAsSvg());
      });
    }
    //: Into the library's "Yours" (decision 25): the rows the table says apply.
    subItem("Library", (sub) => {
      for (const id of ["save-selection", "update-from-library", "unlink-library", "save-branch", "save-shape", "save-style", "save-preset", "save-palette"]) {
        const row = wbCommandMenuRow(id);
        if (row) sub(...row);
      }
    });
    //: The rows the Arrange menu also has come from `WB_COMMANDS`, so the two
    //: say the same words and keys (FEAT-07: this menu called the front "Bring
    //: to front" while the bar's "Bring forward" did the same thing). Not on a
    //: map: a topic's place in a tree is its order (FEAT-17).
    if (!wbIsMap()) {
      subItem("Arrange", (sub) => {
        for (const id of ["group", "ungroup", "lock", "flip-h", "flip-v", "flip-layout-h", "flip-layout-v", "parallel-edges", "change-shape", "replace-library", "edit-ports", "edit-points", "reset-ports", "tidy-down", "tidy-right", "layout-flow-h", "layout-flow-v", "layout-radial", "layout-org", "layout-organic", "layout-circle"]) {
          const row = wbCommandMenuRow(id);
          if (row) sub(...row);
        }
      });
    }
    //: A Free map can overlap, so it keeps Order; a tidied tree cannot
    //: (audit FEAT-17).
    if (!wbIsMap() || wbMapLayout() === "free") {
      subItem("Order", (sub) => {
        for (const id of ["order-forward", "order-backward", "order-front", "order-back"]) {
          const row = wbCommandMenuRow(id);
          if (row) sub(...row);
        }
      });
    }
    item("Delete", "Delete", () => {
      wbCloseMapRadial();
      deleteWbSelection();
    });
    return menu;
  }

  //: **The context bar's "More" menu opens against the bar, whatever the
  //: window's height** (the owner, 2026-09-23: "its kebab menu lands away from
  //: the bar"). `placeEscapedMenu` (menus.js) tries below the opener, then above,
  //: and when neither side holds the whole menu it pins the box to the last
  //: position that fits in the window, which is right for a card's menu whose
  //: opener has scrolled out of view and wrong for a bar floating over the
  //: canvas: measured at 947x608 (1184x760 at 125% zoom), the 333px menu was
  //: put at 267 to 600 with the bar at 316 to 354, over the bar it came from
  //: and 86px from either edge of it.
  //:
  //: So for this bar the menu takes the side with more room, starts or ends
  //: one gap from the bar's own edge (the bar, not the toggle: the toggle is
  //: 5px inside it), and scrolls inside whatever height that side has. Only
  //: for a menu that was escaped to <body>: one the stylesheet placed was not
  //: clipped and already sits under the bar. Set, measured and corrected by
  //: the difference (DESIGN.md, a popup in the window's own coordinates).
  function wbKeepMenuBesideBar(menu, bar) {
    if (!menu || !bar || !menu._escapedHome) return;
    const margin = 8;
    const gap = 2;
    const edge = bar.getBoundingClientRect();
    if (!edge.width || !edge.height) return;
    menu.style.maxHeight = "none";
    const natural = menu.getBoundingClientRect().height;
    const below = window.innerHeight - margin - (edge.bottom + gap);
    const above = edge.top - gap - margin;
    const useBelow = natural <= below || below >= above;
    const room = Math.max(120, Math.floor(useBelow ? below : above));
    const shown = Math.min(natural, room);
    const want = useBelow ? edge.bottom + gap : edge.top - gap - shown;
    menu.style.maxHeight = `${room}px`;
    menu.style.top = `${Math.round(want)}px`;
    const got = menu.getBoundingClientRect().top;
    if (Math.abs(got - want) > 0.5) menu.style.top = `${Math.round(want + (want - got))}px`;
  }

  function wbCloseContextMenu() {
    wbCtxMenuEl?.classList.add("hidden");
  }

  //: **The node's own menu, opened deliberately** (§12.5). The right-click on a
  //: map node belongs to the ring, so this is the other door: the ring's "More"
  //: slot and the ContextMenu key (Shift+F10 on a keyboard without one). It is
  //: the same builder and the same clamp the pointer route uses, because two
  //: menus for one node is how the two come to say different things.
  //:
  //: **Beside the button that opened it, when there is one** (INBOX 394 (d), the
  //: owner: "the dropdown menu doesnt appear next to it but the bottom right").
  //: The ring's More used to pass the whole ring's right edge and top, and the
  //: ring is wider and taller than its More slot: measured at 1440x900 the menu
  //: opened 30 to 41px down and to the right of More, and where the window was
  //: short it was then clamped further away. `opener` is that button: the menu
  //: goes on its right with its top level with the button's, or on its left
  //: when the right has no room, and is clamped into the window on the other
  //: axis. Set, measured and corrected by the difference, the recipe DESIGN.md
  //: gives a popup placed in the window's coordinates.
  //: **A box worth hanging a menu from** (INBOX 421 a, the owner's desktop
  //: window, again: "when I press the more button the dropdown menu appears in
  //: the top left of my screen"). A detached or hidden element's rect is all
  //: zeroes, and a box whose far corner is at or above the window's own corner
  //: is nowhere the person was looking: both are refused here rather than
  //: trusted, because every earlier corner in this file came from trusting one.
  function wbMenuAnchorOk(r) {
    return Boolean(r && Number.isFinite(r.left) && Number.isFinite(r.top)
      && r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0);
  }

  //: The topic's own box on screen, the last honest anchor a node's menu has.
  function wbMapNodeScreenBox(node) {
    const box = document.querySelector(`.wb-object[data-id="${node?.id}"]`)?.getBoundingClientRect();
    return wbMenuAnchorOk(box) ? box : null;
  }

  //: **The corner guard.** A menu that ends up at the window's top-left corner
  //: when what opened it was not there is a placement that went wrong, whatever
  //: the route; this says so in the console (which is what the owner can send
  //: back from the desktop window, where no sweep reaches) and puts the menu
  //: back beside `fallback`. Checked once now and once a frame later, because
  //: the report survived every fix to the synchronous path, so if anything
  //: moves the menu after it is placed, the second look is what catches it.
  function wbGuardMenuCorner(menu, why, fallback) {
    const cornered = () => {
      if (!menu || menu.classList.contains("hidden")) return false;
      const r = menu.getBoundingClientRect();
      return r.left <= 9 && r.top <= 9;
    };
    const fix = (when) => {
      if (!cornered()) return;
      const box = typeof fallback === "function" ? fallback() : fallback;
      console.warn(`[whiteboard] refused a menu at the window's corner (${why}, ${when})`, box ? { left: Math.round(box.left), top: Math.round(box.top) } : "no anchor");
      if (!wbMenuAnchorOk(box)) {
        menu.classList.add("hidden");
        return;
      }
      menu.style.maxHeight = "";
      wbSetMenuSpot(menu, wbMenuSpotBeside(box, menu.getBoundingClientRect()), why);
    };
    fix("placed");
    requestAnimationFrame(() => fix("next frame"));
  }

  function wbOpenMapNodeMenu(node, clientX, clientY, opener = null) {
    if (!node) return;
    let anchor = typeof opener?.getBoundingClientRect === "function" ? opener.getBoundingClientRect() : opener;
    if (!wbMenuAnchorOk(anchor)) anchor = null;
    //: **Never from (0,0).** A point of 0,0 is what a click made from the
    //: keyboard carries and what a zero-sized ring reads once hidden; it is not
    //: a place anyone pointed at. With no box and no point left, the menu does
    //: not open at all rather than open in the corner, and says why.
    if (!(clientX > 0 || clientY > 0)) {
      clientX = 0;
      clientY = 0;
      if (!anchor) anchor = wbMapNodeScreenBox(node);
      if (!anchor) {
        console.warn("[whiteboard] refused to open a topic's menu at (0,0): no anchor to place it by", { node: node.id });
        return;
      }
    }
    const menu = wbBuildContextMenu("object");
    menu.classList.remove("hidden");
    //: A height cap left by the last open that had to scroll is not this
    //: open's: measured with it the menu reads short and is placed as if it fit.
    menu.style.maxHeight = "";
    const margin = 8;
    const size = menu.getBoundingClientRect();
    let left = clientX;
    let top = clientY;
    //: **Never the window's corner** (the owner, 2026-09-24: "I clicked the
    //: more button on a mind map node and it appeared ip the top left middle
    //: section"). Every route to the corner was one where nothing measurable
    //: was left to hang the menu from: an opener with no box (a sector read
    //: while its ring was hidden, or a button whose rect is the whole ring) and
    //: a point of 0,0, which is what a click made from the keyboard carries and
    //: what the ring's own zero-sized box gives once hidden. The clamp below
    //: then turned 0,0 into 8,8, over the tab bar. So a missing anchor falls
    //: back to the topic's own box, which is always on screen when its menu is
    //: asked for, and the corner is no longer a place this menu can open.
    let spot;
    if (anchor) {
      spot = wbMenuSpotBeside(anchor, size);
    } else {
      left = Math.min(Math.max(margin, left), Math.max(margin, window.innerWidth - size.width - margin));
      top = Math.min(Math.max(margin, top), Math.max(margin, window.innerHeight - size.height - margin));
      spot = { left, top, maxHeight: null };
    }
    wbSetMenuSpot(menu, spot, "topic menu");
    menu.querySelector(".menu-item")?.focus({ preventScroll: true });
    wbGuardMenuCorner(menu, "topic menu", () => anchor || wbMapNodeScreenBox(node));
  }

  //: **Where a menu goes beside a box, when a side can be too small** (INBOX
  //: 421 a, the third report from the desktop window: the topic menu over the
  //: top-left of the window, with the text large). The placement knew two
  //: spots, left or right of the More sector with its top level with the
  //: sector's, and when neither had room it fell back to a clamp into the
  //: window that no longer knew about the sector at all. Nothing in a sweep at
  //: 1440x900 ever reached that fallback. The desktop window does: Windows'
  //: display scale divides the window, so a 1256px window at 150% is an 837px
  //: page and at 200% a 628px one, the app's own zoom (up to 130%) makes the
  //: menu wider and taller, and the pie ring is several hundred px across in
  //: the middle of it. Measured before this (mapmorezoom.js), 1256x1366 at
  //: 200% and zoom 130: neither side of More had room for the 310px menu, the
  //: clamp pushed it to x 8, and it opened over More itself, from 199 to 675.
  //:
  //: So the spots are tried in order, each one only if the whole menu fits in
  //: it: the side the sector faces, the other side (both slid up or down to
  //: stay in the window, which keeps them level with some of the sector),
  //: then below and above the box, lined up with its outer edge. When none
  //: holds the whole menu it goes on whichever of above or below has more
  //: room, capped to that room and scrolling inside it (`.action-menu` already
  //: scrolls), because a menu that fits nowhere whole is still one that must
  //: not cover what opened it. The window's edges are the client area's, so a
  //: real scrollbar (Windows draws one, headless does not) is not counted as
  //: room.
  function wbMenuSpotBeside(anchor, size, margin = 8, gap = 4) {
    const W = document.documentElement.clientWidth || window.innerWidth;
    const H = document.documentElement.clientHeight || window.innerHeight;
    const w = size.width;
    const h = size.height;
    //: A menu taller than the whole window can still go on a side: it is
    //: capped to the window there, which keeps it level with the sector.
    const tall = Math.max(0, H - 2 * margin);
    const sideH = Math.min(h, tall);
    const inX = (x) => Math.min(Math.max(margin, x), Math.max(margin, W - w - margin));
    const inY = (y) => Math.min(Math.max(margin, y), Math.max(margin, H - sideH - margin));
    const sides = anchor.outward === "left" ? ["left", "right"] : ["right", "left"];
    for (const side of sides) {
      const x = side === "left" ? anchor.left - gap - w : anchor.right + gap;
      if (x >= margin && x + w <= W - margin) return { left: x, top: inY(anchor.top), maxHeight: sideH < h ? Math.floor(sideH) : null, side };
    }
    //: Lined up with the edge the sector faces, so a left sector's menu hangs
    //: from its left edge outward rather than across the ring.
    const x = inX(anchor.outward === "left" ? anchor.right - w : anchor.left);
    const below = H - margin - (anchor.bottom + gap);
    const above = anchor.top - gap - margin;
    if (h <= below) return { left: x, top: anchor.bottom + gap, maxHeight: null, side: "below" };
    if (h <= above) return { left: x, top: anchor.top - gap - h, maxHeight: null, side: "above" };
    if (below >= above) return { left: x, top: anchor.bottom + gap, maxHeight: Math.floor(below), side: "below" };
    const room = Math.floor(above);
    return { left: x, top: anchor.top - gap - room, maxHeight: room, side: "above" };
  }

  //: Set, measured and corrected by the difference (DESIGN.md, a popup in the
  //: window's coordinates), with one refusal the corner report asked for: a
  //: correction that would take the menu out of the window is a measurement
  //: gone wrong, not an offset to undo, so the plain placement is kept and the
  //: console says what was read. This is the only line in the node menu that
  //: could ever write a top above the window's own (a read with the menu
  //: somewhere other than where it was just put), which is what the owner's
  //: screenshot showed.
  function wbSetMenuSpot(menu, spot, why) {
    const { left, top } = spot;
    menu.style.maxHeight = spot.maxHeight ? `${spot.maxHeight}px` : "";
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
    const got = menu.getBoundingClientRect();
    const dx = got.left - left;
    const dy = got.top - top;
    if (Math.abs(dx) <= 0.5 && Math.abs(dy) <= 0.5) return;
    const W = document.documentElement.clientWidth || window.innerWidth;
    const H = document.documentElement.clientHeight || window.innerHeight;
    const fixedLeft = left - dx;
    const fixedTop = top - dy;
    if (fixedLeft < 0 || fixedTop < 0 || fixedLeft + got.width > W || fixedTop + got.height > H) {
      console.warn(`[whiteboard] refused a correction that would put the ${why} outside the window`, {
        set: { left: Math.round(left), top: Math.round(top) },
        read: { left: Math.round(got.left), top: Math.round(got.top) },
      });
      return;
    }
    menu.style.left = `${Math.round(fixedLeft)}px`;
    menu.style.top = `${Math.round(fixedTop)}px`;
  }

  //: Selects whatever the gesture landed on (unless it's already part of a
  //: multi-selection: right-clicking one member of a group opens the menu
  //: for the whole group, same rule a plain click already uses) and opens the
  //: menu at the pointer, clamped to the viewport the same way the docked
  //: toolbar menu already clamps itself.
  function wbOpenContextMenuFor(kind, id, clientX, clientY) {
    const key = wbMultiKey(kind, id);
    //: **A cross-link on a map gets the map's ring** (§13c), before the
    //: selection is touched: selecting it would put the board's own context bar
    //: over the ring, which is the surface this is replacing.
    //: `<= 1`, the same rule the node ring takes: a multi-selection keeps the
    //: flat menu, because its actions are the only ones that mean anything for
    //: more than one item. Anything less than that and the ring would be
    //: withheld from the ordinary case of right-clicking a line while a topic
    //: happens to be selected, which is how this was first written and what its
    //: own sweep caught.
    if (kind === "sketch" && wbMultiSelection.size <= 1 && wbOpenMapCrossLinkRadial(id, clientX, clientY)) return;
    if (!wbMultiSelection.has(key)) wbHandleItemClick(kind, id, { shiftKey: false });
    //: **A map node gets the ring, not the list** (MINDMAP_PLAN.md §12.1 item
    //: 3). Routed here rather than at the two gestures because right-click and
    //: touch-and-hold both already arrive at this one function: splitting the
    //: decision across both is how one of them ends up opening the other thing.
    //: A multi-selection keeps the flat menu, which is the only one of the two
    //: whose actions mean anything for more than one item.
    const ringNode = wbMultiSelection.size === 0 ? wbSelectedMapNode() : null;
    if (ringNode && ringNode.id === id) {
      wbCloseContextMenu();
      if (wbOpenMapRadial(ringNode)) return;
    }
    wbCloseMapRadial();
    // A multi-selection offers Copy and Cut when there is something in it a
    // copy can be made of (`wbCopyableSelection`), and otherwise gets the same
    // "node" treatment as a card, rather than two buttons that do nothing.
    const menuKind = wbMultiSelection.size > 0
      ? (wbCopyableSelection({ quiet: true }) ? "multi" : "node")
      : kind;
    //: A gesture with no point (0,0, as a menu key or a synthetic event
    //: carries) opens by the item it was made on, never in the corner.
    if (!(clientX > 0 || clientY > 0)) {
      const el = document.querySelector(`[data-id="${CSS.escape(String(id))}"]`);
      const box = el?.getBoundingClientRect();
      if (!wbMenuAnchorOk(box)) {
        console.warn("[whiteboard] refused to open a context menu at (0,0): no anchor to place it by", { kind, id });
        return;
      }
      clientX = box.left + box.width / 2;
      clientY = box.bottom + 4;
    }
    const menu = wbBuildContextMenu(menuKind);
    menu.classList.remove("hidden");
    menu.style.left = `${clientX}px`;
    menu.style.top = `${clientY}px`;
    const margin = 8;
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth - margin) {
      menu.style.left = `${Math.max(margin, window.innerWidth - rect.width - margin)}px`;
    }
    if (rect.bottom > window.innerHeight - margin) {
      menu.style.top = `${Math.max(margin, window.innerHeight - rect.height - margin)}px`;
    }
    wbGuardMenuCorner(menu, `${kind} context menu`, () => ({ left: clientX, top: clientY, right: clientX, bottom: clientY + 1, width: 1, height: 1 }));
  }

  document.addEventListener("click", (e) => {
    if (wbCtxMenuEl && !wbCtxMenuEl.classList.contains("hidden") && !e.target.closest(".wb-ctx-menu")) {
      wbCloseContextMenu();
    }
    // The ring closes on a click anywhere but itself, the same rule. Its own
    // slots close it from their handlers instead, after they have acted.
    if (!e.target.closest("#wb-map-radial")) wbCloseMapRadial();
    if (!e.target.closest("#wb-map-link-radial")) wbCloseMapLinkRadial();
  });
  document.addEventListener("keydown", (e) => {
    //: A keydown with no `key` (the owner's log, 2026-10-10: "Cannot read
    //: properties of undefined (reading 'startsWith')" here, from the desktop
    //: webview) is nobody's shortcut; every reader below wants a string.
    if (typeof e.key !== "string") return;
    if (e.key === "Escape") {
      wbCloseContextMenu();
      wbCloseMapRadial();
      wbCloseMapLinkRadial();
    }
    // Alt is a live modifier while the ring is open, so it is watched here
    // rather than read only at the click: the two add slots re-label themselves
    // the moment it goes down. `e.altKey` rather than `e.key === "Alt"` so the
    // ring is right even when Alt arrives with another key held.
    if (wbMapRadialFor != null) wbSyncMapRadialAlt(e.altKey);
    //: **An arrow with a ring open goes into the ring** (the pie menu): the
    //: sector nearest that direction takes the focus, and from there the ring's
    //: own keys walk it. Before the board's handler, which would otherwise walk
    //: the tree and leave the ring open about a topic no longer selected. Not
    //: while typing, and not with a modifier (Alt+arrow and friends belong to
    //: whoever has them).
    if (e.key.startsWith("Arrow") && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      const open = [...document.querySelectorAll(".wb-map-radial:not(.hidden)")][0];
      const active = document.activeElement;
      const typing = active && (active.isContentEditable || /^(input|textarea|select)$/i.test(active.tagName));
      if (open && !typing && !open.contains(active)) {
        const to = wbMapRadialToward(open, e.key);
        if (to) {
          e.preventDefault();
          e.stopImmediatePropagation();
          to.focus();
        }
      }
    }
  });
  document.addEventListener("keyup", (e) => {
    if (wbMapRadialFor != null) wbSyncMapRadialAlt(e.altKey);
  });

  //: Wires the gesture onto one item type's `enter()` selection: called
  //: right after that type's own `.on("click", ...)` is set up, so it only
  //: needs binding once per element the same way click already is (d3 keeps
  //: the same DOM node across a keyed re-render, so a handler bound on enter
  //: persists without needing to be re-applied on every update/merge).
  //: Is this pointer target inside something that is *actually* being typed
  //: into? One place, because the attribute-versus-element mistake below has
  //: now been made twice in this file for two different gestures.
  function wbIsEditingTarget(target) {
    const editable = target?.closest?.("[contenteditable]");
    return Boolean(editable && editable.isContentEditable);
  }

  function wbWireContextMenu(selection, kind) {
    let holdTimer = null;
    const cancelHold = () => {
      if (holdTimer) {
        clearTimeout(holdTimer);
        holdTimer = null;
      }
    };
    selection
      .on("contextmenu.wbctx", (event, d) => {
        // A text object's own editable body needs its native context menu
        // (cut/copy/paste, spellcheck): hijacking it here would make the
        // text box's contenteditable unusable with the mouse.
        //
        // **Asked of the element, not of the attribute.** `closest(
        // "[contenteditable]")` matches `contenteditable="false"` too, because
        // an attribute selector tests that the attribute is *there*. Every text
        // box and every map node on this board carries exactly that attribute
        // while it is not being edited (`wbBuildMapNode`, and the object render
        // below), so this guard fired on all of them and a right-click on a
        // topic opened nothing at all: found by opening the node radial's own
        // sweep and watching the ring never appear. Same lesson `objDrag`'s own
        // filter records a hundred lines further down, in the same words: ask
        // whether it *is* editable.
        if (wbIsEditingTarget(event.target)) return;
        event.preventDefault();
        event.stopPropagation();
        wbOpenContextMenuFor(kind, d.id, event.clientX, event.clientY);
      })
      // Touch has no right-click, so a hold stands in for it, same 500ms
      // threshold and cancel-on-release/move shape as the toolbar toggle's own
      // long-press (wbWireToggleGestures, a few hundred lines up).
      .on("pointerdown.wbctx", (event, d) => {
        if (event.pointerType !== "touch") return;
        if (wbIsEditingTarget(event.target)) return;
        cancelHold();
        holdTimer = setTimeout(() => {
          holdTimer = null;
          wbOpenContextMenuFor(kind, d.id, event.clientX, event.clientY);
        }, 500);
      })
      .on("pointerup.wbctx pointercancel.wbctx pointermove.wbctx", cancelHold);
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbKeepMenuBesideBar, wbCloseContextMenu, wbMenuAnchorOk, wbMapNodeScreenBox, wbOpenMapNodeMenu, wbIsEditingTarget, wbWireContextMenu });
})();
