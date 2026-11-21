//: The reminder edit form, split out of shell-reminders.js (the boot-script
//: gzip budget): only the one row being edited needs it. `reminderItem`
//: loads this file with `lazyScript` and swaps the form in; the Save and
//: Cancel handlers use the always-loaded `editingReminderId`, `reminderPutUndoably`
//: and `loadReminders`.

// A <select> from [value, label] pairs, with one option preselected.
(() => {
  function buildSelect(options, selected) {
    const select = document.createElement("select");
    select.className = "small-select";
    for (const [value, label] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      if (value === selected) option.selected = true;
      select.appendChild(option);
    }
    return select;
  }

  function reminderEditForm(reminder) {
    const wrap = document.createElement("div");
    wrap.className = "inline-action";
    const textInput = document.createElement("input");
    textInput.type = "text";
    textInput.maxLength = 500;
    textInput.value = reminder.text;
    const dueInput = document.createElement("input");
    dueInput.type = "datetime-local";
    dueInput.value = toLocalInputValue(reminder.due_at);
    const prioritySelect = buildSelect(
      [
        ["normal", "Normal"],
        ["low", "Low priority"],
        ["high", "High priority"],
      ],
      reminder.priority || "normal"
    );
    prioritySelect.title = "Priority";
    const recurringSelect = buildSelect(
      [
        ["none", "Once"],
        ["daily", "Daily"],
        ["weekly", "Weekly"],
        ["monthly", "Monthly"],
        //: A rule the menu has no word for (every weekday) is kept, not
        //: dropped to Once by a Save that only changed the text.
        ...(["none", "daily", "weekly", "monthly"].includes(reminder.recurring || "none") ? [] : [[reminder.recurring, reminder.repeat_words || reminder.recurring]]),
      ],
      reminder.recurring || "none"
    );
    recurringSelect.title = "Repeat";
    //: The early alert was only ever settable when a reminder was made (the
    //: quick add reads "1 day before"); the edit form had no way to change or
    //: clear it. 0 is the API's word for "no alert".
    const alertPresets = [[0, "No alert"], [10, "10 minutes before"], [30, "30 minutes before"], [60, "1 hour before"], [1440, "1 day before"], [10080, "1 week before"]];
    const alertNow = Number(reminder.alert_minutes) || 0;
    if (!alertPresets.some(([minutes]) => minutes === alertNow)) alertPresets.push([alertNow, reminder.alert_words || `${alertNow} minutes before`]);
    const alertSelect = buildSelect(alertPresets.map(([minutes, label]) => [String(minutes), label]), String(alertNow));
    alertSelect.title = "Alert";
    alertSelect.setAttribute("aria-label", "Alert");
    const row = document.createElement("div");
    row.className = "row";
    //: One gap under the fields (INBOX 1468: Save sat flush under them, 0px).
    row.style.marginTop = "var(--space-2)";
    row.appendChild(
      smallButton("Save", "", async () => {
        const text = textInput.value.trim();
        if (!text || !dueInput.value) {
          toast("A reminder needs text and a time.", "info");
          return;
        }
        //: **The time goes only when it changed** (INBOX 1468). An overdue
        //: reminder's own past time was sent back on every Save and refused as a
        //: past date, so no overdue or repeating-overdue reminder could be edited.
        const timeChanged = dueInput.value !== toLocalInputValue(reminder.due_at);
        const before = { text: reminder.text, priority: reminder.priority || "normal", recurring: reminder.recurring || "none", alert_minutes: alertNow };
        const after = { text, priority: prioritySelect.value, recurring: recurringSelect.value, alert_minutes: Number(alertSelect.value) };
        if (timeChanged) {
          before.due_at = reminder.due_at;
          after.due_at = new Date(dueInput.value).toISOString();
        }
        editingReminderId = null;
        try {
          const action = await reminderPutUndoably(reminder.id, "Edited a reminder", before, after);
          //: The same Undo toast delete and snooze give (it was Ctrl+Z only).
          toastAction(`Saved ${toastName(text, "the reminder")}.`, "Undo", async () => {
            settleUndoFromToast(action);
            await action.undo().catch((e) => toast(e.message, true));
            toast(`Put back ${toastName(reminder.text, "the reminder")}.`);
          });
        } catch (error) {
          //: A refusal (a new time already gone) says why and keeps the form.
          editingReminderId = reminder.id;
          if (error.isLockout) return;
          toast(error.message || "Couldn't save that reminder.", true);
          dueInput.setAttribute("aria-invalid", "true");
          dueInput.focus();
        }
      }, false)
    );
    row.appendChild(
      smallButton("Cancel", "", () => {
        editingReminderId = null;
        loadReminders();
      })
    );
    const fields = document.createElement("div");
    fields.className = "row";
    fields.style.flexWrap = "wrap";
    for (const field of [dueInput, prioritySelect, recurringSelect, alertSelect]) {
      field.style.height = "var(--control-h)";
      fields.append(field);
    }
    wrap.append(textInput, fields, row);
    //: Enter saves and Escape cancels, from any field in the form: the two
    //: keys every inline editor answers. Only the buttons did before.
    wrap.addEventListener("keydown", (event) => {
      if (event.isComposing) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        row.querySelectorAll("button")[1]?.click();
      } else if (event.key === "Enter" && event.target.tagName === "INPUT") {
        event.preventDefault();
        row.querySelector("button")?.click();
      }
    });
    setTimeout(() => textInput.focus(), 0);
    return wrap;
  }

  //: L-general-10: ticking a reminder that points at a note asks for one line
  //: on how it went and appends it to that note. Optional: Cancel, Escape or
  //: an empty line leaves the note alone. The append goes through the entry
  //: update route with the hash it read, so an edit made meanwhile is a 409
  //: and not a lost line.
  async function askReminderOutcome(reminder) {
    if (!reminder.entry_id || (reminder.target_kind || "note") !== "note") return;
    const said = await promptDialog("How did it go? One line, or skip", "", { confirmLabel: "Add to note" });
    const line = String(said || "").replace(/\s+/g, " ").trim().slice(0, 300);
    if (!line) return;
    const write = async () => {
      try {
        const note = await apiJson(`/entries/${reminder.entry_id}`);
        if (typeof note.content !== "string") throw new Error("locked");
        const day = new Date().toLocaleDateString("en-CA");
        const content = `${note.content.replace(/\s+$/, "")}\n\nOutcome (${day}): ${line}`;
        const put = (text) => async () => { await apiJson(`/entries/${reminder.entry_id}`, { method: "PUT", body: JSON.stringify({ content: text }) }); };
        await apiJson(`/entries/${reminder.entry_id}`, { method: "PUT", body: JSON.stringify({ content, base_hash: note.content_hash }) });
        const action = pushUndo("Added an outcome to a note", put(note.content), put(content));
        toastAction("Added the outcome to its note.", "Undo", async () => {
          settleUndoFromToast(action);
          await put(note.content)();
        });
      } catch (e) {
        toast("Couldn't add the outcome to its note.", true, { action: ["Try again", write] });
      }
    };
    await write();
  }

  //: L-general-12: the overdue ones, one decision each (Still matters leaves it
  //: as it is, Drop moves it to the bin, Reschedule takes tomorrow 9am), or one
  //: decision for all of them. Applied together, with one Undo.
  function openOverdueTriage(items) {
    const choice = new Map(items.map((r) => [r.id, "keep"]));
    openSheet({
      label: "Overdue reminders",
      sub: "Decide each one, or apply one choice to all.",
      name: "reminder-triage",
      build: (card, close) => {
        const list = document.createElement("ul");
        list.className = "entry-list";
        const options = [["keep", "Still matters"], ["drop", "Drop"], ["move", "Reschedule"]];
        const paint = () => {
          for (const pick of list.querySelectorAll("select")) pick.value = choice.get(Number(pick.dataset.id));
        };
        for (const reminder of items) {
          const li = document.createElement("li");
          li.dataset.id = reminder.id;
          const text = document.createElement("span");
          text.className = "reminder-text";
          text.textContent = `${reminder.text} · ${relativeWhen(reminder.due_at)}`;
          const pick = buildSelect(options, "keep");
          pick.setAttribute("aria-label", `Decide: ${reminder.text}`);
          pick.dataset.id = reminder.id;
          pick.addEventListener("change", () => choice.set(reminder.id, pick.value));
          li.append(text, pick);
          list.appendChild(li);
        }
        const bulk = document.createElement("div");
        bulk.className = "row";
        const all = document.createElement("span");
        all.className = "muted";
        all.textContent = "Apply to all:";
        bulk.appendChild(all);
        for (const [value, label] of options) {
          bulk.appendChild(smallButton(label, `${label} for every overdue reminder`, () => {
            for (const r of items) choice.set(r.id, value);
            paint();
          }));
        }
        const apply = document.createElement("button");
        apply.type = "button";
        apply.textContent = "Apply";
        apply.addEventListener("click", async () => {
          const drops = items.filter((r) => choice.get(r.id) === "drop");
          const moves = items.filter((r) => choice.get(r.id) === "move");
          close();
          if (!drops.length && !moves.length) return;
          const when = presetDate("tomorrow").toISOString();
          const put = (r, body) => apiJson(`/reminders/${r.id}`, { method: "PUT", body: JSON.stringify({ ...body, restore: true }) });
          const forward = async () => {
            await Promise.all([...drops.map((r) => api(`/reminders/${r.id}`, { method: "DELETE" })), ...moves.map((r) => put(r, { due_at: when }))]);
            loadReminders();
          };
          const back = async () => {
            await Promise.all([...drops.map((r) => api(`/reminders/${r.id}/restore`, { method: "POST" })), ...moves.map((r) => put(r, { due_at: r.due_at }))]);
            loadReminders();
          };
          await forward().catch((e) => { toast(e.message, true); loadReminders(); });
          const action = pushUndo("Sorted overdue reminders", back, forward);
          toastAction(`Dropped ${drops.length}, rescheduled ${moves.length}.`, "Undo", async () => {
            settleUndoFromToast(action);
            await back();
          });
        });
        card.append(list, bulk, apply);
        paint();
      },
    });
  }

  async function snoozeReminderTo(reminder, when) {
    const before = { due_at: reminder.due_at, done: Boolean(reminder.done) };
    const put = (body) =>
      apiJson(`/reminders/${reminder.id}`, { method: "PUT", body: JSON.stringify({ ...body, restore: true }) });
    await put({ due_at: when.toISOString(), done: false });
    loadReminders();
    //: Undo puts the old time and state back (WORLD_CLASS_PLAN row 32, from
    //: the world-class branch's 2d867a1); `restore` lets a time already past
    //: through (an overdue reminder is the one that gets snoozed).
    const back = async () => {
      await put(before);
      loadReminders();
    };
    const action = pushUndo("Snoozed a reminder", back, async () => {
      await put({ due_at: when.toISOString(), done: false });
      loadReminders();
    });
    toastAction(`Snoozed to ${whenText(when)}.`, "Undo", async () => {
      settleUndoFromToast(action);
      await back();
    });
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  //: The outcome prompt and the triage sheet ride on `snoozeReminderTo`, which is
  //: already global: two more names would break the shared-scope cap.
  Object.assign(snoozeReminderTo, { askOutcome: askReminderOutcome, triage: openOverdueTriage });
  Object.assign(window, { reminderEditForm, snoozeReminderTo });
})();
