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

  //: The Overdue heading's bulk choices (L-general-12), pressed from `loadReminders.overdueTriage`
  //: (shell-reminders.js). A property, not a global (the scope ratchet).
  loadReminders.overdueRun = function (choice, items) {
    const rows = items.map((r) => ({ id: r.id, due_at: r.due_at, done: r.done }));
    //: allSettled, not all: one refused reminder stopped the batch's reload and its Undo while the
    //: others had already changed (review 5899359161). Returns the rows the server took.
    const each = async (list, call) => {
      const results = await Promise.allSettled(list.map(call));
      loadReminders();
      const ok = list.filter((_, i) => results[i].status === "fulfilled");
      if (ok.length < list.length) toast(`Could not change ${list.length - ok.length} of ${list.length} overdue reminders.`, true);
      return ok;
    };
    const put = (bodyOf) => (r) => apiJson(`/reminders/${r.id}`, { method: "PUT", body: JSON.stringify({ ...bodyOf(r), restore: true }) });
    const back = put((r) => ({ due_at: r.due_at, done: r.done }));
    const drop = (r) => apiJson(`/reminders/${r.id}`, { method: "DELETE" });
    const restore = (r) => apiJson(`/reminders/${r.id}/restore`, { method: "POST" });
    const many = (count) => `${count} overdue reminder${count === 1 ? "" : "s"}`;
    const n = many(rows.length);
    //: One Undo for the batch, never one per reminder, and only over the rows that changed.
    const run = async (label, forward, undo, done) => {
      const ok = await each(rows, forward);
      if (!ok.length) return;
      const action = pushUndo(label(many(ok.length)), () => each(ok, undo), () => each(ok, forward));
      toastAction(done(many(ok.length)), "Undo", async () => {
        settleUndoFromToast(action);
        await each(ok, undo);
      });
    };
    const moveTo = (dateOf, words) => () => {
      const due = dateOf().toISOString();
      return run((m) => `Moved ${m}`, put(() => ({ due_at: due, done: false })), back, (m) => `Moved ${m} to ${words}.`);
    };
    const nextMonday = () => {
      const d = presetDate("tomorrow");
      d.setDate(d.getDate() + ((8 - d.getDay()) % 7));
      return d;
    };
    const binAll = async () => {
      if (!(await confirmDialog(`Move ${n} to the bin?`, { confirmLabel: "Delete", danger: true }))) return;
      await run((m) => `Moved ${m} to the bin`, drop, restore, (m) => `Moved ${m} to the bin.`);
    };
    const choices = {
      tomorrow: moveTo(() => presetDate("tomorrow"), "tomorrow 9am"),
      monday: moveTo(nextMonday, "next Monday 9am"),
      done: () => run((m) => `Completed ${m}`, put(() => ({ done: true })), back, (m) => `Marked ${m} done.`),
      bin: binAll,
    };
    return choices[choice]();
  };

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { reminderEditForm, snoozeReminderTo });
})();
