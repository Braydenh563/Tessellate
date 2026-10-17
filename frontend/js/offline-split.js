// offline-split.js: the no-model notice's split button (INBOX 904 B05). Lazy,
// fetched by `renderAiOfflineNotice` (status.js): the notice is in the boot
// scripts, which are at their gzip budget, and the caret is a menu that is
// only wanted when pressed. The recipe is `ocrSyncReadMenu`'s (DESIGN.md,
// "A split button"); offline-split-lazy.css dresses the pair.

//: Hides the notices (Settings, Models' own preference) and offers the way back.
function hideAiOfflineNotices(value = "on") {
  prefs.set("hideOfflineNotice", value);
  $("pref-hide-offline-notice").checked = value === "on";
  syncModelGatedControls();
  if (value === "on") {
    toastAction("Hid the No model connected notices.", "Show them again", () => hideAiOfflineNotices("off"));
  }
}

//: Wraps the notice's action in the split and gives it the caret half. The poll
//: redraws the notice, so a button already replaced is left alone.
function aiOfflineSplit(link) {
  if (!link.isConnected || link.parentElement.classList.contains("ai-offline-split")) return;
  lazyScript("/css/offline-split-lazy.css");
  const split = document.createElement("div");
  split.className = "split-button ai-offline-split";
  const slot = document.createElement("span");
  slot.className = "split-button-slot";
  link.classList.add("split-button-main");
  link.replaceWith(split);
  split.append(link, slot);
  const menu = kebabMenu([{
    label: "ph:eye-slash Hide these popups",
    title: "Stop showing the No model connected notices. Settings, Models turns them back on.",
    run: () => hideAiOfflineNotices(),
  }], "More: hide these popups");
  const caret = menu.querySelector(":scope > button");
  caret.classList.remove("icon-only");
  caret.classList.add("ghost", "split-button-caret");
  setLabel(caret, "ph:caret-down");
  caret.title = "Hide these popups";
  slot.append(menu);
}
