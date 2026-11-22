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

  // L-whiteboard-10: the first time a tool is held on this device, one line says what it does that its button
  // does not. Shown as a quiet toast, then remembered per tool (`wb-tool-hint-<tool>`), so it never repeats.
  // A muted notification setting silences it without using the hint up. Shape variants share one line.
  const SHAPE_LINE = "Drag to draw the shape; hold Shift to keep it square or round, and type to label it.";
  const TOOL_HINTS = {
    select: "Click to select, drag on empty space to box-select, and Shift-click to add more.",
    pan: "Drag to move around the board; scroll or pinch to zoom.",
    lasso: "Draw a loop round what you want; everything inside it is selected.",
    draw: "Drag to draw freehand; the pen's size and dash are in the bar above.",
    highlighter: "Drag over anything to mark it; the strokes stay see-through.",
    eraser: "Drag across strokes to rub them out; one Undo puts them back.",
    delete: "Click an item to delete it; one Undo puts it back.",
    bucket: "Click a closed shape to fill it with the ink colour.",
    text: "Click to place a text box and type; Escape finishes.",
    sticky: "Click to place a sticky note and type; Enter drops one in the middle of the view.",
    frame: "Drag to draw a frame; what sits inside it moves with it.",
    line: "Drag to draw a line; Shift snaps it to 15 degrees.",
    arrow: "Drag to draw an arrow; the ends and head are in the bar above.",
    "link-curved": "Drag from one item to another to join them with a curved connector.",
    "link-straight": "Drag from one item to another to join them with a straight connector.",
    rect: SHAPE_LINE, circle: SHAPE_LINE, triangle: SHAPE_LINE, diamond: SHAPE_LINE,
  };
  const hintFor = (tool) => TOOL_HINTS[tool] || (String(tool).startsWith("shape-") ? SHAPE_LINE : "");
  //: Returns the line shown, or "" when the tool has none or has been hinted before.
  function toolHint(tool) {
    const line = hintFor(tool);
    const key = `wb-tool-hint-${tool}`;
    if (!line || prefs.get(key, null) === "seen") return "";
    prefs.set(key, "seen");
    toast(line, "info");
    return line;
  }
  wbFmtState.hints = { toolHint, hintFor, TOOL_HINTS };
})();
