// router-overlays.js: what the browser's Back and Escape do about an overlay,
// kept out of router.js because that file is boot code at its gzip cap
// (tests/test_boot_budget.py). Called by router.js's popstate listener through `routerBackHook`. Loaded by `LAZY_MODULES.quickNote`
// (app.js, with quick-note.js), preloaded three seconds after boot; `routerSettle` is reached
// through ensureModule in closeSettingsModal.
//
// WORLD_CLASS_PLAN row 32 (the navigation audit, 2026-10-18): browser Back with
// the palette, finder, Guide, shortcuts or quick note open stepped the tab
// history and left the overlay open on the other tab (5 of 5). Back now closes
// the top overlay and puts the history back where it was.

//: The manual and Statistics are places too (INBOX 1335): overlays that push an
//: entry on open, as Settings does; their own close steps back off it.
const OVERLAY_TABS = { Manual: 1, Statistics: 1 };
const routerBack = { swallow: 0, timer: 0 };

//: The top overlay, closed the way its own Escape closes it. True when one was
//: open. Topmost first: a sheet or a dialog sits over the palettes. Settings is
//: not here: it has a history entry of its own, and Back already closes it.
function routerCloseTopOverlay() {
  const shown = (id) => {
    const el = document.getElementById(id);
    return Boolean(el) && !el.classList.contains("hidden");
  };
  const call = (name) => {
    if (typeof window[name] === "function") window[name]();
  };
  const sheets = document.querySelectorAll(".sheet-overlay:not(.sheet-leaving):not(.hidden)");
  if (sheets.length) {
    sheets[sheets.length - 1].querySelector(".sheet-close")?.click();
    return true;
  }
  const dialog = document.querySelector("dialog[open]");
  if (dialog) {
    if (typeof dialog.requestClose === "function") dialog.requestClose();
    else dialog.close();
    return true;
  }
  if (typeof manualOpen !== "undefined" && manualOpen.close) {
    manualOpen.close();
    return true;
  }
  if (document.querySelector(".lightbox")) {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    return true;
  }
  const closers = [
    ["sketch-overlay", "closeSketch"],
    ["palette-overlay", "closePalette"],
    ["finder-overlay", "closeFinder"],
    ["shortcuts-overlay", "closeShortcuts"],
    ["features-overlay", "closeFeatures"],
    ["notif-panel", "closeNotifications"],
  ];
  for (const [id, name] of closers) {
    if (!shown(id)) continue;
    call(name);
    return true;
  }
  //: The agent's palette has no closer of its own: hiding it is what its Escape does.
  if (shown("command-palette-overlay")) {
    document.getElementById("command-palette-overlay").classList.add("hidden");
    return true;
  }
  return false;
}

//: Called first by router.js's popstate listener; true when the step was
//: spent on closing an overlay, so the tab history is not walked. The step the
//: browser already took is taken back with `history.go`, whose own popstate is
//: swallowed.
function routerBackHook(event) {
  if (routerBack.swallow) {
    routerBack.swallow = 0;
    window.clearTimeout(routerBack.timer);
    return true;
  }
  if (typeof settingsModalOpen === "function" && settingsModalOpen()) return false;
  //: The manual and Statistics have entries of their own, as Settings does.
  if (OVERLAY_TABS[tabHistory.stack[tabHistory.index]?.tab]) return false;
  const navId = event.state && event.state.navId;
  const to = navId ? tabHistory.stack.findIndex((entry) => entry.navId === navId) : -1;
  const delta = to - tabHistory.index;
  if (to < 0 || !delta || !routerCloseTopOverlay()) return false;
  routerBack.swallow = 1;
  //: A refused traversal would leave the flag eating the next real Back.
  routerBack.timer = window.setTimeout(() => {
    routerBack.swallow = 0;
  }, 1500);
  history.go(-delta);
  return true;
}

//: Settings closed by its own X or Escape rather than by a step through
//: history. The entry Settings pushed is stepped back off, as Back would, so
//: the address names what is on screen and Forward reopens Settings (it used
//: to rewrite that entry's address to the tab underneath, so Forward onto it
//: showed the wrong hash). With no tab entry behind it (a pasted
//: `#/settings`, a rows-taken-off history) the address is corrected in place.
function routerSettle() {
  if (!/^#\/settings/.test(location.hash)) return;
  const tab = prefs.get("activeTab", null) || "dashboard";
  const before = tabHistory.stack[tabHistory.index - 1];
  //: Only onto an entry this page wrote: a Settings opened straight from its
  //: address has the browser's blank page under it (CI e2e, d04186d).
  if (tabHistory.index > 0 && before && before.tab === tab && history.state?.depth > 0 && routerGo(-1)) return;
  const entry = { tab, section: null };
  try {
    history.replaceState(history.state, "", `${location.pathname}${location.search}${routeHash(entry)}`);
  } catch {
    // As in routerOnVisit.
  }
  routerPaintTitle(entry);
}

//: The agent's palette opens from a click on the status bar or a key, and
//: closes by four paths (Escape, backdrop, toggle, a skill running); focus went
//: to BODY on all of them (audit, 2026-10-18). One observer returns it to the
//: opener `toggleAgentPalette` recorded.
(() => {
  const overlay = document.getElementById("command-palette-overlay");
  if (!overlay) return;
  new MutationObserver(() => {
    if (!overlay.classList.contains("hidden")) return;
    const back = overlay.opener;
    overlay.opener = null;
    const active = document.activeElement;
    if (back && back.isConnected && (!active || active === document.body || overlay.contains(active))) back.focus?.();
  }).observe(overlay, { attributes: true, attributeFilter: ["class"] });
})();

//: An overlay's own close, not a move through history (manual.js, statistics.js).
//: `stay`: the close is about to go somewhere, so the entry stays for Back.
function overlayClosed(name, { stay = false } = {}) {
  if (stay || tabHistory.navigating) return;
  if (tabHistory.stack[tabHistory.index]?.tab === name && tabHistory.index > 0) stepTabHistory(-1);
}

//: `openHistoryEntry`'s first step. The manual and Statistics open over what is
//: under them (a manual opened from Settings keeps Settings behind it); any
//: other entry closes both. True when the entry was one of the two.
async function overlayGo(entry) {
  if (entry.tab !== "Manual") (typeof manualOpen !== "undefined" ? manualOpen : null)?.close?.();
  if (entry.tab !== "Statistics" && typeof statsCard !== "undefined") statsCard.close?.();
  if (entry.tab === "Manual") {
    if (await lazyScript("/js/manual.js")) await openManual();
  } else if (entry.tab === "Statistics") {
    openStatistics();
  } else {
    return false;
  }
  paintTabHistory();
  return true;
}
