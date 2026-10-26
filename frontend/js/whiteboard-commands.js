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
  tree: () => wbTidyEdges(wbSelectionEntries()).length > 0,
  swappable: () => Boolean(wbSwapTarget()),
  joinable: () => wbJoinableEntries().length >= 2,
  linkable: () => wbMultiSelection.size <= 1 && Boolean(wbSelectedItem) && wbTakesLink(wbSelectedItem.kind, wbFindItem(wbSelectedItem.kind, wbSelectedItem.id)),
  two: () => wbCommandSelectionCount() >= 2,
  three: () => wbCommandSelectionCount() >= 3,
  one: () => wbCommandSelectionCount() === 1,
  copied: () => Boolean(wbClipboard),
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
  reversible: () => wbFmtEntries().some((e) => e.kind === "sketch" && ["link", "arrow"].includes(wbFmtKind(e))),
  bent: () => wbFmtEntries().some((e) => {
    const parsed = e.kind === "sketch" && wbFmtKind(e) === "link" ? wbFmtSketch(e) : null;
    return Boolean(parsed?.points?.length || parsed?.bend);
  }),
  grouped: () => wbFmtEntries().some((e) => e.item.group_id),
  //: The bar's own rule (`wbGroupButtonState`), so the menus, the palette and
  //: the bar never offer both.
  flippable: () => wbFmtEntries().some((e) => e.kind === "sketch" && ["shape", "line", "arrow"].includes(wbFmtKind(e)) && !wbIsLocked(e.kind, e.item)),
  groupable: () => wbGroupButtonState(wbSelectionEntries().map((e) => e.item)).canGroup,
  ungroupable: () => wbGroupButtonState(wbSelectionEntries().map((e) => e.item)).canUngroup,
  sizeCopied: () => wbFmtState.sizeClip !== null && wbCommandSelectionCount() > 0,
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
  { id: "select-shapes", group: "Edit", icon: "ph:selection-all", label: "Select all shapes", keys: "", surface: "board", run: () => wbSelectAllOfKind("shapes") },
  { id: "select-connectors", group: "Edit", icon: "ph:selection-all", label: "Select all connectors", keys: "", surface: "board", run: () => wbSelectAllOfKind("connectors") },
  { id: "select-similar", group: "Edit", icon: "ph:selection-plus", label: "Select similar", keys: "", surface: "board", needs: "selection", run: () => wbSelectSimilar() },
  { id: "copy", group: "Edit", icon: "ph:copy-simple", label: "Copy", keys: "Ctrl+C", surface: "board", needs: "selection", run: () => wbCopySelection() },
  { id: "cut", group: "Edit", icon: "ph:scissors", label: "Cut", keys: "Ctrl+X", surface: "board", needs: "selection", run: () => wbCutSelection() },
  { id: "paste", group: "Edit", icon: "ph:clipboard", label: "Paste", keys: "Ctrl+V", surface: "board", run: () => wbPasteClipboard() },
  { id: "paste-in-place", group: "Edit", icon: "ph:clipboard", label: "Paste in place", keys: "Ctrl+Shift+V", surface: "board", run: () => wbPasteClipboard({ inPlace: true }) },
  { id: "paste-special", group: "Edit", icon: "ph:clipboard-text", label: "Paste special", keys: "", surface: "both", run: () => wbPasteSpecialMenu() },
  { id: "paste-into-shape", group: "Edit", icon: "ph:clipboard-text", label: "Paste into the selected shape's text", menu: "Paste into the shape's text", keys: "", surface: "board", needs: "shape", run: () => wbPasteIntoShape() },
  { id: "paste-no-comments", group: "Edit", icon: "ph:clipboard", label: "Paste without comments", keys: "", surface: "board", needs: "copied", run: () => wbPasteClipboard({ noComments: true }) },
  { id: "duplicate", group: "Edit", icon: "ph:copy", label: "Duplicate", keys: "Ctrl+D", surface: "both", needs: "selection", run: () => wbDuplicateSelection() },
  { id: "delete", group: "Edit", icon: "ph:trash", label: "Delete", keys: "Del", surface: "both", needs: "selection", run: () => deleteWbSelection() },
  { id: "copy-style", group: "Edit", icon: "ph:eyedropper", label: "Copy style", keys: "Ctrl+Alt+C", surface: "board", needs: "one", run: () => wbCopySelectedStyle() },
  { id: "paste-style", group: "Edit", icon: "ph:paint-bucket", label: "Paste style", keys: "Ctrl+Alt+V", surface: "board", needs: "selection", run: () => wbPasteCopiedStyle() },
  { id: "reset-style", group: "Edit", icon: "ph:arrow-counter-clockwise", label: "Reset style", keys: "", surface: "both", needs: "selection", run: () => wbResetSelectedStyle() },
  { id: "clear-format", group: "Edit", icon: "ph:text-t-slash", label: "Clear text formatting", keys: "", surface: "board", needs: "selection", run: () => wbClearTextFormat() },
  { id: "font-bigger", group: "Edit", icon: "ph:text-aa", label: "Make the text larger", keys: "", surface: "board", needs: "selection", run: () => wbStepFontSize(1) },
  { id: "font-smaller", group: "Edit", icon: "ph:text-aa", label: "Make the text smaller", keys: "", surface: "board", needs: "selection", run: () => wbStepFontSize(-1) },
  { id: "copy-size", group: "Edit", icon: "ph:ruler", label: "Copy the size", keys: "", surface: "board", needs: "one", run: () => wbCopySize() },
  { id: "paste-size", group: "Edit", icon: "ph:ruler", label: "Paste the size", keys: "", surface: "board", needs: "sizeCopied", run: () => wbPasteSize() },
  { id: "auto-size", group: "Edit", icon: "ph:arrows-out", label: "Grow to fit the words", keys: "", surface: "board", needs: "selection", run: () => wbAutoSizeSelection() },
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
  { id: "reverse", group: "Item", icon: "ph:arrows-left-right", label: "Reverse the connector or arrow", keys: "", surface: "board", needs: "reversible", run: () => wbReverseSelection() },
  { id: "clear-waypoints", group: "Item", icon: "ph:bezier-curve", label: "Clear the connector's bends", keys: "", surface: "board", needs: "bent", run: () => wbClearWaypoints() },
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
  { id: "insert-parent", group: "Item", icon: "ph:arrow-elbow-left-up", label: "Insert a parent topic", keys: "Ctrl+Enter", surface: "map", needs: "topic", run: () => wbMapInsertParent(wbSelectedMapNode()?.id) },
  { id: "sort-az", group: "Item", icon: "ph:sort-ascending", label: "Sort branches A to Z", keys: "", surface: "map", needs: "topic", run: () => wbMapSortChildren(wbSelectedMapNode()?.id, 1) },
  { id: "sort-za", group: "Item", icon: "ph:sort-descending", label: "Sort branches Z to A", keys: "", surface: "map", needs: "topic", run: () => wbMapSortChildren(wbSelectedMapNode()?.id, -1) },
  { id: "dim-branch", group: "View", icon: "ph:circle-half", label: "Dim all but the selected branch", keys: "", surface: "map", run: () => wbMapSetDim(!wbMapDim.on) },
  { id: "copy-branch-outline", group: "Item", icon: "ph:copy", label: "Copy this branch as an outline", keys: "", surface: "map", needs: "topic", run: () => wbMapCopyBranchOutline(wbSelectedMapNode()?.id) },
  { id: "export-branch", group: "Item", icon: "ph:export", label: "Export this branch…", keys: "", surface: "map", needs: "topic", run: () => wbMapExportBranch(wbSelectedMapNode()?.id) },
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
  { id: "key-object", group: "Arrange", icon: "ph:push-pin", label: "Align to this one (key object)", menu: "Align to this one", keys: "", surface: "board", needs: "two", run: () => wbSetKeyObject() },
  { id: "distribute-h", group: "Arrange", icon: "ph:columns", label: "Distribute evenly, left to right", menu: "Evenly, left to right", keys: "", surface: "board", needs: "three", run: () => wbDistributeSelection("horizontal") },
  { id: "distribute-v", group: "Arrange", icon: "ph:rows", label: "Distribute evenly, top to bottom", menu: "Evenly, top to bottom", keys: "", surface: "board", needs: "three", run: () => wbDistributeSelection("vertical") },
  { id: "same-width", group: "Arrange", icon: "ph:arrows-out-line-horizontal", label: "Same width as the widest", menu: "Same width", keys: "", surface: "board", needs: "two", run: () => wbSameSizeSelection("width") },
  { id: "same-height", group: "Arrange", icon: "ph:arrows-out-line-vertical", label: "Same height as the tallest", menu: "Same height", keys: "", surface: "board", needs: "two", run: () => wbSameSizeSelection("height") },
  { id: "tidy-down", group: "Arrange", icon: "ph:tree-structure", label: "Tidy as a tree, top to bottom", menu: "Top to bottom", keys: "", surface: "board", needs: "tree", run: () => wbTidySelection("down") },
  { id: "tidy-right", group: "Arrange", icon: "ph:tree-view", label: "Tidy as a tree, left to right", menu: "Left to right", keys: "", surface: "board", needs: "tree", run: () => wbTidySelection("right") },
  { id: "join-chain", group: "Arrange", icon: "ph:arrow-elbow-down-right", label: "Connect the selected in a line, one to the next", menu: "In a line", keys: "", surface: "board", needs: "joinable", run: () => wbJoinSelection("chain") },
  { id: "join-fan", group: "Arrange", icon: "ph:share-network", label: "Connect the selected to the first one picked", menu: "All to the first picked", keys: "", surface: "board", needs: "joinable", run: () => wbJoinSelection("fan") },
  { id: "change-shape", group: "Arrange", icon: "ph:shapes", label: "Change the shape to another kind…", menu: "Change the shape…", keys: "", surface: "board", needs: "swappable", run: () => wbOpenShapeSwapMenu() },
  { id: "text-fit", group: "Edit", icon: "ph:arrows-in-simple", label: "Shrink the text to fit the shape (on or off)", keys: "", surface: "board", needs: "swappable", run: () => wbToggleLabelFit() },
  { id: "item-link", group: "Edit", icon: "ph:link-simple", label: "Link to a note or a web page…", menu: "Link…", keys: "", surface: "board", needs: "linkable", run: () => wbEditItemLink() },
  { id: "group", group: "Arrange", icon: "ph:link", label: "Group", keys: "Ctrl+G", surface: "board", needs: "groupable", run: () => wbGroupSelection() },
  { id: "ungroup", group: "Arrange", icon: "ph:link-break", label: "Ungroup", keys: "Ctrl+Shift+G", surface: "board", needs: "ungroupable", run: () => wbUngroupSelection() },
  { id: "remove-from-group", group: "Arrange", icon: "ph:link-break", label: "Remove from the group", keys: "", surface: "board", needs: "grouped", run: () => wbRemoveFromGroup() },
  //: draw.io's Arrange, Flip (Figma's Shift+H and Shift+V): only in the
  //: Format panel before, two presses deep.
  { id: "flip-h", group: "Arrange", icon: "ph:flip-horizontal", label: "Flip left to right", keys: "Shift+H", surface: "board", needs: "flippable", run: () => wbFmtFlip("h") },
  { id: "flip-v", group: "Arrange", icon: "ph:flip-vertical", label: "Flip top to bottom", keys: "Shift+V", surface: "board", needs: "flippable", run: () => wbFmtFlip("v") },
  { id: "turn-90", group: "Arrange", icon: "ph:arrow-clockwise", label: "Turn 90 degrees", keys: "", surface: "board", needs: "selection", run: () => wbTurnSelection(90) },
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
  { id: "format-panel", group: "View", icon: "ph:sliders-horizontal", label: "Format panel (top bar button)", menu: "Format panel", keys: "Ctrl+Shift+P", surface: "board", run: () => wbFormatToggle() },
  { id: "zoom-in", group: "View", icon: "ph:magnifying-glass-plus", label: "Zoom in", keys: "Ctrl+=", surface: "both", run: wbClickId("wb-zoom-in") },
  { id: "zoom-out", group: "View", icon: "ph:magnifying-glass-minus", label: "Zoom out", keys: "Ctrl+-", surface: "both", run: wbClickId("wb-zoom-out") },
  { id: "zoom-100", group: "View", icon: "ph:magnifying-glass", label: "Zoom to 100%", keys: "Ctrl+0", surface: "both", run: wbClickId("wb-zoom-actual") },
  { id: "zoom-fit", group: "View", icon: "ph:frame-corners", label: "Fit everything", keys: "Shift+1", surface: "both", run: () => wbZoomToFit() },
  { id: "zoom-selection", group: "View", icon: "ph:selection", label: "Zoom to the selection", keys: "Shift+2", surface: "both", needs: "selection", run: () => wbZoomToSelection() },
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
  { id: "copy-image", group: "Board", icon: "ph:copy", label: "Copy as an image", keys: "", surface: "both", run: () => wbCopyAsImage() },
  { id: "copy-svg", group: "Board", icon: "ph:code", label: "Copy as SVG", keys: "", surface: "both", run: () => wbCopyAsSvg() },
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
      groupable: "Select two or more items that are not already one group first.",
      flippable: "Select a drawn shape or line first.",
      ungroupable: "Select a group first.",
      three: "Select three or more items first.",
      tree: "Select two or more shapes and the connectors between them first.",
      swappable: "Select one closed shape first.",
      joinable: "Select two or more shapes, text boxes or notes first.",
      linkable: "Select one shape, text box or picture first.",
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
  //: **Rows that are one or the other** (`data-wb-either`, Group and
  //: Ungroup): only the one that applies is shown; when neither does, the
  //: first stays, greyed, so the menu still says the action exists.
  const pair = [...menu.querySelectorAll("[data-wb-either]")];
  if (pair.length) {
    const live = pair.filter((row) => row.getAttribute("aria-disabled") === "false");
    pair.forEach((row, i) => { row.hidden = live.length ? !live.includes(row) : i > 0; });
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
    { cmd: "insert-parent" },
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
    { icon: "ph:hand", label: "Pan", keys: ["H then drag", "middle drag", "two-finger scroll"] },
    { icon: "ph:arrows-horizontal", label: "Pan sideways", keys: ["Shift+wheel"] },
    { icon: "ph:hand-grabbing", label: "Pan with any tool", keys: ["Space+drag"] },
    { icon: "ph:magnifying-glass-plus", label: "Zoom", keys: ["wheel", "pinch"] },
    { cmd: "zoom-in" }, { cmd: "zoom-out" }, { cmd: "zoom-100" }, { cmd: "zoom-fit" },
    { cmd: "overview" }, { cmd: "find" },
    { icon: "ph:keyboard", label: "Walk the board's items", keys: ["Tab", "Shift+Tab"] },
  ] },
  { title: "Select and edit", surface: "both", rows: [
    { icon: "ph:cursor-click", label: "Add to the selection", keys: ["Shift+click"] },
    { cmd: "select-all" }, { cmd: "undo" }, { cmd: "redo" },
    { icon: "ph:clipboard", label: "Copy, paste at the pointer", keys: ["Ctrl+C", "Ctrl+V"] },
    { icon: "ph:clipboard-text", label: "Paste text from another app: a list becomes stickies", keys: ["Ctrl+V"] },
    { icon: "ph:note", label: "Next sticky beside this one, while typing in one", keys: ["Ctrl+Enter"] },
    { cmd: "cut" }, { cmd: "duplicate" },
    { icon: "ph:copy", label: "Copy as you drag", keys: ["Alt+drag"] },
    { cmd: "delete" },
    { icon: "ph:trash", label: "Delete by dropping on the target at the foot (a topic takes its branch)", keys: ["drag"] },
    { icon: "ph:arrows-out-cardinal", label: "Nudge, further", keys: ["arrows", "Shift+arrows"] },
    { icon: "ph:arrows-out-simple", label: "Resize from the top-left corner", keys: ["Ctrl+Shift+arrows"] },
    { icon: "ph:x", label: "Cancel a drag, back to Select", keys: ["Esc"] },
    { icon: "ph:text-t", label: "A text box on the empty board", keys: ["double-click"] },
    { cmd: "text" },
    { cmd: "copy-style" }, { cmd: "paste-style" },
    { icon: "ph:dots-three", label: "The item's or the board's menu", keys: ["right-click", "hold"] },
  ] },
  { title: "Arrange", surface: "board", rows: [
    { cmd: "order-forward" }, { cmd: "order-backward" }, { cmd: "order-front" }, { cmd: "order-back" },
    { cmd: "group" }, { cmd: "ungroup" }, { cmd: "lock" }, { cmd: "flip-h" }, { cmd: "flip-v" },
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


// --- Connect the selected (WHITEBOARD_PLAN 1355) ------------------------------
//
// The owner, 2026-10-26: "what about linking". A connector was only drawn by
// hand, end to end. These join what is selected in one step: in a line (each to
// the next, in reading order) or all to the first one picked, each joined side
// to the facing side, one undo step. A pair already joined is left alone.

function wbJoinableEntries() {
  if (wbIsMap() || wbMultiSelection.size < 2) return [];
  const ok = new Set(wbLinkCandidates().map(([kind, item]) => `${kind}:${item.id}`));
  return wbSelectionEntries().filter((e) => ok.has(`${e.kind}:${e.id}`));
}

function wbJoinedPairs() {
  const pairs = new Set();
  for (const s of wbState.sketches || []) {
    const p = wbIsLinkSketch(s) ? wbSketchParsedData({ data: s.data }) || JSON.parse(s.data) : null;
    if (p && p.sourceId != null && p.targetId != null) pairs.add(`${p.sourceKind || "node"}:${p.sourceId}>${p.targetKind || "node"}:${p.targetId}`);
  }
  return pairs;
}

//: The sides that face: the wider gap between the two centres decides.
function wbFacingAnchors(a, b) {
  const dx = (b.bbox.minX + b.bbox.maxX - a.bbox.minX - a.bbox.maxX) / 2;
  const dy = (b.bbox.minY + b.bbox.maxY - a.bbox.minY - a.bbox.maxY) / 2;
  const [ux, uy] = Math.abs(dx) >= Math.abs(dy) ? [Math.sign(dx) || 1, 0] : [0, Math.sign(dy) || 1];
  return { sourceAnchor: { x: 0.5 + ux / 2, y: 0.5 + uy / 2 }, targetAnchor: { x: 0.5 - ux / 2, y: 0.5 - uy / 2 } };
}

function wbJoinPlan(entries, mode) {
  if (mode === "fan") {
    const [first, ...rest] = entries;
    return rest.map((e) => [first, e]);
  }
  const wide = Math.max(...entries.map((e) => e.bbox.minX)) - Math.min(...entries.map((e) => e.bbox.minX))
    >= Math.max(...entries.map((e) => e.bbox.minY)) - Math.min(...entries.map((e) => e.bbox.minY));
  const key = (e) => (wide ? e.bbox.minX : e.bbox.minY);
  const sorted = [...entries].sort((p, q) => key(p) - key(q));
  return sorted.slice(1).map((e, i) => [sorted[i], e]);
}

async function wbJoinSelection(mode) {
  const entries = wbJoinableEntries();
  if (entries.length < 2) {
    toast("Select two or more shapes, text boxes or notes first.");
    return;
  }
  const have = wbJoinedPairs();
  const end = (e) => `${e.kind}:${e.id}`;
  const plan = wbJoinPlan(entries, mode).filter(([a, b]) => !have.has(`${end(a)}>${end(b)}`) && !have.has(`${end(b)}>${end(a)}`));
  if (!plan.length) {
    toast("Those are already joined.");
    return;
  }
  const color = window.currentStrokeColor || "#888888";
  await wbRecordGesture(async () => {
    for (const [a, b] of plan) {
      const data = {
        type: "link-straight", route: "elbow", color, width: 2, endCap: "arrow",
        sourceId: a.id, targetId: b.id, ...wbFacingAnchors(a, b),
      };
      if (a.kind !== "node") data.sourceKind = a.kind;
      if (b.kind !== "node") data.targetKind = b.kind;
      const link = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: 1, board_id: window.currentBoardId ?? null }),
      });
      wbState.sketches.push(link);
    }
  });
  wbScheduleRender();
  wbAnnounce(`Joined ${plan.length} pair${plan.length === 1 ? "" : "s"}.`);
}

// --- Pasting onto a board or a map, and Paste special (wbpaste-1026) ---
//
// The owner, 2026-10-26, after the document editor got paste options: "Same on
// the whiteboard". Before this a text paste was one thing (a link box, a text
// box, or a grid of stickies by line count) and the only other choice was to
// undo and paste again. Now a paste that changed form leaves a small chip
// beside what it made, offering the other readings of the same clipboard
// (stickies, one text box, a bullet list in a shape, a mind map branch, a
// table, plain text), each applied as one undo step; Paste special in the Edit
// menu and the palette applies one on purpose. The readings of the text itself
// (rows and columns, indentation, list marks) are documents-prose.js's `paste*` functions, shared with
// the document editor; this file is the board's half. The pure half runs in
// node (tests/test_wb_paste_text.py); the wiring is driven by
// scratchpad/ui-sweeps/wbpaste.js. It sits in this file, after the command
// table, because app.js's gzip cap leaves no room for another script line.

// WB-PASTE-PURE-START
const WB_PASTE_STICKY = { w: 180, h: 140, gap: 24 };
const WB_PASTE_MAX_STICKIES = 100;
const WB_PASTE_MAX_BRANCH = 100;
const WB_PASTE_MAX_ROWS = 100;
const WB_PASTE_MAX_COLS = 26;
const WB_PASTE_TABLE = { colW: 120, rowH: 40 };
const WB_PASTE_BRANCH = { w: 180, h: 56, gapX: 64, gapY: 16 };
const WB_PASTE_LABELS = {
  stickies: "Stickies",
  textbox: "One text box",
  bullets: "Bullet list in a shape",
  branch: "Mind map branch",
  table: "Table",
  plain: "Plain text",
  link: "As a link",
  url: "Web address only",
};
const WB_PASTE_KEYS = { stickies: "s", textbox: "t", bullets: "b", branch: "m", table: "a", plain: "p", link: "l", url: "u" };

//: A pasted text's lines, list marks taken off.
function wbPastedLines(text) {
  return pasteClean(text).split("\n").map(pasteStripMark).filter(Boolean);
}

//: What a pasted text becomes by default: `{kind: "link" | "text" | "stickies" |
//: "table", ...}`. Pure, so the rule can be tested without a board. A spreadsheet
//: copy (tabs) is a table; a CSV is offered as one by the chip.
function wbPastePlan(text) {
  const lines = wbPastedLines(text);
  if (!lines.length) return null;
  const grid = /\t/.test(String(text)) ? pasteGrid(text) : null;
  if (grid) return { kind: "table", grid };
  if (lines.length === 1 && /^https?:\/\/\S+$/i.test(lines[0])) return { kind: "link", url: lines[0] };
  if (lines.length === 1) return { kind: "text", text: lines[0] };
  if (lines.length > 50) return { kind: "text", text: lines.join("\n") };
  return { kind: "stickies", lines };
}

//: The readings of this clipboard, the default first. One line of plain words
//: has only itself, so it gets no chip.
function wbPasteVariants(text) {
  const plan = wbPastePlan(text);
  if (!plan) return [];
  const lines = wbPastedLines(text);
  const out = [{ link: "link", text: "textbox", stickies: "stickies", table: "table" }[plan.kind]];
  const add = (id, ok) => {
    if (ok && !out.includes(id)) out.push(id);
  };
  if (plan.kind === "link") {
    add("url", true);
    return out;
  }
  add("stickies", lines.length >= 2 && lines.length <= WB_PASTE_MAX_STICKIES);
  add("textbox", true);
  add("bullets", lines.length >= 2);
  add("branch", lines.length >= 2);
  add("table", Boolean(pasteGrid(text)));
  add("plain", pasteClean(text) !== lines.join("\n"));
  return out;
}

function wbPasteObject(key, kind, data, x, y, width, height, z = 1) {
  return { kind: "object", key, payload: { kind, data, x: Math.round(x), y: Math.round(y), z, width: Math.round(width), height: Math.round(height), rotation: null, group_id: null } };
}

function wbPasteSketch(key, data, extra = {}) {
  return { kind: "sketch", key, payload: { data: JSON.stringify(data), x: 0, y: 0, z: 1, group_id: null }, ...extra };
}

function wbPasteLinkLabel(url) {
  try {
    const u = new URL(url);
    return (u.host + u.pathname).replace(/\/$/, "");
  } catch {
    return url;
  }
}

function wbPasteTextBoxItem(content, cx, cy, extra = {}) {
  const width = 320;
  const rows = Math.min(30, Math.ceil(content.length / 40) + content.split("\n").length - 1);
  const height = Math.min(800, 24 + rows * 22);
  return wbPasteObject("t0", "text", { content, ...extra }, cx - width / 2, cy - height / 2, width, height);
}

function wbPasteStickyItems(lines, cx, cy, paper) {
  const cols = Math.min(5, Math.ceil(Math.sqrt(lines.length)));
  const rowsN = Math.ceil(lines.length / cols);
  const { w, h, gap } = WB_PASTE_STICKY;
  const left = cx - (cols * w + (cols - 1) * gap) / 2;
  const top = cy - (rowsN * h + (rowsN - 1) * gap) / 2;
  return lines.map((line, i) => wbPasteObject(
    `s${i}`, "text", { content: line.slice(0, 2000), sticky: true, bg: paper, color: "#2a2a1f", font_size: 16 },
    left + (i % cols) * (w + gap), top + Math.floor(i / cols) * (h + gap), w, h
  ));
}

//: Rows and columns as one table object (`WB_TABLE_*` in whiteboard-format.js
//: is the same 120 by 40 cell), padded to a rectangle and clipped to what a
//: board can hold.
function wbPasteTableItem(grid, cx, cy) {
  const rows = grid.slice(0, WB_PASTE_MAX_ROWS);
  const cols = Math.min(WB_PASTE_MAX_COLS, Math.max(...rows.map((r) => r.length)));
  const cells = rows.map((r) => Array.from({ length: cols }, (_, c) => String(r[c] || "").slice(0, 500)));
  const w = cols * WB_PASTE_TABLE.colW;
  const h = rows.length * WB_PASTE_TABLE.rowH;
  return wbPasteObject("t0", "table", { cells, header: rows.length > 1 }, cx - w / 2, cy - h / 2, w, h, 2);
}

//: The lines as bullets inside one rounded-off rectangle's label.
function wbPasteBulletShape(lines, cx, cy, ink) {
  const longest = Math.max(...lines.map((l) => l.length));
  const w = Math.max(200, Math.min(420, longest * 8 + 56));
  const h = Math.min(800, lines.length * 26 + 44);
  const x = Math.round(cx - w / 2);
  const y = Math.round(cy - h / 2);
  const label = lines.map((l) => `• ${l.slice(0, 300)}`).join("\n");
  return wbPasteSketch("b0", { d: `M ${x} ${y} h ${w} v ${h} h ${-w} Z`, shape: "rect", color: ink, width: 2, label, label_align: "left" });
}

//: The outline as a tree, `{text, depth, parent}` in reading order. A paste of
//: several top-level lines takes the first as the root and the rest as its
//: branches; one top-level line is the root already.
function wbPasteTree(text) {
  let rows = pasteOutline(text).slice(0, WB_PASTE_MAX_BRANCH);
  if (rows.filter((r) => r.depth === 0).length > 1) rows = rows.map((r, i) => (i ? { ...r, depth: r.depth + 1 } : r));
  const stack = [];
  return rows.map((row, i) => {
    const depth = i ? Math.max(1, Math.min(row.depth, (stack.length ? stack[stack.length - 1].depth : 0) + 1)) : 0;
    while (stack.length && stack[stack.length - 1].depth >= depth) stack.pop();
    const node = { text: row.text, depth, parent: stack.length ? stack[stack.length - 1].i : -1, i };
    stack.push(node);
    return node;
  });
}

//: Each node's row: leaves take the next free row, a parent sits at the middle
//: of its children (a tidy tree, laid out to the right).
function wbPasteTreeRows(tree) {
  const kids = tree.map(() => []);
  for (const n of tree) if (n.parent >= 0) kids[n.parent].push(n.i);
  let next = 0;
  const rowOf = [];
  const walk = (i) => {
    if (!kids[i].length) rowOf[i] = next++;
    else {
      kids[i].forEach(walk);
      rowOf[i] = (rowOf[kids[i][0]] + rowOf[kids[i][kids[i].length - 1]]) / 2;
    }
  };
  walk(0);
  return { rowOf, rows: Math.max(next, 1) };
}

function wbPasteBranchItems(text, cx, cy, look) {
  const tree = wbPasteTree(text);
  if (!tree.length) return [];
  const { rowOf, rows } = wbPasteTreeRows(tree);
  const { w, h, gapX, gapY } = WB_PASTE_BRANCH;
  const depthMax = Math.max(...tree.map((n) => n.depth));
  const left = cx - ((depthMax + 1) * w + depthMax * gapX) / 2;
  const top = cy - (rows * h + (rows - 1) * gapY) / 2;
  const out = tree.map((n) => wbPasteObject(
    `n${n.i}`, "text",
    { content: n.text.slice(0, 500), sticky: true, bg: n.depth === 0 ? look.root : look.paper, color: "#2a2a1f", font_size: n.depth === 0 ? 18 : 16 },
    left + n.depth * (w + gapX), top + rowOf[n.i] * (h + gapY), w, h
  ));
  for (const n of tree) {
    if (n.parent < 0) continue;
    out.push(wbPasteSketch(`l${n.i}`, {
      type: "link-straight", route: "elbow", sourceAnchor: { x: 1, y: 0.5 }, targetAnchor: { x: 0, y: 0.5 }, color: look.ink, width: 2,
    }, { src: `n${n.parent}`, dst: `n${n.i}` }));
  }
  return out;
}

//: What `id` makes of this clipboard, centred on (cx, cy), as the rows the
//: board's one-request paste takes. `look` is `{paper, root, ink}` (a sticky's
//: paper, the root's paper, the line colour), read off the board by the caller.
function wbPasteBuild(id, text, cx, cy, look) {
  const lines = wbPastedLines(text);
  if (!lines.length) return { items: [], said: "" };
  const make = {
    link: () => [wbPasteTextBoxItem(`[${wbPasteLinkLabel(lines[0]).replace(/[[\]]/g, "")}](${lines[0]})`, cx, cy, { md: true })],
    url: () => [wbPasteTextBoxItem(lines[0], cx, cy)],
    textbox: () => [wbPasteTextBoxItem(lines.join("\n"), cx, cy)],
    plain: () => [wbPasteTextBoxItem(pasteClean(text), cx, cy)],
    stickies: () => wbPasteStickyItems(lines.slice(0, WB_PASTE_MAX_STICKIES), cx, cy, look.paper),
    table: () => {
      const grid = pasteGrid(text);
      return grid ? [wbPasteTableItem(grid, cx, cy)] : [];
    },
    bullets: () => [wbPasteBulletShape(lines, cx, cy, look.ink)],
    branch: () => wbPasteBranchItems(text, cx, cy, look),
  }[id];
  const items = make ? make() : [];
  const things = items.filter((i) => i.kind === "object" || !i.src).length;
  const said = {
    stickies: `Pasted ${things} stickies.`, link: "Pasted a link.", table: "Pasted a table.",
    bullets: "Pasted a bullet list.", branch: `Pasted a branch of ${things} boxes.`,
  }[id] || "Pasted a text box.";
  return { items, said };
}

//: A picture at its own size, shrunk only to sit inside the view (`view` in
//: board units), never stretched.
function wbPasteImageSize(natW, natH, viewW, viewH) {
  const w = natW > 0 ? natW : 300;
  const h = natH > 0 ? natH : 200;
  const fit = Math.min(1, (viewW * 0.9) / w, (viewH * 0.9) / h);
  return { width: Math.max(40, Math.round(w * fit)), height: Math.max(40, Math.round(h * fit)) };
}

//: A map's paste, read two ways: the text as it is (indentation is depth) or
//: all of it as one topic.
function wbMapPasteReading(id, text) {
  if (id !== "oneTopic") return String(text || "");
  return wbPastedLines(text).join(" ");
}
// WB-PASTE-PURE-END

const WB_MAP_PASTE_LABELS = { branches: "Child branches", oneTopic: "One topic" };
const WB_MAP_PASTE_KEYS = { branches: "c", oneTopic: "o" };

//: The mode Paste special armed for the next real paste (the browser would not
//: let the app read the clipboard itself).
let wbPasteArmed = "";
//: The open chip: {el, variants, current, entry, apply, onKey, onKeyUp, onMouse, ctrl}.
let wbPasteChip = null;

function wbPasteLook() {
  return { paper: WB_STICKY_PAPERS[0].value, root: WB_STICKY_PAPERS[4].value, ink: window.currentStrokeColor || "#888888" };
}

function wbBoardToClient(x, y) {
  const origin = wbCanvasOrigin();
  const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
  const s = origin.scale || 1;
  return [origin.left + (x * t.k + t.x) * s, origin.top + (y * t.k + t.y) * s];
}

function wbPasteChipClose() {
  const chip = wbPasteChip;
  if (!chip) return;
  wbPasteChip = null;
  chip.el.remove();
  document.removeEventListener("keydown", chip.onKey, true);
  document.removeEventListener("keyup", chip.onKeyUp, true);
  document.removeEventListener("mousedown", chip.onMouse, true);
  window.removeEventListener("resize", chip.onResize);
}

function wbPasteChipPlace(chip) {
  const view = wbVisibleCanvasRect();
  const w = chip.el.offsetWidth;
  const h = chip.el.offsetHeight;
  const [px, py] = wbBoardToClient(chip.at[0], chip.at[1]);
  const left = Math.max(view.left + 8, Math.min(px, view.right - w - 8));
  const below = py + 8;
  const top = below + h > view.bottom - 8 ? Math.max(view.top + 8, py - h - 8) : below;
  chip.el.style.left = `${Math.round(left)}px`;
  chip.el.style.top = `${Math.round(top)}px`;
}

//: Swap what the paste made for another reading: the paste is undone and the
//: new one made, so Undo afterwards takes back the whole paste in one step. A
//: board that has moved on since (the top undo step is not the paste) closes
//: the chip rather than undo something else.
async function wbPasteChipChoose(chip, variant) {
  if (wbUndoStack[wbUndoStack.length - 1] !== chip.entry) {
    wbPasteChipClose();
    return;
  }
  await wbUndo();
  const next = await chip.apply(variant.id);
  if (!next || wbPasteChip !== chip) return;
  chip.current = variant.id;
  chip.entry = wbUndoStack[wbUndoStack.length - 1];
  chip.at = next.at || chip.at;
  wbPasteChipPlace(chip);
}

function wbPasteChipMenu(chip) {
  const rect = chip.el.getBoundingClientRect();
  const items = chip.variants
    .filter((v) => v.id !== chip.current)
    .map((v) => ({ label: `${v.label} (${v.key.toUpperCase()})`, run: () => wbPasteChipChoose(chip, v) }));
  openMenuAtPoint(items, "Paste options", rect.left, rect.bottom + 2);
}

function wbPasteMenuOpen() {
  return Boolean(document.querySelector(".pointer-menu-host .action-menu:not(.hidden)"));
}

//: Ctrl on its own opens the menu (as the document editor's does); with the
//: menu open a reading's letter picks it; Escape or any other key is the
//: writer going back to the board.
function wbPasteChipKey(chip, event) {
  if (event.key === "Control") {
    chip.ctrl = !event.repeat;
    return;
  }
  chip.ctrl = false;
  if (["Shift", "Alt", "Meta"].includes(event.key)) return;
  const inMenu = event.target instanceof Element && event.target.closest(".action-menu");
  if (inMenu || wbPasteMenuOpen()) {
    const hit = !event.ctrlKey && !event.metaKey && chip.variants.find((v) => v.id !== chip.current && v.key === event.key.toLowerCase());
    if (hit) {
      event.preventDefault();
      closeActionMenus();
      wbPasteChipChoose(chip, hit);
    }
    return;
  }
  wbPasteChipClose();
}

//: `variants` is `[{id, label, key}]`, the first the one just made; `apply(id)`
//: undoes nothing itself, it makes that reading and resolves `{at}` (the new
//: anchor) or null.
function wbPasteChipOffer(variants, current, at, entry, apply) {
  wbPasteChipClose();
  if (variants.length < 2) return;
  const el = document.createElement("div");
  el.className = "wb-paste-chip";
  const chip = { el, variants, current, at, entry, apply, ctrl: false };
  const opener = smallButton("ph:clipboard-text Paste options", "Paste options: other ways to paste this (Ctrl)", () => wbPasteChipMenu(chip));
  opener.setAttribute("aria-haspopup", "menu");
  el.appendChild(opener);
  document.body.appendChild(el);
  chip.onKey = (event) => wbPasteChipKey(chip, event);
  chip.onKeyUp = (event) => {
    if (event.key === "Control" && chip.ctrl) wbPasteChipMenu(chip);
    chip.ctrl = false;
  };
  chip.onMouse = (event) => {
    if (!el.contains(event.target) && !(event.target instanceof Element && event.target.closest(".action-menu"))) wbPasteChipClose();
  };
  chip.onResize = () => wbPasteChipPlace(chip);
  document.addEventListener("keydown", chip.onKey, true);
  document.addEventListener("keyup", chip.onKeyUp, true);
  document.addEventListener("mousedown", chip.onMouse, true);
  window.addEventListener("resize", chip.onResize);
  wbPasteChip = chip;
  wbPasteChipPlace(chip);
}

function wbPasteVariantList(ids) {
  return ids.map((id) => ({ id, label: WB_PASTE_LABELS[id], key: WB_PASTE_KEYS[id] }));
}

//: Make `id` for this text, in one undo step, one request. Resolves
//: `{count, at}` (the anchor under what it made) or null.
async function wbPasteMake(id, text, at) {
  const [cx, cy] = at || wbViewCentre();
  const { items, said } = wbPasteBuild(id, text, cx, cy, wbPasteLook());
  if (!items.length) return null;
  let created = [];
  await wbRecordGesture(async () => {
    created = await wbCreateCopies(items, 0, 0);
  });
  if (!created.length) return null;
  const things = created.filter((c) => !(c.kind === "sketch" && wbIsLinkSketch(wbFindItem("sketch", c.id) || {})));
  wbSelectToolRef?.("select");
  wbSelectMade(things);
  wbAnnounce(said);
  toast(`${said} Ctrl+Z takes ${things.length === 1 ? "it" : "them"} back.`);
  return { count: things.length, at: wbPasteAnchor(items, cx, cy) };
}

function wbSelectMade(things) {
  clearWbSelection();
  if (things.length === 1) wbSelectedItem = { kind: things[0].kind, id: things[0].id };
  else for (const c of things) wbMultiSelection.add(wbMultiKey(c.kind, c.id));
  wbApplySelectionHighlight();
  wbUpdateSelectionBar();
  wbScheduleRender();
}

//: The board point under what was made: the bottom-left of its objects, or the
//: middle when a shape was made.
function wbPasteAnchor(items, cx, cy) {
  const objs = items.filter((i) => i.kind === "object");
  if (!objs.length) return [cx, cy + 40];
  return [Math.min(...objs.map((o) => o.payload.x)), Math.max(...objs.map((o) => o.payload.y + o.payload.height))];
}

//: Text from another app, made into items. The default reading goes in at once
//: and the chip offers the others.
async function wbPasteText(text, at) {
  const armed = wbPasteArmed;
  wbPasteArmed = "";
  const ids = wbPasteVariants(text);
  if (!ids.length) return 0;
  const first = armed && ids.includes(armed) ? armed : ids[0];
  const made = await wbPasteMake(first, text, at);
  if (!made) return 0;
  const variants = wbPasteVariantList([first, ...ids.filter((id) => id !== first)]);
  wbPasteChipOffer(variants, first, made.at, wbUndoStack[wbUndoStack.length - 1], (id) => wbPasteMake(id, text, at));
  return made.count;
}

// --- Paste special ----------------------------------------------------------

async function wbPasteReadClipboard() {
  try {
    return (await navigator.clipboard.readText()) || "";
  } catch {
    return null;
  }
}

//: Apply one reading on purpose. When the browser will not let the app read
//: the clipboard, the next real Ctrl+V applies it instead.
async function wbPasteSpecialApply(id) {
  const text = await wbPasteReadClipboard();
  if (text === null) {
    wbPasteArmed = id;
    toast(`Press Ctrl+V to paste as ${WB_PASTE_LABELS[id].toLowerCase()}.`, "info");
    return;
  }
  if (!wbPastedLines(text).length) {
    toast("Nothing on the clipboard to paste as that.", "info");
    return;
  }
  if (id === "table" && !pasteGrid(text)) {
    toast("Nothing on the clipboard reads as rows and columns.", "info");
    return;
  }
  const made = await wbPasteMake(id, text, null);
  if (made) wbPasteChipOffer(wbPasteVariantList(wbPasteVariants(text)), id, made.at, wbUndoStack[wbUndoStack.length - 1], (v) => wbPasteMake(v, text, null));
}

const WB_PASTE_SPECIAL = ["stickies", "textbox", "bullets", "branch", "table", "plain"];

//: Paste into the selected shape's text: the clipboard's words become its
//: label, one undo step.
async function wbPasteIntoShape() {
  const target = wbCommandTextTarget();
  if (!target) {
    toast("Select one closed shape or one connector first.", "info");
    return;
  }
  const text = await wbPasteReadClipboard();
  const words = pasteClean(text || "");
  if (!words.trim()) {
    toast(text === null ? "The browser would not let the app read the clipboard." : "Nothing on the clipboard to paste.", "info");
    return;
  }
  wbPushUndo({ action: "move", kind: "sketch", id: target.sketch.id, before: WB_KIND_INFO.sketch.payload(target.sketch) });
  await wbSaveSketchProps(target.sketch, { label: words.slice(0, 2000) });
  wbScheduleRender();
  wbAnnounce("Pasted into the shape's text.");
}

function wbPasteSpecialMenu() {
  if (wbIsMap()) {
    wbMapPasteSpecial();
    return;
  }
  const view = wbVisibleCanvasRect();
  const items = WB_PASTE_SPECIAL.map((id) => ({ label: `Paste as ${WB_PASTE_LABELS[id].toLowerCase()} (${WB_PASTE_KEYS[id].toUpperCase()})`, run: () => wbPasteSpecialApply(id) }));
  if (wbCommandTextTarget()) items.push({ label: "Paste into the selected shape's text", run: () => wbPasteIntoShape() });
  if (wbClipboard) items.push({ label: "Paste without comments", run: () => wbPasteClipboard({ noComments: true }) });
  openMenuAtPoint(items, "Paste special", (view.left + view.right) / 2 - 110, view.top + 80);
}

// --- The mind map -------------------------------------------------------------
//
// A map already turned pasted lines into child branches of the selected topic,
// indentation as depth (MINDMAP §12.2). The chip adds the other reading: all of
// it as one topic. The paste is undone and made again, as the board's is.

async function wbMapPasteMake(id, text) {
  const reading = wbMapPasteReading(id, text);
  const n = await wbRecordGesture(wbMapPasteText, [reading]);
  return n ? { count: n, at: null } : null;
}

async function wbMapPasteWithChip(text) {
  if (wbPastedLines(text).length < 2) {
    wbRecordGesture(wbMapPasteText, [text]);
    return;
  }
  const n = await wbMapPasteMake("branches", text);
  if (!n) return;
  const variants = ["branches", "oneTopic"].map((id) => ({ id, label: WB_MAP_PASTE_LABELS[id], key: WB_MAP_PASTE_KEYS[id] }));
  const [x, y] = wbViewCentre();
  wbPasteChipOffer(variants, "branches", [x, y], wbUndoStack[wbUndoStack.length - 1], (id) => wbMapPasteMake(id, text));
}

async function wbMapPasteSpecial() {
  const text = await wbPasteReadClipboard();
  if (text === null) {
    toast("The browser would not let the app read the clipboard. Press Ctrl+V to paste branches.", "info");
    return;
  }
  if (!wbPastedLines(text).length) {
    toast("Nothing on the clipboard to paste.", "info");
    return;
  }
  const view = wbVisibleCanvasRect();
  const items = ["branches", "oneTopic"].map((id) => ({
    label: `Paste as ${WB_MAP_PASTE_LABELS[id].toLowerCase()} (${WB_MAP_PASTE_KEYS[id].toUpperCase()})`,
    run: () => wbMapPasteMake(id, text),
  }));
  openMenuAtPoint(items, "Paste special", (view.left + view.right) / 2 - 110, view.top + 80);
}
