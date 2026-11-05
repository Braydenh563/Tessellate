// diagram-steps.js: the empty diagram's walkthrough (INBOX 1615 f, 1679; DOCUMENTS_PLAN 22.1 and 22.4 R4). Lazy:
// `LAZY_MODULES.diagramSteps`, asked for by diagram-builder.js's `show` before the pane is made. Three numbered lines in
// place of the old title, each with its button: add a shape (a Box, whose name opens for typing at once), name it (the label
// editor opens on it), connect it (the picked block's handle is armed on the picture, so the next click is the target). The
// list stays, a tick on each step done, until the diagram has its first arrow (`sync`, called by the builder's `render`);
// steps 2 and 3 add the Box themselves when none is there yet, and every button does its step from a cold start.
// Under the list, "Start from an example" loads the current starter (R6.8: the walkthrough wins for a new diagram, and the
// starter is one press away); it and the template button go once there is a block.
(() => {
  //: The name a new block is given by shape (the builder's SHAPE_TEXT), so "Name it" is done when one block has another.
  const DEFAULT_NAMES = { rect: "Step", round: "Step", stadium: "Start", circle: "Event", diamond: "Question?", hexagon: "Prepare" };

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

  const PURPOSE = "Your blocks, in the order the chart flows. Pick one to find it in the picture.";
  const LABEL_WORDS = "Double-click the name, or press Enter, to rename it.";

  //: The pane's frame (1679 k): the purpose line above the list, and a foot under it with the two things a first use wants where the
  //: eye ends, Add block and Connect. Under the pointer or in focus, the line says what that control does (its own title, so a
  //: hover and a screen reader never disagree); it goes back to the purpose when the pointer or the focus leaves.
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
    foot.append(add, connect);
    S.tree.before(line);
    S.tree.after(foot);
    const say = (target) => {
      const control = target?.closest?.(".dgm-label, [title]");
      const words = control?.classList.contains("dgm-label") ? LABEL_WORDS : control?.title;
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
    S.empty.classList.toggle("hidden", m.edges.length > 0);
    S.foot?.classList.toggle("hidden", !blocks);
    S.empty.classList.toggle("dgm-started", Boolean(blocks));
    //: A phone with an arrow keeps the picture and gets the list as a sheet (diagram-touch.js); before that the steps stay in the page.
    S.root.classList.toggle("dgm-listless", m.edges.length > 0);
    const done = [m.nodes.length > 0, m.nodes.some((n) => n.text !== DEFAULT_NAMES[n.shape]), m.edges.length > 0];
    S.steps?.querySelectorAll(".dgm-step").forEach((item, i) => {
      if (item.classList.contains("dgm-done") === done[i]) return;
      item.classList.toggle("dgm-done", done[i]);
      const tick = Object.assign(document.createElement("i"), { className: "ph ph-check" });
      tick.setAttribute("role", "img");
      tick.setAttribute("aria-label", "Done");
      item.firstElementChild.replaceChildren(done[i] ? tick : String(i + 1));
    });
  }

  diagramModel.steps = { build, sync, frame };
})();
