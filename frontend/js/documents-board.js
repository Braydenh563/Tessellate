// documents-board.js: a board embed edited from the document (DOCUMENTS_PLAN 26, gap row 10). `![[board:12]]` draws the board's
// card; its "Edit here" opens the board in a dialog over the document, with the whiteboard's own toolbar; the dialog's X closes it.
// The whiteboard is one page-wide instance (one `wbState`, one `#whiteboard-container`, ids everywhere), so this does not make a
// second one: it lends the Library's `#library-view-whiteboard` to the panel and puts it back on close. Whiteboard side, two
// hooks: `openWhiteboardBoard(id, { stay: true })` does not switch to the Library, and `wbShowBoardsLanding` first offers a
// cancelable `wb-leave` event, which this file answers by closing the panel (the board's own "Boards" button is hidden, the dialog's X takes its place).
// Lazy: `LAZY_MODULES.docBoard`; documents-embeds.js draws the button and asks for this file on the first press. It adds no global name.
(() => {
  let open = null;

  //: Put the whiteboard view back where the Library keeps it, and leave it on the board list, as the Library expects it.
  async function close() {
    const was = open;
    if (!was) return;
    open = null;
    await window.wbCancelBoardTimers?.();
    window.wbShowBoardsLanding?.();
    was.view.classList.toggle("hidden", was.hidden);
    was.home.insertBefore(was.view, was.next);
    was.overlay.remove();
    //: The card's picture is from the board index, which the edit has outdated.
    await window.loadMapBoardIndex?.(true);
    document.dispatchEvent(new CustomEvent("board-edited", { detail: { id: was.id } }));
  }

  async function show(id, title) {
    if (open) return;
    const view = document.getElementById("library-view-whiteboard");
    if (!view) return;
    //: The overlay recipe (`dialogHead`, then `panelMovable` by its head), as the diagram builder's dialog is built.
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay doc-board-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", `Board: ${title || "Untitled"}`);
    const card = document.createElement("div");
    card.className = "card modal-card space-dialog doc-board-card";
    card.append(dialogHead(title || "Untitled board", close));
    overlay.append(card);
    document.body.append(overlay);
    open = { id, view, overlay, home: view.parentElement, next: view.nextSibling, hidden: view.classList.contains("hidden") };
    card.append(view);
    view.classList.remove("hidden");
    await window.openWhiteboardBoard(id, { stay: true });
    card.querySelector('.dialog-head-actions button[aria-label="Close"]')?.focus();
  }

  document.addEventListener("board-edit", (event) => show(event.detail.id, event.detail.title));
  //: The board's own "Boards" button, the phone shell's back and a space switch all end up here; with the panel open they close it.
  document.addEventListener("wb-leave", (event) => {
    if (!open) return;
    event.preventDefault();
    close();
  });
})();
