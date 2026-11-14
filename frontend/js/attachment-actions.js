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
(() => {
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

  //: **Copy image** (INBOX 1775). The one place a picture is put on the
  //: clipboard: the card menu, the lightbox, Ctrl+C there and the right-click
  //: on any picture below all come here. Chromium writes only image/png, so
  //: another type is drawn onto a canvas first (a GIF gives its first frame, an
  //: SVG its own size or 1024 wide). Bytes come from this app's own routes
  //: (the media cookie or the auth header), a staged picture's blob, or a data
  //: url; a remote picture would taint the canvas, so it falls back to its link.
  //: A staged picture is a `blob:` url and the page's CSP (`connect-src 'self'`)
  //: refuses to fetch one, so a blob or data url is drawn from an <img> (which
  //: `img-src` allows) and read back as a PNG.
  async function pngFromUrl(href) {
    const pic = new Image();
    pic.src = href;
    await pic.decode();
    const width = pic.naturalWidth || 1024;
    const height = pic.naturalHeight || Math.round(width * 0.75);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(pic, 0, 0, width, height);
    return new Promise((done, fail) => canvas.toBlob((png) => (png ? done(png) : fail(new Error("encode"))), "image/png"));
  }

  async function imageBlobOf(source) {
    if (source.file) return source.file;
    const src = await source.src;
    const url = new URL(src, location.href);
    if (url.protocol === "blob:" || url.protocol === "data:") return pngFromUrl(src);
    if (url.origin !== location.origin) throw new Error("remote picture");
    return (await api(url.pathname + url.search)).blob();
  }

  async function pngBlobOf(blob) {
    if (blob.type === "image/png") return blob;
    const holder = URL.createObjectURL(blob);
    try {
      return await pngFromUrl(holder);
    } finally {
      URL.revokeObjectURL(holder);
    }
  }

  //: The blob is handed to the clipboard as a promise, so the click's permission
  //: is spent at the write and not lost while the picture is fetched and drawn.
  async function copyImage(source) {
    const picture = imageBlobOf(source).then(pngBlobOf);
    picture.catch(() => {});
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") throw new Error("no clipboard");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": picture })]);
      toast("Image copied.");
    } catch {
      const src = source.file ? "" : await source.src;
      const link = src && !/^(?:blob|data):/.test(src) ? new URL(src, location.href).href : "";
      if (link && (await copyToClipboard(link))) toast("Copied the image's link: this picture cannot be copied as an image.");
      else toast("This picture cannot be copied.", "info");
    }
  }

  const imageSource = (spec) => ({
    file: spec.file,
    name: spec.name,
    src: spec.src || (spec.thumb ? spec.thumb() : mediaSrc(spec.url)),
  });

  //: Right-click or hold on a picture anywhere in the app. Skipped where the
  //: browser's menu is right (a field, a selection, an open menu), where a row
  //: menu has already claimed the event (`defaultPrevented`: Library tiles,
  //: attachment cards, whiteboard objects) and for the app's own faces.
  const IMAGE_MENU_SKIP =
    "input, textarea, select, .action-menu, [data-chip-menu], .selection-popup, [class*='avatar'], [class*='companion'], .lock-overlay";
  const IMAGE_HOSTS = ".lightbox-stage, .msg-attachment-image, .att-chip, .answer-grounding-thumb, figure";

  function pictureAtEvent(event) {
    const target = event.target;
    if (!(target instanceof Element) || target.closest(IMAGE_MENU_SKIP)) return null;
    if (String(window.getSelection?.() || "").trim()) return null;
    //: The menu key sends the event to the focused element: in the viewer that is the dialog or its stage, and the picture is the stage's.
    const viewer = !target.closest("button, a, .lightbox-info, .lightbox-doc") && target.closest(".lightbox")?.querySelector(".lightbox-stage > img:not(.hidden)");
    const img = target.closest("img") || target.closest(IMAGE_HOSTS)?.querySelector("img") || viewer;
    if (!img || !(img.currentSrc || img.src) || !img.naturalWidth || img.closest(IMAGE_MENU_SKIP)) return null;
    return img;
  }

  function openPictureMenu(img, x, y) {
    //: A staged chip's picture has no alt: its name is the chip's.
    const chipName = img.closest(".att-chip")?.querySelector(".att-chip-name")?.textContent?.trim();
    const spec = { src: img.currentSrc || img.src, name: img.alt || chipName || (img.currentSrc || img.src).split("/").pop().split("?")[0] };
    openMenuAtPoint(
      [
        { label: "ph:image Copy image", title: "Put this picture on the clipboard", run: () => copyImage(imageSource(spec)) },
        {
          label: "ph:download-simple Save image",
          title: "Save this picture to this computer",
          run: async () => {
            try {
              const blob = await imageBlobOf({ src: spec.src });
              //: A blob or data url is saved as the PNG it was drawn into, so the name says so.
              const name = spec.name || "image";
              await saveFile(blob.type === "image/png" && !/\.png$/i.test(name) ? name.replace(/\.[A-Za-z0-9]{1,5}$/, "") + ".png" : name, blob);
            } catch (error) {
              toast(error.message || voiceLine("failed", { what: "save that picture" }), true);
            }
          },
        },
      ],
      "Picture actions",
      x,
      y,
      img.closest("button, [tabindex]") || null
    );
  }

  document.addEventListener("contextmenu", (event) => {
    if (event.defaultPrevented) return;
    const img = pictureAtEvent(event);
    if (!img) return;
    event.preventDefault();
    //: The menu key sends the event to the focused element, not the picture (the viewer's dialog, a card's button), with that element's coordinates: off the picture, the menu opens on it.
    const rect = img.getBoundingClientRect();
    const onPicture = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
    openPictureMenu(img, onPicture ? event.clientX : rect.left + Math.min(rect.width, 160) / 2, onPicture ? event.clientY : rect.top + Math.min(rect.height, 160) / 2);
  });
  wireLongPress(
    document,
    (event, point) => {
      const img = pictureAtEvent(event);
      if (img) openPictureMenu(img, point.x, point.y);
    },
    { selector: "img, " + IMAGE_HOSTS }
  );

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
        toast(error.message || voiceLine("failed", { what: `save “${attachmentLabel(spec)}”` }), true);
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
        toast(error.message || voiceLine("failed", { what: "rename that file" }), true);
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
        toast(error.message || voiceLine("failed", { what: "describe that file" }), true);
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
        toast(error.message || voiceLine("failed", { what: "save that description" }), true);
      }
    },

    //: The sketch pad with this picture under the pen. What is drawn saves as a
    //: new note, as every sketch does, so the original is never painted over.
    annotate: async (spec) => {
      try {
        const blob = await attachmentBlob(spec);
        await openSketch({ image: blob, caption: `Notes on ${attachmentLabel(spec)}` });
      } catch (error) {
        toast(error.message || voiceLine("failed", { what: "open that picture for drawing" }), true);
      }
    },

    "copy-image": (spec) => copyImage(imageSource(spec)),

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
          toast(error.message || voiceLine("failed", { what: `delete “${label}”` }), true);
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

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { attachmentAction });
})();
