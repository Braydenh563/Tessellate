// diagram-touch.js: the block pane on a phone (1546 P2 leftovers). Lazy: `LAZY_MODULES.diagramTouch`,
// asked for by diagram-builder.js's `show` on a narrow window or a touch screen, so a desktop never loads it.
//
// One thing: the palette becomes one "Add" button that opens a sheet of the shapes (the tiles stay in the
// page, hidden, and the sheet presses them, so there is one way a block is added). The picture's pinch, pan
// and fit are diagram-view.js's now (1614), for every window.
(() => {
  const COMPACT = "(max-width: 599.98px), (pointer: coarse)";
  //: The sheet: the Add library's groups (diagram-library.js), a heading each, then a row per tile with the tile's own glyph,
  //: its name and its hint (1594). A tile is pressed, so its handler adds the block.
  function addSheet(root, opener) {
    const groups = [...root.querySelectorAll(".dgm-palette .dgm-lib-group")];
    openSheet({
      label: "Add a block",
      name: "diagram-add",
      returnFocus: opener,
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list dgm-add-list";
        for (const group of groups) {
          const head = document.createElement("p");
          head.className = "dgm-add-head muted";
          head.textContent = group.querySelector(".dgm-lib-head").textContent;
          list.append(head);
          for (const tile of group.querySelectorAll(".dgm-tile")) {
            const row = sheetRow("ph ph-square", tile.querySelector(".dgm-tile-name").textContent, () => {
              close();
              tile.click();
            });
            //: Every glyph in a slot of one width, so the names start at the same x (R6.11: 57, 54 and 56 px before).
            const slot = document.createElement("span");
            slot.className = "dgm-add-glyph";
            //: The glyph by what it is, not by its place: a tile that lost its glyph printed its name here.
            slot.append(tile.querySelector(":scope > :not(.dgm-tile-name)").cloneNode(true));
            row.firstElementChild.replaceWith(slot);
            const hint = document.createElement("small");
            hint.className = "dgm-add-hint muted";
            hint.textContent = tile.dataset.hint;
            row.lastElementChild.append(hint);
            list.append(row);
          }
        }
        card.append(list);
      },
    });
  }

  //: The blocks list on a phone (1679, slice 11): the pane moves into a sheet and home again, so the picture keeps the page once the diagram has an arrow.
  function listSheet(S, opener) {
    const home = S.pane.parentElement;
    const before = S.pane.nextSibling;
    openSheet({
      label: "Blocks",
      name: "diagram-blocks",
      returnFocus: opener,
      build: (card) => card.append(S.pane),
      onClose: () => home.insertBefore(S.pane, before),
    });
  }

  //: Wires one pane, once. `root` is `.dgm`, `fig` the picture; the kinds' panes have the same two.
  function wire(S) {
    if (!S?.root || S.root.dataset.touch) return;
    S.root.dataset.touch = "1";
    //: Wide, a kind's dock only swaps its palette for the Add sheet (`dgm-addlist`); the rest of `dgm-compact` is the phone's.
    S.root.classList.add(matchMedia(COMPACT).matches ? "dgm-compact" : "dgm-addlist");
    const actions = S.root.querySelector(".dgm-dock .dock-actions");
    //: The flowchart's toolbar has its own Add split (diagram-bar.js); the kinds' palettes also open this sheet.
    //: A kind's list is the same sheet once it has a block (1661 m: its list stacked under a 96 px picture at 390;
    //: diagram-kinds.js `sync` says when, with `dgm-listless`).
    if ((S.steps || S.k) && S.pane && actions && matchMedia("(max-width: 599.98px)").matches) {
      const list = smallButton("ph:list-bullets", "Blocks list", () => listSheet(S, list));
      list.classList.add("dgm-listbtn");
      list.setAttribute("aria-haspopup", "dialog");
      actions.prepend(list);
      S.root.classList.add("dgm-phonelist");
      //: Ask sat only inside the Blocks sheet (dgai-1110 left): its own button opens that sheet with the question box in hand.
      if (S.pane.querySelector(".dgm-ai-form")) {
        const ask = smallButton("ph:sparkle", "Ask for a change", () => (listSheet(S, ask), S.pane.querySelector(".dgm-ai-form input")?.focus()));
        ask.classList.add("dgm-askbtn");
        ask.setAttribute("aria-haspopup", "dialog");
        list.after(ask);
      }
    }
    if (actions && !S.root.querySelector(".dgm-addsplit")) {
      const add = smallButton("ph:plus Add", "Choose a shape to add as a block (N, or ? for every key)", () => addSheet(S.root, add), false);
      add.classList.add("dgm-add");
      add.setAttribute("aria-haspopup", "dialog");
      actions.prepend(add);
    }
  }

  diagramModel.touch = { wire };
})();
