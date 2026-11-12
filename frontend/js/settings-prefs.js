// settings-prefs.js: the Settings sections that read /preferences into their
// fields (Preferences, General, Search and index, Personas, Web search, Background
// tasks) and the dirty marks on the Preferences form. Moved out of
// settings-panes.js for the boot gzip budget (tests/test_static_compression.py):
// the only callers are `showSettingsSection` (settings.js) and the Settings
// window's own listeners, all of which run after `openSettingsModal` has
// awaited `ensureModule("settingsControls")`, which loads this file with them.
// `prefsCache`, `savePrefs`, `markPrefsDirty` and `markPrefsSaved` stay in
// settings-panes.js because the status bar and the palette also use them.

async function renderPrefs() {
  //: The optional-package notices for what this pane's switches use (extra-notice.js).
  extraNoticeMount($("xn-documents"), "documents", { fresh: true });
  extraNoticeMount($("xn-semantic"), "semantic");
  //: **A change still waiting for its quiet save is written first.** Profile
  //: and General save 700 ms after the last change (`markPrefsDirty`); opening
  //: either, or Search and index or Personas, lands here, and the GET below
  //: wrote the old value over the form, which the timer then saved: the switch
  //: you had just pressed went back and nothing said so (found by the
  //: deepflows sweep).
  if (prefsDirty) await savePrefs({ quiet: true });
  if (prefsSaveInFlight) await prefsSaveInFlight.catch(() => {});
  prefsCache = await apiJson("/preferences");
  $("pref-display-name").value = prefsCache.display_name || "";
  $("pref-semantic-auto-install").checked = prefsCache.semantic_auto_install ?? false;
  //: The saved look, and its controls (avatars.js, once it is in).
  const savedLook = prefsCache.avatar_style || {};
  afterCharacters(() => {
    setOwnNameMarkStyle(savedLook);
    mountProfileLook();
  });
  $("pref-bin-days").value = prefsCache.recycle_bin_days;
  $("pref-chat-retention").value = prefsCache.conversation_retention_days ?? 0;
  $("pref-search-min-sim").value = prefsCache.search_min_similarity;
  $("pref-search-z-margin").value = prefsCache.search_relative_z_margin;
  $("pref-style").value = prefsCache.communication_style;
  $("pref-voice").value = prefsCache.composer_voice;
  $("pref-week-start").value = prefsCache.week_start || "auto";
  $("pref-season-hemisphere").value = prefsCache.season_hemisphere || "auto";
  $("pref-birthday").value = prefsCache.birthday || "";
  $("pref-date-order").value = prefsCache.date_order || "auto";
  $("pref-before-includes-day").checked = prefsCache.before_includes_day === true;
  $("pref-insight").value = prefsCache.insight_level || "one";
  $("pref-profile").value = prefsCache.user_profile;
  $("pref-profile-enabled").checked = prefsCache.profile_enabled;
  paintUserMarks();
  updateProfileCount();
  if (prefsCache.session_idle_ttl_minutes) {
    $("account-idle-ttl").value = prefsCache.session_idle_ttl_minutes;
  }
  $("account-private-idle").value = prefsCache.private_space_idle_minutes;
  $("pref-new-notes-private").checked = Boolean(prefsCache.new_notes_private);
  $("pref-notif-mute-except-reminders").checked = Boolean(
    prefsCache.notifications_muted_except_reminders
  );
  $("pref-smart-punctuation").checked = prefsCache.smart_punctuation === true;
  $("pref-autocorrect").checked = prefsCache.autocorrect !== false;
  $("pref-link-offers").checked = prefsCache.link_offers !== false;
  $("pref-check-link-text").checked = prefsCache.check_link_text === true;
  $("prefs-status").textContent = "";
  //: The fields now hold what the server holds, so nothing is unsaved: this
  //: also covers the reopen, since `showSettingsSection` re-renders.
  markPrefsSaved();
}

// --- Settings, Web search ------------------------------------------------------
//
// Its own screen, and its own save. Web search used to be four controls inside
// Preferences, which is why every error message that said "Settings, Web
// search" pointed at a screen that did not exist.
//
// The engine list comes from the server rather than being written out here:
// the frontend and `websearch.PROVIDERS` would otherwise drift, and the first
// symptom would be a radio button the API rejects.
// The Background tasks section's own controls (`#pref-autonomous-tasks` and
// everything under it): pulled out so `showSettingsSection` can populate
// them the moment *that* section opens, not only as a side effect of opening
// Web search. They used to be filled in exclusively by `renderWebSearch`
// despite living in `#settings-tasks`, a different section entirely, open
// Settings, Background tasks directly in a fresh session (never having
// visited Web search) and every checkbox here read its raw HTML default
// (unchecked) instead of what was actually saved. Toggling one of them then
// called `savePrefs()`, which rebuilds the *entire* preferences object from
// the DOM: sending those defaults back to the server and silently
// overwriting the real values. This is "my preferences settings keep
// getting deleted": not one bad field, but a whole section's worth of
// settings reset the moment anything on it was touched without the
// Web-search tab having been opened first in the same session.
function renderAutonomousSettings() {
  $("pref-autonomous-tasks").checked = Boolean(prefsCache.autonomous_tasks_enabled);
  $("pref-ai-first-filing").checked = prefsCache.ai_first_filing ?? true;
  $("pref-auto-file-sensitive").checked = Boolean(prefsCache.auto_file_sensitive);
  $("pref-ask-when-unsure").checked = Boolean(prefsCache.ask_when_unsure);
  $("pref-filing-style").value = prefsCache.filing_style || "topic";
  $("pref-background-filing").checked = prefsCache.background_filing ?? true;
  $("pref-warm-search-model").checked = prefsCache.warm_search_model_at_launch ?? true;
  $("pref-filing-wait").value = prefsCache.filing_wait_seconds || 15;
  $("pref-auto-caption-images").checked = prefsCache.auto_caption_images ?? true;
  $("pref-auto-read-image-text").checked = prefsCache.auto_read_image_text ?? true;
  $("pref-auto-tag").checked = prefsCache.auto_tag_enabled ?? true;
  $("pref-auto-link").checked = prefsCache.auto_link_enabled ?? true;
  $("pref-auto-dedupe").checked = prefsCache.auto_dedupe_enabled ?? true;
  $("pref-auto-stale-review").checked = Boolean(prefsCache.auto_stale_review_enabled);
  $("pref-auto-capture").checked = Boolean(prefsCache.auto_capture_enabled);
  $("pref-mcp-writes").checked = Boolean(prefsCache.mcp_writes_enabled);
  $("pref-autonomous-interval").value = prefsCache.autonomous_tasks_interval_hours || 6;
  $("pref-autonomous-model").value = prefsCache.autonomous_tasks_model || "";
  $("pref-battery-mode").checked = Boolean(prefsCache.battery_efficient_mode);
  $("pref-smart-model-routing").checked = prefsCache.smart_model_routing_enabled ?? true;
  toggleAutonomousPanel();
}

async function renderWebSearch() {
  extraNoticeMount($("searxng-host-state")?.closest(".searxng-host"), "searxng", { fresh: true });
  prefsCache = await apiJson("/preferences");
  $("pref-web-search").checked = Boolean(prefsCache.web_search_enabled);
  $("pref-web-store").checked = prefsCache.web_store_enabled !== false;
  $("pref-searxng").value = prefsCache.searxng_url || "";
  renderAutonomousSettings();
  $("searxng-autostart").checked = Boolean(prefsCache.searxng_autostart);
  $("search-provider-status").textContent = "";

  const picker = $("search-provider-picker");
  picker.replaceChildren();
  const info = await apiJson("/websearch/providers").catch(() => null);
  if (!info) {
    picker.textContent = "Couldn't load the engine list.";
    return;
  }
  for (const provider of info.providers) {
    const row = document.createElement("label");
    row.className = "provider-option";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "search-provider";
    radio.value = provider.id;
    radio.checked = provider.id === info.selected;
    radio.addEventListener("change", () => saveSearchProvider(provider.id));
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = provider.label;
    const detail = document.createElement("span");
    detail.className = "muted provider-detail";
    detail.textContent = provider.detail;
    text.append(title, document.createElement("br"), detail);
    row.append(radio, text);
    picker.appendChild(row);
  }
  //: `refreshSearxngHost` is in settings-controls.js; the stand-in
  //: (LAZY_ENTRY_POINTS) loads it for a pane drawn before the window's await.
  refreshSearxngHost().catch(() => {});
}

async function saveSearchProvider(provider) {
  const status = $("search-provider-status");
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ search_provider: provider }),
    });
    status.classList.remove("error");
    status.textContent = "Saved.";
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

//: Every control the payload above reads, so the mark cannot go stale against
//: a field someone adds to one and forgets in the other. A `change` and an
//: `input` both, because a `<select>` and a checkbox fire the first and a
//: text field is worth marking on the keystroke rather than on the blur.
const PREFS_FIELD_IDS = [
  "pref-display-name", "pref-bin-days", "pref-chat-retention",
  "pref-search-min-sim", "pref-search-z-margin", "pref-style",
  "pref-profile", "pref-profile-enabled", "pref-notif-mute-except-reminders",
  "pref-smart-punctuation", "pref-autocorrect",
];

function wirePrefsDirtyMarks() {
  for (const id of PREFS_FIELD_IDS) {
    const el = $(id);
    if (!el) continue;
    el.addEventListener("input", markPrefsDirty);
    el.addEventListener("change", markPrefsDirty);
  }
  //: The profile head previews the name as it is typed; the rest of the app's
  //: marks wait for the save, since that is when the name is real.
  $("pref-display-name")?.addEventListener("input", (e) => {
    const typed = e.target.value.trim();
    afterCharacters(() => $("profile-avatar")?.replaceChildren(nameMark(typed || "You", 56)));
    const head = $("profile-head-name");
    if (head) head.textContent = typed || "Your profile";
  });
  $("pref-profile")?.addEventListener("input", updateProfileCount);
}

//: Moved from ai-tools.js (boot gzip). Called by settings-models.js's status render and the backend radio
//: in settings-controls.js, both through the settingsControls stand-in (app.js LAZY_ENTRY_POINTS).
//: **A control says whether it is the one in use.** Asked after reading the
//: code: *"does the ai embedding model actually get used??"* It does, in
//: seven places, but only when the backend radio above is set to Ollama, and
//: the built-in backend is the default. So somebody who picked a model here
//: expecting it to be doing the work had a fully enabled, fully ignored
//: control, which is the same class of thing as a disabled control that does
//: not say why: a setting whose state is invisible.
//:
//: Disabled rather than hidden, because hiding it would make the choice
//: unfindable from the radio that names it, and the reason rides on the
//: tooltip so the state is legible without another paragraph on screen.
//:
//: `offline` is passed by the status poll, which knows; the radio's own
//: handler omits it and it is read back off the control the poll last set,
//: so a change of radio cannot claim Ollama is reachable when it is not.
function syncEmbeddingPickerState(offline) {
  const ollamaRadio = document.querySelector('input[name="emb-backend"][value="ollama"]');
  const down = offline === undefined ? Boolean(ollamaRadio?.disabled) : offline;
  const usingOllama =
    document.querySelector('input[name="emb-backend"]:checked')?.value === "ollama";
  const picker = $("embedding-model-select");
  if (!picker) return;
  picker.disabled = down || !usingOllama;
  //: An empty select says nothing: with Ollama off it drew as a blank 46px
  //: box beside a pale Apply button. It names why it is empty instead.
  if (!picker.options.length || picker.options[0].dataset.placeholder) {
    const note = down ? "Needs Ollama running" : "No embedding models installed";
    let option = picker.options[0];
    if (!option) {
      option = document.createElement("option");
      option.value = "";
      option.dataset.placeholder = "1";
      picker.appendChild(option);
    }
    option.textContent = note;
  }
  picker.title = down
    ? "Ollama is not running, so there are no embedding models to choose from"
    : usingOllama
      ? "The model used for semantic search"
      : "Only used when the backend above is set to Ollama. The built-in one is in use";
  const apply = $("embedding-apply");
  if (!apply) return;
  //: **Enabled for the built-in choice too.** It was disabled whenever
  //: Built-in was picked, so switching back from an Ollama model could never
  //: be applied: the backend stayed on Ollama and that model stayed "in use"
  //: and could not be removed (owner, 0.3.31).
  apply.disabled = usingOllama && down;
  apply.title = usingOllama
    ? "Re-read every note with this model"
    : "Switch to the built-in model and re-read every note with it";
}
