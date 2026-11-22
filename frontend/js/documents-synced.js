// documents-synced.js: a synced block (DOCUMENTS_PLAN 26, decision 82). `![[Doc#^id]]` shows one block of another document
// as a window onto it; the pencil in the window's corner opens the block's text in a box, and Save writes it into the
// document the block lives in, through the document's own save (its history, its conflict guard). The block exists once.
// Lazy: `LAZY_MODULES.docSynced`; documents-embeds.js draws the pencil and asks for this file on the first press. It uses
// the boot scripts' `window.docBlockFind`, `window.offerUndo`, `smallButton`, `apiJson` and `toast`, and adds no global name.
(() => {
  // DOC-SYNCED-BEGIN (tests/test_doc_blockrefs.py runs this region in node, after the block-reference region)
  //: The document with the block carrying `id` rewritten to `replacement` (SYNCED BLOCKS, DOCUMENTS_PLAN 26): its `^id` stays on
  //: the last line, so every link and embed of it still resolves. Null when nothing carries the id, when the replacement is
  //: empty, or when it would no longer be that one block (a blank line in it splits it in two): the caller refuses the edit
  //: rather than saving a block that has become two.
  function replace(text, id, replacement) {
    const body = String(text == null ? "" : text);
    const found = window.docBlockFind(body, id);
    const clean = String(replacement == null ? "" : replacement).replace(/\s+$/, "");
    if (!found || !clean.trim()) return null;
    const next = body.slice(0, found.from) + clean + ` ^${id}` + body.slice(found.to);
    const again = window.docBlockFind(next, id);
    return again && again.text === clean ? next : null;
  }
  // DOC-SYNCED-END

  //: Other windows hear of a save here (documents-embeds.js listens: `syncedRedraw`); this page's own embeds hear it as an event.
  const channel = window.BroadcastChannel ? new BroadcastChannel("memorymap-doc-synced") : null;

  //: One write of the source document, guarded by the hash of the text the caller last saw (a change elsewhere is a conflict apiJson names).
  const writeSource = (id, hash, content, cache) =>
    apiJson(`/documents/${id}`, { method: "PUT", body: JSON.stringify({ content, base_hash: hash }) }).then((saved) => {
      cache.set(id, saved.content ?? content);
      document.dispatchEvent(new CustomEvent("synced-saved", { detail: { id } }));
      channel?.postMessage({ id });
      return saved;
    });

  //: Undo and Redo for a saved block (the undo contract): each is a write of the whole document back, chained on the hash the last one returned.
  function offerSavedUndo(target, before, after, hash, cache) {
    let at = hash;
    const move = (content) => writeSource(target.doc.id, at, content, cache).then((saved) => void (at = saved.content_hash));
    window.offerUndo(
      "Edit synced block",
      `Saved in ${target.doc.title || "the document"}.`,
      () => move(before),
      () => move(after)
    );
  }

  //: **Edit a synced block where it is shown.** A box of its text and Save, Cancel; Save reads the source document afresh,
  //: rewrites that one block (`replace`, which keeps its `^id`) and saves it with the document's own conflict guard,
  //: so the document history has the change. Other edits to the document in the meantime stay; a changed block is refused.
  //: `own` is the block's pencil in its own document (decision 82 b): the box floats by the marker (`own.close` takes it away) and Save
  //: writes into the open editor, which saves the document as it saves anything, so the text being typed is never overwritten.
  function edit(box, text, target, draw, cache, own = null) {
    const area = document.createElement("textarea");
    area.className = "doc-embed-block-input";
    area.value = text;
    area.rows = 3;
    area.setAttribute("aria-label", `Edit the block from ${target.doc.title || "the document"}`);
    const row = document.createElement("div");
    row.className = "doc-embed-block-actions";
    const back = () => {
      if (own) return own.close();
      const fresh = draw();
      if (fresh) box.replaceWith(fresh);
    };
    const save = smallButton("ph:check Save", "Save this block into its document (Ctrl+Enter)", async () => {
      save.disabled = true;
      try {
        if (own) {
          if (own.save(text, area.value)) back();
          return;
        }
        const source = await apiJson(`/documents/${target.doc.id}`);
        //: The rest of the document may have moved on (the edit lands on the latest text); the block itself may not have.
        if (window.docBlockFind(source.content || "", target.blockId)?.text !== text) {
          toast("That block changed elsewhere since you opened it. Copy your text, cancel, and open it again.", "info");
          return;
        }
        const next = replace(source.content || "", target.blockId, area.value);
        if (next === null) {
          toast("A block is one paragraph. Take out any blank line, or leave it as it was.", "info");
          return;
        }
        if (next !== source.content) {
          const saved = await writeSource(target.doc.id, source.content_hash, next, cache);
          offerSavedUndo(target, source.content || "", next, saved.content_hash, cache);
        }
        back();
      } catch {
        //: apiJson has already said why (a document changed elsewhere is a conflict it names); the text stays for another try.
      } finally {
        save.disabled = false;
      }
    });
    const cancel = smallButton("ph:x Cancel", "Leave the block as it was (Esc)", back);
    area.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        back();
      } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        save.click();
      }
    });
    row.append(save, cancel);
    box.replaceChildren(area, row);
    area.focus();
  }

  //: The block's own document: the editor's text is the source, so the rewrite is an edit of it (the document's own save and Undo follow).
  function saveOwn(id, was, value) {
    const text = docText();
    const found = window.docBlockFind(text, id);
    if (found?.text !== was) {
      toast("That block changed since you opened it. Copy your text, cancel, and open it again.", "info");
      return false;
    }
    if (replace(text, id, value) === null) {
      toast("A block is one paragraph. Take out any blank line, or leave it as it was.", "info");
      return false;
    }
    const surface = docSurface();
    if (!surface) return false;
    docTableDispatch({ surface, text }, [{ from: found.from, to: found.to, insert: `${value.replace(/\s+$/, "")} ^${id}` }]);
    markDocDirty();
    return true;
  }

  document.addEventListener("synced-own", (event) => {
    const { id, anchor } = event.detail;
    const found = window.docBlockFind(docText(), id);
    document.querySelector(".doc-synced-own")?.remove();
    if (!found) return;
    const panel = document.createElement("div");
    panel.className = "doc-synced-own";
    const rect = anchor.getBoundingClientRect();
    panel.style.top = `${Math.round(rect.bottom + 4)}px`;
    panel.style.left = `${Math.round(Math.max(8, Math.min(rect.left, window.innerWidth - 360)))}px`;
    const close = () => {
      panel.remove();
      document.removeEventListener("pointerdown", outside, true);
    };
    const outside = (press) => {
      if (!panel.contains(press.target)) close();
    };
    document.body.append(panel);
    document.addEventListener("pointerdown", outside, true);
    edit(panel, found.text, { doc: currentDoc, blockId: id }, () => null, new Map(), { close, save: (was, value) => saveOwn(id, was, value) });
  });

  //: The pencil (documents-embeds.js) loads this file and then says which box to open; a listener, so the file adds no global name.
  document.addEventListener("synced-edit", (event) => edit(event.target, event.detail.text, event.detail.target, event.detail.draw, event.detail.cache));
})();
