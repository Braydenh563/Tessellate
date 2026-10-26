// settings-wiring.js: saved filters, onboarding and diagnostics, rebindable
// shortcuts, the Wave F wiring, drag and paste. Moved out of app.js on
// 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- saved filters ---------------------------------------------------------------
// Once the filter box understands operators, the useful ones are worth
// keeping. "tag:work is:untagged" is a thing you want on a button, not
// something to retype: and it works with no AI at all.

function savedSearches() {
  return (prefsCache && prefsCache.saved_searches) || [];
}

function renderSavedSearches() {
  const box = $("saved-searches");
  const saved = savedSearches();
  box.replaceChildren();
  box.classList.toggle("hidden", saved.length === 0);
  for (const item of saved) {
    const chipEl = document.createElement("span");
    chipEl.className = "chip saved-search";
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "saved-search-apply";
    setLabel(apply, `ph:star ${item.name}`);
    apply.title = `Filter: ${item.query}`;
    apply.addEventListener("click", () => {
      $("note-search").value = item.query;
      noteSearch = item.query;
      renderEntries();
      refreshNoteSearchWhy();
      announce(`Applied the saved filter "${item.name}".`);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "saved-search-remove";
    setLabel(remove, "ph:x");
    remove.title = `Forget "${item.name}"`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", async () => {
      const next = savedSearches().filter((s) => s.name !== item.name);
      await persistSavedSearches(next);
      toast(`Forgot "${item.name}".`);
    });
    chipEl.append(apply, remove);
    box.appendChild(chipEl);
  }
}

async function persistSavedSearches(next) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ saved_searches: next }),
  });
  renderSavedSearches();
}

async function saveCurrentSearch() {
  const query = $("note-search").value.trim();
  if (!query) return;
  const name = await promptDialog("Name this filter:", query.slice(0, 40), { confirmLabel: "Save filter" });
  if (!name) return;
  // Re-saving an existing name updates it rather than adding a duplicate you
  // then have to hunt down and remove.
  const next = savedSearches().filter((s) => s.name !== name);
  next.push({ name, query });
  await persistSavedSearches(next);
  toast(`Saved "${name}".`);
}

$("save-search").addEventListener("click", saveCurrentSearch);

$("history-close").addEventListener("click", () =>
  $("history-overlay").classList.add("hidden")
);

$("shortcuts-reset").addEventListener("click", resetShortcuts);

wirePrefsDirtyMarks();

//: **Ctrl+S on the Preferences section**, which the section's own copy has
//: promised for a long time ("Ctrl+S saves too") without anything in the app
//: implementing it: reported as no confirmation appearing on ctrl+s, and the
//: reason there was none is that nothing ran. In a browser the press went to
//: "save this page" instead; in the desktop window it did nothing at all.
//:
//: Capturing, so a focused textarea (the profile box is one) cannot swallow
//: it, and `preventDefault` so the browser's own save dialog does not open
//: on top of the toast. Scoped to this one section: ctrl+s elsewhere in
//: Settings has nothing to save, and taking the key globally would break the
//: browser shortcut everywhere for no gain.
document.addEventListener(
  "keydown",
  (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    if (event.key !== "s" && event.key !== "S") return;
    if (!settingsOpen() || !["preferences", "general"].includes(currentSettingsSection)) return;
    event.preventDefault();
    savePrefs();
  },
  true
);
$("draft-model").addEventListener("click", () => openFeatureModelSheet("writing"));
wireFeatureModelSelects();

// Wave N: improve-writing, link suggestions.
$("improve-btn").addEventListener("click", () => openImprove($("entry-content")));
$("improve-close").addEventListener("click", closeImprove);
$("improve-apply").addEventListener("click", applyImprove);
$("improve-retry").addEventListener("click", runImprove);
for (const button of document.querySelectorAll(".improve-mode")) {
  button.addEventListener("click", () => {
    improveMode = button.dataset.mode;
    for (const b of document.querySelectorAll(".improve-mode"))
      b.classList.toggle("active", b === button);
    const isCustom = improveMode === "custom";
    $("improve-custom-row").classList.toggle("hidden", !isCustom);
    // Picking a mode only gets it ready; Start (or Go, for Custom) runs it
    // (`improveReady`, ai-tools.js).
    if (isCustom) $("improve-custom-input").focus();
    improveReady();
  });
}

$("improve-custom-go").addEventListener("click", () => {
  improveCustomInstruction = $("improve-custom-input").value;
  runImprove();
});
$("improve-custom-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    $("improve-custom-go").click();
  }
});
$("link-suggest-btn").addEventListener("click", () => openSuggestionsInbox("links"));
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
    if (radio.checked && radio.value === "sentence-transformers") applyEmbeddingBackend();
  });
}
$("status-back").addEventListener("click", () => stepTabHistory(-1));
$("status-forward").addEventListener("click", () => stepTabHistory(1));
$("status-back").addEventListener("contextmenu", (event) => {
  event.preventDefault();
  openNavHistoryMenu($("status-back"));
});
$("status-forward").addEventListener("contextmenu", (event) => {
  event.preventDefault();
  openNavHistoryMenu($("status-forward"));
});
wireLongPress($("status-back"), () => openNavHistoryMenu($("status-back")));
wireLongPress($("status-forward"), () => openNavHistoryMenu($("status-forward")));
$("status-nav-history")?.addEventListener("click", () => {
  const menu = $("status-nav-history-menu");
  if (menu.classList.contains("hidden")) openNavHistoryMenu($("status-nav-history"));
  else closeNavHistoryMenu();
});
document.addEventListener("click", (event) => {
  const menu = $("status-nav-history-menu");
  if (!menu || menu.classList.contains("hidden")) return;
  if (menu.contains(event.target) || event.target.closest("#status-nav-history")) return;
  closeNavHistoryMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeNavHistoryMenu();
});
// Seed the stack with wherever the app opened, or the first tab clicked has
// nothing behind it and Back stays dead until the second navigation, which
// reads as the button being broken rather than empty.
recordTabVisit(prefs.get("activeTab", null) || "dashboard", null);
$("save-btn").addEventListener("click", saveEntry);
$("save-draft-btn").addEventListener("click", saveEntryAsDraft);
$("ask-btn").addEventListener("click", () => askQuestion()); // no event as preset
// Reported: "the semantic search settings button in the ask tab doesn't
// work", it does exist in the markup (`#ask-search-tune`, same icon/title
// as Chat's own per-turn tune button) but nothing ever wired a listener to
// it. Same destination as the other two quick-access links into this
// preferences group (Chat's per-turn tune button, the Dashboard catalog).
$("ask-search-tune").addEventListener("click", () => {
  openSettingsModal("searchindex", "search-relevance-group");
});
$("stop-btn").addEventListener("click", stopAnswer);
$("retry-btn").addEventListener("click", retryAnswer);
$("copy-btn").addEventListener("click", copyAnswer);
$("new-chat-btn").addEventListener("click", newChat);
$("ask-history-toggle").addEventListener("click", toggleAskHistoryPanel);
// Asked for directly: an X to close the history panel, not only the History
// toggle button that opened it (easy to lose track of once scrolled past).
$("ask-history-close")?.addEventListener("click", () => {
  if (askHistoryOpen) toggleAskHistoryPanel();
});
$("ask-history-more").addEventListener("click", () => loadAskHistoryPage(false));
$("ask-history-pinned-only").addEventListener("change", () => loadAskHistoryPage(true));
$("ask-history-clear").addEventListener("click", clearAskHistory);
let askHistorySearchDebounce;
$("ask-history-search").addEventListener("input", () => {
  clearTimeout(askHistorySearchDebounce);
  askHistorySearchDebounce = setTimeout(() => loadAskHistoryPage(true), 200);
});
$("lock-btn").addEventListener("click", lockNow);

// **Locking has to reach every open tab, not just the one you clicked in.**
//
// The lock audit found this one by opening a second tab, which ROADMAP.md had
// named as an unchecked avenue. Locking in tab A cleared tab A and dropped the
// shared token, so the API correctly refused tab B, but tab B kept showing
// all 61 notes with no lock screen at all, indefinitely. Lock the notebook,
// walk away from a shared machine, and everything is still on screen in the
// window behind.
//
// `storage` fires in *other* tabs of the same origin when a key changes, which
// is exactly the signal wanted: the tab that did the locking has already
// handled itself, and no polling or cross-tab channel is needed. A `null`
// `newValue` is the removal specifically (`localStorage.clear()` also arrives
// with a null `key`, and is treated the same way, the token is gone either
// way).
window.addEventListener("storage", (event) => {
  if (event.storageArea !== localStorage) return;
  if (event.key !== null && event.key !== "token") return;
  if (prefs.get("token", null)) return; // a sign-in elsewhere, not a lock
  // Already locked, unless the overlay is only asking for a password.
  if (!$("lock-overlay").classList.contains("hidden") && $("lock-overlay").dataset.mode !== "prompt") return;
  lockedByHand = true; // a lock elsewhere is a lock here: no quiet new session
  purgeLockedContent();
  showLockScreen(false);
});
//: The lock form's submit (moved from app.js, whose only caller is here).
async function submitLockForm() {
  const password = $("lock-password").value;
  const errorLine = $("lock-error");
  errorLine.textContent = "";
  const mode = $("lock-overlay").dataset.mode;
  //: A new password needs 8 (SEC-17); one set before that still unlocks.
  const floor = mode === "setup" ? 8 : 4;
  if (password.length < floor) {
    errorLine.textContent = `Use at least ${floor} characters.`;
    return;
  }
  if (mode === "prompt") {
    const prompt = lockPrompt;
    if (!prompt) return;
    try {
      await prompt.submit(password);
    } catch (error) {
      errorLine.textContent = error.message;
      return;
    }
    settleLockPrompt(true);
    return;
  }
  try {
    const body = await lockRequest(mode, password, errorLine);
    prefs.set("token", body.token);
    if (body.warning) toast(body.warning, "info");
    vaultOpen = mode === "setup" ? true : Boolean(body.vault_open);
    lockedByHand = false;
    $("lock-password").value = "";
    // **Give the focus back, or every single-key shortcut in the app is
    // dead.** Hiding the overlay does not move focus off the field inside
    // it, so `document.activeElement` stayed `#lock-password` for the whole
    // session that followed. Every handler that (correctly) refuses to steal
    // a keystroke while someone is typing, the whiteboard's V/H/P tool keys,
    // its `n` and `/`, and the same guard elsewhere, therefore returned
    // immediately on every press, until the reader happened to click some
    // other focusable control. Found while testing the tool shortcuts: they
    // did nothing at all from a freshly unlocked app.
    $("lock-password").blur();
    //: The overlay stays up as the opening curtain and fades over the
    //: drawn page (`curtainShell`, `liftLockScreen`).
    $("lock-btn").classList.remove("hidden");
    // Signing in starts a session, and a session starts at the front of every
    // tab: see `resetNavigationForNewSession`. Here as well as at load
    // because the lock screen is an *overlay*, not a page: unlocking after an
    // idle lock never reloads anything, so the load-time reset alone would
    // leave every sub-tab exactly where it was hours ago. Called before
    // `startApp()`, which is what reads the stored section back.
    resetNavigationToDefaults();
    setBusy($("lock-submit"), true, "Opening…");
    const opening = startApp();
    curtainShell(opening);
    //: The step after setup (INBOX 663): a recovery key, offered once the
    //: app is drawn, skippable. The password just chosen goes with it so
    //: the offer does not ask for it again; account-recovery.js drops it
    //: when the dialog closes.
    if (mode === "setup") offerRecoveryKey(password);
  } catch (error) {
    errorLine.textContent = error.message;
  }
}

//: **A new device waits for Allow by itself** (lansafe-1011's leftover): the
//: server holds an unlock from an unknown phone 45 s for this computer's
//: Allow, then answers 403 with `device_pending`. Asking again at once picks
//: the same held request back up, so the phone keeps waiting, up to
//: `LOCK_DEVICE_WAIT_MS`, instead of telling its owner to press Unlock again
//: after walking to the computer. Editing the field stops it.
const LOCK_DEVICE_WAIT_MS = 180_000;
async function lockRequest(mode, password, errorLine) {
  const until = Date.now() + LOCK_DEVICE_WAIT_MS;
  for (;;) {
    try {
      const body = await apiJson(`/auth/${mode === "setup" ? "setup" : "unlock"}`, {
        method: "POST",
        body: JSON.stringify({ password }),
        //: A 401 here is "that password is wrong", said under the field. Left
        //: unclaimed, apiJson read it as an expired session and the field said
        //: "Locked".
        ownsAuthErrors: true,
        silent: true,
      });
      errorLine.textContent = "";
      return body;
    } catch (error) {
      const waiting = error.body?.device_pending && Date.now() < until && $("lock-password").value === password;
      if (!waiting) {
        setBusy($("lock-submit"), false);
        throw error;
      }
      errorLine.textContent = "Waiting for the computer to allow this device. Choose Allow in the notice there.";
      setBusy($("lock-submit"), true, "Waiting…");
      //: A full wait queue answers at once; a pause keeps that from spinning.
      await new Promise((resolve) => setTimeout(resolve, 3000));
      if ($("lock-password").value !== password) {
        setBusy($("lock-submit"), false);
        throw error;
      }
    }
  }
}

$("lock-submit").addEventListener("click", submitLockForm);
//: The lock field's own show-password toggle (the browser's reveal vanished
//: once the field lost focus). Shown text is never kept: a lock resets it.
$("lock-password-show").addEventListener("click", (event) => {
  const field = $("lock-password");
  const show = field.type === "password";
  field.type = show ? "text" : "password";
  const button = event.currentTarget;
  button.setAttribute("aria-pressed", String(show));
  button.title = show ? "Hide password" : "Show password";
  button.setAttribute("aria-label", button.title);
  button.querySelector("i").className = `ph ${show ? "ph-eye-slash" : "ph-eye"}`;
  field.focus();
});
$("lock-password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitLockForm();
  if (e.key === "Escape" && lockPrompt) {
    e.preventDefault();
    e.stopPropagation();
    settleLockPrompt(false);
  }
});
$("lock-cancel").addEventListener("click", () => settleLockPrompt(false));
//: "Forgot your password?" (INBOX 663): the card is account-recovery.js's.
$("lock-forgot").addEventListener("click", () => openForgotPassword());
// Enter in the question box asks; Ctrl+Enter in the note box saves.
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter") askQuestion();
  //: Escape clears the question (CHAT_PLAN, INBOX 63: "Esc clears"); an
  //: empty box lets it through to whatever else it closes. The box is
  //: disabled while an answer streams, so this never races a stop.
  if (e.key === "Escape" && e.target.value) {
    e.preventDefault();
    e.stopPropagation();
    e.target.value = "";
  }
});
//: Time travel on Ask (row 23): the clock opens the "as of" line, Back to
//: now closes it (`showAskAsOf`, capture-ask.js).
$("ask-time-travel").addEventListener("click", () => {
  showAskAsOf($("ask-as-of-row").classList.contains("hidden"));
});
$("ask-as-of-clear").addEventListener("click", () => {
  showAskAsOf(false);
  $("question").focus();
});
$("entry-content").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveEntry();
  }
});
//: The `[[` list is the editor menu's (editor.js), as in every other surface.
$("entry-content").addEventListener("input", () => {
  scheduleCaptureTagSuggestions();
});
//: True while the notebook is locked, the unlock overlay is up and nothing
//: behind it may be reached.
//:
//: **This is a privacy hole, not a polish item.** Reported directly: "I can
//: use keyboard shortcuts to access features even when locked out… like the
//: meeting notes popup." The global handler below had no lock check of any
//: kind, so every shortcut worked behind the lock screen: the command
//: palette (which lists and opens notes by title), "/" to focus search, the
//: `g`-then-letter tab jumps, the meeting recorder, all of it. The lock
//: screen is the only privacy boundary this app has, and the keyboard walked
//: straight past it.
//:
//: Read off the DOM rather than a flag, deliberately: the overlay's own
//: `hidden` class is what every other part of the app already treats as the
//: truth about being locked, and a second source of truth is how a boundary
//: like this drifts back open.
function notebookLocked() {
  const overlay = document.getElementById("lock-overlay");
  return Boolean(overlay) && !overlay.classList.contains("hidden");
}

//: `flashSaved` and `saveWhatIsInFront` live here, at module scope, rather
//: than inside the keydown listener below where they were written.
//: `runShortcut` is the only caller of the second one now and is a top-level
//: function, so a declaration nested in that listener's callback would not be
//: in its scope at all.
  //: A short, non-blocking mark on the control a shortcut just pressed, so a
//: keyboard save is visibly a save rather than a key that did nothing. The
//: class is removed on the animation's own end rather than on a timer, so
//: two presses in a row both show, and at once under
//: `prefers-reduced-motion` (the rule carries no animation there).
function flashSaved(el) {
  if (!el) return;
  el.classList.remove("just-saved");
  //: **The ring is added to the control's shadow, not swapped for it.**
  //: `box-shadow` is one property holding a list, so an animation on it
  //: replaces whatever the control already had. Measured on `#prefs-save`,
  //: whose resting shadow is `rgba(70,100,240,0.25) 0 2px 10px`: the ring
  //: dropped that glow for its whole duration and snapped it back at the end,
  //: which reads as the button flickering rather than acknowledging. The
  //: resting value is handed to the keyframes as a custom property and they
  //: draw it underneath the ring (08-consistency.css). Read before the class
  //: goes on, or it is the animation's own first frame that comes back.
  const resting = getComputedStyle(el).boxShadow;
  el.style.setProperty("--just-saved-rest", resting && resting !== "none" ? resting : "0 0 #0000");
  // Reading a layout property between the remove and the add is what restarts
  // a CSS animation on an element that already has the class; without it a
  // second press inside the animation's own duration shows nothing.
  void el.offsetWidth;
  el.classList.add("just-saved");
  //: **Finished whether or not the ring ran.** Under the system's reduced
  //: motion `.just-saved` is `animation: none`, and an animation that never
  //: starts never ends: the class and the shadow stayed on the button, and
  //: every Ctrl+S left one more `animationend` listener that would never run
  //: (the review, 2026-09-27; `tests/test_motion_endings.py`). So it is
  //: finished at once when no ring is running, and otherwise when this
  //: ring's own `finished` settles, which a cancel (the control hidden
  //: mid-ring) settles too. The ring's promise rather than the element's
  //: events: a second press cancels the first ring, and that ring's cancel
  //: event, dispatched a frame later, would reach the second ring's
  //: listener. The token keeps a late first ring off the second one.
  const token = {};
  el._justSaved = token;
  const finish = () => {
    if (el._justSaved !== token) return;
    el._justSaved = null;
    el.classList.remove("just-saved");
    el.style.removeProperty("--just-saved-rest");
  };
  const ring = el.getAnimations().find((a) => a.animationName === "just-saved-ring");
  if (!ring) {
    finish();
    return;
  }
  ring.finished.then(finish, finish);
}

//: **Ctrl+S saves what is in front of you** (INBOX 74, asked for: "register
//: the ctrl s command for saving progress such as settings"). Settings: the
//: visible section's own Save button, or the nav button for a section that
//: saves as you change it; Documents: the document; Capture: the note.
//:
//: **Called from `runShortcut`, not from a Ctrl+S branch of its own.** This
//: was written as a second `if` further down the same keydown handler, and
//: it never ran once: `shortcuts` carries a `save` binding whose default keys
//: are Ctrl+S, and the chorded loop at the top of that handler matches it,
//: calls `runShortcut("save")` and returns first. Measured live with the
//: Settings modal open (`scratchpad/ui-sweeps/ctrlss4.js`): `matchesShortcut`
//: against a Ctrl+S event returns the `save` binding, so every keystroke went
//: to that two-line handler, which knows only about Documents and Capture and
//: called `saveEntry()` with the settings modal in front of the reader. Both
//: halves of the report ("doesnt work", "needs visual confirmation") were
//: still true for that reason. `runShortcut` now calls this, so the binding
//: is the one place Ctrl+S is decided and rebinding it still works.
function saveWhatIsInFront() {
  if (settingsModalOpen()) {
    //: **Look for a control that is actually on screen, not for a naming
    //: convention.** Reported on 2026-09-09: "ctrl s for saving settings
    //: changes while on the settings modal doesnt work and it needs visual
    //: confirmation as well." Measured with the modal open on its default
    //: section: seventeen `.settings-section` elements, exactly one of them
    //: visible (`#settings-models`), and every one of the six
    //: `button[id$="-save"]` in the document laid out at zero height,
    //: because they all belong to other sections. So the lookup found
    //: nothing every time and the keystroke answered "this section saves as
    //: you change it" whether or not that was true.
    //:
    //: `offsetParent` is the test that a screenshot would use: is this
    //: button on screen. The id suffix stays as the first preference, since
    //: it is exact where it applies, and a visible "Save…" button anywhere
    //: in the modal is the fallback for the sections that never adopted it.
    const onScreen = (el) => el && el.offsetParent !== null && !el.disabled;
    const section = [...document.querySelectorAll(".settings-section")].find(
      (el) => el.offsetParent !== null,
    );
    let save = [...(section?.querySelectorAll('button[id$="-save"]') || [])].find(onScreen);
    if (!save) {
      save = [...document.querySelectorAll("#settings-modal button")].find(
        (el) => onScreen(el) && /^save\b/i.test((el.textContent || "").trim()),
      );
    }
    if (save) {
      save.click();
      //: The visual half of the same report. The save handlers each raise
      //: their own toast, but a keystroke with no immediate mark on the
      //: control it pressed reads as a keystroke that went nowhere, so the
      //: button itself acknowledges the press before its handler answers.
      flashSaved(save);
    } else {
      //: **The other fifteen sections acknowledge the keystroke too.**
      //: Measured across all seventeen (`scratchpad/ui-sweeps/settingssave.js`):
      //: exactly two, Appearance and Preferences, have a Save button on
      //: screen. Everywhere else, including the section Settings opens on,
      //: Ctrl+S raised a toast and marked nothing, so the half of the report
      //: that asked for visual confirmation was still true for most of the
      //: modal. The nav button for the open section is what gets the ring:
      //: it is small, always in view, and it is the control that names the
      //: page the keystroke was aimed at, where the section panel itself is
      //: a scrolling column whose edges are mostly off screen.
      flashSaved(document.querySelector("#settings-nav button.active"));
      toast("Nothing on this settings page needs saving. It saves as you change it.");
    }
    return;
  }
  if (!$("tab-documents")?.classList.contains("hidden") && typeof saveDocument === "function") {
    saveDocument();
    return;
  }
  //: **Capture, and the button does not have to be on screen.** This branch
  //: required `offsetParent`, which was written while the code was unreachable
  //: and is wrong: measured on a fresh Notes tab, the composer is collapsed and
  //: `#save-btn.offsetParent` is null, so with the branch finally running every
  //: keyboard save on Notes answered "Nothing to save here." The question the
  //: keystroke asks is whether anything has been written, not whether the
  //: button happens to be laid out. What the visibility does decide is the
  //: mark: there is no point ringing a control nobody can see.
  const capture = $("save-btn");
  if (capture && !capture.disabled) {
    //: Ctrl+S on an empty composer is a keystroke, not a mistake worth
    //: scolding: pressing the button would raise the composer's own "write
    //: something first" error, which is the line the owner found sitting
    //: there having "didnt do anything".
    const written = ($("entry-content")?.value || "").trim() || ($("entry-title")?.value || "").trim();
    if (!written) {
      toast("Nothing to save yet.");
      return;
    }
    capture.click();
    if (capture.offsetParent) flashSaved(capture);
    return;
  }
  toast("Nothing to save here.");
  return;
}

//: Item 9: a key within 1.5 s of typing in an editor is not a command. The
//: document editor stops its letters at its host and sets this itself.
const typingBurst = { at: 0 };

document.addEventListener("keydown", (e) => {
  // **Before anything else.** A locked notebook answers no shortcut, not a
  // chorded one, not a bare one, not a tab jump. Typing is untouched: this
  // returns before any shortcut is *dispatched*, so the password field still
  // receives every keystroke, and Enter still submits it through the form's
  // own handler rather than this one.
  if (notebookLocked()) return;
  // Rebinding swallows everything while it's listening.
  if (captureShortcutKey(e)) {
    e.preventDefault();
    return;
  }
  // Chorded shortcuts (anything with a modifier) work even while typing, 
  // Ctrl+K from inside the note box should still open the palette. Undo/redo
  // are the deliberate exception: Ctrl+Z/Ctrl+Shift+Z are already the
  // browser's own undo for whatever text field has focus (correcting a typo
  // you just made), and that has to win over this app's global stack: 
  // otherwise fixing a typo in the note box would silently restore a
  // deleted note instead of undoing the keystroke.
  const chorded = e.ctrlKey || e.metaKey || e.altKey;
  //: **A chord the open board answers itself is the board's** (the
  //: conventions pass, 2026-09-23). Ctrl+Shift+G is Ungroup on every canvas
  //: people know and agent mode here, and both listeners ran: ungrouping a
  //: selection on a board also threw you out to Chat (measured: the board's
  //: container measured 0 x 0 straight after). `wbOwnsChord` names the
  //: board's own chords; the same handoff undo already makes
  //: (`boardHistoryActive`), one owner for one shortcut.
  if (chorded && !(typeof wbOwnsChord === "function" && wbOwnsChord(e))) {
    const inTextField =
      ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName) ||
      document.activeElement?.isContentEditable;
    //: **Ctrl+Y is redo too**, the Windows habit: the board's own Redo
    //: button and Edit menu already print "Ctrl+Y" and nothing answered it
    //: (the Guide agent's finding, 2026-09-24). Same rule as Ctrl+Shift+Z:
    //: a text field keeps its own.
    if (!inTextField && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "y") {
      e.preventDefault();
      runShortcut("redo");
      return;
    }
    for (const [id, def] of Object.entries(shortcuts)) {
      if ((id === "undo" || id === "redo" || id === "pasteNote") && inTextField) continue;
      //: INBOX 321: on an open board the same chord duplicates the selection.
      //: And an editor that already answered it keeps it: the documents
      //: editor binds Ctrl+D to "select the next match" (CodeMirror's search
      //: keymap), handles it at the target and marks it `defaultPrevented`.
      if (id === "todaysNote" && (boardHistoryActive() || e.defaultPrevented)) continue;
      //: The same handoff for Ctrl+/ (INBOX 402): the documents editor's
      //: keymap answers it with the comment toggle and marks it handled, and
      //: this then wrote a "/" over the selection the toggle had just made,
      //: so Ctrl+/ on a line of prose left a lone "/" where the line was
      //: (measured, `doccodevs.js`). In a note box nothing answers it first,
      //: so the blocks menu still opens there.
      if (id === "editorMenu" && e.defaultPrevented) continue;
      if (matchesShortcut(e, def.keys)) {
        e.preventDefault();
        //: The chord goes through the same `performUndo`/`performRedo` the
        //: status bar's buttons press, which is where the board handoff
        //: lives (`boardHistoryActive`), so all three doors agree.
        runShortcut(id);
        return;
      }
    }
  }
  if (e.key === "Escape" && !$("notif-panel").classList.contains("hidden")) {
    closeNotifications();
    $("notif-btn").setAttribute("aria-expanded", "false");
    return;
  }
  if (e.key === "Escape" && !$("onboarding-overlay").classList.contains("hidden")) {
    closeOnboarding();
    return;
  }
  if (e.key === "Escape" && !$("features-overlay").classList.contains("hidden")) {
    closeFeatures();
    return;
  }
  if (e.key === "Escape" && !$("graph-new").classList.contains("hidden")) {
    closeGraphNewNote();
    return;
  }
  if (e.key === "Escape" && !$("graph-popup").classList.contains("hidden")) {
    closeGraphPopup();
    return;
  }
  if (e.key === "Escape" && !$("palette-overlay").classList.contains("hidden")) {
    //: A '?' open on the palette (its foot) takes this Escape for itself; the
    //: next one closes the palette (`menus.js` marks the press as spent).
    if (!e.helpPopoverSpent) closePalette();
    return;
  }
  if (e.key === "Escape" && !$("sketch-overlay").classList.contains("hidden")) {
    //: As the palette: an Escape that closed the pad's '?' leaves the pad.
    if (!e.helpPopoverSpent) closeSketch();
    return;
  }
  if (e.key === "Escape" && !$("meeting-overlay").classList.contains("hidden")) {
    closeMeetingRecorder();
    return;
  }
  if (e.key === "Escape" && !$("improve-overlay").classList.contains("hidden")) {
    closeImprove();
    return;
  }
  if (e.key === "Escape" && !$("connections-overlay").classList.contains("hidden")) {
    $("connections-overlay").classList.add("hidden");
    return;
  }
  if (e.key === "Escape" && !$("history-overlay").classList.contains("hidden")) {
    $("history-overlay").classList.add("hidden");
    return;
  }
  if (e.key === "Escape" && !$("shortcuts-overlay").classList.contains("hidden")) {
    closeShortcuts();
    return;
  }
  // Four modal-overlay dialogs (settings, doc AI-edit, extract-to-notes,
  // recycle bin) had a close button and a backdrop-click handler but no
  // Escape wiring here: every other overlay in this list works with
  // Escape, so these four were the exception rather than a deliberate
  // choice (Nielsen's "user control and freedom").
  if (e.key === "Escape" && settingsModalOpen()) {
    closeSettingsModal();
    return;
  }
  if (e.key === "Escape" && !$("doc-ai-panel").classList.contains("hidden")) {
    closeDocAiPanel();
    return;
  }
  if (e.key === "Escape" && !$("extract-panel").classList.contains("hidden")) {
    closeExtractPreview();
    return;
  }
  if (e.key === "Escape" && !$("binned-overlay").classList.contains("hidden")) {
    closeBinnedReader();
    return;
  }
  // "/" focuses search: but only when you're not already typing somewhere
  // and no overlay is open, so it never steals a literal slash (Wave J).
  //: **`isContentEditable` too**, which the chorded branch above already
  //: checks and this one did not. The list of three tag names was exactly
  //: right while every editing surface in this app was a textarea; it is not
  //: any more. The documents editor stops its own single characters at its
  //: host (`docGuardGlobalShortcuts` in documents.js, which explains why it is
  //: done there rather than here), so the gap showed on the next
  //: contenteditable instead: the Library's OCR region text, where a literal
  //: "/" moved focus to the global search and swallowed the rest of the
  //: correction (measured by `scratchpad/ui-sweeps/typingguard.js`). Fixing
  //: the shared guard means the one after that is born working.
  const el = document.activeElement;
  const typing =
    ["INPUT", "TEXTAREA", "SELECT"].includes(el && el.tagName) || Boolean(el && el.isContentEditable);
  const overlayOpen =
    settingsModalOpen() ||
    !$("palette-overlay").classList.contains("hidden") ||
    !$("sketch-overlay").classList.contains("hidden");
  // Unchorded shortcuts ("/", "?") only fire when you're not typing and no
  // overlay is open, so they never steal a literal slash mid-sentence.
  //: Single-key shortcuts can be turned off (WCAG 2.1.4): speech input types
  //: letters.
  const singleKeys = singleKeysOn();
  const now = performance.now();
  if (typing) typingBurst.at = now;
  const burst = !typing && e.key.length === 1 && now - typingBurst.at < 1500 && (typingBurst.at = now);
  //: `boardOwns`: a key the open board answers itself (`wbOwnsChord`), such
  //: as a letter typed while a new map topic is still being made.
  const boardOwns = typeof wbOwnsChord === "function" && wbOwnsChord(e);
  if (!typing && !burst && !overlayOpen && singleKeys && !boardOwns) {
    for (const [id, def] of Object.entries(shortcuts)) {
      const bare = !/\+/.test(def.keys);
      if (bare && matchesShortcut(e, def.keys)) {
        e.preventDefault();
        runShortcut(id);
        return;
      }
    }
  }
  //: **The "m" chord is not behind the overlay guard, and that is the point.**
  //:
  //: Reported: "when I press m and s for settings, it gets stuck when I try
  //: to press m again and something else to navigate out of it". It was
  //: stuck because `m` + `s` opens Settings, Settings makes `overlayOpen`
  //: true, and this whole block used to sit inside `!overlayOpen`: the very
  //: chord that opened the modal could not be used to leave it. Quick-nav is
  //: the app's "take me somewhere else" gesture, so it has to outrank a
  //: surface that is merely on top. The bare shortcuts above stay behind the
  //: guard, because those are single letters that a modal's own controls
  //: have a better claim on.
  //:
  //: `typing` still wins over both: a chord that fired while you were
  //: filling in a settings field would eat the letter you meant to type.
  if (!typing && !burst) {
    // The second half of the "m" then a letter chord, armed below. Checked
    // first so a stray letter within the window is consumed (matched or
    // not) rather than falling through and re-arming on a later "g".
    //: **A second "m" toggles the guide closed rather than being read as an
    //: unrecognised chord key.** Asked for directly: "if i press it then the
    //: popup opens and i can press m again to close it or an x close button
    //: to close it."
    //:
    //: `e.repeat` is refused here and at the arming branch below, because a
    //: held key repeats: reported as "when I hold down m, the screen flashes
    //: with the popup help nav ui". Every repeat was a fresh press to this
    //: handler, so the toggle opened, closed, opened and closed at the
    //: keyboard's repeat rate. Holding "m" now shows the guide once and
    //: holds it there, which is what holding a key should mean.
    if (e.repeat && (e.key === "m" || e.key === "t")) return;
    //: **"t" (Tessellate) is the first key, "m" its alias** (C23, the owner's
    //: decision: the app is Tessellate now). Either one, pressed again while
    //: the guide is up, closes it; Timeline's second key moved from t to i so
    //: "t t" has nothing else to mean.
    if (tabJumpArmedAt && (e.key === "m" || e.key === "t") && !e.ctrlKey && !e.metaKey && !e.altKey) {
      tabJumpArmedAt = 0;
      hideChordGuide();
      return;
    }
    if (tabJumpArmedAt) {
      tabJumpArmedAt = 0;
      const usable = !e.ctrlKey && !e.metaKey && !e.altKey;
      const target = usable ? TAB_JUMP_KEYS[e.key] : undefined;
      const action = usable ? CHORD_ACTIONS[e.key] : undefined;
      hideChordGuide();
      if (target) {
        e.preventDefault();
        //: Leaving for another tab means leaving whatever is over it, or the
        //: jump lands behind a modal that is still taking the keyboard.
        closeOverlaysForChord();
        switchTab(target);
        return;
      }
      if (action) {
        e.preventDefault();
        //: Same for an action: `m` then `s` from inside the palette should
        //: end with Settings open, not with both stacked.
        closeOverlaysForChord();
        action.run();
        return;
      }
      // Not a recognised second key, fall through and let this keypress do
      // whatever it would have done anyway.
    } else if (
      singleKeys && (e.key === "m" || e.key === "t") && !e.ctrlKey && !e.metaKey && !e.altKey
      //: An open board's M is its highlighter and its T the text tool
      //: (`wbOwnsChord`, whiteboard.js).
      && !boardOwns
    ) {
      tabJumpArmedAt = performance.now();
      //: Asked for: "m" rather than "g" (m for Tessellate, and "g" collided
      //: with Graph's own letter), and "some visual assistance and guides":
      //: the first key shows the chord's targets for as long as it is armed,
      //: so the second key is never a guess.
      showTabJumpHint();
      return; // wait for the second key; a lone "m" does nothing on its own
    }
  }
  if (e.key === "Escape" && settingsModalOpen()) closeSettingsModal();
  if (e.key === "Escape") closeActionMenus();
  if (e.key === "Escape" && linkSource !== null) {
    linkSource = null;
    renderEntries();
  }
});

// Clicking anywhere outside an open ⋯ menu closes it (Wave L).
//
// `.action-menu-escaped` covers a menu `wireEscapedActionMenu` has
// reparented to `<body>` while open: its dropdown is no longer a
// descendant of `.menu-wrap` at that point, so a click inside the (still
// open) dropdown would otherwise fail `closest(".menu-wrap")` and be read
// as an outside click. Only ever *widens* what counts as inside; no
// existing kebab gains this class, so nothing about them changes.
//
// **`pointerdown`, capture phase, not `click`.** Reported: an escaped menu
// (reparented to `<body>`, `position: fixed`, so it paints over whatever is
// underneath) sometimes stayed open, or a click meant for the row behind it
// landed on that row instead. `click` fires after `pointerup`, by which
// point a note card's own `pointerdown`/`mousedown` handlers (drag,
// selection) have already run against the *old* DOM, and on some rows that
// consumed or moved the event before it ever reached this listener in the
// bubble phase. `pointerdown` in the capture phase runs first, ahead of
// every other handler on the page, so the menu is gone before anything
// underneath it can react to the same gesture.
//: A press *inside* any open menu is the menu's own: `.action-menu` covers a
//: menu that lives on <body> without a `.menu-wrap` around it (the board's
//: context menu), where a press on one of its group rows closed the whole
//: menu before the row could open its flyout (measured on the map node menu).
//: **A press on the control that opened a menu is the menu's own too** (INBOX
//: 681, "not all dropdown elements close when pressing that element again").
//: A `kebabMenu` opener sits inside `.menu-wrap`, so it always was; a custom
//: select's opener sits in `.select-shell`, outside it, so this closed the
//: list on the press and the opener's click then opened it again: a second
//: press never shut it. Every opener's own click already toggles, so the
//: press is left to it. A chip that opens a menu at a point says so the same
//: way (`aria-haspopup`, `aria-expanded`, chip-menus.js).
document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest(".menu-wrap, .action-menu, .action-menu-escaped, [aria-haspopup][aria-expanded='true']")) closeActionMenus();
}, true);

// Focus trapping (Wave L): while a modal is open, Tab cycles inside it.
// The DOM is asked, not a list of ids (a hard-coded list of eight missed
// eight more): a dialog that is `aria-modal="true"` is trapped, a popover
// that is only `role="dialog"` is not (the page behind it stays live).
// Topmost is the last match in document order, so a confirm opened from
// Settings traps Tab, not Settings. Visibility is `.hidden` plus
// `getClientRects()`, because a fixed overlay's `offsetParent` is null.
function activeOverlay() {
  const open = [
    ...document.querySelectorAll('[role="dialog"][aria-modal="true"]'),
  ].filter((el) => !el.classList.contains("hidden") && el.getClientRects().length > 0);
  return open.length ? open[open.length - 1] : null;
}

// --- first-run onboarding tour (learnability) -------------------------------
//: The welcome card itself (its slides, setup check and buttons) is in
//: onboarding.js, loaded on first use; this file keeps the decision to open it.

// Show the welcome once, after the app is unlocked and running.
//
//: An install that has already been through the welcome (`onboardingDone` is
//: set) is not shown it again, and is not shown the tour uninvited either: a
//: card that takes over the screen of somebody who has been using the app for
//: months is the "trapped" failure the tour is written to avoid. It is offered
//: once instead, in a toast with an action, which is the app's existing recipe
//: for "here is something, and here is the one press that takes it". Declining
//: it is silent and permanent: the offer writes `tourDone` either way, so this
//: runs at most once per notebook.
function maybeShowOnboarding() {
  if (!prefs.get("onboardingDone", null)) {
    openOnboarding();
    return;
  }
  if (prefs.get("tourDone", null)) return;
  if (typeof openTour !== "function") return;
  if (typeof TOUR_ENABLED !== "undefined" && !TOUR_ENABLED) return;
  prefs.set("tourDone", "1");
  toastAction("There is a guided tour of Tessellate now.", "Take the tour", () => {
    openTour("basics");
  });
}

//: The third door into the tour, and it was the one left open (the owner,
//: 2026-09-21: "the take the tour again button in the about settings page
//: isnt disabled"). Same flag, same words as the replay strip's buttons.
//: **After the page has loaded, not now.** `TOUR_ENABLED` is a `const` in
//: tour.js, the last script on the page; at this line that binding does not
//: exist yet, `typeof` says "undefined", and the block below never ran once
//: while it sat here bare: the button stayed live with the flag off, and
//: nothing threw to say so (`tests/test_frontend_load_order.py`, the typeof
//: guard test). `DOMContentLoaded` fires after every classic script has run.
onDomReady(() => {
  if (typeof TOUR_ENABLED !== "undefined" && !TOUR_ENABLED) {
    const aboutTour = $("about-take-tour");
    if (aboutTour) {
      aboutTour.disabled = true;
      aboutTour.title = "The guided tour is being fixed and is turned off for now.";
      aboutTour.setAttribute("aria-label", aboutTour.title);
    }
  }
});

// Keyboard-shortcuts cheat-sheet (press ?), a learnability aid.
// --- rebindable keyboard shortcuts -----------------------------------------------
// The shortcuts used to be hardcoded in the keydown handler, which meant they
// were whatever we'd guessed: no help if one clashes with your OS, your
// browser, or a habit from another app.
//
// Only shortcuts that trigger an *action* are rebindable. Escape (close),
// Tab (move focus) and the arrow keys (move between tabs) deliberately are
// not: they're the conventions every app shares, and letting someone rebind
// Escape is how you end up unable to close the dialog you rebound it in.

const DEFAULT_SHORTCUTS = {
  palette: { keys: "Ctrl+K", label: "Open the command palette" },
  search: { keys: "/", label: "Jump to search (or the chat box on Chat)" },
  // Asked for directly: "add a ctrl+f or equivalent text search... make
  // the find feature available on all tabs." Rebindable like every other
  // chorded shortcut here, which also means it is discoverable in the
  // shortcuts cheat-sheet (?) rather than a secret the app never mentions.
  find: { keys: "Ctrl+F", label: "Find on this page" },
  help: { keys: "?", label: "Show this shortcuts list" },
  newNote: { keys: "Ctrl+Shift+N", label: "Start a new note" },
  quickNote: { keys: "Alt+N", label: "Quick note, saved without leaving the page" },
  //: WORLD_CLASS_PLAN, Placed 2026-09-09 item 99 (d): the fastest capture on
  //: a desktop. Not in a text box, where the chord is the browser's own
  //: "paste as plain text" and is left to it.
  pasteNote: { keys: "Ctrl+Shift+V", label: "Save what you copied as a new note" },
  newDocument: { keys: "Ctrl+Shift+D", label: "Start a new document" },
  //: WORLD_CLASS_PLAN D6. Opens today's page wherever it is (a note or a
  //: document titled with the day), or starts one in the composer. Not while a
  //: board is open: there `Ctrl+D` is the board's duplicate (INBOX 321), and
  //: the chorded loop in the keydown handler steps aside for it.
  todaysNote: { keys: "Ctrl+D", label: "Open today's note, or start it" },
  // A recording is started the moment a meeting starts, and anything that
  // makes you navigate first is what makes it not get started at all, the
  // reason this is a shortcut as well as a palette entry and a tray item.
  recordMeeting: { keys: "Ctrl+Shift+R", label: "Record a meeting or lecture" },
  // Asked for directly: "add a way to force reload the browser or py web
  // view". A plain F5 keeps the service worker's cache and, in the desktop
  // webview, sometimes the old app.js with it, which is how a fixed button
  // gets reported broken again. This drops every cache first.
  forceReload: { keys: "Ctrl+Alt+R", label: "Reload the app (clearing cached files)" },
  toggleTheme: { keys: "Ctrl+Shift+L", label: "Switch light / dark" },
  undo: { keys: "Ctrl+Z", label: "Undo the last change" },
  redo: { keys: "Ctrl+Shift+Z", label: "Redo" },
  // The selection menu's keyboard door. Without it the whole feature is
  // mouse-only for the actual *opening*, the ⋯ now appears for a Shift+Arrow
  // selection too (`selectionchange` fires for those), but a menu you can see
  // and cannot open is not an improvement.
  selectionActions: { keys: "Ctrl+Shift+E", label: "Actions for the selected text" },
  //: DOCUMENTS_PLAN 18c. The "/" menu had exactly one way in, typing "/",
  //: which you had to already know about. Here it is rebindable like the rest
  //: and, more to the point, it is in the cheat sheet, which is where somebody
  //: looks for what an app can do. The other two ways are the placeholder on
  //: every editing surface and the menu itself (editor.js).
  editorMenu: { keys: "Ctrl+/", label: "Blocks and commands, where you are writing" },
  // --- added when the section was expanded (reported: "expand the keyboard
  // shortcuts section in settings") ---------------------------------------
  //
  // Every one of these was already a thing the app does and a thing people do
  // repeatedly; none of them had a key. The bar for adding one is that it
  // saves a *navigation*, not a click, a shortcut that only replaces a button
  // already on the screen you are looking at earns nothing and spends a combo.
  save: { keys: "Ctrl+S", label: "Save the note or document you're editing" },
  newChat: { keys: "Ctrl+Shift+O", label: "Start a new chat" },
  stopAI: { keys: "Ctrl+.", label: "Stop the answer being written" },
  agentMode: { keys: "Ctrl+Shift+G", label: "Turn agent mode on or off" },
  quickSketch: { keys: "Ctrl+Shift+K", label: "Open the quick sketch pad" },
  // **The agent bar's chord, declared here rather than bound loose.** It was
  // moved off Ctrl+K once already, to settle a collision with the navigation
  // palette: onto Ctrl+Shift+K, which `quickSketch` above had held all
  // along, so the fix swapped one silent collision for another and the sketch
  // pad and the agent bar both opened on one press (reported). The cause both
  // times was the same: this chord lived in a `document.addEventListener` of
  // its own, where nothing could see it. In the registry it is checked against
  // every other chord by `test_frontend_shortcuts.py`, appears in the
  // shortcuts help, and can be rebound like all the rest.
  askAgent: { keys: "Ctrl+Shift+A", label: "Ask the agent anything" },
  //: Beside the agent's own chord, because they are the pair: one does things
  //: to your notes and the other explains the app. In the registry rather than
  //: bound loose, which is what puts it in the shortcuts sheet (INBOX 224's
  //: "the keyboard shortcut is listed in the shortcuts sheet": the sheet is
  //: built from this table, so listing it and declaring it are one act).
  askAtlas: { keys: "Ctrl+Shift+H", label: "Ask Atlas about the app" },
  //: **The universal search.** In the registry, not bound loose, for the
  //: reason `askAgent` above records at length: a chord in a listener of its
  //: own is invisible to `test_frontend_shortcuts.py` and to the shortcuts
  //: sheet, which is how two surfaces came to share one chord twice. Ctrl+P
  //: rather than Ctrl+K (the navigation palette) or Ctrl+F (find on this
  //: page): it is the chord every editor uses for "go to anything", and it
  //: was free.
  findAnything: { keys: "Ctrl+P", label: "Find anything: notes, files, actions" },
  whiteboard: { keys: "Ctrl+Shift+B", label: "Open the whiteboard" },
  settings: { keys: "Ctrl+,", label: "Open settings" },
  attachNote: { keys: "Ctrl+Shift+P", label: "Clip a note to your next question" },
  // The status bar's own Back/Forward buttons (`stepTabHistory`) were
  // click-only: asked for directly. Alt+Left/Right rather than the bare
  // arrow keys: those are needed everywhere text is edited or a list is
  // navigated, and a modifier is what every browser already uses for this
  // exact action, so it costs no muscle memory to learn.
  //: **The inline AI's chord.** Not Ctrl+K (the command palette) and not
  //: Ctrl+I (italic, in every editing surface here), the two chords every
  //: other app uses for this. Ctrl+J was free, and this is declared in the
  //: registry rather than bound loose for the reason `askAgent` records above:
  //: a chord in a listener of its own is invisible to
  //: `test_frontend_shortcuts.py`'s collision check and to the shortcuts help.
  inlineAi: { keys: "Ctrl+J", label: "Ask Atlas to write at the cursor" },
  //: INBOX 430, the owner: "a show/hide companion hotkey". In the registry
  //: for the reason `askAgent` records: collisions are checked here, and the
  //: shortcuts sheet is built from this table.
  toggleCompanion: { keys: "Ctrl+Shift+Y", label: "Show or hide the companion" },
  //: INBOX 896, the owner: "add a hotkey" for the status bar's Other devices
  //: panel. Alt+L was free here and in the browsers this runs in; L for LAN.
  lanPanel: { keys: "Alt+L", label: "Other devices on this network: open the switch and the trusted networks" },
  navigateBack: { keys: "Alt+ArrowLeft", label: "Go back to the previous page or view" },
  navigateForward: { keys: "Alt+ArrowRight", label: "Go forward again" },
};

const SHORTCUT_STORE = "keyboardShortcuts";

function loadShortcuts() {
  let saved = {};
  try {
    saved = prefs.json(SHORTCUT_STORE, {});
  } catch {
    saved = {}; // unreadable: fall back to defaults rather than throwing
  }
  const merged = {};
  for (const [id, def] of Object.entries(DEFAULT_SHORTCUTS)) {
    merged[id] = { ...def, keys: saved[id] || def.keys };
  }
  return merged;
}

let shortcuts = loadShortcuts();

SHORTCUT_SOURCE.table = () => shortcuts;

//: **A button says its key** (INBOX 701; first measured when none of the
//: buttons with a chord said so in a tooltip). A button whose action has a
//: binding here carries `data-shortcut="<action>"` in index.html, and this
//: stamps its tooltip from the *current* binding ("New note (Ctrl+Shift+N)",
//: the Command symbol on a Mac) and again whenever a binding changes;
//: `aria-keyshortcuts` says the same to a screen reader. Buttons the JS
//: paints itself (the status bar's) call `shortcutTitle` at the paint, and
//: `tests/test_shortcut_hints.py` fails for an action with a button that does
//: neither, and for a chord written next to a `data-shortcut`.
const SHORTCUT_TITLE_CHORD = /\s*\([^()]*(?:Ctrl|Alt|Shift|⌘|⌥|⇧)[^()]*\)\s*$/;

function stampShortcutTitles() {
  for (const button of document.querySelectorAll("[data-shortcut]")) {
    const combo = shortcuts[button.dataset.shortcut]?.keys;
    if (!combo) continue;
    const base = (button.title || "").replace(SHORTCUT_TITLE_CHORD, "") || button.getAttribute("aria-label") || button.textContent.trim();
    button.title = shortcutTitle(base, button.dataset.shortcut);
    button.setAttribute("aria-keyshortcuts", combo.replace(/\bCtrl\b/g, SHORTCUT_MAC ? "Meta" : "Control"));
  }
}

//: Titles that name a *fixed* chord (Bold, Italic, the board's own keys), not
//: one from the table, are written "Ctrl+B" in the markup; on a Mac they read
//: with the Command symbol. The static ones only: a title a script sets later
//: is written through `shortcutTitle` or `chordLabel` where it is set.
function localizeStaticChords() {
  if (!SHORTCUT_MAC) return;
  const chord = /\b(?:(?:Ctrl|Alt|Shift)\+)+[^\s)(,;]+/g;
  for (const el of document.querySelectorAll('[title*="Ctrl+"], [title*="Alt+"], [title*="Shift+"]')) {
    el.title = el.title.replace(chord, (match) => chordLabel(match));
  }
}

//: A binding changed or reset: the table-driven titles, and the bars that
//: paint their own, are redone from the new table.
function restampShortcutHints() {
  stampShortcutTitles();
  const dashKeys = document.querySelector(".dash-find-keys");
  if (dashKeys) dashKeys.textContent = shortcutHint("findAnything");
  renderStatusBar();
  renderUndoBar();
  paintTabHistory();
}
localizeStaticChords();
restampShortcutHints();
// Sets the status-bar Undo/Redo buttons' icons and "nothing to undo yet"
// tooltips on load: both stacks are empty at this point, so this only
// establishes the disabled state the HTML already carries, not a real render.
renderUndoBar();

// "t" (or "m") then a letter jumps tabs (t for Tessellate), GitHub and Gmail's own "go to" chord, and
// the reason it isn't in DEFAULT_SHORTCUTS/rebindable above: a chord needs
// somewhere to hold the first keypress while it waits for the second, and
// that's state this file has to own regardless, so it lives beside the
// other keys-every-app-shares (Escape, Tab, arrows) rather than pretending
// it is a single rebindable key like the rest of the list.
const TAB_JUMP_KEYS = {
  d: "dashboard",
  n: "notes",
  c: "chat",
  g: "graph",
  l: "library",
  i: "timeline",
  r: "reminders",
};
//: The other half of the same chord: three things you *do* rather than three
//: places you go. Asked for by the owner: "also add a shortcut for 'm' + 's'
//: for opening up settings, maybe 'm' + 'q' for quick sketch?? maybe 'm' +
//: 'm' or 'v' (for voice) for meeting notes or smth??"
//:
//: `v`, not `m`: `m` as the second key would mean the chord's own first key
//: repeated, which is what a person presses when they are not sure the first
//: press registered. Making that open a recorder is the one mapping in the
//: set that could surprise someone twice in a row.
//:
//: These are declared beside `TAB_JUMP_KEYS` rather than in `shortcuts`,
//: because the chord's second key is not a rebindable accelerator: it is a
//: menu of ten entries the guide draws from these two tables, so a new entry
//: here appears in the guide with no other change.
const CHORD_ACTIONS = {
  s: { label: "Settings", icon: "ph:gear", run: () => openSettingsModal() },
  q: { label: "Quick sketch", icon: "ph:palette", run: () => openSketch() },
  v: { label: "Record a meeting", icon: "ph:microphone", run: () => openMeetingRecorder() },
  //: The two assistants (INBOX 249, the owner: "is there a hotkey ot keybind,
  //: as well as an 'm' key navigation to open the atlas window and popup
  //: agent??"). Ctrl+Shift+A and Ctrl+Shift+H are theirs in the registry
  //: above; these are the chord's spellings of the same two.
  //: Named for what it opens, the Guide (the owner: "the option for atlas
  //: leads to the guide, I think it should be called guide instead"),
  //: the same word the status bar's button uses. The key stays `a`.
  a: { label: "Guide", icon: "ph:compass", run: () => askAtlasAbout("") },
  p: { label: "Popup agent", icon: "ph:strategy", run: () => toggleAgentPalette() },
  //: A place, not an act (the owner: "add the ocr workspace to the 'm' quick
  //: nav"): `group: "go"` draws it under "Go to", and it opens the way the
  //: Library's own door does, through the reveal target.
  o: { label: "OCR workspace", icon: "ph:scan", group: "go", run: () => revealFeature("page-reader") },
};
let tabJumpArmedAt = 0;

//: Whatever is currently on top, dismissed so a resolved chord lands on the
//: surface it asked for rather than behind a modal that still holds the
//: keyboard. Each close is guarded by its own "is it open" test, so this is
//: a no-op in the ordinary case where the chord was pressed with nothing
//: over the page. `closeSketch` is async (it saves first); it is not awaited
//: because the tab switch that follows does not depend on the save landing.
function closeOverlaysForChord() {
  if (settingsModalOpen()) closeSettingsModal();
  const palette = document.getElementById("palette-overlay");
  if (palette && !palette.classList.contains("hidden")) closePalette();
  const sketch = document.getElementById("sketch-overlay");
  if (sketch && !sketch.classList.contains("hidden")) closeSketch();
  //: Atlas's sheet, when it is open (settings.js owns the closer).
  if (typeof helpChatSheetClose === "function") helpChatSheetClose();
}

//: **The chord's guide.** A mode, not a notification: the app is waiting for
//: the next key, so it is a centred panel over a dimmed page (it was a toast,
//: and its pairs wrapped mid-pair), gone the moment the chord resolves. The
//: rows are buttons too (the owner: "make these popup options when I press
//: m, actual clickable nav buttons"); a click on the dimmed page, Escape and a
//: second `m` all mean "not this". `role="status"` so a screen reader hears it.
let chordGuideTimer = null;

//: The panel's builders (`chordGuideEl`, `chordGuideGroup`, `chordGuideKey`,
//: `showTabJumpHint`) are in chord-guide.js, loaded after boot; see its header.
function hideChordGuide() {
  const guide = document.getElementById("chord-guide");
  if (!guide) return;
  window.clearTimeout(chordGuideTimer);
  guide.classList.add("hidden");
}

function saveShortcutOverrides() {
  // Only store what differs from the defaults, so improving a default later
  // reaches everyone who never changed it.
  const overrides = {};
  for (const [id, def] of Object.entries(DEFAULT_SHORTCUTS)) {
    if (shortcuts[id].keys !== def.keys) overrides[id] = shortcuts[id].keys;
  }
  prefs.set(SHORTCUT_STORE, JSON.stringify(overrides));
  restampShortcutHints();
}

// A keyboard event -> the canonical string we compare against, e.g. "Ctrl+K".
function comboFromEvent(event) {
  const parts = [];
  if (event.ctrlKey || event.metaKey) parts.push("Ctrl");
  if (event.altKey) parts.push("Alt");
  if (event.shiftKey) parts.push("Shift");
  let key = event.key;
  if (key === " ") key = "Space";
  // Single letters normalise to uppercase so "Ctrl+k" and "Ctrl+K" are one
  // shortcut; longer names (Enter, ArrowUp) keep their own capitalisation.
  if (key.length === 1) key = key.toUpperCase();
  // A bare modifier isn't a shortcut yet, the user is still mid-chord.
  if (["Control", "Meta", "Alt", "Shift"].includes(event.key)) return null;
  parts.push(key);
  return parts.join("+");
}

// "?" is Shift+/ on most layouts; treat the typed character as the shortcut so
// a user who binds "?" doesn't have to know that.
function matchesShortcut(event, combo) {
  if (comboFromEvent(event) === combo) return true;
  return combo.length === 1 && event.key === combo && !event.ctrlKey && !event.metaKey;
}

function runShortcut(id) {
  const actions = {
    //: Handed to editor.js, which owns the menu and knows which surfaces have
    //: one. It answers false when nothing editable has focus, and then this
    //: does nothing rather than inserting a slash into whatever is there.
    editorMenu: () => {
      if (typeof editorOpenMenuByShortcut === "function") editorOpenMenuByShortcut();
    },
    palette: () => {
      if ($("palette-overlay").classList.contains("hidden")) openPalette();
      else closePalette();
    },
    findAnything: () => {
      const overlay = document.getElementById("finder-overlay");
      if (overlay && overlay.classList.contains("hidden")) openFinder();
      else closeFinder();
    },
    search: () => {
      if (prefs.get("activeTab", null) === "chat") {
        $("chat-input").focus();
      } else {
        switchTab("notes");
        $("note-search").focus();
      }
    },
    //: On a board, "?" is the board's own sheet (INBOX 566); everywhere else
    //: the app's.
    help: () => {
      if (typeof wbCommandsLive === "function" && wbCommandsLive() && typeof wbOpenHelpSheet === "function") wbOpenHelpSheet();
      else openShortcuts();
    },
    newNote: () => startNewNote(),
    quickNote: () => openQuickNote(),
    pasteNote: () => pasteClipboardAsNote(),
    newDocument: () => {
      switchTab("documents");
      createDocument();
    },
    todaysNote: () => openTodaysPage(),
    toggleCompanion: () => {
      if (typeof nameMarkBuddyToggle === "function") nameMarkBuddyToggle();
    },
    recordMeeting: openMeetingRecorder,
    forceReload: forceReloadApp,
    toggleTheme,
    undo: performUndo,
    redo: performRedo,
    selectionActions: openSelectionMenuFromKeyboard,
    // Ctrl+S means "save what I am editing", and which editor that is depends
    // on the tab. Documents already autosave, so there it is an explicit
    // checkpoint rather than the only way the text survives.
    //: `saveWhatIsInFront` rather than this two-line dispatch. It knew about
    //: Documents and Capture only, so with the Settings modal open Ctrl+S ran
    //: `saveEntry()` on the note composer behind it, and the settings-aware
    //: code written for INBOX 74 sat unreachable further down the same keydown
    //: handler. See that function for the measurement.
    save: () => saveWhatIsInFront(),
    // Same "which surface depends on the tab" dispatch as `save` above.
    // The Documents tab keeps its own, more capable find-and-replace
    // (`#doc-find-bar`), it can see inside the editor's own textarea,
    // which no generic DOM search can. Everywhere else opens the global
    // one below, scoped to whichever tab-page is currently visible.
    find: () => {
      if (prefs.get("activeTab", null) === "documents") toggleDocFindBar(true);
      else openGlobalFind();
    },
    //: Acts on whichever editing surface has focus, which is the only sane
    //: reading of "write here": the document textarea, or one live-view
    //: paragraph. `inlineAiOpen` refuses (with a toast) anywhere else rather
    //: than opening a bar whose submit could not work.
    inlineAi: () => {
      const active = document.activeElement;
      if (typeof inlineAiOpen === "function" && active instanceof HTMLTextAreaElement) {
        inlineAiOpen(active);
      }
    },
    newChat: () => {
      switchTab("chat");
      newChatConversation();
      $("chat-input")?.focus();
    },
    // The one shortcut whose whole value is being reachable in a hurry: a
    // local model three minutes into the wrong answer is the moment nobody
    // wants to go looking for a button.
    stopAI: () => chatController?.abort(),
    agentMode: () => {
      switchTab("chat");
      const toggle = $("tools-toggle");
      if (!toggle) return;
      toggle.checked = !toggle.checked;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    },
    quickSketch: openSketch,
    askAgent: toggleAgentPalette,
    askAtlas: () => askAtlasAbout(""),
    whiteboard: () => switchTab("whiteboard"),
    settings: () => openSettingsModal(),
    attachNote: () => {
      switchTab("chat");
      openNotePicker();
    },
    lanPanel: () => openLanPanel(),
    // Same call the status bar's own Back/Forward buttons already make.
    navigateBack: () => stepTabHistory(-1),
    navigateForward: () => stepTabHistory(1),
  };
  actions[id]?.();
}

function resetShortcuts() {
  prefs.remove(SHORTCUT_STORE);
  shortcuts = loadShortcuts();
  restampShortcutHints();
  renderShortcutList();
  toast("Shortcuts reset to their defaults.");
}

let capturingShortcut = null; // the id being rebound, or null

// The same list is mounted twice, in the ? overlay and in Settings →
// Keyboard shortcuts. Rendering both from one function is what keeps them
// from drifting apart; two copies of this logic is how one of them goes stale.
const SHORTCUT_LIST_IDS = ["shortcut-list", "shortcut-list-settings"];
const SHORTCUT_STATUS_IDS = ["shortcut-status", "shortcut-status-settings"];

function setShortcutStatus(text) {
  for (const id of SHORTCUT_STATUS_IDS) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
}

function setShortcutStatusError(isError) {
  for (const id of SHORTCUT_STATUS_IDS) {
    document.getElementById(id)?.classList.toggle("error", isError);
  }
}

function renderShortcutList() {
  for (const listId of SHORTCUT_LIST_IDS) {
    const list = document.getElementById(listId);
    if (list) buildShortcutList(list);
  }
}

//: **The key chip is the button** (INBOX 810, Row actions): a column of
//: thirty-one bordered "Change" buttons was the heaviest thing in the pane,
//: louder than the keys it changes. Pressing the keys starts the rebind and
//: pressing them again cancels it; its title says which ("Change" or
//: "Cancel"), and the back-to-default is a quiet icon after the words.
function buildShortcutList(list) {
  list.replaceChildren();
  for (const [id, def] of Object.entries(shortcuts)) {
    const li = document.createElement("li");
    const capturing = capturingShortcut === id;
    const change = document.createElement("button");
    change.className = "ghost small quiet shortcut-key";
    change.type = "button";
    const combo = document.createElement("kbd");
    combo.textContent = capturing ? "Press keys…" : def.keys;
    if (capturing) combo.classList.add("capturing");
    //: A pencil says the keys are the way to change them (INBOX 1300 C22).
    const pen = document.createElement("i");
    pen.className = `ph ${capturing ? "ph-x" : "ph-pencil-simple"} shortcut-edit`;
    pen.setAttribute("aria-hidden", "true");
    change.append(combo, pen);
    change.title = capturing ? "Cancel" : "Change";
    change.setAttribute(
      "aria-label",
      capturing ? `Cancel changing the shortcut for: ${def.label}` : `Change the shortcut for: ${def.label}, now ${def.keys}`
    );
    change.addEventListener("click", () => {
      capturingShortcut = capturingShortcut === id ? null : id;
      setShortcutStatus(
        capturingShortcut ? "Press the keys you want, or Escape to cancel." : ""
      );
      renderShortcutList();
      //: The list was redrawn: the focus goes back to the same row's keys.
      list.querySelector(`[data-shortcut="${id}"] .shortcut-key`)?.focus();
    });

    const label = document.createElement("span");
    label.textContent = def.label;
    li.dataset.shortcut = id;
    li.append(change, label);

    // Only offer "default" when it isn't already the default.
    const changed = def.keys !== DEFAULT_SHORTCUTS[id].keys;
    if (changed) {
      const revert = document.createElement("button");
      revert.className = "ghost small quiet icon-only";
      revert.type = "button";
      setLabel(revert, "ph:arrow-counter-clockwise");
      revert.title = `Back to ${DEFAULT_SHORTCUTS[id].keys}`;
      revert.setAttribute("aria-label", revert.title);
      revert.addEventListener("click", () => {
        shortcuts[id].keys = DEFAULT_SHORTCUTS[id].keys;
        saveShortcutOverrides();
        renderShortcutList();
      });
      li.appendChild(revert);
    }
    list.appendChild(li);
  }
  //: Thirty-one rows: typed to (row 1643, `listFilter`).
  listFilter(list, { label: "Filter shortcuts" })?.refresh();
}

// While rebinding, this handler runs before everything else and swallows the
// keypress: otherwise pressing Ctrl+K to rebind it would also open the
// palette you're trying to move.
function captureShortcutKey(event) {
  if (!capturingShortcut) return false;
  if (event.key === "Escape") {
    capturingShortcut = null;
    setShortcutStatus("");
    renderShortcutList();
    return true;
  }
  const combo = comboFromEvent(event);
  if (!combo) return true; // still holding modifiers

  const clash = Object.entries(shortcuts).find(
    ([otherId, def]) => otherId !== capturingShortcut && def.keys === combo
  );
  if (clash) {
    // Refuse rather than silently stealing it, two actions on one key means
    // one of them quietly stops working.
    setShortcutStatusError(true);
    setShortcutStatus(`${combo} is already used for "${clash[1].label}".`);
    return true;
  }
  shortcuts[capturingShortcut].keys = combo;
  saveShortcutOverrides();
  capturingShortcut = null;
  setShortcutStatusError(false);
  setShortcutStatus(`Set to ${combo}.`);
  renderShortcutList();
  return true;
}

function openShortcuts() {
  capturingShortcut = null;
  setShortcutStatus("");
  renderShortcutList();
  //: **The editor's rows come from the editor's own table**
  //: (DOCUMENTS_PLAN Phase 4 item 4: "a `?` shortcut sheet generated from the
  //: same table so the two cannot disagree"). documents.js is lazily loaded,
  //: so the section says where its contents are rather than sitting empty
  //: when this dialog is opened before that bundle has ever been fetched.
  ensureModule("appPalette").then(() => renderToolShortcutList($("shortcut-list-tools")));
  const editorList = $("shortcut-list-documents");
  const editorNote = $("shortcut-list-documents-note");
  if (editorList && typeof renderDocShortcutSheet === "function") {
    renderDocShortcutSheet(editorList);
    editorNote?.classList.add("hidden");
  } else if (editorNote) {
    editorNote.classList.remove("hidden");
  }
  //: The board's rows, from the board's own table (whiteboard-commands.js),
  //: and the section scrolled into view when "?" was pressed on a board.
  const boardList = $("shortcut-list-whiteboard");
  const boardNote = $("shortcut-list-whiteboard-note");
  const onBoard = typeof wbCommandsLive === "function" && wbCommandsLive();
  if (boardList && typeof renderWbShortcutSheet === "function") {
    renderWbShortcutSheet(boardList);
    boardNote?.classList.add("hidden");
  } else if (boardNote) {
    boardNote.classList.remove("hidden");
  }
  $("shortcuts-overlay").classList.remove("hidden");
  if (onBoard) $("shortcut-head-whiteboard")?.scrollIntoView({ block: "start" });
  $("shortcuts-close").focus();
}
function closeShortcuts() {
  // Stop listening for a rebind. Without this, closing the dialog mid-capture
  // leaves the handler swallowing every keypress in the app, the shortcut you
  // just set appears dead, and so does everything else.
  capturingShortcut = null;
  $("shortcuts-overlay").classList.add("hidden");
}

$("shortcuts-close").addEventListener("click", closeShortcuts);
wireBackdropClose($("shortcuts-overlay"), () => closeShortcuts());

document.addEventListener("keydown", (e) => {
  if (e.key !== "Tab") return;
  const overlay = activeOverlay();
  if (!overlay) return;
  // `[tabindex]` and `[contenteditable]` were missing, and both are real
  // omissions rather than tidiness: an element made focusable with
  // `tabIndex = 0` is focusable to the browser and invisible to this filter,
  // so Tab would step onto it and the trap would not know where it was, the
  // graph canvas (`graph.js` sets `tabIndex = 0` on `#graph-box`) is exactly
  // that shape. `tabindex="-1"` is excluded on purpose: it means
  // programmatically focusable but *not* in the tab order, so including it
  // would invent stops the user never asked for.
  const focusables = [
    ...overlay.querySelectorAll(
      'button, [href], input, select, textarea, [contenteditable=""], ' +
        '[contenteditable="true"], [tabindex]:not([tabindex="-1"])'
    ),
  ].filter((el) => !el.disabled && el.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const outside = !overlay.contains(document.activeElement);
  if (e.shiftKey && (document.activeElement === first || outside)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (document.activeElement === last || outside)) {
    e.preventDefault();
    first.focus();
  }
});

// --- Wave F wiring ------------------------------------------------------------------

// Wave J: note search + sort, capture char count.
// Debounced (150ms, same as Library/Timeline/Graph search): this box was the
// one search input in the app with no debounce, so every keystroke tore down
// and rebuilt the whole visible note list, and with semantic search on, also
// fired a backend embedding-compare request per character typed.
let noteSearchDebounceTimeout;
$("note-search").addEventListener("input", (e) => {
  noteSearch = e.target.value.trim();
  // Nothing to save when the box is empty; the button appears when it isn't.
  // Cheap, so it stays immediate rather than waiting on the debounce below.
  $("save-search").classList.toggle("hidden", !noteSearch);
  clearTimeout(noteSearchDebounceTimeout);
  noteSearchDebounceTimeout = setTimeout(() => {
    if ($("semantic-search-toggle")?.checked) loadEntries(); // trigger semantic backend search
    renderEntries();
    // After the list is on screen, never before it: the reasons are an
    // annotation on a list that is already correct, and waiting for a
    // round trip to show any notes at all would undo the debounce's point.
    refreshNoteSearchWhy();
  }, 150);
});
//: The fading order, fetched once per sort rather than per render. Empty
//: until "Forgotten first" is chosen, so nothing pays for it otherwise, and
//: on a notebook under ten notes the server answers with an empty list by
//: design (`resurface.MIN_NOTEBOOK`), which leaves the list in id order and
//: is the honest answer at that size.
let forgottenOrder = new Map();

async function loadForgottenOrder() {
  try {
    const body = await apiJson("/resurface/all?limit=500", { silent: true, cacheMs: 60000 });
    forgottenOrder = new Map((body.items || []).map((item, index) => [item.id, index]));
  } catch (error) {
    forgottenOrder = new Map();
  }
}

//: Remembered like the page size beside it (INBOX 432: it reset on reload).
try {
  const kept = prefs.get("notes-sort", null);
  if (kept && [...$("note-sort").options].some((o) => o.value === kept)) noteSort = kept;
} catch {
  /* storage blocked: newest, as before */
}
$("note-sort").value = noteSort;
if (noteSort === "forgotten") loadForgottenOrder().then(() => renderEntries());
$("note-sort").addEventListener("change", async (e) => {
  noteSort = e.target.value;
  try {
    prefs.set("notes-sort", noteSort);
  } catch {
    /* storage blocked: this session only */
  }
  notesCurrentPage = 1; // a re-sort can move a note off whatever page it was on
  //: Awaited before the render, not alongside it: painting the list in id
  //: order and re-sorting it a moment later is a list that jumps under the
  //: hand of whoever just chose the sort.
  if (noteSort === "forgotten") await loadForgottenOrder();
  renderEntries();
});
$("notes-page-size").value = notesPageSize;
$("notes-page-size").addEventListener("change", (e) => {
  notesPageSize = e.target.value;
  prefs.set("notes-page-size", notesPageSize);
  notesCurrentPage = 1;
  renderEntries();
});
$("notes-page-prev").addEventListener("click", () => {
  if (notesCurrentPage <= 1) return;
  notesCurrentPage -= 1;
  renderEntries();
  $("entries-heading").scrollIntoView({ block: "start", behavior: reducedMotionWanted() ? "auto" : "smooth" });
});
$("notes-page-next").addEventListener("click", () => {
  notesCurrentPage += 1; // clamped back down inside renderEntries if this overshoots
  renderEntries();
  $("entries-heading").scrollIntoView({ block: "start", behavior: reducedMotionWanted() ? "auto" : "smooth" });
});
//: **The files a note's text points at, as attachment cards** (INBOX 440 (2)),
//: in the Capture box and in a note's edit form alike. The text is where an
//: attachment lives (what is saved, what the AI reads, what an export keeps),
//: so the cards are drawn from it on every keystroke, and Rename and Remove
//: edit that text rather than a second list beside it.
//:
//: One host for every kind, where there were two strips: pictures above the
//: tags as thumbnail chips and other files below the attach row as file
//: cards, and the chip strip's pattern matched links too, so a PDF was drawn
//: in both (measured: two cards for one file in Capture). A picture staged
//: in Capture (`staged:`, its bytes still in this tab) is a card too: it had
//: none, because the pattern only knew `/media` and `/files`. And a file
//: waiting for the note's id (`captureStagedFiles`) joins the same row,
//: dashed, rather than standing in a third place.
//:
//: Ids or elements: the edit form builds its host and textarea and calls this
//: *before* the row is in the document, so a lookup by id would find neither.
function renderEntryAttachmentChips(boxId = "entry-content", hostId = "entry-attachment-chips") {
  const box = hostId instanceof HTMLElement ? hostId : $(hostId);
  const textarea = boxId instanceof HTMLElement ? boxId : $(boxId);
  if (!box || !textarea) return;
  const pattern = /!?\[([^\]]{0,200})\]\(((?:\/media\/|\/files\/|staged:)[^)\s]{1,500})\)/g;
  const matches = [...textarea.value.matchAll(pattern)];
  const staged = textarea.id === "entry-content" ? captureStagedFiles : [];
  box.replaceChildren();
  box.classList.toggle("hidden", matches.length + staged.length === 0);
  for (const [markdown, name, url] of matches) {
    const image = stagedImageByUrl(url);
    box.append(attachmentCard({ name, url, markdown, textarea, staged: !!image, size: image?.file.size }));
  }
  for (const file of staged) {
    box.append(attachmentCard({ name: file.name, url: "", staged: true, file, size: file.size }));
  }
}

//: What `capture-ask.js` and the staging code call when the list of files
//: waiting for Save changes: they are drawn in the same row now.
function renderCaptureFiles() {
  renderEntryAttachmentChips();
  //: The clear button counts staged files as something to clear (field-clear.js).
  if (typeof fieldClearSyncAll === "function") fieldClearSyncAll();
}

//: The Capture foot's count (CHAT_PLAN, INBOX 63: "a live N words · reading
//: time in the foot"), in the words a document's own count line uses
//: (`renderDocCounts`, documents.js) and at its 220 words a minute, so one
//: piece of writing reads the same length in both places.
//: **One count for a text, everywhere it is shown** (CHAT_PLAN section 2,
//: the documents row): words, characters and lines as `wc -w`, `wc -m` and
//: `wc -l` give them, and the reading time. The server's twin is
//: `ai/utilities.py` `counts`; tests/test_text_utilities.py holds both to
//: `wc` on one fixture. Here, not in documents.js, because the composer
//: below counts at boot and the documents bundle is lazy.
const TEXT_READING_WPM = 220;
function textCounts(text) {
  const value = String(text || "");
  const words = (value.match(/\S+/g) || []).length;
  const minutes = words / TEXT_READING_WPM;
  const read = !words ? "" : minutes < 1 ? "under a min" : minutes < 60 ? `${Math.round(minutes)} min read` : `${(minutes / 60).toFixed(1)}h read`;
  let chars = 0;
  for (const _ of value) chars += 1;
  return { words, chars, lines: (value.match(/\n/g) || []).length, minutes, read };
}

function captureCountText(text) {
  const { words, read } = textCounts(text);
  const head = `${words.toLocaleString()} word${words === 1 ? "" : "s"}`;
  return words ? `${head} · ${read}` : head;
}

$("entry-content").addEventListener("input", (e) => {
  $("entry-count").textContent = captureCountText(e.target.value);
  // Keep a draft so a half-typed thought survives a reload or a stray tab
  // switch: losing one is the most annoying thing this app could do.
  //: Whitespace alone is not a draft (INBOX 431 follow-up: the box came
  //: back holding three blank lines after a reload, which hid the empty
  //: placeholder). Newlines left behind by a removed image or a stray Enter
  //: must not be kept and restored as if they were writing.
  if (e.target.value.trim()) prefs.set("captureDraft", e.target.value);
  else prefs.remove("captureDraft");
  renderEntryAttachmentChips();
  // The "go to it" link belongs to the note you just saved, not the one you
  // are now writing: drop it as soon as typing starts.
  $("save-status").querySelector(".jump-to-note")?.remove();
});

//: A staged picture's bytes live in this tab and nowhere else, so a restored
//: draft cannot show one, the Blob went with the page that made it. Left in,
//: the note would carry `![x](staged:img-…)` forever: a dead link that Save
//: would happily write to disk, since the rewrite only knows about images
//: staged in *this* session.
//:
//: Removed rather than kept-and-warned, because there is nothing the reader
//: can do about it and nothing to recover, the picture was never uploaded.
//: The line below says so once, so a vanished screenshot is explained rather
//: than mysterious.
const STAGED_IN_DRAFT = /!\[[^\]\n]{0,200}\]\(staged:[^)\n]{1,120}\)\n?/g;

// Restore an unsaved draft on load.
(() => {
  const stored = prefs.get("captureDraft", null);
  if (!stored) return;
  const draft = stored.replace(STAGED_IN_DRAFT, "");
  const lostImages = draft !== stored;
  //: A draft that is only blank lines (older builds saved those, and removing
  //: a staged image can leave nothing else) restores as nothing, so the
  //: box stays empty and its placeholder shows.
  if (!draft.trim()) {
    prefs.remove("captureDraft");
    if (lostImages) toast("Your restored draft only held images that were never uploaded, so it was cleared.");
    return;
  }
  const box = $("entry-content");
  box.value = draft;
  autoGrow(box); // a long restored draft shouldn't arrive in a one-line box
  $("entry-count").textContent = captureCountText(draft);
  renderEntryAttachmentChips();
  const status = $("save-status");
  if (status) status.textContent = "Restored your unsaved draft.";
  //: A toast rather than the status line for the images, because this runs at
  //: module load, before the lock screen is even answered, and every status
  //: line written here is overwritten by the boot sequence that follows.
  //: Measured: the line came back empty in a driven browser. `toast` queues
  //: and shows once the app is up, which is when there is somebody to read it.
  if (lostImages) {
    toast(
      "Your restored draft mentioned images that were never uploaded, they " +
        "could not come back, so those lines were removed.",
    );
  }
})();

//: The title and the tags are the draft too (INBOX 434): measured, a reload
//: brought the words back and dropped both. `resetCaptureForm` clears them.
for (const [id, key] of [["entry-title", "captureDraftTitle"], ["entry-tags", "captureDraftTags"]]) {
  const field = $(id);
  try {
    field.value ||= prefs.get(key, null) || "";
  } catch {}
  field.addEventListener("input", () => {
    try {
      if (field.value.trim()) prefs.set(key, field.value);
      else prefs.remove(key);
    } catch {}
  });
}

$("sketch-btn").addEventListener("click", () => openSketch());
// Wave H: dictation + read-aloud.
$("mic-note").addEventListener("click", () =>
  toggleDictation($("mic-note"), $("entry-content"))
);
$("mic-chat").addEventListener("click", () =>
  toggleDictation($("mic-chat"), $("chat-input"))
);
$("speak-btn").addEventListener("click", () => speakText($("ai-answer").textContent));

// PWA (WORLD_CLASS_PLAN decision 49): sw.js caches stamped files, vendored
// libraries and icons, and shows offline.html when the server is not
// running; it never caches the shell or the API. When a new service worker
// takes over (after an update), reload once so the page never runs new HTML
// against stale cached CSS/JS (Wave O fix).
if ("serviceWorker" in navigator) {
  // Only reload when an EXISTING worker is replaced (a real update): not
  // on the first install, whose clients.claim() also fires controllerchange
  // and would reload the page mid-setup (Wave O fix).
  const hadController = Boolean(navigator.serviceWorker.controller);
  // sw.js stays at the root, not in js/: a worker only controls its own path.
  // The app version rides on the URL: the worker names its cache for it, and
  // a release is a new URL, so the browser installs the new worker at once.
  // `updateViaCache: "none"` because a `?v=` URL is served as immutable.
  const appVersion = /^\?v=(\d+\.\d+\.\d+)/.exec(lazyAssetStamp("/js/app.js"))?.[1] || "dev";
  navigator.serviceWorker
    .register(`/sw.js?v=${appVersion}`, { updateViaCache: "none" })
    .catch(() => {});
  let swReloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || swReloaded) return;
    swReloaded = true;
    location.reload();
  });
}

// Install as an app (WORLD_CLASS_PLAN 25d): Settings, About. Chromium offers
// the install through `beforeinstallprompt`, which is held until the button is
// pressed; it fires nothing once installed, and `appinstalled` hides the row.
// iPhone has no such event, so the row says how instead of offering a button.
const installPrompt = { event: null };
function renderInstallRow() {
  const row = $("about-install-row");
  if (!row) return;
  const installed =
    window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
  const iphone =
    /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const canPrompt = Boolean(installPrompt.event);
  row.classList.toggle("hidden", installed || !(canPrompt || iphone));
  $("about-install").classList.toggle("hidden", !canPrompt);
  $("about-install-note").textContent = canPrompt
    ? "Opens in its own window, with its own icon."
    : "On iPhone: tap Share, then Add to Home Screen.";
}
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt.event = event;
  renderInstallRow();
});
window.addEventListener("appinstalled", () => {
  installPrompt.event = null;
  renderInstallRow();
});
$("about-install")?.addEventListener("click", async () => {
  const offered = installPrompt.event;
  if (!offered) return;
  installPrompt.event = null; // the event can be used once
  offered.prompt();
  await offered.userChoice.catch(() => {});
  renderInstallRow();
});
renderInstallRow();

// The generative brand emblem's initial draw (Wave O) moved to settings.js's
// own tail (§88.3 item 4): renderBrandLogo() itself stays here (used far
// outside Settings), but the accent/appearance state it reads through
// renderEmblem() moved, so calling it from this bare line, before
// settings.js has loaded: threw ReferenceError. See settings.js's header.

// Whiteboard subsystem moved to frontend/js/whiteboard.js (loaded via a
// second <script> tag in index.html, after this file). Everything that
// used to live here, board/card CRUD, sketch drawing, mind-mapping,
// export, move/resize: is defined there now, in the same shared global
// scope, so nothing here needs to change to keep calling it.

// ======================= FLOATING FORMAT MENU =======================

// --- Global Drag and Drop & Paste Image Upload for Textareas ---
document.addEventListener("dragover", (e) => {
  if (e.target.tagName && e.target.tagName.toLowerCase() === 'textarea') {
    e.preventDefault();
    e.target.classList.add("drag-over");
  } else if (Array.from(e.dataTransfer?.types || []).includes("Files") && fileDropBox(e.target)?.kind === "codemirror") {
    //: Taken, so the window's drop-to-Library veil does not claim it.
    e.preventDefault();
  }
});

document.addEventListener("dragleave", (e) => {
  if (e.target.tagName && e.target.tagName.toLowerCase() === 'textarea') {
    e.preventDefault();
    e.target.classList.remove("drag-over");
  }
});

// ROADMAP.md §89 item 5, fixed: this pair matches ANY `<textarea>` by tag
// name alone, which `#chat-input` is too: so a dropped/pasted image there
// used to route through `handleFileUpload` (written for the Notes/Document
// composer: inserts `![Uploading…]()` markdown placeholders into the
// textarea's own text) instead of the chat composer's real image-staging
// system, `attachImageFiles()`/`renderImageAttachments()`, the same one
// the composer's "+" button already uses, with its own attachment cards and
// its own toast-on-failure error handling. The symptom matched exactly:
// literal markdown-image syntax landing in the message box, and no
// attachment card, because nothing was ever staged through that system.
// `#chat-input` is excluded here and given its own branch instead of a
// second global listener, so there is exactly one place either kind of
// composer's drop/paste behaviour is decided.
function _isChatComposer(target) {
  return target && target.id === "chat-input";
}

//: **The note box under the editor, not only a bare textarea** (INBOX 434).
//: Capture and the edit form are a live editor mounted over their textarea,
//: so a paste or a drop lands on the editor's own element: measured, an
//: image pasted into Capture and a file dropped on it both vanished. The
//: listeners run in the capture phase, ahead of the editor's own handling.
function fileDropBox(el) {
  if (el?.tagName === "TEXTAREA") return el;
  //: **The document editor is neither** (docdog-1026): its engine sits under
  //: `#doc-editor`, not `.note-surface`, so a screenshot pasted or a picture
  //: dropped into a document did nothing at all, while the "/" menu's Image
  //: row promised both. Its surface answers the same box interface. A code
  //: document is text, and keeps what it was given.
  if (el?.closest?.("#doc-editor")) {
    const surface = window.docSurface?.();
    return surface && !surface.classList.contains("doc-content-code") ? surface : null;
  }
  const host = el?.closest?.(".note-surface")?.noteSurfaceHost;
  return host instanceof HTMLTextAreaElement ? host : null;
}

//: Files dragged in from outside the window load the drop-to-Library module
//: (file-drop.js), which starts itself and takes only the drops nothing else did.
document.addEventListener("dragenter", (e) => {
  if (Array.from(e.dataTransfer?.types || []).includes("Files")) ["/css/file-drop-lazy.css", "/js/file-drop.js"].forEach(lazyScript);
});

document.addEventListener("drop", async (e) => {
  const box = fileDropBox(e.target);
  if (!box || (box !== e.target && !e.dataTransfer?.files.length)) return;
  e.preventDefault();
  e.stopPropagation();
  box.classList.remove("drag-over");
  //: Dropped where the pointer is, not where the caret was.
  if (box.kind === "codemirror") {
    const at = box.view.posAtCoords({ x: e.clientX, y: e.clientY });
    if (at !== null) box.setSelection(at);
  }

  if (box.id === "command-palette-input") return agentStageFiles(Array.from(e.dataTransfer.files));
  if (_isChatComposer(box)) {
    const files = Array.from(e.dataTransfer.files);
    const images = files.filter((f) => f.type.startsWith("image/"));
    if (images.length) await attachImageFiles(images);
    if (images.length < files.length) {
      toast("Only images can be attached to a chat message right now.", "info");
    }
    return;
  }

  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/") || f.type.startsWith("application/") || f.type.startsWith("text/") || f.type.startsWith("video/") || f.type.startsWith("audio/"));
  if (!files.length) return;

  await handleFileUpload(box, files);
}, true);

document.addEventListener("paste", async (e) => {
  const box = fileDropBox(e.target);
  if (!box) return;
  const items = (e.clipboardData || e.originalEvent.clipboardData).items;
  const files = [];
  for (const item of items) {
    if (item.kind === 'file') {
      files.push(item.getAsFile());
    }
  }
  if (!files.length) return;
  //: A spreadsheet or Word copy carries a picture of what it copied beside
  //: the text; in a document the words win (table and rich paste), and only a
  //: clipboard with no text at all is a picture to upload.
  if (box.kind === "codemirror" && e.clipboardData.getData("text/plain")) return;
  // Don't prevent default entirely unless we have files, otherwise normal paste breaks
  e.preventDefault();
  e.stopPropagation();

  if (box.id === "command-palette-input") return agentStageFiles(files);

  if (_isChatComposer(box)) {
    const images = files.filter((f) => f.type.startsWith("image/"));
    if (images.length) await attachImageFiles(images);
    if (images.length < files.length) {
      toast("Only images can be attached to a chat message right now.", "info");
    }
    return;
  }

  await handleFileUpload(box, files);
}, true);

//: Files waiting to become attachments on a note that does not exist yet.
//:
//: **Why staging rather than uploading immediately.** `/media/upload`, the
//: only endpoint the composer could reach, accepts nine image types and
//: `.pdf`, and that allowlist is not paranoia to widen: `/media/{name}`
//: serves inline from the app's own origin, so an `.html` or `.svg` landing
//: there is stored XSS, and the AI can write to that folder too. So a
//: `.docx`, a `.txt` or a code file dropped into the composer got a 415 and
//: a red toast, while **the same file attached fine to an already-saved
//: note** through `POST /entries/{id}/files`, whose allowlist covers about
//: sixty types precisely because attachments are served as downloads.
//:
//: The difference was never the file. It was that the composer has no note
//: id yet. So the file waits here until Save produces one, and then takes
//: the attachment path it should have taken all along, which also gets it
//: a real row, a card with a delete button, and a place in the Library.
//:
//: Images are deliberately *not* staged: an image in the middle of a
//: paragraph is content, and it needs to be inline markdown at the point in
//: the text where it was dropped, not an attachment at the bottom.

//: The one place that knows the staged placeholder's shape, so the renderer
//: and the rewrite cannot disagree about it (moved from app.js, its only users
//: are here).
function stagedImageUrl(key) {
  return `${STAGED_URL_PREFIX}${key}`;
}

//: **Images wait for the note too now.**
//:
//: The composer used to `POST /media/upload` the moment a picture was dropped
//: or pasted, and the comment above explained why that was different from the
//: files beside it: an image is *content*, it has to land as inline markdown
//: at the point in the text where it was dropped. That is still true, and it
//: was never a reason for the file to survive a note nobody saved. Every
//: abandoned draft with a pasted screenshot left a row in the Library and a
//: file on disk, which is exactly the leak asked about: "files should only be
//: staged and not permanently saved while uploaded to a note that hasnt been
//: saved yet".
//:
//: So the markdown goes in immediately, pointing at a `staged:<key>` url the
//: renderer resolves to the local Blob, and Save swaps every one of those for
//: the real `/media/...` url the upload returns. The bytes never leave the
//: browser until there is a note to attach them to.
//: Swap every `staged:<key>` for the url its upload produced. A pure string
//: function on purpose: it is the step that decides what gets *saved*, so it
//: is the step worth being able to test on its own.
function rewriteStagedUrls(content, urlByKey) {
  let out = content;
  for (const [key, url] of Object.entries(urlByKey)) {
    out = out.split(stagedImageUrl(key)).join(url);
  }
  return out;
}

//: Upload everything staged in the composer and return `{key: url}`. Throws
//: on the first failure, which is deliberate: Save must not write a note
//: whose picture is a dead `staged:` url, and it must not silently drop the
//: picture either: the same rule `commitStagedImages` follows for chat.
async function commitCaptureImages() {
  const urlByKey = {};
  for (const image of captureStagedImages) {
    const form = new FormData();
    form.append("file", image.file);
    const uploaded = await apiJson("/media/upload", {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    urlByKey[image.key] = uploaded.url;
  }
  return urlByKey;
}

function clearStagedImages() {
  for (const image of captureStagedImages) {
    //: An object URL is a document-lifetime reference to the bytes; dropping
    //: the array alone leaks them for as long as the tab is open.
    if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
  }
  captureStagedImages = [];
}

async function uploadStagedFiles(entryId) {
  if (!captureStagedFiles.length) return;
  const staged = captureStagedFiles;
  captureStagedFiles = [];
  renderCaptureFiles();
  let failures = 0;
  for (const file of staged) {
    const form = new FormData();
    form.append("file", file);
    // `api.upload` (F5): multipart keeps its own type, and both headers ride.
    try {
      await api.upload(`/entries/${entryId}/files`, form);
    } catch (error) {
      failures++;
      toast(`${file.name}: ${error.message}`, true);
    }
  }
  // Only mentioned when it worked; a failure already said so, per file, and
  // "attached 2 files" under two error toasts would be the app arguing with
  // itself.
  if (failures < staged.length) await loadEntries();
}

async function handleFileUpload(textarea, files) {
  // The capture composer is the one place that can stage: it is the only
  // textarea whose content becomes a note with an id a moment later. A
  // document's own editor writes into a document, which has no attachment
  // table, so it keeps the inline-markdown path for everything.
  const canStage = textarea.id === "entry-content";
  const images = canStage ? files.filter((f) => f.type.startsWith("image/")) : files;
  const others = canStage ? files.filter((f) => !f.type.startsWith("image/")) : [];
  if (others.length) {
    captureStagedFiles.push(...others);
    renderCaptureFiles();
    toast(
      others.length === 1
        ? `“${others[0].name}” will be attached when you save.`
        : `${others.length} files will be attached when you save.`
    );
  }
  if (!images.length) return;
  files = images;

  const cursorPosition = textarea.selectionStart;
  const selectionEnd = textarea.selectionEnd;
  const originalText = textarea.value;

  //: **The composer stages instead of uploading**, see `captureStagedImages`.
  //: Everywhere else (the document editor) still uploads inline, because a
  //: document has an id from the moment it exists and nothing to wait for.
  //:
  //: Written before the "Uploading…" placeholder below rather than after it:
  //: assigning `textarea.value` moves the selection, so a branch that ran
  //: afterwards and re-sliced against `selectionEnd` would cut the note in a
  //: different place than it meant to.
  if (canStage) {
    let inserted = "";
    for (const file of files) {
      const key = `img-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      captureStagedImages.push({
        key,
        file,
        objectUrl: URL.createObjectURL(file),
        name: file.name,
      });
      inserted += `![${file.name}](${stagedImageUrl(key)})\n`;
    }
    textarea.value =
      originalText.slice(0, cursorPosition) + inserted + originalText.slice(selectionEnd);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    const at = cursorPosition + inserted.length;
    textarea.setSelectionRange(at, at);
    toast(
      files.length === 1
        ? `“${files[0].name}” will be saved with the note.`
        : `${files.length} images will be saved with the note.`,
    );
    return;
  }

  let textToInsert = "";
  for (const file of files) {
    textToInsert += `![Uploading ${file.name}…]()\n`;
  }
  textarea.value = originalText.substring(0, cursorPosition) + textToInsert + originalText.substring(selectionEnd);
  textarea.dispatchEvent(new Event('input', { bubbles: true }));

  let added = 0;
  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await apiJson("/media/upload", {
        method: "POST",
        headers: authHeaders(),
        body: formData
      });
      // Image syntax (`![]()`) unconditionally became an <img> at render
      // time (renderInlineMarkdown): a non-image upload (PDF, docx, audio)
      // failed to decode as an image and the img.onerror handler then
      // reported it as "filename deleted", which is actively wrong: the
      // file uploaded fine and is sitting at res.url. Link syntax for
      // anything that isn't actually an image.
      const fileMarkdown = file.type.startsWith("image/")
        ? `![${res.filename}](${res.url})\n`
        : `[${res.filename}](${res.url})\n`;
      textarea.value = textarea.value.replace(`![Uploading ${file.name}…]()\n`, fileMarkdown);
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      added += 1;
    } catch (err) {
      // Reported directly (§89 item 2): an upload failure rendered as if it
      // were the AI's own message: literal error text left sitting in the
      // note/document content, indistinguishable from something the user
      // actually typed. A toast is a notification; content is what gets
      // saved. Removing the placeholder outright (not replacing it with
      // more text) leaves the composer exactly as if the file were never
      // dropped/pasted, which is the honest description of what happened.
      console.error("Upload failed", err);
      textarea.value = textarea.value.replace(`![Uploading ${file.name}…]()\n`, "");
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      toast(err.message || `Couldn't upload "${file.name}".`, true);
    }
  }
  if (added) pushTextUndo("Added a file", textarea, originalText, textarea.value);
}

// ROADMAP.md Tier 2 §16c: paste and drag-drop already reached Capture (the
// global textarea handler above matches any `<textarea>`, and `#entry-content`
// is one): checked live before building, and both already worked. The one
// genuinely missing path was a file-picker button; the only "attach" control
// near Capture was for linking existing *notes* to a chat message, not
// uploading a new file. Reuses the same `handleFileUpload` the paste/drop
// paths already use, so all three input paths insert identically.
if ($("entry-attach-file")) {
  $("entry-attach-file").addEventListener("click", () => {
    $("entry-attach-file-input").click();
  });
  $("entry-attach-file-input").addEventListener("change", async (e) => {
    const files = Array.from(e.target.files);
    if (files.length) await handleFileUpload($("entry-content"), files);
    e.target.value = ""; // so picking the same file twice still fires "change"
  });
}

if ($("entry-attach-existing")) {
  $("entry-attach-existing").addEventListener("click", async () => {
    const upload = await pickMediaDialog();
    if (!upload) return;
    // Same inline-markdown insertion shape handleFileUpload's own success
    // path uses, minus the upload, this is already sitting on disk.
    const textarea = $("entry-content");
    const cursorPosition = textarea.selectionStart;
    const original = textarea.value;
    const markdown = `![${upload.original_name}](${upload.url})\n`;
    textarea.value =
      original.substring(0, cursorPosition) + markdown + original.substring(textarea.selectionEnd);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

//: Off when the reader turned single-key shortcuts off (stored in this
//: browser, like the other keyboard preferences); on by default.
function singleKeysOn() {
  try {
    return prefs.get("singleKeys", null) !== "off";
  } catch {
    return true;
  }
}

$("pref-single-keys").checked = singleKeysOn();

//: Ctrl+K types ahead while the lazy palette loads (CI, 2026-10-06): the
//: overlay opens at once; app-palette.js keeps the words and runs an Enter.
{
  const load = window.openPalette;
  window.openPalette = (...args) => {
    const input = $("palette-input");
    if (!window.paletteEarly) {
      //: What was selected, before the palette's box takes the focus (Count
      //: words and Insert template act on it, app-palette.js `paletteCaught`).
      const held = window.getSelection();
      const range = held?.rangeCount ? held.getRangeAt(0).cloneRange() : null;
      const early = (window.paletteEarly = { returnFocus: document.activeElement, selection: String(held || ""), range });
      early.onKey = (e) => e.key === "Enter" && (e.preventDefault(), (early.enter = true));
      input.value = "";
      input.addEventListener("keydown", early.onKey);
      $("palette-overlay").classList.remove("hidden");
      input.focus();
    }
    // Still set after the load: the file never came, so close it here.
    return load(...args).finally(() => {
      const early = window.paletteEarly;
      if (!early) return;
      window.paletteEarly = null;
      input.removeEventListener("keydown", early.onKey);
      $("palette-overlay").classList.add("hidden");
      early.returnFocus?.focus?.();
    });
  };
}
