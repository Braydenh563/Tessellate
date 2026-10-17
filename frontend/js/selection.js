// selection.js: selection to note, the pick dialogs, the selection popup. Moved
// out of app.js on 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// Where the selected passage came from, when the app knows: only the web
// reader (`webReaderPage` holds the page's url and title; BACKLOG.md §65).
// Elsewhere `null` says there is no external source rather than inventing one.
function selectionSource(node) {
  const el = node && (node.nodeType === 1 ? node : node.parentElement);
  if (!el || !el.closest("#web-reader")) return null;
  if (!webReaderPage?.url) return null;
  return { url: webReaderPage.url, title: webReaderPage.title || webReaderPage.domain || "" };
}

// A passage, quoted, its origin attributed under it: a blockquote, because a
// clipping is somebody else's words, and a real markdown link so it stays
// clickable.
function clippingMarkdown(text, source) {
  const quoted = text
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
  if (!source) return quoted;
  const label = source.title || source.url;
  return `${quoted}\n\n: [${label}](${source.url})`;
}

async function saveSelectionAsNote(text, { draft = false, source = null } = {}) {
  const content = source ? clippingMarkdown(text, source) : text;
  // Real metadata beside the body's own quote and link (BACKLOG §65): the body
  // keeps the note a portable markdown file, the columns let a card show a
  // badge without parsing it back out.
  const sourceFields = source
    ? { source_url: source.url, source_title: source.title || "" }
    : {};
  //: **Said the moment it is pressed** (INBOX 446): the save waits on the
  //: server, which files the note first, and seconds of nothing read as a dead
  //: menu item. A progress toast now, then where it went, with Open.
  const progress = toastProgress(draft ? "Saving as a draft…" : "Saving as a note…");
  try {
    const created = await apiJson("/entries", {
      method: "POST",
      //: Filed in the background, as Capture's are: filing first held the
      //: answer for as long as the model took (INBOX 446).
      body: JSON.stringify({ content, is_draft: draft, defer_filing: true, ...sourceFields }),
    });
    // Undoable, like every other create (the global stack, `pushUndo`).
    pushUndo(
      draft ? "Saved a selection as a draft" : "Saved a selection as a note",
      async () => {
        await api(`/entries/${created.id}`, { method: "DELETE" });
        await refreshEntries([created.id]);
      },
      async () => {
        await apiJson("/entries", {
          method: "POST",
          body: JSON.stringify({ content, is_draft: draft, defer_filing: true, ...sourceFields }),
        });
        await loadEntries();
      }
    );
    // Unconditional, as in saveChatAnswerAsNote(): the popup may not be on the
    // Notes tab, and `entries` must not go stale.
    await refreshEntries([created.id]);
    progress.done(
      draft ? "Saved as a draft." : "Saved as a note, filing it now.",
      { actionLabel: "Open", onAction: () => flashEntry(created.id), go: { open: "entry", id: created.id } }
    );
  } catch (error) {
    progress.done(error.message || "Couldn't save that note.", { isError: true });
  }
}

// Append the selection to a note the user picks (`pickEntryDialog`; the chat's
// Attach picker is the composer's). `jump` is for the writing desk's "Insert
// into a note": `flashEntry` would walk off its half-written draft, so the
// trip is offered (`toastAction`) instead.
async function appendSelectionToNote(text, { jump = true, message = null, what = "the selected text" } = {}) {
  const entry = await pickEntryDialog(message || "Add the selected text to which note?");
  if (!entry) return;
  const before = entry.content;
  const after = `${before.trimEnd()}\n\n${text}`;
  try {
    await api(`/entries/${entry.id}`, {
      method: "PUT",
      body: JSON.stringify({ content: after }),
    });
    pushEntryPutUndo(entry.id, "Added text to a note", { content: before }, { content: after });
    await refreshEntries([entry.id]);
    if (jump) {
      toast("Added to the note.");
      flashEntry(entry.id);
    } else {
      toastAction("Added to the note.", "Open it", () => flashEntry(entry.id), { go: { open: "entry", id: entry.id } });
    }
  } catch (error) {
    toast(error.message || `Couldn't add ${what} to the note.`, true);
  }
}

//: **A dialog's head** built in script (DESIGN.md, "A dialog's head"): the
//: title at a dialog's size, then the icon X last, which calls `close`.
function dialogHead(title, close) {
  const head = document.createElement("div");
  head.className = "dialog-head";
  const heading = document.createElement("h2");
  heading.className = "dialog-head-title";
  heading.textContent = title;
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  const x = smallButton("ph:x", "Close", close);
  x.classList.add("icon-only", "dialog-head-btn");
  x.setAttribute("aria-label", "Close");
  actions.appendChild(x);
  head.append(heading, actions);
  return head;
}

//: **The picker dialog** (INBOX 548, the owner: "redesign old ui popups like
//: this as well to be consistent, modern and professional"). One shell for
//: every "choose from your notebook" dialog, on DESIGN.md's recipes rather than
//: the confirm alert's: the `.dialog-head` (the title, the icon X last), a
//: `.seg` of sources when there are several, one line of description, the
//: `.search-field` well, the list, and the dialog foot only when a choice
//: needs confirming. Escape, the X and the backdrop close it, and the focus
//: goes back to what opened it. `role="dialog"` on the overlay is what
//: `activeOverlay()` traps Tab inside, with no registration step. The
//: `entry-pick-*` classes stay as the sweeps' hooks.
function pickerDialog({ title, about = "", placeholder, searchLabel = placeholder, list = null }) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", title);
  const card = document.createElement("div");
  card.className = "card modal-card space-dialog entry-pick-card";
  const line = document.createElement("p");
  line.className = "muted entry-pick-about";
  line.textContent = about;
  const field = document.createElement("div");
  field.className = "search-field";
  const glyph = document.createElement("i");
  glyph.className = "ph ph-magnifying-glass search-field-icon";
  glyph.setAttribute("aria-hidden", "true");
  const search = document.createElement("input");
  search.type = "search";
  search.className = "search-field-input";
  search.autocomplete = "off";
  search.placeholder = placeholder;
  search.setAttribute("aria-label", searchLabel);
  field.append(glyph, search);
  if (!list) {
    list = document.createElement("ul");
    list.className = "rich-picker-list entry-pick-list";
  }
  const returnFocus = document.activeElement;
  let settled = false;
  let answer = () => {};
  const onKey = (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    close(null);
  };
  const close = (value) => {
    if (settled) return;
    settled = true;
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    if (returnFocus?.isConnected) returnFocus.focus?.();
    answer(value);
  };
  const head = dialogHead(title, () => close(null));
  return {
    card, search, list, close,
    //: The parts in the recipe's order, then open.
    open(resolve, { seg = null, foot = null } = {}) {
      answer = resolve;
      card.append(head, ...(seg ? [seg] : []), ...(about ? [line] : []), field, list, ...(foot ? [foot] : []));
      overlay.appendChild(card);
      wireBackdropClose(overlay, () => close(null));
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(overlay);
      search.focus();
    },
  };
}

//: A list's own state in its place (loading, nothing there, nothing
//: matching): the empty state recipe (`.empty-state`), an icon and a title
//: over one sentence when it is a state worth explaining, the sentence alone
//: while loading. It fills the list's fixed height, so nothing moves.
function pickerListState(list, text, { icon = "", title = "" } = {}) {
  list.replaceChildren();
  notePickerEmpty(list, text, null);
  const li = list.lastElementChild;
  li.setAttribute("role", "presentation");
  if (title) {
    const heading = document.createElement("p");
    heading.className = "empty-title";
    heading.textContent = title;
    li.prepend(heading);
  }
  if (icon) {
    const glyph = document.createElement("i");
    glyph.className = `${richPickerIconClass(icon)} empty-icon`;
    glyph.setAttribute("aria-hidden", "true");
    li.prepend(glyph);
  }
}

//: The empty state for a source: nothing matching the words, or nothing yet.
function pickerEmpty(nouns, term, icon, hint) {
  return term
    ? { icon: "ph:magnifying-glass", title: `No ${nouns} match “${term}”`, text: "Try fewer or different words." }
    : { icon, title: `No ${nouns} yet`, text: hint };
}

//: **One choice, picked by typing** (the "/" menu's keys, the rich picker's
//: rows): the field is a combobox driving a listbox; Down and Up light a row,
//: Enter takes it, the pointer lights the row under it and a click takes it.
//: A lit row is brought into view by the list's own `scrollTop`.
let pickerListCount = 0;
function pickerListbox(shell, label) {
  const { search, list } = shell;
  list.id = `entry-pick-list-${(pickerListCount += 1)}`;
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", label);
  search.setAttribute("role", "combobox");
  search.setAttribute("aria-controls", list.id);
  search.setAttribute("aria-expanded", "true");
  search.setAttribute("aria-autocomplete", "list");
  let rows = [];
  let values = [];
  let at = -1;
  const light = (index) => {
    at = index;
    const row = richPickerSetActive(list, rows, index);
    if (!row) return search.removeAttribute("aria-activedescendant");
    search.setAttribute("aria-activedescendant", row.id);
    const box = list.getBoundingClientRect();
    const r = row.getBoundingClientRect();
    if (r.top < box.top) list.scrollTop -= box.top - r.top;
    else if (r.bottom > box.bottom) list.scrollTop += r.bottom - box.bottom;
  };
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (rows.length) light(Math.max(0, Math.min(rows.length - 1, at + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Enter" && rows[at]) {
      event.preventDefault();
      shell.close(values[at]);
    }
  });
  return {
    //: `items` are `{icon, label, about, value}`; `query` marks the letters;
    //: `empty` is `pickerEmpty`'s state for when there are none.
    fill(items, query, empty) {
      if (!items.length) {
        rows = [];
        values = [];
        light(-1);
        return pickerListState(list, empty.text, empty);
      }
      list.replaceChildren();
      rows = items.map((item, i) => {
        const row = richPickerRow({ ...item, query, id: `${list.id}-${i}`, className: "entry-pick-row" });
        row.title = item.label;
        row.addEventListener("mousemove", () => at !== i && light(i));
        row.addEventListener("mousedown", (event) => event.preventDefault());
        row.addEventListener("click", () => shell.close(item.value));
        list.appendChild(row);
        return row;
      });
      values = items.map((item) => item.value);
      list.scrollTop = 0;
      light(0);
    },
    loading(text) {
      rows = [];
      light(-1);
      pickerListState(list, text);
    },
  };
}

//: A note's second line: its category, then when it was last touched.
function pickerNoteAbout(entry) {
  return notePickerFacts(entry.category || "Unfiled", relativeTime(entry.updated_at || entry.created_at));
}

//: A one-off "choose a note" dialog (the selection's "Add to a note…", a
//: board's "Add to which note?"). Drafts are left out: adding to a half-typed
//: capture is not what "an existing note" means.
function pickEntryDialog(message) {
  return new Promise((resolve) => {
    const shell = pickerDialog({ title: message, placeholder: "Search your notes…", searchLabel: "Search your notes" });
    const box = pickerListbox(shell, "Your notes");
    const paint = () => {
      const term = shell.search.value.trim();
      const needle = term.toLowerCase();
      const items = allEntries
        .filter((e) => !e.is_draft && !e.is_deleted)
        .filter((e) => !needle || (e.content || "").toLowerCase().includes(needle))
        .slice(0, 40)
        .map((entry) => ({
          icon: "ph:note",
          label: entry.title || clipText(notePreviewText(entry.content), 200),
          about: pickerNoteAbout(entry),
          value: entry,
        }));
      box.fill(items, term, pickerEmpty("notes", term, "ph:note", LIBRARY_PICK_SOURCES[0].hint));
    };
    shell.search.addEventListener("input", paint);
    paint();
    shell.open(resolve);
  });
}

//: **A note field's picker** (GRAPH_PLAN KG4): a note-kind property was a text
//: box with the first 300 titles as suggestions, so a note past the 300th
//: could only be typed from memory. This puts the notebook's own search beside
//: the box: the button opens `pickEntryDialog`, and the chosen note's name goes
//: into the box (the caller writes it as `[[name]]`), then `after` runs, so a
//: field that saves on change saves.
function noteFieldPickButton(input, after) {
  const button = smallButton("ph:magnifying-glass", "Choose a note", async () => {
    const entry = await pickEntryDialog("Choose a note");
    if (!entry) return;
    input.value = noteNamePlain(entry.title || entry.content).slice(0, 80);
    input.dispatchEvent(new Event("change", { bubbles: true }));
    if (after) after(entry);
  });
  button.classList.add("icon-only", "prop-note-pick");
  button.setAttribute("aria-label", "Choose a note");
  return button;
}

//: **Choose any one thing the library holds**, a note, a document, a file or
//: a saved link, as `{kind, id, label, row}`. Not `pickEntryDialog` (notes
//: only), `pickMediaDialog` (an upload) or the chat's Attach picker (a
//: multi-select bound to the composer). `kind` is the *server's* vocabulary
//: (`MAP_REFERENCE_KINDS` in routes_whiteboard.py), so a map's reference node
//: posts it as is and the server resolves the label (MINDMAP_PLAN.md §9.2).
//: **`optIn` keeps a source out of the default set**: a board is a fine thing
//: to point at from a note (INBOX 309), but not from a map's reference node,
//: so only a caller that names it in `sources` is shown it.
//: `icon` is per row where the row says more than its source does: a file by
//: its type (`attachmentIconClass`, the file surfaces' own table), a link by
//: what it points at (`bookmarkKind`), a board by whether it is a map; then
//: `empty` is the source's own glyph for its empty state. `hint` is that
//: state's sentence: where this kind of thing comes from.
const LIBRARY_PICK_SOURCES = [
  { kind: "note", label: "Notes", icon: "ph:note", placeholder: "Search your notes…", hint: "Notes you write show up here." },
  {
    kind: "document", label: "Documents", icon: "ph:file-text", path: "/documents",
    placeholder: "Search your documents…", hint: "Documents you write in the Library show up here.",
  },
  {
    kind: "file", label: "Files", path: "/files/gallery", placeholder: "Search your files…",
    icon: (row) => `ph:${(attachmentIconClass("", row?.original_name || row?.filename || "file") || "ph-file").slice(3)}`,
    empty: "ph:paperclip", hint: "Files you attach to notes show up here.",
  },
  {
    kind: "link", label: "Bookmarks", path: "/bookmarks", placeholder: "Search your bookmarks…",
    icon: (row) => bookmarkKind(row?.url).icon,
    empty: "ph:link-simple", hint: "Links you save in the Library show up here.",
  },
  {
    kind: "board",
    label: "Boards & maps",
    //: Per row: a whiteboard and a mind map sit in one list, and a list of
    //: bare titles gave no way to tell them apart.
    icon: (row) => (row?.type === "board" ? "ph:squares-four" : "ph:tree-structure"),
    empty: "ph:tree-structure",
    hint: "Boards and maps you make show up here.",
    path: "/whiteboard/boards",
    placeholder: "Search your boards and maps…",
    //: The unnamed scratch board (`id: null`) is where things land when nobody
    //: chose a board, not somewhere to point at (`renderAttachToBoard`).
    keep: (row) => row && row.id != null,
    optIn: true,
  },
];

//: What kind of thing a link points at, from its address alone: this app
//: fetches nothing from the internet, so there is no favicon, but a tile that
//: says "video", "code", "PDF" or "email" tells a list of links apart at a
//: glance, which is what a favicon column is for. Hosts are matched at their
//: tail so "m.youtube.com" and "www.youtube.com" are one kind. Here rather
//: than in library.js (lazy) because the picker draws it before the Library
//: has ever been opened (INBOX 572).
const BOOKMARK_KINDS = [
  { key: "email", icon: "ph:envelope-simple", label: "Email address", test: (u) => u.protocol === "mailto:" },
  { key: "phone", icon: "ph:phone", label: "Phone number", test: (u) => u.protocol === "tel:" },
  { key: "pdf", icon: "ph:file-pdf", label: "PDF", test: (u) => /\.pdf$/i.test(u.pathname) },
  {
    key: "video", icon: "ph:play-circle", label: "Video",
    test: (u) => /(^|\.)(youtube\.com|youtu\.be|vimeo\.com|twitch\.tv|dailymotion\.com)$/.test(u.hostname),
  },
  {
    key: "code", icon: "ph:code", label: "Code",
    test: (u) => /(^|\.)(github\.com|gitlab\.com|bitbucket\.org|codeberg\.org|stackoverflow\.com|developer\.mozilla\.org|docs\.python\.org)$/.test(u.hostname),
  },
  {
    key: "reference", icon: "ph:book-open", label: "Reference",
    test: (u) => /(^|\.)(wikipedia\.org|arxiv\.org|wikimedia\.org|britannica\.com)$/.test(u.hostname),
  },
];
const BOOKMARK_KIND_DEFAULT = { key: "link", icon: "ph:globe", label: "Web page" };

function bookmarkKind(url) {
  const raw = String(url || "").trim();
  try {
    const parsed = new URL(/^[a-z][a-z0-9+.-]*:/i.test(raw) ? raw : `https://${raw}`);
    return BOOKMARK_KINDS.find((kind) => kind.test(parsed)) || BOOKMARK_KIND_DEFAULT;
  } catch {
    return BOOKMARK_KIND_DEFAULT;
  }
}

//: One row's label per source, in one table (`notePickerShape`'s reason).
//: Long enough that the row's own width clips it (an ellipsis in CSS):
//: clipped at 70 characters, a title stopped short with half the row empty.
function libraryPickLabel(kind, row) {
  if (kind === "note") return noteLabel(row, 200);
  if (kind === "board") return row.title || (row.type === "board" ? "Untitled board" : "Untitled map");
  if (kind === "document") return row.title || "Untitled document";
  if (kind === "file") return row.original_name || row.filename || "File";
  return row.title || row.url || "Link";
}

//: And its second line: what tells two rows with one name apart.
function libraryPickAbout(kind, row) {
  const when = relativeTime(row.updated_at || row.created_at);
  if (kind === "note") return pickerNoteAbout(row);
  if (kind === "document") return notePickerFacts(when && `Edited ${when}`, row.words ? `${row.words} word${row.words === 1 ? "" : "s"}` : "");
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

//: The source the person last chose, so the map's picker opens where they
//: were (INBOX 572). A per-viewer convenience: storage that is blocked or
//: empty just opens on the first source.
const PICK_SOURCE_KEY = "libraryPickSource";
function pickerRememberedSource(available) {
  try {
    const kind = prefs.get(PICK_SOURCE_KEY, null);
    return available.find((source) => source.kind === kind) || null;
  } catch {
    return null;
  }
}


//: Pick something already uploaded rather than uploading it again ("attach
//: images that are already in the image library... to new notes in the
//: capture subtab"). `/media` has no mime field, so each tile is tried as an
//: `<img>` and drops itself on error, the gallery's own approach.
function pickMediaDialog() {
  return new Promise((resolve) => {
    const grid = document.createElement("div");
    grid.className = "media-pick-grid";
    const shell = pickerDialog({
      title: "Choose from your library",
      about: "An image already in your library, attached without uploading it again.",
      placeholder: "Search by file name…",
      searchLabel: "Search your uploaded images",
      list: grid,
    });
    let uploads = [];
    //: The grid's states on the empty state recipe, as the lists' are
    //: (`pickerListState`): an icon and a title over the sentence when
    //: there is nothing to show, the sentence alone while loading.
    const say = (text, { icon = "", title = "" } = {}) => {
      const state = document.createElement("div");
      state.className = "empty-state entry-pick-empty";
      if (icon) {
        const glyph = document.createElement("i");
        glyph.className = `${richPickerIconClass(icon)} empty-icon`;
        glyph.setAttribute("aria-hidden", "true");
        state.appendChild(glyph);
      }
      if (title) {
        const heading = document.createElement("p");
        heading.className = "empty-title";
        heading.textContent = title;
        state.appendChild(heading);
      }
      const line = document.createElement("p");
      line.textContent = text;
      state.appendChild(line);
      grid.replaceChildren(state);
    };
    const paint = () => {
      const term = shell.search.value.trim().toLowerCase();
      const matches = uploads.filter((u) => !term || u.original_name.toLowerCase().includes(term)).slice(0, 60);
      if (!matches.length) {
        return uploads.length
          ? say("Try fewer or different words.", { icon: "ph:magnifying-glass", title: "No pictures match that" })
          : say("Attach a new file to start your library.", { icon: "ph:image", title: "No pictures yet" });
      }
      grid.replaceChildren();
      for (const upload of matches) {
        const tile = document.createElement("button");
        tile.type = "button";
        tile.className = "media-pick-tile";
        tile.title = upload.original_name;
        const img = document.createElement("img");
        img.src = mediaSrc(upload.url);
        img.alt = "";
        img.loading = "lazy";
        img.addEventListener("error", () => tile.remove());
        const name = document.createElement("span");
        name.textContent = upload.original_name;
        tile.append(img, name);
        tile.addEventListener("click", () => shell.close(upload));
        grid.appendChild(tile);
      }
    };
    shell.search.addEventListener("input", paint);
    say("Loading your library…");
    shell.open(resolve);
    apiJson("/media", { silent: true })
      .then((list) => {
        uploads = list || [];
        paint();
      })
      .catch(() => say("Couldn't load your library."));
  });
}

// Turn the selection into a reminder, through the same parser the Reminders
// tab's "magic add" box uses: not a second one.
async function remindFromSelection(text) {
  try {
    const reminder = await apiJson("/reminders/parse", {
      method: "POST",
      // Our clock, so "tomorrow evening" resolves against the time the user
      // can see rather than the server's UTC: same as magicAddReminder.
      body: JSON.stringify({ text, tz_offset_minutes: -new Date().getTimezoneOffset() }),
    });
    reminderMadeUndo(reminder);
    toast(`Reminder set: ${relativeWhen(reminder.due_at)}.`);
    askNotificationPermission();
    // Same fix as saveChatAnswerAsNote()/saveSelectionAsNote(): unconditional,
    // so a reminder created from wherever this popup was invoked doesn't sit
    // stale out of the Reminders tab's in-memory list.
    loadReminders();
  } catch (error) {
    toast(error.message || "Couldn't read a reminder from that.", true);
  }
}

// The field a selection came from (what an edit action writes back into), or
// null in rendered content.
let selectionPopupField = null;

// A selection inside a text field, or null: `window.getSelection()` does not
// see inside a <textarea>, which keeps its own
// `selectionStart`/`selectionEnd`.
function fieldSelection() {
  const el = document.activeElement;
  if (!el || (el.tagName !== "TEXTAREA" && el.tagName !== "INPUT")) return null;
  // `selectionStart` is null on input types that do not support it (number,
  // email, colour…), which is exactly the set we should not offer this on.
  if (el.selectionStart == null || el.selectionStart === el.selectionEnd) return null;
  //: A one-line field with all of its text selected is a name waiting to be
  //: replaced (a new document's "Untitled document N", a board's rename), not
  //: a passage: the popup used to open over it (INBOX 904 B17, B24).
  if (el.tagName === "INPUT" && el.selectionStart === 0 && el.selectionEnd === el.value.length) return null;
  //: A search box's selected query is not writing (the Finder and the
  //: palette open with their query selected so typing replaces it), and a
  //: field inside an overlay belongs to that overlay: the popup drew its
  //: menu over the Finder's own results. Writing fields only.
  //: UX-09: `data-no-selection-popup` marks a query box that is not type=search
  //: (the Ask box among them: an answer selects its question so typing
  //: replaces it, and that selection drew the menu over the sources).
  if (el.type === "search" || el.closest("[data-no-selection-popup], .lock-overlay, .modal-overlay, .command-palette, [role='combobox']")) {
    return null;
  }
  const text = el.value.slice(el.selectionStart, el.selectionEnd);
  return text.trim() ? { el, start: el.selectionStart, end: el.selectionEnd, text } : null;
}

// Replace a field's selected range and reselect the passage. `input` is
// dispatched because autosave, the counter and the preview listen for it.
function wrapFieldSelection(field, before, after) {
  const { el, start, end, text } = field;
  el.value = el.value.slice(0, start) + before + text + after + el.value.slice(end);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.focus();
  el.setSelectionRange(start + before.length, start + before.length + text.length);
}

function selectionMenuItems() {
  const text = selectionPopupText;
  const source = selectionPopupSource;
  const aiOff = modelStatus ? modelStatus.ollama_running === false : false;

  const items = [];

  // **Where highlighting is discovered** ("I still dont know how to highlight
  // text"): select, pick a colour; what it writes is still plain `==text==`.
  if (selectionPopupField) {
    const field = selectionPopupField;
    items.push(
      makeMenuItem("ph:highlighter Highlight", "Mark this passage (yellow)", () =>
        wrapFieldSelection(field, "==", "==")
      ),
      //: UX-19: the colours are a menu to pick from, not a name to type.
      makeMenuItem("ph:palette Highlight in a colour…", "Green, blue, pink, purple or orange", () => {
        const at = document.querySelector(".selection-popup")?.getBoundingClientRect() || { left: 80, bottom: 80 };
        openMenuAtPoint(["green", "blue", "pink", "purple", "orange"].map((c) => ({
          label: `ph:highlighter ${c[0].toUpperCase()}${c.slice(1)}`,
          run: () => wrapFieldSelection(field, `==${c}|`, "=="),
        })), "Highlight colour", at.left, at.bottom);
      }),
      makeMenuItem("ph:text-b Bold", "Wrap this in **bold**", () =>
        wrapFieldSelection(field, "**", "**")
      ),
      makeMenuItem("ph:text-italic Italic", "Wrap this in *italic*", () =>
        wrapFieldSelection(field, "*", "*")
      )
    );
  }

  items.push(
    makeMenuItem("ph:note-pencil Save as a note", "File this straight into your notebook", () =>
      saveSelectionAsNote(text)
    ),
    makeMenuItem("ph:pencil-simple-line Save as a draft", "Keep it as an unfinished draft", () =>
      saveSelectionAsNote(text, { draft: true })
    ),
    makeMenuItem("ph:plus-circle Add to a note…", "Append this to a note you already have", () =>
      appendSelectionToNote(text)
    )
  );

  if (source) {
    items.push(
      makeMenuItem(
        "ph:quotes Save with its source",
        `Save as a quote, credited to ${source.title || source.url}`,
        () => saveSelectionAsNote(text, { source })
      )
    );
  }

  items.push(
    // Through the shared helper, not `navigator.clipboard` directly: it falls
    // back to a hidden textarea and then to showing the text pre-selected,
    // which is what makes copy work in the hardened webview the desktop build
    // runs in. (`tests/test_log_console.py` enforces this, and caught the
    // direct call that was here first.)
    makeMenuItem("ph:copy Copy", "Copy the selected text", async () => {
      if (await copyToClipboard(text)) toast("Copied.");
    }),
    makeMenuItem("ph:magnifying-glass Search the notebook", "Find notes that match this", () => {
      switchTab("notes");
      showNotesSection("browse");
      noteSearch = text;
      $("note-search").value = text;
      $("save-search").classList.remove("hidden");
      renderEntries();
      if ($("semantic-search-toggle")?.checked) loadEntries();
      //: Said, with the way back (INBOX 446): on the Notes list already, the
      //: list filtered under the person with nothing to say it had.
      const shown = text.length > 40 ? `${text.slice(0, 40)}…` : text;
      toastAction(`Showing notes with “${shown}”.`, "Clear", () => {
        noteSearch = "";
        $("note-search").value = "";
        $("save-search").classList.add("hidden");
        renderEntries();
      });
    }),
    makeMenuItem("ph:bell Set a reminder", "Read a reminder out of the selection", () =>
      remindFromSelection(text)
    )
  );

  // AI-only, and disabled rather than hidden when the model is off, the same
  // convention `data-needs-model` applies to every other AI action, so the
  // capability stays discoverable and the reason is on the item itself.
  // (That attribute is read from the markup by `syncModelGatedControls`, and
  // these items are built fresh on every open, so they carry the state
  // directly instead.)
  items.push(
    makeMenuItem(
      "ph:scissors Extract notes…",
      aiOff
        ? `Extracting notes needs the local AI. ${AI_OFFLINE_HINT}.`
        : "Split this into one or more linked notes, with a preview first",
      () => {
        if (aiOff) {
          toast("Extracting notes needs the local AI.", "info");
          return;
        }
        openExtractPreview(text);
      }
    ),
    makeMenuItem("ph:chat-circle Ask Atlas about this", "Start a chat about the selection", () => {
      switchTab("chat");
      const input = $("chat-input");
      input.value = `Tell me about this: "${text}"`;
      input.focus();
    })
  );
  return items;
}

function selectionPopup() {
  if (selectionPopupEl) return selectionPopupEl;
  const box = document.createElement("div");
  box.className = "selection-popup hidden";
  document.body.appendChild(box);
  selectionPopupEl = box;
  return box;
}

function hideSelectionPopup() {
  selectionPopupEl?.classList.add("hidden");
  selectionPopupText = "";
  selectionPopupSource = null;
}

// Keep the menu inside the window ("shows the Popup buttons within the
// application window"): measured after opening and flipped, the shape
// `buildMenuGroupButton` uses.
function clampSelectionMenu(menu) {
  menu.classList.remove("menu-flip-up", "menu-flip-left");
  //: **A menu that has left its box is already placed, and flipping it here
  //: collapses it.** Reported: "when I highlight text and the popup kebab
  //: button appears, the first time I click it, a little collapsed line
  //: appears below it, then I need to click the button to close the popup and
  //: reopen it for it to actually show".
  //:
  //: `openActionMenu` calls `escapeMenuIfClipped` first, which reparents a
  //: clipped menu to `<body>`, makes it `position: fixed` and writes an
  //: explicit `top`. `.menu-flip-up` is `top: auto; bottom: calc(100% + 4px)`,
  //: written for a menu positioned against its own offset parent; on an
  //: escaped menu that `100%` resolves against the viewport, so the rule asks
  //: for a box whose bottom edge is four pixels above the top of the screen
  //: and the auto-height box collapses to its own padding. That is the strip
  //: in the report, and it is the same over-constraint
  //: `escapeMenuIfClipped` already guards against for `action-menu-flip`,
  //: one line of which says so: "Both at once over-constrains an auto-height
  //: box, which reproduced as the menu collapsing to its own padding."
  //:
  //: The second click appears to fix it because by then `_escapedHome` is set,
  //: `escapeMenuIfClipped` returns early, and whichever branch runs next
  //: happens not to add the class.
  //:
  //: Nothing is lost by leaving early: `placeEscapedMenu` positions the menu
  //: against the viewport directly, which is strictly better than choosing
  //: between two fixed anchors, and it is what this function is trying to
  //: approximate.
  if (menu.classList.contains("action-menu-escaped") || menu._escapedHome) return;
  const margin = 8;
  let rect = menu.getBoundingClientRect();
  if (rect.bottom > window.innerHeight - margin) menu.classList.add("menu-flip-up");
  rect = menu.getBoundingClientRect();
  if (rect.left < margin) menu.classList.add("menu-flip-left");
}

function showSelectionPopupAt(rect, text, source, point) {
  const box = selectionPopup();
  //: Reported: "I have to click it twice for it to actually properly
  //: expand". The click on the ⋯ opener ends in a `selectionchange` (the
  //: selection is unchanged, the event still fires), which re-entered here
  //: and rebuilt the popup, closed, over the menu that had just opened. The
  //: same selection with its menu open is left exactly as it is.
  if (
    !box.classList.contains("hidden") &&
    selectionPopupText === text &&
    selectionPopupSource === source &&
    box.querySelector(".action-menu:not(.hidden)")
  ) {
    return;
  }
  selectionPopupText = text;
  selectionPopupSource = source;

  // Rebuilt per selection: the item list depends on whether this passage has
  // a source and on whether the model is up.
  box.replaceChildren();
  const kebab = kebabMenu(selectionMenuItems(), "Actions for the selected text");
  box.appendChild(kebab);
  const opener = kebab.querySelector("[aria-haspopup]");
  const menu = kebab.querySelector(".action-menu");
  // Clicking the opener must not clear the selection underneath it. The old
  // three-button bar did this per button for the same reason; the text itself
  // is already captured above, but keeping the visible selection is what makes
  // the menu feel attached to it rather than to nothing.
  opener?.addEventListener("mousedown", (e) => e.preventDefault());
  opener?.addEventListener("click", () => {
    if (!menu.classList.contains("hidden")) clampSelectionMenu(menu);
  });

  // Position *before* revealing. Removing `hidden` first: which is what this
  // used to do: paints one frame of a `position: fixed` element that has no
  // left/top yet, i.e. at the bottom of `<body>`, as a visible flash.
  box.style.visibility = "hidden";
  box.classList.remove("hidden");
  const margin = 8;
  const boxRect = box.getBoundingClientRect();
  // Note the bound order: `max(margin, min(wanted, limit))`. Written the other
  // way round (`min(max(...), limit)`) a box wider than the viewport produces
  // a limit below the floor, `min` wins, and the popup lands off-screen left.
  // Anchored to the selection's top-right corner, just clear of the last
  // character. Asked for directly ("appear to the top right of the selection
  // while still remaining within the screen/window"), and it is the better
  // anchor than the centre this used to use: centred, the kebab drifts as the
  // selection grows, so it is never in the same place twice and it sits over
  // the middle of what you just highlighted. The right-hand end is where the
  // cursor already is when a left-to-right drag finishes.
  //
  // Both clamps keep the bound order `max(margin, min(wanted, limit))`, see
  // the note below on why the other way round puts it off-screen.
  // The cursor when we have one, the selection's right-hand end when we do
  // not (keyboard selections, and any caller without a pointer event).
  const anchorX = point ? point.x : rect.right;
  const anchorY = point ? point.y : rect.top;
  const left = Math.max(
    margin,
    Math.min(anchorX + 4, window.innerWidth - boxRect.width - margin)
  );
  let wantedTop = anchorY - boxRect.height - margin;
  // No room above the anchor, drop below it instead.
  if (wantedTop < margin) wantedTop = (point ? point.y : rect.bottom) + margin;
  const top = Math.max(
    margin,
    Math.min(wantedTop, window.innerHeight - boxRect.height - margin)
  );
  box.style.left = `${left}px`;
  box.style.top = `${top}px`;
  box.style.visibility = "";
}

// Whether this popup should offer to act on a selection. Both ends are
// checked: a drag from prose into a textarea is one selection with two homes.
function selectionIsActionable(selection) {
  const ends = [selection.anchorNode, selection.focusNode];
  for (const node of ends) {
    const el = node && (node.nodeType === 1 ? node : node.parentElement);
    if (!el || el.closest(SELECTION_POPUP_EXCLUDED)) return false;
  }
  return true;
}

// Where the pointer was when the selection finished, or null: the kebab sits
// off the cursor, not the range's corner. A keyboard or touch selection has no
// point and keeps the range anchoring; cleared on keydown.
let selectionPointerPoint = null;

function syncSelectionPopup() {
  // Text fields first. Asked for twice ("the ellipse button doesnt appear
  // when I highlight text in textboxes"), the editor is a <textarea>, whose
  // selection lives on the element rather than in the DOM selection, so the
  // rendered-content path below can never see it.
  const field = fieldSelection();
  if (field) {
    selectionPopupField = field;
    // A textarea has no range rectangle to anchor to, the browser exposes no
    // geometry for a selection inside one, so the pointer is the anchor when
    // there is one, and the field's own box is the fallback for a keyboard
    // selection. Passing the field rect as `rect` keeps showSelectionPopupAt's
    // existing "top-right of the selection" logic working unchanged.
    showSelectionPopupAt(
      field.el.getBoundingClientRect(),
      field.text,
      null,
      selectionPointerPoint
    );
    return;
  }

  const selection = window.getSelection();
  const text = (selection?.toString() || "").trim();
  if (!text || selection.isCollapsed || !selectionIsActionable(selection)) {
    // Don't yank the popup away while its own menu is open, the selection is
    // often cleared as a side effect of interacting with the menu.
    if (!selectionPopupEl?.querySelector(".action-menu:not(.hidden)")) hideSelectionPopup();
    return;
  }
  selectionPopupField = null;
  showSelectionPopupAt(
    selection.getRangeAt(0).getBoundingClientRect(),
    text,
    selectionSource(selection.anchorNode),
    selectionPointerPoint
  );
}

function initSelectionPopup() {
  // **Three ways in, because there used to be one.** `mouseup` alone meant the
  // popup did not exist for anyone selecting by touch (a long-press drag on a
  // phone dispatches `selectionchange`, not a useful `mouseup`) or by keyboard
  // (Shift+Arrow dispatches neither): so the app's richest capture surface
  // was mouse-only, on an app that ships a PWA manifest and a mobile layout.
  //
  // `selectionchange` fires continuously *during* a drag, so it is debounced:
  // repositioning the popup on every intermediate range is both wasteful and
  // visually noisy. `mouseup` stays as the immediate path so a mouse selection
  // still feels instant rather than delayed by the debounce.
  document.addEventListener("mouseup", (event) => {
    if (event.target.closest(".selection-popup")) return;
    selectionPointerPoint = { x: event.clientX, y: event.clientY };
    syncSelectionPopup();
  });
  // Touch releases carry coordinates too, on the changedTouches list rather
  // than the event itself, a long-press drag should anchor to the finger for
  // the same reason a mouse selection anchors to the cursor.
  document.addEventListener("touchend", (event) => {
    const touch = event.changedTouches && event.changedTouches[0];
    if (touch) selectionPointerPoint = { x: touch.clientX, y: touch.clientY };
  });
  // A keyboard selection has no pointer, so fall back to the range rectangle
  // rather than anchoring to wherever the mouse happened to be last.
  document.addEventListener("keydown", (event) => {
    if (event.shiftKey || event.key === "Escape") selectionPointerPoint = null;
  });

  let selectionSettleTimer;
  document.addEventListener("selectionchange", () => {
    clearTimeout(selectionSettleTimer);
    selectionSettleTimer = setTimeout(syncSelectionPopup, 200);
  });

  document.addEventListener("mousedown", (event) => {
    if (!event.target.closest(".selection-popup")) hideSelectionPopup();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideSelectionPopup();
  });
  window.addEventListener("scroll", hideSelectionPopup, true);
  window.addEventListener("resize", hideSelectionPopup);
  document.addEventListener("contextmenu", selectionRestoreOnContextMenu);
}

//: **A selection popup that has gone can be brought back: right-click the
//: selection** (the owner, 2026-10-11). Escape, a scroll and a click outside
//: all dismiss the bubble, and until now the only way back was to select again.
//: One helper for every selection bubble (the editor's format bar in
//: editor.js, the kebab above): it answers only while the right-click lands on
//: a non-empty selection inside a surface that owns a bubble, and otherwise
//: leaves the browser's menu alone. A menu another handler already opened
//: (`defaultPrevented`: a flagged word, a link, a row) wins. Touch is left to
//: the system's own selection menu. DESIGN.md recipe "Selection bubble",
//: `tests/test_ui_recipes.py` keeps the surfaces to this one listener.
function selectionPointInRange(x, y) {
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount || selection.isCollapsed) return null;
  const rects = [...selection.getRangeAt(0).getClientRects()];
  if (!rects.length) return null;
  const slack = 4;
  return rects.some((r) => x >= r.left - slack && x <= r.right + slack && y >= r.top - slack && y <= r.bottom + slack);
}

function selectionRestoreOnContextMenu(event) {
  if (event.defaultPrevented || event.pointerType === "touch") return false;
  const x = event.clientX;
  const y = event.clientY;
  const host = document.activeElement;
  const inHost = Boolean(host && (host.contains(event.target) || host.closest?.(".cm-editor")?.contains(event.target)));
  //: A textarea's selection has no geometry, so being inside the field is the
  //: test; a rendered or CodeMirror selection must be under the pointer.
  const hit = host?.tagName === "TEXTAREA" || host?.tagName === "INPUT" ? inHost : inHost && selectionPointInRange(x, y);
  let shown = false;
  if (inHost && hit) {
    const surface = typeof editorSurfaceFor === "function" ? editorSurfaceFor(host) : null;
    if (surface && isEditorSurface(surface) && surface.selectionStart !== surface.selectionEnd && inlineAiState.phase === "idle") {
      selectionBarShow(surface);
      shown = true;
    }
  }
  const field = fieldSelection();
  const domHit = !field && selectionPointInRange(x, y) && !event.target.closest?.(".selection-popup, #selection-bar");
  if ((field && inHost) || domHit) {
    selectionPointerPoint = { x, y };
    syncSelectionPopup();
    shown = shown || Boolean(selectionPopupText);
  }
  if (shown) event.preventDefault();
  return shown;
}

// Open the selection menu from the keyboard, for a Shift+Arrow selection:
// otherwise the menu needed a pointer.
function openSelectionMenuFromKeyboard() {
  syncSelectionPopup();
  if (!selectionPopupText) {
    toast("Select some text first, then press this again.");
    return;
  }
  const opener = selectionPopupEl?.querySelector("[aria-haspopup]");
  const menu = selectionPopupEl?.querySelector(".action-menu");
  if (!opener || !menu) return;
  openActionMenu(menu, opener);
  clampSelectionMenu(menu);
}

//: **The first drag-selection after boot scrolls at the edge too.** The edge
//: scroll is drag-edge.js, a lazy bundle app.js preloads three seconds after
//: boot; a press in a list before it arrives fetches it now and leaves the
//: pressed element here for its top level to pick up while the button is
//: still down, with where the pointer is now, since a hand already resting at
//: the edge sends no further move (qa-1005: the first drag scrolled 0px).
//: drag-edge.js sets `ready` once it can scroll on its own.
const EDGE_SCROLL_HELD = { press: null, ready: false };
document.addEventListener("mousedown", (event) => {
  if (EDGE_SCROLL_HELD.ready || event.button !== 0) return;
  if (!event.target.closest?.("#entry-list, .library-view-section")) return;
  EDGE_SCROLL_HELD.press = { target: event.target, x: event.clientX, y: event.clientY };
  ensureModule("dragEdge");
}, true);
document.addEventListener("mousemove", (event) => {
  if (EDGE_SCROLL_HELD.press) Object.assign(EDGE_SCROLL_HELD.press, { x: event.clientX, y: event.clientY });
}, true);
document.addEventListener("mouseup", () => {
  EDGE_SCROLL_HELD.press = null;
}, true);
