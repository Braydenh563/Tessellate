// pick-row.js: one row of the Attach picker, its picture frame and its
// count line. Moved out of chat-attach.js on 2026-10-05 (the boot-script gzip
// budget): only the Attach panel's list (attach-to.js) and the whiteboard's
// own pickers draw them, so `LAZY_MODULES.attachTo` and the `library` bundle
// both name this file ahead of their callers; `ensureModule` fetches it once.

function notePickerRow(shape, row) {
  const li = document.createElement("li");
  const label = document.createElement("label");
  label.className = shape.grid ? "note-picker-cell" : "note-picker-row";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.className = "visually-hidden note-picker-box";
  box.checked = shape.isOn(row);
  box.addEventListener("change", () => {
    if (box.checked) {
      // Refused rather than silently dropped: the caps exist because four
      // whole files is already more than most local models can hold, and a
      // tick that comes straight back off reads as a broken control.
      if (shape.add(row) === false) {
        box.checked = false;
        toast(shape.full || "That's as many as one message can carry.", "info");
      }
    } else {
      shape.remove(row);
    }
    updateNotePickerCount();
  });
  const name = document.createElement("span");
  name.className = "note-picker-text";
  name.textContent = shape.label(row);
  const meta = document.createElement("span");
  meta.className = "note-picker-meta";
  meta.append(...shape.meta(row));
  const lines = document.createElement("span");
  lines.className = "note-picker-lines";
  lines.append(name, meta);
  const check = document.createElement("span");
  check.className = "note-picker-check";
  check.setAttribute("aria-hidden", "true");
  const tick = document.createElement("i");
  tick.className = "ph ph-check";
  check.appendChild(tick);
  const thumbUrl = shape.thumb?.(row);
  if (thumbUrl) {
    //: A picture's cell: the picture is the identifier, so the name is its
    //: tooltip and the one line under it is the caption (or where it is used).
    label.title = meta.textContent === name.textContent ? name.textContent : `${name.textContent}: ${meta.textContent}`;
    lines.classList.add("note-picker-cell-text");
    label.append(box, notePickerThumb(thumbUrl), check, lines);
  } else {
    const tile = richPickerTile({ icon: shape.icon(row), face: shape.face?.(row) || null });
    //: A failed page puts the glyph back (capture: `error` does not bubble).
    tile.addEventListener("error", () => tile.replaceWith(richPickerTile({ icon: shape.icon(row) })), true);
    label.append(box, tile, lines, check);
  }
  li.appendChild(label);
  return li;
}

//: The picture in a frame that keeps every cell one size: cropped to fill,
//: lazily loaded, and the app's missing-file glyph (not the browser's torn
//: page) when the file has gone. Empty alt: the name is the cell's own label.
function notePickerThumb(url) {
  const thumb = document.createElement("span");
  thumb.className = "note-picker-thumb";
  const img = document.createElement("img");
  img.alt = "";
  img.loading = "lazy";
  img.addEventListener("error", () => {
    img.remove();
    thumb.classList.add("is-missing");
  });
  img.src = url;
  thumb.appendChild(img);
  return thumb;
}

function updateNotePickerCount() {
  // Every store, not just notes: a count that only ever mentioned notes would
  // say "Nothing attached yet" with three files ticked in front of you.
  const counts = {
    notes: attachedNoteIds.length,
    documents: attachedDocuments.length,
    files: attachedFiles.length,
    images: attachedImages.length,
    maps: attachedBoards.length,
  };
  const words = { notes: "note", documents: "document", files: "file", images: "image", maps: "mind map" };
  const parts = Object.entries(counts)
    .filter(([, n]) => n)
    .map(([key, n]) => `${n} ${words[key]}${n === 1 ? "" : "s"}`);
  $("note-picker-count").textContent = parts.length ? `${parts.join(", ")} attached` : "Nothing attached yet";
  const clear = $("note-picker-clear");
  clear.disabled = !parts.length;
  clear.title = parts.length ? "Take everything off this message" : "Nothing is attached yet";
  //: A count on each source's tab, so what is held in the other four is
  //: visible from this one without walking them.
  for (const button of document.querySelectorAll("#note-picker-sources [data-picker-source]")) {
    let badge = button.querySelector(".note-picker-tab-count");
    const n = counts[button.dataset.pickerSource] || 0;
    if (!n) {
      badge?.remove();
      button.removeAttribute("aria-label");
      continue;
    }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "note-picker-tab-count";
      badge.setAttribute("aria-hidden", "true");
      button.appendChild(badge);
    }
    badge.textContent = String(n);
    button.setAttribute("aria-label", `${button.firstChild.textContent.trim()}, ${n} attached`);
  }
}

// A board's stored thumbnail as an <img> (INBOX 1317), asked for by name from
// `mapPreview` (note-cards.js, boot), which draws its SVG when this has not
// loaded. The server sets `thumb_v` only while the file is current for the
// board, and the URL carries it, so the browser caches each version for good.
window.mapRaster = (board, size) =>
  Object.assign(new Image(), {
    className: `board-minimap board-minimap-${size}`,
    alt: "",
    loading: "lazy",
    decoding: "async",
    src: `/media/board-thumb/${board.id}?v=${board.thumb_v}`,
  });
