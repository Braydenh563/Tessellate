//: The reminder edit form, split out of shell-reminders.js (the boot-script
//: gzip budget): only the one row being edited needs it. `reminderItem`
//: loads this file with `lazyScript` and swaps the form in; the Save and
//: Cancel handlers use the always-loaded `editingReminderId`, `reminderPutUndoably`
//: and `loadReminders`.

// A <select> from [value, label] pairs, with one option preselected.
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
  row.appendChild(
    smallButton("Save", "", async () => {
      const text = textInput.value.trim();
      if (!text || !dueInput.value) {
        toast("A reminder needs text and a time.", "info");
        return;
      }
      editingReminderId = null;
      const before = { text: reminder.text, due_at: reminder.due_at, priority: reminder.priority || "normal", recurring: reminder.recurring || "none", alert_minutes: alertNow };
      await reminderPutUndoably(reminder.id, "Edited a reminder", before, {
        text,
        due_at: new Date(dueInput.value).toISOString(),
        priority: prioritySelect.value,
        recurring: recurringSelect.value,
        alert_minutes: Number(alertSelect.value),
      });
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
