(() => {
  // whiteboard-structure-more.js: the board's structure rows (WHITEBOARD_PLAN section 12, draw.io's tags, collapse and
  // container drop target): tags on shapes, objects and connectors with a filter that dims the untagged rest; a frame
  // that folds to its title bar; the drop highlight a frame wears while an item is dragged over it; and the find
  // bar's "This frame" scope. Everything is held on `wbFmtState.structure`, so no new global name is added.

  // --- Tags ------------------------------------------------------------------------------------------------
  //: `data.tags` (an object's data, a shape's or connector's own JSON), at most 20 words of 40 characters, the bounds
  //: wb_model.py checks. The filter is a mode of the find bar kept in memory: closing the bar shows everything again.
  const MAX_TAGS = 20;
  const MAX_TAG = 40;
  const KINDS = ["node", "object", "sketch"];
  const state = { tag: "", painted: false, scope: null, scopeKeys: null, dropEl: null, down: null };

  const dataOf = (kind, item) => (kind === "sketch" ? wbSketchData(item) : kind === "object" ? item.data : null);
  const tagsOf = (kind, item) => {
    const list = dataOf(kind, item)?.tags;
    return Array.isArray(list) ? list.filter((t) => typeof t === "string" && t) : [];
  };

  //: Words as typed ("a, b  c" is two: a comma parts them), one space inside a tag, no repeats (case aside).
  function parseTags(text) {
    const seen = new Set();
    const out = [];
    for (const raw of String(text ?? "").split(/[,;\n]/)) {
      const word = raw.replace(/\s+/g, " ").trim().slice(0, MAX_TAG);
      if (!word || seen.has(word.toLowerCase())) continue;
      seen.add(word.toLowerCase());
      out.push(word);
    }
    return out.slice(0, MAX_TAGS);
  }

  //: Tags the whole selection can take: a card is a note (its tags are the note's own), so only shapes, connectors and objects.
  const taggable = () => wbFmtEntries().filter((e) => e.kind !== "node" && !wbIsLocked(e.kind, e.item));
  const unionOf = (entries) => {
    const seen = new Map();
    for (const e of entries) for (const t of tagsOf(e.kind, e.item)) if (!seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), t);
    return [...seen.values()];
  };

  //: One Undo step: `add` joins every selected item's tags, `drop` leaves them, `replace` sets them whole.
  function editTags({ add = [], drop = [], replace = null }) {
    const gone = new Set(drop.map((t) => t.toLowerCase()));
    return wbFmtApply("tags", (entry) => {
      if (entry.kind === "node") return null;
      const base = replace ? [] : tagsOf(entry.kind, entry.item).filter((t) => !gone.has(t.toLowerCase()));
      const next = parseTags([...base, ...(replace || []), ...add].join(","));
      return { tags: next.length ? next : undefined };
    }, "Tags saved.");
  }

  //: The Format panel's Data tab row: one chip per tag in the selection (a press removes it), and a field that adds.
  function syncTags(entries) {
    const row = document.getElementById("wb-fmt-tags");
    if (!row || row.contains(document.activeElement)) return;
    const mine = entries.filter((e) => e.kind !== "node");
    row.replaceChildren(...unionOf(mine).map((tag) => {
      const c = chip(tag, "tag wb-tag-chip", () => editTags({ drop: [tag] }));
      c.title = `Remove the tag ${tag}`;
      c.setAttribute("aria-label", `Remove the tag ${tag}`);
      return c;
    }));
  }

  function addFromField(input) {
    const words = parseTags(input.value);
    input.value = "";
    if (words.length) editTags({ add: words });
  }

  //: Tags in use on the board, with how many items hold each, most used first.
  function tagCounts() {
    const counts = new Map();
    for (const kind of KINDS) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        for (const t of tagsOf(kind, item)) {
          const key = t.toLowerCase();
          counts.set(key, { tag: counts.get(key)?.tag || t, n: (counts.get(key)?.n || 0) + 1 });
        }
      }
    }
    return [...counts.values()].sort((a, b) => b.n - a.n || a.tag.localeCompare(b.tag));
  }

  const carries = (kind, item) => tagsOf(kind, item).some((t) => t.toLowerCase() === state.tag.toLowerCase());

  //: After every render: untagged items stand back (`.wb-tag-dim`), tagged ones are as they were.
  function paintTags() {
    if (!state.tag && !state.painted) return;
    document.getElementById("library-view-whiteboard")?.classList.toggle("wb-tag-filtering", Boolean(state.tag));
    for (const kind of KINDS) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        document.querySelector(WB_SELECTOR_BY_KIND[kind](item.id))?.classList.toggle("wb-tag-dim", Boolean(state.tag) && !carries(kind, item));
      }
    }
    state.painted = Boolean(state.tag);
  }

  function setFilter(tag) {
    state.tag = String(tag || "");
    paintTags();
    const select = document.getElementById("wb-search-tag");
    if (select && select.value !== state.tag) select.value = state.tag;
    if (!state.tag) return wbAnnounce("Tag filter cleared.");
    const n = tagCounts().find((c) => c.tag.toLowerCase() === state.tag.toLowerCase())?.n || 0;
    wbAnnounce(`Showing ${nounCount(n, "item")} tagged ${state.tag}. The rest is dimmed.`);
  }

  function fillTagSelect(select) {
    const counts = tagCounts();
    const keep = state.tag;
    const none = new Option("Any tag", "");
    select.replaceChildren(none, ...counts.map((c) => new Option(`${c.tag} (${c.n})`, c.tag)));
    //: A filter on a tag nothing holds any more is dropped rather than kept on nothing.
    if (keep && !counts.some((c) => c.tag.toLowerCase() === keep.toLowerCase())) setFilter("");
    select.value = state.tag;
  }

  // --- Collapse a frame ------------------------------------------------------------------------------------
  //: A folded frame keeps its full height in `data.fold_h` and takes the bar's height; what lay wholly inside that full box
  //: (the rule a drag of the frame uses) is out of sight, and a connector with an end in it with them. Nothing else is saved.
  //: Folded means `collapsed` (the flag a map branch uses too) with the height it held in `fold_h`.
  const isFolded = (f) => Boolean(f?.data?.collapsed && f.data.fold_h);
  const BAR = 40;
  const BAR_PANEL = 72;
  let boxCache = null;

  //: The full boxes of the folded frames, read once per tick (a loop over every item asks for each).
  function foldBoxes() {
    if (boxCache) return boxCache;
    boxCache = (wbState?.objects || []).filter((o) => o.kind === "frame" && isFolded(o)).map((f) => ({
      id: f.id, minX: f.x, minY: f.y, maxX: f.x + f.width, maxY: f.y + f.data.fold_h,
    }));
    queueMicrotask(() => { boxCache = null; });
    return boxCache;
  }

  //: Whether a folded frame hides the item (`wbItemHidden`'s extra rule, so export, present, Select all and find all skip it).
  function folded(kind, item) {
    const boxes = foldBoxes();
    if (!boxes.length || !item) return false;
    const box = wbItemBBox(kind, item);
    if (!box) return false;
    return boxes.some((f) => !(kind === "object" && item.id === f.id)
      && box.minX >= f.minX && box.minY >= f.minY && box.maxX <= f.maxX && box.maxY <= f.maxY);
  }

  const heldBy = (frame) => {
    let n = 0;
    for (const key of wbFrameContents(frame, { withLocked: true })) {
      const sep = key.indexOf(":");
      const item = wbFindItem(key.slice(0, sep), Number(key.slice(sep + 1)));
      if (item && !(key.startsWith("sketch:") && wbIsLinkSketch(item))) n += 1;
    }
    return n;
  };

  async function setFolded(frame, on) {
    if (!frame || frame.kind !== "frame" || wbIsLocked("object", frame) || on === isFolded(frame)) return false;
    await wbRecordGesture(async () => {
      if (on) {
        const bar = frame.data?.tint ? BAR_PANEL : BAR;
        frame.data = { ...frame.data, collapsed: true, fold_h: Math.max(20, Math.round(frame.height)) };
        frame.height = Math.min(frame.height, bar);
      } else {
        frame.height = frame.data.fold_h;
        const { collapsed, fold_h, ...rest } = frame.data;
        frame.data = rest;
      }
      boxCache = null;
      await wbSaveObject(frame);
    });
    boxCache = null;
    //: Whatever the fold hid cannot stay selected; the frame itself is the selection.
    selectWbItem("object", frame.id);
    wbScheduleRender();
    wbAnnounce(on ? `Frame folded. ${nounCount(heldBy(frame), "item")} hidden inside.` : "Frame expanded.");
    wbFormatSyncSoon();
    return true;
  }

  const selectedFrame = () => {
    const entries = wbFmtEntries();
    return entries.length === 1 && entries[0].kind === "object" && entries[0].item.kind === "frame" ? entries[0].item : null;
  };

  function paintFolds() {
    for (const f of wbState?.objects || []) {
      if (f.kind !== "frame") continue;
      const el = document.querySelector(WB_SELECTOR_BY_KIND.object(f.id));
      if (!el) continue;
      const on = isFolded(f);
      el.classList.toggle("wb-frame-collapsed", on);
      if (on) el.dataset.folded = nounCount(heldBy(f), "item");
      else delete el.dataset.folded;
    }
  }

  // --- The drop highlight ----------------------------------------------------------------------------------
  //: While an item is carried (`wbGesture.move`, the drag-to-delete target's own signal) the smallest frame under the pointer
  //: wears `.wb-drop-target`; the frame being carried never does. Gone on release.
  function clearDrop() {
    state.dropEl?.classList.remove("wb-drop-target");
    state.dropEl = null;
  }

  function frameUnder(x, y, skip) {
    let best = null;
    for (const f of wbState?.objects || []) {
      if (f.kind !== "frame" || skip.has(f.id) || wbItemHidden("object", f)) continue;
      if (x < f.x || y < f.y || x > f.x + f.width || y > f.y + f.height) continue;
      if (!best || f.width * f.height < best.width * best.height) best = f;
    }
    return best;
  }

  function onDragMove(event) {
    const g = typeof wbGesture !== "undefined" ? wbGesture : null;
    if (!g || !g.move || g.cancelled || !state.down) return clearDrop();
    if (Math.hypot(event.clientX - state.down.x, event.clientY - state.down.y) < 6) return;
    const [x, y] = wbClientToBoard(event.clientX, event.clientY);
    const skip = new Set(state.down.frames);
    for (const key of wbMultiSelection) if (key.startsWith("object:")) skip.add(Number(key.slice(7)));
    const frame = frameUnder(x, y, skip);
    const el = frame ? document.querySelector(WB_SELECTOR_BY_KIND.object(frame.id)) : null;
    if (el === state.dropEl) return;
    clearDrop();
    if (el) {
      el.classList.add("wb-drop-target");
      state.dropEl = el;
    }
  }

  window.addEventListener("pointerdown", (event) => {
    const grabbed = event.target?.closest?.(".wb-object-frame[data-id]");
    state.down = { x: event.clientX, y: event.clientY, frames: grabbed ? [Number(grabbed.dataset.id)] : [] };
  }, true);
  window.addEventListener("pointermove", onDragMove, true);
  window.addEventListener("pointerup", () => { clearDrop(); state.down = null; }, true);
  window.addEventListener("pointercancel", () => { clearDrop(); state.down = null; }, true);

  // --- Find in this frame ----------------------------------------------------------------------------------
  //: With the scope on, matches and Replace all are limited to the frame that held the selection (or, with none, the view's
  //: centre) when the switch was pressed, and what lies wholly inside it. Pinned then, not followed: a match that is selected
  //: or centred on must not move the scope.
  const frameAtBox = (box) => {
    let best = null;
    for (const f of wbState?.objects || []) {
      if (f.kind !== "frame" || wbItemHidden("object", f)) continue;
      const full = f.y + (isFolded(f) ? f.data.fold_h : f.height);
      if (box.minX < f.x || box.minY < f.y || box.maxX > f.x + f.width || box.maxY > full) continue;
      if (!best || f.width * f.height < best.width * best.height) best = f;
    }
    return best;
  };

  function scopeFrame() {
    const entries = wbFmtEntries();
    const own = selectedFrame();
    if (own) return own;
    const box = wbFmtBox(entries);
    if (box) return frameAtBox(box);
    const container = document.getElementById("whiteboard-container");
    if (!container) return null;
    const r = container.getBoundingClientRect();
    const [x, y] = wbClientToBoard(r.left + r.width / 2, r.top + r.height / 2);
    return frameAtBox({ minX: x, minY: y, maxX: x, maxY: y });
  }

  //: The predicate a search pass asks for once: null when the scope is off, else whether an item is inside the pinned frame.
  function scope() {
    if (!state.scope) return null;
    const frame = (wbState?.objects || []).find((o) => o.id === state.scope && o.kind === "frame");
    if (!frame) {
      setScope(false);
      return null;
    }
    const keys = new Set(wbFrameContents(frame, { withLocked: true }));
    keys.add(wbMultiKey("object", frame.id));
    return (kind, item) => keys.has(wbMultiKey(kind, item.id));
  }

  function setScope(on) {
    const button = document.getElementById("wb-search-frame");
    if (on) {
      const frame = scopeFrame();
      if (!frame) {
        toast("Select a frame, or centre one in view, to search just that frame.", "info");
        on = false;
      } else {
        state.scope = frame.id;
        if (button) button.title = `Searching only inside ${wbFrameTitle(frame)}`;
      }
    }
    if (!on) {
      state.scope = null;
      if (button) button.title = "Search this frame only";
    }
    button?.setAttribute("aria-pressed", String(Boolean(state.scope)));
    wbBoardSearchRun(document.getElementById("wb-search-input")?.value || "");
    return Boolean(state.scope);
  }

  //: Built with the find bar's other options (`wbEnsureSearchOptions`): the scope switch and the tag filter.
  function searchControls(bar) {
    if (document.getElementById("wb-search-frame")) return;
    const after = document.getElementById("wb-search-regex") || document.getElementById("wb-search-input");
    const button = smallButton("ph:frame-corners", "Search this frame only", () => setScope(!state.scope));
    button.id = "wb-search-frame";
    button.setAttribute("aria-pressed", "false");
    const select = document.createElement("select");
    select.id = "wb-search-tag";
    select.className = "wb-search-tag";
    select.setAttribute("aria-label", "Show only items with this tag");
    select.title = "Show only items with this tag; the rest is dimmed";
    fillTagSelect(select);
    select.addEventListener("focus", () => fillTagSelect(select));
    select.addEventListener("mousedown", () => fillTagSelect(select));
    select.addEventListener("change", () => setFilter(select.value));
    after?.after(button, select);
    bar.dataset.structure = "1";
  }

  //: The bar closes: the scope and the dimming go with it.
  function closeSearch() {
    if (state.scope) {
      state.scope = null;
      document.getElementById("wb-search-frame")?.setAttribute("aria-pressed", "false");
    }
    if (state.tag) setFilter("");
  }

  //: Ctrl+K "Filter by tag": the find bar, on its tag list.
  function openFilter() {
    wbOpenBoardSearch();
    const select = document.getElementById("wb-search-tag");
    if (!select) return;
    fillTagSelect(select);
    select.focus();
  }

  async function editSelected() {
    const entries = taggable();
    if (!entries.length) return toast("Select a shape, a connector or an object to tag.", "info");
    const answer = await promptDialog("Tags (separate with commas)", unionOf(entries).join(", "), { confirmLabel: "Save" });
    if (answer == null) return;
    await editTags({ replace: parseTags(answer) });
  }

  // --- The panel -------------------------------------------------------------------------------------------
  //: The Data tab's tag row and the frame's Collapsed box; joined to the Format panel's field lists, which the panel reads.
  for (const list of Object.values(WB_FMT_FIELDS)) if (list.includes("props") && !list.includes("tags")) list.push("tags");
  WB_FMT_FIELDS.frame.push("collapse");

  function sync(entries) {
    syncTags(entries);
    const box = document.getElementById("wb-fmt-collapse");
    const frame = selectedFrame();
    if (box && frame) box.checked = isFolded(frame);
  }

  //: Delegated from the document: the panel's markup is moved when the board opens, so a listener on the element could be lost.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target?.id === "wb-fmt-tag-input") {
      e.preventDefault();
      addFromField(e.target);
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target?.id === "wb-fmt-tag-input") addFromField(e.target);
    else if (e.target?.id === "wb-fmt-collapse") {
      const frame = selectedFrame();
      if (frame) setFolded(frame, e.target.checked);
    }
  });

  //: After every render (whiteboard.js, beside the group paint).
  function paint() {
    boxCache = null;
    paintFolds();
    paintTags();
  }

  wbFmtState.structure = {
    parseTags, tagsOf, editTags, editSelected, taggable: () => taggable().length > 0, filter: setFilter, openFilter, tagCounts,
    folded, setFolded, selectedFrame, foldBoxes: () => foldBoxes().length, isFolded, paint, sync, scope, setScope, searchControls, closeSearch,
    inFrame: () => Boolean(scopeFrame()),
  };
})();
