// documents-links-panels.js: the Notes and Bookmarks panels and the backlink insert.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  let docBacklinksToken = 0;
  function docInsertReferenceLink(bookmark) {
    const surface = docSurface();
    if (!surface) return;
    // Brackets would end the link text early, and a space or ")" the url.
    const text = String(bookmark.title || bookmark.url).replace(/[[\]]/g, "");
    const url = String(bookmark.url).replace(/ /g, "%20").replace(/\)/g, "%29");
    docReplaceRange(surface, surface.selectionStart, surface.selectionEnd, `[${text}](${url})`);
    markDocDirty();
    surface.focus();
  }
  async function renderDocBacklinks() {
    const wrap = $("doc-backlinks-wrap");
    const list = $("doc-backlinks");
    if (!wrap || !list) return;
    const token = ++docBacklinksToken;
    let body = null;
    if (currentDoc?.id != null) {
      body = await apiJson(`/documents/${currentDoc.id}/backlinks`, { silent: true }).catch(() => null);
    }
    if (token !== docBacklinksToken) return; // a newer document answered first
    const links = (body && body.links) || [];
    const mentions = (body && body.mentions) || [];
    //: Nothing to draw and nothing drawn before: the panel stays hidden without fetching its code
    //: (documents-backlinks.js). Rows drawn for the last document are cleared by the piece.
    if (!links.length && !mentions.length && !list.firstChild && !wrap.parentElement?.querySelector(".doc-mentions-wrap")) {
      wrap.classList.add("hidden");
      return;
    }
    if (!(await lazyScript("/js/documents-backlinks.js"))) return toast("The links panel could not be loaded.", true, { action: ["Try again", renderDocBacklinks] });
    if (token === docBacklinksToken) docBacklinksPaint(links, mentions);
  }
  function renderDocNotes() {
    const wrap = $("doc-notes-wrap");
    const list = $("doc-notes");
    const notes = (currentDoc && currentDoc.notes) || [];
    wrap.classList.toggle("hidden", !notes.length);
    list.replaceChildren();
    for (const note of notes) {
      const item = document.createElement("li");
      const open = document.createElement("button");
      open.type = "button";
      open.className = "outline-link";
      if (note.is_private) {
        setLabel(open, "ph:lock (private note)");
      } else {
        renderInlineMarkdown(open, note.preview, [], true);
      }
      open.title = "Show this note";
      open.addEventListener("click", () => {
        switchTab("notes");
        showNotesSection("browse"); // focusing inside a hidden section does nothing
        flashEntry(note.id);
      });
      const remove = smallButton("ph:x", "Detach this note from the document", () =>
        unlinkDocNoteWithUndo(note).catch((e) => toast(e.message, true))
      );
      item.append(open, remove);
      list.appendChild(item);
    }
  }
  async function renderDocBookmarks() {
    const list = $("doc-bookmarks");
    if (!list || !currentDoc) return;
    let attached;
    try {
      attached = await apiJson(`/documents/${currentDoc.id}/bookmarks`);
    } catch {
      return;
    }
    if (currentDoc?.id == null) return; // the document changed while this was in flight
    list.replaceChildren();
    for (const bookmark of attached) {
      const item = document.createElement("li");
      //: **One row per reference** (the owner, 2026-10-10: "references ... with
      //: the buttons on them"): its icon and title, then two icon buttons that
      //: lie over the row's right end only while the row is pointed at or
      //: focused (always on touch), so a long title keeps its width at rest.
      //: Earlier a link chip, an "Aa" and an X sat loose beside each other.
      item.className = "doc-outline-row doc-ref-row";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "outline-link";
      setLabel(open, `ph:link ${bookmark.title || bookmark.url}`);
      open.title = bookmark.url;
      // safeHref() (notes-list.js): the same scheme guard library.js's bookmark rows
      // use, so a bookmark saved before INBOX 310's write-time check existed
      // can't reach window.open() with an unlisted scheme from here either.
      open.addEventListener("click", () => window.open(safeHref(bookmark.url), "_blank", "noopener,noreferrer"));
      //: **Into the text, not only beside it** (owner, 0.3.31: "how do I
      //: hyperlink or attach bookmark references in a document??"). Writes
      //: `[title](url)` at the caret, the way `docLinkBack` writes `[[Source]]`:
      //: every insert in this editor goes where you are.
      const insert = smallButton("ph:cursor-text", "Insert a link to it at the caret", () =>
        docInsertReferenceLink(bookmark)
      );
      const remove = smallButton("ph:link-break", "Remove it from this document", () =>
        docBookmarkWithUndo(bookmark.id, false).catch((e) => toast(e.message, true))
      );
      const tools = document.createElement("span");
      tools.className = "doc-ref-tools";
      for (const button of [insert, remove]) button.classList.add("icon-only", "doc-outline-row-action");
      tools.append(insert, remove);
      item.append(open, tools);
      list.appendChild(item);
    }
  }
  async function attachBookmarkToDocument() {
    if (!currentDoc) return;
    let all;
    try {
      all = await apiJson("/bookmarks");
    } catch (error) {
      toast(error.message, true);
      return;
    }
    if (!all.length) {
      toast("No saved bookmarks yet, add one in Library → Bookmarks first.");
      return;
    }
    const wrap = $("doc-bookmarks-wrap");
    //: **The picker and its way out are one row, and it replaces the button
    //: that opened it.** Before this the select was inserted above a
    //: still-visible "Attach a link", so asking to attach one left two
    //: full-width controls stacked with no way to change your mind but to pick
    //: something: the other half of "References stacks a close button above its
    //: own select". Opening it twice also stacked two selects, because nothing
    //: checked for one already there.
    const existing = wrap.querySelector(".doc-attach-row");
    //: The row's Escape listener goes with it: removing the row alone left the document-level one
    //: behind for every reopen (L327). One controller per picker, kept on this function.
    attachBookmarkToDocument.escape?.abort();
    if (existing) existing.remove();
    const row = document.createElement("div");
    row.className = "row doc-attach-row";
    const select = document.createElement("select");
    select.className = "bookmark-attach-picker";
    const placeholder = document.createElement("option");
    placeholder.textContent = "Pick a saved bookmark…";
    placeholder.value = "";
    select.appendChild(placeholder);
    for (const bookmark of all) {
      const option = document.createElement("option");
      option.value = String(bookmark.id);
      option.textContent = bookmark.title || bookmark.url;
      select.appendChild(option);
    }
    const escape = new AbortController();
    attachBookmarkToDocument.escape = escape;
    const close = () => {
      escape.abort();
      row.remove();
      $("doc-attach-bookmark").classList.remove("hidden");
      $("doc-attach-bookmark").focus();
    };
    //: Escape as well as the ✕, because a picker that opened on a button press
    //: is the shape everyone tries Escape on first.
    //:
    //: **On the document, not on the `<select>` or even on the row.**
    //: `enhanceSelect` in sheets-selects.js replaces every select in the page with a shell
    //: holding a `<button>` opener and a listbox, and takes the real select out
    //: of the tab order (`select-native-hidden`, `tabindex="-1"`), so the
    //: `select.focus()` below lands nowhere and the keystroke is dispatched at
    //: `document.body`. A listener on the element never fired; one on the row
    //: never fired either, because the event's target was outside it. Both were
    //: caught by measuring, not by reading: the sweep pressed Escape twice and
    //: the picker stayed open twice, and the row's children read back as SPAN
    //: and BUTTON rather than SELECT and BUTTON. Removed again in `close`, so
    //: nothing outlives the picker.
    function onEscape(event) {
      if (event.key !== "Escape") return;
      //: Only when the listbox is shut. Escape inside an open listbox is that
      //: menu's own way out, and taking it would close the picker from under
      //: someone who was only backing out of the list.
      if (row.querySelector('[aria-expanded="true"]')) return;
      event.preventDefault();
      close();
    }
    document.addEventListener("keydown", onEscape, { capture: true, signal: escape.signal });
    select.addEventListener("change", async () => {
      if (!select.value || !currentDoc) return;
      await docBookmarkWithUndo(Number(select.value), true).catch((e) => toast(e.message, true));
      close();
    });
    const cancel = smallButton("ph:x", "Don't attach a link", close);
    cancel.classList.add("doc-outline-row-action");
    row.append(select, cancel);
    wrap.insertBefore(row, $("doc-attach-bookmark"));
    $("doc-attach-bookmark").classList.add("hidden");
    //: `focusSelect` (sheets-selects.js), which is where this trap and its answer now live
    //: together. It was open-coded here first, before a sweep of the rest of the
    //: app found three more call sites doing the plain `.focus()` silently.
    focusSelect(select);
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { renderDocBacklinks, renderDocNotes, renderDocBookmarks, attachBookmarkToDocument });
})();
