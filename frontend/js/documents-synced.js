// documents-synced.js: a synced block (DOCUMENTS_PLAN 26, decision 82). `![[Doc#^id]]` shows one block of another document
// as a window onto it; the pencil in the window's corner opens the block's text in a box, and Save writes it into the
// document the block lives in, through the document's own save (its history, its conflict guard). The block exists once.
// Lazy: `LAZY_MODULES.docSynced`; documents-embeds.js draws the pencil and asks for this file on the first press. It uses
// the boot scripts' `window.docBlockFind`, `smallButton`, `apiJson` and `toast`, and adds no global name.
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

  //: **Edit a synced block where it is shown.** A box of its text and Save, Cancel; Save reads the source document afresh,
  //: rewrites that one block (`replace`, which keeps its `^id`) and saves it with the document's own conflict guard,
  //: so the document history has the change. Other edits to the document in the meantime stay; a changed block is refused.
  function edit(box, text, target, draw, cache) {
    const area = document.createElement("textarea");
    area.className = "doc-embed-block-input";
    area.value = text;
    area.rows = 3;
    area.setAttribute("aria-label", `Edit the block from ${target.doc.title || "the document"}`);
    const row = document.createElement("div");
    row.className = "doc-embed-block-actions";
    const back = () => {
      const fresh = draw();
      if (fresh) box.replaceWith(fresh);
    };
    const save = smallButton("ph:check Save", "Save this block into its document (Ctrl+Enter)", async () => {
      save.disabled = true;
      try {
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
          const saved = await apiJson(`/documents/${target.doc.id}`, { method: "PUT", body: JSON.stringify({ content: next, base_hash: source.content_hash }) });
          cache.set(target.doc.id, saved.content ?? next);
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

  //: The pencil (documents-embeds.js) loads this file and then says which box to open; a listener, so the file adds no global name.
  document.addEventListener("synced-edit", (event) => edit(event.target, event.detail.text, event.detail.target, event.detail.draw, event.detail.cache));
})();
