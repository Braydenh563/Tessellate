// diagram-steps.js: the empty diagram's walkthrough (INBOX 1615 f, 1679; DOCUMENTS_PLAN 22.1 and 22.4 R4). Lazy:
// `LAZY_MODULES.diagramSteps`, asked for by diagram-builder.js's `show` before the pane is made. Three numbered lines in
// place of the old title, each with its button: add a shape (a Box, whose name opens for typing at once), name it (the label
// editor opens on it), connect it (the picked block's handle is armed on the picture, so the next click is the target). The
// list stays, a tick on each step done, until the diagram has its first arrow (`sync`, called by the builder's `render`);
// steps 2 and 3 add the Box themselves when none is there yet, and every button does its step from a cold start.
// Under the list, "Start from an example" loads the current starter (R6.8: the walkthrough wins for a new diagram, and the
// starter is one press away); it and the template button go once there is a block.
(() => {
  //: `use` is the builder's own verbs: `add(S, options)` returns the new key, `rename(S, key)`, `connect(S, key)`.
  function build(S, use) {
    const list = use.el("ol", "dgm-steps");
    S.steps = list;
    const first = () => S.sel || use.add(S, { shape: "rect", edit: false });
    //: Step 3 arms the handle on the picture when it is showing (the next click is the target); the picker is the way where it is not.
    const connect = () => {
      const key = first();
      if (S.arm && S.fig?.offsetParent && key?.[0] === "n") S.arm(key.slice(2));
      else use.connect(S, key);
    };
    const steps = [
      ["Add a shape", "ph:plus Add a box", "Add a box to the diagram", () => use.add(S, { shape: "rect", edit: true })],
      ["Name it", "ph:pencil-simple Type a name", "Type the name of the first block", () => use.rename(S, first())],
      ["Connect it", "ph:arrow-bend-down-right Draw an arrow", "Start an arrow from the first block", connect],
    ];
    for (const [i, [words, label, title, run]] of steps.entries()) {
      const item = use.el("li", "dgm-step");
      item.append(use.el("span", "dgm-step-n", String(i + 1)), use.el("span", "dgm-step-text", words), smallButton(label, title, run));
      list.append(item);
    }
    const example = smallButton("ph:flow-arrow Start from an example", "Fill the diagram with a small flowchart to change", () => {
      S.m = diagramModel.parse(diagramModel.starter);
      use.commit(S, "Started from an example.");
    });
    example.classList.add("dgm-example");
    const both = document.createDocumentFragment();
    both.append(list, example);
    return both;
  }

  //: Key hints are for a keyboard; a touch screen is told what a tap does (R12).
  const PURPOSE = `Your blocks, in the order the chart flows. ${matchMedia("(pointer: coarse)").matches ? "Tap one to find it in the picture." : "Tab on the last adds a box. F6 leaves the blocks."}`;
  //: A touch screen has no double-click and often no Enter (dgbt-1109 3: the sheet said "Double-click" on a phone).
  const touch = () => matchMedia("(pointer: coarse)").matches;
  const LABEL_WORDS = () => (touch() ? "Double-tap the name to rename it." : "Double-click the name, or press Enter, to rename it.");

  //: The line under the list: what to do next with the blocks there are.
  function next(S) {
    const [two, how] = touch() ? ["Double-tap", ""] : ["Double-click", ", or press Enter,"];
    if (S.m.edges.length) return `Drag a grip to move or nest a block (the picture lays itself out). The arrow on a block, or Connect, draws an arrow from it. ${two} a name to rename it.`;
    return `${two} a name${how} to rename it. ${S.m.nodes.length < 2 ? "Add a second block, then press Connect to… on one." : "Press Connect to… on a block, or drag its grip onto another block, to draw an arrow."}`;
  }

  //: The pane's frame (1679 k): the purpose line above the list, and a foot under it with the two things a first use wants where the
  //: eye ends, Add block and Connect. Under the pointer or in focus, the line says what that control does (its own title, so a
  //: hover and a screen reader never disagree); it goes back to the purpose when the pointer or the focus leaves.
  //: The pane holds two things: `S.scroll` (the purpose line, the list, the hint: the part that scrolls) and the foot, outside it,
  //: so the foot never lies over a line and a short list leaves no gap under it (the owner, 2026-11-11: the sticky foot covered the hint while it scrolled).
  //: `use` is the builder's `add(S, options)` and `connect(S, key)`.
  function frame(S, use) {
    const line = document.createElement("p");
    line.className = "dgm-purpose muted";
    line.textContent = PURPOSE;
    const foot = document.createElement("div");
    foot.className = "dgm-foot";
    S.foot = foot;
    const add = smallButton("ph:plus Add block", "Add a block after the picked one", () => use.add(S, { edit: true }));
    const connect = smallButton("ph:arrow-bend-down-right Connect", "Draw an arrow from the picked block to another", () => use.connect(S, S.sel || S.tree.querySelector(".dgm-block")?.dataset.key));
    //: Mouse and touch twins of N, C and the toolbar's Add: not Tab stops, so the picture is near (DD-8).
    add.tabIndex = connect.tabIndex = -1;
    foot.append(add, connect);
    S.footConnect = connect;
    S.scroll = document.createElement("div");
    S.scroll.className = "dgm-scroll";
    S.scroll.append(...S.pane.childNodes);
    S.pane.classList.add("dgm-framed");
    S.pane.append(S.scroll, foot);
    S.tree.before(line);
    const say = (target) => {
      const control = target?.closest?.(".dgm-label, [title]");
      const words = control?.classList.contains("dgm-label") ? LABEL_WORDS() : control?.title;
      line.textContent = words || PURPOSE;
      line.classList.toggle("dgm-purpose-live", Boolean(words));
    };
    for (const [on, off] of [["pointerover", "pointerleave"], ["focusin", "focusout"]]) {
      S.pane.addEventListener(on, (event) => say(event.target));
      S.pane.addEventListener(off, () => say(null));
    }
  }

  //: Called by every render: the list shows until the first arrow, each done step ticked; the example and the template button go with the first block.
  function sync(S, blocks) {
    const m = S.m;
    //: The checklist is a lesson for the first two boxes (DD-10, 1107): with two it has taught the box and the name, and the foot's Connect
    //: is the one next action, so the list and its empty frame go rather than stay as a ticked record to the first arrow.
    const lesson = m.edges.length === 0 && m.nodes.length < 2;
    S.empty.classList.toggle("hidden", !lesson);
    S.foot?.classList.toggle("hidden", !blocks);
    //: The checklist already offers the first arrow and the first box, so the foot does not say the same twice (1679 blind pass): Add block
    //: stays where the eye ends, Connect joins it once the checklist has gone, and a box that is added drops the checklist's first row.
    S.footConnect?.classList.toggle("hidden", lesson && Boolean(S.steps));
    S.steps?.firstElementChild?.classList.toggle("hidden", m.nodes.length > 0);
    S.empty.classList.toggle("dgm-started", Boolean(blocks));
    //: A phone with an arrow keeps the picture and gets the list as a sheet (diagram-touch.js); before that the steps stay in the page.
    S.root.classList.toggle("dgm-listless", m.edges.length > 0);
    const done = [m.nodes.length > 0, m.nodes.some((n) => n.text !== diagramModel.ops.TEXT[n.shape] /* the name a new block is given: "Name it" is done once one has another */), m.edges.length > 0];
    S.steps?.querySelectorAll(".dgm-step").forEach((item, i) => {
      if (item.classList.contains("dgm-done") === done[i]) return;
      item.classList.toggle("dgm-done", done[i]);
      const tick = Object.assign(document.createElement("i"), { className: "ph ph-check" });
      tick.setAttribute("role", "img");
      tick.setAttribute("aria-label", "Done");
      item.firstElementChild.replaceChildren(done[i] ? tick : String(i + 1));
    });
  }

  diagramModel.steps = { build, sync, frame, next };
})();
