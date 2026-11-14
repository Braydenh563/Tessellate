// att-chip.js: the one attachment chip and the facts it prints (a file's glyph, its kind
// label, its size), shared by the app and the desktop companion's Quick note, which load
// nothing else of the app. Moved whole from notes-list.js, note-cards.js and chat-attach.js
// (names, bodies and callers unchanged); runtime calls only: `setLabel`, `lazyScript`.

(() => {
  //: A glyph per file kind, for our own /media/ and /files/ attachments.
  const ATTACHMENT_ICONS = {
    pdf: "ph-file-pdf", doc: "ph-file-doc", docx: "ph-file-doc", rtf: "ph-file-doc",
    xls: "ph-file-xls", xlsx: "ph-file-xls", csv: "ph-file-csv",
    ppt: "ph-file-ppt", pptx: "ph-file-ppt",
    zip: "ph-file-archive", rar: "ph-file-archive", "7z": "ph-file-archive",
    mp3: "ph-file-audio", wav: "ph-file-audio", ogg: "ph-file-audio", m4a: "ph-file-audio", webm: "ph-file-audio",
    mp4: "ph-file-video", mov: "ph-file-video",
    txt: "ph-file-text", md: "ph-file-md", json: "ph-file-code",
    png: "ph-file-image", jpg: "ph-file-image", jpeg: "ph-file-image",
    gif: "ph-file-image", webp: "ph-file-image", heic: "ph-file-image", heif: "ph-file-image",
  };

  //: `name` matters for a `/files/{id}` url, which has no extension to read.
  function attachmentIconClass(url, name) {
    const source = name || (url.startsWith("/media/") ? url : "");
    if (!source) return null;
    return ATTACHMENT_ICONS[attachmentExt(source)] || "ph-file";
  }

  //: The kinds the file card names ("PDF", "Word") rather than "File".
  const FILE_KIND_LABELS = {
    pdf: "PDF", doc: "Word", docx: "Word", odt: "Document", rtf: "Document",
    xls: "Sheet", xlsx: "Sheet", ods: "Sheet", csv: "CSV",
    ppt: "Slides", pptx: "Slides", odp: "Slides",
    txt: "Text", md: "Markdown", markdown: "Markdown",
    json: "JSON", xml: "XML", yaml: "YAML", yml: "YAML",
    html: "HTML", htm: "HTML", css: "CSS",
    js: "Code", ts: "Code", jsx: "Code", tsx: "Code", py: "Code", java: "Code",
    c: "Code", h: "Code", cpp: "Code", hpp: "Code", cs: "Code", go: "Code",
    rs: "Code", rb: "Code", php: "Code", sh: "Code", sql: "SQL",
    swift: "Code", kt: "Code", vb: "Code", vbs: "Code", diff: "Code", patch: "Code",
    zip: "Archive", mp3: "Audio", wav: "Audio", m4a: "Audio",
    mp4: "Video", mov: "Video", webm: "Video",
  };

  function fileKindLabel(url, name) {
    const source = name || url;
    const ext = source.split(".").pop().split(/[?#]/)[0].toLowerCase();
    return FILE_KIND_LABELS[ext] || "File";
  }

  function attachmentExt(...sources) {
    for (const source of sources) {
      const match = /\.([a-z0-9]{1,5})(?:[?#].*)?$/i.exec(source || "");
      if (match) return match[1].toLowerCase();
    }
    return "";
  }

  //: A size in words (2.4 MB), nothing when it is unknown.
  function formatFileSize(bytes) {
    const size = Number(bytes) || 0;
    if (size <= 0) return ""; // unknown, or the file is gone, say nothing
    if (size < 1024) return `${size} B`;
    const units = ["KB", "MB", "GB"];
    let value = size / 1024;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    // One decimal below 10 (2.4 MB reads better than 2 MB), none above it.
    return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
  }

  //: **The one attachment chip** (DESIGN.md "An attachment chip"; Chat's images,
  //: documents and files and the popup agent's staged files all build it here).
  //: A tile (the picture, or the kind's glyph), the name with its extension kept
  //: when the stem is cut, one facts line, a bar while it uploads, a round x.
  //: `state` is "ready", "uploading" (with `progress` 0..1) or "error" (the
  //: facts line then says why). A notebook item (`notebookCard`, chat-agent.js)
  //: passes its own `icon` and `facts` (a note's name is words, not a file name,
  //: so no extension is split off) and `onOpen`, which makes the tile and the
  //: words one button; the remove x stays its sibling.
  function attachmentChip({ name, size, thumb, icon, facts: factsText, onOpen, state = "ready", progress = 0, error = "", title, removeTitle, onRemove }) {
    const chipEl = document.createElement("span");
    //: **Staged is a pill, sent is a card** (INBOX 1476, the owner: the grey slab
    //: is not "very clean and dynamic"). A staged chip (`onRemove` given, null while it uploads) is waiting in a
    //: composer: one quiet line, the glyph, the name cut at about 14 characters,
    //: the kind in brackets, the x. Sent, it keeps the two-line card.
    const pill = onRemove !== undefined;
    chipEl.className = `chip att-chip${pill ? " att-chip-pill" : ""}`;
    chipEl.dataset.state = state;
    chipEl.title = title || name;
    let tile;
    if (thumb) {
      tile = document.createElement("img");
      tile.src = thumb;
      tile.alt = "";
    } else {
      tile = document.createElement("i");
      tile.className = `ph ${icon || attachmentIconClass("", name) || "ph-file"}`;
      tile.setAttribute("aria-hidden", "true");
    }
    tile.classList.add("att-chip-tile");
    const ext = icon ? "" : attachmentExt(name);
    const stem = document.createElement("span");
    stem.className = "att-chip-stem";
    stem.textContent = ext ? name.slice(0, -(ext.length + 1)) : name;
    const nameEl = document.createElement("span");
    nameEl.className = "att-chip-name";
    nameEl.append(stem);
    if (ext) {
      const extEl = document.createElement("span");
      extEl.className = "att-chip-ext";
      extEl.textContent = `.${ext}`;
      nameEl.append(extEl);
    }
    const facts = document.createElement("span");
    facts.className = "att-chip-facts";
    const kind = fileKindLabel("", name);
    const factsLine =
      state === "uploading"
        ? `Uploading ${Math.round(progress * 100)}%`
        : state === "error"
          ? error || "Couldn't attach that file"
          : factsText || [kind, formatFileSize(size)].filter(Boolean).join(" · ");
    facts.textContent = pill && state === "ready" ? `[${(factsText || kind || "File").split(" · ")[0]}]` : factsLine;
    const body = document.createElement("span");
    body.className = "att-chip-body";
    body.append(nameEl, facts);
    if (onOpen) {
      const open = document.createElement("button");
      open.type = "button";
      open.className = "att-chip-open";
      open.setAttribute("aria-haspopup", "dialog");
      if (title) open.setAttribute("aria-label", `${title}, ${facts.textContent}`);
      open.append(tile, body);
      open.addEventListener("click", onOpen);
      chipEl.append(open);
    } else chipEl.append(tile, body);
    if (state === "uploading") {
      lazyScript("/css/chip-bar-lazy.css");
      const bar = document.createElement("progress");
      bar.className = "att-chip-bar";
      bar.max = 100;
      bar.value = Math.round(progress * 100);
      bar.setAttribute("aria-label", `Uploading ${name}`);
      chipEl.append(bar);
    }
    if (onRemove) {
      const remove = document.createElement("button");
      remove.className = "att-chip-x";
      remove.type = "button";
      setLabel(remove, "ph:x");
      remove.title = removeTitle || `Remove “${name}”`;
      remove.setAttribute("aria-label", remove.title);
      remove.addEventListener("click", onRemove);
      chipEl.append(remove);
    }
    return chipEl;
  }

  //: A picture by the type the browser reports, else by its extension.
  function isImageFile(file) {
    // The type the browser reports, falling back to the extension, a file
    // dragged from some archives arrives with an empty `type`.
    if ((file.type || "").startsWith("image/")) return true;
    return /\.(png|jpe?g|gif|webp|bmp|avif|ico|tiff?|heic|heif|svg)$/i.test(file.name || "");
  }

  /** The one-line form of the attachment card, for a surface too small for a card. */
  function fileChip(name, url) {
    const label = name && name !== url ? name : url.split("/").pop();
    const chipEl = document.createElement("span");
    chipEl.className = "chip file-chip";
    setLabel(chipEl, `${(attachmentIconClass(url, name) || "ph-file").replace("ph-", "ph:")} ${label}`);
    chipEl.title = `${fileKindLabel(url, name)}: ${label}`;
    return chipEl;
  }

  //: A markdown link to our own `/media/` or `/files/`, the one rule (L544). An `https://` image is
  //: blocked by the CSP (`img-src 'self'`), so it would draw a broken frame.
  const OWN_FILE_LINK = /(!?)\[([^\]\n]{0,200})\]\((\/(?:media|files)\/[^)\s]{1,500})\)/g;
  //: Matches as `[all, bang, alt, url]`.
  const ownFileLinks = (text) => [...String(text || "").matchAll(OWN_FILE_LINK)];

  Object.assign(window, { attachmentIconClass, attachmentExt, fileChip, formatFileSize, attachmentChip, isImageFile, ownFileLinks });
})();
