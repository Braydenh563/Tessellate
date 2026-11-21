// documents-embeds.js: `![[...]]` embeds and wiki-link targets (split out of
// documents.js, audit 1031 DC13 remainder).
//
// What is here: what a `![[name]]` draws in place of a link (`docEmbedNode`,
// the Live image frame `docImageLive`, the chip and `docEmbedFill`) and the
// resolution of a wiki-link name to its target and the opening of it
// (`docResolveWikiTarget`, `docOpenWikiTarget`, `docOpenLink`). What stayed in
// documents.js: `docPhase2State` (its `imageRefocus` is shared with the print
// sheet) and the Read view's call sites, which reach in here from inside
// functions.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: documents.js and documents-cm.js call in here only
// from inside functions, while this file's own top level declares and reads
// nothing from them. One closure; what other files call is the
// `Object.assign` at the foot.
(() => {
  // -----------------------------------------------------------------------------
  // Embeds: `![[…]]` draws the thing, not a link to it
  // -----------------------------------------------------------------------------
  //
  // DOCUMENTS_PLAN Phase 3 item 3, with the sentence that decides how it is
  // built: **one renderer per kind, app-wide.** A note embedded in a document
  // renders through `entryItem`, the same function that draws every note card in
  // the Notes tab; a map through `mapChip` and `mapPreview`, which app.js's own
  // comment already calls "one mapChip() and one mapPreview(), used by all"; a
  // file through `fileCard`, the Library's tile. Nothing here draws a card. The
  // most expensive recurring mistake in this project is building a second one of
  // something that exists, and four card renderers for one app would be exactly
  // that.
  //
  // What resolves a name is `docResolveWikiTarget`, which is what a plain
  // `[[link]]` already uses, plus the Library's own index for files: an embed
  // and a link have to point at the same thing or the two gestures disagree
  // about what a name means.

  //: A name to a thing. The note, board and document indexes are in the page
  //: already; the Library's file list is not, so it is fetched once and the
  //: widget fills itself in when it lands (`docEmbedFill`).
  function docEmbedTarget(name) {
    const target = docResolveWikiTarget(name);
    if (target) return target;
    const wanted = String(name || "").trim().toLowerCase();
    if (!wanted) return null;
    const files = typeof editorFileCache !== "undefined" && editorFileCache ? editorFileCache : [];
    const named = (row) => String(row.original_name || row.filename || "").toLowerCase();
    const file =
      files.find((row) => named(row) === wanted) ||
      files.find((row) => named(row).replace(/\.[^.]+$/, "") === wanted);
    if (file) return { kind: "file", file };
    //: **Audio is a recording, never a file** (WORLD_CLASS_PLAN "Audio in the
    //: notebook", decision 2): the only thing `![[…]]` can play is a recording,
    //: named the way the Library names it.
    const take = (docRecordings.rows || []).find((row) => String(row.title || "").trim().toLowerCase() === wanted);
    return take ? { kind: "recording", recording: take } : null;
  }

  //: The Library's recordings, fetched once when an embed names something that
  //: does not resolve yet, the way the file index is.
  const docRecordings = { rows: null, pending: null, at: 0 };
  const docBoardAsked = new Set();
  //: A list older than half a minute is asked for again (a take made since still embeds); a failed ask counts as an answer.
  const docRecordingsStale = () => Date.now() - docRecordings.at > 30000;
  function docRecordingsLoad() {
    docRecordings.pending ||= apiJson("/recordings?limit=500", { silent: true })
      .then((body) => {
        docRecordings.rows = Array.isArray(body?.recordings) ? body.recordings : [];
      })
      .catch(() => {})
      .finally(() => {
        docRecordings.pending = null;
        docRecordings.at = Date.now();
      });
    return docRecordings.pending;
  }

  //: **A board embedded in a document is edited where it is** (documents-board.js): "Edit here" opens the board in a panel over
  //: the document, and `redraw` runs when the panel closes. Live draws the card here; Read's card is markdown.js's, so
  //: `docEmbedFill.editButtons` (called from `renderDocPreview`) puts the same button after each of those.
  function boardEditButton(id, titleOf, redraw) {
    const edit = smallButton("ph:pencil-simple Edit here", "Edit this board in a panel over the document", () => ensureModule("docBoard").then(() => {
      document.addEventListener("board-edited", redraw, { once: true });
      edit.dispatchEvent(new CustomEvent("board-edit", { bubbles: true, detail: { id, title: titleOf() } }));
    }));
    edit.classList.add("doc-embed-board-edit");
    edit.dataset.boardId = String(id);
    return edit;
  }
  docEmbedFill.editButtons = (root) => {
    for (const card of root.querySelectorAll(".board-embed[data-board-ref]")) {
      if (card.nextElementSibling?.classList.contains("doc-embed-board-edit")) continue;
      const title = () => card.querySelector(".board-embed-title")?.textContent || "";
      card.after(boardEditButton(Number(card.dataset.boardRef), title, renderDocPreview));
    }
  };

  //: The card for a target, from whichever renderer already owns that kind.
  //: Returns null for a kind with no card of its own, which the caller draws as
  //: the link chip it would have been.
  function docEmbedNode(target, name) {
    if (!target) return null;
    //: **A block embed is the block's own markdown, rendered.** Not a card: the
    //: thing being embedded is a paragraph of this notebook's own writing, and
    //: every other renderer here draws an *object* (a note, a map, a file). The
    //: quote bar and the source line are what say where it came from.
    if (target.kind === "block") {
      const text = docBlockDocumentText(target.doc);
      if (text == null) return null; // not fetched yet; `docEmbedFill` asks
      const found = docBlockFind(text, target.blockId);
      const box = document.createElement("blockquote");
      box.className = "doc-embed-block";
      const body = document.createElement("div");
      body.className = "doc-embed-block-body";
      if (found) renderMarkdown(body, found.text);
      else body.textContent = "That block is not in the document any more.";
      if (!found) body.classList.add("muted");
      const source = document.createElement("button");
      source.type = "button";
      source.className = "linklike doc-embed-block-source";
      source.textContent = target.doc.title || "Untitled";
      source.title = "Open the document at this block";
      source.addEventListener("click", () => docOpenResolvedWikiTarget(target, name));
      box.append(body, source);
      //: A synced block (documents-synced.js): edited here, written into the document it lives in.
      if (found && currentDoc?.id !== target.doc.id) {
        const edit = smallButton("ph:pencil-simple", "Edit this block here", () => ensureModule("docSynced").then(() => box.dispatchEvent(new CustomEvent("synced-edit", { bubbles: true, detail: { text: found.text, target, draw: () => docEmbedNode(target, name), cache: docBlockTextCache } }))));
        edit.classList.add("icon-only", "doc-embed-block-edit");
        box.append(edit);
      }
      return box;
    }
    if (target.kind === "note") {
      //: `entryItem` is an `<li>`, and `.entry-list li` is where a note card's
      //: whole appearance lives: handed out on its own it would render as a
      //: bare list item. The list around it is the card's other half.
      const list = document.createElement("ul");
      list.className = "entry-list";
      //: The card is `entryItem` (entry-card.js, lazy): the list is placed at once and filled when the file is in.
      ensureModule("entryCard").then((ok) => (ok && window.entryItem ? list.appendChild(entryItem(target.entry)) : lazyLoadFailed("Notes")));
      return list;
    }
    //: A document is a card (`mdDocumentCard`, app.js), the one the Read view
    //: draws for the same line; it used to be a chip saying there was no
    //: preview for a document yet.
    if (target.kind === "document" && target.doc) return mdDocumentCard(target.doc, name);
    if (target.kind === "board") {
      const box = document.createElement("span");
      box.className = "doc-embed-map";
      box.appendChild(mapChip(target.entry, { interactive: false }));
      box.appendChild(mapPreview(target.entry, { size: "card" }));
      box.appendChild(boardEditButton(target.entry.id, () => target.entry.title, () => {
        //: Looked up again: the board index the panel refreshed holds a new row, and the old one still says the old count.
        const fresh = box.isConnected ? docEmbedNode(docEmbedTarget(name), name) : null;
        if (fresh) box.replaceWith(fresh);
      }));
      return box;
    }
    if (target.kind === "recording") {
      //: The browser's own audio controls under the take's name; nothing loads
      //: until Play (`preload = "none"`), the way a recording row does.
      const box = document.createElement("figure");
      box.className = "doc-embed-recording";
      const title = document.createElement("figcaption");
      title.textContent = target.recording.title || name;
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = `/media/recordings/${target.recording.id}`;
      audio.setAttribute("aria-label", `Recording: ${target.recording.title || name}`);
      box.append(title, audio);
      return box;
    }
    if (target.kind === "file") {
      const file = target.file;
      const url = file.url || `/files/${file.id}`;
      const label = file.original_name || file.filename || name;
      if (file._isImage) {
        //: An image embed is the image. `fileCard` would be a tile with the
        //: picture's *name* on it, which is what `![[photo.png]]` is asking not
        //: to have to look at.
        const img = document.createElement("img");
        img.className = "cm-md-image";
        img.src = mediaSrc(url);
        img.alt = label;
        img.loading = "lazy";
        return img;
      }
      return fileCard(label, url);
    }
    return null;
  }

  //: The Live editor's half of the picture control (image-layout.js
  //: `imageWireEdit`): the picture's markdown is found from where its widget
  //: sits (`posAtDOM`), its alt rewritten in one change, one Undo step.
  function docImageLive(view, frame, options) {
    const root = () => frame.closest(".cm-md-figure") || frame;
    const write = (change, kind) => {
      let at;
      try {
        at = view.posAtDOM(root());
      } catch {
        return false;
      }
      const head = view.state.doc.sliceString(at, Math.min(view.state.doc.length, at + 2000));
      const m = /^!\[([^\]\n]*)\]\(/.exec(head);
      if (!m) return false;
      const alt = imageAltWith(m[1], change);
      if (alt === m[1]) return false;
      docPhase2State.imageRefocus = kind && frame.contains(document.activeElement) ? { at, kind } : null;
      view.dispatch({ changes: { from: at + 2, to: at + 2 + m[1].length, insert: alt } });
      return true;
    };
    const widest = () => Math.max(IMAGE_MIN, Math.floor(view.contentDOM.getBoundingClientRect().width - 48));
    const controls = imageWireEdit(frame, options, { write, widest });
    //: The control that had the keys (the grip, or the align button after its
    //: menu) keeps them after its write redraws the picture.
    const held = docPhase2State.imageRefocus;
    if (held == null) return;
    requestAnimationFrame(() => {
      if (docPhase2State.imageRefocus !== held || !frame.isConnected) return;
      let at = -1;
      try {
        at = view.posAtDOM(root());
      } catch {
        at = -1;
      }
      if (at === held.at) {
        docPhase2State.imageRefocus = null;
        (held.kind === "grip" && controls.grip ? controls.grip : controls.align).focus({ preventScroll: true });
      }
    });
  }

  //: The chip an embed falls back to: a name that resolves to nothing yet, and a
  //: document, which is the one link target in this app with no card of its own.
  //: Said in words rather than left blank, because an embed that draws nothing
  //: reads as a bug in the editor rather than as a name with nothing behind it.
  function docEmbedChip(name, target) {
    const chip = document.createElement("span");
    chip.className = "chip doc-embed-chip";
    chipWords(chip, name);
    chip.title = target
      ? `\u201c${name}\u201d opens in Documents; there is no inline preview for a document yet`
      : `Nothing called \u201c${name}\u201d yet`;
    if (!target) chip.classList.add("muted");
    return chip;
  }

  function docEmbedFill(host, name, options = null) {
    const target = docEmbedTarget(name);
    const node = docEmbedNode(target, name);
    if (node) {
      host.replaceChildren(node);
      //: An image embed is the one kind these options mean anything for; a note
      //: card with a width of 300 is a card somebody has squashed.
      if (node.tagName === "IMG") imageApplyOptions(node, options);
      return;
    }
    //: A block embed of a document nobody has opened has no text to draw yet.
    //: One fetch per document, cached, and the widget fills itself in rather
    //: than waiting for a repaint a document nobody is typing in will never get.
    if (target && target.kind === "block") {
      host.replaceChildren(docEmbedChip(name, target));
      if (docBlockTextCache.has(target.doc.id)) return;
      docBlockTextCache.set(target.doc.id, null);
      apiJson(`/documents/${target.doc.id}`, { silent: true })
        .then((doc) => {
          docBlockTextCache.set(target.doc.id, doc.content || "");
          if (!host.isConnected) return;
          const later = docEmbedNode(target, name);
          if (later) host.replaceChildren(later);
        })
        .catch(() => {
          docBlockTextCache.delete(target.doc.id);
        });
      return;
    }
    //: `keep` is the Read view asking: it already drew its own "Nothing called that yet" box and only wants it
    //: swapped if the name turns out to be a file or a recording once they have loaded.
    if (!options?.keep) host.replaceChildren(docEmbedChip(name, target));
    //: The Library's file index and its recordings are the two things that
    //: might not be loaded yet, so a name that is one of them reads as "nothing
    //: called that" until they arrive. One fetch each, once, and the widget
    //: fills itself in rather than waiting for a repaint that a document nobody
    //: is typing in will never get.
    if (target) return;
    const loads = [];
    const loadFiles = window.editorLoadFiles;
    if (loadFiles && !(typeof editorFileCache !== "undefined" && editorFileCache)) loads.push(loadFiles());
    if (docRecordingsStale()) loads.push(docRecordingsLoad());
    //: A `![[board:12]]` resolves from the board index, which a document has usually never asked for. Once per board id, so a
    //: dead reference costs one walk, not one per redraw (markdown.js `boardEmbedForced` does the same for Read's card).
    const board = window.boardEmbedRef?.(name);
    if (board && !docBoardAsked.has(board.id)) {
      docBoardAsked.add(board.id);
      loads.push(window.loadMapBoardIndex?.(true));
    }
    if (!loads.length) return;
    Promise.all(loads.map((load) => Promise.resolve(load).catch(() => {}))).then(() => {
      if (!host.isConnected) return;
      const later = docEmbedNode(docEmbedTarget(name), name);
      if (later) {
        host.replaceChildren(later);
        if (later.tagName === "IMG") imageApplyOptions(later, options);
      }
    });
  }

  //: **One resolver for a `[[name]]`, and now it really is one.**
  //:
  //: Reported directly: "[[]] links work between notes in the your notes tab,
  //: but it is still coming up with that error in the documents editor",
  //: with a screenshot of `[[# Girl with bell]]` toasting "Nothing called ...
  //: yet" beside a note whose first line is exactly that.
  //:
  //: Both of this file's resolvers looked a note up as
  //: `allEntries.find(e => e.title === wanted)`, an *exact* match on a
  //: *derived* field: `EntryOut.title` is the note's first line with its `# `
  //: stripped (schemas.py says so, and it is `None` for a note whose first
  //: line is not a heading). The `[[…]]` text the picker inserts is the note's
  //: opening words verbatim, `# ` and all, so the two forms differ by exactly
  //: the characters the derivation removes and the comparison could never be
  //: true. `resolveWikiTarget` (notes-list.js) is the resolver the Notes tab has used
  //: all along: it matches a vault note by its file stem, a board by title, a
  //: note by *content prefix* (which is what makes the picker's opening-words
  //: form resolve), and a document by title or title prefix.
  //:
  //: Documents are still tried first, which the previous code did deliberately
  //: and is worth keeping: a document and a note sharing a name, clicked from
  //: inside a document, should open the document. Everything else defers to
  //: the one resolver, so the drift the old comments kept promising was
  //: impossible cannot happen again.
  function docResolveWikiTarget(name) {
    //: **A block reference is resolved before anything else**, because
    //: `Doc title#^abc123` is not a name and would resolve to nothing at all if
    //: it were looked up as one. Documents only: a block id is written into a
    //: document's own text by the command that copies the link, and a note has
    //: no editor here to put one in. `docBlockRefSplit` of a plain name returns
    //: a null id, so this costs every other link one comparison.
    const ref = docBlockRefSplit(wikiLinkTarget(name));
    if (ref.blockId) {
      const base = ref.name ? docResolveWikiTarget(ref.name) : { kind: "document", doc: currentDoc };
      if (base && base.kind === "document" && base.doc) {
        return { kind: "block", doc: base.doc, blockId: ref.blockId };
      }
      return null;
    }
    //: `[[Target|Shown]]` names its document by the part before the bar.
    const wanted = String(wikiLinkTarget(name) || "").trim().toLowerCase();
    if (!wanted) return null;
    const asDoc = docs.find((doc) => (doc.title || "").trim().toLowerCase() === wanted);
    if (asDoc) return { kind: "document", doc: asDoc };
    return resolveWikiTarget(name);
  }

  //: What a resolved target is called, for a link's tooltip. A note has no
  //: title of its own worth showing (see above), so it borrows the preview
  //: text every other note list in the app labels a note with.
  function docWikiTargetLabel(target) {
    if (!target) return "";
    if (target.kind === "block") return `${target.doc.title || ""} (a block)`;
    if (target.kind === "document") return target.doc.title || "";
    if (target.kind === "board") return target.entry.title || "";
    const entry = target.entry || {};
    const text =
      typeof notePreviewText === "function"
        ? notePreviewText(entry.content || "")
        : entry.content || "";
    //: `notePreviewText` strips the markdown but keeps the note's line breaks
    //: and does not shorten. A `title` attribute renders both literally, so a
    //: note would hand the tooltip its whole body across as many lines as it
    //: has: collapsed to one line and cut here.
    const line = text.replace(/\s+/g, " ").trim();
    return line.length > 60 ? `${line.slice(0, 60).trimEnd()}…` : line;
  }

  function docOpenResolvedWikiTarget(target, name) {
    if (!target) {
      toast(`Nothing called "${name}" yet.`, "info");
      return;
    }
    if (target.kind === "block") {
      //: Open the document first *then* find the block, and only when it is a
      //: different document: opening the one you are in would throw away the
      //: unsaved keystroke that made the link worth following.
      const reveal = () => docRevealBlock(target.blockId);
      if (currentDoc && currentDoc.id === target.doc.id) reveal();
      else Promise.resolve(openDocument(target.doc.id)).then(reveal);
      return;
    }
    if (target.kind === "document") {
      openDocument.back = true;
      openDocument(target.doc.id);
    }
    else if (target.kind === "board") openWhiteboardBoard(target.entry.id);
    else flashEntry(target.entry.id);
  }

  function docOpenWikiTarget(name) {
    docOpenResolvedWikiTarget(docResolveWikiTarget(name), name);
  }

  //: Ctrl+click on a link chip. Same-origin paths open in the app; anything else
  //: opens in a new tab with `noopener`, which is what every other outbound link
  //: in this app does. `javascript:` and `data:` are refused outright rather
  //: than handed to the browser.
  function docOpenLink(href) {
    const clean = String(href || "").trim();
    //: The same allowlist every rendered link goes through (audit 1028 D15).
    if (!clean || safeHref(clean) === "#") return;
    //: This app's own address (INBOX 483) opens its view in this window.
    const hash = appAddressHash(clean);
    if (hash) location.hash = hash;
    else window.open(clean, "_blank", "noopener,noreferrer");
  }

  //: **The document editor as a paste and drop target** (docdog-1026, moved from
  //: settings-wiring.js, audit 161 D24). Its engine sits under `#doc-editor`, not
  //: `.note-surface`, so a screenshot pasted or a picture dropped into a document
  //: did nothing at all, while the "/" menu's Image row promised both. The
  //: surface answers the same box interface as a textarea. A code document is
  //: text, and keeps what it was given.
  function docFileDropBox() {
    const surface = window.docSurface?.();
    return surface && !surface.classList.contains("doc-content-code") ? surface : null;
  }

  //: **A `#tag` in the Read view is a chip** (L349). `tagParts` splits a text
  //: into plain strings and `[name]` tags, with the same rule as the editor's
  //: `#tag` completion: a `#` that opens a word and a letter after it, so not
  //: `C#`, `##x` or `#9`. Pressing a chip asks Find for documents with that tag.
  docEmbedFill.tagParts = (text) => {
    const parts = [];
    let from = 0;
    for (const m of text.matchAll(/(^|\s)#(\p{L}[\p{L}\p{N}_-]*)/gu)) {
      const at = m.index + m[1].length;
      if (at > from) parts.push(text.slice(from, at));
      parts.push([m[2]]);
      from = at + 1 + m[2].length;
    }
    if (from < text.length) parts.push(text.slice(from));
    return parts;
  };
  const SKIP_TAG_CHIPS = "code, pre, a, button, h1, h2, h3, h4, h5, h6, .wiki-link, .doc-tag-chip, .katex, .mermaid";
  docEmbedFill.tagChips = (root) => {
    const found = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.nodeValue.includes("#") && !node.parentElement?.closest(SKIP_TAG_CHIPS)) found.push(node);
    }
    for (const node of found) {
      const parts = docEmbedFill.tagParts(node.nodeValue);
      if (!parts.some(Array.isArray)) continue;
      node.replaceWith(...parts.map((part) => {
        if (!Array.isArray(part)) return document.createTextNode(part);
        const [tag] = part;
        const el = chip(`#${tag}`, "tag doc-tag-chip", () => openFinder("#" + tag, { kind: "document" }));
        el.title = `Find documents that mention #${tag}`;
        return el;
      }));
    }
  };

  //: The file's whole surface: what documents.js, documents-cm.js and markdown.js call.
  Object.assign(window, { docEmbedFill, docImageLive, docResolveWikiTarget, docWikiTargetLabel, docOpenResolvedWikiTarget, docOpenWikiTarget, docOpenLink, docFileDropBox });
})();
