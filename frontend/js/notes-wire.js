// notes-wire.js: Notes list wiring that waits for a visit or a click, moved out of notes-list.js (LEDGER
// L-world-class-631): the list's keyboard walk, a shift-click range, the connections rail's listeners and
// the wiki-rename offer. Lazy (`LAZY_MODULES.notesWire`, lazy-entries.js stand-ins); nobody reads a return value.

//: A shift-click range over every row between the two, built or not.
//: By id, as rows folded into a run have no element (L-world-class-873).
function selectNoteRange(list, fromId, toId, on) {
  const ids = listedNoteIds();
  const a = ids.indexOf(Number(fromId));
  const b = ids.indexOf(Number(toId));
  if (a === -1 || b === -1) return;
  for (const id of ids.slice(Math.min(a, b), Math.max(a, b) + 1)) {
    if (on) selectedIds.add(id);
    else selectedIds.delete(id);
    const li = list.querySelector(`:scope > li[data-id="${id}"]:not(.row-shell)`);
    const check = li?.querySelector(":scope > .select-check");
    if (check) check.checked = on;
    li?.classList.toggle("is-selected", on);
  }
  updateBatchCount();
}

function initEntryListKeyboardNav() {
  const list = $("entry-list");
  list.addEventListener("focusin", entryListFocusStop);
  list.addEventListener("keydown", (event) => {
    //: Home/End, Delete (to the bin, with Undo) and F2 (edit) on a focused
    //: row, as a notes list answers them everywhere else (INBOX 432: only
    //: the arrows and Enter did anything).
    const keys = ["ArrowDown", "ArrowUp", "Enter", "Home", "End", "Delete", "F2"];
    if (!keys.includes(event.key)) return;
    //: A note's own ⋯ menu lives inside its row, so its arrow keys bubble
    //: here too: ArrowDown in the menu moved to the next item and then this
    //: moved the focus out of the menu onto the row (measured, menus.js).
    if (event.target.closest('.action-menu, [role="menu"], [role="listbox"]')) return;
    //: **A text field keeps its own keys.** A note's edit form lives inside
    //: its row, so the title box, the tags box and the body editor sent their
    //: Home, End and arrow keys here: the caret never moved, the focus jumped
    //: to another row, and what was typed next went nowhere (found by the
    //: deepflows sweep: click into the editor, press End, type). Checkboxes
    //: and buttons are not fields, so the row's arrows still work from them.
    if (event.target.closest('textarea, select, [contenteditable], .cm-editor, input:not([type="checkbox"]):not([type="radio"]):not([type="button"])')) return;
    const items = entryListItems(list);
    const current = event.target.closest("li");
    const index = current ? items.indexOf(current) : -1;
    if (index === -1) return;

    if (event.target === current && (event.key === "Delete" || event.key === "F2")) {
      const entry = allEntries.find((e) => e.id === Number(current.dataset.id));
      if (!entry || appState.get("note") === entry.id) return;
      event.preventDefault();
      const ids = listedNoteIds();
      const at = ids.indexOf(entry.id);
      const next = ids[at + 1] ?? ids[at - 1];
      if (event.key === "F2") openNoteEditor(entry.id);
      else binNoteWithUndo(entry).then(() => {
        const again = noteRowFor(next);
        if (again) noteWindow.fill(again).focus();
      });
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const nextIndex =
        event.key === "Home" ? 0
          : event.key === "End" ? items.length - 1
            : Math.min(Math.max(index + (event.key === "ArrowDown" ? 1 : -1), 0), items.length - 1);
      //: Into a run from below (ArrowUp, End) builds its last row.
      const target = noteWindow.fill(items[nextIndex], nextIndex < index || event.key === "End");
      entryListSetStop(entryListItems(list), target);
      target.focus();
      // .focus() alone scrolls in most browsers, but not predictably, 
      // explicit and consistent with the same fix on the command palette's
      // own arrow-key nav, which has no focus to lean on at all.
      target.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" && event.target === current) {
      // Only when the <li> itself has focus, not a button/link/textarea
      // inside it: those already handle their own Enter behaviour, and
      // this app has no separate "note view" to open: editing in place is
      // what opening a note means here.
      event.preventDefault();
      current.querySelector(".entry-actions [title='Edit this entry']")?.click();
    }
  });
}

window.wireNotesRail = function wireNotesRail() {
    const rail = $("notes-rail");
    const list = $("entry-list");
    if (!rail || !list) return;
    //: Selecting a row is focusing it: a click on a card's body focuses its
    //: `<li>` (the list's roving tabindex), and so does every arrow key.
    list.addEventListener("focusin", (event) => {
      const li = event.target.closest?.("li[data-id]");
      if (!li || li.parentElement !== list) return;
      //: **Not a card's menu.** Its ⋯ is a button inside the row, so pressing it
      //: is focus in the row, and the rail opened 120ms later: the column takes
      //: 318px from the list and its dock wraps to two lines, so the row moved
      //: 318px left and 44px down under a menu already placed beside where the
      //: ⋯ had been (the review, 2026-09-27, `anchorsmotion.js`: 118px from its
      //: opener at 1440x600, over the rail). A menu acts on a note; it does not
      //: choose one to read.
      if (event.target.closest?.(".menu-wrap, .action-menu")) return;
      //: INBOX 571: a card chosen by hand is the subject (it is pinned in
      //: notes-rail-spy.js); the rail is already drawn, so nothing moves.
      const id = Number(li.dataset.id);
      if (!Number.isFinite(id) || id === notesRailId) return;
      notesRailId = id;
      scheduleNotesRail();
    });
    $("notes-rail-close")?.addEventListener("click", () => {
      notesRailFocusSubject();
      setNotesRailHidden(true);
      toast("Connections hidden. The notes list's More menu brings them back.");
    });
    $("notes-rail-toggle")?.addEventListener("click", () => {
      setNotesRailHidden(!notesRailHiddenByChoice());
      $("notes-more-menu")?.removeAttribute("open");
    });
    //: The keys every list here keeps (WORLD_CLASS_PLAN 1.6): arrows walk the
    //: rows, Enter opens one (they are buttons), Escape goes back to the list.
    rail.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        notesRailFocusSubject();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const rows = [...rail.querySelectorAll("button.connection-row")];
      const at = rows.indexOf(document.activeElement);
      if (at < 0) return;
      event.preventDefault();
      const next = rows[Math.min(rows.length - 1, Math.max(0, at + (event.key === "ArrowDown" ? 1 : -1)))];
      next?.focus();
    });
    notesRailWide.addEventListener("change", renderNotesRail);
    //: A sidebar dragged or collapsed changes the list's room, which decides whether the rail fits; the window
    //: does not change then, so the sidebar is observed (and the list, for the rail's own width check).
    if (typeof ResizeObserver === "function" && $("sidebar")) {
      let last = 0;
      renderNotesRail.ro = new ResizeObserver((entries) => {
        for (const { target, contentRect } of entries) {
          //: L705: read after layout.
          if (target.id === "entry-list") {
            if (target.getBoundingClientRect().width >= NOTES_RAIL_MIN_READING) continue;
            const rail = $("notes-rail");
            rail.hidden = true;
            rail.dataset.cramped = "1";
            window.notesRailMark?.();
          } else if (last !== (last = Math.round(contentRect.width))) scheduleNotesRail();
        }
      });
      renderNotesRail.ro.observe($("sidebar"));
    }
    syncNotesRailToggle();
};

//: GRAPH_PLAN 518: a save that renamed a note while other notes still write
//: its old [[name]] offers to rewrite them as the new one.
function offerWikiRename(entryId, saved) {
  const offer = saved && saved.wiki_rename;
  if (!offer) return;
  const who = offer.notes === 1 ? "1 note still links" : `${offer.notes} notes still link`;
  toastAction(`${who} to [[${offer.old}]].`, `Rename to [[${offer.new}]]`, async () => {
    try {
      const done = await apiJson(`/entries/${entryId}/wiki-rename`, { method: "POST", body: JSON.stringify({ old: offer.old }) });
      pushWikiRenameUndo(entryId, offer.old, done);
      toast(`Updated ${nounCount(done.rewritten, "note")}.`);
      await loadEntries().catch(() => {});
    } catch (error) {
      toast(error.message || voiceLine("failed", { what: "update those links" }), true);
    }
  });
}
