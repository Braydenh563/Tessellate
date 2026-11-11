// documents-tabs.js: the code editor's open files as a tab strip (audit 1028 D52).
//
// The smallest multi-file workspace: every code file you open is remembered
// (up to eight, this browser only, ids and nothing else) and, once two are
// open, a strip of them sits above the editor. A tab is a plain
// `openDocument(id)`, so saving the one you leave, the conflict check and the
// restored caret are the editor's own; nothing here touches a document's text.
// Prose documents never enter the strip and never show it. Split panes stay
// the editor's own Ctrl+\ split.
//
// Loaded in the Library bundle right after documents.js, which announces
// a `doc-shown` event when a document opens (detail: the document) and when
// the page goes back to the list (detail: null). One closure and no exports.
(() => {
  const KEY = "doc-tabs";
  const MAX = 8;

  const read = () => prefs.json(KEY, []).filter((id) => Number.isInteger(id)).slice(0, MAX);
  const write = (ids) => prefs.set(KEY, JSON.stringify(ids.slice(0, MAX)));

  //: The title a tab carries: the open document's own box while it is the open
  //: one (a rename shows at once), else the list row.
  function labelOf(id) {
    if (currentDoc && currentDoc.id === id) return $("doc-title").value.trim() || "Untitled";
    return (docs.find((d) => d.id === id)?.title || "").trim() || "Untitled";
  }

  //: A code file you open joins the strip; the oldest tab that is not the open
  //: one falls off past eight. Called from `openDocument` with the document
  //: now on screen, and with null from `showNoDocument`.
  function docTabsNote(doc) {
    if (doc && docIsCodeFile()) {
      //: A tab keeps its place when it is chosen again; only a new file is added, at the end.
      const ids = read();
      if (!ids.includes(doc.id)) {
        ids.push(doc.id);
        while (ids.length > MAX) ids.shift();
        write(ids);
      }
    }
    docTabsRender();
  }

  //: The strip as it stands. Hidden for a prose document, a blank page and
  //: fewer than two tabs; a tab whose document is gone from the list (deleted,
  //: or in the bin) is dropped here rather than offered.
  function docTabsRender() {
    const row = $("doc-tabs-row");
    const strip = $("doc-tabs");
    if (!row || !strip) return;
    let ids = read();
    if (docs.length) {
      const kept = ids.filter((id) => (currentDoc && currentDoc.id === id) || docs.some((d) => d.id === id));
      if (kept.length !== ids.length) write((ids = kept));
    }
    const show = Boolean(currentDoc) && docIsCodeFile() && ids.length > 1 && ids.includes(currentDoc.id);
    row.classList.toggle("hidden", !show);
    strip.replaceChildren();
    if (!show) return;
    for (const id of ids) {
      const tab = document.createElement("button");
      const active = currentDoc.id === id;
      tab.type = "button";
      tab.className = "doc-tab";
      tab.dataset.docId = String(id);
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", active ? "true" : "false");
      tab.tabIndex = active ? 0 : -1;
      tab.textContent = labelOf(id);
      tab.title = tab.textContent;
      strip.appendChild(tab);
    }
  }

  //: Closing the open tab goes to its neighbour (the one to the left, else the
  //: right); closing another just drops it. The last code file left is not
  //: closable here: the dock's Documents button is the way back.
  function docTabsClose(id) {
    const ids = read();
    const at = ids.indexOf(id);
    if (at < 0 || ids.length < 2) return;
    ids.splice(at, 1);
    write(ids);
    if (currentDoc && currentDoc.id === id) openDocument(ids[Math.max(0, at - 1)]);
    else docTabsRender();
  }

  function onStripClick(event) {
    const tab = event.target.closest?.(".doc-tab");
    if (!tab) return;
    const id = Number(tab.dataset.docId);
    if (currentDoc && currentDoc.id !== id) openDocument(id);
  }

  //: Arrow keys move along the strip and open the tab they land on, the
  //: tablist pattern the other strips follow.
  function onStripKey(event) {
    const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    if (!step) return;
    const tabs = [...$("doc-tabs").querySelectorAll(".doc-tab")];
    const here = tabs.findIndex((t) => t === document.activeElement);
    const next = tabs[here + step];
    if (here < 0 || !next) return;
    event.preventDefault();
    next.focus();
    next.click();
  }

  //: Middle-click closes, as in every editor with tabs.
  function onStripAux(event) {
    if (event.button !== 1) return;
    const tab = event.target.closest?.(".doc-tab");
    if (!tab) return;
    event.preventDefault();
    docTabsClose(Number(tab.dataset.docId));
  }

  const strip = $("doc-tabs");
  if (strip) {
    strip.addEventListener("click", onStripClick);
    strip.addEventListener("keydown", onStripKey);
    strip.addEventListener("auxclick", onStripAux);
    $("doc-tab-end")?.addEventListener("click", () => currentDoc && docTabsClose(currentDoc.id));
    //: A rename shows on its tab as it is typed.
    $("doc-title")?.addEventListener("input", () => {
      const tab = strip.querySelector(`.doc-tab[aria-selected="true"]`);
      if (tab && currentDoc) {
        tab.textContent = labelOf(currentDoc.id);
        tab.title = tab.textContent;
      }
    });
  }

  //: documents.js announces `doc-shown` (the document now on screen, or null
  //: on the blank page); nothing here is a global, so the shared scope does not grow.
  document.addEventListener("doc-shown", (event) => docTabsNote(event.detail));
})();
