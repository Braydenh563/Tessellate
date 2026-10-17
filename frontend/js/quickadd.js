// quickadd.js: one grammar for every field where a dated or tagged thing is
// typed (CHAT_PLAN decision 50, Brief 66): the quick note sheet, the reminders
// box, the new meeting's title, the timeline's search and the palette.
//
// The reading is the server's (`GET /read`, ai/reading.py, decision 47); this
// file never reads language itself (tests/test_one_reader.py). It draws what
// the reading found as chips under the field, lets a chip be switched off,
// asks one question when a slot the surface needs is missing (never a guess),
// and hands the save the values the chips show, so what is saved is what the
// chips said. With no reading (the route missing, the server away) no chips
// show and every field does what it did before.
//
// Lazy (app.js `LAZY_MODULES.quickAdd`, fetched a few seconds after boot):
// the reminders box and the timeline's search are attached when it loads,
// the quick note, meeting and palette fields when they open.

const QA_ICONS = {
  date: "ph:calendar-blank",
  time: "ph:clock",
  datetime: "ph:calendar-blank",
  duration: "ph:timer",
  recurrence: "ph:repeat",
  alert: "ph:bell-ringing",
  range: "ph:calendar-dots",
  place: "ph:map-pin",
  person: "ph:user",
  tag: "ph:hash",
};
//: The kinds each surface saves: a chip is drawn only for what its save uses,
//: so no chip ever says something that is then dropped.
const QA_SURFACES = {
  reminder: ["date", "time", "datetime", "duration", "recurrence", "alert"],
  note: ["date", "time", "datetime", "duration", "recurrence", "tag"],
  meeting: ["date", "time", "datetime", "person"],
  timeline: ["date", "range"],
  palette: ["date", "time", "datetime", "duration", "recurrence", "alert", "tag", "person", "place"],
};
//: Kinds whose words leave the title when their chip is on ("dentist friday
//: 9am" is saved as "dentist"); a person or a place stays in the words.
const QA_STRIPPED = new Set(["date", "time", "datetime", "duration", "recurrence", "alert", "range"]);
const QA_JOINT_BEFORE = /\s*\b(?:on the|on|at|by|in|for|from|every|the)\s*$/i;
const QA_WHEN = new Set(["date", "time", "datetime", "duration"]);
//: Short enough that the chips land inside the 150 ms the plan sets after the
//: last key (CHAT_PLAN section 6), long enough that a word typed at speed
//: is one request rather than five.
const QA_WAIT_MS = 40;
const qaFields = new WeakMap();
//: `undefined` until a reading has been asked for; then the route that
//: answered, or `null` for this page's life when none exists (Brief 65 not
//: merged), so a missing route costs one request, not one per key.
const qaReader = { route: undefined };

function qaNow() {
  const d = new Date();
  const pad = (n) => String(Math.abs(n)).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${off < 0 ? "-" : "+"}${pad(Math.trunc(off / 60))}:${pad(off % 60)}`;
}

//: `surface`: "reminder" asks the reading to take the whole box as a
//: reminder (ai/reading.py `read(context={"surface": ...})`).
async function qaFetch(text, surface) {
  if (qaReader.route === null) return null;
  //: The route's own names (routes_read.py): `q`, the clock as
  //: `/reminders/parse` takes it, the date order from the browser's locale.
  const query = `?q=${encodeURIComponent(text)}&tz_offset_minutes=${-new Date().getTimezoneOffset()}`
    + `&now=${encodeURIComponent(qaNow())}&locale=${encodeURIComponent((navigator.language || "").slice(0, 16))}&surface=${surface}`;
  for (const route of qaReader.route ? [qaReader.route] : ["/read", "/api/v1/read"]) {
    try {
      const reading = await apiJson(route + query, { silent: true, timeoutMs: 8000 });
      if (reading && Array.isArray(reading.spans)) {
        qaReader.route = route;
        return reading;
      }
    } catch (error) {
      //: Away or slow: no chips this time, ask again on the next key.
      if (!(error?.status >= 400 && error.status < 500)) return null;
    }
  }
  if (!qaReader.route) qaReader.route = null;
  return null;
}

// --- Values: what a span's resolved value means for a save ----------------
//
// The values are the reading's, already resolved (ISO dates, 24-hour times,
// seconds); these only unpack the shapes the reading may send them in.

function qaPad(n) {
  return String(n).padStart(2, "0");
}

function qaDateTime(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return { date: value.date || null, time: value.time ? String(value.time).slice(0, 5) : null };
  }
  const s = String(value ?? "");
  //: An instant with a zone is shown and saved on this clock.
  if (/T\d{2}:\d{2}.*(Z|[+-]\d{2}:?\d{2})$/.test(s)) {
    const d = new Date(s);
    if (!Number.isNaN(d.getTime())) {
      return {
        date: `${d.getFullYear()}-${qaPad(d.getMonth() + 1)}-${qaPad(d.getDate())}`,
        time: `${qaPad(d.getHours())}:${qaPad(d.getMinutes())}`,
      };
    }
  }
  return {
    date: /^\d{4}-\d{2}-\d{2}/.exec(s)?.[0] || null,
    time: /(?:^|T)(\d{2}:\d{2})/.exec(s)?.[1] || null,
  };
}

function qaSeconds(value) {
  if (typeof value === "number") return value;
  if (value && typeof value === "object") return Number(value.seconds) || null;
  const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(String(value ?? ""));
  if (!m) return Number(value) || null;
  return (Number(m[1] || 0) * 24 * 60 + Number(m[2] || 0) * 60 + Number(m[3] || 0)) * 60 + Number(m[4] || 0) || null;
}

//: What a reminder keeps for a repeat: daily, weekly or monthly, or the rule
//: itself (every 2 weeks, weekdays, the last Friday of the month,
//: TIMELINE_PLAN 11 row 8) without its hour, which is the due time's.
//: `null` for a shape the store does not take; its chip says so.
const QA_RULE = /^FREQ=(?:DAILY|WEEKLY|MONTHLY|YEARLY)(?:;INTERVAL=\d{1,2})?(?:;BYDAY=(?:-1|[1-4])?[A-Z]{2}(?:,[A-Z]{2}){0,6})?(?:;BYMONTHDAY=\d{1,2})?$/;
function qaRecurring(value) {
  if (["daily", "weekly", "monthly"].includes(value)) return value;
  if (value && typeof value === "object") {
    const interval = Number(value.interval || 1);
    const byday = Array.isArray(value.byday) ? value.byday.join(",") : "";
    value = `FREQ=${String(value.freq || value.frequency || "").toUpperCase()}${interval > 1 ? `;INTERVAL=${interval}` : ""}${byday ? `;BYDAY=${byday}` : ""}`;
  }
  const rule = String(value ?? "").replace(/;BYHOUR=\d+|;BYMINUTE=\d+/g, "");
  const word = { "FREQ=DAILY": "daily", "FREQ=WEEKLY": "weekly", "FREQ=MONTHLY": "monthly" }[rule.replace(/;BY(?:DAY=[A-Z]{2}|MONTHDAY=\d{1,2})$/, "")];
  if (word && !/INTERVAL/.test(rule)) return word;
  return QA_RULE.test(rule) ? rule : null;
}

function qaRange(value) {
  if (!value || typeof value !== "object") return null;
  const start = qaDateTime(value.start).date;
  const end = qaDateTime(value.end).date;
  return start && end ? { start, end } : null;
}

function qaDayWords(date) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

//: What a chip stands for, as its save will carry it (`data-value`, which the
//: sweep compares with what was saved).
function qaChipValue(span) {
  if (QA_WHEN.has(span.kind) && span.kind !== "duration") {
    const dt = qaDateTime(span.value);
    return [dt.date, dt.time].filter(Boolean).join(" ");
  }
  if (span.kind === "duration") return String(qaSeconds(span.value) || "");
  if (span.kind === "recurrence") return qaRecurring(span.value) || "";
  if (span.kind === "range") {
    const range = qaRange(span.value);
    return range ? `${range.start}/${range.end}` : "";
  }
  return String(span.value || span.text).replace(/^#/, "");
}

function qaChipWords(span) {
  //: The icon already says "tag", "person" or "place": the chip is the name.
  if (["tag", "person", "place"].includes(span.kind)) return qaChipValue(span);
  if (span.read_as) return String(span.read_as);
  if (span.kind === "date") return qaDayWords(qaDateTime(span.value).date || span.text);
  return String(span.text || "");
}

// --- The field's state, the request, the chips ----------------------------

function qaKey(span) {
  return `${span.kind}:${span.start}:${span.end}`;
}

//: Attach the grammar to a field. Idempotent: a second call only refreshes
//: the options. `opts.after`: the element the chips go under (the field's
//: own row when it sits in one); `opts.onSlots(slots)`: called when the
//: reading or a chip changes; `opts.offKinds`: kinds whose chips start off
//: (a note's date is an offer of a reminder, not a reminder).
function quickAddAttach(field, surface, opts = {}) {
  if (!field || !QA_SURFACES[surface]) return null;
  let state = qaFields.get(field);
  if (state) {
    Object.assign(state.opts, opts);
    //: Words put in by code (a draft, a reopened palette) fire no input.
    if (state.text !== field.value) qaSchedule(state);
    return state;
  }
  const row = document.createElement("div");
  row.className = "qa-chips hidden";
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", "Read as");
  const ask = document.createElement("span");
  ask.className = "qa-ask hidden";
  ask.setAttribute("role", "status");
  row.appendChild(ask);
  (opts.after || field).after(row);
  state = { field, surface, opts, row, ask, text: "", reading: null, off: new Set(), on: new Set(), seq: 0, timer: 0, pending: null, asked: false };
  qaFields.set(field, state);
  field.addEventListener("input", () => qaSchedule(state));
  if (field.value.trim()) qaSchedule(state);
  return state;
}

function qaSchedule(state) {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => qaStart(state), QA_WAIT_MS);
}

function qaStart(state) {
  clearTimeout(state.timer);
  state.timer = 0;
  const pending = qaRead(state).catch(() => null).finally(() => {
    if (state.pending === pending) state.pending = null;
  });
  state.pending = pending;
  return pending;
}

async function qaRead(state) {
  const text = state.field.value;
  const seq = ++state.seq;
  const reading = text.trim() ? await qaFetch(text, state.surface) : null;
  //: A reply that came back after the next key is dropped: only the newest
  //: words decide the chips.
  if (seq !== state.seq) return state.reading;
  state.text = text;
  state.reading = reading;
  for (const k of [...state.off]) if (!reading?.spans?.some((s) => qaKey(s) === k)) state.off.delete(k);
  qaDraw(state);
  return reading;
}

function qaSpans(state) {
  const kinds = QA_SURFACES[state.surface];
  //: Rank 0 is the reading; a higher rank is another reading of the same
  //: words, which the reading's question names, never a second chip.
  const spans = (state.reading?.spans || []).filter((s) => kinds.includes(s.kind) && !s.rank);
  //: A time the reading put together from words that are not a time on
  //: their own ("friday 9") still gets its chip, so the time saved is shown.
  const due = state.reading?.slots?.due_at;
  //: Only from a number the reading took as the hour: a day alone
  //: ("review budget friday") is asked its time, never given 09:00.
  const hour = (state.reading?.spans || []).some((s) => s.kind === "number" && !s.rank);
  if (due && hour && kinds.includes("time") && qaIntent(state.reading, "remind") && !spans.some((s) => QA_WHEN.has(s.kind) && s.kind !== "date")) {
    const time = qaDateTime(due).time;
    if (time) spans.push({ kind: "time", text: time, start: -1, end: -1, value: time, read_as: time });
  }
  return spans;
}

function qaIsOn(state, span) {
  const key = qaKey(span);
  if (state.off.has(key)) return false;
  if (state.on.has(key)) return true;
  if (span.kind === "recurrence" && !qaRecurring(span.value)) return false;
  const offer = state.opts.offKinds || [];
  return !(offer.includes(span.kind) && !qaIntent(state.reading, "remind"));
}

function qaIntent(reading, word) {
  return String(reading?.intent || "").toLowerCase().includes(word);
}

function qaDraw(state) {
  const { row, ask } = state;
  for (const old of row.querySelectorAll(".qa-chip")) old.remove();
  const spans = qaSpans(state);
  for (const span of spans) {
    const on = qaIsOn(state, span);
    const cannot = span.kind === "recurrence" && !qaRecurring(span.value);
    const toggle = () => {
      const key = qaKey(span);
      const next = !qaIsOn(state, span);
      state.off.delete(key);
      state.on.delete(key);
      (next ? state.on : state.off).add(key);
      qaDraw(state);
      state.field.focus();
    };
    const el = chip(`${QA_ICONS[span.kind] || "ph:tag"} ${qaChipWords(span)}`, "tag qa-chip", cannot ? null : toggle);
    el.dataset.kind = span.kind;
    el.dataset.value = qaChipValue(span);
    el.classList.toggle("is-off", !on);
    if (!cannot) el.setAttribute("aria-pressed", String(on));
    el.title = cannot
      ? "Reminders cannot keep this repeat: this one is saved once"
      : `Read “${span.text}” as this. ${on ? "Press to leave it as words." : "Press to use it."}`;
    row.insertBefore(el, ask);
  }
  //: A question asked stays until the slot it asked for is there.
  if (state.asked && !qaMissing(state)) qaSetAsk(state, "");
  row.classList.toggle("hidden", !spans.length && ask.classList.contains("hidden"));
  state.opts.onSlots?.(qaSlotsOf(state));
}

function qaSetAsk(state, words) {
  state.asked = !!words;
  state.ask.textContent = words;
  state.ask.classList.toggle("hidden", !words);
  state.row.classList.toggle("hidden", !words && !state.row.querySelector(".qa-chip"));
}

//: The values the chips say, for a save. `null` when there is no reading
//: (the caller then does what it did before quick add existed).
function qaSlotsOf(state) {
  if (!state.reading) return null;
  const slots = { title: "", date: null, time: null, seconds: null, recurring: null, alert: null, range: null, tags: [], people: [], places: [], reading: state.reading };
  const cut = [];
  for (const span of qaSpans(state)) {
    if (!qaIsOn(state, span)) continue;
    if (QA_STRIPPED.has(span.kind)) cut.push(span);
    if (span.kind === "date" || span.kind === "time" || span.kind === "datetime") {
      const dt = qaDateTime(span.value);
      slots.date = dt.date || slots.date;
      slots.time = dt.time || slots.time;
    } else if (span.kind === "duration") slots.seconds = qaSeconds(span.value);
    else if (span.kind === "recurrence") {
      slots.recurring = qaRecurring(span.value);
      //: "every day at 8am" is one span: its hour is in the rule.
      const hour = /BYHOUR=(\d+)/i.exec(String(span.value ?? ""));
      if (hour && !slots.time) slots.time = `${qaPad(hour[1])}:${qaPad(/BYMINUTE=(\d+)/i.exec(String(span.value))?.[1] || 0)}`;
    }
    else if (span.kind === "alert") slots.alert = Number(span.value) || null;
    else if (span.kind === "range") slots.range = qaRange(span.value);
    else if (span.kind === "tag") slots.tags.push(qaChipValue(span));
    else if (span.kind === "person") slots.people.push(qaChipValue(span));
    else if (span.kind === "place") slots.places.push(qaChipValue(span));
  }
  //: The reading's own slots (a reminder's `due_at`, `text`, `recurring`)
  //: put "friday" and "9" together the way the chips show them; used while
  //: no chip is pressed off, since an off chip's words are words again.
  const own = state.reading.slots || {};
  const allOn = !qaSpans(state).some((span) => !qaIsOn(state, span));
  if (allOn && own.due_at && qaIntent(state.reading, "remind") && (slots.time || slots.seconds)) {
    const dt = qaDateTime(own.due_at);
    slots.date = dt.date;
    slots.time = dt.time;
    slots.seconds = null;
  }
  if (allOn && typeof own.recurring === "string" && qaRecurring(own.recurring)) slots.recurring = qaRecurring(own.recurring);
  if (slots.date && !slots.range && state.surface === "timeline") slots.range = { start: slots.date, end: slots.date };
  //: The words with the read spans taken out, end first so the offsets
  //: stay true; the reading's own title when it gives one.
  //: A joining word left hanging where a span was cut ("pay rent on the",
  //: "dentist at") goes with it; the span is the reading's, the joint is
  //: only tidied.
  //: Overlapping spans ("every friday" and "friday at 4pm") are cut as one.
  const runs = [];
  for (const span of cut.filter((x) => x.start >= 0).sort((x, y) => x.start - y.start)) {
    const last = runs[runs.length - 1];
    if (last && span.start <= last.end) last.end = Math.max(last.end, span.end);
    else runs.push({ start: span.start, end: span.end });
  }
  let rest = state.text;
  for (const run of runs.reverse()) {
    const before = rest.slice(0, run.start).replace(QA_JOINT_BEFORE, "");
    rest = `${before} ${rest.slice(run.end)}`;
  }
  const given = allOn && qaIntent(state.reading, "remind") ? own.text : null;
  slots.title = typeof given === "string" && given.trim() ? given.trim() : rest.replace(/\s+/g, " ").replace(/^[\s,.;:-]+|[\s,.;:-]+$/g, "");
  slots.due = qaDue(slots);
  return slots;
}

function qaDue(slots) {
  if (slots.date && slots.time) return new Date(`${slots.date}T${slots.time}:00`);
  if (slots.seconds && !slots.date && !slots.time) return new Date(Date.now() + slots.seconds * 1000);
  return null;
}

//: The one question a surface asks when what it needs is missing.
function qaMissing(state) {
  const slots = qaSlotsOf(state);
  if (!slots || state.surface !== "reminder") return "";
  //: Unsure (two readings of the same words): asked once, then Enter takes
  //: the chips as shown.
  if (slots.due) return state.reading.band === "unsure" && state.reading.question && !state.answered ? state.reading.question : "";
  if (state.reading.question && !slots.date && !slots.time) return state.reading.question;
  if (slots.date) return `What time on ${qaDayWords(slots.date)}?`;
  if (slots.time) return `Which day, at ${slots.time}?`;
  return "Remind you when? Add a day or a time, like “friday 9am”.";
}

//: The values the chips say once the newest words have been read, or `null`
//: with no reading. Awaits a request still in flight, so an Enter pressed
//: straight after a key saves what that key made.
async function quickAddSlots(field) {
  const state = qaFields.get(field);
  if (!state) return null;
  if (state.timer) qaStart(state);
  if (state.pending) await state.pending;
  if (state.text !== field.value) await qaStart(state);
  return qaSlotsOf(state);
}

//: Asks the surface's one question when a slot is missing; answers whether
//: it asked, so the save stops there and nothing is guessed.
function quickAddAsk(field) {
  const state = qaFields.get(field);
  if (!state?.reading) return false;
  const question = qaMissing(state);
  if (!question) return false;
  qaSetAsk(state, question);
  if (state.reading.band === "unsure" && qaSlotsOf(state).due) state.answered = true;
  return true;
}

function quickAddClear(field) {
  const state = qaFields.get(field);
  if (!state) return;
  clearTimeout(state.timer);
  state.timer = 0;
  state.seq++;
  state.text = "";
  state.reading = null;
  state.pending = null;
  state.off.clear();
  state.on.clear();
  state.answered = false;
  for (const old of state.row.querySelectorAll(".qa-chip")) old.remove();
  qaSetAsk(state, "");
}

// --- The surfaces ----------------------------------------------------------

//: The reminders box (moved from shell-reminders.js with quick add): what
//: the chips say is saved through `POST /reminders`; with no reading, the
//: old door (`/reminders/parse`: rules, then the model) as before.
async function magicAddReminder() {
  const input = $("reminder-magic");
  const status = $("reminder-magic-status");
  const text = input.value.trim();
  if (!text) return;
  status.classList.remove("error");
  quickAddAttach(input, "reminder", { after: $("reminder-magic-row") });
  const slots = await quickAddSlots(input);
  if (slots && quickAddAsk(input)) {
    status.textContent = "";
    return;
  }
  setLabel(status, "ph:spin Adding…");
  try {
    const reminder = slots
      ? await apiJson("/reminders", {
          method: "POST",
          body: JSON.stringify({ text: slots.title || text, due_at: slots.due.toISOString(), priority: "normal", recurring: slots.recurring || "none", alert_minutes: slots.alert }),
        })
      : await apiJson("/reminders/parse", {
          method: "POST",
          //: Our clock, so "tomorrow evening" is this person's evening.
          body: JSON.stringify({ text, tz_offset_minutes: -new Date().getTimezoneOffset() }),
        });
    input.value = "";
    quickAddClear(input);
    reminderMadeUndo(reminder);
    status.textContent = `Added “${reminder.text}”: ${relativeWhen(reminder.due_at)}. Edit it below if needed.`;
    askNotificationPermission();
    loadReminders();
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
  }
}

//: The timeline's search: Enter with a day or a window read turns it into
//: the timeline's own range (the From and To fields), and the box keeps the
//: rest of the words as its filter.
async function qaTimelineEnter(event) {
  if (event.key !== "Enter" || event.isComposing) return;
  const field = event.currentTarget;
  const slots = await quickAddSlots(field);
  if (!slots?.range) return;
  event.preventDefault();
  const days = $("timeline-days");
  days.value = "custom";
  days.dispatchEvent(new Event("change"));
  $("timeline-start-date").value = slots.range.start;
  $("timeline-end-date").value = slots.range.end;
  $("timeline-end-date").dispatchEvent(new Event("change"));
  field.value = slots.title;
  quickAddClear(field);
  field.dispatchEvent(new Event("input"));
}

//: The palette's first row when the reading is an act (decision 50: "remind
//: me friday 9 dentist" shows the reminder it would make, with its chips).
//: Synchronous, for `paletteMatches`; the reading arrives on its own and
//: redraws the palette.
function quickAddPaletteRow(query) {
  const field = $("palette-input");
  const state = qaFields.get(field);
  if (!state?.reading || state.text !== query) return null;
  const slots = qaSlotsOf(state);
  if (qaIntent(state.reading, "remind")) {
    const words = slots.due
      ? `${slots.due.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}, ${slots.due.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
      : "when?";
    return {
      group: "Do it",
      label: `ph:bell Remind you: ${slots.title || query.trim()} (${words})`,
      about: "Makes the reminder the chips under the box describe. A missing day or time is asked in Reminders.",
      run: () => qaPaletteRemind(query.trim(), slots),
    };
  }
  return null;
}

async function qaPaletteRemind(text, slots) {
  if (!slots.due) {
    await switchTab("reminders");
    openReminderCompose();
    const input = $("reminder-magic");
    input.value = text;
    quickAddAttach(input, "reminder", { after: $("reminder-magic-row") });
    await quickAddSlots(input);
    quickAddAsk(input);
    input.focus();
    return;
  }
  try {
    const reminder = await apiJson("/reminders", {
      method: "POST",
      body: JSON.stringify({ text: slots.title || text, due_at: slots.due.toISOString(), priority: "normal", recurring: slots.recurring || "none", alert_minutes: slots.alert }),
    });
    askNotificationPermission();
    loadReminders();
    reminderMadeUndo(reminder);
    toastAction(`Reminder set: ${relativeWhen(reminder.due_at)}.`, "Go to it", () => flashReminder(reminder.id), { go: { open: "reminder", id: reminder.id } });
  } catch (error) {
    toast(error.message || "Couldn't set the reminder.", true);
  }
}

//: **Warm-up waits for a session** (scan 2026-10-11). Asked at load, as it was,
//: it met the lock screen or the last launch's stale token on every start and
//: answered 401 into the console twice. The boot splash is down and the lock
//: overlay is hidden only once `startApp` has a live session, so that is the
//: signal; polled, not hooked, because this module loads before or after it.
function qaPrewarm(tries = 0) {
  const lock = $("lock-overlay");
  const splash = $("boot-splash");
  const live = authToken() && lock && lock.classList.contains("hidden") && (!splash || splash.classList.contains("hidden"));
  if (!live) {
    if (tries < 600) setTimeout(() => qaPrewarm(tries + 1), 1000);
    return;
  }
  qaFetch("in 5 minutes", "reminder").then(() => qaFetch("in 5 minutes", "note"));
}

(() => {
  //: The reader's first answer loads its tables (measured: over 4 s cold,
  //: and 305 ms for the first note after a reminder: the chat path's own
  //: modules); both asked now, a few seconds after boot, so the first word
  //: typed is not the one that waits.
  qaPrewarm();
  quickAddAttach($("reminder-magic"), "reminder", { after: $("reminder-magic-row") });
  const search = $("timeline-search");
  if (search) {
    quickAddAttach(search, "timeline", { after: search.closest(".search-field") || search });
    search.addEventListener("keydown", qaTimelineEnter);
  }
  const palette = $("palette-input");
  if (palette) {
    quickAddAttach(palette, "palette", {
      onSlots: () => {
        if (!$("palette-overlay").classList.contains("hidden") && typeof renderPalette === "function") renderPalette(palette.value);
      },
    });
  }
})();

// --- The note editor's offers (CHAT_PLAN section 2, the note editor row) ---
//
// A day in the text is a reminder offer, a sum written with a wrong answer is
// caught, a name another note opens with is a `[[link]]` offer, and the
// filing suggestion says why. The offers are the server's (`POST
// /read/offers`, ai/offers.py, through the one recogniser), never on quoted
// words, drawn as this file's chip row under the box once typing pauses,
// inside the 300 ms the plan sets. The new note composer is attached when
// this bundle loads, an opened note's form when it opens
// (note-edit-panels.js, guarded).

const NOTE_OFFER_ICONS = {
  reminder: "ph:bell-simple",
  sum: "ph:equals",
  link: "ph:link-simple",
  filing: "ph:folder-simple",
};
//: A pause, not a keystroke: short enough that the offers land inside the
//: 300 ms the plan sets after the last key, long enough that a word typed at
//: speed asks once.
const NOTE_OFFER_WAIT_MS = 150;
const noteOfferFields = new WeakMap();

function noteOfferKey(offer) {
  return `${offer.kind}:${offer.said}:${offer.label}`;
}

//: `opts.after`: the element the row goes after (the box, not the textarea,
//: which a live editor wraps); `opts.category`: the select a filing offer
//: sets; `opts.entryId`: the note being edited, never linked to itself.
function noteOffersAttach(field, opts = {}) {
  if (!field) return null;
  let state = noteOfferFields.get(field);
  if (state) {
    Object.assign(state.opts, opts);
    return state;
  }
  const row = document.createElement("div");
  row.className = "qa-chips note-offers hidden";
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", "Offers from what you wrote");
  const why = document.createElement("span");
  why.className = "qa-ask muted hidden";
  row.appendChild(why);
  (opts.after || field).after(row);
  state = { field, opts, row, why, seq: 0, timer: 0, done: new Set(), text: "" };
  noteOfferFields.set(field, state);
  field.addEventListener("input", () => noteOffersSchedule(state));
  if (field.value.trim()) noteOffersSchedule(state);
  return state;
}

function noteOffersSchedule(state) {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => noteOffersFetch(state), NOTE_OFFER_WAIT_MS);
}

async function noteOffersFetch(state) {
  const text = state.field.value;
  if (text === state.text) return;
  state.text = text;
  const seq = ++state.seq;
  if (!text.trim()) {
    noteOffersDraw(state, []);
    return;
  }
  let offers = [];
  try {
    const select = state.opts.category;
    const result = await apiJson("/read/offers", {
      method: "POST",
      body: JSON.stringify({
        content: text,
        entry_id: state.opts.entryId || null,
        category: select && select.value && select.value !== "__new__" ? select.value : null,
        tz_offset_minutes: -new Date().getTimezoneOffset(),
      }),
    });
    offers = result.offers || [];
  } catch {
    offers = [];
  }
  if (seq !== state.seq) return;
  noteOffersDraw(state, offers.filter((o) => !state.done.has(noteOfferKey(o))));
}

function noteOffersDraw(state, offers) {
  for (const old of state.row.querySelectorAll(".note-offer")) old.remove();
  let filingWhy = "";
  for (const offer of offers) {
    const el = chip(`${NOTE_OFFER_ICONS[offer.kind] || "ph:sparkle"} ${offer.label}`, "tag qa-chip note-offer", () => noteOfferTake(state, offer, el));
    el.title = offer.reason;
    el.dataset.kind = offer.kind;
    state.row.insertBefore(el, state.why);
    if (offer.kind === "filing") filingWhy = offer.reason;
  }
  state.why.textContent = filingWhy;
  state.why.classList.toggle("hidden", !filingWhy);
  state.row.classList.toggle("hidden", !offers.length);
  state.row.dataset.drawnAt = String(performance.now());
}

//: Words put back through the rich editor when one is mounted over the box
//: (its own history, so Ctrl+Z takes an accepted sum or link back like any
//: typing), else through `insertText` on the plain box for the same reason.
function noteOfferReplace(field, offer) {
  const { start, end } = offer;
  const said = offer.said;
  let at = start;
  if (said && field.value.slice(start, end) !== said) at = field.value.indexOf(said);
  if (at < 0) return false;
  const to = at + (said ? said.length : 0);
  const surface = noteSurfaceIfAny(field);
  if (surface) {
    surface.setRangeText(offer.value.replace, at, to, "end");
    surface.view?.focus();
    return true;
  }
  field.focus();
  field.setSelectionRange(at, to);
  if (!document.execCommand("insertText", false, offer.value.replace)) {
    field.setRangeText(offer.value.replace, at, to, "end");
    field.dispatchEvent(new Event("input", { bubbles: true }));
  }
  return true;
}

//: A taken reminder's notice opens the calendar on its day (INBOX 904 B72).
function noteOfferCalendar(dueAt) {
  switchTab("timeline");
  timelineCalendarCall("timelineCalendarOn", timelineBucketKey(new Date(dueAt), "day"));
}

async function noteOfferTake(state, offer, el) {
  state.done.add(noteOfferKey(offer));
  el.remove();
  if (!state.row.querySelector(".note-offer")) state.row.classList.add("hidden");
  if (offer.kind === "sum" || offer.kind === "link") {
    noteOfferReplace(state.field, offer);
    return;
  }
  if (offer.kind === "filing") {
    const select = state.opts.category;
    if (!select) return;
    if (![...select.options].some((o) => o.value === offer.value.category)) {
      select.insertBefore(Object.assign(document.createElement("option"), { value: offer.value.category, textContent: offer.value.category }), select.lastElementChild);
    }
    const before = select.value;
    select.value = offer.value.category;
    select.dispatchEvent(new Event("change"));
    const setTo = (value) => () => {
      select.value = value;
      select.dispatchEvent(new Event("change"));
    };
    pushUndo(`Filed in ${offer.value.category}`, setTo(before), setTo(offer.value.category));
    return;
  }
  if (offer.kind === "reminder") {
    try {
      const reminder = await apiJson("/reminders", {
        method: "POST",
        body: JSON.stringify({ text: offer.value.text, due_at: offer.value.due_at, entry_id: state.opts.entryId || null, priority: "normal", recurring: "none" }),
      });
      loadReminders();
      toastAction(`Reminder set: ${relativeWhen(reminder.due_at)}, on the timeline and the calendar.`, "Show on calendar", () => noteOfferCalendar(reminder.due_at));
      pushBinPairUndo("Reminder set", `/reminders/${reminder.id}`, `/reminders/${reminder.id}/restore`, true, loadReminders);
    } catch (error) {
      state.done.delete(noteOfferKey(offer));
      toast(`The reminder was not set: ${error.message}`, true);
    }
  }
}

noteOffersAttach($("entry-content"), {
  after: $("entry-content")?.closest(".note-composer") || $("entry-content")?.parentElement,
  category: $("entry-category"),
});
