// account-recovery.js: "Forgot your password?" and the recovery key (INBOX 663).
//
// The owner: "there is no forgot password option in the lock screen", then
// "it needs to be robust and secure." Lazy (app.js `LAZY_MODULES.accountRecovery`,
// with recovery-lazy.css): nothing here is needed until the link is pressed,
// setup has just finished, or Settings asks for a key, and the boot budget
// (tests/test_boot_budget.py) is not the place for it.
//
// Three surfaces, all in index.html:
//
//   #lock-forgot-card     the lock card's twin, two paths: the recovery key
//                         (`POST /auth/recover`, private notes kept) or the
//                         reset the terminal command does (`POST /auth/reset`)
//   #recovery-key-dialog  the key, shown once; or, after setup, the offer
//   Settings              "Make a recovery key" / "Replace it" (settings-controls.js)
//
// **The key is never kept.** It arrives in one response, is written into
// `#recovery-key-value` while the dialog is open, and is taken out when it
// closes; no variable outlives the dialog. Nothing here logs it, puts it in a
// title or an aria-label (the Guide reads those, help-chat.js), or sends it
// anywhere but `/auth/recover`.

//: One const for this file's state (tests/test_global_scope_ratchet.py: no new
//: top-level lets). `wired`: the card's listeners are attached once.
const RECOVERY = { wired: false, dialogWired: false };

const RECOVERY_FILE = "tessellate-recovery-key.txt";
const RECOVERY_LEAD =
  "Save it away from this computer, such as a password manager or on paper. It is shown only this once.";

function recoveryFields() {
  return {
    key: $("lock-recovery-key"),
    fresh: $("lock-recovery-new"),
    again: $("lock-recovery-confirm"),
    word: $("lock-reset-confirm"),
  };
}

//: Which path the card shows: "key" (I have my recovery key) or "reset".
function forgotChoose(path) {
  const key = path === "key";
  $("lock-forgot-have").setAttribute("aria-pressed", String(key));
  $("lock-forgot-lost").setAttribute("aria-pressed", String(!key));
  //: `.active` is what draws a `.seg`'s chosen segment (INBOX 703: the card
  //: opened with neither path looking chosen).
  $("lock-forgot-have").classList.toggle("active", key);
  $("lock-forgot-lost").classList.toggle("active", !key);
  $("lock-forgot-key-pane").classList.toggle("hidden", !key);
  $("lock-forgot-reset-pane").classList.toggle("hidden", key);
  $("lock-forgot-error").textContent = "";
  (key ? $("lock-recovery-key") : $("lock-reset-confirm")).focus();
}

function wireForgotCard() {
  if (RECOVERY.wired) return;
  RECOVERY.wired = true;
  $("lock-forgot-close").addEventListener("click", closeForgotPassword);
  $("lock-forgot-have").addEventListener("click", () => forgotChoose("key"));
  $("lock-forgot-lost").addEventListener("click", () => forgotChoose("reset"));
  $("lock-recovery-submit").addEventListener("click", submitRecovery);
  $("lock-reset-submit").addEventListener("click", submitPasswordReset);
  $("lock-reset-copy").addEventListener("click", (event) =>
    copyToClipboard($("lock-reset-command").textContent, event.currentTarget)
  );
  $("lock-reset-send").addEventListener("click", requestResetCode);
  $("lock-reset-open-logs").addEventListener("click", openResetLogs);
  //: The button wakes only for the word and a full code, so a stray Enter cannot reset.
  for (const id of ["lock-reset-confirm", "lock-reset-code"]) $(id).addEventListener("input", syncResetSubmit);
  $("lock-forgot-card").addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeForgotPassword();
    } else if (event.key === "Enter" && event.target.tagName === "INPUT") {
      event.preventDefault();
      if (event.target.id === "lock-reset-confirm") {
        if (!$("lock-reset-submit").disabled) submitPasswordReset();
      } else {
        submitRecovery();
      }
    }
  });
}

//: Open the card in the lock card's place. On another device it says where
//: to do this instead and offers nothing to type: the server would refuse it
//: (`_from_this_computer`), and a form that cannot work is a worse answer.
async function openForgotPassword() {
  wireForgotCard();
  //: Asked now rather than kept from the boot: `reset_here` is about this
  //: caller only, and costs one local round trip. Unknown reads as here,
  //: since the server still refuses another device whatever the card says.
  const status = await apiJson("/auth/status", { silent: true }).catch(() => null);
  const here = status?.reset_here !== false;
  $("lock-forgot-card").classList.remove("hidden");
  $("lock-forgot-remote").classList.toggle("hidden", here);
  $("lock-forgot-paths").classList.toggle("hidden", !here);
  $("lock-reset-submit").disabled = true;
  $("lock-reset-where").classList.add("hidden");
  $("lock-reset-open-logs").classList.add("hidden");
  $("lock-reset-code").value = "";
  if (here) forgotChoose("key");
  else $("lock-forgot-close").focus();
}

function closeForgotPassword() {
  const fields = recoveryFields();
  for (const field of Object.values(fields)) field.value = "";
  $("lock-forgot-error").textContent = "";
  $("lock-forgot-card").classList.add("hidden");
  $("lock-password").focus();
}

function forgotError(text) {
  $("lock-forgot-error").textContent = text;
}

//: "I have my recovery key". The same checks as setup before the request
//: (eight characters, typed twice alike), so a typo costs a moment rather
//: than a password you did not mean; the server checks again.
async function submitRecovery() {
  const fields = recoveryFields();
  const key = fields.key.value.trim();
  const fresh = fields.fresh.value;
  forgotError("");
  if (!key) return forgotError("Enter your recovery key.");
  if (fresh.length < 8) return forgotError("Use at least 8 characters for the new password.");
  if (fresh !== fields.again.value) return forgotError("The two new passwords don't match.");
  const button = $("lock-recovery-submit");
  setBusy(button, true, "Checking…");
  let body = null;
  try {
    body = await apiJson("/auth/recover", {
      method: "POST",
      body: JSON.stringify({ recovery_key: key, new_password: fresh }),
      //: A 401 here is "that key is wrong", said under the field, not a lockout.
      ownsAuthErrors: true,
      silent: true,
    });
  } catch (error) {
    forgotError(error.message);
    return;
  } finally {
    setBusy(button, false);
  }
  closeForgotPassword();
  prefs.set("token", body.token);
  vaultOpen = true;
  lockedByHand = false;
  $("lock-password").blur();
  $("lock-btn").classList.remove("hidden");
  resetNavigationToDefaults();
  setBusy($("lock-submit"), true, "Opening…");
  curtainShell(startApp());
  if (body.warning) toast(body.warning, "info");
  //: The key just used is spent; its successor is shown once the app is up.
  showRecoveryKey(body.recovery_key, {
    title: "Your new recovery key",
    lead: "Your password is changed and private notes are kept. The key you used no longer works: save this one away from this computer. It is shown only this once.",
  });
}

function syncResetSubmit() {
  const word = $("lock-reset-confirm").value.trim() === "RESET";
  const code = /^\d{6}$/.test($("lock-reset-code").value.trim());
  $("lock-reset-submit").disabled = !(word && code);
}

//: Asks the server to print a code on its stderr (INBOX 1424). The answer
//: never carries the code, only where it went: a terminal, or a log file
//: (a desktop launch has no terminal), named without its folder.
async function requestResetCode() {
  forgotError("");
  const button = $("lock-reset-send");
  setBusy(button, true, "Printing…");
  let answer;
  try {
    answer = await apiJson("/auth/reset-code", { method: "POST", ownsAuthErrors: true, silent: true });
  } catch (error) {
    forgotError(error.message);
    return;
  } finally {
    setBusy(button, false);
  }
  const inLog = answer.where === "log";
  $("lock-reset-where").textContent = inLog
    ? `A code is printed in the log file ${answer.log_file || "desktop-stdio.log"}, in the logs folder. It works for 10 minutes.`
    : "A code is printed in the terminal. It works for 10 minutes.";
  $("lock-reset-where").classList.remove("hidden");
  $("lock-reset-open-logs").classList.toggle("hidden", !inLog);
  $("lock-reset-code").value = "";
  $("lock-reset-code").focus();
}

async function openResetLogs() {
  forgotError("");
  try {
    await apiJson("/auth/reset-code/open-logs", { method: "POST", ownsAuthErrors: true, silent: true });
  } catch (error) {
    forgotError(error.message);
  }
}

//: "I don't have it": the terminal command's reset, after the typed word and the printed code.
async function submitPasswordReset() {
  forgotError("");
  if ($("lock-reset-confirm").value.trim() !== "RESET") return forgotError("Type RESET to confirm.");
  const code = $("lock-reset-code").value.trim();
  if (!/^\d{6}$/.test(code)) return forgotError("Enter the six-digit code that was printed.");
  const button = $("lock-reset-submit");
  setBusy(button, true, "Resetting…");
  try {
    await apiJson("/auth/reset", {
      method: "POST",
      body: JSON.stringify({ confirm: "RESET", code }),
      ownsAuthErrors: true,
      silent: true,
    });
  } catch (error) {
    forgotError(error.message);
    return;
  } finally {
    setBusy(button, false);
  }
  closeForgotPassword();
  prefs.remove("token");
  vaultOpen = false;
  purgeLockedContent();
  $("lock-btn").classList.add("hidden");
  showLockScreen(true);
  toast("Password cleared. Choose a new one to open your notebook.", "info");
}

// --- the key, shown once ----------------------------------------------------------

//: Resolves once the lock screen is gone: a modal opened under it would be
//: stashed and shown again only when it lifts (app.js's lock observer), and
//: the curtain after an unlock is the lock screen too.
function whenLockLifted() {
  const overlay = $("lock-overlay");
  if (overlay.classList.contains("hidden")) return Promise.resolve();
  return new Promise((resolve) => {
    const watch = new MutationObserver(() => {
      if (!overlay.classList.contains("hidden")) return;
      watch.disconnect();
      resolve();
    });
    watch.observe(overlay, { attributes: true, attributeFilter: ["class"] });
  });
}

//: **Never `saveFile`** (INBOX 671): in the desktop window that writes into
//: `<data dir>/exports`, beside the notebook, and a key saved there opens its
//: private notes for whoever copies the folder. The desktop window asks the
//: server for a native Save dialog starting in Documents
//: (`/auth/recovery-key/save`, which also refuses the data dir); a browser
//: tab downloads, and the browser asks where.
async function saveRecoveryKeyFile(text) {
  const error = $("recovery-key-error");
  error.textContent = "";
  if (!(await desktopShell())) {
    downloadBlob(new Blob([text], { type: "text/plain" }), RECOVERY_FILE);
    return;
  }
  try {
    const saved = await apiJson("/auth/recovery-key/save", {
      method: "POST",
      body: JSON.stringify({ text }),
      silent: true,
    });
    if (saved.saved) toast(`Saved to ${saved.path}`, "info");
  } catch (failure) {
    error.textContent = failure.message;
  }
}

function wireRecoveryDialog() {
  const dialog = $("recovery-key-dialog");
  if (RECOVERY.dialogWired) return dialog;
  RECOVERY.dialogWired = true;
  $("recovery-key-copy").addEventListener("click", (event) =>
    copyToClipboard($("recovery-key-value").textContent, event.currentTarget)
  );
  $("recovery-key-download").addEventListener("click", () => {
    const key = $("recovery-key-value").textContent;
    if (!key) return;
    const text = [
      "Tessellate recovery key",
      "",
      key,
      "",
      `Made ${whenText()}.`,
      'If you forget your password, choose "Forgot your password?" on the lock',
      "screen, then \"I have my recovery key\". Your private notes are kept.",
      "",
      "Keep this file away from the computer your notebook is on: anyone with",
      "both can open your private notes.",
      "",
    ].join("\n");
    saveRecoveryKeyFile(text);
  });
  $("recovery-key-done").addEventListener("click", () => dialog.close());
  //: The key leaves the page with the dialog, however it is closed.
  dialog.addEventListener("close", () => {
    $("recovery-key-value").textContent = "";
    $("recovery-key-error").textContent = "";
  });
  return dialog;
}

//: Show a key once. `title` and `lead` say why it is being shown (made,
//: replaced, after a reset, after a re-key). Resolves when it is closed.
async function showRecoveryKey(key, { title = "Your recovery key", lead = RECOVERY_LEAD } = {}) {
  if (!key) return;
  await whenLockLifted();
  const dialog = wireRecoveryDialog();
  $("recovery-key-title").textContent = title;
  $("recovery-key-lead").textContent = lead;
  $("recovery-key-offer").classList.add("hidden");
  $("recovery-key-show").classList.remove("hidden");
  $("recovery-key-value").textContent = key;
  if (!dialog.open) dialog.showModal();
  $("recovery-key-done").focus();
  await new Promise((resolve) => dialog.addEventListener("close", resolve, { once: true }));
}

//: The step after setup: skippable, recommended. `password` is the one just
//: chosen, so the offer need not ask for it again; it lives in this call
//: only, and is dropped when the dialog closes either way.
//: **A turn in the first-run queue** (`firstRunTurn`, onboarding.js). The
//: welcome is queued first (it is what this app is), so on a fresh data dir
//: the order measured is welcome, tour, this offer, the update question.
//: Measured before: this dialog drew over the welcome card, 478x172 px.
async function offerRecoveryKey(password) {
  await ensureModule("onboarding");
  return firstRunTurn(() => showRecoveryOffer(password), "recovery");
}

async function showRecoveryOffer(password) {
  await whenLockLifted();
  const dialog = wireRecoveryDialog();
  $("recovery-key-title").textContent = "Make a recovery key?";
  $("recovery-key-offer").classList.remove("hidden");
  $("recovery-key-show").classList.add("hidden");
  const make = $("recovery-key-make");
  const skip = $("recovery-key-skip");
  let made = false;
  const onMake = async () => {
    setBusy(make, true, "Making…");
    try {
      const body = await apiJson("/auth/recovery-key", {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      });
      made = true;
      $("recovery-key-title").textContent = "Your recovery key";
      $("recovery-key-lead").textContent = RECOVERY_LEAD;
      $("recovery-key-offer").classList.add("hidden");
      $("recovery-key-show").classList.remove("hidden");
      $("recovery-key-value").textContent = body.recovery_key;
      $("recovery-key-done").focus();
    } catch (error) {
      $("recovery-key-error").textContent = error.message;
    } finally {
      setBusy(make, false);
    }
  };
  const onSkip = () => dialog.close();
  make.addEventListener("click", onMake);
  skip.addEventListener("click", onSkip);
  dialog.addEventListener(
    "close",
    () => {
      make.removeEventListener("click", onMake);
      skip.removeEventListener("click", onSkip);
      password = "";
      if (!made) toast("You can make a recovery key later in Settings, Account & security.", "info");
    },
    { once: true }
  );
  dialog.showModal();
  make.focus();
}

//: Settings, Account & security: "Make a recovery key" or "Replace it".
//: The password on the lock card in prompt mode (DESIGN.md's recipe for one
//: action's password), which carries the throttle and the error line.
async function makeRecoveryKey() {
  const status = $("account-recovery-status");
  status.classList.remove("error");
  status.textContent = "";
  const replacing = $("account-recovery-make").dataset.replacing === "yes";
  if (replacing && !(await confirmDialog("Replace your recovery key?\n\nThe one you have stops working.", { confirmLabel: "Replace" }))) {
    return;
  }
  let key = null;
  const done = await askPasswordPrompt({
    title: replacing ? "Replace your recovery key" : "Make a recovery key",
    message: "Enter your current password.",
    submitLabel: replacing ? "Replace" : "Make key",
    submit: async (password) => {
      const body = await apiJson("/auth/recovery-key", {
        method: "POST",
        body: JSON.stringify({ current_password: password }),
        ownsAuthErrors: true,
      });
      key = body.recovery_key;
    },
  });
  if (!done || !key) return;
  renderAccount().catch(() => {});
  await showRecoveryKey(key, {
    title: replacing ? "Your new recovery key" : "Your recovery key",
    lead: replacing
      ? "The old key no longer works. Save this one away from this computer, such as a password manager or on paper. It is shown only this once."
      : RECOVERY_LEAD,
  });
  key = null;
  status.textContent = replacing ? "Recovery key replaced." : "Recovery key made.";
}

//: The Settings Account pane's recovery key row (settings-panes.js
//: `renderAccount`, through the stand-in), and the one button beside it,
//: named for what it will do.
function recoveryAccountRow(info) {
  const made = info.recovery_key_created_at;
  const button = $("account-recovery-make");
  button.textContent = made ? "Replace it" : "Make a recovery key";
  button.dataset.replacing = made ? "yes" : "no";
  return ["Recovery key", made ? `Made ${new Date(made).toLocaleDateString()}` : "None yet"];
}
