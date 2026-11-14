// documents-backlinks.js: what the Links panel draws once a document has backlinks or unlinked mentions
// (split out of documents.js, DOCUMENTS_PLAN L327).
//
// The rows with the sentence each link sits in, Link back, and the Link action that rewrites a mention in the note or
// document that wrote it. **Loaded when there is something to draw**: `renderDocBacklinks` in documents.js asks the
// server (`GET /documents/{id}/backlinks`) on every open, and a document with no links and no mentions, the common
// case, never fetches this file. It calls nothing from documents.js until a function here runs.
(() => {
  //: The unlinked-mentions section, made once and kept, for the same reason the
  //: properties panel is made in script: `tests/test_frontend_ids.py` pairs
  //: every `$("...")` with an element in index.html, and index.html belongs to
  //: another agent. Its shape is the backlinks section's exactly, so the two
  //: read as one panel and not as a panel and an add-on.
  function docMentionsHost(create = false) {
    const anchor = $("doc-backlinks-wrap");
    if (!anchor || !anchor.parentElement) return null;
    let host = anchor.parentElement.querySelector(".doc-mentions-wrap");
    if (!host && create) {
      host = document.createElement("div");
      host.className = "doc-outline-wrap doc-mentions-wrap";
      const heading = document.createElement("h3");
      heading.className = "doc-outline-title";
      heading.append(
        document.createTextNode("Unlinked mentions "),
        docSectionCount("doc-mentions-count")
      );
      //: The one line of description a section gets (CLAUDE.md's copy rule);
      //: anything longer belongs behind the '?' the heading carries.
      const help = document.createElement("p");
      help.className = "muted doc-outline-empty doc-mentions-help";
      help.textContent = "Notes and documents that name this one without linking to it.";
      const list = document.createElement("ul");
      list.className = "doc-outline doc-mentions";
      host.append(heading, help, list);
      anchor.insertAdjacentElement("afterend", host);
    }
    return host;
  }

  //: A heading's count, from the same recipe the outline's own heading uses, so
  //: the four sidebar sections agree about what a count looks like.
  function docSectionCount(className) {
    const count = document.createElement("span");
    count.className = `doc-outline-count ${className}`;
    return count;
  }

  //: Does the open document already point back at this source? Read from the
  //: text rather than remembered, because the answer changes with every
  //: keystroke and a stale "Linked both ways" is worse than no button.
  function docLinksTo(title) {
    const wanted = (title || "").trim().toLowerCase();
    if (!wanted) return false;
    const pattern = /\[\[([^[\]]{1,120})\]\]/g;
    const text = docText();
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (wikiLinkTarget(match[1]).trim().toLowerCase() === wanted) return true;
    }
    return false;
  }

  function docOpenBacklinkSource(row) {
    if (row.kind === "document") {
      openDocument(row.id);
      return;
    }
    switchTab("notes");
    showNotesSection("browse"); // focusing inside a hidden section does nothing
    flashEntry(row.id);
  }


  function docLinkBack(title) {
    const surface = docSurface();
    if (!surface) return;
    const at = surface.selectionStart;
    docReplaceRange(surface, at, surface.selectionEnd, `[[${title}]]`);
    markDocDirty();
    surface.focus();
    renderDocBacklinks();
  }

  //: **Link: rewrite the mention in the source that wrote it**, through that
  //: kind's own update route, so the note's revision, its `[[link]]` sync and
  //: its search vector all happen exactly as they do for a hand edit. Writing
  //: the row from here through a new endpoint would have been a second copy of
  //: machinery that already exists and already has guards.
  async function docLinkMention(row, button) {
    const title = (currentDoc?.title || "").trim();
    if (!title) return;
    button.disabled = true;
    try {
      let content = null;
      if (row.kind === "note") {
        //: Whole text: the offsets are into it and it is written back (`fullEntry`, INBOX 1525).
        content = (await fullEntry(row.id)).content;
      } else {
        content = (await apiJson(`/documents/${row.id}`)).content;
      }
      const slice = (content || "").slice(row.start, row.end);
      //: The offsets were taken when the panel was drawn. A source edited in
      //: another tab since would have this land in the middle of a sentence, so
      //: the span is checked against the title before anything is written and
      //: the panel is redrawn rather than guessed at.
      if (slice.toLowerCase() !== title.toLowerCase()) {
        toast("That mention has moved, the panel is refreshing.");
        renderDocBacklinks();
        return;
      }
      const next = content.slice(0, row.start) + `[[${title}]]` + content.slice(row.end);
      const mentionUndo = () =>
        pushRequestUndo(
          `Linked a mention in ${row.title}`,
          row.kind === "note" ? `/entries/${row.id}` : `/documents/${row.id}`,
          "PUT",
          { content },
          { content: next },
          () => (row.kind === "note" ? loadEntries() : loadDocuments(currentDoc?.id))
        );
      if (row.kind === "note") {
        await apiJson(`/entries/${row.id}`, {
          method: "PUT",
          body: JSON.stringify({ content: next }),
        });
        loadEntries();
      } else {
        const saved = await apiJson(`/documents/${row.id}`, {
          method: "PUT",
          body: JSON.stringify({ content: next }),
        });
        //: The answer is the row (DC7): patched in place, read only when it is not in the list.
        if (docs.some((d) => d.id === saved.id)) {
          docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
          renderDocList();
        } else await loadDocuments(currentDoc?.id);
      }
      mentionUndo();
      toast(`Linked from ${row.title}.`);
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
      renderDocBacklinks();
    }
  }

  function docBacklinkItem(row, linked) {
    const item = document.createElement("li");
    item.className = "doc-backlink";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "outline-link doc-backlink-title";
    setLabel(open, `${row.kind === "document" ? "ph:file-text" : "ph:note"} ${row.title}`);
    open.title = row.kind === "document" ? "Open this document" : "Show this note";
    open.addEventListener("click", () => docOpenBacklinkSource(row));
    const foot = document.createElement("div");
    foot.className = "doc-backlink-foot";
    if (linked) {
      const already = docLinksTo(row.title);
      const back = smallButton(
        already ? "Linked both ways" : "Link back",
        already
          ? "This document already links to it"
          : `Insert [[${row.title}]] where the caret is`,
        () => docLinkBack(row.title)
      );
      back.disabled = already;
      back.classList.add("doc-backlink-action");
      foot.appendChild(back);
    } else {
      const link = smallButton("Link", `Turn this mention into a link to ${currentDoc?.title || "this document"}`, () => {});
      link.classList.add("doc-backlink-action");
      link.addEventListener("click", () => docLinkMention(row, link));
      foot.appendChild(link);
    }
    item.append(open, docBacklinkContext(row), foot);
    return item;
  }

  //: Draws the two lists and their counts; the caller has already read the server's answer.
  function docBacklinksPaint(links, mentions) {
    const wrap = $("doc-backlinks-wrap");
    const list = $("doc-backlinks");
    wrap.classList.toggle("hidden", !links.length);
    list.replaceChildren();
    for (const row of links) list.appendChild(docBacklinkItem(row, true));
    const count = wrap.querySelector(".doc-backlinks-count") || docSectionCount("doc-backlinks-count");
    if (!count.parentElement) wrap.querySelector("h3")?.append(document.createTextNode(" "), count);
    count.textContent = links.length ? String(links.length) : "";

    const host = docMentionsHost(mentions.length > 0);
    if (host) {
      const mentionList = host.querySelector(".doc-mentions");
      mentionList.replaceChildren();
      for (const row of mentions) mentionList.appendChild(docBacklinkItem(row, false));
      host.querySelector(".doc-mentions-count").textContent = mentions.length ? String(mentions.length) : "";
      host.classList.toggle("hidden", !mentions.length);
    }
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { docBacklinksPaint });
})();
