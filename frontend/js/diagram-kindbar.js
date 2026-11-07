// diagram-kindbar.js: the kind of diagram, said at the top of the builder (INBOX 1679 m). Lazy: `LAZY_MODULES.diagramKindbar`,
// asked for by diagram-builder.js's `show` for every kind, and mounted by the flowchart toolbar (diagram-bar.js) and the other
// kinds' (diagram-kinds.js). One `.seg` well of worded buttons, Flowchart, Sequence, Mind map and Timeline, the chosen one pressed.
// Before this the other kinds were reachable only through Suggest's templates, so a sequence diagram was a thing nobody found.
// A press on another kind starts a new, empty diagram of it; a diagram with blocks in it is one Undo away (the document's own
// history), and the line says so. The front matter (title, theme) stays.
(() => {
  //: key, the word on the button, the header a new diagram starts with, what it is for (the button's title).
  const KINDS = [
    ["flowchart", "Flowchart", "flowchart TD", "Boxes and arrows: steps, decisions and groups"],
    ["sequence", "Sequence", "sequenceDiagram", "Who sends what to whom, in order: people, systems and messages"],
    ["mindmap", "Mind map", "mindmap", "One idea in the middle with branches"],
    ["timeline", "Timeline", "timeline", "Dates or periods in order, each with its events"],
  ];
  const NOUN = { flowchart: "flowchart", sequence: "sequence diagram", mindmap: "mind map", timeline: "timeline" };

  //: A new empty source of `to`, keeping the front matter of the one it replaces.
  const fresh = (source, to) => {
    const front = diagramModel.front(String(source || "").replace(/\r/g, ""));
    const header = KINDS.find(([key]) => key === to)[2];
    const lead = front.front.length ? `${front.front.join("\n")}\n` : "";
    return `${lead}${header}\n`;
  };

  function mount(S, h) {
    const here = S.k ? S.k.name : "flowchart";
    const seg = h.el("div", "seg dgm-kinds");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Kind of diagram");
    for (const [key, label, , about] of KINDS) {
      const button = smallButton(label, about, () => choose(S, h, here, key));
      button.dataset.kind = key;
      button.classList.toggle("active", key === here);
      button.setAttribute("aria-pressed", String(key === here));
      seg.append(button);
    }
    //: One tab stop for the four (arrows move between them), resting on the chosen kind: the dialog is 3 stops shorter to cross.
    wireToolbarRoving(seg);
    for (const button of seg.children) button.tabIndex = button.dataset.kind === here ? 0 : -1;
    S.root.prepend(seg);
  }

  function choose(S, h, here, to) {
    if (to === here) return;
    //: A source the blocks cannot read (a Gantt, say) is content, not blank: the Undo line must say so.
    const blank = !S.source.trim() || (S.plain ? false : S.k ? S.k.blank(S.m) : !S.m?.nodes.length && !S.m?.subgraphs.length && !S.m?.edges.length);
    diagramModel.builder.tell(blank ? `A new ${NOUN[to]}.` : `A new ${NOUN[to]}. Undo, Ctrl+Z, brings the ${NOUN[here]} back.`);
    S.io.set(fresh(S.source, to));
  }

  diagramModel.kindbar = { mount, fresh, KINDS };
})();
