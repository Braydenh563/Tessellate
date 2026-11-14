// documents-block-ids.js: block ids (^id): find, make, strip and reveal.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  // DOC-BLOCKREF-BEGIN
  const DOC_BLOCK_ID = "[A-Za-z0-9][A-Za-z0-9-]{0,31}";
  const DOC_BLOCK_ID_AT_END = new RegExp(`(?:^|[ \\t])\\^(${DOC_BLOCK_ID})[ \\t]*$`);
  const DOC_BLOCK_LIST_LINE = /^\s*(?:[-*+]|\d{1,9}[.)])\s+/;
  function docBlockRefSplit(spec) {
    const text = String(spec == null ? "" : spec);
    const hash = text.indexOf("#^");
    if (hash === -1) return { name: text.trim(), blockId: null };
    const id = text.slice(hash + 2).trim();
    return {
      name: text.slice(0, hash).trim(),
      blockId: new RegExp(`^${DOC_BLOCK_ID}$`).test(id) ? id : null,
    };
  }
  function docBlockInFence(lines, index) {
    let open = false;
    for (let i = 0; i < index; i++) {
      if (/^\s*(?:```|~~~)/.test(lines[i])) open = !open;
    }
    return open;
  }
  function docBlockBounds(text, pos) {
    const body = String(text == null ? "" : text);
    const lines = body.split("\n");
    const starts = [];
    let at = 0;
    for (const line of lines) {
      starts.push(at);
      at += line.length + 1;
    }
    const clamped = Math.max(0, Math.min(body.length, pos | 0));
    let index = 0;
    while (index + 1 < lines.length && starts[index + 1] <= clamped) index++;
    if (!lines[index].trim()) return null;
    if (docBlockInFence(lines, index)) return null;
    let first = index;
    let last = index;
    if (!DOC_BLOCK_LIST_LINE.test(lines[index])) {
      while (first > 0 && lines[first - 1].trim() && !DOC_BLOCK_LIST_LINE.test(lines[first - 1])) {
        first--;
      }
      while (
        last + 1 < lines.length &&
        lines[last + 1].trim() &&
        !DOC_BLOCK_LIST_LINE.test(lines[last + 1])
      ) {
        last++;
      }
    }
    return {
      from: starts[first],
      to: starts[last] + lines[last].length,
      lastFrom: starts[last],
      lastTo: starts[last] + lines[last].length,
    };
  }
  function docBlockIdOf(text, bounds) {
    if (!bounds) return null;
    const line = String(text).slice(bounds.lastFrom, bounds.lastTo);
    const match = DOC_BLOCK_ID_AT_END.exec(line);
    if (!match) return null;
    return {
      id: match[1],
      from: bounds.lastFrom + match.index,
      to: bounds.lastFrom + match.index + match[0].length,
    };
  }
  function docBlockIds(text) {
    const found = new Set();
    for (const line of String(text == null ? "" : text).split("\n")) {
      const match = DOC_BLOCK_ID_AT_END.exec(line);
      if (match) found.add(match[1]);
    }
    return found;
  }
  function docBlockNewId(text, random) {
    const roll = typeof random === "function" ? random : Math.random;
    const taken = docBlockIds(text);
    for (let attempt = 0; attempt < 50; attempt++) {
      const id = Math.floor(roll() * 36 ** 6)
        .toString(36)
        .padStart(6, "0")
        .slice(-6);
      if (!taken.has(id)) return id;
    }
    return null;
  }
  function docBlockEnsureIdEdits(text, pos, random) {
    const bounds = docBlockBounds(text, pos);
    if (!bounds) return { id: null, edits: [], reason: "no-block" };
    const existing = docBlockIdOf(text, bounds);
    if (existing) return { id: existing.id, edits: [], reason: "already" };
    const id = docBlockNewId(text, random);
    if (!id) return { id: null, edits: [], reason: "no-id" };
    const line = String(text).slice(bounds.lastFrom, bounds.lastTo);
    //: Trailing spaces are not kept in front of the id: two of them at the end
    //: of a markdown line are a hard line break, and `  ^id` would move it.
    const trimmed = line.replace(/[ \t]+$/, "");
    return {
      id,
      edits: [
        {
          from: bounds.lastFrom + trimmed.length,
          to: bounds.lastTo,
          insert: ` ^${id}`,
        },
      ],
      reason: "added",
    };
  }
  function docBlockFind(text, id) {
    const body = String(text == null ? "" : text);
    if (!new RegExp(`^${DOC_BLOCK_ID}$`).test(String(id || ""))) return null;
    const lines = body.split("\n");
    let at = 0;
    for (let index = 0; index < lines.length; index++) {
      const match = DOC_BLOCK_ID_AT_END.exec(lines[index]);
      if (match && match[1] === id && !docBlockInFence(lines, index)) {
        const bounds = docBlockBounds(body, at);
        if (!bounds) return null;
        const marker = docBlockIdOf(body, bounds);
        const whole = body.slice(bounds.from, bounds.to);
        const clean = marker
          ? whole.slice(0, marker.from - bounds.from) + whole.slice(marker.to - bounds.from)
          : whole;
        return { from: bounds.from, to: bounds.to, text: clean };
      }
      at += lines[index].length + 1;
    }
    return null;
  }
  function docBlockStripIds(text) {
    let fenced = false;
    return String(text == null ? "" : text)
      .split("\n")
      .map((line) => {
        if (/^\s*(?:```|~~~)/.test(line)) {
          fenced = !fenced;
          return line;
        }
        return fenced ? line : line.replace(DOC_BLOCK_ID_AT_END, "");
      })
      .join("\n");
  }
  // DOC-BLOCKREF-END
  const docBlockTextCache = new Map();
  function docBlockDocumentText(doc) {
    if (!doc) return null;
    if (currentDoc && doc.id === currentDoc.id) return docText();
    if (doc.content != null) return doc.content;
    return docBlockTextCache.has(doc.id) ? docBlockTextCache.get(doc.id) : null;
  }
  async function docCopyBlockRef(mode = "link") {
    if (!(await lazyScript("/js/documents-blockref.js"))) return toast("The block references could not be loaded.", true, { action: ["Try again", () => docCopyBlockRef(mode)] });
    return docBlockrefPiece.docCopyBlockRef(mode);
  }
  async function docRevealBlock(blockId) {
    if (!(await lazyScript("/js/documents-blockref.js"))) return toast("The block references could not be loaded.", true, { action: ["Try again", () => docRevealBlock(blockId)] });
    return docBlockrefPiece.docRevealBlock(blockId);
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docBlockRefSplit, docBlockEnsureIdEdits, docBlockFind, docBlockStripIds, docBlockTextCache, docBlockDocumentText, docCopyBlockRef, docRevealBlock });
})();
