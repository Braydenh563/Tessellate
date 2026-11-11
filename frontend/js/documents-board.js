// documents-board.js: a board embed edited from the document (DOCUMENTS_PLAN 26, gap row 10). `![[board:12]]` draws the board's
// card; its "Edit here" opens the board in a dialog over the document, with the whiteboard's own toolbar; the dialog's X closes it.
// The whiteboard is one page-wide instance (one `wbState`, one `#whiteboard-container`, ids everywhere), so this does not make a
// second one: it lends the Library's `#library-view-whiteboard` to the panel and puts it back on close. Whiteboard side, small
// hooks: `openWhiteboardBoard(id, { stay: true })` does not switch to the Library (`restore: true` puts the board's remembered camera
// back), `wbShowBoardsLanding` first offers a cancelable `wb-leave` event, which this file answers by closing the panel (the board's
// own "Boards" button is hidden, the dialog's X takes its place), and `wbShowBoardsLanding.wantsEscape()` says whether the board
// still has a use for an Escape. Closing leaves the Library as it was: its board open again, or its list.
// Lazy: `LAZY_MODULES.docBoard`; documents-embeds.js draws the button and asks for this file on the first press. It adds no global name.
(() => {
  let open = null;

  //: Put the whiteboard view back where the Library keeps it, and the Library as it was: the board it had open is loaded again
  //: (with the camera it had), or the board list is shown when it was on the list.
  async function close() {
    const was = open;
    if (!was) return;
    open = null;
    await window.wbCancelBoardTimers?.();
    window.wbLeaveFullscreen?.();
    if (was.libraryBoard != null) {
      //: Loaded while the view is still in the dialog, unseen (a hidden Library has no size to frame by): the camera is restored, not framed.
      was.overlay.classList.add("doc-board-closing");
      await window.openWhiteboardBoard(was.libraryBoard, { stay: true, restore: true });
    } else {
      window.wbShowBoardsLanding?.();
    }
    was.view.classList.toggle("hidden", was.hidden);
    was.home.insertBefore(was.view, was.next);
    was.overlay.remove();
    window.dispatchEvent(new Event("resize"));
    //: The card's picture is from the board index, which the edit has outdated.
    await window.loadMapBoardIndex?.(true);
    document.dispatchEvent(new CustomEvent("board-edited", { detail: { id: was.id } }));
    //: The redraw above may have replaced the button that opened the panel: the same board's button at the same place gets the focus.
    setTimeout(() => {
      const same = [...document.querySelectorAll(`.doc-embed-board-edit[data-board-id="${was.id}"]`)];
      (was.opener?.isConnected ? was.opener : same[was.nth] || same[0])?.focus();
    }, 0);
  }

  async function show(id, title, opener) {
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
    //: What the Library has open now, so closing leaves it so: the board on its canvas, or none (the list).
    const canvas = document.getElementById("wb-canvas-view");
    const libraryBoard = canvas && !canvas.classList.contains("hidden") && window.currentBoardId != null ? window.currentBoardId : null;
    const nth = [...document.querySelectorAll(`.doc-embed-board-edit[data-board-id="${id}"]`)].indexOf(opener);
    open = { id, view, overlay, opener, nth, libraryBoard, home: view.parentElement, next: view.nextSibling, hidden: view.classList.contains("hidden") };
    card.append(view);
    view.classList.remove("hidden");
    await window.openWhiteboardBoard(id, { stay: true });
    card.querySelector('.dialog-head-actions button[aria-label="Close"]')?.focus();
  }

  //: **Escape is the board's first, the panel's next.** A menu, a selection, a tool, a find bar, a text being typed or full screen
  //: each take an Escape; the one that finds none of them closes the panel. The board's state is read before its own handlers run
  //: (capture), because a handler that clears a selection does not say it did.
  let boardTookEscape = false;
  function boardWantsEscape(event) {
    const { view } = open;
    if (view.classList.contains("wb-fullscreen") || view.classList.contains("wb-presenting")) return true;
    if (document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden), .wb-ctx-menu:not(.hidden), .wb-map-radial:not(.hidden)")) return true;
    if (event.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return true;
    return Boolean(window.wbShowBoardsLanding?.wantsEscape?.());
  }
  document.addEventListener("keydown", (event) => {
    if (open && event.key === "Escape") boardTookEscape = boardWantsEscape(event);
  }, true);
  //: On `window`, after every `document` handler: one that took the key has stopped it or prevented it.
  window.addEventListener("keydown", (event) => {
    if (!open || event.key !== "Escape" || boardTookEscape || event.defaultPrevented) return;
    if (activeOverlay() !== open.overlay) return;
    event.preventDefault();
    close();
  });

  document.addEventListener("board-edit", (event) => show(event.detail.id, event.detail.title, event.target));
  //: The board's own "Boards" button, the phone shell's back and a space switch all end up here; with the panel open they close it.
  document.addEventListener("wb-leave", (event) => {
    if (!open) return;
    event.preventDefault();
    close();
  });
})();
