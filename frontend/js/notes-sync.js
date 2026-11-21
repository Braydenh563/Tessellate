// notes-sync.js: a change made on another device shows here (`followNoteChanges`, its timer and the
// visibility listener). Moved out of notes-list.js (LEDGER L698, L639) to come off the boot file: lazy, the
// `notesSync` bundle, started by `ensureModule("notesSync")` where notes-list.js used to call it, so it begins
// as early as it did. Nothing else calls it.


//: **A change made on another device shows here** (INBOX 881, the owner
//: 2026-10-11: "what if I make a change on my phone?? does it live
//: update??"). Every `NOTE_CHANGES_MS` while the page is visible, and at once
//: when it comes back (the phone's browser brought forward), the list asks
//: `GET /entries/changes` which notes moved since its last answer and
//: patches those in with `refreshEntries`. The note being edited is left
//: alone: its Save sends `base_hash`, so a newer text from elsewhere still
//: gets the Keep mine / Take theirs prompt rather than being overwritten
//: under the person's cursor. `seen` drops an id already refreshed at the
//: same `updated_at` (the server's stamp overlaps by two seconds).
const NOTE_CHANGES_MS = 15_000;
const noteChanges = { since: "", seen: new Map(), timer: 0, busy: false, quiet: 0 };
async function followNoteChanges() {
  clearTimeout(noteChanges.timer);
  if (document.hidden) return;
  noteChanges.timer = setTimeout(followNoteChanges, noteChanges.since ? NOTE_CHANGES_MS * (noteChanges.quiet >= 4 ? 2 : 1) : 2000);
  //: The first stamp is taken as soon as there is a session, before the list
  //: has finished loading, so a change made while it loads is not missed.
  if (noteChanges.busy || !authToken() || (noteChanges.since && !entriesComplete)) return;
  noteChanges.busy = true;
  try {
    const body = await apiJson(`/entries/changes?since=${encodeURIComponent(noteChanges.since)}`, { silent: true });
    const first = !noteChanges.since;
    noteChanges.since = body.since;
    if (first) return;
    //: More than one answer holds: an empty patch is `refreshEntries`'s full read.
    if (body.more) return void refreshEntries([]);
    const ids = body.ids.filter((id) => id !== appState.get("note") && noteChanges.seen.get(id) !== body.stamps[id]);
    if (noteChanges.seen.size > 500) noteChanges.seen.clear();
    for (const id of body.ids) noteChanges.seen.set(id, body.stamps[id]);
    //: Battery: four empty answers in a row slow the ask to 30 s; a change or a return to the tab restores 15 s.
    noteChanges.quiet = body.ids.length ? 0 : noteChanges.quiet + 1;
    if (!ids.length) return;
    await refreshEntries(ids);
    refreshNotePage(ids);
  } catch {
    /* offline or locked: the next tick asks again */
  } finally {
    noteChanges.busy = false;
  }
}
document.addEventListener("visibilitychange", () => {
  noteChanges.quiet = 0;
  followNoteChanges();
});
followNoteChanges();
