// settings-controls.js: the click, change and input listeners of every control
// inside the Settings window. They were top-level element `addEventListener`
// statements spread over skills.js, settings-panes.js, ai-tools.js,
// phone-shell.js, wiring.js, settings-wiring.js and spaces-find.js, and moved
// here on 2026-10-05 (the boot-script gzip budget, ratchet in
// tests/test_static_compression.py): a control inside the window cannot be
// pressed before the window opens, so nothing here is needed to draw the
// first screen.
//
// **Why this is safe.** The window opens in exactly one place,
// `openSettingsModal` (settings.js), and its first line awaits
// `ensureModule("settingsControls")`, before the window is unhidden, so there
// is no moment in which a control is on screen without its listener. Each
// statement is moved whole, with the comment that sat on it, in the order the
// files loaded, so two listeners on one element (`pref-export-dir` has two)
// still run in the order they did. No other file adds a listener to any of
// these elements (checked by listing every `addEventListener` on each id), and
// nothing in the boot files clicks or dispatches on them, so no listener is
// reached before the window is.
//
// Only element listeners are here. The handlers they call (`savePrefs`,
// `applyBackendChoice`, ...) stay in the boot files, because other code calls
// them too, and document-level listeners (Ctrl+S on Preferences, the
// `storage` event) stay because they run with the window closed.
//: The marker `openSettingsModal` looks for, so it only waits for this file once.
const SETTINGS_CONTROLS_READY = true;

// ---- from skills.js ----

$("small-model-mode")?.addEventListener("change", async () => {
  const select = $("small-model-mode");
  const status = $("small-model-mode-status");
  if (status) status.textContent = "Saving…";
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ small_model_mode: select.value }),
    });
  } catch (error) {
    if (status) {
      status.classList.add("error");
      status.textContent = error.message;
    }
    return;
  }
  if (!status) return;
  status.classList.remove("error");
  status.textContent =
    select.value === "on"
      ? "Every skill step is offered only the tool it names."
      : select.value === "off"
        ? "Every step is offered the skill's whole toolbox."
        : "Decided per run from the chat model's name.";
});

$("run-budget-tokens")?.addEventListener("change", saveRunBudget);

$("run-budget-seconds")?.addEventListener("change", saveRunBudget);

$("tool-filter")?.addEventListener("input", applyToolFilter);

// ---- from settings-panes.js ----

$("account-allow-lan")?.addEventListener("change", async (event) => {
  const box = event.target;
  const wanted = box.checked;
  box.checked = !wanted; // the server's answer decides what it shows
  const state = await lanSwitch(wanted);
  if (state) renderLanState(state);
});

//: **The switch, in one place** (INBOX 896): Settings and the status bar's
//: Other devices panel (lan-watch.js) both call this. On asks for the
//: password, off asks nothing; the answer is the new state, or null. Since
//: INBOX 900 the launcher's supervisor opens or closes the LAN port while
//: the app runs and the route waits for it, so `restart_required` is true
//: only for a server started without it (a `TESSELLATE_BIND` run).
async function lanSwitch(wanted) {
  try {
    if (!wanted) {
      const off = await apiJson("/auth/lan-access", {
        method: "POST",
        body: JSON.stringify({ enabled: false }),
      });
      if (off.restart_required) {
        toastAction("Restart to close the app to other devices now.", "Restart now", () =>
          restartMemoryMap({ confirm: false })
        );
      } else {
        toast("Only this computer can open the app now.");
      }
      return off;
    }
    let reply = null;
    const done = await askPasswordPrompt({
      title: "Allow other devices",
      message: "Enter your password to let devices on this network open the app. They will need it too.",
      submitLabel: "Allow",
      submit: async (password) => {
        reply = await apiJson("/auth/lan-access", {
          method: "POST",
          body: JSON.stringify({ enabled: true, current_password: password }),
          ownsAuthErrors: true,
        });
        return reply;
      },
    });
    if (!done || !reply) return null;
    if (reply.restart_required) {
      toastAction("Other devices can open the app after a restart.", "Restart now", () =>
        restartMemoryMap({ confirm: false })
      );
    } else if (reply.other_devices) {
      toast("Other devices on this network can open the app now, with your password.");
    } else {
      toast("On, and closed on this network until you trust it.");
    }
    return reply;
  } catch (error) {
    toast(error.message, true);
    return null;
  }
}

$("account-lan-restart")?.addEventListener("click", () => restartMemoryMap({ confirm: false }));

$("account-lan-download")?.addEventListener("click", () => {
  window.location.assign("/auth/lan-certificate.pem");
});

$("account-lan-regenerate")?.addEventListener("click", async () => {
  const ok = await confirmDialog(
    "Regenerate the certificate?\n\nEvery device that opened the app before warns once more, " +
      "with the new fingerprint to compare.",
    { confirmLabel: "Regenerate", danger: false }
  );
  if (!ok) return;
  try {
    renderLanState(await apiJson("/auth/lan-certificate", { method: "POST" }));
    toast("New certificate made. Compare its fingerprint on the other device.");
  } catch (error) {
    toast(error.message || "Couldn't make a new certificate.", true);
  }
});

$("privacy-refresh")?.addEventListener("click", () => renderPrivacyReceipt().catch(() => {}));

$("backup-retention")?.addEventListener("change", async (e) => {
  const status = $("backup-retention-status");
  const keep = Number(e.target.value);
  try {
    const result = await apiJson("/backups/retention", {
      method: "PUT",
      body: JSON.stringify({ keep }),
    });
    status.textContent = result.removed
      ? `Saved: removed ${result.removed} old backup${result.removed === 1 ? "" : "s"}.`
      : "Saved.";
    renderBackups();
  } catch (error) {
    status.textContent = error.message;
    renderBackupRetention(); // put the field back to what's actually saved
  }
});

// ---- from ai-tools.js ----

$("embedding-error-fix").addEventListener("click", runEmbeddingFallback);

// ---- from phone-shell.js ----

$("account-change").addEventListener("click", changePassword);

//: "Set up a PIN for this computer" / "Change PIN": the PIN typed twice
//: here, then the password on the lock card in prompt mode, like the
//: recovery key. The server checks the digits again and keeps the PIN in the
//: OS store (core/pinstore.py).
$("account-pin-set").addEventListener("click", async () => {
  const status = $("account-pin-status");
  status.classList.remove("error");
  const pin = $("account-pin-new").value;
  const fail = (text) => {
    status.classList.add("error");
    status.textContent = text;
  };
  if (!/^[0-9]{4,12}$/.test(pin)) return fail("A PIN is 4 to 12 digits.");
  if (pin !== $("account-pin-confirm").value) return fail("The two PINs don't match.");
  status.textContent = "";
  const done = await askPasswordPrompt({
    title: "Set up a PIN",
    message: "Enter your password to let a PIN unlock this computer.",
    submitLabel: "Set PIN",
    submit: (password) =>
      apiJson("/auth/pin", {
        method: "POST",
        body: JSON.stringify({ current_password: password, pin }),
        ownsAuthErrors: true,
      }),
  });
  if (!done) return;
  $("account-pin-new").value = "";
  $("account-pin-confirm").value = "";
  status.textContent = "PIN set for this computer.";
  renderAccount().catch(() => {});
});

//: "Forget PIN": the password too (removing it is a change to how this
//: computer opens the notebook).
$("account-pin-forget").addEventListener("click", async () => {
  const status = $("account-pin-status");
  status.classList.remove("error");
  status.textContent = "";
  const done = await askPasswordPrompt({
    title: "Forget PIN",
    message: "Enter your password to remove the PIN from this computer.",
    submitLabel: "Forget PIN",
    submit: (password) =>
      apiJson("/auth/pin/forget", {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      }),
  });
  if (!done) return;
  status.textContent = "PIN removed. The lock screen asks for your password.";
  renderAccount().catch(() => {});
});

//: Re-encrypt private notes (WORLD_CLASS_PLAN, Placed 2026-09-09, 261's
//: vault re-key, `POST /auth/rotate-vault-key`): a new key for every private
//: note. Like Change password it ends every other session and hands this tab
//: a fresh token, kept under the key `authToken()` reads.
//: The password is asked on the lock card in prompt mode (DESIGN.md's recipe
//: for one action's password; tests/test_lock_boundary.py), which carries the
//: throttle, the error line under the field and the purge.
$("account-rekey").addEventListener("click", async () => {
  const status = $("account-rekey-status");
  status.classList.remove("error");
  status.textContent = "";
  if (!(await confirmDialog("Give every private note a new key? Other open sessions are signed out.", { confirmLabel: "Re-encrypt" }))) return;
  let result = null;
  const done = await askPasswordPrompt({
    title: "Re-encrypt private notes",
    message: "Enter your current password to give every private note a new key.",
    submitLabel: "Re-encrypt",
    submit: async (password) => {
      // 401 here is "wrong password", said beside the field.
      result = await apiJson("/auth/rotate-vault-key", {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      });
      return result;
    },
  });
  if (!done || !result) return;
  prefs.set("token", result.token);
  const n = result.notes_reencrypted;
  status.textContent = `Done: ${n} private note${n === 1 ? "" : "s"} on a new key.`;
  //: Sealed by a reset without the recovery key: left as they were (INBOX 663).
  if (result.notes_sealed) status.textContent += ` ${result.notes_sealed} sealed by a password reset stay as they were.`;
  //: The old recovery key wrapped the old key, so it is dead; a notebook
  //: that had one is handed its successor, shown once (INBOX 663).
  if (result.recovery_key) {
    renderAccount().catch(() => {});
    showRecoveryKey(result.recovery_key, {
      title: "Your new recovery key",
      lead: "Re-encrypting replaced your recovery key: the old one no longer works. Save this one away from this computer. It is shown only this once.",
    });
  }
});

//: Settings, Account and security: "Make a recovery key" / "Replace it" (INBOX 663).
$("account-recovery-make").addEventListener("click", () => makeRecoveryKey());

//: "Ask for a password when the app opens". Off needs the current password,
//: asked through the lock screen's card; on needs nothing.
$("account-password-on-open").addEventListener("change", async (e) => {
  const box = e.target;
  const wanted = box.checked;
  box.checked = !wanted; // the server's answer decides what it shows
  try {
    if (wanted) {
      await apiJson("/auth/password-on-open", {
        method: "POST",
        body: JSON.stringify({ enabled: true }),
      });
      autoSessionOffered = false;
      box.checked = true;
      toast("The app asks for your password when it opens.");
    } else {
      const done = await askPasswordPrompt({
        title: "Stop asking for a password",
        message: "Enter your password to open the app on this computer without it.",
        submitLabel: "Turn off",
        submit: (password) =>
          apiJson("/auth/password-on-open", {
            method: "POST",
            body: JSON.stringify({ enabled: false, current_password: password }),
            ownsAuthErrors: true,
          }),
      });
      if (done) {
        box.checked = false;
        toast("This computer opens the app without a password. Private notes still ask.");
      }
    }
  } catch (error) {
    toast(error.message, true);
  }
  renderAccount().catch(() => {});
});

$("account-idle-ttl").addEventListener("change", (e) => {
  setPreference("session_idle_ttl_minutes", Number(e.target.value));
});

$("account-lock-all").addEventListener("click", async () => {
  //: With "Ask for a password when the app opens" off, this computer gets
  //: back in without one (only other devices and private notes need it).
  const back = autoSessionOffered
    ? "Other devices will need your password to get back in, and private notes will lock."
    : "You'll need your password to get back in.";
  if (!(await confirmDialog(`End every session, including this one? ${back}`))) return;
  await apiJson("/auth/lock-all", { method: "POST" }).catch(() => {});
  prefs.remove("token");
  location.reload();
});

$("local-only-ai").addEventListener("change", async (e) => {
  const on = e.target.checked;
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ local_only_ai: on }),
  }).catch((error) => toast(error.message, true));
  // Say it plainly on the way out of the safe state. Turning the lock ON is
  // unremarkable; turning it OFF is the moment worth naming, because the app's
  // central promise stops being enforced at exactly that click.
  toast(
    on
      ? "Atlas is locked to this machine."
      : "Off: Tessellate will now let you point Atlas at a server on the internet."
  );
  refreshModelStatus();
});

$("task-history-clear").addEventListener("click", async () => {
  await apiJson("/tasks/history/clear", { method: "POST" }).catch((e) =>
    toast(e.message, true)
  );
  renderTasks();
});

$("app-quit").addEventListener("click", quitApp);

// Web search saves on change rather than behind a Save button: there are two
// controls, and a checkbox that needs a second click elsewhere to take effect
// is the shape of "this control does nothing" that keeps getting reported.
$("pref-web-search").addEventListener("change", saveWebSearchSettings);

$("pref-searxng").addEventListener("change", saveWebSearchSettings);

$("pref-update-check").addEventListener("change", (e) =>
  setPreference("update_check_enabled", e.target.checked)
);

$("update-check-now").addEventListener("click", () => checkForUpdate());

$("update-apply-now").addEventListener("click", async () => {
  const button = $("update-apply-now");
  const status = $("update-check-status");
  button.disabled = true;
  const ok = await applyUpdateNow((state) => {
    if (status) {
      status.textContent = state.total_bytes
        ? `${state.step} (${Math.round((state.done_bytes / state.total_bytes) * 100)}%)`
        : state.step;
    }
  });
  if (!ok) {
    // Failed (offline, GitHub unreachable, no asset), never leave the
    // button stuck disabled over a real network error someone can just
    // retry once they're back online.
    button.disabled = false;
    toast((status && status.textContent) || "Couldn't apply the update.", true);
  }
});

$("pref-auto-update").addEventListener("change", (e) =>
  setPreference("auto_update_enabled", e.target.checked)
);

$("pref-update-channel-main").addEventListener("change", (e) =>
  setPreference("update_channel", e.target.checked ? "main" : "stable")
);

$("pref-update-beta").addEventListener("change", (e) =>
  setPreference("update_beta", e.target.checked)
);

// "Choose a specific version…" fetches the release list only on demand, 
// not on every Settings open, so leaving this tab open doesn't mean
// repeated GitHub calls, same restraint as the rest of this app's opt-in
// network features.
$("update-show-versions").addEventListener("click", async () => {
  const select = $("update-version-select");
  const installBtn = $("update-install-version");
  const status = $("update-version-status");
  status.textContent = "Loading releases…";
  const result = await apiJson("/update/releases", { silent: true }).catch(() => null);
  if (!result || !result.available) {
    select.classList.add("hidden");
    installBtn.classList.add("hidden");
    status.textContent =
      result?.reason === "channel_unavailable"
        ? "Not available while tracking the main branch."
        : result?.reason === "not_supported"
          ? "Only available for the packaged Windows app."
          : result?.reason === "disabled"
            ? "Enable 'Check GitHub for a newer version' first."
            : "Couldn't reach GitHub to list releases.";
    return;
  }
  select.innerHTML = "";
  for (const release of result.releases) {
    const option = document.createElement("option");
    option.value = release.tag;
    option.textContent = release.tag === `v${result.current}` || release.version === result.current
      ? `${release.name} (current)`
      : release.name;
    select.appendChild(option);
  }
  select.classList.toggle("hidden", result.releases.length === 0);
  installBtn.classList.toggle("hidden", result.releases.length === 0);
  status.textContent = result.releases.length ? "" : "No installable releases found.";
});

$("update-install-version").addEventListener("click", async () => {
  const select = $("update-version-select");
  const button = $("update-install-version");
  const status = $("update-version-status");
  const tag = select.value;
  if (!tag) return;
  if (
    !(await confirmDialog(
      `Download and install ${tag} now? Tessellate will close once the installer starts.`,
      { confirmLabel: "Install" }
    ))
  ) {
    return;
  }
  button.disabled = true;
  select.disabled = true;
  const ok = await applyUpdateNow((state) => {
    status.textContent = state.total_bytes
      ? `${state.step} (${Math.round((state.done_bytes / state.total_bytes) * 100)}%)`
      : state.step;
  }, tag);
  if (!ok) {
    button.disabled = false;
    select.disabled = false;
    toast(status.textContent || "Couldn't install that version.", true);
  }
});

// Not a plain setPreference: switching Dev view/User view is meant to take
// effect live, not just on the next launch (asked for directly: togglable
// from Settings as well as the tray). /system/console-mode saves the same
// preference and, in the desktop app on Windows, restarts the whole
// process into the new console mode right after responding.
$("pref-show-console").addEventListener("change", async (e) => {
  const checked = e.target.checked;
  try {
    const result = await apiJson("/system/console-mode", {
      method: "POST",
      body: JSON.stringify({ show_console_on_startup: checked }),
    });
    if (prefsCache) prefsCache.show_console_on_startup = result.show_console_on_startup;
    toast(
      result.restarting
        ? `Switching to ${checked ? "Dev" : "User"} view: restarting…`
        : `Will switch to ${checked ? "Dev" : "User"} view next launch.`
    );
  } catch (error) {
    e.target.checked = !checked; // the change didn't take: don't leave the switch lying
    toast(error.message || "Couldn't switch view.", true);
  }
});

//: Settings, Data: the same clearing with a word first, and a beat so the toast
//: is read before the page goes.
$("clear-app-cache")?.addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  await clearAppCache();
  toast("App cache cleared. Reloading.");
  setTimeout(() => location.reload(), 900);
});

$("about-force-reload")?.addEventListener("click", forceReloadApp);

//: `restartMemoryMap` (settings-panes.js): one restart mechanism shared with
//: the LAN switch's own "Restart now" toast action, rather than two copies
//: of "ask, restart, or say why not" drifting apart.
$("about-restart")?.addEventListener("click", () => restartMemoryMap());

// Takes effect on the next close, not on a restart, the handler reads the
// preference each time the window is closed rather than at launch, precisely
// so this switch is not a "restart to apply" one.
//: Read by the launcher on the next launch, before any window opens, so this
//: is not a "restart to apply" switch either: it decides what the *next*
//: double-click does.
$("pref-new-window-on-launch")?.addEventListener("change", (e) => {
  const checked = e.target.checked;
  setPreference("new_window_on_launch", checked);
  toast(
    checked
      ? "Launching again will open another window onto this notebook."
      : "Launching again will bring this window forward."
  );
});

$("pref-close-to-tray")?.addEventListener("change", (e) => {
  const checked = e.target.checked;
  setPreference("close_to_tray", checked);
  toast(
    checked
      ? "Closing the window will keep Tessellate in the tray."
      : "Closing the window will quit Tessellate."
  );
});

$("exports-refresh")?.addEventListener("click", renderExportsList);

$("open-exports-folder").addEventListener("click", async () => {
  try {
    const result = await apiJson("/files/open-exports-folder", { method: "POST" });
    toast(`Opened ${result.path}`);
  } catch (error) {
    toast(error.message || "Couldn't open the exports folder.", true);
  }
});

$("pref-export-dir").addEventListener("blur", saveExportSaveDir);

$("pref-export-dir").addEventListener("keydown", (event) => {
  if (event.key === "Enter") $("pref-export-dir").blur();
});

$("pref-export-dir-reset").addEventListener("click", () => {
  $("pref-export-dir").value = "";
  saveExportSaveDir();
});

// Each of these saves only its own key via `setPreference`, never
// `savePrefs`, which rebuilds and re-sends every field on the Preferences
// section's own form. That form may never have been rendered this session
// (a fresh page load landing straight on Background tasks, say), and its
// stale/default DOM values would silently overwrite whatever was really
// saved the moment any one of these checkboxes changed.
$("pref-autonomous-tasks").addEventListener("change", (e) => {
  toggleAutonomousPanel();
  setPreference("autonomous_tasks_enabled", e.target.checked);
});

$("pref-background-filing").addEventListener("change", (e) =>
  setPreference("background_filing", e.target.checked)
);

$("pref-semantic-auto-install").addEventListener("change", (e) =>
  setPreference("semantic_auto_install", e.target.checked)
);
$("pref-warm-search-model").addEventListener("change", (e) =>
  setPreference("warm_search_model_at_launch", e.target.checked)
);
$("pref-week-start").addEventListener("change", (e) => setPreference("week_start", e.target.value));
//: The voice's live sample (CHAT_PLAN decision 72): the same three lines
//: `composer_digest.sample` writes, kept equal by tests/test_answer_voice.py.
const VOICE_SAMPLES = {
  natural: "You have four notes about uni, 17 July to 4 August. Nothing yet on assessments or due dates. Remind you to ask the tutor on Thursday?",
  professional: "Your notebook holds four notes on uni, 17 July to 4 August. The notes do not yet cover assessments or due dates. Set a reminder to ask the tutor on Thursday?",
  playful: "Found four notes about uni, 17 July to 4 August. No word yet on assessments or due dates. Want a nudge to ask the tutor on Thursday?",
  plain: "Four notes about uni, 17 July to 4 August. Not in your notes: assessments or due dates. Remind you to ask the tutor on Thursday?",
};
function showVoiceSample(voice) {
  $("pref-voice-sample").textContent = VOICE_SAMPLES[voice] || VOICE_SAMPLES.natural;
}
$("pref-voice").addEventListener("change", (e) => {
  setPreference("composer_voice", e.target.value);
  showVoiceSample(e.target.value);
});
showVoiceSample($("pref-voice").value);
//: Decision 73: what an answer volunteers past itself.
$("pref-insight").addEventListener("change", (e) => setPreference("insight_level", e.target.value));

//: Clamped here as the backend clamps it (5 to 60), so a typed 100 saves
//: as 60 rather than being refused by the preferences schema.
$("pref-filing-wait").addEventListener("change", (e) => {
  const seconds = Math.max(5, Math.min(60, Math.round(Number(e.target.value) || 15)));
  e.target.value = seconds;
  setPreference("filing_wait_seconds", seconds);
});

$("pref-filing-wait-reset").addEventListener("click", () => {
  $("pref-filing-wait").value = 15;
  setPreference("filing_wait_seconds", 15);
});

//: Section 17 row 3: the filing style reaches the filing prompt.
$("pref-filing-style").addEventListener("change", (e) => setPreference("filing_style", e.target.value));

$("pref-ai-first-filing").addEventListener("change", (e) =>
  setPreference("ai_first_filing", e.target.checked)
);

//: WORLD_CLASS 23, decision 6: sensitive notes file by their words only when on.
$("pref-auto-file-sensitive").addEventListener("change", (e) =>
  setPreference("auto_file_sensitive", e.target.checked)
);

$("pref-auto-caption-images").addEventListener("change", (e) =>
  setPreference("auto_caption_images", e.target.checked)
);

$("pref-auto-read-image-text").addEventListener("change", (e) =>
  setPreference("auto_read_image_text", e.target.checked)
);

$("pref-auto-tag").addEventListener("change", (e) =>
  setPreference("auto_tag_enabled", e.target.checked)
);

$("pref-auto-link").addEventListener("change", (e) =>
  setPreference("auto_link_enabled", e.target.checked)
);

$("pref-auto-dedupe").addEventListener("change", (e) =>
  setPreference("auto_dedupe_enabled", e.target.checked)
);

$("pref-auto-stale-review").addEventListener("change", (e) =>
  setPreference("auto_stale_review_enabled", e.target.checked)
);

$("pref-auto-capture").addEventListener("change", (e) =>
  setPreference("auto_capture_enabled", e.target.checked)
);

$("pref-battery-mode").addEventListener("change", (e) => {
  setPreference("battery_efficient_mode", e.target.checked);
  $("power-saver-indicator")?.classList.toggle("hidden", !e.target.checked);
  //: `prefsCache` is what `batteryModeOn` reads, and `setPreference` writes
  //: the server before the cache, so the two pictures are restarted from
  //: here with the new value already in hand. Without this the setting took
  //: effect on the next load, which for a setting about power is the wrong
  //: half of "immediately".
  if (prefsCache) prefsCache.battery_efficient_mode = e.target.checked;
  startBgArt();
  renderDashboard();
});

$("pref-autonomous-interval").addEventListener("change", (e) =>
  setPreference("autonomous_tasks_interval_hours", Number(e.target.value) || 6)
);

$("pref-autonomous-model").addEventListener("change", (e) =>
  setPreference("autonomous_tasks_model", e.target.value.trim())
);

//: The switch changes which model background jobs run on, so the line under
//: the utility picker (INBOX 277) is re-read once the preference has landed
//: rather than left describing the old state until the next poll.
$("pref-smart-model-routing").addEventListener("change", async (e) => {
  await setPreference("smart_model_routing_enabled", e.target.checked);
  refreshModelStatus();
});

$("memory-add")?.addEventListener("click", addMemoryByHand);

$("memory-new")?.addEventListener("keydown", (e) => {
  // Enter saves. Typing a one-line rule and having to reach for the mouse is
  // the kind of small friction that stops people using a feature at all.
  if (e.key === "Enter") { e.preventDefault(); addMemoryByHand(); }
});

$("autonomous-review-clear")?.addEventListener("click", async () => {
  await api("/tasks/autonomous/last/clear", { method: "POST" }).catch(() => {});
  renderAutonomousReview();
});

$("autonomous-trigger").addEventListener("click", () => {
  api("/tasks/trigger-autonomous", { method: "POST" })
    .then(async (response) => {
      const body = await response.json().catch(() => ({}));
      toast(
        body.started === false
          ? "A pass is already running, the results will appear below."
          : "Optimization started. Its changes will be listed below when it finishes."
      );
      // The pass runs on a worker thread, so there is nothing to await. Look
      // again shortly rather than leaving the panel showing the previous run.
      setTimeout(renderAutonomousReview, 4000);
    })
    .catch((err) => toast(err.message, true));
});

//: The dictation size select is wired in settings-packages.js (voiceModelsWire), which paints it.
$("voice-skip-silence").addEventListener("change", (e) =>
  setPreference("voice_skip_silence", e.target.checked)
);
$("voice-language-select").addEventListener("change", (e) =>
  setPreference("voice_language", e.target.value)
);
//: On change, not on input: one save when the field is left, not one a key.
$("voice-vocabulary").addEventListener("change", (e) =>
  setPreference("voice_vocabulary", e.target.value.trim())
);

// ---- from wiring.js ----

$("dashboard-persona-select").addEventListener("change", async () => {
  const persona = $("dashboard-persona-select").value;
  //: Set before the save, not after it: the mark and the dashboard's face
  //: read it, and a second change while the first save was in flight was
  //: drawn from the old value (the owner: "when I changed the persona
  //: again, it didnt change again").
  if (prefsCache) prefsCache.dashboard_persona = persona;
  paintDashboardPersonaMark();
  paintDashEmblem();
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ dashboard_persona: persona }),
  }).catch(() => {});
  toast(persona ? `Dashboard greeting now speaks as ${persona}.` : "Dashboard greeting back to matching Chat.");
});

$("dashboard-greeting-regenerate")?.addEventListener("click", async () => {
  const btn = $("dashboard-greeting-regenerate");
  const status = $("dashboard-greeting-status");
  btn.disabled = true;
  //: The persona actually asked, not always Atlas (the owner: "I set the
  //: dashboard greeting to another persona, but when I hit regenerate, it
  //: said asking Atlas").
  const who = dashboardGreetingPersona();
  if (status) status.textContent = `Asking ${who}…`;
  const ok = await refreshAiGreeting(true).catch(() => false);
  btn.disabled = false;
  if (status) status.textContent = ok ? "New greeting set." : `Couldn't reach ${who}, kept the current one.`;
  setTimeout(() => { if (status) status.textContent = ""; }, 3000);
});

$("persona-add").addEventListener("click", addPersona);

$("skill-add").addEventListener("click", addSkill);

$("skill-cancel").addEventListener("click", stopEditingSkill);

$("skill-verify-expect").addEventListener("change", syncSkillVerifyRow);

$("settings-manage-categories").addEventListener("click", () => openManageCategories());

$("settings-manage-tags").addEventListener("click", () => openTagsSheet());

$("skill-export").addEventListener("click", () =>
  downloadJson("tessellate-skills.json", {
    skills: (prefsCache && prefsCache.skills) || [],
  })
);

$("skill-import").addEventListener("click", () =>
  pickJsonFile("skill-import-file", async (data) => {
    const merged = mergeNamedPrompts((prefsCache && prefsCache.skills) || [], data.skills);
    if (!merged) return toast("No skills found in that file.", "info");
    try {
      await saveSkillList(merged);
    } catch (error) {
      // The server validates imports the same way it validates the editor, 
      // a skill naming a tool that no longer exists is refused by name.
      return toast(error.message, true);
    }
    toast("Skills imported.");
  })
);

$("persona-export").addEventListener("click", () =>
  downloadJson("tessellate-personas.json", {
    personas: (prefsCache && prefsCache.personas) || [],
  })
);

$("persona-import").addEventListener("click", () =>
  pickJsonFile("persona-import-file", async (data) => {
    const merged = mergeNamedPrompts(
      (prefsCache && prefsCache.personas) || [],
      data.personas
    );
    if (!merged) return toast("No personas found in that file.", "info");
    await savePersonaList(merged);
    toast("Personas imported.");
  })
);

// Start the user's own engine with the app. See the markup for why this is the
// answer to "web search keeps disabling itself", it was the container going
// away, not the setting.
$("searxng-autostart").addEventListener("change", async (event) => {
  const on = event.target.checked;
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ searxng_autostart: on }),
  }).catch((error) => {
    toast(error.message, true);
    return prefsCache;
  });
  toast(
    on
      ? "SearXNG will start with Tessellate from now on."
      : "SearXNG will only start when you press Start."
  );
});

// ---- from settings-wiring.js ----

$("find-duplicates").addEventListener("click", findDuplicates);

$("duplicate-threshold").addEventListener("input", (e) => {
  $("duplicate-threshold-value").textContent = `${e.target.value}%`;
});

// From Help, go to the Settings section rather than swapping one dialog for
// another: "how do I change a shortcut?" should end somewhere you can find
// again, not in an overlay with no address.
$("about-shortcuts").addEventListener("click", () => showSettingsSection("shortcuts"));

$("shortcuts-reset-settings").addEventListener("click", resetShortcuts);

$("prefs-save").addEventListener("click", () => savePrefs());

$("pref-search-reset").addEventListener("click", () => {
  $("pref-search-min-sim").value = 0.25;
  $("pref-search-z-margin").value = 0.5;
  savePrefs();
});

$("searxng-reinstall").addEventListener("click", async () => {
  if (
    !(await confirmDialog(
      "Delete the SearXNG install and set it up again from scratch?\n\n" +
        "Your settings file is kept, only the downloaded copy and its " +
        "virtualenv are removed. Reinstalling takes a few minutes."
    ))
  )
    return;
  const status = $("searxng-host-status");
  status.classList.remove("error");
  setLabel(status, "ph:spin Removing the old install…");
  try {
    await apiJson("/websearch/searxng/reinstall", { method: "POST" });
    status.textContent = "Reinstalling: this takes a few minutes.";
    toast("Reinstalling SearXNG.");
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
  refreshSearxngHost();
});

$("searxng-start").addEventListener("click", async () => {
  const status = $("searxng-host-status");
  status.classList.remove("error");
  //: "Give it a minute" only before the first run (the owner, 2026-10-10:
  //: "the notification said it takes a while to pull the first image for
  //: searxng but ive already used multiple times").
  status.textContent = $("searxng-host-state").textContent === "Not installed"
    ? "Setting SearXNG up… the first run downloads it, so give it a minute."
    : "Starting SearXNG…";
  $("searxng-start").disabled = true;
  try {
    const body = await apiJson("/websearch/searxng/start", { method: "POST" });
    $("pref-searxng").value = body.url;
    prefsCache = await apiJson("/preferences").catch(() => prefsCache);
    status.textContent = `Running at ${body.url}: web search now uses it.`;
    toast("SearXNG is running.");
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
  refreshSearxngHost();
});

$("searxng-stop").addEventListener("click", async () => {
  const status = $("searxng-host-status");
  status.classList.remove("error");
  status.textContent = "Stopping…";
  try {
    await apiJson("/websearch/searxng/stop", { method: "POST" });
    $("pref-searxng").value = "";
    prefsCache = await apiJson("/preferences").catch(() => prefsCache);
    status.textContent = "Stopped: web search is back on DuckDuckGo.";
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
  refreshSearxngHost();
});

// Find a running SearXNG so the user never has to work out the wiring.
$("searxng-detect").addEventListener("click", async () => {
  const status = $("searxng-status");
  const typed = $("pref-searxng").value.trim();
  status.classList.remove("error");
  status.textContent = typed ? "Testing that URL…" : "Looking for a local SearXNG…";
  const query = typed ? `?url=${encodeURIComponent(typed)}` : "";
  const body = await apiJson(`/websearch/detect-searxng${query}`, {
    method: "POST",
  }).catch((error) => ({ found: false, detail: error.message }));
  if (body.found) {
    $("pref-searxng").value = body.url;
    prefsCache = await apiJson("/preferences").catch(() => prefsCache);
    status.textContent = `Connected to ${body.url}`;
  } else {
    status.classList.add("error");
    status.textContent = body.detail || "No SearXNG found.";
  }
});

$("profile-delete").addEventListener("click", deleteProfile);

$("export-json").addEventListener("click", () => downloadExport("json"));

$("export-csv").addEventListener("click", () => downloadExport("csv"));

$("chat-model-apply").addEventListener("click", applyChatModel);

//: Stop the model (WORLD_CLASS_PLAN 28.1 rule 5): the server stops every
//: answer, then asks the backend to unload it, and says what it did.
$("chat-model-stop").addEventListener("click", async () => {
  const result = await apiJson("/activity/model/stop", { method: "POST" }).catch((e) => ({ detail: e.message }));
  $("chat-model-note").textContent = result.detail || "";
});

//: `change`, not `input`: a number box fires `change` when the value is
//: committed (Enter, or focus leaving), which is the moment somebody means it.
//: `input` would PUT once per keystroke while they type 16384.
$("model-context-window")?.addEventListener("change", saveModelContextWindow);

$("llm-provider-apply").addEventListener("click", applyBackendChoice);

// Mark the fields dirty on any edit so the five-second status poll stops
// rewriting them underneath the person typing an address into them.
$("llm-base-url").addEventListener("input", () => (backendFieldsDirty = true));

$("llm-provider-select").addEventListener("change", () => {
  backendFieldsDirty = true;
  // Switching the dropdown should re-suggest that backend's usual address
  // rather than leave the other one's sitting there looking authoritative.
  const defaults = (modelStatus && modelStatus.provider_default_base_urls) || {};
  $("llm-base-url").value = "";
  $("llm-base-url").placeholder = defaults[$("llm-provider-select").value] || "Default address";
});

$("utility-model-apply").addEventListener("click", applyUtilityModel);

$("feature-models-reset").addEventListener("click", resetAllFeatureModels);

$("vision-model-apply").addEventListener("click", applyVisionModel);

$("ocr-model-apply")?.addEventListener("click", applyOcrModel);

$("embedding-apply").addEventListener("click", applyEmbeddingBackend);

$("utility-model-select").addEventListener(
  "change",
  () => ($("utility-model-select").dataset.userChosen = "1")
);

$("vision-model-select").addEventListener(
  "change",
  () => ($("vision-model-select").dataset.userChosen = "1")
);

$("settings-nav-back")?.addEventListener("click", () => stepTabHistory(-1));

$("settings-nav-forward")?.addEventListener("click", () => stepTabHistory(1));

// Two buttons, two behaviours, each the one its own words name. Settings →
// Help has "Replay the welcome" and Settings → About has "Take tour again";
// only the first was ever wired, so the About one was a button that did
// nothing at all (found by listing every id in index.html that no JS file and
// no stylesheet mentions), and wiring both to the same call then made the
// About one say "tour" and open the welcome card instead. They are not the
// same thing: the card is five slides about what Tessellate is, the tour is
// anchored cards on the real controls. So the welcome button opens the
// welcome and the tour button opens the tour.
$("show-guide-btn")?.addEventListener("click", () => {
  closeSettingsModal();
  openOnboarding();
});

$("about-take-tour")?.addEventListener("click", () => {
  if (typeof TOUR_ENABLED !== "undefined" && !TOUR_ENABLED) return;
  closeSettingsModal();
  // A frame later, for the same reason tour.js's own replay strip waits: the
  // first step's rectangle is measured against the page the modal was
  // covering, and a step measured while the modal is still up is dropped for
  // having nothing on screen to point at.
  requestAnimationFrame(() => {
    openTour("basics");
  });
});

$("export-md").addEventListener("click", () => downloadExport("markdown"));
//: The whole notebook as a folder (WORLD_CLASS 25b): notes, attachments,
//: documents and boards, which From a Tessellate folder reads back whole.
$("export-folder").addEventListener("click", async () => saveFile("tessellate-notebook.zip", await (await api("/export/folder")).blob()));

//: One step (INBOX 464 (18)): the button opens its picker and choosing
//: starts the import. The folder picker posts through the same function,
//: the only difference is which input it reads, so `importMarkdown` takes
//: the id rather than growing a second copy of the upload/report sequence.
$("import-md").addEventListener("click", () => $("import-md-files").click());

$("import-md-files").addEventListener("change", () => importMarkdown());

$("import-md-folder-btn").addEventListener("click", () => $("import-md-folder").click());

$("import-md-folder").addEventListener("change", () => importMarkdown("import-md-folder"));

$("import-dir")?.addEventListener("click", importDirectory);

$("export-backup-zip")?.addEventListener("click", () =>
  exportFullBackup().catch((error) => toast(error.message || "Couldn't save the backup.", true))
);

$("restore-bundle")?.addEventListener("click", () => $("restore-bundle-file").click());

$("restore-bundle-file")?.addEventListener("change", () => restoreFullBackup());

$("import-document").addEventListener("click", () => $("import-document-file").click());

$("import-document-file").addEventListener("change", () => importDocument());

$("backup-now").addEventListener("click", backupNow);

$("pref-hide-offline-notice").checked = aiOfflineNoticeHidden();
$("pref-hide-offline-notice").addEventListener("change", (event) => {
  try {
    prefs.set("hideOfflineNotice", event.target.checked ? "on" : "off");
  } catch {
    // Storage blocked: the switch holds for this session only.
  }
  syncModelGatedControls();
});

$("pref-single-keys").addEventListener("change", (event) => {
  try {
    prefs.set("singleKeys", event.target.checked ? "on" : "off");
  } catch {
    // Storage blocked: the switch holds for this session only.
  }
});

// ---- from spaces-find.js ----

$("template-add")?.addEventListener("click", addTemplate);

//: **Draft with Atlas** (INBOX 430): the body written from the name and the
//: line; pressed again it asks for a different take on what is in the box,
//: and the result is only ever put in the box, never saved, so Add is still
//: the person's decision.
$("template-draft")?.addEventListener("click", async () => {
  const name = $("template-name").value.trim();
  const status = $("template-status");
  status.classList.remove("error");
  if (!name) {
    status.classList.add("error");
    status.textContent = "Name it first, then Atlas can draft it.";
    $("template-name").focus();
    return;
  }
  const button = $("template-draft");
  button.disabled = true;
  status.textContent = "Drafting…";
  try {
    const result = await apiJson("/templates/draft", {
      method: "POST",
      body: JSON.stringify({ name, description: $("template-description").value.trim(), current: $("template-body").value }),
    });
    if (result.content) {
      $("template-body").value = result.content;
      status.textContent = "Drafted. Edit it, press again for another version, then save.";
    } else {
      status.classList.add("error");
      status.textContent = result.reason || "The model wrote nothing.";
    }
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

$("template-cancel")?.addEventListener("click", stopEditingTemplate);

// ---- from settings-wiring.js (search-boot-1005) ----
//
// `refreshSearxngHost` paints Settings' managed-SearXNG block and polls an
// install; its callers are this file's own buttons and `renderWebSearch`, a
// Settings pane's render, which runs after the window has opened and so after
// this file is in. app.js keeps a stand-in for it (`LAZY_ENTRY_POINTS`), so
// the pane's `refreshSearxngHost().catch(...)` is one call either way.

// Managed SearXNG: show what's there, and start/stop it on request.
async function refreshSearxngHost() {
  const badge = $("searxng-host-state");
  const start = $("searxng-start");
  const stop = $("searxng-stop");
  const info = await apiJson("/websearch/searxng/status").catch(() => null);
  if (!info) {
    badge.textContent = "Unknown";
    return;
  }
  // No usable backend: nothing we can drive, so say so plainly. "Docker is
  // installed but not started" is a different problem from "Docker isn't
  // installed", and the detail from the server distinguishes them.
  if (!info.backend) {
    badge.textContent = info.docker_installed ? "Docker not started" : "Not available";
    badge.title = info.detail || "";
    start.disabled = true;
    stop.disabled = true;
    $("searxng-host-status").classList.remove("error");
    $("searxng-host-status").textContent = info.detail || "";
    return;
  }
  // Which way it'll be run, so "a few minutes" isn't a surprise.
  $("searxng-backend").textContent =
    info.backend === "docker"
      ? "Docker is installed, so it runs as a container."
      : "Docker isn't installed, so it runs from its own virtualenv instead. " +
        "The first start takes a few minutes to download and install.";

  // An install is minutes long and runs in the background, poll it so the
  // step text keeps moving instead of the screen looking stuck.
  const bar = $("searxng-install-progress");
  if (info.installing) {
    const stage = info.install_stage || 1;
    const stages = info.install_stages || 5;
    badge.textContent = `Installing… ${stage}/${stages}`;
    badge.className = "chip";
    start.disabled = true;
    stop.disabled = true;
    $("searxng-host-status").classList.remove("error");
    $("searxng-host-status").textContent =
      info.install_step || "Setting SearXNG up…";
    // Reported: "the searxng reinstall doesn't have a progress bar so idk if
    // it has frozen or is working". The bar moves through the five stages;
    // the line under it is what pip is printing right now, which is what
    // actually distinguishes slow from stuck.
    bar.classList.remove("hidden");
    if (typeof info.install_progress === "number") {
      bar.removeAttribute("data-indeterminate");
      bar.value = info.install_progress;
    } else {
      bar.setAttribute("data-indeterminate", "1");
      bar.removeAttribute("value");
    }
    const said = (info.install_log || []).at(-1);
    $("searxng-install-line").textContent = said || "";
    clearTimeout(refreshSearxngHost.timer);
    refreshSearxngHost.timer = setTimeout(refreshSearxngHost, 2000);
    return;
  }
  bar.classList.add("hidden");
  $("searxng-install-line").textContent = "";
  if (info.install_error) {
    $("searxng-host-status").classList.add("error");
    $("searxng-host-status").textContent = info.install_error;
  } else if (info.detail) {
    // e.g. "Docker isn't running, so it'll be set up in a virtualenv", an
    // explanation of what will happen, not a failure.
    $("searxng-host-status").classList.remove("error");
    $("searxng-host-status").textContent = info.detail;
  } else {
    // Always say something current. This line used to keep whatever the last
    // poll wrote, so a finished install left "Installing SearXNG…" sitting
    // under a badge reading "Stopped", reported with a photo, and the
    // install had in fact completed.
    $("searxng-host-status").classList.remove("error");
    $("searxng-host-status").textContent =
      info.state === "stopped"
        ? "Installed and ready: press Start SearXNG."
        : info.state === "running"
          ? "Running."
          : "";
  }
  const running = info.state === "running" && info.responding;
  badge.textContent = running
    ? "Running"
    : info.state === "running"
      ? "Starting…"
      : info.state === "stopped"
        ? "Stopped"
        : "Not installed";
  badge.className = `chip item-label${running ? " is-ok" : ""}`;
  start.disabled = running;
  stop.disabled = info.state === "absent";
  setLabel(start, info.state === "absent" ? "ph:play Install & start" : "ph:play Start SearXNG");
  // Keep polling while it's starting, so "Starting…" can't stick forever with
  // no way to tell whether anything is still happening.
  if (info.state === "running" && !info.responding) {
    clearTimeout(refreshSearxngHost.timer);
    refreshSearxngHost.timer = setTimeout(refreshSearxngHost, 3000);
  }
  // What the instance itself printed. Only worth showing when it is not
  // running happily: when it is, its own log is just noise.
  const fold = $("searxng-output-fold");
  const said = (info.output || "").trim();
  fold.classList.toggle("hidden", !said || running);
  if (said) $("searxng-output").textContent = said;

  // The port, answered rather than suggested. Only three states matter, and
  // only one of them is the user's problem to go and solve.
  const port = info.port;
  const portLine = $("searxng-port");
  portLine.textContent = port ? port.detail : "";
  portLine.classList.toggle("error", Boolean(port && !port.free && !port.held_by_searxng));
}

// ---- from status.js (search-boot-1005): applyBackendChoice ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function applyBackendChoice() {
  const provider = $("llm-provider-select").value;
  const baseUrl = $("llm-base-url").value.trim();
  const note = $("llm-provider-status");
  setLabel(note, "ph:spin Connecting…");
  try {
    const body = await apiJson("/models/provider", {
      method: "POST",
      body: JSON.stringify({ provider, base_url: baseUrl }),
    });
    backendFieldsDirty = false;
    // The setting is saved either way, you set the address, then you start
    // the server: so this reports what was found rather than treating an
    // unreachable server as a rejected setting.
    setLabel(
      note,
      body.reachable
        ? `ph:plugs-connected Connected to ${body.base_url}: ${body.installed_models.length} model(s) available.`
        : `ph:plugs Saved, but nothing is answering at ${body.base_url} yet. Start the server and this will light up.`
    );
    // This app's headline promise is that notes stay on the machine. A backend
    // somewhere else is allowed, someone may want it, but never quietly, so
    // the warning is loud and stays until the address changes.
    const privacy = $("llm-privacy-warning");
    privacy.textContent = body.privacy_note || "";
    privacy.classList.toggle("hidden", !body.privacy_note);
    await refreshModelStatus();
  } catch (err) {
    note.textContent = err.message;
  }
}

// ---- from chat.js (search-boot-1005): saveModelContextWindow ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function saveModelContextWindow() {
  const box = $("model-context-window");
  if (!box || !modelContextModel) return;
  const raw = box.value.trim();
  const parsed = Number.parseInt(raw, 10);
  //: Anything that is not a positive number is auto, including the empty box
  //: this control is cleared with. `null` rather than deleting the key, so the
  //: PUT says "this model is on auto" rather than saying nothing about it: the
  //: whole map is replaced on save, and an omitted model would be indistinct
  //: from one that was never set, which is the same thing here but would stop
  //: being so the moment anything else wrote to the map.
  const value = raw === "" || !Number.isFinite(parsed) || parsed <= 0 ? null : parsed;
  const windows = { ...((prefsCache && prefsCache.model_context_windows) || {}) };
  windows[modelContextModel] = value;
  try {
    await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ model_context_windows: windows }),
    });
    if (prefsCache) prefsCache.model_context_windows = windows;
    //: Re-read the spec rather than trusting the number just typed: the
    //: backend floors a window below its own minimum, so a 40 typed here comes
    //: back as 4,096, and the note has to say what will actually run.
    renderModelSpec(modelContextModel);
    toast(value ? `${modelContextModel} will run at ${value.toLocaleString()} tokens.` : `${modelContextModel} is back on auto.`);
  } catch (e) {
    toast(e.message || "Couldn't save that window.", true);
  }
}

// ---- from sheets-selects.js (search-boot-1005): addPersona ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function addPersona() {
  const name = $("persona-name").value.trim();
  const promptText = $("persona-prompt").value.trim();
  const status = $("persona-status");
  if (!name || !promptText) {
    status.textContent = "Both a name and a prompt are needed.";
    return;
  }
  const custom = ((prefsCache && prefsCache.personas) || []).filter(
    (p) => p.name !== name
  );
  custom.push({ name, prompt: promptText });
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ personas: custom }),
  });
  $("persona-name").value = "";
  $("persona-prompt").value = "";
  status.textContent = `Added “${name}”.`;
  await renderPersonas();
  personaOptions();
}

// ---- from ai-tools.js (search-boot-1005): runEmbeddingFallback, resetAllFeatureModels, applyChatModel, applyOcrModel, applyUtilityModel, applyVisionModel ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

// One click for the sentence #embedding-error already prints: download
// nomic-embed-text (skipped if it's already installed), then switch the
// search engine to it and re-index. Self-contained polling rather than
// riding the shared `modelStatus` refresh loop: that loop backs off to a
// slow cadence when nothing else is running, which would make a fresh
// download look stalled for up to 20s at a time; this polls every second
// for exactly as long as this one operation is in flight.
async function runEmbeddingFallback() {
  if (embeddingFallbackRunning) return;
  embeddingFallbackRunning = true;
  const button = $("embedding-error-fix");
  const status = $("embedding-error-fix-status");
  button.disabled = true;
  const setStatus = (text) => {
    status.textContent = text;
  };
  try {
    const already = (modelStatus?.installed_models || []).some(
      (m) => m.name === EMBEDDING_FALLBACK_MODEL || m.name.split(":")[0] === EMBEDDING_FALLBACK_MODEL
    );
    if (!already) {
      setStatus(`Downloading ${EMBEDDING_FALLBACK_MODEL}…`);
      try {
        await api("/models/pull", {
          method: "POST",
          body: JSON.stringify({ name: EMBEDDING_FALLBACK_MODEL }),
        });
      } catch (error) {
        // 409 "Already downloading" means someone else (or a previous
        // click) already started this exact pull, fall through to the
        // same wait loop rather than treating it as a failure.
        if (!/already downloading/i.test(error.message || "")) throw error;
      }
      // Poll until the pull leaves "running", succeeded (it drops out of
      // `pulls` once installed) or failed (status "error").
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const poll = await apiJson("/models/status", { silent: true }).catch(() => null);
        if (!poll) continue; // a transient miss mid-download isn't a failure
        const pull = (poll.pulls || {})[EMBEDDING_FALLBACK_MODEL];
        if (pull && pull.status === "error") {
          throw new Error(pull.error || `Couldn't download ${EMBEDDING_FALLBACK_MODEL}.`);
        }
        const nowInstalled = (poll.installed_models || []).some(
          (m) => m.name === EMBEDDING_FALLBACK_MODEL || m.name.split(":")[0] === EMBEDDING_FALLBACK_MODEL
        );
        if (nowInstalled || !pull) break;
        setStatus(
          pull.total
            ? `Downloading ${EMBEDDING_FALLBACK_MODEL}… ${Math.round((pull.done / pull.total) * 100)}%`
            : `Downloading ${EMBEDDING_FALLBACK_MODEL}…`
        );
      }
    }
    setStatus("Switching search engine and re-indexing…");
    await api("/models/embedding-backend", {
      method: "POST",
      body: JSON.stringify({ backend: "ollama", model: EMBEDDING_FALLBACK_MODEL }),
    });
    toast(`Switched to ${EMBEDDING_FALLBACK_MODEL}: re-indexing your notes now.`);
    setStatus("");
  } catch (error) {
    toast(error.message || `Couldn't switch to ${EMBEDDING_FALLBACK_MODEL}.`, true);
    setStatus("");
  } finally {
    embeddingFallbackRunning = false;
    button.disabled = false;
    refreshModelStatus();
  }
}

async function resetAllFeatureModels() {
  try {
    const body = await api("/models/feature-models/reset", { method: "POST" });
    const cleared = Number(body.cleared || 0);
    toast(
      cleared === 0
        ? "Nothing to reset: every feature was already on its default model."
        : cleared === 1
          ? "One feature is back on its default model."
          : `${cleared} features are back on their default models.`
    );
    refreshModelStatus();
  } catch (error) {
    toast(error.message || "Couldn't reset those models.", true);
  }
}

async function applyChatModel() {
  const select = $("chat-model-select");
  const note = $("chat-model-note");
  try {
    await api("/models/chat-model", {
      method: "POST",
      body: JSON.stringify({ name: select.value }),
    });
    delete select.dataset.userChosen; // applied: polling may reflect it now
    note.textContent = `${aiNameNow()}, running ${select.value}: switched instantly, no re-index needed.`;
    refreshModelStatus();
  } catch (error) {
    note.textContent = error.message;
  }
}

async function applyOcrModel() {
  const select = $("ocr-model-select");
  try {
    await api("/models/ocr-model", {
      method: "POST",
      body: JSON.stringify({ name: select.value }),
    });
    delete select.dataset.userChosen;
    toast(
      select.value
        ? `Text will be read with ${select.value}.`
        : "Reading text is automatic again."
    );
    refreshModelStatus();
  } catch (error) {
    toast(error.message || "Couldn't set that model.", true);
  }
}

async function applyUtilityModel() {
  const select = $("utility-model-select");
  try {
    await api("/models/utility-model", {
      method: "POST",
      body: JSON.stringify({ name: select.value }),
    });
    delete select.dataset.userChosen;
    toast(
      select.value
        ? `Background jobs now use ${select.value}.`
        : "Background jobs now use the chat model."
    );
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
  }
}

async function applyVisionModel() {
  const select = $("vision-model-select");
  try {
    await api("/models/vision-model", {
      method: "POST",
      body: JSON.stringify({ name: select.value }),
    });
    delete select.dataset.userChosen;
    toast(
      select.value
        ? `Images now go to ${select.value}.`
        : "Images now use auto-detect."
    );
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
  }
}

// ---- from spaces-find.js (search-boot-1005): addTemplate ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function addTemplate() {
  const name = $("template-name").value.trim();
  const body = $("template-body").value.trim();
  const status = $("template-status");
  status.classList.remove("error");
  if (!name || !body) {
    status.classList.add("error");
    status.textContent = "Both a name and a template body are needed.";
    return;
  }
  // Only the entry being edited is dropped before the push, a genuine
  // rename (or, for a built-in, the previous edit of it). A name that
  // instead collides with a DIFFERENT saved template is left in place and
  // the save is rejected server-side (§_validated_templates) rather than
  // silently replacing someone else's saved text the way a same-named skill
  // would. A new template given a built-in's name becomes that built-in's
  // edit, which is what the name means now.
  const custom = customTemplates().filter((t) => t.name !== editingTemplateName);
  custom.push({
    name,
    description: $("template-description").value.trim(),
    content: body,
  });
  const wasEditing = editingTemplateName;
  try {
    await saveTemplateList(custom);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    return;
  }
  stopEditingTemplate();
  status.textContent = wasEditing ? `Updated “${name}”.` : `Saved “${name}”.`;
}

// ---- from skills.js (search-boot-1005): saveRunBudget ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function saveRunBudget() {
  const tokens = $("run-budget-tokens");
  const seconds = $("run-budget-seconds");
  const status = $("run-budget-status");
  if (!tokens || !seconds) return;
  //: Clamped here as well as by the server: a negative number in a number
  //: input is one keystroke away, and the failure it causes (a budget that is
  //: exceeded before the first round) would look like the feature being
  //: broken rather than like a typo.
  const body = {
    run_budget_tokens: Math.max(0, Math.round(Number(tokens.value) || 0)),
    run_budget_seconds: Math.max(0, Math.round(Number(seconds.value) || 0)),
  };
  if (status) status.textContent = "Saving…";
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify(body),
    });
  } catch (error) {
    if (status) {
      status.classList.add("error");
      status.textContent = error.message;
    }
    return;
  }
  if (!status) return;
  status.classList.remove("error");
  const parts = [];
  parts.push(body.run_budget_tokens ? `${body.run_budget_tokens} tokens` : "no token limit");
  parts.push(body.run_budget_seconds ? `${body.run_budget_seconds}s` : "no time limit");
  status.textContent = `A run may spend ${parts.join(" and ")}.`;
}

// ---- from settings-panes.js (search-boot-1005): saveWebSearchSettings, restartMemoryMap ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function saveWebSearchSettings() {
  const status = $("search-provider-status");
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({
        web_search_enabled: $("pref-web-search").checked,
        searxng_url: $("pref-searxng").value.trim(),
      }),
    });
    // Reported: "the web search button is visibly disabled in the chat
    // dock instead of inactive when I have web search enabled in the
    // settings", the chat dock's own click handler keeps this Settings
    // checkbox in sync going the other way, but this save handler never
    // synced the chat dock button back, so it stayed on whatever look it
    // had at page load until clicked directly or the page reloaded.
    renderWebSearchToggle();
    status.classList.remove("error");
    status.textContent = "Saved.";
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

//: **Shared with the About panel's own "Restart Tessellate" button**
//: (`#about-restart`, phone-shell.js): one restart mechanism, `/system/restart`
//: (Windows desktop only; everywhere else it answers `restarting: false` and
//: this says so), so the LAN switch's own restart offer below reuses it
//: rather than re-implementing "ask, restart, or say why not" a second time.
//: `confirm` is skipped for a `toastAction` call: the person already made an
//: explicit choice by pressing that button's own label, the same reasoning
//: every other `toastAction` in the app (Undo, and the rest) already follows.
async function restartMemoryMap({ confirm = true } = {}) {
  if (
    confirm &&
    !(await confirmDialog(
      "Restart Tessellate?\n\nThe app closes and reopens. Your notes are already saved."
    ))
  ) {
    return;
  }
  try {
    const result = await apiJson("/system/restart", { method: "POST" });
    if (result.restarting) {
      toast("Restarting…");
      waitForRestart();
    } else {
      toast("Restart isn't available in this build, close and reopen Tessellate by hand.", "info");
    }
  } catch (error) {
    toast(error.message || "Couldn't restart.", true);
  }
}

//: The page waits out a restart and reloads onto the new copy (INBOX 872):
//: in a browser tab nothing else would, and the old page sat on a dead
//: server. It must see the server go away first, so a refused restart
//: (the old copy still answering after 20 s) is said rather than reloaded.
async function waitForRestart() {
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const started = Date.now();
  let wentAway = false;
  while (Date.now() - started < 90000) {
    await pause(600);
    try {
      await apiJson("/auth/status", { silent: true });
      if (wentAway) {
        window.location.reload();
        return;
      }
      if (Date.now() - started > 20000) break;
    } catch {
      wentAway = true;
    }
  }
  toast(wentAway ? "The app hasn't come back yet. Start it again by hand." : "The app didn't restart. Close and reopen it by hand.", true, { action: ["Try again", () => restartMemoryMap({ confirm: false })] });
}

// ---- from wiring.js (search-boot-1005): findDuplicates ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function findDuplicates() {
  const status = $("duplicate-status");
  const box = $("duplicate-groups");
  const threshold = Number($("duplicate-threshold").value) / 100;
  status.classList.remove("error");
  status.textContent = "Comparing your notes…";
  box.replaceChildren();
  try {
    const body = await apiJson(`/duplicates?threshold=${threshold}`);
    renderDuplicateGroups(body.groups);
    status.textContent = body.groups.length
      ? `${body.groups.length} group${body.groups.length === 1 ? "" : "s"} of similar notes.`
      : "No duplicates at that similarity, try lowering the slider.";
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

// ---- from phone-shell.js (search-boot-1005): saveExportSaveDir, addMemoryByHand ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

// Saved on blur/Enter, not on every keystroke, a half-typed path is not a
// preference worth validating server-side yet. Reverts the field on a
// rejected value rather than leaving a bad path sitting there looking saved.
async function saveExportSaveDir() {
  const input = $("pref-export-dir");
  const value = input.value.trim();
  if (value === (prefsCache?.export_save_dir || "")) return; // nothing changed
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ export_save_dir: value }),
    });
    input.value = prefsCache.export_save_dir;
    toast(value ? `Exports will now be saved to ${prefsCache.export_save_dir}` : "Exports will save to the default location.");
  } catch (error) {
    input.value = prefsCache?.export_save_dir || "";
    toast(error.message || "Couldn't save that folder.", true);
  }
}

async function addMemoryByHand() {
  const input = $("memory-new");
  const status = $("memory-status");
  const text = (input?.value || "").trim();
  status.classList.add("hidden");
  status.classList.remove("error");
  if (!text) return;
  try {
    const made = await apiJson("/memory", { method: "POST", body: JSON.stringify({ content: text }) });
    if (made?.id != null) {
      let liveId = made.id;
      pushUndo(
        "Added a memory",
        async () => {
          await api(`/memory/${liveId}`, { method: "DELETE" });
          renderMemorySettings();
        },
        async () => {
          const again = await apiJson("/memory", { method: "POST", body: JSON.stringify({ content: text }) });
          liveId = again?.id ?? liveId;
          renderMemorySettings();
        }
      );
    }
    input.value = "";
    renderMemorySettings();
  } catch (error) {
    status.textContent = error.message || "Couldn't save that.";
    status.classList.remove("hidden");
    status.classList.add("error");
  }
}

// ---- from wiring.js (search-boot-1005): renderDuplicateGroups ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

function renderDuplicateGroups(groups) {
  const box = $("duplicate-groups");
  box.replaceChildren();
  for (const group of groups) {
    const card = document.createElement("div");
    card.className = "duplicate-group";

    const head = document.createElement("p");
    head.className = "muted";
    head.textContent = `${group.entries.length} notes · ${Math.round(group.similarity * 100)}% alike`;
    card.appendChild(head);

    // Every note ticked by default: the whole point is merging the group.
    const chosen = new Set(group.entries.map((e) => e.id));
    for (const entry of group.entries) {
      const label = document.createElement("label");
      label.className = "duplicate-note";
      const box2 = document.createElement("input");
      box2.type = "checkbox";
      box2.checked = true;
      box2.addEventListener("change", () => {
        if (box2.checked) chosen.add(entry.id);
        else chosen.delete(entry.id);
        merge.disabled = chosen.size < 2;
      });
      const text = document.createElement("span");
      text.textContent = clipText(notePreviewText(entry.content), 160);
      label.append(box2, text);
      card.appendChild(label);
    }

    const row = document.createElement("div");
    row.className = "row";
    const merge = smallButton("ph:arrows-merge Merge these", "Combine them into one note", async () => {
      await mergeDuplicateGroup([...chosen], card);
    }, false);
    const useAi = document.createElement("label");
    useAi.className = "muted";
    const aiBox = document.createElement("input");
    aiBox.type = "checkbox";
    aiBox.id = `merge-ai-${group.entries[0].id}`;
    // Only offer the AI when it can actually do the job.
    const aiReady = !modelStatus || modelStatus.ollama_running !== false;
    aiBox.checked = aiReady;
    aiBox.disabled = !aiReady;
    useAi.append(aiBox, document.createTextNode(
      aiReady ? " let Atlas write the merged note" : " Atlas is not running: notes will be joined"
    ));
    card.dataset.aiBoxId = aiBox.id;
    row.append(merge, useAi);
    card.appendChild(row);
    box.appendChild(card);
  }
}

// ---- from wiring.js (search-boot-1005): mergeDuplicateGroup ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

async function mergeDuplicateGroup(ids, card) {
  if (ids.length < 2) return;
  const aiBox = document.getElementById(card.dataset.aiBoxId);
  const useAi = !!(aiBox && aiBox.checked);
  const status = $("duplicate-status");

  // Show what it will say BEFORE anything changes, merging is the one action
  // here that can quietly lose writing, so it shouldn't be a leap of faith.
  status.classList.remove("error");
  status.textContent = "Working out the merged note…";
  let preview;
  try {
    preview = await apiJson("/duplicates/preview", {
      method: "POST",
      body: JSON.stringify({ ids, use_ai: useAi }),
    });
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    return;
  }
  status.textContent = "";

  const ok = (await confirmDialog(
    `Merge ${ids.length} notes into one?\n\n` +
      `The merged note will read:\n\n${preview.merged.slice(0, 400)}` +
      `${preview.merged.length > 400 ? "…" : ""}\n\n` +
      `The other ${ids.length - 1} go to the bin, so this is undoable.`
  ));
  if (!ok) return;

  //: The kept note's words and tags as they were, for Undo (INBOX 537): the
  //: others went to the bin, so Undo also brings them back.
  const keeper = allEntries.find((e) => e.id === ids[0]);
  try {
    const result = await apiJson("/duplicates/merge", {
      method: "POST",
      body: JSON.stringify({ ids, use_ai: useAi }),
    });
    card.remove();
    const binned = result.binned_ids || [];
    const swap = (back) => async () => {
      if (keeper) await api(`/entries/${result.id}`, { method: "PUT", body: JSON.stringify(back ? { content: keeper.content, tags: keeper.tags } : { content: result.content }) });
      for (const id of binned) await api(back ? `/entries/${id}/restore` : `/entries/${id}`, { method: back ? "POST" : "DELETE" });
      await refreshEntries([result.id, ...binned]);
    };
    const action = pushUndo(`Merged ${result.merged_count} notes`, swap(true), swap(false));
    toastAction(`Merged ${result.merged_count} notes${result.used_ai ? " with Atlas" : ""}.`, "Undo", async () => {
      settleUndoFromToast(action);
      await swap(true)();
    });
    await refreshEntries([result.id, ...binned]);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

// Moved from settings-panes.js (boot gzip): every caller is in this file.
//: Restoring replaces the notebook and ends every session, so the page is
//: reloaded afterwards: the lock screen is the honest next thing to see.
async function restoreFullBackup() {
  const input = $("restore-bundle-file");
  const status = $("restore-bundle-status");
  const file = input.files[0];
  if (!file) return;
  input.value = "";
  const sealed = /\.mmenc$/i.test(file.name);
  const password = $("restore-bundle-password").value;
  if (sealed && !password) {
    status.textContent = "That file is sealed. Enter its password, then choose it again.";
    return;
  }
  if (
    !(await confirmDialog(
      "Restore this backup? Your current notebook is snapshotted first, then replaced by the one in the file."
    ))
  )
    return;
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("password", password);
  setLabel(status, "ph:spin Restoring…");
  try {
    const response = await api.upload("/backups/bundle/restore", form);
    const result = await response.json();
    $("restore-bundle-password").value = "";
    status.textContent = `Restored, with ${result.files} attached file${result.files === 1 ? "" : "s"}. Reloading to unlock it.`;
    setTimeout(() => location.reload(), 1200);
  } catch (error) {
    status.textContent = error.message || "The restore did not work. Nothing was changed.";
  }
}

// Moved from settings-panes.js (boot gzip): every caller is in this file.
//: The full backup is a POST, not `/export/backup`'s GET, so a password goes
//: in the body and not in an address that lands in a log. With one the file is
//: a sealed .mmenc (`core/backup_bundle.py`); without, the same zip as before.
async function exportFullBackup() {
  const field = $("export-backup-password");
  const password = field ? field.value : "";
  const response = await api("/backups/bundle", {
    method: "POST",
    body: JSON.stringify({ password: password || null }),
  });
  await saveFile(password ? "tessellate-backup.mmenc" : "tessellate-backup.zip", await response.blob());
  if (field) field.value = "";
}

// Moved from settings-panes.js (boot gzip): every caller is in this file.
async function deleteProfile() {
  if (!(await confirmDialog("Delete your profile text? Atlas will stop personalising answers."))) return;
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ user_profile: "", profile_enabled: false }),
  });
  await renderPrefs();
  toast("Profile data deleted.");
}

// Moved from skills.js (boot gzip): every caller is in this file.
// Merge imported {name, prompt} items over existing ones (imports win
// on a name clash), used by both skills and personas.
function mergeNamedPrompts(existing, imported) {
  const cleaned = (imported || []).filter(
    (item) => item && typeof item.name === "string" && typeof item.prompt === "string"
  );
  if (!cleaned.length) return null;
  const names = new Set(cleaned.map((item) => item.name));
  return [...existing.filter((item) => !names.has(item.name)), ...cleaned];
}

// Moved from settings.js (boot gzip): a listener inside the Settings window.
//: **A pane's "New ..." in its bar** (design-rows-1005): Personas, Skills and
//: Templates carry it in their dock, `data-opens` naming the form's first
//: field and `data-cancel` the form's Cancel edit. One listener for all
//: three: it ends an edit in progress (a New that filled the form with the
//: skill being edited would be a second Edit), opens the form's fold, brings
//: the form into view under the sticky dock, and puts the cursor in Name.
document.getElementById("settings-modal")?.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-opens]");
  if (!opener) return;
  const field = document.getElementById(opener.dataset.opens);
  if (!field) return;
  const cancel = opener.dataset.cancel && document.getElementById(opener.dataset.cancel);
  if (cancel && !cancel.classList.contains("hidden")) cancel.click();
  const fold = field.closest("details");
  if (fold) fold.open = true;
  //: The field, not its group: on a phone the Skills form is taller than
  //: the window, and centring the group left Name under the sticky dock.
  field.scrollIntoView({ block: "center" });
  field.focus({ preventScroll: true });
});

// Moved from skills.js (boot gzip): Settings, Skills' Add is its only caller.
async function addSkill() {
  const name = $("skill-name").value.trim();
  const promptText = $("skill-prompt").value.trim();
  const status = $("skill-status");
  status.classList.remove("error");
  if (!name || !promptText) {
    status.textContent = "Both a name and a request are needed.";
    return;
  }
  // Drop any skill with the new name AND (when editing) the one being edited,
  // so saving updates in place and even a rename doesn't leave a duplicate.
  const custom = customSkills().filter(
    (s) => s.name !== name && s.name !== editingSkillName
  );
  const verify = chosenSkillVerify();
  custom.push({
    name,
    prompt: promptText,
    description: $("skill-description").value.trim(),
    steps: textToSteps($("skill-steps").value),
    tools: chosenSkillTools(),
    inputs: textToInputs($("skill-inputs").value),
    ...(verify ? { verify } : {}),
  });
  const wasEditing = editingSkillName;
  try {
    await saveSkillList(custom);
  } catch (error) {
    // The server validates both ways in, so this is the same message the AI
    // would get for the same mistake, an undeclared {{placeholder}}, say.
    status.classList.add("error");
    status.textContent = error.message;
    return;
  }
  stopEditingSkill();
  status.textContent = wasEditing ? `Updated “${name}”.` : `Saved “${name}”.`;
}

//: The block the editor sends, or null. Built here rather than assembled in
//: `addSkill` so the shape has one home: the server validates it again
//: (`skills.verify_spec`) and its complaint is what the status line shows.
function chosenSkillVerify() {
  const tool = $("skill-verify-tool").value;
  if (!tool) return null;
  const predicate = $("skill-verify-expect").value;
  const block = {
    tool,
    expect: {
      [predicate]: predicate === "unchanged" ? true : Number($("skill-verify-value").value) || 0,
    },
  };
  if ($("skill-verify-untagged").checked) {
    block.args = { untagged: true };
    //: `count_notes` answers a filtered question in `count` and an unfiltered
    //: one in `total`, and the verifier tries `total` first, so a filtered
    //: block that did not name its field would read the number it is
    //: filtering away from.
    block.field = "count";
  }
  return block;
}

function chosenSkillTools() {
  const box = $("skill-tool-list");
  if (!box) return [];
  return [...box.querySelectorAll("input:checked")].map((input) => input.value);
}

// ---- from spaces-find.js: the status bar's slots, drawn only in Settings ----

//: What shows in the status bar.
//
// Asked for: "allow more stuff to be added and removed to the bottom status
// bar?? maybe??" The bar is a permanent strip across the bottom of every
// screen, so what belongs on it is taste rather than correctness.
//
// **Stored as what is hidden, not what is shown**, and that choice is the
// whole of the forward-compatibility story: a slot added in a later version
// appears by default for everyone, instead of being invisible to every user
// who ever opened this screen and saved a list that could not have named it.
//
// Only the slots that are *always* there are listed. The offline badge, the
// power-saver badge and the running-job slot appear when there is something
// to say and hide themselves again, and hiding a warning you asked for is a
// different kind of setting from tidying a permanent one away.
const STATUS_SLOTS = [
  { key: "ai", label: "AI status", hint: "The dot and emblem saying what the local model is doing" },
  { key: "notes", label: "Note count", hint: "How many notes you have, as a link to them" },
  { key: "reminders", label: "Reminders", hint: "Open and due reminders" },
  { key: "nav", label: "Back and forward", hint: "Move between the pages you have visited" },
  { key: "undo", label: "Undo and redo", hint: "The same undo the rest of the app uses" },
  { key: "command", label: "Command palette hint", hint: "The Ctrl-K reminder" },
  {
    key: "agent",
    label: "Ask the agent",
    hint: "Open the agent over whatever you are doing, from any tab",
  },
  //: Added with INBOX 207, when the Guide left the header cluster. A slot
  //: added later appears by default for everyone, which is what storing the
  //: hidden set rather than the shown one buys (the note above).
  {
    key: "guide",
    label: "Guide",
    hint: "Ask the guide how this app works, from any tab",
  },
  //: Added with INBOX 270. A slot added later appears by default for
  //: everyone, which is what storing the hidden set rather than the shown one
  //: buys (the note above).
  {
    key: "find",
    label: "Find anything",
    hint: "Search your notes, documents, files and the app itself",
  },
  //: INBOX 896. Shown on this computer only; another device never sees it.
  {
    key: "lan",
    label: "Other devices",
    hint: "Whether a phone on this network can open the app: open, closed or off",
  },
];

function renderStatusBarSettings() {
  const box = $("status-bar-items");
  if (!box) return;
  const hidden = hiddenStatusSlots();
  // The clock's own row lives inside this same container now (index.html): 
  // moved there so it wraps as one more compact chip alongside STATUS_SLOTS'
  // instead of stretching full-width as a lone sibling after the flex box.
  // `replaceChildren()` below is only ever meant to clear the *generated*
  // rows this loop is about to rebuild; without pulling the static clock
  // label out first, it would delete that markup along with them on every
  // call and silently orphan `#status-bar-clock-toggle` for the rest of
  // this function.
  const clockLabel = document.getElementById("status-bar-clock-toggle")?.closest("label");
  box.replaceChildren();
  for (const slot of STATUS_SLOTS) {
    const label = document.createElement("label");
    label.className = "checkbox-label status-bar-item";
    label.title = slot.hint;
    const box_ = document.createElement("input");
    box_.type = "checkbox";
    box_.checked = !hidden.has(slot.key);
    box_.addEventListener("change", () => {
      const next = hiddenStatusSlots();
      if (box_.checked) next.delete(slot.key);
      else next.add(slot.key);
      const list = [...next];
      if (prefsCache) prefsCache.status_bar_hidden = list;
      applyStatusBarSlots();
      setPreference("status_bar_hidden", list);
    });
    const text = document.createElement("span");
    text.textContent = slot.label;
    label.append(box_, text);
    box.appendChild(label);
  }
  // Put the clock's row back: see the comment above `clockLabel`'s
  // declaration. Appended last, so it reads as the odd one out it actually
  // is (off by default) without visually separating from its siblings.
  if (clockLabel) box.appendChild(clockLabel);
  // The clock's own opt-in toggle, not one of STATUS_SLOTS above (it is
  // off by default, so it is rendered and wired separately rather than
  // joining a loop that assumes every entry starts visible).
  const clockToggle = $("status-bar-clock-toggle");
  if (clockToggle) {
    clockToggle.checked = Boolean(prefsCache?.status_bar_clock);
    clockToggle.onchange = () => {
      if (prefsCache) prefsCache.status_bar_clock = clockToggle.checked;
      applyStatusClock();
      setPreference("status_bar_clock", clockToggle.checked);
    };
  }
}

//: The MCP client snippet (Brief 40), lazy because only the Tools pane draws it (reached
//: through the settingsControls stub in app.js): the capabilities route knows this
//: interpreter and this notebook's folder, so the snippet is correct to paste.
async function renderMcpSnippet() {
  const pre = $("mcp-config-snippet");
  if (!pre) return;
  const caps = await apiJson("/capabilities").catch(() => null);
  const mcp = caps?.features?.mcp;
  const note = $("mcp-config-note");
  const copy = $("mcp-config-copy");
  if (!mcp?.installed || !mcp.config) {
    pre.classList.add("hidden");
    copy.classList.add("hidden");
    note.textContent = mcp?.reason || "This install cannot start the tool server.";
    note.classList.remove("hidden");
    return;
  }
  pre.classList.remove("hidden");
  copy.classList.remove("hidden");
  note.classList.add("hidden");
  const text = JSON.stringify({ mcpServers: { tessellate: mcp.config } }, null, 2);
  pre.textContent = text;
  copy.onclick = () => copyToClipboard(text, copy);
}

//: The network pane's state line and certificate facts, lazy with the listeners that
//: also call them (settings-panes.js reaches them through the settingsControls stubs).
function renderLanState(state) {
  const box = $("account-allow-lan");
  const line = $("account-lan-state");
  if (!box || !line) return;
  box.checked = !!state.allow_lan;
  const addresses = (state.addresses || []).filter(Boolean);
  let icon = "ph:info";
  let words = "";
  if (state.restart_required) {
    icon = "ph:arrow-clockwise";
    words = state.allow_lan
      ? "Restart the app to let other devices in."
      : "Restart the app to close it to other devices.";
  } else if (state.other_devices) {
    icon = "ph:wifi-high";
    //: The address is its own block below (INBOX 867, the owner: "can this
    //: be better styled and easier to read??"), not a run-on sentence.
    words = addresses.length
      ? "Other devices on this network can open it, with your password, at:"
      : "Other devices can open the app at this computer's network address.";
  } else if (!state.allow_lan && state.switched_off) {
    //: The 14-day rule (lantrust.UNUSED_DAYS): said here as well as in the
    //: bell, since this is where a person goes to turn it back on.
    words = `Turned itself off on ${state.switched_off}: no other device opened the app for ${state.unused_days || 14} days.`;
  }
  line.classList.toggle("hidden", !words);
  if (words) setLabel(line, `${icon} ${words}`);
  renderLanTrust(state);
  $("account-lan-restart")?.classList.toggle("hidden", !state.restart_required);
  //: The certificate the network is served with (core/lancert.py), shown
  //: while the switch is on so a phone's one-time warning can be checked.
  const cert = $("account-lan-cert");
  if (cert) {
    const shown = Boolean(state.allow_lan && state.certificate);
    cert.classList.toggle("hidden", !shown);
    $("account-lan-fingerprint").textContent = shown ? state.certificate.fingerprint : "";
    //: The names it vouches for and when it ends: "wrong name" on a phone
    //: is read off these against the address in the phone's bar.
    $("account-lan-cert-names").textContent = shown
      ? `Names on it: ${(state.certificate.names || []).join(", ")}`
      : "";
    $("account-lan-cert-expiry").textContent = shown ? `Expires ${state.certificate.expires}` : "";
    $("account-lan-authority").textContent = shown ? state.certificate.authority_fingerprint || "" : "";
  }
}

//: **The address as a QR code** (WORLD_CLASS_PLAN "Placed from Brief 40" fix
//: 2): typing `https://192.168.x.y:8443` on a phone is the step people get
//: wrong, and a phone's camera opens a QR code. Drawn by the server
//: (`GET /privacy/lan-qr.svg`, core/qrsvg.py, only for an address it shows),
//: fetched with the session header and shown from a blob. Which address is
//: open is kept, so a repaint of the block (a state refresh) draws it again.
const settingsControlState = {
  lanQrShown: "",
  themePreviewTimer: 0,
};
async function showLanQr(holder, address, button, open) {
  holder.querySelector(".lan-qr")?.remove();
  button.setAttribute("aria-expanded", String(open));
  settingsControlState.lanQrShown = open ? address : "";
  if (!open) return;
  let blob;
  try {
    blob = await (await api(`/privacy/lan-qr.svg?address=${encodeURIComponent(address)}`, { silent: true })).blob();
  } catch (error) {
    toast(`Couldn't draw the QR code: ${error.message}`, true);
    button.setAttribute("aria-expanded", "false");
    settingsControlState.lanQrShown = "";
    return;
  }
  if (!button.isConnected || button.getAttribute("aria-expanded") !== "true") return;
  const figure = document.createElement("figure");
  figure.className = "lan-qr";
  const img = document.createElement("img");
  img.src = URL.createObjectURL(blob);
  img.alt = `QR code for ${address}`;
  img.addEventListener("load", () => URL.revokeObjectURL(img.src), { once: true });
  const caption = document.createElement("figcaption");
  caption.className = "muted text-sm";
  caption.textContent = "Point the phone's camera at it to open this address.";
  figure.append(img, caption);
  holder.querySelector(".lan-address-main")?.after(figure);
}

//: **Where a phone opens the notebook** (INBOX 867): one address, the one on
//: the network's own interface, large and monospaced with Copy, and the rest
//: folded under "Other addresses" (IPv6 last, virtual adapters already left
//: out by the server, `netbind.order_addresses`). Settings, Other devices and
//: the privacy receipt draw the same block from the same state.
function renderLanAddresses(holder, state) {
  if (!holder) return;
  lazyScript("/css/lan-lazy.css");
  const addresses = (state.addresses || []).filter(Boolean);
  holder.replaceChildren();
  holder.classList.toggle("hidden", !addresses.length);
  if (!addresses.length) return;
  const [first, ...rest] = addresses;
  const main = document.createElement("div");
  main.className = "lan-address-main";
  const value = document.createElement("code");
  value.className = "lan-address";
  value.textContent = first;
  const copy = smallButton("ph:copy Copy", "Copy this address", () => copyToClipboard(first, copy));
  const qr = smallButton("ph:qr-code QR code", "Show a QR code the phone's camera opens", () =>
    showLanQr(holder, first, qr, qr.getAttribute("aria-expanded") !== "true"));
  qr.setAttribute("aria-expanded", "false");
  main.append(value, copy, qr);
  holder.appendChild(main);
  if (settingsControlState.lanQrShown === first) showLanQr(holder, first, qr, true);
  if (!rest.length) return;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ghost disclosure-row lan-address-more";
  toggle.setAttribute("aria-expanded", "false");
  setLabel(toggle, `ph:caret-right Other addresses (${rest.length})`);
  const list = document.createElement("ul");
  list.className = "lan-address-list hidden";
  list.id = `${holder.id}-more`;
  toggle.setAttribute("aria-controls", list.id);
  for (const address of rest) {
    const li = document.createElement("li");
    const code = document.createElement("code");
    code.className = "lan-address-small";
    code.textContent = address;
    li.appendChild(code);
    list.appendChild(li);
  }
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    list.classList.toggle("hidden", !open);
  });
  holder.append(toggle, list);
}

//: The Windows firewall line (OPEN ledger 315 and 316): the server sends it
//: only on Windows with the switch on, so everywhere else this stays hidden.
function renderLanFirewall(state) {
  const holder = $("account-lan-firewall");
  if (!holder) return;
  const command = state.firewall?.command || "";
  holder.classList.toggle("hidden", !command);
  $("account-lan-firewall-command").textContent = command;
  const copy = $("account-lan-firewall-copy");
  copy.onclick = () => copyToClipboard(command, copy);
}

const LAN_HELD_REASONS = {
  new_network: "it is not a network you allowed",
  unknown_network: "this network could not be identified",
  public_network: "Windows calls this network public",
  untrusted_network: "you stopped trusting it",
  no_network: "this computer is not on a network",
};

function lanListRow(title, facts, actions) {
  const li = document.createElement("li");
  //: Its actions stay on screen (lan-lazy.css): an `.entry-list` hides a
  //: row's actions until hover, which left a blank where they wait and
  //: nothing at all to a finger.
  li.className = "lan-network-row";
  const row = document.createElement("div");
  row.className = "entry-meta";
  const name = document.createElement("strong");
  name.textContent = title;
  row.append(name, rowActions(actions, `More for ${title}`));
  const detail = document.createElement("p");
  detail.className = "muted task-detail";
  detail.textContent = facts.filter(Boolean).join(" · ");
  li.append(row, detail);
  return li;
}

function lanEmptyRow(words) {
  const li = document.createElement("li");
  li.className = "muted empty-line";
  li.textContent = words;
  return li;
}

async function lanCall(path, options) {
  try {
    renderLanState(await apiJson(path, options));
  } catch (error) {
    toast(error.message, true);
  }
}

//: The held notice, the address block, the two overrides and the three lists.
function renderLanTrust(state) {
  const held = $("account-lan-held");
  if (!held) return;
  held.classList.toggle("hidden", !state.held);
  if (state.held) {
    const where = state.network?.network?.label || "this network";
    setLabel(
      $("account-lan-held-text"),
      `ph:shield-warning Other devices can't open the notebook on ${where}: ${LAN_HELD_REASONS[state.held] || "it is not allowed"}.`
    );
  }
  renderLanAddresses($("account-lan-addresses"), state.other_devices ? state : { addresses: [] });
  renderLanFirewall(state);
  const trust = $("account-lan-trust");
  trust.classList.toggle("hidden", !state.allow_lan);
  $("account-lan-ask").checked = state.ask_new_devices !== false;
  $("account-lan-any").checked = state.any_network === true;
  const pending = state.pending || [];
  $("account-lan-pending-wrap").classList.toggle("hidden", !pending.length);
  $("account-lan-pending").replaceChildren(
    ...pending.map((device) =>
      lanListRow(device.name, [device.address, "gave the right password"], [
        { label: "Allow", title: "Let this device sign in", run: () => lanCall(`/auth/lan-devices/${encodeURIComponent(device.id)}/allow`, { method: "POST" }) },
        { label: "Deny", title: "Do not let it in", danger: true, run: () => lanCall(`/auth/lan-devices/${encodeURIComponent(device.id)}/deny`, { method: "POST" }) },
      ])
    )
  );
  const devices = state.devices || [];
  $("account-lan-devices").replaceChildren(
    ...(devices.length
      ? devices.map((device) =>
          lanListRow(device.name, [device.address, device.last_seen && `last seen ${device.last_seen}`, device.added && `allowed ${device.added}`], [
            { label: "Remove", title: "Sign it out; it asks again next time", danger: true, run: () => lanCall(`/auth/lan-devices/${encodeURIComponent(device.id)}`, { method: "DELETE" }) },
          ])
        )
      : [lanEmptyRow("None yet. A phone is added when you allow its first sign-in.")])
  );
  const rows = lanNetworkRows(state, renderLanState);
  $("account-lan-networks").replaceChildren(
    ...(rows.trusted.length ? rows.trusted : [lanEmptyRow("None yet. Turning other devices on trusts the network you are on.")])
  );
  $("account-lan-untrusted-wrap").classList.toggle("hidden", !rows.untrusted.length);
  $("account-lan-untrusted").replaceChildren(...rows.untrusted);
}

//: **Trusted and untrusted networks, as rows** (INBOX 896), for Settings and
//: the status bar's panel; `paint(state)` redraws whichever asked. Trust is
//: a loosening, so it asks for the password (the server also refuses it from
//: another device); Stop trusting and Forget only ever let fewer in.
function lanNetworkRows(state, paint) {
  const send = async (path, options) => {
    try {
      paint(await apiJson(path, options));
    } catch (error) {
      toast(error.message, true);
    }
  };
  const here = state.current_network || "";
  //: A row starts with a capital ("Network with router 192.168.0.1"); the
  //: label itself stays lower case for the sentences it sits inside.
  const name = (network) => {
    const label = network.label.charAt(0).toUpperCase() + network.label.slice(1);
    return network.key === here ? `${label} (this network)` : label;
  };
  const path = (network, verb = "") => `/auth/lan-networks/${encodeURIComponent(network.key)}${verb && `/${verb}`}`;
  const forget = (network) => ({
    label: "Forget",
    title: "Forget: take it off both lists; it comes back untrusted if the app sees it again",
    danger: true,
    run: () => send(path(network), { method: "DELETE" }),
  });
  const trusted = (state.networks || []).map((network) =>
    lanListRow(name(network), [network.subnet, network.added && `trusted ${network.added}`], [
      { label: "Stop trusting", title: "Stop trusting: keep other devices out on this network", run: () => send(path(network, "untrust"), { method: "POST" }) },
      forget(network),
    ])
  );
  const untrusted = (state.untrusted || []).map((network) =>
    lanListRow(name(network), [network.subnet, network.blocked ? "you stopped trusting it" : network.added && `seen ${network.added}`], [
      { label: "Trust", title: "Trust: let other devices in on this network; asks for your password", run: () => lanTrustNetwork(network, paint) },
      forget(network),
    ])
  );
  return { trusted, untrusted };
}

async function lanTrustNetwork(network, paint) {
  let reply = null;
  const done = await askPasswordPrompt({
    title: `Trust ${network.label}`,
    message: "Enter your password to let devices on this network open the app. It is remembered for next time.",
    submitLabel: "Trust",
    submit: async (password) => {
      reply = await apiJson(`/auth/lan-networks/${encodeURIComponent(network.key)}/trust`, {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      });
      return reply;
    },
  });
  if (done && reply) {
    paint(reply);
    toast(`${network.label} is trusted. Other devices there can open the app with your password.`);
  }
}

//: A looser setting asks for the password, like the switch; a safer one
//: does not (routes_auth `set_lan_option`).
async function setLanOption(box, name, looser) {
  const wanted = box.checked;
  box.checked = !wanted;
  if (!looser(wanted)) return lanCall("/auth/lan-options", { method: "POST", body: JSON.stringify({ name, enabled: wanted }) });
  let reply = null;
  const done = await askPasswordPrompt({
    title: name === "any_network" ? "Allow on any network" : "Stop asking about new devices",
    message: "Enter your password to change how other devices get in.",
    submitLabel: "Change",
    submit: async (password) => {
      reply = await apiJson("/auth/lan-options", {
        method: "POST",
        body: JSON.stringify({ name, enabled: wanted, current_password: password }),
        ownsAuthErrors: true,
      });
      return reply;
    },
  });
  if (done && reply) renderLanState(reply);
}

$("account-lan-ask")?.addEventListener("change", (event) => setLanOption(event.target, "ask_new_devices", (on) => !on));
$("account-lan-any")?.addEventListener("change", (event) => setLanOption(event.target, "any_network", (on) => on));

$("account-lan-allow-here")?.addEventListener("click", () => lanAllowHere(renderLanState));

//: Allow on this network (`/auth/lan-networks/allow`), password first:
//: Settings' button, and the status bar panel's Trust this network for a
//: network the app has not listed yet (INBOX 896).
async function lanAllowHere(paint) {
  let reply = null;
  const done = await askPasswordPrompt({
    title: "Trust this network",
    message: "Enter your password to let devices on this network open the app. It is remembered for next time.",
    submitLabel: "Trust",
    submit: async (password) => {
      reply = await apiJson("/auth/lan-networks/allow", {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      });
      return reply;
    },
  });
  if (done && reply) {
    paint(reply);
    toast("Other devices can open the app on this network now.");
  }
}

async function renderLanAccess() {
  if (!$("account-allow-lan")) return;
  try {
    renderLanState(await apiJson("/auth/lan-access", { silent: true }));
  } catch {
    $("account-lan-state").classList.add("hidden");
  }
}

// Open a picker, parse the chosen file, hand the object to `apply`.
function pickJsonFile(inputId, apply) {
  const input = $(inputId);
  input.onchange = async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    try {
      apply(JSON.parse(await file.text()));
    } catch {
      toast("That file isn't valid JSON.", "info");
    }
  };
  input.click();
}

function textToSteps(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function textToInputs(text) {
  return textToSteps(text).map((line) => {
    const [name, ...rest] = line.split(":");
    return { name: name.trim(), label: rest.join(":").trim(), required: true };
  });
}
//: Settings, General, Microphone (UI_MODERNISATION V2): drawn by the
//: recorder's bundle, so the two copies are one set of controls.
ensureModule("meetings").then((ok) => {
  if (ok && $("mic-settings-controls")) micControlsInto($("mic-settings-controls"));
});

//: Moved from navigation.js (boot) on 2026-10-11 for the boot scripts' gzip
//: ratchet: Settings is its only door, and `renderMemorySettings` is a stand-in
//: (app.js `LAZY_ENTRY_POINTS.settingsControls`) until this file is in.
// --- what the AI remembers (ROADMAP §39B) ------------------------------------------
//
// The list `save_user_preference` writes into, and the only place the user can
// see it. Worth the screen: this tool's output becomes part of the model's own
// system prompt on every later turn, so without this the assistant's behaviour
// could change permanently for a reason nobody could look up, edit or undo.
//
// The budget line is not decoration. Only active preferences reach the model,
// newest first, and only until the character budget runs out, so a long list
// quietly stops including its oldest entries. Saying so beats letting someone
// wonder why the rule they saved first is being ignored.
async function renderMemorySettings() {
  const list = $("memory-list");
  const empty = $("memory-empty");
  const budget = $("memory-budget");
  if (!list) return;

  //: Placeholders while the first answer is on its way, so a slow disk never
  //: reads as "nothing saved yet" (DESIGN.md's list recipe; only into an
  //: empty list, so a refresh never covers rows already there).
  showSkeletons(list, 3);
  const data = await apiJson("/memory").catch(() => null);
  clearSkeletons(list);
  if (!data) {
    list.replaceChildren();
    budget.textContent = "Couldn't load what Atlas has remembered.";
    return;
  }

  const active = data.preferences.filter((p) => p.active).length;
  budget.textContent = active
    ? `${active} in use, about ${data.in_prompt} of ${data.budget_chars} characters. ` +
      "The newest are kept when this runs out."
    : "";
  empty.classList.toggle("hidden", data.preferences.length > 0);

  // Pending suggestions first. They are the only rows that need an answer,
  // and a proposal buried below thirty settled ones is a proposal nobody
  // sees: which was the whole complaint about the silent version of this
  // feature. Order is otherwise unchanged (newest first, from the API).
  const ordered = [
    ...data.preferences.filter((p) => p.proposed),
    ...data.preferences.filter((p) => !p.proposed),
  ];

  list.replaceChildren(
    ...ordered.map((pref) => {
      const row = document.createElement("div");
      row.className =
        "memory-row" + (pref.proposed ? " is-proposed" : pref.active ? "" : " is-off");

      const text = document.createElement("span");
      text.className = "memory-text";
      text.textContent = pref.content;
      text.title = pref.created_at
        ? `Saved ${whenText(new Date(pref.created_at))}`
        : "";

      // A suggestion is a question, not a switch someone flipped: it gets
      // yes/no rather than on/off, and it is not in the prompt either way
      // until it is answered.
      if (pref.proposed) {
        const tag = document.createElement("span");
        tag.className = "memory-proposed-tag";
        setLabel(tag, "ph:sparkle Suggested by Atlas");

        const answer = async (accept) => {
          await apiJson(`/memory/${pref.id}/answer`, {
            method: "POST",
            body: JSON.stringify({ accept }),
          }).catch((error) => toast(error.message || "Couldn't save that answer.", true));
          renderMemorySettings();
        };
        const yes = document.createElement("button");
        yes.type = "button";
        yes.className = "small";
        yes.textContent = "Remember it";
        yes.addEventListener("click", () => answer(true));

        const no = document.createElement("button");
        no.type = "button";
        no.className = "ghost small";
        no.textContent = "No thanks";
        no.addEventListener("click", () => answer(false));

        row.append(text, tag, yes, no);
        return row;
      }

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "ghost small";
      toggle.textContent = pref.active ? "Turn off" : "Turn on";
      toggle.addEventListener("click", async () => {
        toggle.disabled = true;
        const flipped = await apiJson(`/memory/${pref.id}`, {
          method: "PATCH",
          body: JSON.stringify({ active: !pref.active }),
        }).catch((error) => toast(error.message || "Couldn't change that.", true));
        if (flipped) {
          pushRequestUndo(pref.active ? "Turned a memory off" : "Turned a memory on", `/memory/${pref.id}`, "PATCH", { active: pref.active }, { active: !pref.active }, () => renderMemorySettings());
        }
        renderMemorySettings();
      });

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "ghost small danger";
      remove.textContent = "Forget";
      remove.addEventListener("click", async () => {
        const ok = await confirmDialog(
          `Forget this?\n\n“${pref.content}”\n\nThe AI will stop applying it.`,
          { confirmLabel: "Forget it" }
        );
        if (!ok) return;
        //: Said when it fails (audit 2026-10-05, FE-12): a silent catch
        //: redrew the list with the memory still in it and no reason why.
        try {
          await apiJson(`/memory/${pref.id}`, { method: "DELETE" });
          let liveId = null;
          pushUndo(
            "Forgot a memory",
            async () => {
              const again = await apiJson("/memory", { method: "POST", body: JSON.stringify({ content: pref.content }) });
              liveId = again?.id ?? null;
              if (liveId != null && !pref.active) await apiJson(`/memory/${liveId}`, { method: "PATCH", body: JSON.stringify({ active: false }) });
              renderMemorySettings();
            },
            async () => {
              if (liveId != null) await apiJson(`/memory/${liveId}`, { method: "DELETE" });
              renderMemorySettings();
            }
          );
        } catch (error) {
          toast(error.message || "Couldn't forget that.", true);
        }
        renderMemorySettings();
      });

      row.append(text, toggle, remove);
      return row;
    })
  );
}
// ---- Settings, About, Maintenance (core/maintenance.py, core/doctor.py) ----
//: The owner, 2026-10-11: "Can you add like buttons in settings to run them
//: in like the about page??", about doctor, reinstall, tools and uninstall.
//: Every route is this computer only (api/this_computer.py): on a phone the
//: first read is refused, the buttons go off and the status line carries the
//: server's own sentence.
const MAINTENANCE_MARKS = {
  ok: ["check-circle", "Passed"],
  warn: ["warning", "Worth a look"],
  x: ["x-circle", "Needs fixing"],
};

function maintenanceSay(text) {
  $("maintenance-status").textContent = text;
}

async function renderMaintenance() {
  const buttons = [...$("maintenance-actions").querySelectorAll("button")];
  let state;
  try {
    state = await apiJson("/system/maintenance");
  } catch (error) {
    for (const button of buttons) button.disabled = true;
    $("maintenance-reinstall-row").classList.add("hidden");
    maintenanceSay(error.message || "Couldn't read this computer's state.");
    return;
  }
  for (const button of buttons) button.disabled = false;
  //: The installer's copy has no .venv to rebuild: no button, and the '?'
  //: says its Repair shortcut is the way.
  $("maintenance-reinstall").classList.toggle("hidden", !state.source);
  $("maintenance-reinstall-row").classList.toggle("hidden", !(state.source && state.reinstall_pending));
  $("maintenance-uninstall").dataset.plan = JSON.stringify(state.uninstall || {});
  maintenanceSay("");
}

function maintenanceDoctorRow(row) {
  const el = document.createElement("div");
  el.className = "setting-row doctor-row";
  const label = document.createElement("div");
  label.className = "setting-label";
  const name = document.createElement("span");
  const [icon, words] = MAINTENANCE_MARKS[row.status] || MAINTENANCE_MARKS.warn;
  const mark = document.createElement("i");
  mark.className = `ph ph-${icon} doctor-mark is-${row.status in MAINTENANCE_MARKS ? row.status : "warn"}`;
  mark.setAttribute("role", "img");
  mark.setAttribute("aria-label", words);
  name.append(mark, document.createTextNode(` ${row.label}`));
  label.appendChild(name);
  if (row.fix) {
    const fix = document.createElement("small");
    fix.className = "muted";
    fix.textContent = row.fix;
    label.appendChild(fix);
  }
  const value = document.createElement("span");
  value.className = "setting-control muted";
  value.textContent = row.value;
  el.append(label, value);
  return el;
}

async function runMaintenanceDoctor() {
  const button = $("maintenance-doctor");
  const box = $("maintenance-doctor-rows");
  button.disabled = true;
  maintenanceSay("Checking…");
  try {
    const result = await apiJson("/system/doctor");
    box.replaceChildren(...result.rows.map(maintenanceDoctorRow));
    box.classList.remove("hidden");
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const worth = result.rows.filter((row) => row.status === "warn").length;
    maintenanceSay(
      result.failed
        ? `Checked at ${time}. Something below needs fixing: each cross says what to do.`
        : worth
          ? `Checked at ${time}. Nothing is broken; ${worth} worth a look.`
          : `Checked at ${time}. Everything checks out.`
    );
  } catch (error) {
    maintenanceSay(error.message || "Couldn't run the checks.");
  } finally {
    button.disabled = false;
  }
}

async function setMaintenanceReinstall(enabled) {
  try {
    const result = await apiJson("/system/reinstall-on-start", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    });
    $("maintenance-reinstall-row").classList.toggle("hidden", !result.reinstall_pending);
    maintenanceSay(result.reinstall_pending ? "" : "Reinstall cancelled. The next start is an ordinary one.");
  } catch (error) {
    maintenanceSay(error.message || "Couldn't set the reinstall.");
  }
}

async function openMaintenanceFolder() {
  try {
    const result = await apiJson("/system/open-logs-folder", { method: "POST" });
    maintenanceSay(`Opened ${result.path}`);
  } catch (error) {
    maintenanceSay(error.message || "Couldn't open the launcher logs.");
  }
}

async function makeMaintenanceShortcut() {
  try {
    const result = await apiJson("/system/desktop-shortcut", { method: "POST" });
    maintenanceSay(`Shortcut made: ${result.desktop_copy || result.path}`);
  } catch (error) {
    maintenanceSay(error.message || "Couldn't make the shortcut.");
  }
}

//: **Uninstall is never one click** (the brief): a dialog with the steps,
//: the command for this computer with Copy, and Export my notes first.
function openUninstallSteps() {
  let plan = {};
  try {
    plan = JSON.parse($("maintenance-uninstall").dataset.plan || "{}");
  } catch {
    plan = {};
  }
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Uninstall");
  const card = document.createElement("div");
  card.className = "card modal-card confirm-card uninstall-card";
  const returnFocus = document.activeElement;
  const onKey = (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    close();
  };
  const close = () => {
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    returnFocus?.focus?.();
  };
  const blurb = document.createElement("p");
  blurb.className = "muted";
  blurb.textContent = "Nothing is removed from here. These are the steps for this computer.";
  const steps = document.createElement("ol");
  steps.className = "uninstall-steps";
  for (const step of plan.steps || []) {
    const li = document.createElement("li");
    li.textContent = step;
    steps.appendChild(li);
  }
  card.append(dialogHead("Uninstall", close), blurb, steps);
  if (plan.command) {
    const row = document.createElement("div");
    row.className = "row uninstall-command-row";
    const code = document.createElement("code");
    code.className = "uninstall-command";
    code.textContent = plan.command;
    const copy = smallButton("ph:copy Copy", "Copy the command", () => copyToClipboard(plan.command, copy));
    row.append(code, copy);
    card.appendChild(row);
  }
  const footer = document.createElement("div");
  footer.className = "row confirm-actions";
  footer.append(
    smallButton("Close", "Close", close),
    smallButton("ph:export Export my notes first", "Open Settings, Import & export", () => {
      close();
      openSettingsModal("data", "export-folder");
    }, false)
  );
  card.appendChild(footer);
  overlay.appendChild(card);
  wireBackdropClose(overlay, close);
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  footer.querySelector("button:last-child")?.focus();
}

$("maintenance-doctor")?.addEventListener("click", runMaintenanceDoctor);
$("maintenance-reinstall")?.addEventListener("click", () => setMaintenanceReinstall(true));
$("maintenance-reinstall-cancel")?.addEventListener("click", () => setMaintenanceReinstall(false));
//: One restart mechanism (`restartMemoryMap`, `#about-restart`'s).
$("maintenance-restart")?.addEventListener("click", () => restartMemoryMap());
$("maintenance-logs")?.addEventListener("click", openMaintenanceFolder);
$("maintenance-shortcut")?.addEventListener("click", makeMaintenanceShortcut);
$("maintenance-uninstall")?.addEventListener("click", openUninstallSteps);
//: Settings, Appearance, Themes (ledger 1451, 1452): a theme shows on the
//: whole app while the pointer or focus rests on its card, and "Surprise me"
//: applies one you are not using. The preview is `settingsLook.themePreview` (settings.js),
//: read ahead of the manual layer and never stored.
//: Hover waits this long before it repaints the whole app, so crossing the grid
//: previews nothing (B58: "slightly longer"); the eye and the keyboard do not wait.
const THEME_HOVER_PREVIEW_MS = 450;
function previewTheme(name, delay = name ? THEME_HOVER_PREVIEW_MS : 0) {
  clearTimeout(settingsControlState.themePreviewTimer);
  if (!name && settingsControlState.themeHold) return;
  settingsControlState.themePreviewTimer = setTimeout(() => {
    if (settingsLook.themePreview === name) return;
    settingsLook.themePreview = name;
    applyAppearance();
    applyThemeChoice(appearancePref("theme"), false);
    applyPalette(appearancePref("palette"), false);
  }, delay);
}
//: The eye in each card's corner (B58). Hover or focus previews at once; a click
//: holds the preview (the touch path) until the next click anywhere.
function releaseThemeHold() {
  settingsControlState.themeHold = "";
  for (const b of document.querySelectorAll("#theme-presets .theme-eye")) {
    b.setAttribute("aria-pressed", "false");
    b.classList.remove("is-on");
  }
  previewTheme("", 0);
}
function themeEyeButton(name, label) {
  const eye = document.createElement("button");
  eye.type = "button";
  eye.className = "theme-eye icon-only ghost small";
  eye.dataset.preset = name;
  eye.title = `Preview the ${label} theme`;
  eye.setAttribute("aria-label", `Preview the ${label} theme`);
  const held = settingsControlState.themeHold === name;
  eye.setAttribute("aria-pressed", String(held));
  eye.classList.toggle("is-on", held);
  const icon = document.createElement("i");
  icon.className = "ph ph-eye";
  icon.setAttribute("aria-hidden", "true");
  eye.appendChild(icon);
  eye.addEventListener("pointerenter", () => previewTheme(name, 0));
  eye.addEventListener("pointerleave", () => previewTheme(""));
  eye.addEventListener("focus", () => eye.matches(":focus-visible") && previewTheme(name, 0));
  eye.addEventListener("blur", () => previewTheme(""));
  eye.addEventListener("click", (event) => {
    event.stopPropagation();
    const wasHeld = settingsControlState.themeHold === name;
    releaseThemeHold();
    if (wasHeld) return;
    settingsControlState.themeHold = name;
    eye.setAttribute("aria-pressed", "true");
    eye.classList.add("is-on");
    previewTheme(name, 0);
  });
  return eye;
}
function decorateThemeCards() {
  for (const card of document.querySelectorAll("#theme-presets > .theme-card")) {
    const cell = document.createElement("span");
    cell.className = "theme-card-cell";
    card.before(cell);
    cell.append(card, themeEyeButton(card.dataset.preset, card.querySelector(".theme-card-name")?.textContent || ""));
  }
}
(() => {
  //: The cards are redrawn by settings.js on every Appearance render.
  const draw = renderThemePresets;
  renderThemePresets = function renderThemePresetsWithEyes() {
    draw();
    decorateThemeCards();
  };
  decorateThemeCards();
  document.addEventListener("click", (event) => {
    if (settingsControlState.themeHold && !event.target.closest?.(".theme-eye")) releaseThemeHold();
  }, true);
})();
(() => {
  const holder = $("theme-presets");
  if (!holder) return;
  const card = (event) => event.target.closest?.(".theme-card");
  holder.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch") return;
    const c = card(event);
    if (c) previewTheme(c.dataset.preset);
  });
  holder.addEventListener("pointerleave", () => previewTheme(""));
  holder.addEventListener("focusin", (event) => {
    const c = card(event);
    if (c && c.matches(":focus-visible")) previewTheme(c.dataset.preset);
  });
  holder.addEventListener("focusout", () => previewTheme(""));
  //: Capture: the preview is gone before the card's own click applies the theme.
  holder.addEventListener("click", () => {
    clearTimeout(settingsControlState.themePreviewTimer);
    settingsLook.themePreview = "";
  }, true);
})();
$("theme-surprise")?.addEventListener("click", () => {
  const active = activeThemePreset();
  const names = Object.keys(THEME_PRESETS).filter((n) => n !== active);
  const pick = names[Math.floor(Math.random() * names.length)];
  applyThemePreset(pick, true);
  renderAppearance();
  toast(`${THEME_PRESETS[pick].label} theme. Press Surprise me again for another.`, "info");
});

//: Logs, from a job history row and the empty log (moved out of boot code, the
//: gzip budget): the row's button awaits this file through openSettingsModal.
async function openTaskLog(item) {
  await openSettingsModal("logs");
  const filter = $("log-filter");
  //: The run's id, which its log lines carry in brackets (jobruns.py), so the
  //: lines shown are this run's. An older entry without one falls back to words.
  settingsLook.logFilterFromRun = !!item.run_id;
  filter.value = item.run_id ? `[${item.run_id}]` : /\(([^)]+)\)/.exec(item.label || "")?.[1] || item.name || item.label || "";
  filter.dispatchEvent(new Event("input"));
}

$("logs-empty-clear").addEventListener("click", () => {
  settingsLook.logFilterFromRun = false;
  $("log-filter").value = "";
  $("log-level").value = "all";
  $("log-source").value = "all";
  renderActiveLogView();
});

// ---- B56: Auto says what it resolved to (settings-controls.js is lazy, off the boot budget) ----

//: **Auto says what it resolved to** (INBOX 904 B56: "when settings are on auto,
//: I can't tell what it autoed to"). Each Appearance select that has an Auto
//: option names the answer in the option itself, so the closed face reads
//: "Auto (compact now)" and the open list shows the same. The long form of what
//: Auto means stays in the option's title and the row's own words.
function renderAutoChoices() {
  const word = (id, resolved, meaning) => {
    const option = $(id)?.querySelector('option[value="auto"]');
    if (!option) return;
    const text = `Auto (${resolved})`;
    if (option.textContent !== text) option.textContent = text;
    if (meaning) option.title = meaning;
  };
  const dens = effectiveDensity();
  word("density-seg", `${dens} now`, "Compact on a window 700px tall or less, the look's own spacing on a taller one");
  const perf = smallMachine() || lessTransparencyWanted();
  word("perf-mode", perf ? "on now" : "off now", "On for a machine with 2 cores or 4 GB or fewer, or when your system asks for less transparency");
  const still = reducedMotionWanted();
  word("progress-motion", still ? "still now" : "moving now", "Follows reduced motion: your system's, or this app's own");
  word("bg-motion", still ? "still now" : "moving now", "Follows reduced motion: your system's, or this app's own");
  const { look, reason } = atlasLookReason();
  const from = { "face-looks": "from Face looks", "your-look": "from your own look", default: "main look" }[reason] || "";
  word("atlas-look", from ? `${look}, ${from}` : look, "Matches Face looks when it is one look, otherwise the look you chose for your own face");
}

//: B56: Auto names what it resolved to for the model in use. The server's
//: answer is `chat_model_small` (True, False, or None for "the name has no
//: size in it", which the runner treats as off).
function renderSmallModelAuto() {
  const option = $("small-model-mode")?.querySelector('option[value="auto"]');
  if (!option || typeof modelStatus === "undefined" || !modelStatus) return;
  const small = modelStatus.chat_model_small;
  const text = `Auto (${small === true ? "on" : "off"} now)`;
  if (option.textContent !== text) option.textContent = text;
  option.title =
    small === true
      ? `${modelStatus.chat_model} reads as a small model, so each step is offered one tool`
      : small === false
        ? `${modelStatus.chat_model} does not read as a small model, so each step is offered the whole toolbox`
        : `The name ${modelStatus.chat_model} carries no size, which counts as not small`;
}
settingsReadouts.auto = renderAutoChoices;
settingsReadouts.smallModel = renderSmallModelAuto;

//: **Expand all / Collapse all in a pane's dock** (INBOX 904 B14: "each settings
//: page should have an expand and collapse all sections button at the top").
//: A pane with two or more folds gets one worded ghost in its `.dock-actions`,
//: before the icon run; one fold or none has nothing to open all of. It says
//: what pressing it does: Expand all while any fold is shut, Collapse all once
//: every one is open. `toggle` does not bubble, so the pane listens in the
//: capture phase and the label follows folds opened by hand too.
function ensureSettingsFoldAll(box) {
  if (!box) return;
  const folds = () => [...box.querySelectorAll("details")].filter((d) => !d.parentElement.closest("details"));
  const bar = box.querySelector(":scope > .settings-pane-title");
  if (!bar || folds().length < 2) return;
  let button = bar.querySelector("[data-fold-all]");
  const paint = () => {
    const shut = folds().some((d) => !d.open);
    button.dataset.foldAll = shut ? "expand" : "collapse";
    setLabel(button, shut ? "ph:arrows-out-line-vertical Expand all" : "ph:arrows-in-line-vertical Collapse all");
    button.title = shut ? "Open every section on this page" : "Close every section on this page";
  };
  if (!button) {
    let actions = bar.querySelector(".dock-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "dock-actions";
      bar.appendChild(actions);
    }
    button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small settings-fold-all";
    button.dataset.foldAll = "expand";
    button.addEventListener("click", () => {
      const open = button.dataset.foldAll === "expand";
      for (const fold of folds()) fold.open = open;
      paint();
    });
    //: Worded ghosts first, the icon-only run (the '?') after them.
    actions.insertBefore(button, actions.querySelector(".icon-only"));
    box.addEventListener("toggle", paint, true);
  }
  paint();
}

//: This file arrives after the first Appearance render, so label once now.
renderAutoChoices();
renderSmallModelAuto();
