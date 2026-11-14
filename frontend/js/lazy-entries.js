// lazy-entries.js: the lazy bundles that came out of the boot scripts on
// 2026-10-12 (the gzip budget), registered here because app.js is at its own
// cap. Loads straight after app.js: later scripts name these functions at
// load (a widget table's `render`, a listener), so the stand-ins must exist.
Object.assign(LAZY_MODULES, {
  //: Boards and maps (audit D22): the `library` files, then d3 and the nine whiteboard files (820 KB gzipped) a first
  //: document open no longer pays for. A copy by spread so the lists cannot drift; tests/test_lazy_boards_split.py reads every name.
  boards: [
    ...LAZY_MODULES.library,
    "/vendor/d3.v7.min.js", //: Before whiteboard.js, whose top level calls `d3.zoom()`.
    "/js/whiteboard-map.js",
    "/js/whiteboard-map-more.js", //: After whiteboard-map.js: the Gantt view and the audio note, calling its date words and style writer at run time only.
    "/js/whiteboard.js",
    "/js/whiteboard-commands.js",
    "/js/whiteboard-library.js",
    //: The New board dialog and every template's picture (INBOX 715).
    "/js/whiteboard-templates.js",
    "/js/whiteboard-format.js",
    "/js/whiteboard-label.js", //: After whiteboard-format.js: it joins that file's field lists and `wbFmtState`.
    "/js/whiteboard-hints.js", //: The View switches for the arrow grips and the connection dots; needs the page, `prefs`, `toast` and `wbFmtState`.
    "/js/whiteboard-options.js", //: The Format panel's Board section; reads `wbSetBackground` and `onSurface` at run time only.
    "/js/whiteboard-export-more.js", //: PNG resolution and embedded board, the HTML page; pure, joins `wbFmtState` (whiteboard-format.js).
    "/js/whiteboard-keys.js",
    "/js/whiteboard-toolbar.js", //: One tab stop per section of the tool rail, arrows inside it; needs `onSurface` and `wbFmtState`.
    "/js/whiteboard-workspace.js", //: Edit inside a group and saved panel layouts; names whiteboard.js, whiteboard-library.js and whiteboard-format.js at run time only.
    "/js/whiteboard-layers-more.js",
    "/js/whiteboard-draw-more.js",
    "/js/whiteboard-arrange-more.js", //: After whiteboard-draw-more.js: it reads that file's loop sides at run time.
    "/js/whiteboard-layouts-more.js", //: After whiteboard-arrange-more.js: the board Layout menu and the lane stack; names whiteboard.js at run time only.
    "/js/whiteboard-structure-more.js", //: Tags, folded frames, the frame drop highlight and the find bar's frame scope; joins `wbFmtState` and the field lists (whiteboard-format.js).
    "/js/whiteboard-shape-more.js", //: A table's row ports and the shape's points; names whiteboard.js and whiteboard-format.js at run time only.
    "/js/whiteboard-shapes-js.js", //: Insert, Polygon and the JS-drawn shape classes; joins `wbFmtState` (whiteboard-format.js), names whiteboard.js at run time only.
    "/js/whiteboard-text-more.js", //: Subscript, superscript and `$...$` maths in board words; joins `wbFmtState` (whiteboard-format.js), names whiteboard.js at run time only.
    "/js/whiteboard-effects.js", //: Text shadow, glass, a picture fill, mirroring and the status bar; joins `wbFmtState` (whiteboard-format.js), names whiteboard.js at run time only.
    "/vendor/perfect-freehand/perfect-freehand.min.js", //: Before whiteboard-ink-more.js: it sets `window.perfectFreehand` (MIT, 5 KB).
    "/js/whiteboard-ink-more.js", //: Free-line hollow ends, smoothed pen strokes, shape clean-up, replay and the GIF; joins `wbFmtState` (whiteboard-format.js), names whiteboard.js at run time only.
    "/js/whiteboard-ink-recognise.js", //: Turns a rough stroke into a clean shape; pure, joins `wbFmtState` and runs after whiteboard-ink-more.js.
    "/js/whiteboard-ink-replay.js", //: Replay ink and its GIF; joins `wbFmtState`, names whiteboard.js at run time only.
    "/js/whiteboard-pdf.js", //: A PDF dropped on a board, placed as pages or kept as one object; joins `wbFmtState`, names whiteboard.js at run time only.
    "/js/whiteboard-gif.js", //: The animated-GIF writer; pure, joins `wbFmtState`.
    "/js/whiteboard-shape-table.js", //: The table of JS-drawn shapes (cylinder, cube, step...): the picker rows, resize and draw.io words; joins `wbFmtState`.
    "/js/whiteboard-library-more.js", //: The shape picker and Replace with a library shape; names whiteboard.js and whiteboard-library.js at run time only.
    "/js/whiteboard-interchange.js",
    "/js/whiteboard-history.js",
  ],
  //: A non-image file chosen in the chat: imported as a document, or kept in the Library (chat-docs.js).
  chatDocs: ["/js/chat-docs.js"],
  //: The offline studio's sheet and the natural voice's reading (studio.js's header; WORLD_CLASS_PLAN rows 35 and 37).
  studio: ["/js/studio.js"],
  //: Sync between computers through a folder, no server (sync-folder.js's header; WORLD_CLASS_PLAN row 36).
  syncFolder: ["/js/sync-folder.js"],
  //: A space switch, in place (space-swap.js).
  spaceSwap: ["/js/space-swap.js"],
  //: Unlocking, editing and leaving a private space (private-spaces.js's header; INBOX 1727).
  //: hello-unlock.js: Windows Hello on the lock card and in Settings (its header).
  privateSpaces: ["/js/private-spaces.js", "/js/hello-unlock.js"],
  //: What the companion says about the notebook now and then (companion-remark.js's header).
  companionRemark: ["/js/companion-remark.js"],
  //: The capture bar's card (capture-card.js; notes-list.js opens it on the first focus).
  captureCard: ["/css/capture-card-lazy.css", "/js/capture-card.js"],
  chatPrivate: ["/css/chat-private-lazy.css", "/js/chat-private.js"],
  //: The plain head's disc, fetched only when the faces failed (`plainHead`).
  plainHead: ["/css/plain-head-lazy.css"],
  //: One anatomy for every popup: the head's glyph, the glyph tab row, the bordered card (INBOX 1478).
  popupAnatomy: ["/css/popup-anatomy-lazy.css", "/js/popup-glyph.js"],
  //: Every popup panel draggable by its head and resizable from its corner (INBOX 1427): see panel-movable.js.
  panelMovable: ["/css/panel-movable-lazy.css", "/js/panel-movable.js"],
  //: The activity panel and the run folds it shares with Settings, Tasks (task-steps.js).
  activity: ["/js/task-steps.js", "/js/activity-panel.js"],
  //: Settings, Tasks (chat-tasks.js), About's health block (settings-health.js), Personas (personas-pane.js).
  settingsPanes: ["/js/task-steps.js", "/js/chat-tasks.js", "/js/settings-health.js", "/js/personas-pane.js"],
  //: Improve (improve-panel.js) and a note's re-check and attach actions (lightbox-actions.js).
  noteActions: ["/css/improve-lazy.css", "/js/improve-panel.js", "/js/lightbox-actions.js"],
  //: The Library item picker (library-pick.js).
  libraryPick: ["/js/library-pick.js"],
  statusPanels: ["/js/status-panels.js"],
  featureModelSheet: ["/js/feature-model-sheet.js"],
  //: The composer's model picker: search, Recent, a row per source, pins (model-menu.js's header; INBOX 1477).
  modelMenu: ["/css/model-menu-lazy.css", "/js/model-menu.js"],
  //: The dashboard's Loose ends, While you were away and day digest widgets.
  dashLazy: ["/css/dash-orphans-lazy.css", "/css/dash-night-lazy.css", "/js/dash-orphans.js", "/js/dash-night.js", "/js/dash-day.js"],
  //: What the app draws into a reply beside its words (reply-kit.js's header).
  replyKit: ["/css/key-grid-lazy.css", "/css/reply-kit-lazy.css", "/js/citation-peek.js", "/js/documents-math.js", "/js/reply-kit.js"],
  //: The phone bar's More sheet (phone-more.js's header; INBOX 1314).
  phoneMore: ["/js/phone-more.js"],
  //: The generative background's styles and runtime (bg-art.js, 20 KB gzipped):
  //: only a notebook with the art on, or an open Appearance grid, needs them.
  bgArt: ["/js/bg-art.js"],
  dashArt: ["/js/dash-art.js"],
  //: The Appearance quick panel (appearance-panel.js, INBOX 1435).
  appearancePanel: ["/css/appearance-panel-lazy.css", "/css/appearance-panel-own-lazy.css", "/js/appearance-panel.js"],
  //: Settings, Appearance, Glass controls: the icon buttons' glass, fetched only while the switch is on.
  glassControls: ["/css/glass-controls-lazy.css"],
  //: Ask, Chat and the Guide's screen context (screen-context.js's header).
  screenContext: ["/js/screen-context.js"],
  //: Word-style equation fields, MathLive and its glue (math-field.js's header; INBOX 1473 a):
  //: the first edit of a rendered `$...$` and the guided equation editor both fetch it.
  mathField: ["/css/math-field-lazy.css", "/vendor/mathlive/mathlive.min.js", "/js/math-field.js"],
  //: The guided equation editor (math-editor.js's header; DOCUMENTS_PLAN 16), on the same field.
  mathEditor: ["/css/key-grid-lazy.css", "/css/math-field-lazy.css", "/vendor/mathlive/mathlive.min.js", "/js/math-field.js", "/css/math-editor-lazy.css", "/js/math-editor.js"],
  //: The model badge's spec panel, editing an answer, a note's Explain row, the extract preview's Save, dictation (gesture-kit.js's header).
  gestureKit: ["/js/gesture-kit.js"],
  //: One chat turn (chat-turn.js): `sendChatMessage` awaits it; the chat box's focus warms it.
  chatTurn: ["/js/citation-peek.js", "/js/entry-card.js", "/js/answer-kit.js", "/js/chat-turn.js"],
  //: A note card's ... menu rows (entry-menu.js): the first press awaits it, a pointer over a card warms it.
  entryMenu: ["/js/entry-menu.js"],
  //: The Boards & maps gallery on its own (boards-gallery.js; INBOX 1772): it paints before the board code has run.
  boardsGallery: [...LAZY_MODULES.libraryList, "/js/boards-gallery.js"],
  //: A board's miniature (map-preview.js): `mapPreview` returns the empty svg and draws into it once this is in.
  mapPreview: ["/js/map-preview.js"],
  //: The palette's rows (`paletteCommands`) and the dashboard's Quick access draw (app-features.js): `renderQuickLinks` is its stand-in.
  featureRows: ["/js/app-features.js"],
  //: A note's card (entry-card.js, `entryItem`): `renderEntries` draws once it is in; fetched when the app goes idle.
  entryCard: ["/js/entry-card.js"],
  //: The bar a table in a reply or a note wears (table-block.js): the table render (navigation.js) swaps it in when it arrives.
  tableBlock: ["/js/table-block.js"],
  //: A row's expand chevron and the bell's untagged and review nudges (notes-lazy.js).
  notesLazy: ["/js/notes-lazy.js"],
  //: Every ```mermaid fence, in documents, chat and Ask (mermaid-draw.js). The 5 MB
  //: library is not here: it loads inside the hidden frame mermaid-draw.js creates.
  mermaid: ["/css/mermaid-lazy.css", "/js/mermaid-draw.js"],
  //: Colour for a fenced code block that names a language (code-colour.js; the vendored CodeMirror parsers).
  codeColour: ["/css/code-colour-lazy.css", "/js/code-colour.js"],
  //: Settings, Packages, with the package steps it shares with Settings, Tasks
  //: (task-steps.js); named here, not in app.js, whose gzip cap is tight.
  packages: ["/js/task-steps.js", "/js/settings-packages.js"],
  //: The failed-load state (load-failed.js's header).
  loadFailed: ["/js/load-failed.js"],
  //: The generated faces, the companion and Atlas (see "The characters" below).
  characters: ["/js/avatars.js", "/js/atlas.js", "/js/characters-ready.js"],
  //: What a person does to the companion on purpose: the Settings controls, Show or
  //: hide, Call back, the Look repaint (companion-settings.js's header; audit AI23).
  companionSettings: ["/js/companion-settings.js"],
  //: What a click, a hover or a focus brings onto the screen fades in, and out where it floats (INBOX 1565): ui-reveal-lazy.css.
  uiReveal: ["/css/ui-reveal-lazy.css"],
  //: The ```graph and ```base blocks in a document (documents-graph.js, documents-base.js; documents-math.js asks by name),
  //: and a synced block's edit box (documents-synced.js; documents-embeds.js asks on the pencil).
  docGraph: ["/css/doc-graph-lazy.css", "/js/documents-graph.js"],
  docBase: ["/css/doc-base-lazy.css", "/js/documents-base.js"],
  docSynced: ["/js/documents-synced.js"],
  docBoard: ["/js/documents-board.js"],
  //: The csv and tsv grid, fetched on the first press of Grid (documents-csvgrid.js).
  docCsvGrid: ["/css/doc-csv-grid-lazy.css", "/js/documents-csvgrid.js"],
});
setTimeout(() => ["loadFailed", "modelMenu", "entryCard", "uiReveal"].forEach(ensureModule), 3000);
installStandIns({
  //: What the Library list, the documents and every surface that names a board call into the board code (D22).
  //: Nobody reads a return value: a function whose answer is read (`wbCommandsLive`, `wbEditorSurfaceById`)
  //: cannot be one, and its caller tests `typeof` instead, meaning "no board is open".
  boards: ["createNewBoard", "openWhiteboardBoard", "wbMapFromDocument", "wbShowBoardsLanding", "wbBinBoard", "wbDeleteBoard", "addBoardToNote"],
  //: The gallery's redraw, asked for by the Library list and the boards' own Reload (boards-gallery.js).
  boardsGallery: ["renderLibraryBoardsGallery"],
  //: The lock card's offer of a backup when the notebook file is gone (INBOX 1573).
  accountRecovery: ["showRestoreOffer"],
  companionSettings: ["mountBuddyCustom", "mountBuddyActivities", "mountProfileLook", "nameMarkBuddyMakeIt", "nameMarkBuddyHide", "nameMarkBuddyToggle", "nameMarkBuddyCallBack", "nameMarkRepaintAll"],
  spaceSwap: ["swapSpace", "spaceEnterFor"],
  studio: ["openStudio", "speakNatural"],
  syncFolder: ["openFolderSync"],
  privateSpaces: ["privateSpaces"],
  companionRemark: ["nameMarkBuddyRemark"],
  chatPrivate: ["chatPrivateStart", "chatPrivateToggle", "chatPrivateLeave"],
  settingsPanes: ["renderTasks", "renderTaskHistory", "renderHealthBlock", "renderSamplingRows", "renderPersonas", "savePersonaList"],
  noteActions: ["openImprove", "closeImprove", "runImprove", "applyImprove", "reevaluateEntry", "attachFileTo", "attachFromLibrary"],
  libraryPick: ["pickLibraryItemDialog", "pickMediaDialog"],
  statusPanels: ["renderSearchEngineHealth", "emailSupportReport", "renderBackendPicker", "openUndoHistoryMenu", "openModelOffer"],
  featureModelSheet: ["openFeatureModelSheet"],
  dashLazy: ["renderOrphanNotesWidget", "renderNightWidget", "renderDayDigest", "dashPatternBit", "dashTodayLine"],
  dashArt: ["renderArtWidget"],
  phoneMore: ["openPhoneMoreSheet"],
  screenContext: ["screenContext"],
  mathEditor: ["openMathEditor"],
  mathField: ["openMathInPlace"],
  gestureKit: ["openChatModelPanel", "editChatAnswer", "explainNote", "commitExtractPreview", "toggleDictation"],
  notesLazy: ["toggleRowExpanded", "fullEntry", "nudgeUntaggedNotes", "nudgeReviewQueue", "refreshNoteSearchWhy", "loadSemanticEntries", "noMatchHint", "liveQueryBar"],
  quickAdd: ["reminderComposeAdd"],
  featureRows: ["renderQuickLinks"],
  loadFailed: ["surfaceFailed"],
  appearancePanel: ["openAppearancePanel"],
});
//: A lone Alt is nobody's (INBOX 1422): its release hands focus to the window's
//: own menu, which stays until blur. Cancelled; Alt+key is untouched.
document.addEventListener("keydown", (e) => { document.altAlone = e.key === "Alt"; }, true);
document.addEventListener("keyup", (e) => { if (e.key === "Alt" && document.altAlone) e.preventDefault(); document.altAlone = false; }, true);
window.addEventListener("blur", () => { document.altAlone = false; });
//: Alt+= opens the equation editor, as in Word, in the boxes that write
//: markdown and in the Ask box (math-editor.js).
document.addEventListener("keydown", (event) => {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.code !== "Equal") return;
  const box = event.target;
  //: By the box's id while the adapters are still on their way (maths1527: about 1 s after a fresh note box's first focus, Alt+= did nothing).
  const kind = (typeof editorSurfaceKind === "function" ? editorSurfaceKind(box) : null) ?? (typeof EDITOR_SURFACES === "object" ? EDITOR_SURFACES[box?.id] ?? null : null);
  if (box?.id !== "question" && !["note", "document", "chat", "board"].includes(kind)) return;
  event.preventDefault();
  openMathEditor({ target: box });
});

//: **The characters** (audit 1028 S3). avatars.js and atlas.js, the faces, the
//: companion and Atlas, were 248 KB of the 574 KB gzipped the lock screen waited
//: for; they are the `characters` bundle now and arrive once the app is open and
//: idle (`loadCharactersIdle`, called when the opening curtain lifts). Until then
//: a call into them goes one of three ways, and each is chosen by what the caller
//: does with the answer:
//:
//: 1. **A stand-in** (below) when nobody reads the return value. It never fetches
//:    anything: the bundle is on its way. A cue (Atlas proud of a saved note, the
//:    companion hearing a bell) is stale a second later and is dropped; a sync
//:    (apply this setting, redraw that mark) is idempotent and is replayed once,
//:    with its last arguments, when the bundle arrives.
//: 2. **`afterCharacters(fn)`** when the caller draws a face: runs now once they are
//:    in, else when they arrive, in call order and once per function.
//: 3. **`charactersLoaded`** where the answer is "is there a companion to ask", which
//:    is no before they arrive (whiteboard.js).
//:
//: A bundle that reaches into them at once, not from a call of theirs, lists
//: the files first (`CHARACTER_DEPENDENTS`: the welcome card's Atlas, and the
//: companion's own menu, throws, remarks and Atlas's motion and tail, which call
//: avatars.js and atlas.js by name: tests/test_lazy_bundle_calls.py reads the list);
//: `characters-ready.js`, last in the list, reports the arrival whichever
//: bundle asked for the files.
let charactersLoaded = false;
const characterWaiters = new Set();
const characterBacklog = new Map();
const CHARACTER_DEPENDENTS = ["onboarding", "companionSettings", "companionMenu", "companionThrow", "companionRemark", "atlasLife", "atlasMotion"];
for (const name of CHARACTER_DEPENDENTS) LAZY_MODULES[name] = [...LAZY_MODULES.characters, ...LAZY_MODULES[name]];

//: `fallback` is a face that needs no bundle (`plainHead`, or the app's emblem): it
//: runs instead of `fn` when the bundle could not be fetched (offline, a 500), so
//: a head is never left empty for good.
const characterFallbacks = new Map();

function afterCharacters(fn, fallback) {
  if (charactersLoaded) fn();
  else if (characterWaiters.failed) fallback?.();
  else {
    characterWaiters.add(fn);
    if (fallback) characterFallbacks.set(fn, fallback);
  }
}

function charactersLost() {
  characterWaiters.failed = true;
  characterWaiters.clear();
  for (const fallback of characterFallbacks.values()) runCharacterJob(fallback);
  characterFallbacks.clear();
}

//: The app's own mark, already in the page (phone-shell.js), as the app's head.
function emblemHead(holder, size) {
  holder.replaceChildren();
  renderEmblem(holder, size, { animate: true });
}

//: The name's initial in a quiet disc, for a head whose face did not arrive.
function plainHead(holder, name) {
  const initial = document.createElement("span");
  initial.className = "plain-head";
  initial.textContent = String(name || "?").trim().charAt(0).toUpperCase() || "?";
  holder.replaceChildren(initial);
  ensureModule("plainHead");
}

function runCharacterJob(fn, args = []) {
  try {
    fn(...args);
  } catch (error) {
    console.error(error);
  }
}


function loadCharactersIdle() {
  const load = () => ensureModule("characters").then((ok) => ok || charactersLost());
  if (window.requestIdleCallback) requestIdleCallback(load, { timeout: 3000 });
  else setTimeout(load, 400);
}

function installCharacterStandIns(names, replay) {
  for (const name of names) {
    window[name] = (...args) => {
      if (replay) characterBacklog.set(name, args);
    };
  }
}
//: Cues: the moment has passed by the time the bundle is in (a bell, a toast, a
//: saved note, the read-aloud's start and end, the perch check's nudge).
installCharacterStandIns(["nameMarkBuddyNoteOpened", "atlasOn", "nameMarkBuddyCue", "nameMarkBuddySound", "nmbTickArm"], false);
//: Syncs and one-offs: the companion's settings, Atlas's look, a streak, the
//: Show or Hide row.
installCharacterStandIns([
  "syncNameMarkBuddy", "nameMarkBuddyMotionApply", "nameMarkBuddySizeSelect",
  "nameMarkBuddySetSize", "nameMarkBuddyHint",
  "atlasRepaint", "atlasStreak", "nameMarkBuddyStreak",
], true);

//: Whether a companion is on or about to be (the palette's Show or Hide row,
//: and its toggle). Reads a setting and the page, so it lives here, not in the
//: bundle the row has to be built before.
function nameMarkBuddyShowing() {
  try {
    if ((prefs.get("avatar-buddy", null) || "off") !== "off") return true;
  } catch (e) {
    //: Unreadable stays off.
  }
  return !!document.getElementById("nm-buddy");
}

//: What a person reads when a lazy file could not be fetched; said once a few
//: seconds, not per keystroke. Callers that need the file check the boolean
//: `lazyScript` / `ensureModule` resolve with and call this when it is false.
function lazyLoadFailed(what = "That part of Tessellate") {
  if (Date.now() - (lazyLoadFailed.at || 0) < 4000) return;
  lazyLoadFailed.at = Date.now();
  toast(`${what} needs a connection the first time. Try again once you are back online.`);
}

//: **A lazy bundle's "when the page is ready" is now.** A file loaded on first
//: use missed its `DOMContentLoaded` listener (the Library sub-tabs had no
//: handler), so wiring runs at once when the document is parsed. A microtask,
//: not a direct call: the wiring reads `let` bindings declared further down
//: its file, which a direct call reached before they existed.
function onDomReady(fn) {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
  else queueMicrotask(fn);
}

//: The library bundle (documents and the list; the boards, d3 and the whiteboard files are `boards`, fetched on a first board) is
//: not fetched at boot at all (perf 1031 row 21, PF4: 103 scripts and 6.5 MB
//: parsed in the first nine seconds on a tab that opened nothing). It is warmed
//: after the person first touches the page, and only with four cores or more
//: and no data saving (audit 1030 Y16); a visit to a surface that needs it
//: fetches it on the spot (`ensureModule`). One file at a time, the graph's
//: first, each after 2.5 s without a press (INBOX 1516: a tab switch ran twenty).
function warmLibraryAfterInput() {
  if (navigator.connection?.saveData || (navigator.hardwareConcurrency || 2) < 4) return;
  let calmAt = 0;
  const files = [...LAZY_MODULES.graph, ...LAZY_MODULES.library].filter((f) => f[1] > "c");
  const warmNext = () =>
    Date.now() < calmAt ? setTimeout(warmNext, 600) : files[0] && lazyScript(files.shift()).then(() => setTimeout(warmNext, 600));
  const warm = (event) => {
    //: Typing the password is not the person arriving: the lock screen is over
    //: the page until they are in.
    if (event.target?.closest?.("#lock-overlay")) return;
    calmAt || setTimeout(warmNext);
    calmAt = Date.now() + 2500;
  };
  for (const type of ["pointerdown", "keydown"]) window.addEventListener(type, warm, { capture: true, passive: true });
}
warmLibraryAfterInput();

//: One helper for the three "fetch it before it is wanted" doors: `bundle` is
//: fetched the first time `type` reaches a target matching `selector`.
function warmOnFirst(type, selector, bundle) {
  document.addEventListener(type, function warm(event) {
    if (!event.target?.closest?.(selector)) return;
    document.removeEventListener(type, warm);
    ensureModule(bundle);
  });
}
//: The chat turn's code is fetched while the person types, so Send finds it in.
warmOnFirst("focusin", "#chat-input", "chatTurn");
//: The popup agent's box takes typing for commands too, so its turn is fetched at the first key, not the first focus.
warmOnFirst("input", "#command-palette-input", "chatTurn");

//: A note card's ... menu rows are fetched when the pointer first reaches a card, so the first press finds them in.
warmOnFirst("pointerover", "li[data-id] .menu-wrap", "entryMenu");
//: A slider fetches the value field on its first hover or focus (a keyboard-only reach too), so its readout becomes typeable (INBOX 1694 c, value-field.js). Range inputs only: a plain number box has no readout to upgrade.
warmOnFirst("pointerover", "[type=range]", "vf");
warmOnFirst("focusin", "[type=range]", "vf");
//: The gallery and the miniature drawer are fetched when the pointer or focus first reaches the Boards & maps sub-tab, so the press finds them in (INBOX 1772). Not the board code: running 2.3 MB just before the press would delay the first card.
for (const type of ["pointerover", "focusin"]) for (const bundle of ["boardsGallery", "mapPreview"]) warmOnFirst(type, '#library-subtabs [data-target="library-view-whiteboard"]', bundle);
installStandIns({ chatDocs: ["importChatDocuments", "keepUnreadableChatFile"] });
