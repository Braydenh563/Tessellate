// board-embed.js: what a `![[board]]` card in a note draws (`boardEmbedFill`):
// the board's preview, or the tombstone once a forced look has not found it.
// Moved out of markdown.js on 2026-11-14 for the boot gzip budget
// (tests/test_static_compression.py); `boardEmbedElement` (markdown.js) waits
// for the bundle `boardEmbed` (lazy-entries.js) before its first fill.

function boardEmbedFill(box, ref, final) {
  const board = boardEmbedTarget(ref);
  box.replaceChildren();
  box.classList.toggle("board-embed-gone", !board && final);

  if (!board && !final) {
    //: **Not the tombstone.** "We have not looked yet" and "it is gone" are
    //: different facts, and printing the second while the first is true is
    //: how a working board gets reported as deleted.
    const waiting = document.createElement("p");
    waiting.className = "note-embed-head";
    setLabel(waiting, `${ref.map ? "ph:tree-structure" : "ph:squares-four"} ${ref.title || "Loading\u2026"}`);
    box.appendChild(waiting);
    return null;
  }

  if (!board) {
    //: **A tombstone, not a disappearance** (the decision recorded in
    //: DOCUMENTS_PLAN's "Decisions made"). A board deleted after it was put
    //: in a note would otherwise take a paragraph of that note with it, and
    //: the reader would never learn that anything had been there: content
    //: that vanishes silently is worse than content that says it is gone.
    //: The title the reference carries is exactly what makes this sentence
    //: worth reading.
    const head = document.createElement("p");
    head.className = "note-embed-head";
    setLabel(head, "ph:trash Removed");
    const what = document.createElement("p");
    what.className = "board-embed-title";
    what.textContent = ref.title || (ref.map ? "A mind map" : "A whiteboard");
    const why = document.createElement("p");
    why.className = "library-file-meta board-embed-meta";
    why.textContent = "This board is no longer in your notebook.";
    box.append(head, what, why);
    return null;
  }

  const isMap = board.type !== "board";
  const title = board.title || ref.title || (isMap ? "Untitled map" : "Untitled board");
  const open = document.createElement("button");
  open.type = "button";
  open.className = "board-embed-open";
  open.title = `Open \u201c${title}\u201d`;

  const head = document.createElement("span");
  head.className = "note-embed-head";
  setLabel(head, `${isMap ? "ph:tree-structure" : "ph:squares-four"} ${isMap ? "Mind map" : "Whiteboard"}`);

  const body = document.createElement("span");
  body.className = "board-embed-body";
  const picture = mapPreview(board, { size: "card" });
  picture.classList.add("board-embed-picture");
  const text = document.createElement("span");
  text.className = "board-embed-text";
  const name = document.createElement("span");
  name.className = "board-embed-title";
  name.textContent = title;
  //: The facts line recipe (DESIGN.md), the same sentence the Library card
  //: and the dashboard row carry under the same picture.
  const meta = document.createElement("span");
  meta.className = "library-file-meta board-embed-meta";
  meta.textContent = mapCountLabel(board);
  text.append(name, meta);
  body.append(picture, text);
  open.append(head, body);
  open.addEventListener("click", (event) => {
    //: The note card underneath is itself clickable (it expands), so a press
    //: meant for the board must not also open the note.
    event.stopPropagation();
    openWhiteboardBoard(board.id);
  });
  box.appendChild(open);
  return board;
}
