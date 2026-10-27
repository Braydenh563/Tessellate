// screen-context.js: where the person is and what they just did, for the
// composer to pick up from (ai/composer_aware.py). Lazy: a stand-in in
// lazy-entries.js fetches it on the first Ask, Chat or Guide turn, and the
// callers await it. The tab, the open document's id and the undo stack's last
// three labels; the server names a note or document, and never a private one.
function screenContext(tab = "") {
  const doc = !$("tab-documents")?.classList.contains("hidden") && typeof currentDoc === "object" && currentDoc?.id;
  return { tab: tab || agentCurrentTab(), actions: undoStack.slice(-3).map((a) => a.label), open_doc_id: doc || undefined };
}
