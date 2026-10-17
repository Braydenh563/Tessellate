// timeline-cal-add.js: adding on a day from the Timeline's calendar
// (TIMELINE_PLAN section 12 row 6; INBOX 904 B72). Loaded by `timelineCalAdd`
// in timeline-calendar.js the first time a day is added to; its styles are in
// timeline-calendar-lazy.css, which that file has already loaded.
//
// A double click on a day or an hour, the head's Add and N open one sheet with
// the day filled (the owner: "double click on a date and be able to add an
// event and set a reminder"): a reminder, or an event, which is a meeting note
// on the day (decision 27: no events table) with a reminder at its start. The
// words are quick add's, and a chip naming a day or a time moves the fields,
// so what the fields show is what is saved.

//: Where the fields open: an hour cell's hour, else nine, or on today once
//: nine has gone the next hour (late at night, the day's last quarter).
function timelineCalAddStart(key, hour, now) {
  const pad = (n) => String(n).padStart(2, "0");
  if (hour !== null && hour !== undefined) return { date: key, time: `${pad(hour)}:00` };
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  if (key !== today || now.getHours() < 9) return { date: key, time: "09:00" };
  return { date: key, time: now.getHours() < 23 ? `${pad(now.getHours() + 1)}:00` : "23:45" };
}

//: What the fields show once the words are read: the day or time a chip says,
//: else what the fields held (the cell's, or what was typed into them). A
//: time alone keeps the cell's day: the reading puts "at 3pm" on its next
//: 3pm, which is not the day that was pressed.
function timelineCalAddFields(slots, typed) {
  const named = slots?.reading?.spans?.some((s) => !s.rank && (s.kind === "date" || s.kind === "datetime"));
  return { date: (named && slots.date) || typed.date, time: slots?.time || typed.time };
}

function timelineCalAddOpen(key, hour) {
  if (document.querySelector('[data-sheet="calendar-add"]')) return;
  timelineCal.focus = key;
  openSheet({
    label: `Add to ${TIMELINE_CAL_LONG.format(timelineCalDate(key))}`,
    sub: "A reminder, or an event saved as a meeting note.",
    name: "calendar-add",
    build: (card, close) => timelineCalAddBuild(card, close, key, timelineCalAddStart(key, hour, new Date())),
  });
}

function timelineCalAddRow(label, control, id) {
  const row = document.createElement("div");
  row.className = "prop-row";
  const name = document.createElement("label");
  name.className = "prop-key muted";
  name.textContent = label;
  control.id = id;
  name.htmlFor = id;
  row.append(name, control);
  return row;
}

function timelineCalAddBuild(card, close, key, start) {
  card.classList.add("inbox-card", "timeline-cal-adder");
  const typed = { ...start };
  const field = (type, value) => Object.assign(document.createElement("input"), { type, value, className: "prop-value" });
  const form = { kind: "reminder", date: field("date", start.date), time: field("time", start.time), words: {}, close };
  form.date.addEventListener("input", () => { typed.date = form.date.value; });
  form.time.addEventListener("input", () => { typed.time = form.time.value; });
  const show = (slots) => {
    const at = timelineCalAddFields(slots, typed);
    form.date.value = at.date;
    form.time.value = at.time;
  };
  const body = document.createElement("div");
  body.className = "inbox-body";
  //: The kind is a tab strip under the head (DESIGN.md, "A popup that
  //: chooses a kind"), words only, one tab stop, the arrows walking it.
  form.tabs = document.createElement("div");
  form.tabs.className = "tabs-line popup-kinds timeline-cal-addkind";
  form.tabs.setAttribute("role", "tablist");
  form.tabs.setAttribute("aria-label", "Reminder or event");
  form.tabs.addEventListener("keydown", (event) => {
    const to = { ArrowRight: 1, ArrowLeft: -1, Home: -9, End: 9 }[event.key];
    if (!to) return;
    event.preventDefault();
    const kinds = Object.keys(form.words);
    const at = Math.min(kinds.length - 1, Math.max(0, Math.abs(to) === 9 ? (to < 0 ? 0 : kinds.length - 1) : kinds.indexOf(form.kind) + to));
    timelineCalAddKind(form, kinds[at], true);
  });
  for (const [kind, label, surface, hint] of [["reminder", "Reminder", "reminder", "Call the dentist at 3pm"], ["event", "Event", "meeting", "Lunch with Sam at 1pm"]]) {
    const tab = Object.assign(document.createElement("button"), { type: "button", textContent: label });
    tab.title = kind === "event" ? "An event: a meeting note on the day, at its time" : "A reminder at the day and time";
    tab.setAttribute("role", "tab");
    tab.dataset.addKind = kind;
    tab.id = `timeline-cal-add-tab-${kind}`;
    tab.setAttribute("aria-controls", `timeline-cal-add-panel-${kind}`);
    tab.addEventListener("click", () => timelineCalAddKind(form, kind));
    form.tabs.appendChild(tab);
    const input = Object.assign(document.createElement("input"), { type: "text", maxLength: 200, className: "prop-value", placeholder: hint });
    const holder = document.createElement("div");
    holder.id = `timeline-cal-add-panel-${kind}`;
    holder.setAttribute("role", "tabpanel");
    holder.setAttribute("aria-labelledby", tab.id);
    holder.appendChild(timelineCalAddRow("What", input, `timeline-cal-add-${kind}`));
    body.appendChild(holder);
    form.words[kind] = { input, holder };
    quickAddAttach(input, surface, { after: holder.firstChild, onSlots: show });
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      timelineCalAddSave(form);
    });
  }
  const remind = document.createElement("label");
  remind.className = "check-row timeline-cal-addremind";
  form.remind = Object.assign(document.createElement("input"), { type: "checkbox", checked: true });
  remind.append(form.remind, Object.assign(document.createElement("span"), { textContent: "Remind me at the start" }));
  form.remindRow = remind;
  body.append(timelineCalAddRow("Day", form.date, "timeline-cal-add-date"), timelineCalAddRow("Time", form.time, "timeline-cal-add-time"), remind);
  form.status = Object.assign(document.createElement("p"), { className: "status" });
  form.status.setAttribute("role", "status");
  const actions = document.createElement("div");
  actions.className = "row right space-dialog-actions";
  const page = smallButton("ph:calendar-dot Day page", "Open this day's page, or start it", () => {
    close();
    openDayPage(key);
  }, false);
  page.className = "ghost small timeline-cal-addpage";
  const cancel = smallButton("Cancel", "Close without adding", close, false);
  cancel.className = "ghost small";
  form.add = smallButton("ph:plus Add", "Add it to the day", () => timelineCalAddSave(form), false);
  form.add.className = "accent small";
  actions.append(page, cancel, form.add);
  card.append(form.tabs, body, form.status, actions);
  timelineCalAddKind(form, "reminder");
}

//: The kind's own words box (each reads with its surface's chips, so a repeat
//: is never shown on an event that would drop it); the words carry across.
function timelineCalAddKind(form, kind, byKey = false) {
  const from = form.words[form.kind].input;
  const to = form.words[kind].input;
  if (to !== from && from.value && !to.value) {
    to.value = from.value;
    to.dispatchEvent(new Event("input"));
  }
  form.kind = kind;
  for (const [name, { holder }] of Object.entries(form.words)) holder.hidden = name !== kind;
  form.remindRow.hidden = kind !== "event";
  for (const tab of form.tabs.children) {
    const on = tab.dataset.addKind === kind;
    tab.classList.toggle("active", on);
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    if (on && byKey) tab.focus();
  }
  if (!byKey) setTimeout(() => to.focus(), 0);
}

async function timelineCalAddSave(form) {
  const { input } = form.words[form.kind];
  form.status.classList.remove("error");
  const slots = await quickAddSlots(input);
  const title = (slots ? slots.title : input.value.trim()) || input.value.trim();
  if (!title) {
    form.status.textContent = form.kind === "event" ? "Name the event, like “lunch with Sam”." : "Say what to remind you of, like “call the dentist”.";
    input.focus();
    return;
  }
  const due = new Date(`${form.date.value}T${form.time.value || "09:00"}:00`);
  if (Number.isNaN(due.getTime())) {
    form.status.textContent = "Pick a day for it.";
    return;
  }
  form.add.disabled = true;
  try {
    const made = form.kind === "event" ? await timelineCalAddEvent(form, title, due, slots) : await timelineCalAddReminder(title, due, slots);
    form.close();
    timelineCal.url = "";
    paintTimeline();
    loadReminders();
    toast(`Added “${made}” on ${TIMELINE_CAL_SHORT.format(due)}, ${TIMELINE_CAL_TIME.format(due)}.`);
  } catch (error) {
    form.status.classList.add("error");
    form.status.textContent = error.message;
    form.add.disabled = false;
  }
}

async function timelineCalAddReminder(title, due, slots) {
  const reminder = await apiJson("/reminders", {
    method: "POST",
    body: JSON.stringify({ text: title, due_at: due.toISOString(), priority: "normal", recurring: slots?.recurring || "none", alert_minutes: slots?.alert || null }),
  });
  reminderMadeUndo(reminder);
  return reminder.text;
}

//: The meeting first, then its reminder linked to it; Undo bins both.
async function timelineCalAddEvent(form, title, due, slots) {
  const pad = (n) => String(n).padStart(2, "0");
  const when = `${form.date.value}T${pad(due.getHours())}:${pad(due.getMinutes())}`;
  const made = await apiJson("/meetings", { method: "POST", body: JSON.stringify({ title, when, attendees: slots?.people || [] }) });
  const back = [[`/entries/${made.id}`, "DELETE"]];
  const again = [[`/entries/${made.id}/restore`, "POST"]];
  //: An event already past gets no reminder (the reminders refuse a past time).
  const remind = form.remind.checked && due > new Date();
  if (remind) {
    const reminder = await apiJson("/reminders", {
      method: "POST",
      body: JSON.stringify({ text: title, due_at: due.toISOString(), entry_id: made.id, priority: "normal", recurring: "none" }),
    });
    back.push([`/reminders/${reminder.id}`, "DELETE"]);
    again.push([`/reminders/${reminder.id}/restore`, "POST"]);
  }
  await refreshEntries([made.id]).catch(() => {});
  pushRoutePairUndo(remind ? "Added an event and its reminder" : "Added an event", back, again, async () => {
    timelineCal.url = "";
    paintTimeline();
    loadReminders();
  });
  return title;
}
