// notes-rail-spy.js: the Connections rail follows the note you are reading
// (INBOX 571, a follow-up to 546). The owner: "what constitutes opening a note
// if I can see a whole note in the notes section, Id just scroll to it and see
// it yk??" Notes are read in the list, so there is no "open" moment for the
// rail to wait for; the decision taken:
//
// - a card you click, focus or press a key on is the subject, as before
//   (notes-list.js's own `focusin`), and stays it until the list has scrolled
//   more than one viewport from where it was chosen;
// - otherwise, as the list scrolls, the card whose top is nearest the upper
//   third of the list's visible part is the subject: an IntersectionObserver
//   keeps the set of cards on screen, and a scroll settles for 150ms before
//   the few of those are measured (reads only, no writes between, so no
//   layout thrash);
// - the subject card wears `.rail-subject`, a left accent hairline, so it is
//   plain which note the column is about; the column cross-fades on a change.
//
// A lazy piece (app.js `LAZY_MODULES.notesRail`), loaded by `renderNotesRail`
// at 1280px and wider, where the rail is drawn: the boot scripts are at their
// gzip cap. Phones keep the note's Connections sheet; nothing here runs there.

const NOTES_SPY_SETTLE_MS = 150;
const notesSpyVisible = new Set();
const notesSpy = { timer: 0, last: null };
//: The card chosen by hand (a click, a focus, an edit, a jump to it), held
//: until it is more than a viewport out of sight. Measured from the card, not
//: from where the list was when it was chosen: a jump scrolls to its note
//: after choosing it, and that scroll must not undo the choice.
let notesSpyPin = null;
//: The subject this file chose, so a subject chosen anywhere else (notes-list
//: sets `notesRailId` for an edit, a jump and a focus) is known to be a pin.

function notesSpyActive() {
  return (
    notesRailWide.matches &&
    !notesRailHiddenByChoice() &&
    prefs.get("activeTab", null) === "notes" &&
    !$("browse")?.classList.contains("hidden")
  );
}

//: The card nearest the upper third of what is visible of the list, from the
//: cards the observer says are on screen. A pinned card holds until the list
//: has moved more than a viewport from where it was pinned.
function notesSpyPick() {
  const list = $("entry-list");
  if (!list || !notesSpyActive()) return;
  const box = list.getBoundingClientRect();
  if (notesRailId != null && notesRailId !== notesSpy.last && notesSpyPin?.id !== String(notesRailId)) {
    notesSpyPin = { id: String(notesRailId) };
  }
  if (notesSpyPin) {
    const card = list.querySelector(`:scope > li[data-id="${notesSpyPin.id}"]`)?.getBoundingClientRect();
    const far = window.innerHeight;
    if (card && card.bottom > -far && card.top < 2 * far) return;
    notesSpyPin = null;
  }
  const top = Math.max(box.top, 0);
  const bottom = Math.min(box.bottom, window.innerHeight);
  if (bottom <= top) return;
  const line = top + (bottom - top) / 3;
  let best = null;
  let bestGap = Infinity;
  const seen = notesSpyVisible.size ? notesSpyVisible : new Set(list.querySelectorAll(":scope > li[data-id]"));
  for (const li of seen) {
    if (!li.isConnected || li.parentElement !== list) continue;
    const gap = Math.abs(li.getBoundingClientRect().top - line);
    if (gap < bestGap) {
      bestGap = gap;
      best = li;
    }
  }
  //: An empty list (a filter that matched nothing) has no subject, so the
  //: column goes rather than keep talking about a note that is not shown.
  const id = best ? Number(best.dataset.id) : null;
  if (id !== notesRailId && (id == null || Number.isFinite(id))) {
    notesRailId = id;
    notesSpy.last = id;
    scheduleNotesRail();
  }
}

function notesSpySchedule() {
  clearTimeout(notesSpy.timer);
  notesSpy.timer = setTimeout(notesSpyPick, NOTES_SPY_SETTLE_MS);
}

//: Called by `renderNotesRail` with the note it is drawing (or null): the
//: hairline goes on that card and off every other, and the column fades
//: across when the note changes.
function notesRailMark(entry) {
  if (notesRail.handle) notesRail.handle.hidden = !entry; // the drag handle follows the rail
  if (entry && notesRail.restore) notesRail.restore();
  const list = $("entry-list");
  if (!list) return;
  const id = entry ? String(entry.id) : "";
  for (const li of list.querySelectorAll(":scope > li.rail-subject")) {
    if (li.dataset.id !== id) li.classList.remove("rail-subject");
  }
  if (!id) return;
  list.querySelector(`:scope > li[data-id="${id}"]`)?.classList.add("rail-subject");
  const body = $("notes-rail-body");
  if (body && body.dataset.subject !== id) {
    body.dataset.subject = id;
    body.classList.add("is-switching");
    setTimeout(() => body.classList.remove("is-switching"), NOTES_SPY_SETTLE_MS);
  }
}

(function wireNotesRailSpy() {
  const list = $("entry-list");
  if (!list) return;
  const seen = typeof IntersectionObserver === "function"
    ? new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) notesSpyVisible.add(entry.target);
          else notesSpyVisible.delete(entry.target);
        }
        notesSpySchedule();
      })
    : null;
  const observeAll = () => {
    if (!seen) return;
    notesSpyVisible.clear();
    seen.disconnect();
    for (const li of list.querySelectorAll(":scope > li[data-id]")) seen.observe(li);
  };
  //: A render replaces the cards: observe the new ones and pick again, so a
  //: filter or a sort never leaves the column on a note that has gone.
  //: Only the rows that changed: the windowed list (notes-list.js) swaps a
  //: few rows on every scroll, and observing all three hundred again each
  //: time was a measured 0.8s of a long scroll.
  new MutationObserver((records) => {
    for (const record of records) {
      for (const node of record.removedNodes) {
        notesSpyVisible.delete(node);
        if (node.nodeType === 1) seen?.unobserve(node);
      }
      for (const node of record.addedNodes) if (node.dataset?.id) seen?.observe(node);
    }
    notesSpySchedule();
  }).observe(list, { childList: true });
  //: Capture, so a scroll of whichever element holds the list is heard.
  document.addEventListener("scroll", notesSpySchedule, { capture: true, passive: true });
  //: A card chosen by hand pins it (its menu is acting on it, not choosing).
  list.addEventListener("focusin", (event) => {
    const li = event.target.closest?.("li[data-id]");
    if (!li || li.parentElement !== list || event.target.closest?.(".menu-wrap, .action-menu")) return;
    notesSpyPin = { id: li.dataset.id };
  });
  observeAll();
  notesSpyPick();
})();

// --- the column's width (INBOX 1443, the owner: "the connections sidebar also
// cant be resized") ------------------------------------------------------------
// The width is the layout's `grid-auto-columns` (the rail is its implicit third
// track, 04-chat-dock-appearance.css); removed, the stylesheet's clamp() is back. The handle is a sibling of
// the rail on its left edge (not inside it, which scrolls), shown only on a
// fine pointer at 600px or wider. Arrows move 16px (WCAG 2.5.7), Home resets.
const NOTES_RAIL_W_MIN = 240;
const NOTES_RAIL_W_MAX = 560;
const NOTES_RAIL_STEP = 16;
const NOTES_RAIL_W_KEY = "notesRailWidth";
//: The drag handle, and `restore`, which puts the kept width back once, when
//: the rail is first drawn, against the room there is then.
const notesRail = { handle: null, restore: null };

//: `room` is the widest the list beside it allows (it keeps its reading width).
function notesRailClamp(width, room) {
  const max = Math.max(NOTES_RAIL_W_MIN, Math.min(NOTES_RAIL_W_MAX, room));
  return Math.min(Math.max(Math.round(width), NOTES_RAIL_W_MIN), max);
}

//: The next width for a key, null to reset, undefined for a key that is not ours.
function notesRailKeyWidth(key, width) {
  if (key === "ArrowLeft") return width + NOTES_RAIL_STEP;
  if (key === "ArrowRight") return width - NOTES_RAIL_STEP;
  return key === "Home" ? null : undefined;
}

(function wireNotesRailResize() {
  const rail = $("notes-rail");
  if (!rail || !window.matchMedia("(pointer: fine) and (min-width: 600px)").matches) return;
  const layout = rail.parentElement;
  const handle = document.createElement("div");
  handle.className = "sidebar-resize notes-rail-resize";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("tabindex", "0");
  handle.setAttribute("aria-label", "Resize the connections column: arrow keys, or drag");
  handle.title = "Drag to resize; double-click to reset";
  //: `.sidebar-resize` gives the look; here it sits in column 3 as a grid item, on the rail's left edge.
  Object.assign(handle.style, { position: "static", gridArea: "1 / 3", justifySelf: "start", translate: "-50% 0" });
  handle.hidden = true; // shown by notesRailMark with the rail
  notesRail.handle = handle;
  rail.after(handle);
  const room = () => Math.floor(rail.getBoundingClientRect().width + ($("entry-list")?.getBoundingClientRect().width || 0)) - NOTES_RAIL_MIN_READING - 2;
  //: The one separator recipe: min, max and the width as the rail resizes.
  trackSeparatorValue(handle, rail, NOTES_RAIL_W_MIN, NOTES_RAIL_W_MAX);
  //: null puts the stylesheet's own width back.
  const apply = (width) => {
    if (width == null) {
      layout.style.removeProperty("grid-auto-columns");
      try { prefs.remove(NOTES_RAIL_W_KEY); } catch { /* blocked storage */ }
      return;
    }
    const px = notesRailClamp(width, room());
    layout.style.gridAutoColumns = `${px}px`;
    try { prefs.set(NOTES_RAIL_W_KEY, String(px)); } catch { /* this session only */ }
  };
  let saved = null;
  try { saved = Number(prefs.get(NOTES_RAIL_W_KEY, "")) || null; } catch { /* blocked */ }
  if (saved) {
    notesRail.restore = () => {
      notesRail.restore = null;
      layout.style.gridAutoColumns = `${notesRailClamp(saved, room())}px`;
    };
  }
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startW = rail.getBoundingClientRect().width;
    document.body.classList.add("resizing-sidebar");
    const move = (e) => apply(startW + (startX - e.clientX));
    const stop = () => {
      document.body.classList.remove("resizing-sidebar");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      handle.removeEventListener("pointercancel", stop);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
  });
  handle.addEventListener("keydown", (event) => {
    const next = notesRailKeyWidth(event.key, rail.getBoundingClientRect().width);
    if (next === undefined) return;
    event.preventDefault();
    apply(next);
  });
  handle.addEventListener("dblclick", () => apply(null));
})();
