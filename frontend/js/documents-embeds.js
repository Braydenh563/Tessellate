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
    return file ? { kind: "file", file } : null;
  }

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
    host.replaceChildren(docEmbedChip(name, target));
    //: The Library's index is the one thing that might not be loaded yet, so a
    //: name that is a file reads as "nothing called that" until it arrives. One
    //: fetch, once, and the widget fills itself in rather than waiting for a
    //: repaint that a document nobody is typing in will never get.
    if (target || typeof editorLoadFiles !== "function") return;
    if (typeof editorFileCache !== "undefined" && editorFileCache) return;
    editorLoadFiles()
      .then(() => {
        if (!host.isConnected) return;
        const later = docEmbedNode(docEmbedTarget(name), name);
        if (later) {
          host.replaceChildren(later);
          if (later.tagName === "IMG") imageApplyOptions(later, options);
        }
      })
      .catch(() => {});
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
    if (target.kind === "document") openDocument(target.doc.id);
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

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { docEmbedFill, docImageLive, docResolveWikiTarget, docWikiTargetLabel, docOpenResolvedWikiTarget, docOpenWikiTarget, docOpenLink });
})();
