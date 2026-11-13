// entry-menu.js: the rows of a note card's "..." menu (`entryOverflowMenu`,
// menus.js), moved out of the boot scripts on 2026-11-01 for the gzip budget
// (tests/test_static_compression.py). The card draws only its opener at boot;
// the first press awaits `ensureModule("entryMenu")` and calls this, and the
// first pointer over a card warms the file (lazy-entries.js), so the press
// finds it in. About 50 nodes per menu, built once per card on its first open.

function fillEntryMenu(menu, entry) {
  // Kept flat: the three actions used often enough, or serious enough (a
  // delete), that burying them a level down would cost more than the
  // grouping below saves. Everything else groups into three side flyouts, 
  // asked for directly, to cut what had grown into a 15-item flat list.
  const topLevel = [
    // Direct instruction: a way into multi-select from the row itself,
    // not only the toolbar's own "Select" button: which is real and
    // already works, but requires knowing it exists and is above the
    // list rather than on the note someone actually wants to start
    // selecting from. Reuses that exact same mode (`enterSelectMode`,
    // `selectedIds`) rather than inventing a second one, and seeds it
    // with this note already checked, so choosing "Select" here is a
    // head start rather than an empty selection identical to the
    // toolbar button's own.
    {
      label: "ph:check-square Select",
      title: "Start selecting multiple notes, beginning with this one",
      run: () => {
        enterSelectMode();
        selectedIds.add(entry.id);
        updateBatchCount();
        renderEntries();
      },
    },
    //: Beside Select, not inside the Add flyout (audit 1028 S12): a copy of
    //: the note is an action on it, found where the note's other actions are.
    {
      label: "ph:copy Duplicate",
      title: "Make a copy of this note, opens ready to edit",
      run: async () => {
        closeActionMenus();
        try {
          //: The whole note: a list row holds its first 300 characters (`fullEntry`, INBOX 1525).
          const { content } = await fullEntry(entry.id);
          const copy = await apiJson("/entries", {
            method: "POST",
            body: JSON.stringify({
              //: The copy's title is its first "# " line: the API takes no
              //: `title`, so the "(Copy)" this sent was dropped and the two
              //: notes were indistinguishable (INBOX 432).
              content: /^#\s+\S/.test(content || "")
                ? content.replace(/^#\s+[^\n]*/, (line) => `${line.trimEnd()} (copy)`)
                : content,
              category: entry.category,
              tags: entry.tags || [],
            }),
          });
          await loadEntries();
          pushEntryCreateUndo(copy, "Duplicated a note");
          // Open the new note in edit mode straight away.
          if (copy && copy.id) {
            flashEntry(copy.id);
            await openNoteEditor(copy.id);
          }
          toast("Note duplicated.");
        } catch (err) {
          toast(err.message || "Couldn't duplicate note.", true);
        }
      },
    },
    //: The one correction a notebook that files for you is asked for most
    //: (INBOX 432); the card's category chip opens the same sheet.
    {
      label: "ph:folder-open Move to category",
      title: `Now in ${entry.category || "Uncategorised"}; choose another`,
      run: () => chooseNoteCategory([entry.id], entry.category),
    },
    //: A note with three or more headings gets a way to jump to one (S74).
    ...(fillEntryMenu.headingCount(entry) >= 3
      ? [{ label: "ph:list-dashes Headings", title: "Jump to a heading in this note", run: () => fillEntryMenu.headings(entry) }]
      : []),
    //: Inside a private space the switch is locked on: no per-note opt-out (INBOX 1727).
    spacesCache.find((space) => space.id === entry.workspace_id)?.is_private
      ? { label: "ph:lock Private in this space", title: "Move it out of this space to share it", disabled: true, run: () => toast("Move it out of this space to share it.") }
      : {
          label: entry.is_private ? "ph:lock-open Make readable" : "ph:lock Make private",
          title: entry.is_private
            ? "Decrypt this note so search and Atlas can use it again"
            : "Encrypt this note at rest, and keep it out of search and Atlas",
          run: () => toggleEntryPrivacy(entry),
        },
    {
      // Sits above History because it is the more common question by far:
      // "what else is this about?" is asked of a note every time it is
      // read, and "what did it used to say?" only when something looks
      // wrong.
      label: "ph:graph Connections",
      title: "Everything this note is joined to, links both ways, documents, boards and files",
      // The note's own title when it wrote one, and its first words
      // otherwise: `notePreviewText` alone hands back both lines of a
      // titled note ("Probe A\nrelates to sourdough"), which reads as
      // two sentences jammed together on one line of the dialog.
      run: () =>
        lazyScript("/js/connections.js").then(() => openConnections(
          "entries",
          entry.id,
          entry.title || noteNamePlain(entry.content, 80)
        )),
    },
    {
      label: "ph:clock-counter-clockwise History",
      title: "See earlier versions of this note, and put one back",
      run: () => openEntryHistory(entry),
    },
    // BACKLOG.md §95 item D.14: "Full export exists. There is no way to
    // hand one note to someone." Same route shape and same "download,
    // not navigate" pattern the Documents kebab's own "Download .md"
    // already uses (library.js).
    {
      label: "ph:download-simple Download .md",
      title: "Save a copy of this note as a markdown file",
      run: () => downloadFromApi(`/entries/${entry.id}/export.md`, "note.md"),
    },
  ];

  //: With no model the app does these itself and the menu says so (O7;
  //: BACKLOG "The composer does Improve writing and Generate title").
  const off = aiIsOff();
  const aiItems = [
    ...(entry.is_private ? [] : [
    {
      //: **Named for what it does, not for what it is called internally**
      //: (INBOX 292, the owner: "i feel like it is more than just
      //: re-evaluating, and it is hidden away"). The route re-files the
      //: note, refreshing its confidence and its category unless the person
      //: filed it themselves, *and* suggests tags and links for them to
      //: apply. "Re-evaluate" named the smallest part of that, and tags,
      //: the part it is actually reached for, were not in the name at all.
      label: off ? "ph:tag Tag and file" : "ph:sparkle Tag and file with Atlas",
      title: "Atlas re-reads the note, suggests tags and links, and may refile it",
      run: () => reevaluateEntry(entry),
    },
    {
      label: off ? "ph:text-aa Proofread" : "ph:sparkle Improve writing",
      title: off ? "Spelling and capitals put right with no model; rewording needs one" : "Proofread or rewrite this note with AI",
      run: async () => {
        if (!(await openNoteEditor(entry.id))) return;
        // The edit textarea now exists, improve it in place.
        const box = document.querySelector(`#entry-list li[data-id="${entry.id}"] textarea`);
        if (box) openImprove(box);
      },
    },
    {
      // Recognising a title the note already wrote (a leading `# Heading`)
      // is free; writing one costs a real model call, so it's this
      // separate, on-request action rather than something automatic.
      label: off ? "ph:text-h Title from its words" : entry.title ? "ph:sparkle Regenerate title" : "ph:sparkle Generate title",
      title: off ? "A title taken from the note's first sentence, with no model" : "Write a short title for this note with AI",
      run: () => generateEntryTitle(entry),
    },
    ...(entry.title
      ? [
          {
            label: "ph:x Remove title",
            title: "Take the title back out, the note's text is unchanged",
            run: () => removeEntryTitle(entry),
          },
        ]
      : []),
    ]),
    //: Every act Atlas does is here, whichever thing it acts on (INBOX 1518,
    //: N20): reading, mapping, asking and translating, with no model where
    //: the app does it itself.
    //: Section 17 row 6: the note read aloud, then what it links to and why.
    { label: "ph:speaker-high Explain this note", title: "Read it aloud, then what it links to and why", run: () => explainNote(entry) },
    //: OPEN row 566: the note's headings and lists as a mind map, the same
    //: build as the agent's `map_from_note`, so no model is needed.
    ...(entry.is_private ? [] : [{
      label: "ph:tree-structure Make a mind map",
      title: "A mind map of this note: its title in the centre, its headings and lists as branches",
      run: async () => {
        try {
          const board = await apiJson(`/whiteboard/maps/from-note/${entry.id}`, { method: "POST" });
          pushBinPairUndo("Made a mind map from a note", `/entries/${board.id}`, `/entries/${board.id}/restore`, true, () => refreshEntries([board.id]));
          await openWhiteboardBoard(board.id);
        } catch (err) {
          toast(err.message || "Couldn't make a mind map of this note.", true);
        }
      },
    }]),
    {
      label: "ph:chat-circle Ask Atlas about this note",
      title: "Start a chat about this note and what it connects to",
      run: () => askAtlasAboutNote(entry),
    },
    //: Left off with no model: translating needs one (INBOX 1488).
    ...(aiIsOff() ? [] : [{
      label: "ph:translate Translate",
      title: "Open this note in the Writing room, set to translate",
      run: () => translateNoteInDesk(entry),
    }]),
  ];

  const connectItems = [
    {
      label: "ph:file-text Add to a document",
      title: "Attach this note to a document you have already started",
      run: () => {
        inlineAction = inlineActionIs(entry.id, "document")
          ? null
          : { id: entry.id, kind: "document" };
        renderEntries();
      },
    },
    {
      //: INBOX 246's first sentence. Next to "Add to a document" because
      //: it is the same act on the other kind of surface, and the note
      //: stays exactly where it is either way.
      label: "ph:squares-four Add to a board or map",
      title: "Put this note on a whiteboard or a mind map",
      run: () => {
        inlineAction = inlineActionIs(entry.id, "board")
          ? null
          : { id: entry.id, kind: "board" };
        renderEntries();
      },
    },
    {
      label: "ph:file-text Expand into a document",
      title: "Start a document from this note, the note stays where it is",
      run: () => expandNoteIntoDocument(entry),
    },
    { label: "ph:link Link to another", run: () => beginOrCompleteLink(entry) },
    //: The way to point at this note from another one, ready to paste
    //: (INBOX 432: there was no copy link at all). Its name as `[[` finds
    //: it, the title or the first words.
    {
      label: "ph:brackets-square Copy wiki link",
      title: "Copy a [[wiki link]] to this note, to paste into another note or document",
      run: async () => {
        const name = noteNamePlain(entry.title || entry.content).slice(0, 80).trim();
        if (await copyToClipboard(`[[${name}]]`)) toast("Link copied. Paste it into any note.");
      },
    },
    appLinkMenuItem("note", entry.id),
    { label: "ph:approximate-equals Similar notes", run: () => toggleRelated(entry) },
    {
      label: "ph:arrow-u-up-left Referenced by",
      title: "Documents, notes, boards and maps that point at this note",
      run: () => toggleReferences(entry),
    },
    {
      label: "ph:hourglass-medium Forgotten notes like this",
      title: "Notes you have not looked at in a long time that are close to this one",
      run: () => toggleFaded(entry),
    },
    //: **The note's two other homes, one press away** (INBOX 393: "there
    //: needs to be more integration between all the main features"). The
    //: menu could put a note on a board, in a document and in a reminder,
    //: and could not take it to the graph that draws it or to the chat that
    //: answers about it.
    {
      label: "ph:graph Show in graph",
      title: "Open the graph centred on this note, its links lit",
      run: () => showNoteInGraph(entry.id),
    },
  ];

  const addItems = [
    //: A meeting's sheet (INBOX 644): its action items, decisions,
    //: Summarise and Record into it. The meeting chip opens the same.
    ...(noteIsMeeting(entry)
      ? [{ label: "ph:users-three Meeting", run: () => openMeetingSheet(entry.id) }]
      : []),
    //: KG4: the note's properties and type, as a table.
    {
      label: "ph:list-bullets Properties",
      title: "Fields at the top of this note (status, due, a type's fields), kept in its text",
      run: () => openNotePropertiesSheet(entry),
    },
    //: Section 17 row 1: settle a filing from the note itself.
    ...(entryNeedsReview(entry)
      ? [{
        label: "ph:check-circle Accept the filing",
        title: `Keep it in ${entry.category}; it leaves the review queue`,
        run: async () => {
          const accepted = await apiJson(`/review-queue/${entry.id}/accept`, { method: "POST" }).catch((e) => toast(e.message, true));
          if (accepted !== undefined) {
            const settle = (value) => async () => {
              await apiJson(`/entries/${entry.id}/filing`, { method: "POST", body: JSON.stringify({ accepted: value }) });
              await refreshEntries([entry.id]);
            };
            pushUndo(`Kept a note in ${entry.category}`, settle(false), settle(true));
          }
          await refreshEntries([entry.id]);
          toast(`Kept in ${entry.category}.`);
        },
      }]
      : []),
    {
      label: "ph:plus Add context",
      title: "Append detail: Atlas may refile it",
      run: () => {
        inlineAction = inlineActionIs(entry.id, "context") ? null : { id: entry.id, kind: "context" };
        renderEntries();
      },
    },
    {
      label: "ph:arrow-bend-down-right Continue thought",
      title: "Start or extend a thread from this note",
      run: () => {
        inlineAction = inlineActionIs(entry.id, "continue") ? null : { id: entry.id, kind: "continue" };
        renderEntries();
      },
    },
    {
      label: "ph:alarm Remind me",
      run: () => {
        inlineAction = inlineActionIs(entry.id, "remind") ? null : { id: entry.id, kind: "remind" };
        renderEntries();
      },
    },
    { label: "ph:paperclip Attach a file", run: () => attachFileTo(entry) },
    { label: "ph:images-square Attach from Library", run: () => attachFromLibrary(entry) },
  ];

  // Not destructive, so not grouped with "danger" below: but visually
  // adjacent to it (asked for directly: a way to keep a note but get it
  // out of the way, distinct from binning it) so the two "get this off my
  // list" actions sit together rather than one being buried in a group.
  const archive = entry.archived_at
    ? {
        label: "ph:arrow-u-up-left Unarchive",
        title: "Bring this note back into your notebook",
        run: async () => {
          await apiJson(`/entries/${entry.id}/unarchive`, { method: "POST" });
          pushRoutePairUndo("Unarchived a note", [`/entries/${entry.id}/archive`, "POST"], [`/entries/${entry.id}/unarchive`, "POST"], () => refreshEntries([entry.id]));
          await refreshEntries([entry.id]);
          toast("Unarchived.");
        },
      }
    : {
        label: "ph:archive Archive",
        title: "Keep it, but out of the way, not the bin",
        //: Undoable like Move to bin beside it (INBOX 432), and it says
        //: where the note went, since nothing in the Notes tab shows it.
        run: async () => {
          const archive = async () => {
            await apiJson(`/entries/${entry.id}/archive`, { method: "POST" });
            await refreshEntries([entry.id]);
          };
          const unarchive = async () => {
            await apiJson(`/entries/${entry.id}/unarchive`, { method: "POST" });
            await refreshEntries([entry.id]);
          };
          await archive();
          const action = pushUndo("Archived a note", unarchive, archive);
          toastAction("Archived. Find it in Library, Archived.", "Undo", async () => {
            settleUndoFromToast(action);
            await unarchive();
          });
        },
      };

  const danger = {
    label: "ph:trash Move to bin",
    danger: true,
    run: () => binNoteWithUndo(entry),
  };

  //: Three groups, broken by the same hairline `kebabMenu` draws for a
  //: grouped menu (DESIGN.md: past five rows a menu is grouped): what you
  //: do to this note, the three families that open further, and the two
  //: that put it away. Ten rows read as one list before this (menus.js).
  const rule = () => {
    const sep = document.createElement("div");
    sep.className = "menu-sep";
    sep.setAttribute("role", "separator");
    return sep;
  };
  //: History and Download .md are the two rarest rows: one flyout; Connections joins Connect (INBOX 1469).
  const keep = topLevel.splice(-2);
  const connections = topLevel.pop();
  for (const item of topLevel) menu.appendChild(buildMenuItemButton(item));
  menu.appendChild(buildMenuGroupButton("ph:clock-counter-clockwise History and export", keep));
  menu.appendChild(rule());
  //: A private note never goes to a model: the server refuses retitling
  //: and re-filing one, so the menu does not offer what would only toast
  //: a refusal (sweep 1004).
  if (aiItems.length) menu.appendChild(buildMenuGroupButton("ph:sparkle AI actions", aiItems));
  menu.appendChild(buildMenuGroupButton("ph:link Connect", [connections, ...connectItems]));
  menu.appendChild(buildMenuGroupButton("ph:plus Add", addItems));
  menu.appendChild(rule());
  menu.appendChild(buildMenuItemButton(archive));
  menu.appendChild(buildMenuItemButton(danger));
}

//: **Headings (S74).** The card draws the text after its title line, so the title's own heading is not one to jump to.
//: A clipped row carries the server's count of the whole text (`heading_count`); a whole row is counted here.
fillEntryMenu.headingCount = function (entry) {
  const titled = entry.title ? 1 : 0;
  if (entry.content_truncated) return Math.max(0, (entry.heading_count ?? 0) - titled);
  return mdTocEntries(entry.title ? bodyWithoutTitleLine(entry.content) : stripFrontmatter(entry.content)).length;
};

//: Contents recipe (`mdTocElement`) in a sheet: a link per heading, indented by level; a press closes the sheet and
//: brings that heading to the top of the card, opened out (the card is one paragraph of text, so each heading line is
//: a `.note-heading` span, notes-list.js).
fillEntryMenu.headings = async function (entry) {
  let whole;
  try {
    whole = await fullEntry(entry.id);
  } catch (error) {
    toast(error.message || "Couldn't read that note.", true);
    return;
  }
  const entries = mdTocEntries(whole.title ? bodyWithoutTitleLine(whole.content) : stripFrontmatter(whole.content));
  openSheet({
    label: "Headings",
    sub: entry.title || noteNamePlain(whole.content, 80),
    name: "note-headings",
    build: (card, close) => {
      const toc = mdTocElement();
      toc.querySelector(".md-toc-head").remove();
      const list = toc.querySelector(".md-toc-list");
      const top = entries.length ? Math.min(...entries.map((e) => e.level)) : 1;
      entries.forEach((heading, index) => {
        const item = document.createElement("li");
        item.className = `md-toc-item md-toc-depth-${Math.min(3, heading.level - top)}`;
        const link = document.createElement("a");
        link.href = "#";
        link.textContent = heading.text;
        link.addEventListener("click", (event) => {
          event.preventDefault();
          close();
          fillEntryMenu.jump(entry.id, index, entries.length, heading.text);
        });
        item.appendChild(link);
        list.appendChild(item);
      });
      card.appendChild(toc);
    },
  });
};

fillEntryMenu.jump = async function (id, index, total, text) {
  const row = document.querySelector(`li[data-id="${id}"]`);
  const content = row?.querySelector(".entry-content");
  if (!content) return;
  const more = row.querySelector(".entry-more");
  if (more && more.textContent === "Show more") more.click();
  await content.fillWhole?.();
  const spans = [...content.querySelectorAll(".note-heading")];
  //: By place when the card drew every heading the text holds; by words when markup (a table, a column) shifted them.
  const target = spans.length === total ? spans[index] : spans.find((s) => s.textContent.trim() === text.trim());
  target?.scrollIntoView({ block: "start", behavior: reducedMotionWanted() ? "auto" : "smooth" });
};

// Moved here from menus.js with the rows that call them (gzip budget, laglist-1108).
async function toggleEntryPrivacy(entry) {
  const makingPrivate = !entry.is_private;
  if (makingPrivate) {
    const ok = (await confirmDialog(
      "Make this note private?\n\n" +
        "It gets encrypted with a key derived from your password, so it stays " +
        "unreadable in the database, in backups, and to anyone without that " +
        "password.\n\n" +
        "It also stops appearing in search and stops being given to Atlas.\n\n" +
        "There is no recovery: if you forget your password this note is gone."
    ));
    if (!ok) return;
  }
  // Both directions need the key, which a session without a password lacks.
  if (!(await ensureVaultOpen())) return;
  try {
    await apiJson(`/entries/${entry.id}/privacy`, {
      method: "POST",
      body: JSON.stringify({ private: makingPrivate }),
    });
    const setPrivacy = (value) => async () => {
      await apiJson(`/entries/${entry.id}/privacy`, { method: "POST", body: JSON.stringify({ private: value }) });
      await refreshEntries([entry.id]);
    };
    pushUndo(makingPrivate ? "Made a note private" : "Made a note readable", setPrivacy(!makingPrivate), setPrivacy(makingPrivate));
    toast(makingPrivate ? "Note encrypted." : "Note is readable again.");
    await refreshEntries([entry.id]);
  } catch (error) {
    toast(error.message, true);
  }
}

// Reported: no popup shows when a title is regenerated.
//
// There WAS a toast, and it was being swallowed. `toast()` drops anything
// that is not an error while notifications are muted, which is right for
// background chatter and wrong here: this is the result of a button the user
// just pressed, and a direct action that reports nothing reads as a broken
// button. Muting is about noise you did not ask for.
//
// The "Generating…" toast is also worth keeping distinct from the settled one:
// this call waits on the model, so it can take seconds, and a control that
// looks inert for seconds gets pressed again.
async function generateEntryTitle(entry) {
  const regenerating = Boolean(entry.title);
  try {
    toast(regenerating ? "Regenerating the title…" : "Generating a title…", false, {
      exempt: true,
    });
    const was = (await fullEntry(entry.id)).content; // the undo puts back the whole text, not a list row's first 300 characters
    const updated = await apiJson(`/entries/${entry.id}/generate-title`, { method: "POST" });
    if (updated?.content) pushEntryPutUndo(entry.id, "Titled a note", { content: was }, { content: updated.content });
    await refreshEntries([entry.id]);
    flashEntry(entry.id);
    const title = updated && updated.title;
    toast(title ? `Titled “${title}”.` : "Titled.", false, { exempt: true });
    // And in the notification centre, so the result survives the 5.5 seconds
    // the toast lives for, the model can finish while you are on another tab.
    recordNotification({
      kind: "task",
      title: regenerating ? "Title regenerated" : "Title generated",
      detail: title ? `“${title}”` : `Note #${entry.id}`,
    });
  } catch (error) {
    toast(error.message || "Couldn't generate a title.", true);
  }
}

async function removeEntryTitle(entry) {
  try {
    const was = (await fullEntry(entry.id)).content;
    const updated = await apiJson(`/entries/${entry.id}/remove-title`, { method: "POST" });
    if (updated?.content) pushEntryPutUndo(entry.id, "Removed a title", { content: was }, { content: updated.content });
    await refreshEntries([entry.id]);
    flashEntry(entry.id);
    // Said out loud: it was silent.
    toast("Title removed.", false, { exempt: true });
  } catch (error) {
    toast(error.message || "Couldn't remove the title.", true);
  }
}

//: Moved here from the boot files (W27): only this file calls them.
function inlineActionIs(id, kind) {
  return inlineAction && inlineAction.id === id && inlineAction.kind === kind;
}

//: **Translate a note from where it is read** (INBOX 405). Writing room
//: already translates; this takes the note there, loaded and set to the last
//: language picked, rather than asking the reader to copy it across. Nothing
//: runs until Draft is pressed, like every other starting point on the desk,
//: and a desk that already holds writing is asked about before it is
//: replaced.
async function translateNoteInDesk(entry) {
  entry = await fullEntry(entry.id).catch(() => entry); // the list holds a preview (INBOX 1525)
  if (entry.content_truncated) return;
  const busy = $("draft-thoughts").value.trim() || $("draft-text").value.trim();
  if (busy && !(await confirmDialog("Replace what is in the Writing room with this note?"))) return;
  switchTab("notes");
  showNotesSection("writing-room");
  $("draft-thoughts").value = entry.content || "";
  $("draft-text").value = "";
  $("draft-kind").value = draftTranslateKind();
  $("draft-kind").dispatchEvent(new Event("change"));
  saveDraftLocally();
  toast("Pick the language in the menu beside Draft, then press Draft.");
  $("draft-kind").closest(".select-shell")?.querySelector("button")?.focus();
}

// Moved from note-cards.js (boot gzip budget, L611): this menu row is its one caller.
//: Start a chat about one note. Named by its title in the words a person
//: would use, so the agent's own search tools find it, rather than pasting the
//: whole note into the box.
function askAtlasAboutNote(entry) {
  const name = (entry.title || noteNamePlain(entry.content) || "this note").trim();
  askAtlasAboutThing("note", name);
}
