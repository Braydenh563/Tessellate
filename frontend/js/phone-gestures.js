// phone-gestures.js: what only a phone does with a row: swipe it to star or bin (`initRowSwipe`), and open a note as a page
// (`openNotePage`, `refreshNotePageNow`, `dropRepeatedTitle`, `initNotePage`). Moved out of phone-shell.js
// (LEDGER L-world-class-810) to come off the boot file: lazy, the `phoneGestures` bundle, fetched by phone-shell.js
// only when the window is in the phone band (at load, or when it narrows into it). The state the rest of the app
// reads (`notePageOpenId`, `notePageClose`) and the checks that run on every list draw (`closeNotePageIfGone`) stay there.

// --- swipe a row: star to the right, bin to the left --------------------------
// UI_MODERNISATION_PLAN Phase 11 item 2: "the list as full-width rows with
// swipe actions (pin, bin) matched to the row's menu (the HIG rule)". The
// rule is the whole design: a swipe is a shortcut to something the row
// already offers where a person can see it, never the only way to it, and
// never a third copy of the action. So the swipe presses the row's own
// controls: the star button (`.favourite-btn`, visible on the row) and the
// row menu's "Move to bin" (`binNoteWithUndo`, the one function that menu
// row calls, undo toast and all). Nothing here knows what favouriting or
// binning does.
//
// One delegated set of listeners on the list, so re-rendered rows need no
// wiring. Touch only, and only in the phone band: a mouse has the controls
// under it already. The row's children slide on `--swipe-x` and the row's
// own `::before`/`::after` are the two coloured underlays that appear in
// the gap (10-responsive.css); past `ROW_SWIPE_ARM` the underlay saturates
// to say a lift-off will act. `touch-action: pan-y` on the row is what
// makes the horizontal drag ours and the vertical one the page's: the
// first 8px decide which, and a vertical start hands the pointer back.
const ROW_SWIPE_ARM = 88;
const ROW_SWIPE_MAX = 124;

//: `list` is the element the rows live under (delegated, so re-rendered rows
//: need no wiring); `actions.right` and `actions.left` each take the row and
//: press its own control. A direction the row has no label for
//: (`data-swipe-right` / `data-swipe-left`, which are also the underlay's
//: words) never arms: a reminder swipes right to Done and left to nothing.
function initRowSwipe(list, actions) {
  if (!list) return;
  let row = null;
  let startX = 0;
  let startY = 0;
  let dx = 0;
  let decided = false;

  const settle = (li) => {
    li.classList.add("is-settling");
    li.style.setProperty("--swipe-x", "0px");
    li.classList.remove("swipe-left", "swipe-right", "swipe-armed", "is-swiping");
    setTimeout(() => li.classList.remove("is-settling"), 240);
  };

  list.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "touch" || !window.matchMedia(PHONE_TABS).matches) return;
    const li = event.target.closest("li[data-id]");
    if (!li || li.querySelector("textarea")) return; // the edit form is not a row
    if (event.target.closest("button, a, input, select, [contenteditable]")) return;
    row = li;
    startX = event.clientX;
    startY = event.clientY;
    dx = 0;
    decided = false;
  });

  list.addEventListener("pointermove", (event) => {
    if (!row) return;
    const mx = event.clientX - startX;
    const my = event.clientY - startY;
    if (!decided) {
      if (Math.abs(mx) < 8 && Math.abs(my) < 8) return;
      decided = true;
      if (Math.abs(my) > Math.abs(mx)) {
        row = null; // a scroll, the page's
        return;
      }
      row.classList.add("is-swiping");
    }
    const canRight = Boolean(row.dataset.swipeRight);
    const canLeft = Boolean(row.dataset.swipeLeft);
    dx = Math.max(canLeft ? -ROW_SWIPE_MAX : 0, Math.min(canRight ? ROW_SWIPE_MAX : 0, mx));
    row.style.setProperty("--swipe-x", `${dx}px`);
    row.classList.toggle("swipe-right", dx > 0);
    row.classList.toggle("swipe-left", dx < 0);
    row.classList.toggle("swipe-armed", Math.abs(dx) >= ROW_SWIPE_ARM);
  });

  const end = () => {
    if (!row) return;
    const li = row;
    const travelled = dx;
    row = null;
    // A tap never moved: settling it would mark it a swipe and eat its click.
    if (!decided) return;
    settle(li);
    if (Math.abs(travelled) < ROW_SWIPE_ARM) return;
    if (travelled > 0) actions.right?.(li);
    else actions.left?.(li);
  };
  list.addEventListener("pointerup", end);
  list.addEventListener("pointercancel", end);
}

onSurface("notes", () => initRowSwipe($("entry-list"), {
  right: (li) => li.querySelector(".favourite-btn")?.click(),
  // The menu builds its rows on open, so the bin is reached as the one
  // function the menu's own row calls, not by pressing a row that does
  // not exist yet.
  left: (li) => {
    const entry = allEntries.find((e) => String(e.id) === li.dataset.id);
    if (entry) binNoteWithUndo(entry);
  },
}));

//: Reminders (Phase 11 item 8, "reminders as rows with swipe done"): right
//: presses the row's own Done checkbox, which toggles and saves as a tap on
//: it would; there is no left.
onSurface("reminders", () => {
  initRowSwipe($("reminder-groups"), {
    right: (li) => li.querySelector('input[type="checkbox"]')?.click(),
  });
});

//: The sheet's head already says the note's name, so the card inside does
//: not say it again (audit 1031 N14): its own `.entry-title`, or the opening
//: heading of a note that has no stored title. Text compared with the
//: clipped head, so a long heading still matches.
function dropRepeatedTitle(root, title) {
  root.querySelector(".entry-title")?.remove();
  const shown = root.querySelector(".entry-content");
  //: A clipped note's card fills in the whole text once it arrives (`fillWhole`, entry-card.js): its heading again.
  if (shown && !shown.titled) shown.titled = shown.addEventListener("note-whole", () => dropRepeatedTitle(shown.parentNode, title)) || 1;
  const first = shown?.firstElementChild;
  const said = (first?.textContent || "").replace(/\s+/g, " ").trim();
  if (first && /^H[1-6]$/.test(first.tagName) && said && title.startsWith(said.slice(0, 80))) first.remove();
}

function openNotePage(entry, returnFocus = null) {
  if (!entry || notePageOpenId === entry.id) return;
  //: The card is `entryItem` (entry-card.js, lazy): in by the time any list was drawn, fetched here if not.
  if (!window.entryItem) return ensureModule("entryCard").then((ok) => (ok && window.entryItem ? openNotePage(entry, returnFocus) : lazyLoadFailed("Notes")));
  expandedNotes.add(entry.id);
  notePageOpenId = entry.id;
  const title = entry.title || noteNamePlain(entry.content, 80) || "Note";
  notePageClose = openSheet({
    label: title,
    name: "note",
    variant: "page",
    returnFocus,
    onClose: () => {
      notePageOpenId = null;
      notePageClose = null;
    },
    build: (card) => {
      const list = document.createElement("ul");
      list.className = "entry-list note-page-list";
      const item = entryItem(entry, { actions: true });
      item.querySelector(".entry-content")?.classList.remove("entry-clamped");
      item.querySelector(".entry-more")?.remove();
      dropRepeatedTitle(item, title);
      list.appendChild(item);
      card.appendChild(list);
      const actions = item.querySelector(".entry-actions");
      if (actions) {
        const bar = document.createElement("div");
        bar.className = "thumb-bar note-page-bar";
        bar.setAttribute("role", "toolbar");
        bar.setAttribute("aria-label", "Note actions");
        while (actions.firstChild) bar.appendChild(actions.firstChild);
        actions.remove();
        card.appendChild(bar);
      }
    },
  });
  const close = document.querySelector('.sheet-overlay[data-sheet="note"] .sheet-close');
  if (close) {
    setLabel(close, "ph:arrow-left");
    close.setAttribute("aria-label", "Back");
    close.title = "Back (Escape)";
  }
}

function refreshNotePageNow(ids) {
  const entry = allEntries.find((e) => e.id === notePageOpenId);
  const old = document.querySelector('.sheet-overlay[data-sheet="note"] .note-page-list .entry-content');
  if (!entry || !old) return;
  //: An open note page was drawn by `entryItem`, so the file is in; fetched here all the same.
  if (!window.entryItem) return ensureModule("entryCard").then((ok) => (ok && window.entryItem ? refreshNotePageNow(ids) : lazyLoadFailed("Notes")));
  const fresh = entryItem(entry, { actions: true }).querySelector(".entry-content");
  if (!fresh) return;
  fresh.classList.remove("entry-clamped");
  dropRepeatedTitle(fresh.parentNode || fresh, entry.title || noteNamePlain(entry.content, 80) || "Note");
  old.replaceWith(fresh);
}

function initNotePage() {
  const list = $("entry-list");
  if (!list) return;
  list.addEventListener("click", (event) => {
    if (!window.matchMedia(PHONE_TABS).matches) return;
    //: **In Select mode a tap is a tick, not an opening.** The whole card is
    //: the checkbox (note-cards.js), and this handler did not know the mode:
    //: the first tap selected the note and opened its page over the list too
    //: (found by the deepflows sweep).
    if (selectMode) return;
    const li = event.target.closest("li[data-id]");
    if (!li || li.querySelector("textarea")) return;
    if (event.target.closest("button, a, input, select, [contenteditable], .chip-interactive, summary")) return;
    // The lift-off of a swipe is a click too; a row that moved was not tapped.
    if (li.classList.contains("is-settling")) return;
    if (window.getSelection && String(window.getSelection()).length) return;
    const entry = allEntries.find((e) => String(e.id) === li.dataset.id);
    if (entry) openNotePage(entry, li);
  });
}

onSurface("notes", initNotePage);
