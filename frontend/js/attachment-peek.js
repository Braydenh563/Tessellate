// A notebook card's preview in Chat (INBOX 1460), loaded on the first press
// (LAZY_MODULES.attachmentPeek in app.js), off the boot scripts' budget.
//: **The citation peek, for what a message was given.** A note, a document, a
//: mind map or a library file previews in the one panel a numbered source mark
//: opens (`openCitationPeek`, capture-ask.js), so the shell, the placing, the
//: Escape and the way back to the card are already its own. The card passes
//: its own door as `open`, which the panel's Open button and a press on the
//: preview both take. What the panel reads is fetched here: a document's
//: opening words, a map's topics in outline order, a file's extracted text;
//: when the fetch fails the panel carries the card's facts line instead.
//:
//: `item` is the card's `{kind, id, name, entry, facts}`, `door` the button
//: that was pressed (the panel points at it and hands focus back to it), and
//: `keyboard` is true when Enter or Space pressed it, so focus moves into the
//: panel as it does for a mark (capture-ask.js).
async function attachmentPeek(item, door, open, keyboard) {
  let entry = item.entry;
  if (item.kind === "document") {
    const doc = await apiJson(`/documents/${item.id}`).catch(() => null);
    entry = { content: doc?.content || "", category: "Document", created_at: doc?.updated_at || doc?.created_at };
  }
  if (item.kind === "map") {
    const tree = await apiJson(`/whiteboard/boards/${item.id}/tree`).catch(() => null);
    const topics = [];
    const walk = (nodes) => nodes.forEach((n) => (n.text && topics.push(n.text), walk(n.children || [])));
    walk(tree?.roots || []);
    if (topics.length) entry = { content: topics.join(" · "), category: "Mind map" };
  }
  if (item.kind === "file") {
    const file = await apiJson(`/files/${item.id}/text`).catch(() => null);
    if (file?.text) entry = { content: file.text.slice(0, 1200), category: "File" };
  }
  const what = { note: "note", document: "document", map: "mind map", file: "file" }[item.kind] || "item";
  closeCitationPeek();
  openCitationPeek(door, { noteId: item.id, number: "", entry, title: item.name, label: item.facts || item.name, what, open }, { pinned: true });
  const panel = citationPeekState.panel;
  panel?.setAttribute("aria-label", `Preview of ${item.name}`);
  if (keyboard) panel?.querySelector(".citation-peek-preview")?.focus({ preventScroll: true });
}
