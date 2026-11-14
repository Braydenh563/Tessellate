// diagram-kindbar.js: the kind of diagram, said at the top of the builder (INBOX 1679 m). Lazy: `LAZY_MODULES.diagramKindbar`,
// asked for by diagram-builder.js's `show` for every kind, and mounted by the flowchart toolbar (diagram-bar.js) and the other
// kinds' (diagram-kinds.js). One Kind button in the dialog's Title row (first in the toolbar where there is none) opens a menu
// of the four kinds, each with a small drawn sample and a line on what it makes (1661 k: a row of four words said nothing of
// what they did, and took a row of its own). Before 1679 m the other kinds were reachable only through Suggest's templates.
// A press on another kind starts a new, empty diagram of it; a diagram with blocks in it is one Undo away (the document's own
// history), and the line says so. The front matter (title, theme) stays.
(() => {
  //: key, the word on the button, the header a new diagram starts with, what it is for (the button's title).
  const KINDS = [
    ["flowchart", "Flowchart", "flowchart TD", "Boxes and arrows: steps, decisions and groups"],
    ["sequence", "Sequence", "sequenceDiagram", "Who sends what to whom, in order"],
    ["mindmap", "Mind map", "mindmap", "One idea in the middle with branches"],
    ["timeline", "Timeline", "timeline", "Dates or periods in order, with their events"],
    ["gantt", "Gantt", "gantt", "Tasks on a calendar, in sections"],
    ["pie", "Pie", "pie", "Slices of a whole, by number"],
    ["state", "State", "stateDiagram-v2", "States and the moves between them"],
    ["class", "Class", "classDiagram", "Classes, their members and relations"],
    ["er", "ER", "erDiagram", "Entities, their attributes and relationships"],
  ];
  const NOUN = { flowchart: "flowchart", sequence: "sequence diagram", mindmap: "mind map", timeline: "timeline", gantt: "Gantt chart", pie: "pie chart", state: "state diagram", class: "class diagram", er: "ER diagram" };
  //: The five newest kinds open on a small example, so the picture is there to read and change (an empty one draws nothing).
  const STARTERS = {
    gantt: "gantt\n    title Plan\n    dateFormat YYYY-MM-DD\n    section Work\n    First task :a1, 2026-01-05, 3d\n    Second task :after a1, 4d\n",
    pie: 'pie title Share\n    "Slice A" : 60\n    "Slice B" : 40\n',
    state: "stateDiagram-v2\n    [*] --> Idle\n    Idle --> Busy : start\n    Busy --> Idle : done\n    Busy --> [*]\n",
    class: "classDiagram\n    class Animal {\n        +String name\n        +eat()\n    }\n    class Dog\n    Animal <|-- Dog\n",
    er: "erDiagram\n    CUSTOMER ||--o{ ORDER : places\n    CUSTOMER {\n        string name\n    }\n",
  };

  //: A new empty source of `to`, keeping the front matter of the one it replaces.
  const fresh = (source, to) => {
    const front = diagramModel.front(String(source || "").replace(/\r/g, ""));
    const header = KINDS.find(([key]) => key === to)[2];
    const lead = front.front.length ? `${front.front.join("\n")}\n` : "";
    return `${lead}${STARTERS[to] || `${header}\n`}`;
  };

  //: The kind just pressed: the pane is drawn again and the bar with it, so the new bar takes the focus the old one lost.
  let pending = "";

  //: A kind drawn small: one path of strokes in a 40 by 28 box, the picture the menu row and the button show.
  const SAMPLE = {
    flowchart: "M3 3h14v8H3zM23 17h14v8H23zM10 11v10h10M17 18l3 3-3 3",
    sequence: "M3 2h12v6H3zM25 2h12v6H25zM9 8v18M31 8v18M9 15h21M27 12l3 3-3 3M31 21H10",
    mindmap: "M14 14a6 4 0 1 0 12 0a6 4 0 1 0-12 0M14 14H4M26 14h10M16 11 8 4M24 17l8 7M24 11l8-7",
    timeline: "M2 14h36M8 10v8M20 10v8M32 10v8M4 5h8M16 23h8M28 5h8",
    gantt: "M3 4h14v5H3zM12 12h18v5H12zM22 20h15v5H22zM2 2v24",
    pie: "M20 3a11 11 0 1 0 11 11H20zM24 3a11 11 0 0 1 7 7h-7z",
    state: "M3 14a3 3 0 1 0 6 0a3 3 0 1 0-6 0M15 6h12v8H15zM21 14v8M25 22h12v4H25zM9 14h6",
    class: "M4 3h14v22H4zM4 9h14M4 16h14M26 8h12v12H26zM18 12h8",
    er: "M3 6h12v8H3zM25 14h12v8H25zM15 10h5v8h5M3 9h12",
  };
  function sample(key) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 40 28");
    svg.setAttribute("class", "dgm-kindpic");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", SAMPLE[key]);
    svg.append(path);
    return svg;
  }

  //: Blank: nothing would be lost by a new kind. A source the blocks cannot read (a Gantt, say) is content, not blank.
  const blankOf = (S) => !S.source.trim() || (S.plain ? false : S.k ? S.k.blank(S.m) : !S.m?.nodes.length && !S.m?.subgraphs.length && !S.m?.edges.length);

  //: `dock` is the toolbar, passed by diagram-bar.js before it is in the pane.
  function mount(S, h, dock = S.root.querySelector(".dgm-dock")) {
    const here = S.k ? S.k.name : "flowchart";
    const label = KINDS.find(([key]) => key === here)[1];
    const button = h.el("button", "ghost small dgm-kindbtn");
    button.type = "button";
    button.title = "Choose the kind of diagram";
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", `Kind of diagram: ${label}. Choose a kind`);
    const caret = h.el("i", "ph ph-caret-down");
    caret.setAttribute("aria-hidden", "true");
    button.append(sample(here), h.el("span", "dgm-kindword", label), caret);
    button.addEventListener("click", () => open(S, h, here, button));
    //: The Title row outlives the pane (a new kind draws the pane again), so the button it held is replaced, not added to.
    const row = S.host.closest(".dgm-dialog")?.querySelector(".dgm-titlebar");
    if (row) {
      row.querySelectorAll(":scope > :is(.dgm-kindbtn, .dgm-kindlabel)").forEach((old) => old.remove());
      const word = h.el("span", "muted dgm-kindlabel", "Kind");
      word.setAttribute("aria-hidden", "true");
      //: The row is a <label> for the title field, so a press on this word would land in that field.
      word.addEventListener("click", (event) => (event.preventDefault(), button.click()));
      row.append(word, button);
    } else dock?.prepend(button, h.el("div", "dock-group"));
    //: After a tick: the bar is not in the page yet while it is being built.
    if (pending === here) setTimeout(() => button.focus(), 0);
    pending = "";
  }

  function open(S, h, here, button) {
    //: A second press closes it (the owner 2026-11-09): the outside-press closer skips an expanded opener, so it is closed here.
    if (button.getAttribute("aria-expanded") === "true") return closeActionMenus();
    const r = button.getBoundingClientRect();
    //: Held, not looked up by its host: the menu can be moved out of it (the shelf's caret menu was).
    //: Anchored at the button's right edge, as the shelf caret is: the menu's end lines up under the button (it opened 660 px to its left).
    const menu = openMenuAtPoint(KINDS.map(([key, label]) => ({ label, run: () => choose(S, h, here, key) })), "Kinds of diagram", r.right, r.bottom, button);
    if (!menu) return;
    decorate(menu, here, blankOf(S));
    //: The closer resets this button, not the menu's hidden anchor.
    menu._escapedOpener = button;
    button.setAttribute("aria-expanded", "true");
  }

  //: Each row is its sample, its word and what it makes; the chosen one is marked; the line under them says what a change costs.
  function decorate(menu, here, blank) {
    menu.classList.add("dgm-kindmenu");
    [...menu.querySelectorAll(":scope > .menu-item")].forEach((row, i) => {
      const [key, label, , about] = KINDS[i];
      const text = document.createElement("span");
      text.className = "dgm-kindtext";
      const word = document.createElement("span");
      word.textContent = label;
      const line = document.createElement("span");
      line.className = "muted dgm-kind-about";
      line.textContent = about;
      text.append(word, line);
      row.removeAttribute("title");
      row.classList.toggle("active", key === here);
      if (key === here) row.setAttribute("aria-current", "true");
      row.replaceChildren(sample(key), text);
    });
    if (blank) return;
    const note = document.createElement("p");
    note.className = "muted dgm-kindnote";
    note.textContent = "A new kind starts empty. Undo brings this one back.";
    menu.append(note);
  }

  //: The three-box starter a new diagram opens on (documents-mermaid.js), as it was given or as printed: nothing in it was written by the person (dgbt-1109 8).
  const untouched = (S) => !S.plain && !S.k && [diagramModel.starter, diagramModel.print(diagramModel.parse(diagramModel.starter))].includes(S.source.trim());

  //: What a change would clear, in words: "The 3 boxes", "The 5 blocks", "The diagram" (a source the blocks cannot read).
  function lost(S, here) {
    if (S.plain) return "The diagram";
    const n = here === "flowchart" ? S.m?.nodes.length || 0 : S.root.querySelectorAll(".dgm-block").length;
    if (!n) return "The diagram";
    const noun = here === "flowchart" ? (n === 1 ? "box" : "boxes") : n === 1 ? "block" : "blocks";
    return `The ${n} ${noun}`;
  }

  //: A diagram with content is not swapped silently (blind test 1108: 3 cards went to 0 and only Undo knew). The person is
  //: asked first, in the app's confirm; a blank one switches at once.
  async function choose(S, h, here, to) {
    if (to === here) return;
    const blank = blankOf(S) || untouched(S);
    if (!blank) {
      const ok = await confirmDialog(`Switch to ${NOUN[to]}?\n\n${lost(S, here)} will be cleared. Undo, Ctrl+Z, brings the ${NOUN[here]} back.`, { confirmLabel: "Switch", cancelLabel: `Keep ${NOUN[here]}`, danger: false });
      if (!ok) return;
    }
    diagramModel.builder.tell(blank ? `A new ${NOUN[to]}.` : `A new ${NOUN[to]}. Undo, Ctrl+Z, brings the ${NOUN[here]} back.`);
    pending = to;
    S.io.set(fresh(S.source, to));
  }


  //: Ctrl+Z and Ctrl+Y anywhere inside the builder (a tile, the picture, the toolbar) are the builder's: the app's undo listens on the
  //: document and would run a second step, even bin the document ("Undone: Created"). A text field keeps the browser's own.
  //: Lives here, not in diagram-bar.js: that loads for flowcharts only, and a sequence .mmd opened first threw on every keydown (review 1108).
  function historyKey(S, event) {
    const t = event.target;
    if (event.altKey || !(event.ctrlKey || event.metaKey) || !/^[zy]$/i.test(event.key) || t.isContentEditable || t.closest?.("input, textarea, select")) return;
    event.preventDefault();
    event.stopPropagation();
    return event.shiftKey || /y/i.test(event.key) ? S.io.redo() : S.io.undo();
  }

  
  //: The toolbar's Expand (a diagram in a document opens in the full screen builder) or, in that builder, its Collapse; the same
  //: place and the same arrows. Neither where the builder is already a dialog of its own (a board's, the door's). Both toolbars add it.
  function expand(S) {
    const out = !S.io.dialog;
    if (!out && !S.io.collapse) return null;
    const button = smallButton(out ? "ph:arrows-out" : "ph:arrows-in", out ? "Expand to the full screen builder" : "Back to the document (Escape)", () =>
      out ? ensureModule("diagramEmbed").then((ok) => (ok ? diagramModel.embed.expand(S) : toast("The full screen builder did not load. Try again.", "info"))) : S.io.collapse()
    );
    button.setAttribute("aria-label", out ? "Expand" : "Collapse");
    button.classList.add("dgm-expand", "icon-only");
    return button;
  }

  //: The ... menu's rows for a narrow phone (L-documents-7): 480 px or less, Direction, Redo and Ask leave the dock (diagram-lazy.css).
  //: 360 px or less, the dock drops the kind button's caret and its side padding to stay one row at 320.
  const COMPACT = "(max-width: 599.98px), (pointer: coarse)";

  function fold(S, DIRS, suggestMenu) {
    const narrow = matchMedia("(max-width: 480px)").matches;
    S.root.classList.toggle("dgm-narrow", narrow);
    S.root.classList.toggle("dgm-tight", matchMedia("(max-width: 360px)").matches);
    const ask = narrow && S.pane && (S.steps || S.k) && S.pane.querySelector(".dgm-ai-form");
    const more = () => S.root.querySelector(".dgm-more button");
    const rows = [];
    if (S.suggestBtn && matchMedia(COMPACT).matches) rows.push({ label: "ph:sparkle Suggest…", group: "edit", run: () => suggestMenu(S, more() || S.suggestBtn) });
    if (narrow) {
      if (S.dirs) rows.push({ label: "ph:arrows-out-cardinal Direction…", group: "edit", run: () => { const r = (more() || S.root).getBoundingClientRect(); openMenuAtPoint(DIRS.map(([d, icon, name]) => ({ label: `${icon} ${name}`, run: () => S.turn(d) })), "Direction", r.right, r.bottom, more()); } });
      rows.push({ label: "ph:arrow-clockwise Redo", group: "edit", run: () => S.io.redo() });
      if (ask) rows.push({ label: "ph:sparkle Ask for a change…", group: "edit", run: () => S.root.querySelector(".dgm-askbtn")?.click() });
    }
    return { rows, key: (S.io.menu || []).map((row) => row.label).join("|") + (ask ? "|ask" : "") };
  }

  diagramModel.kindbar = { mount, fresh, historyKey, expand, fold, KINDS, SAMPLE };
})();
