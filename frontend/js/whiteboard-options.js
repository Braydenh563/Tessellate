(() => {
  // whiteboard-options.js: the board's own options in the Format panel's Board section (WHITEBOARD_PLAN,
  // wbformat2). Each is kept on the board in its `background` settings (`wbSetBackground`), so it syncs, is in
  // a backup, and is undone like the board's colour: grid spacing and colour, alignment guides, page view,
  // the shadow new shapes start with, paper size and orientation, and the units the position and size fields
  // show. Nothing here is a global: the board reads it through `wbFmtState.opts`, which `wbApplyBackground` calls
  // (`sync`) whenever the board's settings load or change.
  const $ = (id) => document.getElementById(id);
  const DEFAULT_GRID = 24;

  //: Paint the controls from the board's settings; a field being typed in is left alone.
  function sync(bg) {
    const put = (id, value, prop = "value") => {
      const el = $(id);
      if (el && document.activeElement !== el) el[prop] = value;
    };
    put("wb-bo-grid-size", bg.grid_size || "");
    put("wb-bo-grid-color", bg.grid_color || "#888888");
  }

  //: A number box: blank is the default (the setting is removed), else clamped to the server's bounds.
  const boxValue = (el, min, max) => (el.value === "" ? null : Math.max(min, Math.min(max, Math.round(Number(el.value) || 0))));

  function wire() {
    $("wb-bo-grid-size")?.addEventListener("change", (e) => {
      const size = boxValue(e.target, 4, 200);
      wbSetBackground({ grid_size: size === DEFAULT_GRID ? null : size }).then((ok) => ok && wbAnnounce(size ? `Grid size ${size}.` : "Grid size default."));
    });
    $("wb-bo-grid-color")?.addEventListener("change", (e) => wbSetBackground({ grid_color: e.target.value }));
    $("wb-bo-grid-reset")?.addEventListener("click", () => wbSetBackground({ grid_color: null }));
  }

  wbFmtState.opts = { sync };
  onSurface("board", wire);
})();
