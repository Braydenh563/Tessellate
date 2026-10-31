// settings.js: the settings modal, the logs console, and appearance (theme,
// accent, curated palettes, saved looks, the background art preview).
// Split out of app.js (§88.3; HISTORY.md has the split's full account).
//
// Load order: everything here that reaches into another file is a runtime
// call inside a function or a listener, never a parse-time reference. The
// one exception ran the other way, and is why `applyAppearance()` (with
// `startBgArt()`) and `renderBrandLogo()` are called at the very end of this
// file rather than from app.js: they read functions defined here, so called
// from app.js's top level they threw before this file had loaded. The
// head's pre-paint script already applied the saved look, so this later
// call changes nothing a person can see.
//
// Deliberately left in app.js: `applyPalette()` (the whole app's palette),
// the brand emblem (used by the lock screen, the tour, the chat avatar),
// the UI-state mirroring (`watchMirroredUiKeys`, run at app.js's top level)
// with `LOOK_KEYS`, and the AI status pill (app-shell chrome with callers
// everywhere). The other Settings sections (account, web search, models,
// skills, tools, memory, templates, tasks, backups, shortcuts) render inside
// the modal this file drives, from wherever their code lives.

//: Every section id, and a new one is invisible until it is in this list, 
//: `showSettingsSection` un-hides by iterating it, so a section left out is
//: rendered, in the DOM, and never shown. Found by driving it: the Extras
//: panel had five rows in it and a nav button that appeared to do nothing.
const SETTINGS_SECTIONS = ["models", "searchindex", "preferences", "personas", "skills", "tools", "memory", "learned", "websearch", "general", "appearance", "templates", "shortcuts", "account", "privacy", "extras", "tasks", "data", "logs", "help", "about"];

// Which settings section is on screen. The Background tasks list polls while
// it is open, and needs to know that it is.
let currentSettingsSection = "models";

//: **Every pane opens with its own name** (the owner's de-vibecoding pass:
//: seven panes began with a title and eleven began mid-thought, with a
//: description, a status line or a group's small label). The ones without a
//: head get the nav's own label as the same heading the others use
//: (a `.dock.settings-pane-title`, styled in 08-consistency.css), made
//: once and kept, so the word in the list and the word over the pane can
//: never disagree.
//: **Arrow keys walk the pane list**, the way a sidebar of sections moves
//: in every settings window people know: Up and Down go to the previous and
//: next pane and open it, Home and End to the first and last. Tab still
//: leaves the list for the pane, so nothing a keyboard user relied on moves.
document.getElementById("settings-nav")?.addEventListener("keydown", (event) => {
  //: Page Up and Page Down still read the pane from the list (INBOX 426 u's
  //: reading keys, now that a click leaves the focus here: INBOX 467).
  if ((event.key === "PageDown" || event.key === "PageUp") && document.activeElement?.closest("#settings-nav")) {
    const scroller = settingsScroller(currentSettingsSection);
    if (scroller) {
      event.preventDefault();
      scroller.scrollBy({ top: (event.key === "PageDown" ? 1 : -1) * scroller.clientHeight * 0.9 });
    }
    return;
  }
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const buttons = [...document.querySelectorAll("#settings-nav button[data-section]")]
    .filter((b) => b.getClientRects().length);
  const at = buttons.indexOf(document.activeElement);
  if (at < 0) return;
  event.preventDefault();
  const next =
    event.key === "Home" ? 0
      : event.key === "End" ? buttons.length - 1
        : Math.max(0, Math.min(buttons.length - 1, at + (event.key === "ArrowDown" ? 1 : -1)));
  buttons[next].focus();
  //: Walking the list keeps the focus in it (the next arrow has to land on the
  //: next entry); only choosing one by Enter, Space or the pointer hands the
  //: focus on to the section's heading (`focusSettingsHeading`).
  settingsNavWalking = true;
  buttons[next].click();
  settingsNavWalking = false;
});
let settingsNavWalking = false;

function ensureSettingsPaneTitle(box, name) {
  //: Not "any `.help-head` child": Background tasks ends on one (Quit
  //: Tessellate), which used to count as its title and left the pane with none.
  if (!box || box.querySelector(":scope > .settings-pane-title, :scope > .dock")) return;
  const label = document.querySelector(`#settings-nav [data-section="${name}"]`)?.textContent.trim();
  if (!label) return;
  //: A pane whose first group is already named the same (Packages) would
  //: say it twice, one heading straight over the other.
  const firstHeading = box.querySelector("h3")?.textContent.trim().toLowerCase();
  if (firstHeading === label.toLowerCase()) return;
  //: The pane's dock (INBOX 599): the bar every tab and Library view opens
  //: with, here holding only the title, as the panes written in the markup do.
  const head = document.createElement("div");
  head.className = "dock settings-pane-title";
  const identity = document.createElement("div");
  identity.className = "dock-identity";
  const title = document.createElement("h3");
  title.textContent = label;
  identity.appendChild(title);
  head.appendChild(identity);
  box.prepend(head);
}

//: The section's own scrolling ancestor. Shared with the back/forward
//: history (navigation.js), which remembers where in a section you were.
//: Asked on every scroll event of a section (navigation.js) and every frame
//: of one ("On this page", settings-find.js), so the walk, a computed style
//: per ancestor and a forced style recalculation straight after a scroll,
//: is done once per pane and window width (the phone band moves it).
function settingsScroller(name) {
  const box = $(`settings-${name}`);
  if (box?._scroller?.contains(box) && box._scrollerAt === innerWidth) return box._scroller;
  for (let el = box && box.parentElement; el; el = el.parentElement) {
    const overflow = getComputedStyle(el).overflowY;
    if (overflow === "auto" || overflow === "scroll") {
      box._scroller = el;
      box._scrollerAt = innerWidth;
      return el;
    }
  }
  return null;
}

function showSettingsSection(name) {
  //: The companion's one-time nudge (avatars.js) may show when Appearance
  //: is first opened.
  if (name === "appearance") nameMarkBuddyHint(true);
  //: Help's tour buttons are drawn by tour.js, a lazy bundle.
  if (name === "help") renderTourReplay();
  //: Help's topics (about 2,100 nodes, from the Guide's own table, settings-find.js) are
  //: drawn when Help is shown or Settings is searched (filterSettings), not on every open.
  //: settings-find.js is awaited by openSettingsModal; `?.` covers a bundle that failed to load.
  if (name === "help") window.renderHelpTopics?.();
  //: Reported: reopening Settings lands on Models "but the scroll doesn't
  //: reset", so the first section opened halfway down. The section's own
  //: scrolling ancestor goes back to the top whenever the section changes.
  const scroller = settingsScroller(name);
  if (scroller) scroller.scrollTop = 0;
  currentSettingsSection = name;
  //: After the jump list has followed the nav (phone-shell.js), say the pane's name once.
  setTimeout(() => {
    const jump = document.getElementById("settings-jump");
    if (jump) echoSettingsPaneTitle(jump);
  }, 0);
  // Part of the same back/forward stack every tab and sub-tab already lives
  // in (app.js's tabHistory): asked for directly. Safe to call on every
  // section switch, restores included: recordTabVisit no-ops both when
  // nothing actually changed and while a back/forward move is in progress
  // (tabHistory.navigating), the same guard showNotesSection already relies
  // on for Notes' own sub-tabs.
  recordTabVisit("settings", name);
  for (const section of SETTINGS_SECTIONS) {
    $(`settings-${section}`).classList.toggle("hidden", section !== name);
  }
  ensureSettingsPaneTitle($(`settings-${name}`), name);
  ensureSettingsFoldAll($(`settings-${name}`));
  for (const button of document.querySelectorAll("#settings-nav button")) {
    button.classList.toggle("active", button.dataset.section === name);
    if (button.dataset.section) {
      if (button.dataset.section === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  }
  //: A long section gets its own index (settings-find.js, loaded on the first
  //: open of Settings).
  if (typeof settingsIndexWatchSection === "function") settingsIndexWatchSection(name);
  updatePeekAvailability(name);
  // The log stream is the only section that holds a connection open, so it is
  // the only one that has to be told it is no longer being looked at.
  if (name !== "logs") closeLogs();
  if (name === "logs") renderLogs();
  if (["preferences", "general", "searchindex", "personas"].includes(name)) renderPrefs().catch(() => {});
  if (name === "websearch") renderWebSearch().catch(() => {});
  if (name === "personas") renderPersonas().catch(() => {});
  if (name === "skills") renderSkillSettings();
  if (name === "templates") renderTemplateSettings();
  if (name === "tools") renderToolSettings();
  if (name === "memory") renderMemorySettings().catch(() => {});
  if (name === "learned") renderLearned().catch(() => {});
  if (name === "tasks") renderAutonomousReview().catch(() => {});
  if (name === "tasks") {
    apiJson("/preferences")
      .then((prefs) => {
        prefsCache = prefs;
        renderAutonomousSettings();
      })
      .catch(() => {});
  }
  //: `#pref-smart-model-routing` sits in Models, beside the utility picker it
  //: governs, and was only ever filled by `renderAutonomousSettings`, which
  //: runs when *Background tasks* opens. So Settings opened on Models showed
  //: the raw HTML default, unchecked, over a preference that ships on:
  //: measured, the box read false while `/preferences` said true, and the
  //: first click "turned on" a switch that was already on. The same shape the
  //: comment on `renderAutonomousSettings` records, one section over.
  if (name === "models") {
    apiJson("/preferences")
      .then((prefs) => {
        prefsCache = prefs;
        $("pref-smart-model-routing").checked = prefs.smart_model_routing_enabled ?? true;
      })
      .catch(() => {});
  }
  if (name === "models") renderModelBench();
  if (name === "general") {
    renderUsage();
    //: Search suggestions are kept on this device (search-suggest.js).
    $("pref-search-suggest").checked = prefs.get("searchSuggest", "on") !== "off";
  }
  if (name === "appearance") renderAppearance();
  if (name === "shortcuts") {
    ensureModule("reveal").then(() => renderShortcutList());
    renderCaptureCommand();
  }
  if (name === "account") renderAccount().catch(() => {});
  if (name === "privacy") renderPrivacyReceipt().catch(() => {});
  if (name === "data") {
    ensureModule("webClip");
    ensureModule("appImport");
    renderBackups();
    renderBackupRetention();
    ensureModule("settingsData").then(() => {
      renderSettingsClear();
      renderSettingsHistory();
    });
  }
  if (name === "tasks") renderTasks(); // fill it in now, then poll
  if (name === "extras") renderExtras();
  if (name === "searchindex") renderEmbedChoices();
  //: The Atlas row's starter chips, with the chat's bundle (help-chat.js).
  if (name === "help") renderAtlasStarters();
  if (name === "about") renderHealthBlock().catch(() => {});
  //: Settings, About, Maintenance: settings-controls.js, the window's lazy file.
  if (name === "about") ensureModule("settingsControls").then(() => renderMaintenance());
  //: The "Last run" lines on this section's controls, and the Background jobs
  //: overview (INBOX 438): one fetch fills every line on the page.
  refreshJobRuns();
}

// Peek fades the settings panel so a colour change is visible on the page
// behind it. Two details make it work: the fade is on the BACKGROUND via
// color-mix rather than element opacity (opacity would fade the swatches and
// controls too, making the thing you are judging harder to see), and it clears
// itself whenever the panel is closed or you leave Appearance, a settings
// panel left semi-transparent on the Logs screen just looks broken.
function setSettingsPeek(on) {
  const modal = $("settings-modal");
  const button = $("settings-peek");
  modal.classList.toggle("peeking", !!on);
  // A button that toggles has to *say* it is pressed, the class on the modal
  // is the visible half, and `aria-pressed` is the half a screen reader hears.
  if (button) {
    button.setAttribute("aria-pressed", String(!!on));
    button.classList.toggle("is-on", !!on);
  }
}

function settingsPeekIsOn() {
  return $("settings-modal").classList.contains("peeking");
}

function updatePeekAvailability(section) {
  const button = $("settings-peek");
  const appearance = section === "appearance";
  if (button) button.classList.toggle("hidden", !appearance);
  if (!appearance) setSettingsPeek(false);
}

// `scrollToId`: a quick-access link into one setting buried in a long
// section (e.g. "Search relevance (advanced)" from the Dashboard, the Ask
// sub-tab, or Chat) needs to land on that control, not just the top of
// Preferences: otherwise it's a link to "somewhere in here, scroll and
// find it yourself", which is what it was before this existed.
async function openSettingsModal(section = "models", scrollToId = null) {
  //: **The control names its own section** (INBOX 444). A caller that passes
  //: both used to be right only until the control moved: Search relevance went
  //: from General to Search and index and every link to it opened a section
  //: that no longer held it. The control is the truth, so the section is read
  //: from where it sits now, and the one the caller named is only the answer
  //: when the control is not in the markup at all.
  if (scrollToId) {
    const holder = $(scrollToId)?.closest(".settings-section");
    if (holder?.id.startsWith("settings-")) section = holder.id.slice("settings-".length);
  }
  overlayReturnFocus = document.activeElement;
  window.uiSettlingUntil = performance.now() + 400;
  //: **The window's own listeners arrive before the window does** (the gzip
  //: budget, settings-controls.js). Only the first open waits, and only for
  //: that file: once its marker constant exists this stays synchronous, so a
  //: caller that reads the window straight after the call still finds it open.
  if (typeof SETTINGS_CONTROLS_READY === "undefined") {
    await ensureModule("settingsControls");
  }
  $("settings-modal").classList.remove("hidden");
  // Runs on open rather than once at load: several sections are built
  // lazily, and a pass that ran before they existed would leave exactly the
  // rows a user is most likely to be reading uncollapsed. Idempotent, so
  // reopening costs nothing.
  collapseLongSettingHints();
  //: Your face in the head (`#settings-profile-btn`) redrawn on every open:
  //: reported still showing an older look (the owner at release) and not
  //: reproduced, so whatever path changed the look without a repaint, the
  //: window never opens on a stale one.
  paintUserMarks();
  $("settings-close").focus();
  //: The version alone: "46 entries loaded" was a debugging line (the
  //: client's cache size, drafts included) sitting beside the Health
  //: section's own count of the same thing, and the two disagreed.
  const aboutHealth = await apiJson("/health").catch(() => null);
  $("about-version").textContent = aboutHealth?.version ? `Version ${aboutHealth.version}` : "Version not available right now";
  if (typeof nameMarkBuddyMotion === "function") {
    const { mode, reason } = nameMarkBuddyMotion();
    const word = { full: "moves freely", fades: "fades only", still: "stays still" }[mode];
    $("about-motion").textContent = `Companion motion: ${word}${reason && NMB_MOTION_WHY[reason] ? `. ${NMB_MOTION_WHY[reason]}` : "."}`;
  }
  $("pref-update-check").checked = Boolean(prefsCache?.update_check_enabled);
  $("pref-auto-update").checked = Boolean(prefsCache?.auto_update_enabled);
  $("pref-update-bar").checked = prefsCache?.show_update_bar !== false;
  $("pref-update-channel-main").checked = prefsCache?.update_channel === "main";
  $("pref-update-beta").checked = prefsCache?.update_beta === true;
  $("update-check-status").textContent = "";
  $("update-version-select").classList.add("hidden");
  $("update-install-version").classList.add("hidden");
  $("update-version-status").textContent = "";
  const isDesktop = await desktopShell();
  $("desktop-console-row").classList.toggle("hidden", !isDesktop);
  $("desktop-console-hint").classList.toggle("hidden", !isDesktop);
  // Desktop-only for the same reason the console row is: there is no tray in
  // a browser tab, and a setting whose effect is unreachable reads as broken.
  $("desktop-tray-row")?.classList.toggle("hidden", !isDesktop);
  $("desktop-tray-hint")?.classList.toggle("hidden", !isDesktop);
  $("desktop-advanced-fold")?.classList.toggle("hidden", !isDesktop);
  $("desktop-companion-row")?.classList.toggle("hidden", !isDesktop);
  // Same reasoning as the tray/console rows above: /system/restart can only
  // ever do something in the packaged desktop app on Windows specifically
  // (the one platform _spawn_desktop knows how to relaunch), not desktop in
  // general: but this app's own convention (the console row just above)
  // is to gate on desktop-ness alone and let the backend's own platform
  // check be the final word, so a browser tab never even offers the button
  // while a desktop build on macOS/Linux still can, and finds out only
  // when it actually tries, rather than a client-side guess going stale
  // the moment this app ships a real relaunch for those platforms too.
  $("about-restart-row").classList.toggle("hidden", !isDesktop);
  $("open-exports-row").classList.toggle("hidden", !isDesktop);
  $("export-save-dir-row").classList.toggle("hidden", !isDesktop);
  //: The exports list is for every shell, not only the desktop: on a browser
  //: tab it is the only way back to a file the app saved (INBOX 159).
  renderExportsList();
  if (isDesktop) $("pref-export-dir").value = prefsCache?.export_save_dir || "";
  if (isDesktop) {
    $("pref-show-console").checked = Boolean(prefsCache?.show_console_on_startup);
    // Defaults to on, and `?? true` rather than `Boolean(...)` matters: an
    // install that has never touched this has no stored value, and Boolean()
    // of undefined would render the default as off.
    $("pref-close-to-tray").checked = prefsCache?.close_to_tray ?? true;
    //: Off unless chosen: a second launch brings the open window forward.
    $("pref-new-window-on-launch").checked = Boolean(prefsCache?.new_window_on_launch);
    //: Off unless chosen: the corner companion only shows once it is turned on.
    $("pref-desktop-companion").checked = Boolean(prefsCache?.desktop_companion);
  }
  // Rebuilt each open rather than once at startup: the list reflects saved
  // preferences, and those can change from another window or a restore.
  renderStatusBarSettings();
  //: The setting search's results, each long section's index and the model
  //: cards arrive with the first open (app.js `LAZY_MODULES.settingsUi`);
  //: every call into them is behind a `typeof` guard.
  await ensureModule("settingsUi");
  if (typeof renderCredits === "function") renderCredits();
  showSettingsSection(section);
  // Re-read every open, not cached: the panel shows what the *currently
  // selected* model recommends, and changing the chat model is the most likely
  // reason to come back here.
  loadSamplingSettings();
  if (!suggestedCatalog) {
    suggestedCatalog = await apiJson("/models/suggested").catch(() => null);
  }
  loadChangelog();
  //: The Models pane opens on the page's own "Checking the models…" and
  //: `renderSettings` only ran once the refresh below answered, so a status
  //: already known (the poll has run since boot) is painted at once, and one
  //: not yet known gets the pane's placeholders, which `renderSettings` takes
  //: off when it has an answer.
  if (modelStatus) renderSettings();
  else showSkeletons($("models-skeleton"), 2);
  refreshModelStatus();
  if (scrollToId) {
    requestAnimationFrame(() => {
      const found = $(scrollToId);
      if (!found) return;
      //: A deep link into a folded group opens the fold first (a closed
      //: `details.settings-fold` has no box, so the jump below would be
      //: skipped and the link would land on the section's top).
      for (let fold = found.closest("details"); fold; fold = fold.parentElement?.closest("details")) {
        fold.open = true;
      }
      // **Scroll to what the user can see, not to the element that holds the
      // value.** Every `<select>` in this app is replaced at runtime by an
      // opener button plus a menu (`enhanceSelect`), and the native control
      // is kept only for its value, its label association and the
      // accessibility tree: as a 1x1 clipped, fully transparent box.
      //
      // A deep link that targets a select id therefore scrolled to a point
      // with no visible control at it, and, worse, because it fails
      // silently: put the `flash` highlight on an invisible element, so the
      // "here is the setting you asked for" cue never appeared at all. Found
      // by measuring: the modal opened on the right section with the select
      // present and `selectInView: false`.
      //
      // `.select-shell` is the wrapper `enhanceSelect` puts around both, so
      // it is the visible representative of any enhanced select and the
      // right thing to scroll to and highlight. A select that was never
      // enhanced has no shell and is its own target, unchanged.
      const target = found.closest(".select-shell") || found;
      // A target with no layout box cannot be scrolled to or highlighted, and
      // trying is a silent no-op that looks like the deep link is broken.
      // This is a real state, not a defensive guard: several settings are
      // gated on a backend being present (`#models-config` is hidden outright
      // when no local model server is detected), so a link into one of them
      // legitimately lands on a `display: none` control. Opening the section
      // is still right, it is where the explanation lives, so only the
      // scroll and flash are skipped.
      if (!target.getClientRects().length) return;
      //: **The ring is `flashRevealed`'s now** (app.js), the one every
      //: catalogue row lands with. This used to add `flash` alone, which
      //: draws only on an element that already carries `flash-target`: the
      //: one caller whose group did (Search relevance) got a ring, and a deep
      //: link to anything else scrolled and drew nothing. Measured while
      //: making the Tools and features rows land on their settings.
      flashRevealed(target);
      // The helper takes it off again, the way flashEntry and flashReminder both already
      // do. Reported directly: "the search relevance settings section stays
      // highlighted permanently and doesn't return to normal."
      //
      // This was the one of the three flash call sites with no cleanup, and it
      // looked harmless because the animation ends on `transparent`, so on an
      // ordinary machine the highlight does fade and the stuck class is
      // invisible. Under `prefers-reduced-motion: reduce` the stylesheet
      // deliberately swaps the animation for a *static* outline and background
      // (see .flash-target.flash there), and with nothing ever removing the
      // class that static highlight is permanent. A value that is only wrong
      // under a setting the author does not have on is exactly the shape this
      // codebase keeps getting caught by.
    });
  }
}

// CHANGELOG.md, rendered in Settings, About (§36E). Loaded once per session
// and only when the settings panel is opened, it is several thousand words
// and nobody is waiting for it at startup.
let changelogLoaded = false;
//: **The changelog renders when it is opened, not when Settings is.**
//:
//: Measured during the first audit of Settings (ROADMAP.md item 7: it had
//: never been measured): `#changelog-body` held **21,452 words across ~505
//: paragraphs**, laid out on every single open of Settings -> About, while
//: the `<details>` around it showed 47 pixels of that. It is not a visual
//: problem, the fold clips it, and the panel reads as compact, which is
//: exactly why it went unnoticed. It is DOM weight and layout work for
//: content nobody has asked to see yet.
//:
//: The fetch stays eager, because its answer decides whether the control is
//: shown at all: a packaged build may not ship the file, and offering a
//: disclosure that opens onto nothing is worse than not offering one. Only
//: the render is deferred, since that is the expensive half.
//:
//: `toggle` rather than `click`: a `<details>` can also be opened by the
//: keyboard, by find-in-page, and programmatically, and `toggle` is the one
//: event that fires for all of them.
async function loadChangelog() {
  if (changelogLoaded) return;
  const fold = $("changelog-fold");
  const body = $("changelog-body");
  if (!fold || !body) return;
  const data = await apiJson("/changelog", { silent: true }).catch(() => null);
  if (!data || !data.markdown) {
    // A packaged build may not ship the file. Hiding the control is better
    // than offering one that opens onto nothing.
    fold.classList.add("hidden");
    return;
  }
  changelogLoaded = true;
  fold.classList.remove("hidden");
  const paint = () => {
    if (fold.dataset.rendered) return;
    fold.dataset.rendered = "1";
    renderMarkdown(body, data.markdown);
  };
  if (fold.open) paint(); // already open from a previous visit
  fold.addEventListener("toggle", () => {
    if (fold.open) paint();
  });
}

//: PLAN.md B9's frontend half: `GET /debug/health` already assembled every
//: number cheaply (its own docstring's whole design constraint is <20ms on
//: an empty notebook), so this just paints them, no polling, since About is
//: somewhere you glance at, not a status bar. Read once per section open,
//: the same "rebuilt each open rather than cached" rule `openSettingsModal`
//: already uses for the model-status and backup rows just above this one in
//: the file.
function paintIntegrity(check) {
  $("health-integrity").textContent = check && check.at
    ? `${check.ok ? "Sound" : `Problems: ${check.result}`} · ${Object.entries(check.index || {}).filter(([k, v]) => v && k !== "notes").map(([k, v]) => `${v} ${k} indexed`).join(", ") || "nothing indexed"} of ${check.index?.notes ?? 0} notes · ${relativeTime(check.at)}`
    : "Not checked yet";
}

$("health-integrity-check")?.addEventListener("click", async () => {
  const button = $("health-integrity-check");
  setLabel(button, "ph:spin Checking");
  try {
    paintIntegrity(await apiJson("/debug/health/integrity", { method: "POST" }));
  } catch (e) {
    toast(`The integrity check could not run: ${e.message}`, true, { action: ["Try again", () => button.click()] });
  }
  setLabel(button, "Check now");
});


// --- finding a setting (§36B) ------------------------------------------------------
//
// Eighteen sections, grouped four ways. The grouping helps, and it is only
// ever right for some people, "where do I turn off web search?" is a guess
// between The AI and System until you have learned the layout, and "where is
// the corner rounding?" is a guess even after you have.
//
// So the search looks inside each section's rendered text rather than only at
// its title. Typing "theme", "corner", "password" or "backup" then lands on
// the section that actually contains that word, which is the question people
// are really asking.
//
// Text is read live rather than indexed once: several sections are filled in
// by JS after their first paint (the model list, the tool catalog, the saved
// looks), and an index built at startup would be searching empty panels.
//
// "Live" does not have to mean "recomputed per keystroke", though, and it
// used to. `section.textContent` walks a whole subtree and builds one
// string, `.toLowerCase()` then copies it, and both ran for every one of
// them on every character typed.
//
// Measured on a fresh notebook at 1440x900 (scratchpad sweep, 2026-09-19):
// 17 sections, 63,093 characters rebuilt and lowercased per pass, 0.265 ms
// uncached against 0.005 ms cached, so 53x. A quarter of a millisecond is
// not a stall on this machine and it is not claimed to be one. It is worth
// removing anyway because of which way it moves: the sections that hold the
// most text are the ones filled in from the notebook (the model list, the
// tool catalog, the skills, the saved looks), so the cost grows with how
// much someone has, on exactly the machines least able to absorb it. The
// cache also means the input needs no debounce, which is the other way this
// gets "fixed" and the one that trades a real 200 ms delay on every
// keystroke for a saving of a quarter of one.
//
// So the string is cached per section and thrown away the moment anything
// under the modal actually changes, which is the event the "read it live"
// comment above was really about. A `WeakMap` keyed by the section element
// so a section that is ever replaced wholesale takes its entry with it.
//
// Only `childList` and `characterData` are observed, deliberately not
// `attributes`: `filterSettings` and `showSettingsSection` both toggle
// classes on elements inside this very subtree, and observing those would
// make every filter pass invalidate the cache it had just filled.
let settingsTextCache = new WeakMap();
let settingsTextCacheStale = false;
let settingsTextObserver = null;

function settingsSectionText(section) {
  if (!settingsTextObserver) {
    const modal = $("settings-modal");
    if (modal) {
      settingsTextObserver = new MutationObserver(() => {
        // One flag rather than a per-section diff: working out which
        // sections a mutation touched costs more than re-reading the one
        // section the next search actually asks about.
        settingsTextCacheStale = true;
      });
      settingsTextObserver.observe(modal, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    }
  }
  if (settingsTextCacheStale) {
    settingsTextCache = new WeakMap();
    settingsTextCacheStale = false;
  }
  const cached = settingsTextCache.get(section);
  if (cached !== undefined) return cached;
  const text = (section.textContent || "").toLowerCase();
  settingsTextCache.set(section, text);
  return text;
}

function filterSettings(term) {
  const query = term.trim().toLowerCase();
  const count = $("settings-search-count");
  const buttons = [...document.querySelectorAll("#settings-nav button[data-section]")];

  if (!query) {
    for (const button of buttons) button.classList.remove("hidden");
    for (const label of document.querySelectorAll("#settings-nav .nav-group-label")) {
      label.classList.remove("hidden");
    }
    count.classList.add("hidden");
    if (typeof renderSettingResults === "function") renderSettingResults("");
    return;
  }

  //: The topics are findable settings too: draw them on the first query, then ask again.
  if ($("help-topics")?.hasAttribute("aria-busy")) {
    window.renderHelpTopics?.()?.then(() => {
      if ($("settings-search").value.trim().toLowerCase() === query) filterSettings(query);
    });
  }
  let matches = 0;
  //: Each word, or a word meaning the same thing (settings-find.js
  //: `settingQueryAlts`, once that file has loaded): "night" keeps the
  //: section with the theme in it. Held at a word start (meaning.js,
  //: `meaningHolds`, Brief 94): "bin" is not in "binding".
  const alts = typeof settingQueryAlts === "function" ? settingQueryAlts(query) : [[query]];
  const holds = (text) =>
    text.includes(query) ||
    (typeof meaningHolds === "function" ? meaningHolds(alts, text) : alts.every((said) => said.some((w) => text.includes(w))));
  for (const button of buttons) {
    const section = $(`settings-${button.dataset.section}`);
    const hit =
      holds(button.textContent.toLowerCase()) ||
      (section && holds(settingsSectionText(section)));
    button.classList.toggle("hidden", !hit);
    if (hit) matches += 1;
  }
  // A group label with nothing under it is a heading for an empty list.
  for (const label of document.querySelectorAll("#settings-nav .nav-group-label")) {
    const group = label.nextElementSibling;
    const anyVisible =
      group && [...group.querySelectorAll("button[data-section]")].some((b) => !b.classList.contains("hidden"));
    label.classList.toggle("hidden", !anyVisible);
  }

  count.classList.remove("hidden");
  //: The settings themselves, under the field (settings-find.js).
  const settingsFound = typeof renderSettingResults === "function" ? renderSettingResults(query) : 0;
  count.textContent = settingsFound
    ? `${nounCount(settingsFound, "setting")} in ${nounCount(matches, "section")}`
    : matches
      ? nounCount(matches, "section")
      : "Nothing matches that";
  // The first match is shown rather than leaving the pane on what it was
  // (dog2 item 18: "phone" listed results over the Models pane).
  const first = settingsFound ? findSettings(query, 1)[0]?.section : buttons.find((b) => !b.classList.contains("hidden"))?.dataset.section;
  if (first) showSettingsSection(first);
}

function closeSettingsModal() {
  //: The address and the title go back to the tab under it (router.js).
  ensureModule("quickNote").then(() => routerSettle());
  const search = $("settings-search");
  if (search) {
    search.value = "";
    filterSettings("");
  }
  // Always cleared on the way out. A panel that reopens semi-transparent
  // reads as a rendering bug, not as a setting anyone chose.
  setSettingsPeek(false);
  //: A select's list escapes to <body> while it is open, so it does not go
  //: away with the window: closing Settings with one open left the list
  //: floating over the page (measured, scratchpad/ui-sweeps/menus.js).
  closeActionMenus();
  $("settings-modal").classList.add("hidden");
  overlayReturnFocus?.focus?.();
  overlayReturnFocus = null;
}

// --- logs viewer (Wave A) ---------------------------------------------------------

// The ring buffer discards its oldest record silently once it is full, which
// makes a busy hour and a quiet one look identical: 200 rows either way, with
// no way to tell whether the top row is the start of the story or the middle.
// That is worst in exactly the case the viewer exists for, chasing something
// that keeps failing, where the repetition is what pushed the first occurrence
// out of the window.
// --- the log console (§1) -------------------------------------------------
//
// Asked for directly: this screen should read "like the terminal running in
// the background, with key errors flagged", not a list you refresh by hand.
//
// One array holds both sources so a single screen answers "what just
// happened". The server's records arrive on a stream; the browser's are
// already in memory. They are merged and sorted by time, because a browser
// error and the request that caused it are the same event seen from two ends,
// and reading them apart is what made this screen hard to use.

const LOG_LEVEL_RANK = { DEBUG: 0, LOG: 0, INFO: 1, WARN: 2, WARNING: 2, ERROR: 3, CRITICAL: 4 };
const MAX_LOG_ROWS = 1000; // what the list holds; the buffers themselves are smaller

let logRecords = [];
let logStreamAbort = null;
let logStreamCursor = 0;
let logStreamRetry = null;
let logFollowPinned = true; // false once the user scrolls up to read something
let logErrorsSinceOpened = 0;
let logScreenOpen = false;
// "List" (structured rows, foldable tracebacks) or "Terminal" (raw lines,
// styled like a real console, see .log-terminal). Same persistence pattern
// as timeline-view: a per-browser display preference, not
// something worth round-tripping through /preferences.
let logView = prefs.get("logView", null) === "terminal" ? "terminal" : "list";

function logLevelRank(level) {
  return LOG_LEVEL_RANK[String(level || "").toUpperCase()] ?? 1;
}

// The ring buffer discards its oldest record silently once it is full, which
// makes a busy hour and a quiet one look identical: the same rows either way,
// with no way to tell whether the top row is the start of the story or the
// middle. That is worst in exactly the case the viewer exists for, chasing
// something that keeps failing, where the repetition is what pushed the first
// occurrence out of the window.
function renderLogGap(stats) {
  const note = $("logs-dropped");
  if (!stats || !stats.dropped) {
    note.classList.add("hidden");
    note.textContent = "";
    return;
  }
  const since = stats.dropped_since
    ? ` The oldest record still kept is from ${new Date(stats.dropped_since).toLocaleTimeString()}.`
    : "";
  note.textContent =
    `${stats.dropped.toLocaleString()} earlier record${stats.dropped === 1 ? "" : "s"} ` +
    `dropped: this log keeps the most recent ${stats.capacity.toLocaleString()}.${since}`;
  note.classList.remove("hidden");
}

function browserLogRecords() {
  return browserLogs.map((r, index) => ({
    ...r,
    source: "browser",
    logger: r.logger || "browser",
    key: `b${index}-${r.time}`,
  }));
}

function serverLogRecord(record) {
  return { ...record, source: "server", key: `s${record.seq}` };
}

function sortLogRecords() {
  // Stable on equal timestamps, so records logged in the same millisecond keep
  // the order they arrived rather than shuffling on every repaint.
  logRecords.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  if (logRecords.length > MAX_LOG_ROWS) {
    logRecords = logRecords.slice(-MAX_LOG_ROWS);
  }
}

function logMatchesFilters(record) {
  if (!record) return false;
  const source = $("log-source").value;
  if (source !== "all" && record.source !== source) return false;

  //: One line per HTTP request (uvicorn.access) is a server's diary, not the
  //: app's: forty of them on every start buried the records a person opens
  //: this pane to read (INBOX 472). Off unless asked for.
  if (record.logger === "uvicorn.access" && !$("log-requests").checked) return false;

  const level = $("log-level").value;
  if (level === "warning" && logLevelRank(record.level) < 2) return false;
  if (level === "error" && logLevelRank(record.level) < 3) return false;

  const needle = $("log-filter").value.trim().toLowerCase();
  if (!needle) return true;
  return (
    String(record.message || "").toLowerCase().includes(needle) ||
    String(record.logger || "").toLowerCase().includes(needle)
  );
}

function logRow(record) {
  const li = document.createElement("li");
  const rank = logLevelRank(record.level);
  if (rank >= 3) li.classList.add("log-error");
  else if (rank === 2) li.classList.add("log-warn");

  const when = document.createElement("span");
  when.className = "when";
  when.textContent = new Date(record.time).toLocaleTimeString();

  const level = document.createElement("span");
  level.className = "what";
  level.textContent = record.level;

  // Which side of the app said it. Only worth showing in the merged view, 
  // in a single-source view every row would carry the same tag.
  const line = document.createElement("span");
  line.className = "log-line";
  if ($("log-source").value === "all") {
    const tag = document.createElement("span");
    tag.className = `log-source-tag log-source-${record.source}`;
    tag.textContent = record.source === "browser" ? "browser" : "server";
    line.appendChild(tag);
  }
  const text = document.createElement("span");
  text.textContent = record.logger ? `${record.logger}: ${record.message}` : record.message;
  line.appendChild(text);

  // One record, copyable on its own. "Copy all" plus the filters can already
  // narrow to a single error, but that is a three-step answer to "send me that
  // error", and hand-selecting a row whose traceback lives in its own
  // scrolling box is worse. This copies the record AND its traceback together,
  // which is the thing anyone actually wants to paste.
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "log-copy ghost small";
  setLabel(copy, "ph:clipboard");
  copy.title = "Copy this record (with its traceback)";
  copy.setAttribute("aria-label", `Copy this ${record.level} record`);
  copy.addEventListener("click", async (event) => {
    event.stopPropagation(); // never toggles the fold it sits beside
    if (await copyToClipboard(logRecordText(record), copy)) toast("Record copied.");
  });

  li.append(when, level, line, copy);

  // A traceback is the difference between "something failed" and knowing
  // what. Folded, because it is many lines and most rows do not have one.
  if (record.trace) {
    const fold = document.createElement("details");
    fold.className = "log-trace";
    const summary = document.createElement("summary");
    summary.textContent = "Traceback";
    const pre = document.createElement("pre");
    pre.textContent = record.trace; // real newlines here: it is not a row
    const copyTrace = document.createElement("button");
    copyTrace.type = "button";
    copyTrace.className = "ghost small";
    copyTrace.textContent = "Copy traceback";
    copyTrace.addEventListener("click", async () => {
      if (await copyToClipboard(record.trace, copyTrace)) toast("Traceback copied.");
    });
    fold.append(summary, pre, copyTrace);
    li.appendChild(fold);
  }
  return li;
}

// One record as the text you would paste into a bug report. The source tag is
// always included here even though the row only shows it in the merged view, 
// out of context, "which half of the app said this" is the first question.
function logRecordText(record) {
  const head =
    `${record.time} [${record.source}] ${record.level} ` +
    `${record.logger || ""} ${record.message}`.trimEnd();
  return record.trace ? `${head}\n${record.trace}` : head;
}

function activeLogContainer() {
  return $(logView === "terminal" ? "log-terminal" : "log-list");
}

function nearLogBottom() {
  const list = activeLogContainer();
  // 40px of slack: "close enough to the bottom that you meant to be there".
  return list.scrollHeight - list.scrollTop - list.clientHeight < 40;
}

function scrollLogToBottom() {
  const list = activeLogContainer();
  list.scrollTop = list.scrollHeight;
}

// Shared by both views: the empty state, the "N hidden by filters" note, and
// the copy-button label all describe the filtered set, not how it is drawn.
function renderLogSharedUI(visibleCount) {
  //: The empty state recipe (Library, Bookmarks): shown instead of an empty
  //: bar, in place of the list and the terminal. "Nothing matches" and
  //: "nothing happened" are different answers, and only the first one is
  //: fixed by changing the filter.
  const none = visibleCount === 0;
  const hiddenCount = logRecords.length - visibleCount;
  $("log-list").classList.toggle("log-none", none);
  $("log-terminal").classList.toggle("log-none", none);
  $("logs-empty").classList.toggle("hidden", !none);
  if (none) {
    const nothing = logRecords.length === 0;
    $("logs-empty-title").textContent = nothing
      ? "No log records yet"
      : settingsLook.logFilterFromRun ? "This job wrote no log lines" : "No log lines match";
    $("logs-empty-text").textContent = nothing
      ? "Records appear here as the app runs."
      : settingsLook.logFilterFromRun
        ? "Only runs since the app last started write lines here. Clear the filters to see every record."
        : "Nothing fits the filters above.";
    $("logs-empty-clear").classList.toggle("hidden", nothing);
  }
  const filtered = $("logs-filtered-out");
  if (hiddenCount > 0 && !none) {
    filtered.textContent = `${hiddenCount.toLocaleString()} record${hiddenCount === 1 ? "" : "s"} hidden by the filters above.`;
    filtered.classList.remove("hidden");
  } else {
    filtered.classList.add("hidden");
  }
  renderCopyLogsLabel();
}

function renderLogList() {
  const list = $("log-list");
  const shouldStick = $("log-follow").checked && logFollowPinned;
  const visible = logRecords.filter(logMatchesFilters);

  list.replaceChildren();
  // **Deliberately not `renderIncrementally`, unlike every other list here.**
  // Two reasons, and the second is the disqualifying one. This list is already
  // bounded, `MAX_LOG_ROWS` (1000) is a real cap, not an unbounded notebook , 
  // so the problem the incremental renderer solves is one the cap has already
  // solved. And the log's "follow" mode scrolls to the *newest* row, which
  // sits at the end: a renderer that paints the first chunk and fills in
  // towards the end as you scroll would leave follow mode scrolling to the
  // bottom of whatever happened to be painted, not to the newest line. Making
  // this incremental would mean inverting the window, which is a different
  // mechanism built to fix a cost that is already capped.
  for (const record of visible) list.appendChild(logRow(record));

  renderLogSharedUI(visible.length);
  if (shouldStick) scrollLogToBottom();
}

// One line the way it would print to a real console: "HH:MM:SS LEVEL   logger
//, message", level padded like uvicorn's own default formatter pads
// "INFO:"/"WARNING:"/"ERROR:" so a column of mixed levels still lines up.
function logTerminalParts(record) {
  const when = new Date(record.time).toLocaleTimeString();
  const level = `${record.level}:`.padEnd(9);
  const body = record.logger ? `${record.logger}: ${record.message}` : record.message;
  return [`${when} ${level}`, body];
}

function logTerminalRow(record) {
  const line = document.createElement("div");
  line.className = "log-term-line";
  const rank = logLevelRank(record.level);
  if (rank >= 3) line.classList.add("is-error");
  else if (rank === 2) line.classList.add("is-warn");
  // Two cells, so a long message wraps under where the message starts, not
  // under the time (owner, 2026-10-12).
  const [lead, body] = logTerminalParts(record);
  const head = document.createElement("span");
  head.className = "log-term-head";
  head.textContent = lead;
  const text = document.createElement("span");
  text.className = "log-term-body";
  text.textContent = body;
  line.append(head, text);
  return line;
}

// A real terminal never folds a traceback behind a click, so this view
// doesn't either: every line prints, indented, right under the record that
// raised it. That is the one real advantage this view has over List, not
// just a different coat of paint on the same data.
function logTerminalTraceRow(record) {
  const trace = document.createElement("div");
  trace.className = "log-term-trace";
  trace.textContent = record.trace;
  return trace;
}

function renderLogTerminal() {
  const el = $("log-terminal");
  const shouldStick = $("log-follow").checked && logFollowPinned;
  const visible = logRecords.filter(logMatchesFilters);

  el.replaceChildren();
  for (const record of visible) {
    el.appendChild(logTerminalRow(record));
    if (record.trace) el.appendChild(logTerminalTraceRow(record));
  }

  renderLogSharedUI(visible.length);
  if (shouldStick) scrollLogToBottom();
}

function renderActiveLogView() {
  if (logView === "terminal") renderLogTerminal();
  else renderLogList();
}

function setLogLive(state, detail) {
  const pill = $("log-live");
  setLabel(pill, detail);
  pill.dataset.state = state;
}

// Errors that have arrived since the screen was last opened, shown on the nav
// item so a failure in the background is noticed without going looking.
function bumpLogErrorBadge(record) {
  if (logScreenOpen || logLevelRank(record.level) < 3) return;
  logErrorsSinceOpened += 1;
  renderLogErrorBadge();
}

function renderLogErrorBadge() {
  const link = document.querySelector('#settings-nav button[data-section="logs"]');
  if (!link) return;
  let badge = link.querySelector(".log-error-badge");
  if (!logErrorsSinceOpened) {
    badge?.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "log-error-badge";
    // Clicking the badge opens the Logs screen already filtered to errors.
    // Set synchronously so it is in place before renderLogs() draws: the
    // badge is the only place a failure announces itself, so it should also
    // be the shortest way to the failure itself.
    badge.addEventListener("click", () => {
      $("log-source").value = "all";
      $("log-level").value = "error";
      $("log-filter").value = "";
    });
    link.appendChild(badge);
  }
  badge.textContent = logErrorsSinceOpened > 99 ? "99+" : String(logErrorsSinceOpened);
  badge.title = `${nounCount(logErrorsSinceOpened, "error")} since you last looked at the logs, click to show just those`;
}

// NDJSON over fetch rather than an EventSource, for one blunt reason:
// EventSource cannot set request headers, and this app authenticates with
// X-Auth-Token. The usual workaround is to put the token in the query string,
// which would write it into the very log this stream is serving.
async function startLogStream() {
  stopLogStream();
  const controller = new AbortController();
  logStreamAbort = controller;
  setLogLive("connecting", "connecting…");
  try {
    // `api.stream` (F5), silent: a refusal throws into the reconnect below.
    const response = await api.stream(`/logs/stream?after=${logStreamCursor}`, {
      silent: true,
      signal: controller.signal,
    });
    if (!response.body) throw new Error("stream failed");
    setLogLive("live", "ph:broadcast live");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffered = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffered += decoder.decode(value, { stream: true });
      const lines = buffered.split("\n");
      buffered = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        let event;
        try {
          event = JSON.parse(line);
        } catch {
          continue; // a torn line is not worth dropping the stream over
        }
        if (event.type === "open") {
          logStreamCursor = Math.max(logStreamCursor, event.cursor || 0);
        } else if (event.type === "record") {
          logStreamCursor = event.record.seq || logStreamCursor;
          logRecords.push(serverLogRecord(event.record));
          bumpLogErrorBadge(event.record);
          sortLogRecords();
          if (logScreenOpen) renderActiveLogView();
        } else if (event.type === "ping") {
          logStreamCursor = event.cursor || logStreamCursor;
        } else if (event.type === "reconnect") {
          break; // the server handed back; reconnect below picks up the cursor
        }
      }
    }
  } catch (error) {
    if (controller.signal.aborted) return; // we closed it on purpose
    setLogLive("offline", "reconnecting…");
  }
  if (controller.signal.aborted) return;
  // Reconnect while the screen is open. The cursor means the gap is closed on
  // the way back rather than left as a hole in the middle of the log.
  if (logScreenOpen) {
    logStreamRetry = setTimeout(startLogStream, 2000);
  } else {
    setLogLive("paused", "paused");
  }
}

function stopLogStream() {
  if (logStreamRetry) {
    clearTimeout(logStreamRetry);
    logStreamRetry = null;
  }
  if (logStreamAbort) {
    logStreamAbort.abort();
    logStreamAbort = null;
  }
}

async function renderLogs() {
  logScreenOpen = true;
  logErrorsSinceOpened = 0;
  renderLogErrorBadge();

  //: The first open has an empty list and a fetch ahead of it; a reopen finds
  //: its rows already there and `showSkeletons` leaves them alone.
  showSkeletons($("log-list"), 4, "li");
  const [records, stats] = await Promise.all([
    apiJson("/logs?limit=500").catch(() => null),
    apiJson("/logs/stats?limit=500").catch(() => null),
  ]);
  clearSkeletons($("log-list"));
  if (!records) {
    const note = $("logs-dropped");
    note.textContent = "Could not load the server log. The records from this browser are shown.";
    note.classList.remove("hidden");
  }
  const served = records || [];
  logStreamCursor = served.length ? served[served.length - 1].seq || 0 : 0;
  logRecords = [...served.map(serverLogRecord), ...browserLogRecords()];
  sortLogRecords();
  renderLogGap(stats);
  renderActiveLogView();
  scrollLogToBottom();
  logFollowPinned = true;
  startLogStream();
}

// Leaving the screen closes the connection. A stream held open by a tab
// nobody is looking at is the kind of thing that is invisible until it is a
// hundred of them.
function closeLogs() {
  logScreenOpen = false;
  stopLogStream();
  // Said here rather than left to the stream's own exit path: a deliberate
  // abort returns early from there, so the pill would still read "● live"
  // with nothing behind it, a status that lies is worse than none.
  setLogLive("paused", "paused");
}

async function copyLogs() {
  const shown = logRecords.filter(logMatchesFilters);
  if (!shown.length) {
    toast("Nothing to copy: the filters above are hiding every record.", "info");
    return;
  }
  const text = shown.map(logRecordText).join("\n");
  if (await copyToClipboard(text)) {
    toast(`Copied ${nounCount(shown.length, "record")}.`);
  }
}

// The button copies what is ON SCREEN, not the whole buffer, so it has to say
// which. "Copy all" while a filter hides 400 records is a promise it does not
// keep: and the reader would not find out until they pasted it.
function renderCopyLogsLabel() {
  const button = $("logs-copy");
  if (!button) return;
  const shown = logRecords.filter(logMatchesFilters).length;
  const filtering = shown !== logRecords.length;
  //: `setLabel`, not `textContent`: this is a row in the Logs dock's kebab
  //: now, so the label carries an icon, and writing the text directly would
  //: delete it the first time a filter changed. The same trap the Support
  //: bundle button was already in (it restored `textContent` after a run and
  //: dropped its own icon), fixed the same way.
  setLabel(button, filtering ? `ph:copy Copy ${shown} shown` : "ph:copy Copy all");
  button.title = filtering
    ? "Copies only the records the filters are showing"
    : "Copies every record in this list, tracebacks included";
}

// Jump straight from "something failed while I was elsewhere" to the failures
// themselves. The badge is the only place an error announces itself, so it
// should also be the way to reach one.
async function clearLogs() {
  const source = $("log-source").value;
  if (source !== "browser") {
    //: Said when it fails (audit 2026-10-05, FE-12).
    const cleared = await api("/logs", { method: "DELETE" }).then(
      () => true,
      (error) => {
        toast(error.message || "Couldn't clear the server log.", true);
        return false;
      }
    );
    if (!cleared) return;
  }
  if (source !== "server") {
    browserLogs.length = 0;
  }
  logRecords = [];
  await renderLogs();
}

// The bundle is built server-side and downloaded straight to disk. Nothing is
// transmitted anywhere: that is the whole difference between this and the
// crash reporting the roadmap turned down.
async function downloadSupportBundle() {
  const button = $("logs-bundle");
  setBusy(button, true, "Collecting…");
  try {
    const response = await api("/support-bundle").catch(() => {
      throw new Error("Couldn't build the support bundle. Try again.");
    });
    await saveFile("tessellate-support-bundle.zip", await response.blob());
    toast("Support bundle saved. Have a look inside before you send it.");
  } catch (error) {
    toast(error.message || "Couldn't build the support bundle.", true);
  } finally {
    setBusy(button, false);
  }
}

// --- theme ----------------------------------------------------------------------

//: **A theme switch is one repaint, not a cross-fade and two canvas
//: rebuilds** (INBOX 202, the owner: "switching between light and dark mode
//: is realllly glitchy and takes a bit to load").
//:
//: Measured before this (`scratchpad/ui-sweeps/chrome202.js`,
//: `chrome202art.js`, headless at 1440x900): the click starts 24 CSS
//: transitions, on background-color and the four border colours, running
//: 120ms, 160ms and 200ms depending on which rule the surface got its
//: transition from. That is what "glitchy" describes: the app does not
//: change theme, it dissolves into the other one at three speeds at once,
//: while the 79 `backdrop-filter` surfaces re-composite over a ground that is
//: itself still moving.
//:
//: And the two generative canvases are torn down and rebuilt *inside the
//: click*: `startBgArt()` removes the p5 instance and its canvas and builds a
//: new sketch, and `refreshArtForTheme()` does the same to the dashboard
//: constellation. With the background art on, the click's own synchronous
//: work measured 10.9ms against 7.4ms with it off, and the canvas is visibly
//: absent while it is rebuilt, which is the "takes a bit to load" half.
//:
//: So: the colours are applied with transitions suppressed, which makes the
//: switch a single frame, and the canvas work is moved off the click to the
//: frame after the new colours have painted. Both rebuilds are coalesced, so
//: pressing the toggle five times rebuilds the art once rather than five
//: times.
let themeArtTimer = 0;

function repaintThemeAtOnce(apply) {
  const root = document.documentElement;
  root.classList.add("theme-switching");
  apply();
  //: Force the new custom properties to be computed while the suppression is
  //: still on, so no transition can be started from the old values.
  void getComputedStyle(root).backgroundColor;
  //: Two frames: one for the browser to paint the new colours, one to be sure
  //: that paint has happened before transitions are allowed back. Removing it
  //: in the first frame re-arms them against values that have not landed yet,
  //: which is the same cross-fade with extra steps.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => root.classList.remove("theme-switching"));
  });
}

function scheduleThemeArt() {
  if (themeArtTimer) cancelAnimationFrame(themeArtTimer);
  themeArtTimer = requestAnimationFrame(() => {
    themeArtTimer = 0;
    if (bgArtOn()) startBgArt();
    //: The dashboard constellation reads light-or-dark when it is built, so
    //: it is rebuilt too; it returns immediately when the dashboard is not on
    //: screen.
    refreshArtForTheme();
  });
}

function toggleTheme() {
  const root = document.documentElement;
  // Current effective theme: explicit choice, else the OS preference.
  const current =
    root.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  prefs.set("theme", next); // remembered across restarts

  repaintThemeAtOnce(() => {
    root.dataset.theme = next;
    // Clear any custom background colour that would otherwise override the new theme
    prefs.remove("page-bg");
    prefs.remove("page-bg-dark");
    applyPageBackground(null);
    if (document.getElementById("page-bg-custom")) {
      document.getElementById("page-bg-custom").value = "#f5f7fb";
    }
    applyResolvedMode();
  });
  scheduleThemeArt();
}

// --- Wave J: accent themes + generative background --------------------------------

// Simple accent presets. The colours themselves live in the CSS
// (:root[data-accent="…"]); this list just drives the swatch picker and
// gives the background art a hue to paint with.
const ACCENTS = [
  //: "indigo" is the stored name; it means the palette's own accent (Quiet's
  //: ink blue by default), so it is labelled Default (owner, 2026-10-12).
  { name: "indigo", label: "Default", swatch: "#4664f0" },
  { name: "emerald", label: "Emerald", swatch: "#0e9f6e" },
  { name: "rose", label: "Rose", swatch: "#ec4899" },
  { name: "amber", label: "Amber", swatch: "#d97706" },
  { name: "violet", label: "Violet", swatch: "#7c3aed" },
  { name: "teal", label: "Teal", swatch: "#0d9488" },
  { name: "sky", label: "Sky", swatch: "#0ea5e9" },
  { name: "lime", label: "Lime", swatch: "#65a30d" },
  { name: "crimson", label: "Crimson", swatch: "#dc2626" },
  { name: "fuchsia", label: "Fuchsia", swatch: "#c026d3" },
  { name: "slate", label: "Slate", swatch: "#475569" },
  { name: "sunset", label: "Sunset", swatch: "#f97316" },
  { name: "ocean", label: "Ocean", swatch: "#2563eb" },
  { name: "mint", label: "Mint", swatch: "#10b981" },
  { name: "grape", label: "Grape", swatch: "#9333ea" },
  //: Brief 95 (INBOX 858, "add more colour options"): nine more, chosen to
  //: fill the wheel's gaps (coral, gold, forest, navy, cyan, berry, olive,
  //: copper, lavender). Each is a fill; `accentTone` lifts or deepens it per
  //: mode, so none needs a CSS rule of its own.
  { name: "coral", label: "Coral", swatch: "#e8604c" },
  { name: "gold", label: "Gold", swatch: "#b8860b" },
  { name: "forest", label: "Forest", swatch: "#2f7d32" },
  { name: "navy", label: "Navy", swatch: "#1e3a8a" },
  { name: "cyan", label: "Cyan", swatch: "#0891b2" },
  { name: "berry", label: "Berry", swatch: "#be185d" },
  { name: "olive", label: "Olive", swatch: "#6b7a1f" },
  { name: "copper", label: "Copper", swatch: "#b4642d" },
  { name: "lavender", label: "Lavender", swatch: "#8b7cf6" },
];

function activeAccent() {
  // Goes through appearancePref so a theme's accent applies until you pick
  // one yourself, at which point yours wins.
  return appearancePref("accent");
}

// The colour the app is *actually* wearing right now. The generative art used
// to look this up from the ACCENTS list via localStorage, which only knows
// about the accent picker, so a curated palette changed every surface in the
// app except the two canvases, leaving them wearing the previous theme. The
// computed variable is the one source of truth once palettes can set it too.
function currentAccentHex() {
  const computed = getComputedStyle(document.documentElement)
    .getPropertyValue("--accent")
    .trim();
  if (computed) return computed;
  return (
    prefs.get("accent-custom", null) ||
    (ACCENTS.find((a) => a.name === activeAccent()) || ACCENTS[0]).swatch
  );
}

function applyAccent(name, remember = true) {
  // applyThemePreset re-applies the theme's accent without recording it as a
  // manual choice: otherwise merely picking a theme would pin its colour as
  // an override and the next theme couldn't change it.
  if (remember) prefs.set("accent", name);
  applyEffectiveAccent();
  if (bgArtOn()) startBgArt(); // repaint the background in the new accent
  refreshArtForTheme(); // its wash is painted from the accent as well
  renderBrandLogo(); // recolour the emblem too
}

// Which accent the app actually wears, decided in one place.
//
// Two bugs came out of not having this. Both were reported as "with a theme
// selected, the individual colour controls can't be changed":
//
// 1. The accent swatches did nothing under any theme. `[data-accent]` rules
//    live at the top of the stylesheet and `[data-palette]` rules near the
//    bottom, both `:root[data-…]` and so both specificity (0,2,0): so the
//    palette won on source order alone, every time. Since every theme selects
//    a palette, picking an accent was visibly dead the moment a theme was on.
// 2. Clearing a manual accent left it applied. `applyAppearance` re-applied
//    every other setting but never the accent, so "clear my changes" removed
//    the stored value and the picker showed nothing selected while the app
//    carried on wearing the old colour.
//
// An explicit pick is written as an inline custom property, which beats any
// stylesheet rule and so beats the palette. No pick means no inline property,
// leaving the palette to supply the colour as it should. That is the
// documented layering, your change → theme → default, applied to colour.
// It owns `data-accent` as well as the inline property. Keeping the attribute
// in step matters even though the inline colour is what wins: the pre-paint
// script in index.html sets it from localStorage to avoid a flash, so a stale
// attribute survives a reload and re-colours the app from the stylesheet the
// moment the inline property is removed. That is what kept a cleared accent
// visible after "clear my changes".
function applyEffectiveAccent() {
  const root = document.documentElement;
  const custom = prefs.get("accent-custom", null);
  // Only a *stored* accent is a deliberate choice; a theme never sets one.
  const chosen = prefs.get("accent", null);
  //: "indigo" is the stored name of Default, which is no accent: the palette's
  //: own shows (B57: picking Default after a colour painted the swatch's
  //: fallback #4664f0 inline over every palette).
  const preset = chosen && chosen !== "indigo" ? ACCENTS.find((a) => a.name === chosen) : null;
  if (preset) root.dataset.accent = preset.name;
  else delete root.dataset.accent;
  if (custom) return applyCustomAccent(custom); // a picked hex wins outright
  applyCustomAccent(preset ? preset.swatch : null);
}

function contrastOn() {
  return prefs.get("contrast", null) === "on";
}

function applyContrast(on) {
  if (on) document.documentElement.dataset.contrast = "on";
  else delete document.documentElement.dataset.contrast;
  prefs.set("contrast", on ? "on" : "off");
}

// --- Wave O: expanded appearance controls -------------------------------------------
// Each preference is a data-attribute on <html> + a localStorage key, all
// applied before first paint by applyAppearance() so there's no flash.
const APPEARANCE_DEFAULTS = {
  fontsize: "normal",
  font: "system", // system | serif | mono
  density: "comfortable", // comfortable | compact | spacious
  glass: "on",
  // Performance mode (INBOX 49): "auto" turns it on for a small machine, 4
  // cores or 4 GB or fewer, and when the operating system asks for reduced
  // transparency; "on" and "off" are the person's own word. On, it takes the
  // glass blur and the animations off and runs the graph's physics at half
  // rate, whatever the three settings below say, without rewriting them, so
  // turning it back off restores exactly the look that was chosen.
  perf: "auto", // auto | on | off
  motion: "auto", // "auto" = follow the OS; "reduced" = force-still
  // Interface animations (the polish set): on plays them whatever reduced
  // motion says; off makes them instant (00-tokens-shell.css, `--ui-*`).
  "ui-motion": "on",
  // Background movement, separate from the interface-wide motion setting.
  // "auto" follows reduced-motion; "moving" is an explicit request that
  // overrides it; "still" never moves. This key was missing entirely, which
  // left the picker rendering blank (selectedIndex -1): so choosing "Moving"
  // looked like it did nothing, and there was no way at all to get the art
  // moving on a machine with reduced motion turned on.
  // "auto" follows the reduced-motion setting; "moving" is an explicit
  // request that overrides it; "still" never moves. This key was declared
  // twice, once here as "auto" and again below as "moving", after two
  // sessions fixed the same blank-picker bug independently. The later
  // declaration silently won, so the documented default was not the one
  // anybody got. One declaration, matching the <option> list and the hint
  // text that explains what "auto" means.
  "bg-motion": "auto", // auto | moving | still
  //: **Progress indicators, separate from everything above, and defaulting
  //: to "always" on purpose.** The background art's own key is the shape this
  //: copies; the *default* is what differs, and the reason is the whole point
  //: of the setting. Reported with a screenshot of a frozen "Thinking…":
  //: "the thinking and writing animation is completely broken, doesn't move."
  //: The app's Reduce motion had turned it into one static italic word, 
  //: which is also exactly what a hung app shows, so the setting had made the
  //: interface unable to tell the user whether anything was happening.
  //:
  //: Turning off "animations and transitions" is a statement about chrome. A
  //: spinner is not chrome. "always" keeps progress moving through this app's
  //: own Reduce motion; the *operating system's* accessibility setting is
  //: still obeyed (see `progressMotionWanted` in chat.js), and the indicator
  //: steps through a colour rather than freezing when it is.
  "progress-motion": "always", // always | auto | still
  //: The rotating word beside those same dots (chat.js's `wantsThinkingWords`,
  //: sheets-selects.js): on by default, since it is the feature being asked
  //: for. This table is only read for the Settings checkbox's own render;
  //: `wantsThinkingWords` reads `localStorage` directly.
  "show-thinking-words": "on", // on | off
  //: Generated faces (`nameMark`, avatars.js) blink and emote. Always by
  //: default (the owner: "I want the avatars animated by default"); only
  //: the faces on screen move (`watchNameMark`), so a long list costs what
  //: its visible rows cost. On hover and Off remain one click away.
  "avatar-motion": "always", // always | hover | off
  "avatar-follow": "on", // on | off
  "avatar-buddy": "off", // off | me | persona | atlas | custom
  //: How Atlas is drawn everywhere (atlas.js): the character, or the classic
  //: globe the owner asked to keep as a choice.
  "atlas-style": "character", // character | classic
  //: Which face the assistant's chat heads wear (chat-agent.js,
  //: `assistantAvatar`): Atlas, or the app's animated emblem. Atlas is what
  //: every head wore before the choice existed.
  "assistant-avatar": "atlas", // atlas | emblem
  //: Atlas's look (atlas.js, `atlasLook`). Auto, the default, follows Face
  //: looks (feminine there is a feminine Atlas, anything else masculine), and
  //: the select says so: it used to read Masculine while nothing was stored
  //: and Atlas was following Face looks anyway (OPEN.md, 0.3.3).
  "atlas-look": "auto", // auto | masculine | feminine
  "face-look": "mixed", // mixed (shown as Neutral) | masculine | feminine
  "dash-mark": "logo", // logo | atlas | me | persona
  // Half strength (was 90): a professional product has a quiet page
  // (UI_MODERNISATION_PLAN Phase 3). theme-boot.js and index.html carry the
  // same default: keep the three in step.
  "bg-intensity": "45",
  radius: "14", // global corner rounding, px
  // 14px, not 18. Blur radius is the exponential term in a backdrop-filter's
  // cost, and the published band worth staying inside is 8-15px. The slider
  // still reaches higher for anyone who wants it; this is what a fresh
  // profile gets. See `.glass` in css/03-dashboard-widgets.css for the
  // measured layer counts this multiplies across.
  "glass-blur": "14", // frosted-glass blur strength, px
  // Percent of a card's own base alpha that survives, separate dial from
  // blur strength above (how frosted vs. how clear). 100 renders identically
  // to before this setting existed.
  "glass-opacity": "100",
  // Off by default even while glass itself is on, a diagonal highlight is a
  // stronger visual statement than the blur/opacity dials above, worth
  // opting into rather than imposing. Turning glass on from off auto-sets
  // this to "on" (see #glass-toggle's own listener), so the full look shows
  // up without a second trip to Settings; unchecking #glass-sheen-toggle
  // afterward turns just the sheen back off without touching glass itself.
  "glass-sheen": "off",
  // Icon buttons in the same glass (css/glass-controls-lazy.css, fetched only
  // while this is on), and only while the glass look itself is on.
  "glass-controls": "off",
  // The flat looks' soft ground light (owner: "maybe it can be togglable").
  "page-wash": "on",
  // 0-100, how strong the sheen reads when it's on: its own dial, separate
  // from whether it's on at all.
  "glass-sheen-strength": "100",
  zoom: "100", // §37E: interface-wide scale, percent: multiplies the root font-size
  "bg-style": "aurora", // aurora | constellation | waves | bubbles | mesh | microbes | mycelium | dusk | ripples | fireflies | rain | wander | drift
  palette: "default", // which curated colour set; themes select one
  // No accent by default: the palette supplies the colour until you pick one
  // yourself. Named here so appearancePref("accent") has a defined answer
  // rather than returning undefined and relying on a lookup miss.
  accent: "indigo",
  // Both of these arrived with their Settings controls and neither was listed
  // here, which is not a cosmetic omission, it took the borders and shadows
  // off the entire interface. `applyAppearance` writes them onto <html> as
  // custom properties, so a missing default became the literal strings
  // "undefined" and "NaN" on the root element. `border-style: undefined` is
  // invalid, so `border-style: var(--border-style) !important`, which is
  // `!important` and matches .card, input, textarea, select, .modal and
  // .sidebar: computed to `none` for all of them. `--shadow-intensity: NaN`
  // poisoned `--glass-shadow`'s rgba(), so every card's box-shadow computed to
  // `none` as well. The app rendered completely flat and borderless on a fresh
  // profile, and stayed that way until you happened to touch both controls.
  "border-style": "solid", // solid | dashed | none
  "shadow-intensity": "5", // percent; divided by 100 into --shadow-intensity
  // Matches the pre-paint script's own `pref("theme", "system")`. Without it
  // `applyThemeChoice(undefined)` took the else branch and stamped
  // `data-theme="undefined"` onto <html> on every fresh profile. The app still
  // looked right, because the palettes key off the resolved `data-mode`, but
  // it left a live element attribute that is neither "light", "dark" nor
  // absent, so any rule written as `:root:not([data-theme])` to mean "following
  // the system" would quietly never match.
  theme: "system", // light | dark | system
};

// --- curated visual themes ---------------------------------------------------------
// A theme is just a bundle of the same settings the individual controls write,
// so nothing here is a separate system that could drift from them. It sits as a
// LAYER between the app defaults and your own choices:
//
//     your manual change  →  the selected theme  →  the app default
//
// which is what makes "apply manual colour changes over a selected theme" work
// (user request). Picking a theme never erases a manual setting, and clearing a
// manual setting falls back to the theme rather than to the app default.
// A theme is a COMPLETE look: which colour palette to wear, plus the
// typography and shape that go with it. It deliberately does not carry colours
// of its own: main's palettes already own colour, with a matched light and
// dark set each, and a theme that also set `accent` would silently lose to
// them ([data-palette] rules come later in the stylesheet and win at equal
// specificity). One mechanism for colour, one for everything else.
//
// It sits as a LAYER between the app defaults and your own choices:
//
//     your manual change  →  the selected theme  →  the app default
//
// which is what makes "apply manual colour changes over a selected theme"
// work. Picking a theme never erases a manual setting, and clearing a manual
// setting falls back to the theme rather than to the app default.
const DEFAULT_THEME_PRESET = "utilitarian";

const THEME_PRESETS = {
  //: **Quiet utilitarian is the default look** (UI_MODERNISATION_PLAN
  //: decisions, 2026-09-23): used whenever no look has been chosen, see
  //: `activeThemePreset`. The old default is "Classic", kept exactly.
  //: No density of its own: it once set compact, which as the default
  //: scaled every spacing token to 0.75 across the app (owner: "the
  //: dashboard feels squished now"). Quiet is flat colour and small radii,
  //: not less room; density stays the reader's choice.
  utilitarian: {
    label: "Quiet utilitarian",
    values: { palette: "utilitarian", glass: "off", radius: "8" },
  },
  default: {
    label: "Classic",
    values: { palette: "default", glass: "on", radius: "14" },
  },
  paper: {
    label: "Editorial paper",
    values: { palette: "paper", glass: "off", radius: "4" },
  },
  mono: {
    label: "Technical mono",
    values: { palette: "mono", glass: "off", radius: "2", density: "compact" },
  },
  manuscript: {
    label: "Manuscript",
    values: {
      palette: "parchment", font: "serif", glass: "off",
      radius: "6", density: "spacious",
    },
  },
  terminal: {
    label: "Terminal",
    values: {
      palette: "carbon", font: "mono", glass: "off",
      radius: "2", density: "compact",
    },
  },
  study: {
    label: "Sage Study",
    values: { palette: "sage", font: "serif", glass: "on", radius: "16" },
  },
  abyss: {
    label: "Deep Ocean",
    values: {
      palette: "ocean", glass: "on", "glass-blur": "26", radius: "14",
    },
  },
  ember: {
    label: "Ember",
    values: { palette: "ember", glass: "on", radius: "12" },
  },
  orchid: {
    label: "Orchid",
    values: { palette: "plum", glass: "on", radius: "18" },
  },
  blueprint: {
    label: "Blueprint",
    values: {
      palette: "ocean", font: "mono", glass: "off",
      radius: "4", density: "compact",
    },
  },
  graphite: {
    label: "Graphite",
    values: { palette: "carbon", glass: "off", radius: "4" },
  },
  lagoon: {
    label: "Lagoon",
    values: { palette: "lagoon", glass: "on", radius: "14" },
  },
  //: Brief 95: two new looks, each on a palette of its own.
  midnight: {
    label: "Midnight",
    values: { palette: "midnight", glass: "on", radius: "12" },
  },
  rosewood: {
    label: "Rosewood",
    values: { palette: "rosewood", font: "serif", glass: "on", radius: "16" },
  },
};

// The two colours a theme card shows: the page it sits on and the accent it
// picks out. Read from the palette itself so a palette tweak can never leave
// the theme cards advertising a colour the app no longer uses.
function themeSwatch(preset) {
  const palette = PALETTES.find((p) => p.id === preset.values.palette) || PALETTES[0];
  const isDark = document.documentElement.dataset.mode === "dark";
  const set = isDark ? palette.dark : palette.light;
  return [set.page, set.accent];
}

//: A theme under the pointer in Settings (settings-controls.js previewTheme):
//: read before the manual layer, because a click would clear that layer.
const settingsLook = {
  themePreview: "",
  logFilterFromRun: false,
};
function activeThemePreset() {
  if (settingsLook.themePreview) return settingsLook.themePreview;
  //: No look chosen yet means the default look, not "no look": the default is
  //: a look like any other now (Quiet utilitarian), and theme-boot.js reads
  //: the same fallback so the first paint agrees.
  const name = prefs.get("themePreset", null) ?? DEFAULT_THEME_PRESET;
  return THEME_PRESETS[name] ? name : "";
}

// What the selected theme says about one setting, or undefined.
function themeValue(key) {
  const preset = THEME_PRESETS[activeThemePreset()];
  return preset ? preset.values[key] : undefined;
}

// The three layers, in order. `??` rather than `||` so a legitimate "0"
// (corner rounding) isn't treated as unset.
function appearancePref(key, fallback) {
  // `fallback` is the last resort, after the stored value, the active theme
  // and APPEARANCE_DEFAULTS. It exists because five call sites were already
  // passing one to a function that took a single parameter and dropped it on
  // the floor: so two settings resolved to `undefined` and wrote that word
  // into a CSS custom property. A defaulted parameter that is silently ignored
  // is worse than no parameter at all: it reads as a guarantee.
  //
  // The table is still the right place for a new setting's default. This just
  // means forgetting it degrades to the caller's intent rather than to
  // "undefined".
  return (
    (settingsLook.themePreview ? THEME_PRESETS[settingsLook.themePreview].values[key] : undefined) ??
    prefs.get(key, null) ?? themeValue(key) ?? APPEARANCE_DEFAULTS[key] ?? fallback
  );
}

// Applying a theme only records WHICH theme. Because every read goes through
// appearancePref, that is enough to change everything the theme covers while
// leaving your manual choices sitting on top of it, untouched.
function applyThemePreset(name, chosenByUser = false) {
  // Picking a theme has to *win*. `appearancePref` reads the manual layer
  // first, so a single earlier tweak, one accent, one corner radius, sat on
  // top of every theme picked afterwards and silently cancelled that part of
  // it. With several tweaks stored, a theme could change nothing visible at
  // all, which is what "the themes don't work half the time" was.
  //
  // Only the keys *this* theme has an opinion about are dropped: choosing
  // Lagoon should not also throw away a font size it says nothing about.
  if (chosenByUser && THEME_PRESETS[name]) {
    for (const key of Object.keys(THEME_PRESETS[name].values)) {
      prefs.remove(key);
    }
    // The accent and page background are painted from stored values rather
    // than read through `appearancePref`, so they need clearing by hand or a
    // custom accent outlives the palette it was picked against.
    if (THEME_PRESETS[name].values.palette) {
      prefs.remove("accent");
      prefs.remove("accent-custom");
      prefs.remove("page-bg");
      prefs.remove("page-bg-dark");
      applyCustomAccent(null);
      applyPageBackground(null);
    }
  }
  if (THEME_PRESETS[name]) prefs.set("themePreset", name);
  else prefs.remove("themePreset");
  applyAppearance();
  // `false` on both: re-applying what the theme says must not record it as a
  // manual choice, or merely picking a theme would pin its values as
  // overrides and the next theme couldn't change them.
  applyThemeChoice(appearancePref("theme"), false);
  applyPalette(appearancePref("palette"), false);
  renderBrandLogo();
  if (bgArtOn()) startBgArt();
}

function manualOverrides() {
  return OVERRIDABLE_KEYS.filter((key) => prefs.get(key, null) !== null);
}

// Drop the manual layer, keeping the chosen theme, the counterpart to
// "reset the theme" below.
function clearManualOverrides() {
  for (const key of manualOverrides()) prefs.remove(key);
  applyCustomAccent(null);
  applyPageBackground(null);
  applyThemePreset(activeThemePreset());
  renderAppearance();
  toast("Your manual changes are cleared, the theme is showing on its own.");
}

// Drop the theme, keeping every manual change, so "reset the theme to
// default because I want my own colours instead" does exactly that, rather
// than wiping the colours too (user request).
function resetThemeOnly() {
  prefs.remove("themePreset");
  applyThemePreset("");
  renderAppearance();
  toast("Theme reset to the app default. Your own changes are still applied.");
}

// --- building a scheme from one colour ---------------------------------------
//
// Picking an accent is easy. Picking a page background that *goes* with it is
// the part people give up on and end up with a default they didn't choose: so
// the relationship is arithmetic rather than judgement: rotate the hue by a
// known amount, drop the saturation hard, and push the lightness to whichever
// end the current mode needs.
//
// Only two things are written: the accent and the page background. It would be
// easy to generate a dozen variables and much harder to undo, and both of
// these already have a Clear button and a place in the override layer that the
// rest of the appearance settings understand.

function hexToHsl(hex) {
  const clean = String(hex || "").replace("#", "");
  if (clean.length !== 6) return null;
  const n = Number.parseInt(clean, 16);
  if (Number.isNaN(n)) return null;
  const r = ((n >> 16) & 255) / 255;
  const g = ((n >> 8) & 255) / 255;
  const b = (n & 255) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l * 100];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;
  return [h * 360, s * 100, l * 100];
}

function hslToHex(h, s, l) {
  const sat = Math.max(0, Math.min(100, s)) / 100;
  const light = Math.max(0, Math.min(100, l)) / 100;
  const hue = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2 * light - 1)) * sat;
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1));
  const m = light - c / 2;
  const [r, g, b] =
    hue < 60 ? [c, x, 0] :
    hue < 120 ? [x, c, 0] :
    hue < 180 ? [0, c, x] :
    hue < 240 ? [0, x, c] :
    hue < 300 ? [x, 0, c] : [c, 0, x];
  const to = (v) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return `#${to(r)}${to(g)}${to(b)}`;
}

// How far to rotate the background's hue away from the accent's. The names are
// the standard colour-wheel relationships; the numbers are what those names
// mean in degrees.
const HARMONY_ROTATIONS = {
  monochromatic: 0,
  analogous: -30,
  complementary: 180,
  triadic: 120,
};

function harmonyScheme(baseHex, kind, dark) {
  const hsl = hexToHsl(baseHex);
  if (!hsl) return null;
  const [h, s] = hsl;
  const rotation = HARMONY_ROTATIONS[kind] ?? 0;
  // A page background carrying the accent's full saturation is exhausting to
  // read against, so it keeps only a trace of it, enough to feel related, far
  // too little to compete with the text.
  const bgSaturation = Math.max(3, s * 0.14);
  const bgLightness = dark ? 12 : 96;
  return {
    accent: baseHex,
    page: hslToHex(h + rotation, bgSaturation, bgLightness),
  };
}

// `resolvedTheme` rather than the raw preference: under "System" there is no
// stored light/dark to read, and generating a light background for someone
// looking at a dark page is the one way this feature can be obviously wrong.

function applyHarmony() {
  const base = $("harmony-base").value;
  const kind = $("harmony-kind").value;
  const scheme = harmonyScheme(base, kind, resolvedTheme() === "dark");
  const note = $("harmony-note");
  if (!scheme) {
    note.textContent = "That colour didn't parse: try picking it again.";
    return;
  }
  prefs.set("accent-custom", scheme.accent);
  // A scheme's background is worked out *for a mode*, the same accent wants a
  // near-white page in light and a near-black one in dark. Storing only the one
  // for whichever mode happened to be on is what made the light/dark toggle
  // "stop working on the background": the stored value is written inline on
  // <html>, and an inline custom property outranks every `[data-mode="dark"]`
  // rule in the stylesheet, so the page stayed put while the rest of the UI
  // changed around it. Both are computed and stored; `currentPageBackground`
  // picks the right one whenever the mode changes.
  const dark = harmonyScheme(base, kind, true);
  const light = harmonyScheme(base, kind, false);
  prefs.set("page-bg", light ? light.page : scheme.page);
  prefs.set("page-bg-dark", dark ? dark.page : scheme.page);
  applyCustomAccent(scheme.accent);
  applyPageBackground(currentPageBackground());
  renderAppearance();
  note.textContent =
    `Accent ${scheme.accent}, background ${scheme.page}. ` +
    "Both have their own Clear buttons above if you'd rather start again.";
}

// --- your own saved themes ---------------------------------------------------
//
// A saved theme is a snapshot of the same localStorage keys every appearance
// control already writes, so it is not a second system that could drift from
// them: the same idea as the built-in presets, which are also just bundles of
// those values.
//
// Stored server-side with the rest of the preferences rather than in the
// browser. The look itself lives in localStorage because it has to be applied
// before first paint, but a *saved* look is something you would be upset to
// lose to a cleared cache, and in preferences it also rides along in the
// daily backup and is there in the desktop window as well as the browser tab.

const MAX_CUSTOM_THEMES = 20;

//: Everything a saved look captures: every manual override, plus the
//: background-art switch. `bgArt` is deliberately NOT in OVERRIDABLE_KEYS, 
//: that list also drives "clear my manual changes", and turning someone's
//: background off is not what clearing a colour override should do. But a
//: look that remembers *which* art and how intense, and not whether it is on,
//: can never turn it on when applied. Which is exactly what was reported
//: (§35J): the generative background had to be switched on by hand, separately
//: from the saved theme it belongs to.
//
// LOOK_KEYS itself lives in app.js, not here, see the comment there. It is
// read across the file boundary below, which is safe: currentLookValues()
// only ever runs from saveCurrentLook(), itself only ever run from a click,
// long after every script (app.js included) has loaded.

function currentLookValues() {
  const values = {};
  for (const key of LOOK_KEYS) {
    const value = prefs.get(key, null);
    if (value !== null) values[key] = value;
  }
  // The chosen preset is part of the look: without it, saving while "Manuscript"
  // is active and then applying the save would drop back to whatever preset
  // happened to be selected at the time.
  const preset = prefs.get("themePreset", null);
  return { values, preset: preset || "" };
}

function savedThemes() {
  const saved = prefsCache && prefsCache.custom_themes;
  return Array.isArray(saved) ? saved : [];
}

async function saveCurrentLook() {
  const input = $("custom-theme-name");
  const name = input.value.trim().slice(0, 30);
  if (!name) {
    toast("Give the look a name first.", "info");
    input.focus();
    return;
  }
  const existing = savedThemes();
  if (existing.length >= MAX_CUSTOM_THEMES && !existing.some((t) => t.name === name)) {
    toast(`You can keep ${MAX_CUSTOM_THEMES} saved looks: delete one first.`, "info");
    return;
  }
  const snapshot = { name, ...currentLookValues() };
  // Saving under an existing name replaces it, which is what "save" means when
  // you have just tweaked a look you already saved.
  const next = [...existing.filter((t) => t.name !== name), snapshot];
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ custom_themes: next }),
  });
  if (prefsCache) prefsCache.custom_themes = next;
  input.value = "";
  renderCustomThemes();
  toast(`Saved “${name}”.`);
}

function applySavedTheme(theme) {
  // Everything the snapshot named is restored; everything it didn't is left
  // alone rather than reset, so applying a saved look never silently changes a
  // setting the snapshot had nothing to say about.
  for (const [key, value] of Object.entries(theme.values || {})) {
    // A look saved before sizes became the device's own may still carry them.
    if (DEVICE_ONLY_KEYS.includes(key)) continue;
    prefs.set(key, value);
  }
  if (theme.preset) prefs.set("themePreset", theme.preset);
  else prefs.remove("themePreset");
  // The same function startup uses, so a restored look is applied by exactly
  // the path that would have applied it on a fresh load.
  applyThemeChoice(theme.values?.theme || "system", false);
  applyAppearance();
  // The art is a running p5 sketch, not a CSS variable, so applyAppearance
  // marking the root "on" is not enough to start or stop one.
  if (bgArtOn()) startBgArt();
  else stopBgArt();
  renderAppearance();
  toast(`Applied “${theme.name}”.`);
}

async function deleteSavedTheme(name) {
  const next = savedThemes().filter((t) => t.name !== name);
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ custom_themes: next }),
  });
  if (prefsCache) prefsCache.custom_themes = next;
  renderCustomThemes();
  toast(`Deleted “${name}”.`);
}

function renderCustomThemes() {
  const box = $("custom-themes");
  if (!box) return;
  const themes = savedThemes();
  box.replaceChildren();
  // The container is a grid of `minmax(104px, 1fr)` swatch columns, so a
  // paragraph dropped straight into it becomes a grid ITEM in a 104px track
  // and wraps to roughly one word per line. Screenshotted looking exactly like
  // that. The empty state turns the grid off for as long as it is the only
  // thing in there.
  box.classList.toggle("theme-presets-empty", !themes.length);
  if (!themes.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nothing saved yet: set the app up how you like it, then save it here.";
    box.appendChild(empty);
    return;
  }
  for (const theme of themes) {
    box.appendChild(savedThemeCard(theme));
  }
}

//: One saved look, shown as the look rather than as its name.
//:
//: It was a text pill and a ✕, which told you a look called "Sea of
//: Prosperity" existed but nothing about what it was, so picking between five
//: of them meant applying each in turn and undoing it. A saved *look* is a set
//: of colours; showing the colours is the whole job of this control.
//:
//: The values are already stored (`currentLookValues`), so the preview is the
//: real thing, not an illustration: the same accent, page and card colours the
//: look will apply. A theme saved before a given key existed simply falls back
//: to the current value for that swatch, which is also what applying it does.
function savedThemeCard(theme) {
  const values = theme.values || {};
  // Built from the keys a look actually stores (OVERRIDABLE_KEYS in app.js),
  // not from invented ones: the accent is either a custom hex or the name of a
  // preset whose swatch ACCENTS already holds, and light/dark is what decides
  // every neutral around it. Anything the saved look does not carry falls back
  // to the live theme, which is also what applying it would do.
  const named = (ACCENTS || []).find((a) => a.name === values.accent);
  const accent = values["accent-custom"] || named?.swatch || cssVarNow("--accent");
  const dark = (values.theme || document.documentElement.dataset.theme || "dark") !== "light";
  const page = dark ? "#12141c" : "#f5f6f9";
  const surface = dark ? "#1b1f2b" : "#ffffff";
  const ink = dark ? "#e7e9ee" : "#1f2430";

  const card = document.createElement("div");
  card.className = "saved-look";

  const preview = document.createElement("button");
  preview.type = "button";
  preview.className = "saved-look-preview";
  preview.title = `Apply “${theme.name}”`;
  preview.setAttribute("aria-label", `Apply the saved look “${theme.name}”`);
  preview.style.background = page;
  // A miniature of the thing itself: a card on the page colour, a line of ink
  // on it, and the accent as the one saturated element, which is how the real
  // interface is composed.
  const mini = document.createElement("span");
  mini.className = "saved-look-mini";
  mini.style.background = surface;
  const line = document.createElement("span");
  line.className = "saved-look-line";
  line.style.background = ink;
  const dot = document.createElement("span");
  dot.className = "saved-look-dot";
  dot.style.background = accent;
  mini.append(line, dot);
  preview.appendChild(mini);
  preview.addEventListener("click", () => applySavedTheme(theme));

  const foot = document.createElement("div");
  foot.className = "saved-look-foot";
  const name = document.createElement("span");
  name.className = "saved-look-name";
  name.textContent = theme.name;
  name.title = theme.name;
  const remove = smallButton("ph:trash", `Delete “${theme.name}”`, () => {
    deleteSavedTheme(theme.name).catch((e) => toast(e.message, true));
  });
  remove.classList.add("ghost", "icon-button", "quiet", "danger", "saved-look-delete");
  foot.append(name, remove);

  card.append(preview, foot);
  return card;
}

//: One resolved custom property, for building a preview out of the live theme
//: when a saved look predates a given key.
function cssVarNow(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "";
}

// "#rrggbb" -> "r, g, b" so a custom colour can drive rgba() softs.
function hexToRgbParts(hex) {
  const clean = String(hex || "").replace("#", "");
  if (clean.length !== 6) return null;
  const n = Number.parseInt(clean, 16);
  if (Number.isNaN(n)) return null;
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

// **A picked accent, made safe for the mode showing** (Brief 95, INBOX 858).
// The accent is a fill under `--on-accent` (white in light, near-black in
// dark), and one hex cannot be right in both: measured over the fifteen
// presets, the button text was under 4.5:1 on 14 of 30 preset and mode pairs
// (Mint 3.2:1 in light, Slate 2.5:1 in dark). `accentTone` keeps the hue and
// saturation and moves the lightness the least that clears 4.5:1 against the
// mode's ink, so a pick that already reads is returned as it is.
const ACCENT_MIN_RATIO = 4.5;

//: Relative luminance of an [r, g, b] triple; bg-art.js (lazy) uses it too.
function bgLuma(rgb) {
  const lin = (v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
}

function hexRatio(a, b) {
  const lum = (hex) => {
    const parts = hexToRgbParts(hex);
    return parts ? bgLuma(parts.split(", ").map(Number)) : 0;
  };
  const [lo, hi] = [lum(a), lum(b)].sort((x, y) => x - y);
  return (hi + 0.05) / (lo + 0.05);
}

function accentInk(dark) {
  return dark ? "#0d1017" : "#ffffff";
}

function accentTone(hex, dark) {
  const ink = accentInk(dark);
  if (hexRatio(hex, ink) >= ACCENT_MIN_RATIO) return hex;
  const hsl = hexToHsl(hex);
  if (!hsl) return hex;
  const [h, s, l] = hsl;
  // Binary search on lightness between the pick and the end that passes
  // (black's side in light, white's in dark): twelve halvings is under a
  // hundredth of a percent, once per pick, never per frame.
  let pass = dark ? 100 : 0, fail = l;
  for (let i = 0; i < 12; i++) {
    const mid = (pass + fail) / 2;
    if (hexRatio(hslToHex(h, s, mid), ink) >= ACCENT_MIN_RATIO) pass = mid;
    else fail = mid;
  }
  return hslToHex(h, s, pass);
}

// A user-chosen accent overrides the preset palette via inline custom
// properties; clearing it falls back to the data-accent presets. The soft,
// surface, hover and text tones all follow from the mode-safe tone: soft
// and the blob here, the surface (the tone itself, so what you pick is what
// a button wears), and hover and text from it in the stylesheet
// (`--accent-surface-hover`, `--accent-text`).
function applyCustomAccent(hex) {
  const root = document.documentElement;
  const dark = root.dataset.mode === "dark";
  const tone = hex && hexToRgbParts(hex) ? accentTone(hex, dark) : null;
  const parts = tone ? hexToRgbParts(tone) : null;
  if (!parts) {
    for (const name of ["--accent", "--accent-soft", "--accent-surface", "--blob-a"]) {
      root.style.removeProperty(name);
    }
    return;
  }
  root.style.setProperty("--accent", tone);
  root.style.setProperty("--accent-surface", tone);
  root.style.setProperty("--accent-soft", `rgba(${parts}, ${dark ? 0.18 : 0.14})`);
  root.style.setProperty("--blob-a", `rgba(${parts}, 0.30)`);
}

function applyPageBackground(hex) {
  const root = document.documentElement;
  if (hex) root.style.setProperty("--page", hex);
  else root.style.removeProperty("--page");
}

// The custom page background for the mode that is actually showing.
//
// `page-bg-dark` is only set by the scheme builder, which knows both. A
// background picked by hand from the colour input stays one colour in both
// modes, which is what picking one colour means.
function currentPageBackground() {
  const dark = prefs.get("page-bg-dark", null);
  if (dark && resolvedTheme() === "dark") return dark;
  return appearancePref("page-bg");
}

// User CSS lives in one stylesheet we own, so applying and clearing is clean.
//
// A constructed stylesheet rather than a <style> tag, because the app now
// sends `style-src 'self'`, and an injected <style> is exactly what that
// refuses: this feature was the one thing the strict policy broke. Adopted
// sheets are not inline content, so they are unaffected, and this is what the
// API was added for. Keeping the tag would have meant 'unsafe-inline' on every
// page, which would also have re-permitted style injected through note text.
let userCssSheet = null;

function applyCustomCss(css) {
  const supported =
    typeof CSSStyleSheet !== "undefined" &&
    "replaceSync" in CSSStyleSheet.prototype &&
    "adoptedStyleSheets" in Document.prototype;
  if (!supported) return applyCustomCssLegacy(css);

  if (!userCssSheet) {
    userCssSheet = new CSSStyleSheet();
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, userCssSheet];
  }
  try {
    // Invalid CSS throws here rather than being silently dropped, which is an
    // improvement: a <style> tag with a typo in it just did nothing.
    userCssSheet.replaceSync(css || "");
  } catch (err) {
    console.warn("Custom CSS was rejected:", err);
  }
}

// Only for a browser without constructable stylesheets (pre-2019 Chrome, or
// Safari before 16.4). Such a browser is old enough that it likely predates
// the CSP directive that makes this necessary in the first place.
function applyCustomCssLegacy(css) {
  let tag = document.getElementById("user-css");
  if (!tag) {
    tag = document.createElement("style");
    tag.id = "user-css";
    document.head.appendChild(tag);
  }
  tag.textContent = css || "";
}

// Applied once at startup (called from the pre-paint path) and on change.
// A machine that will feel every blurred layer: the two signals a browser
// gives without a permission prompt. `deviceMemory` is Chromium-only and
// capped at 8, so a missing value never counts as small on its own. Two
// cores, not four: a 4-thread laptop is common and runs the glass fine, and
// the owner wants the frosted art on by default, so only a machine that is
// small on memory or down to two threads is switched without being asked.
function smallMachine() {
  return (
    (navigator.deviceMemory && navigator.deviceMemory <= 4) ||
    (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2)
  ) === true;
}

function lessTransparencyWanted() {
  return window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
}

// What Performance mode resolves to right now. theme-boot.js repeats this
// reading for the first paint; keep the two in step.
function perfModeOn() {
  const pref = appearancePref("perf");
  if (pref === "on") return true;
  if (pref === "off") return false;
  return smallMachine() || lessTransparencyWanted();
}

// Why it is on, for the hint under the setting: the person's own choice
// needs no explanation; an automatic one does.
function perfModeReason() {
  if (appearancePref("perf") !== "auto" || !perfModeOn()) return "";
  if (lessTransparencyWanted()) return "On: your system asks for less transparency.";
  return "On for this machine: 2 cores or 4 GB of memory or fewer.";
}

//: **Height-aware density** (WORLD_CLASS_PLAN 22.1 item 2, the owner's
//: laptop: 1366x768 at 125%, 614px of window). With nothing chosen (Auto),
//: a window 700px tall or less is Compact and any other takes the look's own
//: density; a choice in Appearance always wins. theme-boot.js makes the same
//: call before first paint.
const DENSITY_SHORT = window.matchMedia("(max-height: 700px)");

function effectiveDensity() {
  const chosen = prefs.get("density", null);
  if (chosen) return chosen;
  return DENSITY_SHORT.matches ? "compact" : appearancePref("density");
}

//: A window that crosses 700px tall changes Auto's answer.
DENSITY_SHORT.addEventListener("change", () => {
  if (!prefs.get("density", null)) applyAppearance();
  settingsReadouts.auto?.();
});

//: **Where a label's icon sits: on its words' cap-height centre** (INBOX
//: 592, after 494 and 503). A flex row centres boxes, and a line of words'
//: box is centred on the font's ascent and descent, which is not where the
//: words are: in DejaVu Sans (the sandbox) that centre falls within 0.02em of
//: the capitals' middle, in Segoe UI (the owner's Windows) 0.064em above it,
//: because Segoe's ascent is tall. So a centred icon beside centred words
//: read right in every sweep here and high on Windows, and the per-family
//: drops written to correct it (0.05em in a chip, 0.1em in the status bar)
//: were calibrated against the wrong font. CSS has a unit for the cap height
//: and none for the ascent, so the gap is read once, here, from the font the
//: page is actually drawn in: a probe line with a zero-size box on its
//: baseline and one `1cap` tall. `--ph-cap-dy` is that gap in em of the
//: words, and `.ph-lead`/`.ph-trail` move by it (07-whiteboard-misc.css,
//: next to `.ph`). `translate` does nothing to an inline box, so an icon in
//: running text keeps its `vertical-align`, which is already on the
//: baseline and needs no font's metrics. Measured again when Settings
//: changes the font (`applyAppearance`, below). Here and not in app.js, whose
//: gzipped size is a ratchet; nothing calls it before this file loads.
//: Re-measured only when the font or the loaded faces change (INBOX 1415).
const labelOptics = { key: "" };
function measureLabelOptics() {
  const key = `${document.documentElement.dataset.font}${document.fonts?.size}${document.fonts?.status}`;
  if (key === labelOptics.key) return;
  labelOptics.key = key;
  const probe = document.createElement("div");
  probe.setAttribute("aria-hidden", "true");
  for (const [key, value] of [["position", "fixed"], ["top", "0"], ["left", "0"], ["visibility", "hidden"],
    ["fontSize", "100px"], ["lineHeight", "normal"], ["whiteSpace", "nowrap"], ["pointerEvents", "none"]]) probe.style[key] = value;
  const words = document.createTextNode("H");
  const mark = (height) => {
    const box = document.createElement("span");
    box.style.display = "inline-block";
    box.style.width = "0";
    box.style.height = height;
    box.style.verticalAlign = "baseline";
    return box;
  };
  const baseline = mark("0");
  const cap = mark("1cap");
  probe.append(words, baseline, cap);
  document.body.append(probe);
  const range = document.createRange();
  range.selectNodeContents(words);
  const line = range.getBoundingClientRect();
  const base = baseline.getBoundingClientRect().bottom;
  const capHeight = cap.getBoundingClientRect().height;
  probe.remove();
  // No `cap` unit (an old engine) or nothing laid out: leave the icons
  // box-centred, which is what they were before this.
  if (!(capHeight > 1) || !(line.height > 1)) return;
  const ascent = base - line.top;
  const descent = line.bottom - base;
  const dy = ((ascent - descent) / 2 - capHeight / 2) / 100;
  document.documentElement.style.setProperty("--ph-cap-dy", String(Math.round(dy * 1000) / 1000));
}

measureLabelOptics();
document.fonts?.ready?.then(measureLabelOptics);

//: Zoom alone, so a keypress writes one property (INBOX 1415).
function applyZoomVar() {
  document.documentElement.style.setProperty("--zoom", Number(appearancePref("zoom")) / 100);
}

function applyAppearance() {
  const root = document.documentElement;
  root.dataset.fontsize = appearancePref("fontsize");
  root.dataset.font = appearancePref("font");
  measureLabelOptics();
  root.dataset.density = effectiveDensity();
  //: The dashboard's own level follows the app's Compact (dashboard.js).
  applyDashDensity(dashDensity(), { persist: false });
  const perf = perfModeOn();
  root.dataset.perf = perf ? "on" : "off";
  // The preferences themselves are untouched: Performance mode overrides
  // what the page shows, not what the person chose.
  root.dataset.glass = perf ? "off" : appearancePref("glass");
  root.dataset.glassSheen = appearancePref("glass-sheen");
  root.dataset.glassControls = appearancePref("glass-controls");
  if (appearancePref("glass-controls") === "on") ensureModule("glassControls");
  root.dataset.pageWash = appearancePref("page-wash");
  root.style.setProperty("--glass-sheen-strength", Number(appearancePref("glass-sheen-strength")) / 100);
  root.dataset.themePreset = activeThemePreset();
  root.dataset.motion = perf ? "reduced" : appearancePref("motion");
  root.dataset.uiMotion = appearancePref("ui-motion");
  //: The blankets for these two switches are a sheet that matches only while one is on (motion-still.css).
  const stillSheet = document.getElementById("motion-still-sheet");
  if (stillSheet) stillSheet.media = root.dataset.motion === "reduced" || root.dataset.uiMotion === "off" ? "all" : "(prefers-reduced-motion: reduce)";
  //: The Capture box holds its line-number column from first paint when this is on.
  root.dataset.noteGutter = prefs.get("doc-gutter", null) === "1" ? "on" : "off";
  root.dataset.progressMotion = appearancePref("progress-motion");
  // The skeleton shimmer follows the OS reduced-motion setting unless "Always move" was chosen.
  root.toggleAttribute("data-progress-chosen", prefs.get("progress-motion", null) === "always");
  root.dataset.avatarMotion = appearancePref("avatar-motion");
  root.dataset.avatarFollow = appearancePref("avatar-follow");
  syncNameMarkBuddy();
  root.style.setProperty("--bg-art-opacity", Number(appearancePref("bg-intensity")) / 100);
  // Cards thin out slightly while the art is on, so it reads through the page
  // rather than only in the margins.
  root.dataset.bgArt = bgArtOn() ? "on" : "off";
  root.style.setProperty("--radius", `${appearancePref("radius")}px`);
  root.style.setProperty("--glass-blur", `${appearancePref("glass-blur")}px`);
  root.style.setProperty("--glass-opacity", Number(appearancePref("glass-opacity")) / 100);
  applyZoomVar();
  root.style.setProperty("--border-style", appearancePref("border-style", "solid"));
  // Belt and braces over the two fixes above. A custom property will happily
  // hold the string "NaN"; it is only invalid where it gets *used*, which here
  // is inside `--glass-shadow`'s rgba(), so a bad number silently removes
  // every shadow in the app rather than failing anywhere near this line.
  const shadow = Number(appearancePref("shadow-intensity", "5"));
  root.style.setProperty(
    "--shadow-intensity", String((Number.isFinite(shadow) ? shadow : 5) / 100)
  );
  applyResolvedMode();
  // remember=false: this runs on every startup, and recording the resolved
  // value would pin whatever the theme supplied as a manual override, after
  // which no other theme could ever change the palette again.
  applyPalette(activePalette(), false);
  // After the palette, never before: the accent has to be able to override
  // whatever colour the palette just supplied.
  applyEffectiveAccent();
  // A theme may set the page colour; your own pick overrides it.
  applyPageBackground(currentPageBackground());
  applyCustomCss(prefs.get("custom-css", null));
}

function effectiveTheme() {
  // "system" is a real choice, so an explicit one is only overridden by a
  // manual pick; a theme supplies it when you haven't made one.
  return prefs.get("theme", null) ?? themeValue("theme") ?? "system";
}

// What the app is *actually* showing right now: "system" is a choice, not a
// colour. The curated palettes need the resolved answer, because under
// "System" there is no data-theme attribute for CSS to match on, and writing
// each palette twice, once in a prefers-color-scheme block, is exactly how two
// copies of a palette drift apart.
function resolvedTheme() {
  const choice = effectiveTheme();
  if (choice === "light" || choice === "dark") return choice;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// The theme button shows the mode you will GET, not the one you are in.
//
// Reported as "the toggle light/dark button doesn't change". It was a fixed
// half-filled circle in both modes, so the one control whose entire job is to
// say which way it will flip looked identical either way, and there was no
// way to tell from it whether pressing it would darken or lighten.
//
// Showing the destination rather than the current state is the convention
// worth following here: a sun means "press for light", and it is the thing you
// are choosing, not a redundant restatement of the background you can already
// see.
function renderThemeToggle() {
  const button = $("theme-btn");
  if (!button) return;
  const dark = resolvedTheme() === "dark";
  setLabel(button, dark ? "ph:sun" : "ph:moon");
  const next = dark ? "light" : "dark";
  button.title = shortcutTitle(`Switch to ${next} mode`, "toggleTheme");
  button.setAttribute("aria-label", `Switch to ${next} mode`);
}

function applyResolvedMode() {
  document.documentElement.dataset.mode = resolvedTheme();
  renderThemeToggle();
  //: A picked accent is toned per mode (`accentTone`), so it is re-toned here.
  applyEffectiveAccent();
  // Light and dark can want different custom backgrounds, and the stored one
  // is written inline: so it has to be re-picked here rather than left to the
  // stylesheet, which cannot outrank it.
  applyPageBackground(currentPageBackground());
}

// Follow the OS while the choice is "System", without a reload.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (effectiveTheme() === "system") {
    //: Same one-frame repaint the toggle uses (INBOX 202): the OS changing
    //: mode under the app is the same event as the button, arriving by
    //: another route.
    repaintThemeAtOnce(applyResolvedMode);
    scheduleThemeArt();
  }
});

function applyThemeChoice(choice, remember = true) {
  if (remember) {
    if (choice === "system") prefs.remove("theme");
    else prefs.set("theme", choice);
  }
  //: The attribute that changes every colour in the app is set INSIDE the
  //: repaint (INBOX 202), not before it: set outside, the transitions it
  //: starts are already running by the time they are suppressed.
  repaintThemeAtOnce(() => {
    if (choice === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = choice;
    // A single hand-picked background is one colour in both modes, so it is
    // cleared when switching themes: it would override the new theme's native
    // background and the toggle would look broken. A scheme (`page-bg-dark`
    // set) is a pair made for both modes and stays: `applyResolvedMode`
    // picks the one for the mode now showing (audit 1028 S10).
    if (remember && !prefs.get("page-bg-dark", null)) {
      prefs.remove("page-bg");
      prefs.remove("page-bg-dark");
      applyPageBackground(null);
      if ($("page-bg-custom")) $("page-bg-custom").value = "#f5f7fb";
    }
    applyResolvedMode();
    renderBrandLogo();
  });
  // The dashboard constellation reads light-or-dark when it is built, so it
  // has to be rebuilt too, the background art already was, which is why only
  // this one appeared stuck on the old mode. Both are off the click now
  // (INBOX 202), coalesced into one frame after the colours have landed.
  scheduleThemeArt();
}

function _segActive(groupId, attr, value) {
  for (const b of document.querySelectorAll(`#${groupId} button`)) {
    b.classList.toggle("active", b.dataset[attr] === value);
  }
}

function renderThemePresets() {
  const holder = $("theme-presets");
  if (!holder) return;
  holder.replaceChildren();
  const active = activeThemePreset();
  for (const [name, preset] of Object.entries(THEME_PRESETS)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "theme-card";
    button.dataset.preset = name;
    button.title = `Apply the ${preset.label} theme`;
    button.setAttribute("aria-pressed", String(name === active));
    const swatch = document.createElement("span");
    swatch.className = "theme-swatch";
    // Two bands: the page it sits on and the accent it picks out.
    const [page, accent] = themeSwatch(preset);
    swatch.style.background = page;
    swatch.style.borderBottom = `6px solid ${accent}`;
    const caption = document.createElement("span");
    caption.className = "theme-card-name";
    caption.textContent = preset.label;
    button.append(swatch, caption);
    button.addEventListener("click", () => {
      // Clicking the active theme turns it off, so the control is a toggle
      // rather than a one-way door.
      // `true`: this is the user asking for the theme, so it clears the
      // manual tweaks that would otherwise cancel parts of it.
      applyThemePreset(name === active ? "" : name, true);
      renderAppearance();
    });
    holder.appendChild(button);
  }

  // Say plainly which manual settings are covering the theme, so a theme that
  // "isn't working" has a visible cause and a one-click fix beside it.
  const overrides = manualOverrides();
  const note = $("theme-override-note");
  if (!active && !overrides.length) {
    note.textContent = "No theme selected: the app's default look.";
  } else if (!overrides.length) {
    note.textContent = `${THEME_PRESETS[active].label} is showing exactly as designed.`;
  } else {
    note.textContent =
      `${nounCount(overrides.length, "setting")} you changed ` +
      `(${overrides.join(", ")}) ${overrides.length === 1 ? "is" : "are"} on top of ` +
      (active ? `the ${THEME_PRESETS[active].label} theme.` : "the default look.");
  }
  $("theme-clear-overrides").disabled = overrides.length === 0;
  $("theme-reset").disabled = !active;
}

//: The accent the theme wears with no accent chosen: read with the choice
//: (the data-accent rule, an inline custom colour) lifted for one
//: synchronous style read, so nothing paints in between.
//: Kept for as long as nothing on the root but the accent itself, and the
//: custom CSS, has changed: lifting the choice and putting it back is two
//: whole-page style recalculations, once per Appearance open (the lag log).
function themeDefaultAccent() {
  const root = document.documentElement;
  const key = [...root.attributes].filter((a) => a.name !== "data-accent").map((a) => `${a.name}=${a.value.replace(/--accent:[^;]*;?/g, "")}`).join("|") + prefs.get("custom-css", "");
  if (themeDefaultAccent.kept?.key === key) return themeDefaultAccent.kept.value;
  const chosen = root.dataset.accent;
  const inline = root.style.getPropertyValue("--accent");
  const priority = root.style.getPropertyPriority("--accent");
  delete root.dataset.accent;
  root.style.removeProperty("--accent");
  const value = getComputedStyle(root).getPropertyValue("--accent").trim();
  if (chosen !== undefined) root.dataset.accent = chosen;
  if (inline) root.style.setProperty("--accent", inline, priority);
  themeDefaultAccent.kept = { key, value };
  return value;
}

function renderAppearance() {
  renderThemePresets();
  const holder = $("accent-swatches");
  holder.replaceChildren();
  for (const accent of ACCENTS) {
    const button = document.createElement("button");
    button.className = "accent-swatch";
    //: Default is no accent at all, the palette's own: the swatch shows
    //: that, not a fixed hex (owner, 2026-10-12: "the selected one should
    //: match the default colour").
    button.style.background = accent.name === "indigo" ? themeDefaultAccent() || accent.swatch : accent.swatch;
    button.title = accent.label;
    button.setAttribute("aria-label", `${accent.label} accent`);
    // A custom colour wins, so no preset shows as active while it's set.
    const customSet = Boolean(prefs.get("accent-custom", null));
    button.classList.toggle("active", !customSet && accent.name === activeAccent());
    button.addEventListener("click", () => {
      prefs.remove("accent-custom"); // presets clear a custom colour
      applyAccent(accent.name); // re-derives the inline colour from scratch
      renderAppearance();
    });
    holder.appendChild(button);
  }
  renderCustomThemes();
  // Seed the harmony picker from whatever accent is showing, so "Apply" on an
  // untouched picker keeps the colour you already have rather than jumping to
  // an arbitrary default.
  //: Seeded a timer past the frame: the read settles the style of a page the
  //: press has just rewritten, and was the press's largest cost (the lag
  //: log: 295ms of a 376ms press, forced).
  afterFrames(() => setTimeout(() => {
    const showing = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
    if (/^#[0-9a-f]{6}$/i.test(showing)) $("harmony-base").value = showing;
  }), 1);
  $("contrast-toggle").checked = contrastOn();
  $("reduce-motion-toggle").checked = appearancePref("motion") === "reduced";
  $("ui-motion-toggle").checked = appearancePref("ui-motion") !== "off";
  $("bg-art-toggle").checked = bgArtOn();
  $("bg-intensity-row").classList.toggle("hidden", !bgArtOn());
  $("progress-motion").value = appearancePref("progress-motion");
  $("pref-show-thinking-words").checked = appearancePref("show-thinking-words") !== "off";
  $("avatar-motion").value = appearancePref("avatar-motion");
  $("avatar-follow").checked = appearancePref("avatar-follow") === "on";
  $("avatar-buddy").value = appearancePref("avatar-buddy");
  mountBuddyCustom();
  mountBuddyActivities();
  //: The menu's file reaches into the faces at load, so it waits for them.
  afterCharacters(mountBuddyPresets);
  try {
    $("avatar-buddy-motion").value = prefs.get("avatar-buddy-motion", null) || "follow";
  } catch (e) {
    $("avatar-buddy-motion").value = "follow";
  }
  nameMarkBuddyMotionApply();
  nameMarkBuddySizeSelect();
  $("atlas-style").value = appearancePref("atlas-style");
  $("assistant-avatar").value = appearancePref("assistant-avatar");
  $("atlas-look").value = appearancePref("atlas-look");
  $("face-look").value = appearancePref("face-look");
  $("dash-mark").value = appearancePref("dash-mark");
  renderProgressMotionHint();
  $("bg-motion").value = appearancePref("bg-motion");
  $("bg-motion-row").classList.toggle("hidden", !bgArtOn());
  renderBgMotionHint();
  $("perf-mode").value = appearancePref("perf");
  const perfWhy = perfModeReason();
  $("perf-mode-hint").textContent = perfWhy;
  $("perf-mode-hint").classList.toggle("hidden", !perfWhy);
  $("glass-toggle").checked = appearancePref("glass") === "on";
  $("glass-row").classList.toggle("disabled-row", perfModeOn());
  $("reduce-motion-row").classList.toggle("disabled-row", perfModeOn());
  $("glass-sheen-toggle").checked = appearancePref("glass-sheen") === "on";
  $("glass-controls-toggle").checked = appearancePref("glass-controls") === "on";
  $("glass-controls-row").classList.toggle("disabled-row", appearancePref("glass") !== "on" || perfModeOn());
  if ($("page-wash-toggle")) $("page-wash-toggle").checked = appearancePref("page-wash") === "on";
  $("glass-sheen-row").classList.toggle("disabled-row", appearancePref("glass") !== "on" || perfModeOn());
  $("glass-sheen-strength").value = appearancePref("glass-sheen-strength");
  $("glass-sheen-strength-value").textContent = `${appearancePref("glass-sheen-strength")}%`;
  $("glass-sheen-strength-row").classList.toggle(
    "disabled-row",
    appearancePref("glass") !== "on" || appearancePref("glass-sheen") !== "on"
  );
  $("bg-intensity").value = appearancePref("bg-intensity");
  $("bg-intensity-value").textContent = `${appearancePref("bg-intensity")}%`;
  renderBgStyleGrid();
  renderBgStyleHint();
  $("radius-slider").value = appearancePref("radius");
  $("radius-value").textContent = `${appearancePref("radius")}px`;
  $("glass-blur").value = appearancePref("glass-blur");
  $("glass-blur-value").textContent = `${appearancePref("glass-blur")}px`;
  $("glass-opacity").value = appearancePref("glass-opacity");
  $("glass-opacity-value").textContent = `${appearancePref("glass-opacity")}%`;
  $("zoom-slider").value = appearancePref("zoom");
  $("zoom-value").textContent = `${appearancePref("zoom")}%`;
  _segActive("border-style-seg", "borderChoice", appearancePref("border-style", "solid"));
  $("shadow-intensity").value = appearancePref("shadow-intensity", "5");
  $("shadow-intensity-value").textContent = `${appearancePref("shadow-intensity", "5")}%`;
  $("accent-custom").value = prefs.get("accent-custom", null) || "#4664f0";
  $("page-bg-custom").value = prefs.get("page-bg", null) || "#f5f7fb";
  $("custom-css").value = prefs.get("custom-css", null) || "";
  // Blur strength and opacity only matter while glass is on.
  $("glass-blur-row").classList.toggle("disabled-row", appearancePref("glass") !== "on");
  $("glass-opacity-row").classList.toggle("disabled-row", appearancePref("glass") !== "on");
  // Style/intensity only matter while the background art is on.
  const artOff = !bgArtOn();
  $("bg-intensity-row").classList.toggle("disabled-row", artOff);
  renderPaletteGrid();
  _segActive("theme-seg", "themeChoice", effectiveTheme());
  _segActive("fontsize-seg", "fontsize", appearancePref("fontsize"));
  //: Two lists, not wells (INBOX 670): a value no option carries (a font a
  //: saved look set that the list does not offer) leaves the list on its
  //: first row rather than on a blank.
  $("font-seg").value = appearancePref("font");
  $("density-seg").value = prefs.get("density", null) || "auto";
  settingsReadouts.auto?.();
}

// A frozen background with no explanation reads as a broken app, which is
// how it was reported. Say which setting is holding it still, and that
// "Moving" will override it.
//: The one case where this setting is *not* in charge, said where the choice
//: is made rather than left to be discovered. "Always move" overrides this
//: app's own Reduce motion; it deliberately does not override the operating
//: system's, which can be on for a medical reason. `typingDots` still steps
//: the dots through a colour there, so the indicator is never dead.
function renderProgressMotionHint() {
  const hint = $("progress-motion-hint");
  if (!hint) return;
  const osReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const choice = appearancePref("progress-motion");
  let text = "";
  if (choice === "always" && osReduced) {
    text = "Moving anyway: your system asks for reduced motion, and this setting overrides it. Choose Auto to follow the system instead.";
  } else if (choice === "still") {
    text = "Held still. The dots step through a colour once a second so you can still tell work is happening.";
  }
  hint.textContent = text;
  hint.classList.toggle("hidden", !text);
}

// The two seeded styles say what they grew from and what grew, so the
// name-to-ecosystem link is visible rather than a hidden rule (the species
// are the same ones bg-art.js draws: same strains, same genome).
function renderBgStyleHint() {
  const hint = $("bg-style-hint");
  if (!hint) return;
  if (typeof bgArtStrains !== "function") {
    ensureModule("bgArt").then((ok) => ok && renderBgStyleHint());
    return;
  }
  const style = bgArtStyle();
  let text = "";
  if ((style === "microbes" || style === "mycelium")) {
    const seed = bgArtSeedText();
    const names = bgArtStrains(seed, bgArtStrainCount(seed)).map(bgArtSpeciesName);
    const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0];
    text = `Grown from "${seed}": ${list}. A new display name grows a new one.`;
  }
  hint.textContent = text;
  hint.classList.toggle("hidden", !text);
}

function renderBgMotionHint() {
  const hint = $("bg-motion-hint");
  if (!hint) return;
  const choice = appearancePref("bg-motion");
  const osReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const appReduced = appearancePref("motion") === "reduced";
  let text = "";
  if (choice === "auto" && (osReduced || appReduced)) {
    text = osReduced
      ? "Held still because your system asks for reduced motion. Choose Moving to override it here."
      : "Held still because Reduce motion is on above. Choose Moving to override it just for the background.";
  }
  hint.textContent = text;
  hint.classList.toggle("hidden", !text);
}

// --- curated palettes -------------------------------------------------------------
// The palette is a look; Mode (light/dark/system) is a separate axis. Every
// palette defines both, so picking "Parchment" never also decides whether
// it's night. Swatch colours are duplicated here from the CSS on purpose: the
// preview has to show a palette that isn't currently applied, and a variable
// can only ever report the active one.
const PALETTES = [
  {
    id: "utilitarian",
    name: "Quiet",
    note: "The default. A warm grey ground, solid panels and one ink-blue accent.",
    light: { page: "#f4f3f1", card: "#ffffff", accent: "#2f5bd3", border: "rgba(28,28,26,0.12)" },
    dark: { page: "#161615", card: "#1e1e1c", accent: "#78a8ff", border: "rgba(236,235,232,0.12)" },
  },
  {
    id: "default",
    name: "Classic",
    note: "The original look: indigo glass over a soft gradient.",
    light: { page: "linear-gradient(135deg,#e9edfb,#f6f2ec 45%,#e6f1f2)", card: "rgba(255,255,255,0.75)", accent: "#4664f0", border: "rgba(31,36,48,0.12)" },
    dark: { page: "linear-gradient(135deg,#0e1017,#171a26 45%,#0f1720)", card: "rgba(29,33,46,0.85)", accent: "#8b9df8", border: "rgba(255,255,255,0.14)" },
  },
  {
    id: "paper",
    name: "Paper",
    note: "Off-white paper, black type and hairlines, one red-orange for actions.",
    light: { page: "#faf9f6", card: "#faf9f6", accent: "#c63d17", border: "rgba(17,17,17,0.18)" },
    dark: { page: "#141312", card: "#141312", accent: "#ff7a4d", border: "rgba(242,239,233,0.18)" },
  },
  {
    id: "mono",
    name: "Mono",
    note: "Cool graphite, monospace numbers and a green signal accent.",
    light: { page: "#eceff2", card: "#f8f9fa", accent: "#1a7f45", border: "rgba(21,25,30,0.15)" },
    dark: { page: "#0f1215", card: "#161a1f", accent: "#42d67f", border: "rgba(230,234,238,0.13)" },
  },
  {
    id: "parchment",
    name: "Parchment",
    note: "Paper, ink and a little gold. Made for long writing.",
    light: { page: "linear-gradient(135deg,#f6efe2,#f3e9d8 45%,#efe4d2)", card: "rgba(255,252,245,0.85)", accent: "#9a6b1f", border: "rgba(63,51,30,0.16)" },
    dark: { page: "linear-gradient(135deg,#1b1710,#221c13 45%,#1a1611)", card: "rgba(43,36,25,0.85)", accent: "#e0b458", border: "rgba(238,224,196,0.16)" },
  },
  {
    id: "sage",
    name: "Sage",
    note: "Quiet greens. The calmest of the set.",
    light: { page: "linear-gradient(135deg,#eaf1e9,#f2f5ee 45%,#e4eeea)", card: "rgba(253,255,252,0.85)", accent: "#2f7d54", border: "rgba(30,43,35,0.14)" },
    dark: { page: "linear-gradient(135deg,#0d1512,#121d17 45%,#0e1a16)", card: "rgba(25,38,31,0.85)", accent: "#5fd39a", border: "rgba(210,240,224,0.15)" },
  },
  {
    id: "ocean",
    name: "Ocean",
    note: "Cool teal and deep blue. Crisp rather than cosy.",
    light: { page: "linear-gradient(135deg,#e4f0f6,#eef6f8 45%,#dfeef2)", card: "rgba(252,254,255,0.85)", accent: "#0f7d99", border: "rgba(20,38,46,0.14)" },
    dark: { page: "linear-gradient(135deg,#08131a,#0d1e28 45%,#091a22)", card: "rgba(21,36,45,0.85)", accent: "#46c9e6", border: "rgba(200,238,250,0.15)" },
  },
  {
    id: "lagoon",
    name: "Lagoon",
    note: "Indigo ground with a teal accent, both colours, not blended.",
    light: { page: "linear-gradient(135deg,#eef1fa,#eaf4f6 45%,#e6edf8)", card: "rgba(253,254,255,0.85)", accent: "#0b6b7d", border: "rgba(26,34,62,0.15)" },
    dark: { page: "linear-gradient(135deg,#10142a,#141b38 45%,#0e1626)", card: "rgba(28,35,62,0.85)", accent: "#5fd8d0", border: "rgba(200,218,255,0.16)" },
  },
  {
    id: "ember",
    name: "Ember",
    note: "Warm oranges. Best in the evening.",
    light: { page: "linear-gradient(135deg,#fbeee4,#f9efe6 45%,#f6e6e0)", card: "rgba(255,252,249,0.85)", accent: "#bc5622", border: "rgba(46,30,22,0.15)" },
    dark: { page: "linear-gradient(135deg,#17100c,#1f1511 45%,#1a0f0e)", card: "rgba(41,29,23,0.85)", accent: "#f5924f", border: "rgba(246,220,204,0.16)" },
  },
  {
    id: "plum",
    name: "Plum",
    note: "Deep violet and magenta. The most saturated.",
    light: { page: "linear-gradient(135deg,#f1e9f7,#f6eef8 45%,#ece6f6)", card: "rgba(254,252,255,0.85)", accent: "#8332ad", border: "rgba(38,26,46,0.14)" },
    dark: { page: "linear-gradient(135deg,#130d1a,#1c1226 45%,#170f20)", card: "rgba(35,26,45,0.85)", accent: "#c07df5", border: "rgba(232,212,250,0.16)" },
  },
  {
    id: "midnight",
    name: "Midnight",
    note: "Deep navy and lamplight gold.",
    light: { page: "linear-gradient(135deg,#eef1f8,#f4f2ec 45%,#eceff6)", card: "rgba(255,255,255,0.85)", accent: "#9a6a00", border: "rgba(20,28,51,0.15)" },
    dark: { page: "linear-gradient(135deg,#0a0f1f,#0f1630 45%,#0b1226)", card: "rgba(22,30,56,0.85)", accent: "#f2c14e", border: "rgba(200,215,255,0.16)" },
  },
  {
    id: "rosewood",
    name: "Rosewood",
    note: "Dusty rose and wine. Warm without orange.",
    light: { page: "linear-gradient(135deg,#f8ecee,#faf1ef 45%,#f3e6ea)", card: "rgba(255,251,251,0.85)", accent: "#a3324f", border: "rgba(45,26,32,0.15)" },
    dark: { page: "linear-gradient(135deg,#170c10,#211218 45%,#1a0e14)", card: "rgba(44,26,33,0.85)", accent: "#f08aa6", border: "rgba(250,214,224,0.16)" },
  },
  {
    id: "carbon",
    name: "Carbon",
    note: "Near-monochrome. Colour only where it means something.",
    light: { page: "linear-gradient(135deg,#f2f3f5,#eceef1 45%,#e7e9ed)", card: "rgba(255,255,255,0.9)", accent: "#2b3441", border: "rgba(20,24,31,0.18)" },
    dark: { page: "linear-gradient(135deg,#0a0b0d,#101216 45%,#0c0e11)", card: "rgba(24,27,33,0.9)", accent: "#cdd5e0", border: "rgba(255,255,255,0.14)" },
  },
];

function activePalette() {
  // Through appearancePref, so a theme supplies the palette until you pick one
  // yourself: at which point yours wins and stays won.
  const saved = appearancePref("palette");
  return PALETTES.some((p) => p.id === saved) ? saved : "default";
}

function renderPaletteGrid() {
  const grid = $("palette-grid");
  if (!grid) return;
  const current = activePalette();
  const dark = resolvedTheme() === "dark";
  grid.replaceChildren();
  for (const palette of PALETTES) {
    const swatch = dark ? palette.dark : palette.light;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "theme-card";
    card.setAttribute("aria-pressed", String(palette.id === current));
    card.title = palette.note;

    const preview = document.createElement("span");
    preview.className = "theme-preview";
    // The preview must show *its own* palette, so these are inline.
    preview.style.background = swatch.page;
    preview.style.setProperty("--sw-card", swatch.card);
    preview.style.setProperty("--sw-accent", swatch.accent);
    preview.style.setProperty("--sw-border", swatch.border);

    const name = document.createElement("span");
    name.className = "theme-name";
    name.textContent = palette.name;
    const note = document.createElement("span");
    note.className = "theme-note";
    note.textContent = palette.note;

    card.append(preview, name, note);
    card.addEventListener("click", () => {
      // A palette brings its own accent, and an accent chosen earlier sits at
      // higher specificity: leaving it would make every palette come out the
      // same colour, which reads as the picker not working. The accent row
      // below is still there to deviate from the palette afterwards.
      const hadAccent =
        activeAccent() !== "indigo" || prefs.get("accent-custom", null);
      prefs.remove("accent-custom");
      applyCustomAccent(null);
      applyAccent("indigo");
      applyPalette(palette.id);
      renderAppearance();
      toast(
        hadAccent
          ? `Palette: ${palette.name}. Its own accent is back, pick another below if you'd rather.`
          : `Palette: ${palette.name}.`
      );
    });
    grid.appendChild(card);
  }
}

function resetAppearance() {
  for (const key of [
    "fontsize", "font", "density", "glass", "perf", "motion", "ui-motion", "reply-motion", "progress-motion", "avatar-motion", "avatar-follow", "avatar-buddy", "avatar-buddy-size", "avatar-buddy-actions", "atlas-style", "assistant-avatar", "atlas-look", "face-look", "dash-mark", "bg-intensity", "accent",
    "contrast", "bgArt", "theme", "radius", "glass-blur", "glass-opacity",
    "glass-sheen", "glass-sheen-strength", "glass-controls", "page-wash", "bg-style", "bg-motion", "palette", "themePreset",
    "accent-custom", "page-bg", "custom-css", "zoom",
  ]) {
    prefs.remove(key);
  }
  delete document.documentElement.dataset.accent;
  delete document.documentElement.dataset.contrast;
  delete document.documentElement.dataset.theme;
  applyCustomAccent(null);
  applyPageBackground(null);
  applyCustomCss("");
  stopBgArt();
  applyAppearance();
  renderBrandLogo();
  renderAppearance();
  toast("Appearance reset to defaults.");
}

// --- generative background ---------------------------------------------------------
//
// The styles and the runtime (mounting, pausing, the still capture) live in
// bg-art.js, which loads just before this file; this part decides whether
// the art runs, and moving or still, from the settings.

// A seeded style (microbes, mycelium) started before the preferences
// arrived, or before a rename, grew from the old name; regrow it from the
// one in Preferences now. A no-op for every other style and when nothing
// changed.
function bgArtRefreshSeed() {
  //: bg-art.js not fetched: nothing has been drawn from a seed.
  if (typeof bgArtSeedUsed === "undefined" || bgArtSeedUsed === null || !bgArtOn()) return;
  if (bgArtSeedUsed !== bgArtSeedText()) startBgArt();
}

function bgArtOn() {
  return prefs.get("bgArt", null) === "on";
}

function stopBgArt() {
  //: Nothing to halt until bg-art.js has been fetched.
  if (typeof bgArtHalt === "function") bgArtHalt();
}

// Which generative background to paint. Persisted like the other
// appearance prefs (user asked for more variety of art).
const BG_ART_STYLES = ["aurora", "constellation", "waves", "bubbles", "mesh", "microbes", "mycelium", "dusk", "ripples", "fireflies", "rain", "wander", "drift"];
//: The cards (Brief 95): a name and one line each, shown lightest first by
//: their measured cost (`BG_ART_COST`, bg-art.js).
const BG_ART_INFO = {
  aurora: ["Aurora", "Curtains of light"],
  constellation: ["Constellation", "Stars at three depths"],
  waves: ["Waves", "Rolling lines"],
  bubbles: ["Floating orbs", "Rising glass bubbles"],
  mesh: ["Mesh gradient", "Slow colour fields"],
  microbes: ["Microbes", "An ecosystem grown from your name"],
  mycelium: ["Mycelium", "A network grown from your name"],
  dusk: ["Dusk", "A sky and a slow glow"],
  ripples: ["Ripples", "Rings on still water"],
  fireflies: ["Fireflies", "Soft lights wandering"],
  rain: ["Rain", "Fine streaks falling"],
  wander: ["Wander", "Pen strokes that walk"],
  drift: ["Drift", "Slow colour noise"],
};

//: Built once, then only marked; the previews are drawn when the cards are
//: on screen and again only when what they show (mode, accent, intensity,
//: name) has changed.
function renderBgStyleGrid() {
  const grid = $("bg-art-style");
  if (!grid) return;
  if (typeof BG_ART_COST === "undefined") {
    ensureModule("bgArt").then((ok) => ok && renderBgStyleGrid());
    return;
  }
  if (!grid.childElementCount) {
    const order = [...BG_ART_STYLES].sort((a, b) => BG_ART_COST[a] - BG_ART_COST[b]);
    for (const name of order) {
      const [label, note] = BG_ART_INFO[name];
      const tier = bgArtTier(name);
      const card = document.createElement("button");
      card.type = "button";
      card.className = "theme-card bg-style-card";
      card.dataset.bgStyle = name;
      card.title = `${label}: ${note.toLowerCase()}. ${tier}, about ${BG_ART_COST[name].toFixed(1)}ms a frame.`;
      const preview = document.createElement("canvas");
      preview.className = "theme-preview bg-style-preview";
      preview.width = 160;
      preview.height = 90;
      const title = document.createElement("span");
      title.className = "theme-name";
      title.textContent = label;
      //: The cost is a facts row of its own, so a long name never pushes the
      //: label onto a second line on some cards and not others.
      const facts = document.createElement("span");
      facts.className = "row bg-style-facts";
      const ms = document.createElement("span");
      ms.className = "theme-note";
      ms.textContent = `${BG_ART_COST[name].toFixed(1)}ms a frame`;
      facts.append(chip(tier, `item-label${tier === "Light" ? " is-ok" : tier === "Heavy" ? " is-warn" : ""}`), ms);
      const line = document.createElement("span");
      line.className = "theme-note";
      line.textContent = note;
      card.append(preview, title, facts, line);
      card.addEventListener("click", () => {
        prefs.set("bg-style", name);
        if (!bgArtOn()) toggleBgArt(true);
        else startBgArt();
        renderAppearance();
      });
      grid.append(card);
    }
  }
  const current = bgArtStyle();
  for (const card of grid.children) {
    const on = card.dataset.bgStyle === current;
    card.classList.toggle("active", on && bgArtOn());
    card.setAttribute("aria-pressed", String(on && bgArtOn()));
  }
  if (!grid.closest("details")?.open) return;
  const o = {
    dark: document.documentElement.dataset.mode === "dark",
    accent: currentAccentHex(),
    density: Math.max(0.25, (Number(appearancePref("bg-intensity")) || 90) / 90),
    seedText: bgArtSeedText(),
  };
  const key = JSON.stringify(o);
  if (grid.dataset.drawn === key) return;
  grid.dataset.drawn = key;
  //: One preview a frame, so opening the section never holds a frame for
  //: all eleven at once.
  const cards = [...grid.children];
  const next = () => {
    const card = cards.shift();
    if (!card || grid.dataset.drawn !== key) return;
    try {
      bgArtPreview(card.dataset.bgStyle, o, card.querySelector("canvas"));
    } catch (err) {
      console.warn("Background preview failed:", err);
    }
    requestAnimationFrame(next);
  };
  requestAnimationFrame(next);
}
// One source of truth for the chosen style. This used to read a "bgArtStyle"
// key that nothing writes any more (the picker saves "bg-style"), so the
// builder always fell back to aurora no matter what was selected.
function bgArtStyle() {
  const saved = appearancePref("bg-style");
  return BG_ART_STYLES.includes(saved) ? saved : "aurora";
}

function startBgArt() {
  //: Off means off, whoever asks (INBOX 611, the owner: "I started the tour
  //: from the settings and it turned my generative bg art on except the
  //: setting is off"). Several callers restart the pictures after a change
  //: (the power saver, a theme, a resize) without asking whether the art is
  //: wanted, and this drew it over a notebook that had it switched off.
  if (!bgArtOn()) {
    stopBgArt();
    return;
  }
  // Wanting a calm background isn't the same as wanting a calm interface, so
  // the art has its own setting. "Moving" is an explicit request and wins over
  // the reduced-motion hint: the hint exists to protect people from motion
  // they didn't ask for, and this is someone asking for it, in a control that
  // does nothing else. Without that override there was no way to get the art
  // moving at all on a machine with reduced motion on, which is exactly what
  // was reported.
  const bgMotion = appearancePref("bg-motion");
  // **"Moving" wins over the reduced-motion hint, and does not win over
  // Performance mode.** The hint exists to protect people from motion they
  // did not ask for, and this setting is someone asking for it, in a control
  // that does nothing else; without that override there was no way to get the
  // art moving at all on a machine with reduced motion on, which was
  // reported. Performance mode is a different kind of statement: not a
  // preference about motion but a judgement about what this machine can
  // afford to draw, and DESIGN.md rule 12 says every animation stops there
  // except the progress indicators. Measured at 1440x900 in headless
  // Chromium, the art costs between +17ms and +28ms a frame
  // (`scratchpad/ui-sweeps/bgart.js`), which makes it the single most
  // expensive thing Performance mode could switch off, and it was the one
  // thing that kept running.
  //: **Battery-efficient mode stops it too, and "moving" does not override
  //: that** (INBOX 260), for the same reason Performance mode is not
  //: overridden two lines up: both are statements about what this machine
  //: should be spending, not preferences about motion, and this art is the
  //: most expensive thing on the page to draw (+17ms to +28ms a frame,
  //: `scratchpad/ui-sweeps/bgart.js`). A person asking for less battery use
  //: is asking for exactly that saving.
  const reduceMotion =
    bgMotion === "still" ||
    perfModeOn() ||
    batteryModeOn() ||
    (bgMotion !== "moving" && reducedMotionWanted());
  if (typeof bgArtRun !== "function") {
    ensureModule("bgArt").then((ok) => ok && startBgArt());
    return;
  }
  const bgStyle = bgArtStyle();
  //: No p5: the art draws on its own canvas (bg-art.js), so it mounts at
  //: once, including the one boot-time call to this function that used to
  //: arrive before p5 had loaded and wait for it.
  // Intensity drives how much is on screen, not just the CSS opacity.
  const intensity = Number(appearancePref("bg-intensity")) || 90;
  bgArtRun({
    style: bgStyle,
    dark: document.documentElement.dataset.mode === "dark",
    // Whatever colour the app is wearing, accent picker or curated palette.
    accent: currentAccentHex(),
    // The intensity slider scales how much is actually on screen, so each
    // style decides its own population from one number.
    density: Math.max(0.25, intensity / 90),
    // The seeded styles (microbes, mycelium) grow their species from it.
    seedText: bgArtSeedText(),
    still: reduceMotion,
    requested: bgMotion === "moving",
    restart: () => { if (bgArtOn()) startBgArt(); },
  });
}

function toggleBgArt(on) {
  prefs.set("bgArt", on ? "on" : "off");
  applyAppearance(); // updates data-bg-art so the cards adjust with it
  if (on) startBgArt();
  else stopBgArt();
}

$("theme-btn").addEventListener("click", toggleTheme);
$("theme-btn").addEventListener("contextmenu", (e) => { e.preventDefault(); openAppearancePanel(); });
//: The one switch for every box's suggestions (Brief 86, CHAT_PLAN decision
//: 69), kept on this device: absent reads as on.
$("pref-search-suggest")?.addEventListener("change", (event) => {
  prefs.set("searchSuggest", event.target.checked ? "on" : "off");
  toast(event.target.checked ? "Search boxes suggest as you type." : "Search boxes no longer suggest.");
});
$("bg-art-toggle").addEventListener("change", (e) => {
  toggleBgArt(e.target.checked);
  renderAppearance(); // enable/disable the style + intensity rows
});
$("contrast-toggle").addEventListener("change", (e) => applyContrast(e.target.checked));

// Wave O: expanded appearance controls.
for (const b of document.querySelectorAll("#theme-seg button")) {
  b.addEventListener("click", () => {
    applyThemeChoice(b.dataset.themeChoice);
    renderAppearance();
  });
}
for (const b of document.querySelectorAll("#fontsize-seg button")) {
  b.addEventListener("click", () => {
    prefs.set("fontsize", b.dataset.fontsize);
    applyAppearance();
    renderAppearance();
  });
}
$("font-seg").addEventListener("change", (e) => {
  prefs.set("font", e.target.value);
  applyAppearance();
  renderAppearance();
});
$("density-seg").addEventListener("change", (e) => {
  //: Auto is no choice at all: the window's height decides.
  if (e.target.value === "auto") prefs.remove("density");
  else prefs.set("density", e.target.value);
  applyAppearance();
  renderAppearance();
});
$("perf-mode").addEventListener("change", (e) => {
  prefs.set("perf", e.target.value);
  applyAppearance();
  renderAppearance();
});
// The OS setting can change while the app is open; "auto" follows it.
window.matchMedia("(prefers-reduced-transparency: reduce)").addEventListener("change", () => {
  applyAppearance();
  if (!$("settings-appearance").classList.contains("hidden")) renderAppearance();
});
$("glass-toggle").addEventListener("change", (e) => {
  const turningOn = e.target.checked && appearancePref("glass") !== "on";
  prefs.set("glass", e.target.checked ? "on" : "off");
  // Asked for directly: switching glassmorphism on from off also turns the
  // sheen on, so the full look shows up in one action, the sheen's own
  // checkbox can still turn it back off afterward without touching this.
  if (turningOn) prefs.set("glass-sheen", "on");
  applyAppearance();
  renderAppearance();
});
$("page-wash-toggle")?.addEventListener("change", (e) => {
  prefs.set("page-wash", e.target.checked ? "on" : "off");
  applyAppearance();
});
$("glass-sheen-toggle").addEventListener("change", (e) => {
  prefs.set("glass-sheen", e.target.checked ? "on" : "off");
  applyAppearance();
  $("glass-sheen-strength-row")?.classList.toggle("disabled-row", !e.target.checked);
});
$("glass-controls-toggle").addEventListener("change", (e) => {
  prefs.set("glass-controls", e.target.checked ? "on" : "off");
  applyAppearance();
});
$("glass-sheen-strength").addEventListener("input", (e) => {
  prefs.set("glass-sheen-strength", e.target.value);
  $("glass-sheen-strength-value").textContent = `${e.target.value}%`;
  applyAppearance();
});
$("reduce-motion-toggle").addEventListener("change", (e) => {
  prefs.set("motion", e.target.checked ? "reduced" : "auto");
  // The background-art picker has its own "Moving" override so someone can
  // ask for motion despite the OS-level reduced-motion hint (see
  // startBgArt()'s comment: that fix was reported missing once already).
  // But flipping the in-app reduce-motion toggle is a direct, explicit ask,
  // and "Moving" silently surviving it read as the two settings being
  // unrelated. Turning it on selects "Still"; turning it back off only
  // clears that if we're the ones who set it, so an independent "Moving"
  // choice made before or after isn't clobbered.
  if (e.target.checked) {
    prefs.set("bg-motion", "still");
  } else if (appearancePref("bg-motion") === "still") {
    prefs.set("bg-motion", "auto");
  }
  if ($("bg-motion")) $("bg-motion").value = appearancePref("bg-motion");
  renderBgMotionHint();
  applyAppearance();
  if (e.target.checked) stopBgArt(); // a still UI shouldn't keep the art running
  else if (bgArtOn()) startBgArt();
  renderBrandLogo(); // start/stop the emblem's rotation to match
});
$("ui-motion-toggle").addEventListener("change", (e) => {
  prefs.set("ui-motion", e.target.checked ? "on" : "off");
  applyAppearance();
});
$("bg-intensity").addEventListener("input", (e) => {
  prefs.set("bg-intensity", e.target.value);
  $("bg-intensity-value").textContent = `${e.target.value}%`;
  applyAppearance();
  if (bgArtOn()) startBgArt(); // intensity also drives particle density
});
// Corner rounding + glass blur: live sliders over CSS custom properties.
$("radius-slider").addEventListener("input", (e) => {
  prefs.set("radius", e.target.value);
  $("radius-value").textContent = `${e.target.value}px`;
  applyAppearance();
});
$("glass-blur").addEventListener("input", (e) => {
  prefs.set("glass-blur", e.target.value);
  $("glass-blur-value").textContent = `${e.target.value}px`;
  applyAppearance();
});
$("glass-opacity").addEventListener("input", (e) => {
  prefs.set("glass-opacity", e.target.value);
  $("glass-opacity-value").textContent = `${e.target.value}%`;
  applyAppearance();
});
// All four routes go through app.js's setZoom, so the slider, the buttons, the
// Ctrl+/- shortcut and the command palette cannot disagree about the range,
// the step, or where the value is stored.
$("zoom-slider").addEventListener("input", (e) => setZoom(Number(e.target.value)));
$("zoom-in")?.addEventListener("click", () => nudgeZoom(1));
$("zoom-out")?.addEventListener("click", () => nudgeZoom(-1));
$("zoom-reset")?.addEventListener("click", () => setZoom(100));
for (const btn of document.querySelectorAll("#border-style-seg button")) {
  btn.addEventListener("click", () => {
    prefs.set("border-style", btn.dataset.borderChoice);
    applyAppearance();
    renderAppearance();
  });
}
$("shadow-intensity").addEventListener("input", (e) => {
  prefs.set("shadow-intensity", e.target.value);
  $("shadow-intensity-value").textContent = `${e.target.value}%`;
  applyAppearance();
});
// Custom accent + page background.
// A pick whose button words would read under 4.5:1 in the mode showing is
// refused, not quietly altered: the row says the ratio and offers the
// nearest shade that reads, one press to take it (Brief 95).
function setCustomAccent(hex) {
  $("accent-offer").classList.add("hidden");
  prefs.set("accent-custom", hex);
  applyCustomAccent(hex);
  renderAppearance();
  if (bgArtOn()) startBgArt();
  renderBrandLogo();
}
$("accent-custom").addEventListener("input", (e) => {
  const pick = e.target.value;
  const dark = resolvedTheme() === "dark";
  const tone = accentTone(pick, dark);
  if (tone === pick) return setCustomAccent(pick);
  const ratio = hexRatio(pick, accentInk(dark)).toFixed(1);
  $("accent-offer-text").textContent =
    `Words on ${pick} read at ${ratio}:1 in ${dark ? "dark" : "light"} mode, under the 4.5:1 they need.`;
  $("accent-offer-dot").style.setProperty("--swatch", tone);
  $("accent-offer-label").textContent = `Use ${tone} (${hexRatio(tone, accentInk(dark)).toFixed(1)}:1)`;
  $("accent-offer-use").dataset.tone = tone;
  $("accent-offer").classList.remove("hidden");
});
$("accent-offer-use").addEventListener("click", (e) => {
  const tone = e.currentTarget.dataset.tone;
  if (!tone) return;
  $("accent-custom").value = tone;
  setCustomAccent(tone);
});
$("accent-custom-clear").addEventListener("click", () => {
  $("accent-offer").classList.add("hidden");
  prefs.remove("accent-custom");
  applyCustomAccent(null);
  renderAppearance();
  if (bgArtOn()) startBgArt();
  renderBrandLogo();
});
$("page-bg-custom").addEventListener("input", (e) => {
  prefs.set("page-bg", e.target.value);
  applyPageBackground(e.target.value);
});
$("page-bg-clear").addEventListener("click", () => {
  prefs.remove("page-bg");
  prefs.remove("page-bg-dark");
  applyPageBackground(null);
  renderAppearance();
});
// Background art style.
$("bg-art-style").closest("details")?.addEventListener("toggle", renderBgStyleGrid);
$("avatar-follow").addEventListener("change", (e) => {
  const value = e.target.checked ? "on" : "off";
  prefs.set("avatar-follow", value);
  document.documentElement.dataset.avatarFollow = value;
});
$("avatar-buddy").addEventListener("change", (e) => {
  prefs.set("avatar-buddy", e.target.value);
  mountBuddyCustom();
  syncNameMarkBuddy();
  nameMarkBuddySizeSelect();
});
$("avatar-buddy-size").addEventListener("change", (e) => nameMarkBuddySetSize(Number(e.target.value)));
$("avatar-buddy-motion").addEventListener("change", (e) => {
  try {
    prefs.set("avatar-buddy-motion", e.target.value);
  } catch (err) {
    // For this visit only.
  }
  nameMarkBuddyMotionApply();
});
$("avatar-buddy-actions").addEventListener("change", (e) => {
  try {
    prefs.set("avatar-buddy-actions", e.target.value);
  } catch (err) {
    // This visit only.
  }
});
try {
  $("avatar-buddy-actions").value = prefs.get("avatar-buddy-actions", null) || "fewer";
} catch (err) {
  $("avatar-buddy-actions").value = "fewer";
}
$("avatar-buddy-recall").addEventListener("click", () => nameMarkBuddyCallBack());
$("atlas-style").addEventListener("change", (e) => {
  prefs.set("atlas-style", e.target.value);
  atlasRepaint();
});
$("assistant-avatar").addEventListener("change", (e) => {
  prefs.set("assistant-avatar", e.target.value);
  repaintAssistantAvatars();
});
$("atlas-look").addEventListener("change", (e) => {
  prefs.set("atlas-look", e.target.value);
  atlasRepaint();
});
$("face-look").addEventListener("change", (e) => {
  prefs.set("face-look", e.target.value);
  nameMarkRepaintAll();
  //: An Atlas on Auto takes its look from here (`atlasLook`).
  atlasRepaint();
});
$("dash-mark").addEventListener("change", (e) => {
  prefs.set("dash-mark", e.target.value);
  paintDashEmblem();
});
$("avatar-motion").addEventListener("change", (e) => {
  prefs.set("avatar-motion", e.target.value);
  document.documentElement.dataset.avatarMotion = e.target.value;
});
$("progress-motion").addEventListener("change", (e) => {
  prefs.set("progress-motion", e.target.value);
  document.documentElement.dataset.progressMotion = e.target.value;
  document.documentElement.toggleAttribute("data-progress-chosen", e.target.value === "always");
  renderProgressMotionHint();
});
$("pref-show-thinking-words")?.addEventListener("change", (e) => {
  prefs.set("show-thinking-words", e.target.checked ? "on" : "off");
});
$("bg-motion").addEventListener("change", (e) => {
  prefs.set("bg-motion", e.target.value);
  // Still vs moving is decided in setup, so the sketch has to be rebuilt.
  if (bgArtOn()) startBgArt();
});
// Custom CSS (advanced).
$("custom-css-apply").addEventListener("click", () => {
  const css = $("custom-css").value;
  prefs.set("custom-css", css);
  applyCustomCss(css);
  $("custom-css-status").textContent = "Applied.";
});
$("custom-css-clear").addEventListener("click", () => {
  prefs.remove("custom-css");
  $("custom-css").value = "";
  applyCustomCss("");
  $("custom-css-status").textContent = "Cleared.";
});
$("appearance-reset").addEventListener("click", resetAppearance);
$("theme-reset").addEventListener("click", resetThemeOnly);

$("theme-clear-overrides").addEventListener("click", clearManualOverrides);

// Settings modal (Wave A).
$("settings-btn").addEventListener("click", () => openSettingsModal());
$("settings-close").addEventListener("click", closeSettingsModal);
$("settings-peek").addEventListener("click", () => setSettingsPeek(!settingsPeekIsOn()));

$("harmony-apply").addEventListener("click", applyHarmony);
$("custom-theme-save").addEventListener("click", () => {
  saveCurrentLook().catch((error) => toast(error.message, true));
});
$("custom-theme-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("custom-theme-save").click();
});

wireBackdropClose($("settings-modal"), () => closeSettingsModal()); // backdrop click
//: **A section chosen with the pointer hands the keys to the pane** (INBOX
//: 426 u: "keeps scroll jumping me between sections"). A click left the
//: focus on the nav button, and the nav's own arrow keys (above) walk the
//: sections, so the reading keys a person then pressed to scroll the page
//: they had just opened switched them to the next one, back to its top:
//: measured, three ArrowDowns from Appearance landed on Import & export
//: with the pane never moved, and PageDown and Space did nothing at all.
//: A press from the keyboard (`detail` 0) keeps the focus in the list,
//: where the arrows are what a keyboard user expects.
function focusSettingsPane() {
  document.querySelector("#settings-modal .modal-content")?.focus({ preventScroll: true });
}

//: **Focus lands on the section's heading after a switch** (INBOX 444). The
//: pane used to take the focus itself, which a screen reader announces as
//: nothing; the heading says where you are, and the reading keys still scroll
//: the pane because a focused heading's nearest scrolling ancestor is the pane.
function focusSettingsHeading(name) {
  const pane = $(`settings-${name}`);
  const head = pane?.querySelector(":scope > .settings-pane-title h3, :scope > .help-head h3, h3");
  if (!head) return focusSettingsPane();
  head.tabIndex = -1;
  head.focus({ preventScroll: true });
}

//: A group heading (INBOX 697) is in the loop too: a press on it opens its
//: group's first page rather than doing nothing.
for (const button of document.querySelectorAll("#settings-nav button, #settings-nav .nav-group-label")) {
  button.addEventListener("click", (event) => {
    const name = (button.dataset.section ? button : button.nextElementSibling.querySelector("[data-section]:not(.hidden)")).dataset.section;
    showSettingsSection(name);
    //: **A pointer click keeps the focus in the list** (INBOX 467, the owner:
    //: "I cant navigate on the settings navigation side bar with arrows"),
    //: so Up and Down walk on from the section clicked, as in every settings
    //: window's sidebar; a click in the pane gives the reading keys to the
    //: pane. Enter or Space (`detail` 0) still hands the focus to the
    //: section's heading, where a keyboard user reads on.
    if (!settingsNavWalking && event.detail === 0) focusSettingsHeading(name);
    else if (!settingsNavWalking) button.focus({ preventScroll: true });
  });
}
$("settings-search")?.addEventListener("input", (e) => filterSettings(e.target.value));
$("settings-search")?.addEventListener("keydown", (e) => {
  // Escape clears the filter rather than closing the whole panel, closing on
  // Escape while someone is mid-search loses both the search and their place.
  if (e.key === "Escape" && e.target.value) {
    e.stopPropagation();
    e.target.value = "";
    filterSettings("");
    return;
  }
  //: Down walks into the results; Enter opens the first one.
  if (e.key === "ArrowDown" && typeof settingResultsKey === "function" && settingResultsKey(e)) {
    e.preventDefault();
  } else if (e.key === "Enter") {
    document.querySelector("#settings-results .settings-result")?.click();
  }
});
$("settings-results")?.addEventListener("keydown", (e) => {
  if (typeof settingResultsKey === "function" && settingResultsKey(e)) e.preventDefault();
});
// Cross-links between settings screens ("web search lives over there").
// Delegated, so a link added to the markup later needs no wiring.
$("settings-modal").addEventListener("click", (event) => {
  const link = event.target.closest("[data-goto-section]");
  if (!link) return;
  //: `data-goto-target` lands on one row of that section, scrolled to and
  //: flashed the way the catalogue's deep links are, rather than on its top.
  if (link.dataset.gotoTarget) openSettingsModal(link.dataset.gotoSection, link.dataset.gotoTarget);
  else showSettingsSection(link.dataset.gotoSection);
});
// Same idea, one step further: a Help topic about a *tab* (Reminders,
// Graph, Library…) should be able to send you there directly, not just to
// whatever Settings section happens to mention it, asked for directly,
// after the Settings-only links above shipped without this half. Closes
// the modal first: a tab switch happening behind it would be invisible.
//: On `document`, not the Settings modal: the Atlas chat now opens in a
//: sheet outside the modal (INBOX 224), and its answer badges ("Chat",
//: "Skills") were `[data-goto-tab]` buttons nothing listened to there
//: ("clicking the hyperlinked badges under atlas responses doesnt work").
//: The sheet closes first for the same reason the modal does: a tab switch
//: behind an overlay is invisible.
//: `[data-goto-section]` too, not only `[data-goto-tab]` (INBOX 234: "the web
//: search and skills hyperlinked badges in the atlas interface dont work",
//: while Chat did). A help answer's badge names either a tab, a Settings
//: section, or both, and the section-only ones were landing on nothing at all
//: outside the Settings modal. The modal's own links keep their own handler
//: above: matching them here as well would close and re-open the modal under
//: the pointer.
document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-goto-tab], [data-goto-section]");
  if (!link) return;
  if (!link.dataset.gotoTab && link.closest("#settings-modal")) return;
  //: Whatever the link was clicked inside closes, not only Settings and the
  //: Atlas sheet: the popup agent, the sketch pad (INBOX 250, the owner: "the
  //: modal or other popup I clicked the link in should close"). The chord's
  //: closer already knows every overlay that can hold the keyboard.
  closeOverlaysForChord();
  if (link.dataset.gotoSection) {
    //: The row too (INBOX 430: the Guide's "a link that opens it" lands on
    //: the setting it named, not the top of its section).
    openSettingsModal(link.dataset.gotoSection, link.dataset.gotoTarget || null);
    return;
  }
  switchTab(link.dataset.gotoTab);
});

// Filters only re-draw what is already held, they never refetch, so changing
// one mid-incident cannot lose the records you were looking at.
$("log-source").addEventListener("change", renderActiveLogView);
$("log-level").addEventListener("change", renderActiveLogView);
$("log-requests").addEventListener("change", renderActiveLogView);
//: **A finished task's log** (Background tasks' history, its Logs button):
//: Logs, with the filter set to the most particular words the row has, the
//: package or model in its brackets ("fastembed"), else the
//: model it names, else its label. A log line names what it worked on, not
//: the sentence the row says, so the brackets are tried first.
function taskLogButton(item) {
  return rowActions([{ label: "ph:scroll Logs", title: "Open the log, filtered to this run", run: () => openTaskLog(item) }], "Logs");
}


let logFilterDebounceTimeout;
$("log-filter").addEventListener("input", (event) => {
  if (event.isTrusted) settingsLook.logFilterFromRun = false;
  clearTimeout(logFilterDebounceTimeout);
  logFilterDebounceTimeout = setTimeout(renderActiveLogView, 150);
});
$("logs-copy").addEventListener("click", copyLogs);
$("logs-clear").addEventListener("click", clearLogs);
$("logs-bundle").addEventListener("click", downloadSupportBundle);
$("logs-email-bundle").addEventListener("click", () => emailSupportReport(""));

$("log-follow").addEventListener("change", (event) => {
  logFollowPinned = event.target.checked;
  if (event.target.checked) scrollLogToBottom();
});

// Scrolling up is how you say "stop moving, I am reading this", so it pauses
// the follow rather than fighting you for the scroll position. Scrolling back
// to the bottom resumes it, which is the same gesture every terminal uses.
// Both containers get the listener, only one is ever visible at a time, but
// whichever it is has to pause Follow the same way.
for (const id of ["log-list", "log-terminal"]) {
  $(id).addEventListener("scroll", () => {
    if (!$("log-follow").checked) return;
    logFollowPinned = nearLogBottom();
    $("log-follow-label").classList.toggle("is-paused", !logFollowPinned);
  });
}

for (const button of document.querySelectorAll("#log-view-toggle button")) {
  button.addEventListener("click", () => {
    logView = button.dataset.view;
    prefs.set("logView", logView);
    for (const b of document.querySelectorAll("#log-view-toggle button")) {
      b.classList.toggle("active", b === button);
    }
    $("log-list").classList.toggle("hidden", logView !== "list");
    $("log-terminal").classList.toggle("hidden", logView !== "terminal");
    $("log-terminal-hint").classList.toggle("hidden", logView !== "terminal");
    renderActiveLogView();
    scrollLogToBottom();
  });
  // The markup hardcodes "List" as the active button; a returning visitor
  // whose last choice (localStorage) was "terminal" needs that reflected
  // here too, not just in which container renders.
  button.classList.toggle("active", button.dataset.view === logView);
}
$("log-list").classList.toggle("hidden", logView !== "list");
$("log-terminal").classList.toggle("hidden", logView !== "terminal");
$("log-terminal-hint").classList.toggle("hidden", logView !== "terminal");

// --- initial paint (relocated from app.js's own top-level wiring) ----------
//
// Both hazards this file's own header describes, fixed the same way: the
// call site moved here, after every function above it exists, instead of
// splitting definition from call site. Order preserved from app.js's
// original wiring (applyAppearance()/startBgArt() ran before renderBrandLogo()
// there too).
applyAppearance();

// Said once, on the machine it applies to: the app has just switched the
// glass and the animations off without being asked, and a person who set up
// their look on a bigger machine deserves to know where that went. Never
// repeated, and never shown when the mode was chosen by hand.
function noticePerfMode() {
  if (appearancePref("perf") !== "auto" || !perfModeOn()) return;
  if (prefs.get("perf-noticed", null) === "yes") return;
  if (typeof toastAction !== "function") return;
  prefs.set("perf-noticed", "yes");
  toastAction(
    "Performance mode is on for this machine: flat panels, no animations.",
    "Change",
    () => openSettingsModal("appearance", "perf-mode"),
    { go: { settings: "appearance", focus: "perf-mode" } }
  );
}
window.setTimeout(noticePerfMode, 8000);
if (bgArtOn()) startBgArt();
// The generative brand emblem, unique each visit (Wave O). p5 is loaded long
// before any of these split files (a vendor `<script>` tag, ahead of
// app.js's own): draw once everything this file owns is defined too.
renderBrandLogo();

// --- advanced response settings (sampling) -------------------------------------
//
// Asked for directly: expose top-k, top-p, repeat penalty and the rest,
// "because different models require different parameters to get the same
// result", and detect them per model if that is possible.
//
// It is, and the detection is not a guess: a GGUF ships its author's
// recommended parameters, Ollama reports them in /api/show, and the server
// reads them (see ai/sampling.py). Every row therefore starts at what the
// model itself asks for, and says so, "0.6 because this model recommends it"
// and "0.6 because you set it" are different facts and only the second has
// anything to revert to.
//
// The knob table comes from the server rather than being repeated here, for
// the same reason the file-type table does: a slider whose range disagrees
// with what the backend accepts is a bug nobody can see until a request is
// rejected.
let samplingState = null;
let samplingSaveTimer;

async function loadSamplingSettings() {
  const box = $("sampling-box");
  if (!box) return;
  samplingState = await apiJson("/models/sampling", { silent: true }).catch(() => null);
  renderSamplingRows();
}


$("sampling-reset")?.addEventListener("click", async () => {
  try {
    await apiJson("/models/sampling", {
      method: "PUT",
      body: JSON.stringify({ overrides: {} }),
    });
    toast("Back to what each model recommends.");
  } catch {
    toast("Couldn't reset those settings.", true);
  }
  await loadSamplingSettings();
});


// --- settings rows: one shape, and the prose out of the way ------------------
//
// Reported: "there is often a spacing issue between elements and excessive
// paragraph texts in places", with a screenshot of Settings, and later
// "fix and reimagine the ui design for the settings pages".
//
// Measured before this: **six paragraphs over 160 characters, the longest
// 385**, and setting rows at 22px, 37px and 91px, a four-fold height spread
// decided entirely by whether a row happened to carry an explanation. A list
// whose items are three different sizes is not a list you can scan, and the
// scan is the whole job of a settings page: find the one switch you came for.
//
// The prose itself is good and worth keeping, it explains *consequences*,
// which is exactly what a settings hint should do and what most apps omit.
// So it is not cut; it is collapsed. Every row is the same height at rest,
// with a hint one click away on the rows that have one.
//
// Long ones only. A six-word hint costs nothing to read and hiding it behind
// a control would be more chrome than text, the threshold is where a hint
// stops being a label's tail and starts being a paragraph.
const SETTINGS_HINT_INLINE_CHARS = 90;
//: Ids for switches that had none, so their label can name them (below).
let settingSwitchSeq = 0;

function collapseLongSettingHints(root) {
  const scope = root || document.getElementById("settings-modal");
  if (!scope) return;
  // Any depth, not `label > small`: most hints sit inside a `<span>` that
  // wraps the label's text, so a direct-child selector matched none of the
  // twenty-three that exist. Checked live rather than assumed, the first
  // version of this ran, found nothing, and changed no measurement.
  //: `.setting-label` rows (a label word beside a select) carry the same
  //: hints; their long ones collapse the same way (Brief 4).
  for (const hint of scope.querySelectorAll("label small.muted, .setting-label small.muted")) {
    if (hint.dataset.collapsible) continue;
    const text = (hint.textContent || "").trim();
    if (text.length <= SETTINGS_HINT_INLINE_CHARS) continue;
    hint.dataset.collapsible = "1";
    hint.classList.add("setting-hint", "is-collapsed");

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "ghost small icon-only setting-hint-toggle";
    setLabel(toggle, "ph:question");
    // The label text, so the control says which setting it explains rather
    // than being one of a column of identical "?"s to a screen reader.
    const label = (hint.parentElement.textContent || "")
      .replace(text, "")
      .trim()
      .slice(0, 60);
    toggle.title = `What does “${label}” do?`;
    toggle.setAttribute("aria-label", toggle.title);
    toggle.setAttribute("aria-expanded", "false");
    // The same popover every other "?" in this app opens (app.js), rather
    // than this control's own inline expand, reported directly: "the search
    // relevance '?' popup tooltip is completely different from all other
    // tooltips like it, same with the 'keep the ai on this machine' tooltip".
    // `wireHelpPopover` handles the click (including the preventDefault a
    // hint living inside a <label> needs, or opening it would toggle the very
    // setting it explains), the placement, and all three ways it closes.
    wireHelpPopover(toggle, hint);
    // **On the label's own line, not under it.** Reported with a
    // screenshot ("the 'keep the ai on this machine' line in settings needs
    // visual fixing and alignment"): this used to be
    // `hint.insertAdjacentElement("afterend", toggle)`, which made the
    // button a sibling of the label text inside `.setting-check > span`, 
    // and that span is a flex *column*, so every element child becomes its
    // own row. The "?" sat on a line of its own beneath the setting it
    // explains, which reads as a broken row rather than a control.
    //
    // Wrapping the label's leading nodes and the button together in one
    // flex row fixes it structurally instead of fighting the column with
    // margins: text and "?" share a line, the hint still opens underneath.
    // The disclosure order stays correct for a screen reader too, the
    // button now precedes the region its `aria-expanded` describes.
    const parent = hint.parentElement;
    // **A `.setting-check` row puts the "?" in the right-hand control
    // cluster, next to the switch, not mid-sentence.** Reported: "the 'keep
    // the AI on this machine' toggle and '?' icon need to be swapped and
    // properly aligned." Measured before the change: the label text ran to
    // x=724, the "?" sat at 732 as a 32px circle, and the switch was at
    // 1089: 325 pixels of empty row between two controls that belong to
    // each other, with the heavier of the two interrupting the sentence.
    //
    // `.setting-check` is a grid (04-chat-dock-appearance.css), and its
    // whole point is that the switches down a group form one straight
    // right edge. So the button becomes a grid item of its own in the
    // column beside the switch, rather than a child of the label span.
    // Every other label shape in Settings is flex or block flow with no
    // such column, and there the button still needs the wrapping row
    // below: a bare child of `.setting-check > span` (a flex *column*)
    // lands on a line of its own under the label, which is what the
    // previous report about this same row was.
    const settingCheck = parent.closest(".setting-check");
    if (settingCheck) {
      const box = settingCheck.querySelector("input[type=checkbox]");
      settingCheck.insertBefore(toggle, box);
      //: **The row's words must still toggle the row's switch.** A label
      //: activates its first labelable descendant, and the "?" is a button,
      //: placed above, before the checkbox: pressing "Keep Atlas on this
      //: machine" opened its help and left the setting as it was (found by the
      //: deepflows sweep). Naming the checkbox with `for` is what a label
      //: uses when it has one, wherever the button sits.
      if (box && settingCheck.tagName === "LABEL") {
        if (!box.id) box.id = `setting-switch-${++settingSwitchSeq}`;
        settingCheck.htmlFor = box.id;
      }
      continue;
    }
    const row = document.createElement("span");
    row.className = "setting-hint-row";
    while (parent.firstChild && parent.firstChild !== hint) {
      row.appendChild(parent.firstChild);
    }
    row.appendChild(toggle);
    parent.insertBefore(row, hint);
  }
}
window.collapseLongSettingHints = collapseLongSettingHints;

// --- the Guide's names (the chat itself is help-chat.js, a lazy bundle) ----
//: The guide's name, read from here everywhere the interface says it
//: (CHAT_PLAN.md decision 15). `help_chat.GUIDE_NAME` is the same word on the
//: server, where the model is told it.
//: One name for the notebook's AI, spelt once (INBOX 225) in app.js, which
//: index.html loads first; the backend's `AI_NAME` in ai/__init__.py is the
//: same word. The guide is the same Atlas wearing its "about the app" hat.
const GUIDE_NAME = AI_NAME;

//: **What the panel calls itself.** The owner, 2026-09-20: "the atlas help
//: panel needs a better title to make it evident that it is the guide". The
//: head said "Atlas" and nothing else, which names the speaker and not the
//: surface: a person who has not read the help does not know whether this is
//: the chat that reads their notes or the one that does not. "Atlas guide"
//: says which of the app's two assistants this is in the two words the head
//: has room for, and it is still derived from the one name, so a rename
//: still costs one edit. The sheet's accessible label is this same string
//: rather than the bare name: a visible title and an accessible name that
//: disagree is a screen reader describing a different panel.
const GUIDE_TITLE = `${GUIDE_NAME} guide`;

//: The line under it, and the reason it changed with the title: "About the
//: app, never your notes" says what the guide will not do before it says what
//: it does. DESIGN.md's rule is one line of description per section, so that
//: one line is the whole budget, and it was spending it on a disclaimer that
//: the '?' popover, the empty state and the composer's own hint all carry
//: too. What it says instead is where the answers come from, which is the
//: fact that makes the panel worth opening.
//:
//: **One line, and it has to fit on one** (INBOX 270 part 4). The previous
//: wording was 41 characters in a 251px column at `--text-sm` and wrapped at
//: 1440 and 1024 both, leaving "text" alone on a second line and the head
//: 63px tall against the agent activity panel's 37. Thirty characters says
//: the same thing and fits with room to spare; the CSS still ellipsises it,
//: so a longer translation cannot put the second line back.
const GUIDE_LINE = "Answers from the app's own help";
//: The persona hint's "(Atlas)" follows the name too.
{
  const hint = document.getElementById("persona-placeholder-hint");
  if (hint) hint.textContent = `Write {ai_name} where the name should go and it is replaced with ${AI_NAME}. Optional.`;
}

//: The header's '?' became the status bar's Guide slot with INBOX 207;
//: app.js binds that one, because the status bar is its markup and it can
//: reach this function through `window` by the time a click happens.
$("settings-guide-btn")?.addEventListener("click", () => openHelpChat());
//: The avatar in the Settings head is the way to the profile from every pane.
$("settings-profile-btn")?.addEventListener("click", () => showSettingsSection("preferences"));
$("atlas-open")?.addEventListener("click", () => openHelpChat());


// =============================================================================
// What it learned (WORLD_CLASS_PLAN I9)
// =============================================================================
//
// **The backend has been complete since 2026-09-13 and nothing called it.**
// Found by scanning all 319 routes against every path the frontend fetches:
// `GET /learned`, `GET|PUT /learned/switches`, `PATCH|DELETE /learned/{id}`,
// `POST /learned/{id}/reset`, `GET /learned/export` and `DELETE /learned` had
// no caller anywhere. The plan's own words for why that matters: "a model
// that is wrong quietly is worse than no model", and every one of those
// routes exists so a person can see the model being wrong and say so. With
// no screen, `derived_facts` grew where nobody could read it.
//
// Built against what the backend ships rather than against the whole spec.
// The bulk actions waited for `POST /learned/bulk` (2026-09-23) rather than
// being a client-side loop over N rows, which is N requests that can half
// fail: the route changes every selected row in one transaction.

//: One page. 50 rather than the route's 100 default: this is a settings
//: panel inside a modal, and a hundred rows is a scroll nobody finishes.
const LEARNED_PAGE = 50;

//: What each switch is, in the words a person would use. The keys are
//: `ai/facts.py`'s `SWITCHES`, and a key that appears there and not here
//: still renders, under its own name, rather than vanishing: a switch the
//: person cannot see is a switch they cannot turn off, which is the one
//: thing this section exists to prevent.
const LEARNED_SWITCH_COPY = {
  night_shift: ["Night shift", "Reads notes you have added or changed and works out what they claim."],
  margin_reader: ["Margin reader", "Adds notes in the margin of a note as you read it."],
  open_questions: ["Open questions", "Collects the questions your notes leave unanswered."],
  resurfacing: ["Resurfacing", "Brings notes you have not looked at in a while back to the dashboard."],
  evidence_checks: ["Evidence checks", "Shows each sentence of an answer beside the passage in your notes it came from."],
  corrections: ["Learning from corrections", "Remembers when you refile a note or dismiss a suggestion, and stops repeating it."],
  model_bench: ["Model bench", "Compares your installed models on your own notes."],
};

//: The master, which is not one of the seven: `facts.switches()` reports it
//: alongside them and, when it is on, reports every other one as off.
const LEARNED_MASTER = "paused";

//: What a derived kind is called. `ai/facts.py`'s `KINDS` is ("claim",
//: "question") today and the plan adds more (tensions, duplicates, entities,
//: dates); an unknown kind shows its own name rather than being dropped.
const LEARNED_KIND_COPY = {
  claim: "Claim",
  question: "Open question",
  //: The person's own word (decision 60, B31, B32).
  confirmed: "Confirmed by you",
  pinned: "Pinned as true",
  wrong: "Marked wrong",
};

let learnedOffset = 0;
let learnedTotal = 0;
//: The filter typing debounce, so a search box does not fire a request per
//: keystroke against a table that can hold thousands of rows.
let learnedSearchTimer = null;

function learnedKindLabel(kind) {
  return LEARNED_KIND_COPY[kind] || String(kind || "").replace(/_/g, " ") || "Fact";
}

async function renderLearnedSwitches() {
  const host = $("learned-switches");
  const banner = $("learned-paused-banner");
  if (!host) return;
  showSkeletons(host, 2);
  const switches = await apiJson("/learned/switches").catch(() => null);
  clearSkeletons(host);
  if (!switches) {
    host.replaceChildren();
    return;
  }
  const paused = Boolean(switches[LEARNED_MASTER]);
  host.replaceChildren();

  //: **`.setting-check`, the app's own on/off recipe** (DESIGN.md's index:
  //: "An on/off setting: `label.setting-check` with the switch first").
  //: These were built as `.checkbox-label row align-center`, which is the
  //: recipe for a checkbox *beside a word*, and it has no opinion about a
  //: hint: the `<small>` stayed inline, so every row read "Night shiftReads
  //: notes you have added or changed". Reported as "messy and not consistent
  //: with the design.md rules and the rest of the application", which is
  //: exactly what standing order 11 says happens when a new surface builds
  //: its own shape instead of taking one from the index.
  //:
  //: `.setting-check` is a three-column grid whose label column is a flex
  //: column, so the hint lands under its own title with the switch centred
  //: beside both, and the row fills with `--accent-soft` when it is on.
  const learnedRow = (title, hint) => {
    const row = document.createElement("label");
    row.className = "setting-check";
    const box = document.createElement("input");
    box.type = "checkbox";
    const text = document.createElement("span");
    //: The space is not decoration. `<small>` is a flex item in this column
    //: so it draws on its own line either way, but the accessible name is
    //: `textContent`, which without it reads "Night shiftReads notes you have
    //: added or changed" to a screen reader. The markup rows in index.html
    //: get the same space for free from their own indentation.
    text.append(document.createTextNode(hint ? `${title} ` : title));
    if (hint) {
      const small = document.createElement("small");
      small.className = "muted";
      small.textContent = hint;
      text.appendChild(small);
    }
    row.append(box, text);
    return { row, box };
  };

  //: The master first and set apart, because it is the answer to "stop all of
  //: this now" and a person looking for that is not going to read seven rows
  //: to find it.
  const master = learnedRow(
    "Pause all learning",
    "Nothing below runs while this is on. What has already been worked out is kept.",
  );
  master.row.classList.add("learned-master");
  master.box.id = "learned-pause-all";
  master.box.checked = paused;
  master.box.addEventListener("change", async () => {
    await learnedSetSwitch(LEARNED_MASTER, master.box.checked);
  });
  host.appendChild(master.row);

  //: **The seven live in their own box, and that is a layout decision with a
  //: rule behind it.** 08-consistency.css makes consecutive `.setting-check`
  //: rows one stack: hairline between, square where they meet, rounded only
  //: at the two outer ends. That is right for the seven, which are one set of
  //: choices. It is wrong across the master, which is set apart by a gap, and
  //: a row separated by a gap with a square top edge and a stack hairline on
  //: it looks like a mistake rather than a boundary. Putting the seven in a
  //: container means the adjacent-sibling rules simply stop at the master, so
  //: it keeps all four of its corners and the seven get their own stack.
  const stack = document.createElement("div");
  stack.className = "learned-switch-stack";
  host.appendChild(stack);

  for (const [name, value] of Object.entries(switches)) {
    if (name === LEARNED_MASTER) continue;
    const [title, hint] = LEARNED_SWITCH_COPY[name] || [name.replace(/_/g, " "), ""];
    const { row, box } = learnedRow(title, hint);
    box.checked = Boolean(value);
    //: Disabled rather than hidden while paused: the master says these are
    //: off, and a row that disappeared would leave no way to see what the
    //: master is holding down. `.disabled-row` is the app's own class for
    //: exactly this ("a row whose parent control is switched off"), so the
    //: seven dim together rather than each switch greying on its own.
    box.disabled = paused;
    row.classList.toggle("disabled-row", paused);
    box.addEventListener("change", async () => {
      await learnedSetSwitch(name, box.checked);
    });
    stack.appendChild(row);
  }

  if (banner) {
    banner.classList.toggle("hidden", !paused);
    banner.textContent = paused
      ? `Paused. ${nounCount(learnedTotal, "thing")} already worked out are kept and stay editable below.`
      : "";
  }
}

async function learnedSetSwitch(name, value) {
  try {
    await apiJson("/learned/switches", {
      method: "PUT",
      body: JSON.stringify({ [name]: value }),
    });
  } catch (error) {
    toast(error.message, true);
  }
  //: Re-read rather than trust the click: the master turns the other seven
  //: off in the *reply*, not in the request, so the only correct picture of
  //: the switches after any write is the one the server just sent back.
  //: The answers' evidence view reads Evidence checks again too.
  if (typeof evidenceSwitchReset === "function") evidenceSwitchReset();
  await renderLearnedSwitches();
}

//: The ticked rows on the page on screen. Cleared whenever the page is
//: redrawn: a selection you cannot see is one you cannot check before
//: deleting it, so it never survives a page turn or a new search.
const learnedSelected = new Map();

function syncLearnedSelectbar() {
  const bar = $("learned-selectbar");
  if (!bar) return;
  const count = learnedSelected.size;
  bar.classList.toggle("hidden", count === 0);
  $("learned-selected-count").textContent = `${count} selected`;
  //: Reset only means something for a row you edited; offering it over a
  //: selection with none would be a button that does nothing.
  const edited = [...learnedSelected.values()].filter((fact) => fact.edited_by_user).length;
  $("learned-bulk-reset").classList.toggle("hidden", edited === 0);
}

async function learnedBulk(action) {
  const ids = [...learnedSelected.keys()];
  if (!ids.length) return;
  if (action === "delete") {
    const ok = await confirmDialog(
      `Delete ${ids.length === 1 ? "this" : `these ${ids.length}`} and never work ${ids.length === 1 ? "it" : "them"} out again?\n\nYour notes are not touched. Each deletion is remembered, so the next run will not derive the same things.`,
      { confirmLabel: "Delete" }
    );
    if (!ok) return;
  }
  try {
    const picked = [...learnedSelected.values()];
    const reply = await apiJson("/learned/bulk", {
      method: "POST",
      body: JSON.stringify({ ids, action }),
    });
    const bulk = (what) => ["/learned/bulk", "POST", { ids, action: what }];
    if (action === "delete") {
      pushRoutePairUndo(`Deleted ${ids.length} learned thing${ids.length === 1 ? "" : "s"}`, bulk("restore"), bulk("delete"), () => renderLearnedList());
    } else {
      //: A reset puts the model's words back; Undo writes each edited text again.
      const edited = picked.filter((fact) => fact.edited_by_user);
      pushUndo(
        `Reset ${edited.length} learned thing${edited.length === 1 ? "" : "s"}`,
        async () => {
          for (const fact of edited) await apiJson(`/learned/${fact.id}`, { method: "PATCH", body: JSON.stringify({ text: fact.text }) });
          renderLearnedList();
        },
        async () => {
          await apiJson("/learned/bulk", { method: "POST", body: JSON.stringify({ ids: edited.map((fact) => fact.id), action: "reset" }) });
          renderLearnedList();
        }
      );
    }
    const verb = action === "delete" ? "Deleted" : "Reset";
    const gone = reply.missing?.length ? `, ${reply.missing.length} already gone` : "";
    toast(`${verb} ${reply.done}${gone}.`);
    if (action === "delete" && learnedOffset > 0 && learnedTotal - reply.done <= learnedOffset) {
      learnedOffset = Math.max(0, learnedOffset - LEARNED_PAGE);
    }
    renderLearnedList();
  } catch (error) {
    toast(error.message, true);
  }
}

function learnedRow(fact) {
  const li = document.createElement("li");
  li.className = "entry-item learned-row";
  li.dataset.factId = String(fact.id);

  const head = document.createElement("div");
  head.className = "row align-center learned-row-head";
  const pick = document.createElement("input");
  pick.type = "checkbox";
  pick.className = "learned-select";
  pick.setAttribute("aria-label", "Select this");
  pick.checked = learnedSelected.has(fact.id);
  pick.addEventListener("change", () => {
    if (pick.checked) learnedSelected.set(fact.id, fact);
    else learnedSelected.delete(fact.id);
    syncLearnedSelectbar();
  });
  head.appendChild(pick);
  const kind = document.createElement("span");
  kind.className = "chip";
  chipWords(kind, learnedKindLabel(fact.kind));
  head.appendChild(kind);
  if (fact.edited_by_user) {
    const edited = document.createElement("span");
    edited.className = "chip";
    chipWords(edited, "Edited by you");
    edited.title = "No later run overwrites this";
    head.appendChild(edited);
  }
  li.appendChild(head);

  const text = document.createElement("p");
  text.className = "learned-text";
  text.textContent = fact.text;
  li.appendChild(text);

  //: Where it came from, which is the whole difference between a claim you
  //: can check and a sentence an app asserted at you.
  const meta = document.createElement("p");
  meta.className = "muted learned-meta";
  const parts = [];
  if (fact.model) parts.push(fact.model);
  if (typeof fact.confidence === "number") parts.push(`${Math.round(fact.confidence * 100)}% sure`);
  if (fact.computed_at) parts.push(relativeTime(fact.computed_at));
  meta.textContent = parts.join(" · ");
  li.appendChild(meta);

  const acts = [];
  if (fact.entry_id) {
    acts.push({
      label: "ph:arrow-square-out Open the note",
      title: "Open the note this came from",
      run: () => {
        closeSettingsModal();
        flashEntry(fact.entry_id);
      },
    });
  }
  acts.push({ label: "ph:pencil-simple Edit", title: "Correct what this says", run: () => learnedEdit(fact) });
  if (fact.edited_by_user) {
    acts.push({
      label: "ph:arrow-counter-clockwise Reset",
      title: "Put the model's own words back",
      run: () => learnedReset(fact),
    });
  }
  acts.push({
    label: "ph:trash Delete",
    title: "Delete this, and never work it out again",
    run: () => learnedDelete(fact),
    danger: true,
  });
  const actions = rowActions(acts, "More for this fact");
  li.appendChild(actions);
  return li;
}

async function renderLearnedList() {
  const list = $("learned-list");
  const empty = $("learned-empty");
  const count = $("learned-count");
  if (!list) return;
  const kind = $("learned-kind")?.value || "";
  const q = $("learned-search")?.value.trim() || "";
  const query = new URLSearchParams({ limit: String(LEARNED_PAGE), offset: String(learnedOffset) });
  if (kind) query.set("kind", kind);
  if (q) query.set("q", q);
  showSkeletons(list, 3, "li");
  const data = await apiJson(`/learned?${query}`).catch(() => null);
  clearSkeletons(list);
  if (!data) {
    list.replaceChildren();
    if (count) count.textContent = "Couldn't load what it learned.";
    return;
  }
  learnedTotal = Number(data.total) || 0;
  learnedSelected.clear();
  syncLearnedSelectbar();
  list.replaceChildren(...data.items.map(learnedRow));
  if (empty) empty.classList.toggle("hidden", data.items.length > 0 || Boolean(q) || Boolean(kind));
  if (count) {
    if (!learnedTotal) count.textContent = q || kind ? "Nothing matches." : "";
    else {
      const from = learnedOffset + 1;
      const to = learnedOffset + data.items.length;
      count.textContent = `${from} to ${to} of ${learnedTotal}`;
    }
  }
  const prev = $("learned-prev");
  const next = $("learned-next");
  if (prev) prev.disabled = learnedOffset <= 0;
  if (next) next.disabled = learnedOffset + LEARNED_PAGE >= learnedTotal;
  //: The pager disappears rather than sitting there greyed out when one page
  //: is the whole table, which is every notebook until it is not.
  $("learned-pager")?.classList.toggle("hidden", learnedTotal <= LEARNED_PAGE);
}

async function learnedEdit(fact) {
  //: `promptDialog`, the app's one text dialog, rather than an inline
  //: textarea grown in the row: standing order 11, new UI comes from the
  //: recipe index. Its field is one line, which suits a derived claim (20 to
  //: 300 characters by `facts.MIN_SENTENCE_CHARS`/`MAX_SENTENCE_CHARS`).
  const next = await promptDialog("What should this say?", fact.text, { confirmLabel: "Save" });
  //: Empty is Cancel here, the way it is at every other `promptDialog` call
  //: site in the app: the dialog resolves with `""` for Cancel, for Escape
  //: and for a backdrop click alike, so a caller that treated empty as a
  //: value would answer a cancelled dialog with an error toast. Clearing the
  //: box and pressing Save therefore also does nothing, which is right:
  //: deleting a fact is the button next to this one.
  if (!next.trim() || next.trim() === fact.text.trim()) return;
  try {
    await apiJson(`/learned/${fact.id}`, {
      method: "PATCH",
      body: JSON.stringify({ text: next.trim() }),
    });
    pushRequestUndo("Edited a learned claim", `/learned/${fact.id}`, "PATCH", { text: fact.text }, { text: next.trim() }, () => renderLearnedList());
    toast("Saved. No later run will overwrite it.");
    renderLearnedList();
  } catch (error) {
    toast(error.message, true);
  }
}

async function learnedReset(fact) {
  try {
    await apiJson(`/learned/${fact.id}/reset`, { method: "POST" });
    pushUndo(
      "Put the model's words back",
      async () => {
        await apiJson(`/learned/${fact.id}`, { method: "PATCH", body: JSON.stringify({ text: fact.text }) });
        renderLearnedList();
      },
      async () => {
        await apiJson(`/learned/${fact.id}/reset`, { method: "POST" });
        renderLearnedList();
      }
    );
    toast("Put the model's own words back.");
    renderLearnedList();
  } catch (error) {
    toast(error.message, true);
  }
}

async function learnedDelete(fact) {
  const ok = await confirmDialog(
    "Delete this and never work it out again?\n\nYour note is not touched. The deletion is remembered, so the next run will not derive the same thing.",
    { confirmLabel: "Delete" }
  );
  if (!ok) return;
  try {
    await api(`/learned/${fact.id}`, { method: "DELETE" });
    pushRoutePairUndo("Deleted a learned thing", [`/learned/${fact.id}/restore`, "POST"], [`/learned/${fact.id}`, "DELETE"], () => { renderLearnedList(); renderLearnedSwitches(); });
    //: The page can be left holding nothing if the last row of the last page
    //: went, which reads as a bug ("it deleted everything"). Step back one
    //: page first, exactly as the note list does.
    if (learnedOffset > 0 && learnedTotal - 1 <= learnedOffset) {
      learnedOffset = Math.max(0, learnedOffset - LEARNED_PAGE);
    }
    renderLearnedList();
    renderLearnedSwitches();
  } catch (error) {
    toast(error.message, true);
  }
}

async function learnedForget() {
  const ok = await confirmDialog(
    "Forget everything the notebook has worked out?\n\nEvery derived claim, question and learned preference goes. Your notes, their history and everything you told it to remember are untouched. Undo brings it all back.",
    { confirmLabel: "Forget it all" }
  );
  if (!ok) return;
  try {
    const gone = await apiJson("/learned", {
      method: "DELETE",
      body: JSON.stringify({ confirm: true }),
    });
    pushTokenUndo("Forgot everything learned", [{ del: ["/learned", "DELETE", { confirm: true }], restore: "/learned/unforget", token: gone.undo_token }], renderLearned);
    learnedOffset = 0;
    toast("Forgotten. Your notes are exactly as they were.");
    renderLearned();
  } catch (error) {
    toast(error.message, true);
  }
}

async function learnedExport() {
  try {
    const data = await apiJson("/learned/export");
    const day = new Date().toISOString().slice(0, 10);
    await downloadJson(`tessellate-learned-${day}.json`, data);
  } catch (error) {
    toast(error.message, true);
  }
}

//: **One pass, now.** `POST /night/run` is the manual half of I1 and had no
//: caller: the pass ran on its own schedule and a person who wanted to know
//: what their notebook would make of a note they had just written had to
//: wait for it. The reply is the pass's own report, and it is worth showing
//: in full: `{paused}` when the switch above is off (which is the honest
//: answer, not an error), and otherwise how many notes were read, how many
//: things came out and why it stopped, because "it did nothing" and "it read
//: four thousand notes and found nothing new" are different answers and this
//: is the one screen that can tell them apart.
async function learnedRunNow() {
  const button = $("learned-run-now");
  const note = $("learned-run-note");
  if (!button) return;
  button.disabled = true;
  if (note) note.textContent = "Reading\u2026";
  try {
    const result = await apiJson("/night/run", {
      method: "POST",
      body: JSON.stringify({ budget: 20000 }),
    });
    if (result.paused) {
      if (note) note.textContent = "Night shift is off. Turn it on above and press this again.";
    } else {
      const derived = Number(result.derived) || 0;
      const scanned = Number(result.scanned) || 0;
      const stopped = result.stopped_reason === "budget" ? ", stopped at this run's budget" : "";
      if (note) {
        note.textContent = derived
          ? `Read ${nounCount(scanned, "note")}, worked out ${derived} new thing${derived === 1 ? "" : "s"}${stopped}.`
          : `Read ${nounCount(scanned, "note")}, nothing new${stopped}.`;
      }
      if (derived) renderLearnedList();
    }
  } catch (error) {
    if (note) note.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

//: Built once, with the modal, not per open: these are static controls and
//: rebinding them on every visit is how a settings panel ends up with six
//: copies of one listener.
function wireLearnedSection() {
  const kind = $("learned-kind");
  if (kind && kind.options.length <= 1) {
    for (const [value, label] of Object.entries(LEARNED_KIND_COPY)) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      kind.appendChild(option);
    }
  }
  kind?.addEventListener("change", () => {
    learnedOffset = 0;
    renderLearnedList();
  });
  $("learned-search")?.addEventListener("input", () => {
    clearTimeout(learnedSearchTimer);
    learnedSearchTimer = setTimeout(() => {
      learnedOffset = 0;
      renderLearnedList();
    }, 250);
  });
  $("learned-prev")?.addEventListener("click", () => {
    learnedOffset = Math.max(0, learnedOffset - LEARNED_PAGE);
    renderLearnedList();
  });
  $("learned-next")?.addEventListener("click", () => {
    learnedOffset += LEARNED_PAGE;
    renderLearnedList();
  });
  $("learned-run-now")?.addEventListener("click", learnedRunNow);
  $("learned-export")?.addEventListener("click", learnedExport);
  $("learned-forget")?.addEventListener("click", learnedForget);
  $("learned-bulk-delete")?.addEventListener("click", () => learnedBulk("delete"));
  $("learned-bulk-reset")?.addEventListener("click", () => learnedBulk("reset"));
  $("learned-bulk-done")?.addEventListener("click", () => {
    learnedSelected.clear();
    for (const box of document.querySelectorAll("#learned-list .learned-select")) box.checked = false;
    syncLearnedSelectbar();
  });
}

//: The "Learned from you" line (WORLD_CLASS_PLAN row 20, I7), from
//: `GET /learned/summary`: corrections counted and filing accuracy read off
//: the rows (`learning.filing_accuracy`), never estimated. Hidden while there
//: is nothing to say, so a new notebook does not open on "0 corrections".
function learnedFromYouText(sum) {
  if (!sum || (!sum.corrections && !sum.notes)) return "";
  const n = Number(sum.corrections) || 0;
  const head = `Learned from you: ${nounCount(n, "correction")}.`;
  if (!sum.notes || sum.accuracy == null) return `${head} No notes filed by Atlas yet.`;
  const over = `over the last ${nounCount(sum.notes, "note")} it filed`;
  if (sum.earlier != null && sum.later != null) {
    return `${head} Filing accuracy ${sum.earlier}% to ${sum.later}% ${over}.`;
  }
  return `${head} Filing accuracy ${sum.accuracy}% ${over}.`;
}

async function renderLearnedFromYou() {
  const line = $("learned-from-you");
  if (!line) return;
  const sum = await apiJson("/learned/summary").catch(() => null);
  const text = learnedFromYouText(sum);
  line.textContent = text;
  line.classList.toggle("hidden", !text);
}

async function renderLearned() {
  //: The list first, so the switches' "N things kept" line has a number.
  await renderLearnedList();
  await renderLearnedSwitches();
  await renderLearnedFromYou();
}

wireLearnedSection();

//: **Long Settings panes fold their tuned-once groups** (INBOX 424 m:
//: Appearance was 4,115px with 151 controls). Each group is a
//: `details.settings-fold` carrying a `data-fold-key` (DESIGN.md, the recipe
//: index): the markup says which one starts open (the first), and after
//: that the reader's own choice is kept, per group, in this browser. Open is
//: a property of how the pane is used rather than of one visit, which is the
//: recipe's own rule. A deep link opens the fold it lands in
//: (`openSettingsModal`), and that counts as opening it.
const SETTINGS_FOLDS_KEY = "settingsFolds";

function settingsFoldState() {
  try {
    const saved = prefs.json(SETTINGS_FOLDS_KEY, {});
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  } catch {
    return {};
  }
}

function wireSettingsFolds() {
  const state = settingsFoldState();
  for (const fold of document.querySelectorAll("#settings-modal details.settings-fold[data-fold-key]")) {
    const key = fold.dataset.foldKey;
    if (typeof state[key] === "boolean") fold.open = state[key];
    fold.addEventListener("toggle", () => {
      const now = settingsFoldState();
      now[key] = fold.open;
      try {
        prefs.set(SETTINGS_FOLDS_KEY, JSON.stringify(now));
      } catch {
        // A private window: the fold still works, it just is not remembered.
      }
    });
    //: A '?' on a folded group's head explains what is inside it, so
    //: pressing it opens the group too. It sits beside the summary rather
    //: than in it (`placeFoldHelp`), so the press cannot toggle the fold.
    fold.parentElement?.querySelector(":scope.fold-help-wrap > .fold-help")?.addEventListener("click", () => {
      fold.open = true;
    });
  }
}

//: **A fold head's '?' is beside its `<summary>`, drawn where it was in it**
//: (INBOX 433). A button inside a summary is a control inside a control:
//: axe-core's nested-interactive (WCAG 4.1.2) counted six in Settings, and
//: a screen reader announced the fold and could not reach its '?' as one.
//: So the '?' is the wrapper's first child (before the fold, so the Tab
//: order is the '?' and then the head, not the '?' after everything the
//: open fold holds), and the summary keeps an empty `.fold-help-slot` of the
//: button's size where the button was, so the head is laid out exactly as
//: before. This puts the button over its slot. Measured, because the slot
//: moves with the head's height, which differs by surface and by pointer
//: (36px, 44, 46, 50 measured; `scratchpad/ui-sweeps/foldhelp.js`); a
//: `ResizeObserver` on the wrapper and the summary re-places it whenever
//: either changes size, which is also when a hidden pane is first shown.
function placeFoldHelp(wrap) {
  const help = wrap.querySelector(":scope > .fold-help");
  const slot = wrap.querySelector(":scope > details > summary .fold-help-slot");
  if (!help || !slot || !slot.offsetParent) return;
  const box = wrap.getBoundingClientRect();
  const at = slot.getBoundingClientRect();
  help.style.top = `${at.top - box.top}px`;
  help.style.left = `${at.left - box.left}px`;
  help.style.right = "auto";
}

function wireFoldHelps() {
  const wraps = document.querySelectorAll("#settings-modal .fold-help-wrap");
  if (!wraps.length || typeof ResizeObserver !== "function") return;
  const observer = new ResizeObserver((entries) => {
    const seen = new Set();
    for (const entry of entries) {
      const wrap = entry.target.closest(".fold-help-wrap");
      if (wrap && !seen.has(wrap)) {
        seen.add(wrap);
        placeFoldHelp(wrap);
      }
    }
  });
  for (const wrap of wraps) {
    observer.observe(wrap);
    const summary = wrap.querySelector(":scope > details > summary");
    if (summary) observer.observe(summary);
  }
}

wireFoldHelps();

wireSettingsFolds();

// --- Last run of each job (INBOX 438) ------------------------------------------
//
// The owner: "there should be timestamps and success status for when various
// things were last ran like the search reindexing etc." The backend keeps one
// record per job kind (`core/jobruns.py`, `GET /jobs/last-runs`); this paints
// it. Every `[data-job-line="<kind>"]` in the page is filled from that one
// list, so a control gets its line by carrying the attribute and nothing else,
// and the Background jobs overview in Settings is the same lines in a column.
//
// One fetch serves them all. It runs when Settings changes section, after a
// button inside a block that has a line is pressed (a beat later, and again
// once the job has had time to finish), and every two seconds while any line
// on screen says "Running…". It stops by itself: no visible line, no timer.

const JOB_STATUS_WORDS = { ok: "succeeded", failed: "failed", cancelled: "stopped" };

let jobRunsList = null;
let jobRunsTimer = 0;
let jobRunsInFlight = false;

function jobDurationWords(ms) {
  if (typeof ms !== "number" || ms < 0) return "";
  if (ms < 1000) return "under a second";
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

// The words of one job's line, and what it should look like. `bare` leaves off
// the "Last run" lead for the overview, where the row's own name leads.
function jobRunLine(run, bare) {
  if (!run || !run.ran) {
    // Beside a control the line has to say which job it is about: the import
    // line sits under three different importers.
    const text = bare || !run ? "Not run yet." : `${run.label}: not run yet.`;
    return { text, title: "", failed: false, running: false };
  }
  if (run.status === "running") {
    return {
      text: "ph:spin Running…",
      title: run.started_at ? `Started ${whenText(run.started_at)}` : "",
      failed: false,
      running: true,
    };
  }
  const when = relativeTime(run.finished_at || run.started_at) || "at an unknown time";
  const head = bare ? when.charAt(0).toUpperCase() + when.slice(1) : `Last run ${when}`;
  const stamp = whenText(run.finished_at || run.started_at);
  const took = jobDurationWords(run.duration_ms);
  const title = took ? `${stamp}, took ${took}` : stamp;
  if (run.status === "failed") {
    return { text: `${head} · failed: ${run.error || "no reason was recorded"}`, title, failed: true, running: false };
  }
  const word = JOB_STATUS_WORDS[run.status] || run.status;
  return {
    text: `${head} · ${word}${run.result ? ` · ${run.result}` : ""}`,
    title,
    failed: false,
    running: false,
  };
}

function paintJobLine(el) {
  if (!jobRunsList) return;
  const run = jobRunsList.find((item) => item.kind === el.dataset.jobLine);
  const line = jobRunLine(run, el.dataset.jobBare === "1");
  // Skip a repaint that would say the same thing: a polite live region
  // re-reads whatever is replaced under it, and the timer fires every two
  // seconds for as long as a job runs.
  const signature = `${line.text}|${line.title}|${line.failed}`;
  if (el.dataset.jobSig === signature) return;
  el.dataset.jobSig = signature;
  el.dataset.jobRunning = line.running ? "1" : "";
  el.classList.toggle("error", line.failed);
  el.title = line.title;
  setLabel(el, line.text);
}

async function refreshJobRuns() {
  //: Not while locked: the 2 s poll outlived a lock and was refused with a
  //: 401 once or twice per lock (OPEN, forgotpw-1006). `lockNow` drops the
  //: token, so no token means no poll, and the timer is not re-armed.
  if (!authToken()) {
    clearTimeout(jobRunsTimer);
    return;
  }
  if (jobRunsInFlight) return;
  jobRunsInFlight = true;
  try {
    const body = await apiJson("/jobs/last-runs", { silent: true });
    jobRunsList = body.jobs || [];
  } catch {
    return; // a missing line is better than a toast over a status nicety
  } finally {
    jobRunsInFlight = false;
  }
  renderJobOverview();
  const lines = [...document.querySelectorAll("[data-job-line]")];
  for (const el of lines) paintJobLine(el);
  clearTimeout(jobRunsTimer);
  const running = lines.some((el) => el.offsetParent !== null && el.dataset.jobRunning === "1");
  if (running && authToken()) jobRunsTimer = setTimeout(refreshJobRuns, 2000);
}

// Settings, Background tasks, Background jobs: every kind in one column,
// the ones that have never run included, so the absence of a job reads as
// "not run yet" rather than "this app cannot do that".
function renderJobOverview() {
  const list = $("job-runs-list");
  if (!list || !jobRunsList) return;
  const reports = jobRunsList.map((run) => run.report || "").join();
  if (list.children.length === jobRunsList.length && list.dataset.reports === reports) return;
  list.dataset.reports = reports;
  list.replaceChildren();
  for (const run of jobRunsList) {
    const li = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = run.label;
    const line = document.createElement("p");
    line.className = "status job-line";
    line.setAttribute("role", "status");
    line.dataset.jobLine = run.kind;
    line.dataset.jobBare = "1";
    li.append(name, line);
    //: The last import's page of counts and skipped items (ledger 1406).
    if (run.report) {
      const page = smallButton("ph:file-text Report", `Open the report of the last ${run.label.toLowerCase()}`, async () => {
        if (await ensureModule("appImport")) openImportReport(run.report);
      });
      page.classList.add("quiet");
      li.append(page);
    }
    //: A scheduled pass says when it runs and has Run now (INBOX 713, the
    //: owner: "is it possible to manually run them").
    if (run.can_run) {
      const when = document.createElement("p");
      when.className = "muted task-detail";
      when.textContent = run.schedule || "";
      const go = smallButton("ph:play Run now", `Run ${run.label} now`, async () => {
        const result = await apiJson(`/jobs/passes/${encodeURIComponent(run.kind)}/run`, { method: "POST" }).catch((e) => ({ started: false, failed: true, error: e, message: e.message }));
        //: Already running is an expected answer, a plain toast; a request
        //: that threw is a fault, the red one.
        if (result.failed) toast(result.error.message, true);
        else toast(result.message, "info");
        refreshBackgroundTasks();
      });
      go.classList.add("job-run-now", "quiet");
      li.append(when, go);
    }
    list.appendChild(li);
  }
}

// A beat after a button inside a block with a line is pressed, and again once
// the job has had time to finish: the line then shows "Running…" and keeps
// itself fresh, or shows the ending of something quick.
document.addEventListener("click", (event) => {
  const button = event.target.closest && event.target.closest("button");
  if (!button) return;
  for (let node = button.parentElement; node && node !== document.body; node = node.parentElement) {
    if (node.querySelector("[data-job-line]")) {
      setTimeout(refreshJobRuns, 500);
      setTimeout(refreshJobRuns, 3000);
      return;
    }
  }
});
