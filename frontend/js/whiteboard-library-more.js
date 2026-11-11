(() => {
  // whiteboard-library-more.js: draw.io's shape picker and its "replace a shape" (WHITEBOARD_PLAN sections 10 and 15). One
  // small popup, built from the rich picker's rows: a search box over the library's shapes, each row drawn with its own
  // thumbnail. It has three jobs. `place`: the Insert menu and the command palette open it (draw.io's Ctrl+Shift+K is the app's Quick sketch pad, so there is no chord)
  // at the pointer and Enter puts the match where the pointer was. `replace`: the selected shape takes the match's outline
  // and keeps its words, colours and connectors. `connect`: a drag from a copy arrow to empty space opens it there; the
  // match is placed and joined, and Enter on an empty search takes the copy of the shape the arrow would have made.
  // The pure parts take plain data, so a node test runs them without a board.

  const ROWS = 30;
  const START = 12;
  const HIDDEN_KINDS = new Set(["style", "palette", "preset", "branch", "template"]);

  //: Pure: the data of the one drawing a library entry holds, if it is one closed shape that can stand in for another
  //: (no icon, no connector, no second item), else null.
  function replacement(entry) {
    const items = entry?.payload?.items;
    if (!entry || !["element", "shape"].includes(entry.kind) || !Array.isArray(items) || items.length !== 1) return null;
    if ((entry.payload.links || []).length) return null;
    const [one] = items;
    const data = one?.data;
    if (one?.kind !== "sketch" || !data || typeof data.d !== "string" || data.icon || /^link-/.test(String(data.type || ""))) return null;
    return /[zZ]/.test(data.d) ? data : null;
  }

  //: Pure: the data a shape has after it takes `data`'s outline, stretched over its own box. `box` is the shape's box and
  //: `own` the outline's, both `{minX, minY, width, height}`; `transform` is the board's path transform. The words, colours,
  //: line and fill stay; the outline, its kind and its label area come from the entry.
  function replaceData(parsed, data, box, own, transform) {
    const sx = Math.max(box.width, 1) / Math.max(own.width, 1);
    const sy = Math.max(box.height, 1) / Math.max(own.height, 1);
    const next = {
      ...parsed,
      d: transform(data.d, { dx: box.minX - own.minX, dy: box.minY - own.minY, sx, sy, anchorX: own.minX, anchorY: own.minY }),
      shape: data.shape || "custom",
    };
    delete next.label_area;
    delete next.shapeKind;
    if (data.shapeKind) next.shapeKind = data.shapeKind;
    if (data.label_area) next.label_area = data.label_area;
    return next;
  }

  //: Pure: the entries that match `query`, best first: a name that starts with it, a word of the name that starts with the
  //: first word, a name that holds the words, then a tag or the set's name. Every word must be somewhere in the entry.
  function rankEntries(entries, query, limit = ROWS) {
    const words = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    const scored = [];
    for (const entry of entries) {
      const name = String(entry.name || "").toLowerCase();
      const all = `${name} ${(entry.tags || []).join(" ")} ${entry.set || ""}`.toLowerCase();
      if (!words.every((w) => all.includes(w))) continue;
      const full = words.join(" ");
      const rank = name.startsWith(full) ? 0
        : name.split(/[\s\-_/()]+/).some((part) => part.startsWith(words[0])) && words.every((w) => name.includes(w)) ? 1
          : words.every((w) => name.includes(w)) ? 2 : 3;
      scored.push({ entry, rank, name });
    }
    scored.sort((a, b) => a.rank - b.rank || a.name.length - b.name.length || a.name.localeCompare(b.name));
    return scored.slice(0, limit).map((s) => s.entry);
  }

  //: Pure: what is offered before anything is typed: what was placed last (`recent`, refs), then the favourites, then the
  //: first entries of the list, without a repeat.
  function startEntries(entries, recent, limit = START) {
    const byRef = new Map(entries.map((e) => [e.ref, e]));
    const out = [];
    const add = (entry) => {
      if (entry && !out.includes(entry) && out.length < limit) out.push(entry);
    };
    for (const ref of recent || []) add(byRef.get(ref));
    for (const entry of entries) if (entry.favourite) add(entry);
    for (const entry of entries) add(entry);
    return out;
  }

  const TEXT = {
    place: { title: "Add a shape", placeholder: "Search shapes", hint: "Enter places it where the pointer was." },
    replace: { title: "Replace with a shape", placeholder: "Search shapes", hint: "Enter swaps the outline; its words and connectors stay." },
    connect: { title: "Add a shape and join it", placeholder: "Search shapes, or Enter for a copy", hint: "Enter on an empty search copies this shape and joins it." },
  };

  const state = { open: null, drag: null, dragged: false };

  function close() {
    state.open?.close();
  }

  //: Where the pointer last was on the canvas, as a client point, else the middle of the canvas.
  function pointerClient() {
    if (typeof wbPointerClient !== "undefined" && wbPointerClient) return { x: wbPointerClient.clientX, y: wbPointerClient.clientY };
    const rect = document.getElementById("whiteboard-container")?.getBoundingClientRect();
    return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  }

  async function entriesFor(mode) {
    if (!wbLibState.lib) await wbLoadLibrary();
    const all = wbLibEntries().filter((e) => !HIDDEN_KINDS.has(e.kind));
    return mode === "replace" ? all.filter((e) => replacement(e)) : all;
  }

  //: Swap the selected shape's outline for the entry's. One Undo step, as Change the shape is.
  async function replaceWith(entry) {
    const target = wbSwapTarget();
    const data = replacement(entry);
    if (!target || !data) {
      toast("Select one closed shape first.", "info");
      return false;
    }
    const { item, parsed } = target;
    const box = wbPathBBox(parsed.d);
    const own = wbPathBBox(data.d);
    if (!box || !own) return false;
    const before = WB_KIND_INFO.sketch.payload(item);
    item.data = JSON.stringify(replaceData(parsed, data, box, own, wbTransformPathD));
    await wbSaveSketchProps(item, {});
    wbPushUndo({ action: "move", kind: "sketch", id: item.id, before });
    wbScheduleRender();
    wbAnnounce(`Replaced with ${entry.name}.`);
    return true;
  }

  //: Open the picker. `mode`: place, replace or connect. `at`: the board point a placed shape lands on (the pointer's by
  //: default); `client`: the client point the panel hangs from; `dir`: the copy arrow's side, for a copy; `from`: the shape it came from, selected again on a pick (the release click cleared it).
  async function openPicker({ mode = "place", at = null, client = null, dir = null, from = null } = {}) {
    close();
    if (mode === "replace" && !wbSwapTarget()) {
      toast("Select one closed shape first.", "info");
      return;
    }
    const text = TEXT[mode] || TEXT.place;
    const hangs = client || pointerClient();
    const target = at || wbClientToBoard(hangs.x, hangs.y);
    const returnFocus = document.activeElement;
    let entries = await entriesFor(mode);
    let query = "";
    let rows = [];
    let active = -1;
    let turn = 0;

    const anchor = document.createElement("span");
    anchor.className = "wb-libpick-anchor";
    anchor.style.left = `${Math.round(hangs.x)}px`;
    anchor.style.top = `${Math.round(hangs.y)}px`;
    const panel = document.createElement("div");
    panel.className = "help-popover wb-libpick";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", text.title);
    const shut = () => {
      if (!panel.isConnected) return;
      document.removeEventListener("pointerdown", outside, true);
      panel.remove();
      anchor.remove();
      if (state.open?.panel === panel) state.open = null;
    };
    const closeAndReturn = () => {
      shut();
      if (returnFocus?.isConnected && returnFocus !== document.body) returnFocus.focus({ preventScroll: true });
    };
    const head = dialogHead(text.title, closeAndReturn);
    const field = document.createElement("div");
    field.className = "search-field";
    const lens = document.createElement("i");
    lens.className = "ph ph-magnifying-glass search-field-icon";
    lens.setAttribute("aria-hidden", "true");
    const search = document.createElement("input");
    search.type = "search";
    search.className = "search-field-input";
    search.autocomplete = "off";
    search.placeholder = text.placeholder;
    search.setAttribute("aria-label", "Search shapes");
    search.setAttribute("role", "combobox");
    search.setAttribute("aria-expanded", "true");
    search.setAttribute("aria-autocomplete", "list");
    field.append(lens, search);
    const list = document.createElement("ul");
    list.className = "rich-picker-list wb-libpick-list";
    list.id = "wb-libpick-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Shapes");
    search.setAttribute("aria-controls", list.id);
    const status = document.createElement("p");
    status.className = "muted wb-libpick-hint";
    status.setAttribute("aria-live", "polite");
    status.textContent = text.hint;
    panel.append(head, field, list, status);

    const light = (at2, scroll = true) => {
      if (!rows.length) return;
      active = Math.max(0, Math.min(rows.length - 1, at2));
      const lit = richPickerSetActive(null, rows, active);
      search.setAttribute("aria-activedescendant", lit.id);
      if (scroll) lit.scrollIntoView({ block: "nearest" });
    };
    const pick = async (row) => {
      if (!row) return;
      shut();
      if (from) selectWbItem(from.kind, from.id);
      if (row._copy) {
        await wbCloneConnect(dir, target);
      } else if (mode === "replace") {
        await replaceWith(row._entry);
      } else {
        await wbLibPlace(row._entry, target, { connect: mode === "connect" });
      }
    };
    const draw = () => {
      turn += 1;
      const q = query.trim();
      const found = q ? rankEntries(entries, q) : startEntries(entries, wbLibState.lib?.recent);
      rows = [];
      list.replaceChildren();
      if (mode === "connect" && !q) {
        const row = richPickerRow({ icon: "ph:copy", label: "A copy of this shape", about: "Joined to it", id: "wb-shape-pick-copy" });
        row._copy = true;
        rows.push(row);
      }
      found.forEach((entry, i) => {
        const row = richPickerRow({ face: wbLibThumb(entry), label: entry.name, about: entry.set, query: q, id: `wb-shape-pick-${i}` });
        row._entry = entry;
        rows.push(row);
      });
      if (!rows.length) {
        const none = document.createElement("li");
        none.className = "muted wb-libpick-empty";
        none.setAttribute("role", "presentation");
        none.textContent = q ? "No shape by that name." : "No shapes to show.";
        list.append(none);
        search.removeAttribute("aria-activedescendant");
        return;
      }
      list.append(...rows);
      light(0, false);
    };
    search.addEventListener("input", () => {
      query = search.value;
      draw();
    });
    search.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        light(active + (event.key === "ArrowDown" ? 1 : -1));
      } else if (event.key === "Enter") {
        event.preventDefault();
        pick(rows[active >= 0 ? active : 0]);
      }
    });
    list.addEventListener("click", (event) => {
      const row = event.target.closest(".rich-picker-row");
      if (row) pick(row);
    });
    list.addEventListener("pointermove", (event) => {
      const row = event.target.closest(".rich-picker-row");
      const at2 = row ? rows.indexOf(row) : -1;
      if (at2 >= 0 && at2 !== active) light(at2, false);
    });
    //: A dialog: no key leaves it (Enter must not reach the canvas behind), and Escape closes it first.
    panel.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        closeAndReturn();
      }
    });
    const outside = (event) => {
      if (!panel.contains(event.target)) shut();
    };
    document.addEventListener("pointerdown", outside, true);

    draw();
    document.body.append(anchor, panel);
    state.open = { panel, close: shut };
    panel.style.visibility = "hidden";
    afterFrames(() => setTimeout(() => {
      if (!panel.isConnected) return;
      placeHelpPopover(panel, anchor);
      //: The placement measured the panel while its arrival animation still had it at 94% (`ui-grow`), so a panel near the
      //: right or bottom edge ended a few pixels outside the window: held inside by its laid-out size, which no scale changes.
      const left = Math.min(parseFloat(panel.style.left) || 0, window.innerWidth - 8 - panel.offsetWidth);
      const top = Math.min(parseFloat(panel.style.top) || 0, window.innerHeight - 8 - panel.offsetHeight);
      panel.style.left = `${Math.max(8, Math.round(left))}px`;
      panel.style.top = `${Math.max(8, Math.round(top))}px`;
      panel.style.visibility = "";
      search.focus({ preventScroll: true });
    }), 1);
    //: The converted draw.io sets and the icons come when asked, as the panel's search does; the list is drawn again when
    //: they arrive, unless the person has moved on.
    const mine = turn;
    wbLoadShapeSets().then(async () => {
      if (!panel.isConnected) return;
      entries = await entriesFor(mode);
      if (turn === mine || query) draw();
    });
  }

  //: A press on a copy arrow: if the pointer then travels away and lets go in empty space, the picker opens there. A
  //: plain click is left to the arrow (it copies one step along, as before).
  function gripPress(event, dir) {
    state.dragged = false;
    const start = { x: event.clientX, y: event.clientY };
    const move = (e) => {
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 16) state.dragged = true;
    };
    const stop = () => {
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", up, true);
      window.removeEventListener("pointercancel", stop, true);
    };
    const up = (e) => {
      stop();
      if (!state.dragged) return;
      const source = wbCloneSource();
      const at = wbClientToBoard(e.clientX, e.clientY);
      const box = source?.bbox;
      const inside = box && at[0] >= box.minX && at[0] <= box.maxX && at[1] >= box.minY && at[1] <= box.maxY;
      if (!source || inside) return;
      openPicker({ mode: "connect", at, client: { x: e.clientX, y: e.clientY }, dir, from: { kind: source.kind, id: source.id } });
    };
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", up, true);
    window.addEventListener("pointercancel", stop, true);
  }

  wbFmtState.libraryMore = {
    replacement, replaceData, rankEntries, startEntries, replaceWith, open: openPicker, close, gripPress,
    dragged: () => state.dragged,
  };
})();
