// utility-tools.js: the small tools the palette runs (UI_MODERNISATION_PLAN
// "Deepened 2026-10-10: utilities", rows 2 to 4; Brief 89).
//
// Lazy (`LAZY_MODULES.utilities`), reached from the palette's rows through
// the stand-ins in app.js: a timer and a stopwatch on the status bar's
// `#status-timer` chip (pressing it stops them, a timer that runs out says so
// in a toast and a notification), the counts of a selection in any editor
// (`textCounts`, held to `wc` by tests/test_text_utilities.py), and a
// template from Settings, Templates put in at the caret. The dashboard's
// Focus timer was the seed; it stays the widget's own, this one is the
// palette's and the bar's.

//: Every clock that is running: {id, kind, name, start, end}. A timer is its
//: end time and nothing else (audit 1029 X14): remaining is the end minus the
//: clock, so a throttled tab reads true, several can run, and the list is
//: kept in `prefs` so a reload gets them back (`utilityRestore`).
const utilityClocks = [];
let utilityTick = 0;

function utilityTimeText(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

//: Seconds left (a timer) or gone (a stopwatch), from the clock.
function utilityClockSeconds(clock) {
  const now = Date.now();
  if (clock.kind === "timer") return Math.max(0, Math.ceil((clock.end - now) / 1000));
  return Math.floor((now - clock.start) / 1000);
}

function utilitySave() {
  if (utilityClocks.length) prefs.set("utility-clocks", JSON.stringify(utilityClocks));
  else prefs.remove("utility-clocks");
}

//: The one on the bar: the timer that ends first, else the stopwatch.
function utilityShown() {
  const end = (c) => (c.kind === "timer" ? c.end : Infinity);
  return [...utilityClocks].sort((x, y) => end(x) - end(y))[0];
}

function paintUtilityChip() {
  for (const clock of utilityClocks.filter((c) => c.kind === "timer" && c.end <= Date.now())) utilityTimerDone(clock);
  const chip = $("status-timer");
  const clock = utilityShown();
  if (!clock) {
    chip.classList.add("hidden");
    return;
  }
  const time = utilityTimeText(utilityClockSeconds(clock));
  setLabel(chip, `ph:stop-circle ${time}`);
  const more = utilityClocks.length > 1 ? `, ${utilityClocks.length} timers running` : "";
  const what = (clock.kind === "timer" ? `${clock.name} timer, ${time} left` : `Stopwatch, ${time}`) + more;
  chip.title = `${what}. Press to stop`;
  chip.setAttribute("aria-label", `${what}. Stop`);
  chip.classList.remove("hidden");
}

function utilityClockRun(kind, name, seconds = 0) {
  if (kind === "stopwatch") utilityClocks.splice(0, utilityClocks.length, ...utilityClocks.filter((c) => c.kind !== kind));
  const start = Date.now();
  utilityClocks.push({ id: `${start}-${utilityClocks.length}`, kind, name, start, end: start + seconds * 1000 });
  utilitySave();
  utilityEnsureTick();
  paintUtilityChip();
}

//: The one wake source here: a second's tick while any clock is on the bar,
//: cleared the moment none is (tests/wake_sources_seed.json).
function utilityEnsureTick() {
  if (utilityClocks.length && !utilityTick) utilityTick = setInterval(paintUtilityChip, 1000);
  if (!utilityClocks.length && utilityTick) {
    clearInterval(utilityTick);
    utilityTick = 0;
  }
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
    if (ok && !utilityClocks.some((x) => x.id === String(c.id))) utilityClocks.push({ id: String(c.id), kind: c.kind, name: String(c.name), start: c.start, end: c.end });
  }
  utilityEnsureTick();
  paintUtilityChip();
}

function utilityMinutesName(minutes) {
  if (minutes < 1) return `${Math.round(minutes * 60)} second`;
  if (minutes % 60 === 0) return `${minutes / 60} hour`;
  return `${Math.round(minutes * 10) / 10} minute`;
}

function startUtilityTimer(minutes = 25) {
  const span = Math.min(24 * 60, Math.max(1 / 60, Number(minutes) || 25));
  askNotificationPermission();
  const name = utilityMinutesName(span);
  utilityClockRun("timer", name, Math.round(span * 60));
  toast(`Timer started: ${name}${/^1 /.test(name) ? "" : "s"}. Press it on the status bar to stop.`);
}

function startStopwatch() {
  utilityClockRun("stopwatch", "Stopwatch");
  toast("Stopwatch started. Press it on the status bar to stop.");
}

//: Stops the one the bar shows.
function stopUtilityClock() {
  const clock = utilityShown();
  if (!clock) return;
  const time = utilityTimeText(utilityClockSeconds(clock));
  utilityDrop(clock);
  paintUtilityChip();
  toast(clock.kind === "timer" ? `Timer stopped with ${time} left.` : `Stopwatch stopped at ${time}.`);
}

function utilityTimerDone(clock) {
  utilityDrop(clock);
  toast(`Time is up: the ${clock.name} timer has finished.`);
  notify("Tessellate", `Time is up: the ${clock.name} timer has finished.`);
}

$("status-timer").addEventListener("click", stopUtilityClock);
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
