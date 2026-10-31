// lazy-entries.js: the lazy bundles that came out of the boot scripts on
// 2026-10-12 (the gzip budget), registered here because app.js is at its own
// cap. Loads straight after app.js: later scripts name these functions at
// load (a widget table's `render`, a listener), so the stand-ins must exist.
Object.assign(LAZY_MODULES, {
  chatPrivate: ["/css/chat-private-lazy.css", "/js/chat-private.js"],
  //: The plain head's disc, fetched only when the faces failed (`plainHead`).
  plainHead: ["/css/plain-head-lazy.css"],
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
  //: The dashboard's Loose ends, While you were away and day digest widgets.
  dashLazy: ["/css/dash-orphans-lazy.css", "/css/dash-night-lazy.css", "/js/dash-orphans.js", "/js/dash-night.js", "/js/dash-day.js"],
  //: What the app draws into a reply beside its words (reply-kit.js's header).
  replyKit: ["/css/reply-kit-lazy.css", "/js/reply-kit.js"],
  //: The phone bar's More sheet (phone-more.js's header; INBOX 1314).
  phoneMore: ["/js/phone-more.js"],
  //: The generative background's styles and runtime (bg-art.js, 20 KB gzipped):
  //: only a notebook with the art on, or an open Appearance grid, needs them.
  bgArt: ["/js/bg-art.js"],
  //: The Appearance quick panel (appearance-panel.js, INBOX 1435).
  appearancePanel: ["/css/appearance-panel-lazy.css", "/css/appearance-panel-own-lazy.css", "/js/appearance-panel.js"],
  //: Settings, Appearance, Glass controls: the icon buttons' glass, fetched only while the switch is on.
  glassControls: ["/css/glass-controls-lazy.css"],
  //: Ask, Chat and the Guide's screen context (screen-context.js's header).
  screenContext: ["/js/screen-context.js"],
  //: The guided equation editor (math-editor.js's header; DOCUMENTS_PLAN 16).
  mathEditor: ["/css/math-editor-lazy.css", "/js/math-editor.js"],
  //: The model badge's spec panel, editing an answer, a note's Explain row, the extract preview's Save (gesture-kit.js's header).
  gestureKit: ["/js/gesture-kit.js"],
  //: A row's expand chevron and the bell's untagged and review nudges (notes-lazy.js).
  notesLazy: ["/js/notes-lazy.js"],
  //: Every ```mermaid fence, in documents, chat and Ask (mermaid-draw.js). The 5 MB
  //: library is not here: it loads inside the hidden frame mermaid-draw.js creates.
  mermaid: ["/css/mermaid-lazy.css", "/js/mermaid-draw.js"],
  //: Settings, Packages, with the package steps it shares with Settings, Tasks
  //: (task-steps.js); named here, not in app.js, whose gzip cap is tight.
  packages: ["/js/task-steps.js", "/js/settings-packages.js"],
  //: The failed-load state (load-failed.js's header).
  loadFailed: ["/js/load-failed.js"],
  //: The generated faces, the companion and Atlas (see "The characters" below).
  characters: ["/js/avatars.js", "/js/atlas.js", "/js/characters-ready.js"],
});
setTimeout(() => ensureModule("loadFailed"), 3000);
installStandIns({
  chatPrivate: ["chatPrivateStart", "chatPrivateToggle", "chatPrivateLeave"],
  settingsPanes: ["renderTasks", "renderTaskHistory", "renderHealthBlock", "renderSamplingRows", "renderPersonas", "savePersonaList"],
  noteActions: ["openImprove", "closeImprove", "runImprove", "applyImprove", "reevaluateEntry", "attachFileTo", "attachFromLibrary"],
  libraryPick: ["pickLibraryItemDialog", "pickMediaDialog"],
  statusPanels: ["renderSearchEngineHealth", "emailSupportReport", "renderBackendPicker", "openUndoHistoryMenu", "openModelOffer"],
  featureModelSheet: ["openFeatureModelSheet"],
  dashLazy: ["renderOrphanNotesWidget", "renderNightWidget", "renderDayDigest", "dashPatternBit", "dashTodayLine"],
  phoneMore: ["openPhoneMoreSheet"],
  screenContext: ["screenContext"],
  mathEditor: ["openMathEditor"],
  gestureKit: ["openChatModelPanel", "editChatAnswer", "explainNote", "commitExtractPreview"],
  notesLazy: ["toggleRowExpanded", "nudgeUntaggedNotes", "nudgeReviewQueue"],
  quickAdd: ["reminderComposeAdd"],
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
  const kind = typeof editorSurfaceKind === "function" ? editorSurfaceKind(box) : null;
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
//: the files first (`CHARACTER_DEPENDENTS`: the welcome card's Atlas);
//: `characters-ready.js`, last in the list, reports the arrival whichever
//: bundle asked for the files. The companion's own bundles (menu, throws)
//: are asked for by avatars.js, so they find it in.
let charactersLoaded = false;
const characterWaiters = new Set();
const characterBacklog = new Map();
const CHARACTER_DEPENDENTS = ["onboarding"];
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
  renderEmblem(holder, size);
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

//: A task of its own, so the files' parse and this are two long tasks, not one.
function charactersArrived() {
  setTimeout(() => {
    charactersLoaded = true;
    const waiting = [...characterWaiters];
    characterWaiters.clear();
    for (const fn of waiting) runCharacterJob(fn);
    for (const [name, args] of characterBacklog) runCharacterJob(window[name], args);
    characterBacklog.clear();
  }, 0);
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
//: Cues: the moment has passed by the time the bundle is in.
installCharacterStandIns(["nameMarkBuddyNoteOpened", "atlasOn"], false);
//: Syncs and one-offs: the companion's settings, Atlas's look, a streak, the
//: Show or Hide row.
installCharacterStandIns([
  "syncNameMarkBuddy", "mountBuddyCustom", "mountBuddyActivities", "nameMarkBuddyMotionApply", "nameMarkBuddySizeSelect",
  "nameMarkBuddySetSize", "nameMarkBuddyCallBack", "nameMarkBuddyToggle", "nameMarkBuddyHint", "nameMarkRepaintAll",
  "atlasRepaint", "atlasStreak", "nameMarkBuddyStreak",
], true);

//: Whether a companion is on or about to be (the palette's Show or Hide row,
//: and its toggle). Reads a setting and the page, so it lives here, not in the
//: bundle the row has to be built before.
function nameMarkBuddyShowing() {
  let choice = "off";
  try {
    choice = prefs.get("avatar-buddy", null) || "off";
  } catch (e) {
    choice = "off";
  }
  return choice !== "off" || !!document.getElementById("nm-buddy");
}
