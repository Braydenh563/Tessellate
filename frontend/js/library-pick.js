// library-pick.js: the Library item picker dialog (bookmark, board, note or document), moved out of selection.js on 2026-10-12 for the boot gzip budget. Every caller awaits it: `lazy-entries.js` stands in until this loads. Its source table and remembered-tab helper stay in selection.js.

//: And its second line: what tells two rows with one name apart.
function libraryPickAbout(kind, row) {
  const when = relativeTime(row.updated_at || row.created_at);
  if (kind === "note") return pickerNoteAbout(row);
  if (kind === "document") return notePickerFacts(when && `Edited ${when}`, row.words ? nounCount(row.words, "word") : "");
  if (kind === "file") return notePickerFacts(row.size_bytes ? formatFileSize(row.size_bytes) : "", notePickerUsedIn(row) || when);
  if (kind === "board") return notePickerFacts(row.type === "board" ? "Whiteboard" : "Mind map", when);
  let host = "";
  try {
    host = new URL(row.url).hostname.replace(/^www\./, "");
  } catch {
    host = row.url || "";
  }
  return notePickerFacts(host, row.group || "");
}

//: Fetched once per dialog and per source, not per keystroke. The shown
//: source first; the others after it, one at a time, so each tab carries its
//: count (what matches the words typed, or everything) and opens at once. A
//: slow fetch that lands after the tab changed paints nothing.
function pickLibraryItemDialog(message, { sources = null } = {}) {
  const available = LIBRARY_PICK_SOURCES.filter((source) =>
    sources ? sources.includes(source.kind) : !source.optIn
  );
  return new Promise((resolve) => {
    let active = (available.length > 1 && pickerRememberedSource(available)) || available[0];
    const shell = pickerDialog({ title: message, placeholder: active.placeholder, searchLabel: message });
    const box = pickerListbox(shell, active.label);
    const seg = document.createElement("div");
    //: A tab strip, never a pill, in a popup (INBOX 715, DESIGN.md "A popup
    //: that chooses a kind"); each tab carries its count.
    seg.className = "tabs-line popup-kinds picker-kinds";
    seg.setAttribute("role", "tablist");
    seg.setAttribute("aria-label", "What to point at");

    //: Notes are never cached: `allEntries` is kept current by every save.
    //: Drafts, deleted, private notes and boards are left out (a board is
    //: usually the very thing this picker was opened from).
    const cache = {};
    let token = 0;
    const notes = () =>
      (typeof allEntries !== "undefined" ? allEntries : []).filter(
        (entry) => !entry.is_draft && !entry.is_deleted && !entry.is_board && !entry.is_private
      );
    const rowsFor = async (kind) => {
      if (kind === "note") return notes();
      if (cache[kind]) return cache[kind];
      const source = available.find((s) => s.kind === kind);
      //: The gallery is paged (tests/test_gallery_paging.py); the rest answer once.
      const read = source.path === "/files/gallery"
        ? apiPagedList(source.path, 200, { silent: true })
        : apiJson(source.path, { silent: true });
      //: A failed read is not remembered as an empty source: the next visit to the tab asks again.
      const rows = await read.catch(() => null);
      if (!rows) return [];
      const list = Array.isArray(rows) ? rows : rows.documents || [];
      cache[kind] = source.keep ? list.filter(source.keep) : list;
      return cache[kind];
    };
    const matching = (kind, rows, term) =>
      rows
        .map((row) => ({ row, label: libraryPickLabel(kind, row) }))
        .filter(({ label }) => !term || label.toLowerCase().includes(term.toLowerCase()));

    //: Each tab's count, for the sources already read; blank until then, so a
    //: number is never a guess.
    const counts = () => {
      const term = shell.search.value.trim();
      for (const tab of seg.children) {
        const kind = tab.dataset.pickKind;
        const rows = kind === "note" ? notes() : cache[kind];
        tab.querySelector(".seg-count").textContent = rows ? String(matching(kind, rows, term).length) : "";
      }
    };

    const paint = async () => {
      const mine = (token += 1);
      const source = active;
      const term = shell.search.value.trim();
      if (source.kind !== "note" && !cache[source.kind]) box.loading(`Loading your ${source.label.toLowerCase()}…`);
      const rows = await rowsFor(source.kind);
      counts();
      if (mine !== token || active !== source) return;
      const items = matching(source.kind, rows, term)
        .slice(0, 40)
        //: The row itself travels with the choice, so a caller that needs a
        //: fact the row carries (whether a board is a map) has it without a
        //: second fetch. Its label is the short one a toast can carry.
        .map(({ row, label }) => ({
          icon: typeof source.icon === "function" ? source.icon(row) : source.icon,
          label,
          about: libraryPickAbout(source.kind, row),
          value: { kind: source.kind, id: row.id, label: clipText(label, 70), row },
        }));
      const empty = typeof source.icon === "function" ? source.empty : source.icon;
      box.fill(items, term, pickerEmpty(source.label.toLowerCase(), term, empty, source.hint));
    };

    //: The tabs: one Tab stop, the arrows (and Home and End) walk them, the
    //: Attach picker's keys; a tab the person chose is remembered.
    const choose = (source, focus) => {
      active = source;
      for (const tab of seg.children) {
        const on = tab.dataset.pickKind === source.kind;
        tab.classList.toggle("active", on);
        tab.setAttribute("aria-selected", String(on));
        tab.tabIndex = on ? 0 : -1;
        if (on && focus) tab.focus();
      }
      shell.search.placeholder = source.placeholder;
      shell.list.setAttribute("aria-label", source.label);
      paint();
    };
    const pick = (source, focus) => {
      choose(source, focus);
      try {
        prefs.set(PICK_SOURCE_KEY, source.kind);
      } catch {
        // A blocked store only means the next open starts on the first tab.
      }
    };
    for (const source of available) {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", shell.list.id);
      tab.dataset.pickKind = source.kind;
      const name = document.createElement("span");
      name.textContent = source.label;
      const count = document.createElement("span");
      count.className = "seg-count";
      tab.append(name, count);
      tab.addEventListener("click", () => {
        pick(source);
        shell.search.focus();
      });
      seg.appendChild(tab);
    }
    seg.addEventListener("keydown", (event) => {
      const at = available.indexOf(active);
      const last = available.length - 1;
      const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: last }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      pick(available[(to + available.length) % available.length], true);
    });
    shell.search.addEventListener("input", paint);
    choose(active);
    shell.open(resolve, { seg: available.length > 1 ? seg : null });
    //: The other sources' counts, read after the dialog is up and one at a
    //: time, so the first paint never waits on them.
    if (available.length > 1) {
      (async () => {
        for (const source of available) {
          if (source.kind === "note" || cache[source.kind]) continue;
          await rowsFor(source.kind);
          if (!shell.card.isConnected) return;
          counts();
        }
      })();
    }
  });
}
