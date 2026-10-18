// whiteboard-commands.js: every board action by name, in one table
// (2026-10-05, the features audit's controls redesign, section 9.2 item 1).
//
// **Why a table.** The audit found the same action under three names on
// three surfaces ("Bring forward" in the Arrange menu and the context bar,
// "Bring to front" on the right-click menu, all three doing the front), Group
// and Lock missing from the menu that names arranging, and no way to find a
// board action by typing its name (FEAT-07, FEAT-11, FEAT-19). One row per
// action, read by every surface that offers it, is what makes those three
// impossible rather than fixed once:
//
// - the Arrange and Edit menus' rows carry `data-wb-cmd` and the lint
//   (`tests/test_wb_commands.py`) holds each row's words and key to the row
//   here;
// - the right-click menu builds its shared rows through `wbCommandMenuRow`;
// - the command palette's "This board" group is `wbPaletteCommands`;
// - the shortcut sheet's whiteboard section is `renderWbShortcutSheet`.
//
// Standing order 13 made structural: a control renamed here is renamed on
// every surface, and the help (`ai/help_chat.py`'s whiteboard entry) is
// checked against the keys by `tests/test_help_controls.py`.
//
// **Loaded in the Library bundle after whiteboard.js** (`LAZY_MODULES`,
// app.js). Its top level declares the table and nothing else; every `run`
// and `when` reads whiteboard.js's functions at call time. The palette
// (palette.js) and the shortcut sheet (settings-wiring.js) reach in through
// `typeof` guards listed in `tests/test_lazy_bundle_calls.py`.

//: What a command needs to apply. `selection`: something is selected;
//: `two` / `three`: at least that many; `shape`: one closed shape or one
//: connector (the text in it, decisions 12 and 13); `one`: exactly one item.
function wbCommandSelectionCount() {
  if (wbMultiSelection.size) return wbMultiSelection.size;
  return wbSelectedItem ? 1 : 0;
}

function wbCommandOneSketch() {
  if (wbMultiSelection.size > 1 || wbSelectedItem?.kind !== "sketch") return null;
  return (wbState.sketches || []).find((s) => s.id === wbSelectedItem.id) || null;
}

//: The one selected shape or connector that can hold words, or null.
function wbCommandTextTarget() {
  const sketch = wbCommandOneSketch();
  if (!sketch) return null;
  if (wbShapeLabelKind(wbSketchParsedData(sketch))) return { sketch, kind: "shape" };
  let parsed = null;
  try {
    parsed = JSON.parse(sketch.data);
  } catch {
    parsed = null;
  }
  return wbLinkTakesLabel(sketch, parsed) ? { sketch, kind: "link" } : null;
}

const wbCommandNeeds = {
  link: () => wbCommandTextTarget()?.kind === "link",
  clone: () => Boolean(wbCloneSource()),
  selection: () => wbCommandSelectionCount() > 0,
  two: () => wbCommandSelectionCount() >= 2,
  three: () => wbCommandSelectionCount() >= 3,
  one: () => wbCommandSelectionCount() === 1,
  shape: () => Boolean(wbCommandTextTarget()),
  frame: () => {
    const item = wbSelectedItem && wbMultiSelection.size <= 1 ? wbFindItem(wbSelectedItem.kind, wbSelectedItem.id) : null;
    return wbSelectedItem?.kind === "object" && item?.kind === "frame";
  },
  comment: () => {
    if (wbMultiSelection.size > 1 || !wbSelectedItem) return false;
    return wbTakesComments(wbSelectedItem.kind, wbFindItem(wbSelectedItem.kind, wbSelectedItem.id));
  },
  locked: () => wbLockedItems().length > 0,
  topic: () => Boolean(wbSelectedMapNode()),
  notetopic: () => wbMapIsNoteTopic(wbSelectedMapNode()),
  drawing: () => Boolean(wbCommandOneSketch() && wbSketchParsedData(wbCommandOneSketch())?.d),
  styled: () => {
    if (wbMultiSelection.size > 1 || !wbSelectedItem || wbSelectedItem.kind === "node") return false;
    const item = wbFindItem(wbSelectedItem.kind, wbSelectedItem.id);
    return wbSelectedItem.kind === "sketch" ? Boolean(wbSketchParsedData(item)) : item?.kind === "text";
  },
  textbox: () => {
    if (wbMultiSelection.size > 1 || wbSelectedItem?.kind !== "object") return false;
    return wbFindItem("object", wbSelectedItem.id)?.kind === "text";
  },
};

//: Each names what it presses (`clickId`, `tool`), so the phone's More sheet
//: can tell whether that control is already in reach of a thumb.
const wbClickId = (id) => Object.assign(() => document.getElementById(id)?.click(), { clickId: id });
const wbTool = (tool) => Object.assign(() => {
  wbSelectToolRef?.(tool);
}, { tool });

//: The table. `keys` is what the board already listens for ("" where the
//: action has no key); `menu` is the shorter words a menu row uses where its
//: group heading says the rest ("Left edges" under "Align"); `surface` is
//: "board", "map" or "both"; `needs` names a `wbCommandNeeds` test.
const WB_COMMANDS = [
  // Edit
  { id: "undo", group: "Edit", icon: "ph:arrow-counter-clockwise", label: "Undo", keys: "Ctrl+Z", surface: "both", run: () => wbUndo() },
  { id: "redo", group: "Edit", icon: "ph:arrow-clockwise", label: "Redo", keys: "Ctrl+Y", surface: "both", run: () => wbRedo() },
  { id: "select-all", group: "Edit", icon: "ph:selection-all", label: "Select all", keys: "Ctrl+A", surface: "both", run: () => wbSelectAllItems() },
  { id: "copy", group: "Edit", icon: "ph:copy-simple", label: "Copy", keys: "Ctrl+C", surface: "board", needs: "selection", run: () => wbCopySelection() },
  { id: "cut", group: "Edit", icon: "ph:scissors", label: "Cut", keys: "Ctrl+X", surface: "board", needs: "selection", run: () => wbCutSelection() },
  { id: "paste", group: "Edit", icon: "ph:clipboard", label: "Paste", keys: "Ctrl+V", surface: "board", run: () => wbPasteClipboard() },
  { id: "duplicate", group: "Edit", icon: "ph:copy", label: "Duplicate", keys: "Ctrl+D", surface: "both", needs: "selection", run: () => wbDuplicateSelection() },
  { id: "delete", group: "Edit", icon: "ph:trash", label: "Delete", keys: "Del", surface: "both", needs: "selection", run: () => deleteWbSelection() },
  { id: "copy-style", group: "Edit", icon: "ph:eyedropper", label: "Copy style", keys: "Ctrl+Alt+C", surface: "board", needs: "one", run: () => wbCopySelectedStyle() },
  { id: "paste-style", group: "Edit", icon: "ph:paint-bucket", label: "Paste style", keys: "Ctrl+Alt+V", surface: "board", needs: "selection", run: () => wbPasteCopiedStyle() },
  { id: "reset-style", group: "Edit", icon: "ph:arrow-counter-clockwise", label: "Reset style", keys: "", surface: "both", needs: "selection", run: () => wbResetSelectedStyle() },
  { id: "find", group: "Edit", icon: "ph:magnifying-glass", label: "Find on this board", menu: "Find on this board", keys: "Ctrl+F", surface: "both", run: () => wbOpenBoardSearch() },
  { id: "replace", group: "Edit", icon: "ph:swap", label: "Find and replace on this board", menu: "Find and replace", keys: "Ctrl+H", surface: "board", run: () => wbOpenBoardSearch({ replace: true }) },
  // The item
  { id: "text", group: "Item", icon: "ph:text-aa", label: "Write in the shape or label the connector", keys: "Enter", surface: "board", needs: "shape",
    run: () => {
      const target = wbCommandTextTarget();
      if (target?.kind === "shape") wbEditShapeLabel(target.sketch);
      else if (target) wbEditLinkLabel(target.sketch);
    } },
  { id: "line-curved", group: "Item", icon: "ph:bezier-curve", label: "Line shape: curved", keys: "", surface: "board", needs: "link", run: () => wbSetLinkRoute("curved") },
  { id: "line-straight", group: "Item", icon: "ph:line-segment", label: "Line shape: straight", keys: "", surface: "board", needs: "link", run: () => wbSetLinkRoute("straight") },
  { id: "line-elbow", group: "Item", icon: "ph:arrow-elbow-down-right", label: "Line shape: elbow", keys: "", surface: "board", needs: "link", run: () => wbSetLinkRoute("elbow") },
  { id: "clone-right", group: "Item", icon: "ph:arrow-right", label: "Copy to the right and join", keys: "Alt+Shift+Right", surface: "board", needs: "clone", run: () => wbCloneConnect("right") },
  { id: "clone-down", group: "Item", icon: "ph:arrow-down", label: "Copy below and join", keys: "Alt+Shift+Down", surface: "board", needs: "clone", run: () => wbCloneConnect("down") },
  { id: "comment", group: "Item", icon: "ph:chat-teardrop-text", label: "Comment on the item", keys: "", surface: "board", needs: "comment",
    run: () => wbOpenComments(wbSelectedItem.kind, wbSelectedItem.id) },
  { id: "fit-frame", group: "Item", icon: "ph:arrows-in", label: "Fit this frame to its contents", keys: "", surface: "board", needs: "frame",
    run: () => wbFrameFit(wbFindItem("object", wbSelectedItem.id), "nesw") },
  { id: "export-frame", group: "Item", icon: "ph:frame-corners", label: "Export this frame", keys: "", surface: "board", needs: "frame",
    run: () => wbExportFrame(wbFindItem("object", wbSelectedItem.id)) },
  // The library (decision 25, whiteboard-library.js)
  { id: "open-library", group: "Library", icon: "ph:shapes", label: "Open the library", menu: "Shapes, icons and frames…", keys: "", surface: "both", run: () => wbOpenSidebar("library") },
  { id: "save-selection", group: "Library", icon: "ph:bookmark-simple", label: "Save to the library…", keys: "Ctrl+Shift+S", surface: "board", needs: "selection", run: () => wbSaveSelectionToLibrary() },
  { id: "save-branch", group: "Library", icon: "ph:tree-structure", label: "Save this branch to the library…", keys: "Ctrl+Shift+S", surface: "map", needs: "topic", run: () => wbSaveBranchToLibrary() },
  { id: "fold-level-1", group: "View", icon: "ph:list-dashes", label: "Show the trunks only", keys: "Alt+1", surface: "map", run: () => wbMapFoldToLevel(1) },
  { id: "fold-level-2", group: "View", icon: "ph:list-dashes", label: "Show two levels", keys: "Alt+2", surface: "map", run: () => wbMapFoldToLevel(2) },
  { id: "fold-level-3", group: "View", icon: "ph:list-dashes", label: "Show three levels", keys: "Alt+3", surface: "map", run: () => wbMapFoldToLevel(3) },
  { id: "summarise-branch", group: "Item", icon: "ph:text-align-left", label: "Summarise this branch", keys: "", surface: "map", needs: "topic", run: () => wbMapSummariseBranch(wbSelectedMapNode()) },
  { id: "expand-from-note", group: "Item", icon: "ph:tree-structure", label: "Expand from my notes…", keys: "", surface: "map", needs: "notetopic", run: () => wbMapExpandFromNote(wbSelectedMapNode()) },
  { id: "suggest-branches", group: "Item", icon: "ph:lightbulb", label: "Branches from my notes…", keys: "", surface: "map", needs: "topic", run: () => wbMapSuggestBranches(wbSelectedMapNode()) },
  { id: "save-shape", group: "Library", icon: "ph:polygon", label: "Save as a shape…", keys: "", surface: "board", needs: "drawing", run: () => wbSaveShapeToLibrary() },
  { id: "save-style", group: "Library", icon: "ph:paint-brush", label: "Save this style…", keys: "", surface: "board", needs: "styled", run: () => wbSaveStyleToLibrary() },
  { id: "save-preset", group: "Library", icon: "ph:note", label: "Save as a preset…", keys: "", surface: "board", needs: "textbox", run: () => wbSavePresetToLibrary() },
  { id: "save-palette", group: "Library", icon: "ph:palette", label: "Save these colours as a palette…", keys: "", surface: "board", needs: "selection", run: () => wbSavePaletteToLibrary() },
  { id: "save-template", group: "Library", icon: "ph:squares-four", label: "Save this board as a template…", keys: "", surface: "both", run: () => wbSaveBoardAsTemplate() },
  // Arrange
  { id: "align-left", group: "Arrange", icon: "ph:align-left", label: "Align left edges", menu: "Left edges", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("left") },
  { id: "align-hcenter", group: "Arrange", icon: "ph:align-center-horizontal", label: "Align centres horizontally", menu: "Centres, horizontally", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("hcenter") },
  { id: "align-right", group: "Arrange", icon: "ph:align-right", label: "Align right edges", menu: "Right edges", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("right") },
  { id: "align-top", group: "Arrange", icon: "ph:align-top", label: "Align top edges", menu: "Top edges", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("top") },
  { id: "align-vcenter", group: "Arrange", icon: "ph:align-center-vertical", label: "Align centres vertically", menu: "Centres, vertically", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("vcenter") },
  { id: "align-bottom", group: "Arrange", icon: "ph:align-bottom", label: "Align bottom edges", menu: "Bottom edges", keys: "", surface: "board", needs: "two", run: () => wbAlignSelection("bottom") },
  { id: "distribute-h", group: "Arrange", icon: "ph:columns", label: "Distribute evenly, left to right", menu: "Evenly, left to right", keys: "", surface: "board", needs: "three", run: () => wbDistributeSelection("horizontal") },
  { id: "distribute-v", group: "Arrange", icon: "ph:rows", label: "Distribute evenly, top to bottom", menu: "Evenly, top to bottom", keys: "", surface: "board", needs: "three", run: () => wbDistributeSelection("vertical") },
  { id: "same-width", group: "Arrange", icon: "ph:arrows-out-line-horizontal", label: "Same width as the widest", menu: "Same width", keys: "", surface: "board", needs: "two", run: () => wbSameSizeSelection("width") },
  { id: "same-height", group: "Arrange", icon: "ph:arrows-out-line-vertical", label: "Same height as the tallest", menu: "Same height", keys: "", surface: "board", needs: "two", run: () => wbSameSizeSelection("height") },
  { id: "group", group: "Arrange", icon: "ph:link", label: "Group", keys: "Ctrl+G", surface: "board", needs: "two", run: () => wbGroupSelection() },
  { id: "ungroup", group: "Arrange", icon: "ph:link-break", label: "Ungroup", keys: "Ctrl+Shift+G", surface: "board", needs: "selection", run: () => wbUngroupSelection() },
  { id: "order-forward", group: "Arrange", icon: "ph:arrow-up", label: "Bring forward", keys: "]", surface: "board", needs: "selection", run: () => wbStepSelectionZOrder(1) },
  { id: "order-backward", group: "Arrange", icon: "ph:arrow-down", label: "Send backward", keys: "[", surface: "board", needs: "selection", run: () => wbStepSelectionZOrder(-1) },
  { id: "order-front", group: "Arrange", icon: "ph:arrow-line-up", label: "Bring to front", keys: "Ctrl+]", surface: "board", needs: "selection", run: () => wbSendSelectionZOrder(true) },
  { id: "order-back", group: "Arrange", icon: "ph:arrow-line-down", label: "Send to back", keys: "Ctrl+[", surface: "board", needs: "selection", run: () => wbSendSelectionZOrder(false) },
  { id: "lock", group: "Arrange", icon: "ph:lock-simple", label: "Lock", keys: "Ctrl+Shift+L", surface: "board", needs: "selection", run: () => wbLockSelection() },
  { id: "unlock-all", group: "Arrange", icon: "ph:lock-simple-open", label: "Unlock every locked item", menu: "Unlock all", keys: "", surface: "board", needs: "locked", run: () => wbUnlockAll() },
  // Insert
  { id: "insert-sticky", group: "Insert", icon: "ph:note", label: "Sticky note", keys: "N", surface: "board", run: wbTool("sticky") },
  { id: "insert-text", group: "Insert", icon: "ph:text-t", label: "Text box", keys: "T", surface: "board", run: wbTool("text") },
  { id: "insert-frame", group: "Insert", icon: "ph:frame-corners", label: "Frame", keys: "F", surface: "board", run: wbTool("frame") },
  //: canvasdepth2: draw.io's table, rows and columns of text cells.
  { id: "insert-table", group: "Insert", icon: "ph:table", label: "Table", keys: "", surface: "board", run: () => wbInsertTable() },
  //: draw.io's Edit data (Ctrl+M): the Format panel's Data tab.
  { id: "edit-data", group: "Edit", icon: "ph:database", label: "Edit data", keys: "", surface: "board", needs: "selection", run: () => wbFormatOpen("data") },
  { id: "insert-image", group: "Insert", icon: "ph:image", label: "Image from a file", keys: "I", surface: "board", run: wbClickId("wb-add-image") },
  { id: "insert-note", group: "Insert", icon: "ph:note-pencil", label: "A note from the library", keys: "", surface: "both", run: wbClickId("wb-add-note") },
  //: MINDMAP_PLAN decision 44: a sticker, or (dropped on a topic) its icon.
  { id: "insert-sticker", group: "Insert", icon: "ph:smiley-sticker", label: "Emoji and icon stickers", menu: "Emoji and icons…", keys: "", surface: "both", run: () => wbOpenStickerPicker() },
  // Tools
  { id: "tool-select", group: "Tools", icon: "ph:cursor", label: "Select tool", keys: "V", surface: "both", run: wbTool("select") },
  { id: "tool-pan", group: "Tools", icon: "ph:hand", label: "Hand tool", keys: "H", surface: "both", run: wbTool("pan") },
  { id: "tool-lasso", group: "Tools", icon: "ph:lasso", label: "Lasso", keys: "K", surface: "board", run: wbTool("lasso") },
  { id: "tool-pen", group: "Tools", icon: "ph:pen", label: "Pen", keys: "P", surface: "board", run: wbTool("draw") },
  { id: "tool-highlighter", group: "Tools", icon: "ph:highlighter", label: "Highlighter", keys: "M", surface: "board", run: wbTool("highlighter") },
  { id: "tool-eraser", group: "Tools", icon: "ph:eraser", label: "Eraser", keys: "E", surface: "board", run: wbTool("eraser") },
  { id: "tool-fill", group: "Tools", icon: "ph:paint-bucket", label: "Fill", keys: "B", surface: "board", run: wbTool("bucket") },
  { id: "tool-line", group: "Tools", icon: "ph:line-segment", label: "Line", keys: "L", surface: "board", run: wbTool("line") },
  { id: "tool-arrow", group: "Tools", icon: "ph:arrow-up-right", label: "Arrow", keys: "A", surface: "board", run: wbTool("arrow") },
  { id: "tool-rect", group: "Tools", icon: "ph:square", label: "Rectangle", keys: "R", surface: "board", run: wbTool("rect") },
  { id: "tool-circle", group: "Tools", icon: "ph:circle", label: "Circle", keys: "O", surface: "board", run: wbTool("circle") },
  { id: "tool-triangle", group: "Tools", icon: "ph:triangle", label: "Triangle", keys: "G", surface: "board", run: wbTool("triangle") },
  { id: "tool-diamond", group: "Tools", icon: "ph:diamond", label: "Diamond", keys: "D", surface: "board", run: wbTool("diamond") },
  //: The more shapes (2026-10-11), from their own table, so a shape added
  //: there is in the palette and the phone's sheet with no second list.
  ...Object.entries(WB_MORE_SHAPES).map(([tool, shape]) => ({ id: `tool-${tool}`, group: "Tools", icon: shape.icon, label: shape.label, keys: "", surface: "board", run: wbTool(tool) })),
  { id: "tool-connector", group: "Tools", icon: "ph:line-segment", label: "Connector", keys: "C", surface: "both", run: wbTool("link-straight") },
  { id: "tool-connector-curved", group: "Tools", icon: "ph:bezier-curve", label: "Curved connector", keys: "Shift+C", surface: "both", run: wbTool("link-curved") },
  { id: "tool-delete", group: "Tools", icon: "ph:trash", label: "Delete tool", keys: "X", surface: "board", run: wbTool("delete") },
  // View
  { id: "import-diagram", group: "Insert", icon: "ph:flow-arrow", label: "Import a Mermaid diagram, a draw.io file or a board SVG", menu: "Mermaid, draw.io or board SVG…", keys: "", surface: "board", run: () => wbOpenImportDialog() },
  { id: "format-panel", group: "View", icon: "ph:sliders-horizontal", label: "Format panel", keys: "Ctrl+Shift+P", surface: "board", run: () => wbFormatToggle() },
  { id: "zoom-in", group: "View", icon: "ph:magnifying-glass-plus", label: "Zoom in", keys: "Ctrl+=", surface: "both", run: wbClickId("wb-zoom-in") },
  { id: "zoom-out", group: "View", icon: "ph:magnifying-glass-minus", label: "Zoom out", keys: "Ctrl+-", surface: "both", run: wbClickId("wb-zoom-out") },
  { id: "zoom-100", group: "View", icon: "ph:magnifying-glass", label: "Zoom to 100%", keys: "Ctrl+0", surface: "both", run: wbClickId("wb-zoom-actual") },
  { id: "zoom-fit", group: "View", icon: "ph:frame-corners", label: "Fit everything", keys: "Shift+1", surface: "both", run: () => wbZoomToFit() },
  { id: "overview", group: "View", icon: "ph:map-trifold", label: "Board overview", keys: "Shift+N", surface: "both", run: () => wbToggleNavigator() },
  //: The View menu's background, grid and colour rows (row 9), each pressing
  //: or setting the menu's own control, so the two cannot disagree.
  { id: "bg-reset", group: "View", icon: "ph:arrow-counter-clockwise", label: "Reset the background colour to the theme default", keys: "", surface: "both", run: wbClickId("wb-bg-color-reset") },
  { id: "bg-image", group: "View", icon: "ph:image", label: "Set a background image", keys: "", surface: "both", run: wbClickId("wb-bg-image") },
  ...[["none", "None"], ["lines", "Lines"], ["dots", "Dots"], ["iso", "Isometric"]].map(([value, name]) => (
    { id: `grid-${value}`, group: "View", icon: "ph:grid-four", label: `Grid: ${name.toLowerCase()}`, keys: "", surface: "both", run: () => wbSetSelectValue("wb-grid-select", value) })),
  ...[["branch", "branch"], ["category", "category"], ["age", "age"], ["notes", "behind a note"]].map(([value, name]) => (
    { id: `colour-by-${value}`, group: "View", icon: "ph:palette", label: `Colour by ${name}`, keys: "", surface: "map", run: () => wbSetSelectValue("wb-map-perspective", value) })),
  { id: "dock-side", group: "View", icon: "ph:sidebar-simple", label: "Dock the tools as a sidebar or at the bottom", keys: "", surface: "both", run: wbClickId("wb-dock-toggle") },
  { id: "sidebar", group: "View", icon: "ph:sidebar-simple", label: "Show or hide the sidebar", keys: "", surface: "both", run: wbClickId("wb-add-note") },
  { id: "fullscreen", group: "View", icon: "ph:arrows-out", label: "Full screen", keys: "", surface: "both", run: () => toggleWhiteboardFullscreen() },
  { id: "present", group: "View", icon: "ph:presentation", label: "Present frames", keys: "", surface: "board", run: () => wbStartPresenting() },
  // The board
  //: The top bar's first two controls, by name (MINDMAP_PLAN 15 row 9: every
  //: bar control has a palette row).
  { id: "back-to-boards", group: "Board", icon: "ph:arrow-left", label: "Back to the board list", keys: "", surface: "both", run: wbClickId("wb-back-to-boards") },
  { id: "switch-board", group: "Board", icon: "ph:swap", label: "Which board or map to show", menu: "Open another board or map…", keys: "", surface: "both", run: () => document.getElementById("wb-board-select")?.closest(".select-shell")?.querySelector(".select-opener")?.click() },
  //: And the Board menu's rows that had none (row 9).
  { id: "add-to-note", group: "Board", icon: "ph:note-pencil", label: "Put this board in a note as an object", keys: "", surface: "both", run: wbClickId("wb-add-to-note") },
  { id: "copy-link", group: "Board", icon: "ph:link", label: "Copy this board's or mind map's address to open it in the app", menu: "Copy app link", keys: "", surface: "both", run: wbClickId("wb-copy-link") },
  { id: "delete-board", group: "Board", icon: "ph:trash", label: "Delete this board and everything on it", keys: "", surface: "both", run: wbClickId("wb-delete-board") },
  { id: "keys", group: "Board", icon: "ph:keyboard", label: "Every key and gesture on a board", menu: "Keys and controls", keys: "?", surface: "both", run: wbClickId("wb-help-btn") },
  { id: "export", group: "Board", icon: "ph:download-simple", label: "Export this board", keys: "", surface: "both", run: wbClickId("wb-export") },
  { id: "rename", group: "Board", icon: "ph:pencil-simple", label: "Rename this board", keys: "", surface: "both", run: wbClickId("wb-rename-board") },
  { id: "new-board", group: "Board", icon: "ph:plus", label: "New board", keys: "", surface: "both", run: wbClickId("wb-new-board") },
  { id: "switch-kind", group: "Board", icon: "ph:tree-structure", label: "Switch between a whiteboard and a mind map", keys: "", surface: "both", run: wbClickId("wb-board-kind") },
  { id: "clear", group: "Board", icon: "ph:eraser", label: "Clear this board", keys: "", surface: "both", run: wbClickId("wb-clear-board") },
  { id: "snapshots", group: "Board", icon: "ph:camera", label: "Snapshots: named versions of this board", menu: "Snapshots…", keys: "", surface: "both", run: () => wbOpenSnapshots() },
  { id: "history", group: "Board", icon: "ph:clock-counter-clockwise", label: "History: see the board as it was, and put it back", menu: "History…", keys: "", surface: "both", run: () => wbOpenHistory() },
];

const WB_COMMAND_BY_ID = new Map(WB_COMMANDS.map((c) => [c.id, c]));

//: Whether a command applies on the board as it is now.
function wbCommandApplies(command) {
  if (!command) return false;
  const map = wbIsMap();
  if (command.surface === "board" && map) return false;
  if (command.surface === "map" && !map) return false;
  return !command.needs || Boolean(wbCommandNeeds[command.needs]?.());
}

//: Runs a command by id, saying why when it does not apply rather than doing
//: nothing (a menu row is pressed on purpose).
function wbRunCommand(id) {
  const command = WB_COMMAND_BY_ID.get(id);
  if (!command) return false;
  if (!wbCommandApplies(command)) {
    const why = {
      selection: "Select something first.",
      one: "Select one item first.",
      two: "Select two or more items first.",
      three: "Select three or more items first.",
      shape: "Select one closed shape or one connector first.",
      link: "Select one connector first.",
      clone: "Select one shape or text box first.",
      frame: "Select a frame first.",
      comment: "Select one item first.",
      locked: "Nothing on this board is locked.",
      topic: "Select a topic first.",
      notetopic: "Select a topic that is one of your notes first.",
      drawing: "Select one drawn shape or pen stroke first.",
      styled: "Select one shape, line or text box first.",
      textbox: "Select one sticky or text box first.",
    }[command.needs];
    toast(why || "That is not on a mind map.");
    return false;
  }
  command.run();
  return true;
}

//: A right-click menu row from the table: the same words and the same key
//: as the Arrange menu's row and the palette's.
function wbCommandMenuRow(id) {
  const command = WB_COMMAND_BY_ID.get(id);
  if (!command || !wbCommandApplies(command)) return null;
  return [command.label, command.keys || "", () => command.run()];
}

//: Whether the board is the thing on screen, with a board in it: the
//: palette's "This board" group shows only then.
function wbCommandsLive() {
  const view = document.getElementById("library-view-whiteboard");
  const canvas = document.getElementById("wb-canvas-view");
  //: Rendered, not only un-hidden: the Library tab hides by its own panel,
  //: so a board left open there kept these classes while Notes or Ask was on
  //: screen, and a stray Ctrl+V dropped an image onto the unseen board (and
  //: started captioning it). `getClientRects()` is empty under any hidden
  //: ancestor.
  return Boolean(view && !view.classList.contains("hidden") && canvas && !canvas.classList.contains("hidden") && canvas.getClientRects().length);
}

//: The command palette's rows (palette.js, through `paletteCommands` in
//: settings-panes.js), in the documents editor's group shape: a group, a
//: label with its icon, the keys, a `run`. Only what applies now.
function wbPaletteCommands() {
  if (!wbCommandsLive()) return [];
  const later = (fn) => () => setTimeout(fn);
  return WB_COMMANDS.filter((command) => wbCommandApplies(command)).map((command) => ({
    group: wbIsMap() ? "This map" : "This board",
    label: `${command.icon} ${command.label}`,
    keys: command.keys,
    run: later(() => command.run()),
  }));
}

//: **A sentence over a board is an act** (CHAT_PLAN section 2, the board's
//: acts): "arrange as a grid of 3", "stack them", "align left" in the command
//: palette is the first row, read by the server (`GET /read/board`,
//: `acts.board_parse`; this file reads no words itself) and run by the
//: board's own arrange commands, so Undo takes it back. Synchronous for
//: `paletteMatches`, like quick add's act row: the reading arrives on its own
//: and redraws the palette.
const wbActReading = { q: null, act: null };

function wbPaletteActRow(query) {
  if (!wbCommandsLive() || wbIsMap()) return null;
  const q = String(query || "").trim();
  if (!q) return null;
  if (wbActReading.q !== q) {
    wbActReading.q = q;
    wbActReading.act = null;
    apiJson("/read/board?q=" + encodeURIComponent(q), { silent: true })
      .then((got) => {
        if (wbActReading.q !== q || !got.act) return;
        wbActReading.act = got.act;
        const field = $("palette-input");
        if (!$("palette-overlay").classList.contains("hidden") && field.value.trim() === q) renderPalette(field.value);
      })
      .catch(() => {});
    return null;
  }
  const act = wbActReading.act;
  if (!act) return null;
  return { group: "This board", label: `ph:squares-four ${act.label}`, about: act.help, run: () => setTimeout(() => wbRunBoardAct(act)) };
}

function wbRunBoardAct(act) {
  const slots = act.slots || {};
  if (act.intent === "grid") return wbArrangeGridSelection(slots.columns || 0);
  if (act.intent === "row") return wbArrangeGridSelection(Infinity);
  if (act.intent === "column") return wbArrangeGridSelection(1);
  if (act.intent === "align") return wbAlignSelection(slots.edge);
  if (act.intent === "distribute") return wbDistributeSelection(slots.axis);
  if (act.intent === "same-size") return wbSameSizeSelection(slots.dimension);
  return null;
}

//: The shortcut sheet's whiteboard section, from the same table, so the two
//: cannot disagree. Called by `openShortcuts` (settings-wiring.js).
function renderWbShortcutSheet(list) {
  if (!list) return;
  list.replaceChildren();
  for (const command of WB_COMMANDS) {
    if (!command.keys) continue;
    const li = document.createElement("li");
    const keys = document.createElement("span");
    keys.className = "shortcut-keys";
    for (const part of command.keys.split(/\s*\+\s*/)) {
      if (keys.childNodes.length) keys.append(" ");
      const kbd = document.createElement("kbd");
      kbd.textContent = part;
      keys.append(kbd);
    }
    const what = document.createElement("span");
    what.textContent = command.label;
    li.append(keys, what);
    list.append(li);
  }
}

//: Menu rows that name a command run it (`data-wb-cmd`), and grey out while
//: it does not apply, refreshed as the menu opens.
function wbSyncCommandRows(menu) {
  for (const row of menu.querySelectorAll("[data-wb-cmd]")) {
    const applies = wbCommandApplies(WB_COMMAND_BY_ID.get(row.dataset.wbCmd));
    row.setAttribute("aria-disabled", applies ? "false" : "true");
    row.classList.toggle("is-muted", !applies);
  }
}

// --- The phone's More sheet (Brief 77, WORLD_CLASS 28.1 rules 8 and 2) -----
//
// Below 820 the bar keeps Insert, Edit, View and Board and the tools sheet;
// Arrange, Full screen, View's zoom rows, the shape flyout's lines and every
// context-bar row had no path a thumb could take (measured,
// `scratchpad/ui-sweeps/wbphonecmds.js`: 40 of 81 at 390). One `kebabMenu` at
// the bar's end lists each command the bar does not carry, in the table's
// groups; `kebabMenu` makes it the action sheet below 600.

//: A menu's select set from a command, through its own change handler.
function wbSetSelectValue(id, value) {
  const select = document.getElementById(id);
  if (!select) return;
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

//: Whether a control is a thumb's reach away: rendered, or behind a door
//: that is (a top-bar menu whose toggle shows, the tools sheet's opener, a
//: closed flyout inside either). A control the stylesheet hides at this width
//: is not.
function wbPhoneReachable(el) {
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    if (node.classList.contains("wb-board-menu") && node.id) {
      const toggle = document.querySelector(`[aria-controls="${node.id}"]`);
      return Boolean(toggle && toggle.getClientRects().length);
    }
    if (node.id === "wb-tool-group") {
      return Boolean(node.getClientRects().length || document.getElementById("wb-tools-opener")?.getClientRects().length);
    }
    if (node.classList.contains("hidden")) continue;
    if (getComputedStyle(node).display === "none") return false;
  }
  return true;
}

//: Whether the bar, its menus or the tools sheet already carry `command`.
function wbPhoneCarries(command) {
  const run = command.run || {};
  const found = [
    ...document.querySelectorAll(`#wb-topbar [data-wb-cmd="${command.id}"], .wb-board-menu [data-wb-cmd="${command.id}"]`),
    ...(run.tool ? document.querySelectorAll(`#wb-tool-group [data-tool="${run.tool}"]`) : []),
    ...(run.clickId ? [document.getElementById(run.clickId)].filter(Boolean) : []),
  ].filter((el) => !el.closest("#wb-more-menu"));
  return found.some(wbPhoneReachable);
}

//: Shows the rows this board needs as the sheet opens: the surface's, minus
//: what the bar carries, greyed while they do not apply (pressed anyway, a
//: row says why, `wbRunCommand`). A hairline between two groups shows only
//: when both sides keep a row.
function wbSyncMoreMenu(menu) {
  const map = wbIsMap();
  wbSyncMoreMapRows(menu, map);
  for (const row of menu.querySelectorAll("[data-wb-cmd]")) {
    const command = WB_COMMAND_BY_ID.get(row.dataset.wbCmd);
    const surface = command.surface === "both" || command.surface === (map ? "map" : "board");
    row.hidden = !surface || wbPhoneCarries(command);
    const applies = wbCommandApplies(command);
    row.classList.toggle("menu-item-unavailable", !applies);
    row.setAttribute("aria-disabled", applies ? "false" : "true");
  }
  let shown = false;
  let rule = null;
  for (const child of menu.children) {
    if (child.classList.contains("menu-sep")) {
      child.hidden = true;
      if (shown) rule = child;
      continue;
    }
    if (child.hidden) continue;
    if (rule) rule.hidden = false;
    rule = null;
    shown = true;
  }
}

//: **The open map's own commands, in the same sheet** (MINDMAP_PLAN 15,
//: row 5: at 390 the bar shows 6 controls and 6 of the map palette's 33
//: commands had a way in). The palette's rows (`mapPaletteCommands`), read
//: as the sheet opens so the topic's rows follow the selection, minus any
//: the table's own rows already name; not a second menu.
function wbSyncMoreMapRows(menu, map) {
  for (const old of menu.querySelectorAll(".wb-more-map")) old.remove();
  if (!map || typeof mapPaletteCommands !== "function") return;
  const words = (label) => label.replace(/^ph:[\w-]+\s+/, "").replace(/…$/, "").trim().toLowerCase();
  const named = new Set();
  for (const row of menu.querySelectorAll("[data-wb-cmd]")) {
    const command = WB_COMMAND_BY_ID.get(row.dataset.wbCmd);
    if (command && command.surface !== "board") named.add(words(command.label));
  }
  let group = null;
  for (const command of mapPaletteCommands()) {
    if (named.has(words(command.label))) continue;
    if (command.group !== group) {
      const rule = document.createElement("div");
      rule.className = "menu-sep wb-more-map";
      rule.setAttribute("role", "separator");
      menu.append(rule);
      group = command.group;
    }
    const row = document.createElement("button");
    row.type = "button";
    row.className = "menu-item wb-more-map";
    row.setAttribute("role", "menuitem");
    setLabel(row, command.label);
    if (command.keys) row.title = `${words(command.label)} (${command.keys})`;
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActionMenus();
      command.run();
    });
    menu.append(row);
  }
}

function wbInitMoreMenu() {
  const bar = document.querySelector("#wb-topbar .wb-topbar-right");
  if (!bar || document.getElementById("wb-more-toggle") || typeof kebabMenu !== "function") return;
  const wrap = kebabMenu(
    WB_COMMANDS.map((command) => ({
      label: `${command.icon} ${command.label}`,
      title: command.keys ? `${command.label} (${command.keys})` : command.label,
      group: command.group,
      run: () => wbRunCommand(command.id),
    })),
    "More board commands"
  );
  wrap.classList.add("wb-more-wrap");
  const menu = wrap.querySelector(".action-menu");
  menu.id = "wb-more-menu";
  menu.querySelectorAll(".menu-item").forEach((row, i) => {
    row.dataset.wbCmd = WB_COMMANDS[i].id;
  });
  const opener = wrap.querySelector(".kebab-opener");
  opener.id = "wb-more-toggle";
  //: Capture, so the rows are right before `kebabMenu`'s own listener opens
  //: the menu or moves it into the sheet.
  opener.addEventListener("click", () => wbSyncMoreMenu(menu), true);
  bar.append(wrap);
}

// --- The board's help and shortcut sheet (INBOX 566) ------------------------
//
// The owner: "the whiteboard help popup is still cooked and needs a redesign".
// The old card was a three-column grid of `label · key` rows set `nowrap`, so
// a long label ran under its keys and the right column ran out of the card
// (UX-03, measured). This is the dialog recipe instead: a head with its X and
// '?', one line, a search field, and sections of rows. A row is a grid of the
// icon, the words (they wrap first) and a fixed key column whose caps wrap
// inside it, so nothing can overlap. A row that names a `cmd` takes its words,
// icon and key from `WB_COMMANDS`, so the sheet cannot drift from the menus.

//: `cmd` rows read the table; the others are gestures the table has no row
//: for. `keys` is a list of alternatives, each drawn as one cap.
const WB_HELP_SECTIONS = [
  { title: "Mind map", surface: "map", rows: [
    { icon: "ph:plus", label: "Add a child, a topic beside it", keys: ["Tab", "Enter"] },
    { icon: "ph:arrow-left", label: "Outdent a branch", keys: ["Shift+Tab"] },
    { icon: "ph:arrows-out-cardinal", label: "Walk the tree", keys: ["arrows"] },
    { icon: "ph:pencil-simple", label: "Rename a topic", keys: ["F2", "double-click"] },
    { icon: "ph:trash", label: "Delete the topic and its branch", keys: ["Delete"] },
    { icon: "ph:caret-down", label: "Fold or open a branch", keys: ["C"] },
    { icon: "ph:list-dashes", label: "Show that many levels", keys: ["Alt+1 to 9"] },
    { icon: "ph:crosshair", label: "Focus here, show all again", keys: ["F"] },
    { icon: "ph:dots-three", label: "The topic's whole menu", keys: ["Shift+F10"] },
    { icon: "ph:text-aa", label: "Label a line", keys: ["double-click it"] },
    { icon: "ph:line-segment", label: "Straighten a line", keys: ["double-click its grip"] },
  ] },
  { title: "Tools", surface: "both", rows: [
    { cmd: "tool-select" }, { cmd: "tool-pan" }, { cmd: "tool-lasso" }, { cmd: "tool-pen" },
    { cmd: "tool-highlighter" }, { cmd: "tool-eraser" }, { cmd: "tool-fill" }, { cmd: "tool-line" },
    { cmd: "tool-arrow" }, { cmd: "tool-rect" }, { cmd: "tool-circle" }, { cmd: "tool-triangle" },
    { cmd: "tool-diamond" }, { cmd: "insert-text" }, { cmd: "insert-sticky" }, { cmd: "insert-frame" },
    { cmd: "insert-image" }, { cmd: "tool-connector" }, { cmd: "tool-connector-curved" }, { cmd: "tool-delete" },
  ] },
  { title: "Move around", surface: "both", rows: [
    { icon: "ph:hand", label: "Pan", keys: ["wheel", "two fingers", "middle drag"] },
    { icon: "ph:arrows-horizontal", label: "Pan sideways", keys: ["Shift+wheel"] },
    { icon: "ph:hand-grabbing", label: "Pan with any tool", keys: ["Space+drag"] },
    { icon: "ph:magnifying-glass-plus", label: "Zoom", keys: ["Ctrl+wheel", "pinch"] },
    { cmd: "zoom-in" }, { cmd: "zoom-out" }, { cmd: "zoom-100" }, { cmd: "zoom-fit" },
    { cmd: "overview" }, { cmd: "find" },
    { icon: "ph:keyboard", label: "Walk the board's items", keys: ["Tab", "Shift+Tab"] },
  ] },
  { title: "Select and edit", surface: "both", rows: [
    { icon: "ph:cursor-click", label: "Add to the selection", keys: ["Shift+click"] },
    { cmd: "select-all" }, { cmd: "undo" }, { cmd: "redo" },
    { icon: "ph:clipboard", label: "Copy, paste at the pointer", keys: ["Ctrl+C", "Ctrl+V"] },
    { icon: "ph:clipboard-text", label: "Paste text from another app: a list becomes stickies", keys: ["Ctrl+V"] },
    { cmd: "cut" }, { cmd: "duplicate" },
    { icon: "ph:copy", label: "Copy as you drag", keys: ["Alt+drag"] },
    { cmd: "delete" },
    { icon: "ph:trash", label: "Delete by dropping on the target at the foot (a topic takes its branch)", keys: ["drag"] },
    { icon: "ph:arrows-out-cardinal", label: "Nudge, further", keys: ["arrows", "Shift+arrows"] },
    { icon: "ph:x", label: "Cancel a drag, back to Select", keys: ["Esc"] },
    { icon: "ph:text-t", label: "A text box on the empty board", keys: ["double-click"] },
    { cmd: "text" },
    { cmd: "copy-style" }, { cmd: "paste-style" },
    { icon: "ph:dots-three", label: "The item's or the board's menu", keys: ["right-click", "hold"] },
  ] },
  { title: "Arrange", surface: "board", rows: [
    { cmd: "order-forward" }, { cmd: "order-backward" }, { cmd: "order-front" }, { cmd: "order-back" },
    { cmd: "group" }, { cmd: "ungroup" }, { cmd: "lock" },
    { icon: "ph:lock-simple-open", label: "Unlock everything", keys: ["Ctrl+Shift+L with nothing selected"] },
    { icon: "ph:arrows-left-right", label: "Keep to one axis", keys: ["Shift+drag"] },
    { icon: "ph:corners-out", label: "Keep proportions", keys: ["Shift+corner"] },
    { icon: "ph:arrows-out", label: "Resize from the centre", keys: ["Alt+handle"] },
    { icon: "ph:arrows-in-simple", label: "Fit the box to its text", keys: ["double-click a corner"] },
    { icon: "ph:arrow-clockwise", label: "Rotate, upright again", keys: ["the handle above it", "double-click it"] },
    { icon: "ph:bezier-curve", label: "Bend a line", keys: ["double-click it"] },
    { icon: "ph:text-aa", label: "Label a line", keys: ["select it, Enter"] },
  ] },
  { title: "View", surface: "both", rows: [
    { icon: "ph:presentation", label: "Present frames (View menu): next, end", keys: ["arrows", "Esc"] },
    { icon: "ph:keyboard", label: "This sheet", keys: ["?"] },
    { icon: "ph:command", label: "Find any action by name", keys: ["Ctrl+K"] },
  ] },
];

//: The rows of one section as they read now: a `cmd` row from the table.
function wbHelpRows(section) {
  return section.rows
    .map((row) => {
      if (!row.cmd) return row;
      const command = WB_COMMAND_BY_ID.get(row.cmd);
      if (!command || !command.keys) return null;
      return { icon: command.icon, label: command.label, keys: [command.keys] };
    })
    .filter(Boolean);
}

function wbHelpSections() {
  const map = wbIsMap();
  return WB_HELP_SECTIONS.filter((s) => s.surface === "both" || s.surface === (map ? "map" : "board"));
}

//: Draws the sheet, filtered by `query` (words or keys, any order).
function wbRenderHelpSheet(query = "") {
  const host = document.getElementById("wb-help-sections");
  if (!host) return;
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (row) => {
    const text = `${row.label} ${row.keys.join(" ")}`.toLowerCase();
    return words.every((w) => text.includes(w));
  };
  host.replaceChildren();
  let shown = 0;
  for (const section of wbHelpSections()) {
    const rows = wbHelpRows(section).filter(matches);
    if (!rows.length) continue;
    const box = document.createElement("section");
    box.className = "wb-help-section";
    const head = document.createElement("h3");
    head.className = "wb-help-section-head";
    head.textContent = section.title;
    const list = document.createElement("ul");
    list.className = "wb-help-list";
    list.setAttribute("aria-label", section.title);
    for (const row of rows) {
      const li = document.createElement("li");
      li.className = "wb-help-row";
      const icon = document.createElement("i");
      icon.className = `ph ${row.icon.replace(/^ph:/, "ph-")} wb-help-row-icon`;
      icon.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.className = "wb-help-row-label";
      label.textContent = row.label;
      const keys = document.createElement("span");
      keys.className = "wb-help-row-keys";
      for (const key of row.keys) {
        const kbd = document.createElement("kbd");
        kbd.textContent = key;
        keys.append(kbd);
      }
      li.append(icon, label, keys);
      list.append(li);
      shown += 1;
    }
    box.append(head, list);
    host.append(box);
  }
  document.getElementById("wb-help-none")?.classList.toggle("hidden", shown > 0);
}

const wbHelpReturn = { focus: null };

function wbOpenHelpSheet() {
  const overlay = document.getElementById("wb-help-overlay");
  if (!overlay) return;
  wbHelpReturn.focus = document.activeElement;
  const search = document.getElementById("wb-help-search");
  if (search) search.value = "";
  wbRenderHelpSheet("");
  overlay.classList.remove("hidden");
  document.getElementById("wb-help-sections")?.scrollTo?.(0, 0);
  search?.focus();
}

function wbCloseHelpSheet() {
  const overlay = document.getElementById("wb-help-overlay");
  if (!overlay || overlay.classList.contains("hidden")) return;
  overlay.classList.add("hidden");
  const back = wbHelpReturn.focus;
  wbHelpReturn.focus = null;
  if (back && back.isConnected && typeof back.focus === "function") back.focus();
}

//: Wired once, when this file arrives with the Library bundle.
onDomReady(() => {
  wbInitMoreMenu();
  const overlay = document.getElementById("wb-help-overlay");
  if (!overlay) return;
  document.getElementById("wb-help-close")?.addEventListener("click", wbCloseHelpSheet);
  document.getElementById("wb-help-search")?.addEventListener("input", (e) => wbRenderHelpSheet(e.target.value));
  wireBackdropClose(overlay, wbCloseHelpSheet);
  //: Escape closes the sheet and nothing behind it (the board would drop its
  //: selection on the same key otherwise); a first Escape in a typed search
  //: clears the search instead.
  overlay.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    const search = document.getElementById("wb-help-search");
    if (search && search.value && document.activeElement === search) {
      search.value = "";
      wbRenderHelpSheet("");
      return;
    }
    wbCloseHelpSheet();
  });
});
