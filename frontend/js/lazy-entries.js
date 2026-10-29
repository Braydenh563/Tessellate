// lazy-entries.js: the lazy bundles that came out of the boot scripts on
// 2026-10-12 (the gzip budget), registered here because app.js is at its own
// cap. Loads straight after app.js: later scripts name these functions at
// load (a widget table's `render`, a listener), so the stand-ins must exist.
Object.assign(LAZY_MODULES, {
  //: Every popup panel draggable by its head and resizable from its corner (INBOX 1427): see panel-movable.js.
  panelMovable: ["/css/panel-movable-lazy.css", "/js/panel-movable.js"],
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
  //: The model badge's spec panel, editing an answer, a note's Explain row (gesture-kit.js's header).
  gestureKit: ["/js/gesture-kit.js"],
  //: Every ```mermaid fence, in documents, chat and Ask (mermaid-draw.js). The 5 MB
  //: library is not here: it loads inside the hidden frame mermaid-draw.js creates.
  mermaid: ["/css/mermaid-lazy.css", "/js/mermaid-draw.js"],
  //: Settings, Packages, with the package steps it shares with Settings, Tasks
  //: (task-steps.js); named here, not in app.js, whose gzip cap is tight.
  packages: ["/js/task-steps.js", "/js/settings-packages.js"],
  //: The failed-load state (load-failed.js's header).
  loadFailed: ["/js/load-failed.js"],
});
setTimeout(() => ensureModule("loadFailed"), 3000);
installStandIns({
  settingsPanes: ["renderTasks", "renderTaskHistory", "renderHealthBlock", "renderSamplingRows", "renderPersonas", "savePersonaList"],
  noteActions: ["openImprove", "closeImprove", "runImprove", "applyImprove", "reevaluateEntry", "attachFileTo", "attachFromLibrary"],
  libraryPick: ["pickLibraryItemDialog"],
  statusPanels: ["renderSearchEngineHealth", "emailSupportReport", "renderBackendPicker", "openUndoHistoryMenu"],
  featureModelSheet: ["openFeatureModelSheet"],
  dashLazy: ["renderOrphanNotesWidget", "renderNightWidget", "renderDayDigest", "dashPatternBit", "dashTodayLine"],
  phoneMore: ["openPhoneMoreSheet"],
  screenContext: ["screenContext"],
  mathEditor: ["openMathEditor"],
  gestureKit: ["openChatModelPanel", "editChatAnswer", "explainNote"],
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
