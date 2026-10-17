// whiteboard-library.js: the board's left sidebar and its object library
// (2026-10-05; WHITEBOARD_PLAN decisions 25 and 26; INBOX 557, 558).
//
// The owner: "an object or elements library would be really good like with
// what draw.io has", "take everything from draw.io", and "the ability to save
// custom elements and stuff as well". One sidebar on the board's left edge,
// collapsible to a rail of tabs:
//
// - **Library**: Favourites, Recent, the built-in sets (General, Flowchart,
//   Arrows, Frames, Icons; static files in `frontend/board-library/`) and the
//   person's own libraries ("Yours", and any made or imported). A search
//   field over names and tags. A tile places by a click (the middle of the
//   view, fanning out on repeats), a drag (under the pointer), Enter (the
//   same as a click, announced) or Shift+Enter (joined to the selected item
//   by a connector, draw.io's clone-and-connect). Its menu (right-click,
//   Shift+F10) has the rest.
// - **Notes**: the note list that used to be its own panel on the right,
//   for dragging a note onto the board as a card.
// - **Layers**: the board as a tree in paint order (`wbRenderLayers`).
//
// Saving goes the other way (`wbSaveToLibrary*`): a selection, one shape, a
// style, a palette, a sticky or text preset, a map branch, or the whole board
// as a template, all into "Yours". Placing is one request
// (`POST /whiteboard/boards/{id}/place`), one event and, through
// `wbRecordGesture`, one undo step.
//
// **Loaded in the Library bundle after whiteboard-commands.js**
// (`LAZY_MODULES`, app.js): its top level declares and wires; everything it
// calls in whiteboard.js is read at call time.

//: The library as the server last listed it (`GET /board-library`).
//: Built-in sets read from their static files, by key; icons apart.
const wbLibSets = new Map();
//: Which sidebar tab is showing, and whether the panel is open, per device.
const WB_SIDE_KEY = "wb-sidebar";
//: How many icons a group draws before "Show more".
const WB_ICON_PAGE = 120;
//: The group folds the person opened or closed, by key.
const wbLibFolds = new Map();
//: The library and sidebar's state, one name in the shared scope.
//: `libDragging` is the entry a tile drag carries, for the canvas's drop, and
//: `libGrab` where in its picture the tile was held (INBOX 664);
//: `libPress` where a tile was pressed, before the drag began;
//: `libLastClick` is where the last click placed, for the next one to step
//: off it.
const wbLibState = { libQuery: "", lib: null, libIcons: null, libIconShown: WB_ICON_PAGE, libLastClick: null, libDragging: null, libGrab: null, libPress: null, layersDrag: null, pagesDrag: null, sideRefreshTimer: 0 };

function wbSideState() {
  const saved = prefs.json(WB_SIDE_KEY, {});
  return { open: saved.open === true, tab: saved.tab || "library" };
}

function wbSaveSideState(state) {
  try {
    prefs.set(WB_SIDE_KEY, JSON.stringify(state));
  } catch {
    // Private mode: the panel opens closed next time.
  }
}

//: Opens the sidebar on `tab`, or closes it when `tab` is already showing
//: and `toggle` is set (a rail tab pressed twice).
function wbOpenSidebar(tab = null, { toggle = false, focus = true } = {}) {
  const side = document.getElementById("wb-sidebar");
  const panel = document.getElementById("wb-sidebar-panel");
  if (!side || !panel) return;
  const state = wbSideState();
  const want = tab || state.tab || "library";
  const isMapTab = want === "outline" || want === "map";
  //: A map has no frames, so no pages, and no paint order or note cards
  //: (INBOX 596): its order is its outline, and a note joins it as a topic.
  if (["pages", "layers", "notes"].includes(want) && wbIsMap()) return wbOpenSidebar("library", { focus });
  const showing = !panel.classList.contains("hidden");
  if (toggle && showing && state.tab === want) {
    wbCloseSidebar();
    return;
  }
  if (isMapTab && !wbIsMap()) return wbOpenSidebar("library", { focus });
  panel.classList.remove("hidden");
  side.classList.add("is-open");
  for (const button of side.querySelectorAll("[data-side-tab]")) {
    const on = button.dataset.sideTab === want;
    button.setAttribute("aria-selected", on ? "true" : "false");
    button.tabIndex = on ? 0 : -1;
  }
  for (const section of panel.querySelectorAll("[data-side-panel]")) {
    section.hidden = section.dataset.sidePanel !== want;
  }
  for (const only of panel.querySelectorAll("[data-side-only]")) only.hidden = only.dataset.sideOnly !== want;
  const title = document.getElementById("wb-sidebar-title");
  if (title) title.textContent = { library: "Library", notes: "Notes", layers: "Layers", pages: "Pages", outline: "Outline", map: "This map" }[want] || "Library";
  document.getElementById("wb-add-note")?.classList.add("is-on");
  wbSaveSideState({ open: true, tab: want });
  if (want === "library") {
    wbLoadLibrary().then(() => {
      if (focus) document.getElementById("wb-lib-search")?.focus({ preventScroll: true });
    });
  } else if (want === "notes") {
    renderWbLibrary();
  } else if (want === "layers") {
    wbRenderLayers();
    if (focus) document.querySelector("#wb-layers-tree [tabindex='0']")?.focus({ preventScroll: true });
  } else if (want === "pages") {
    wbRenderPages();
    if (focus) document.querySelector("#wb-pages-list [tabindex='0']")?.focus({ preventScroll: true });
  } else if (want === "map") {
    wbRenderSideMap();
  } else if (want === "outline") {
    wbOutlineSync(true);
    if (focus) wbOutlineFocusSelected();
  }
  wbOutlineSwitchShows();
}

function wbCloseSidebar() {
  document.getElementById("wb-sidebar-panel")?.classList.add("hidden");
  document.getElementById("wb-sidebar")?.classList.remove("is-open");
  document.getElementById("wb-add-note")?.classList.remove("is-on");
  for (const button of document.querySelectorAll("#wb-sidebar [data-side-tab]")) {
    button.setAttribute("aria-selected", "false");
  }
  const state = wbSideState();
  wbSaveSideState({ ...state, open: false });
  wbOutlineSwitchShows();
}

//: Which tabs a board of this kind shows: a map's library is its branches
//: and templates, and only a map has an outline.
//: **A map's rail is the map's** (INBOX 596, the owner: half of it "is empty
//: when on the mind map as it isnt applicable like with layers"): This map
//: and Outline in place of Notes, Layers and Pages.
const WB_SIDE_TABS_BY_KIND = { map: ["library", "map", "outline"], board: ["library", "notes", "layers", "pages"] };

function wbSyncSidebarKind() {
  const map = wbIsMap();
  const shown = WB_SIDE_TABS_BY_KIND[map ? "map" : "board"];
  for (const tab of document.querySelectorAll("#wb-sidebar [data-side-tab]")) tab.hidden = !shown.includes(tab.dataset.sideTab);
  const state = wbSideState();
  if (!shown.includes(state.tab)) wbSaveSideState({ ...state, tab: "library" });
  if (!document.getElementById("wb-sidebar-panel")?.classList.contains("hidden")) {
    const tab = wbSideState().tab;
    if (tab === "library") wbRenderLibrary();
    else if (tab === "layers") wbRenderLayers();
    else if (tab === "pages") wbRenderPages();
    else if (tab === "outline") wbOutlineSync(true);
    else if (tab === "map") wbRenderSideMap();
  }
}

//: **This map** (INBOX 596): what the map is made of, the stats dialog's own
//: list, kept current while the tab is open (`wbSideRefreshSoon` redraws the
//: open tab after a change), and the three map-wide actions beside it.
function wbRenderSideMap() {
  const host = document.getElementById("wb-side-map-facts");
  if (!host || !wbIsMap()) return;
  host.replaceChildren(wbMapStatsList(wbMapStats(wbMapIndex()), { tiles: true }));
}

// --- loading -------------------------------------------------------------------

async function wbLoadLibrary({ force = false } = {}) {
  //: **A first open waits on skeletons, not on nothing** (INBOX 596, the
  //: owner: "some skeleton loaders are missing like on the dashboard"): the
  //: index and each set are fetched before a tile is drawn, and the list sat
  //: empty the whole while. `showSkeletons` draws only into an empty list, so
  //: a reopen keeps the tiles it has; `wbRenderLibrary` clears them.
  if (!wbLibState.lib || force || (wbLibState.lib.sets || []).some((s) => s.key !== "icons" && !wbLibSets.has(s.key))) {
    showSkeletons(document.getElementById("wb-lib-list"), 6);
  }
  if (!wbLibState.lib || force) {
    try {
      wbLibState.lib = await apiJson("/board-library");
    } catch (err) {
      const list = document.getElementById("wb-lib-list");
      if (list) surfaceFailed(list, "the library", () => wbLoadLibrary({ force: true }));
      return;
    }
  }
  const sets = (wbLibState.lib.sets || []).filter((s) => s.key !== "icons");
  await Promise.all(sets.filter((s) => !wbLibSets.has(s.key)).map(async (s) => {
    try {
      const res = await api(`/board-library/${s.key}.json${lazyAssetStamp()}`, { silent: true });
      wbLibSets.set(s.key, await res.json());
    } catch {
      // A set that does not load is left out; the rest still show.
    }
  }));
  wbRenderLibrary();
}

//: The converted draw.io sets (`shape_sets`, 196 shapes, 0.37 MB) are not
//: fetched with the panel: a set comes when its group is opened, and all of
//: them when a search is typed, so a search finds a router or a gateway
//: without the person knowing which set holds it.
async function wbLoadShapeSets(keys = null) {
  const want = (wbLibState.lib?.shape_sets || []).filter((s) => !wbLibSets.has(s.key) && (!keys || keys.includes(s.key)));
  if (!want.length) return;
  await Promise.all(want.map(async (s) => {
    try {
      const res = await api(`/board-library/${s.path}${lazyAssetStamp()}`, { silent: true });
      wbLibSets.set(s.key, { ...(await res.json()), name: s.name });
    } catch {
      // A set that does not load stays a closed group; the rest still show.
    }
  }));
  wbRenderLibrary();
}

async function wbLoadIcons() {
  if (wbLibState.libIcons) return wbLibState.libIcons;
  try {
    const res = await api(`/board-library/icons.json${lazyAssetStamp()}`, { silent: true });
    wbLibState.libIcons = (await res.json()).icons || {};
  } catch {
    wbLibState.libIcons = {};
  }
  return wbLibState.libIcons;
}

//: Every entry the panel can show, as `{ref, name, tags, kind, set, payload,
//: favourite, item}`. `ref` is `builtin:<set>/<key>` or `item:<id>`.
function wbLibEntries() {
  const out = [];
  const marks = wbLibState.lib?.marks || {};
  for (const [key, set] of wbLibSets) {
    for (const entry of set.items || []) {
      const ref = `builtin:${key}/${entry.key}`;
      out.push({
        ref, name: entry.name, tags: entry.tags || [], kind: entry.kind || "element", set: set.name,
        group: `set:${key}`, payload: entry.payload, favourite: Boolean(marks[`${key}/${entry.key}`]?.favourite),
        template: entry.template || null, shape: entry.shape || null, layout: entry.layout || null,
        hint: entry.hint || null, purpose: entry.purpose || null,
      });
    }
  }
  for (const item of wbLibState.lib?.items || []) {
    out.push({
      ref: `item:${item.id}`, name: item.name, tags: item.tags || [], kind: item.kind,
      set: (wbLibState.lib.libraries || []).find((l) => l.id === item.library_id)?.name || "Yours",
      group: `lib:${item.library_id}`, payload: item.payload, favourite: item.favourite, item,
    });
  }
  return out;
}

function wbLibIconEntry(name) {
  const d = wbLibState.libIcons?.[name];
  if (!d) return null;
  return {
    ref: `builtin:icons/${name}`, name: name.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase()),
    tags: ["icon"], kind: "element", set: "Icons", group: "set:icons",
    favourite: Boolean(wbLibState.lib?.marks?.[`icons/${name}`]?.favourite),
    payload: { box: { w: 96, h: 96 }, items: [{ key: "i", kind: "sketch", data: { d, fill: "ink", noStroke: true, icon: name } }] },
  };
}

//: **A sticker from the icon and emoji picker** (MINDMAP_PLAN.md decision
//: 44), centred on `at`: an emoji is a text object drawn as its glyph alone
//: (`sticker`), an icon the library's own vector icon, so it recolours and
//: exports as a shape. One Undo step either way.
const WB_STICKER_SIZE = 96;

async function wbPlaceSticker(choice, at = null) {
  if (!choice) return null;
  const point = at || wbLibCentre();
  if (choice.kind === "icon") {
    await wbLoadIcons();
    const entry = wbLibIconEntry(choice.value);
    if (!entry) {
      toast("That icon is not in the library's set.", "info");
      return null;
    }
    await wbLibPlace(entry, point);
    return entry;
  }
  const half = WB_STICKER_SIZE / 2;
  const made = await wbCreateObject("text", { content: choice.value, sticker: true },
    point[0] - half, point[1] - half, WB_STICKER_SIZE, WB_STICKER_SIZE, 2);
  if (made) wbAnnounce("Sticker placed.");
  return made;
}

//: The board's Insert, Emoji and icons…: the picker stays open, so several
//: can be placed or dragged; a pick lands in the middle of the view.
function wbOpenStickerPicker(from = null) {
  const anchor = from?.isConnected ? from : document.querySelector('[aria-controls="wb-insert-menu"]');
  pickIconOrEmoji({
    anchor,
    title: "Emoji and icons to place",
    keepOpen: true,
    onPick: (choice) => wbPlaceSticker(choice),
  });
}

//: What a map's library shows: branches and templates; a board's: the rest.
function wbLibFits(entry) {
  const map = wbIsMap();
  if (map) return entry.kind === "branch" || entry.kind === "template";
  return entry.kind !== "branch";
}

// --- drawing the panel ----------------------------------------------------------

//: A thumbnail drawn from the payload itself, with DOM calls: nothing is
//: stored or uploaded for it, so nothing needs sanitising.
function wbLibThumb(entry) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "wb-lib-thumb");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const payload = entry.payload || {};
  if (entry.kind === "palette") {
    svg.setAttribute("viewBox", "0 0 64 40");
    const colours = (payload.colours || []).slice(0, 8);
    colours.forEach((c, i) => {
      const r = document.createElementNS(NS, "rect");
      const w = 64 / Math.max(1, colours.length);
      r.setAttribute("x", String(i * w));
      r.setAttribute("y", "6");
      r.setAttribute("width", String(w));
      r.setAttribute("height", "28");
      r.setAttribute("fill", c);
      svg.appendChild(r);
    });
    return svg;
  }
  if (entry.kind === "style") {
    svg.setAttribute("viewBox", "0 0 64 40");
    const s = payload.style || {};
    const r = document.createElementNS(NS, "rect");
    r.setAttribute("x", "8");
    r.setAttribute("y", "6");
    r.setAttribute("width", "48");
    r.setAttribute("height", "28");
    r.setAttribute("rx", "4");
    r.setAttribute("fill", s.fill || s.bg || "none");
    r.setAttribute("stroke", s.color || s.border_color || "currentColor");
    r.setAttribute("stroke-width", String(Math.min(6, s.width || 2)));
    svg.appendChild(r);
    return svg;
  }
  //: A branch and a drawing are drawn by whiteboard-templates.js, so a tile,
  //: the New board dialog and a new map's offer draw one picture (INBOX 715).
  if (entry.kind === "branch" || payload.branch) return wbThumbSvg(wbMapThumbSpec(entry));
  //: A tile of something that is placed draws it as placed: in the pen's ink
  //: (a template's picture is a whole board at a glance and stays as it was).
  return entry.kind === "template"
    ? wbThumbSvg(wbBoardThumbSpec(payload.element || {}))
    : wbThumbSvg(wbBoardThumbSpec(payload, { placed: true, ink: wbLibInk() }));
}

function wbLibTile(entry) {
  const tile = document.createElement("div");
  tile.className = "wb-lib-tile";
  tile.setAttribute("role", "option");
  tile.setAttribute("aria-selected", "false");
  tile.tabIndex = -1;
  tile.dataset.ref = entry.ref;
  tile.id = `wb-lib-${entry.ref.replace(/[^a-z0-9]+/gi, "-")}`;
  const kindWord = { element: "", shape: "shape", style: "style", palette: "palette", preset: "preset", branch: "branch", template: "template" }[entry.kind] || "";
  const said = [entry.name, kindWord, entry.set, entry.favourite ? "favourite" : ""].filter(Boolean).join(", ");
  tile.setAttribute("aria-label", said);
  tile.title = entry.tags?.length ? `${entry.name} (${entry.tags.join(", ")})` : entry.name;
  tile.append(wbLibThumb(entry));
  const name = document.createElement("span");
  name.className = "wb-lib-name";
  name.textContent = entry.name;
  tile.append(name);
  if (entry.favourite) {
    const star = document.createElement("i");
    star.className = "ph ph-star star-fill wb-lib-star";
    star.setAttribute("aria-hidden", "true");
    tile.append(star);
  }
  tile.draggable = entry.kind !== "style" && entry.kind !== "palette";
  //: A built-in template says which kind of board it starts (INBOX 596).
  if (entry.template) tile.dataset.libTemplate = entry.template;
  tile._entry = entry;
  return tile;
}

function wbLibGroup(host, key, title, entries, { open = true, extra = null, count: shown = null } = {}) {
  if (!entries.length && !extra) return;
  const details = document.createElement("details");
  details.className = "wb-lib-group";
  details.dataset.group = key;
  details.open = wbLibFolds.has(key) ? wbLibFolds.get(key) : open;
  const summary = document.createElement("summary");
  summary.className = "wb-lib-group-head";
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-down wb-lib-caret";
  caret.setAttribute("aria-hidden", "true");
  const words = document.createElement("span");
  words.textContent = title;
  const count = document.createElement("span");
  count.className = "muted wb-lib-count";
  count.textContent = String(entries.length || shown || "");
  summary.append(caret, words, count);
  details.append(summary);
  const grid = document.createElement("div");
  grid.className = "wb-lib-grid";
  grid.setAttribute("role", "group");
  grid.setAttribute("aria-label", title);
  for (const entry of entries) grid.append(wbLibTile(entry));
  details.append(grid);
  if (extra) details.append(extra);
  details.addEventListener("toggle", () => {
    wbLibFolds.set(key, details.open);
    if (key === "set:icons" && details.open && !wbLibState.libIcons) wbLoadIcons().then(() => wbRenderLibrary());
    if (key.startsWith("set:drawio-") && details.open && !wbLibSets.has(key.slice(4))) wbLoadShapeSets([key.slice(4)]);
  });
  host.append(details);
}

function wbRenderLibrary() {
  const list = document.getElementById("wb-lib-list");
  if (!list || !wbLibState.lib) return;
  const query = (document.getElementById("wb-lib-search")?.value || "").trim().toLowerCase();
  const words = query.split(/\s+/).filter(Boolean);
  const all = wbLibEntries().filter(wbLibFits);
  const matches = (e) => {
    const text = `${e.name} ${(e.tags || []).join(" ")} ${e.set}`.toLowerCase();
    return words.every((w) => text.includes(w));
  };
  const active = list.querySelector(".wb-lib-tile.is-active")?.dataset.ref;
  const hadFocus = list.contains(document.activeElement);
  //: Where the list was scrolled to, put back at the end (INBOX 904 B26): the
  //: redraw empties it, and a draw.io group opened low in the list redraws
  //: when its shapes arrive, which sent the list to the top and the opened
  //: group out of sight ("these dropdowns don't show anything"). A new search
  //: starts at the top, as it did.
  const top = query === wbLibState.libQuery ? list.scrollTop : 0;
  wbLibState.libQuery = query;
  clearSkeletons(list);
  list.replaceChildren();
  const map = wbIsMap();
  if (words.length) {
    //: A name that starts with the words first, then a name that holds
    //: them, then a tag: "decision" finds Decision before the diamond whose
    //: tag says decision.
    const rank = (e) => {
      const name = e.name.toLowerCase();
      return name.startsWith(query) ? 0 : words.every((w) => name.includes(w)) ? 1 : 2;
    };
    let found = all.filter(matches).sort((a, b) => rank(a) - rank(b));
    if (!map && wbLibState.libIcons) {
      const icons = Object.keys(wbLibState.libIcons).filter((n) => words.every((w) => n.replace(/-/g, " ").includes(w))).slice(0, 60);
      found = found.concat(icons.map(wbLibIconEntry).filter(Boolean));
    }
    wbLibGroup(list, "search", found.length ? `Results for "${query}"` : "Nothing matches", found);
    if (!map && !wbLibState.libIcons) wbLoadIcons().then(() => wbRenderLibrary());
    if (!map) wbLoadShapeSets();
  } else {
    const byRef = new Map(all.map((e) => [e.ref, e]));
    const favourites = all.filter((e) => e.favourite);
    wbLibGroup(list, "favourites", "Favourites", favourites);
    const recent = (wbLibState.lib.recent || []).map((r) => byRef.get(r.replace(/^builtin:/, "builtin:")) || (r.startsWith("builtin:icons/") ? wbLibIconEntry(r.slice(14)) : null)).filter(Boolean);
    wbLibGroup(list, "recent", "Recent", recent);
    //: In the index's order (Templates first), not the order the files
    //: happened to arrive in. On a map too (INBOX 596): `wbLibFits` leaves a
    //: map the one built-in set that applies there, its templates, which are
    //: branches; an empty set draws nothing.
    const order = (wbLibState.lib.sets || []).map((x) => x.key);
    const shapeSets = wbLibState.lib.shape_sets || [];
    const sets = [...wbLibSets].filter(([key]) => order.includes(key)).sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
    for (const [key, set] of sets) {
      wbLibGroup(list, `set:${key}`, set.name, all.filter((e) => e.group === `set:${key}`), { open: ["templates", "maps", "general", "flowchart"].includes(key) });
    }
    if (!map) {
      const iconsOpen = wbLibFolds.get("set:icons") === true;
      const iconEntries = iconsOpen && wbLibState.libIcons ? Object.keys(wbLibState.libIcons).slice(0, wbLibState.libIconShown).map(wbLibIconEntry).filter(Boolean) : [];
      let more = null;
      if (iconsOpen && wbLibState.libIcons && Object.keys(wbLibState.libIcons).length > wbLibState.libIconShown) {
        more = document.createElement("button");
        more.type = "button";
        more.className = "ghost small wb-lib-more";
        more.textContent = `Show more icons (${Object.keys(wbLibState.libIcons).length - wbLibState.libIconShown} left)`;
        more.addEventListener("click", () => {
          wbLibState.libIconShown += WB_ICON_PAGE * 2;
          wbRenderLibrary();
        });
      } else if (!iconsOpen || !wbLibState.libIcons) {
        more = document.createElement("p");
        more.className = "muted wb-lib-note";
        more.textContent = "1,530 icons, drawn as shapes. Search finds one by name.";
      }
      wbLibGroup(list, "set:icons", "Icons", iconEntries, { open: false, extra: more });
      for (const s of shapeSets) {
        const loaded = wbLibSets.has(s.key);
        let note = null;
        if (!loaded) {
          note = document.createElement("p");
          note.className = "muted wb-lib-note";
          note.textContent = wbLibFolds.get(`set:${s.key}`) ? "Loading…" : `${s.count} shapes from draw.io, each with its own connection points.`;
        }
        wbLibGroup(list, `set:${s.key}`, s.name, all.filter((e) => e.group === `set:${s.key}`), { open: false, extra: note, count: s.count });
      }
    }
    for (const lib of wbLibState.lib.libraries || []) {
      const mine = all.filter((e) => e.group === `lib:${lib.id}`);
      if (!mine.length && lib.kind !== "yours") continue;
      const empty = mine.length ? null : wbLibEmptyYours(map);
      wbLibGroup(list, `lib:${lib.id}`, lib.name, mine, { extra: empty });
    }
  }
  const tiles = [...list.querySelectorAll(".wb-lib-tile")];
  const keep = tiles.find((t) => t.dataset.ref === active) || tiles[0];
  //: A redraw under the keyboard (a star, a rename) keeps the reader's place.
  if (keep) wbLibSetActive(keep, { focus: hadFocus });
  list.scrollTop = top;
  wbLibAnnounceCount(tiles.length, words.length > 0);
}

function wbLibEmptyYours(map) {
  const p = document.createElement("p");
  p.className = "muted wb-lib-note";
  p.textContent = map
    ? "Save a branch here from a topic's menu, or the whole map from Board, Save as a template."
    : "Select something and press Ctrl+Shift+S, or right-click it, Save to the library.";
  return p;
}

function wbLibAnnounceCount(n, searching) {
  const status = document.getElementById("wb-lib-status");
  if (status) status.textContent = searching ? `${n} ${n === 1 ? "match" : "matches"}` : "";
}

//: The roving focus: one tile is the list's tab stop.
function wbLibSetActive(tile, { focus = true } = {}) {
  const list = document.getElementById("wb-lib-list");
  for (const t of list.querySelectorAll(".wb-lib-tile.is-active")) {
    t.classList.remove("is-active");
    t.tabIndex = -1;
    t.setAttribute("aria-selected", "false");
  }
  tile.classList.add("is-active");
  tile.tabIndex = 0;
  tile.setAttribute("aria-selected", "true");
  list.setAttribute("aria-activedescendant", tile.id);
  if (focus) tile.focus({ preventScroll: false });
}

function wbLibVisibleTiles() {
  return [...document.querySelectorAll("#wb-lib-list .wb-lib-tile")].filter((t) => t.offsetParent !== null);
}

// --- placing ---------------------------------------------------------------------

function wbLibInk() {
  const value = document.getElementById("wb-rail-ink")?.value || window.currentStrokeColor || "#3355ff";
  return /^#[0-9a-f]{6}$/i.test(value) ? value : "#3355ff";
}

//: Where a click places: the middle of the canvas you can see
//: (`wbViewCentre`). A click with the view where it was for the last one
//: would land exactly on top of it, so each such repeat steps 24px on screen
//: further down and right, ten steps and round again; the run starts over
//: once the view moves. It was a four-second timer, so a fifth click a
//: moment later stacked on the first.
function wbLibCentre() {
  const [x, y] = wbViewCentre();
  const k = d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1;
  const board = window.currentBoardId ?? 0;
  const last = wbLibState.libLastClick;
  const same = last && last.board === board && Math.abs(last.x - x) < 0.5 && Math.abs(last.y - y) < 0.5;
  const n = same ? (last.n + 1) % 10 : 0;
  wbLibState.libLastClick = { board, x, y, n };
  return [x + (n * 24) / k, y + (n * 24) / k];
}

//: The box an element's drawing fills, in its own units: its thumbnail's
//: paths and boxes measured by the browser (the thumbnail draws the payload
//: in the payload's own coordinates), so a curve or an arc is bounded where
//: it is drawn, not by its control points. Its words are left out. Cached by
//: the entry's ref and version; null for a branch, which has no drawing.
const wbLibDrawnBoxes = new Map();

function wbLibContentBox(entry) {
  if (!entry || entry.kind === "branch") return null;
  const key = `${entry.ref}:${entry.item?.version || 0}`;
  if (wbLibDrawnBoxes.has(key)) return wbLibDrawnBoxes.get(key);
  const svg = wbLibThumb(entry);
  //: Measured in the page (an element outside it has no box), out of sight;
  //: `getBBox` is in the drawing's own units whatever size it is shown at.
  svg.classList.add("visually-hidden");
  document.body.append(svg);
  let box = null;
  try {
    for (const el of svg.querySelectorAll("path, rect")) {
      const b = el.getBBox();
      if (!b.width && !b.height) continue;
      box = box
        ? { minX: Math.min(box.minX, b.x), minY: Math.min(box.minY, b.y), maxX: Math.max(box.maxX, b.x + b.width), maxY: Math.max(box.maxY, b.y + b.height) }
        : { minX: b.x, minY: b.y, maxX: b.x + b.width, maxY: b.y + b.height };
    }
  } catch {
    box = null;
  }
  svg.remove();
  wbLibDrawnBoxes.set(key, box);
  return box;
}

//: Where in a tile's picture the pointer is, as a fraction of the drawing
//: (0 to 1 each way, held inside it), and the same point in the picture's own
//: pixels, for the drag image. The middle for a branch, whose picture is a
//: sign rather than a drawing of what it places.
function wbLibGrabPoint(tile, clientX, clientY) {
  const svg = tile.querySelector("svg.wb-lib-thumb");
  if (!svg) return null;
  const r = svg.getBoundingClientRect();
  if (!r.width || !r.height) return null;
  let l = Infinity, t = Infinity, rt = -Infinity, b = -Infinity;
  if (tile._entry?.kind !== "branch") {
    for (const el of svg.querySelectorAll("path, rect")) {
      const q = el.getBoundingClientRect();
      if (!q.width && !q.height) continue;
      l = Math.min(l, q.left); t = Math.min(t, q.top); rt = Math.max(rt, q.right); b = Math.max(b, q.bottom);
    }
  }
  if (!Number.isFinite(l)) {
    return { frac: [0.5, 0.5], offset: [r.width / 2, r.height / 2] };
  }
  const clamp = (v) => Math.max(0, Math.min(1, v));
  const fx = rt > l ? clamp((clientX - l) / (rt - l)) : 0.5;
  const fy = b > t ? clamp((clientY - t) / (b - t)) : 0.5;
  return { frac: [fx, fy], offset: [l + (rt - l) * fx - r.left, t + (b - t) * fy - r.top] };
}

function wbLibRefBody(ref) {
  return ref.startsWith("item:") ? { item_id: Number(ref.slice(5)) } : { builtin: ref.slice(8) };
}

//: Places an entry at `at` (board units), selects what it made, announces it
//: and records it as one undo step. `connect`: join the item that was
//: selected before to what was placed, on its right (Shift+Enter). `grab`:
//: which point of the drawing goes at `at`, as a fraction of its box (where
//: its tile was held for a drag; the middle otherwise). See "Where a placed
//: thing lands" in whiteboard.js.
async function wbLibPlace(entry, at = null, { connect = false, onto = null, grab = null } = {}) {
  if (!entry) return;
  if (entry.kind === "style") return wbLibApplyStyle(entry);
  if (entry.kind === "palette") return wbLibApplyPalette(entry, entry.payload?.colours?.[0]);
  if (entry.kind === "template") return wbLibNewBoardFrom(entry);
  const map = wbIsMap();
  const was = wbSelectedItem ? { ...wbSelectedItem } : null;
  const wasItem = was ? wbFindItem(was.kind, was.id) : null;
  let point = at;
  if (!point && connect && wasItem) {
    const box = wbItemBBox(was.kind, wasItem);
    const w = entry.payload?.box?.w || 160;
    if (box) point = [box.maxX + 120 + w / 2, (box.minY + box.maxY) / 2];
  }
  point = point || wbLibCentre();
  const frac = grab || [0.5, 0.5];
  const body = { ...wbLibRefBody(entry.ref), x: point[0], y: point[1], ink: wbLibInk() };
  //: The server centres the payload's declared box on x, y, and a drawing
  //: need not fill its box (a star sat 6px high, a cloud 7px off), so the box
  //: is asked for where it puts the drawing by the rule: exact before it is
  //: drawn, and so no second save after it.
  if (entry.kind !== "branch") {
    const box = entry.payload?.box || { w: 100, h: 100 };
    const drawn = wbLibContentBox(entry) || { minX: 0, minY: 0, maxX: box.w, maxY: box.h };
    const [left, top] = wbAnchorDelta(drawn, point, frac, wbSnapOn() ? WB_GRID_SPACING : 0);
    body.x = left + box.w / 2;
    body.y = top + box.h / 2;
  }
  //: A branch goes under the topic it was dropped on, else the selected
  //: one; a map template with neither goes under the root, since a
  //: template is the map's first branches rather than a second trunk. With
  //: no root to go under, the server makes the central topic (INBOX 670): the
  //: template's one top-level topic, or a new one named after the template.
  if (map && entry.kind === "branch") {
    const dropped = onto != null ? wbFindItem("object", onto) : null;
    const topic = (dropped && WB_MAP_KINDS.has(dropped.kind) ? dropped : null) || wbSelectedMapNode()
      || (entry.template === "map" ? wbMapIndex().roots[0] : null);
    if (topic) body.parent_id = topic.id;
  }
  const boardId = window.currentBoardId ?? 0;
  let made = null;
  await wbRecordGesture(async () => {
    try {
      made = await apiJson(`/whiteboard/boards/${boardId}/place`, { method: "POST", body: JSON.stringify(body) });
    } catch (err) {
      toast(err.message || "Couldn't place that.", true);
      return;
    }
    wbState.sketches = [...(wbState.sketches || []), ...made.sketches];
    wbState.objects = [...(wbState.objects || []), ...made.objects];
    if (connect && wasItem && !map) {
      const first = made.objects.find((o) => o.kind !== "frame") || made.sketches.find((s) => !/"type"\s*:\s*"link-/.test(s.data));
      if (first) {
        const targetKind = made.objects.includes(first) ? "object" : "sketch";
        try {
          const link = await apiJson("/whiteboard/sketches", {
            method: "POST",
            body: JSON.stringify({
              data: JSON.stringify({ type: "link-straight", sourceId: was.id, sourceKind: was.kind, targetId: first.id, targetKind, color: wbLibInk(), endCap: "arrow" }),
              x: 0, y: 0, z: 1, board_id: window.currentBoardId ?? null,
            }),
          });
          wbState.sketches.push(link);
        } catch {
          // The shape is placed either way; the join is a convenience.
        }
      }
    }
    if (map) await wbRefreshMapState();
    renderWhiteboardNow();
    //: Then put what was drawn where the rule says, inside this gesture so
    //: it is the same undo step. A branch is laid out by the server from
    //: its first topic's corner, so on a map it is always measured and
    //: moved; on a map with a layout the tidy below places it instead.
    if (!map || wbMapLayout() === "free") {
      const rows = [
        ...made.sketches.filter((s) => !/"type"\s*:\s*"link-/.test(s.data)).map((item) => ({ kind: "sketch", item })),
        ...made.objects.map((item) => ({ kind: "object", item })),
      ];
      await wbAnchorPlaced(rows, point, frac);
    }
  });
  if (!made) return;
  if (map) await wbMapTidy({ quiet: true });
  clearWbSelection();
  const keys = [
    ...made.sketches.filter((s) => !/"type"\s*:\s*"link-/.test(s.data)).map((s) => wbMultiKey("sketch", s.id)),
    ...made.objects.map((o) => wbMultiKey("object", o.id)),
  ];
  if (keys.length === 1) {
    const [kind, id] = keys[0].split(":");
    wbSelectedItem = { kind, id: Number(id) };
  } else {
    for (const key of keys) wbMultiSelection.add(key);
  }
  wbApplySelectionHighlight();
  wbUpdateSelectionBar();
  wbAnnounce(`Placed ${entry.name}${connect && wasItem ? ", joined to the selected item" : ""}.`);
  wbLibState.lib = null; // Recent moved.
}

//: A whole library made, imported or deleted, as one step (INBOX 898): the
//: server keeps what a delete took (core/undo_bin.py) and answers with a token.
//: `created` is the direction of the act; `withItems` takes an import's items
//: with it, which a plain delete would have moved to Yours.
function wbLibPairStep(label, libraryId, token, { created = false, withItems = false } = {}) {
  let held = token;
  const del = async () => {
    held = (await apiJson(`/board-library/libraries/${libraryId}${withItems ? "?with_items=true" : ""}`, { method: "DELETE" })).undo_token;
    await wbLoadLibrary({ force: true });
  };
  const restore = async () => {
    libraryId = (await apiJson("/board-library/libraries/restore", { method: "POST", body: JSON.stringify({ token: held }) })).id;
    await wbLoadLibrary({ force: true });
  };
  return created ? wbPushCall(label, del, restore) : wbPushCall(label, restore, del);
}

async function wbLibNewBoardFrom(entry) {
  const name = await promptDialog("Name the new board", entry.name, { confirmLabel: "Create" });
  if (!name || !name.trim()) return;
  try {
    const board = await apiJson("/board-library/new-board", {
      method: "POST",
      body: JSON.stringify({ ...wbLibRefBody(entry.ref), name: name.trim(), ink: wbLibInk() }),
    });
    await openWhiteboardBoard(board.id);
    wbBoardMadeStep(board);
    toast(`Started "${board.title}" from ${entry.name}.`);
  } catch (err) {
    toast(err.message || "Couldn't start a board from that.", true);
  }
}

//: A saved style onto the selection, through the board's own Paste style.
async function wbLibApplyStyle(entry) {
  const { target, style } = entry.payload || {};
  if (!style) return;
  if (!wbSelectedItem && !wbMultiSelection.size) {
    toast("Select something to give it this style.");
    return;
  }
  const keep = typeof wbCopiedStyle !== "undefined" ? wbCopiedStyle : null;
  wbCopiedStyle = { kind: target === "text" ? "object" : "sketch", style };
  await wbRecordGesture(() => wbPasteCopiedStyle());
  wbCopiedStyle = keep;
}

//: One colour of a palette: onto the selection (a shape's fill, a line's
//: colour, a box's ground), or into the pen when nothing is selected.
async function wbLibApplyPalette(entry, colour) {
  if (!colour) return;
  if (!wbSelectedItem && !wbMultiSelection.size) {
    const ink = document.getElementById("wb-rail-ink");
    if (ink) {
      ink.value = colour;
      ink.dispatchEvent(new Event("input", { bubbles: true }));
      ink.dispatchEvent(new Event("change", { bubbles: true }));
    }
    wbAnnounce(`Pen colour ${colour}.`);
    return;
  }
  const entries = wbMultiSelection.size ? wbSelectionEntries() : [{ ...wbSelectedItem, item: wbFindItem(wbSelectedItem.kind, wbSelectedItem.id) }];
  await wbRecordGesture(async () => {
    for (const e of entries) {
      const item = e.item;
      if (!item) continue;
      if (e.kind === "sketch") {
        const parsed = wbSketchParsedData(item);
        const shape = parsed && WB_FILLABLE_SHAPES.has(parsed.shape);
        await wbSaveSketchProps(item, shape ? { fill: colour, fillOpacity: parsed.fillOpacity ?? 1 } : { color: colour });
      } else if (e.kind === "object" && item.kind === "text") {
        item.data = { ...item.data, [item.data?.bg ? "bg" : "color"]: colour };
        await wbSaveObject(item);
      }
    }
  });
  wbScheduleRender();
  wbAnnounce(`Coloured ${colour}.`);
}

// --- the tile's menu --------------------------------------------------------------

function wbLibMenuItems(entry) {
  const items = [];
  const own = entry.ref.startsWith("item:");
  if (entry.kind === "palette") {
    for (const colour of entry.payload?.colours || []) {
      items.push({ label: `ph:circle ${colour}`, title: "Use this colour", run: () => wbLibApplyPalette(entry, colour), group: "colours" });
    }
  } else if (entry.kind === "style") {
    items.push({ label: "ph:paint-brush Apply to the selection", title: "Enter", run: () => wbLibApplyStyle(entry), group: "use" });
  } else if (entry.kind === "template") {
    items.push({ label: "ph:plus New board from this", title: "Enter", run: () => wbLibNewBoardFrom(entry), group: "use" });
  } else {
    items.push({ label: "ph:plus Place in the middle", title: "Enter", run: () => wbLibPlace(entry), group: "use" });
    if (entry.kind !== "branch") {
      items.push({ label: "ph:flow-arrow Place joined to the selection", title: "Shift+Enter", run: () => wbLibPlace(entry, null, { connect: true }), group: "use" });
    }
    if (entry.kind === "element" && /^builtin:(frames)\//.test(entry.ref)) {
      items.push({ label: "ph:squares-four New board from this", title: "A board that starts with it", run: () => wbLibNewBoardFrom(entry), group: "use" });
    }
  }
  items.push({
    label: entry.favourite ? "ph:star Remove from favourites" : "ph:star Add to favourites",
    title: "F", run: () => wbLibToggleFavourite(entry), group: "mark",
  });
  if (own) {
    items.push({ label: "ph:pencil-simple Rename…", title: "F2", run: () => wbLibRename(entry), group: "edit" });
    items.push({ label: "ph:tag Tags…", title: "Words search finds it by", run: () => wbLibTags(entry), group: "edit" });
    if (["element", "shape", "preset"].includes(entry.kind)) {
      items.push({ label: "ph:arrows-clockwise Replace with the selection", title: "Saves what is selected now in its place; copies already placed keep their look", run: () => wbLibReplace(entry), group: "edit" });
    }
    items.push({ label: "ph:copy Duplicate", title: "A second copy to change", run: () => wbLibDuplicate(entry), group: "edit" });
    const others = (wbLibState.lib?.libraries || []).filter((l) => l.id !== entry.item.library_id);
    for (const lib of others) {
      items.push({ label: `ph:folder-simple Move to ${lib.name}`, title: "Move it to another library", run: () => wbLibMove(entry, lib.id), group: "move" });
    }
    items.push({ label: "ph:trash Delete", title: "Delete (Ctrl+Z or the toast's Undo brings it back)", run: () => wbLibDelete(entry), group: "delete" });
  }
  return items;
}

function wbLibOpenMenu(tile, x = null, y = null) {
  const entry = tile?._entry;
  if (!entry) return;
  const r = tile.getBoundingClientRect();
  openMenuAtPoint(wbLibMenuItems(entry), `${entry.name}: actions`, x ?? r.right - 8, y ?? r.bottom - 8);
}

async function wbLibToggleFavourite(entry) {
  try {
    //: Item or built-in mark: the same request with the flag as it was.
    const send = (favourite) => async () => {
      if (entry.ref.startsWith("item:")) {
        await apiJson(`/board-library/${entry.ref.slice(5)}`, { method: "PUT", body: JSON.stringify({ favourite }) });
      } else {
        await apiJson("/board-library/marks", { method: "POST", body: JSON.stringify({ key: entry.ref.slice(8), favourite }) });
      }
      await wbLoadLibrary({ force: true });
    };
    await send(!entry.favourite)();
    wbPushCall(entry.favourite ? "Removed a library item from favourites" : "Made a library item a favourite", send(Boolean(entry.favourite)), send(!entry.favourite));
    wbAnnounce(entry.favourite ? `${entry.name} removed from favourites.` : `${entry.name} added to favourites.`);
    await wbLoadLibrary({ force: true });
  } catch (err) {
    toast(err.message || "Couldn't change that.", true);
  }
}

async function wbLibRename(entry) {
  const name = await promptDialog("Rename this library item", entry.name, { confirmLabel: "Rename" });
  if (!name || !name.trim() || name.trim() === entry.name) return;
  const put = (body) => async () => {
    await apiJson(`/board-library/${entry.ref.slice(5)}`, { method: "PUT", body: JSON.stringify(body) });
    await wbLoadLibrary({ force: true });
  };
  await put({ name: name.trim() })();
  wbPushCall("Renamed a library item", put({ name: entry.name }), put({ name: name.trim() }));
}

async function wbLibTags(entry) {
  const tags = await promptDialog("Tags, separated by commas", (entry.tags || []).join(", "), { confirmLabel: "Save" });
  if (tags === null || tags === undefined) return;
  const nextTags = String(tags).split(",").map((t) => t.trim()).filter(Boolean);
  const put = (list) => async () => {
    await apiJson(`/board-library/${entry.ref.slice(5)}`, { method: "PUT", body: JSON.stringify({ tags: list }) });
    await wbLoadLibrary({ force: true });
  };
  await put(nextTags)();
  wbPushCall("Changed a library item's tags", put(entry.tags || []), put(nextTags));
}

async function wbLibDuplicate(entry) {
  const copy = await apiJson(`/board-library/${entry.ref.slice(5)}/duplicate`, { method: "POST" });
  if (copy?.id != null) {
    const bin = (verb) => async () => {
      if (verb === "bin") await apiJson(`/board-library/${copy.id}`, { method: "DELETE" });
      else await apiJson(`/board-library/${copy.id}/restore`, { method: "POST" });
      await wbLoadLibrary({ force: true });
    };
    wbPushCall("Duplicated a library item", bin("bin"), bin("restore"));
  }
  await wbLoadLibrary({ force: true });
  wbAnnounce(`${entry.name} duplicated.`);
}

async function wbLibMove(entry, libraryId) {
  const put = (id) => async () => {
    await apiJson(`/board-library/${entry.ref.slice(5)}`, { method: "PUT", body: JSON.stringify({ library_id: id }) });
    await wbLoadLibrary({ force: true });
  };
  await put(libraryId)();
  wbPushCall("Moved a library item", put(entry.item?.library_id ?? null), put(libraryId));
}

async function wbLibDelete(entry) {
  const id = entry.ref.slice(5);
  await apiJson(`/board-library/${id}`, { method: "DELETE" });
  await wbLoadLibrary({ force: true });
  const bring = (verb) => async () => {
    if (verb === "restore") await apiJson(`/board-library/${id}/restore`, { method: "POST" });
    else await apiJson(`/board-library/${id}`, { method: "DELETE" });
    await wbLoadLibrary({ force: true });
  };
  const step = wbPushCall(`Deleted “${entry.name}” from the library`, bring("restore"), bring("bin"));
  toastAction(`Deleted ${entry.name} from the library.`, "Undo", async () => {
    wbDropUndoEntry(step);
    await bring("restore")();
  });
}

async function wbLibReplace(entry) {
  const payload = wbLibSelectionPayload();
  if (!payload) return;
  const was = entry.payload || entry.item?.payload || null;
  const put = (body) => async () => {
    await apiJson(`/board-library/${entry.ref.slice(5)}`, { method: "PUT", body: JSON.stringify({ payload: body }) });
    await wbLoadLibrary({ force: true });
  };
  await put(payload)();
  if (was) wbPushCall(`Replaced “${entry.name}” in the library`, put(was), put(payload));
  toast(`${entry.name} now holds the selection. Copies already on boards keep their look.`);
}

// --- saving ------------------------------------------------------------------------

//: The selection as an element payload: positions from its box's top left,
//: the links whose two ends are both in it, group ids kept (the server makes
//: them new on every placement), comments left behind.
function wbLibSelectionPayload({ quiet = false } = {}) {
  const copied = wbCopyableSelection({ quiet });
  if (!copied) {
    if (!quiet) toast("Select the things to save first. A note card stays a card: drop the note again instead.");
    return null;
  }
  const { box } = copied;
  const keyOf = new Map();
  const items = [];
  const entries = wbMultiSelection.size ? wbSelectionEntries() : [{ ...wbSelectedItem, item: wbFindItem(wbSelectedItem.kind, wbSelectedItem.id) }];
  for (const e of entries) {
    const item = e.item;
    if (!item || e.kind === "node") continue;
    if (e.kind === "sketch") {
      const parsed = wbSketchParsedData(item);
      if (!parsed) continue;
      const key = `s${item.id}`;
      keyOf.set(`sketch:${item.id}`, key);
      const data = { ...parsed, d: wbTransformPathD(parsed.d, { dx: -box.minX, dy: -box.minY }) };
      delete data.comments;
      delete data.library_ref;
      delete data.locked;
      items.push({ key, kind: "sketch", data, z: item.z || 0, group: item.group_id || undefined });
    } else if (e.kind === "object") {
      if (WB_MAP_KINDS?.has?.(item.kind)) continue;
      const key = `o${item.id}`;
      keyOf.set(`object:${item.id}`, key);
      const data = { ...(item.data || {}) };
      delete data.comments;
      delete data.library_ref;
      delete data.locked;
      items.push({
        key, kind: "object", type: item.kind, data,
        x: item.x - box.minX, y: item.y - box.minY, w: item.width, h: item.height,
        rotation: item.rotation ?? undefined, z: item.z || 0, group: item.group_id || undefined,
      });
    }
  }
  const links = [];
  for (const s of wbState.sketches || []) {
    let data = null;
    try {
      data = JSON.parse(s.data);
    } catch {
      continue;
    }
    if (!String(data?.type || "").startsWith("link-")) continue;
    const from = keyOf.get(`${data.sourceKind || "node"}:${data.sourceId}`);
    const to = keyOf.get(`${data.targetKind || "node"}:${data.targetId}`);
    if (!from || !to) continue;
    const linkData = { ...data };
    for (const k of ["sourceId", "targetId", "sourceKind", "targetKind", "library_ref"]) delete linkData[k];
    //: An elbow's bends are board points: kept from the saved box's corner,
    //: as the items are, so a placed copy bends where the original did.
    if (Array.isArray(linkData.points)) linkData.points = linkData.points.map((p) => ({ x: p.x - box.minX, y: p.y - box.minY }));
    links.push({ from, to, data: linkData });
  }
  if (!items.length) {
    if (!quiet) toast("Nothing in this selection can be saved: a note card stays a card.");
    return null;
  }
  return { box: { w: Math.max(1, box.maxX - box.minX), h: Math.max(1, box.maxY - box.minY) }, items, links };
}

async function wbLibCreate(kind, name, payload, tags = []) {
  try {
    const made = await apiJson("/board-library", { method: "POST", body: JSON.stringify({ kind, name, payload, tags }) });
    if (made?.id != null) {
      const bin = (verb) => async () => {
        if (verb === "bin") await apiJson(`/board-library/${made.id}`, { method: "DELETE" });
        else await apiJson(`/board-library/${made.id}/restore`, { method: "POST" });
        await wbLoadLibrary({ force: true });
      };
      wbPushCall(`Saved “${made.name}” to the library`, bin("bin"), bin("restore"));
    }
    wbLibState.lib = null;
    toastAction(`Saved "${made.name}" to your library.`, "Show", () => wbOpenSidebar("library"));
    if (!document.getElementById("wb-sidebar-panel")?.classList.contains("hidden")) await wbLoadLibrary({ force: true });
    wbAnnounce(`Saved ${made.name} to the library.`);
    return made;
  } catch (err) {
    toast(err.message || "Couldn't save that to the library.", true);
    return null;
  }
}

//: Kind 1: the selection.
async function wbSaveSelectionToLibrary() {
  const map = wbIsMap();
  if (map) return wbSaveBranchToLibrary();
  const payload = wbLibSelectionPayload();
  if (!payload) return;
  const one = payload.items.length === 1 ? payload.items[0] : null;
  const guess = one?.data?.label || noteNamePlain(one?.data?.content, 40) || `${payload.items.length} items`;
  const name = await promptDialog("Save to the library as", guess, { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("element", name.trim(), payload);
}

//: Kind 2: one drawn path kept as a shape, which then fills, takes text and
//: scales like the built-in shapes.
async function wbSaveShapeToLibrary() {
  const sketch = wbSelectedItem?.kind === "sketch" && wbMultiSelection.size <= 1 ? wbFindItem("sketch", wbSelectedItem.id) : null;
  const parsed = sketch && wbSketchParsedData(sketch);
  if (!parsed?.d) {
    toast("Select one drawn shape or pen stroke first.");
    return;
  }
  const box = wbPathBBox(parsed.d);
  const closed = /[Zz]\s*$/.test(parsed.d.trim());
  const data = {
    d: wbTransformPathD(parsed.d, { dx: -box.minX, dy: -box.minY }),
    shape: closed ? "custom" : parsed.shape || "draw",
    color: parsed.color || "ink",
    width: parsed.width || 2,
  };
  if (parsed.fill) {
    data.fill = parsed.fill;
    data.fillOpacity = parsed.fillOpacity ?? 1;
  }
  if (parsed.dash) data.dash = parsed.dash;
  const name = await promptDialog("Save as a shape named", parsed.label || "My shape", { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("shape", name.trim(), { box: { w: Math.max(1, box.width), h: Math.max(1, box.height) }, items: [{ key: "s", kind: "sketch", data, z: 5 }], links: [] }, ["shape"]);
}

//: Kind 3: one item's look.
async function wbSaveStyleToLibrary() {
  const sel = wbMultiSelection.size <= 1 ? wbSelectedItem : null;
  const item = sel && wbFindItem(sel.kind, sel.id);
  if (!item || sel.kind === "node") {
    toast("Select one shape, line or text box first.");
    return;
  }
  let target, style;
  if (sel.kind === "sketch") {
    const parsed = wbSketchParsedData(item) || {};
    style = wbPickStyle(parsed, WB_SKETCH_STYLE_KEYS);
    target = WB_FILLABLE_SHAPES.has(parsed.shape) ? "shape" : "line";
  } else {
    style = wbPickStyle(item.data, [...WB_OBJECT_STYLE_KEYS, "bold", "italic", "align"]);
    target = "text";
  }
  const name = await promptDialog("Save this style as", `${target[0].toUpperCase()}${target.slice(1)} style`, { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("style", name.trim(), { target, style }, ["style", target]);
}

//: Kind 3b: the colours of the selection (up to sixteen).
async function wbSavePaletteToLibrary() {
  const entries = wbMultiSelection.size ? wbSelectionEntries() : wbSelectedItem ? [{ ...wbSelectedItem, item: wbFindItem(wbSelectedItem.kind, wbSelectedItem.id) }] : [];
  const colours = [];
  for (const e of entries) {
    const src = e.kind === "sketch" ? wbSketchParsedData(e.item) || {} : e.item?.data || {};
    for (const key of ["color", "fill", "bg", "border_color"]) {
      const c = src[key];
      if (typeof c === "string" && /^#[0-9a-f]{6}$/i.test(c) && !colours.includes(c.toLowerCase())) colours.push(c.toLowerCase());
    }
  }
  if (!colours.length) {
    toast("Select a few coloured things first: their colours become the palette.");
    return;
  }
  const name = await promptDialog("Save these colours as a palette named", "My palette", { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("palette", name.trim(), { colours: colours.slice(0, 16) }, ["palette", "colours"]);
}

//: Kind 4: a sticky or a text box, its look and its words.
async function wbSavePresetToLibrary() {
  const sel = wbMultiSelection.size <= 1 ? wbSelectedItem : null;
  const item = sel?.kind === "object" ? wbFindItem("object", sel.id) : null;
  if (!item || item.kind !== "text") {
    toast("Select one sticky or text box first.");
    return;
  }
  const sticky = Boolean(item.data?.bg);
  const name = await promptDialog(`Save as a ${sticky ? "sticky" : "text"} preset named`, sticky ? "My sticky" : "My text box", { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  const data = { ...item.data };
  delete data.comments;
  delete data.library_ref;
  delete data.locked;
  return wbLibCreate("preset", name.trim(), {
    box: { w: item.width, h: item.height },
    items: [{ key: "t", kind: "object", type: "text", data, x: 0, y: 0, w: item.width, h: item.height, z: 1 }],
    links: [],
  }, ["preset", sticky ? "sticky" : "text"]);
}

//: Kind 5: a map topic and everything under it.
function wbLibBranchOf(rootId) {
  const index = wbMapIndex();
  const walk = (id, depth) => {
    const node = index.byId.get(id);
    if (!node || depth > 30) return null;
    const data = { ...(node.data || {}) };
    for (const k of ["content", "comments", "library_ref", "order", "pinned", "collapsed", "ref_id"]) delete data[k];
    //: Already in sibling order (`wbMapIndex` sorts every child list).
    const kids = index.childrenOf.get(id) || [];
    return { text: String(wbMapLabel(node) || ""), data, children: kids.map((k) => walk(k.id, depth + 1)).filter(Boolean) };
  };
  return walk(rootId, 0);
}

async function wbSaveBranchToLibrary(topic = null) {
  const node = topic || wbSelectedMapNode();
  if (!node) {
    toast("Select a topic first: it and everything under it is saved.");
    return;
  }
  const branch = wbLibBranchOf(node.id);
  if (!branch) return;
  const name = await promptDialog("Save this branch as", branch.text.slice(0, 60) || "My branch", { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("branch", name.trim(), { nodes: [branch] }, ["branch"]);
}

//: Kind 6: the whole board or map, its settings and what is on it.
async function wbSaveBoardAsTemplate() {
  const map = wbIsMap();
  const settings = { type: map ? "map" : "board" };
  if (map && window.wbMapState) {
    settings.layout = window.wbMapState.layout || null;
    if (window.wbMapState.theme && Object.keys(window.wbMapState.theme).length) settings.theme = window.wbMapState.theme;
  }
  const bg = wbBoardBackground();
  if (bg && (bg.color || bg.image)) settings.background = bg;
  const payload = { board: settings };
  if (map) {
    const index = wbMapIndex();
    const roots = index.nodes.filter((n) => n.parent_id == null || !index.byId.has(n.parent_id));
    const nodes = roots.map((r) => wbLibBranchOf(r.id)).filter(Boolean);
    if (!nodes.length) return toast("This map is empty: add a topic first.");
    payload.branch = { nodes };
  } else {
    const keep = { multi: new Set(wbMultiSelection), one: wbSelectedItem };
    wbMultiSelection.clear();
    for (const s of wbState.sketches || []) wbMultiSelection.add(wbMultiKey("sketch", s.id));
    for (const o of wbState.objects || []) wbMultiSelection.add(wbMultiKey("object", o.id));
    wbSelectedItem = null;
    payload.element = wbLibSelectionPayload({ quiet: true });
    wbMultiSelection.clear();
    for (const k of keep.multi) wbMultiSelection.add(k);
    wbSelectedItem = keep.one;
    if (!payload.element) return toast("This board has nothing a template can hold yet: shapes, text, stickies and frames.");
  }
  const title = wbBoardTitleForExport();
  const name = await promptDialog("Save this board as a template named", title || "My template", { confirmLabel: "Save" });
  if (!name || !name.trim()) return;
  return wbLibCreate("template", name.trim(), payload, ["template", map ? "map" : "board"]);
}

// --- import and export --------------------------------------------------------------

async function wbLibExport(libraryId) {
  try {
    const res = await api(`/board-library/export?library_id=${libraryId}`);
    const blob = await res.blob();
    const named = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "library.memorymap-library.json";
    await saveFile(named, blob);
  } catch (err) {
    toast(err.message || "Couldn't export that library.", true);
  }
}

async function wbLibImportFile(file) {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) return toast("That file is too large to be a library (8 MB at most).", "info");
  let body;
  try {
    body = JSON.parse(await file.text());
  } catch {
    return toast("That file is not a Tessellate library.", "info");
  }
  try {
    const out = await apiJson("/board-library/import", { method: "POST", body: JSON.stringify(body) });
    wbLibPairStep(`Imported the library “${out.library.name}”`, out.library.id, null, { created: true, withItems: true });
    await wbLoadLibrary({ force: true });
    const extra = [out.skipped ? `${out.skipped} skipped` : "", out.dropped_media ? `${out.dropped_media} picture${out.dropped_media === 1 ? "" : "s"} not in this notebook left out` : ""].filter(Boolean).join(", ");
    toast(`Imported ${out.items} into "${out.library.name}"${extra ? ` (${extra})` : ""}.`);
  } catch (err) {
    toast(err.message || "Couldn't import that library.", true);
  }
}

async function wbLibNewLibrary() {
  const name = await promptDialog("Name the new library", "My library", { confirmLabel: "Create" });
  if (!name || !name.trim()) return;
  const made = await apiJson("/board-library/libraries", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
  wbLibPairStep(`Made the library “${made.name}”`, made.id, null, { created: true });
  await wbLoadLibrary({ force: true });
}

function wbLibPanelMenu() {
  const libs = wbLibState.lib?.libraries || [];
  const items = [
    { label: "ph:folder-plus New library…", title: "A library of your own to save into", run: () => wbLibNewLibrary(), group: "lib" },
    { label: "ph:upload-simple Import a library file…", title: "A .memorymap-library.json file", run: () => document.getElementById("wb-lib-import")?.click(), group: "file" },
  ];
  for (const lib of libs) {
    items.push({ label: `ph:download-simple Export ${lib.name}`, title: "Save it as a file to share or keep", run: () => wbLibExport(lib.id), group: "file" });
  }
  for (const lib of libs.filter((l) => l.kind !== "yours")) {
    items.push({
      label: `ph:trash Delete the ${lib.name} library`, title: "What it holds moves to Yours", group: "delete",
      run: async () => {
        const gone = await apiJson(`/board-library/libraries/${lib.id}`, { method: "DELETE" });
        wbLibPairStep(`Deleted the library “${lib.name}”`, lib.id, gone.undo_token);
        await wbLoadLibrary({ force: true });
      },
    });
  }
  return items;
}

// --- wiring --------------------------------------------------------------------------

onDomReady(() => {
  const side = document.getElementById("wb-sidebar");
  if (!side) return;
  for (const button of side.querySelectorAll("[data-side-tab]")) {
    button.addEventListener("click", () => wbOpenSidebar(button.dataset.sideTab, { toggle: true }));
  }
  //: The rail is one tab stop; Up and Down walk it (a vertical tablist).
  side.querySelector(".wb-sidebar-rail")?.addEventListener("keydown", (e) => {
    if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) return;
    const tabs = [...side.querySelectorAll("[data-side-tab]")].filter((t) => !t.hidden);
    const at = tabs.indexOf(document.activeElement);
    const next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (at + (e.key === "ArrowDown" ? 1 : -1) + tabs.length) % tabs.length;
    e.preventDefault();
    for (const t of tabs) t.tabIndex = -1;
    tabs[next].tabIndex = 0;
    tabs[next].focus();
  });
  document.getElementById("wb-sidebar-close")?.addEventListener("click", () => wbCloseSidebar());
  const search = document.getElementById("wb-lib-search");
  search?.addEventListener("input", () => wbRenderLibrary());
  search?.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "Enter") {
      const first = wbLibVisibleTiles()[0];
      if (first) {
        e.preventDefault();
        wbLibSetActive(first);
        if (e.key === "Enter") wbLibPlace(first._entry, null, { connect: e.shiftKey });
      }
    } else if (e.key === "Escape" && search.value) {
      e.preventDefault();
      e.stopPropagation();
      search.value = "";
      wbRenderLibrary();
    }
  });
  const list = document.getElementById("wb-lib-list");
  //: Every key in the panel is the panel's: the board's single-letter tools
  //: stay out of a search and a list.
  document.getElementById("wb-sidebar-panel")?.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") e.stopPropagation();
  });
  list?.addEventListener("click", (e) => {
    const tile = e.target.closest(".wb-lib-tile");
    if (!tile) return;
    wbLibSetActive(tile, { focus: false });
    wbLibPlace(tile._entry, null, { connect: e.shiftKey });
  });
  list?.addEventListener("contextmenu", (e) => {
    const tile = e.target.closest(".wb-lib-tile");
    if (!tile) return;
    e.preventDefault();
    wbLibSetActive(tile, { focus: false });
    wbLibOpenMenu(tile, e.clientX, e.clientY);
  });
  //: The list's keys: arrows walk the grid (left and right one, up and down
  //: a row), Enter places, Shift+Enter places joined, F stars, Shift+F10 or
  //: the menu key opens the tile's menu, letters search.
  list?.addEventListener("keydown", (e) => {
    const tile = e.target.closest(".wb-lib-tile");
    if (!tile) return;
    const tiles = wbLibVisibleTiles();
    const at = tiles.indexOf(tile);
    const perRow = Math.max(1, Math.round((tile.parentElement.clientWidth || 1) / (tile.offsetWidth || 1)));
    const go = (i) => {
      const t = tiles[Math.max(0, Math.min(tiles.length - 1, i))];
      if (t) wbLibSetActive(t);
    };
    if (e.key === "ArrowRight") go(at + 1);
    else if (e.key === "ArrowLeft") go(at - 1);
    else if (e.key === "ArrowDown") go(at + perRow);
    else if (e.key === "ArrowUp") {
      if (at - perRow < 0) document.getElementById("wb-lib-search")?.focus();
      else go(at - perRow);
    } else if (e.key === "Home") go(0);
    else if (e.key === "End") go(tiles.length - 1);
    else if (e.key === "Enter") wbLibPlace(tile._entry, null, { connect: e.shiftKey });
    else if ((e.key === "F10" && e.shiftKey) || e.key === "ContextMenu") wbLibOpenMenu(tile);
    else if (e.key.toLowerCase() === "f" && !e.ctrlKey && !e.metaKey && !e.altKey) wbLibToggleFavourite(tile._entry);
    else if (e.key === "F2" && tile._entry.ref.startsWith("item:")) wbLibRename(tile._entry);
    else if (e.key === "Delete" && tile._entry.ref.startsWith("item:")) wbLibDelete(tile._entry);
    else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && search) {
      search.focus();
      return;
    } else return;
    e.preventDefault();
  });
  list?.addEventListener("pointerdown", (e) => {
    const tile = e.target.closest(".wb-lib-tile");
    wbLibState.libPress = tile ? { tile, x: e.clientX, y: e.clientY } : null;
  });
  list?.addEventListener("dragstart", (e) => {
    const tile = e.target.closest(".wb-lib-tile");
    if (!tile?._entry) return;
    e.dataTransfer.setData("application/x-memorymap-library", tile._entry.ref);
    e.dataTransfer.effectAllowed = "copy";
    wbLibState.libDragging = tile._entry;
    //: **The tile's picture is what is carried, held where it was grabbed**
    //: (INBOX 664). The browser's own drag image was the whole tile, name
    //: and padding included, and where it was held meant nothing: the drop
    //: put the item's middle under the pointer whatever part of the picture
    //: was there (48px off for a rectangle held by its corner, 291px for the
    //: Kanban template). Now the drag image is the drawing, the pointer holds
    //: it at the point it was grabbed (kept inside the drawing), and the drop
    //: puts that same point of the placed item under the pointer.
    //: Held where it was pressed: the browser starts a drag only once the
    //: pointer has travelled a few pixels, and on a 60px picture of a
    //: 1040px template those few pixels were 10 to 15px of board.
    const press = wbLibState.libPress?.tile === tile ? wbLibState.libPress : { x: e.clientX, y: e.clientY };
    const grab = wbLibGrabPoint(tile, press.x, press.y);
    wbLibState.libGrab = grab?.frac || null;
    const svg = tile.querySelector("svg.wb-lib-thumb");
    if (grab && svg && e.dataTransfer.setDragImage) e.dataTransfer.setDragImage(svg, grab.offset[0], grab.offset[1]);
  });
  list?.addEventListener("dragend", () => {
    wbLibState.libDragging = null;
    wbLibState.libGrab = null;
    wbLibState.libPress = null;
    wbMapClearDropTarget();
  });
  const canvas = document.getElementById("whiteboard-container");
  //: **On a map, the topic a branch or an icon will join is lit while it is
  //: over it**, the same cue a dragged topic gives (`wbMapShowDropTarget`):
  //: the drop goes under that topic rather than where the pointer is, and
  //: nothing said so until it had happened.
  const showJoin = (e, carries) => {
    if (typeof wbMapShowDropTarget !== "function" || !wbIsMap()) return;
    const joins = carries === "icon" || wbLibState.libDragging?.kind === "branch";
    const id = joins ? Number(e.target.closest?.(".wb-object[data-id]")?.dataset.id) || null : null;
    const topic = id != null ? wbFindItem("object", id) : null;
    wbMapShowDropTarget(topic && WB_MAP_KINDS.has(topic.kind) ? id : null);
  };
  canvas?.addEventListener("dragover", (e) => {
    if (e.dataTransfer?.types?.includes("application/x-memorymap-library")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      showJoin(e, "library");
    }
  });
  canvas?.addEventListener("dragleave", (e) => {
    if (!canvas.contains(e.relatedTarget)) wbMapClearDropTarget();
  });
  canvas?.addEventListener("drop", (e) => {
    if (!e.dataTransfer?.types?.includes("application/x-memorymap-library") || !wbLibState.libDragging) return;
    e.preventDefault();
    e.stopPropagation();
    wbMapClearDropTarget();
    const onto = Number(e.target.closest?.(".wb-object[data-id]")?.dataset.id) || null;
    wbLibPlace(wbLibState.libDragging, wbClientToBoard(e.clientX, e.clientY), { onto, grab: wbLibState.libGrab });
    wbLibState.libDragging = null;
    wbLibState.libGrab = null;
  }, true);
  //: **An icon or an emoji dragged from the picker** (MINDMAP_PLAN.md
  //: decision 44): onto a map topic it is that topic's icon, anywhere else a
  //: sticker under the pointer. Capture, as the library's own drop above is,
  //: so the note drop's handler never sees it.
  canvas?.addEventListener("dragover", (e) => {
    if (e.dataTransfer?.types?.includes("application/x-memorymap-icon")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      showJoin(e, "icon");
    }
  }, true);
  canvas?.addEventListener("drop", (e) => {
    if (!e.dataTransfer?.types?.includes("application/x-memorymap-icon")) return;
    e.preventDefault();
    e.stopPropagation();
    let choice = null;
    try {
      choice = JSON.parse(e.dataTransfer.getData("application/x-memorymap-icon"));
    } catch {
      choice = window.iconPickerDragging;
    }
    window.iconPickerDragging = null;
    wbMapClearDropTarget();
    if (!choice || (choice.kind !== "emoji" && choice.kind !== "icon") || typeof choice.value !== "string") return;
    const onto = Number(e.target.closest?.(".wb-object[data-id]")?.dataset.id) || null;
    const topic = onto != null ? wbFindItem("object", onto) : null;
    if (topic && WB_MAP_KINDS.has(topic.kind)) {
      wbMapSetTopicIcon(topic, choice.value);
      return;
    }
    wbPlaceSticker(choice, wbClientToBoard(e.clientX, e.clientY));
  }, true);
  document.getElementById("wb-lib-more")?.addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    //: **Hung from the button's right edge, 4px under it**, as every ⋯
    //: menu opens (INBOX 596: from its left edge it sat 20px left of the
    //: button and 15px low). The pointer recipe parks its host at a point and
    //: hangs the menu from a 1px anchor there, which lands a few pixels off
    //: a button's corner; so set, measured and corrected by the difference
    //: (DESIGN.md, a popup in the window's own coordinates).
    //: It escapes to <body> on the next frame (the sidebar clips), so it is
    //: the menu that is moved then, by its own `left` and `top`.
    openMenuAtPoint(wbLibPanelMenu(), "Library actions", r.right, r.bottom);
    requestAnimationFrame(() => {
      const menu = document.querySelector("body > .action-menu-escaped:not(.hidden)");
      if (!menu) return;
      const got = menu.getBoundingClientRect();
      menu.style.left = `${parseFloat(menu.style.left) + r.right - got.right}px`;
      menu.style.top = `${parseFloat(menu.style.top) + r.bottom + 4 - got.top}px`;
    });
  });
  document.getElementById("wb-side-map-look")?.addEventListener("click", () => wbMapThemeDialog());
  document.getElementById("wb-side-map-expand")?.addEventListener("click", () => wbMapExpandAll());
  document.getElementById("wb-side-map-tidy")?.addEventListener("click", async () => {
    const moved = await wbMapTidy({ quiet: true });
    toast(moved ? `Tidied ${moved} node${moved === 1 ? "" : "s"}.` : "Everything is already where this layout puts it.");
  });
  //: The tiles are drawn in the pen's ink (`wbLibThumb`), so a new ink draws
  //: them again, once the picker has settled, where the list was scrolled to.
  let inkTimer = 0;
  for (const type of ["input", "change"]) {
    document.getElementById("wb-rail-ink")?.addEventListener(type, () => {
      clearTimeout(inkTimer);
      inkTimer = setTimeout(() => {
        const panel = document.getElementById("wb-sidebar-panel");
        if (!wbLibState.lib || !panel || panel.classList.contains("hidden") || wbSideState().tab !== "library") return;
        const list = document.getElementById("wb-lib-list");
        const was = list?.scrollTop || 0;
        wbRenderLibrary();
        if (list) list.scrollTop = was;
      }, 150);
    });
  }
  const importInput = document.getElementById("wb-lib-import");
  importInput?.addEventListener("change", () => {
    const file = importInput.files?.[0];
    importInput.value = "";
    wbLibImportFile(file);
  });
  //: The top bar's Library button opens the sidebar where it was left.
  const state = wbSideState();
  if (state.open && !window.matchMedia("(max-width: 600px)").matches) wbOpenSidebar(state.tab, { focus: false });
});

// --- Layers (WHITEBOARD_PLAN decision 27; INBOX 557b) ------------------------
//
// The board as a tree in paint order, front first: what is drawn in the card
// layer (cards, text, stickies, pictures), the frames under them, then the
// drawing layer (shapes, lines, ink, connectors), which this app always
// paints under the cards. A group is a row with its members under it. Each
// row: the eye (hide, show), the lock (decision 15's flag) and its name; a
// press selects the item and brings it on screen; a drag, or Alt+Up and
// Alt+Down, restacks it within its layer; F2 renames; Delete deletes.
// `role="tree"` with `aria-level`, so every item on the board is reachable
// and named without a pointer.


function wbLayerName(kind, item) {
  const own = kind === "sketch" ? wbSketchData(item)?.name : kind === "object" ? item.data?.name : null;
  return own || wbItemSpokenName(kind, item);
}

//: The frames whose rows are folded shut in the Layers tab (kept for the
//: session, not saved: it is a view of the list, not of the board).
const wbLayerFoldedFrames = new Set();

function wbLayerEntryByKey(key) {
  const [kind, id] = String(key).split(":");
  const item = wbFindItem(kind, Number(id));
  return item ? { kind, item } : null;
}

function wbLayerRows() {
  const rows = [];
  const layer = (title, entries, held = null) => {
    entries.sort((a, b) => (b.item.z || 0) - (a.item.z || 0) || b.item.id - a.item.id);
    const groups = new Map();
    const top = [];
    for (const e of entries) {
      const g = e.item.group_id;
      if (g) {
        if (!groups.has(g)) {
          const head = { group: g, members: [] };
          groups.set(g, head);
          top.push(head);
        }
        groups.get(g).members.push(e);
      } else {
        top.push(e);
      }
    }
    rows.push({ head: title, count: entries.length });
    for (const t of top) {
      if (t.group && t.members.length > 1) {
        rows.push({ group: t.group, level: 2, name: `Group of ${t.members.length}` });
        for (const m of t.members) rows.push({ ...m, level: 3, name: wbLayerName(m.kind, m.item) });
      } else {
        const m = t.group ? t.members[0] : t;
        const inside = held?.get(m.item.id) || [];
        rows.push({ ...m, level: 2, name: wbLayerName(m.kind, m.item), holds: inside.length });
        if (inside.length && !wbLayerFoldedFrames.has(m.item.id)) {
          const members = inside.map((key) => wbLayerEntryByKey(key)).filter(Boolean)
            .sort((a, b) => (b.item.z || 0) - (a.item.z || 0) || b.item.id - a.item.id);
          for (const h of members) rows.push({ ...h, level: 3, name: wbLayerName(h.kind, h.item), held: true });
        }
      }
    }
  };
  const cards = [
    ...(wbState.nodes || []).map((item) => ({ kind: "node", item })),
    ...(wbState.objects || []).filter((o) => o.kind !== "frame").map((item) => ({ kind: "object", item })),
  ];
  const frames = (wbState.objects || []).filter((o) => o.kind === "frame").map((item) => ({ kind: "object", item }));
  const drawings = (wbState.sketches || []).filter((s) => wbSketchIsDrawable(s)).map((item) => ({ kind: "sketch", item }));
  //: **What a frame holds is nested under it** (INBOX 824, the owner asking
  //: whether the tint on a row meant "in the frame"): an item lying wholly
  //: inside a frame (`wbFrameContents`, the same rule a drag of the frame
  //: uses) is listed once, under the first frame that holds it, indented and
  //: collapsible, and not again in its kind's own list.
  const held = new Map();
  const claimed = new Set();
  for (const frame of frames) {
    const keys = wbFrameContents(frame.item, { withLocked: true }).filter((k) => !claimed.has(k));
    for (const k of keys) claimed.add(k);
    held.set(frame.item.id, keys);
  }
  const unclaimed = (list) => list.filter((e) => !claimed.has(wbMultiKey(e.kind, e.item.id)));
  layer("Cards, text and pictures", unclaimed(cards));
  if (frames.length) layer("Frames", frames, held);
  layer("Drawings, shapes and lines", unclaimed(drawings));
  return rows;
}

function wbLayerButton(className, icon, title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `ghost small icon-only ${className}`;
  button.tabIndex = -1;
  button.setAttribute("aria-hidden", "true");
  button.title = title;
  const glyph = document.createElement("i");
  glyph.className = `ph ${icon}`;
  button.append(glyph);
  return button;
}

// --- Named layers (canvasdepth, INBOX 797; WHITEBOARD_PLAN section 6) ------
//
// draw.io's layers: a named set of items that hides, shows and locks
// together. The board keeps the list (`layers` in its settings), an item
// names its layer in `data.layer`, and `wbItemHidden` and `wbIsLocked` read
// the layer's flags, so every place that skips a hidden or locked item
// skips these too. Above the paint-order tree, one row per layer: the eye,
// the lock, the name with its count, and a menu.

function wbNamedLayerOf(kind, item) {
  if (kind === "sketch") return wbSketchData(item)?.layer || null;
  return kind === "object" ? item.data?.layer || null : null;
}

//: **The layer wins** over an item's own eye or lock. An item on a hidden or
//: locked named layer is hidden or locked whatever its own flag says
//: (`wbItemHidden`, `wbIsLocked`), so its eye changed nothing visible. Rather
//: than a second per-item override to explain, the row says whose state it is
//: and the toggle points at the layer. Returns that layer or null.
function wbLayerOwning(kind, item, flag) {
  const id = wbNamedLayerOf(kind, item);
  return (id && (wbState.layers || []).find((l) => l.id === id && l[flag])) || null;
}

function wbLayerSaysOwner(text) {
  toast(text);
  wbAnnounce(text);
}

async function wbSaveNamedLayers(layers, { undo = true, said = "" } = {}) {
  const id = window.currentBoardId;
  if (!id) {
    toast("The default board has no layers. Make a board of your own to use them.", "info");
    return false;
  }
  const before = (wbState.layers || []).map((x) => ({ ...x }));
  try {
    const out = await apiJson(`/whiteboard/boards/${id}`, { method: "PUT", body: JSON.stringify({ layers }) });
    if (String(window.currentBoardId ?? "") !== String(id)) return false;
    wbState.layers = out.layers || [];
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "change the layers" }), true);
    return false;
  }
  if (undo) wbPushUndo({ action: "layers", before });
  wbScheduleRender();
  wbRenderLayers();
  if (said) wbAnnounce(said);
  return true;
}

//: Puts the selection on a layer (null: off every layer), one undo step.
async function wbMoveSelectionToLayer(layerId) {
  const entries = wbSelectionEntries().map((e) => [e.kind, e.item]);
  if (wbSelectedItem) {
    const item = wbFindItem(wbSelectedItem.kind, wbSelectedItem.id);
    if (item && !entries.some(([k, i]) => k === wbSelectedItem.kind && i === item)) entries.push([wbSelectedItem.kind, item]);
  }
  const movable = entries.filter(([kind]) => kind !== "node");
  if (!movable.length) {
    toast(entries.length ? "Cards stay off layers; select shapes, text or drawings." : "Select something to put on the layer first.", "info");
    return 0;
  }
  const undo = [];
  for (const [kind, item] of movable) {
    if (wbNamedLayerOf(kind, item) === layerId) continue;
    undo.push({ action: "move", kind, id: item.id, before: WB_KIND_INFO[kind].payload(item) });
    if (kind === "object") {
      const data = { ...item.data };
      if (layerId) data.layer = layerId;
      else delete data.layer;
      item.data = data;
      await wbSaveObject(item);
    } else {
      await wbSaveSketchProps(item, { layer: layerId || undefined });
    }
  }
  wbPushMoveBatch(undo);
  wbScheduleRender();
  wbRenderLayers();
  const name = (wbState.layers || []).find((x) => x.id === layerId)?.name;
  wbAnnounce(`${undo.length} item${undo.length === 1 ? "" : "s"} ${name ? `moved to ${name}` : "taken off their layer"}.`);
  return undo.length;
}

async function wbNewNamedLayer() {
  const layers = wbState.layers || [];
  const name = await promptDialog("Name the new layer", `Layer ${layers.length + 1}`, { confirmLabel: "Add layer" });
  if (!name || !name.trim()) return;
  const layer = { id: `l${Date.now().toString(36)}`, name: name.trim().slice(0, 60), hidden: false, locked: false };
  if (await wbSaveNamedLayers([...layers, layer], { said: `Layer ${layer.name} added.` }) && (wbMultiSelection.size || wbSelectedItem)) {
    await wbMoveSelectionToLayer(layer.id);
  }
}

//: **The current layer** (draw.io's; canvasdepth2): new things land on it,
//: set by the server on every create (`_on_current_layer`). An item brought
//: back by Undo says `layer: ""` when it had none, so it comes back where it
//: was rather than onto whichever layer is current now.
function wbKeepOwnLayer(kind, payload) {
  if (kind === "object" && payload?.data && !payload.data.layer) return { ...payload, data: { ...payload.data, layer: "" } };
  if (kind === "sketch" && typeof payload?.data === "string") {
    try {
      const data = JSON.parse(payload.data);
      if (data && typeof data === "object" && !data.layer) return { ...payload, data: JSON.stringify({ ...data, layer: "" }) };
    } catch {
      return payload;
    }
  }
  return payload;
}

//: Make a layer the current one, or none (`null`), one Undo step.
function wbSetCurrentLayer(id) {
  const name = (wbState.layers || []).find((x) => x.id === id)?.name;
  return wbSaveNamedLayers((wbState.layers || []).map((x) => ({ ...x, current: x.id === id })),
    { said: name ? `New things go on ${name}.` : "New things go on no layer." });
}

function wbNamedLayerSet(id, patch, said) {
  return wbSaveNamedLayers((wbState.layers || []).map((x) => (x.id === id ? { ...x, ...patch } : x)), { said });
}

function wbNamedLayerItems(id) {
  const out = [];
  for (const kind of ["object", "sketch"]) {
    for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) if (wbNamedLayerOf(kind, item) === id) out.push([kind, item]);
  }
  return out;
}

function wbNamedLayerMenu(layer) {
  return kebabMenu([
    { label: "ph:arrow-square-in Move the selection here", run: () => wbMoveSelectionToLayer(layer.id) },
    layer.current
      ? { label: "ph:pencil-slash Stop drawing on it", title: "New things go on no layer", run: () => wbSetCurrentLayer(null) }
      : { label: "ph:pencil-simple-line Draw on this layer", title: "New things go on it: its name is pressed", run: () => wbSetCurrentLayer(layer.id) },
    { label: "ph:selection-all Select what is on it", run: () => {
      clearWbSelection();
      for (const [kind, item] of wbNamedLayerItems(layer.id)) wbMultiSelection.add(wbMultiKey(kind, item.id));
      wbApplySelectionHighlight();
      wbUpdateSelectionBar();
    } },
    { label: "ph:pencil-simple Rename", run: async () => {
      const name = await promptDialog("Rename the layer", layer.name, { confirmLabel: "Rename" });
      if (name && name.trim()) wbNamedLayerSet(layer.id, { name: name.trim().slice(0, 60) }, "Layer renamed.");
    } },
    { label: "ph:trash Delete the layer", title: "Its items stay on the board, on no layer", group: "delete", run: async () => {
      const items = wbNamedLayerItems(layer.id);
      if (items.length) {
        clearWbSelection();
        for (const [kind, item] of items) wbMultiSelection.add(wbMultiKey(kind, item.id));
        await wbMoveSelectionToLayer(null);
        clearWbSelection();
      }
      wbSaveNamedLayers((wbState.layers || []).filter((x) => x.id !== layer.id), { said: `Layer ${layer.name} deleted; its items stay.` });
    } },
  ], `More for the layer ${layer.name}`);
}

function wbRenderNamedLayers(tree) {
  let box = document.getElementById("wb-named-layers");
  if (!box) {
    box = document.createElement("div");
    box.id = "wb-named-layers";
    box.className = "wb-named-layers";
    tree.before(box);
  }
  box.replaceChildren();
  box.hidden = wbIsMap();
  if (box.hidden) return;
  const head = document.createElement("div");
  head.className = "wb-named-layers-head";
  const title = document.createElement("span");
  title.className = "wb-layer-head";
  title.textContent = "Layers";
  const add = smallButton("ph:plus", "New layer, with the selection on it", () => wbNewNamedLayer());
  add.classList.add("wb-named-layer-add");
  head.append(title, add);
  box.append(head);
  const list = document.createElement("ul");
  list.className = "wb-named-layer-list";
  list.setAttribute("aria-label", "Named layers");
  for (const layer of wbState.layers || []) {
    const li = document.createElement("li");
    li.className = "wb-named-layer";
    li.dataset.layer = layer.id;
    li.classList.toggle("is-hidden", layer.hidden);
    li.classList.toggle("is-locked", layer.locked);
    const eye = smallButton(layer.hidden ? "ph:eye-slash" : "ph:eye", `${layer.hidden ? "Show" : "Hide"} the layer ${layer.name}`,
      () => wbNamedLayerSet(layer.id, { hidden: !layer.hidden }, `${layer.name} ${layer.hidden ? "shown" : "hidden"}.`));
    eye.setAttribute("aria-pressed", String(layer.hidden));
    const lock = smallButton(layer.locked ? "ph:lock-simple" : "ph:lock-simple-open", `${layer.locked ? "Unlock" : "Lock"} the layer ${layer.name}`,
      () => wbNamedLayerSet(layer.id, { locked: !layer.locked }, `${layer.name} ${layer.locked ? "unlocked" : "locked"}.`));
    lock.setAttribute("aria-pressed", String(layer.locked));
    //: The name is the layer's "draw here" switch, draw.io's current layer.
    const name = document.createElement("button");
    name.type = "button";
    name.className = "wb-layer-name wb-named-layer-current";
    name.textContent = layer.name;
    name.setAttribute("aria-pressed", String(Boolean(layer.current)));
    name.title = layer.current ? `New things go on ${layer.name}; press to draw on no layer` : `Draw on ${layer.name}: new things go on it`;
    name.addEventListener("click", () => wbSetCurrentLayer(layer.current ? null : layer.id));
    if (layer.current) li.setAttribute("aria-current", "true");
    const count = document.createElement("span");
    count.className = "muted wb-lib-count";
    count.textContent = String(wbNamedLayerItems(layer.id).length);
    li.append(eye, lock, name, count, wbNamedLayerMenu(layer));
    list.append(li);
  }
  if (!(wbState.layers || []).length) {
    const none = document.createElement("li");
    none.className = "muted wb-lib-note";
    none.textContent = "None yet. Select things and press + to put them on a layer you can hide or lock; press a layer's name to draw on it.";
    list.append(none);
  }
  box.append(list);
}

function wbRenderLayers() {
  const tree = document.getElementById("wb-layers-tree");
  if (!tree || tree.closest("[hidden]")) return;
  wbRenderNamedLayers(tree);
  const map = wbIsMap();
  const activeKey = tree.querySelector("[tabindex='0']")?.dataset.key;
  tree.replaceChildren();
  if (map) {
    const p = document.createElement("li");
    p.className = "muted wb-lib-note";
    p.setAttribute("role", "none");
    p.textContent = "A mind map's order is its outline.";
    tree.append(p);
    return;
  }
  const selected = new Set(wbMultiSelection);
  if (wbSelectedItem) selected.add(wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id));
  wbLayersSelectedHead(selected.size);
  for (const row of wbLayerRows()) {
    const li = document.createElement("li");
    if (row.head) {
      li.className = "wb-layer-head";
      li.setAttribute("role", "none");
      li.textContent = row.count ? row.head : `${row.head}: none`;
      tree.append(li);
      continue;
    }
    li.setAttribute("role", "treeitem");
    li.setAttribute("aria-level", String(row.level));
    li.className = `wb-layer-row wb-layer-depth-${row.level - 2}`;
    li.tabIndex = -1;
    const icon = document.createElement("i");
    icon.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "wb-layer-name";
    name.textContent = row.name;
    if (row.group) {
      li.dataset.group = row.group;
      li.dataset.key = `group:${row.group}`;
      li.setAttribute("aria-expanded", "true");
      li.classList.add("is-group");
      icon.className = "ph ph-link wb-layer-icon";
      li.append(icon, name);
      li.setAttribute("aria-label", row.name);
      tree.append(li);
      continue;
    }
    const key = wbMultiKey(row.kind, row.item.id);
    li.dataset.key = key;
    li.dataset.kind = row.kind;
    li.dataset.id = String(row.item.id);
    const hidden = wbItemHidden(row.kind, row.item);
    const locked = wbIsLocked(row.kind, row.item);
    li.draggable = true;
    li.setAttribute("aria-selected", selected.has(key) ? "true" : "false");
    icon.className = `ph ${wbLayerIcon(row.kind, row.item)} wb-layer-icon`;
    const hideLayer = wbLayerOwning(row.kind, row.item, "hidden");
    const lockLayer = wbLayerOwning(row.kind, row.item, "locked");
    const eye = wbLayerButton("wb-layer-eye", hidden ? "ph-eye-slash" : "ph-eye",
      hideLayer ? `Hidden by its layer, ${hideLayer.name}. Show the layer to see it.` : hidden ? "Show it (H)" : "Hide it (H)");
    const lock = wbLayerButton("wb-layer-lock", locked ? "ph-lock-simple" : "ph-lock-simple-open",
      lockLayer ? `Locked by its layer, ${lockLayer.name}. Unlock the layer to edit it.` : locked ? "Unlock it (L)" : "Lock it (L)");
    eye.classList.toggle("is-by-layer", Boolean(hideLayer));
    lock.classList.toggle("is-by-layer", Boolean(lockLayer));
    li.classList.toggle("is-hidden", hidden);
    li.classList.toggle("is-locked", locked);
    if (row.holds) {
      //: A frame that holds items folds them (INBOX 824).
      const folded = wbLayerFoldedFrames.has(row.item.id);
      li.setAttribute("aria-expanded", folded ? "false" : "true");
      li.classList.add("has-held");
      const fold = wbLayerButton("wb-layer-fold", folded ? "ph-caret-right" : "ph-caret-down",
        `${folded ? "Show" : "Hide"} the ${row.holds} item${row.holds === 1 ? "" : "s"} in this frame`);
      fold.removeAttribute("aria-hidden");
      fold.setAttribute("aria-label", fold.title);
      name.textContent = `${row.name} \u00b7 ${row.holds}`;
      li.append(fold, icon, name, eye, lock);
    } else {
      li.append(icon, name, eye, lock);
    }
    li.classList.toggle("is-held", Boolean(row.held));
    li.setAttribute("aria-label", `${row.name}${row.holds ? `, holds ${row.holds}` : ""}${hidden ? ", hidden" : ""}${locked ? ", locked" : ""}`);
    tree.append(li);
  }
  const items = [...tree.querySelectorAll("[role='treeitem']")];
  const keep = items.find((r) => r.dataset.key === activeKey) || items.find((r) => r.getAttribute("aria-selected") === "true") || items[0];
  if (keep) keep.tabIndex = 0;
}

//: **The head says what the tint means** (INBOX 824: the owner asked whether
//: a tinted row meant "in the frame"). A tinted row is selected on the board;
//: the count is that, and Clear is the way out of it.
function wbLayersSelectedHead(count) {
  const label = document.getElementById("wb-layers-selected-count");
  if (label) label.textContent = count ? `${count} selected on the board` : "Nothing selected";
  const clear = document.getElementById("wb-layers-clear");
  if (clear) clear.disabled = !count;
}

function wbLayerIcon(kind, item) {
  if (kind === "node") return "ph-note";
  if (kind === "sketch") {
    const parsed = wbSketchParsedData(item);
    if (!parsed) return "ph-flow-arrow";
    if (parsed.icon) return "ph-smiley";
    return WB_FILLABLE_SHAPES.has(parsed.shape) ? "ph-shapes" : "ph-scribble";
  }
  return { image: "ph-image", frame: "ph-frame-corners", text: item.data?.bg ? "ph-note-blank" : "ph-text-t" }[item.kind] || "ph-square";
}

function wbLayerEntry(li) {
  const kind = li?.dataset.kind;
  const item = kind ? wbFindItem(kind, Number(li.dataset.id)) : null;
  return item ? [kind, item] : null;
}

function wbLayerFocus(key) {
  const row = document.querySelector(`#wb-layers-tree [data-key="${key}"]`);
  if (!row) return;
  for (const r of document.querySelectorAll("#wb-layers-tree [tabindex='0']")) r.tabIndex = -1;
  row.tabIndex = 0;
  row.focus({ preventScroll: true });
}

function wbLayerSelect(li, { zoom = true } = {}) {
  if (li?.dataset.group) {
    clearWbSelection();
    for (const kind of ["node", "object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        if (item.group_id === li.dataset.group && !wbIsLocked(kind, item) && !wbItemHidden(kind, item)) wbMultiSelection.add(wbMultiKey(kind, item.id));
      }
    }
    wbApplySelectionHighlight();
    wbUpdateSelectionBar();
    wbRenderLayers();
    wbLayerFocus(li.dataset.key);
    return;
  }
  const entry = wbLayerEntry(li);
  if (!entry) return;
  const [kind, item] = entry;
  if (wbIsLocked(kind, item) || wbItemHidden(kind, item)) {
    wbAnnounce(`${wbLayerName(kind, item)} is ${wbIsLocked(kind, item) ? "locked: L unlocks it" : "hidden: H shows it"}.`);
    return;
  }
  selectWbItem(kind, item.id);
  if (zoom) {
    const box = wbItemBBox(kind, item);
    if (box) wbCenterOn(box, { animate: true });
  }
  wbAnnounce(wbLayerName(kind, item));
  wbRenderLayers();
  wbLayerFocus(wbMultiKey(kind, item.id));
}

async function wbLayerToggleHidden(li) {
  const entry = wbLayerEntry(li);
  if (!entry) return;
  const [kind, item] = entry;
  const hideLayer = wbLayerOwning(kind, item, "hidden");
  if (hideLayer) return wbLayerSaysOwner(`${wbLayerName(kind, item)} is hidden by its layer, ${hideLayer.name}. Show the layer to see it.`);
  const on = !wbItemHidden(kind, item);
  if (on && wbSelectedItem?.kind === kind && wbSelectedItem.id === item.id) clearWbSelection();
  await wbSetHidden([[kind, item]], on);
  wbScheduleRender();
  wbAnnounce(`${wbLayerName(kind, item)} ${on ? "hidden" : "shown"}.`);
  wbRenderLayers();
  wbLayerFocus(li.dataset.key);
}

async function wbLayerToggleLock(li) {
  const entry = wbLayerEntry(li);
  if (!entry) return;
  const [kind, item] = entry;
  const lockLayer = wbLayerOwning(kind, item, "locked");
  if (lockLayer) return wbLayerSaysOwner(`${wbLayerName(kind, item)} is locked by its layer, ${lockLayer.name}. Unlock the layer to edit it.`);
  const on = !wbIsLocked(kind, item);
  if (on && wbSelectedItem?.kind === kind && wbSelectedItem.id === item.id) clearWbSelection();
  await wbSetLocked([[kind, item]], on);
  wbScheduleRender();
  wbAnnounce(`${wbLayerName(kind, item)} ${on ? "locked" : "unlocked"}.`);
  wbRenderLayers();
  wbLayerFocus(li.dataset.key);
}

async function wbLayerRename(li) {
  const entry = wbLayerEntry(li);
  if (!entry) return;
  const [kind, item] = entry;
  if (kind === "node") {
    toast("A card is named by its note's title: rename the note.");
    return;
  }
  const name = await promptDialog("Name it in the layers", wbLayerName(kind, item), { confirmLabel: "Rename" });
  if (name === null || name === undefined) return;
  const clean = String(name).trim().slice(0, 80);
  await wbRecordGesture(async () => {
    if (kind === "sketch") await wbSaveSketchProps(item, { name: clean || undefined });
    else {
      const data = { ...item.data };
      if (clean) data.name = clean;
      else delete data.name;
      item.data = data;
      await wbSaveObject(item);
    }
  });
  wbRenderLayers();
  wbLayerFocus(li.dataset.key);
}

//: Restacks `li`'s item to just in front of (`above`) or behind the row
//: `target`, within the same layer, through the order commands' z writes,
//: one undo step.
async function wbLayerRestack(li, target, above) {
  const a = wbLayerEntry(li);
  const b = wbLayerEntry(target);
  if (!a || !b || a[1] === b[1]) return;
  const [kind, item] = a;
  const sameLayer = (kind === "sketch") === (b[0] === "sketch") && (item.kind === "frame") === (b[1].kind === "frame");
  if (!sameLayer) {
    toast("Drawings stay under the cards, and frames under both: an item restacks within its own layer.");
    return;
  }
  const peers = wbZOrderStepPeers(kind, item);
  const order = peers.map((p) => p.row).sort((x, y) => (x.z || 0) - (y.z || 0) || x.id - y.id).filter((r) => r !== item);
  const at = order.indexOf(b[1]);
  if (at < 0) return;
  order.splice(above ? at + 1 : at, 0, item);
  const kindOf = new Map(peers.map((p) => [p.row, p.kind]));
  const entries = [];
  let z = Math.min(...order.map((r) => r.z || 0));
  for (const row of order) {
    if ((row.z || 0) !== z) {
      const entry = await wbWriteZ(kindOf.get(row), row, z);
      if (entry) entries.push(entry);
    }
    z += 1;
  }
  if (entries.length === 1) wbPushUndo(entries[0]);
  else if (entries.length > 1) wbPushUndo({ action: "batch", entries });
  wbScheduleRender();
  wbAnnounce(`${wbLayerName(kind, item)} moved ${above ? "in front of" : "behind"} ${wbLayerName(b[0], b[1])}.`);
  wbRenderLayers();
  wbLayerFocus(li.dataset.key);
}

onDomReady(() => {
  const tree = document.getElementById("wb-layers-tree");
  if (!tree) return;
  tree.addEventListener("click", (e) => {
    const li = e.target.closest("[role='treeitem']");
    if (!li) return;
    if (e.target.closest(".wb-layer-eye")) return wbLayerToggleHidden(li);
    if (e.target.closest(".wb-layer-lock")) return wbLayerToggleLock(li);
    wbLayerSelect(li);
  });
  tree.addEventListener("dblclick", (e) => {
    const li = e.target.closest("[role='treeitem']");
    if (li && !e.target.closest("button")) wbLayerRename(li);
  });
  const foldFrame = (li, fold) => {
    const id = Number(li?.dataset.id);
    if (!id || !li.classList.contains("has-held")) return false;
    const folded = wbLayerFoldedFrames.has(id);
    if (fold === folded) return true;
    if (fold) wbLayerFoldedFrames.add(id);
    else wbLayerFoldedFrames.delete(id);
    wbRenderLayers();
    wbLayerFocus(li.dataset.key);
    return true;
  };
  tree.addEventListener("click", (e) => {
    const fold = e.target.closest(".wb-layer-fold");
    if (!fold) return;
    e.stopPropagation();
    const li = fold.closest("[role='treeitem']");
    foldFrame(li, !wbLayerFoldedFrames.has(Number(li.dataset.id)));
  }, true);
  document.getElementById("wb-layers-clear")?.addEventListener("click", () => {
    clearWbSelection();
    wbRenderLayers();
  });
  tree.addEventListener("keydown", (e) => {
    const li = e.target.closest("[role='treeitem']");
    if (!li) return;
    if (e.key === "ArrowLeft" && foldFrame(li, true)) return e.preventDefault();
    if (e.key === "ArrowRight" && foldFrame(li, false)) return e.preventDefault();
    const rows = [...tree.querySelectorAll("[role='treeitem']")];
    const at = rows.indexOf(li);
    const go = (i) => {
      const next = rows[Math.max(0, Math.min(rows.length - 1, i))];
      if (next) wbLayerFocus(next.dataset.key);
    };
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      let i = at + (e.key === "ArrowUp" ? -1 : 1);
      while (rows[i]?.dataset.group) i += e.key === "ArrowUp" ? -1 : 1;
      if (rows[i]) wbLayerRestack(li, rows[i], e.key === "ArrowUp");
    } else if (e.key === "ArrowDown") go(at + 1);
    else if (e.key === "ArrowUp") go(at - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(rows.length - 1);
    else if (e.key === "Enter" || e.key === " ") wbLayerSelect(li);
    else if (plain && e.key.toLowerCase() === "h") wbLayerToggleHidden(li);
    else if (plain && e.key.toLowerCase() === "l") wbLayerToggleLock(li);
    else if (e.key === "F2") wbLayerRename(li);
    else if (e.key === "Delete") {
      wbLayerSelect(li, { zoom: false });
      if (wbSelectedItem || wbMultiSelection.size) deleteWbSelection();
      setTimeout(() => wbRenderLayers(), 400);
    } else return;
    e.preventDefault();
  });
  tree.addEventListener("dragstart", (e) => {
    const li = e.target.closest("[role='treeitem']");
    if (!li || li.dataset.group) return;
    wbLibState.layersDrag = li;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/x-memorymap-layer", li.dataset.key);
  });
  const clearMarks = () => {
    for (const x of tree.querySelectorAll(".drop-above, .drop-below")) x.classList.remove("drop-above", "drop-below");
  };
  tree.addEventListener("dragover", (e) => {
    if (!wbLibState.layersDrag) return;
    const over = e.target.closest("[role='treeitem']");
    if (!over || over === wbLibState.layersDrag || over.dataset.group) return;
    e.preventDefault();
    const r = over.getBoundingClientRect();
    clearMarks();
    over.classList.add(e.clientY < r.top + r.height / 2 ? "drop-above" : "drop-below");
  });
  tree.addEventListener("drop", (e) => {
    if (!wbLibState.layersDrag) return;
    e.preventDefault();
    const over = e.target.closest("[role='treeitem']");
    const above = over?.classList.contains("drop-above");
    clearMarks();
    if (over && over !== wbLibState.layersDrag && !over.dataset.group) wbLayerRestack(wbLibState.layersDrag, over, above);
    wbLibState.layersDrag = null;
  });
  tree.addEventListener("dragend", () => {
    wbLibState.layersDrag = null;
    clearMarks();
  });
});

// --- Pages (WHITEBOARD_PLAN decision 22: frames are the pages) --------------
//
// draw.io has pages; a board here has frames, and decision 22 keeps one
// concept: the sidebar's Pages tab lists the board's frames in presentation
// order, and changing that order is changing the presentation. A frame's
// place is `page` in its data (1, 2, ...); a board whose frames have none is
// in reading order, top to bottom and left to right (`wbFramesInOrder`), and
// the first reorder writes every frame's number, one undo step.


function wbRenderPages() {
  const list = document.getElementById("wb-pages-list");
  if (!list || list.closest("[hidden]")) return;
  const active = list.querySelector("[tabindex='0']")?.dataset.id;
  list.replaceChildren();
  const frames = wbFramesInOrder();
  if (!frames.length) {
    const li = document.createElement("li");
    li.className = "muted wb-lib-note";
    li.setAttribute("role", "none");
    li.textContent = "No frames yet. Add one (F) and it becomes a page.";
    list.append(li);
    return;
  }
  const selected = wbSelectedItem?.kind === "object" ? wbSelectedItem.id : null;
  frames.forEach((frame, i) => {
    const li = document.createElement("li");
    li.className = "wb-layer-row wb-page-row";
    li.setAttribute("role", "treeitem");
    li.setAttribute("aria-level", "1");
    li.dataset.id = String(frame.id);
    li.tabIndex = -1;
    li.draggable = true;
    li.setAttribute("aria-selected", frame.id === selected ? "true" : "false");
    const number = document.createElement("span");
    number.className = "wb-page-number";
    number.textContent = String(i + 1);
    number.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "wb-layer-name";
    name.textContent = wbFrameTitle(frame);
    const present = wbLayerButton("wb-page-present", "ph-presentation", "Present from this page (P)");
    li.append(number, name, present, wbPageMenu(frame));
    li.setAttribute("aria-label", `Page ${i + 1}: ${wbFrameTitle(frame)}`);
    list.append(li);
  });
  const focusRow = list.querySelector(`[data-id="${active}"]`) || list.querySelector("[role='treeitem']");
  if (focusRow) focusRow.tabIndex = 0;
}

function wbPageFocus(id) {
  const list = document.getElementById("wb-pages-list");
  const row = list?.querySelector(`[data-id="${id}"]`);
  if (!row) return;
  for (const r of list.querySelectorAll("[tabindex='0']")) r.tabIndex = -1;
  row.tabIndex = 0;
  row.focus({ preventScroll: false });
}

//: Brings the frame on screen and selects it.
function wbPageGo(id) {
  const frame = (wbState.objects || []).find((o) => o.id === id);
  if (!frame) return;
  clearWbSelection();
  selectWbItem("object", id);
  wbCenterOn({ minX: frame.x, minY: frame.y - 28, maxX: frame.x + frame.width, maxY: frame.y + frame.height });
  wbRenderPages();
  wbPageFocus(id);
}

//: Moves page `id` to `to` (0-based) and writes every frame's number, one
//: undo step.
async function wbPageMove(id, to) {
  const frames = wbFramesInOrder();
  const from = frames.findIndex((f) => f.id === id);
  if (from < 0 || to < 0 || to >= frames.length || from === to) return;
  const [moved] = frames.splice(from, 1);
  frames.splice(to, 0, moved);
  await wbRecordGesture(async () => {
    for (const [i, frame] of frames.entries()) {
      if (frame.data?.page === i + 1) continue;
      frame.data = { ...frame.data, page: i + 1 };
      await wbSaveObject(frame);
    }
  });
  wbRenderPages();
  wbPageFocus(id);
  wbAnnounce(`${wbFrameTitle(moved)} is page ${to + 1} of ${frames.length}.`);
}

//: **A page row is renamed in the row** (INBOX 822, the owner: "I cant rename
//: frames in the pages sidebar"): the same one-line editor as the frame's own
//: title on the canvas (`wbEditFrameTitle`: Enter keeps, Escape cancels, one
//: Undo step), on the row's name. The canvas title and the row repaint once
//: it commits.
function wbPageRename(id) {
  const frame = (wbState.objects || []).find((o) => o.id === id);
  const row = document.querySelector(`#wb-pages-list [data-id="${id}"]`);
  const nameEl = row?.querySelector(".wb-layer-name");
  if (!frame || !nameEl || nameEl.isContentEditable) return;
  row.draggable = false;
  wbEditFrameTitle(nameEl, frame);
  nameEl.addEventListener("blur", () => {
    setTimeout(() => {
      wbScheduleRender();
      wbRenderPages();
      wbPageFocus(id);
    }, 0);
  }, { once: true });
}

//: The row's actions: the kebab recipe, so what a frame's menu on the canvas
//: offers is also on the page that stands for it.
function wbPageMenu(frame) {
  const id = frame.id;
  const menu = kebabMenu([
    { label: "ph:pencil-simple Rename", title: "Rename this page (F2)", run: () => wbPageRename(id) },
    { label: "ph:arrows-in Fit to contents", title: "Snug the frame to what is inside it", run: () => wbFrameFit((wbState.objects || []).find((o) => o.id === id), "nesw") },
    { label: "ph:presentation Present from here", title: "Start the presentation on this page (P)", run: () => wbPagePresent(id) },
    { label: "ph:trash Delete the frame", title: "What it holds stays on the board", group: "delete", run: () => {
      wbPageGo(id);
      deleteWbSelection();
      setTimeout(() => wbRenderPages(), 400);
    } },
  ], "Actions for this page");
  menu.classList.add("wb-page-menu");
  return menu;
}

function wbPagePresent(id) {
  const at = wbFramesInOrder().findIndex((f) => f.id === id);
  wbStartPresenting();
  if (at > 0 && wbPresent) requestAnimationFrame(() => requestAnimationFrame(() => wbPresentShow(at)));
}

onDomReady(() => {
  const list = document.getElementById("wb-pages-list");
  if (!list) return;
  const rowOf = (e) => e.target.closest("[role='treeitem']");
  list.addEventListener("click", (e) => {
    const li = rowOf(e);
    if (!li) return;
    if (e.target.closest(".wb-page-present")) return wbPagePresent(Number(li.dataset.id));
    if (e.target.closest(".wb-page-menu, .menu-wrap") || e.target.isContentEditable) return;
    //: The second press of a double-click renames. The first one went to the
    //: page and redrew the list, so the browser never sees the same element
    //: twice and sends no `dblclick`: `detail` is what counts the presses.
    if (e.detail === 2) return wbPageRename(Number(li.dataset.id));
    wbPageGo(Number(li.dataset.id));
  });
  list.addEventListener("dblclick", (e) => {
    const li = rowOf(e);
    if (li && !e.target.closest("button, .menu-wrap") && !e.target.isContentEditable) wbPageRename(Number(li.dataset.id));
  });
  list.addEventListener("keydown", (e) => {
    const li = rowOf(e);
    if (!li) return;
    const rows = [...list.querySelectorAll("[role='treeitem']")];
    const at = rows.indexOf(li);
    const id = Number(li.dataset.id);
    const go = (i) => {
      const next = rows[Math.max(0, Math.min(rows.length - 1, i))];
      if (next) wbPageFocus(next.dataset.id);
    };
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) wbPageMove(id, at + (e.key === "ArrowUp" ? -1 : 1));
    else if (e.key === "ArrowDown") go(at + 1);
    else if (e.key === "ArrowUp") go(at - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(rows.length - 1);
    else if (e.key === "Enter" || e.key === " ") wbPageGo(id);
    else if (plain && e.key.toLowerCase() === "p") wbPagePresent(id);
    else if (e.key === "F2") wbPageRename(id);
    else return;
    e.preventDefault();
  });
  list.addEventListener("dragstart", (e) => {
    const li = rowOf(e);
    if (!li) return;
    wbLibState.pagesDrag = li;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/x-memorymap-page", li.dataset.id);
  });
  const clearMarks = () => {
    for (const x of list.querySelectorAll(".drop-above, .drop-below")) x.classList.remove("drop-above", "drop-below");
  };
  list.addEventListener("dragover", (e) => {
    if (!wbLibState.pagesDrag) return;
    const over = rowOf(e);
    if (!over || over === wbLibState.pagesDrag) return;
    e.preventDefault();
    const r = over.getBoundingClientRect();
    clearMarks();
    over.classList.add(e.clientY < r.top + r.height / 2 ? "drop-above" : "drop-below");
  });
  list.addEventListener("drop", (e) => {
    const over = rowOf(e);
    const dragged = wbLibState.pagesDrag;
    wbLibState.pagesDrag = null;
    if (!over || !dragged || over === dragged) return clearMarks();
    e.preventDefault();
    const rows = [...list.querySelectorAll("[role='treeitem']")];
    const from = rows.indexOf(dragged);
    let to = rows.indexOf(over) + (over.classList.contains("drop-below") ? 1 : 0);
    if (from < to) to -= 1;
    clearMarks();
    wbPageMove(Number(dragged.dataset.id), to);
  });
  list.addEventListener("dragend", () => {
    wbLibState.pagesDrag = null;
    clearMarks();
  });
});

// --- Outline ---------------------------------------------------------------
//
// A mind map's sidebar has an Outline tab. Its rows are the mind map's
// editable outline (MINDMAP_PLAN decision 33, M3): `wbOutlineSync` and its
// keys live in whiteboard-map.js, which redraws them after every render, so
// the refresh below leaves this tab to it.

//: **An open tab follows the board** (found with the Pages tab): Layers,
//: Pages and Outline were drawn when the tab opened and not again, so a shape
//: drawn with the Layers tab open was missing from it. After every render,
//: once things settle, the open tab is drawn again; a row that had the focus
//: keeps it.

function wbSideRefreshSoon() {
  const panel = document.getElementById("wb-sidebar-panel");
  if (!panel || panel.classList.contains("hidden")) return;
  clearTimeout(wbLibState.sideRefreshTimer);
  wbLibState.sideRefreshTimer = setTimeout(() => {
    const tab = wbSideState().tab;
    if (tab === "map") return wbRenderSideMap();
    const list = { layers: "wb-layers-tree", pages: "wb-pages-list" }[tab];
    const host = list && document.getElementById(list);
    if (!host || host.closest("[hidden]")) return;
    //: A row being renamed is not redrawn under the hand typing in it.
    if (host.querySelector("[contenteditable]")) return;
    const focused = host.contains(document.activeElement) ? document.activeElement : null;
    const key = focused?.dataset.key || focused?.dataset.id;
    if (tab === "layers") wbRenderLayers();
    else wbRenderPages();
    if (key) {
      const row = host.querySelector(`[data-key="${key}"], [data-id="${key}"]`);
      if (row) {
        for (const r of host.querySelectorAll("[tabindex='0']")) r.tabIndex = -1;
        row.tabIndex = 0;
        row.focus({ preventScroll: true });
      }
    }
  }, 250);
}
