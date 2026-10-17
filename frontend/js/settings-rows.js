// settings-rows.js: a setting is a row with a default and a reset
// (WORLD_CLASS_PLAN 25f, decision 52).
//
// Loaded by settings-find.js (itself lazy, with the first open of Settings),
// so none of this is in the boot budget. Three things:
//
// 1. **Changed from its default, said so.** A row whose control holds anything
//    but its default carries `.setting-modified` (a bar at its edge) and a
//    reset button; a pane with changed rows gets "Reset N" in its title bar.
//    A reset sets the control and fires its own event, so the save is the one
//    the control already makes: there is no second way to write a setting.
// 2. **Where it is kept, said so.** A look setting the notebook does not keep
//    (it is not in `mirroredUiKeys`, ai-tools.js) is marked "On this device".
//    Performance mode is the machine's, and sizes (`DEVICE_ONLY_KEYS`) are the
//    screen's; the rest follow the person.
// 3. **The settings as a file**: Settings, Import and export, Your settings.
//
// The registries are walked by tests/test_settings_rows.py against every key
// GET /preferences returns, so a new preference gets a row or a stated reason.

//: Preferences the notebook keeps (GET /preferences), each with the one
//: Settings control that shows it. `ui` is what the control shows for the
//: default when the two differ (a blank filing wait reads as 15); `on` and
//: `off` are a switch's two values when they are words, not true and false;
//: `radio` names a radio group by its `name`.
const SETTING_ROWS = [
  { key: "recycle_bin_days", id: "pref-bin-days" },
  { key: "conversation_retention_days", id: "pref-chat-retention" },
  { key: "search_min_similarity", id: "pref-search-min-sim" },
  { key: "search_relative_z_margin", id: "pref-search-z-margin" },
  { key: "communication_style", id: "pref-style" },
  { key: "composer_voice", id: "pref-voice" },
  { key: "week_start", id: "pref-week-start" },
  { key: "insight_level", id: "pref-insight" },
  { key: "smart_punctuation", id: "pref-smart-punctuation" },
  { key: "autocorrect", id: "pref-autocorrect" },
  { key: "profile_enabled", id: "pref-profile-enabled" },
  { key: "notifications_muted_except_reminders", id: "pref-notif-mute-except-reminders" },
  { key: "session_idle_ttl_minutes", id: "account-idle-ttl" },
  { key: "semantic_auto_install", id: "pref-semantic-auto-install" },
  { key: "ai_first_filing", id: "pref-ai-first-filing" },
  { key: "auto_file_sensitive", id: "pref-auto-file-sensitive" },
  { key: "filing_style", id: "pref-filing-style" },
  { key: "background_filing", id: "pref-background-filing" },
  { key: "warm_search_model_at_launch", id: "pref-warm-search-model" },
  { key: "filing_wait_seconds", id: "pref-filing-wait", ui: 15 },
  { key: "auto_caption_images", id: "pref-auto-caption-images" },
  { key: "auto_read_image_text", id: "pref-auto-read-image-text" },
  { key: "autonomous_tasks_enabled", id: "pref-autonomous-tasks" },
  { key: "auto_tag_enabled", id: "pref-auto-tag" },
  { key: "auto_link_enabled", id: "pref-auto-link" },
  { key: "auto_dedupe_enabled", id: "pref-auto-dedupe" },
  { key: "auto_stale_review_enabled", id: "pref-auto-stale-review" },
  { key: "auto_capture_enabled", id: "pref-auto-capture" },
  { key: "autonomous_tasks_interval_hours", id: "pref-autonomous-interval" },
  { key: "autonomous_tasks_model", id: "pref-autonomous-model" },
  { key: "battery_efficient_mode", id: "pref-battery-mode" },
  { key: "smart_model_routing_enabled", id: "pref-smart-model-routing" },
  { key: "local_only_ai", id: "local-only-ai" },
  { key: "tool_focus", id: "tool-focus-auto", radio: "tool-focus" },
  { key: "small_model_mode", id: "small-model-mode" },
  { key: "run_budget_tokens", id: "run-budget-tokens" },
  { key: "run_budget_seconds", id: "run-budget-seconds" },
  { key: "web_search_enabled", id: "pref-web-search" },
  { key: "searxng_url", id: "pref-searxng" },
  { key: "searxng_autostart", id: "searxng-autostart" },
  { key: "update_check_enabled", id: "pref-update-check" },
  { key: "auto_update_enabled", id: "pref-auto-update" },
  { key: "update_channel", id: "pref-update-channel-main", on: "main", off: "stable" },
  { key: "update_beta", id: "pref-update-beta" },
  { key: "voice_model", id: "voice-model-select" },
  { key: "voice_skip_silence", id: "voice-skip-silence" },
  { key: "voice_language", id: "voice-language-select" },
  { key: "voice_vocabulary", id: "voice-vocabulary" },
  { key: "show_console_on_startup", id: "pref-show-console" },
  { key: "close_to_tray", id: "pref-close-to-tray" },
  { key: "new_window_on_launch", id: "pref-new-window-on-launch" },
  { key: "status_bar_clock", id: "status-bar-clock-toggle" },
];

//: Appearance, kept in `localStorage` and mirrored to the notebook (every key
//: in `mirroredUiKeys`; `perf` and the sizes in `DEVICE_ONLY_KEYS` stay on the device). The default is the active theme's value, else
//: APPEARANCE_DEFAULTS (settings.js), else `base`. `seg` names a segmented
//: group's data attribute. Zoom, the accent and the palette are left out:
//: each already has its own reset beside it.
const LOOK_ROWS = [
  { key: "fontsize", id: "fontsize-seg", seg: "fontsize" },
  { key: "font", id: "font-seg" },
  { key: "density", id: "density-seg", ui: "auto" },
  { key: "contrast", id: "contrast-toggle", on: "on", base: "off" },
  { key: "motion", id: "reduce-motion-toggle", on: "reduced", off: "auto" },
  { key: "ui-motion", id: "ui-motion-toggle", on: "on", off: "off" },
  { key: "progress-motion", id: "progress-motion" },
  { key: "show-thinking-words", id: "pref-show-thinking-words", on: "on", off: "off" },
  { key: "perf", id: "perf-mode" },
  { key: "glass", id: "glass-toggle", on: "on", off: "off" },
  { key: "glass-sheen", id: "glass-sheen-toggle", on: "on", off: "off" },
  { key: "page-wash", id: "page-wash-toggle", on: "on", off: "off" },
  { key: "glass-sheen-strength", id: "glass-sheen-strength" },
  { key: "glass-blur", id: "glass-blur" },
  { key: "glass-opacity", id: "glass-opacity" },
  { key: "radius", id: "radius-slider" },
  { key: "border-style", id: "border-style-seg", seg: "borderChoice" },
  { key: "shadow-intensity", id: "shadow-intensity" },
  { key: "bgArt", id: "bg-art-toggle", on: "on", base: "off" },
  { key: "bg-style", id: "bg-art-style", seg: "bgStyle" },
  { key: "bg-motion", id: "bg-motion" },
  { key: "bg-intensity", id: "bg-intensity" },
  { key: "avatar-motion", id: "avatar-motion" },
  { key: "avatar-follow", id: "avatar-follow", on: "on", off: "off" },
  { key: "avatar-buddy", id: "avatar-buddy" },
  { key: "atlas-style", id: "atlas-style" },
  { key: "assistant-avatar", id: "assistant-avatar" },
  { key: "atlas-look", id: "atlas-look" },
  { key: "face-look", id: "face-look" },
  { key: "dash-mark", id: "dash-mark" },
];

//: The defaults the server gives a fresh notebook, fetched once per page.
const settingRowsState = { defaults: null, loading: null, wired: false, timers: [] };

function settingDefaults() {
  if (settingRowsState.defaults) return Promise.resolve(settingRowsState.defaults);
  settingRowsState.loading ||= apiJson("/preferences/defaults", { silent: true })
    .then((body) => (settingRowsState.defaults = body))
    .catch(() => {
      settingRowsState.loading = null;
      return null;
    });
  return settingRowsState.loading;
}

// --- what a control shows -------------------------------------------------------

function settingRadio(row, value) {
  return document.querySelector(`#settings-modal input[name="${row.radio}"][value="${value}"]`);
}

function settingSegButton(row, value) {
  const attr = row.seg.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
  return $(row.id)?.querySelector(`button[data-${attr}="${value}"]`);
}

//: The control's state as a string, comparable with `settingShows`.
function settingNow(row) {
  const el = $(row.id);
  if (!el) return null;
  if (row.radio) return document.querySelector(`#settings-modal input[name="${row.radio}"]:checked`)?.value ?? "";
  if (row.seg) return el.querySelector("button.active")?.dataset[row.seg] ?? "";
  if (el.type === "checkbox") return el.checked ? "true" : "false";
  return el.value;
}

//: What the control shows for `value`, in `settingNow`'s terms.
function settingShows(row, value) {
  const el = $(row.id);
  if (el?.type === "checkbox" && !row.radio) {
    return (row.on !== undefined ? String(value) === row.on : value === true) ? "true" : "false";
  }
  return value === null || value === undefined ? "" : String(value);
}

function sameSettingValue(a, b) {
  if (a === b) return true;
  //: "0.25" and "0.250", "30" and "30.0": a number box rewrites what it holds.
  return a !== "" && b !== "" && !Number.isNaN(Number(a)) && Number(a) === Number(b);
}

function lookBase(row) {
  return themeValue(row.key) ?? APPEARANCE_DEFAULTS[row.key] ?? row.base;
}

//: The value a reset puts back, in the control's own terms.
function settingDefaultShown(row) {
  if (row.look) return settingShows(row, row.ui ?? lookBase(row));
  const value = row.ui ?? settingRowsState.defaults?.[row.key];
  return settingShows(row, value);
}

function settingIsModified(row) {
  if (row.look) {
    //: A look setting with nothing stored is the theme's or the default.
    const stored = prefs.get(row.key, null);
    if (stored == null) return false;
    return row.ui !== undefined || !sameSettingValue(String(stored), String(lookBase(row)));
  }
  if (!settingRowsState.defaults || !(row.key in settingRowsState.defaults)) return false;
  const now = settingNow(row);
  return now !== null && !sameSettingValue(now, settingDefaultShown(row));
}

// --- the row and its marks ------------------------------------------------------

//: The row a person reads as one setting. An appearance row is a
//: `.setting-row` holding its words and, in a `.row` of its own, the control;
//: the outer one is the setting, so it is asked for first.
function settingRowEl(row) {
  const el = $(row.id);
  return el?.closest(".setting-row") || el?.closest("label.setting-check, label.check-row, .check-row, .row") || el?.parentElement || null;
}

//: A row's name for its reset's label: the words a person reads beside it,
//: never a slider's value ("14px").
function settingRowName(row, rowEl) {
  const own = $(row.id);
  const words = rowEl.querySelector(":scope > .setting-label") || own?.labels?.[0] || rowEl;
  const text = settingRowText(words);
  const named = /[a-z]{3}/i.test(text) ? text : own?.getAttribute("aria-label");
  return (named || "this setting").slice(0, 80);
}

//: A row the window is not showing (a desktop-only row in a browser, a panel
//: whose switch is off) holds whatever its markup said, not the setting.
function settingRowShown(rowEl, pane) {
  const hidden = rowEl.closest(".hidden");
  return !hidden || hidden === pane || !pane.contains(hidden);
}

//: Where the reset and the chip go: right after the setting's name where the
//: row has a name of its own (an appearance row, a switch with a line under
//: it), so the row neither grows nor gives up width; at the row's end
//: otherwise. Measured before: rows 12 to 38px taller once marked, the
//: third child wrapping under a two-column row.
function settingMarkHost(rowEl) {
  const named = rowEl.querySelector(":scope > .setting-label > span:first-child");
  if (named) return { host: named, before: null };
  const words = rowEl.matches("label.setting-check") ? rowEl.querySelector(":scope > span") : null;
  if (words?.querySelector(":scope > small")) return { host: settingNameLine(words), before: null };
  return { host: rowEl, before: null };
}

//: A switch's words are a flex column (the name, then its line), so a mark
//: put beside the name would take a line of its own. The name goes into the
//: one-line row the "?" toggles already use (`.setting-hint-row`).
function settingNameLine(words) {
  const line = words.querySelector(":scope > .setting-hint-row");
  if (line) return line;
  const made = document.createElement("span");
  made.className = "setting-hint-row";
  while (words.firstChild && !(words.firstChild.nodeType === 1 && words.firstChild.matches("small, .setting-hint, div, p"))) {
    made.appendChild(words.firstChild);
  }
  words.prepend(made);
  return made;
}

function settingResetButton(row, rowEl) {
  let button = rowEl.querySelector(`.setting-reset[data-setting-key="${row.key}"]`);
  if (button) return button;
  button = document.createElement("button");
  button.type = "button";
  button.className = "icon-only ghost small setting-reset";
  button.dataset.settingKey = row.key;
  const name = settingRowName(row, rowEl);
  button.title = "Reset to default";
  button.setAttribute("aria-label", `Reset ${name} to its default`);
  const icon = document.createElement("i");
  icon.className = "ph ph-arrow-counter-clockwise";
  icon.setAttribute("aria-hidden", "true");
  button.appendChild(icon);
  //: Inside a `label` the press must not also toggle the switch it sits by.
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    resetSettingRow(row);
  });
  const place = settingMarkHost(rowEl);
  place.host.insertBefore(button, place.before);
  //: A reset beside or inside a dropdown's shell keeps its gap from it in
  //: settings-controls-lazy.css (an inline margin here missed the inside case).
  return button;
}

function settingScopeChip(row, rowEl) {
  if (!row.look || rowEl.querySelector(".setting-scope")) return;
  if (mirroredUiKeys().includes(row.key)) return;
  const scope = chip("On this device", "setting-scope");
  scope.title = "Kept on this device only: another browser, computer or phone has its own";
  const place = settingMarkHost(rowEl);
  place.host.insertBefore(scope, place.before);
}

function paintSettingRow(row, pane) {
  const rowEl = settingRowEl(row);
  if (!rowEl) return false;
  settingScopeChip(row, rowEl);
  const modified = settingRowShown(rowEl, pane) && settingIsModified(row);
  if (rowEl.classList.contains("setting-modified") !== modified) rowEl.classList.toggle("setting-modified", modified);
  const button = modified ? settingResetButton(row, rowEl) : rowEl.querySelector(`.setting-reset[data-setting-key="${row.key}"]`);
  if (button) button.hidden = !modified;
  return modified;
}

function allSettingRows() {
  return [...SETTING_ROWS, ...LOOK_ROWS.map((row) => ({ ...row, look: true }))];
}

function settingRowsIn(pane) {
  return allSettingRows().filter((row) => {
    const el = $(row.id);
    return el && pane.contains(el);
  });
}

function paintSettingRows(name) {
  const pane = $(`settings-${name}`);
  if (!pane) return;
  const changed = settingRowsIn(pane).filter((row) => paintSettingRow(row, pane));
  paintSectionReset(pane, changed);
}

//: "Reset N" in the pane's title bar, only while something in it is changed.
function paintSectionReset(pane, changed) {
  const bar = pane.querySelector(":scope > .settings-pane-title, :scope > .dock");
  let button = pane.querySelector(".settings-reset-section");
  if (!bar) return;
  if (!button && changed.length) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small settings-reset-section";
    button.addEventListener("click", () => resetSettingSection(pane));
    bar.appendChild(button);
  }
  if (!button) return;
  button.hidden = !changed.length;
  button.textContent = changed.length === 1 ? "Reset 1 change" : `Reset ${changed.length} changes`;
  button.title = "Put every changed setting in this section back to its default";
}

// --- resetting ------------------------------------------------------------------

function fireSettingEvents(el) {
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

//: Puts the control at its default and lets the control's own handler save
//: it, so a reset writes exactly what choosing the default by hand writes.
function resetSettingRow(row) {
  const shown = settingDefaultShown(row);
  const el = $(row.id);
  if (!el) return;
  if (row.radio) {
    const radio = settingRadio(row, shown);
    if (radio) {
      radio.checked = true;
      fireSettingEvents(radio);
    }
  } else if (row.seg) {
    settingSegButton(row, shown)?.click();
  } else if (el.type === "checkbox") {
    el.checked = shown === "true";
    fireSettingEvents(el);
  } else {
    el.value = shown;
    fireSettingEvents(el);
  }
  scheduleSettingRowsPaint(currentSettingsSection, [60, 600]);
}

function resetSettingSection(pane) {
  const rows = settingRowsIn(pane).filter((row) => settingRowEl(row)?.classList.contains("setting-modified"));
  for (const row of rows) resetSettingRow(row);
  toast(rows.length === 1 ? "1 setting reset to its default." : `${rows.length} settings reset to their defaults.`);
}

// --- when to paint --------------------------------------------------------------

function scheduleSettingRowsPaint(name, delays) {
  for (const timer of settingRowsState.timers) clearTimeout(timer);
  settingRowsState.timers = delays.map((ms) => setTimeout(() => {
    if (currentSettingsSection === name) paintSettingRows(name);
  }, ms));
}

//: Called by `settingsIndexWatchSection` (settings-find.js) on every section
//: shown. The panes fill from their own fetches after they are shown, so the
//: rows are painted again once those have had time to land; a change made in
//: the window repaints at once.
function settingRowsWatch(name) {
  if (!settingRowsState.wired) {
    settingRowsState.wired = true;
    const modal = $("settings-modal");
    const repaint = () => scheduleSettingRowsPaint(currentSettingsSection, [30, 500]);
    modal?.addEventListener("change", repaint);
    modal?.addEventListener("input", repaint);
    modal?.addEventListener("click", (event) => {
      if (event.target.closest?.(".seg button")) repaint();
    });
    wireSettingsFile();
  }
  settingDefaults().then(() => scheduleSettingRowsPaint(name, [0, 400, 1200]));
}

// --- the settings file ----------------------------------------------------------

//: The look settings only this browser keeps, which the server's export cannot
//: see, so the file carries them beside the notebook's own.
function browserOnlySettings() {
  const mirrored = new Set(mirroredUiKeys());
  const out = {};
  for (const row of LOOK_ROWS) {
    if (mirrored.has(row.key) || DEVICE_ONLY_KEYS.includes(row.key)) continue;
    const value = prefs.get(row.key, null);
    if (value != null) out[row.key] = String(value).slice(0, 400);
  }
  return out;
}

async function settingsFileSnapshot() {
  const body = await apiJson("/preferences/export");
  return { ...body, this_browser: browserOnlySettings() };
}

async function exportSettingsFile() {
  const status = $("settings-file-status");
  try {
    const body = await settingsFileSnapshot();
    const day = new Date().toISOString().slice(0, 10);
    await downloadJson(`tessellate-settings-${day}.json`, body);
    status.textContent = `Exported ${Object.keys(body.preferences).length + Object.keys(body.this_browser).length} settings.`;
  } catch (error) {
    status.textContent = error.message;
    toast(error.message, true, { action: ["Try again", exportSettingsFile] });
  }
}

//: Writes the file's look settings into this browser, which is where the app
//: reads them from: the notebook's copy (`ui_state`) only seeds an empty one.
function applyLookSettings(file) {
  const mirrored = new Set(mirroredUiKeys());
  const local = new Set(LOOK_ROWS.map((row) => row.key).filter((key) => !mirrored.has(key)));
  const fromNotebook = file.preferences?.ui_state || {};
  const fromBrowser = file.this_browser || {};
  for (const [key, value] of Object.entries(fromNotebook)) {
    if (mirrored.has(key) && typeof value === "string") prefs.set(key, value);
  }
  for (const [key, value] of Object.entries(fromBrowser)) {
    if (local.has(key) && !DEVICE_ONLY_KEYS.includes(key) && typeof value === "string") prefs.set(key, value);
  }
  applyAppearance();
  if (currentSettingsSection === "appearance") renderAppearance();
}

async function applySettingsFile(file) {
  const result = await apiJson("/preferences/import", { method: "POST", body: JSON.stringify(file) });
  prefsCache = result.preferences;
  applyLookSettings(file);
  return result;
}

function settingsImportWords(result) {
  const applied = result.applied.length;
  const head = applied === 1 ? "1 setting changed" : `${applied} settings changed`;
  if (!result.skipped.length) return `${head}.`;
  const names = result.skipped.slice(0, 4).map((row) => `${row.key} (${row.reason})`).join(", ");
  return `${head}; skipped ${names}${result.skipped.length > 4 ? ", and more" : ""}.`;
}

async function importSettingsFile(fileHandle) {
  const status = $("settings-file-status");
  try {
    const file = JSON.parse(await fileHandle.text());
    const before = await settingsFileSnapshot();
    const result = await applySettingsFile(file);
    status.textContent = settingsImportWords(result);
    offerUndo(
      "Import settings",
      `Settings imported: ${settingsImportWords(result)}`,
      //: Undo replaces the lists whole: the import merged them by name.
      () => applySettingsFile({ ...before, replace_lists: true }).then(() => scheduleSettingRowsPaint(currentSettingsSection, [0])),
      () => applySettingsFile(file).then(() => scheduleSettingRowsPaint(currentSettingsSection, [0]))
    );
    scheduleSettingRowsPaint(currentSettingsSection, [0, 500]);
  } catch (error) {
    const words = error instanceof SyntaxError ? "That file is not a settings file (it is not JSON)." : error.message;
    status.textContent = words;
    //: A file the import cannot use is the person's pick, not a fault: it says
    //: why, and the server names each setting it skipped and its reason.
    toast(words, "info");
  }
}

function wireSettingsFile() {
  const input = $("settings-file-input");
  $("settings-file-export")?.addEventListener("click", exportSettingsFile);
  $("settings-file-import")?.addEventListener("click", () => input?.click());
  input?.addEventListener("change", () => {
    const chosen = input.files?.[0];
    input.value = "";
    if (chosen) importSettingsFile(chosen);
  });
}
