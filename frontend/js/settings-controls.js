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
(() => {
  const SETTINGS_CONTROLS_READY = true;
  //: The body these listeners wire is built here if nothing asked for a control
  //: first (settings-body.js; INBOX 1501): every `$` below finds its element.
  surfaceBuild("settings");

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
  // Enter anywhere in the change-password form submits it.
  for (const id of ["account-current", "account-new", "account-confirm"]) {
    $(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") changePassword();
    });
  }

  //: Here, not in the boot settings-panes.js (the gzip ratchet): Settings is its
  //: only door, and its fields are drawn before this file loads.
  async function changePassword() {
    const status = $("account-status");
    const current = $("account-current").value;
    const next = $("account-new").value;
    const confirmed = $("account-confirm").value;
    status.classList.remove("error");

    // Checked here as well as on the server, so a typo costs a moment rather
    // than a password you didn't mean to set.
    if (!current || !next) {
      status.classList.add("error");
      status.textContent = "Fill in your current and new password.";
      return;
    }
    if (next !== confirmed) {
      status.classList.add("error");
      status.textContent = "The two new passwords don't match.";
      return;
    }
    if (next.length < 8) {
      status.classList.add("error");
      status.textContent = "A new password needs at least 8 characters.";
      return;
    }

    status.textContent = "Changing…";
    try {
      const result = await apiJson("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
        // A 401 here means "wrong current password", not "your session died".
        ownsAuthErrors: true,
      });
      // Changing the password invalidates every token, including this tab's.
      // The server hands back a fresh one so the change doesn't log you out of
      // the screen you just used to make it. Key must match authToken().
      prefs.set("token", result.token);
      $("account-current").value = "";
      $("account-new").value = "";
      $("account-confirm").value = "";
      status.textContent = result.warning || "Password changed.";
      if (result.pin_cleared) status.textContent += " Your PIN was removed; set it up again if you want one.";
      if (result.hello_cleared) status.textContent += " Windows Hello was turned off; turn it on again if you want it.";
      toast(
        result.other_sessions_ended
          ? `Password changed. ${result.other_sessions_ended} other session(s) were signed out.`
          : "Password changed."
      );
      renderAccount().catch(() => {});
    } catch (error) {
      status.classList.add("error");
      status.textContent = error.message;
    }
  }

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
  $("account-private-idle").addEventListener("change", (e) => {
    setPreference("private_space_idle_minutes", Number(e.target.value));
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

  $("pref-web-store").addEventListener("change", (e) => setPreference("web_store_enabled", e.target.checked));
  $("web-store-clear").addEventListener("click", async () => {
    let done;
    try {
      done = await apiJson("/websearch/stored", { method: "DELETE" });
    } catch (error) {
      return toast(`Couldn't clear the kept pages: ${error.message}`, "info");
    }
    toast(`Cleared ${done.cleared} kept page${done.cleared === 1 ? "" : "s"}.`, "info");
  });

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

  $("pref-update-bar").addEventListener("change", (e) => {
    if (!e.target.checked) document.querySelector(".update-bar")?.remove();
    return setPreference("show_update_bar", e.target.checked);
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

  $("pref-desktop-companion")?.addEventListener("change", (e) => {
    const checked = e.target.checked;
    setPreference("desktop_companion", checked);
    toast(checked ? "Your companion will sit in the corner while the window is minimised or in the tray." : "The desktop companion is off.");
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
  $("pref-date-order").addEventListener("change", (e) => setPreference("date_order", e.target.value));
  $("pref-before-includes-day").addEventListener("change", (e) => setPreference("before_includes_day", e.target.checked));
  $("pref-birthday").addEventListener("change", (e) => setPreference("birthday", e.target.value));
  $("pref-season-hemisphere").addEventListener("change", (e) => setPreference("season_hemisphere", e.target.value));
  //: The voice's live sample (CHAT_PLAN decision 72): the same three lines
  //: `composer_digest.sample` writes, kept equal by tests/test_answer_voice.py.
  const VOICE_SAMPLES = {
    natural: "You have four notes about uni. Nothing yet on assessments or due dates. Remind you to ask the tutor on Thursday?",
    professional: "Your notebook holds four notes on uni. The notes do not yet cover assessments or due dates. Set a reminder to ask the tutor on Thursday?",
    playful: "Found four notes about uni. No word yet on assessments or due dates. Want a nudge to ask the tutor on Thursday?",
    plain: "Four notes about uni. Not in your notes: assessments or due dates. Remind you to ask the tutor on Thursday?",
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

  $("pref-ask-when-unsure").addEventListener("change", (e) =>
    setPreference("ask_when_unsure", e.target.checked)
  );

  //: INBOX 1695 (Q30): a new note is sealed from its first write; off by default.
  $("pref-new-notes-private").addEventListener("change", (e) =>
    setPreference("new_notes_private", e.target.checked).then(() => {
      //: The Capture page's Private follows the setting until it is pressed (its draft key).
      if (!prefs.has("captureDraftPrivate")) createNoteSafely.lock?.sync($("entry-private"));
    })
  );

  //: INBOX 1695 (d): seal every ordinary note. The confirm says what private costs.
  $("account-make-all-private").addEventListener("click", async () => {
    const status = $("account-make-all-status");
    status.classList.remove("error");
    status.textContent = "";
    const ask = "Make every note private? Private notes are locked with your password and left out of Ask, chat, filing and meaning search. You can make one readable again from its menu.";
    if (!(await confirmDialog(ask, { confirmLabel: "Make all private" }))) return;
    try {
      const result = await apiJson("/entries/make-all-private", { method: "POST", body: JSON.stringify({ confirm: true }) });
      status.textContent = `Done: ${nounCount(result.sealed, "note")} made private.`;
      refreshEntries(result.ids).catch(() => {});
      //: Undo opens the same notes again, one by one; Redo seals them again.
      const setAll = async (on) => {
        for (const id of result.ids || []) await apiJson(`/entries/${id}/privacy`, { method: "POST", body: JSON.stringify({ private: on }) });
        refreshEntries(result.ids).catch(() => {});
      };
      if (result.ids?.length) offerUndo("Make all notes private", `${nounCount(result.sealed, "note")} made private.`, () => setAll(false), () => setAll(true));
    } catch (err) {
      status.classList.add("error");
      status.textContent = err.message || "Couldn't make the notes private.";
    }
  });

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

  $("pref-mcp-writes").addEventListener("change", (e) =>
    setPreference("mcp_writes_enabled", e.target.checked)
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
    const ok = await api("/tasks/autonomous/last/clear", { method: "POST" }).then(() => true, () => false);
    if (!ok) toast("The last review was not cleared. Try again.", true, { action: ["Try again", () => $("autonomous-review-clear")?.click()] });
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
  //: Read aloud's speed (E71), kept on this device; `speakText` reads it each time.
  $("pref-read-aloud-voice").value = prefs.get("read-aloud-voice", "browser");
  //: The natural voice (studio.js) is chosen only where it is installed; otherwise the way to it is named.
  $("pref-read-aloud-voice").addEventListener("change", async (e) => {
    const ready = e.target.value !== "natural" || (await apiJson("/voice/status", { silent: true }).catch(() => null))?.speak?.available;
    if (!ready) {
      e.target.value = "browser";
      return toastAction("The natural voice isn't installed.", "Open Packages", () => openSettingsModal("extras"));
    }
    prefs.set("read-aloud-voice", e.target.value);
  });
  //: The browser voice (L333): this computer's own voices, filled when the browser has listed them (it
  //: lists late, so again on `voiceschanged`). Kept on this device by name; `speakText` and the document's
  //: read aloud look it up each time and fall back to Automatic when the voice is gone.
  const voiceName = $("pref-read-aloud-voice-name");
  const fillVoices = () => {
    const voices = ("speechSynthesis" in window ? speechSynthesis.getVoices() : []).filter((v) => v.localService !== false);
    voiceName.replaceChildren(new Option("Automatic", ""), ...voices.map((v) => new Option(`${v.name} (${v.lang})`, v.name)));
    voiceName.value = prefs.get("read-aloud-voice-name", "");
  };
  fillVoices();
  if ("speechSynthesis" in window) speechSynthesis.addEventListener("voiceschanged", fillVoices);
  voiceName.addEventListener("change", (e) => prefs.set("read-aloud-voice-name", e.target.value));
  $("pref-read-aloud-rate").value = prefs.get("read-aloud-rate", "1");
  $("pref-read-aloud-rate").addEventListener("change", (e) => prefs.set("read-aloud-rate", e.target.value));
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
    const saved = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ dashboard_persona: persona }),
    }).then(() => true, () => false);
    if (!saved) return toast("The dashboard greeting was not saved. Try again.", true, { action: ["Try again", () => $("dashboard-persona-select").dispatchEvent(new Event("change"))] });
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

  //: Currency rates (CHAT_PLAN decision 43): lines of "EUR 0.88" and the day they are from.
  async function showCurrencyRates() {
    const got = await apiJson("/utilities/units");
    $("currency-rates-date").value = got.rates_date || "";
    $("currency-rates-text").value = Object.entries(got.rates || {})
      .filter(([code]) => code !== "USD")
      .map(([code, rate]) => `${code} ${rate}`)
      .join("\n");
  }
  async function saveCurrencyRates(clear) {
    const status = $("currency-rates-status");
    const rates = {};
    for (const line of $("currency-rates-text").value.split("\n")) {
      const [code, rate] = line.trim().split(/[\s:=,]+/);
      if (code && Number(rate) > 0) rates[code.toUpperCase()] = Number(rate);
    }
    const day = $("currency-rates-date").value;
    if (!clear && !day) {
      status.textContent = "Pick the day these rates are from.";
      return;
    }
    //: The rates kept before this save, so Undo puts them back (or the built-in table).
    const before = (await apiJson("/preferences").catch(() => ({})))?.currency_rates || null;
    const put = async (value) => {
      await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify(value ? { currency_rates: value } : { unset: ["currency_rates"] }),
      });
      await showCurrencyRates();
    };
    const after = clear ? null : { date: day, rates };
    try {
      await put(after);
      status.textContent = clear ? "Back to the built-in table." : "Saved.";
      offerUndo("Currency rates", clear ? "Built-in rates back." : "Rates saved.", () => put(before), () => put(after));
    } catch (e) {
      status.textContent = "Couldn't save the currency rates. Check each line reads like EUR 0.92.";
    }
  }
  $("currency-rates-save").addEventListener("click", () => saveCurrencyRates(false));
  $("currency-rates-reset").addEventListener("click", () => saveCurrencyRates(true));

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
    $("searxng-start").disabled = true;
    try {
      await ensureModule("webClip");
      const body = await startSearxng($("searxng-host-state").textContent === "Not installed", (text) => { status.textContent = text; });
      $("pref-searxng").value = body.url;
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
  // Help has "Replay the welcome" and Settings, About has "Take tour again";
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

  //: The owner, 2026-10-26: "if I hide this getting started button, is there a
  //: way to get it to show again in settings?" Customise and the palette could;
  //: Settings now can too.
  $("show-get-started-btn")?.addEventListener("click", () => {
    closeSettingsModal();
    lazyScript("/js/first-run.js").then(() => getStartedShow());
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
    const info = await apiJson("/websearch/searxng/status", { silent: true }).catch(() => null);
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
    // An install is minutes long and runs in the background, poll it so the
    // step text keeps moving instead of the screen looking stuck.
    const bar = $("searxng-install-progress");
    if (info.installing) {
      const stage = info.install_stage || 1;
      const stages = info.install_stages || 5;
      badge.textContent = `Installing… ${stage}/${stages}`;
      badge.className = "chip item-label";
      start.classList.remove("ghost");
      stop.classList.add("ghost");
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
    const view = refreshSearxngHost.view(info);
    const note = $("searxng-host-status");
    note.classList.toggle("error", Boolean(info.install_error));
    note.textContent = view.status;
    $("searxng-backend").textContent = view.backend;
    const running = view.running;
    badge.textContent = view.badge;
    badge.className = `chip item-label${view.running ? " is-ok is-live" : ""}`;
    start.disabled = running;
    stop.disabled = info.state === "absent";
    // The primary action is the one that fits: Stop while it runs, Start when not.
    start.classList.toggle("ghost", running);
    stop.classList.toggle("ghost", !running);
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

    const portLine = $("searxng-port");
    portLine.textContent = view.port;
    portLine.classList.toggle("error", view.portError);
  }

  // What the card says for one status payload (INBOX 1734). While our own
  // instance answers, the setup lines (how it will run, who held the default
  // port before it moved) are stale and read like a failure: a running card is
  // one calm line. A property of its caller, not a global.
  refreshSearxngHost.view = (info) => {
    const running = info.state === "running" && Boolean(info.responding);
    const badges = { running: "Starting…", stopped: "Stopped" };
    const view = { running, badge: running ? "Running" : badges[info.state] || "Not installed", backend: "", port: "", portError: false, status: "" };
    if (running) {
      const port = new URL(info.url).port;
      view.status = `Running${port ? ` on port ${port}` : ""}, ${info.backend === "docker" ? "in Docker" : "from its own virtualenv"}.`;
      return view;
    }
    view.backend = info.backend === "docker"
      ? "Docker is installed, so it runs as a container."
      : "Docker isn't installed, so it runs from its own virtualenv instead. The first start takes a few minutes to download and install.";
    const port = info.port;
    view.port = port ? port.detail : "";
    view.portError = Boolean(port && !port.free && !port.held_by_searxng);
    view.status = info.install_error || info.detail || (info.state === "stopped" ? "Installed and ready: press Start SearXNG." : "");
    return view;
  };

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
        ? `${nounCount(body.groups.length, "group")} of similar notes.`
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
      status.textContent = error.message || "Couldn't save that memory.";
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
      head.textContent = `${nounCount(group.entries.length, "note")} · ${Math.round(group.similarity * 100)}% alike`;
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
      const aiReady = !aiIsOff(true);
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
      `Merge ${nounCount(ids.length, "note")} into one?\n\n` +
        `The merged note will read:\n\n${preview.merged.slice(0, 400)}` +
        `${preview.merged.length > 400 ? "…" : ""}\n\n` +
        `The other ${ids.length - 1} go to the bin, so this is undoable.`
    ));
    if (!ok) return;

    //: The kept note's words and tags as they were, for Undo (INBOX 537): the
    //: others went to the bin, so Undo also brings them back.
    const keeper = await fullEntry(ids[0]).catch(() => null);
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
      const action = pushUndo(`Merged ${nounCount(result.merged_count, "note")}`, swap(true), swap(false));
      toastAction(`Merged ${nounCount(result.merged_count, "note")}${result.used_ai ? " with Atlas" : ""}.`, "Undo", async () => {
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
    //: INBOX 1467. A few cards held while you go to another page.
    {
      key: "tray",
      label: "Tray",
      hint: "Hold cards to paste or drag somewhere else",
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
    //: The clock's own opt-in toggle, not one of STATUS_SLOTS (it is off by default, so it is wired apart).
    const wireClock = () => {
      const clockToggle = $("status-bar-clock-toggle");
      if (!clockToggle) return;
      clockToggle.checked = Boolean(prefsCache?.status_bar_clock);
      clockToggle.onchange = () => {
        if (prefsCache) prefsCache.status_bar_clock = clockToggle.checked;
        applyStatusClock();
        setPreference("status_bar_clock", clockToggle.checked);
      };
    };
    //: Drawn once; a later open only sets the ticks (perf audit 1108 P12: 11 listeners and their rows per open).
    const drawn = box.querySelectorAll(".status-bar-item");
    if (drawn.length === STATUS_SLOTS.length) {
      STATUS_SLOTS.forEach((slot, at) => { drawn[at].querySelector("input").checked = !hidden.has(slot.key); });
      wireClock();
      return;
    }
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
    wireClock();
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
    renderAddressNames(state);
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

  //: **Address names** (the owner, "customise the domain name"): the short
  //: `<name>.localhost` the window opens and the domains a reverse proxy uses.
  //: Both live in the LAN reply (`names`); a new domain asks for the password.
  function renderAddressNames(state) {
    const names = state?.names;
    const label = $("account-local-name");
    const domains = $("account-domains");
    if (!names || !label || !domains) return;
    const envLabel = names.local_name_env || "";
    label.value = envLabel || names.local_name || "";
    label.disabled = !!envLabel;
    const envNote = $("account-local-name-env");
    envNote.classList.toggle("hidden", !envLabel);
    envNote.textContent = envLabel ? `Set by TESSELLATE_LOCAL_NAME (${envLabel}); change it there.` : "";
    domains.value = (names.allowed_hosts || []).join(", ");
    domains.dataset.saved = (names.allowed_hosts || []).join(",");
    const fromEnv = names.allowed_hosts_env || [];
    const domainNote = $("account-domains-env");
    domainNote.classList.toggle("hidden", !fromEnv.length);
    domainNote.textContent = fromEnv.length ? `Also set by TESSELLATE_ALLOWED_HOSTS: ${fromEnv.join(", ")}.` : "";
  }

  async function saveAddressNames() {
    const label = $("account-local-name");
    const domains = $("account-domains");
    const status = $("account-names-status");
    const wanted = (domains.value || "").split(/[,;\s]+/).filter(Boolean);
    const body = { local_name: label.disabled ? "" : label.value.trim(), allowed_hosts: wanted };
    // A domain not already saved loosens the host guard, so it asks for the password.
    const saved = (domains.dataset.saved || "").split(",");
    const added = wanted.some((name) => !saved.includes(name.toLowerCase()));
    const send = (extra) => apiJson("/auth/address-names", { method: "POST", body: JSON.stringify({ ...body, ...extra }), ownsAuthErrors: true, silent: true });
    try {
      let reply = null;
      if (added) {
        const done = await askPasswordPrompt({
          title: "Add a domain name",
          message: "Enter your password to let the app answer to this domain.",
          submitLabel: "Add",
          submit: async (password) => (reply = await send({ current_password: password })),
        });
        if (!done || !reply) return;
      } else {
        reply = await send({});
      }
      renderLanState(reply);
      status.textContent = "Saved.";
    } catch (error) {
      status.textContent = "";
      toast(error.message, true); // a 4xx (bad name, wrong password) shows plain; a fault gets Report this
    }
  }

  $("account-names-save")?.addEventListener("click", saveAddressNames);

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
      let data;
      try {
        data = JSON.parse(await file.text());
      } catch {
        return toast("That file isn't valid JSON.", "info");
      }
      //: The apply step is awaited: a refused save (a prompt over its limit)
      //: used to be an unhandled rejection, so an import said nothing at all
      //: (audit 1031 HR12).
      try {
        await apply(data);
      } catch (error) {
        toast(error?.message || "Couldn't import that file.", "info");
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

    //: **Confirmed patterns, their own group** (CHAT_PLAN B9, the owner: "also
    //: is there a way to edit or managed confirmed patterns??"): each Patterns
    //: line the person confirmed, its sentence, the day and the notes behind it
    //: (each opens its note), with the Patterns line's own menu (`rowActions`).
    //: Local, not a global: the shared scope only goes down (row 37a).
    //: Confirmed patterns (CHAT_PLAN B9), built on first draw rather than shipped
    //: in the page (the boot document's element cap, tests/test_boot_diet3.py).
    const confirmedHost = () => {
      const found = $("memory-confirmed-list");
      const section = $("settings-memory");
      if (found || !section) return found;
      const group = section.appendChild(document.createElement("div"));
      group.className = "settings-group";
      const head = group.appendChild(document.createElement("h4"));
      head.className = "setting-subhead";
      head.textContent = "Confirmed patterns";
      const host = group.appendChild(document.createElement("ul"));
      host.id = "memory-confirmed-list";
      host.className = "entry-list";
      const empty = group.appendChild(document.createElement("p"));
      empty.id = "memory-confirmed-empty";
      empty.className = "muted empty-line hidden";
      empty.textContent = "None yet. Confirm a line in Tidy's Patterns and it is listed here.";
      return host;
    };
    //: The list is paged (200 a page); every page is read, so a long list is not cut at the first one without a word.
    const confirmedPages = async () => {
      const items = [];
      let total = Infinity;
      while (items.length < total) {
        const page = await apiJson(`/insights/confirmed?limit=200&offset=${items.length}`);
        if (!page?.items?.length) break;
        items.push(...page.items);
        total = Number.isFinite(page.total) ? page.total : items.length;
      }
      return { items, total: items.length };
    };
    const drawConfirmed = async () => {
      const host = confirmedHost();
      if (!host) return;
      showSkeletons(host, 2, "li");
      //: `lazyScript` answers false on a failed load; either failure is said,
      //: never shown as "None yet" (the review).
      const [data, ready] = await Promise.all([confirmedPages().catch(() => null), lazyScript("/js/confirmed-patterns.js")]);
      clearSkeletons(host);
      const empty = $("memory-confirmed-empty");
      if (empty) {
        empty.dataset.none ??= empty.textContent.trim();
        empty.textContent = data && ready ? empty.dataset.none : "Couldn't load your confirmed patterns.";
        empty.classList.toggle("hidden", Boolean(data && ready && data.items.length));
      }
      host.replaceChildren(
        ...(ready ? data?.items || [] : []).map((item) => {
          const li = document.createElement("li");
          li.className = "entry-item learned-row";
          const text = li.appendChild(document.createElement("p"));
          text.className = "learned-text";
          text.textContent = item.sentence;
          const meta = li.appendChild(document.createElement("p"));
          meta.className = "muted learned-meta";
          const on = item.confirmed_on ? new Date(`${item.confirmed_on}T12:00:00`) : null;
          //: Day then month, as the line itself says it ("as you told me on 5 November").
          meta.append(on ? `Confirmed ${on.getDate()} ${on.toLocaleDateString(undefined, { month: "long" })}` : "Confirmed by you");
          if (item.subject) meta.append(`, about ${item.subject}`);
          const notes = item.notes || [];
          notes.slice(0, 5).forEach((note, i) => {
            meta.append(i ? ", " : `. From ${notes.length === 1 ? "a note" : `${notes.length} notes`}: `);
            //: A word in a sentence that does something is a `.linklike` button, not an `<a href="#">` (DESIGN.md, Plain).
            const open = meta.appendChild(document.createElement("button"));
            open.type = "button";
            open.className = "linklike";
            open.textContent = noteNamePlain(note.title) || "Untitled note";
            open.addEventListener("click", () => {
              closeSettingsModal();
              flashEntry(note.id);
            });
          });
          if (notes.length > 5) meta.append(`, and ${notes.length - 5} more`);
          li.append(rowActions(confirmedPatternItems(item, drawConfirmed), "More for this pattern"));
          return li;
        })
      );
    };
    drawConfirmed();

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
  //: Settings, Appearance, Themes (ledger 1451, 1452; INBOX 1300 C21, the
  //: owner: "if the eye preview buttons are there on the themes then the hover
  //: preview doesn't need to be a thing ... make sure that the preview ...
  //: undoes if the user switches tabs"). The eye in a card's corner shows its
  //: theme on the whole app and holds it under a notice with Apply and Cancel;
  //: closing Settings, another section, leaving the window, Escape or a card
  //: chosen ends it. No hover preview. The preview is `settingsLook.themePreview`
  //: (settings.js), read ahead of the manual layer and never stored.
  function previewTheme(name) {
    if (settingsLook.themePreview === name) return;
    settingsLook.themePreview = name;
    applyAppearance();
    applyThemeChoice(appearancePref("theme"), false);
    applyPalette(appearancePref("palette"), false);
  }
  function releaseThemeHold() {
    settingsControlState.themeHold = "";
    for (const b of document.querySelectorAll("#theme-presets .theme-eye")) {
      b.setAttribute("aria-pressed", "false");
      b.classList.remove("is-on");
    }
    const note = settingsControlState.themeNotice;
    settingsControlState.themeNotice = null;
    if (note) dismissToast(note);
    previewTheme("");
  }
  //: The held preview's notice: the toast recipe with two actions, kept up
  //: until one is pressed (unstamped, so the stack never folds it away).
  function themePreviewNotice(name, label) {
    if (settingsControlState.themeNotice) dismissToast(settingsControlState.themeNotice);
    const box = toastHost();
    const note = document.createElement("div");
    note.className = "toast theme-preview-notice";
    note.setAttribute("role", "status");
    const text = document.createElement("span");
    text.className = "toast-msg";
    text.textContent = `Previewing the ${label} theme.`;
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "small toast-action";
    apply.textContent = "Apply";
    apply.addEventListener("click", () => {
      releaseThemeHold();
      applyThemePreset(name, true);
      renderAppearance();
    });
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost small";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", releaseThemeHold);
    note.append(text, toastActions(apply, cancel));
    settingsControlState.themeNotice = note;
    toastStack(box, () => box.appendChild(note));
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
    eye.addEventListener("click", (event) => {
      event.stopPropagation();
      const wasHeld = settingsControlState.themeHold === name;
      releaseThemeHold();
      if (wasHeld) return;
      settingsControlState.themeHold = name;
      eye.setAttribute("aria-pressed", "true");
      eye.classList.add("is-on");
      previewTheme(name);
      themePreviewNotice(name, label);
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
    //: The ways out that are not the notice's buttons.
    const close = closeSettingsModal;
    closeSettingsModal = function closeSettingsModalEndingPreview() {
      if (settingsControlState.themeHold) releaseThemeHold();
      return close();
    };
    const show = showSettingsSection;
    showSettingsSection = function showSettingsSectionEndingPreview(name) {
      if (settingsControlState.themeHold && name !== currentSettingsSection) releaseThemeHold();
      return show(name);
    };
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && settingsControlState.themeHold) releaseThemeHold();
    });
    //: Capture: a card chosen ends the preview before its own click applies it.
    $("theme-presets")?.addEventListener("click", (event) => {
      if (settingsControlState.themeHold && !event.target.closest?.(".theme-eye")) releaseThemeHold();
    }, true);
  })();
  $("theme-surprise")?.addEventListener("click", () => {
    const active = activeThemePreset();
    const names = Object.keys(THEME_PRESETS).filter((n) => n !== active);
    const pick = names[Math.floor(Math.random() * names.length)];
    applyThemePreset(pick, true);
    renderAppearance();
    toast(`${THEME_PRESETS[pick].label} theme. Press Random theme again for another.`, "info");
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
    //: The button that sent us here is in the pane just left: the keyboard goes
    //: to the filter, which is what the pane now shows (audit 1031 HR21).
    filter.focus({ preventScroll: true });
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
    afterCharacters(() => {
      const { look, reason } = atlasLookReason();
      const from = { "face-looks": "from Face looks", "your-look": "from your own look", default: "main look" }[reason] || "";
      word("atlas-look", from ? `${look}, ${from}` : look, "Matches Face looks when it is one look, otherwise the look you chose for your own face");
    });
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
    ensurePaneTabs(box);
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
    if (box.id === "settings-appearance") ensureAppearancePopOut(box);
    paint();
  }

  //: **A pane's glyph tab row** (INBOX 1478, DESIGN.md "A popup's anatomy"): a
  //: `.pane-tabs` nav in the markup whose buttons name a section by
  //: `data-target`. A press opens the section's fold and goes to it (the pane is
  //: one scroll, so nothing is hidden and Find, "On this page" and Expand all
  //: still reach everything); a fold opened by anything else marks its tab.
  function ensurePaneTabs(box) {
    const nav = box?.querySelector(":scope > .pane-tabs");
    if (!nav || nav.dataset.wired) return;
    nav.dataset.wired = "1";
    ensureModule("popupAnatomy");
    const tabs = [...nav.querySelectorAll("button[data-target]")];
    const aim = (tab) => box.querySelector(tab.dataset.target);
    const mark = (on) => tabs.forEach((tab) => {
      tab.classList.toggle("active", tab === on);
      tab.setAttribute("aria-current", String(tab === on));
    });
    for (const tab of tabs) {
      tab.addEventListener("click", () => {
        const el = aim(tab);
        if (!el) return;
        if (el.matches("details")) el.open = true;
        mark(tab);
        el.scrollIntoView({ block: "start", behavior: reducedMotionWanted() ? "auto" : "smooth" });
        if (tab.dataset.focus) $(tab.dataset.focus)?.focus({ preventScroll: true });
      });
    }
    box.addEventListener("toggle", (event) => {
      const hit = tabs.find((tab) => aim(tab) === event.target);
      if (hit && event.target.open) mark(hit);
    }, true);
    mark(tabs[0]);
  }

  //: The Pop out button at the top of Settings, Appearance: the same controls in
  //: a panel beside the app (appearance-panel.js, INBOX 1435).
  function ensureAppearancePopOut(box) {
    const actions = box.querySelector(":scope > .settings-pane-title .dock-actions");
    if (!actions || actions.querySelector("[data-pop-out]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small";
    button.dataset.popOut = "appearance";
    button.title = "Open Appearance in a panel beside the app, so you see each change without closing Settings";
    setLabel(button, "ph:arrow-square-out Pop out");
    button.addEventListener("click", () => openAppearancePanel());
    actions.insertBefore(button, actions.firstChild);
  }

  //: **A model per feature, the list in Settings, Models** (moved here from
  //: ai-tools.js: only the open Settings window draws it). `renderFeatureModels`
  //: keeps the state the rest of the app reads and calls this.
  function renderFeatureModelRows(status) {
    const list = $("feature-models-list");
    //: **Only when something moved.** The status poll asks every three seconds
    //: while Settings is open, and every answer rebuilt each row and its
    //: enhanced select (20 rows and 34 menus replaced during a 40-step scroll
    //: of Help), invalidating the page under whatever was being scrolled.
    const sig = JSON.stringify([featureModelRows, featureModelNames, featureModelFollow, status.feature_models_overridden]);
    if (!list || list.dataset.sig === sig) return;
    list.dataset.sig = sig;
    list.replaceChildren();
    list.removeAttribute("aria-busy");
    for (const row of featureModelRows) {
      const line = document.createElement("div");
      line.className = "feature-model-row";
      line.dataset.feature = row.key;
      //: Read by the stylesheet, which tints the state line of a row that is on
      //: a model of its own: the list's only job is to make those findable.
      line.dataset.overridden = row.overridden ? "1" : "0";

      const name = document.createElement("div");
      name.className = "feature-model-name";
      const label = document.createElement("span");
      label.className = "feature-model-label";
      label.textContent = row.label;
      const state = document.createElement("span");
      state.className = "feature-model-state";
      state.textContent = featureModelState(row);
      state.title = row.note || "";
      name.append(label, state);

      const select = document.createElement("select");
      select.setAttribute("aria-label", `Model for ${row.label}`);
      select.title = `Model for ${row.label}`;
      //: The "inherited" option names what it inherits, so the list can be read
      //: without opening anything: every row says which model it is on. The two
      //: "Same as ..." options (INBOX 430) are the sentinels themselves, so
      //: picking one round-trips to `applyFeatureModel` unchanged and the
      //: backend stores the sentinel, not a name that would go stale the next
      //: time that role's model changes.
      let savedValue = "";
      if (row.override_kind === "model") savedValue = row.override_value;
      else if (row.override_kind === "chat") savedValue = featureModelFollow.chat;
      else if (row.override_kind === "utility") savedValue = featureModelFollow.utility;
      fillModelSelect(
        select,
        featureModelNames,
        [
          { value: "", label: `Inherited: ${row.inherits}` },
          { value: featureModelFollow.chat, label: "Same as chat model" },
          { value: featureModelFollow.utility, label: "Same as utility model" },
        ],
        savedValue
      );
      select.addEventListener("change", () => applyFeatureModel(row.key, select.value));

      //: Disabled until the row is overridden, because a reset on a row that is
      //: already on its default is a control that does nothing when pressed.
      const reset = smallButton(
        "ph:arrow-counter-clockwise",
        row.overridden
          ? `Reset ${row.label} to the model it inherits`
          : `${row.label} is already on the model it inherits`,
        () => applyFeatureModel(row.key, "")
      );
      //: Named, because `enhanceSelect` wraps the select beside it in a shell
      //: with a button of its own: "the first button in the row" stopped being
      //: this one the moment the select was enhanced.
      reset.classList.add("icon-only", "feature-model-reset");
      reset.disabled = !row.overridden;

      line.append(name, select, reset);
      list.appendChild(line);
    }

    const count = Number(status.feature_models_overridden || 0);
    const reset = $("feature-models-reset");
    const note = $("feature-models-reset-note");
    if (reset) {
      //: The mass reset says how many it would clear and does nothing when the
      //: answer is none, rather than reporting success over a no-op.
      reset.disabled = count === 0;
      reset.title = count
        ? `Hand ${count === 1 ? "one feature" : `${count} features`} back to the model they inherit`
        : "No feature has a model of its own yet";
    }
    if (note) {
      note.textContent = count === 0
        ? "No feature has a model of its own yet."
        : count === 1
          ? "One feature is on a model of its own."
          : `${count} features are on models of their own.`;
    }
  }

  //: This file arrives after the first Appearance render, so label once now.
  renderAutoChoices();
  renderSmallModelAuto();

  async function renderAccount() {
    const facts = $("account-facts");
    facts.replaceChildren();
    showSkeletons(facts, 3, "li");
    const info = await apiJson("/auth/account").catch(() => null);
    clearSkeletons(facts);
    if (!info) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Couldn't read the account state.";
      facts.appendChild(li);
      return;
    }
    const rows = [
      ["Password", info.configured ? "Set" : "Not set yet"],
      [
        "Created",
        info.created_at ? new Date(info.created_at).toLocaleDateString() : "Unknown",
      ],
      [
        "Private notes",
        info.vault_exists
          ? info.vault_open
            ? "Encryption key loaded: private notes are readable"
            : "Locked: unlock to read private notes"
          : "No encrypted notes yet",
      ],
      ["Open sessions", String(info.active_sessions)],
      //: INBOX 663: the recovery key's row and its one button, drawn by
      //: account-recovery.js (lazy: the boot scripts' total cap).
      await recoveryAccountRow(info),
    ];
    if (typeof info.vault_open === "boolean") vaultOpen = info.vault_open;
    $("account-password-on-open").checked = info.password_on_open !== false;
    renderPinSettings(info.pin);
    //: "Unlock with Windows Hello", beside the PIN (hello-unlock.js).
    if (info.hello) privateSpaces("hello", "settings", info.hello);
    renderLanAccess().catch(() => {});
    for (const [label, value] of rows) {
      //: A label column and a value column (`.account-facts`), not "Label: value"
      //: in bold run-in: four facts read as a table, so they are laid out as one.
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "account-fact-label";
      name.textContent = label;
      const text = document.createElement("span");
      text.textContent = value;
      li.append(name, text);
      facts.appendChild(li);
    }
  }

  //: "PIN for this computer" (owner, 2026-10-12): the fields show only where a
  //: PIN can be set, which is this computer with an OS protected store; the
  //: line under the heading says why when it cannot.
  function renderPinSettings(pin) {
    const state = $("account-pin-state");
    if (!state || !pin) return;
    const usable = pin.available && pin.here;
    $("account-pin-fields").classList.toggle("hidden", !usable);
    $("account-pin-set").classList.toggle("hidden", !usable);
    $("account-pin-set").textContent = pin.set ? "Change PIN" : "Set up a PIN for this computer";
    $("account-pin-forget").classList.toggle("hidden", !(pin.set && pin.here));
    if (!pin.here) {
      state.textContent = "A PIN can be set up only on the computer this notebook runs on.";
    } else if (!pin.available) {
      state.textContent = "This computer has no protected store for a PIN, so the password is the only way in here.";
    } else {
      state.textContent = pin.set
        ? "A PIN is set: the lock screen takes it or your password, on this computer only."
        : "Unlock on this computer with a few digits instead of your password.";
    }
  }

  // The review panel for the background librarian (ROADMAP §40 item 2).
  //
  // A true dry-run is not available here, the agent picks each call from the
  // result of the last one, so a pass with the writes stubbed out stops
  // resembling the pass that would really run, and a preview that lies is worse
  // than no preview. What is available is honest and nearly as useful: every
  // write already captured the call that reverses it, so the pass can be read
  // back and undone one item at a time. `changeRow` is the same renderer the
  // chat uses for a skill's result, so Undo here goes through exactly the path
  // the chat's own Undo buttons do.
  async function renderAutonomousReview() {
    const box = $("autonomous-review");
    const list = $("autonomous-review-list");
    if (!box || !list) return;

    const pass = await apiJson("/tasks/autonomous/last").catch(() => null);
    const changes = pass?.changes || [];
    box.classList.toggle("hidden", changes.length === 0);
    if (!changes.length) return;

    const when = pass.finished_at ? whenText(pass.finished_at) : "";
    $("autonomous-review-title").textContent =
      `What the last run changed, ${changes.length} thing(s)` + (when ? `, ${when}` : "");
    list.replaceChildren(...changes.map((change) => changeRow(change)));
  }

  async function renderToolSettings() {
    renderMcpSnippet();
    const list = $("tool-list");
    showSkeletons(list, 4, "li");
    const [catalog, prefs] = await Promise.all([
      apiJson("/chat/tools").catch(() => []),
      apiJson("/preferences").catch(() => ({ disabled_tools: [] })),
    ]);
    clearSkeletons(list);
    prefsCache = prefs;
    renderToolFocus(prefs.tool_focus || "auto");
    renderSmallModelMode(prefs.small_model_mode || "auto");
    renderRunBudget(prefs);
    const disabled = new Set(prefs.disabled_tools || []);
    list.replaceChildren();
    //: Grouped by what a tool does to the notebook (CHAT_PLAN, INBOX 71: "a
    //: grouped table (read, write, destructive)"), each group under an
    //: `h4.setting-subhead` (DESIGN.md: a subdivision inside a group) that
    //: spans both columns. Within a group, the catalog's own order.
    for (const [key, title] of TOOL_GROUPS) {
      const members = catalog.filter((t) => (t.group || "read") === key);
      if (!members.length) continue;
      const head = document.createElement("li");
      head.className = "tool-group-head";
      head.dataset.group = key;
      const h4 = document.createElement("h4");
      h4.className = "setting-subhead";
      h4.textContent = title;
      head.append(h4);
      //: One switch for the group (audit 1031 HR14: seventy-two switches in ten groups).
      const all = document.createElement("button");
      all.type = "button";
      all.className = "linklike tool-group-all";
      all.addEventListener("click", () => saveToolGroup(head));
      head.append(all);
      list.append(head);
      for (const tool of members) appendToolRow(list, tool, disabled, key);
    }
    applyToolFilter();
  }

  //: Moved here from skills.js (audit 1031, the boot gzip budget): Tools and features is
  //: the only caller of every function below.
  // --- Wave O: agent-tools toggles ----------------------------------------------------

  // How many tool descriptions each message carries (§11a). Saved on change
  // rather than behind an Apply button, the search-engine picker taught us
  // that a control which saves nothing until later reads as broken, because
  // the next status poll paints the old value back over it.
  function renderToolFocus(current) {
    for (const radio of document.querySelectorAll('input[name="tool-focus"]')) {
      radio.checked = radio.value === current;
      radio.onchange = async () => {
        if (!radio.checked) return;
        const status = $("tool-focus-status");
        status.textContent = "Saving…";
        prefsCache = await apiJson("/preferences", {
          method: "PUT",
          body: JSON.stringify({ tool_focus: radio.value }),
        });
        status.textContent =
          radio.value === "auto"
            ? "Each message is offered the tools it needs."
            : "Every message is offered every tool.";
      };
    }
  }

  //: **The Phase B setting, given the control it never had.** `small_model_mode`
  //: has been on GET/PUT /preferences since the skills reform's backend half,
  //: read by the chat route on every run, with nothing anywhere in the app that
  //: could change it, so every notebook ran on `auto` whatever its owner wanted.
  //: Saved on change for the same reason the tool-focus radios above are: a
  //: control that waits for an Apply button reads as broken here, because the
  //: next preferences render paints the old value back over it.
  function renderSmallModelMode(current) {
    const select = $("small-model-mode");
    if (!select) return;
    select.value = current || "auto";
    renderSmallModelAuto();
  }

  //: **The run budget** (Brief 13), the same shape as the two controls above:
  //: saved on change, because a control that waits for an Apply button reads as
  //: broken here, the next preferences render paints the old value back over it.
  //: Both fields together in one request, so a person who edits one and then the
  //: other does not race two writes of the same preferences file.
  function renderRunBudget(prefs) {
    const tokens = $("run-budget-tokens");
    const seconds = $("run-budget-seconds");
    if (tokens) tokens.value = String(prefs.run_budget_tokens ?? 20000);
    if (seconds) seconds.value = String(prefs.run_budget_seconds ?? 90);
  }

  //: One tool's switch, saved. A refused save puts the switch back and says why:
  //: the handler used to `await` with nothing to catch it, so a 422 was an
  //: unhandled rejection and the switch stayed where the server disagreed (found
  //: by the deepflows sweep, which turned all the tools off).
  async function saveToolSwitch(check, name) {
    const next = new Set(prefsCache.disabled_tools || []);
    if (check.checked) next.delete(name);
    else next.add(name);
    try {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ disabled_tools: [...next] }),
      });
    } catch (error) {
      check.checked = !check.checked;
      toast(error.message || "Couldn't save that tool setting. Try again.", true);
      return;
    }
    // The "N of 51 on" count is only true until someone flips one.
    applyToolFilter();
  }

  //: The boxes a group's switch acts on: its rows on screen, so a filter is never
  //: overstepped, and not the one the web opt-in holds off.
  function toolGroupBoxes(key) {
    const rows = $("tool-list")?.querySelectorAll(`:scope > li[data-tool][data-group="${key}"]`) || [];
    return [...rows]
      .filter((row) => !row.classList.contains("hidden"))
      .map((row) => row.querySelector("input[type=checkbox]"))
      .filter((check) => check && !check.disabled);
  }

  //: The group switch says what a press does now: off while any is on, else on.
  function toolGroupAllPaint(head) {
    const button = head.querySelector(".tool-group-all");
    if (!button) return;
    const boxes = toolGroupBoxes(head.dataset.group);
    const words = boxes.some((check) => check.checked) ? "Turn all off" : "Turn all on";
    button.hidden = !boxes.length;
    button.textContent = words;
    button.setAttribute("aria-label", `${words} in ${head.querySelector("h4").textContent}`);
  }

  //: A group in one save; the boxes follow the answer and a failure leaves them as they were.
  async function saveToolGroup(head) {
    const boxes = toolGroupBoxes(head.dataset.group);
    if (!boxes.length) return;
    const turnOn = !boxes.some((check) => check.checked);
    const next = new Set(prefsCache.disabled_tools || []);
    for (const check of boxes) {
      const name = check.closest("li").dataset.tool;
      if (turnOn) next.delete(name);
      else next.add(name);
    }
    try {
      prefsCache = await apiJson("/preferences", {
        method: "PUT",
        body: JSON.stringify({ disabled_tools: [...next] }),
      });
    } catch (error) {
      toast(error.message || "Couldn't save those tool settings. Try again.", true);
      return;
    }
    for (const check of boxes) check.checked = turnOn;
    applyToolFilter();
  }

  //: The four groups, in the order a person scanning for risk reads them.
  const TOOL_GROUPS = [
    ["read", "Reads your notebook"],
    ["write", "Changes your notebook"],
    ["confirm", "Asks you first"],
    ["online", "Reaches the web"],
  ];

  function appendToolRow(list, tool, disabled, group) {
    const li = document.createElement("li");
    li.dataset.group = group;
    //: What a Tools and features row for this tool lands on (`ai-tool` in
    //: REVEAL_TARGETS).
    li.dataset.tool = tool.name;
    const label = document.createElement("label");
    label.className = "tool-row setting-check";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = !disabled.has(tool.name);
    // web_search is gated by the separate online opt-in, show why it's off.
    if (tool.online && !tool.enabled && !disabled.has(tool.name)) {
      check.checked = false;
      check.disabled = true;
      check.title = "Enable web search in Preferences first";
    }
    check.addEventListener("change", () => saveToolSwitch(check, tool.name));
    const text = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = tool.name.replace(/_/g, " ");
    text.append(name);
    // The chips sit on their own line under the name, not after it on the
    // same one: the switch is centred on the name's line (the grid in
    // 03-dashboard-widgets.css), and a chip that wrapped would have made
    // that line two lines tall and pulled the switch off the name again.
    if (tool.destructive || tool.online) {
      const tags = document.createElement("span");
      tags.className = "tool-tags";
      if (tool.destructive) tags.append(chip("confirms first", "item-label is-warn"));
      if (tool.online) tags.append(chip("online", "item-label"));
      text.append(tags);
    }
    const desc = document.createElement("span");
    desc.className = "muted tool-desc";
    desc.textContent = tool.description;
    desc.title = tool.description || ""; // clamped to two lines; the whole of it on hover
    // The description goes *inside* the label's text column, not beside the
    // label in the <li>. That is what lets this row be `.setting-check`'s
    // grid, name and description stacked in column one, switch hard right , 
    // instead of a flex row whose switch tracked the length of each name.
    // It also makes the description part of the control's own hit area, the
    // way the hint under every other setting already is.
    text.append(desc);
    label.append(check, text);
    li.append(label);
    // Matched against by the filter below. Stored on the row rather than
    // re-read from the DOM on every keystroke, and lower-cased once here
    // instead of once per row per keystroke.
    li.dataset.search = `${tool.name} ${tool.description || ""}`.toLowerCase().replace(/_/g, " ");
    list.appendChild(li);
  }

  //: Narrow a fifty-one item list, and say how many are on.
  //:
  //: The first audit of Settings measured this section at **5,708px**, by some
  //: way the longest scroll in the app, with every tool a name plus a
  //: paragraph of description. Finding one meant scrolling past fifty others,
  //: and nothing anywhere answered the question the list actually raises: how
  //: many of these are switched on?
  //:
  //: Filtering hides rows rather than re-rendering them, so a checkbox keeps
  //: its state and its listener while you type. Re-rendering would also lose
  //: focus from the filter field on every keystroke.
  function applyToolFilter() {
    const list = $("tool-list");
    const box = $("tool-filter");
    const count = $("tool-count");
    const empty = $("tool-filter-empty");
    if (!list) return;
    const needle = (box?.value || "").trim().toLowerCase();
    const rows = [...list.querySelectorAll(":scope > li[data-tool]")];
    let shown = 0;
    const groupsShown = new Set();
    for (const row of rows) {
      const hit = !needle || (row.dataset.search || "").includes(needle);
      row.classList.toggle("hidden", !hit);
      if (hit) {
        shown++;
        groupsShown.add(row.dataset.group);
      }
    }
    //: A group's head goes with its last matching row.
    for (const head of list.querySelectorAll(":scope > li.tool-group-head")) {
      head.classList.toggle("hidden", !groupsShown.has(head.dataset.group));
      toolGroupAllPaint(head);
    }
    empty?.classList.toggle("hidden", shown > 0 || !rows.length);
    if (count) {
      // Two different questions, so two different answers: with no filter the
      // useful number is how many are enabled; while filtering it is how many
      // the search actually found.
      const on = rows.filter((r) => r.querySelector("input[type=checkbox]")?.checked).length;
      count.textContent = needle
        ? `${shown} of ${rows.length}`
        : `${on} of ${rows.length} on`;
    }
  }

  // ---- from settings.js, settings-wiring.js and settings-panes.js (INBOX 1501) ----
  // The statements below sat in the boot files and asked for controls inside the
  // body at load, which would have built the 2,700-node body at every boot. They
  // run here, with the first open, after the body exists, in the order they ran.

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
  for (const key of ["read-leading", "read-measure"]) {
    $(key).addEventListener("change", (e) => {
      prefs.set(key, e.target.value);
      applyAppearance();
      renderAppearance();
    });
  }
  $("perf-mode").addEventListener("change", (e) => {
    prefs.set("perf", e.target.value);
    applyAppearance();
    renderAppearance();
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
  //: Using a glass setting while the glass is off turns the glass on (and the
  //: sheen, for its strength): a dimmed row is a hint, not a wall
  //: (`renderGlassRows`, settings.js). Repaints the rows only when it woke one.
  function glassWake(sheen = false) {
    const wake = [["glass", true], ["glass-sheen", sheen]].filter(([key, want]) => want && appearancePref(key) !== "on");
    for (const [key] of wake) prefs.set(key, "on");
    if (wake.length) renderAppearance();
  }
  $("glass-sheen-toggle").addEventListener("change", (e) => {
    prefs.set("glass-sheen", e.target.checked ? "on" : "off");
    if (e.target.checked) glassWake();
    applyAppearance();
    renderGlassRows();
  });
  $("glass-controls-toggle").addEventListener("change", (e) => {
    prefs.set("glass-controls", e.target.checked ? "on" : "off");
    if (e.target.checked) glassWake();
    applyAppearance();
  });
  $("glass-sheen-strength").addEventListener("input", (e) => {
    prefs.set("glass-sheen-strength", e.target.value);
    $("glass-sheen-strength-value").textContent = `${e.target.value}%`;
    glassWake(true);
    applyAppearance();
  });
  for (const btn of document.querySelectorAll("#motion-seg button")) {
    btn.addEventListener("click", () => {
      const off = btn.dataset.motionChoice === "off";
      prefs.set("motion", btn.dataset.motionChoice);
      // The background-art picker has its own "Moving" override (see
      // startBgArt()'s comment). Choosing Off here is a direct, explicit ask
      // for stillness, and "Moving" silently surviving it read as the two
      // settings being unrelated: Off selects "Still"; leaving Off only clears
      // that if we set it, so an independent "Moving" choice isn't clobbered.
      if (off) {
        prefs.set("bg-motion", "still");
      } else if (appearancePref("bg-motion") === "still") {
        prefs.set("bg-motion", "auto");
      }
      if ($("bg-motion")) $("bg-motion").value = appearancePref("bg-motion");
      applyAppearance();
      renderAppearance();
      if (reducedMotionWanted()) stopBgArt(); // a still UI shouldn't keep the art running
      else if (bgArtOn()) startBgArt();
      renderBrandLogo(); // start/stop the emblem's rotation to match
    });
  }

  $("ui-motion-toggle").addEventListener("change", (e) => {
    prefs.set("ui-motion", e.target.checked ? "on" : "off");
    applyAppearance();
  });
  $("bg-intensity").addEventListener("input", (e) => {
    prefs.set("bg-intensity", e.target.value);
    $("bg-intensity-value").textContent = `${e.target.value}%`;
    // Using it while the art is off turns the art on (`.dependent-off`, settings.js).
    if (!bgArtOn()) {
      toggleBgArt(true);
      renderAppearance();
    }
    applyAppearance();
    startBgArt(); // intensity also drives particle density
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
    glassWake();
    applyAppearance();
  });
  $("glass-opacity").addEventListener("input", (e) => {
    prefs.set("glass-opacity", e.target.value);
    $("glass-opacity-value").textContent = `${e.target.value}%`;
    glassWake();
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
  //: Motion at rest (atlas-life.js, `atlasTailCalm.rest.holds`): read once a second, so the choice is taken up within a second.
  $("avatar-buddy-rest").addEventListener("change", (e) => {
    try {
      prefs.set("avatar-buddy-rest", e.target.value);
    } catch (err) {
      // For this visit only.
    }
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

  $("harmony-apply").addEventListener("click", applyHarmony);
  $("custom-theme-save").addEventListener("click", () => {
    saveCurrentLook().catch((error) => toast(error.message, true));
  });
  $("custom-theme-name").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("custom-theme-save").click();
  });
  $("look-surprise").addEventListener("click", () => settingsLook.lookFile.surpriseNow());
  $("look-export").addEventListener("click", () => settingsLook.lookFile.exportNow());
  $("look-import").addEventListener("click", () => pickJsonFile("look-import-file", (data) => settingsLook.lookFile.importNow(data)));

  $("log-source").addEventListener("change", renderActiveLogView);
  $("log-level").addEventListener("change", renderActiveLogView);
  $("log-requests").addEventListener("change", renderActiveLogView);

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
  //: Live records draw together, at most four times a second, not once each: every request is a
  //: log line, and each draw rebuilt up to 500 rows and laid them out (190ms of forced layout at
  //: 4x across the draws on opening Logs, INBOX 1111). `toBottom` is the browser's own errors.
  renderActiveLogView.soon = (toBottom) => {
    renderActiveLogView.bottom ||= toBottom;
    renderActiveLogView.frame ||= setTimeout(() => {
      renderActiveLogView.frame = 0;
      renderActiveLogView();
      if (renderActiveLogView.bottom) scrollLogToBottom();
      renderActiveLogView.bottom = false;
    }, 250);
  };
  //: Only drawn with the Logs section open, which is after this file is in (settings.js: renderLogs).

  //: The read waits for a timer past the frame (the stream appends rows between scrolls, and
  //: reading `scrollHeight` right after laid the whole list out: 120ms in the handler at 4x).
  for (const id of ["log-list", "log-terminal"]) {
    let queued = false;
    $(id).addEventListener("scroll", () => {
      if (queued || !$("log-follow").checked) return;
      queued = true;
      afterFrames(() => setTimeout(() => {
        queued = false;
        logFollowPinned = nearLogBottom();
        $("log-follow-label").classList.toggle("is-paused", !logFollowPinned);
      }), 1);
    }, { passive: true });
  }

  //: Reading up draws the next window of older records at once (INBOX 1608); they are held in
  //: memory for the session, so the list never has to ask for them twice.
  $("log-list").addEventListener("scroll", (event) => {
    const list = event.currentTarget;
    if (list.scrollTop < 80) list.querySelector(":scope > li:first-child > button")?.click();
  });
  //: Re-reads the server's records now: for when Follow is off, or the stream is reconnecting.
  $("logs-refresh").addEventListener("click", async () => {
    const button = $("logs-refresh");
    setBusy(button, true);
    await renderLogs();
    setBusy(button, false);
    toast("Log refreshed.");
  });

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

  //: The persona hint's "(Atlas)" follows the name too.
  {
    const hint = document.getElementById("persona-placeholder-hint");
    if (hint) hint.textContent = `Write {ai_name} where the name should go and it is replaced with ${AI_NAME}. Optional.`;
  }

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
    //: Answers marked not right (L225): a count and one button, kept only on this device.
    const marks = (await apiJson("/learned/answer-verdicts").catch(() => null))?.count || 0;
    let row = line.parentElement.querySelector(".learned-not-right");
    if (!marks) return void row?.remove();
    if (!row) {
      row = document.createElement("p");
      row.className = "muted row learned-not-right";
      line.after(row);
    }
    const clear = smallButton("ph:eraser Clear answers marked not right", "Forget every answer you marked not right", async () => {
      await api("/learned/answer-verdicts", { method: "DELETE" });
      renderLearnedFromYou();
    }, true);
    row.replaceChildren(`${nounCount(marks, "answer mark")} kept on this device. `, clear);
  }

  async function renderLearned() {
    //: The list first, so the switches' "N things kept" line has a number.
    await renderLearnedList();
    await renderLearnedSwitches();
    await renderLearnedFromYou();
  }

  wireLearnedSection();

  wirePrefsDirtyMarks();

  // Mark a picker as "user has a pending choice" so the status poll stops
  // resetting it (Wave N bug fix).
  for (const id of ["chat-model-select", "embedding-model-select"]) {
    $(id).addEventListener("change", () => ($(id).dataset.userChosen = "1"));
  }
  for (const radio of document.querySelectorAll('input[name="emb-backend"]')) {
    radio.addEventListener("change", () => {
      $("embedding-model-select").dataset.userChosen = "1";
      // The radio itself needs the latch too: the choice isn't saved until
      // "Apply & re-index", and without this the next status poll put the old
      // backend back the instant focus left the radio.
      radio.dataset.userChosen = "1";
      //: The picker's enabled state follows the radio immediately rather than
      //: waiting for the next status poll: choosing Ollama and finding the
      //: model list still greyed for a second reads as the choice not having
      //: taken. It says which backend is *selected*, which is the question the
      //: control is about; whether it is applied is what Apply is for.
      syncEmbeddingPickerState();
      if (radio.checked && radio.value === "fastembed") applyEmbeddingBackend();
    });
  }

  $("about-install")?.addEventListener("click", async () => {
    const offered = installPrompt.event;
    if (!offered) return;
    installPrompt.event = null; // the event can be used once
    offered.prompt();
    await offered.userChoice.catch(() => {});
    renderInstallRow();
  });

  $("pref-single-keys").checked = singleKeysOn();

  for (const button of document.querySelectorAll("#privacy-range [data-range]")) {
    button.addEventListener("click", () => {
      privacyRange = button.dataset.range;
      renderPrivacyRange();
    });
  }


  // ---- Check what it learned (CHAT_PLAN decision 68) ----
  //
  // The button on What it learned's bar runs `POST /learned/audit/run`: every
  // open claim and question is re-read against its note, what no longer holds is
  // retired (a tombstone, with its reason) or flagged. Here, and not in the boot
  // files, because the panel cannot be seen before Settings opens. What a check
  // retired, a scheduled one included, is read back from `GET /learned/audit/last`
  // so its Undo is in the panel whoever ran it; a flag is a mark on the list's row.
  const LEARNED_CHECK = { flags: {}, loaded: false };

  function learnedCheckSentence(words) {
    const text = String(words || "").trim();
    return text ? `${text.charAt(0).toUpperCase()}${text.slice(1)}.` : "";
  }

  function learnedCheckLine(item) {
    const li = document.createElement("li");
    li.className = "entry-item learned-row";
    const text = document.createElement("p");
    text.className = "learned-text";
    text.textContent = item.text;
    const why = document.createElement("p");
    why.className = "muted learned-meta";
    why.textContent = `Retired: ${item.reason}`;
    li.append(text, why);
    return li;
  }

  //: The box: the sentence, what the last check retired, and its Undo.
  function learnedCheckShow(last, summary) {
    const box = $("learned-check-result");
    if (!box) return;
    const retired = last?.retired || [];
    const flagged = Object.keys(LEARNED_CHECK.flags).length;
    let words = summary;
    if (!words && retired.length) words = `The last check retired ${nounCount(retired.length, "thing")}.`;
    if (!words && flagged) words = `${nounCount(flagged, "thing is", "things are")} flagged below for your eye.`;
    box.classList.toggle("hidden", !words);
    $("learned-check-summary").textContent = words || "";
    $("learned-check-list").replaceChildren(...retired.map(learnedCheckLine));
    const undo = $("learned-check-undo");
    undo.classList.toggle("hidden", !retired.length);
    undo.dataset.run = last?.run || "";
    undo.dataset.count = String(retired.length);
  }

  //: A flagged row says why, beside its own words.
  function learnedCheckMark() {
    for (const li of document.querySelectorAll("#learned-list [data-fact-id]")) {
      const reason = LEARNED_CHECK.flags[li.dataset.factId];
      if (!reason || li.querySelector(".learned-flag")) continue;
      const note = document.createElement("p");
      note.className = "muted learned-meta learned-flag";
      note.textContent = `Check this: ${reason}`;
      li.appendChild(note);
    }
  }

  async function learnedCheckRefresh(summary = "") {
    const last = await apiJson("/learned/audit/last").catch(() => null);
    const flags = await apiJson("/learned/audit/flags").catch(() => null);
    LEARNED_CHECK.flags = flags?.flags || {};
    learnedCheckShow(last, summary);
    learnedCheckMark();
  }

  async function learnedCheckRun() {
    const button = $("learned-check");
    button.disabled = true;
    const refresh = () => {
      renderLearnedList();
      return learnedCheckRefresh();
    };
    try {
      const done = await apiJson("/learned/audit/run", { method: "POST" });
      const run = { run: done.run };
      if (done.retired.length) {
        pushRoutePairUndo(
          `Check what it learned, ${nounCount(done.retired.length, "thing")} retired`,
          ["/learned/audit/undo", "POST", run],
          ["/learned/audit/redo", "POST", run],
          refresh
        );
      }
      await learnedCheckRefresh(learnedCheckSentence(done.summary));
      renderLearnedList();
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  //: The box's Undo: put back what the last check retired, whoever ran it, and
  //: leave a step on the stack that retires it again.
  async function learnedCheckPutBack() {
    const button = $("learned-check-undo");
    const run = { run: button.dataset.run };
    const count = Number(button.dataset.count) || 0;
    const post = (path) => apiJson(path, { method: "POST", body: JSON.stringify(run) });
    const refresh = () => {
      renderLearnedList();
      return learnedCheckRefresh();
    };
    try {
      await post("/learned/audit/undo");
    } catch (error) {
      toast(error.message, true);
      return;
    }
    pushUndo(
      `Put back ${nounCount(count, "thing")} the check retired`,
      async () => {
        await post("/learned/audit/redo");
        await refresh();
      },
      async () => {
        await post("/learned/audit/undo");
        await refresh();
      }
    );
    toast(`Put back ${nounCount(count, "thing")}.`);
    await refresh();
  }

  $("learned-check")?.addEventListener("click", learnedCheckRun);
  $("learned-check-undo")?.addEventListener("click", learnedCheckPutBack);
  //: The list is drawn on every filter, page and edit (`renderLearnedList`, a
  //: boot file that cannot know this one): the draw is wrapped, so the marks
  //: follow it, and the first draw reads what the last check did (a scheduled
  //: one too). A wrapper and not a MutationObserver: nothing here may add a wake source.
  const learnedListDrawn = renderLearnedList;
  renderLearnedList = async function renderLearnedListMarked() {
    const drawn = await learnedListDrawn();
    if (LEARNED_CHECK.loaded) learnedCheckMark();
    else {
      LEARNED_CHECK.loaded = true;
      await learnedCheckRefresh();
    }
    return drawn;
  };

  async function applyEmbeddingBackend() {
    const backend = document.querySelector('input[name="emb-backend"]:checked')?.value;
    const model = $("embedding-model-select").value || null;
    if (!backend) return;
    // Guard the #1 misconfiguration: a chat model chosen as the search engine.
    if (backend === "ollama") {
      if (!model) {
        toast("Pick an embedding model first, e.g. nomic-embed-text.", "info");
        return;
      }
      if (!looksLikeEmbeddingModel(model)) {
        const proceed = (await confirmDialog(
          `"${model}" doesn't look like an embedding model. Chat models can't create ` +
            "embeddings, so semantic search will fail (Ollama returns 501). Download and " +
            "pick a dedicated embedding model like nomic-embed-text instead.\n\nApply anyway?"
        ));
        if (!proceed) return;
      }
    }
    const ok = (await confirmDialog(
      `Switching the search engine re-indexes all ${allEntries.length} of your ` +
        "notes so search keeps making sense. Notes and keyword search stay " +
        "available while it runs. Continue?"
    ));
    if (!ok) {
      // Backing out puts the saved backend back on screen, rather than leaving
      // a radio selected for a switch that never happened.
      clearEmbeddingBackendLatch();
      refreshModelStatus();
      return;
    }
    try {
      await api("/models/embedding-backend", {
        method: "POST",
        body: JSON.stringify({ backend, model: backend === "ollama" ? model : null }),
      });
      clearEmbeddingBackendLatch(); // applied: polling may reflect it again
      refreshModelStatus();
    } catch (error) {
      toast(error.message, true);
    }
  }

  //: Moved here from the boot files (W27): only this file calls them.
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

  function applyContrast(on) {
    if (on) document.documentElement.dataset.contrast = "on";
    else delete document.documentElement.dataset.contrast;
    prefs.set("contrast", on ? "on" : "off");
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

  function nearLogBottom() {
    const list = activeLogContainer();
    // 40px of slack: "close enough to the bottom that you meant to be there".
    return list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  }

  // Let the status poll own the radios again. Called once a choice is applied,
  // and when the user backs out of applying it, otherwise a cancelled switch
  // would leave the radio showing a backend that was never saved, which is the
  // same lie in the opposite direction.
  function clearEmbeddingBackendLatch() {
    delete $("embedding-model-select").dataset.userChosen;
    for (const radio of document.querySelectorAll('input[name="emb-backend"]')) {
      delete radio.dataset.userChosen;
    }
  }

  // Heuristic: does this Ollama model look like it can produce embeddings?
  // Chat/generation models can't, Ollama answers /api/embed with 501, and
  // picking one by mistake is the #1 way people break the search engine.
  function looksLikeEmbeddingModel(name) {
    return /embed|minilm|bge|gte|e5|arctic/i.test(name || "");
  }

  //: The Skills pane's list, moved from skills.js on 2026-11-12 (the boot-script gzip
  //: cap): only the pane and a save after a gesture draw it, and `saveSkillList`'s call
  //: reaches it through its stand-in (`LAZY_ENTRY_POINTS`, app.js).
  function skillRow(skill) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "entry-meta skill-row";
    //: A title, a label and facts, not six pills of one weight (owner: "there
    //: is still missing distinguishing between titles that used to be
    //: badges"). The recipe is `.item-title`, `.item-label` and `.item-fact`
    //: in 08-consistency.css, shared with the personas.
    row.appendChild(chip(skill.name, "item-title"));
    if (skill.builtin) row.appendChild(chip("Built-in", "item-label"));
    if (skill.folder) {
      const from = chip("From the skills folder", "item-label");
      from.title = `The file ${skill.file}; edit or delete it there`;
      row.appendChild(from);
    }
    if (skill.changes) row.appendChild(chip("ph:pencil-simple Changes notes", "item-fact item-writes"));
    if (skill.needs_larger_model) {
      const larger = chip("Needs a larger model", "item-fact");
      larger.title = skill.needs_larger_model;
      row.appendChild(larger);
    }
    if ((skill.steps || []).length) {
      row.appendChild(chip(nounCount(skill.steps.length, "step"), "item-fact"));
    }
    if ((skill.tools || []).length) {
      row.appendChild(chip(`${skill.tools.length} tools`, "item-fact"));
    }
    for (const item of skill.inputs || []) row.appendChild(chip(`Asks for ${item.name}`, "item-fact"));
    // Its own class, not `persona-preview`. That one is `white-space: nowrap`
    // with an ellipsis, which is right for a persona (one line of voice) and
    // wrong here: a skill's description is the only thing that says what it
    // *does*, and clipping it to the width left over after five chips showed
    // three words. Reported twice. It wraps onto its own line now.
    const note = document.createElement("span");
    note.className = "muted skill-blurb";
    note.textContent = skill.description || skill.prompt;
    row.appendChild(note);
    if (!skill.builtin && !skill.folder) {
      const actions = document.createElement("span");
      actions.className = "entry-actions";
      actions.appendChild(
        smallButton("Edit", "Edit this skill", () => startEditingSkill(skill))
      );
      actions.appendChild(
        smallButton("Delete", "Remove this skill", async () => {
          if (!(await confirmDialog(`Delete the “${skill.name}” skill?`))) return;
          await saveSkillList(customSkills().filter((s) => s.name !== skill.name));
        })
      );
      li.append(row, actions);
    } else {
      li.appendChild(row);
    }
    return li;
  }

  async function renderSkillSettings() {
    const list = $("skill-list");
    showSkeletons(list, 3, "li");
    try {
      await loadSkills();
    } finally {
      clearSkeletons(list);
    }
    list.replaceChildren();
    for (const skill of allSkills()) list.appendChild(skillRow(skill));
    $("skills-count").textContent = String(allSkills().length);
    renderSkillFolderLine();
    if (!$("skill-tool-list").children.length) renderSkillToolPicker([]);
    if (!$("skill-verify-tool").children.length) renderSkillVerifyPicker(null);
  }

  //: Where the skills folder is and which of its files did not load (B8): a file
  //: that is not in the list says why here rather than being silently absent.
  function renderSkillFolderLine() {
    const line = $("skill-folder-line");
    if (!line) return;
    const folder = skillsState.folder || {};
    line.textContent = folder.path
      ? `Skills folder: ${folder.path}. A Markdown file saved there is listed here without a restart.`
      : "";
    for (const problem of folder.problems || []) {
      const item = document.createElement("span");
      item.className = "skill-folder-problem";
      item.textContent = problem.file ? `${problem.file}: ${problem.message}.` : `${problem.message}.`;
      line.append(document.createElement("br"), item);
    }
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { SETTINGS_CONTROLS_READY, ensureSettingsFoldAll, lanAllowHere, lanEmptyRow, lanNetworkRows, lanSwitch, lanTrustNetwork, openTaskLog, refreshSearxngHost, releaseThemeHold, renderAccount, renderAutonomousReview, renderFeatureModelRows, renderLanAccess, renderLanAddresses, renderLanState, renderLearned, renderMaintenance, renderMemorySettings, renderSkillSettings, renderStatusBarSettings, renderToolSettings, settingsControlState });
})();
