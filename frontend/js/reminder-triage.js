// Lazy (`loadReminders.act(name, detail)` in shell-reminders.js loads it, then fires `reminders:<name>`):
// a finished reminder's outcome line for its note (L-general-10), and the Overdue triage sheet (L-general-12).
// Every act joins the undo stack; a bulk act is one entry.

(() => {
  //: Empty (Skip, Escape, Enter on nothing) does nothing at all. The note is read just before the write, so
  //: the append lands on the text as it is now. Undo takes off only the appended line, read again first, so an
  //: edit made since is kept (review of PR 222); a note whose end changed is left as it is. A private note with
  //: the vault locked refuses the write (409, `test_a_locked_vault_refuses_an_edit_of_a_private_note`).
  async function reminderOutcomePrompt(reminder) {
    if (!reminder?.entry_id) return false;
    const typed = await promptDialog(`How did it go? ${reminder.text || "This reminder"}`, "", {
      confirmLabel: "Add to note",
      cancelLabel: "Skip",
    });
    const line = (typed || "").replace(/\s+/g, " ").trim();
    if (!line) return false;
    const id = reminder.entry_id;
    try {
      const before = await apiJson(`/entries/${id}`);
      const base = (before.content || "").replace(/\s+$/, "");
      const after = `${base}\n\nOutcome (${new Date().toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}): ${line}`;
      const added = after.slice(base.length);
      const put = (content) => async () => {
        await apiJson(`/entries/${id}`, { method: "PUT", body: JSON.stringify({ content }) });
        await refreshEntries([id]).catch(() => {});
      };
      const takeOff = async () => {
        const now = (await apiJson(`/entries/${id}`)).content || "";
        if (!now.endsWith(added)) throw new Error("The note changed since, so the outcome line was left in it.");
        await put(now.slice(0, now.length - added.length))();
      };
      const putBack = async () => {
        const now = ((await apiJson(`/entries/${id}`)).content || "").replace(/\s+$/, "");
        await put(`${now}${added}`)();
      };
      await put(after)();
      const undoable = pushUndo("Added an outcome to a note", takeOff, putBack);
      toastAction("Added the outcome to the note.", "Undo", async () => {
        settleUndoFromToast(undoable);
        await takeOff().catch((e) => toast(e.message, true));
      });
      return true;
    } catch (e) {
      toast(e.message || "Couldn't add the outcome to the note.", true);
      return false;
    }
  }

  const dayValue = (d) => d.toLocaleDateString("sv");

  //: A day chosen in the date field, as a time: 9 in the morning, or an hour from now when that has passed (today).
  function triageDueFor(value, now = new Date()) {
    const [y, m, d] = value.split("-").map(Number);
    const at = new Date(y, m - 1, d, 9, 0, 0, 0);
    return at.getTime() < now.getTime() + 60000 ? new Date(now.getTime() + 60 * 60 * 1000) : at;
  }

  const putReminder = (id, body) =>
    apiJson(`/reminders/${id}`, { method: "PUT", body: JSON.stringify({ ...body, restore: true }) });
  const binReminder = (id) => apiJson(`/reminders/${id}`, { method: "DELETE" });
  const unbinReminder = (id) => apiJson(`/reminders/${id}/restore`, { method: "POST" });

  //: A row's name and due time: no state of the sheet, so it lives outside `openReminderTriage`.
  function triageRowText(reminder) {
    const text = document.createElement("div");
    text.className = "triage-text";
    const name = document.createElement("span");
    name.className = "triage-name";
    name.textContent = reminder.text;
    const when = document.createElement("span");
    when.className = "muted triage-when";
    when.textContent = `Due ${relativeWhen(reminder.due_at)}`;
    text.append(name, when);
    return text;
  }

  async function openReminderTriage(reminders) {
    lazyScript("/css/triage-lazy.css");
    const rows = (reminders || []).filter((r) => !r.done);
    if (!rows.length) return null;
    const kept = new Set();
    let list = null;
    let note = null;
    let dateInput = null;
    let bulk = [];

    const remaining = () => rows.filter((r) => !kept.has(r.id) && !r.gone);
    const afterAct = () => {
      loadReminders();
      paint();
    };

    //: The toast's Undo and the stack's undo run the same `back`; either puts the sheet's rows back too.
    const toastUndo = (message, action, back) =>
      toastAction(message, "Undo", async () => {
        settleUndoFromToast(action);
        await back().catch((e) => toast(e.message, true));
        paint();
      });

    //: One act on the reminders given, drop or move: one stack entry and one toast Undo, whether for a row or for all.
    async function act(todo, kind, value) {
      if (!todo.length) return;
      if (kind === "move" && !value) return; // a cleared date field (the buttons are off then too)
      const when = kind === "move" ? triageDueFor(value) : null;
      let done = todo;
      const apply = async () => {
        for (const r of done) {
          if (when) await putReminder(r.id, { due_at: when.toISOString(), done: false });
          else await binReminder(r.id);
          r.gone = true;
        }
        loadReminders();
      };
      const back = async () => {
        for (const r of done) {
          if (when) await putReminder(r.id, { due_at: r.due_at, done: false });
          else await unbinReminder(r.id);
          r.gone = false;
        }
        loadReminders();
      };
      try {
        await apply();
      } catch (e) {
        //: Some went before one failed (review of PR 222): those keep an Undo, then the failure is said.
        done = todo.filter((r) => r.gone);
        if (done.length) undoFor(done, when, back, apply);
        afterAct();
        throw e;
      }
      undoFor(todo, when, back, apply);
      afterAct();
    }

    function undoFor(todo, when, back, apply) {
      const plural = todo.length === 1 ? "an overdue reminder" : `${todo.length} overdue reminders`;
      const label = `${when ? "Rescheduled" : "Dropped"} ${plural}`;
      toastUndo(`${label}${when ? ` to ${whenText(when)}` : ""}.`, pushUndo(label, back, apply), back);
    }

    function rowEl(reminder) {
      const li = document.createElement("li");
      li.className = "triage-row";
      li.dataset.id = reminder.id;
      const text = triageRowText(reminder);
      const acts = document.createElement("span");
      acts.className = "row triage-acts";
      const keep = smallButton("Still matters", "Keep this reminder as it is", () => {
        kept.add(reminder.id);
        paint();
      });
      keep.dataset.triage = "keep";
      const drop = smallButton("Drop", "Move this reminder to the bin", () => act([reminder], "drop").catch((e) => toast(e.message, true)));
      drop.dataset.triage = "drop";
      const move = smallButton("Reschedule", "Move this reminder to the chosen day", () =>
        act([reminder], "move", dateInput.value).catch((e) => toast(e.message, true))
      );
      move.dataset.triage = "move";
      move.disabled = !dateInput.value;
      acts.append(keep, drop, move);
      li.append(text, acts);
      return li;
    }

    let focusAt = null;
    function paint() {
      if (!list) return;
      const at = [...list.children].findIndex((li) => li.contains(document.activeElement));
      if (at >= 0) focusAt = at;
      const todo = remaining();
      list.replaceChildren(...todo.map(rowEl));
      note.textContent = todo.length
        ? `${todo.length} overdue. Keep what still matters, drop the rest, or move it to a day.`
        : "Nothing left to triage.";
      for (const b of bulk) b.disabled = !todo.length;
      if (bulk[0]) bulk[0].disabled = !todo.length || !dateInput.value;
      //: Focus would fall to the page with the row it was on (review of PR 222): the row now in its place, else the note.
      if (focusAt !== null) {
        const row = list.children[Math.min(focusAt, list.children.length - 1)];
        (row?.querySelector("button:not(:disabled)") || note).focus();
        focusAt = null;
      }
    }

    return openSheet({
      label: "Triage overdue reminders",
      name: "reminder-triage",
      build: (card) => {
        note = document.createElement("p");
        note.className = "muted triage-note";
        note.setAttribute("role", "status");
        note.tabIndex = -1;
        const bar = document.createElement("div");
        bar.className = "row";
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        dateInput = document.createElement("input");
        dateInput.type = "date";
        dateInput.id = "triage-day";
        dateInput.value = dayValue(tomorrow);
        dateInput.min = dayValue(new Date());
        dateInput.setAttribute("aria-label", "Day to move reminders to");
        dateInput.addEventListener("input", () => paint());
        const moveAll = smallButton("Reschedule all", "Move every reminder left here to the chosen day", () =>
          act(remaining(), "move", dateInput.value).catch((e) => toast(e.message, true))
        );
        moveAll.id = "triage-move-all";
        const dropAll = smallButton("Drop all", "Move every reminder left here to the bin", () =>
          act(remaining(), "drop").catch((e) => toast(e.message, true))
        );
        dropAll.id = "triage-drop-all";
        bulk = [moveAll, dropAll];
        bar.append(dateInput, moveAll, dropAll);
        list = document.createElement("ul");
        list.className = "entry-list triage-list";
        card.append(note, bar, list);
        paint();
      },
    });
  }

  //: Clear done (moved here from shell-reminders.js: only its button reaches it, so it need not load at boot).
  async function clearDoneReminders() {
    //: To the end, or this clears the first page's done rows and reports that
    //: count as if it were all of them.
    const all = await apiPagedList("/reminders", 200).catch(() => null);
    if (!all) return toast("Couldn't load your reminders. Try again.", true, { action: ["Try again", clearDoneReminders] });
    const done = all.filter((r) => r.done);
    if (!done.length) return;
    if (!(await confirmDialog(`Delete ${done.length} completed reminder${done.length === 1 ? "" : "s"}?`))) {
      return;
    }
    //: One Undo for the lot (INBOX 537): they go to the recycle bin and come
    //: back from it (WORLD_CLASS_PLAN 5 item 10).
    //: Every delete is tried; how many failed is said once (audit 2026-10-05,
    //: FE-12), where a silent catch let them come back unexplained, with a Try
    //: again for just those rows.
    const drop = async (rows = done) => {
      const results = await Promise.all(
        rows.map((r) => api(`/reminders/${r.id}`, { method: "DELETE" }).then(() => true, () => false))
      );
      const left = rows.filter((_, i) => !results[i]);
      if (left.length) toast(`Couldn't delete ${left.length} of the reminders.`, true, { action: ["Try again", () => drop(left)] });
      loadReminders();
    };
    const remake = async (rows = done) => {
      const results = await Promise.all(
        rows.map((r) => api(`/reminders/${r.id}/restore`, { method: "POST" }).then(() => true, () => false))
      );
      const left = rows.filter((_, i) => !results[i]);
      if (left.length) toast(`Couldn't bring back ${left.length} of the reminders.`, true, { action: ["Try again", () => remake(left)] });
      loadReminders();
    };
    await drop();
    const action = pushUndo(`Cleared ${done.length} completed reminders`, remake, drop);
    toastAction(`Cleared ${done.length} completed reminder${done.length === 1 ? "" : "s"}.`, "Undo", async () => {
      settleUndoFromToast(action);
      await remake().catch((e) => toast(e.message, true));
    });
  }

  //: No new names in the shared scope (the ratchet): shell-reminders.js loads this file and then sends one of these.
  document.addEventListener("reminders:outcome", (event) => reminderOutcomePrompt(event.detail));
  document.addEventListener("reminders:clear", clearDoneReminders);
  document.addEventListener("reminders:triage", (event) => openReminderTriage(event.detail));
})();
