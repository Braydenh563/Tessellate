// notes-lazy.js: Notes list pieces moved out of notes-list.js (audit 1029
// N9) to pay for the windowed list in the gzip budget
// (tests/test_static_compression.py). A row's expand chevron (reached only by
// a click) and the bell's weekly untagged and review nudges (after the
// notebook loads). No caller reads a return value, so stand-ins
// (`notesLazy`, lazy-entries.js) fetch this file on first use.

function toggleRowExpanded(id) {
  const open = !expandedRows.has(id);
  if (open) {
    expandedRows.add(id);
    notesRailId = id;
  } else {
    expandedRows.delete(id);
    //: Closing the note the rail is about closes the rail's subject with it:
    //: a column describing a note nobody has open is the chrome-with-nothing
    //: the local map already learned not to be.
    if (notesRailId === id) notesRailId = null;
  }
  const li = document.querySelector(`#entry-list > li[data-id="${id}"]`);
  if (!li) return renderEntries();
  //: **In place, and animated** (INBOX 676, the owner: "the dropdown and
  //: collapse should be a smooth animation adn not sudden and janky"). This
  //: was a full list redraw: a new row in one frame (49.6 to 237.8px) and a
  //: new chevron, so its glyph could not turn. The row is the same DOM open
  //: or closed (CSS hides what a closed row does not show), so the class
  //: alone is the change. The height runs from where the row *is*, read
  //: before the previous animation is cancelled, so a second press mid-way
  //: turns back from there instead of snapping; what the change reveals
  //: fades in over the same time. `--ui-slow` is the Interface animations
  //: switch's token: 0s with it off, and then nothing animates.
  const from = li.getBoundingClientRect().height;
  const parts = [...li.querySelectorAll(":scope > :not(.row-expand, .entry-title)")];
  const seen = parts.map((el) => (el.getAnimations().length ? +getComputedStyle(el).opacity : 0));
  for (const el of [li, ...parts]) for (const a of el.getAnimations()) if (a.id === "row") a.cancel();
  li.classList.toggle("row-expanded", open);
  const button = li.querySelector(":scope > .row-expand");
  if (button) {
    button.title = open ? "Show less of this note" : "Show the whole note here";
    button.setAttribute("aria-label", button.title);
    button.setAttribute("aria-expanded", String(open));
  }
  const to = li.getBoundingClientRect().height;
  const style = getComputedStyle(li);
  const duration = parseFloat(style.getPropertyValue("--ui-slow")) * 1000 || 0;
  const easing = style.getPropertyValue("--ease-in-out").trim() || "ease-in-out";
  if (duration && Math.abs(to - from) > 1) {
    li.animate({ height: [`${from}px`, `${to}px`], overflow: ["hidden", "hidden"] }, { id: "row", duration, easing });
    parts.forEach((el, i) => el.animate({ opacity: [seen[i], 1] }, { id: "row", duration, easing }));
  }
  scheduleNotesRail();
  updateExpandAllButton();
}

//: The bell says so once a week, past a handful, as it does for untagged.
async function nudgeReviewQueue() {
  const queue = await apiJson("/review-queue?limit=1", { silent: true, cacheMs: 60000 }).catch(() => null);
  if (!queue || queue.count < UNTAGGED_NUDGE_MIN) return;
  const now = new Date();
  const week = Math.floor((now - new Date(now.getFullYear(), 0, 1)) / (7 * 86400000));
  recordNotification({
    kind: "assist",
    title: `${queue.count} filings to check`,
    detail: "Atlas was unsure where these belong. Accept each, or move it.",
    key: `review:${now.getFullYear()}-${week}`,
    action: { tab: "notes", filter: "is:review" },
  });
}

//: **The app notices what the person has not got round to** (INBOX 162).
//: Once the notebook is loaded, a bell entry counts the real notes with no
//: tag and offers the filtered list. Keyed by the ISO week, so it is said
//: once a week at most however often the list reloads, and only past a
//: handful: three untagged notes is a Tuesday, not a backlog.
const UNTAGGED_NUDGE_MIN = 5;

function nudgeUntaggedNotes() {
  const untagged = allEntries.filter((e) => !e.is_board && !e.is_draft && !e.map_topic && !(e.tags || []).length);
  if (untagged.length < UNTAGGED_NUDGE_MIN) return;
  const now = new Date();
  const week = Math.floor((now - new Date(now.getFullYear(), 0, 1)) / (7 * 86400000));
  recordNotification({
    kind: "assist",
    title: `${untagged.length} notes have no tags`,
    detail: "Tags are how notes find each other. Open the list and add a few.",
    key: `untagged:${now.getFullYear()}-${week}`,
    action: { tab: "notes", filter: "is:untagged" },
  });
}
