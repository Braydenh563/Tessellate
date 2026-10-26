// Lazily loaded (LAZY_MODULES.attachments in app.js): what a click on an
// attachment card does. The card itself (`attachmentCard`, notes-list.js) is
// drawn at boot because a note list needs it at once; everything behind its
// button and its ⋯ menu waits for the first click, so it stays off the boot
// scripts' gzip budget (tests/test_static_compression.py).
//
// INBOX 440 (2), the owner: "all of the attachment cards ui and ux and
// utility need a massive redesign and upgrade." The old card could caption a
// picture and remove it, and nothing else: no open, no download, no rename, no
// way to play a recording. These are the actions the menu now names, one
// handler each, given the card's `spec` (see `attachmentCard` for its shape).

//: The upload row behind a `/media/<name>` url (its id, caption and usage),
//: or null. `/media/meta` answers by the stored name, one request; the
//: listing is read only when the usage is wanted, because only the listing
//: carries `used_by` and it is paged.
async function attachmentUpload(url, withUsage = false) {
  const name = /^\/media\/([^/?#]+)$/.exec(url || "")?.[1];
  if (!name) return null;
  if (!withUsage) return apiJson(`/media/meta/${name}`).catch(() => null);
  const uploads = await apiPagedList("/media", 200);
  return uploads.find((u) => u.url === url) || null;
}

function attachmentLabel(spec) {
  return spec.name && spec.name !== spec.url ? spec.name : (spec.url || "").split("/").pop();
}

function attachmentFileId(spec) {
  return /^\/files\/(\d+)/.exec(spec.url || "")?.[1] || null;
}

//: The bytes, whichever way this file is held: a staged picture is a blob url
//: in this tab, everything else goes through `api` for the auth header.
async function attachmentBlob(spec) {
  if (spec.file) return spec.file;
  const src = mediaSrc(spec.url);
  if (/^blob:/.test(src)) return (await fetch(src)).blob();
  return (await api(spec.url)).blob();
}

//: **A recording plays where it is.** The lightbox draws pictures and reads
//: documents; it has no player, and a recording has nothing to zoom or read.
//: So the card opens out: the native player (keyboard, captions and speed
//: come with it) across the card's full width, started at once, and a second
//: press folds it away again.
function attachmentPlayer(spec, card) {
  const kind = card.dataset.kind;
  const open = card.querySelector(".att-card-open");
  const existing = card.querySelector(".att-card-player");
  if (existing) {
    existing.pause?.();
    existing.remove();
    open?.setAttribute("aria-expanded", "false");
    return;
  }
  const player = document.createElement(kind === "video" ? "video" : "audio");
  player.className = "att-card-player";
  player.controls = true;
  player.preload = "metadata";
  player.src = mediaSrc(spec.url);
  player.setAttribute("aria-label", attachmentLabel(spec));
  card.append(player);
  open?.setAttribute("aria-expanded", "true");
  player.play().catch(() => player.focus());
}

const ATTACHMENT_ACTIONS = {
  open: (spec, card) => {
    const kind = card.dataset.kind;
    if (kind === "audio" || kind === "video") return attachmentPlayer(spec, card);
    const many = spec.gallery?.();
    if (many?.items.length) return openLightbox(many.items, Math.max(0, many.index));
    return openLightbox(
      [{ filename: attachmentLabel(spec), getUrl: () => (spec.thumb ? spec.thumb() : mediaSrc(spec.url)) }],
      0
    );
  },

  download: async (spec) => {
    try {
      await saveFile(attachmentLabel(spec), await attachmentBlob(spec));
    } catch (error) {
      toast(error.message || `Couldn't save “${attachmentLabel(spec)}”.`, true);
    }
  },

  //: The name a file is shown under, never its bytes. A note's own file is
  //: renamed on the server (`PUT /files/{id}`); a file the text points at is
  //: renamed in the text, which is where its name lives, and on its upload row
  //: too so the Library agrees. An extension left off is put back: the kind
  //: is read from it.
  rename: async (spec) => {
    const label = attachmentLabel(spec);
    const typed = (await promptDialog(`Rename “${label}”`, label, { confirmLabel: "Rename" }))
      .replace(/[[\]\n]/g, "")
      .trim();
    if (!typed || typed === label) return;
    const ext = attachmentExt(label);
    const next = ext && !attachmentExt(typed) ? `${typed}.${ext}` : typed;
    try {
      if (spec.attachment) {
        await apiJson(`/files/${spec.attachment.id}`, { method: "PUT", body: JSON.stringify({ filename: next }) });
        pushRequestUndo("Renamed a file", `/files/${spec.attachment.id}`, "PUT", { filename: label }, { filename: next }, () => spec.onChange?.());
        spec.onChange?.();
      } else if (spec.textarea && spec.markdown) {
        const box = spec.textarea;
        const renamed = spec.markdown.replace(`[${spec.name}](`, `[${next}](`);
        box.value = box.value.replace(spec.markdown, renamed);
        box.dispatchEvent(new Event("input", { bubbles: true }));
        const upload = await attachmentUpload(spec.url);
        if (upload) {
          await apiJson(`/media/${upload.id}`, { method: "PUT", body: JSON.stringify({ original_name: next }) });
          pushRequestUndo("Renamed a file", `/media/${upload.id}`, "PUT", { original_name: label }, { original_name: next });
        }
      }
      toast(`Renamed to “${next}”.`);
    } catch (error) {
      toast(error.message || "Couldn't rename that file.", true);
    }
  },

  //: The description a model writes from the picture, or from the file's own
  //: text for a document. Shown in a toast here and kept with the file, where
  //: the lightbox and the Library show it beside the file.
  describe: async (spec) => {
    if (aiIsOff()) return toast(`Describing a file needs the local AI. ${AI_OFFLINE_HINT}.`, "info");
    const id = attachmentFileId(spec);
    toast(`Describing “${attachmentLabel(spec)}”…`);
    try {
      let row;
      if (id) {
        row = await apiJson(`/files/${id}/analyse`, { method: "POST", body: JSON.stringify({ kind: "caption", force: true }) });
      } else {
        const upload = await attachmentUpload(spec.url);
        if (!upload) return toast("That upload is no longer in the Library; it may have been deleted.", "info");
        row = await apiJson(`/media/${upload.id}/caption`, { method: "POST", body: JSON.stringify({ force: true }) });
      }
      toast(row.caption ? `Description: ${row.caption}` : "No description came back.");
    } catch (error) {
      toast(error.message || "Couldn't describe that file.", true);
    }
  },

  caption: async (spec) => {
    const id = attachmentFileId(spec);
    try {
      const current = id
        ? (await apiPagedList("/files/gallery", 200)).find((row) => String(row.id) === id)
        : await attachmentUpload(spec.url);
      if (!current) return toast("That file is no longer in the Library; it may have been deleted.", "info");
      const typed = await promptDialog(`Description of “${attachmentLabel(spec)}”`, current.caption || "", { confirmLabel: "Save" });
      // "" is both "cancelled" and "cleared": harmless when there was nothing.
      if (typed === "" && !current.caption) return;
      const row = id
        ? await apiJson(`/files/${id}/analyse`, { method: "POST", body: JSON.stringify({ kind: "caption", text: typed }) })
        : await apiJson(`/media/${current.id}/caption`, { method: "POST", body: JSON.stringify({ text: typed }) });
      toast(row.caption ? "Description saved." : "Description cleared.");
    } catch (error) {
      toast(error.message || "Couldn't save that description.", true);
    }
  },

  //: The sketch pad with this picture under the pen. What is drawn saves as a
  //: new note, as every sketch does, so the original is never painted over.
  annotate: async (spec) => {
    try {
      const blob = await attachmentBlob(spec);
      await openSketch({ image: blob, caption: `Notes on ${attachmentLabel(spec)}` });
    } catch (error) {
      toast(error.message || "Couldn't open that picture for drawing.", true);
    }
  },

  copy: async (spec) => {
    const bang = attachmentKind(spec.name, spec.url) === "image" ? "!" : "";
    const markdown = `${bang}[${attachmentLabel(spec)}](${spec.url})`;
    if (await copyToClipboard(markdown)) toast("Copied. Paste it into any note or document.");
  },

  //: **Out of the text at once, with an Undo; off the disk only once nothing
  //: uses it.** The old remove deleted the upload the moment it was pressed.
  //: In the edit form that broke the saved note whenever the edit was then
  //: cancelled (the note still pointed at a file that was gone), and in
  //: Capture it deleted a picture taken "From library" that other notes show.
  //: Now the bytes go only after the undo has lapsed, and only when the
  //: Library's own usage scan finds no note, document or board using them,
  //: which in the edit form is never (the saved note still does) and in
  //: Capture is exactly the draft-only upload the old rule was written for.
  remove: async (spec) => {
    const label = attachmentLabel(spec);
    if (spec.attachment) {
      if (!(await confirmDialog(`Delete “${label}” from this note?`, { confirmLabel: "Delete" }))) return;
      try {
        const id = spec.attachment.id;
        const gone = await apiJson(`/files/${id}`, { method: "DELETE" });
        pushTokenUndo(`Deleted “${label}”`, [{ del: [`/files/${id}`, "DELETE"], restore: "/files/restore", token: gone.undo_token }], () => spec.onChange?.(), `Deleted “${label}”.`);
        spec.onChange?.();
      } catch (error) {
        toast(error.message || `Couldn't delete “${label}”.`, true);
      }
      return;
    }
    if (spec.file) {
      const unstage = () => {
        captureStagedFiles = captureStagedFiles.filter((f) => f !== spec.file);
        renderCaptureFiles();
      };
      unstage();
      offerUndo(
        `Removed “${label}”`,
        `“${label}” won't be attached.`,
        () => {
          captureStagedFiles.push(spec.file);
          renderCaptureFiles();
        },
        unstage
      );
      return;
    }
    const box = spec.textarea;
    if (!box || !spec.markdown) return;
    const before = box.value;
    const after = before.replace(spec.markdown, "").replace(/\n{3,}/g, "\n\n");
    const setText = (value) => {
      box.value = value;
      box.dispatchEvent(new Event("input", { bubbles: true }));
    };
    setText(after);
    let undone = false;
    let binned = null;
    offerUndo(
      `Removed “${label}”`,
      `Removed “${label}”.`,
      async () => {
        undone = true;
        setText(before);
        //: The picture was tidied away after the toast; it comes back with the text.
        if (binned) await apiJson("/media/restore", { method: "POST", body: JSON.stringify({ token: binned }) });
        binned = null;
      },
      () => setText(after)
    );
    if (!/^\/media\//.test(spec.url)) return;
    setTimeout(async () => {
      if (undone || box.value.includes(spec.url)) return;
      try {
        const upload = await attachmentUpload(spec.url, true);
        if (upload && !upload.used_by?.length && !upload.usage_incomplete) {
          binned = (await apiJson(`/media/${upload.id}`, { method: "DELETE" }))?.undo_token ?? null;
        }
      } catch (err) {
        console.error("Couldn't tidy the removed upload", err);
      }
    }, 9000);
  },
};

async function attachmentAction(action, spec, card) {
  return ATTACHMENT_ACTIONS[action]?.(spec, card);
}
