// note-edit-panels.js: the two panels an open note's edit form shows under the
// text, "Similar" notes and the note's saved links, and the picker that attaches
// a saved link. Moved out of notes-list.js on 2026-10-05 (the boot-script gzip
// budget, ratchet in tests/test_static_compression.py): they draw only after a
// person presses Edit. Loaded on first use, in the same bundle as
// note-panels.js (`LAZY_MODULES.notePanels`, app.js; `similarNoteRow` is
// there), whose stand-ins for `renderRelatedWhileEditing` and
// `renderNoteBookmarksWhileEditing` fetch this file and then call the real
// one. `renderEditForm` calls both and reads neither's result (they are
// `async` and fill a panel they append themselves), so a stand-in's promise is
// the shape they already return; the panels appear a moment late on the first
// Edit of a session and on time after that.
// The edit form's formatting strip (`noteEditToolbar`, `NOTE_EDIT_TOOLBAR`, last in this
// file) moved here from notes-list.js the same day: `renderEditForm` is its only caller.

// **A related-notes panel, live while a note is open for editing**, asked
// for as a competitor gap (Mem.ai's own "AI Thought Partner" pitch keeps a
// similar-notes rail visible continuously while writing, not behind a
// click). This app already had the same signal one click away
// (`toggleRelated`'s "≈ Similar notes" menu item, same `/entries/{id}/related`
// endpoint): the gap was that it stayed hidden until asked for, so it read
// as a lookup rather than a thing the app was already thinking about. Shown
// automatically the moment the edit form opens, not gated behind a second
// interaction; a note with nothing similar says so rather than leaving a
// blank space that looks broken.
async function renderRelatedWhileEditing(li, entry) {
  const panel = document.createElement("div");
  panel.className = "entry-related-live muted text-sm";
  setLabel(panel, "ph:spin Finding related notes…");
  //: Above the form's foot (INBOX 606), which stays the last row.
  li.insertBefore(panel, li.querySelector(":scope > .note-edit-foot"));
  let related;
  try {
    related = await apiJson(`/entries/${entry.id}/related`);
  } catch {
    panel.remove(); // a failed lookup says nothing rather than "no notes found"
    return;
  }
  // The form may have closed (Save/Cancel) or moved on to a different note
  // while this was in flight.
  if (editingId !== entry.id || !panel.isConnected) return;
  panel.replaceChildren();
  if (!related.length) {
    panel.textContent = "No related notes yet.";
    return;
  }
  //: **Folded into one line until asked for** (INBOX 616, the owner: Related
  //: was "three large rows" under the text): "3 suggested links" with a caret,
  //: and the notes as compact chips with a + each once it is opened.
  panel.classList.add("note-edit-related");
  const list = document.createElement("div");
  list.className = "note-edit-related-list";
  list.hidden = true;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ghost small note-edit-related-toggle";
  toggle.setAttribute("aria-expanded", "false");
  const say = () => {
    const n = list.querySelectorAll(".entry-related-row").length;
    if (!n) {
      panel.textContent = "All related notes are linked.";
      return;
    }
    setLabel(toggle, `${list.hidden ? "ph:caret-right" : "ph:caret-down"} ${n} suggested link${n === 1 ? "" : "s"}`);
  };
  toggle.addEventListener("click", () => {
    list.hidden = !list.hidden;
    toggle.setAttribute("aria-expanded", String(!list.hidden));
    say();
  });
  for (const other of related) list.appendChild(similarNoteRow(entry, other, say));
  panel.append(toggle, list);
  say();
}

// **A note's References** (§30, directly requested: "attach a bookmark to
// a note... show up in References"): the saved-links half of what a note
// can point at, alongside `entry.links`' [[wiki links]] to other notes.
// Its own small panel and its own endpoint (`/entries/{id}/bookmarks`),
// not folded into `entry.links`, a Bookmark isn't an Entry (see the
// Bookmark model's own docstring), so this is a second, parallel kind of
// reference rather than a variant of the first.
async function renderNoteBookmarksWhileEditing(li, entry) {
  const panel = document.createElement("div");
  panel.className = "entry-related-live muted text-sm";
  li.insertBefore(panel, li.querySelector(":scope > .note-edit-foot"));

  //: In the form's foot, a quiet icon at its left (INBOX 606: a lone boxed
  //: button under everything else).
  const attachButton = document.createElement("button");
  attachButton.type = "button";
  attachButton.className = "ghost small icon-only";
  setLabel(attachButton, "ph:link-simple-horizontal");
  attachButton.title = "Attach a link";
  attachButton.setAttribute("aria-label", "Attach a link");
  attachButton.addEventListener("click", () => openBookmarkAttachPicker(entry, refresh));

  async function refresh() {
    let attached;
    try {
      attached = await apiJson(`/entries/${entry.id}/bookmarks`);
    } catch {
      return;
    }
    if (editingId !== entry.id || !panel.isConnected) return;
    panel.replaceChildren();
    if (attached.length) {
      const label = document.createElement("span");
      label.textContent = "References: ";
      panel.appendChild(label);
      for (const bookmark of attached) {
        // safeHref(): same scheme guard as library.js's bookmark rows
        // (INBOX 310), so an already-stored bad-scheme bookmark can't reach
        // window.open() from this chip either.
        const bmChip = chip(`ph:link ${bookmark.title || bookmark.url}`, "link", () =>
          window.open(safeHref(bookmark.url), "_blank", "noopener,noreferrer")
        );
        bmChip.title = bookmark.url;
        const detach = document.createElement("span");
        detach.className = "unlink";
        setLabel(detach, "ph:x"); // raw "×" glyph vs Phosphor icon font mismatch mis-centers the icon
        detach.title = "Remove this reference";
        detach.setAttribute("aria-label", `Remove reference to ${bookmark.title || bookmark.url}`);
        detach.addEventListener("click", async (e) => {
          e.stopPropagation();
          const path = `/entries/${entry.id}/bookmarks/${bookmark.id}`;
          const gone = await apiJson(path, { method: "DELETE" }).catch((error) => {
            toast(error.message, true);
            return null;
          });
          if (!gone) return;
          refresh();
          //: Undo puts it back where it was in the list (undo-1005): the
          //: DELETE answers with when it was attached, the order References
          //: are listed in. The panel repaints only while this note is open.
          const repaint = () => { if (editingId === entry.id && panel.isConnected) refresh(); };
          const reattach = async () => {
            await apiJson(`/entries/${entry.id}/bookmarks`, { method: "POST", body: JSON.stringify({ bookmark_id: bookmark.id, created_at: gone.created_at }) });
            repaint();
          };
          const action = pushUndo(`Removed the reference to ${bookmark.title || bookmark.url}`, reattach, async () => {
            await apiJson(path, { method: "DELETE" });
            repaint();
          });
          toastAction("Reference removed.", "Undo", async () => {
            settleUndoFromToast(action);
            await reattach().catch((error) => toast(error.message, true));
          });
        });
        makeUnlinkAccessible(detach);
        bmChip.appendChild(detach);
        panel.appendChild(bmChip);
      }
    }
    panel.hidden = !attached.length;
    const foot = li.querySelector(":scope > .note-edit-foot");
    if (foot) {
      if (!attachButton.isConnected) foot.prepend(attachButton);
    } else {
      panel.hidden = false;
      panel.appendChild(attachButton);
    }
  }
  await refresh();
}

//: **The app's one-thing picker on its Bookmarks source** (INBOX 616, the
//: owner: "the note edit form attach a link button doesnt do anything"). It
//: put a bare select into the References panel, which is hidden while the
//: note has no reference, so the first press drew nothing anyone could see,
//: and a pick re-ran the whole panel, which added a second Attach button. The
//: picker dialog (`pickLibraryItemDialog`, selection.js) is what the "/"
//: menu's bookmark link already uses; its empty state says where links come
//: from. `done` repaints the one panel this form already has.
async function openBookmarkAttachPicker(entry, done) {
  const chosen = await pickLibraryItemDialog("Attach a link", { sources: ["link"] });
  const id = chosen?.row?.id;
  if (id == null || editingId !== entry.id) return;
  try {
    await apiJson(`/entries/${entry.id}/bookmarks`, {
      method: "POST",
      body: JSON.stringify({ bookmark_id: Number(id) }),
    });
    const repaint = () => (editingId === entry.id ? done() : null);
    pushUndo(
      "Attached a link to a note",
      async () => {
        await apiJson(`/entries/${entry.id}/bookmarks/${Number(id)}`, { method: "DELETE" });
        repaint();
      },
      async () => {
        await apiJson(`/entries/${entry.id}/bookmarks`, { method: "POST", body: JSON.stringify({ bookmark_id: Number(id) }) });
        repaint();
      }
    );
  } catch (error) {
    toast(error.message, true);
    return;
  }
  toast("Link attached.");
  done();
}

//: **A note's text as the edit form holds it** (meetings-644 audit, item 6):
//: the property block aside, the leading heading as the Title, the rest as the
//: body. A note of a type opens with its `---` block, so the heading was never
//: at offset 0 and the Title stayed empty, and the block's raw lines were the
//: first thing in the box (until the editor mounted and hid them, if it did).
//: The block is the Properties sheet's to edit; the form puts it back on save.
function noteFormParts(content) {
  const source = String(content || "");
  const afterBlock = stripFrontmatter(source);
  const heading = /^\n*#[ \t]+([^\n]+)\n*/.exec(afterBlock);
  return {
    block: source.slice(0, source.length - afterBlock.length),
    title: heading ? heading[1].trim() : "",
    body: heading ? afterBlock.slice(heading[0].length) : afterBlock,
  };
}

//: The note edit form, moved from notes-list.js (boot gzip): `entryItem`
//: reaches it through its stand-in (`LAZY_ENTRY_POINTS.notePanels`), and the
//: bundle is fetched a few seconds after boot so the first Edit is not a wait.
function renderEditForm(li, entry) {
  const draft = noteFormDraft && noteFormDraft.id === entry.id ? noteFormDraft : null;
  noteFormDirty = Boolean(draft);
  //: **A title field, as Capture has** (INBOX 432: renaming a note meant
  //: finding and editing its "# " line by hand). Not a stored field: the
  //: leading heading is split off into it and put back on save, the shape
  //: `withTitle` writes in Capture, so the two cannot disagree.
  //: The property block is held aside and the heading looked for after it
  //: (`noteFormParts`, meetings-644 audit item 6).
  const parts = noteFormParts(entry.content);
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.maxLength = 200;
  titleInput.className = "note-edit-title";
  titleInput.dataset.autocorrect = ""; // autocorrect.js serves it
  titleInput.placeholder = "Title";
  titleInput.setAttribute("aria-label", "Title: becomes the note's leading heading");
  titleInput.value = draft ? draft.title : parts.title;
  titleInput.addEventListener("input", () => { noteFormDirty = true; });
  const textarea = document.createElement("textarea");
  textarea.rows = 3;
  textarea.setAttribute("aria-label", "Note text"); // its editor takes this name (noteSurfaceName)
  textarea.value = draft ? draft.content : parts.body;
  textarea.addEventListener("input", () => { noteFormDirty = true; });
  //: A stable id, because three separate features key off one: the "/" menu
  //: and the `[[` autocomplete (EDITOR_SURFACES in editor.js), the selection
  //: bar, and this form's own toolbar. Safe to be a constant rather than a
  //: per-note id: `editingId` allows exactly one open edit form at a time.
  textarea.id = "entry-edit-content";
  textarea.className = "note-edit-box";
  textarea.dataset.autocorrect = "";
  //: Ctrl+B/Ctrl+I/Ctrl+Shift+S, same as the capture box (documents.js:
  //: `wireMdFormatShortcuts`). Passed the element itself, not its id: this
  //: textarea is not in the document yet, and a fresh one exists every
  //: time a note is opened for editing, so this runs on every open rather
  //: than once at boot.
  if (typeof wireMdFormatShortcuts === "function") wireMdFormatShortcuts(textarea);
  //: Three rows is a form field; a note is prose. Grows with its content the
  //: way the composer does, up to the same shared ceiling.
  textarea.addEventListener("input", () => autoGrow(textarea));
  //: `requestAnimationFrame`, not `queueMicrotask`: a microtask runs before
  //: the browser has laid anything out, and `autoGrow` reads `scrollHeight`,
  //: which is 0 on an element that is not yet in the document, measured, the
  //: box stayed at its three-row height with the note scrolling inside it.
  //: Also on focus, because a note opened while its list was hidden (a tab
  //: switch, a filter) is laid out only when it becomes visible.
  textarea.addEventListener("focus", () => autoGrow(textarea));
  requestAnimationFrame(() => autoGrow(textarea));

  //: **Tags are chips with one input** (INBOX 606, the owner: the edit form
  //: "still feels off", with a long comma field in the screenshot). The comma
  //: string the save reads stays in a hidden input; each tag is a `.chip.tag`
  //: that removes itself on a press, and Enter, a comma or leaving the field
  //: makes a chip of what was typed; Backspace in an empty field takes the last.
  //: **No well, no leading '#'** (INBOX 616: a boxed field with a '#' icon
  //: beside chips that each say '#', and no room inside it): the chips and the
  //: input sit on the properties line under the title, one chip height.
  const tagsInput = document.createElement("input");
  tagsInput.type = "hidden";
  tagsInput.value = draft ? draft.tags : entry.tags.join(", ");
  const tagField = document.createElement("div");
  tagField.className = "tag-field note-edit-tags";
  const tagEntry = document.createElement("input");
  tagEntry.type = "text";
  tagEntry.className = "note-edit-tag-input";
  tagEntry.placeholder = "Add tag";
  tagEntry.setAttribute("aria-label", "Add a tag");
  tagEntry.autocomplete = "off";
  tagField.append(tagsInput, tagEntry);
  const tagList = () => tagsInput.value.split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean);
  const setTags = (tags) => {
    tagsInput.value = [...new Set(tags)].join(", ");
    noteFormDirty = true;
    keepDraft();
    drawTagChips();
  };
  const commitTag = () => {
    const typed = tagEntry.value.split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean);
    tagEntry.value = "";
    if (!typed.length) return;
    setTags([...tagList(), ...typed]);
    //: A tag just entered: the tag list (tag-suggest.js) stays shut until the
    //: next key or press in the field, rather than opening every tag over Save.
    tagEntry.dataset.tagged = "1";
  };
  for (const type of ["focus", "pointerdown"]) tagEntry.addEventListener(type, () => delete tagEntry.dataset.tagged);
  function drawTagChips() {
    for (const old of tagField.querySelectorAll(".chip")) old.remove();
    for (const tag of tagList()) {
      const tagChip = chip(`#${tag}`, "tag", () => {
        setTags(tagList().filter((t) => t !== tag));
        tagEntry.focus();
      });
      tagChip.append(Object.assign(document.createElement("i"), { className: "ph ph-x" }));
      tagChip.title = `Remove #${tag}`;
      tagChip.setAttribute("aria-label", `Remove tag ${tag}`);
      tagField.insertBefore(tagChip, tagEntry);
    }
  }
  drawTagChips();
  tagEntry.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commitTag();
    } else if (event.key === "Backspace" && !tagEntry.value && tagList().length) {
      setTags(tagList().slice(0, -1));
    }
  });
  //: A suggestion taken from the tag list (tag-suggest.js) arrives as "tag, ".
  tagEntry.addEventListener("input", () => {
    noteFormDirty = true;
    if (tagEntry.value.includes(",")) commitTag();
  });
  tagEntry.addEventListener("blur", commitTag);
  if (focusTagsAfterRender === entry.id) {
    focusTagsAfterRender = null;
    // The form is not in the document yet; focus once it is.
    requestAnimationFrame(() => tagEntry.focus());
  }
  if (focusBodyAfterRender === entry.id) {
    focusBodyAfterRender = null;
    requestAnimationFrame(() => {
      const surface = noteSurfaceIfAny(textarea);
      if (surface) surface.focus();
      else textarea.focus();
    });
  }

  const categorySelect = document.createElement("select");
  fillCategoryOptions(categorySelect, entry.category);
  categorySelect.setAttribute("aria-label", "Category");
  if (draft && [...categorySelect.options].some((o) => o.value === draft.category)) {
    categorySelect.value = draft.category;
  }
  categorySelect.addEventListener("change", () => { noteFormDirty = true; });
  //: **The category is its chip** (INBOX 606): the note card's own category
  //: chip, dot and name, opening a menu of the categories. The select is the
  //: value `resolveCategoryChoice` reads, never in the page.
  const categoryChip = chip("", "category note-edit-category", (event) => {
    event.stopPropagation();
    const box = categoryChip.getBoundingClientRect();
    const items = [...categorySelect.options].map((option) => ({
      group: option.value === "__new__" ? "new" : "pick",
      label: `${option.value === "__new__" ? "ph:plus" : option.selected ? "ph:check" : "ph:folder-simple"} ${option.textContent.replace(/^\+ /, "")}`,
      run: async () => {
        let value = option.value;
        if (value === "__new__") {
          const name = await promptDialog("Name for the new category", "", { confirmLabel: "Create" });
          if (!name) return;
          const made = Object.assign(document.createElement("option"), { value: name, textContent: name });
          categorySelect.insertBefore(made, option);
          value = name;
        }
        categorySelect.value = value;
        categorySelect.dispatchEvent(new Event("change"));
      },
    }));
    openMenuAtPoint(items, "Category", box.left, box.bottom + 4);
  });
  categoryChip.setAttribute("aria-haspopup", "menu");
  const drawCategoryChip = () => {
    const name = categorySelect.value;
    const label = categorySelect.selectedOptions[0]?.textContent || "Let Atlas decide";
    categoryChip.replaceChildren(
      Object.assign(document.createElement("span"), { className: "ph-text", textContent: label }),
      Object.assign(document.createElement("i"), { className: "ph ph-caret-down" })
    );
    categoryChip.setAttribute("aria-label", `Category: ${label}`);
    if (name) paintCategoryDot(categoryChip, name);
  };
  drawCategoryChip();
  categorySelect.addEventListener("change", drawCategoryChip);
  const keepDraft = () => {
    noteFormDraft = { id: entry.id, title: titleInput.value, content: textarea.value, tags: tagsInput.value, category: categorySelect.value };
    keepNoteEditLocally(noteFormDraft);
  };
  for (const field of [titleInput, textarea]) field.addEventListener("input", keepDraft);
  categorySelect.addEventListener("change", keepDraft);

  const row = document.createElement("div");
  row.className = "row";
  const saveButton = (
    smallButton(
      "Save changes",
      "Save your corrections",
      async () => {
        commitTag();
        const category = await resolveCategoryChoice(categorySelect);
        if (category === undefined) return; // user cancelled the prompt
        //: An emptied box used to save as "Note saved." while quietly
        //: keeping the old text (INBOX 432). Said instead, with the way to
        //: actually remove a note.
        //: The held block goes back on top, unless the box now has a block
        //: of its own (typed, or a draft kept before the block was held).
        const typed = textarea.value.trim();
        const written = (stripFrontmatter(typed) === typed ? parts.block : "") + withTitle(typed, titleInput.value);
        if (!written.trim()) {
          toast("A note needs some text. To remove it, use Move to bin in its menu.", "info");
          return;
        }
        const before = { content: entry.content, category: entry.category, tags: entry.tags };
        const after = {
          content: written,
          category,
          tags: tagsInput.value.split(",").map((t) => t.trim()).filter(Boolean),
        };
        //: `base_hash`: the text this form opened on, so a save over a
        //: newer text from another window is refused rather than silently
        //: replacing it (WORLD_CLASS_PLAN 22.1 item 5); the prompt then
        //: decides: "keep mine" saves again from the other window's text,
        //: "take theirs" puts that text in the form to go on from.
        let base = entry.content_hash;
        let saved = null;
        for (;;) {
          try {
            saved = await api(`/entries/${entry.id}`, {
              method: "PUT",
              body: JSON.stringify({ ...after, base_hash: base, ai_assisted: textarea.dataset.aiTouched === "1" }),
            });
            break;
          } catch (error) {
            if (!isEditConflict(error)) throw error;
            const current = error.detail.current;
            const answer = await editConflictPrompt({ noun: "note", mine: after.content, theirs: current.content || "" });
            if (answer === "mine") {
              base = current.content_hash;
              continue;
            }
            if (answer === "theirs") {
              Object.assign(entry, current);
              Object.assign(parts, noteFormParts(current.content));
              titleInput.value = parts.title;
              textarea.value = parts.body;
              noteFormDirty = false;
            }
            return;
          }
        }
        editingId = null;
        noteFormDirty = false;
        noteFormDraft = null;
        forgetNoteEditLocally();
        toast("Note saved.");
        offerWikiRename(entry.id, await saved?.json?.().catch(() => null));
        await refreshEntries([entry.id]);
        pushEntryPutUndo(entry.id, "Edited a note", before, after);
      },
      false
    )
  );
  //: Ctrl+Enter saves, as it does in the capture box (INBOX 432): the edit
  //: form had no chord at all, so a note opened from the list could only be
  //: saved with the mouse. The editor view forwards the chord here.
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveButton.click();
    }
  });
  //: Escape closes the form, asking first when it has changes (INBOX 432:
  //: it did nothing). Bubbling, and only when nothing inside took it first,
  //: so the "/" menu, the [[ list and the editor's own Escape still win.
  li.addEventListener("keydown", async (event) => {
    if (event.key !== "Escape" || event.defaultPrevented || editingId !== entry.id) return;
    if (document.querySelector(".action-menu:not(.hidden), #editor-menu:not(.hidden)")) return;
    event.preventDefault();
    if (await noteFormMayClose()) closeNoteForm();
  });
  row.append(
    smallButton("Cancel", "Discard changes", async () => {
      if (await noteFormMayClose()) closeNoteForm();
    }),
    saveButton
  );

  //: **The properties line**, under the title inside the surface (INBOX 616,
  //: the owner: "the core concepts dropdown is completely out of place"): the
  //: category chip, then the tags, then the add-tag input, one chip height,
  //: wrapping as one line. The foot under everything: the panels' Attach a
  //: link at its left, the word count, then Cancel and the one filled Save at
  //: its right (INBOX 606: Save sat mid-row between the fields and Cancel).
  const meta = document.createElement("div");
  meta.className = "note-edit-meta";
  row.classList.add("note-edit-actions");
  meta.append(categoryChip, tagField);
  //: **The tags turned down on this note, each one press from coming back**
  //: (the owner, 2026-10-10: "is there a way to undo it or see the list of
  //: things not to show again"). At the end of the properties line, quiet,
  //: only when there are any.
  if (entry.discarded_tags?.length) {
    const down = document.createElement("span");
    down.className = "muted note-edit-turned-down";
    down.append("Not suggested:");
    for (const tag of entry.discarded_tags) {
      const back = chip(`ph:arrow-counter-clockwise #${tag}`, "", () => answerTags(entry, { restore: [tag] }));
      back.title = `Suggest #${tag} for this note again`;
      down.append(" ", back);
    }
    meta.append(down);
  }
  //: Words and reading time while the note is open (WORLD_CLASS_PLAN 5 item
  //: 9): the count a document's head carries, for a note, at the documents'
  //: 220 words a minute; the properties block is not prose, so not counted.
  const count = document.createElement("span");
  count.className = "char-count muted note-edit-count note-edit-counts";
  count.setAttribute("aria-live", "polite");
  const recount = () => {
    const words = wordCount(stripFrontmatter(`${titleInput.value}
${textarea.value}`));
    const minutes = words / 220;
    const read = !words ? "" : minutes < 1 ? " · under a min" : ` · ${Math.round(minutes)} min read`;
    count.textContent = `${words.toLocaleString()} word${words === 1 ? "" : "s"}${read}`;
  };
  recount();
  for (const field of [titleInput, textarea]) field.addEventListener("input", recount);
  const foot = document.createElement("div");
  foot.className = "note-edit-foot";
  foot.append(count, row);
  const toolbarEl = noteEditToolbar(textarea.id);
  //: Preview: reported: "there is no preview", then, once there was one,
  //: "if the formatting bar was the same, the preview button would be in
  //: it". So there is no second Write / Preview control any more: the
  //: cloned strip's own Preview button is the switch, exactly as in the
  //: capture box and the document editor, and it renders the textarea's
  //: current text with the same renderer every note card uses.
  //: The cloned strip's Source button (wiring.js `setNoteSource`): the same
  //: one choice as Capture's, for every note box. The edit box renders as you
  //: type, so there is no Preview to switch to (INBOX 430).
  const sourceBtn = toolbarEl.querySelector("[data-note-preview]");
  sourceBtn?.addEventListener("click", () => setNoteSource(!noteSourceOn()));
  if (sourceBtn) {
    sourceBtn.setAttribute("aria-pressed", String(noteSourceOn()));
    sourceBtn.classList.toggle("is-active", noteSourceOn());
  }
  //: Attachment cards for the files this note's text points at, the same
  //: cards and the same menu as the capture box (INBOX 440 (2)).
  const chipsHost = document.createElement("div");
  chipsHost.className = "att-cards hidden";
  chipsHost.id = "entry-edit-attachment-chips";
  chipsHost.setAttribute("role", "group");
  chipsHost.setAttribute("aria-label", "Files in this note");
  //: **One writing surface** (INBOX 606): the title, the properties line, the
  //: strip and the text in the capture box's own `.note-composer`, which
  //: carries the edge, the ground and the focus ring for all of them.
  const surface = document.createElement("div");
  surface.className = "note-composer note-edit-surface";
  surface.append(titleInput, meta, toolbarEl, textarea);
  li.append(surface, chipsHost, foot);
  //: The editor's offers (quickadd.js `noteOffersAttach`): a form
  //: opened before the bundle loads has none rather than an error.
  if (typeof noteOffersAttach === "function") noteOffersAttach(textarea, { after: surface, category: categorySelect, entryId: entry.id });
  // The same line-number gutter the capture box and the documents editor
  // carry (documents.js `mountGutterFor`); it follows the one remembered
  // choice, so a person who turned numbers on in Capture sees them here too.
  //: On the next frame, not now: this <li> is still detached (`entryItem`
  //: returns it to the list renderer), and `applyDocGutter` walks the
  //: document to set the strip button's pressed state: measured, the button
  //: opened with no state and no title until the first click without this.
  //:
  //: **Both are lazy entry points** (`LAZY_ENTRY_POINTS`). `applyDocGutter`
  //: was not, so before the Library bundle had loaded this line threw a
  //: ReferenceError in the middle of `renderEntries` and left the list half
  //: drawn: the owner's "the first time I try editing a note after a restart,
  //: the notes page goes blank". The mount is awaited so the strip exists
  //: when the pressed state is set.
  Promise.resolve(mountGutterFor(textarea)).then(() => requestAnimationFrame(() => applyDocGutter()));
  renderEntryAttachmentChips(textarea, chipsHost);
  textarea.addEventListener("input", () => renderEntryAttachmentChips(textarea, chipsHost));
  renderRelatedWhileEditing(li, entry);
  renderNoteBookmarksWhileEditing(li, entry);
}

// Moved from notes-list.js (boot gzip): the edit form's Cancel and Escape are its callers.
function closeNoteForm() {
  //: The focus goes back to the note (WCAG 2.4.3): the redraw removes the form
  //: that held it.
  const back = editingId;
  const held = document.activeElement;
  const wasInside = !held || held === document.body || Boolean(held.closest?.("#entry-list"));
  editingId = null;
  noteFormDirty = false;
  noteFormDraft = null;
  forgetNoteEditLocally();
  renderEntries();
  if (back != null && wasInside) focusNoteRow(back);
}

//: **An edit survives a reload** (INBOX 648, the owner: "unsaved edits
//: survive tab switch, reload and a server restart"; found by the e2e flow
//: pass, tests-e2e/specs/notes.spec.js). The Capture box kept its draft on
//: this device and the edit form did not: the browser asked before a reload,
//: and a Leave (or the desktop window closed, which asks nothing) lost the
//: edit for good. Each change is kept here until Save or Cancel, and the
//: next start offers it back, once, beside the note it belongs to.
const NOTE_EDIT_KEPT = "note-edit-draft";

function keepNoteEditLocally(draft) {
  prefs.setJSON(NOTE_EDIT_KEPT, { ...draft, at: Date.now() });
}

function forgetNoteEditLocally() {
  prefs.remove(NOTE_EDIT_KEPT);
}

//: Run once, when this file arrives (app.js preloads it three seconds after
//: start). A kept edit whose text is already the note's (saved from another
//: window, say) is dropped without a word.
//: **Only a note that is gone, or already equal, lets the copy go.** A
//: server that restarted since the last visit answers the first requests
//: with 401 until the person signs in (sessions live in memory), and this
//: runs three seconds after start, on a slow boot while the lock screen is
//: still up: the failed read counted as "no such note" and threw the kept
//: edit away (found by tests-e2e/specs/draft-recovery.spec.js). A locked
//: or unreachable server keeps the copy; a lock waits for the unlock, which
//: runs `startApp` again.
const keptEdit = { awaitsUnlock: false };
const startAppBeforeKeptEdit = window.startApp;
window.startApp = async function () {
  const opened = startAppBeforeKeptEdit ? await startAppBeforeKeptEdit.apply(this, arguments) : undefined;
  if (keptEdit.awaitsUnlock) {
    keptEdit.awaitsUnlock = false;
    offerKeptNoteEdit();
  }
  return opened;
};

async function offerKeptNoteEdit() {
  const kept = prefs.json(NOTE_EDIT_KEPT, {});
  if (!Number.isInteger(kept.id) || editingId !== null) return;
  let note = null;
  try {
    note = await apiJson(`/entries/${kept.id}`, { silent: true });
  } catch (error) {
    if (error.isLockout) keptEdit.awaitsUnlock = true;
    if (error.isLockout || error.status !== 404) return;
  }
  const keptText = withTitle(String(kept.content || "").trim(), kept.title);
  //: The form holds a typed note's block aside, so a kept body is the note's
  //: text after its block.
  if (!note || keptText === note.content || (note.content.startsWith("---") && note.content.endsWith(`\n${keptText}`))) {
    forgetNoteEditLocally();
    return;
  }
  const name = kept.title || noteNamePlain(note.content, 40) || "a note";
  toastAction(`Your unsaved changes to “${name}” were kept.`, "Open them", async () => {
    await switchTab("notes");
    showNotesSection("browse");
    if (!(await openNoteEditor(kept.id))) return;
    //: After the open, which clears any draft for a different note.
    noteFormDraft = { id: kept.id, title: kept.title, content: kept.content, tags: kept.tags, category: kept.category };
    keepNoteEditLocally(noteFormDraft);
    renderEntries();
  });
}
offerKeptNoteEdit();


//: **The formatting row the note edit form never had.**
//:
//: Editing an existing note is the most common editing action in a notebook,
//: and it was the app's poorest surface by a distance: a bare three-row
//: textarea with no toolbar, no "/" menu and no selection bar, while the
//: composer beside it and the document editor both had all three. That is
//: most of what *"the editors feel very fake and just rudimentary"* is about.
//:
//: The same `data-md` contract the other two toolbars use, wired here rather
//: than through `initMarkdownToolbars` (documents.js) because that runs once
//: over the markup at load and this row is built each time a note is opened.
//: The same set the document editor's strip carries (minus colours), in
//: the same groups: asked for: "the ui and features when editing a note
//: need to be updated with the new upgraded formatting toolbar". `null`
//: entries are group separators.
const NOTE_EDIT_TOOLBAR = [
  { md: "h1", label: "ph:text-h-one", title: "Heading 1 (Ctrl+1)" },
  { md: "h2", label: "ph:text-h-two", title: "Heading 2 (Ctrl+2)" },
  { md: "h3", label: "ph:text-h-three", title: "Heading 3 (Ctrl+3)" },
  null,
  { md: "bold", label: "ph:text-b", title: "Bold (Ctrl+B)" },
  { md: "italic", label: "ph:text-italic", title: "Italic (Ctrl+I)" },
  { md: "strike", label: "ph:text-strikethrough", title: "Strikethrough" },
  { md: "highlight", label: "ph:highlighter", title: "Highlight" },
  { md: "code", label: "ph:code", title: "Inline code (Ctrl+E)" },
  { md: "clearformat", label: "ph:eraser", title: "Clear highlight and colour" },
  null,
  { md: "ul", label: "ph:list-bullets", title: "Bulleted list" },
  { md: "ol", label: "ph:list-numbers", title: "Numbered list" },
  { md: "task", label: "ph:check-square", title: "Task list" },
  { md: "quote", label: "ph:quotes", title: "Quote" },
  null,
  { md: "link", label: "ph:link", title: "Link" },
  { md: "table", label: "ph:table", title: "Table (Tab moves between cells)" },
  { md: "codeblock", label: "ph:brackets-curly", title: "Code block" },
  { md: "hr", label: "ph:minus", title: "Divider" },
];

function noteEditToolbar(boxId) {
  //: **The same strip as the capture box, cloned**, reported: "the toolbar
  //: isn't the same as the note capture and documents". The capture strip
  //: (`#note-toolbar`) is the source of truth; a clone drops the extras the
  //: mount appended (their listeners do not survive cloning) and is wired
  //: fresh by `wireMarkdownToolbar`, which mounts them again. The hand-built
  //: list below is only the fallback for a page without that strip.
  const source = document.getElementById("note-toolbar");
  if (source && typeof wireMarkdownToolbar === "function") {
    const clone = source.cloneNode(true);
    clone.removeAttribute("id");
    //: `note-toolbar` is kept on the clone: it is what makes this the
    //: *composer's* strip rather than the full-page editor's, and dropping it
    //: gave a form inside a note card the document editor's own chrome padding
    //: (measured 91px against the composer's 88 at the same width, both above
    //: a small box). Reported with the capture strip beside it.
    clone.className = "doc-toolbar note-toolbar note-edit-toolbar";
    clone.setAttribute("aria-label", "Formatting");
    for (const extra of clone.querySelectorAll("[data-md-extra]")) extra.remove();
    //: **The Source button stays in the strip**, marked because the id is
    //: stripped two lines down and renderEditForm wires it (INBOX 430: it was
    //: Preview, a pane the box already is).
    clone.querySelector("#entry-preview-toggle")?.setAttribute("data-note-preview", "1");
    //: **Every id goes.** A clone carries the capture strip's ids, and two
    //: elements with one id means `document.getElementById` hands back the
    //: *capture* toolbar's control: so the edit form's dropdowns opened and
    //: then applied their formatting to the capture box instead of the note
    //: being edited (reported: "none of the toolbar dropdowns work"). Nothing
    //: in `wireMarkdownToolbar` needs an id; it walks elements.
    for (const el of clone.querySelectorAll("[id]")) el.removeAttribute("id");
    delete clone.dataset.mdExtras;
    clone.dataset.mdTarget = boxId;
    //: The wrap/collapse group is appended by `mountDocToolbarControls`, so a
    //: clone carries a *dead* copy of it -- two arrow buttons whose listeners
    //: did not survive cloning -- and, because it was cloned in place rather
    //: than appended, it sat mid-strip where the capture bar's sits last.
    //: Dropped and re-mounted, which is the same trick `data-md-extra` plays
    //: for the dropdown menus.
    clone.querySelector(".doc-toolbar-tools")?.remove();
    wireMarkdownToolbar(clone);
    if (typeof mountDocToolbarControlsFor === "function") mountDocToolbarControlsFor(clone);
    return clone;
  }
  const bar = document.createElement("div");
  bar.className = "doc-toolbar note-toolbar note-edit-toolbar";
  bar.setAttribute("role", "toolbar");
  bar.setAttribute("aria-label", "Formatting");
  for (const action of NOTE_EDIT_TOOLBAR) {
    if (!action) {
      const sep = document.createElement("span");
      sep.className = "doc-toolbar-sep";
      sep.setAttribute("aria-hidden", "true");
      bar.appendChild(sep);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.md = action.md;
    button.title = action.title;
    button.setAttribute("aria-label", action.title);
    setLabel(button, action.label);
    //: mousedown-preventDefault keeps the caret in the textarea, the same
    //: rule `initMarkdownToolbars` and the selection bar both follow, and for
    //: the same reason: a click moves focus first and the selection is gone.
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => applyMarkdown(action.md, boxId));
    bar.appendChild(button);
  }
  return bar;
}
