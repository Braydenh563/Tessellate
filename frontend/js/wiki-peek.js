// wiki-peek.js: a `[[link]]` in a note previews the note it points at on hover
// or focus (L573), in the citation peek's one panel (citation-peek.js), so the
// placing, Escape, Tab and the way back are that panel's own. Loaded on the
// first hover or focus of a wiki link (the delegate in app.js), off the
// boot scripts' budget.
(() => {
  let timer = 0;
  //: `keyboard` is true for a focus: the panel opens at once and stays until
  //: focus leaves, as a citation mark does. A hover waits 350 ms, so a pointer
  //: crossing a paragraph does not flash a card at every link it passes.
  function wikiPeek(link, keyboard) {
    clearTimeout(timer);
    clearTimeout(citationPeekState.closeTimer);
    if (citationPeekState.link === link || citationPeekState.restoring) return;
    if (!link.dataset.peekWired) {
      link.dataset.peekWired = "1";
      link.addEventListener("mouseleave", () => (clearTimeout(timer), scheduleCitationPeekClose()));
      link.addEventListener("focusout", (event) => {
        clearTimeout(timer);
        if (!citationPeekState.panel?.contains(event.relatedTarget)) scheduleCitationPeekClose();
      });
    }
    timer = setTimeout(() => {
      if (!link.isConnected || !(keyboard ? link === document.activeElement : link.matches(":hover"))) return;
      //: Only a note previews: a board shows as its own chip and a document
      //: opens a pane, and a name with nothing behind it offers to make one.
      const target = resolveWikiTarget(link.dataset.wiki);
      if (target?.kind !== "note") return;
      openCitationPeek(link, { noteId: target.entry.id, number: "", entry: target.entry, title: link.textContent, what: "note", open: () => link.click() }, { pinned: false });
      citationPeekState.panel?.setAttribute("aria-label", `Preview of ${link.textContent}`);
    }, keyboard ? 0 : 350);
  }

  //: The file's whole surface: what app.js's delegate calls.
  Object.assign(window, { wikiPeek });
})();
