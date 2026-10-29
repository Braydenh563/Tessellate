// note-history.js: one note's History, everything that ever happened to it
// with a way back to any of it. A lazy piece (app.js LAZY_MODULES), moved out
// of menus.js on 2026-10-03 (INBOX 432) to bring the boot scripts back under
// their gzip total: it runs only when History is chosen from a note's menu,
// and boot code reaches it through LAZY_ENTRY_POINTS. The words and the actor
// label it uses stay in menus.js, which the dashboard's feed shares.

async function openEntryHistory(entry) {
  const overlay = $("history-overlay");
  const list = $("history-list");
  $("history-status").textContent = "";
  $("history-status").classList.remove("error");
  list.replaceChildren();
  overlay.classList.remove("hidden");
  $("history-close").focus();

  let history;
  try {
    history = await apiJson(`/entries/${entry.id}/history`).catch(async (error) => {
      //: A locked private note answers 409 "Unlock first." (INBOX 1437): the
      //: usual password prompt, then the sheet reads once more.
      if (error?.detail !== "Unlock first." || !(await ensureVaultOpen())) throw error;
      return apiJson(`/entries/${entry.id}/history`);
    });
  } catch (error) {
    if (error?.detail === "Unlock first.") {
      overlay.classList.add("hidden");
      return;
    }
    $("history-status").classList.add("error");
    $("history-status").textContent = error.message;
    return;
  }
  const events = history?.items || [];
  const revisions = history?.revisions || [];
  if (!events.length && !revisions.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Nothing has happened to this note yet, so there's nothing to go back to.";
    list.appendChild(p);
    return;
  }

  //: Rule 1.8: putting a version back is one Undo (the bar, Ctrl+Z, the
  //: toast), not a confirm before it. Undo writes back the text and tags the
  //: note had when the sheet opened; the server keeps that text as a version
  //: too, so the sheet itself is a second way back.
  const restoreTo = async (url, message) => {
    const before = { content: entry.content, tags: entry.tags || [] };
    const show = async () => {
      await loadEntries();
      flashEntry(entry.id);
    };
    const back = async () => {
      await apiJson(`/entries/${entry.id}`, { method: "PUT", body: JSON.stringify(before) });
      await show();
    };
    const again = async () => {
      await apiJson(url, { method: "POST" });
      await show();
    };
    try {
      await apiJson(url, { method: "POST" });
    } catch (error) {
      $("history-status").classList.add("error");
      $("history-status").textContent = error.message;
      return;
    }
    overlay.classList.add("hidden");
    const action = pushUndo("Put back an earlier version", back, again);
    toastAction(message, "Undo", async () => {
      settleUndoFromToast(action);
      await back();
    });
    await show();
  };

  // The current text first, so you can see what you'd be replacing.
  const current = document.createElement("div");
  current.className = "history-entry history-current";
  const currentHead = document.createElement("p");
  currentHead.className = "muted";
  currentHead.textContent = "Now";
  const currentBody = document.createElement("p");
  currentBody.textContent = notePreviewText(entry.content);
  current.append(currentHead, currentBody);
  list.appendChild(current);

  // The row every event renders as. A function rather than a loop body
  // because a second page of events is rendered by the same code, below.
  const eventRow = (item) => {
    const row = document.createElement("div");
    row.className = "history-entry";
    const head = document.createElement("p");
    head.className = "muted";
    head.textContent = `${HISTORY_ACTION_WORDS[item.action] || item.action} ${relativeTime(item.created_at)}`;
    head.title = whenText(item.created_at); // the exact time, on hover and to a reader
    const actor = historyActorLabel(item.actor);
    if (actor) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chipWords(chip, actor);
      head.append(" ", chip);
    }
    row.appendChild(head);
    //: A filing says where and who decided: "filed under Gym by
    //: granite4.1:3b, 82% sure" (manager.record_filing's `by`).
    if (item.action === "filed" && item.detail) {
      const who = document.createElement("p");
      who.className = "muted small";
      who.textContent = item.detail.charAt(0).toUpperCase() + item.detail.slice(1);
      row.appendChild(who);
    }
    if (item.compacted) {
      // The event is still a fact, its text is not kept: `events.compact`
      // drops the values behind changes older than the history window so the
      // log stops growing by a copy of the note on every edit. Saying that in
      // the row is the difference between a history with a gap and a history
      // that looks broken.
      const gone = document.createElement("p");
      gone.className = "muted";
      gone.textContent = "The text from this change is no longer kept.";
      row.appendChild(gone);
    } else if (item.content) {
      const body = document.createElement("p");
      body.textContent = notePreviewText(item.content);
      row.appendChild(body);
      // Only a version that differs from what is on screen is worth putting
      // back: offering "restore" on the state the note is already in reads as
      // a broken button rather than a safe one.
      if (item.content !== entry.content) {
        row.appendChild(
          smallButton("ph:arrow-u-up-left Put this back", "Restore this version", () =>
            restoreTo(`/entries/${entry.id}/restore/${item.id}`, "Earlier version restored.")
          )
        );
        //: Then and now (WORLD_CLASS_PLAN I5, row 23): what this note
        //: claimed at the end of that day against what it claims today.
        row.appendChild(
          smallButton("ph:arrows-left-right Then and now", "Compare what this note said then with what it says now", (event) =>
            toggleThenAndNow(entry, item.content, row, event.currentTarget)
          )
        );
      }
    }
    return row;
  };

  // **Paging, and saying what is on screen.** `GET /entries/{id}/history`
  // returns at most `HISTORY_PAGE` (fifty) events and a `next_cursor` for
  // what is older than the oldest of them. This sheet used to read the first
  // page and drop the cursor, so a note edited more than fifty times showed
  // its newest fifty and looked like the whole history: silent truncation,
  // which is worse than a short list, because nothing on screen says the
  // rest exists and a version that is still there reads as lost. The row
  // below is both halves of the fix: it counts what is shown and it fetches
  // the next page.
  let shown = 0;
  let paged = false;  // whether "load older" has been pressed at least once
  let cursor = history?.next_cursor || null;

  // The control sits at the bottom of the events and stays there: the pages
  // that follow are inserted above it, so the list stays in newest-first
  // order however many times it is pressed.
  const more = document.createElement("div");
  more.className = "history-entry";

  const addEvents = (items) => {
    for (const item of items) {
      list.insertBefore(eventRow(item), more);
      shown += 1;
    }
  };

  const loadOlder = async () => {
    if (!cursor) return;
    const at = cursor;
    cursor = null;  // so a second press while this one is in flight is a no-op
    renderMore(true);
    let page;
    try {
      page = await apiJson(`/entries/${entry.id}/history?before=${at}`);
    } catch (error) {
      cursor = at;
      renderMore();
      $("history-status").classList.add("error");
      $("history-status").textContent = error.message;
      return;
    }
    addEvents(page?.items || []);
    paged = true;
    cursor = page?.next_cursor || null;
    renderMore();
  };

  const renderMore = (loading = false) => {
    more.replaceChildren();
    // A history that fits in one page says nothing extra: the row exists to
    // answer "is this all of it?", and on a note with a dozen changes the
    // list already answers that by ending.
    more.classList.toggle("hidden", !cursor && !loading && !paged);
    const note = document.createElement("p");
    note.className = "muted";
    if (cursor || loading) {
      // Plain about what it is: the count is what is on screen, not a
      // guess at the total, which the route does not send and which
      // counting would cost a second query to know.
      note.textContent = `Showing the ${shown} most recent changes to this note.`;
    } else if (paged) {
      note.textContent = `That is all ${shown} changes to this note.`;
    }
    more.appendChild(note);
    if (cursor) {
      more.appendChild(
        smallButton("ph:clock-counter-clockwise Load older changes", "Load the next page of this note's history", loadOlder)
      );
    } else if (loading) {
      const wait = document.createElement("p");
      wait.className = "muted";
      wait.textContent = "Loading older changes.";
      more.appendChild(wait);
    }
  };

  list.appendChild(more);
  addEvents(events);
  renderMore();

  // The snapshots are the same versions the events already show, one row
  // earlier, so they are only worth rendering for a note whose edits predate
  // the event log: measured on a note edited twice, both lists said "version
  // one of the note" and the sheet showed it twice.
  const snapshotsOnly = !events.some((item) => item.content);
  for (const revision of snapshotsOnly ? revisions : []) {
    const item = document.createElement("div");
    item.className = "history-entry";
    const head = document.createElement("p");
    head.className = "muted";
    head.textContent = `Before ${whenText(revision.created_at)}`;
    const body = document.createElement("p");
    body.textContent = notePreviewText(revision.content);
    const restore = smallButton("ph:arrow-u-up-left Put this back", "Restore this version", () =>
      restoreTo(`/entries/${entry.id}/history/${revision.id}/restore`, "Earlier version restored.")
    );
    item.append(head, body, restore);
    list.appendChild(item);
  }
}


const THEN_NOW_WORDS = { revised: "Changed", dropped: "No longer says", new: "Says now" };

//: One row's then-and-now block, opened under the row and closed by the same
//: button. The row's own version against the note now (`POST
//: /entries/{id}/then-and-now`, by text, so two edits on one day are still
//: two versions): sentences paired by their words, so "Changed" shows the
//: sentence then above the sentence now.
async function toggleThenAndNow(entry, thenText, row, button) {
  const open = row.querySelector(".then-now");
  if (open) {
    open.remove();
    button?.setAttribute("aria-expanded", "false");
    return;
  }
  const block = document.createElement("div");
  block.className = "then-now";
  block.setAttribute("role", "region");
  block.setAttribute("aria-label", "Then and now");
  row.appendChild(block);
  button?.setAttribute("aria-expanded", "true");
  let body;
  try {
    body = await apiJson(`/entries/${entry.id}/then-and-now`, {
      method: "POST",
      readOnly: true,
      body: JSON.stringify({ then: thenText || "" }),
    });
  } catch (error) {
    block.textContent = error.message;
    block.classList.add("muted");
    return;
  }
  const changes = body.changed || [];
  if (!changes.length) {
    const same = document.createElement("p");
    same.className = "muted";
    same.textContent = "It says the same things now as it did then.";
    block.append(same);
    return;
  }
  for (const change of changes) {
    const item = document.createElement("div");
    item.className = `then-now-row then-now-${change.kind}`;
    const kind = document.createElement("span");
    kind.className = "chip";
    chipWords(kind, THEN_NOW_WORDS[change.kind] || change.kind);
    item.append(kind);
    if (change.then !== null && change.then !== undefined) {
      const then = document.createElement("p");
      then.className = "muted then-now-then";
      then.textContent = body.then[change.then];
      item.append(then);
    }
    if (change.now !== null && change.now !== undefined) {
      const now = document.createElement("p");
      now.className = "then-now-now";
      now.textContent = body.now[change.now];
      item.append(now);
    }
    block.append(item);
  }
  if (body.exact === false) {
    const note = document.createElement("p");
    note.className = "muted small";
    note.textContent = "Older edits to this note are no longer kept, so the version then may be later than that day.";
    block.append(note);
  }
}

//: **A skill run's own Undo** (AGENT_SKILLS_REFORM, placed 2026-10-05 from
//: brief7-event-log; Brief 13). The run's result carries `undo_span`: the
//: AI's actors and the event ids its writes fall between
//: (`skill_runner._undo_span`), which `POST /events/undo` takes as one. The
//: Recent activity widget's "Undo what Atlas did" grammar, the same plan
//: sentence (`activityUndoPlanText`): always the dry run first, shown in the
//: confirm, then that plan applied. A board item stays "can't be undone",
//: said in the plan rather than skipped silently. Lives here, beside the
//: note's own History, because both are about putting a note back; reached
//: through `LAZY_ENTRY_POINTS.noteHistory`.
async function undoSkillRun(span, button, onDone) {
  const body = { actors: span.actors || [], since: span.since || 0, until: span.until || 0 };
  let plan;
  try {
    plan = await apiJson("/events/undo", { method: "POST", body: JSON.stringify(body) });
  } catch (error) {
    toast(error.message || "Couldn't read what would be undone.", true);
    return;
  }
  const undoable = plan.items.filter((item) => item.status === "undo").length;
  if (!undoable) {
    const already = plan.items.length && plan.items.every((item) => item.status === "already undone");
    toast(already ? "Already undone: nothing this run changed is left to put back." : "Nothing this run changed can be put back from here.");
    if (already) {
      button?.remove();
      onDone?.();
    }
    return;
  }
  const byId = new Map((allEntries || []).map((entry) => [entry.id, entry]));
  const ok = await confirmDialog(`Undo this run?\n\n${activityUndoPlanText(plan, byId, "this run")}`, {
    confirmLabel: "Undo",
    danger: false,
  });
  if (!ok) return;
  try {
    const done = await apiJson("/events/undo", { method: "POST", body: JSON.stringify({ ...body, dry_run: false }) });
    toast(`Put back ${nounCount(done.undone, "note")}.`);
    button?.remove();
    onDone?.();
    await loadEntries().catch(() => {});
  } catch (error) {
    toast(error.message || "Couldn't undo that.", true);
  }
}
