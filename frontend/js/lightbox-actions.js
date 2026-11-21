// lightbox-actions.js: re-check a note with the model, attach a file to a note, attach from the Library; moved out of lightbox.js on 2026-10-12 for the boot gzip budget. Each is a menu or button action whose return nobody reads: `LAZY_ENTRY_POINTS.lightboxActions` (app.js) stands in.

// The Add context / continue / remind boxes inside an entry card.
// Ask the AI to re-evaluate one note, then show its suggestions inline.
(() => {
  async function reevaluateEntry(entry) {
    closeActionMenus();
    toast("Atlas is reading this note…");
    // Show a spinner on this exact card while the AI works.
    busyEntryId = entry.id;
    renderEntries();
    try {
      const result = await apiJson(`/entries/${entry.id}/reevaluate`, { method: "POST" });
      // If the confidence actually changed, flash the badge on the next render.
      const newConfidence = result.entry ? result.entry.ai_confidence : null;
      if (newConfidence !== null && newConfidence !== entry.ai_confidence) {
        flashConfidenceId = entry.id;
      }
      inlineAction = { id: entry.id, kind: "reevaluate", data: result };
      busyEntryId = null;
      await loadEntries(); // reflect the refreshed confidence/category, then show suggestions
    } catch (error) {
      busyEntryId = null;
      renderEntries();
      toast(error.message || "Atlas could not read this note.", true);
    }
  }


  function attachFileTo(entry) {
    const input = document.createElement("input");
    input.type = "file";
    // The backend already accepts one attachment per POST and a note already
    // renders any number of them, the only thing missing was the picker
    // itself only ever taking `files[0]`, silently dropping a multi-select.
    input.multiple = true;
    input.addEventListener("change", async () => {
      const files = [...input.files];
      if (!files.length) return;
      let failures = 0;
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        // `api.upload` (F5): multipart keeps its own type, and both headers ride.
        try {
          await api.upload(`/entries/${entry.id}/files`, form);
        } catch (error) {
          failures++;
          toast(`${file.name}: ${error.message}`, true);
        }
      }
      const attached = files.length - failures;
      if (attached > 0) {
        toast(attached === 1 ? `Attached ${files[0].name}.` : `Attached ${attached} files.`);
      }
      await loadEntries();
    });
    input.click();
  }

  // The Library's other half of "upload directly, attach later", asked for
  // directly. `attachFileTo` above always opens a fresh disk picker; this
  // instead offers whatever already lives in the Library's image/PDF gallery
  // (MediaUpload: GET /media), so an image uploaded once doesn't need
  // re-uploading onto every note that wants it. Note attachments (Attachment,
  // PDFs, docs, audio: attachFileTo's own domain) have no "floating, not yet
  // attached to anything" state to pick from, so this is images/PDFs only,
  // same as the Library gallery itself.
  async function attachFromLibrary(entry) {
    const images = await apiJson("/media", { silent: true }).catch(() => null);
    if (!images) {
      toast(voiceLine("failed", { what: "load the Library gallery" }), true, { action: ["Try again", () => attachFromLibrary(entry)] });
      return;
    }
    if (!images.length) {
      toast("Nothing in the Library gallery yet, upload one from Library → Files & Images first.", "info");
      return;
    }

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay library-attach-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Attach from Library");

    const card = document.createElement("div");
    card.className = "card modal-card";
    const head = document.createElement("div");
    head.className = "row space-between library-head";
    const title = document.createElement("h2");
    title.textContent = "Attach from Library";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "ghost small";
    close.setAttribute("aria-label", "Close");
    setLabel(close, "ph:x");
    head.append(title, close);
    const hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = "Pick an image or PDF already in the Library to attach it to this note.";
    const grid = document.createElement("div");
    grid.className = "library-image-grid library-attach-grid";

    const done = () => {
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        done();
      }
    };
    close.addEventListener("click", done);
    wireBackdropClose(overlay, () => done());
    document.addEventListener("keydown", onKey, true);

    const isPdf = (url) => /\.pdf$/i.test(url);
    for (const image of images) {
      const fig = document.createElement("figure");
      fig.className = "library-image-tile";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "library-attach-pick";
      button.title = `Attach “${image.original_name}”`;
      if (isPdf(image.url)) {
        const icon = document.createElement("i");
        icon.className = "ph ph-file-pdf";
        icon.setAttribute("aria-hidden", "true");
        button.appendChild(icon);
      } else {
        const img = document.createElement("img");
        img.src = mediaSrc(image.url);
        img.alt = "";
        img.loading = "lazy";
        button.appendChild(img);
      }
      button.addEventListener("click", async () => {
        const markdown = isPdf(image.url)
          ? `[${image.original_name}](${image.url})\n`
          : `![${image.original_name}](${image.url})\n`;
        try {
          //: The whole note, not a list row's first 300 characters (`fullEntry`).
          const whole = await fullEntry(entry.id);
          const nextContent = `${whole.content.trim()}\n\n${markdown}`.trim();
          await apiJson(`/entries/${entry.id}`, {
            method: "PUT",
            body: JSON.stringify({ content: nextContent }),
          });
          toast(`Attached ${image.original_name}.`);
          done();
          await loadEntries();
          pushEntryPutUndo(
            entry.id,
            `Attached ${image.original_name}`,
            { content: whole.content },
            { content: nextContent }
          );
        } catch (error) {
          toast(error.message || voiceLine("failed", { what: "attach that file" }), true);
        }
      });
      const cap = document.createElement("figcaption");
      cap.textContent = image.original_name;
      cap.title = image.original_name;
      fig.append(button, cap);
      grid.appendChild(fig);
    }

    card.append(head, hint, grid);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    close.focus();
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { attachFileTo, attachFromLibrary, reevaluateEntry });
})();
