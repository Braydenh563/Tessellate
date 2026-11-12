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

  //: Pure: the forms of one typed word to look for, the word first: light English stemming (plural, -ing, -ed, -er), so
  //: "arrows" finds "arrow" and "connecting" finds "connector". Each cut also tries the stem with an "e" back and a
  //: doubled last letter dropped ("running" to "run", "making" to "make"). Short words are left alone.
  function wordForms(word) {
    const out = [word];
    const add = (stem) => {
      if (stem.length >= 3 && !out.includes(stem)) out.push(stem);
    };
    const cut = (stem) => {
      add(stem);
      add(`${stem}e`);
      if (/([^aeiou])\1$/.test(stem)) add(stem.slice(0, -1));
    };
    if (word.length < 4) return out;
    if (/ies$/.test(word)) add(`${word.slice(0, -3)}y`);
    if (/(?:ing|ed|er)$/.test(word) && word.length >= 5) cut(word.replace(/(?:ing|ed|er)$/, ""));
    if (/es$/.test(word)) add(word.slice(0, -2));
    if (/s$/.test(word) && !/ss$/.test(word)) add(word.slice(0, -1));
    return out;
  }

  //: Pure: the entries that match `query`, best first: a name that starts with it, a word of the name that starts with the
  //: first word, a name that holds the words, then a tag or the set's name. Every word must be somewhere in the entry,
  //: as typed or as one of its stems (`wordForms`); the typed form wins where both are there, so the order is unchanged.
  function rankEntries(entries, query, limit = ROWS) {
    const typed = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
    if (!typed.length) return [];
    const scored = [];
    for (const entry of entries) {
      const name = String(entry.name || "").toLowerCase();
      const all = `${name} ${(entry.tags || []).join(" ")} ${entry.set || ""}`.toLowerCase();
      const words = typed.map((w) => wordForms(w).find((form) => all.includes(form)));
      if (words.some((w) => w === undefined)) continue;
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

  //: **Shape libraries** (draw.io's "More shapes"): a dialog on the Library tab with one row per set, its name and count and
  //: an on/off switch. The choice is per device (`prefs`, "wb-lib-sets-off", read by `wbLibState.isOff`). A set that is off is
  //: not listed or searched, and is not fetched; turning one on fetches it then. The two template sets feed the new-board
  //: galleries, so they have no row.
  const SETS_KEY = "wb-lib-sets-off";
  const librarySets = {
    rows() {
      const lib = wbLibState.lib || {};
      const own = (lib.sets || []).filter((x) => !["templates", "maps"].includes(x.key));
      return [...own, ...(lib.shape_sets || [])].map((x) => ({ key: x.key, name: x.name, count: x.count }));
    },
    //: Turn one set on or off, and draw the list again (a set turned on is fetched first).
    async setOn(key, on) {
      const off = new Set(prefs.json(SETS_KEY, []));
      if (on) off.delete(key);
      else off.add(key);
      prefs.set(SETS_KEY, JSON.stringify([...off]));
      if (on && (wbLibState.lib?.shape_sets || []).some((x) => x.key === key)) await wbLoadShapeSets([key]);
      else if (on && key === "icons") await wbLoadIcons();
      if (on) await wbLoadLibrary();
      else wbRenderLibrary();
    },
    async open() {
      document.getElementById("wb-sets-dialog")?.remove();
      if (!wbLibState.lib) await wbLoadLibrary();
      const returnFocus = document.activeElement;
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay confirm-overlay wb-sets-overlay";
      overlay.id = "wb-sets-dialog";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-label", "Shape libraries");
      const card = document.createElement("div");
      card.className = "card modal-card confirm-card wb-sets-card";
      const hint = document.createElement("p");
      hint.className = "muted wb-sets-hint";
      hint.textContent = "Sets that are off are hidden from the library and from search. The choice is kept on this device.";
      const list = document.createElement("div");
      list.className = "wb-sets-list";
      for (const row of librarySets.rows()) {
        const label = document.createElement("label");
        label.className = "setting-check wb-sets-row";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.dataset.set = row.key;
        box.checked = !wbLibState.isOff(row.key);
        box.addEventListener("change", () => librarySets.setOn(row.key, box.checked));
        const name = document.createElement("span");
        name.textContent = row.name;
        const count = document.createElement("span");
        count.className = "muted wb-sets-count";
        count.textContent = String(row.count ?? "");
        label.append(box, name, count);
        list.append(label);
      }
      let settled = false;
      const close = () => {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
        returnFocus?.focus?.();
      };
      const onKey = (event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        event.stopPropagation();
        close();
      };
      card.append(dialogHead("Shape libraries", close), hint, list);
      overlay.append(card);
      wireBackdropClose(overlay, close);
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(overlay);
      list.querySelector("input")?.focus();
    },
  };

  //: **Drop a library item onto a line to put it in the line** (draw.io's `dropAndConnect`): the link A to B becomes A to the
  //: item and the item to B, split at the item's ports (the side facing A to enter, the opposite side to leave, by whichever
  //: way the line mostly runs). Both halves keep the line's look and its caps; its bends and free ends go with the half they
  //: belonged to. Run inside the placement's gesture, so the placement and the split are one undo step.
  const ROUTE_KEYS = ["bend", "points", "via", "waypoints"];

  //: Pure: the two port fractions for an item put on a line from `from` to `to` (board points): `into` is where the first
  //: half lands on the item, `out` where the second leaves it.
  function splitPorts(from, to) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const across = Math.abs(dx) >= Math.abs(dy);
    const forward = (across ? dx : dy) >= 0;
    const into = across ? { x: forward ? 0 : 1, y: 0.5 } : { x: 0.5, y: forward ? 0 : 1 };
    return { into, out: { x: 1 - into.x, y: 1 - into.y } };
  }

  //: Pure: the two links' data a line `data` becomes when item (`kind`, `id`) is put in it.
  function splitData(data, kind, id, ports) {
    const first = { ...data, targetId: id, targetKind: kind, targetAnchor: ports.into };
    const second = { ...data, sourceId: id, sourceKind: kind, sourceAnchor: ports.out };
    delete first.targetPoint;
    delete second.sourcePoint;
    for (const key of ROUTE_KEYS) {
      delete first[key];
      delete second[key];
    }
    //: The second half is a line of the board's own, not a part of a library copy.
    for (const key of ["library_ref", "library_part", "library_link"]) delete second[key];
    return [first, second];
  }

  //: Put the placed item (`kind`, `item`) into the line `link` (a sketch). False when the line cannot be split: it has no
  //: resolvable ends, or it already ends on the item.
  async function splitLink(link, kind, item) {
    let data = null;
    try {
      data = JSON.parse(link.data);
    } catch {
      return false;
    }
    if (!data || !String(data.type || "").startsWith("link-")) return false;
    const ends = wbResolveLinkEndpoints(data);
    if (!ends) return false;
    const touches = (side) => data[`${side}Id`] === item.id && (data[`${side}Kind`] || "node") === kind;
    if (touches("source") || touches("target")) return false;
    const [firstData, secondData] = splitData(data, kind, item.id, splitPorts(ends.source, ends.target));
    //: The line is replaced by two new ones, not edited: undone as one step, the old line comes back first and the two halves
    //: go after it. An edited line would be dropped by the server with the item (it ends on it) before its old shape was put back.
    await apiJson(`/whiteboard/sketches/${link.id}`, { method: "DELETE" });
    wbState.sketches = wbState.sketches.filter((s) => s.id !== link.id);
    for (const half of [firstData, secondData]) {
      const made = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ data: JSON.stringify(half), x: link.x ?? 0, y: link.y ?? 0, z: link.z ?? wbStackNewZ("sketch"), board_id: window.currentBoardId ?? null }),
      });
      wbState.sketches.push(made);
    }
    return true;
  }

  //: **Placed copies and their source** (L-whiteboard-9, L275). A placed part remembers `library_ref` (`{id, version}` or
  //: `{builtin}`, never followed by the server). "Update from the library" reads that source again and gives the copy its
  //: content: a drawing takes the source's outline stretched over the copy's own box, an object keeps its place and size, so
  //: the copy stays where it is and as big as it is. "Linked" is a placement that also carries `library_ref.linked {sig}`
  //: (a hash of the source's payload); a copy whose source now hashes differently is updated when the board opens and when
  //: the library item is replaced, with no undo step of its own. Unlink drops the flag. A copy is its group's parts (or the one
  //: part) plus the links between them; it is matched to the source part by part, per kind in order, so a copy that lost or
  //: gained a part is left alone and said so.
  const isLinkRow = (kind, item) => kind === "sketch" && /"type"\s*:\s*"link-/.test(item.data);
  const refOf = (kind, item) => {
    if (kind === "object") return item.data?.library_ref || null;
    try {
      return JSON.parse(item.data)?.library_ref || null;
    } catch {
      return null;
    }
  };
  const refKey = (ref) => JSON.stringify([ref?.id ?? null, ref?.builtin ?? null]);
  const copies = {
    //: Pure: a short hash of a payload; it changes when the source's content does.
    sigOf(payload) {
      const text = JSON.stringify(payload ?? null);
      let hash = 5381;
      for (let i = 0; i < text.length; i += 1) hash = ((hash * 33) ^ text.charCodeAt(i)) >>> 0;
      return hash.toString(36);
    },
    //: The sketches and objects of the open board, as `{kind, item}`.
    boardRows: () => [
      ...(wbState?.sketches || []).map((item) => ({ kind: "sketch", item })),
      ...(wbState?.objects || []).map((item) => ({ kind: "object", item })),
    ],
    selectionRows() {
      const entries = wbMultiSelection.size
        ? wbSelectionEntries()
        : wbSelectedItem ? [{ kind: wbSelectedItem.kind, item: wbFindItem(wbSelectedItem.kind, wbSelectedItem.id) }] : [];
      return entries.filter((e) => e.item && (e.kind === "sketch" || e.kind === "object"));
    },
    //: The copies the rows belong to: `{ref, members, links}`, one per source and group.
    collect(seed) {
      const board = copies.boardRows();
      const found = new Map();
      for (const { kind, item } of seed) {
        const ref = refOf(kind, item);
        if (!ref || isLinkRow(kind, item)) continue;
        const rk = refKey(ref);
        const group = item.group_id || null;
        const key = `${rk}|${group || `${kind}${item.id}`}`;
        if (found.has(key)) continue;
        const members = group
          ? board.filter((r) => r.item.group_id === group && !isLinkRow(r.kind, r.item) && refOf(r.kind, r.item) && refKey(refOf(r.kind, r.item)) === rk)
          : [{ kind, item }];
        members.sort((a, b) => a.item.id - b.item.id);
        const ids = new Set(members.map((m) => `${m.kind}:${m.item.id}`));
        const links = board.filter((r) => {
          if (!isLinkRow(r.kind, r.item) || refKey(refOf("sketch", r.item)) !== rk) return false;
          const data = JSON.parse(r.item.data);
          return ids.has(`${data.sourceKind || "node"}:${data.sourceId}`) && ids.has(`${data.targetKind || "node"}:${data.targetId}`);
        });
        links.sort((a, b) => a.item.id - b.item.id);
        found.set(key, { ref, members, links });
      }
      return [...found.values()];
    },
    //: The source of a ref now: `{name, kind, payload, body, sig, version}`, or null when it is gone.
    async resolve(ref, cache) {
      const key = refKey(ref);
      if (cache.has(key)) return cache.get(key);
      let source = null;
      try {
        if (ref.id != null) {
          if (!cache.has("lib")) cache.set("lib", await apiJson("/board-library"));
          const row = (cache.get("lib").items || []).find((i) => i.id === ref.id);
          if (row) source = { name: row.name, kind: row.kind, payload: row.payload, version: row.version || 1 };
        } else if (typeof ref.builtin === "string") {
          const [set, entryKey] = ref.builtin.split("/");
          let data = wbLibSets.get(set);
          if (!data && set !== "icons") {
            if (!cache.has("lib")) cache.set("lib", await apiJson("/board-library"));
            const file = (cache.get("lib").shape_sets || []).find((x) => x.key === set)?.path || `${set}.json`;
            data = await (await api(`/board-library/${file}${lazyAssetStamp()}`, { silent: true })).json();
          }
          const entry = (data?.items || []).find((e) => e.key === entryKey);
          if (entry) source = { name: entry.name, kind: entry.kind || "element", payload: entry.payload };
        }
      } catch {
        source = null;
      }
      if (source) {
        const body = source.kind === "template" ? source.payload?.element : source.payload;
        source = body && Array.isArray(body.items) ? { ...source, body, sig: copies.sigOf(source.payload) } : null;
      }
      cache.set(key, source);
      return source;
    },
    //: Give a copy its source's content. The rows to save, or null when the copy no longer has the source's parts.
    apply(copy, source) {
      const parts = source.body.items || [];
      const srcSketches = parts.filter((p) => p.kind === "sketch");
      const srcObjects = parts.filter((p) => p.kind !== "sketch");
      const sketches = copy.members.filter((m) => m.kind === "sketch");
      const objects = copy.members.filter((m) => m.kind === "object");
      if (sketches.length !== srcSketches.length || objects.length !== srcObjects.length) return null;
      const ref = { ...(source.version != null ? { id: copy.ref.id, version: source.version } : { builtin: copy.ref.builtin }), ...(copy.ref.linked ? { linked: { sig: source.sig } } : {}) };
      const pen = wbLibInk();
      const inked = (value, was) => (value === "ink" ? (was && was !== "ink" ? was : pen) : value);
      const KEEP = ["locked", "comments", "layer", "name", "hidden", "page"];
      const rows = [];
      sketches.forEach(({ item }, i) => {
        const old = JSON.parse(item.data);
        const data = { ...srcSketches[i].data };
        for (const key of ["color", "fill"]) if (key in data) data[key] = inked(data[key], old[key]);
        const box = typeof old.d === "string" ? wbPathBBox(old.d) : null;
        const own = typeof data.d === "string" ? wbPathBBox(data.d) : null;
        if (box && own) {
          data.d = wbTransformPathD(data.d, { dx: box.minX - own.minX, dy: box.minY - own.minY, sx: Math.max(box.width, 1) / Math.max(own.width, 1), sy: Math.max(box.height, 1) / Math.max(own.height, 1), anchorX: own.minX, anchorY: own.minY });
        } else if (typeof old.d === "string") data.d = old.d;
        for (const key of KEEP) if (old[key] !== undefined) data[key] = old[key];
        item.data = JSON.stringify({ ...data, library_ref: ref });
        rows.push({ kind: "sketch", item });
      });
      objects.forEach(({ item }, i) => {
        const old = item.data || {};
        const data = { ...srcObjects[i].data };
        for (const key of ["color", "bg", "border_color"]) if (key in data) data[key] = inked(data[key], old[key]);
        for (const key of KEEP) if (old[key] !== undefined) data[key] = old[key];
        item.data = { ...data, library_ref: ref };
        rows.push({ kind: "object", item });
      });
      const srcLinks = source.body.links || [];
      if (copy.links.length === srcLinks.length) {
        copy.links.forEach(({ item }, i) => {
          const old = JSON.parse(item.data);
          const data = { ...srcLinks[i].data };
          if ("color" in data) data.color = inked(data.color, old.color);
          //: Where it joins and how it runs belong to the copy; its look comes from the source.
          for (const key of ["sourceId", "sourceKind", "targetId", "targetKind", "sourceAnchor", "targetAnchor", "points", "bend"]) {
            if (old[key] === undefined) delete data[key];
            else data[key] = old[key];
          }
          item.data = JSON.stringify({ ...data, library_ref: ref });
          rows.push({ kind: "sketch", item });
        });
      }
      return rows;
    },
    //: The command: update the selected copies from their source, one undo step.
    async update() {
      const found = copies.collect(copies.selectionRows());
      if (!found.length) {
        toast("Select something placed from the library first.", "info");
        return false;
      }
      const cache = new Map();
      let done = 0;
      let gone = 0;
      let differs = 0;
      let name = "";
      await wbRecordGesture(async () => {
        const rows = [];
        for (const copy of found) {
          const source = await copies.resolve(copy.ref, cache);
          if (!source) {
            gone += 1;
            continue;
          }
          const got = copies.apply(copy, source);
          if (!got) {
            differs += 1;
            continue;
          }
          rows.push(...got);
          done += 1;
          name = source.name;
        }
        if (rows.length) await wbSaveMany(rows);
      });
      wbScheduleRender();
      const note = gone ? " The library item behind the rest is gone, so they stay as they are." : differs ? " The rest no longer have the parts of their library item, so they were left alone." : "";
      if (done) {
        const said = `Updated ${done === 1 ? name : `${done} copies`} from the library.${note}`;
        toast(said);
        wbAnnounce(said);
      } else {
        toast(gone ? "The library item this copy came from is gone. The copy stays as it is." : "This copy no longer has the parts of its library item, so it was left alone. Place it again to get the new one.", "info");
      }
      return done > 0;
    },
    //: Linked copies whose source changed are updated, without an undo step of their own. Returns how many.
    async refresh() {
      if (!wbState || wbIsMap()) return 0;
      const boardId = window.currentBoardId;
      const seed = copies.boardRows().filter((r) => !isLinkRow(r.kind, r.item) && refOf(r.kind, r.item)?.linked);
      if (!seed.length) return 0;
      const cache = new Map();
      const rows = [];
      let n = 0;
      for (const copy of copies.collect(seed)) {
        if (!copy.ref.linked) continue;
        const source = await copies.resolve(copy.ref, cache);
        if (!source || source.sig === copy.ref.linked.sig) continue;
        const got = copies.apply(copy, source);
        if (got) {
          rows.push(...got);
          n += 1;
        }
      }
      if (!rows.length || window.currentBoardId !== boardId) return 0;
      await wbSaveMany(rows);
      wbScheduleRender();
      toast(`Updated ${n === 1 ? "1 linked copy" : `${n} linked copies`} from the library.`);
      return n;
    },
    //: Mark what a placement made as linked to its source (`made` is the place route's answer).
    async mark(made, entry) {
      const linked = { sig: copies.sigOf(entry.payload) };
      const rows = [];
      for (const item of made.sketches) {
        if (isLinkRow("sketch", item)) continue;
        const data = JSON.parse(item.data);
        if (!data.library_ref) continue;
        item.data = JSON.stringify({ ...data, library_ref: { ...data.library_ref, linked } });
        rows.push({ kind: "sketch", item });
      }
      for (const item of made.objects) {
        if (!item.data?.library_ref) continue;
        item.data = { ...item.data, library_ref: { ...item.data.library_ref, linked } };
        rows.push({ kind: "object", item });
      }
      if (rows.length) await wbSaveMany(rows);
    },
    //: Take the selected copies off their link; they stay as they are, still remembering the item they came from.
    async unlink() {
      const found = copies.collect(copies.selectionRows()).filter((c) => c.ref.linked);
      if (!found.length) {
        toast("Select a linked copy first.", "info");
        return false;
      }
      await wbRecordGesture(async () => {
        const rows = [];
        for (const copy of found) {
          for (const { kind, item } of [...copy.members, ...copy.links]) {
            const strip = (ref) => {
              const { linked, ...rest } = ref;
              return rest;
            };
            if (kind === "object") item.data = { ...item.data, library_ref: strip(item.data.library_ref) };
            else item.data = JSON.stringify({ ...JSON.parse(item.data), library_ref: strip(refOf("sketch", item)) });
            rows.push({ kind, item });
          }
        }
        await wbSaveMany(rows);
      });
      wbAnnounce("Unlinked from the library.");
      toast("Unlinked. The copy stays as it is.");
      return true;
    },
  };

  wbFmtState.libraryMore = {
    replacement, replaceData, rankEntries, wordForms, sets: librarySets, splitPorts, splitData, splitLink, copies, startEntries, replaceWith, open: openPicker, close, gripPress,
    dragged: () => state.dragged,
  };
})();
