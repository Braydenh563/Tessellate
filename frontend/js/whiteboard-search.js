(() => {
  // whiteboard-search.js: the find-a-card bar.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  // --- Find a card on this board ---------------------------------------------

  //: `word` and `regex` are the find bar's two options; they outlive a close.
  const wbBoardSearch = { query: "", matches: [], index: -1, word: false, regex: false, error: "", late: 0 };

  /**
   * Every searchable string an item carries, lowercased.
   *
   * `byId` is built once per search run rather than per item, `allEntries` is
   * the whole notebook, and re-Mapping it for each of a board's cards on every
   * keystroke is the kind of quiet quadratic that only shows up on someone
   * else's larger notebook.
   *
   * **Not `entriesById`.** That map is a `const` *inside* `renderWhiteboard`,
   * so it does not exist out here, a first cut guarded with
   * `typeof entriesById !== "undefined"`, which meant the guard silently
   * returned "" and the search matched nothing at all while looking like it
   * worked. Caught by driving it in a browser, not by reading it.
   */
  function wbSearchTextFor(kind, item, byId) {
    if (kind === "node") {
      const entry = byId ? byId.get(String(item.entry_id)) : null;
      if (entry) return ((entry.content || entry.preview) || "").toLowerCase();
      // The note is not in the in-memory list (created since the last
      // `loadEntries()`), but its card is on screen with its text in it, so
      // read what the person can actually see rather than reporting no match
      // for a card they are looking straight at.
      const el = document.querySelector(`.node-card[data-id="${item.id}"] .wb-card-content`);
      return (el?.textContent || "").toLowerCase();
    }
    if (kind === "object") {
      // A text box keeps its words in the same `data` JSON blob an image keeps
      // its URL in (see WhiteboardObject's own docstring), so a bad parse here
      // means "not searchable", never a thrown render.
      //: `data` arrives parsed (`_object_to_out`); a string is read too. It
      //: was only ever parsed, so `JSON.parse` of an object threw and no text
      //: box was ever found (measured, canvasdepth: "SHIP" in a text box, 0).
      try {
        const data = typeof item.data === "string" ? JSON.parse(item.data || "{}") : item.data || {};
        //: A map topic's note (`data.note`, the text behind the topic) is searched too (MINDMAP gap 13, OPEN F3);.
        const note = typeof data.note === "string" ? `\n${data.note}` : "";
        return `${data.content || ""}${wbCellsText(data.cells)}${wbPropsText(data.props)}${note}`.toLowerCase();
      } catch {
        return "";
      }
    }
    //: A shape's or a connector's label (canvasdepth): what draw.io's find
    //: reads first, and what this one missed.
    if (kind === "sketch") {
      const data = wbSketchData(item);
      return `${data?.label || ""}${data?.label2 ? `\n${data.label2}` : ""}${wbPropsText(data?.props)}`.toLowerCase();
    }
    return "";
  }

  //: A table's words are its cells: Find reads them too (a table of "zebra" was
  //: "0 matches" on a board that showed it), and Replace all rewrites them.
  function wbCellsText(cells) {
    if (!Array.isArray(cells)) return "";
    return cells.flat().map((cell) => `\n${cell ?? ""}`).join("");
  }

  function wbReplaceInCells(cells, find, to, opts = {}) {
    if (!Array.isArray(cells)) return { cells, count: 0 };
    let count = 0;
    const out = cells.map((row) => (Array.isArray(row) ? row : []).map((cell) => {
      if (typeof cell !== "string") return cell;
      const done = wbReplaceText(cell, find, to, opts);
      count += done.count;
      return done.text;
    }));
    return { cells: out, count };
  }

  //: Find reads an item's data values too (draw.io's find reads its metadata).
  //: Names are not searched, only what a person typed as a value.
  function wbPropsText(props) {
    if (!props || typeof props !== "object") return "";
    return Object.values(props).map((v) => `\n${v}`).join("");
  }

  //: Pure (node-tested): the one pattern find and replace share. Literal text
  //: is escaped, so "a.b" is three characters; `regex` takes the query as a
  //: pattern; `word` demands a non-word character (or an edge) on each side,
  //: which is a lookaround rather than `\b` so "c++" can still be a word.
  //: Case never matters and `^`/`$` work per line. A pattern that can match
  //: empty text would match everywhere, so it is refused with the others.
  function wbSearchPattern(query, { word = false, regex = false } = {}) {
    const q = String(query ?? "");
    if (!q.trim()) return { re: null, has: () => false, error: "" };
    let source = regex ? q : q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (word) source = `(?<!\\w)(?:${source})(?!\\w)`;
    let re = null;
    try {
      re = new RegExp(source, "gim");
    } catch {
      return { re: null, has: () => false, error: "Not a valid pattern" };
    }
    if (re.test("")) return { re: null, has: () => false, error: "This pattern matches empty text" };
    return {
      re,
      // A global pattern remembers where it stopped; every test starts over.
      has: (text) => {
        re.lastIndex = 0;
        return re.test(text);
      },
      error: "",
    };
  }

  //: Pure (node-tested): every match of `find` in `text` swapped for `to`.
  //: Literal mode takes `to` as typed; a pattern takes `$1`, `$&` and `$$`.
  function wbReplaceText(text, find, to, opts = {}) {
    const source = String(text ?? "");
    const { re } = wbSearchPattern(find, opts);
    if (!re) return { text: source, count: 0 };
    let count = 0;
    const out = source.replace(re, (...args) => {
      const hit = args[0];
      if (!hit) return hit;
      count += 1;
      if (!opts.regex) return to;
      const caught = args.slice(1, args.findIndex((a, i) => i > 0 && typeof a === "number"));
      return String(to).replace(/\$(\d{1,2}|&|\$)/g, (_, k) => (k === "$" ? "$" : k === "&" ? hit : caught[Number(k) - 1] ?? ""));
    });
    return { text: out, count };
  }

  //: Pure (node-tested): the replacement applied to each data value of an
  //: item, names untouched (as `wbPropsText` reads only values).
  function wbReplaceInProps(props, find, to, opts = {}) {
    if (!props || typeof props !== "object") return { props, count: 0 };
    let count = 0;
    const out = {};
    for (const [name, value] of Object.entries(props)) {
      const done = wbReplaceText(String(value), find, to, opts);
      count += done.count;
      out[name] = done.count ? done.text : value;
    }
    return { props: out, count };
  }

  //: A Replace all hit written into its item in memory (the caller saves the lot).
  function wbReplaceWrite(kind, item, { text, values, grid, note, second }) {
    const props = values.count ? { props: values.props } : {};
    const noted = note?.count ? { note: note.text } : {};
    if (kind === "object") item.data = { ...item.data, content: text.text, ...props, ...noted, ...(grid.count ? { cells: grid.cells } : {}) };
    else wbSketchSetProps(item, { label: text.text, ...props, ...(second?.count ? { label2: second.text } : {}) });
  }

  //: **Replace all** (canvasdepth; WHITEBOARD_PLAN section 9): text boxes,
  //: shape labels and connector labels, one undo step. A card is a note and
  //: keeps its words; the announcement says how many cards hold the words.
  async function wbBoardReplaceAll(find, to, only = null) {
    const needle = String(find || "").trim() ? String(find) : "";
    if (!needle) return 0;
    const pattern = wbSearchPattern(needle, wbBoardSearch);
    if (!pattern.re) {
      toast(pattern.error, "info");
      return 0;
    }
    const undo = [];
    const rows = [];
    let changes = 0, cards = 0;
    const inScope = wbFmtState.structure?.scope() || (() => true);
    for (const kind of ["object", "sketch", "node"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
        if (wbItemHidden(kind, item) || wbIsLocked(kind, item) || !inScope(kind, item)) continue;
        //: Replace (one) is the same pass over the item the find bar is on.
        if (only && (only.kind !== kind || only.id !== item.id)) continue;
        if (kind === "node") {
          if (pattern.has(wbSearchTextFor("node", item, null))) cards += 1;
          continue;
        }
        const own = kind === "object" ? item.data : wbSketchData(item);
        const field = kind === "object" ? own?.content : own?.label;
        //: Find reads the data values too (`wbPropsText`), so Replace all must
        //: rewrite them, or the count says 3 of 3 and the toast says 1.
        const text = typeof field === "string" ? wbReplaceText(field, needle, to, wbBoardSearch) : { text: field, count: 0 };
        const values = wbReplaceInProps(own?.props, needle, to, wbBoardSearch);
        const grid = kind === "object" ? wbReplaceInCells(own?.cells, needle, to, wbBoardSearch) : { cells: undefined, count: 0 };
        //: A map topic's note (`data.note`) is searched, so it is rewritten too (undo already holds the whole payload).
        const note = kind === "object" && typeof own?.note === "string" ? wbReplaceText(own.note, needle, to, wbBoardSearch) : { text: "", count: 0 };
        //: A connector's second label (`label2`) is searched, so it is rewritten too.
        const second = kind === "sketch" && typeof own?.label2 === "string" ? wbReplaceText(own.label2, needle, to, wbBoardSearch) : { text: "", count: 0 };
        const done = { count: text.count + values.count + grid.count + note.count + second.count };
        if (!done.count) continue;
        undo.push({ action: "move", kind, id: item.id, before: WB_KIND_INFO[kind].payload(item) });
        wbReplaceWrite(kind, item, { text, values, grid, note, second });
        rows.push({ kind, item });
        changes += done.count;
      }
    }
    await wbCommitMoves(rows, undo);
    wbScheduleRender();
    const said = `Replaced ${nounCount(changes, "time")} in ${nounCount(undo.length, "item")}`
      + `${cards ? `; ${nounCount(cards, "card")} hold it too, edited in their note` : ""}.`;
    wbAnnounce(said);
    toast(said);
    wbBoardSearchRun(document.getElementById("wb-search-input")?.value || "");
    return changes;
  }

  //: **Replace** (`wbBoardSearch.replaceOne`, a method so it adds no global name; the one the find bar is on, draw.io's Replace beside Replace all): the first press goes to the first
  //: match, the next ones replace in the match the bar is on and move to the next. A card keeps its words.
  wbBoardSearch.replaceOne = async (find, to) => {
    if (wbBoardSearch.index < 0) {
      wbBoardSearchGo(1);
      return 0;
    }
    const match = wbBoardSearch.matches[wbBoardSearch.index];
    if (!match) return 0;
    const at = wbBoardSearch.index;
    const changes = await wbBoardReplaceAll(find, to, match);
    //: A replaced item usually stops matching, so the next one is at the same place; one that still matches (a card,
    //: or words that hold the needle) is stepped past.
    const total = wbBoardSearch.matches.length;
    if (total) {
      const still = wbBoardSearch.matches.findIndex((m) => m.kind === match.kind && m.id === match.id);
      wbBoardSearch.index = ((still >= 0 ? still + 1 : at) % total) - 1;
      wbBoardSearchGo(1);
    }
    return changes;
  };

  function wbBoardSearchRun(query) {
    wbBoardSearch.query = query;
    wbBoardSearch.matches = [];
    wbBoardSearch.index = -1;
    const pattern = wbSearchPattern(wbBoardSearch.regex ? query : query.trim(), wbBoardSearch);
    wbBoardSearch.error = pattern.error;
    if (pattern.re) {
      const byId = new Map(
        (typeof allEntries !== "undefined" && Array.isArray(allEntries) ? allEntries : []).map((e) => [
          String(e.id),
          e,
        ]),
      );
      //: "This frame" limits the pass to what the pinned frame holds (whiteboard-structure-more.js); null is the whole board.
      const inScope = wbFmtState.structure?.scope() || (() => true);
      for (const kind of ["node", "object", "sketch"]) {
        for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) {
          if (!wbItemHidden(kind, item) && inScope(kind, item) && pattern.has(wbSearchTextFor(kind, item, byId))) {
            wbBoardSearch.matches.push({ kind, id: item.id });
          }
        }
      }
      // Reading order, so pressing Enter walks the board top-to-bottom rather
      // than in whatever order the two lists happened to load.
      wbBoardSearch.matches.sort((a, b) => {
        const ba = wbItemBBox(a.kind, wbSearchItem(a));
        const bb = wbItemBBox(b.kind, wbSearchItem(b));
        if (!ba || !bb) return 0;
        return ba.minY - bb.minY || ba.minX - bb.minX;
      });
    }
    wbApplySearchHighlight();
    wbUpdateSearchCount();
    if (wbBoardSearch.matches.length) wbBoardSearchGo(0);
  }

  function wbSearchItem(match) {
    return (wbState[WB_LIST_BY_KIND[match.kind]] || []).find((i) => i.id === match.id) || null;
  }

  function wbApplySearchHighlight() {
    //: No search and nothing marked: every render called this and walked every
    //: object to toggle two classes off that were never on (about 7 ms of the
    //: 108 ms Tab-to-editable at 390, 6x, 41 topics; L-mindmap-13).
    if (!wbBoardSearch.matches.length && !document.querySelector(".wb-search-hit, .wb-search-current")) return;
    const wanted = new Set(wbBoardSearch.matches.map((m) => wbMultiKey(m.kind, m.id)));
    const current = wbBoardSearch.index >= 0 ? wbBoardSearch.matches[wbBoardSearch.index] : null;
    const currentKey = current ? wbMultiKey(current.kind, current.id) : null;
    for (const el of document.querySelectorAll("#wb-html-layer [data-id], #wb-zoom-group [data-id]")) {
      const kind = el.classList.contains("node-card")
        ? "node"
        : el.classList.contains("wb-object")
        ? "object"
        : null;
      if (!kind) continue;
      const key = wbMultiKey(kind, Number(el.dataset.id));
      el.classList.toggle("wb-search-hit", wanted.has(key));
      el.classList.toggle("wb-search-current", key === currentKey);
    }
  }

  function wbUpdateSearchCount() {
    const el = document.getElementById("wb-search-count");
    if (!el) return;
    const total = wbBoardSearch.matches.length;
    clearTimeout(wbBoardSearch.late);
    if (!wbBoardSearch.query.trim()) {
      el.textContent = "";
      return;
    }
    //: A pattern half-typed is not wrong yet: its error waits for a pause (INBOX 1579).
    if (!total && wbBoardSearch.error) {
      el.textContent = "";
      wbBoardSearch.late = setTimeout(() => (el.textContent = wbBoardSearch.error), 800);
      return;
    }
    // "3 of 12", not a bare number, a screen reader reading this aria-live
    // region needs to know which of how many, and so does everyone else.
    el.textContent = total ? `${wbBoardSearch.index + 1} of ${total}` : wbBoardSearch.error || "No matches";
  }

  /** Step through the matches, wrapping at both ends. */
  function wbBoardSearchGo(delta) {
    const total = wbBoardSearch.matches.length;
    if (!total) return;
    const next = wbBoardSearch.index < 0 ? 0 : (wbBoardSearch.index + delta + total) % total;
    wbBoardSearch.index = next;
    const match = wbBoardSearch.matches[next];
    const item = wbSearchItem(match);
    const box = item ? wbItemBBox(match.kind, item) : null;
    if (box) wbCenterOn(box);
    //: A drawing has no element to ring, so a matched shape or connector is
    //: selected instead, which draws its handles.
    if (match.kind === "sketch" && item) {
      clearWbSelection();
      wbSelectedItem = { kind: "sketch", id: item.id };
      wbApplySelectionHighlight();
    }
    wbApplySearchHighlight();
    wbUpdateSearchCount();
  }

  function wbCloseBoardSearch() {
    const bar = document.getElementById("wb-search-bar");
    if (!bar) return;
    bar.classList.add("hidden");
    wbFmtState.structure?.closeSearch();
    wbBoardSearch.query = "";
    wbBoardSearch.matches = [];
    wbBoardSearch.index = -1;
    wbApplySearchHighlight();
    document.getElementById("whiteboard-container")?.focus?.();
  }

  //: The Replace row, built on first use so the boot page carries none of it:
  //: a toggle after the find field, and under it a field and Replace all.
  function wbEnsureReplaceRow(bar) {
    if (document.getElementById("wb-replace-toggle")) return;
    const toggle = smallButton("ph:swap", "Replace (Ctrl+H)", () => wbToggleReplace());
    toggle.id = "wb-replace-toggle";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "wb-replace-row");
    document.getElementById("wb-search-count")?.before(toggle);
    const row = document.createElement("div");
    row.id = "wb-replace-row";
    row.className = "wb-replace-row";
    row.hidden = true;
    const field = document.createElement("input");
    field.id = "wb-replace-input";
    field.type = "text";
    field.placeholder = "Replace with";
    field.setAttribute("aria-label", "Replace with");
    field.autocomplete = "off";
    field.spellcheck = false;
    const all = document.createElement("button");
    all.type = "button";
    all.id = "wb-replace-all";
    all.className = "small";
    all.textContent = "Replace all";
    const query = () => document.getElementById("wb-search-input")?.value || "";
    const go = () => wbBoardReplaceAll(query(), field.value);
    all.addEventListener("click", go);
    const one = document.createElement("button");
    one.type = "button";
    one.id = "wb-replace-one";
    one.className = "small";
    one.textContent = "Replace";
    one.title = "Replace in the match the bar is on, then go to the next";
    one.addEventListener("click", () => wbBoardSearch.replaceOne(query(), field.value));
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        go();
      } else if (event.key === "Escape") {
        event.preventDefault();
        wbCloseBoardSearch();
      }
    });
    row.append(field, one, all);
    bar.append(row);
  }

  //: Whole word and Pattern, two pressed-state toggles after the find field,
  //: built on first use like the Replace row. Changing one searches again.
  function wbEnsureSearchOptions(bar) {
    if (document.getElementById("wb-search-word")) return;
    const input = document.getElementById("wb-search-input");
    const make = (id, icon, title, option) => {
      const button = smallButton(icon, title, () => {
        wbBoardSearch[option] = !wbBoardSearch[option];
        button.setAttribute("aria-pressed", String(wbBoardSearch[option]));
        wbBoardSearchRun(input?.value || "");
      });
      button.id = id;
      button.setAttribute("aria-pressed", String(wbBoardSearch[option]));
      return button;
    };
    const word = make("wb-search-word", "ph:text-a-underline", "Whole word", "word");
    const pattern = make("wb-search-regex", "ph:brackets-curly", "Pattern (a regular expression)", "regex");
    input?.after(word, pattern);
    wbFmtState.structure?.searchControls(bar);
  }

  function wbToggleReplace(on = null) {
    const row = document.getElementById("wb-replace-row");
    if (!row) return;
    const show = on ?? row.hidden;
    row.hidden = !show;
    document.getElementById("wb-replace-toggle")?.setAttribute("aria-expanded", String(show));
    document.getElementById("wb-search-bar")?.classList.toggle("is-replacing", show);
    if (show) document.getElementById("wb-replace-input")?.focus();
  }

  function wbOpenBoardSearch({ replace = false } = {}) {
    const bar = document.getElementById("wb-search-bar");
    const input = document.getElementById("wb-search-input");
    if (!bar || !input) return;
    wbEnsureReplaceRow(bar);
    wbEnsureSearchOptions(bar);
    bar.classList.remove("hidden");
    input.focus();
    input.select();
    if (replace) wbToggleReplace(true);
  }

  //: The file's surface: what other files call (L286).
  //: The map's quick add (wbMapCache.renderAdd) asks this, not the state itself, so
  //: the state stays private and the shared scope gains no name (global-scope ratchet).
  wbMapCache.searchLive = () => Boolean(wbBoardSearch.matches.length || wbBoardSearch.query.trim());
  Object.assign(window, { wbBoardSearchRun, wbApplySearchHighlight, wbBoardSearchGo, wbCloseBoardSearch, wbOpenBoardSearch });
})();
