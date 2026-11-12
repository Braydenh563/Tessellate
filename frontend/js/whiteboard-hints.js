(() => {
  // whiteboard-hints.js: View, Connection arrows and Connection points (WHITEBOARD_PLAN, draw.io
  // section 10, "Connection arrows and points as View toggles"). Each is a switch kept on this
  // device; off hides the four arrow grips round a selected shape, or the dots that show where a
  // line can join, for a board you are only reading or presenting. Joining by dragging a line onto
  // a shape still snaps to the same places: only the drawing of them is hidden, as in draw.io.
  const SWITCHES = [
    { id: "wb-view-grips", pref: "wb-view-grips", hide: "wb-hide-grips" },
    { id: "wb-view-ports", pref: "wb-view-ports", hide: "wb-hide-ports" },
  ];
  //: The View menu is part of the board's surface, so the switches are found once it is built.
  function wire() {
    const host = document.getElementById("library-view-whiteboard");
    for (const { id, pref, hide } of SWITCHES) {
      const box = document.getElementById(id);
      if (!box || !host) continue;
      const apply = (on) => {
        box.checked = on;
        host.classList.toggle(hide, !on);
      };
      apply(prefs.get(pref, null) !== "off");
      box.addEventListener("change", () => {
        prefs.set(pref, box.checked ? "on" : "off");
        apply(box.checked);
      });
    }
  }
  onSurface("board", wire);
})();
