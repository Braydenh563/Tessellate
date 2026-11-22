// documents-ai-edit.js: the doors to the Atlas panel and the AI edit history, the dock's History buttons, Extract notes, and the sidebar's
// List and Outline tabs. Moved out of documents.js and wrapped (L-documents-116): only what other files call goes on `window`. At load it binds
// two listeners through boot helpers and otherwise only declares; `docAiController` is its own (documents-ai.js assigns it through a window accessor).
(() => {
  //: State that moved here from documents.js (L-documents-118).
  let docAiController = null;
  //: The Atlas panel's code is documents-ai.js, fetched on the first press of any
  //: of its controls (audit 1031 DC13): `docAiLazy` loads it, then calls the
  //: function of that name the file defines.
  async function docAiLazy(name, ...args) {
    //: With the diff library beside it: the panel draws its proposal with `docRenderDiff`.
    if (!(await Promise.all([lazyScript("/js/documents-ai.js"), lazyScript("/js/documents-history.js")])).every(Boolean)) return toast("The Atlas panel could not be loaded.", true, { action: ["Try again", () => docAiLazy(name, ...args)] });
    return window[name](...args);
  }

  function closeDocAiPanel() {
    $("doc-ai-panel").classList.add("hidden");
  }

  // Extract notes (BACKLOG.md §62): the same selection-or-whole-document scope
  // AI edit above already uses, select a passage first to extract from just
  // that, or leave nothing selected to extract from the whole document.
  function openDocExtractPreview() {
    if (!currentDoc) return;
    const box = docSurface();
    const { from, to } = box.selection();
    const selection = box.text.slice(from, to).trim();
    openExtractPreview(selection || box.text, { sourceDocumentId: currentDoc.id });
  }

  // --- AI edit history (the changelog) ---------------------------------------

  function docAiVerbIcon(verb) {
    return { edit: "ph-pencil-simple", write: "ph-plus-circle", remove: "ph-x-circle", revert: "ph-arrow-counter-clockwise" }[verb] || "ph-pencil-simple";
  }

  async function openDocAiHistory() {
    if (!currentDoc) return;
    const dialog = $("doc-ai-history-dialog");
    const list = $("doc-ai-history-list");
    const empty = $("doc-ai-history-empty");
    list.replaceChildren();
    empty.classList.add("hidden");
    dialog.showModal();
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "Loading…";
    list.appendChild(li);
    try {
      const entries = await apiJson(`/documents/${currentDoc.id}/ai-edit-log`);
      list.replaceChildren();
      if (!entries.length) {
        empty.classList.remove("hidden");
        return;
      }
      for (const entry of entries) {
        const row = document.createElement("li");
        row.className = "doc-ai-history-entry";
        const icon = document.createElement("i");
        icon.className = `ph ${docAiVerbIcon(entry.verb)}`;
        icon.setAttribute("aria-hidden", "true");
        const text = document.createElement("div");
        text.className = "doc-ai-history-text";
        const line = document.createElement("p");
        line.textContent = entry.instruction || (entry.verb === "remove" ? "Removed a selection" : "AI edit");
        const meta = document.createElement("p");
        meta.className = "muted text-sm";
        const when = whenText(entry.created_at);
        meta.textContent = entry.selection_excerpt
          ? `${when} · “${entry.selection_excerpt}”`
          : when;
        text.append(line, meta);
        const revertBtn = document.createElement("button");
        revertBtn.type = "button";
        revertBtn.className = "ghost small";
        revertBtn.textContent = "Revert";
        revertBtn.addEventListener("click", async () => {
          revertBtn.disabled = true;
          try {
            const saved = await apiJson(
              `/documents/${currentDoc.id}/ai-edit-log/${entry.id}/revert`,
              { method: "POST" }
            );
            if (currentDoc && currentDoc.id === saved.id) {
              currentDoc = saved;
              docSurface().text = saved.content;
              $("doc-title").value = saved.title;
              renderDocPreview();
              docDirty = false;
              $("doc-saved").textContent = "Saved";
            }
            docs = docs.map((d) => (d.id === saved.id ? { ...d, ...saved } : d));
            renderDocList();
            toast(voiceLine("done", "Reverted"));
            dialog.close();
          } catch (error) {
            toast(error.message || voiceLine("failed", "revert that"), true);
          } finally {
            revertBtn.disabled = false;
          }
        });
        row.append(icon, text, revertBtn);
        list.appendChild(row);
      }
    } catch (error) {
      list.replaceChildren();
      const errLi = document.createElement("li");
      errLi.className = "muted";
      errLi.textContent = error.message || "Couldn't load the history.";
      list.appendChild(errLi);
    }
  }

  //: The version history dialog and the line diff are documents-history.js,
  //: fetched on the first press of the dock's History or Name this version
  //: (audit 1031 DC13). The AI edit panel, the code assistant and the edit-conflict
  //: prompt wait on the same `lazyScript` before they draw a diff, so none of them
  //: can run ahead of `docRenderDiff`.
  for (const [id, name] of [["doc-history", "openDocHistory"], ["doc-history-name", "docNameCurrentVersion"]]) {
    $(id)?.addEventListener("click", async () => {
      if (!(await lazyScript("/js/documents-history.js"))) return toast("The history could not be loaded.", true, { action: ["Try again", () => $(id).click()] });
      return window[name]();
    });
  }
  //: The AI assistant's own model. `openFeatureModelSheet` lives in app.js,
  //: which loads first, and is the same sheet the Chat tab and the writing desk
  //: open: one picker, three ways in.
  $("doc-ai-model")?.addEventListener("click", () => window.openFeatureModelSheet?.("documents"));

  const DOC_SIDEBAR_SECTIONS = ["list", "outline"];
  const DOC_SIDEBAR_STORE = "docSidebarSection";

  function showDocSidebarSection(name) {
    const wanted = DOC_SIDEBAR_SECTIONS.includes(name) ? name : "list";
    for (const section of DOC_SIDEBAR_SECTIONS) {
      $(`doc-sidebar-${section}`)?.classList.toggle("hidden", section !== wanted);
    }
    for (const button of document.querySelectorAll("#doc-sidebar-tabs button")) {
      const active = button.dataset.section === wanted;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    }
    prefs.set(DOC_SIDEBAR_STORE, wanted);
    //: A hidden list has no scroll position to correct, so the mark made while
    //: the Documents tab was showing could not bring its row into view. Asked
    //: again on the way in, when the outline has a box.
    if (wanted === "outline") {
      docOutlineMarked = -1;
      markDocOutline();
      //: The comments section is in this tab and is drawn from the document's own
      //: text on every facts pass, so the same argument applies to it: a hidden
      //: list has nothing to draw into, and the pass that ran while the Documents
      //: tab was showing left it with nothing in it.
      renderDocComments();
    }
  }

  function initDocSidebarTabs() {
    const strip = $("doc-sidebar-tabs");
    if (!strip || strip.dataset.ready) return;
    strip.dataset.ready = "1";
    strip.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-section]");
      if (button) showDocSidebarSection(button.dataset.section);
    });
    strip.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const index = DOC_SIDEBAR_SECTIONS.indexOf(
        prefs.get(DOC_SIDEBAR_STORE, null) || "list"
      );
      const next =
        DOC_SIDEBAR_SECTIONS[
          (index + step + DOC_SIDEBAR_SECTIONS.length) % DOC_SIDEBAR_SECTIONS.length
        ];
      showDocSidebarSection(next);
      strip.querySelector(`button[data-section="${next}"]`)?.focus();
    });
    showDocSidebarSection(prefs.get(DOC_SIDEBAR_STORE, null) || "list");
  }

  //: The file's surface: what other files call.
  Object.assign(window, { closeDocAiPanel, showDocSidebarSection, initDocSidebarTabs });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docAiController", () => docAiController, (value) => { docAiController = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });

  $("doc-ai").addEventListener("click", () => docAiLazy("openDocAiPanel"));

  $("doc-ai-close").addEventListener("click", closeDocAiPanel);

  $("doc-ai-cancel").addEventListener("click", closeDocAiPanel);

  $("doc-ai-run").addEventListener("click", () => docAiLazy("runDocAiEdit"));

  $("doc-ai-cancel-run").addEventListener("click", () => docAiController?.abort());

  $("doc-ai-accept").addEventListener("click", () => docAiLazy("acceptDocAiEdit"));

  $("doc-ai-instruction").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); docAiLazy("runDocAiEdit"); }
  });

  for (const radio of document.querySelectorAll('input[name="doc-ai-verb"]')) {
    radio.addEventListener("change", () => docAiLazy("docAiVerbChanged"));
  }

  $("doc-ai-history").addEventListener("click", openDocAiHistory);

  $("doc-extract").addEventListener("click", openDocExtractPreview);

  initDocSidebarTabs();
})();
