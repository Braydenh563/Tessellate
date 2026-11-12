// capture-stage.js: what the capture card holds back until Save, shared by the app's Quick
// capture and the desktop companion's Quick note (fetched by capture-card.js on the card's
// first open). Pictures (staged as object URLs, uploaded to /media/upload and written into the
// note as markdown, as the editor writes them) and every other file the chat picker takes
// (`ATTACH_ACCEPT`, attach-accept.js), kept as chips and attached through the note's own
// `POST /entries/{id}/files` once the note has an id. Nothing leaves the browser before Save;
// Close on the desk, and a finished save, revoke every object URL (`discardCaptureStage`).
// Needs: `apiJson`, `authHeaders` (the app's, or desk-companion.js's), `attachmentChip`, `isImageFile`.

(() => {
  //: A note carries a handful of pictures and files, not an album.
  const CAPTURE_PICTURE_LIMIT = 8;
  const CAPTURE_FILE_LIMIT = 8;

  //: The attach button in the foot, the hidden picker, the strip of thumbnails and the row of
  //: chips under the words. `pick`: the bar's picture button took the click that fetched this
  //: file, so the picker opens now (the click's permission to open it is still live).
  function mountCaptureStage(pick = false) {
    const card = captureCard.root;
    if (!card.dataset.stage) {
      card.dataset.stage = "1";
      const attach = captureCardButton("ghost small icon-only", "Add pictures or files", "ph-paperclip", "picture");
      const file = captureCardEl("input", "hidden", { type: "file", accept: ATTACH_ACCEPT, multiple: "", tabindex: "-1", "aria-hidden": "true", "aria-label": "Choose pictures or files for this note", "data-cc": "file" });
      card.querySelector(".capture-card-modes").after(attach, file);
      const thumbs = captureCardEl("div", "capture-card-thumbs", { "data-cc": "thumbs", hidden: "" });
      const chips = captureCardEl("div", "chat-attachments capture-card-chips hidden", { "data-cc": "chips", role: "group", "aria-label": "Files for this note" });
      card.querySelector(".note-composer").after(thumbs, chips);
      attach.addEventListener("click", () => file.click());
      file.addEventListener("change", () => {
        addCaptureFiles([...file.files]);
        file.value = "";
      });
      //: A paste of files stages them; a paste that carries words too (a spreadsheet cell
      //: arrives as text and a picture) keeps its words and takes the pictures only.
      card.addEventListener("paste", (event) => {
        const data = event.clipboardData;
        let files = [...(data?.files || [])];
        if (data?.getData("text/plain")) files = files.filter(isImageFile);
        if (!files.length) return;
        event.preventDefault();
        addCaptureFiles(files);
      });
      card.addEventListener("dragover", (event) => {
        if ([...(event.dataTransfer?.types || [])].includes("Files")) event.preventDefault();
      });
      card.addEventListener("drop", (event) => {
        const files = [...(event.dataTransfer?.files || [])];
        if (!files.length) return;
        event.preventDefault();
        addCaptureFiles(files);
      });
    }
    if (pick) captureCardField("file").click();
  }

  //: A file the chat picker would take: any picture, or a suffix on the one list.
  function captureAccepts(file) {
    if (isImageFile(file)) return true;
    const suffix = /\.[^.]+$/.exec(file.name || "")?.[0].toLowerCase();
    return Boolean(suffix) && ATTACH_ACCEPT.split(",").includes(suffix);
  }

  //: Pictures and files, up to their limits; what was left out is said under the card.
  function addCaptureFiles(files, alt = "") {
    const taken = files.filter(captureAccepts);
    const images = taken.filter(isImageFile);
    const others = taken.filter((file) => !isImageFile(file));
    const pictureRoom = Math.max(CAPTURE_PICTURE_LIMIT - captureCard.pictures.length, 0);
    const fileRoom = Math.max(CAPTURE_FILE_LIMIT - captureCard.files.length, 0);
    for (const file of images.slice(0, pictureRoom)) {
      captureCard.pictures.push({ file, preview: URL.createObjectURL(file), alt: alt || file.name.replace(/\.[^.]+$/, ""), uploaded: "" });
    }
    for (const file of others.slice(0, fileRoom)) captureCard.files.push(file);
    renderCaptureStage();
    const left = files.length - Math.min(images.length, pictureRoom) - Math.min(others.length, fileRoom);
    captureCardStatus(left ? `Added what fits: a note takes ${CAPTURE_PICTURE_LIMIT} pictures and ${CAPTURE_FILE_LIMIT} files, of the kinds the chat takes.` : "", Boolean(left));
  }

  function renderCaptureStage() {
    const thumbs = captureCardField("thumbs");
    const chips = captureCardField("chips");
    if (!thumbs || !chips) return;
    thumbs.replaceChildren(...captureCard.pictures.map(captureThumb));
    thumbs.hidden = !captureCard.pictures.length;
    chips.replaceChildren(...captureCard.files.map(captureFileChip));
    chips.classList.toggle("hidden", !captureCard.files.length);
    captureCard.settle();
  }

  function captureThumb(picture) {
    const item = captureCardEl("span", "capture-card-thumb");
    const image = captureCardEl("img", "", { src: picture.preview, alt: picture.alt });
    const remove = captureCardButton("ghost small icon-only", `Remove ${picture.alt}`, "ph-x", "thumb-remove");
    remove.addEventListener("click", () => removeCapturePicture(picture));
    item.append(image, remove);
    return item;
  }

  //: A file waiting for Save is the chat's staged chip, with the same x.
  function captureFileChip(file) {
    return attachmentChip({ name: file.name, size: file.size, removeTitle: `Remove “${file.name}”`, onRemove: () => removeCaptureFile(file) });
  }

  function removeCapturePicture(picture) {
    URL.revokeObjectURL(picture.preview);
    captureCard.pictures = captureCard.pictures.filter((item) => item !== picture);
    renderCaptureStage();
  }

  function removeCaptureFile(file) {
    captureCard.files = captureCard.files.filter((item) => item !== file);
    renderCaptureStage();
  }

  //: Everything staged goes, and the card forgets a note it had made for them. The desk's
  //: Close and a finished save call it; nothing was ever sent, so there is nothing to undo.
  function discardCaptureStage() {
    for (const picture of captureCard.pictures) URL.revokeObjectURL(picture.preview);
    captureCard.pictures = [];
    captureCard.files = [];
    captureCard.made = null;
    if (captureCard.root?.dataset.stage) renderCaptureStage();
  }

  //: The editor's own path: each picture goes to /media/upload and the note
  //: refers to it as markdown. One already sent (a retry after a failure) is not
  //: sent twice. Returns the markdown lines, one picture a paragraph.
  async function uploadCapturePictures() {
    const lines = [];
    for (const picture of captureCard.pictures) {
      if (!picture.uploaded) {
        const form = new FormData();
        form.append("file", picture.file, picture.file.name);
        const sent = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
        if (!sent?.url) throw new Error("Couldn't upload a picture. Nothing was saved.");
        picture.uploaded = sent.url;
      }
      lines.push(`![${picture.alt}](${picture.uploaded})`);
    }
    return lines.join("\n\n");
  }

  //: The note's own attachment path (`POST /entries/{id}/files`). A file that went is no longer
  //: staged, so a retry sends only the rest. Returns the failures and the note as last answered.
  async function attachCaptureFiles(entryId) {
    const failed = [];
    let entry = null;
    for (const file of [...captureCard.files]) {
      const form = new FormData();
      form.append("file", file, file.name);
      try {
        entry = await apiJson(`/entries/${entryId}/files`, { method: "POST", headers: authHeaders(), body: form });
        captureCard.files = captureCard.files.filter((item) => item !== file);
      } catch (error) {
        failed.push(`${file.name}: ${error.message}`);
      }
    }
    renderCaptureStage();
    return { failed, entry };
  }

  Object.assign(window, { addCaptureFiles, attachCaptureFiles, discardCaptureStage, mountCaptureStage, uploadCapturePictures });
})();
