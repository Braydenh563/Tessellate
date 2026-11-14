// documents-subpages.js: sub-pages (DOCUMENTS_PLAN D14, L-documents-44). A document may sit under one other; the
// server keeps the parent (`documents.parent_id`) and refuses a loop. This file is the browser half: the Library's
// Documents list drawn as a tree (collapsed by default, a disclosure per parent), the kebab's New sub-page and Move
// under, the "/" menu's `/subpage`, and the breadcrumb of parents in the document head.
//
// **Loaded by library.js** (both of its bundles) as it loads, so nothing in the boot budget grows; every caller reaches
// it through `docSubpagesPiece` and checks it is there, and a list drawn before it lands is a flat list, as before.
(() => {
  //: Which parents are open, kept per viewer: a tree that closes on every redraw would be a tree to reopen after each rename.
  const OPEN_KEY = "library-docs-open";
  const opened = new Set((prefs.get(OPEN_KEY, null) || []).map(Number));
  const keepOpened = () => prefs.set(OPEN_KEY, [...opened]);
  //: What `order` worked out for each row, read back by `decorate` as the row is drawn.
  const placed = new Map();

  //: The list in tree order: each parent, then its children (in the order the list was sorted), depth first. A row
  //: whose parent is not in the list (binned, shelved, another space's) is drawn at the top level. Under a closed
  //: parent the rows are left out.
  function order(docs) {
    placed.clear();
    const ids = new Set(docs.map((d) => d.id));
    const kids = new Map();
    const roots = [];
    for (const doc of docs) {
      const parent = doc.parent_id != null && ids.has(doc.parent_id) && doc.parent_id !== doc.id ? doc.parent_id : null;
      if (parent == null) roots.push(doc);
      else (kids.get(parent) || kids.set(parent, []).get(parent)).push(doc);
    }
    const out = [];
    const seen = new Set();
    const walk = (doc, depth) => {
      if (seen.has(doc.id)) return;
      seen.add(doc.id);
      const children = kids.get(doc.id) || [];
      placed.set(doc.id, { depth, children: children.length });
      out.push(doc);
      if (children.length && opened.has(doc.id)) for (const child of children) walk(child, depth + 1);
    };
    for (const doc of roots) walk(doc, 0);
    return out;
  }

  //: The row's depth and, on a parent, its disclosure: a caret button before the tick that opens and closes the
  //: rows under it (`aria-expanded`), the count in its name.
  function decorate(item, row, doc, redraw) {
    const at = placed.get(doc.id);
    if (!at) return;
    if (at.depth) {
      item.classList.add("doc-tree-child");
      if (at.depth > 1) item.style.marginInlineStart = `calc(${at.depth} * var(--space-7))`;
    }
    if (!at.children) return;
    const open = opened.has(doc.id);
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "ghost icon-btn doc-tree-toggle";
    toggle.setAttribute("aria-expanded", String(open));
    const name = `${open ? "Hide" : "Show"} ${nounCount(at.children, "sub-page")} of “${doc.title || "Untitled"}”`;
    toggle.setAttribute("aria-label", name);
    toggle.title = name;
    setLabel(toggle, "ph:caret-right");
    toggle.addEventListener("click", (event) => {
      event.stopPropagation();
      if (opened.has(doc.id)) opened.delete(doc.id);
      else opened.add(doc.id);
      keepOpened();
      redraw();
    });
    row.querySelector(".doc-list-top")?.prepend(toggle);
  }

  //: After a write, both lists that show documents follow: the Library's (drawn here) and the editor's own, when loaded.
  function refresh() {
    //: library.js loads this file, so its list function is always there; documents.js may not be loaded yet.
    if ($("library-docs-list")?.offsetParent) renderLibraryDocuments();
    if (typeof loadDocuments === "function" && $("tab-documents") && !$("tab-documents").classList.contains("hidden")) loadDocuments(currentDoc?.id);
    if (typeof currentDoc !== "undefined" && currentDoc) crumbs(currentDoc.id);
    document.dispatchEvent(new Event("documents-undone"));
  }

  //: A new document under `parent`, titled by the person; Undo bins it and Redo brings the same one back.
  async function create(parent, title) {
    const made = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title, content: "", parent_id: parent.id }) });
    opened.add(parent.id);
    keepOpened();
    offerUndo(
      `Made “${clipText(made.title, 40)}”`,
      `Made ${toastName(made.title, "the sub-page")} under ${toastName(parent.title, "its parent")}.`,
      async () => (await apiJson(`/documents/${made.id}`, { method: "DELETE" }), refresh()),
      async () => (await apiJson(`/documents/${made.id}/restore`, { method: "POST" }), refresh())
    );
    return made;
  }

  //: The kebab's New sub-page: named, made, opened.
  async function newSubpage(parent) {
    const title = await promptDialog(`New sub-page under “${clipText(parent.title || "Untitled", 40)}”`, "", { confirmLabel: "Create" });
    if (!title) return;
    let made;
    try {
      made = await create(parent, title);
    } catch (error) {
      toast(voiceLine("failed", { what: "make the sub-page", why: error.message }), true);
      return;
    }
    refresh();
    switchTab("documents");
    openDocument(made.id);
  }

  //: Put `doc` under `parentId` (null is the top level); the server refuses a loop with a sentence of its own.
  async function place(doc, parentId) {
    return apiJson(`/documents/${doc.id}`, { method: "PUT", body: JSON.stringify({ parent_id: parentId }) });
  }

  //: The kebab's Move under: the document picker, then the move; Undo puts it back under the parent it had.
  async function moveUnder(doc, toTop = false) {
    let parentId = null;
    if (!toTop) {
      const chosen = await pickLibraryItemDialog(`Move “${clipText(doc.title || "Untitled", 40)}” under`, { sources: ["document"] });
      if (!chosen?.row) return;
      parentId = chosen.row.id;
    }
    const before = doc.parent_id ?? null;
    try {
      await place(doc, parentId);
    } catch (error) {
      toast(voiceLine("failed", { what: "move that page", why: error.message }), true);
      return;
    }
    if (parentId != null) opened.add(parentId), keepOpened();
    offerUndo(
      `Moved “${clipText(doc.title || "Untitled", 40)}”`,
      parentId == null ? `Moved ${toastName(doc.title, "the page")} to the top level.` : `Moved ${toastName(doc.title, "the page")} under ${toastName(chosenTitle(parentId), "that page")}.`,
      async () => (await place(doc, before), refresh()),
      async () => (await place(doc, parentId), refresh())
    );
    refresh();
  }

  function chosenTitle(id) {
    const all = typeof libraryDocsAll !== "undefined" ? libraryDocsAll : [];
    return all.find((d) => d.id === id)?.title || "";
  }

  //: The two kebab rows, for library.js's row menu: New sub-page always, Move under, and Move to the top level on a child.
  function menuItems(doc) {
    const items = [
      makeMenuItem("ph:file-plus New sub-page", "Make a document under this one", () => newSubpage(doc)),
      makeMenuItem("ph:tree-view Move under", "Put this document under another one", () => moveUnder(doc)),
    ];
    if (doc.parent_id != null) items.push(makeMenuItem("ph:arrow-line-left Move to the top level", "Take this document out from under its parent", () => moveUnder(doc, true)));
    return items;
  }

  //: The "/" menu's Sub-page: a child of the open document, and a link to it where the "/" was typed. The person stays
  //: in the parent, which is where they were writing; the link opens the child.
  async function slash(textarea) {
    const parent = typeof currentDoc !== "undefined" ? currentDoc : null;
    if (!parent?.id) return toast("Save the document first.", "info");
    const at = textarea.selectionStart;
    const title = await promptDialog("Title for the sub-page", "", { confirmLabel: "Create" });
    if (!title) return;
    let made;
    try {
      made = await create(parent, title);
    } catch (error) {
      toast(voiceLine("failed", { what: "make the sub-page", why: error.message }), true);
      return;
    }
    textarea.focus();
    editorSplice(textarea, at, at, `[[${String(made.title).replace(/[[\]|]/g, "")}]]`, null);
    refresh();
  }

  //: The breadcrumb: the open document's parents, root first, each a link that opens it. Empty on a top-level page.
  async function crumbs(id) {
    const host = $("doc-back")?.parentElement;
    if (!host) return;
    let trail = host.querySelector(".doc-crumbs");
    let full;
    try {
      full = await apiJson(`/documents/${id}`);
    } catch {
      return trail?.remove();
    }
    if (typeof currentDoc !== "undefined" && currentDoc?.id !== id) return;
    const parents = full.parents || [];
    if (!parents.length) return trail?.remove();
    if (!trail) {
      trail = document.createElement("nav");
      trail.className = "doc-crumbs muted";
      trail.setAttribute("aria-label", "Parent pages");
      //: After the way back ("Documents"), so the row reads as one path: Documents / Parent / this page.
      (host.querySelector("#doc-back") || host.querySelector("#doc-title")).after(trail);
    }
    trail.replaceChildren(
      ...parents.flatMap((p) => {
        const link = document.createElement("button");
        link.type = "button";
        link.className = "ghost small doc-crumb";
        link.textContent = p.title || "Untitled";
        link.title = `Open “${p.title || "Untitled"}”`;
        link.addEventListener("click", () => openDocument(p.id));
        const sep = document.createElement("span");
        sep.className = "doc-crumb-sep";
        sep.setAttribute("aria-hidden", "true");
        sep.textContent = "/";
        return [link, sep];
      })
    );
  }

  document.addEventListener("doc-shown", (event) => event.detail?.id && crumbs(event.detail.id));
  //: Opened before this file landed: draw for the document already on screen.
  if (typeof currentDoc !== "undefined" && currentDoc?.id) crumbs(currentDoc.id);

  //: The file's whole surface, one name in the shared scope (documents-blockref.js's pattern).
  Object.assign(window, { docSubpagesPiece: { order, decorate, menuItems, slash } });
})();
