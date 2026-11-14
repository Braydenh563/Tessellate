(() => {
  // whiteboard-map-look.js: map topic fill, focus and look helpers.
  // Moved out of whiteboard-map.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: A topic's fill as drawn: `solid`, `tint` or nothing. Its own or its
  //: branch's (`wbMapFills`) first, then its level's.
  function wbMapFillOf(d, fills) {
    const said = fills?.get(d.id);
    if (said === "solid" || said === "tint") return said;
    if (said === false) return null;
    const level = wbMapLevelLook(d).fill;
    return level === "solid" || level === "tint" ? level : null;
  }

  //: **A stored name for the app's own default** (MINDMAP_PLAN.md decision 9's
  //: narrow case, built). The strip's selects store the app's default as no
  //: value, which on a map that themes the field means "follow the map", so a
  //: topic could not be pulled back to the app's own look there. Each name
  //: below is a value a topic can carry that draws exactly what no value draws,
  //: and being a value it beats the theme. The server's `MAP_APP_DEFAULT_PINS`
  //: is the same table, and validates every one of them.
  const WB_MAP_APP_DEFAULT_PINS = Object.freeze({
    font_size: 0,
    align: "auto",
    shape: "rounded",
    spine: "solid",
    edge_width: "normal",
    edge_style: "curve",
  });

  //: What one field draws, with a pin read as the default it names: nothing.
  //: The stylesheet keys the looks off attributes (`:not([data-shape])` is how a
  //: core idea gets its own shape), so a pin painted as `data-shape="rounded"`
  //: would be a value that quietly changes what the default does.
  function wbMapDrawn(data, field) {
    const value = data?.[field];
    return value === WB_MAP_APP_DEFAULT_PINS[field] ? undefined : value;
  }

  //: **The map's font** (§13e's remainder). One face for every topic and line
  //: label on the map, set as `--wb-map-font` on the Library's whiteboard view
  //: and read by `.wb-map-node` and `.wb-map-edge-label`; the image export reads
  //: the same stack (`wbMapFontStack`), which is the second place a map's text
  //: is drawn. The three are stacks of faces that ship with the systems this
  //: app runs on, since nothing here is fetched: a font that is not installed
  //: would be a choice that visibly does nothing.
  const WB_MAP_FONTS = Object.freeze({
    serif: MD_RUN_FONTS.serif,
    mono: MD_RUN_FONTS.mono,
    wide: MD_RUN_FONTS.wide,
  });

  function wbMapFontStack() {
    return (wbIsMap() && WB_MAP_FONTS[wbMapTheme().font]) || null;
  }

  function wbApplyMapFont() {
    const view = document.getElementById("library-view-whiteboard");
    if (!view) return;
    const stack = wbMapFontStack();
    if (stack) view.style.setProperty("--wb-map-font", stack);
    else view.style.removeProperty("--wb-map-font");
  }

  //: What a strip toggle writes when it is pressed: `true`, `false` or `null`.
  //:
  //: `null` is "say nothing and follow the map", which is the right answer only
  //: when the map is not already saying the opposite: on a themed map the
  //: unset state *is* the theme's, so turning a themed-on field off has to be
  //: stored as an explicit `false`. Three values rather than two because a
  //: boolean cannot hold three states, and the third one ("I chose off") is the
  //: only thing that distinguishes a deliberate choice from an untouched topic.
  function wbMapToggleValue(node, field) {
    const want = !wbMapThemedData(node)[field];
    const fallback = Boolean(wbMapThemeDefault(field));
    if (want === fallback) return null;
    return want ? true : false;
  }

  //: Refresh `window.wbMapState` from `GET /boards/{id}/tree`.
  //:
  //: One request, because that endpoint is the only one carrying all three
  //: things this needs: the board's `type`, its `layout`, and the **resolved
  //: label** of every reference node. `GET /whiteboard/` returns objects whose
  //: `data.ref_id` says which note a node points at and nothing about what that
  //: note is called: so without this a map full of notes draws as a column of
  //: identical blank boxes.
  //:
  //: Structure is deliberately *not* taken from here. `parent_id` is already on
  //: every object `GET /whiteboard/` returned, so the tree is rebuilt locally on
  //: every render (`wbMapIndex`) and a Tab keypress redraws immediately instead
  //: of waiting on a round trip to be told what it already knows. This call is
  //: for the two facts only the server has.
  async function wbRefreshMapState() {
    const boardId = window.currentBoardId ?? null;
    if (!boardId) {
      // The default scratch board has no note behind it, so it has nowhere to
      // store settings and is always an ordinary board (`list_boards`' own
      // comment says so). Nothing to ask for.
      window.wbMapState = null;
      return null;
    }
    try {
      const tree = await apiJson(`/whiteboard/boards/${boardId}/tree`, { silent: true });
      const labels = new Map();
      const facets = new Map();
      // Iterative and seen-guarded: `parent_id` has no database constraint
      // behind it (§9.1), so a ring is possible in principle and has to end this
      // walk rather than the tab.
      const frontier = [...(tree.roots || [])];
      const seen = new Set();
      while (frontier.length) {
        const node = frontier.pop();
        if (!node || seen.has(node.id)) continue;
        seen.add(node.id);
        labels.set(node.id, node.text || "");
        //: What the notebook knows about the note behind this node, for the
        //: perspectives (§5 item 19). Only reference nodes have any, and only
        //: the server can resolve it, so it rides along with the labels rather
        //: than being a second request per node.
        if (node.ref_category || node.ref_updated_at) {
          facets.set(node.id, {
            category: node.ref_category || null,
            updated_at: node.ref_updated_at || null,
          });
        }
        frontier.push(...(node.children || []));
      }
      window.wbMapState = {
        type: tree.type,
        layout: tree.layout,
        theme: tree.theme && typeof tree.theme === "object" ? tree.theme : {},
        //: The branch colours, resolved by the server from the theme's palette
        //: (decision 8): the one list the Library thumbnail is drawn from too.
        palette: Array.isArray(tree.palette) ? tree.palette : [],
        //: Whether the map numbers its branches (MINDMAP_PLAN.md decision 17).
        numbered: tree.numbered === true,
        labels,
        facets,
        crossLinks: tree.cross_links || [],
      };
    } catch {
      // A board that 404s here (the default board; a note deleted mid-session)
      // is simply not a map. Failing soft matters because this runs on every
      // board load: an ordinary whiteboard must not break because of it.
      window.wbMapState = null;
    }
    return window.wbMapState;
  }

  // --- Phase 5: perspectives, focus, metrics, templates ------------------------
  //
  //: MINDMAP_PLAN.md §5 items 18 to 21. Four things that make a map worth
  //: keeping rather than worth making, and all four are *views* of the same
  //: tree: none of them changes a node, and nothing here writes to the server
  //: except a template, which creates nodes exactly as the keyboard does.
  //:
  //: They live together because they share one idea. A map's own structure is
  //: all the canvas knew: which node is whose child, and what each is called.
  //: The notebook knows more than that about half the nodes, what they are
  //: filed under and when they were last touched, and item 19's own note says
  //: this is "the thing a general mindmapper cannot do". `wbMapState.facets`
  //: is that knowledge, resolved server-side in `/tree` (a reference node's
  //: category and age) and never guessed here.

  //: What a node's colour means. Branch is Coggle's rule and the default: the
  //: other three answer a question about the notebook instead.
  const WB_MAP_PERSPECTIVES = [
    { key: "branch", label: "Branch", hint: "Coggle's own rule: one colour per first-level branch" },
    { key: "category", label: "Category", hint: "The category each note behind a node is filed under" },
    { key: "age", label: "Age", hint: "When the note behind each node was last edited" },
    { key: "notes", label: "Behind a note", hint: "Which nodes stand for a real note and which are just topics" },
  ];

  //: Kept in the browser, not on the board: a perspective is how *you* are
  //: looking at a map right now, not a property of the map, and two people
  //: opening the same notebook should not change each other's view. Same
  //: reasoning as the Library's Cards/Rows preference, which is stored the same
  //: way.
  function wbMapPerspective() {
    try {
      const stored = prefs.get("wbMapPerspective", null);
      return WB_MAP_PERSPECTIVES.some((p) => p.key === stored) ? stored : "branch";
    } catch {
      return "branch";
    }
  }

  function wbMapSetPerspective(key) {
    try {
      prefs.set("wbMapPerspective", key);
    } catch {
      // A browser with storage switched off still gets the view it asked for
      // for this session; it just will not be remembered.
    }
    wbSyncMapChrome();
    renderWhiteboardNow();
  }

  //: The categories and ages the tree endpoint resolved, by node id. Empty for
  //: every topic (a topic has nothing behind it) and for a private note, whose
  //: facts stay behind the same boundary its text does.
  function wbMapFacets() {
    return window.wbMapState?.facets || new Map();
  }

  //: Age, in the four buckets a person actually thinks in. Not a continuous
  //: ramp: "how old is this" is answered as today / this week / this month /
  //: older, and a gradient over six months makes two notes a fortnight apart
  //: look identical anyway.
  const WB_MAP_AGE_BUCKETS = [
    { key: "today", label: "Today", days: 1 },
    { key: "week", label: "This week", days: 7 },
    { key: "month", label: "This month", days: 31 },
    { key: "older", label: "Older", days: Infinity },
  ];

  function wbMapAgeBucket(iso) {
    if (!iso) return null;
    const then = Date.parse(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
    if (Number.isNaN(then)) return null;
    const days = (Date.now() - then) / 86400000;
    return WB_MAP_AGE_BUCKETS.find((bucket) => days < bucket.days) || WB_MAP_AGE_BUCKETS[3];
  }

  //: The palette every perspective draws from, `d3.schemeTableau10`, which is
  //: what branch colour already uses and what `graph.js` colours clusters with.
  //: One scale for the whole app rather than a second list of hex per view.
  function wbMapPalette() {
    //: The map's own, from `/tree`: the server's `MAP_BRANCH_PALETTES` is the
    //: only copy of every palette (decision 8). d3's Tableau 10, which is that
    //: list's `classic`, only for the moment before the tree has answered.
    const own = window.wbMapState?.palette;
    if (Array.isArray(own) && own.length) return own;
    return (window.d3?.schemeTableau10 || []).slice(0, 10);
  }

  //: A grey for "this node has nothing to say under this perspective": a topic
  //: with no note behind it, or a note whose category is unknown. Read off the
  //: stylesheet rather than written here, so it follows the theme: a hard-coded
  //: grey is invisible in dark mode, which is the failure `--wb-branch` was
  //: introduced to avoid.
  function wbMapQuietColour() {
    const style = getComputedStyle(document.documentElement);
    return (style.getPropertyValue("--muted") || "#8a8f98").trim();
  }

  //: Every node's colour under the current perspective, `Map<id, colour>`, the
  //: same shape `wbMapColors` returns, so the renderer, the edge pass and the
  //: export all keep taking one map and asking it for a colour.
  function wbMapNodeColors(index) {
    const perspective = wbMapPerspective();
    if (perspective === "branch") return wbMapColors(index);
    const facets = wbMapFacets();
    const palette = wbMapPalette();
    const quiet = wbMapQuietColour();
    const colors = new Map();

    if (perspective === "notes") {
      for (const node of index.nodes) {
        colors.set(node.id, WB_MAP_REFERENCE_KINDS.has(node.kind) ? palette[0] : quiet);
      }
      return colors;
    }
    if (perspective === "age") {
      for (const node of index.nodes) {
        const bucket = wbMapAgeBucket(facets.get(node.id)?.updated_at);
        const at = bucket ? WB_MAP_AGE_BUCKETS.indexOf(bucket) : -1;
        // Newest darkest: `schemeBlues[4]` runs light to dark, so the index is
        // read from the end. More ink on the thing you touched today is the
        // reading a ramp is for.
        const blues = window.d3?.schemeBlues?.[4];
        colors.set(node.id, at < 0 || !blues ? quiet : blues[blues.length - 1 - at]);
      }
      return colors;
    }
    // Category. The order is the order they appear walking the tree, so the
    // same map draws the same colours twice running.
    const seen = new Map();
    for (const node of index.nodes) {
      const name = facets.get(node.id)?.category;
      if (!name) {
        colors.set(node.id, quiet);
        continue;
      }
      if (!seen.has(name)) seen.set(name, palette[seen.size % palette.length] || quiet);
      colors.set(node.id, seen.get(name));
    }
    return colors;
  }

  //: What the colours mean, on screen, while they are on screen. A view that
  //: recolours a map and does not say what the colours are is a puzzle: the
  //: legend is the difference between "these are blue" and "these were edited
  //: this week".
  function wbRenderMapLegend(passed = null) {
    const box = document.getElementById("wb-map-legend");
    if (!box) return;
    const perspective = wbMapPerspective();
    const own = perspective === "branch" && wbMapTheme().legend;
    if (!wbIsMap() || (perspective === "branch" && !own)) {
      box.hidden = true;
      box.replaceChildren();
      return;
    }
    const index = passed || wbMapIndex();
    const facets = wbMapFacets();
    const palette = wbMapPalette();
    const quiet = wbMapQuietColour();
    //: **The map's own legend** (MINDMAP_PLAN gap 11): the colour of each main
    //: branch, named by its topic, and each marker the map actually uses (a
    //: priority, a flag, a progress pie, each icon) with the words it carries
    //: elsewhere. Only what is on the map is listed, so a legend never explains a
    //: mark nobody can see. Branch rows are capped at ten.
    const ownRows = () => {
      const colors = wbMapColors(index);
      const out = [];
      const branches = index.nodes.filter((n) => n.parent_id != null && index.byId.get(n.parent_id)?.parent_id == null);
      for (const node of branches.slice(0, 10)) {
        const colour = colors.get(node.id);
        if (colour) out.push({ label: wbMapLabel(node) || "Untitled", colour });
      }
      if (branches.length > 10) out.push({ label: `${branches.length - 10} more branches`, colour: quiet });
      const used = { priority: false, progress: false, flag: false, icons: new Set() };
      for (const node of index.nodes) {
        const parts = wbMapMarkerParts(node.data);
        used.priority ||= parts.priority != null;
        used.progress ||= parts.progress != null;
        used.flag ||= parts.flag;
        parts.icons.forEach((icon) => used.icons.add(icon));
      }
      if (used.priority) out.push({ marker: { priority: 1 }, label: "Priority, 1 is first" });
      if (used.progress) out.push({ marker: { progress: 50 }, label: "How far along" });
      if (used.flag) out.push({ marker: { flag: true }, label: "Flagged" });
      for (const icon of used.icons) out.push({ marker: { markers: [icon] }, label: WB_MAP_MARKER_ICON_NAMES.get(icon) || icon });
      return out;
    };
    const rows = [];
    if (own) {
      rows.push(...ownRows());
    } else if (perspective === "notes") {
      rows.push({ label: "Stands for a note", colour: palette[0] });
      rows.push({ label: "A topic of its own", colour: quiet });
    } else if (perspective === "age") {
      const blues = window.d3?.schemeBlues?.[4] || [];
      WB_MAP_AGE_BUCKETS.forEach((bucket, at) => {
        rows.push({ label: bucket.label, colour: blues[blues.length - 1 - at] || quiet });
      });
      rows.push({ label: "No note behind it", colour: quiet });
    } else {
      const seen = new Map();
      for (const node of index.nodes) {
        const name = facets.get(node.id)?.category;
        if (!name || seen.has(name)) continue;
        seen.set(name, palette[seen.size % palette.length] || quiet);
      }
      for (const [name, colour] of seen) rows.push({ label: name, colour });
      rows.push({ label: "No note behind it", colour: quiet });
    }

    const title = document.createElement("span");
    title.className = "wb-map-legend-title";
    title.textContent = own ? "Legend" : `Colour: ${WB_MAP_PERSPECTIVES.find((p) => p.key === perspective)?.label || perspective}`;
    box.dataset.own = own ? "1" : "";
    const list = document.createElement("div");
    list.className = "wb-map-legend-rows";
    for (const row of rows) {
      const line = document.createElement("span");
      line.className = "wb-map-legend-row";
      const swatch = document.createElement("i");
      swatch.className = "wb-map-legend-swatch";
      swatch.setAttribute("aria-hidden", "true");
      // Through the CSSOM, not an inline `style` attribute in markup: the CSP
      // drops those (CLAUDE.md, "a policy silently refusing the work").
      if (!row.marker) swatch.style.background = row.colour;
      const text = document.createElement("span");
      text.textContent = row.label;
      let lead = swatch;
      if (row.marker) {
        lead = document.createElement("span");
        lead.className = "wb-map-markers wb-map-legend-mark";
        lead.setAttribute("aria-hidden", "true");
        wbMapPaintMarkers(lead, row.marker);
      }
      line.append(lead, text);
      list.appendChild(line);
    }
    box.replaceChildren(title, list);
    box.hidden = false;
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbMapFillOf, WB_MAP_FONTS, WB_MAP_APP_DEFAULT_PINS, wbMapDrawn, wbMapFontStack, wbApplyMapFont, wbMapToggleValue, wbRefreshMapState, wbMapPerspective, wbMapSetPerspective, wbMapFacets, wbMapPalette, wbMapNodeColors, wbRenderMapLegend });
})();
