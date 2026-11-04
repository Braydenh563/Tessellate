// diagram-steps.js: the empty diagram's walkthrough (INBOX 1615 f, DOCUMENTS_PLAN 22.1 and 22.4 R4). Lazy:
// `LAZY_MODULES.diagramSteps`, asked for by diagram-builder.js's `show` before the pane is made. Three numbered lines in
// place of the old title, each with its button: add a shape (a Box), name it (the label editor opens on it), connect
// it (a connection starts from it). The pane hides the whole list once the diagram has a block (`render`), so steps 2
// and 3 add the Box themselves when none is there yet, and every button does its step from a cold start.
// Under the list, "Start from an example" loads the current starter (R6.8: the walkthrough wins for a new diagram, and the
// starter is one press away).
(() => {
  //: `use` is the builder's own verbs: `add(S, options)` returns the new key, `rename(S, key)`, `connect(S, key)`.
  function build(S, use) {
    const list = use.el("ol", "dgm-steps");
    const first = () => S.sel || use.add(S, { shape: "rect", edit: false });
    const steps = [
      ["Add a shape", "ph:plus Add a Box", "Add a Box to the diagram", () => use.add(S, { shape: "rect", edit: false })],
      ["Name it", "ph:pencil-simple Type a name", "Type the name of the first block", () => use.rename(S, first())],
      ["Connect it", "ph:arrow-bend-down-right Draw an arrow", "Start an arrow from the first block", () => use.connect(S, first())],
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

  diagramModel.steps = { build };
})();
