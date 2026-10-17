// lazy-entries.js: the lazy bundles that came out of the boot scripts on
// 2026-10-12 (the gzip budget), registered here because app.js is at its own
// cap. Loads straight after app.js: later scripts name these functions at
// load (a widget table's `render`, a listener), so the stand-ins must exist.
Object.assign(LAZY_MODULES, {
  //: Settings, Tasks (chat-tasks.js), About's health block (settings-health.js), Personas (personas-pane.js).
  settingsPanes: ["/js/chat-tasks.js", "/js/settings-health.js", "/js/personas-pane.js"],
  //: Improve (improve-panel.js) and a note's re-check and attach actions (lightbox-actions.js).
  noteActions: ["/css/improve-lazy.css", "/js/improve-panel.js", "/js/lightbox-actions.js"],
  //: The Library item picker (library-pick.js).
  libraryPick: ["/js/library-pick.js"],
  statusPanels: ["/js/status-panels.js"],
  featureModelSheet: ["/js/feature-model-sheet.js"],
  //: The dashboard's Loose ends, While you were away and day digest widgets.
  dashLazy: ["/css/dash-orphans-lazy.css", "/css/dash-night-lazy.css", "/js/dash-orphans.js", "/js/dash-night.js", "/js/dash-day.js"],
});
installStandIns({
  settingsPanes: ["renderTasks", "renderTaskHistory", "renderHealthBlock", "renderSamplingRows", "renderPersonas", "savePersonaList"],
  noteActions: ["openImprove", "closeImprove", "runImprove", "applyImprove", "reevaluateEntry", "attachFileTo", "attachFromLibrary"],
  libraryPick: ["pickLibraryItemDialog"],
  statusPanels: ["renderSearchEngineHealth", "emailSupportReport", "renderBackendPicker", "openUndoHistoryMenu"],
  featureModelSheet: ["openFeatureModelSheet"],
  dashLazy: ["renderOrphanNotesWidget", "renderNightWidget", "renderDayDigest", "dashPatternBit"],
});
