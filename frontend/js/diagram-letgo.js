// diagram-letgo.js: a press off the diagram's elements lets go of the pick, for every kind (INBOX 1696, the owner: "I still
// cant clcik off diagram elements"). Lazy: `LAZY_MODULES.diagramLetGo`, registered at the foot of documents-mermaid.js and
// asked for by diagram-builder.js's `show` for every pane, after the canvas. Measured before (dgmoff sweep, 1440): a
// flowchart let go on empty picture space and Escape (diagram-canvas.js, 1661 h) but not on a press beside the picture; a
// sequence, mind map or timeline let go on none of the three. A kind gets the same `S.clear` the canvas gives a flowchart
// (the embed's Escape asks it first), and one document listener lets go on a press in the builder's page that lands on no
// block, control or picture: the picture's own handlers decide there (a node picks, empty space clears).
(() => {
  const live = new Set();
  const KEEP = ".dgm-block, .dgm-picture, .dock, button, a, input, label, select, textarea, [contenteditable], .action-menu, .help-popover, .menu-wrap";
  let on = false;

  function wire(S, h) {
    if (live.has(S)) return;
    live.add(S);
    if (!S.clear) {
      S.clear = () => {
        if (!S.sel && !S.picked?.size) return false;
        S.sel = null;
        S.picked?.clear();
        h.stops(S, S.tree.querySelector(".dgm-block"));
        return true;
      };
      S.fig.addEventListener("click", (event) => event.target.closest(".dock, .dgm-zoom, button, a") || S.clear());
      S.pane.addEventListener("click", (event) => event.target.closest(".dgm-block, button, a, input, label") || S.clear());
      S.root.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || event.defaultPrevented || event.target.closest?.("input, textarea, [contenteditable]") || document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden)")) return;
        if (S.clear()) event.preventDefault(), event.stopPropagation();
      });
    }
    if (on) return;
    on = true;
    document.addEventListener("click", (event) => {
      const at = event.target;
      if (event.button || !at?.closest || at.closest(KEEP)) return;
      for (const one of live) {
        if (!one.root.isConnected) live.delete(one);
        else if ((one.host.closest(".doc-preview, .modal-card") || one.host).contains(at) && !one.pane.contains(at)) one.clear();
      }
    });
  }

  diagramModel.letgo = { wire };
})();
