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
  const empty = pane?.querySelector(".chat-empty");
  if (!empty) return;
  //: A hidden Chat has no room to read, and reading it forced the whole page's layout (the Notes tab's
  //: 5,000 rows, 20ms) from the observer's frame as Chat went away. The class test costs no layout.
  if (pane.closest(".tab-page.hidden")) return;
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
  //: Only on a change: `remove` rewrites the attribute even when the class is absent, a restyle of the dock on every key (B59).
  if (dock?.classList.contains("ring-held")) dock.classList.remove("ring-held");
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
  const box = document.getElementById("chat-input");
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
  //: `pressed` is a pointer down on the box. Only a pointer resizes a textarea
  //: by hand, so a size change without one (the app's Ctrl +/- zoom, the
  //: window, autoGrow) is never a height the person chose: it was recorded as
  //: one, and its measure was a forced layout of 75 to 118 ms a zoom step at
  //: 4x CPU (INBOX 1508).
  const held = { pressed: false };
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
    held.pressed = true;
    const rect = box.getBoundingClientRect();
    dragging = event.clientX >= rect.right - GRABBER && event.clientY >= rect.bottom - GRABBER;
    if (dragging) box.dataset.resizing = "1";
  });
  window.addEventListener("pointerup", () => {
    held.pressed = false;
    if (!dragging) return;
    dragging = false;
    delete box.dataset.resizing;
    record();
  });
  const observer = new ResizeObserver(() => {
    if (dragging || !held.pressed) return;
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
  if (zone && prefsCache?.timezone !== zone) body.timezone = zone;
  if (weekDay !== null && prefsCache?.week_start_locale !== weekDay) {
    body.week_start_locale = weekDay;
  }
  //: The browser's language and region, so "automatic" seasons can follow
  //: it (southern for en-AU, en-NZ, en-ZA ...) when a call carries no locale.
  const tag = String(navigator.language || "").slice(0, 35);
  if (tag && prefsCache?.season_locale !== tag) body.season_locale = tag;
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
  ask_when_unsure: ["pref-ask-when-unsure"],
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
    toast(error.message || voiceLine("failed", { what: "save that setting" }), true);
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
      check_link_text: $("pref-check-link-text").checked,
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
    bgArtRefreshSeed();
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
    renderDashboardGreeting();
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
  window.valueField?.refresh();
  applyZoomVar();
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

//: A row's declaration, turned into the `run` the three lists call.
function catalogueRun(row) {
  if (typeof row.run === "function") return row;
  let run = () => {};
  if (row.reveal) run = () => revealFeature(row.reveal, row.arg);
  else if (row.tab) run = () => switchTab(row.tab);
  else if (typeof row.act === "function") run = row.act;
  return { ...row, run };
}

//: **The popup tools, one registry** (INBOX K27): the palette, Tools and
//: features, the shortcuts dialog's Tools list, both "/" menus and the Guide
//: read it; tests/test_popup_tools.py fails for a tool missing from any. `widget`
//: names the dashboard widget that draws the tool inline (`POPUP_WIDGETS`,
//: dashboard.js), or `widgetExempt` gives the reason it has none (INBOX 1558).
const POPUP_TOOLS = [
  {
    id: "calculator", name: "Calculator and equations", icon: "ph:calculator", group: "Ask & chat", widget: "calculator",
    keywords: "calculator calc sum maths math work out percent convert units currency keypad equation formula symbol fraction greek matrix integral latex alt word",
    about: "Sums, conversions and equations in one dialog, with no model; Alt+= opens the equation tab in a text box, /calc the calculator in Chat.",
    keys: "Alt+= or /calc", where: "Equation in text boxes, Calculator in Chat",
    //: `t`: the box a slash row was typed in, which outranks the palette's last box (a stale one sent "/calc" in a note to the Ask box).
    guide: "calculator", open: (t) => ensureModule("appPalette").then(() => popupToolMaths({ target: t || null })),
  },
  {
    id: "convert", name: "Convert units", icon: "ph:ruler", group: "Ask & chat", widget: "convert",
    keywords: "convert conversion unit units miles km kg pounds celsius fahrenheit litres currency",
    about: "Length, weight, temperature, volume and currency, with no model; the second tab of Calculator and equations.",
    keys: "/calc", where: "Convert units, in Calculator and equations",
    guide: "calculator", open: () => ensureModule("replyKit").then(() => openCalculator("", "convert")),
  },
  {
    id: "timer", name: "Start a timer", icon: "ph:timer", group: "Plan & focus", widget: "clock",
    keywords: "timer countdown pomodoro",
    about: "Opens the Clock.",
    keys: "Ctrl+K", where: "Start a timer",
    guide: "timer", open: () => ensureModule("utilities").then(() => openClockPanel("timer")),
  },
  {
    id: "stopwatch", name: "Start a stopwatch", icon: "ph:timer", group: "Plan & focus", widget: "stopwatch",
    keywords: "stopwatch count up",
    about: "Opens the Clock.",
    keys: "Ctrl+K", where: "Start a stopwatch",
    guide: "timer", open: () => ensureModule("utilities").then(() => openClockPanel("stopwatch")),
  },
  {
    id: "alarm", name: "Set an alarm", icon: "ph:alarm", group: "Plan & focus", widget: "alarm",
    keywords: "alarm",
    about: "Opens the Clock.",
    keys: "Ctrl+K", where: "Set an alarm",
    guide: "timer", open: () => ensureModule("utilities").then(() => openClockPanel("alarm")),
  },
  //: The Diagram builder (INBOX 1588): one opener, `diagramModel.door` (documents-mermaid.js), for every list.
  //: A text box or board in hand needs the Library (the door writes into it); with none, the model file alone opens the builder (INBOX 1722), and `lazyScript` fetches it once whichever asks first.
  {
    id: "diagram", name: "Diagram builder", icon: "ph:flow-arrow", group: "Documents", widgetExempt: "It needs a full dialog or a document, too big for a card.",
    keywords: "flowchart mind map timeline sequence mermaid mmd draw process boxes arrows",
    about: "Build a flowchart, mind map, timeline or sequence diagram from blocks, into what you write, a board or a new .mmd file.",
    keys: "/diagram", where: "Diagram builder, from Insert or Ctrl+K",
    guide: "diagram-builder", open: (t) => (t ? ensureModule("library") : lazyScript("/js/documents-mermaid.js")).then(() => diagramModel.door({ target: t || null })),
  },
];

//: What the palette caught from the field it was opened over (`paletteCaught`,
//: app-palette.js, lazy): nothing yet when that file is not in, so a caller
//: other than the palette (Tools and features, audit 1031 Z17) cannot throw,
//: and nothing once the row it ran has started (`live`, INBOX 1530 g).
function paletteCaughtNow() {
  return typeof paletteCaught === "undefined" || !paletteCaught.live ? { target: null, selection: "", start: null, end: null, range: null } : paletteCaught;
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
