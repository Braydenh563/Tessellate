// utility-tools.js: the small tools the palette runs (UI_MODERNISATION_PLAN
// "Deepened 2026-10-10: utilities", rows 2 to 4; Brief 89; INBOX 1551).
//
// Lazy (`LAZY_MODULES.utilities`), reached from the palette's rows through
// the stand-ins in app.js: **the Clock** (`openClockPanel`: a movable panel
// with Timer, Stopwatch and Alarm tabs over the clocks below; the "/" rows,
// the palette's rows and a press on the status bar's `#status-timer` chip all
// open it), the counts of a selection in any editor (`textCounts`, held to
// `wc` by tests/test_text_utilities.py), and a template from Settings,
// Templates put in at the caret. The dashboard's Focus timer was the seed; it
// stays the widget's own ring, and reads these clocks on a line under it.

//: Every clock that is running or paused: {id, kind, name, start, end, paused?,
//: laps?}. A timer is its end time and nothing else (audit 1029 X14):
//: remaining is the end minus the clock, so a throttled tab reads true, several
//: can run, and the list is kept in `prefs` so a reload gets them back
//: (`utilityRestore`). `paused` is the milliseconds a timer had left or a
//: stopwatch had counted when it was paused (INBOX 1551); `laps` are the
//: stopwatch's elapsed milliseconds at each lap. The one store: the panel, the
//: chip and the dashboard line all read this list.
const utilityClocks = [];
const utilityTick = { on: false, end: 0 };

function utilityTimeText(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

//: Seconds left (a timer) or gone (a stopwatch), from the clock; a paused one
//: reads what it held.
function utilityClockSeconds(clock) {
  const now = Date.now();
  if (clock.kind === "timer") return Math.max(0, Math.ceil((clock.paused ?? clock.end - now) / 1000));
  return Math.floor((clock.paused ?? now - clock.start) / 1000);
}

//: The key is also what asks for this module at boot (spaces-find.js), so it stays, empty, while the
//: lock screen's list is on (INBOX 1553).
function utilitySave() {
  if (utilityClocks.length) prefs.set("utility-clocks", JSON.stringify(utilityClocks));
  else if (utilityOps.lockOn()) prefs.set("utility-clocks", "[]");
  else prefs.remove("utility-clocks");
}

//: The one on the bar: the running timer that ends first, then a running
//: stopwatch, then a paused clock.
function utilityShown() {
  const rank = (c) => (c.paused != null ? 2 : c.kind === "timer" ? 0 : 1);
  const end = (c) => (rank(c) === 0 ? c.end : 0);
  return [...utilityClocks].sort((x, y) => rank(x) - rank(y) || end(x) - end(y))[0];
}

function paintUtilityChip() {
  //: Behind the lock screen, or before the session is proven, a timer that ran out waits and speaks after the unlock (INBOX 1553).
  const due = utilityOps.open() ? utilityClocks.filter((c) => c.kind === "timer" && c.paused == null && c.end <= Date.now()) : [];
  for (const clock of due) utilityTimerDone(clock);
  const chip = $("status-timer");
  const clock = utilityShown();
  utilityTick.panel?.();
  utilityOps.summary();
  if (!clock) {
    chip.classList.add("hidden");
    return;
  }
  const time = utilityTimeText(utilityClockSeconds(clock));
  setLabel(chip, `ph:timer ${time}`);
  const noun = utilityClocks.every((c) => c.kind === "timer") ? "timers" : "clocks";
  const more = utilityClocks.length > 1 ? `, ${utilityClocks.length} ${noun} running` : "";
  const held = clock.paused != null ? ", paused" : "";
  const what = (clock.kind === "timer" ? `${clock.name} timer, ${time} left` : `Stopwatch, ${time}`) + held + more;
  chip.title = `${what}. Press to open the clock`;
  chip.setAttribute("aria-label", `${what}. Open the clock`);
  chip.classList.remove("hidden");
}

function utilityClockRun(kind, name, seconds = 0) {
  const start = Date.now();
  let n = utilityClocks.length;
  while (utilityClocks.some((c) => c.id === `${start}-${n}`)) n++;
  const clock = { id: `${start}-${n}`, kind, name, start, end: start + seconds * 1000 };
  if (kind === "timer") clock.len = seconds * 1000;
  utilityClocks.push(clock);
  utilityOps.changed();
  return clock;
}

//: A second's tick while any clock is on the bar, on the shared `secondTick`
//: (prefs.js, L-world-class-15 and 93), removed the moment none is.
function utilityEnsureTick() {
  if (utilityClocks.length && !utilityTick.on) {
    utilityTick.on = true;
    secondTick.add(paintUtilityChip);
  }
  if (!utilityClocks.length && utilityTick.on) {
    utilityTick.on = false;
    secondTick.remove(paintUtilityChip);
  }
  //: A one-shot at the soonest end: a hidden tab runs the interval about
  //: once a minute after a while, so "Time is up" came up to a minute late;
  //: a lone timeout is not throttled that hard (audit 1030 Y6). A paused timer has no end.
  clearTimeout(utilityTick.end);
  const next = Math.min(...utilityClocks.filter((c) => c.kind === "timer" && c.paused == null).map((c) => c.end));
  if (Number.isFinite(next)) utilityTick.end = setTimeout(paintUtilityChip, Math.max(0, next - Date.now()) + 50);
}

function utilityDrop(clock) {
  utilityClocks.splice(utilityClocks.indexOf(clock), 1);
  utilitySave();
  utilityEnsureTick();
}

//: What was running when the page last closed. A timer that ran out in the
//: meantime is announced now; one bad entry never blocks the rest.
function utilityRestore() {
  for (const c of prefs.json("utility-clocks", [])) {
    const ok = c && (c.kind === "timer" || c.kind === "stopwatch") && Number.isFinite(c.start) && Number.isFinite(c.end);
    if (!ok || utilityClocks.some((x) => x.id === String(c.id))) continue;
    const back = { id: String(c.id), kind: c.kind, name: String(c.name), start: c.start, end: c.end };
    if (Number.isFinite(c.paused)) back.paused = c.paused;
    if (Number.isFinite(c.len)) back.len = c.len;
    const laps = Array.isArray(c.laps) ? c.laps.filter(Number.isFinite) : [];
    if (laps.length) back.laps = laps;
    utilityClocks.push(back);
  }
  utilityEnsureTick();
  paintUtilityChip();
}

//: A timer of `minutes` (to a day), put on the list; the Clock panel shows it.
function startUtilityTimer(minutes = 25) {
  const span = Math.min(24 * 60, Math.max(1 / 60, Number(minutes) || 25));
  askNotificationPermission();
  return utilityClockRun("timer", utilityOps.minutesName(span), Math.round(span * 60));
}

function startStopwatch() {
  return utilityClockRun("stopwatch", "Stopwatch");
}

//: Removes a clock (the one the bar shows when none is named) and offers it
//: back with the time it had: a stray press no longer costs a 25-minute focus
//: timer (audit 1031 Z2). The removed clock is restored from what it had left
//: (a timer) or had counted (a stopwatch), so the minutes spent deciding are not
//: counted.
function stopUtilityClock(clock = utilityShown()) {
  if (!clock) return;
  const seconds = utilityClockSeconds(clock);
  const time = utilityTimeText(seconds);
  utilityDrop(clock);
  paintUtilityChip();
  const message = clock.kind === "timer" ? `Timer stopped with ${time} left.` : `Stopwatch stopped at ${time}.`;
  offerUndo(clock.kind === "timer" ? "Stop timer" : "Stop stopwatch", message, () => utilityResume(clock, seconds), () => {
    const live = utilityClocks.find((c) => c.id === clock.id);
    if (live) utilityDrop(live);
    paintUtilityChip();
  });
}

//: A stopped clock back on the list, from the seconds it showed (a paused one as it was).
function utilityResume(clock, seconds) {
  const now = Date.now();
  const back = clock.paused != null ? { ...clock } : clock.kind === "timer" ? { ...clock, end: now + seconds * 1000 } : { ...clock, start: now - seconds * 1000 };
  if (utilityClocks.some((c) => c.id === clock.id)) return;
  utilityClocks.push(back);
  utilityOps.changed();
}

function utilityTimerDone(clock) {
  utilityDrop(clock);
  toast(`Time is up: the ${clock.name} timer has finished.`);
  notify("Tessellate", `Time is up: the ${clock.name} timer has finished.`);
  //: The chime itself catches a missing Web Audio; this catches a page where the dashboard's file is not in.
  if (utilityOps.soundOn()) {
    try {
      focusChime();
    } catch {
      // The message and the notification say it.
    }
  }
}

//: **The clock's helpers, in one object** (tests/test_global_scope_ratchet.py counts every top-level
//: name): pause and play, laps, a typed length, the alarm, the sound pref and the dashboard's line.
const utilityOps = (() => {
  //: A lap's time, with the tenth that a whole second would hide.
  function lapText(ms) {
    return `${utilityTimeText(Math.floor(ms / 1000))}.${Math.floor((ms % 1000) / 100)}`;
  }

  //: One line for the dashboard's Focus timer widget (`#focus-clocks-text`):
  //: what is running now, from the same clocks.
  function clocksLine() {
    if (!utilityClocks.length) return "No clock running";
    const clock = utilityShown();
    const time = utilityTimeText(utilityClockSeconds(clock));
    const what = clock.kind === "timer" ? `${clock.name} timer ${time}` : `Stopwatch ${time}`;
    const paused = utilityClocks.filter((c) => c.paused != null).length;
    const many = utilityClocks.length > 1 ? `${utilityClocks.length} clocks running, next ${what}` : `1 clock running, ${what}`;
    return paused ? `${many} (${paused} paused)` : many;
  }

  function summary() {
    const line = document.getElementById?.("focus-clocks-text");
    if (line) line.textContent = clocksLine();
    paintLock();
  }

  //: **Behind the lock screen** (INBOX 1553). `covered`: the lock card is up (one borrowed for a
  //: password prompt is not). `open`: not covered, and the session is proven (the preferences are
  //: in; a token left from before a restart is stale, and `/auth/status` is still on its way at
  //: boot while the card is hidden), or 20 s have passed with no card to say otherwise.
  function covered() {
    const lock = $("lock-overlay");
    return Boolean(lock) && !lock.classList.contains("hidden") && lock.dataset.mode !== "prompt";
  }

  function open() {
    return !covered() && (Boolean(prefsCache) || performance.now() > 2e4);
  }

  //: Settings, Account: off unless the person turned it on, kept on this device.
  const noticesOn = () => prefs.get("lock-notices", null) === "on";

  //: What the lock card may list: each timer by name and time left, then up to five reminders by
  //: title and time, kept from the last time the notebook was open (`lockSave`). Never a note's text.
  function lockRows() {
    if (!noticesOn()) return [];
    const now = Date.now();
    const timers = utilityClocks
      .filter((c) => c.kind === "timer")
      .map((c) => `${c.name} timer, ${c.paused == null && c.end <= now ? "time is up" : `${utilityTimeText(utilityClockSeconds(c))} left${c.paused == null ? "" : ", paused"}`}`);
    const when = { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", ...clockOptions() };
    return [...timers, ...prefs.json("lock-digest", []).map((r) => `${r.t}, ${new Date(r.d).toLocaleString([], when)}`)];
  }

  //: Called with every list of open reminders the app reads. A reminder about a private note, a
  //: done one and every field but the title and the due time are left out; off keeps nothing.
  function lockSave(list) {
    if (!noticesOn()) return void prefs.remove("lock-digest");
    const rows = list.filter((r) => !r.done && !r.private).sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
    prefs.set("lock-digest", JSON.stringify(rows.slice(0, 5).map((r) => ({ t: String(r.text).slice(0, 80), d: r.due_at }))));
  }

  //: The list on the lock card, under the Unlock button; gone once the app is open or the switch is off.
  function paintLock() {
    let list = document.getElementById?.("lock-notices");
    const lines = covered() && $("lock-overlay").dataset.mode === "unlock" ? lockRows() : [];
    if (!lines.length) return list?.remove();
    if (!list) {
      list = document.createElement("ul");
      list.id = "lock-notices";
      list.className = "lock-notices muted";
      list.setAttribute("aria-label", "Timers and reminders");
      document.getElementById("lock-forgot").after(list);
    }
    list.replaceChildren(...lines.map((line) => Object.assign(document.createElement("li"), { textContent: line })));
  }

  //: The switch was just changed in Settings: read the reminders once now, or forget them.
  function lockRefresh() {
    if (noticesOn()) apiJson("/reminders?include_done=false", { silent: true }).then(lockSave).catch(() => {});
    else lockSave([]);
    utilitySave();
  }

  //: Two eager functions take one more step each from here, so the boot scripts carry none of it
  //: (the gzip cap): every list of open reminders is kept for the lock card, and the card is drawn
  //: whenever the lock screen is raised. It comes down with the next tick, or with the overlay's `hidden`.
  for (const [name, step] of [["paintReminderList", lockSave], ["showLockScreen", paintLock]]) {
    const was = window[name];
    if (was) {
      window[name] = (...args) => {
        const result = was(...args);
        step(...args);
        return result;
      };
    }
  }
  window.lockNotices = { save: lockSave, rows: lockRows, paint: paintLock, refresh: lockRefresh };

  //: After any change to the list: saved, the tick re-armed, every view repainted.
  function changed() {
    utilitySave();
    utilityEnsureTick();
    paintUtilityChip();
  }

  //: Pause holds what was left or counted; play moves the end or the start so the
  //: held time is kept and the time paused is not counted.
  function pause(clock) {
    if (clock.paused != null) return;
    const now = Date.now();
    clock.paused = clock.kind === "timer" ? Math.max(0, clock.end - now) : now - clock.start;
    changed();
  }

  function play(clock) {
    if (clock.paused == null) return;
    const now = Date.now();
    if (clock.kind === "timer") clock.end = now + clock.paused;
    else clock.start = now - clock.paused;
    delete clock.paused;
    changed();
  }

  //: Back to zero (a stopwatch, its laps cleared) or to the length it was set to (a timer), held there until Resume.
  function reset(clock) {
    delete clock.laps;
    clock.paused = clock.kind === "timer" ? clock.len ?? clock.end - clock.start : 0;
    changed();
  }

  function lap(clock) {
    if (clock.kind !== "stopwatch") return;
    if (!clock.laps) clock.laps = [];
    clock.laps.push(clock.paused ?? Date.now() - clock.start);
    changed();
  }

  //: A length typed in the Timer tab, in minutes: "10", "10m", "90s", "2h",
  //: "1h30m", "1:30" (minutes and seconds) or "1:02:03"; null when it is not one.
  function parseLength(text) {
    const t = String(text ?? "").trim().toLowerCase();
    let minutes = null;
    const hms = t.match(/^(\d+):(\d{2}):(\d{2})$/);
    const ms = t.match(/^(\d+):(\d{2})$/);
    if (hms) minutes = Number(hms[1]) * 60 + Number(hms[2]) + Number(hms[3]) / 60;
    else if (ms) minutes = Number(ms[1]) + Number(ms[2]) / 60;
    else if (/^\d+(?:\.\d+)?$/.test(t)) minutes = Number(t);
    else {
      const part = (unit) => `(?:(\\d+(?:\\.\\d+)?)\\s*(?:${unit}))?\\s*`;
      const words = t.match(new RegExp(`^${part("h|hrs?|hours?")}${part("m|mins?|minutes?")}${part("s|secs?|seconds?")}$`));
      if (words && (words[1] || words[2] || words[3])) minutes = Number(words[1] || 0) * 60 + Number(words[2] || 0) + Number(words[3] || 0) / 60;
    }
    return Number.isFinite(minutes) && minutes > 0 ? minutes : null;
  }

  //: The sound is the dashboard's chime (`focusChime`), on unless turned off in the Timer tab.
  function soundOn() {
    return prefs.json("utility-sound", 1) !== 0;
  }

  //: The local "YYYY-MM-DDTHH:MM" for an alarm at `hhmm` ("07:30"): today when it
  //: is still ahead, else tomorrow; null for no time. It is what `addReminder` takes.
  function alarmValue(hhmm) {
    const match = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm || "").trim());
    if (!match) return null;
    const at = new Date(Date.now());
    at.setHours(Number(match[1]), Number(match[2]), 0, 0);
    if (at.getTime() <= Date.now()) at.setDate(at.getDate() + 1);
    const pad = (n) => String(n).padStart(2, "0");
    return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
  }

  //: An alarm is a reminder at that time (`addReminder`, shell-reminders.js: the
  //: reminders API, its Undo, the bell and the system notification when due).
  async function alarmSet(hhmm, label) {
    const value = alarmValue(hhmm);
    if (!value) return null;
    const made = await addReminder(label || "Alarm", value);
    return made ? value : null;
  }

  function minutesName(minutes) {
    if (minutes < 1) return `${Math.round(minutes * 60)} second`;
    if (minutes % 60 === 0) return `${minutes / 60} hour`;
    return `${Math.round(minutes * 10) / 10} minute`;
  }

  //: The Dashboard's Focus timer widget gets one line from the same list the status
  //: bar reads, and a button into the Clock panel; `summary` repaints it each second.
  function focusRow(body) {
    if (!body.isConnected || body.querySelector("#focus-clocks")) return;
    const row = document.createElement("div");
    row.id = "focus-clocks";
    row.className = "row focus-clocks";
    const text = document.createElement("span");
    text.id = "focus-clocks-text";
    text.className = "muted focus-clocks-text";
    text.textContent = clocksLine();
    row.append(text, smallButton("ph:timer Clock", "Open the Clock: timers, a stopwatch and an alarm", () => openClockPanel("timer")));
    body.appendChild(row);
  }

  return { open, lockOn: noticesOn, focusRow, minutesName, lapText, clocksLine, summary, changed, pause, play, reset, lap, parseLength, soundOn, alarmValue, alarmSet };
})();

//: A press is a way into the panel (pause, lap, reset and stop are there), never a stop (INBOX 1551).
$("status-timer").addEventListener("click", () => openClockPanel(utilityShown()?.kind === "stopwatch" ? "stopwatch" : "timer"));
//: A page that closes with a clock running gets it back when this loads (spaces-find.js asks for the module at boot).
utilityRestore();

//: The text a palette command acts on: what was selected when the palette
//: opened (`paletteCaught`, app-palette.js), else the whole of the editor
//: that had the focus.
function utilitySelectedText({ target, selection, start, end }) {
  if (target && typeof target.value === "string" && end > start) return { text: target.value.slice(start, end), whole: false };
  if (selection) return { text: selection, whole: false };
  if (target && typeof target.value === "string") return { text: target.value, whole: true };
  if (target?.isContentEditable) return { text: target.innerText, whole: true };
  return { text: "", whole: true };
}

function countSelection(caught) {
  const { text, whole } = utilitySelectedText(caught);
  if (!text.trim()) {
    toast("Select some text in an editor, then count it from the palette.");
    return;
  }
  const { words, chars, read } = textCounts(text);
  const noSpaces = text.replace(/\s/g, "").length;
  const what = whole ? "This editor" : "The selection";
  toast(`${what}: ${words.toLocaleString()} word${words === 1 ? "" : "s"}, ${chars.toLocaleString()} characters (${noSpaces.toLocaleString()} without spaces), ${read || "nothing to read"}.`);
}

//: A template's text (`noteTemplateForUse`: its date, time and clipboard
//: filled) goes in where the caret was when the palette opened: a text box
//: through `setRangeText` and an `input` event (so its draft, count and
//: rendering follow), a rich editor through the browser's own insert at the
//: range it held. With no editor in hand it goes at the end of Capture.
async function insertTemplate(template, caught) {
  const { text } = await noteTemplateForUse(template);
  let { target, start, end, range } = caught;
  if (!target?.isContentEditable && typeof target?.setRangeText !== "function") {
    await switchTab("notes");
    showNotesSection("capture");
    target = $("entry-content");
    start = end = target.value.length;
  }
  target.focus();
  if (target.isContentEditable) {
    if (range) {
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    document.execCommand("insertText", false, text);
  } else {
    target.setRangeText(text, start ?? target.selectionStart, end ?? target.selectionEnd, "end");
    target.dispatchEvent(new Event("input", { bubbles: true }));
  }
  toast(`Inserted the ${template.name} template.`);
}

// --- The Clock panel (INBOX 1551, the owner: "is there a timer/stopwatch/alarm window") ---
//
//: **One window for the clocks.** `openClockPanel(tab)` is a modeless
//: `openSheet` (the Guide's recipe: no scrim, the app stays usable), so
//: `panelMovable` drags, resizes, docks and minimises it, with the tab strip of
//: the calculator (`tabs-line popup-kinds`) over Timer, Stopwatch and Alarm.
//: The list under the tabs is every clock in `utilityClocks` (the status bar's
//: store, so there is no second one): each row has the time, Pause or Resume,
//: Lap (a stopwatch) and Stop, and is repainted in place by `paintClockPanel`
//: on the bar's one-second tick, so a focused button keeps its focus. The "/"
//: rows, the palette's rows and a press on the status bar's chip all land here.
//: **Wrapped, so its names stay out of the shared scope** (tests/test_global_scope_ratchet.py):
//: the panel exports `openClockPanel` and hangs `paintClockPanel` on `utilityTick.panel`.
(() => {
  const CLOCK_PRESETS = [5, 10, 15, 25, 45];
  const CLOCK_TABS = [["timer", "Timer"], ["stopwatch", "Stopwatch"], ["alarm", "Alarm"]];
  const CLOCK_HELP = [
    "Timer: press a length or type one (10, 90s, 1h30m or 1:30). Several can run at once, and each has its own Pause and Stop in the list. A timer that runs out says so in a message, a notification and a chime (Sound at the end turns the chime off).",
    "Stopwatch: Start counts up, Lap writes down the time so far, Pause holds it and Resume carries on without the time paused. Reset puts a stopwatch or a timer back to its start.",
    "Alarm: a reminder at a time, today or tomorrow. It is an ordinary reminder, so it rings as one does and shows in Reminders and on the Dashboard.",
    "Whatever is running also shows on the status bar. Press it to come back here. They are kept when the page reloads.",
  ];
  //: Every drawn Clock: the popup and any dashboard widget (INBOX 1558), each with its own tab strip and list over the one `utilityClocks` store.
  const clockMounts = new Set();
  const clockPanel = { sheet: null, made: 0 };

  function openClockPanel(tab = "timer") {
    if (document.querySelector('[data-sheet="clock"]')) {
      clockPanel.sheet?.select(tab);
      return;
    }
    openSheet({
      label: "Clock",
      name: "clock",
      variant: "corner",
      modal: false,
      build: (card) => clockPanelBuild(card, tab),
      onClose: () => {
        clockMounts.delete(clockPanel.sheet);
        clockPanel.sheet = null;
      },
    });
  }

  function clockEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text) el.textContent = text;
    return el;
  }

  //: An icon-only button's name, as its title and its accessible name (WCAG 2.5.3).
  function clockName(button, words) {
    button.title = words;
    button.setAttribute("aria-label", words);
  }

  function clockField(labelText, input, id) {
    const label = clockEl("label", "clock-field");
    label.append(clockEl("span", "muted", labelText), input);
    input.id = id;
    return label;
  }

  function clockTimerPane() {
    const pane = clockEl("div", "clock-pane");
    const presets = clockEl("div", "row clock-presets");
    presets.setAttribute("role", "group");
    presets.setAttribute("aria-label", "Start a timer of");
    for (const minutes of CLOCK_PRESETS) presets.append(smallButton(`${minutes} min`, `Start a ${minutes} minute timer`, () => startUtilityTimer(minutes)));
    const form = clockEl("form", "row field-row clock-length");
    const input = clockEl("input");
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = "10, 90s, 1h30m, 1:30";
    input.setAttribute("aria-label", "A length for the timer");
    input.dataset.clockFocus = "timer";
    const note = clockEl("p", "muted clock-note");
    note.setAttribute("role", "status");
    const start = smallButton("ph:play Start", "Start a timer of the typed length", () => {}, false);
    start.type = "submit";
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const minutes = utilityOps.parseLength(input.value);
      note.textContent = minutes ? "" : "Type a length such as 10, 90s, 1h30m or 1:30.";
      if (!minutes) return;
      startUtilityTimer(minutes);
      input.value = "";
    });
    form.append(input, start);
    const sound = clockEl("label", "check-row clock-sound");
    const box = clockEl("input");
    box.type = "checkbox";
    box.checked = utilityOps.soundOn();
    box.addEventListener("change", () => prefs.set("utility-sound", box.checked ? "1" : "0"));
    sound.append(box, clockEl("span", "", "Sound at the end"));
    pane.append(presets, form, note, sound);
    return pane;
  }

  function clockStopwatchPane() {
    const pane = clockEl("div", "clock-pane");
    const start = smallButton("ph:play Start a stopwatch", "Start a stopwatch", () => startStopwatch(), false);
    start.dataset.clockFocus = "stopwatch";
    pane.append(start, clockEl("p", "muted clock-note", "Lap, Pause, Reset and Stop are on its row below."));
    return pane;
  }

  function clockAlarmPane() {
    const pane = clockEl("form", "clock-pane clock-alarm");
    const time = clockEl("input");
    time.type = "time";
    time.required = true;
    time.dataset.clockFocus = "alarm";
    const label = clockEl("input");
    label.type = "text";
    label.maxLength = 200;
    label.autocomplete = "off";
    label.placeholder = "Alarm";
    const note = clockEl("p", "muted clock-note");
    note.setAttribute("role", "status");
    const set = smallButton("ph:alarm Set alarm", "Set a reminder at this time", () => {}, false);
    set.type = "submit";
    const seeReminders = smallButton("ph:bell Open Reminders", "Open the Reminders tab", () => switchTab("reminders"));
    seeReminders.classList.add("hidden");
    pane.addEventListener("submit", async (event) => {
      event.preventDefault();
      const value = utilityOps.alarmValue(time.value);
      if (!value) {
        note.textContent = "Pick a time for the alarm.";
        return;
      }
      try {
        const done = await utilityOps.alarmSet(time.value, label.value.trim());
        if (!done) return;
        const tomorrow = new Date(value).getDate() !== new Date(Date.now()).getDate();
        note.textContent = `Alarm set for ${time.value}${tomorrow ? " tomorrow" : ""}. It is a reminder.`;
        seeReminders.classList.remove("hidden");
        label.value = "";
      } catch (error) {
        note.textContent = error.message || "Couldn't set that alarm.";
      }
    });
    const actions = clockEl("div", "row");
    actions.append(set, seeReminders);
    pane.append(clockField("Time", time, "clock-alarm-time"), clockField("Label (optional)", label, "clock-alarm-label"), actions, note);
    return pane;
  }

  //: Draws the Clock into `card` (the popup's card, or a widget's body when `inline`). Ids carry the view's number so two can be on screen.
  //: `only` draws one tab's pane with no strip (the Stopwatch and Alarm widgets, INBOX 1617); a stopwatch's list holds stopwatches only, an alarm's none (an alarm is a reminder).
  function clockPanelBuild(card, tab, { inline = false, only = false } = {}) {
    const n = ++clockPanel.made;
    const view = { select: null, list: null, empty: null, rows: new Map(), wasHere: false, kinds: only ? (tab === "stopwatch" ? ["stopwatch"] : []) : null };
    clockMounts.add(view);
    if (inline) card.classList.add("clock-inline");
    else {
      card.classList.add("clock-card");
      clockPanel.sheet = view;
    }
    const strip = clockEl("div", "tabs-line popup-kinds clock-tabs");
    strip.setAttribute("role", "tablist");
    strip.setAttribute("aria-label", "Clock tools");
    const made = { timer: clockTimerPane, stopwatch: clockStopwatchPane, alarm: clockAlarmPane };
    const panes = Object.fromEntries(Object.entries(made).filter(([key]) => !only || key === tab).map(([key, build]) => [key, build()]));
    const tabs = CLOCK_TABS.filter(([key]) => !only || key === tab).map(([key, words]) => {
      const button = clockEl("button", "", words);
      button.type = "button";
      button.setAttribute("role", "tab");
      button.dataset.tab = key;
      button.id = `clock-tab-${n}-${key}`;
      button.setAttribute("aria-controls", `clock-panel-${n}-${key}`);
      panes[key].setAttribute("role", "tabpanel");
      panes[key].id = `clock-panel-${n}-${key}`;
      panes[key].setAttribute("aria-labelledby", button.id);
      button.addEventListener("click", () => select(button.dataset.tab));
      return button;
    });
    const select = (key, { focus = true } = {}) => {
      if (!panes[key]) key = "timer";
      for (const button of tabs) {
        const on = button.dataset.tab === key;
        button.setAttribute("aria-selected", String(on));
        button.classList.toggle("active", on);
        button.tabIndex = on ? 0 : -1;
      }
      for (const [name, pane] of Object.entries(panes)) pane.classList.toggle("hidden", name !== key);
      if (focus) panes[key].querySelector("[data-clock-focus]")?.focus();
    };
    view.select = select;
    strip.addEventListener("keydown", (event) => {
      const at = tabs.indexOf(document.activeElement);
      const to = { ArrowRight: (at + 1) % tabs.length, ArrowLeft: (at + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
      if (at < 0 || to === undefined) return;
      event.preventDefault();
      select(tabs[to].dataset.tab, { focus: false });
      tabs[to].focus();
    });
    strip.append(...tabs);
    if (only) {
      card.classList.add("clock-only");
      const pane = panes[tab];
      pane.removeAttribute("aria-labelledby");
      pane.setAttribute("role", "group");
      pane.setAttribute("aria-label", tab === "alarm" ? "Alarm" : "Stopwatch");
    }
    const running = clockEl("div", "clock-running");
    const heading = clockEl("h3", "muted clock-heading", "Running");
    view.empty = clockEl("p", "muted clock-empty", only ? "No stopwatch is running. Press Start above." : "Nothing is running. Start a timer or a stopwatch above.");
    view.list = clockEl("ul", "clock-list");
    view.list.setAttribute("aria-label", "Running clocks");
    running.append(heading, view.empty, view.list);
    card.append(...(only ? [] : [strip]), ...Object.values(panes), ...(only && tab === "alarm" ? [] : [running]));
    select(tab, { focus: false });
    paintClockPanel();
    //: A widget is drawn with the page and takes no focus. The popup does, after `openSheet` has attached the card and made its own focus pass (a microtask, not a frame).
    if (inline) return;
    clockPanelHelp(card);
    Promise.resolve().then(() => {
      select(tab);
      paintClockPanel();
    });
  }

  //: The head's '?' (DESIGN.md `data-help-for`): what each tab does, behind the title.
  function clockPanelHelp(card) {
    const head = card.querySelector(".sheet-head");
    if (!head) return;
    const help = clockEl("button", "icon-only ghost small dialog-head-btn");
    help.type = "button";
    help.setAttribute("data-help-for", "clock-help");
    help.setAttribute("aria-controls", "clock-help");
    help.setAttribute("aria-expanded", "false");
    clockName(help, "About the Clock");
    const icon = clockEl("i", "ph ph-question");
    icon.setAttribute("aria-hidden", "true");
    help.append(icon);
    const group = clockEl("span", "dialog-head-actions");
    const closeButton = head.querySelector(".sheet-close");
    if (closeButton) group.append(closeButton);
    head.querySelector(".sheet-title")?.after(help);
    head.append(group);
    const body = clockEl("div", "help-body hidden");
    body.id = "clock-help";
    body.setAttribute("role", "dialog");
    body.setAttribute("aria-label", "About the Clock");
    for (const line of CLOCK_HELP) body.append(clockEl("p", "", line));
    head.after(body);
  }

  //: One row of the list. Its buttons look the clock up by id each press: an
  //: Undo after Stop puts back a new object with the same id.
  function clockRow(id) {
    const find = () => utilityClocks.find((c) => c.id === id);
    const el = clockEl("li", "clock-row");
    el.dataset.clock = id;
    const top = clockEl("div", "row clock-row-top");
    const name = clockEl("span", "clock-name");
    const time = clockEl("span", "clock-time");
    time.setAttribute("role", "timer");
    const toggle = smallButton("ph:pause", "Pause", () => {
      const clock = find();
      if (!clock) return;
      if (clock.paused != null) utilityOps.play(clock);
      else utilityOps.pause(clock);
    });
    const lap = smallButton("ph:flag", "Lap", () => {
      const clock = find();
      if (clock) utilityOps.lap(clock);
    });
    const reset = smallButton("ph:arrow-counter-clockwise", "Reset", () => {
      const clock = find();
      if (clock) utilityOps.reset(clock);
    });
    const stop = smallButton("ph:stop", "Stop", () => stopUtilityClock(find()));
    top.append(name, time, toggle, lap, reset, stop);
    const laps = clockEl("ol", "clock-laps muted");
    el.append(top, laps);
    return { el, name, time, toggle, lap, reset, stop, laps };
  }

  function clockRowPaint(row, clock, label) {
    const paused = clock.paused != null;
    row.name.textContent = label;
    const text = utilityTimeText(utilityClockSeconds(clock));
    if (row.time.textContent !== text) row.time.textContent = text;
    row.el.classList.toggle("is-paused", paused);
    const words = paused ? "Resume" : "Pause";
    if (row.toggle.title !== `${words} ${label}`) {
      setLabel(row.toggle, paused ? "ph:play" : "ph:pause");
      clockName(row.toggle, `${words} ${label}`);
    }
    clockName(row.reset, `Reset ${label}`);
    clockName(row.stop, `Stop ${label}`);
    clockName(row.lap, `Lap ${label}`);
    const isWatch = clock.kind === "stopwatch";
    row.lap.classList.toggle("hidden", !isWatch);
    //: A stopwatch's laps area holds its full height from the start (INBOX 1651): the card is anchored to the window's foot, so a list that grew with each lap lifted the Lap button away from the pointer.
    row.laps.classList.toggle("clock-laps-held", isWatch);
    const laps = clock.laps || [];
    if (row.laps.children.length !== laps.length) {
      //: Newest first, each with the time it took since the one before.
      row.laps.replaceChildren(...laps.map((at, i) => clockEl("li", "", `Lap ${i + 1}: ${utilityOps.lapText(at)}, +${utilityOps.lapText(at - (laps[i - 1] || 0))}`)).reverse());
      row.laps.classList.toggle("hidden", !laps.length && !isWatch);
    }
  }

  //: Repaints every drawn Clock's list from `utilityClocks`, in place (called from `paintClockViews`). A view whose card was on the page and left it is dropped.
  function paintClockPanel() {
    const total = utilityClocks.filter((c) => c.kind === "stopwatch").length;
    for (const view of clockMounts) {
      const list = view.list;
      if (!list?.isConnected) {
        if (view.wasHere) clockMounts.delete(view);
        continue;
      }
      view.wasHere = true;
      const seen = new Set();
      let stopwatches = 0;
      for (const clock of utilityClocks) {
        if (view.kinds && !view.kinds.includes(clock.kind)) continue;
        let row = view.rows.get(clock.id);
        if (!row) {
          row = clockRow(clock.id);
          view.rows.set(clock.id, row);
          list.append(row.el);
        }
        if (clock.kind === "stopwatch") stopwatches++;
        clockRowPaint(row, clock, clock.kind === "timer" ? `${clock.name} timer` : total > 1 ? `Stopwatch ${stopwatches}` : "Stopwatch");
        seen.add(clock.id);
      }
      for (const [id, row] of view.rows) {
        if (seen.has(id)) continue;
        row.el.remove();
        view.rows.delete(id);
      }
      view.empty.classList.toggle("hidden", seen.size > 0);
    }
  }

  //: A dashboard widget's body (INBOX 1558): the same Clock drawn into it, inline, through the popup's own build.
  openClockPanel.inline = (tab, host, { only = false } = {}) => clockPanelBuild(host, tab, { inline: true, only });
  window.openClockPanel = openClockPanel;
  utilityTick.panel = paintClockPanel;
})();
