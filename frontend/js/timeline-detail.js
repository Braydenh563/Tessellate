// timeline-detail.js: what a Timeline row shows when it is opened (a note's
// body, its files and pictures, its actions; a document's line and Open),
// for the feed and the table alike. Loaded by `openTimelineRowDetail` in
// timeline.js the first time a row opens, so the boot carries none of it.

async function timelineRowDetail(detail, row) {
  const actions = document.createElement("div");
  actions.className = "row timeline-row-actions";

  //: A document's body is not a note's: it is long, it is `file_type`-shaped,
  //: and loading it into a row would put a thousand lines inside a feed. The
  //: row says what it is and opens the editor, which is where a document is
  //: read (TIMELINE_PLAN Phase 4).
  if (row.kind === "document") {
    const line = document.createElement("p");
    line.className = "timeline-row-body";
    line.textContent = row.snippet || "This document is empty.";
    detail.appendChild(line);
    actions.appendChild(
      smallButton("ph:file-text Open this document", "Open it in the editor", () => {
        switchTab("documents");
        openDocument(row.id);
      })
    );
    detail.appendChild(actions);
    return;
  }

  if (row.kind === "reminder") {
    const line = document.createElement("p");
    line.className = "timeline-row-body";
    line.textContent = row.done ? "Done." : "Not done yet.";
    detail.appendChild(line);
    //: A reminder attached to a note can reach it, which is the one link the
    //: Reminders tab has that a row here would otherwise lose.
    if (row.entryId) {
      actions.appendChild(
        smallButton("ph:note The note this is about", "Open the note this reminder is on", () => {
          flashEntry(row.entryId);
        })
      );
    }
    actions.appendChild(
      smallButton("ph:bell Open in reminders", "Show this in the Reminders tab", () => {
        switchTab("reminders");
      })
    );
    detail.appendChild(actions);
    return;
  }

  if (row.kind === "board") {
    // A map has no prose to render. Its own chip says what it is and how big
    // it is, which is what the Library and the dashboard show for one too.
    detail.append(mapChip(row.board, { interactive: false }));
    actions.appendChild(
      smallButton("ph:tree-structure Open this map", "Open this map on the whiteboard", () =>
        openWhiteboardBoard(row.board.id)
      )
    );
    detail.appendChild(actions);
    return;
  }

  const body = document.createElement("div");
  body.className = "timeline-row-body";
  body.textContent = "Loading…";
  const media = document.createElement("div");
  media.className = "timeline-row-media hidden";
  detail.append(body, media, actions);

  actions.appendChild(
    smallButton("ph:pencil-simple Open in editor", "Open this note in the Notes tab", () => {
      switchTab("notes");
      showNotesSection("browse");
      flashEntry(row.id);
    })
  );

  const entry = await apiJson(`/entries/${row.id}`).catch(() => null);
  // The row may have been closed, or the feed repainted, while this was in
  // flight; writing into a detached node would be invisible and confusing.
  if (!detail.isConnected) return;
  if (!entry) {
    body.textContent = "Couldn't load this note.";
    return;
  }
  body.replaceChildren();
  renderMarkdown(body, entry.content || "");
  renderTimelineRowMedia(entry, media);
}

//: **Everything attached, not only the pictures.** Reported twice against the
//: popup this moved out of: "a photo i attached to a note ... doesn't render"
//: and "files and attachments dont render in the timeline and popups". The
//: non-image half is `fileCard`, the same control the note cards, the chat
//: transcript and the widgets use, so a file looks the same wherever the app
//: shows it. Kept through the redesign on purpose: the popup went, the two
//: fixes it carried did not.
function renderTimelineRowMedia(entry, box) {
  box.replaceChildren();
  const all = entry.attachments || [];
  box.classList.toggle("hidden", all.length === 0);
  if (!all.length) return;
  const images = all.filter((a) => a.is_image);
  for (const attachment of all.filter((a) => !a.is_image)) {
    //: `url` is what every other file surface is given; attachments carry
    //: theirs as `/files/{id}` when the row does not spell one out.
    box.appendChild(
      fileCard(attachment.filename || attachment.name || "", attachment.url || `/files/${attachment.id}`)
    );
  }
  for (const attachment of images) {
    const img = document.createElement("img");
    img.className = "timeline-row-thumb";
    img.alt = attachment.filename;
    img.title = `${attachment.filename}: click to view full size`;
    attachmentObjectUrl(attachment)
      .then((url) => {
        img.src = url;
      })
      .catch(() => img.remove());
    img.addEventListener("click", () => {
      openLightbox(
        images.map((a) => ({ filename: a.filename, getUrl: () => attachmentObjectUrl(a) })),
        images.indexOf(attachment)
      );
    });
    box.appendChild(img);
  }
}

//: The keys are the app's (TIMELINE_PLAN §6): arrows walk the rows in document
//: order, Enter and Space open one in place, Escape closes it. Delegated to the
//: feed rather than bound per row, because a repaint builds every row again and
//: a listener per row is a listener per row per repaint.
//:
//: Guarded on the row itself being the target: a chip inside a row is its own
//: `role="button"` with its own Enter, and an arrow pressed inside one should
//: not steal the key from it.
