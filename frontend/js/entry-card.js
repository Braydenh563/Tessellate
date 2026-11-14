// entry-card.js: a note's card (`entryItem`: the row's text, facts line, tag chips,
// actions, meeting glance and every control on it), with `tagAddChipKind` and
// `meetingGlance` that only it reads. Moved out of note-cards.js on 2026-11-01
// for the boot gzip budget (tests/test_static_compression.py, audit row 21).
// Lazy (bundle `entryCard`, lazy-entries.js): `renderEntries` (notes-list.js)
// waits for it and draws once it is in, the phone's note page and a document's
// embedded note wait the same way, and the bundles that carry answer-kit.js list
// it first (`clickableResult` draws a card).

//: Brief 89: which add-tags chip a card draws. "add" is the empty note's
//: "Add tags" (the edit form, cursor in the tags field), "more" the quiet
//: "+ Tag" for a note with one or two tags, or with none but suggestions
//: showing; null from three tags up, on a board or draft, and on a read-only
//: row (a fact only, drawn by the empty-state branch).
const TAG_ADD_BELOW = 3;
function tagAddChipKind(entry, options) {
  if (!options.actions || entry.is_board || entry.is_draft) return null;
  const tags = (entry.tags || []).length;
  if (tags >= TAG_ADD_BELOW) return null;
  return !tags && !(entry.suggested_tags || []).length ? "add" : "more";
}

//: **A meeting card shows what the meeting settled, not its raw headings**
//: (libr-1011 row 1238: `## Agenda` and `## Notes` printed as text). The four
//: sections of `entry/meetings.py` read for one line each: the first agenda
//: item, the decisions, and the action items still open. Null for anything
//: that is not a meeting, so every other card is unchanged.
const MEETING_GLANCE_SECTIONS = {
  agenda: "agenda", notes: "notes", discussion: "notes", transcript: "notes",
  decisions: "decisions", decided: "decisions",
  "action items": "actions", actions: "actions", "action points": "actions", "to do": "actions", todo: "actions", "next steps": "actions",
};

function meetingGlance(entry) {
  const types = (entry?.properties?.type || []).map((value) => String(value).toLowerCase());
  if (!types.includes("meeting")) return null;
  const sections = { agenda: [], decisions: [], actions: [] };
  let current = "";
  for (const line of stripFrontmatter(entry.content || "").split("\n")) {
    const heading = /^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$/.exec(line);
    if (heading) {
      current = MEETING_GLANCE_SECTIONS[heading[1].toLowerCase()] || "";
      continue;
    }
    if (current && sections[current] && line.trim()) sections[current].push(line);
  }
  const plain = (line) => line.replace(/^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+(?:\[[ xX]\][ \t]*)?/, "").trim();
  const rows = [];
  if (sections.agenda.length) rows.push({ label: "Agenda", text: plain(sections.agenda[0]) + (sections.agenda.length > 1 ? ` (+${sections.agenda.length - 1})` : "") });
  if (sections.decisions.length) rows.push({ label: "Decisions", text: `${sections.decisions.length}: ${plain(sections.decisions[0])}` });
  const open = sections.actions.filter((line) => /^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+\[ \]/.test(line));
  const done = sections.actions.filter((line) => /\[[xX]\]/.test(line)).length;
  if (open.length) rows.push({ label: "Open actions", text: `${open.length}: ${plain(open[0])}` });
  else if (done) rows.push({ label: "Actions", text: `all ${done} done` });
  return rows.length ? rows : [{ label: "", text: "Nothing written yet." }];
}

//: **Copy a note's text** (INBOX 1525 review). A clipped list row holds 300 characters, so the whole text is read first,
//: and the clipboard takes a promise of it inside the press itself (a write after an await loses the press in Safari).
//: A read that fails says why; with no `ClipboardItem` the text is read, then copied by `copyToClipboard`.
entryItem.copyText = async (entry) => {
  const clipped = entry.content_truncated;
  const text = clipped ? fullEntry(entry.id).then((whole) => whole.content) : entry.content;
  try {
    if (!clipped || typeof ClipboardItem === "undefined" || !navigator.clipboard?.write) throw 0;
    const blob = text.then((t) => new Blob([t], { type: "text/plain" }));
    blob.catch(() => {});
    await navigator.clipboard.write([new ClipboardItem({ "text/plain": blob })]);
    toast("Note copied.");
  } catch {
    try {
      if (await copyToClipboard(await text)) toast("Note copied.");
    } catch (error) {
      toast(error.message, true);
    }
  }
};

//: Moved here from lightbox.js (unslop 1103, boot gzip): its one caller is below, in the lazy note card.
// The inline result of a re-evaluate: new confidence, plus tag and link
// suggestions the user applies with a click (nothing is applied on its own).
function renderInlineAction(entry) {
  const wrap = document.createElement("div");
  wrap.className = "inline-action";

  if (inlineAction.kind === "reevaluate") {
    renderReevaluateResult(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "document") {
    renderAttachToDocument(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "board") {
    renderAttachToBoard(entry, wrap);
    return wrap;
  }

  if (inlineAction.kind === "remind") {
    const shown = stripFrontmatter(entry.content).trim();
    const preview = shown.length > 40 ? shown.slice(0, 39) + "…" : shown;
    const textInput = document.createElement("input");
    textInput.type = "text";
    textInput.value = `Follow up: ${preview}`;
    const dueInput = document.createElement("input");
    dueInput.type = "datetime-local";
    dueInput.value = defaultDueValue();
    const row = document.createElement("div");
    row.className = "row";
    row.appendChild(
      smallButton("Set reminder", "", async () => {
        //: A refusal (a time already gone) is said, not an unhandled rejection.
        try {
          if (!(await addReminder(textInput.value.trim(), dueInput.value, entry.id))) return;
        } catch (error) {
          if (!error.isLockout) toast(error.message || "Couldn't set that reminder.", true);
          return;
        }
        inlineAction = null;
        renderEntries();
      }, false)
    );
    row.appendChild(
      smallButton("Cancel", "", () => {
        inlineAction = null;
        renderEntries();
      })
    );
    wrap.append(textInput, dueInput, row);
    setTimeout(() => textInput.focus(), 0);
    return wrap;
  }

  const isContext = inlineAction.kind === "context";

  const textarea = document.createElement("textarea");
  textarea.rows = 2;
  textarea.placeholder = isContext
    ? "Add detail: Atlas re-reads the whole note and may refile it…"
    : "Continue this train of thought…";
  wrap.appendChild(textarea);

  const row = document.createElement("div");
  row.className = "row";
  row.appendChild(
    smallButton(
      isContext ? "Add context" : "Add to thread",
      "",
      async () => {
        const text = textarea.value.trim();
        if (!text) return;
        try {
          if (isContext) {
            const updated = await apiJson(`/entries/${entry.id}/context`, {
              method: "POST",
              body: JSON.stringify({ text }),
            });
            toast(
              updated.category === entry.category
                ? `Context added: still filed under “${updated.category}”.`
                : `Context added: refiled under “${updated.category}”.`
            );
          } else {
            await apiJson("/entries", {
              method: "POST",
              body: JSON.stringify({ content: text, parent_id: entry.id }),
            });
            toast("Thread continued.");
          }
          inlineAction = null;
          await loadEntries();
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
  wrap.appendChild(row);
  setTimeout(() => textarea.focus(), 0);
  return wrap;
}

//: **An open edit form is never redrawn** (the notes.spec.js edit-form flake). A redraw
//: (filing event, change poll, late refresh) built the form again: a bare textarea whose
//: editor mounts only on a focus nobody gave it, a click on it losing its target. The
//: form's row is kept here and handed back, unless the redraw is a fresh open (a focus
//: request pending) or the form was closed since (`editingId` moved).

function entryItem(entry, options = {}) {
  if (entryItem.live?.dataset.id == entry.id) {
    if (editingId !== entry.id) entryItem.live = null;
    else if (options.actions && focusBodyAfterRender !== entry.id && focusTagsAfterRender !== entry.id
      && (!entryItem.live.isConnected || entryItem.live.parentElement.id === "entry-list")) return entryItem.live;
  }
  const li = document.createElement("li");
  li.dataset.id = entry.id;
  if (rowEnterIds && rowEnterIds.size && !rowEnterIds.has(String(entry.id))) li.classList.add("row-enter");
  if (entry.id === linkSource) li.classList.add("link-source");
  // The phone's swipe underlays read their words from the row (`initRowSwipe`,
  // 10-responsive.css): what a swipe right and a swipe left will do to it.
  if (entry.pinned) li.classList.add("is-favourite-row");
  if (CATEGORY_PALETTE[entry.colour]) {
    li.dataset.colour = entry.colour;
    li.style.setProperty("--swatch", CATEGORY_PALETTE[entry.colour]);
  }
  if (!entry.is_board && !entry.is_draft && options.actions) {
    li.dataset.swipeRight = entry.pinned ? "Unfavourite" : "Favourite";
    li.dataset.swipeLeft = "Bin";
  }
  // An opened-out row renders as the full card, see `expandedRows`. The
  // class does nothing in card view, where every note is already this shape.
  if (expandedRows.has(entry.id)) li.classList.add("row-expanded");

  if (editingId === entry.id && options.actions) {
    //: **Placeholders while the form's own file arrives** (qa-1005). Before
    //: app.js's preload, or on a slow disk, `renderEditForm` is the lazy
    //: stand-in, which answers with a promise and draws later: the card fell
    //: to a 15px empty strip and the notes under it jumped up and back
    //: (188px, then 15, then 277, with note-edit-panels.js held 3s). The
    //: real function draws at once and answers nothing, so only the
    //: stand-in's promise puts placeholders up.
    entryItem.live = li;
    const drawn = renderEditForm(li, entry);
    if (drawn instanceof Promise) {
      showSkeletons(li, 2);
      drawn.finally(() => clearSkeletons(li));
    }
    return li;
  }

  // The row's own open/close control. Rendered always and only *shown* in
  // rows view (CSS), since the view can change without a re-render. A direct
  // child of `<li>`, pinned to the card's top-left (`.row-expand`,
  // 01-forms-settings.css): inside `.entry-meta` it jumped from the row's
  // right edge to the card's bottom on every expand (owner: "keep its
  // position even when expanded").
  {
    const open = expandedRows.has(entry.id);
    const expand = document.createElement("button");
    expand.type = "button";
    expand.className = "ghost small icon-only row-expand";
    //: One glyph in both states; `.row-expanded` turns it (INBOX 676).
    setLabel(expand, "ph:caret-down");
    expand.title = open ? "Show less of this note" : "Show the whole note here";
    expand.setAttribute("aria-label", expand.title);
    expand.setAttribute("aria-expanded", String(open));
    expand.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleRowExpanded(entry.id);
      //: A pointer press leaves no focus behind: kept, it held the row's
      //: :focus-within actions open until a click elsewhere (the owner,
      //: 2026-10-07). A keyboard press (detail 0) keeps its focus.
      if (event.detail) expand.blur();
    });
    li.appendChild(expand);
  }

  // Click on a row's own body toggles it, as the button does (owner's ask).
  // Rows view only (`.entry-list.is-rows`, checked live: the view can change
  // after this card was built), and not when the click landed on something
  // with its own job: a link, button, image, selected text, the checkbox.
  li.addEventListener("click", (event) => {
    if (event.target.closest("a, button, input, textarea, .chip, img, .unlink")) return;
    if (window.getSelection()?.toString()) return; // a text selection, not a click
    // **In select mode the whole card is the checkbox.** Direct instruction:
    // "when I have selected on the 'select' button in the notes tab, I want
    // to be able to click on the whole body of the note to select it, not
    // the select radiobutton in the corner." Asking someone to hit a 16px
    // box in the corner of a card they are already pointing at is the
    // slowest possible way to tick twenty notes, and every list that has a
    // batch mode (Finder, Gmail, Photos) lets the row itself carry it.
    //
    // Checked before the rows-view guard below, and in every view: the
    // expand-on-click behaviour is a *rows* affordance, but selecting is
    // what the card means while this mode is on, so it takes precedence
    // wherever it is shown.
    if (selectMode && options.actions) {
      const check = li.querySelector(".select-check");
      if (check) {
        check.checked = !check.checked;
        // `change` does not fire for a programmatic `.checked`, and the
        // checkbox's own listener is the single place that owns the set.
        check.dispatchEvent(new Event("change", { bubbles: true }));
        li.classList.toggle("is-selected", check.checked);
      }
      return;
    }
    if (!li.closest(".entry-list.is-rows")) return;
    toggleRowExpanded(entry.id);
  });

  // Batch select mode (Wave M): a checkbox leads each card.
  if (options.actions && selectMode) {
    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "select-check";
    check.checked = selectedIds.has(entry.id);
    check.setAttribute("aria-label", "Select this note");
    check.addEventListener("change", () => {
      if (check.checked) selectedIds.add(entry.id);
      else selectedIds.delete(entry.id);
      // The card carries the selected look, so it has to follow the box
      // whichever of the two was actually clicked.
      li.classList.toggle("is-selected", check.checked);
      updateBatchCount();
    });
    li.appendChild(check);
    li.classList.add("selectable");
    li.classList.toggle("is-selected", check.checked);
  }

  // A note's own leading `# Heading` becomes its title (asked for directly).
  // Not a separate field to edit, the body below is shown with that line
  // taken out, so the title isn't just the same text shown twice.
  if (entry.title) {
    // A <p>, not <h3>, `.card h3` is this app's small-caps *section label*
    // treatment (DESIGN.md's hierarchy), which is the wrong voice for a
    // note's own title: it read as a muted, uppercase eyebrow instead of
    // the prominent heading a title should be. `.entry-title` below defines
    // its own look rather than inheriting one built for a different job.
    const titleEl = document.createElement("p");
    titleEl.className = "entry-title";
    titleEl.textContent = entry.title;
    li.appendChild(titleEl);
    //: A daily note's title is its day (timeline.js, `dailyNoteTitle`), and
    //: the day before and after are one press away (WORLD_CLASS_PLAN D6).
    if (/^\d{4}-\d{2}-\d{2}$/.test(entry.title) && typeof dailyNotePair === "function") {
      li.appendChild(dailyNotePair(entry.title));
    }
  }
  //: GRAPH_PLAN KG4: the note's properties, a quiet table under its title
  //: (the `---` block in its text, which the body below leaves out).
  const props = Object.entries(entry.properties || {});
  if (props.length) {
    const table = document.createElement("dl");
    table.className = "note-props";
    for (const [key, values] of props.slice(0, 8)) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      //: Each value finds its notes (`prop:key=value` in the filter box).
      for (const value of (values || []).filter(Boolean)) {
        const shown = String(value).replace(/^\[\[|\]\]$/g, "");
        const find = chip(shown, "refs", (event) => {
          event.stopPropagation();
          filterNotesBy(propQuery(key, shown));
        });
        find.title = `Find the notes whose ${key} is ${shown}`;
        dd.append(find, " ");
      }
      if (!dd.firstChild) dd.textContent = "–";
      table.append(dt, dd);
    }
    li.appendChild(table);
  }

  const content = document.createElement("p");
  content.className = "entry-content";
  // One long note used to push everything else off the screen, so the list
  // stopped being a list. Anything past this is clamped with a "Show more".
  //
  // The trigger is the character count, not a measured height: this list
  // renders inside a `display: none` sub-tab, where every measurement comes
  // back 0: the trap that has caught four separate features here already.
  //: Pictures, sketches and attachment links are shown whole (a thumbnail,
  //: a file chip), so they never count toward "long": a note that is only a
  //: sketch, or a title and a PDF, has nothing hidden to show more of.
  const textOnly = stripFrontmatter(entry.content)
    .split("\n")
    .filter((line) => line.trim() && !/^\s*!?\[[^\]]*\]\([^)]*\)\s*$/.test(line))
    .join("\n");
  const glance = meetingGlance(entry);
  //: A row holding only a preview (`content_truncated`) is long by definition: there is more behind it.
  const isLong = !glance && (
    entry.content_truncated ||
    textOnly.length > LONG_NOTE_CHARS ||
    textOnly.split("\n").length > LONG_NOTE_LINES);
  if (isLong && !expandedNotes.has(entry.id)) content.classList.add("entry-clamped");
  // Mark the matched words while filtering, so it's obvious WHY a note is in
  // the list. Built with createElement/textContent rather than innerHTML, 
  // note text is user content and must never be parsed as markup.
  //: A clamped card's two lines are text, not the blank line between its
  //: paragraphs (INBOX 458: "Tonight, I have work." then a lone "..."):
  //: folded, the paragraphs run on one line each; opened, the note as written.
  //: `body` is set again when a clipped row's card is filled with the whole note (INBOX 1525).
  const bodyOf = (note) => (note.title ? bodyWithoutTitleLine(note.content) : stripFrontmatter(note.content));
  let body = bodyOf(entry);
  const fillContent = () => renderNoteText(
    content,
    content.classList.contains("entry-clamped") ? body.replace(/\n[ \t\r]*(?:\n[ \t\r]*)+/g, "\n") : body,
    searchHighlightTerms(),
    //: Heading hashes are source, not words (dogfood item 18). Run on the
    //: prose only, not the whole note: a code fence keeps its own `#` and `-`.
    (prose) => prose.replace(/^#{1,6}[ \t]+/gm, "").replace(/^( *)-(?= \w)/gm, "$1•")
  );
  fillContent();
  //: **A card drawn open fills itself with the whole note** (INBOX 1525 review). A clipped row's card read the rest only
  //: on a "Show more" press, so an opened-out card, row or phone note page drawn again showed 300 characters with no
  //: way on. One way in for all of them: drawn open, the row's chevron, a press. The card's own `entry` becomes the
  //: whole note, so its menus and Copy read it too; "note-whole" tells a host that changed the text (the note page).
  //: `clipped` is how the card was drawn: another reader's `fullEntry` fills the shared row, not this card's text.
  let clipped = entry.content_truncated;
  content.fillWhole = () => clipped && (content.whole ||= fullEntry(entry.id).then((whole) => {
    clipped = false;
    entry = whole;
    body = bodyOf(whole);
    fillContent();
    if (content.unclip) noteClampFit.observe(content);
    content.dispatchEvent(new Event("note-whole"));
  }, () => void (content.whole = null)));
  if (expandedNotes.has(entry.id) || expandedRows.has(entry.id)) content.fillWhole();
  content.addEventListener("remove-inline-image", async (e) => {
    e.stopPropagation();
    if (!(await confirmDialog("Remove this image from the note?"))) return;
    //: The PUT sends the whole text back, so it is built from the note `fullEntry` read, never the card's own row,
    //: which a list refresh can have swapped for a clipped one meanwhile (INBOX 1525).
    const whole = await fullEntry(entry.id).catch((error) => void toast(error.message, true));
    if (!whole) return;
    const contentBefore = whole.content;
    const contentAfter = contentBefore.replace(e.detail.originalText, "").replace(/\n{3,}/g, "\n\n").trim();
    try {
      await apiJson(`/entries/${entry.id}`, { method: "PUT", body: JSON.stringify({ content: contentAfter }) });
      pushEntryPutUndo(entry.id, "Removed an image from a note", { content: contentBefore }, { content: contentAfter });
      await refreshEntries([entry.id]);
      flashEntry(entry.id);
      toast("Image removed.");
    } catch(err) {
      toast(err.message || "Couldn't remove that image.", true);
    }
  });
  if (glance) {
    //: The glance and the body are both in the card; the card's class says
    //: which shows (note-cards CSS), so a search, the caret in rows view and
    //: "Show the whole note" all land on the body.
    const box = document.createElement("div");
    box.className = "meeting-glance";
    for (const row of glance) {
      const line = document.createElement("p");
      line.className = "meeting-glance-row";
      if (row.label) {
        const label = document.createElement("span");
        label.className = "meeting-glance-label";
        label.textContent = row.label;
        line.append(label, " ");
      }
      line.append(row.text);
      box.appendChild(line);
    }
    li.classList.add("meeting-card");
    li.classList.toggle("meeting-open", expandedNotes.has(entry.id) || searchHighlightTerms().length > 0);
    li.append(box, content);
    const more = document.createElement("button");
    more.type = "button";
    more.className = "entry-more";
    const sayMore = () => (li.classList.contains("meeting-open") ? "Show the glance" : "Show the whole note");
    more.textContent = sayMore();
    more.addEventListener("click", () => {
      const open = li.classList.toggle("meeting-open");
      if (open) expandedNotes.add(entry.id);
      else expandedNotes.delete(entry.id);
      more.textContent = sayMore();
    });
    li.appendChild(more);
  } else {
    //: A long note says what it is about before its clamped lines (CHAT_PLAN B22):
    //: the gist is the server's (`composer_gist`), under 90 characters.
    if (entry.gist && isLong) {
      const gist = document.createElement("p");
      gist.className = "entry-gist muted text-sm";
      gist.textContent = entry.gist;
      li.appendChild(gist);
    }
    li.appendChild(content);
  }
  if (isLong) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "entry-more";
    const label = () =>
      expandedNotes.has(entry.id) ? "Show less" : "Show more";
    toggle.textContent = label();
    toggle.addEventListener("click", () => {
      if (expandedNotes.has(entry.id)) expandedNotes.delete(entry.id);
      else expandedNotes.add(entry.id);
      content.classList.toggle("entry-clamped", !expandedNotes.has(entry.id));
      fillContent();
      toggle.textContent = label();
      if (expandedNotes.has(entry.id)) content.fillWhole();
    });
    li.appendChild(toggle);
    // **Then check whether it was actually needed.** Reported: "a show
    // more/less button appears when it isnt needed sometimes", and
    // "notes shouldnt be truncated".
    //
    // `isLong` above is a character and line count, not a measurement, and
    // the comment there explains why: this list renders inside a
    // `display: none` sub-tab where every measured height comes back 0, 
    // the trap that has caught four features in this codebase. But a count
    // is a guess, and it is wrong in both directions: a note of 700 short
    // words wrapped narrow really is long, while 700 characters of one
    // paragraph in a wide card is three lines that fit with room to spare,
    // and gets a "Show more" that expands nothing.
    //
    // So: guess first so the markup is right when it cannot be measured,
    // then measure once the text has a size (`noteClampFit`, above
    // `entryItem`: a ResizeObserver, so a card built hidden or in a later
    // chunk is measured when it is laid out, not never) and take the control
    // back off when the text was never clipped.
    content.unclip = () => {
      noteClampFit.unobserve(content);
      content.classList.remove("entry-clamped");
      fillContent();
      toggle.remove();
    };
    if (!entry.content_truncated) noteClampFit.observe(content);
  }

  const meta = document.createElement("div");
  //: `note-meta` scopes the one-line facts styling (08-consistency.css) to a
  //: note card: `.entry-meta` alone is also the chip row of the skills, the
  //: personas and the extras in Settings, which that styling flattened.
  meta.className = "entry-meta note-meta";
  // A note saved with filing deferred is in its holding category, not its
  // real one, and saying "Uncategorised" for the second or two before the
  // background pass lands reads as the AI having failed. Say what is
  // actually happening instead.
  if (entry.filing_state === "pending") {
    const filing = chip("ph:spin Filing…", "filing");
    filing.title = "Atlas is deciding where this note goes. It's already saved.";
    meta.appendChild(filing);
    //: Any pending card is watched, not only the one just saved: a note
    //: left filing when the app closed, or listed after a reload, would
    //: otherwise say "Filing…" until something else re-read the list.
    //: Quiet, because a toast for a note saved minutes ago is noise, and
    //: deduped by id inside `watchFiling`.
    watchFiling(entry, { quiet: true });
    //: **Stop it by hand** (owner, 0.3.31: "a manual way to stop note
    //: filing ... accessible on the filing note"). The same stop is on the
    //: filing rows of Settings, Background tasks and the activity popup.
    if (options.actions) {
      const stop = (action, done) => async () => {
        try {
          const result = await apiJson(`/entries/${entry.id}/filing/stop`, {
            method: "POST",
            body: JSON.stringify({ action }),
          });
          toast(done(result.category));
        } catch (error) {
          toast(error.message, true);
        }
        await loadEntries();
      };
      meta.appendChild(
        kebabMenu(
          [
            {
              label: "ph:sparkle File by meaning now",
              title: "Stop waiting for Atlas and file it by what it's about",
              run: stop("fallback", (category) => `Filed under “${category}” by meaning.`),
            },
            {
              label: "ph:hand-palm Leave it where it is",
              title: `Stop filing; it stays in “${entry.category}”`,
              run: stop("keep", (category) => `Left in “${category}”.`),
            },
            {
              label: "ph:folder-simple File it myself",
              title: "Stop filing, then pick its category yourself",
              run: stop(
                "keep",
                () => "Filing stopped. Drag it onto a category in the sidebar, or edit it to pick one."
              ),
            },
          ],
          "Stop filing this note"
        )
      );
    }
  } else if (entry.board_kind) {
    //: A board or a mind map says so where a note says its category (the
    //: owner: "a whitebaord showed as a note"); it has none of its own.
    meta.appendChild(chip(entry.board_kind === "map" ? "ph:tree-structure Mind map" : "ph:pencil-circle Board", "category"));
  } else {
    //: `category` names the chip for the meta line's own styles (08-
    //: consistency.css, "one line of facts"): before it had a class, the
    //: category rule was "a chip with none of these variants", which caught
    //: every variant added after it and drew "No tags yet" and "Linked by 5
    //: notes" as accent pills too.
    //: The name in a `.ph-text` span, so a narrow line can ellipsise it.
    const categoryEl = chip("", "category");
    categoryEl.append(Object.assign(document.createElement("span"), { className: "ph-text", textContent: entry.category }));
    paintCategoryDot(categoryEl, entry.category);
    //: The drag handle for moving this note to another category (INBOX 431
    //: (e), `wireCategoryDropTarget`): only in a list with actions.
    if (options.actions && !entry.is_board) {
      categoryEl.draggable = true;
      categoryEl.title = `${entry.category}: click for options, or drag it onto a category in the sidebar`;
      categoryEl.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/x-memorymap-note", String(entry.id));
        event.dataTransfer.effectAllowed = "move";
      });
    }
    //: A click opens its menu (INBOX 432, 447): the chip is the category, so it is the
    //: obvious place to change it, and it was a label that did nothing.
    if (options.actions && !entry.is_board && entry.id && !entry.deleted_at) {
      categoryEl.classList.add("is-action", "chip-interactive");
      categoryEl.setAttribute("role", "button");
      categoryEl.tabIndex = 0;
      categoryEl.setAttribute("aria-haspopup", "menu");
      categoryEl.setAttribute("aria-label", `Category ${entry.category}: show notes, move or manage`);
      //: A click opens a menu (INBOX 447 (5)): show the notes in this
      //: category, move this note, manage categories. It went straight to
      //: Move before (INBOX 432), which left no way to just look.
      const move = (event) => {
        event.stopPropagation();
        openCategoryChipMenu(categoryEl, entry);
      };
      categoryEl.addEventListener("click", move);
      categoryEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          move(event);
        }
      });
    }
    meta.appendChild(categoryEl);
  }
  //: `hashtag` marks a real tag: `tag` alone is also the quiet look the
  //: documents, the source and the space borrow, and only a tag gets the #.
  for (const tag of entry.tags) {
    //: The meeting chip says it, and opens the meeting (INBOX 644): a
    //: "#meeting" beside it was the same fact twice on one line.
    if (options.actions && tag === "meeting" && !entry.is_board) continue;
    const tagChip = options.actions
      ? chip(tag, "tag hashtag", (event) => {
        event.stopPropagation();
        filterNotesByTag(tag);
      })
      : chip(tag, "tag hashtag");
    if (options.actions) {
      tagChip.title = `Show every note tagged #${tag}. Right-click for more.`;
      tagChip.setAttribute("aria-haspopup", "menu");
      //: The chip's own menu (INBOX 447 (4)): Show notes, Rename, Remove from
      //: this note. Right-click and the menu keys; a plain click still filters.
      tagChip.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openTagChipMenu(tagChip, entry, tag, event.clientX, event.clientY);
      });
      //: A hold on a phone is the same menu, and takes the hold away from the
      //: note's own menu (`rowMenuAtEvent` leaves `[data-chip-menu]` alone).
      tagChip.dataset.chipMenu = "tag";
      wireLongPress(tagChip, (event, point) => openTagChipMenu(tagChip, entry, tag, point.x, point.y));
      tagChip.addEventListener("keydown", (event) => {
        if (event.key !== "ContextMenu"&& !(event.key === "F10" && event.shiftKey)) return;
        event.preventDefault();
        event.stopPropagation();
        openTagChipMenu(tagChip, entry, tag);
      });
    }
    tagChip.dataset.tag = tag;
    meta.appendChild(tagChip);
  }
  //: Where the tags that do not fit go (INBOX 455 (1), `fitNoteMetas`).
  meta.appendChild(noteMetaMore(entry));
  //: Tags filing suggested, kept on the note (INBOX 440): a split chip, its
  //: first half takes the tag, its x half dismisses it for good.
  const suggestions = options.actions && !entry.is_board ? entry.suggested_tags || [] : [];
  for (const tag of suggestions) {
    //: Two sibling buttons in one chip, take and discard, not a button
    //: holding a button (axe nested-interactive, found by the density pass).
    const group = chip("", "tag suggested-tag");
    group.replaceChildren();
    group.dataset.tag = tag;
    //: Real buttons (N37), not spans with a role: a keyboard, a screen reader and a
    //: finger all meet a control. The look is the chip's own (08-consistency.css).
    const take = document.createElement("button");
    take.type = "button";
    take.className = "suggested-tag-take";
    setLabel(take, `ph:plus ${tag}`);
    //: Each suggestion says what in the note backs it (WORLD_CLASS 23,
    //: decision 5): "It mentions “exam”."
    const reason = entry.suggested_tag_reasons?.[tag];
    take.title = reason ? `Add tag ${tag}. ${reason}` : `Add tag ${tag}`;
    take.addEventListener("click", (event) => {
      event.stopPropagation();
      answerTags(entry, { take: [tag] });
    });
    //: A short name: the reason belongs to the hover, not to a screen reader's every pass.
    take.setAttribute("aria-label", `Add tag ${tag}`);
    group.appendChild(take);
    const discard = document.createElement("button");
    discard.type = "button";
    //: Its own half of the chip, not `.unlink`'s glyph after the words
    //: (INBOX 1583: "those x button on the suggested tags are badly designed").
    discard.className = "suggested-tag-dismiss";
    setLabel(discard, "ph:x");
    discard.title = `Dismiss: stop suggesting #${tag} for this note`;
    discard.addEventListener("click", (event) => {
      event.stopPropagation();
      answerTags(entry, { discard: [tag] });
    });
    discard.setAttribute("aria-label", `Dismiss tag ${tag}`);
    group.appendChild(discard);
    meta.appendChild(group);
  }
  //: **A note with no tags says so, where the tags would be** (INBOX 162),
  //: and the chip is the fix: the edit form, cursor in the tags field.
  //: **Fewer than three tags: a quiet "+ Tag" after them** (brief 89, the
  //: owner: "should add tags show for notes with 0-2/3 tags on them??"). It
  //: opens a small popover with up to three suggested tags, the field, and a
  //: menu that turns suggestions off for this note (tag-suggest.js).
  if (tagAddChipKind(entry, options) === "more") {
    const more = chip("ph:plus Tag", "untagged tag-add", (event) => {
      event.stopPropagation();
      ensureModule("tagSuggest").then(() => openNoteTagPopover(entry, more));
    });
    more.title = "Add a tag to this note, or pick a suggested one";
    more.setAttribute("aria-haspopup", "dialog");
    more.setAttribute("aria-expanded", "false");
    meta.appendChild(more);
  }
  if (tagAddChipKind(entry, options) === "add"
      || (!options.actions && options.facts && !entry.tags.length && !entry.is_board && !entry.is_draft)) {
    //: On a read-only row it is a fact only (INBOX 297).
    const untagged = options.actions
      ? chip("ph:tag Add tags", "untagged", (event) => {
        event.stopPropagation();
        openNoteEditor(entry.id, { focusTags: true });
      })
      : chip("ph:tag No tags yet", "untagged");
    untagged.title = options.actions
      ? "Add tags to this note"
      : "This note has no tags yet";
    meta.appendChild(untagged);
    //: **And the offer to have them written** (INBOX 292). Left out rather
    //: than gated with no model answering: `disabled` does nothing to a
    //: span, and an offer that cannot be honoured is worse than none.
    //: Not on a private note: the route refuses it (sweep 1004 item 7), so the
    //: chip's only answer would be a refusal toast.
    if (options.actions && !entry.is_private && !aiIsOff(true)) {
      const askAtlas = chip("ph:sparkle Tag with Atlas", "untagged-ai", (event) => {
        event.stopPropagation();
        reevaluateEntry(entry);
      });
      askAtlas.title = "Atlas reads the note and suggests tags for you to approve";
      meta.appendChild(askAtlas);
    }
  }
  //: **What points at this note, on the card** (INBOX 246's third gap).
  //: Only when the counts for this page have landed; `ensureCardCounts`
  //: patches the chip in afterwards for cards rendered before they had.
  const refs = referenceCountChip(entry, options);
  if (refs) meta.appendChild(refs);
  const topicMark = options.actions || options.facts ? noteTopicChip(entry) : null;
  if (topicMark) meta.appendChild(topicMark);
  //: **And what it made you promise to do** (INBOX 309). Same cache, same
  //: patch-in, same line: a reminder that came out of this note is a fact
  //: about the note in exactly the way "on 1 board" is.
  const alarms = reminderCountChip(entry, options);
  if (alarms) meta.appendChild(alarms);

  // "AI 0%: check this" is a warning about the AI's filing, and it only makes
  // sense when the AI actually did some. On a note you filed yourself, or one
  // saved while no AI was running, it accused a perfectly good note of being
  // suspect: which is most notes if you don't run Ollama.
  const aiDidFile = entry.ai_confidence > 0 && !entry.user_filed;
  // Plain-language explanation on hover, "confidence" is jargon otherwise,
  // and the number alone doesn't say what it's confident *about*.
  const confidenceHint = "Atlas's estimate that it picked the right category. Low, so worth a look.";
  //: A confident score is quiet text beside the category (INBOX 440); a low
  //: one is the warn mark, because that one is a request to check.
  const categoryChip = meta.querySelector(".chip.category");
  if (aiDidFile && categoryChip && entry.ai_confidence >= REVIEW_THRESHOLD) {
    categoryChip.title = `Filed by Atlas, ${entry.ai_confidence}% sure`;
    const byWords = entry.filing_state === "words";
    const who = byWords ? "your notebook's words" : "Atlas";
    if (byWords) categoryChip.title = `Filed from your notebook's words, ${entry.ai_confidence}% sure`;
    const sure = chip(`${byWords ? "ph:text-aa" : "ph:sparkle"} ${entry.ai_confidence}%`, "item-fact filing-sure");
    sure.title = `How sure ${who} ${byWords ? "were" : "was"} when filing this in “${entry.category}”`;
    sure.setAttribute("aria-label", `Filed by ${who}, ${entry.ai_confidence}% sure`);
    categoryChip.after(sure);
  }
  const confidenceChip = aiDidFile && entry.ai_confidence < REVIEW_THRESHOLD
    ? // Low confidence from a real attempt, worth a human look (Phase 3).
      chip(`ph:warning AI ${entry.ai_confidence}%: check this`, "review")
    : null;
  if (confidenceChip) confidenceChip.title = confidenceHint;
  // Flash the badge once when this note's confidence just changed, so the
  // update after a re-evaluation is actually noticeable (user request).
  //: The category flashes when the score went to its tooltip, since the
  //: category is what a re-evaluation actually answered.
  const flashed = confidenceChip || categoryChip;
  if (flashed && entry.id === flashConfidenceId) {
    flashed.classList.add("badge-flash");
    flashConfidenceId = null;
  }
  //: Beside the category, as the high score is: how sure leads the line.
  if (confidenceChip) categoryChip ? categoryChip.after(confidenceChip) : meta.appendChild(confidenceChip);

  // The documents this note feeds. Notes and documents are separate things
  // on purpose; this is the one place that says they are about the same one.
  for (const doc of entry.documents || []) {
    const mark = chip(`ph:file-text ${doc.title}`, "tag", () => openDocumentFromNote(doc.id));
    mark.title = `Open “${doc.title}”`;
    if (options.actions) {
      // Detach from the note's side too. The document editor has had this
      // since the link existed; from here it took going and finding the
      // document first, which is the wrong way round when the note is what
      // you are already looking at.
      const unlink = document.createElement("span");
      unlink.className = "unlink";
      setLabel(unlink, "ph:x"); // raw "×" glyph vs Phosphor icon font mismatch mis-centers the icon
      unlink.title = `Detach from “${doc.title}”: the note stays`;
      unlink.addEventListener("click", async (event) => {
        event.stopPropagation(); // the chip itself opens the document
        await api(`/documents/${doc.id}/notes/${entry.id}`, { method: "DELETE" });
        pushRoutePairUndo(`Detached from “${doc.title}”`, [`/documents/${doc.id}/notes`, "POST", { entry_id: entry.id }], [`/documents/${doc.id}/notes/${entry.id}`, "DELETE"], () => refreshEntries([entry.id]));
        await refreshEntries([entry.id]);
        toast(`Detached from “${doc.title}”.`);
      });
      makeUnlinkAccessible(unlink);
      mark.appendChild(unlink);
    }
    meta.appendChild(mark);
  }

  // Where a web-reader clipping came from (BACKLOG §65's "source as
  // metadata"). Opens the real page, the note's own body already has the
  // same link inline, this is the at-a-glance version.
  if (entry.source_url) {
    const sourceChip = chip(
      `ph:globe ${entry.source_title || entry.source_url}`,
      "tag",
      () => window.open(safeHref(entry.source_url), "_blank", "noopener,noreferrer")
    );
    sourceChip.title = `Open the source: ${entry.source_url}`;
    meta.appendChild(sourceChip);
  }

  // What this note's own "tomorrow" meant on the day it was written (§10A).
  // A chip rather than a mark inside the text: `renderNoteText` already
  // layers wiki links, inline markdown and filter highlighting through each
  // other, and a fourth pass over the same string is where that breaks.
  //: **The dates a note mentions, said as mentions** (owner: the meta row is
  //: "a bit hard to read, especially in regards to the date parsing"). Two
  //: calendar chips beside "3 days ago" read as three dates of the same kind;
  //: they are different facts: when the note was written is at the card's
  //: corner, and the days its words point at are one labelled item here.
  const mentioned = [];
  for (const when of entry.dates || []) {
    const day = new Date(`${when.at}T00:00:00`);
    const dayLabel = day.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    //: UX-02: a clock said with the day, shown as written.
    const clock = when.precision === "minute" && /^\d{2}:\d{2}$/.test(when.time || "")
      ? new Date(`${when.at}T${when.time}:00`).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
      : "";
    //: A month or a year is shown as that, not as a day in it (audit 1031 N8:
    //: "month of Nov 30" read as a date).
    const label = clock
      ? `${dayLabel}, ${clock}`
      : when.precision === "month"
        ? day.toLocaleDateString(undefined, { month: "short" })
        : when.precision === "year"
          ? String(day.getFullYear())
          : when.precision === "week"
            ? `week of ${dayLabel}`
            : dayLabel;
    //: The date alone, the phrase on hover (owner, with a screenshot of
    //: "Tonight → 21 Sept on Friday → 25 Sept" in one meta line: "clean up
    //: the notes metadata and badges a bit more"). What a reader scans for is
    //: the day; the words the note used for it are the explanation.
    mentioned.push({
      label,
      title: `“${when.phrase}” meant ${day.toLocaleDateString(undefined, {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
      })}`,
    });
  }
  if (mentioned.length) {
    const shown = mentioned.slice(0, 3).map((m) => m.label).join(", ");
    const more = mentioned.length > 3 ? ` +${mentioned.length - 3}` : "";
    const mark = chip(`ph:calendar-blank Mentions ${shown}${more}`, "when");
    mark.title = `Dates this note mentions, not a reminder. ${mentioned.map((m) => m.title).join("; ")}. Worked out from the day this note was written.`;
    meta.appendChild(mark);
  }

  //: **Which space this note is filed in (INBOX 1a/38)**, wherever the
  //: picker does not already say it. An empty `spacesCache` means "not
  //: loaded yet" (`loadSpaces` re-renders), not "no spaces": without the
  //: guard 57 cards said "a space that no longer exists" in a README shot.
  //: Only when the notes in view span spaces (INBOX 432): "Default Space"
  //: on every card told nobody anything.
  if (entry.workspace_id && spacesCache.length > 1 && notesSpanSpaces()) {
    const active = activeSpaceId();
    if (active === SPACE_ALL || entry.workspace_id !== active) {
      const space = spacesCache.find((s) => s.id === entry.workspace_id);
      // Stored as a class name ("ph-house"), not the `setLabel` "ph:house".
      const iconName = (space?.icon || "ph-circles-four").replace(/^ph-/, "");
      const spaceName = space ? space.name : "a space that no longer exists";
      const spaceChip = chip(`ph:${iconName} ${spaceName}`, "tag", () =>
        setActiveSpace(entry.workspace_id)
      );
      spaceChip.title = `Filed in ${spaceName}. Click to switch there.`;
      meta.appendChild(spaceChip);
    }
  }

  // While the AI is re-evaluating this note, show a live spinner chip so
  // it's obvious something is running on this specific card.
  if (entry.id === busyEntryId) {
    li.classList.add("entry-busy");
    const busy = chip("ph:spin Atlas is reading…", "busy");
    busy.classList.add("chip-busy");
    meta.appendChild(busy);
  }

  //: The actions' corner (`.entry-meta-end`, 08-consistency.css).
  const metaEnd = document.createElement("span");
  metaEnd.className = "entry-meta-end";

  const date = document.createElement("span");
  date.className = "entry-date";
  const stamp = entry.created_at;
  //: Sorted by "Recently edited", the date is the edit's (INBOX 432); the
  //: tooltip always carries both when they differ.
  const edited = entry.edited_at && entry.edited_at !== stamp ? entry.edited_at : null;
  const byEdit = edited && noteSort === "edited";
  date.textContent = byEdit ? `edited ${relativeTime(edited)}` : relativeTime(stamp);
  date.title = `Written ${whenText(stamp)}` + // exact on hover
    (edited ? `, edited ${whenText(edited)}` : "");
  //: **The time ends the details line, on every card** (INBOX 446: the
  //: corner faded it whenever the card was pointed at; INBOX 455 (1): a line
  //: that wrapped put it on a line of its own). The line never wraps now
  //: (`fitNoteMetas`), so this is the line's last fact at its right edge.
  //: The suffix its own span: a phone drops it before the category (UX-13).
  if (edited && !byEdit) date.append(Object.assign(document.createElement("span"), { className: "entry-edited", textContent: "\u00a0· edited" }));
  meta.appendChild(date);
  meta.appendChild(metaEnd);

  if (options.actions) {
    // Wave L rework: two everyday actions stay visible; the rest live in
    // one ⋯ menu: the old row of nine icons was unscannable noise.
    const actions = document.createElement("span");
    actions.className = "entry-actions";
    actions.appendChild(
      //: **Star, not pin, and "Favourites", not "pinned".** The flag does two
      //: things: floats a note to the top of a list *and* collects it into
      //: the Favourites row in the sidebar, and it was named for only the
      //: first, so the app showed one concept under two names with two icons.
      //: Asked for: "make sure the favourites feature is actually integrated
      //: everywhere." The tooltip keeps the sort behaviour, since that is the
      //: half a star does not imply on its own.
      favouriteButton(entry)
    );
    actions.appendChild(
      smallButton("ph:clipboard", "Copy this note's text", () => entryItem.copyText(entry))
    );
    actions.appendChild(
      //: `openNoteEditor` scrolls the form into view after the redraw (the
      //: nearest scroller, DESIGN.md) and asks before dropping another
      //: note's unsaved changes.
      smallButton("ph:pencil-simple", "Edit this entry", () => openNoteEditor(entry.id))
    );
    // And a button beside Edit, since the chip alone was not read as one.
    if (entry.is_draft) {
      actions.appendChild(smallButton("ph:check-circle", "Publish this draft as a proper note", () => publishDraft(entry)));
    }
    actions.appendChild(entryOverflowMenu(entry));
    //: **The icon buttons say which note they act on** (audit 1029 N17): a list
    //: of buttons read "Edit this entry" once per card. The note's name after
    //: the verb tells them apart; `title` stays (notes-list.js finds Edit by it).
    const cardName = (entry.title || noteNamePlain(entry.content || "", 60) || "").trim();
    if (cardName) {
      for (const button of actions.querySelectorAll("button")) {
        const verb = (button.getAttribute("aria-label") || button.title || "").trim();
        if (verb) button.setAttribute("aria-label", `${verb}: ${cardName}`);
      }
    }
    metaEnd.appendChild(actions);
    //: A draft's strip holds a fifth target (Publish): the card's first
    //: lines and the row's lane keep that much more clear for it
    //: (08-consistency.css, "The strip's own width, kept clear").
    li.classList.toggle("has-wide-strip", actions.childElementCount > 4);
  }
  if (entry.is_private) {
    // With the vault known to be locked (sign-in off, INBOX 426 aa), the
    // chip is the way in: it asks for the password and redraws the list.
    const lockedChip = vaultOpen === false
      ? chip("ph:lock-key unlock to read", "", () => unlockPrivateNotes())
      : chip("ph:lock private");
    meta.insertBefore(lockedChip, meta.firstChild);
  }
  if (entry.pinned) meta.insertBefore(chip("ph:star favourite"), meta.firstChild);
  //: **A meeting says so, and the chip is its way in** (INBOX 644): the
  //: meeting sheet, with its action items as reminders, its decisions,
  //: Summarise and Record. The draft chip's shape: a fact you press.
  if (options.actions && !entry.is_board && noteIsMeeting(entry)) {
    const meetingChip = chip("ph:users-three meeting", "meeting", (event) => {
      event.stopPropagation();
      openMeetingSheet(entry.id);
    });
    meetingChip.title = "Open the meeting";
    meta.insertBefore(meetingChip, meta.firstChild);
  }
  // A draft (the selection popup's "Save as draft note", the Writing Room's
  // "Save as note"): the Drafts filter finds them, and **the chip publishes**,
  // said on it, since "click to clear the label" read as no way to publish.
  if (entry.is_draft) {
    const draftChip = chip("ph:pencil-simple-line draft", "draft", (event) => {
      event.stopPropagation();
      publishDraft(entry);
    });
    draftChip.title =
      "This is a draft, click to publish it as a proper note. It stays where it is either way; only the Drafts filter changes.";
    meta.insertBefore(draftChip, meta.firstChild);
  }
  //: **Where an imported note came from**: the file name its `[[links]]`
  //: use. A chip, because the importer must not rewrite the file.
  if (entry.source_path) {
    const fileChip = chip(`ph:file-md ${entry.source_path.split("/").pop()}`, "source-path");
    fileChip.title = `Imported from ${entry.source_path}`;
    meta.insertBefore(fileChip, date);
  }
  li.appendChild(meta);
  noteMetaFit.observe(meta);

  // "Why this result" is its own line under the note, not another chip in
  // the meta lane. Measured: in the compact rows view that lane is a
  // `fit-content(26rem)` track with `overflow-x: auto`, and a chip naming
  // two signals pushed the date and the actions strip out of the visible
  // box (57 to 84px past its right edge, `scratchpad/ui-sweeps/searchwhy.js`),
  // which is the exact crowding `.entry-meta`'s own comment says that track
  // was rebuilt to stop. A row of its own also says what it is: a reason for
  // this note being in *this* list, which appears with a query and goes with
  // it, rather than a permanent fact about the note like its category.
  const why = whyThisResultChip(entry);
  if (why) {
    const line = document.createElement("div");
    line.className = "entry-why";
    line.appendChild(why);
    li.appendChild(line);
  }
  //: The review queue's three answers (WORLD_CLASS_PLAN section 17, row 1),
  //: a line of their own for the reason "why this result" is: they belong to
  //: the `is:review` list and go with it, rather than sit on every card.
  if (options.actions && !entry.is_board && entryNeedsReview(entry) && parseNoteQuery(noteSearch || "").flags.includes("review")) {
    li.appendChild(noteReviewActions(entry));
  }

  // A note's own files, as attachment cards (INBOX 440 (2)). Before `meta`
  // (the category/date/pin/actions footer), not after, reported directly: a
  // sketch or attached image sat below the note's own metadata row rather
  // than reading as part of the note's own content.
  if (entry.attachments.length > 0) li.insertBefore(renderAttachmentCards(entry, options.actions), meta);

  // Inline add-context / continue-thought forms (Wave B).
  if (options.actions && inlineAction && inlineAction.id === entry.id) {
    li.appendChild(renderInlineAction(entry));
  }

  if (entry.links.length > 0) {
    const linkRow = document.createElement("div");
    linkRow.className = "entry-links";
    for (const link of entry.links) {
      // **A link is navigation, not content.** Measured on the busiest screen
      // in the app: a card was 25px of its own note, 23px of metadata and 21px
      // of link chips: and the chips were the loudest thing on it, filled and
      // bold, each carrying the *whole first line of another note*. On a
      // well-linked note the links were wider than the note and read first,
      // which is §36B.3's "everything at equal weight" with the weights
      // actually inverted.
      //
      // Clipped to a glanceable length, quiet by default, with the full text
      // on hover for when the clip is not enough.
      //: An image in the other note's first line is markdown a chip cannot
      //: draw, and it showed as its raw `![...](...)` (owner's screenshot:
      //: "Gary The Moss Monster :D ![Gary The Moss Monst..."). The picture
      //: is dropped from the label; the words around it stay.
      //: The preview is clipped by the server, so an image can arrive cut
      //: in half (`![WallpaperEngineOverride_rand`, owner's screenshot) and
      //: a heading with its `#`: both go, whole or truncated.
      //: **Plain words** (INBOX 474: a chip showed "[something](https://..."):
      //: the server clips at 60 characters, so a token arrives half open and
      //: the inline renderer printed it as typed. The last rule takes a `[`
      //: whose `]` was cut off.
      const label = plainText(
        (link.preview || "").replace(/!\[[^\]]*(?:\](?:\([^)]*\)?)?)?/g, "")
      )
        .replace(/\[([^\]]*)$/, "$1")
        .trim();
      const short = label.length > LINK_CHIP_CHARS
        ? `${label.slice(0, LINK_CHIP_CHARS - 1).trimEnd()}…`
        : label;
      // The label is plain text (a chip is navigation, not content; see
      // above), so it needs no rendering and cannot show half a token.
      //
      // The click handler is built first and passed into chip()'s own
      // onClick param: every sibling chip() call site in this file does
      // the same and gets keyboard support (Enter/Space, role="button",
      // tabindex) for free. This one used to build a bare chip and attach a
      // plain `click` listener after the fact instead, which quietly opted
      // this specific "Go to note" chip out of keyboard operability while
      // every other chip stayed reachable (Web Interface Guidelines pass).
      const goToLinkedNote = (e) => {
        if (e.target.classList.contains("unlink")) return;
        flashEntry(link.entry_id);
      };
      const linkChip = chip("", "link", goToLinkedNote);
      // **Which way the link points.** Every link used to draw the same
      // bidirectional glyph, because the API merged both directions into one
      // list and never said which was which, so a note could show what it
      // was connected to and never whether it had reached out or been
      // reached for. Those are different facts, and telling them apart is
      // most of what a Connections list is for (asked for by way of
      // Kortex's own, which arrows every row).
      const outgoing = link.direction !== "in";
      linkChip.classList.add(outgoing ? "link-out" : "link-in");
      //: The arrow and the words are the label grammar's own pair, so the
      //: arrow is a `.ph-lead` straight in the chip and lands on the words'
      //: cap height like every other label's icon (INBOX 592). It sat in a
      //: span of its own, inline on that span's baseline in a 12px line box
      //: its 13.8px glyph overflowed: 1.1px above the words, measured.
      //: The words are a note's own text, so they never go through the label
      //: grammar (a preview ending in "ph:x" would draw an icon).
      setLabel(linkChip, outgoing ? "ph:arrow-up-right" : "ph:arrow-down-left");
      linkChip.firstElementChild.classList.add("ph-lead");
      const linkPreview = document.createElement("span");
      linkPreview.className = "ph-text";
      linkPreview.textContent = short;
      linkChip.appendChild(linkPreview);
      const reasonNote = link.reason
        ? link.reason_confidence != null
          ? `${link.reason} (deduced, ${deducedStrength(link.reason_confidence)})`
          : link.reason
        : null;
      const wayRound = outgoing ? "This note links to" : "Links to this note";
      //: KG3: a kind of link is named on the chip from this end ("Has part"
      //: on the whole, "Part of" on the piece); "Related" says nothing.
      const kindName = link.link_label && link.link_type !== "related" ? link.link_label : "";
      if (kindName) {
        const kind = document.createElement("span");
        kind.className = "link-kind";
        kind.textContent = kindName;
        linkChip.insertBefore(kind, linkPreview);
      }
      linkChip.title = (reasonNote
        ? `${wayRound}: ${label}\nReason: ${reasonNote}`
        : `${wayRound}: ${label}`) + (kindName ? `\nKind: ${kindName}` : "");
      //: **One chip and one menu per connection** (INBOX 319, the owner: "the
      //: buttons in these connections in notes need a redesign and look").
      //: Edit reason, clear reason and unlink were three round buttons of one
      //: size inside every chip, so three connections were nine identical
      //: circles with the labels reading as captions between them. They are
      //: the `kebabMenu` recipe now (DESIGN.md, standing order 11), which also
      //: gives the label the width the buttons took.
      const putReason = async (reason) => {
        await api(`/entries/${entry.id}/links/${link.link_id}/reason`, {
          method: "PUT",
          body: JSON.stringify({ reason }),
        });
        await refreshEntries([entry.id, link.entry_id]);
      };
      const editReason = async () => {
        const next = await promptDialog("Why are these notes connected?", link.reason || "");
        if (!next) return;
        const was = link.reason || null;
        await putReason(next);
        pushUndo("Edited why two notes are connected", () => putReason(was), () => putReason(next));
      };
      const clearReason = async () => {
        const was = link.reason || null;
        await putReason(null);
        pushUndo("Cleared why two notes are connected", () => putReason(was), () => putReason(null));
      };
      const unlink = async () => {
        const otherId = link.entry_id;
        const reason = link.reason;
        let liveLinkId = link.link_id;
        await api(`/entries/${entry.id}/links/${liveLinkId}`, { method: "DELETE" });
        await refreshEntries([entry.id, otherId]);
        pushUndo(
          "Removed a link between notes",
          async () => {
            const updated = await apiJson(`/entries/${entry.id}/links`, {
              method: "POST",
              body: JSON.stringify({ target_id: otherId, reason }),
            });
            liveLinkId = updated.links.find((l) => l.entry_id === otherId)?.link_id ?? liveLinkId;
            await refreshEntries([entry.id, otherId]);
          },
          async () => {
            await api(`/entries/${entry.id}/links/${liveLinkId}`, { method: "DELETE" });
            await refreshEntries([entry.id, otherId]);
          }
        );
      };
      const connection = document.createElement("span");
      connection.className = "link-connection";
      connection.appendChild(linkChip);
      if (options.actions) {
        const items = [
          {
            label: link.reason ? "ph:pencil-simple Edit the reason" : "ph:pencil-simple Add a reason",
            title: link.reason ? "Edit why these notes are connected" : "Say why these notes are connected",
            run: editReason,
            group: "reason",
          },
        ];
        if (link.reason) {
          items.push({ label: "ph:eraser Clear the reason", title: "Keep the link, drop its reason", run: clearReason, group: "reason" });
        }
        items.push({ label: "ph:tag Kind and properties…", title: "What kind of link this is (Part of, Supports…) and its properties", run: () => openLinkTypeSheet(entry.id, link), group: "kind" });
        items.push({ label: "ph:link-break Remove the link", title: "Remove this link (undoable)", run: unlink, group: "remove" });
        connection.appendChild(kebabMenu(items, `Actions for the link to ${label || "a note without a title"}`, { vertical: true }));
      }
      linkRow.appendChild(connection);
    }
    //: **Three links, then a count** (INBOX 424 q): a well-linked note drew
    //: every connection as a chip, measured at 109 controls on the Notes tab
    //: with 19 under 24px, and the chips outweighed the note. The first
    //: three show; the rest wait behind "+N more links", which opens them
    //: in place (and stays open for this render).
    const LINKS_SHOWN = 3;
    const connections = [...linkRow.children];
    if (connections.length > LINKS_SHOWN + 1) {
      for (const extra of connections.slice(LINKS_SHOWN)) extra.classList.add("entry-link-extra");
      const more = document.createElement("button");
      more.type = "button";
      more.className = "ghost small entry-links-more";
      const hidden = connections.length - LINKS_SHOWN;
      //: A toggle (INBOX 474): it stays and reads "Show less" while open.
      const label = () => linkRow.classList.contains("show-all")
        ? "Show less"
        : `+${hidden} more link${hidden === 1 ? "" : "s"}`;
      more.textContent = label();
      more.setAttribute("aria-expanded", "false");
      more.addEventListener("click", (event) => {
        event.stopPropagation();
        const open = linkRow.classList.toggle("show-all");
        more.textContent = label();
        more.setAttribute("aria-expanded", String(open));
      });
      linkRow.appendChild(more);
    }
    li.appendChild(linkRow);
  }
  return li;
}

//: Take a note to the graph and put it in the middle, lit. The graph is its
//: own lazy bundle and lays itself out after the tab opens, so this waits for
//: the node to exist and to have a position rather than guessing a delay.
//: Accept keeps the janitor's category and makes it the person's (the note
//: leaves the queue, with Undo); Refile is the Move to category sheet, and a
//: move is a decision already; Split is Extract notes over the whole note,
//: which needs the model, so it is disabled with the reason when it is off.
function noteReviewActions(entry) {
  const row = document.createElement("div");
  //: `.night-questions-row` is the wrapping line of small buttons this is.
  row.className = "row night-questions-row entry-review";
  const set = async (accepted) => {
    await apiJson(`/entries/${entry.id}/filing`, { method: "POST", body: JSON.stringify({ accepted }) });
    for (const e of allEntries) if (e.id === entry.id) e.user_filed = accepted;
    renderEntries();
  };
  const where = entry.category || "Uncategorised";
  const accept = smallButton("ph:check Accept", `Keep it in ${where}`, async () => {
    try {
      await set(true);
    } catch (error) {
      toast(error.message, true);
      return;
    }
    const message = `Kept in ${where}.`;
    const action = pushUndo(message, () => set(false), () => set(true));
    toastAction(message, "Undo", async () => {
      settleUndoFromToast(action);
      await set(false).catch((error) => toast(error.message, true));
    });
  });
  const refile = smallButton("ph:folder-open Refile…", `Now in ${where}; choose another`, () => chooseNoteCategory([entry.id], entry.category));
  const split = smallButton(
    "ph:scissors Split…",
    "Split it into linked notes, with a preview first",
    () => fullEntry(entry.id).then((whole) => openExtractPreview(whole.content || "", { sourceEntryIds: [entry.id] }), (error) => toast(error.message, true))
  );
  row.append(accept, refile, split);
  return row;
}

function favouriteButton(entry) {
  //: `.favourite-btn` names the control for the phone's swipe (`initRowSwipe`),
  //: which presses it rather than carrying a second copy of the toggle.
  const button = smallButton(
    "ph:star",
    entry.pinned ? "Remove from Favourites" : "Add to Favourites (also floats it to the top)",
    async () => {
      const was = Boolean(entry.pinned);
      await api(`/entries/${entry.id}`, {
        method: "PUT",
        body: JSON.stringify({ pinned: !was }),
      });
      //: On the global stack, because a mis-click here is silent: the star
      //: changes shape and the note moves to the top of the list, and there
      //: was nothing that put it back. Reported as the undo stack being
      //: "significantly outdated and dont register a lot of actions".
      pushEntryPutUndo(
        entry.id,
        was ? "Removed a favourite" : "Added a favourite",
        { pinned: was },
        { pinned: !was }
      );
      await loadEntries();
    }
  );
  button.classList.add("favourite-btn");
  button.classList.toggle("is-favourite", Boolean(entry.pinned));
  button.setAttribute("aria-pressed", Boolean(entry.pinned));
  return button;
}

//: A note's own attached files (the `Attachment` table, `/files/{id}`), one
//: card each, in a wrapping grid. Pictures page through the lightbox
//: together; the bytes need the auth header, so a picture's src is a blob url
//: (`attachmentObjectUrl`). `editable` is the note list's own actions flag:
//: a card on a read-only surface offers no Rename or Remove.
function renderAttachmentCards(entry, editable) {
  const row = document.createElement("div");
  row.className = "att-cards";
  const images = entry.attachments.filter((a) => a.is_image);
  for (const attachment of entry.attachments) {
    row.append(attachmentCard({
      name: attachment.filename,
      url: `/files/${attachment.id}`,
      size: attachment.size,
      added: attachment.created_at,
      attachment,
      onChange: editable ? () => loadEntries() : null,
      thumb: attachment.is_image ? () => attachmentObjectUrl(attachment) : null,
      gallery: attachment.is_image
        ? () => ({
          items: images.map((a) => ({ filename: a.filename, getUrl: () => attachmentObjectUrl(a) })),
          index: images.indexOf(attachment),
        })
        : null,
    }));
  }
  return row;
}

//: The "+N" itself: a press lists what folded, each row doing what its chip
//: does (a tag shows its notes, a suggestion is taken).
function noteMetaMore(entry) {
  const more = chip("+0", "note-meta-more", (event) => {
    event.stopPropagation();
    const at = more.getBoundingClientRect();
    const items = [...more.parentElement.querySelectorAll(":scope > [data-tag][hidden]")].map((el) => {
      const tag = el.dataset.tag;
      return el.classList.contains("suggested-tag")
        ? { label: `ph:plus ${tag}`, title: `Suggested: add #${tag}`, group: "Suggested", run: () => answerTags(entry, { take: [tag] }) }
        : { label: `ph:hash ${tag}`, title: `Show every note tagged #${tag}`, group: "Tags", run: () => filterNotesByTag(tag) };
    });
    openMenuAtPoint(items, "More tags", at.left, at.bottom);
  });
  more.setAttribute("aria-haspopup", "menu");
  more.hidden = true;
  return more;
}

//: Moved here from the boot files (W27): only this file calls them.
function notesSpanSpaces() {
  if (notesSpanMemo.list !== allEntries) {
    const first = allEntries[0]?.workspace_id;
    notesSpanMemo = { list: allEntries, many: allEntries.some((e) => e.workspace_id && e.workspace_id !== first) };
  }
  return notesSpanMemo.many;
}

// The words worth highlighting in a result, operators aren't text to find.
function searchHighlightTerms() {
  if (!noteSearch) return [];
  const query = parseNoteQuery(noteSearch);
  return [...query.phrases, ...query.words].filter((t) => t.length > 1);
}

//: The note card's "..." menu, moved here from menus.js (boot gzip budget): only this lazy file builds it.
function entryOverflowMenu(entry) {
  const wrap = document.createElement("span");
  wrap.className = "menu-wrap";

  const menu = document.createElement("div");
  menu.className = "action-menu hidden";
  menu.setAttribute("role", "menu");

  //: Same square-kebab rule as `kebabMenu` below: this is the *other* ⋯
  //: builder (note cards, built lazily on first open), and a rule applied to
  //: one of two implementations of the same control is how they drift.
  //:
  //: **And they had.** Reported: "the ellipse kebab icons in the notes on the
  //: your notes tab are not centred." `kebabMenu` draws `ph:dots-three`; this
  //: one drew the literal character `⋯` (U+22EF), and a text glyph is placed
  //: on the *font's* baseline inside a 19.2px line box centred in a 28px
  //: button: U+22EF sits at the em box's midline, which is above the line
  //: box's optical centre, so the dots rode high. No amount of flex centring
  //: fixes that: the box is centred correctly and the glyph is not centred
  //: within the box. The icon font's own glyph is drawn to fill its box, so
  //: using the same icon as the other builder fixes the centring and the
  //: drift in one go.
  const opener = smallButton("ph:dots-three", "More actions", async () => {
    //: Built now, and given the card rows (Copy, Move, Add to tray) as `kebabMenu` gives them.
    filled ||= ensureModule("entryMenu").then((ok) => ok && (fillEntryMenu(menu, entry), true));
    if (!(await filled)) return ((filled = null), lazyLoadFailed());
    window.objKebabRows?.(menu);
    // The phone's action sheet, as `kebabMenu` opens (`openKebabSheet`).
    if (window.matchMedia(PHONE_ACTION_SHEET).matches) {
      openKebabSheet(menu, opener, "Note actions");
      return;
    }
    if (menu.classList.contains("hidden")) openActionMenu(menu, opener);
    else closeActionMenus();
  });
  opener.classList.add("icon-only");
  opener.setAttribute("aria-haspopup", "menu");
  opener.setAttribute("aria-expanded", "false");

  // **Built on first open, not on render: a scale fix.** This menu is about 50
  // nodes and `entryItem()` builds one per note card, on every renderEntries()
  // (every search keystroke, sort, filter and save); a 2,500-note notebook built
  // over a hundred thousand hidden nodes nobody opens. The opener renders eagerly
  // (it carries the aria state and a tab stop); the rows are `fillEntryMenu`
  // (entry-menu.js, lazy), awaited by the opener so `openActionMenu` finds a first item.
  let filled = null;

  wireMenuKeyboard(menu, opener);

  wrap.append(opener, menu);
  return wrap;
}

//: The draft's Publish button and menu row are this file's only callers (moved from note-cards.js for the boot gzip budget, 2026-11-11).
async function publishDraft(entry) {
  try {
    await apiJson(`/entries/${entry.id}`, { method: "PUT", body: JSON.stringify({ is_draft: false }) });
    entry.is_draft = false;
    pushEntryPutUndo(entry.id, "Published a draft", { is_draft: true }, { is_draft: false });
    await refreshEntries([entry.id]);
    toast("Published.");
  } catch (error) {
    toast(error.message || "Couldn't publish that draft.", true);
  }
}
