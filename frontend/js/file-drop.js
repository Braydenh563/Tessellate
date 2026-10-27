// file-drop.js: drop files anywhere to add them to the Library (WORLD_CLASS_PLAN
// "Drag and drop of files onto any page", ledger libr-1011 row 1266). Lazy
// (`LAZY_MODULES.fileDrop`): the only boot code is the dragenter stub in
// settings-wiring.js, which loads this file the first time a file is dragged
// over the window and then calls `fileDropEnter`.
//
// It takes only what nothing else took: a textarea, the whiteboard, a note row
// and the documents list each handle their own file drops and call
// preventDefault, so a drop that arrives here undefended is one the window
// would otherwise have opened in the browser. Pictures and PDFs go to the
// Library's Images through the same upload the Library's button uses
// (`direct`); anything else becomes a document (`importLibraryDocuments`).
// While it works the drop veil (DESIGN.md "A drop target") says so.

const FILE_DROP_MEDIA = /\.(png|jpe?g|gif|webp|avif|bmp|ico|pdf)$/i;
//: A drag that stops sending `dragover` for this long is over (a drag that
//: left the window sends no `dragleave` to `document` in every engine).
const FILE_DROP_QUIET_MS = 400;

const fileDrop = { armed: false, veil: null, label: null, timer: 0, busy: false };

function fileDragHasFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes("Files");
}

function fileDropLocked() {
  const lock = document.getElementById("lock-overlay");
  return Boolean(lock && !lock.classList.contains("hidden"));
}

function fileDropVeil() {
  if (!fileDrop.veil) {
    const veil = document.createElement("div");
    veil.className = "drop-veil";
    //: A manual popover: the top layer puts it over every dock and sheet
    //: without a z-index of its own (DESIGN.md, the stylesheet's grammar:
    //: no new literal layer).
    veil.popover = "manual";
    veil.setAttribute("role", "status");
    veil.setAttribute("aria-live", "polite");
    const card = document.createElement("div");
    card.className = "drop-veil-card";
    const icon = document.createElement("i");
    icon.className = "ph ph-upload-simple";
    icon.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    card.append(icon, label);
    veil.appendChild(card);
    document.body.appendChild(veil);
    Object.assign(fileDrop, { veil, label });
  }
  return fileDrop.veil;
}

function fileDropShow(text) {
  const veil = fileDropVeil();
  if (!veil.matches(":popover-open")) veil.showPopover();
  fileDrop.label.textContent = text;
}

function fileDropHide() {
  clearTimeout(fileDrop.timer);
  if (fileDrop.veil?.matches(":popover-open")) fileDrop.veil.hidePopover();
}

function fileDropOver(event) {
  if (!fileDragHasFiles(event) || fileDrop.busy || fileDropLocked()) return;
  if (event.defaultPrevented) {
    fileDropHide();
    return;
  }
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
  fileDropShow("Drop files to add them to your Library");
  clearTimeout(fileDrop.timer);
  fileDrop.timer = setTimeout(fileDropHide, FILE_DROP_QUIET_MS);
}

function fileDropArm() {
  if (fileDrop.armed) return;
  fileDrop.armed = true;
  document.addEventListener("dragover", fileDropOver);
  document.addEventListener("dragend", fileDropHide);
  document.addEventListener("drop", (event) => {
    if (!fileDragHasFiles(event) || event.defaultPrevented || fileDropLocked()) {
      fileDropHide();
      return;
    }
    event.preventDefault();
    fileDropImport(Array.from(event.dataTransfer.files));
  });
}

//: Called when this file arrives, by its last line. The dragenter that loaded it
//: is already past, so the veil is raised here and the quiet timer takes it
//: down again if the drag was over.
function fileDropEnter() {
  fileDropArm();
  if (fileDrop.busy || fileDropLocked()) return;
  fileDropShow("Drop files to add them to your Library");
  clearTimeout(fileDrop.timer);
  fileDrop.timer = setTimeout(fileDropHide, FILE_DROP_QUIET_MS * 2);
}

//: Opens Library on one of its two file sub-tabs (the bell's stored `go.media`
//: does the same, notifications.js).
async function showLibraryMedia(kind) {
  await switchTab("library");
  document.querySelector(`#library-subtabs [data-media-kind="${kind}"]`)?.click();
}

async function fileDropImport(files) {
  if (!files.length) {
    fileDropHide();
    return;
  }
  fileDrop.busy = true;
  clearTimeout(fileDrop.timer);
  fileDropShow(files.length === 1 ? "Adding 1 file…" : `Adding ${files.length} files…`);
  const media = files.filter((file) => FILE_DROP_MEDIA.test(file.name));
  const other = files.filter((file) => !FILE_DROP_MEDIA.test(file.name));
  let added = 0;
  const lands = new Set();
  try {
    for (const file of media) {
      const form = new FormData();
      form.append("file", file);
      //: The upload is the commit, as the Library's own button (library.js).
      form.append("direct", "true");
      try {
        const made = await (await api.upload("/media/upload", form)).json().catch(() => null);
        pushUploadUndo(`Added “${file.name}”`, "/media", made, () => (typeof renderLibraryImagesGallery === "function" ? renderLibraryImagesGallery() : undefined));
        added++;
        lands.add(/\.pdf$/i.test(file.name) ? "files" : "images");
      } catch (error) {
        toast(`${file.name}: ${error.message}`, true);
      }
    }
    if (added) {
      //: A PDF lives under Library > Files, a picture under Images: the notice
      //: and its bell row both open the sub-tab the drop actually filled.
      const where = lands.size === 1 && lands.has("files") ? "files" : "images";
      const noun = where === "files" ? ["PDF", "PDFs"] : ["picture or PDF", "pictures or PDFs"];
      toastAction(
        `Added ${added} ${noun[added === 1 ? 0 : 1]} to your Library.`,
        "Show",
        () => showLibraryMedia(where),
        { go: { tab: "library", media: where } },
      );
      if (typeof renderLibraryImagesGallery === "function") renderLibraryImagesGallery();
    }
    if (other.length) {
      await ensureModule("libraryList");
      await importLibraryDocuments(other);
    }
  } finally {
    fileDrop.busy = false;
    fileDropHide();
  }
}

fileDropEnter();
