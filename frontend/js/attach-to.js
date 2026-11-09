// attach-to.js: the two inline pickers under a note card that put it on a board
// or in a document ("Put this note on a whiteboard or a mind map", "Add this
// note to a document"). Moved out of capture-ask.js on 2026-10-05 (the
// boot-script gzip budget, ratchet in tests/test_static_compression.py): each
// draws only after a person picks that action from a note's menu. Loaded on
// first use by `LAZY_MODULES.attachTo` (app.js), whose stand-ins for
// `renderAttachToBoard` and `renderAttachToDocument` fetch this file and then
// call the real one. Their one caller (`renderInlineAction`, entry-card.js)
// reads neither's result: both are `async` and fill the `wrap` element it
// already returned, so the picker appears a moment late on the first use of a
// session and on time after that.

//: A picture by its name, for the one store (`/media`) that also holds PDFs.
(() => {
  const NOTE_PICKER_IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg|avif|heic|heif)$/i;

  // The picker's value for "one that doesn't exist yet". A string, so it can
  // never collide with a document id.
  const NEW_DOCUMENT = "new";

  //: **Put this note on a whiteboard or a mind map** (INBOX 246). The note goes
  //: on the board as a card: a `WhiteboardNode` row written from the note's
  //: side, the reference a board already stores, so "Referenced by" reads it
  //: back with no new relation. The shape of `renderAttachToDocument` below,
  //: one idea learned once. **No "new board" option**: a board needs a type and
  //: a name, which is the Library's New board dialog, not a third creator.
  async function renderAttachToBoard(entry, wrap) {
    const status = document.createElement("p");
    status.className = "muted";
    status.textContent = "Loading boards\u2026";
    wrap.appendChild(status);

    const boards = await apiJson("/whiteboard/boards", { silent: true }).catch(() => null);
    if (!boards) {
      status.textContent = "Couldn't load your boards.";
      return;
    }
    //: The unnamed scratch board (`id: null`) is left out: it is where things
    //: land when nobody chose a board, not somewhere to file a note on
    //: purpose, and it has no name to offer in a list.
    const named = boards.filter((board) => board.id != null);
    if (!named.length) {
      status.textContent = "No boards or maps yet. Make one in the Library first.";
      const only = document.createElement("div");
      only.className = "row";
      only.appendChild(
        smallButton("Cancel", "", () => {
          inlineAction = null;
          renderEntries();
        })
      );
      wrap.appendChild(only);
      return;
    }
    status.textContent = "Put this note on:";

    const picker = document.createElement("select");
    for (const board of named) {
      const option = document.createElement("option");
      option.value = String(board.id);
      //: The kind in the label, because the owner asked for whiteboards and
      //: mind maps by name and a list of bare titles does not say which is
      //: which. The word, not an icon: this is an `<option>`, and an option's
      //: text is all it has.
      option.textContent = `${board.title || "Untitled"} (${board.type === "map" ? "map" : "board"})`;
      //: The name on its own, for the toast. The `(board)` half belongs in a
      //: list where two kinds sit together and reads as part of the name
      //: anywhere else: "Put on \u201cHouse jobs (board)\u201d" is not a sentence
      //: somebody wrote.
      option.dataset.title = board.title || "Untitled";
      picker.appendChild(option);
    }

    const row = document.createElement("div");
    row.className = "row";
    row.appendChild(
      smallButton(
        "Attach",
        "Put this note on the chosen board",
        async () => {
          const id = Number(picker.value);
          const title = picker.selectedOptions[0]?.dataset.title || "that board";
          try {
            const card = { entry_id: entry.id, board_id: id, x: 80, y: 80, z: 1 };
            const made = await apiJson("/whiteboard/nodes", {
              method: "POST",
              //: Placed rather than dropped at the origin: every board already
              //: has something at 0,0 sooner or later, and a card that lands
              //: exactly under another one reads as "nothing happened". This is
              //: the same offset the board's own "add a card" starts from, and
              //: the card is draggable the moment it is there.
              body: JSON.stringify(card),
            });
            pushMadeUndo(`Put a note on “${title}”`, ["/whiteboard/nodes", "POST", card], made, (node) => `/whiteboard/nodes/${node.id}`, () => refreshEntries([entry.id]));
            inlineAction = null;
            await refreshEntries([entry.id]);
            toastAction(`Put on \u201c${title}\u201d.`, "Open", () => {
              openWhiteboardBoard(id);
            }, { go: { open: "board", id } });
          } catch (error) {
            toast(error.message, true);
          }
        },
        false
      )
    );
    row.appendChild(
      smallButton("Cancel", "", () => {
        inlineAction = null;
        renderEntries();
      })
    );
    wrap.append(picker, row);
    focusSelect(picker);
  }

  // The other direction, asked for straight after the capture-time picker:
  // "what about adding a document to a note??". A note you wrote weeks ago
  // turns out to belong to something you are writing now, and the capture box
  // is long gone by then.
  async function renderAttachToDocument(entry, wrap) {
    const status = document.createElement("p");
    status.className = "muted";
    status.textContent = "Loading documents…";
    wrap.appendChild(status);

    //: To the end, same reason as `loadCaptureDocuments`.
    const documents = await apiPagedList("/documents", 200).catch(() => null);
    if (!documents) {
      status.classList.add("error");
      status.textContent = "Couldn't load your documents.";
      return;
    }
    const already = new Set((entry.documents || []).map((doc) => doc.id));
    const free = documents.filter((doc) => !already.has(doc.id));

    status.textContent = free.length
      ? "Add this note to:"
      : documents.length
        ? "This note is on all of your documents, or start a new one:"
        : "No documents yet: start one:";
    const picker = document.createElement("select");
    for (const doc of free) {
      const option = document.createElement("option");
      option.value = String(doc.id);
      option.textContent = doc.title || "Untitled";
      picker.appendChild(option);
    }
    // Same offer as the capture box: the document this note belongs to often
    // does not exist until the note makes you realise you want it.
    const fresh = document.createElement("option");
    fresh.value = NEW_DOCUMENT;
    //: No mark at all, and that is the only honest answer here: an `<option>`
    //: may hold text and nothing else, so it cannot carry one of the app's
    //: icons, and a typed one beside a menu of Phosphor is the mismatch this
    //: rule exists to stop. The ellipsis already says "this opens something".
    fresh.textContent = "New document…";
    picker.appendChild(fresh);

    const row = document.createElement("div");
    row.className = "row";
    row.appendChild(
      smallButton(
        "Attach",
        "Add this note to the chosen document",
        async () => {
          let id = picker.value;
          let title = picker.selectedOptions[0]?.textContent || "that document";
          if (id === NEW_DOCUMENT) {
            const made = await createDocumentNamed(entry.content.trim().slice(0, 60));
            if (!made) return;
            id = String(made.id);
            title = made.title;
          }
          try {
            await apiJson(`/documents/${id}/notes`, {
              method: "POST",
              body: JSON.stringify({ entry_id: entry.id }),
            });
            pushUndo(
              `Added a note to “${title}”`,
              async () => {
                await apiJson(`/documents/${id}/notes/${entry.id}`, { method: "DELETE" });
                await refreshEntries([entry.id]);
              },
              async () => {
                await apiJson(`/documents/${id}/notes`, { method: "POST", body: JSON.stringify({ entry_id: entry.id }) });
                await refreshEntries([entry.id]);
              }
            );
            inlineAction = null;
            await refreshEntries([entry.id]);
            toastAction(`Added to “${title}”.`, "Open", () =>
              openDocumentFromNote(Number(id)), { go: { open: "doc", id: Number(id) } }
            );
          } catch (error) {
            toast(error.message, true);
          }
        },
        false
      )
    );
    row.appendChild(
      smallButton("Cancel", "", () => {
        inlineAction = null;
        renderEntries();
      })
    );
    wrap.append(picker, row);
    //: `picker` is a `<select>`, so the same trap: see `focusSelect`. The
    //: `setTimeout` was there to wait for the element to be in the document;
    //: `focusSelect` waits for the frame that gives it its opener, which is the
    //: later of the two events and the one that actually matters.
    focusSelect(picker);
  }

  //: **The Attach panel's list** (Chat's Attach, `openNotePicker`), moved here
  //: from chat-attach.js on 2026-10-05 (op4-1005, the boot-script gzip budget):
  //: it draws only once a person opens the panel. `LAZY_MODULES.attachTo`'s
  //: stand-in for `renderNotePickerList` fetches this file on that first open;
  //: every caller fires it and forgets (none reads its result), so the list
  //: appears a moment late on the first open of a session. The row itself
  //: (`notePickerRow`, pick-row.js, which both bundles name) and each
  //: source's shape stay out of this file: the whiteboard's pickers draw the
  //: same row synchronously.

  async function notePickerRows(source) {
    if (source === "notes") return allEntries; // already in memory
    if (notePickerCache[source]) return notePickerCache[source];
    //: **Maps come from `/whiteboard/boards?type=map`**: a map is an Entry, but
    //: its node count, the fact its row adds over its title, lives only on
    //: `BoardOut`. Read to the end: the filter is server-side, the list a page.
    if (source === "maps") {
      const boards = await apiPagedList("/whiteboard/boards?type=map", 200, { silent: true }).catch(() => null);
      if (!Array.isArray(boards)) return null;
      notePickerCache.maps = boards.filter((b) => b.id != null);
      return notePickerCache.maps;
    }
    //: Files are both tables, the one list every picker shares (library-pick.js).
    if (source === "files") {
      await lazyScript("/js/library-pick.js");
      return (notePickerCache.files = await pickLibraryItemDialog.fileRows());
    }
    const path = source === "documents" ? "/documents" : "/media";
    //: All three are paged, and `apiPagedList` reads each to the end: a picker
    //: that silently cannot reach half the library is worse than a slow one.
    const rows = await apiPagedList(path, 200).catch(() => null);
    if (rows == null) return null;
    let list = Array.isArray(rows) ? rows : rows.documents || [];
    //: Images reach both tables, each row marked with the one it came from.
    //: **The two tables number their rows separately**, so an id alone is not a
    //: picture: a note's picture (an Attachment) was pushed onto the images sent
    //: as `image_media_ids` and the server read that id as a different upload,
    //: and ticking one row lit every row in the other table with the same id.
    //: A note's picture now travels as the file it is (`file_ids`).
    if (source === "images") {
      const attachments = await apiPagedList("/files/gallery", 200).catch(() => []);
      list = [
        ...list
          .filter((row) => NOTE_PICKER_IMAGE_EXT.test(row.original_name || row.url || ""))
          .map((row) => ({ ...row, store: "media" })),
        ...(Array.isArray(attachments) ? attachments : [])
          .filter((row) => (row.mime || "").startsWith("image/"))
          .map((row) => ({ ...row, store: "file" })),
      ];
    }
    notePickerCache[source] = list;
    return list;
  }

  //: How many rows one source draws. Search reaches the rest, and the list says
  //: so rather than ending as if that were everything.
  const NOTE_PICKER_LIMIT = 60;

  //: **One renderer for every source** (INBOX 485, the owner: "that whole panel
  //: needs to be better redesigned"). A row is a leading tile (the source's
  //: icon, the file's own glyph, or the picture), the name over one muted line
  //: of facts, and a check at the right edge that fills when the row is on;
  //: the real checkbox inside is visually hidden, so Space toggles it and a
  //: screen reader hears a checkbox. Images are a grid of the pictures, since a
  //: picture is what tells two of them apart. The list is one tab stop and the
  //: arrows walk it (`notePickerKeydown`).
  async function renderNotePickerList() {
    const search = $("note-picker-search");
    const query = search.value.trim().toLowerCase();
    const list = $("note-picker-list");
    const source = notePickerSource;
    const shape = notePickerShape(source);
    list.classList.toggle("is-grid", Boolean(shape.grid));
    list.setAttribute("aria-label", `Your ${shape.nouns}`);
    if (source !== "notes" && !notePickerCache[source]) {
      const wait = document.createElement("li");
      wait.className = "note-picker-state";
      setLabel(wait, `ph:spin Loading your ${shape.nouns}…`);
      list.replaceChildren(wait);
    }
    const rows = await notePickerRows(source);
    // The source can have been switched while the fetch was in flight.
    if (notePickerSource !== source) return;
    list.replaceChildren();
    if (rows == null) {
      notePickerEmpty(list, `Couldn't load your ${shape.nouns}.`, {
        label: "ph:arrow-clockwise Try again",
        run: () => renderNotePickerList(),
      });
      updateNotePickerCount();
      return;
    }
    // Attached rows stay on top even when the search would not match them, so
    // ticking one never makes it vanish from under the pointer.
    //: A note row holds its first 300 characters; the server's literal match reads the whole text (INBOX 1525 review).
    const served = source === "notes" && query ? noteEngine.literal(noteEngine.pick, query, renderNotePickerList) : null;
    const matches = rows.filter(
      (row) => shape.isOn(row) || !query || shape.search(row).toLowerCase().includes(query) || served?.has(row.id)
    );
    matches.sort((a, b) => (shape.isOn(a) ? 0 : 1) - (shape.isOn(b) ? 0 : 1));
    if (!matches.length) {
      if (query) {
        notePickerEmpty(list, `Nothing in your ${shape.nouns} matches “${search.value.trim()}”.`, {
          label: "ph:x Clear search",
          run: () => {
            search.value = "";
            renderNotePickerList();
            search.focus();
          },
        });
      } else {
        notePickerEmpty(list, shape.empty, shape.upload
          ? { label: "ph:upload-simple Upload one", run: () => $("attach-image")?.click() }
          : null);
      }
    }
    for (const row of matches.slice(0, NOTE_PICKER_LIMIT)) list.appendChild(notePickerRow(shape, row));
    if (matches.length > NOTE_PICKER_LIMIT) {
      const more = document.createElement("li");
      more.className = "note-picker-state note-picker-more";
      more.textContent = `Showing ${NOTE_PICKER_LIMIT} of ${matches.length}. Search to find the rest.`;
      list.appendChild(more);
    }
    notePickerRoving(list, 0);
    updateNotePickerCount();
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { renderAttachToBoard, renderAttachToDocument, renderNotePickerList });
})();
