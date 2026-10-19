// settings-panes.js: autogrow, account, web search, backups, document import,
// the catalogue row runner (the deep links themselves are in reveal-targets.js,
// loaded on first use since 2026-10-05). Moved out of app.js on 2026-09-26 as one
// contiguous range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md).
// A classic script sharing app.js's globals, loaded in app.js's old order;
// nothing in an earlier file calls into it while the page loads
// (scratchpad/appjs-map.js --check).

// --- textareas that grow with what you type -----------------------------------
// A fixed-height box for "capture a thought" or "magic add" hides everything
// but the last couple of lines the moment a note runs long, which is exactly
// when you most want to see it (user request). Height follows content, up to a
// cap so the page never gets pushed around; past that it scrolls.
// 480, not 340: "about a third of the screen" (asked for) is the 0.35 cap
// below on any window under ~1370px tall; 340 undercut it on a 1080p display.
const AUTOGROW_MAX_PX = 480;

// How much of the window a growing box may take before it scrolls instead.
//
// A flat 340px is most of a laptop window's chat area and nearly all of a
// phone's: the box kept growing and the conversation it was about disappeared
// above it. The cap is the *smaller* of the two, so a tall screen keeps the
// familiar 340 and a short one keeps its conversation.
const AUTOGROW_MAX_VIEWPORT = 0.35;
//: The most of the window a hand-dragged composer may take (INBOX 111).
const COMPOSER_DRAG_MAX_VIEWPORT = 0.7;

//: Where a hand-dragged composer height is remembered. A preference about how
//: you write, so it outlives the session that set it.
const COMPOSER_HEIGHT_KEY = "chat-composer-height";

function autoGrowLimit(el) {
  // A height the user dragged to wins over both defaults, they have said, in
  // the most direct way an interface allows, how tall they want this box.
  const chosen = Number(el.dataset.maxPx || 0);
  if (chosen > 0) return chosen;
  return Math.min(AUTOGROW_MAX_PX, Math.round(window.innerHeight * AUTOGROW_MAX_VIEWPORT));
}

function autoGrow(el) {
  if (!el) return;
  //: **A note editor's mirror is not a box anyone sees** (INBOX 424i). Once
  //: the capture box's editor has mounted, the textarea is laid over it at
  //: zero opacity and sized by the stylesheet to the editor's own box
  //: (`.note-surface > textarea.note-surface-mirror`); the editor is what
  //: grows. Every keystroke mirrors the text into it with an `input` event,
  //: and this function then paid a forced layout per keystroke (the
  //: `offsetParent` read below, then the measure) to size a box that is not
  //: drawn: measured at 4x CPU, 448ms of a 50-character typing run. A class
  //: check reads no layout.
  if (el.classList.contains("note-surface-mirror")) return;
  // **A hidden textarea reports scrollHeight 0, and sizing to that collapses
  // it.** This is the reported "the capture box is short at the bottom and
  // only opens up when I click in it": the box was measured while its section
  // was display:none, sized to nothing, and the first `focus` re-ran this with
  // the box finally on screen, which looked like clicking made it grow.
  //
  // One caller already re-measured after a sub-tab switch, which fixed that
  // one route in. It did not fix arriving from another TAB with Capture
  // already the remembered section, and it never could, the bug is that a
  // measurement taken while invisible is meaningless, and the right place to
  // say so is here, once, rather than at every call site that might run early.
  //
  // `offsetParent` is null for a display:none element and for any element
  // inside one, which is exactly the condition. (It is also null for
  // position:fixed elements: none of the app's autogrow boxes are fixed, and
  // the cost of being wrong would be one un-resized box, not a collapsed one.)
  if (el.offsetParent === null) {
    // Marked so the box gets its size the moment it becomes visible, instead
    // of waiting for a focus that may never come.
    el.dataset.autogrowPending = "1";
    return;
  }
  delete el.dataset.autogrowPending;
  if (el.dataset.resizing) return; // a grabber drag is in progress; it wins
  if (autoGrowStillFits(el)) return;
  // Reset first: without it the height only ever ratchets upwards, because
  // scrollHeight is measured against the height already set.
  el.style.height = "auto";
  const limit = autoGrowLimit(el);
  // **A height somebody dragged to is a floor, not just a ceiling.** Driven in
  // a browser: dragging the composer taller stored the new height and then
  // snapped the box straight back to one line, because this took
  // `min(scrollHeight, limit)` and an empty box has a scrollHeight of one row.
  // The setting was saved and instantly undone, which is worse than not
  // offering the drag at all.
  //
  // So a hand-set height is the height. It is what "manually adjustable"
  // means: the box stays where it was put, and only scrolls once the text
  // outgrows it.
  //: **Revised, by direct instruction**: "should auto expand to about a
  //: third of the screen if large amounts of text are in it but should be
  //: able to be lowered in height manually and should go back to normal
  //: when empty or the text reduces." A fixed hand-set height (the previous
  //: rule) is exactly what stopped the box expanding. Now a drag *below*
  //: the automatic height is a cap, a drag *above* it is a floor.
  //: **Revised again (INBOX 111)**: "when I drag the height of the chat bar,
  //: it snaps back to what it was with or without text in it." The earlier
  //: rule also forgot the drag the moment the box was empty, exempting only
  //: the release of the drag itself; the next `input` event on an empty box
  //: (a keystroke, then backspace) forgot it anyway, which from the chair
  //: is the same snap-back one keystroke later. A dragged height is a
  //: preference and is kept until the next drag; what "go back to normal
  //: when empty" still gets is the *automatic* growth collapsing, which
  //: `chosen < auto` below already does for a drag under the automatic
  //: height.
  const chosen = Number(el.dataset.maxPx || 0);
  const viewportLimit = Math.min(AUTOGROW_MAX_PX, Math.round(window.innerHeight * AUTOGROW_MAX_VIEWPORT));
  //: A drag may exceed the automatic ceiling (that is what the drag is for),
  //: but not the window: past this the conversation above is gone entirely.
  const dragLimit = Math.round(window.innerHeight * COMPOSER_DRAG_MAX_VIEWPORT);
  const auto = Math.min(el.scrollHeight, viewportLimit);
  //: **INBOX 37: an empty box is pinned to its CSS floor, not measured.**
  //: Reported with a screenshot: Reminders' Magic add field taller than its
  //: own Add button on the owner's desktop shell; measured 44/44 (equal) in
  //: this sandbox's headless Chromium, on the bundled system font, in light
  //: mode. `el.scrollHeight` on an *empty* box is still a function of the
  //: rendered line box, which is a function of the actual font in use, and
  //: that is exactly what differs: a fallback font before a webfont has
  //: finished loading, a heavier weight dark mode's own stylesheet may pick,
  //: a different system font entirely on another OS. Every one of those can
  //: round `scrollHeight` a pixel or two past the button's fixed height,
  //: which is why this was invisible here and not there. `min-height` in
  //: rem is none of that, it is a fixed length the browser converts from the
  //: root font size alone, so reading it back is the one measurement that
  //: cannot drift with the textarea's own font. Only while there is nothing
  //: to measure: the moment real content wraps past this floor, `scrollHeight`
  //: takes back over below, which is the box actually growing to fit typed
  //: text rather than a static height with nothing behind it.
  const next = chosen > 0
    ? (chosen < auto ? chosen : Math.max(auto, Math.min(chosen, dragLimit)))
    : !el.value.trim()
      //: An empty box is its own natural height (`rows` and the placeholder,
      //: measured at height:auto above), floored at min-height, never *just*
      //: min-height. Reported with a screenshot: the capture box at 44px
      //: under a two-line placeholder, the second line clipped, a scrollbar
      //: on an empty textarea. "A cleared box must not keep the height of
      //: what was in it" still holds: scrollHeight at height:auto is the
      //: empty box's own size, not the old text's.
      ? Math.max(parseFloat(getComputedStyle(el).minHeight) || 0, auto)
      : Math.min(el.scrollHeight, limit);
  el.style.height = `${next}px`;
  const overflows = el.scrollHeight > next;
  //: What this height was measured against, read while the layout the
  //: `scrollHeight` above just flushed is still clean (see `autoGrowVisible`).
  el._autoGrownValue = el.value;
  el._autoGrownFor = autoGrowInputs(el);
  el.style.overflowY = overflows ? "auto" : "hidden";
  // What this function chose, so a later resize can be told apart from a drag
  // by the user: the two are indistinguishable to a ResizeObserver otherwise.
  el.dataset.autoHeight = String(next);
  fitComposerToDock(el);
}

//: **The keystroke that changes nothing costs one read, not two writes and
//: three layouts** (the performance pass, 2026-09-27). `autoGrow` runs on
//: every `input`, and its full path resets the height to `auto`, measures,
//: writes the height back and measures again, then the composer's fit reads
//: the card: measured on the chat composer, 40 keys forced 82 style recalcs
//: and 82 layouts, and every key's input-to-paint took two frames (32ms,
//: `scratchpad/ui-sweeps/perfpass.js typing`).
//:
//: Most keys only add a character to the end of what is there. Text that
//: only grew at its end cannot make the box's natural height smaller, so
//: if the text still fits the height already set (or the box is already
//: capped and scrolling), there is nothing to do: one `scrollHeight` read
//: answers it, and nothing is written. Anything else (a deletion, a paste in
//: the middle, a width, window, font or drag change since the last measure,
//: a hand-set height) takes the full path below, exactly as before.
function autoGrowStillFits(el) {
  const before = el._autoGrownValue;
  if (typeof before !== "string" || el.dataset.maxPx) return false;
  const now = el.value;
  if (now.length <= before.length || !now.startsWith(before)) return false;
  const set = parseFloat(el.style.height);
  if (!Number.isFinite(set) || set <= 0) return false;
  const natural = el.scrollHeight;
  if (el._autoGrownFor !== autoGrowInputs(el)) return false;
  const capped = el.style.overflowY === "auto";
  if (natural > set && !capped) return false;
  el._autoGrownValue = now;
  return true;
}

//: Everything besides the text that a grown box's height depends on: its
//: width (`offsetWidth`, which a scrollbar appearing does not change), the
//: window's height (the cap), a height dragged by hand, and the font.
function autoGrowInputs(el) {
  return `${el.offsetWidth}|${window.innerHeight}|${el.dataset.maxPx || ""}|${getComputedStyle(el).font}`;
}

//: **Every visible box whose height could be wrong, and only those** (INBOX
//: 424h). A tab or section switch used to run `autoGrow` on every visible
//: autogrow box: each one a height write, a forced layout for its
//: `scrollHeight`, another write, another read, box after box: measured at
//: 4x CPU, 70 to 110ms of every tab switch. A box that was measured on
//: screen, has the same text and the same width, font and caps as then, is
//: already the height `autoGrow` would give it. So every check is read first,
//: in one pass (one layout for all of them), and only the boxes that were
//: measured while hidden or whose inputs changed are grown, after it.
function autoGrowVisible() {
  const due = [];
  for (const box of document.querySelectorAll("textarea.autogrow")) {
    if (box.classList.contains("note-surface-mirror") || box.offsetParent === null) continue;
    if (
      box.dataset.autogrowPending ||
      box._autoGrownValue !== box.value ||
      box._autoGrownFor !== autoGrowInputs(box)
    ) {
      due.push(box);
    }
  }
  for (const box of due) autoGrow(box);
}

//: A composer smaller than this is not a composer. The floor exists so a very
//: short window trims the box rather than erasing it, at that point the
//: conversation scrolls and the user can drag the window instead.
const MIN_COMPOSER_PX = 44;

// A hand-dragged composer height, trimmed to the room the chat card has.
//
// The drag is a preference and it is kept as one: `dataset.maxPx` and
// localStorage are **not** touched here. Only the applied height is trimmed,
// so a box dragged to 380px on a large monitor comes back to 380px the moment
// there is room for it again. Writing the trimmed value back would be the app
// quietly forgetting a setting because the window was small once.
//
// The measurement is the card's own overflow rather than any sum of the
// furniture above it. Every number this file has ever guessed at, a viewport
// fraction, a rem cap, the dock's height: has been wrong within two sessions,
// because the dock gains controls and the tab strip wraps. `scrollHeight -
// clientHeight` is the browser answering "by how much does this not fit",
// which needs no maintenance and is exact.
// It iterates because one subtraction does not converge. The conversation
// above the dock is `flex: 1 1 auto` with a floor, so some of the height the
// composer gives back is immediately taken by the message list growing into
// it: measured: a 56px trim cleared only 24px of a 88px overflow. Each pass
// is exact about what it can see, and three of them have been enough at every
// size driven so far; the cap is there so a layout that somehow oscillates
// costs four reflows rather than the frame.
const COMPOSER_FIT_PASSES = 4;

function fitComposerToDock(box) {
  if (!box || box.id !== "chat-input") return;
  const card = document.getElementById("chat-main");
  // Nothing to measure while the tab is hidden; switchTab re-runs this.
  if (!card || !card.getClientRects().length) return;
  for (let pass = 0; pass < COMPOSER_FIT_PASSES; pass += 1) {
    const overflow = Math.round(card.scrollHeight - card.clientHeight);
    if (overflow <= 0) return;
    const now = Math.round(box.getBoundingClientRect().height);
    const next = Math.max(MIN_COMPOSER_PX, now - overflow);
    if (next >= now) return; // already as small as it is allowed to be
    // Set before the style write: the ResizeObserver below reads this to
    // decide whether a height change was a drag, and a trim must never be
    // recorded as one: that is how a preference gets eaten.
    box.dataset.autoHeight = String(next);
    box.style.height = `${next}px`;
    box.style.overflowY = box.scrollHeight > next ? "auto" : "hidden";
  }
}

// The trim depends on the window, so it has to be redone when the window
// changes. Re-running `autoGrow` rather than `fitComposerToDock` alone is what
// lets the box grow *back* towards the dragged height when the window gets
// bigger: autoGrow re-applies the preference, and the fit trims it again only
// if it still does not fit.
function refitComposer() {
  const box = document.getElementById("chat-input");
  if (box) autoGrow(box);
  fitChatEmpty();
}

//: **The welcome fits its pane, or it gets smaller** (the owner, 2026-09-24:
//: "the new chat page has a scrollbar as the suggested try asking stuff makes
//: it scroll"). Measured at 1440x720 with no model connected: the pane is
//: 295px and the welcome 350px, so a new chat opened on a scrollbar. Below
//: its own natural height the welcome drops the emblem and tightens its
//: spacing (`.chat-empty.is-short`, 08-consistency.css), which is 110px back.
//: The choice is made against the welcome's *full* height, and that is never
//: read by taking the class off: doing so resized the pane whenever the pane's
//: own height followed its content, the ResizeObserver fired on it, and the
//: two chased each other every frame (the owner, 2026-09-24: after closing
//: the skill hint above the composer "the whole new chat page started
//: viciously stuttering jumping up and down"). The full height is read while
//: the welcome is full; while it is compact, the height saved at the switch
//: plus what the welcome has grown since (the chips arrive late). A change
//: under 4px, or one this function caused, does nothing.
function fitChatEmpty() {
  const pane = document.getElementById("chat-messages");
  const empty = pane && pane.querySelector(".chat-empty");
  if (!empty) return;
  const room = pane.clientHeight;
  if (!room) return;
  const short = empty.classList.contains("is-short");
  const now = empty.offsetHeight;
  const full = short ? Number(empty.dataset.fullHeight || 0) + (now - Number(empty.dataset.shortHeight || now)) : now;
  const want = room + 4 < full ? true : room >= full + 4 ? false : short;
  if (want === short) return;
  const now2 = performance.now();
  if (now2 - (fitChatEmpty.lastFlip || 0) < 500) return;
  fitChatEmpty.lastFlip = now2;
  if (want) {
    empty.dataset.fullHeight = String(full);
    empty.classList.add("is-short");
    empty.dataset.shortHeight = String(empty.offsetHeight);
  } else {
    empty.classList.remove("is-short");
  }
}

//: `ring-held` holds `.chat-dock:focus-within`'s accent ring off while the
//: focus in the composer is the app's doing rather than the reader's. See the
//: call in `switchTab` for the measurement that produced it, and
//: `.chat-dock.ring-held` in 04-chat-dock-appearance.css for what it turns off.
//:
//: A class rather than a `blur()` because the caret has to stay where it is:
//: the whole point of focusing the composer on arrival is that you can type
//: straight away, and taking the focus back to fix the ring would undo that.
//:
//: **Everything here is a hoisted `function` and the class name is a literal.**
//: `switchTab` can run before this line does (the app restores the last tab at
//: startup), so a `const` holding the name would be in its temporal dead zone
//: at the one moment that matters, and a module-level IIFE binding the
//: listeners would run before `.chat-dock` is necessarily in the document. The
//: listeners are therefore bound on the first suppression instead, which is
//: also the first moment the dock is certain to exist.
function chatDockSuppressRing() {
  const dock = document.querySelector(".chat-dock");
  if (!dock) return;
  //: Three ways the focus becomes the reader's: they type, they press
  //: something in the dock, or they leave and come back. `focusout` covers
  //: the last on its own, since the ring is only ever drawn while something
  //: in here has focus, so releasing the hold as focus leaves means the next
  //: focus, however it arrives, rings normally. Bound once (the dock element
  //: itself remembers), on the dock rather than per control: all three
  //: bubble.
  if (!dock.dataset.ringWired) {
    dock.dataset.ringWired = "1";
    for (const type of ["keydown", "pointerdown", "focusout"]) {
      dock.addEventListener(type, chatDockReleaseRing);
    }
  }
  dock.classList.add("ring-held");
}

function chatDockReleaseRing() {
  const dock = document.querySelector(".chat-dock");
  if (dock) dock.classList.remove("ring-held");
}

// The chat composer can be dragged taller, and remembers it.
//
// Asked for directly: *"there should be a max height that the chat text bar
// can grow to before it gets a scrollbar. the height should also be manually
// adjustable."* Both halves: the cap above, and this.
//
// The native resize grabber does the dragging; all this has to do is notice
// the result and stop `autoGrow` from immediately undoing it on the next
// keystroke. A drag is told from a grow by comparing against the height
// autoGrow last set: anything else was a hand on the corner.
function initComposerResize() {
  const box = $("chat-input");
  if (!box || box.dataset.resizeReady) return;
  box.dataset.resizeReady = "1";

  //: A saved drag is no longer applied on load: the box starts at its
  //: automatic size and a drag is remembered only until the box is emptied
  //: (see autoGrow). The key is still cleared here for profiles that have
  //: one from before.
  try { prefs.remove(COMPOSER_HEIGHT_KEY); } catch { /* storage may be unavailable */ }

  //: **Double-tap the grabber to put it back.** Asked for directly: "allow
  //: double tapping the bottom expansion corner of the chat text box to reset
  //: it to the regular height." A dragged height is sticky by design (it
  //: survives reloads, see above), so without this the only way back to the
  //: automatic height was to drag it to *exactly* the right size by hand, 
  //: which is not a thing anyone can do.
  //:
  //: Scoped to the corner rather than the whole box: a double-click in the
  //: text is how you select a word, and stealing that would trade one small
  //: annoyance for a much larger one. The grabber is ~16px square at the
  //: bottom-right, and a little slack around it costs nothing because the
  //: only thing in that corner *is* the grabber.
  const GRABBER = 22;
  box.addEventListener("dblclick", (event) => {
    const rect = box.getBoundingClientRect();
    const inCorner =
      event.clientX >= rect.right - GRABBER && event.clientY >= rect.bottom - GRABBER;
    if (!inCorner) return;
    event.preventDefault();
    delete box.dataset.maxPx;
    try {
      prefs.remove(COMPOSER_HEIGHT_KEY);
    } catch {
      /* private mode: there was nothing stored to remove */
    }
    // The inline height a drag left behind has to go too, or `autoGrow`'s own
    // reset measures against it and the box never shrinks back.
    box.style.height = "auto";
    autoGrow(box);
    toast("Composer height reset.");
  });

  if (typeof ResizeObserver !== "function") return;
  // The observer used to re-run autoGrow on every size change, including
  // the ones the grabber drag itself was making: autoGrow reset the height,
  // the drag set it again, the observer fired again (reported: "it just
  // spasms and fails"). While the pointer is down on the grabber nothing
  // fights the drag; the final height is recorded once on release. The
  // deferred frame stays: a synchronous autoGrow inside the callback is
  // the "ResizeObserver loop" console error.
  let dragging = false;
  const record = () => {
    const height = Math.round(box.getBoundingClientRect().height);
    const automatic = Number(box.dataset.autoHeight || 0);
    if (!height || Math.abs(height - automatic) <= 2) return;
    box.dataset.maxPx = String(height);
    try { prefs.set(COMPOSER_HEIGHT_KEY, String(height)); } catch { /* private mode */ }
    requestAnimationFrame(() => autoGrow(box));
  };
  box.addEventListener("pointerdown", (event) => {
    const rect = box.getBoundingClientRect();
    dragging = event.clientX >= rect.right - GRABBER && event.clientY >= rect.bottom - GRABBER;
    if (dragging) box.dataset.resizing = "1";
  });
  window.addEventListener("pointerup", () => {
    if (!dragging) return;
    dragging = false;
    delete box.dataset.resizing;
    record();
  });
  const observer = new ResizeObserver(() => {
    if (dragging) return;
    record();
  });
  observer.observe(box);
}

function initAutoGrow() {
  for (const el of document.querySelectorAll("textarea.autogrow")) {
    if (el.dataset.autogrowReady) continue;
    el.dataset.autogrowReady = "1";
    el.addEventListener("input", () => autoGrow(el));
    // Also on programmatic changes, templates, the Remind button, a cleared form.
    el.addEventListener("focus", () => autoGrow(el));
    autoGrow(el);
  }
  initComposerResize();
}

function watchOverlays() {
  let queued = false;
  // The app toggles classes constantly while streaming a chat answer, so this
  // observer sees a lot of traffic it doesn't care about. Ignore anything that
  // isn't an overlay, then coalesce the rest into one check per frame, the
  // lock must never become a cost on the hot path.
  const touchesOverlay = (record) => {
    const target = record.target;
    if (target instanceof Element && target.matches(OVERLAY_SELECTOR)) return true;
    // An added/removed node may BE an overlay (the lightbox) or contain one.
    const isOverlay = (node) =>
      node instanceof Element &&
      (node.matches(OVERLAY_SELECTOR) || node.querySelector(OVERLAY_SELECTOR) !== null);
    return [...record.addedNodes, ...record.removedNodes].some(isOverlay);
  };

  const observer = new MutationObserver((records) => {
    if (queued || !records.some(touchesOverlay)) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      syncScrollLock();
    });
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true, // lightbox-style overlays appended at runtime
    attributes: true,
    attributeFilter: ["class"], // the `hidden` toggle on existing dialogs
  });
  syncScrollLock();
}

// --- account & security ------------------------------------------------------------

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

// --- Account & security: other devices (LAN mode) -----------------------------
//
// "Allow other devices on this network" (WORLD_CLASS_PLAN section 12, Brief
// 15). The bind happens when the app starts, so the switch says what it will
// do and when: `restart_required` from the server is the whole of that
// answer. On asks for the password, like turning sign-in off, and for the
// same reason: an unlocked screen is not proof of knowing it.

// --- Privacy: where your data went (GET /privacy/receipt) ---------------------
//
// WORLD_CLASS_PLAN section 2, standout 5: "a page that proves, from the app's
// own logs, that nothing left the machine". The record is the server's audit
// hook, which sees every connection and name lookup the app's process makes;
// this pane only reads it. Two ranges on one `.seg`: since this launch, and
// since the ledger on disk began. Nothing here can change a setting: the
// switches listed at the bottom are facts, each set where it lives.

let privacyRange = "launch";

for (const button of document.querySelectorAll("#privacy-range [data-range]")) {
  button.addEventListener("click", () => {
    privacyRange = button.dataset.range;
    renderPrivacyRange();
  });
}

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

let prefsCache = null;
// Set by savePrefs() to the PUT's own promise while it is in flight, and
// awaited here first (INBOX 73, see savePrefs' own comment): without this,
// re-showing the Preferences section (closing and reopening Settings does,
// via showSettingsSection) fires this function's fresh GET concurrently
// with an unfinished save, and whichever one the server answers first wins
// -- reproduced with the GET winning, which replaced prefsCache wholesale
// with the pre-save value and left the checkbox showing it permanently,
// not just for the moment the save was in flight.
let prefsSaveInFlight = null;

//: Moved here from app.js (Brief 89, app.js's gzip ratchet): it is a
//: preferences write, beside the reader it awaits; `startApp` calls it after
//: every boot script has loaded.
// The browser is the only thing that knows where the user actually is. The
// server may be running in UTC, a container, a NAS, a machine whose clock was
// never set: and every relative time the AI computes ("in 10 minutes",
// "tomorrow at 9") is resolved against that. So the zone is reported once at
// startup, and again whenever it changes (travel, or a DST shift).
//
// Only the IANA NAME is sent, never coordinates: "Australia/Brisbane" is what
// makes the arithmetic right, and it is far less identifying than a location.
async function reportTimezone() {
  let zone = "";
  try {
    zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return; // an environment without Intl still works, just on server time
  }
  //: Awaited, not read straight off `prefsCache` (A2): every `startApp` step
  //: runs in parallel, so this one used to reach the comparison before the
  //: boot GET had answered, find `prefsCache` still null, and PUT the same
  //: zone the server already had on every single cold start. With the shared
  //: reader the comparison has something to compare.
  await loadPreferences().catch(() => null);
  //: The locale's first day of the week, as a Python weekday (Intl says 1 for
  //: Monday to 7 for Sunday). `weekInfo` is missing in older engines, and
  //: then the server's Monday stands. Reported with the zone, only on change.
  let weekDay = null;
  try {
    const info = new Intl.Locale(navigator.language).weekInfo;
    if (info && Number.isInteger(info.firstDay)) weekDay = (info.firstDay - 1) % 7;
  } catch {
    weekDay = null;
  }
  const body = {};
  if (zone && !(prefsCache && prefsCache.timezone === zone)) body.timezone = zone;
  if (weekDay !== null && !(prefsCache && prefsCache.week_start_locale === weekDay)) {
    body.week_start_locale = weekDay;
  }
  if (!Object.keys(body).length) return;
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify(body),
    silent: true,
  }).catch(() => prefsCache);
}

//: **One GET /preferences per boot** (WORLD_CLASS_PLAN A2). The whole of
//: `startApp` runs its steps in parallel, and three of them wanted the
//: preferences: the settings restore, `loadTemplates` (custom templates and
//: saved searches live in the same payload) and `reportTimezone`. Each did its
//: own `apiJson("/preferences")`, so a cold start asked for the same document
//: twice and then decided what to do with the second copy. Measured: two GETs
//: at 311 ms and 290 ms on this sandbox, of 24 boot fetches.
//:
//: This is `fetchDashStats`'s shape, for the same reason: the cache if it is
//: filled, otherwise the one request already in flight, otherwise a new one.
//: Every PUT in this file assigns its own response to `prefsCache`, so the
//: cache is current after a save and a caller that has just written does not
//: need `refresh`; pass it where a *server-side* change is expected (another
//: window, or a job that writes preferences behind the app's back).
let prefsInflight = null;

function loadPreferences({ refresh = false } = {}) {
  if (!refresh && prefsCache) return Promise.resolve(prefsCache);
  if (prefsInflight) return prefsInflight;
  //: Silent: the one boot caller that cared about the error is the settings
  //: restore, and behind the lock screen a 401 here is the lock screen's
  //: message, not a second toast about preferences (§35E).
  prefsInflight = apiJson("/preferences", { silent: true })
    .then((prefs) => {
      prefsCache = prefs;
      paintUserMarks();
      return prefs;
    })
    .finally(() => {
      prefsInflight = null;
    });
  return prefsInflight;
}

async function renderPrefs() {
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
  $("pref-semantic-auto-install").checked = prefsCache.semantic_auto_install ?? true;
  //: The saved look, and its controls (avatars.js).
  if (typeof setOwnNameMarkStyle === "function") {
    setOwnNameMarkStyle(prefsCache.avatar_style || {});
    mountProfileLook();
  }
  $("pref-bin-days").value = prefsCache.recycle_bin_days;
  $("pref-chat-retention").value = prefsCache.conversation_retention_days ?? 0;
  $("pref-search-min-sim").value = prefsCache.search_min_similarity;
  $("pref-search-z-margin").value = prefsCache.search_relative_z_margin;
  $("pref-style").value = prefsCache.communication_style;
  $("pref-voice").value = prefsCache.composer_voice;
  $("pref-week-start").value = prefsCache.week_start || "auto";
  $("pref-insight").value = prefsCache.insight_level || "one";
  $("pref-profile").value = prefsCache.user_profile;
  $("pref-profile-enabled").checked = prefsCache.profile_enabled;
  paintUserMarks();
  updateProfileCount();
  if (prefsCache.session_idle_ttl_minutes) {
    $("account-idle-ttl").value = prefsCache.session_idle_ttl_minutes;
  }
  $("pref-notif-mute-except-reminders").checked = Boolean(
    prefsCache.notifications_muted_except_reminders
  );
  $("pref-smart-punctuation").checked = prefsCache.smart_punctuation === true;
  $("pref-autocorrect").checked = prefsCache.autocorrect !== false;
  $("pref-link-offers").checked = prefsCache.link_offers !== false;
  $("prefs-status").textContent = "";
  //: The fields now hold what the server holds, so nothing is unsaved: this
  //: also covers the reopen, since `showSettingsSection` re-renders.
  markPrefsSaved();
}

// --- Settings → Web search ------------------------------------------------------
//
// Its own screen, and its own save. Web search used to be four controls inside
// Preferences, which is why every error message that said "Settings → Web
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
// Settings → Background tasks directly in a fresh session (never having
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
  $("pref-autonomous-interval").value = prefsCache.autonomous_tasks_interval_hours || 6;
  $("pref-autonomous-model").value = prefsCache.autonomous_tasks_model || "";
  $("pref-battery-mode").checked = Boolean(prefsCache.battery_efficient_mode);
  $("pref-smart-model-routing").checked = prefsCache.smart_model_routing_enabled ?? true;
  toggleAutonomousPanel();
}

async function renderWebSearch() {
  prefsCache = await apiJson("/preferences");
  $("pref-web-search").checked = Boolean(prefsCache.web_search_enabled);
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
    detail.className = "muted";
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

// A source checkout (start.sh/start.bat) auto-updates via `git pull` before
// the server even starts, asked for directly, the same "popup after
// login, only if the app auto updates" the packaged-Windows dialog above
// gives, for the other install type that also auto-updates but had no way
// to say so. GET /update/source-status is a plain env-var read with no
// network call and self-clears after one read, so this never fires twice
// for the same real update and never blocks on being offline.
async function checkForSourceUpdateNotice() {
  const result = await apiJson("/update/source-status", { silent: true }).catch(() => null);
  if (!result || !result.just_updated) return;
  showSourceUpdatedDialog(result);
}

//: Which checkbox in Settings mirrors which one elsewhere in the app. Two
//: controls for one preference is a reasonable convenience and a reliable way
//: to get them out of step; this is the list that keeps them honest.
const MIRRORED_PREFS = {
  autonomous_tasks_enabled: ["pref-autonomous-tasks", "skills-auto-toggle"],
  auto_tag_enabled: ["pref-auto-tag", "skills-auto-tag"],
  auto_link_enabled: ["pref-auto-link", "skills-auto-link"],
};

// Save one preference without rebuilding the whole object from the DOM.
//
// `savePrefs` reads every control on the Preferences screen and PUTs the lot,
// which is fine when that screen is what you are looking at and wrong when it
// is not: a control on another panel that saved directly left `prefsCache`
// stale, and the next `savePrefs` overwrote it from a checkbox nobody had
// touched. Anything outside the Preferences form should come through here.
async function setPreference(key, value) {
  try {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ [key]: value }),
    });
    for (const id of MIRRORED_PREFS[key] || []) {
      const box = $(id);
      if (box && box.checked !== value) box.checked = value;
    }
    if (key === "autonomous_tasks_enabled") {
      $("autonomous-settings-panel")?.classList.toggle("hidden", !value);
    }
  } catch (error) {
    toast(error.message || "Couldn't save that setting.", true);
  }
}

async function savePrefs(options = {}) {
  const quiet = options?.quiet === true;
  clearTimeout(prefsAutoSaveTimer);
  try {
    const binDaysRaw = Number($("pref-bin-days").value);
    const recycleBinDays = Number.isFinite(binDaysRaw) && binDaysRaw >= 1
      ? Math.min(365, Math.round(binDaysRaw))
      : 30;
    $("pref-bin-days").value = recycleBinDays;
    const minSimRaw = Number($("pref-search-min-sim").value);
    const searchMinSim = Number.isFinite(minSimRaw) ? Math.min(1, Math.max(0, minSimRaw)) : 0.25;
    const zMarginRaw = Number($("pref-search-z-margin").value);
    const searchZMargin = Number.isFinite(zMarginRaw) ? Math.min(3, Math.max(0, zMarginRaw)) : 0.5;
    $("pref-search-min-sim").value = searchMinSim;
    $("pref-search-z-margin").value = searchZMargin;
    // Only this section's own fields: Background tasks' checkboxes save
    // independently via `setPreference` (see `renderAutonomousSettings`: a
    // form never rendered this session sent stale defaults and overwrote them).
    const payload = {
      display_name: $("pref-display-name").value.trim(),
      avatar_style: typeof ownNameMarkStyle === "function" ? ownNameMarkStyle() : undefined,
      recycle_bin_days: recycleBinDays,
      conversation_retention_days: Number($("pref-chat-retention").value) || 0,
      search_min_similarity: searchMinSim,
      search_relative_z_margin: searchZMargin,
      communication_style: $("pref-style").value,
      user_profile: $("pref-profile").value,
      profile_enabled: $("pref-profile-enabled").checked,
      notifications_muted_except_reminders:
        $("pref-notif-mute-except-reminders").checked,
      smart_punctuation: $("pref-smart-punctuation").checked,
      autocorrect: $("pref-autocorrect").checked,
      link_offers: $("pref-link-offers").checked,
    };
    // INBOX 73: "'Mute notifications except reminders' toggle disables
    // itself when the settings close." Reproduced two ways with Playwright
    // route interception: (1) check the box, Save, close and reopen
    // Settings before the PUT resolves -- renderPrefs' own fresh GET can
    // win the race and replace prefsCache wholesale with the pre-save
    // value; (2) delay the PUT leaving the browser at all (a slow
    // connection) so a concurrent GET genuinely reaches the server first
    // -- the checkbox then stayed wrong even after the PUT went on to
    // succeed, since nothing re-read it afterwards. Two matched fixes:
    // write the change into prefsCache immediately, before the await, so
    // any render mid-flight already sees it (renderPrefs still overwrites
    // this with the server's answer once its own GET lands, this is only
    // for the window before that); and hold the PUT's promise in
    // `prefsSaveInFlight` so renderPrefs (above) waits for it first
    // instead of racing it, which is what closes case 2.
    if (prefsCache) Object.assign(prefsCache, payload);
    prefsSaveInFlight = apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    try {
      prefsCache = await prefsSaveInFlight;
    } finally {
      prefsSaveInFlight = null;
    }
    $("prefs-status").textContent = "Saved.";
    markPrefsSaved();
    // The microbes and mycelium backgrounds grow from the display name
    // (bg-art.js), so a new name regrows them now rather than next launch.
    if (typeof bgArtRefreshSeed === "function") bgArtRefreshSeed();
    //: **A toast as well as the inline word** (INBOX 263). Reported: "no
    //: visual confirmation popup shows when I use ctrl s to save my
    //: preferences settings". The inline "Saved." is beside the button, which
    //: is at the bottom of the last group: press ctrl+s while reading the
    //: field you just changed at the top of the section and the only feedback
    //: the app gives is off screen. `toast` is DESIGN.md's recipe for a brief
    //: confirmation and it is the same one every other save in the app uses,
    //: so this also stops Preferences being the one place a save says
    //: nothing.
    if (!quiet) toast("Preferences saved.");

    // Reflect a name change immediately if the dashboard is showing.
    if (typeof renderDashboardGreeting === "function") renderDashboardGreeting();
    paintUserMarks();
  } catch (error) {
    $("prefs-status").textContent = error.message;
    toast(error.message, true);
  }
}

//: **Preferences is the only section in Settings that does not save on its
//: own**, and that was true without being said anywhere: every other section
//: writes on change (`setPreference`, `saveSearchProvider`, the appearance
//: controls), so someone who has learned that everywhere else closes this one
//: and loses the field they just typed. Reported as "there is no visual
//: indications that the preferences settings are the only settings that dont
//: save automatically".
//:
//: Two things say it. A standing line at the top of the section says it
//: before anything is typed, and this mark says it again at the moment it
//: starts to matter: the button fills and names the state, so the thing you
//: have to press is the thing that changed.
let prefsDirty = false;

//: **The profile saves itself** (the owner: "remove the need for saving
//: preferences in the settings and just have it auto save like the rest of
//: the settings, it is too unintuitive for it to be the only settings page
//: in which you need to do that", and "my shuffled avatar reset and didnt
//: persist", which is the same cause: a shuffle nobody pressed Save after).
//: Every change schedules one quiet save a moment later, the same save the
//: button used to run, so a burst of typing is one request, not one per key.
let prefsAutoSaveTimer = 0;
function markPrefsDirty() {
  clearTimeout(prefsAutoSaveTimer);
  prefsAutoSaveTimer = setTimeout(() => savePrefs({ quiet: true }), 700);
  if (prefsDirty) return;
  prefsDirty = true;
  const button = $("prefs-save");
  if (button) {
    button.classList.add("primary");
    button.textContent = "Save preferences";
  }
  const note = $("prefs-unsaved");
  if (note) note.classList.remove("hidden");
  const status = $("prefs-status");
  if (status) status.textContent = "";
}

function markPrefsSaved() {
  prefsDirty = false;
  const button = $("prefs-save");
  if (button) button.classList.remove("primary");
  const note = $("prefs-unsaved");
  if (note) note.classList.add("hidden");
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
    $("profile-avatar")?.replaceChildren(nameMark(typed || "You", 56));
    const head = $("profile-head-name");
    if (head) head.textContent = typed || "Your profile";
  });
  $("pref-profile")?.addEventListener("input", updateProfileCount);
}

//: The prompt reads the first 600 characters of About me
//: (`librarian.PROFILE_ABOUT_CAP_CHARS`); the box stops there, and the count
//: says how much is left. A profile saved before the cap may be longer, and
//: then the line says which part Atlas reads rather than hiding the rest.
const PROFILE_ABOUT_CAP = 600;

function updateProfileCount() {
  const line = $("pref-profile-count");
  const box = $("pref-profile");
  if (!line || !box) return;
  const used = box.value.length;
  line.textContent = used > PROFILE_ABOUT_CAP
    ? `${used} characters; Atlas reads the first ${PROFILE_ABOUT_CAP}.`
    : `${used} of ${PROFILE_ABOUT_CAP} characters.`;
}

// Downloads need the auth header, so plain <a href> won't do: fetch the
// bytes and hand the browser a blob instead.
async function downloadExport(kind) {
  const response = await api(`/export/${kind}`);
  // Markdown and the full backup arrive as zips; the rest are single files.
  const name =
    kind === "markdown" ? "tessellate-markdown.zip" :
    kind === "backup" ? "tessellate-backup.zip" :
    `tessellate-export.${kind}`;
  await saveFile(name, await response.blob());
}

// --- Wave F: backups UI -------------------------------------------------------------

// --- Wave F: command palette (Ctrl/Cmd-K) -------------------------------------------

// Static commands; note search results are appended live as you type.
//: Interface zoom, in one place so the slider, the +/- buttons, the keyboard
//: shortcut and the command palette cannot drift apart. Asked for directly:
//: "a nicer way to adjust zoom… + and - buttons next to the slider, hotkeys
//: like ctrl + +/-, and in the commands list".
//:
//: Same range and step as the slider in Settings -> Appearance, and it writes
//: the same key, so all four routes are literally the same control.
const ZOOM_MIN = 70;
const ZOOM_MAX = 130;
const ZOOM_STEP = 5;

function currentZoom() {
  return prefs.number("zoom", 100, { min: ZOOM_MIN, max: ZOOM_MAX }) || 100;
}

function setZoom(percent) {
  const next = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(percent / ZOOM_STEP) * ZOOM_STEP));
  prefs.set("zoom", String(next));
  const slider = $("zoom-slider");
  if (slider) slider.value = next;
  const readout = $("zoom-value");
  if (readout) readout.textContent = `${next}%`;
  applyAppearance();
  return next;
}

//: **Feedback for a control you just used, which muting must not swallow.**
//: Reported: "the mute notifications button mutes things like if I hot key
//: zooming in and out, I cant see what zoom level Im at if the notifications
//: dont appear, maybe they can appear some other way visually??"
//:
//: The answer is that this was never a notification. A notification tells you
//: about something that happened elsewhere -- a background pass, a reminder --
//: and muting it is a real preference. Confirming a key you are holding down
//: is a *readout*: it belongs on screen for a moment, centred, with no history
//: and no dismiss button, and it has nothing to do with whether the app is
//: allowed to interrupt you. Every editor with a zoom shortcut does this.
//:
//: Deliberately not recorded in the notifications centre either: "Zoom 110%"
//: is not something anyone wants to scroll back through tomorrow.
let hudTimer = null;

//: Where the HUD has to live to be seen. INBOX 86: "zoom popup does not show
//: while a dialog (Settings) is open." Two different reasons, and only one of
//: them is a z-index.
//:
//: Settings is a `.modal-overlay` div at `z-index: 1010` against the HUD's
//: 90, so it simply painted over it: that is fixed in the stylesheet. A
//: native `<dialog>` opened with `showModal()` is a harder case, because it
//: renders in the browser's top layer, which sits above *every* z-index in
//: the document, so no number would ever win. The only way in is to be inside
//: that dialog, so while one is open the HUD is moved into it and put back
//: afterwards. `hudHome` remembers where it belongs rather than assuming
//: `<body>`, the same shape `wireEscapedActionMenu` uses for menus.
let hudHome = null;

function hud(text) {
  const box = $("hud");
  if (!box) return;
  const dialog = document.querySelector("dialog[open]");
  const wanted = dialog || hudHome || document.body;
  if (box.parentElement !== wanted) {
    if (!hudHome) hudHome = box.parentElement;
    wanted.appendChild(box);
  }
  box.textContent = text;
  box.classList.remove("hidden");
  clearTimeout(hudTimer);
  hudTimer = setTimeout(() => {
    box.classList.add("hidden");
    //: Home again once it is hidden, so a dialog that closes does not take
    //: the app's only HUD element out of the document with it.
    if (hudHome && box.parentElement !== hudHome) hudHome.appendChild(box);
  }, 1100);
}
window.hud = hud;

function nudgeZoom(direction) {
  const next = setZoom(currentZoom() + direction * ZOOM_STEP);
  hud(`Zoom ${next}%`);
}

// Ctrl/Cmd with + or - . On `capture` so a focused textarea cannot swallow it,
// and `preventDefault` so the browser's own zoom does not fire as well, 
// otherwise the two stack and one press moves both.
//
// `event.key` for "-" and "=" rather than a keyCode: "+" needs Shift on most
// layouts, so the unshifted "=" is what people actually press, and both are
// accepted for the same reason every other app accepts both.
document.addEventListener(
  "keydown",
  (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      nudgeZoom(1);
    } else if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      nudgeZoom(-1);
    } else if (event.key === "0") {
      event.preventDefault();
      setZoom(100);
      hud("Zoom 100%");
    }
  },
  true
);

//: Kept at boot, not in reveal-targets.js: settings.js and settings-find.js ring a
//: Settings control with it on a plain deep link, with no catalogue row involved.
const revealTimers = new WeakMap();

//: The ring, on what the person can see. An enhanced `<select>` is a 1x1
//: clipped box behind its opener (`enhanceSelect`, and openSettingsModal's
//: own comment on the deep link that ringed nothing because of it), and a
//: checkbox is a square whose meaning is in the label beside it, so both ring
//: their visible representative.
function flashRevealed(target) {
  if (!target) return null;
  const shown =
    target.closest(".select-shell") ||
    (target.matches('input[type="checkbox"], input[type="radio"], input[type="color"], input[type="range"]')
      ? target.closest("label, .setting-row, .row")
      : null) ||
    target;
  //: Scrolled only when it is not already in the window: a scroll moves the
  //: page under a resting pointer, and the hover that follows closed a menu
  //: group the reveal had just opened (measured on the phone's note sheet).
  const box = shown.getBoundingClientRect();
  const inView = box.top >= 0 && box.left >= 0 && box.bottom <= window.innerHeight && box.right <= window.innerWidth;
  //: Inside an open menu only the menu's own list scrolls: a scroll of the
  //: page closes every open menu (`closeActionMenusOnScroll`), which took the
  //: document's Export group away the moment it was ringed on a phone.
  const menu = shown.closest(".action-menu, .dock-menu-list, .doc-dock-menu-list, [role='menu'], .sheet-card");
  if (!inView && menu) {
    for (let box = shown.parentElement; box && menu.contains(box); box = box.parentElement) {
      if (box.scrollHeight > box.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(box).overflowY)) {
        const offset = shown.getBoundingClientRect().top - box.getBoundingClientRect().top;
        box.scrollTop += offset - box.clientHeight / 2 + shown.offsetHeight / 2;
        break;
      }
    }
  } else if (!inView) {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    shown.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center", inline: "nearest" });
  }
  shown.classList.remove("feature-reveal");
  void shown.offsetWidth;
  shown.classList.add("feature-reveal");
  //: Taken off again, reduced motion included: under that setting the ring is
  //: static rather than animated, and a class nothing removes is a ring that
  //: stays for good (the Search relevance report, openSettingsModal).
  clearTimeout(revealTimers.get(shown));
  revealTimers.set(shown, setTimeout(() => shown.classList.remove("feature-reveal"), 2700));
  return shown;
}

//: A row's declaration, turned into the `run` the three lists call. The
//: order matters only for a row that wrongly carries two, which the test
//: refuses.
function catalogueRun(row) {
  if (typeof row.run === "function") return row;
  let run = () => {};
  if (row.reveal) run = () => revealFeature(row.reveal, row.arg);
  else if (row.tab) run = () => switchTab(row.tab);
  else if (typeof row.act === "function") run = row.act;
  return { ...row, run };
}

function paletteCommands() {
  //: **The documents editor's own commands, at the top, while one is open**
  //: (DOCUMENTS_PLAN Phase 4 item 4). The plan named `Ctrl+K` for an editor
  //: palette of its own, which is the chord this one already has: two
  //: palettes on one key is the collision the agent palette's comment records
  //: being caught twice. So the editor contributes a group here instead, and
  //: `docPaletteCommands` (documents.js) returns nothing at all unless the
  //: Documents tab is showing with a document in it. Guarded by `typeof`
  //: because that file is in the Library's lazy bundle and the palette opens
  //: from every tab, including before it has ever been fetched.
  const editor = typeof docPaletteCommands === "function" ? docPaletteCommands() : [];
  //: And an open map's (whiteboard-map.js, lazy for the same reason).
  if (typeof mapPaletteCommands === "function") editor.push(...mapPaletteCommands());
  //: The open board's commands, the same way (FEAT-11, whiteboard-commands.js):
  //: nothing unless a board is on screen, which needs the bundle in.
  const board = typeof wbPaletteCommands === "function" ? wbPaletteCommands() : [];
  //: Every row below declares where it goes (tests/test_catalogue_reveal.py)
  //: and `catalogueRun` makes its `run`; the editor's rows are commands on
  //: the document already open, so they keep their own.
  return [
    ...editor,
    ...board,
    { label: "ph:clipboard Go to Dashboard", tab: "dashboard", about: "Today at a glance: recent notes, reminders and widgets." },
    { label: "ph:magnifying-glass-plus Zoom in", about: "Make everything in the app a step larger.", act: () => nudgeZoom(1) },
    { label: "ph:magnifying-glass-minus Zoom out", about: "Make everything in the app a step smaller.", act: () => nudgeZoom(-1) },
    { label: "ph:arrow-counter-clockwise Reset zoom to 100%", about: "Back to the size the app was drawn at.", act: () => { setZoom(100); hud("Zoom 100%"); } },
    { label: "ph:note-pencil Go to Notes", tab: "notes", about: "Every note, with capture, filters and the reading pane." },
    { label: "ph:chat-circle Go to Chat", tab: "chat", about: "A conversation with your notebook, saved as you go." },
    { label: "ph:graph Go to Graph", tab: "graph", about: "Your notes as a map of what links to what." },
    { label: "ph:file-text Go to Documents", tab: "documents", about: "Long-form writing, with blocks, an outline and history." },
    //: Two tabs the palette could not reach. The Library holds six sub-tabs of
    //: real surfaces (documents, images, files, links, skills, contents) and
    //: the Timeline is a top-level tab, and neither had a command: a jump list
    //: missing two of the seven places you can be is the one kind of gap that
    //: teaches people not to use it.
    { label: "ph:books Go to Library", tab: "library", about: "Documents, images, files, links, skills and boards." },
    { label: "ph:clock-counter-clockwise Go to Timeline", tab: "timeline", about: "Everything you have written, by the day it happened." },
    { label: "ph:alarm Go to Reminders", tab: "reminders", about: "What is due, and what you asked to be told about." },
    // Features reachable *only* from inside one surface are exactly the ones a
    // palette has to carry, or they are found by accident or not at all.
    // The inbox is a sheet; the board's overview and find bar live on a
    // board you have to be on already.
    { label: "ph:tray Suggestions: links, disagreements, names and link types", reveal: "suggestions" },
    { label: "ph:users People and things in my notes", reveal: "entities" },
    { label: "ph:tag Kinds of link: Part of, Cites and your own", reveal: "relation-types" },
    { label: "ph:list-bullets Note types: Meeting, Book and their fields", reveal: "note-types" },
    { label: "ph:scales Tensions: find where I disagreed with myself", reveal: "tensions" },
    //: Atlas is a surface with no tab of its own, which is exactly what a
    //: command palette is for (INBOX 224).
    //: The row wears Atlas's own face rather than a glyph (the owner: "find
    //: anything search" should have the avatar too), see `renderPalette`.
    { label: "Ask Atlas about the app", mark: "atlas", reveal: "atlas-help", chord: "askAtlas" },
    //: A companion that went somewhere it cannot be reached (INBOX 426 k).
    { label: "ph:arrow-counter-clockwise Call the companion back", about: "Bring the companion back to its corner of the window.", act: () => nameMarkBuddyCallBack() },
    //: Both did nothing at all unless a board was already on screen: the
    //: palette opens from every tab, and the two functions act on the board
    //: that is open. The reveal opens one first (the newest), and with no
    //: board at all rings the button that makes one.
    { label: "ph:map-trifold Board overview", reveal: "board-overview", about: "The whole board at once, to jump to any part of it." },
    { label: "ph:magnifying-glass Find on this board", reveal: "board-find", about: "Search the open board's cards, text and labels; Ctrl+H replaces." },
    //: Capture is a sub-tab of Notes, and focusing its box while another
    //: sub-tab was showing did nothing (the dashboard's own New note says so).
    { label: "ph:pencil-simple New note", reveal: "notes-capture", chord: "newNote" },
    //: Ctrl+D had no palette row (tests/test_consistency_contract.py: every
    //: chord is in the palette or says why it cannot be).
    { label: "ph:calendar-check Open today's note", reveal: "todays-note", chord: "todaysNote", about: "Today's page, or a new one titled with the day." },
    { label: "ph:lightning Quick note", about: "A note saved without leaving this page.", chord: "quickNote", act: () => openQuickNote() },
    { label: "ph:clipboard-text Paste as a note", about: "What you copied, saved as a new note.", chord: "pasteNote", act: () => pasteClipboardAsNote() },
    { label: "ph:file-text New document", reveal: "doc-new", chord: "newDocument" },
    { label: "ph:sparkle Write a note from rough thoughts", reveal: "writing-room" },
    { label: "ph:sparkle New chat", reveal: "chat-new", chord: "newChat" },
    // The popup agent (Ctrl+Shift+A) has real capability, it's the same
    // tool-calling agent as Chat's agent mode, just reachable from anywhere
    //, but was reachable only by already knowing that chord. This palette
    // is the app's own "what can I do here" list; it belongs in it.
    { label: "ph:strategy Ask the agent anything", reveal: "agent-palette", chord: "askAgent" },
    { label: "ph:palette New sketch", reveal: "sketch", chord: "quickSketch" },
    //: A command, not a search (INBOX 666: the palette is commands and
    //: places; finding a meeting is Find anything's). INBOX 644: there was
    //: no way to start a meeting note by name anywhere in the app.
    { label: "ph:users-three New meeting", reveal: "meeting-new", about: "Agenda, notes, decisions and action items." },
    {
      // Reachable from anywhere, which is the point. Asked for directly: "I
      // would also like the meeting notes popup to be expanded as a proper
      // feature with more capabilities and expansion which is also accessible
      // throughout the app, not just from the dashboard." A recording is
      // started the moment a meeting starts, and "go to the Dashboard first"
      // is exactly the friction that means it does not get started at all.
      label: "ph:microphone Record a meeting or lecture",
      reveal: "meeting",
      chord: "recordMeeting",
    },
    { label: "ph:microphone-stage Voice note", reveal: "voice-note" },
    { label: "ph:microphone Dictate a note", reveal: "notes-dictation" },
    { label: "ph:waveform Recordings", reveal: "recordings" },
    {
      // The same ask about the page reader, in the same words: "I want an
      // easier and more accessible way to access the ocr workspace as a proper
      // and more central feature." It had four doors and every one of them
      // started from a file you had already found, which is no answer to "I
      // want to read something". `openPageReader` (library.js) opens it on what
      // you were last reading, else your newest readable file; the decision and
      // what was deliberately not built is in UI_MODERNISATION_PLAN.md, "how
      // the page reader is reached".
      //: "OCR" in the words (the owner, 2026-10-10: searching "ocr" in the
      //: palette, Find anything and Quick access's list found nothing).
      label: "ph:scan OCR workspace: read a document or image",
      reveal: "page-reader",
    },
    {
      // Asked for directly: "add creating a new board to the command
      // palette and tools and features as well", the only way in before
      // this was the Add button inside the whiteboard's own board-picker
      // panel, unreachable without already being on that tab.
      label: "ph:folders New whiteboard board",
      reveal: "board-create",
      about: "A blank board for cards, drawings, images and links.",
    },
    {
      //: The Library's New, Mind map, from anywhere: Untitled map N, its
      //: root in edit (MINDMAP_PLAN 15, rows 1 and 2).
      label: "ph:tree-structure New mind map",
      reveal: "map-create",
    },
    {
      //: The Library's sub-tabs, as commands. These are the two halves of the
      //: file gallery, and getting to either meant three clicks through a tab
      //: and a sub-tab strip that scrolls on a narrow window.
      label: "ph:image Browse images",
      reveal: "library-images",
    },
    {
      label: "ph:paperclip Browse files",
      reveal: "library-files",
    },
    {
      label: "ph:link Browse links",
      reveal: "library-links",
    },
    {
      //: The whole list of what the app can do, from the list of what the app
      //: can do: the features browser was reachable from a dashboard button
      //: and nowhere else, and it is the answer to "what was that thing
      //: called", which is exactly the question the palette is opened with.
      label: "ph:compass Tools and features",
      reveal: "features",
      about: "Everything the app can do, a line each, and where it is.",
    },
    {
      //: Resurfacing shipped as a sort and a widget and was named in neither
      //: list. The sort is the half a person can act on: it re-ranks the notes
      //: they are already looking at by what is slipping out of reach.
      label: "ph:hourglass Show forgotten notes first",
      reveal: "notes-forgotten",
    },
    {
      //: The word list the document spelling check reads, which is otherwise
      //: only reachable from inside a suggestion popup on a flagged word, so
      //: "what have I taught it" had no door at all.
      label: "ph:book-bookmark Words you have taught it",
      reveal: "doc-dictionary",
    },
    {
      //: Ctrl+F is bound globally (`openGlobalFind`) and the palette is where
      //: a person looks for a key they have forgotten.
      label: "ph:magnifying-glass Find on this screen",
      reveal: "global-find",
      chord: "find",
    },
    {
      //: Workspaces filter every tab in the app from one control in the top
      //: left, and nothing in the palette mentioned them.
      label: "ph:folders New workspace",
      reveal: "workspace-new",
    },
    // Filters as commands: the fastest route to "the notes I mean" without
    // remembering the operator syntax.
    ...[
      ["ph:star Show favourites", "is:favourite"],
      ["ph:tag Show untagged notes", "is:untagged"],
      ["ph:lock Show private notes", "is:private"],
      ["ph:link Show linked notes", "is:linked"],
      ["ph:check-square Show filings to check", "is:review"],
    ].map(([label, query]) => ({
      label,
      about: `The notes list, filtered to ${query}.`,
      act: () => showNotesFilter(query),
    })),
    //: UX-08: places Ctrl+K could not reach (tests/test_palette_synonyms.py).
    { label: "ph:trash Open the bin", reveal: "library-bin", keywords: "bin trash deleted binned restore recover", about: "Everything you threw away, in the Library, ready to restore." },
    { label: "ph:question Questions your notes ask", reveal: "notes-questions", keywords: "questions open questions", about: "The open questions found in your notes." },
    { label: "ph:chat-text Ask your notes", reveal: "notes-ask", keywords: "ask question answer search my notes", about: "An answer quoted from your own notes, with or without a model." },
    //: The Guide had no row: "guide" found the tour (CHAT_PLAN 9 row 3).
    { label: "ph:question Ask the Guide", reveal: "atlas-help", keywords: "guide help how do i how does where is question", about: "Ask how anything in the app works; it answers from the app's own help." },
    //: The tour's third door (the e2e flow pass): the Dashboard's first-run
    //: tile and Settings, Help were the only two (tests/test_palette_synonyms.py).
    { label: "ph:compass Take the guided tour", keywords: "tour walkthrough guide how to start show me around", about: "A short walk round the app, pointing at the real controls.", act: () => openTour("basics") },
    //: INBOX 1304: Get started, hidden or done, comes back from the palette too.
    { label: "ph:list-checks Show Get started", keywords: "unhide", act: () => lazyScript("/js/first-run.js").then(() => getStartedShow()) },
    { label: "ph:arrow-u-up-left Undo", keywords: "undo take back revert", about: "Undo the last change, wherever it was made.", act: () => performUndo() },
    { label: "ph:arrow-u-up-right Redo", keywords: "redo", about: "Do again what Undo took back.", act: () => performRedo() },
    {
      label: "ph:magnifying-glass What can I type in the filter?",
      reveal: "notes-filter-help",
      about: "The words the notes filter understands, like is:favourite.",
    },
    { label: "ph:gear Settings → Models", reveal: "settings:models", about: "Which local model answers, and where it runs." },
    { label: "ph:mask-happy Settings → Personas", reveal: "settings:personas" },
    { label: "ph:lightning Settings → Skills", reveal: "settings:skills" },
    { label: "ph:toolbox Settings → Tools it can use", reveal: "settings:tools" },
    { label: "ph:palette Settings → Appearance", reveal: "settings:appearance", keywords: "theme colour color accent font text size look", about: "The look, the accent colour, the glass and the text size." },
    { label: "ph:user-circle Settings → Profile", reveal: "settings:preferences", about: "Your name, and what the app knows to call you." },
    { label: "ph:sliders Settings → General", reveal: "settings:general", keywords: "recycle bin auto-clear chat history notifications", chord: "settings" },
    { label: "ph:floppy-disk Settings → Import & export", reveal: "settings:data", keywords: "backup backups restore import export data", about: "Bring notes in, take everything out, and back up." },
    { label: "ph:brain Settings → What it remembers", reveal: "settings:memory" },
    { label: "ph:note-blank Settings → Templates", reveal: "settings:templates", about: "The shapes a new note or document can start from." },
    { label: "ph:shield-check Settings → Account & security", reveal: "settings:account", about: "The password, the lock and when it asks for it." },
    { label: "ph:globe-hemisphere-west Settings → Privacy", reveal: "settings:privacy", about: "The two things that can go online, both off by default." },
    { label: "ph:list-checks Settings → Background tasks", reveal: "settings:tasks", about: "What the app is working on while you write." },
    { label: "ph:heartbeat Health", reveal: "settings:about", keywords: "integrity check last backup last error data folder size status storage disk space files", about: "How the notebook is: last backup, last error, what is running, size, integrity." },
    { label: "ph:chart-bar Statistics", quick: "statistics", keywords: "stats numbers counts usage week review growth", about: "Your notebook, reminders and usage, counted, with this week against last.", act: () => openStatistics() },
    { label: "ph:book-open-text Open the manual", reveal: "manual" },
    //: The small tools (Brief 89, UI_MODERNISATION utilities rows 2 to 4):
    //: "timer 10 minutes" and "insert template ..." also build their own rows
    //: from the words (`utilityPaletteRows`, app-palette.js).
    { label: "ph:calculator Calculator", keywords: "calculator calc sum maths math work out percent convert units currency keypad", about: "Sums, percentages and unit or currency conversions, worked out by the app; /calc does the same in a chat.", act: () => ensureModule("replyKit").then(() => openCalculator()) },
    { label: "ph:timer Start a timer", keywords: "timer countdown pomodoro minutes alarm", about: "25 minutes on the status bar, or type “timer 10 minutes”. Press it to stop.", act: () => ensureModule("utilities").then(() => startUtilityTimer(25)) },
    { label: "ph:timer Start a stopwatch", keywords: "stopwatch count up how long time it", about: "Counts up on the status bar. Press it to stop.", act: () => ensureModule("utilities").then(() => startStopwatch()) },
    { label: "ph:closed-captioning Live captions", quick: "captions", keywords: "live captions subtitles transcribe speech microphone listen real time stop", about: "Write what the microphone hears as you go, on this computer. Run it again to stop and save a note.", act: () => toggleLiveCaptions() },
    { label: "ph:text-aa Count words", keywords: "word count characters letters reading time selection length", about: "Words, characters and reading time of the selected text, or of the editor.", act: () => ensureModule("utilities").then(() => countSelection(paletteCaught)) },
    { label: "ph:translate Translate this", keywords: "translate translation spanish language offline selection passage", about: "The selected passage into Spanish, offline (a package).", act: () => { const caught = { ...paletteCaught }; ensureModule("translate").then(() => translateCaught(caught)); } },
    { label: "ph:activity Activity", keywords: "running jobs stop background model unload memory agent runs", about: "Every job running now, with Stop, and the agent's runs.", act: () => openActivity("running") },
    { label: "ph:stop-circle Stop the model", keywords: "unload free memory model stop generating", about: "Stop any answer and unload the model from memory.", act: () => ensureModule("activity").then(() => window.stopActivityModel()) },
    { label: "ph:package Settings → Packages", reveal: "settings:extras", about: "Optional parts: speech, reading pages, better search." },
    { label: "ph:tree-evergreen Settings → Logs", reveal: "settings:logs", about: "What happened, for when something did not work." },
    { label: "ph:question Settings → Help", reveal: "settings:help", about: "How the app works, a section at a time." },
    { label: "ph:info Settings → About", reveal: "settings:about", about: "The version you have and whether a newer one exists." },
    { label: "ph:archive Back up now", keywords: "backup snapshot save a copy", about: "Save a copy of the whole notebook, now.", act: () => { openSettingsModal("data"); backupNow(); } },
    { label: "ph:export Export markdown", about: "Every note as a Markdown file, in one download.", act: () => downloadExport("markdown") },
    { label: "ph:circle-half Toggle light/dark", keywords: "theme dark mode light mode night", chord: "toggleTheme", act: toggleTheme },
    //: INBOX 430: also in Find anything, which lists these same commands;
    //: the row says which it will do, since this list is built per query.
    { label: nameMarkBuddyShowing() ? "ph:eye-slash Hide companion" : "ph:person-simple Show companion", chord: "toggleCompanion", act: () => nameMarkBuddyToggle() },
    { label: "ph:keyboard Keyboard shortcuts", reveal: "shortcuts", chord: "help" },
    //: INBOX 896: the status bar's wifi icon, by name, from anywhere.
    { label: "ph:wifi-high Other devices", keywords: "lan network wifi phone open close trusted networks address", about: "Whether a phone on this network can open the app, with the switch and the trusted networks.", chord: "lanPanel", act: () => openLanPanel() },
    { label: "ph:arrow-left Go back", about: "To the page or view you were on before.", chord: "navigateBack", act: () => stepTabHistory(-1) },
    { label: "ph:arrow-right Go forward", about: "Forward again, after going back.", chord: "navigateForward", act: () => stepTabHistory(1) },
    { label: "ph:arrows-clockwise Reload the app", about: "Clears cached files first, so the newest version loads.", chord: "forceReload", act: () => forceReloadApp() },
    { label: "ph:lock Lock Tessellate", about: "Close the notebook until the password is typed again.", act: lockNow },
    //: The top bar's other controls, so each is in the palette too (ledger 1410).
    { label: "ph:gear Open Settings", chord: "settings", act: () => openSettingsModal() },
    { label: "ph:bell Open notifications", keywords: "bell", act: () => openNotifications() },
    { label: "ph:squares-four Switch space", act: () => $("space-switcher-btn")?.click() },
    { label: "ph:power Quit Tessellate", act: () => quitApp() },
  ].map(catalogueRun);
}

//: **A row's keycap: the way to run it without the palette.** A chord the
//: row declares by its registry name (`chord`, read from the live
//: `shortcuts` table, so a rebinding shows here as it is), the editor's own
//: rows' `keys`, and for a tab the "t" then a letter jump. A palette that only
//: performs an action teaches nobody the key for it.
function paletteKeys(match) {
  if (match.keys) return match.keys;
  if (match.chord && typeof shortcuts !== "undefined") return shortcuts[match.chord]?.keys || "";
  if (match.tab && typeof TAB_JUMP_KEYS !== "undefined") {
    const letter = Object.keys(TAB_JUMP_KEYS).find((key) => TAB_JUMP_KEYS[key] === match.tab);
    if (letter) return `T ${letter.toUpperCase()}`;
  }
  return "";
}

//: **A row's one line of what it does.** Its own `about` first; then the
//: line "Tools and features" already writes for the same place (the rows
//: share their `reveal` with `featureCatalog`, so the two lists cannot
//: describe one control two ways); then the shortcut registry's label.
function paletteAbouts() {
  const abouts = new Map();
  const catalog = typeof featureCatalog === "function" ? featureCatalog() : [];
  for (const group of catalog) {
    for (const item of group.items || []) {
      if (item.reveal && item.desc && !abouts.has(item.reveal)) abouts.set(item.reveal, item.desc);
    }
  }
  return abouts;
}

function paletteRowParts(match, abouts) {
  const { icon, text } = richPickerSplitLabel(match.label);
  const chordLabel = match.chord && typeof shortcuts !== "undefined" ? shortcuts[match.chord]?.label : "";
  return {
    icon: icon || "ph:dot-outline",
    //: Atlas's own face stands in its tile (the owner: "find anything
    //: search" should have the avatar too).
    face: match.mark === "atlas" && typeof atlasAvatar === "function" ? atlasAvatar(20) : null,
    label: text,
    about: match.about || abouts.get(match.reveal) || chordLabel || "",
    keys: paletteKeys(match),
  };
}
