// update-dialogs.js: the update check, applying an update, and the two
// update bar and the "was updated" dialog. Moved out of settings-panes.js on 2026-10-05 (the
// boot-script gzip budget, ratchet in tests/test_static_compression.py): the
// check runs from Settings' "Check for updates" button and, only for someone who
// turned it on, once at startup; the dialogs open from those and from the
// source-checkout notice. Loaded on first use by `LAZY_MODULES.updates`
// (app.js), whose stand-ins for `checkForUpdate`, `applyUpdateNow` and
// `showSourceUpdatedDialog` fetch this file and then call the real one. All
// three are `async` or read by nobody (callers `await` the result), so the
// stand-in's promise is the shape they already return.
// `checkForSourceUpdateNotice` stays in settings-panes.js: it runs on every
// start, and the common answer (nothing was updated) needs none of this.

// Shared by the "Check for updates" button and the silent startup check. `silent`
// suppresses the status-line text and the toast for the common "you're on
// the latest version" outcome: the startup check should only ever speak up
// when there's actually something to say.
async function checkForUpdate(silent = false) {
  const status = $("update-check-status");
  const applyBtn = $("update-apply-now");
  if (!silent && status) setLabel(status, "ph:spin Checking…");
  let result;
  try {
    // A click on Check for updates is the person asking for this one
    // request, so the server does not refuse it with the switch off.
    result = await apiJson(silent ? "/update/check" : "/update/check?manual=1", { silent: true });
  } catch (error) {
    if (!silent && status) status.textContent = "Couldn't check for updates.";
    return;
  }
  if (!result || !result.checked) {
    if (!silent && status) {
      //: The server's own sentence when it wrote one. It knows which of
      //: "offline", "no release published yet" and "rate-limited" happened,
      //: and all three used to be printed here as the first: reported with a
      //: screenshot of "Couldn't reach GitHub" on a machine that was online,
      //: which it was, and had nothing to update to.
      status.textContent =
        result && result.reason === "disabled"
          ? "Enable the checkbox above, then try again."
          : (result && result.message) || "Couldn't reach GitHub to check for updates.";
    }
    applyBtn?.classList.add("hidden");
    return;
  }
  // Settings -> About's own fallback for "or they can manually do it in the
  // settings", same button, same apiJson('/update/apply') call the
  // post-login dialog's "Update automatically" makes.
  applyBtn?.classList.toggle("hidden", !(result.update_available && result.can_auto_apply));
  if (result.update_available) {
    //: Section 21 row 13: how big the download is, before it is asked for.
    const size = result.asset && result.asset.size ? `, a ${formatFileSize(result.asset.size)} download` : "";
    const msg = `Version ${result.latest} is available (you have ${result.current})${size}.`;
    if (status) status.textContent = msg;
    // INBOX 1440: the startup check shows a closable bar, once per version
    // (the seen key), unless the person turned the bar off in Settings. It
    // never installs anything: the bar's Update button is the press.
    if (silent) {
      if (prefsCache?.show_update_bar !== false && prefs.get(UPDATE_SEEN_KEY, null) !== result.latest) showUpdateBar(result);
    } else {
      toast(msg);
    }
  } else if (!silent && status) {
    status.textContent = `You're on the latest version (${result.current}).`;
  }
}

//: **Ask once** (the owner, 2026-10-05, WORLD_CLASS_PLAN 12 "Decisions
//: made"): the first start asks whether to check for updates by itself, and
//: until the answer is in nothing about updating touches the network.
//: Closing the question is "no", the answer that touches nothing; Settings,
//: About holds the switch and the Check for updates button either way.
//: start.sh may already have asked in the terminal, and then this never runs.
async function askUpdateChoiceOnce() {
  //: Never over the welcome, the tour it hands on to, the recovery-key offer
  //: or the desktop's console question: the first-run queue holds its slot,
  //: last in `FIRST_RUN_ORDER` (onboarding.js). Measured before: on a first
  //: start it took the welcome's Skip from under the pointer, and it opened
  //: with the tour's first card in the same 0.4 s.
  const ask = () => confirmDialog(
    "Check for updates automatically?\n\nTessellate can look for a newer version each time it starts. " +
      "Nothing about your notes is sent. You can change this in Settings, About.",
    { confirmLabel: "Check automatically", cancelLabel: "Don't check", danger: false }
  );
  await ensureModule("onboarding").catch(() => {});
  const yes = typeof firstRunTurn === "function" ? await firstRunTurn(ask, "updates") : await ask();
  //: Escape or the backdrop answers undefined (not a "no"): nothing stored,
  //: asked again next start (X12).
  if (yes === undefined) return;
  try {
    const saved = await apiJson("/update/choice", { method: "POST", body: JSON.stringify({ check: Boolean(yes) }) });
    if (prefsCache) Object.assign(prefsCache, saved);
    if ($("pref-update-check")) $("pref-update-check").checked = Boolean(saved.update_check_enabled);
    if ($("pref-auto-update")) $("pref-auto-update").checked = Boolean(saved.auto_update_enabled);
  } catch (error) {
    toast(error.message || "Couldn't save that answer.", true);
    return;
  }
  if (yes) await checkForUpdate(true);
}

//: The last version this profile was already told about, so the update bar
//: shows once per newly-available release rather than every login
//: for as long as the user hasn't updated.
const UPDATE_SEEN_KEY = "update-seen-version";

// Shared by the update bar's Update button and Settings ->
// About's manual one: asked for directly: "either by the message popping
// up the next time they load up the app and are connected to the internet,
// and/or they can manually do it in the settings." `onProgress(state)` is
// called on every poll (`{step, done_bytes, total_bytes}` from
// GET /update/apply/status) so each caller can render it its own way; the
// promise resolves `true` on outcome "launched" and `false` on "failed", 
// never rejects, since a failed apply is exactly the case both callers have
// to handle gracefully (offline, GitHub unreachable, no asset), not an
// exception to propagate.
async function applyUpdateNow(onProgress, tag = null) {
  const url = tag ? `/update/apply?tag=${encodeURIComponent(tag)}` : "/update/apply";
  const start = await apiJson(url, { method: "POST" }).catch((error) => {
    onProgress?.({ step: error.message, failed: true });
    return null;
  });
  if (!start) return false;
  //: A transient miss mid-poll is not a failure, but ten in a row (7 s with
  //: no answer) is: the loop ends rather than spinning forever (X12).
  for (let misses = 0; misses < 10; ) {
    await new Promise((resolve) => setTimeout(resolve, 700));
    const state = await apiJson("/update/apply/status", { silent: true }).catch(() => null);
    if (!state) {
      misses += 1;
      continue;
    }
    misses = 0;
    onProgress?.(state);
    if (state.outcome === "launched") return true;
    if (state.outcome === "failed") return false;
    if (!state.running) return false; // shouldn't happen, but never loop forever
  }
  onProgress?.({ step: "The update stopped answering. Try again from Settings, About.", failed: true });
  return false;
}

async function showUpdateBar(result) {
  //: Its own sheet, loaded here and not named in `LAZY_MODULES.updates`: app.js
  //: is at its gzip cap. Awaited, so the bar never paints unstyled.
  await lazyScript("/css/update-bar-lazy.css");
  document.querySelector(".update-bar")?.remove();
  const bar = document.createElement("div");
  bar.id = "update-bar";
  bar.className = "notice update-bar";
  bar.setAttribute("role", "region");
  bar.setAttribute("aria-label", "Update available");
  const icon = document.createElement("span");
  setLabel(icon, "ph:arrow-circle-up");
  // role="status": progress and failures are spoken as they change.
  const text = document.createElement("span");
  text.className = "update-bar-text";
  text.setAttribute("role", "status");
  text.textContent = `Tessellate ${result.latest} is available.`;

  const close = () => {
    bar.remove();
    prefs.set(UPDATE_SEEN_KEY, result.latest);
  };
  // The intentional press. Where this build cannot install itself, the same
  // button opens the release page instead.
  const update = smallButton("Update", result.can_auto_apply ? "Download and install the update" : "Open the release page", async () => {
    if (!result.can_auto_apply) {
      window.open(result.url, "_blank", "noopener");
      return;
    }
    update.disabled = true;
    const ok = await applyUpdateNow((state) => {
      text.textContent = state.total_bytes
        ? `${state.step} (${Math.round((state.done_bytes / state.total_bytes) * 100)}%)`
        : state.step;
    });
    // A failed apply keeps the bar and re-enables the button to retry. On
    // success the app exits itself shortly after (routes_update.py).
    if (!ok) {
      update.disabled = false;
      toast(text.textContent || "Couldn't apply the update.", true);
    }
  }, false);
  // Closable notice recipe (DESIGN.md): the icon-only ghost button is the last child.
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost small icon-only";
  dismiss.setAttribute("data-dismiss", "notice");
  dismiss.title = "Hide this until the next version";
  dismiss.setAttribute("aria-label", "Hide this until the next version");
  setLabel(dismiss, "ph:x");
  dismiss.addEventListener("click", close);
  bar.append(icon, text, update, dismiss);
  document.querySelector("#top-bar").after(bar);
}

function showSourceUpdatedDialog(result) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Tessellate was updated");

  const card = document.createElement("div");
  card.className = "card modal-card confirm-card";
  const heading = document.createElement("h3");
  heading.textContent = "Tessellate was updated";
  const text = document.createElement("p");
  text.className = "confirm-text";
  text.textContent = result.from
    ? `Your checkout auto-updated from ${result.from} to ${result.to} when you started it just now.`
    : `Your checkout auto-updated to ${result.to} when you started it just now.`;
  const row = document.createElement("div");
  row.className = "row confirm-actions";

  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      dismiss();
    }
  };
  const ok = smallButton("Got it", "Got it", dismiss, false);
  row.appendChild(ok);

  card.append(heading, text, row);
  overlay.appendChild(card);
  wireBackdropClose(overlay, () => dismiss());
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  ok.focus();
}
