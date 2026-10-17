// timeline-calendar.js: the Timeline's third view, the calendar (TIMELINE_PLAN
// section 9, Phase 5; WORLD_CLASS_PLAN 25, decision 47). Loaded by
// `timelineCalendarCall` in timeline.js the first time the view is chosen, so
// the boot scripts carry none of it.
//
// One calendar (decision 19): the reminders tab's Calendar button opens this
// view filtered to reminders, and the month grid that tab used to draw went.
// The rows are the feed's (decision 2): the same `/timeline` endpoint, read
// for the period on screen, mapped by `timelineRow` and filtered by
// `timelineVisibleRows`, so the feed, the table and the calendar cannot
// disagree about what a day holds or what a search matched.
//
// What sits on a day (decision 15): reminders and meetings as rows at their
// time, the day's page as the cell's head, everything else as dots, so a month
// stays readable at a thousand notes. A cell holds three rows and a "+n"
// (decision 14). Month at 1024 and up, week (hour rows) at 768 and up, below
// that the month as an agenda, which is the feed's own rows.

lazyScript("/css/timeline-calendar-lazy.css");

//: Timed rows a month cell shows beside its dots when it is too short for
//: note chips (`timelineCalFit`); an hour cell shows two, or one and "+n"
//: (its height is two lines).
const TIMELINE_CAL_ROWS = 3;
//: Note chips built for one cell at most; the rest are the "+n".
const TIMELINE_CAL_NOTE_CHIPS = 24;
const TIMELINE_CAL_HOUR_ROWS = 2;
//: Dots drawn before the count says the rest.
const TIMELINE_CAL_DOTS = 6;
//: Pages of 1,000 read for one period at most: a month of 5,000 notes is
//: five, and past ten the dots are a count of what arrived.
const TIMELINE_CAL_PAGES = 10;
//: Where the week's hour rows open: the working day, not midnight.
const TIMELINE_CAL_FIRST_HOUR = 8;
const TIMELINE_CAL_SPANS = ["month", "week", "day"];
const TIMELINE_CAL_SPAN_STORE = "timeline-cal-span";
const TIMELINE_CAL_DRAG = "application/x-memorymap-calendar";
//: Long enough for a double click, short enough that one press still feels
//: like it opened the day.
const TIMELINE_CAL_DOUBLE_MS = 250;

const timelineCal = {
  span: TIMELINE_CAL_SPANS.includes(prefs.get(TIMELINE_CAL_SPAN_STORE, "")) ? prefs.get(TIMELINE_CAL_SPAN_STORE, "") : "month",
  focus: timelineBucketKey(new Date(), "day"),
  url: "",
  rows: [],
  more: false,
  //: The reminders tab's door: a filter on top of the feed's kinds, shown as
  //: a removable chip and never stored.
  only: null,
  drag: null,
  //: A press on a day waits this long for a second one (a double click adds).
  pickTimer: 0,
  painted: "",
  renders: 0,
};

const TIMELINE_CAL_MONTH = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });
const TIMELINE_CAL_LONG = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const TIMELINE_CAL_SHORT = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const TIMELINE_CAL_TIME = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const TIMELINE_CAL_HOUR = new Intl.DateTimeFormat(undefined, { hour: "numeric" });

function timelineCalDate(key) {
  return new Date(`${key}T00:00:00`);
}

//: The span drawn at this width (decision 14): the month needs 1024, the
//: hour rows 768, and below that the period reads as an agenda.
function timelineCalSpan() {
  if (!window.matchMedia("(min-width: 768px)").matches) return "agenda";
  if (timelineCal.span === "month" && !window.matchMedia("(min-width: 1024px)").matches) return "week";
  return timelineCal.span;
}

//: The first and last day of the period holding `key`. Weeks start on
//: Monday, as the feed's week buckets do (`timelineBucketKey`).
function timelineCalRange(span, key) {
  if (span === "day") return [key, key];
  if (span === "week") {
    const first = timelineBucketKey(timelineCalDate(key), "week");
    return [first, timelineDayShift(first, 6)];
  }
  const first = `${key.slice(0, 7)}-01`;
  const start = timelineCalDate(first);
  const days = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate();
  return [first, timelineDayShift(first, days - 1)];
}

//: The feed's own query for a window: its grouping and kinds, the range
//: as the UTC instants of the local days' edges (rows are stored in UTC).
function timelineCalUrl(first, last) {
  const utc = (key, time) => new Date(`${key}T${time}`).toISOString().slice(0, 19);
  const kinds = timelineCal.only ? [timelineCal.only] : timelineKindChoice();
  const kind = kinds.length < TIMELINE_KINDS.length ? `&kind=${kinds.join(",")}` : "";
  return `/timeline?scale=day&group=${$("timeline-group").value}&start=${utc(first, "00:00:00")}`
    + `&end=${utc(last, "23:59:59")}&tz=${-new Date().getTimezoneOffset()}&limit=1000&also=true${kind}`;
}

async function timelineCalFetch(url) {
  await loadMapBoardIndex();
  const rows = [];
  let cursor = null;
  let more = false;
  for (let page = 0; page < TIMELINE_CAL_PAGES; page += 1) {
    const body = await apiJson(cursor ? `${url}&cursor=${encodeURIComponent(cursor)}` : url);
    rows.push(...(body.rows || []).map(timelineRow));
    cursor = body.next_cursor;
    more = Boolean(cursor);
    if (!cursor) break;
  }
  return { rows, more };
}

//: What each day holds (decision 15), by the local day the row sits on.
function timelineCalDays(rows) {
  const days = new Map();
  for (const row of rows) {
    const key = timelineBucketKey(row.when, "day");
    if (!days.has(key)) days.set(key, { rows: [], items: [], dots: [], page: null });
    const day = days.get(key);
    day.rows.push(row);
    //: A note that names a clock ("the dentist on 2026-10-20 at 3pm") sits on its hour.
    if (row.kind === "reminder" || row.placedBy === "meeting" || (row.placedBy === "mentioned" && !row.allDay)) day.items.push(row);
    else if (!day.page && timelineIsDailyNote(row)) day.page = row;
    else day.dots.push(row);
  }
  //: A note that names more than one day sits on the first and shows an "also
  //: on" chip on each other (decision 23): a ghost of the row, not a second row.
  for (const row of rows) {
    for (const key of row.alsoOn || []) {
      if (!days.has(key)) days.set(key, { rows: [], items: [], dots: [], page: null });
      const day = days.get(key);
      const ghost = { ...row, key: `${row.key}@${key}`, also: true, when: timelineCalDate(key), allDay: true };
      day.rows.push(ghost);
      day.dots.push(ghost);
    }
  }
  //: An event's own reminder (the add sheet's "Remind me at the start") is
  //: the event's chip, said in its title, not a second chip saying the same.
  for (const day of days.values()) {
    const events = new Map(day.items.filter((r) => r.placedBy === "meeting").map((r) => [`${r.id}@${+r.when}`, r]));
    day.items = day.items.filter((row) => {
      const event = row.kind === "reminder" && events.get(`${row.entryId}@${+row.when}`);
      if (event) event.reminded = true;
      return !event;
    });
    day.items.sort((a, b) => a.when - b.when);
  }
  return days;
}

//: The view's paint, from `paintTimeline`. A period not yet read is read
//: once; a search, a filter or a change of span is a repaint of what is
//: here. `renders` drops an answer that arrives after a later paint.
async function paintTimelineCalendar() {
  const box = $("timeline-calendar");
  const span = timelineCalSpan();
  const [first, last] = timelineCalRange(span === "agenda" ? "month" : span, timelineCal.focus);
  const url = timelineCalUrl(first, last);
  const render = ++timelineCal.renders;
  const pressed = document.activeElement?.closest?.("#timeline-calendar [data-cal-act]");
  if (pressed) box.dataset.refocusAct = pressed.dataset.calAct;
  if (url !== timelineCal.url) {
    timelineCalMount(box, timelineCalHead(span, first));
    //: The head is already mounted, so `showSkeletons(box)` saw a non-empty
    //: box and drew nothing (owner, 2026-10-12: no loading state). The
    //: placeholder is the Timeline list's own five rows, in a holder of its own.
    const loading = document.createElement("div");
    loading.className = "timeline-cal-loading";
    box.appendChild(loading);
    showSkeletons(loading, 5);
    let read = null;
    try {
      read = await timelineCalFetch(url);
    } catch {
      read = null;
    }
    if (render !== timelineCal.renders) return;
    loading.remove();
    if (!read) {
      timelineCal.url = "";
      surfaceFailed($("timeline-empty"), "calendar", paintTimelineCalendar);
      return;
    }
    surfaceRecovered($("timeline-empty"));
    timelineCal.url = url;
    timelineCal.rows = read.rows;
    timelineCal.more = read.more;
  }
  timelineCalDraw(box, span, first, last);
}

function timelineCalDraw(box, span, first, last) {
  const all = timelineVisibleRows(timelineCal.rows);
  const days = timelineCalDays(all);
  //: A row whose first day is outside the window came in for a later day it names.
  const rows = all.filter((row) => {
    const key = timelineBucketKey(row.when, "day");
    return key >= first && key <= last;
  });
  const ghosts = [...days.entries()].reduce((n, [key, day]) => n + (key >= first && key <= last ? day.rows.filter((r) => r.also).length : 0), 0);
  const head = timelineCalHead(span, first);
  const feed = $("timeline-feed");
  feed.classList.toggle("hidden", span !== "agenda");
  if (span === "agenda") {
    timelineCalMount(box, head);
    paintTimelineFeed([...rows].sort((a, b) => b.when - a.when));
  } else {
    feed.replaceChildren();
    const grid = span === "month" ? timelineCalMonth(first, last, days) : timelineCalWeek(first, last, days, span);
    timelineCalMount(box, head, grid);
    timelineCalFit(grid);
  }
  const period = span === "day" ? TIMELINE_CAL_LONG.format(timelineCalDate(first))
    : span === "week" ? `${TIMELINE_CAL_SHORT.format(timelineCalDate(first))} to ${TIMELINE_CAL_SHORT.format(timelineCalDate(last))}`
      : TIMELINE_CAL_MONTH.format(timelineCalDate(first));
  const shown = rows.length + ghosts;
  $("timeline-count").textContent = `${shown}${timelineCal.more ? "+" : ""} item${shown === 1 ? "" : "s"} · ${period}`;
  //: The hour rows open on the working day the first time a week is drawn,
  //: not at midnight; a repaint keeps where the reader scrolled to.
  const drawn = `${span}:${first}`;
  if (span !== "month" && span !== "agenda" && timelineCal.painted !== drawn) {
    const hour = box.querySelector(`.timeline-cal-hourlabel[data-cal-hour="${TIMELINE_CAL_FIRST_HOUR}"]`);
    const pane = box.querySelector(".timeline-cal-hours");
    if (hour && pane) pane.scrollTop += hour.getBoundingClientRect().top - pane.getBoundingClientRect().top;
  }
  timelineCal.painted = drawn;
  timelineCalRefocus(box);
}

//: A repaint rebuilds every button, so the focus is put back where it was:
//: on the head's control that was pressed, or on the day.
function timelineCalRefocus(box) {
  const act = box.dataset.refocusAct;
  const day = box.dataset.refocus;
  const moved = box.dataset.refocusKey;
  delete box.dataset.refocusAct;
  delete box.dataset.refocus;
  delete box.dataset.refocusKey;
  if (moved && box.querySelector(`[data-cal-key="${moved}"]`)) return box.querySelector(`[data-cal-key="${moved}"]`).focus({ preventScroll: true });
  //: `preventScroll`: the week has just been scrolled to its working hours.
  if (act) box.querySelector(`[data-cal-act="${act}"]`)?.focus({ preventScroll: true });
  else if (day) box.querySelector(`.timeline-cal-stop[data-cal-day="${timelineCal.focus}"]`)?.focus({ preventScroll: true });
}

//: The period's own row: earlier, its name, later, the reminders chip when
//: the reminders tab sent the reader here, and the span.
function timelineCalMount(box, head, grid) {
  for (const child of [...box.children]) if (child !== head) child.remove();
  if (box.firstChild !== head) box.prepend(head);
  if (grid) box.appendChild(grid);
}

function timelineCalHead(span, first) {
  //: One head for good, with its span strip never lifted out: moving an element
  //: cancels its running animation, which is the strip's glide.
  const head = timelineCal.headEl || (timelineCal.headEl = Object.assign(document.createElement("div"), { className: "timeline-cal-head" }));
  const seg = span === "agenda" ? null : timelineCalSpanSeg(span);
  for (const child of [...head.children]) if (child !== seg) child.remove();
  const unit = span === "agenda" ? "month" : span;
  const step = (delta) => smallButton(
    delta < 0 ? "ph:caret-left" : "ph:caret-right",
    `${delta < 0 ? "Earlier" : "Later"} ${unit}`,
    () => timelineCalMove(delta, unit)
  );
  const back = step(-1);
  const on = step(1);
  back.classList.add("icon-only");
  on.classList.add("icon-only");
  back.setAttribute("aria-label", `Earlier ${unit}`);
  on.setAttribute("aria-label", `Later ${unit}`);
  const title = document.createElement("h3");
  title.className = "timeline-cal-title";
  title.setAttribute("role", "status");
  title.textContent = span === "day" ? TIMELINE_CAL_LONG.format(timelineCalDate(first)) : TIMELINE_CAL_MONTH.format(timelineCalDate(first));
  //: Today is the dock's own button (and T), not a second one here.
  back.dataset.calAct = "earlier";
  on.dataset.calAct = "later";
  head.prepend(back, title, on);
  //: The way in without a double click (a touch screen, the agenda).
  const add = smallButton("ph:plus Add", "Add a reminder or an event on the chosen day (or double-click a day, or press N)", () => timelineCalAdd(timelineCal.focus));
  add.classList.add("timeline-cal-add");
  add.dataset.calAct = "add";
  seg ? seg.before(add) : head.appendChild(add);
  if (timelineCal.only) {
    const only = smallButton("ph:x Show: reminders", "Show every kind again", () => {
      timelineCal.only = null;
      paintTimeline();
    }, false);
    only.className = "library-chip active timeline-cal-only";
    only.dataset.calAct = "only";
    add.before(only);
  }
  if (seg && seg.parentNode !== head) head.appendChild(seg);
  return head;
}

//: The strip is kept between paints and only its buttons' state changes: a
//: strip built afresh each paint has no earlier position for `glideStrip`
//: (shell-reminders.js) to slide from, so the choice jumped (the owner,
//: 2026-10-11). Month is left out below 1024, so the kept strip is rebuilt
//: when the set of options differs.
function timelineCalSpanSeg(span) {
  const wide = window.matchMedia("(min-width: 1024px)").matches;
  const names = TIMELINE_CAL_SPANS.filter((name) => wide || name !== "month");
  let seg = timelineCal.spanSeg;
  if (!seg || seg.dataset.spans !== names.join()) {
    seg = document.createElement("div");
    seg.className = "seg seg-compact timeline-cal-span";
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Month, week or day");
    seg.dataset.spans = names.join();
    for (const name of names) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.calSpan = name;
      button.textContent = name[0].toUpperCase() + name.slice(1);
      seg.appendChild(button);
    }
    timelineCal.spanSeg = seg;
  }
  for (const button of seg.children) {
    const pressed = button.dataset.calSpan === span;
    button.classList.toggle("active", pressed);
    button.setAttribute("aria-pressed", String(pressed));
  }
  return seg;
}

//: One label a screen reader hears for a day: the date, then what it holds.
function timelineCalDayLabel(key, day) {
  const parts = [TIMELINE_CAL_LONG.format(timelineCalDate(key))];
  if (day?.page) parts.push("has a day page");
  if (day?.items.length) parts.push(`${day.items.length} at a time`);
  if (day?.dots.length) parts.push(`${day.dots.length} written`);
  return parts.join(", ");
}

function timelineCalMonth(first, last, days) {
  const grid = document.createElement("div");
  grid.className = "timeline-cal-month";
  grid.setAttribute("role", "group");
  grid.setAttribute("aria-label", TIMELINE_CAL_MONTH.format(timelineCalDate(first)));
  //: 2024-01-01 was a Monday: weekday names in the reader's language.
  for (let i = 0; i < 7; i += 1) {
    const name = document.createElement("span");
    name.className = "timeline-cal-dow";
    name.setAttribute("aria-hidden", "true");
    name.textContent = new Date(2024, 0, 1 + i).toLocaleDateString(undefined, { weekday: "short" });
    grid.appendChild(name);
  }
  for (let i = (timelineCalDate(first).getDay() + 6) % 7; i > 0; i -= 1) {
    const pad = document.createElement("span");
    pad.className = "timeline-cal-pad";
    grid.appendChild(pad);
  }
  const focus = timelineCalStop(first, last);
  for (let key = first; key <= last; key = timelineDayShift(key, 1)) {
    grid.appendChild(timelineCalCell(key, days.get(key), key === focus, "month"));
  }
  return grid;
}

//: The one day in the period that holds the tab stop: the focused day when
//: it is on screen, else today, else the first.
function timelineCalStop(first, last) {
  const today = timelineBucketKey(new Date(), "day");
  if (timelineCal.focus >= first && timelineCal.focus <= last) return timelineCal.focus;
  return today >= first && today <= last ? today : first;
}

//: One day's box. `place` is "month" (a month cell, the period's tab stop),
//: "allday" (the week's all-day row, its tab stop) or an hour of the week.
function timelineCalCell(key, day, stop, place) {
  const cell = document.createElement("div");
  cell.className = "timeline-cal-cell";
  cell.dataset.calDay = key;
  const today = timelineBucketKey(new Date(), "day");
  cell.classList.toggle("is-today", key === today);
  cell.classList.toggle("is-past", key < today);
  const hourly = typeof place === "number";
  if (hourly) {
    cell.dataset.calHour = String(place);
    cell.classList.add("timeline-cal-hourcell");
  } else {
    cell.classList.add("timeline-cal-stop", `timeline-cal-${place}cell`);
    cell.setAttribute("role", "group");
    cell.tabIndex = stop ? 0 : -1;
    cell.setAttribute("aria-label", `${timelineCalDayLabel(key, day)}, press Enter to open the day`);
    cell.appendChild(timelineCalCellHead(key, day, stop, place === "month"));
  }
  const all = day ? day.items : [];
  if (!hourly) return timelineCalFill(cell, key, day, all, place, stop);
  const items = all.filter((row) => timelineCalTimed(row) && row.when.getHours() === place);
  //: An hour's two lines hold two rows, or one and "+n".
  const shown = items.length <= TIMELINE_CAL_HOUR_ROWS ? items : items.slice(0, TIMELINE_CAL_HOUR_ROWS - 1);
  for (const row of shown) cell.appendChild(timelineCalItem(row, stop));
  if (items.length > shown.length) cell.appendChild(timelineCalMore(key, items.length - shown.length, stop));
  return cell;
}

function timelineCalMore(key, count, stop) {
  const more = smallButton(`+${count} more`, `Everything on ${TIMELINE_CAL_LONG.format(timelineCalDate(key))}, in the feed`, () => timelineCalOpenDay(key));
  more.classList.add("timeline-cal-more");
  more.tabIndex = stop ? 0 : -1;
  return more;
}

//: A month cell or the all-day row: the day's timed rows, then what was
//: written as chips with titles (the owner, 2026-10-11: "items show only as
//: dots"). How many fit is measured once the grid is in the page
//: (`timelineCalFit`); a cell too short for a chip and a "+n" falls back to
//: the dots of decision 15.
function timelineCalFill(cell, key, day, items, place, stop) {
  const shown = place === "allday" ? items.filter((row) => !timelineCalTimed(row)) : items;
  const notes = day ? day.dots : [];
  for (const row of shown) cell.appendChild(timelineCalItem(row, stop));
  for (const row of notes.slice(0, TIMELINE_CAL_NOTE_CHIPS)) cell.appendChild(timelineCalItem(row, stop));
  const more = timelineCalMore(key, 0, stop);
  more.hidden = true;
  more.dataset.extra = String(Math.max(0, notes.length - TIMELINE_CAL_NOTE_CHIPS));
  cell.appendChild(more);
  cell.dataset.count = String(day ? day.rows.length : 0);
  return cell;
}

//: How many one-line rows a month cell or all-day row has room for, then
//: shows that many chips; the last slot is "+n more" when some are left, and
//: a cell with room for no chip beside its "+n" shows dots for the notes.
//: Run after the grid is attached, because it reads the laid-out height.
function timelineCalFit(root) {
  for (const cell of root.querySelectorAll(".timeline-cal-monthcell, .timeline-cal-alldaycell")) {
    const chips = [...cell.querySelectorAll(":scope > .timeline-cal-item")];
    const more = cell.querySelector(":scope > .timeline-cal-more");
    const head = cell.querySelector(":scope > .timeline-cal-cellhead");
    if (!more || !head || !cell.clientHeight) continue;
    for (const chip of chips) chip.hidden = false;
    more.hidden = false;
    const style = getComputedStyle(cell);
    const gap = parseFloat(style.rowGap) || 0;
    const room = cell.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - head.offsetHeight - gap;
    const slots = Math.max(0, Math.floor((room + gap) / (more.offsetHeight + gap)));
    const notes = chips.filter((chip) => chip.classList.contains("is-note"));
    const extra = Number(more.dataset.extra || 0);
    const total = chips.length + extra;
    //: Chips for everything when it fits; else one slot goes to "+n".
    const dots = notes.length > 0 && slots < 2;
    let keep = total <= slots ? chips.length : slots - 1;
    if (dots) keep = Math.min(chips.length - notes.length, TIMELINE_CAL_ROWS, slots - 1);
    keep = Math.max(0, keep);
    cell.classList.toggle("is-dots", dots);
    chips.forEach((chip, i) => { chip.hidden = (dots && chip.classList.contains("is-note")) || i >= keep; });
    const left = dots ? chips.length - notes.length - keep : total - keep;
    more.hidden = left <= 0 || slots < 1;
    if (!more.hidden) more.textContent = `+${left} more`;
  }
}

//: Whether a row has a time of its own (a reminder always does; a meeting
//: or a mentioned day may be all day).
function timelineCalTimed(row) {
  return row.kind === "reminder" || !row.allDay;
}

//: The cell's head: the number, the day's page, the dots.
function timelineCalCellHead(key, day, stop, numbered) {
  const head = document.createElement("div");
  head.className = "timeline-cal-cellhead";
  if (numbered) {
    const number = document.createElement("span");
    number.className = "timeline-cal-num";
    number.textContent = String(Number(key.slice(8)));
    head.appendChild(number);
  }
  if (day?.page) {
    const page = smallButton("ph:calendar-dot Day page", "Open this day's page", () => openDayPage(key));
    page.classList.add("timeline-cal-page");
    page.tabIndex = stop ? 0 : -1;
    page.draggable = true;
    page.dataset.calKey = day.page.key;
    head.appendChild(page);
  }
  if (day?.dots.length) head.appendChild(timelineCalDots(key, day.dots.length, stop));
  return head;
}

function timelineCalDots(key, count, stop) {
  const dots = document.createElement("button");
  dots.type = "button";
  dots.className = "timeline-cal-dots";
  dots.tabIndex = stop ? 0 : -1;
  const label = `${count} written on ${TIMELINE_CAL_SHORT.format(timelineCalDate(key))}: open the day in the feed`;
  dots.title = label;
  dots.setAttribute("aria-label", label);
  for (let i = 0; i < Math.min(count, TIMELINE_CAL_DOTS); i += 1) {
    const dot = document.createElement("span");
    dot.className = "timeline-cal-dot";
    dots.appendChild(dot);
  }
  if (count > TIMELINE_CAL_DOTS) {
    const more = document.createElement("span");
    more.className = "timeline-cal-dotcount";
    more.textContent = String(count);
    dots.appendChild(more);
  }
  dots.addEventListener("click", () => timelineCalOpenDay(key));
  return dots;
}

//: A row's glyph: a reminder's bell, a meeting's people, else the note's own
//: (a note that talks about the day, a document, a map, or a note).
function timelineCalGlyph(row) {
  if (row.also) return "ph:arrow-bend-down-right";
  if (row.kind === "reminder") return "ph:bell-simple";
  if (row.placedBy === "meeting") return "ph:users-three";
  if (row.kind === "document") return "ph:file-text";
  if (row.kind === "board") return "ph:graph";
  return row.placedBy === "mentioned" ? "ph:clock-countdown" : "ph:note";
}

function timelineCalItem(row, stop) {
  //: A written note's moment is when it was typed, which is not its time on the grid.
  const clocked = row.kind === "reminder" || row.placedBy === "meeting" || row.placedBy === "mentioned";
  const time = row.allDay || !clocked ? "" : TIMELINE_CAL_TIME.format(row.when);
  const item = smallButton(`${timelineCalGlyph(row)} ${time ? `${time} ` : ""}${row.title}`, row.also ? `Also on this day: ${row.title}` : `${row.title}${time ? `, ${time}` : ""}${row.reminded ? ", with a reminder" : ""}`, () => timelineCalOpenRow(row));
  item.classList.toggle("is-also", Boolean(row.also));
  const timed = row.kind === "reminder" || row.placedBy === "meeting";
  item.classList.add("timeline-cal-item", `is-${timed ? row.kind === "reminder" ? "reminder" : "meeting" : "note"}`);
  item.classList.toggle("is-done", row.done === true);
  item.dataset.calKey = row.key;
  item.tabIndex = stop ? 0 : -1;
  //: A meeting or a note drags too, so the drop can say why it stays (decision 16);
  //: an "also on" chip is not the note's row and does not.
  item.draggable = !row.also;
  return item;
}

//: The week and the day: a head per day and an all-day row that stay put,
//: then 24 hour rows in their own pane under them, as a calendar's are.
function timelineCalWeek(first, last, days, span) {
  const wrap = document.createElement("div");
  wrap.className = `timeline-cal-weekwrap is-${span}`;
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", span === "day" ? TIMELINE_CAL_LONG.format(timelineCalDate(first)) : `Week of ${TIMELINE_CAL_LONG.format(timelineCalDate(first))}`);
  const keys = [];
  for (let key = first; key <= last; key = timelineDayShift(key, 1)) keys.push(key);
  const focus = timelineCalStop(first, last);
  const top = document.createElement("div");
  top.className = "timeline-cal-week timeline-cal-weektop";
  const corner = document.createElement("span");
  corner.className = "timeline-cal-corner";
  top.appendChild(corner);
  for (const key of keys) top.appendChild(timelineCalWeekHead(key, days.get(key)));
  const allDay = document.createElement("span");
  allDay.className = "timeline-cal-hourlabel timeline-cal-allday";
  allDay.textContent = "All day";
  top.appendChild(allDay);
  for (const key of keys) top.appendChild(timelineCalCell(key, days.get(key), key === focus, "allday"));
  const hours = document.createElement("div");
  hours.className = "timeline-cal-week timeline-cal-hours";
  for (let hour = 0; hour < 24; hour += 1) {
    const label = document.createElement("span");
    label.className = "timeline-cal-hourlabel";
    label.dataset.calHour = String(hour);
    label.textContent = TIMELINE_CAL_HOUR.format(new Date(2024, 0, 1, hour));
    hours.appendChild(label);
    for (const key of keys) hours.appendChild(timelineCalCell(key, days.get(key), key === focus, hour));
  }
  wrap.append(top, hours);
  return wrap;
}

//: A week's day head opens that day; the day's own head says its date.
function timelineCalWeekHead(key, day) {
  const date = timelineCalDate(key);
  const label = `${date.toLocaleDateString(undefined, { weekday: "short" })} ${date.getDate()}`;
  const head = smallButton(label, `${timelineCalDayLabel(key, day)}: show this day`, () => {
    timelineCal.focus = key;
    timelineCalSetSpan("day");
  });
  head.classList.add("timeline-cal-dayhead");
  head.classList.toggle("is-today", key === timelineBucketKey(new Date(), "day"));
  head.tabIndex = -1;
  return head;
}

function timelineCalSetSpan(span) {
  timelineCal.span = span;
  try { prefs.set(TIMELINE_CAL_SPAN_STORE, span); } catch { /* a private window */ }
  $("timeline-calendar").dataset.refocus = "1";
  paintTimelineCalendar();
}

//: A row opens where it lives, as the feed's row actions do.
function timelineCalOpenRow(row) {
  if (row.kind === "reminder") return flashReminder(row.id);
  if (row.kind === "document") {
    switchTab("documents");
    return openDocument(row.id);
  }
  if (row.kind === "board" && row.board) return openWhiteboardBoard(row.board.id);
  switchTab("notes");
  showNotesSection("browse");
  return flashEntry(row.id);
}

//: A press or Enter or Space on a day's ground: the day in the Day view, or
//: from the Day view the day in the feed (decision 20).
function timelineCalPick(key) {
  timelineCal.focus = key;
  if (timelineCalSpan() === "day") return timelineCalOpenDay(key);
  return timelineCalSetSpan("day");
}

//: A day's "+n" and its dots: the day in the feed (decision 18).
//: The feed is scrolled to the day when its range holds it; otherwise the
//: range becomes that one day, said in the Options menu like any custom range.
function timelineCalOpenDay(key) {
  prefs.set("timeline-view", "feed");
  syncTimelineViewSeg();
  paintTimeline();
  const feed = $("timeline-feed");
  const find = () => feed.querySelector(`.timeline-bucket[data-bucket="${timelineBucketKey(timelineCalDate(key), feed.dataset.scale || "day")}"]`);
  const show = (section) => {
    const box = $("timeline-scroll");
    box.scrollTop += section.getBoundingClientRect().top - box.getBoundingClientRect().top;
    section.querySelector(".timeline-row")?.focus({ preventScroll: true });
  };
  const section = find();
  if (section) return show(section);
  $("timeline-days").value = "custom";
  $("timeline-custom-range").classList.remove("hidden");
  $("timeline-start-date").value = key;
  $("timeline-end-date").value = key;
  return renderTimeline().then(() => {
    const found = find();
    if (found) show(found);
  });
}

function timelineCalMove(delta, unit) {
  const date = timelineCalDate(timelineCal.focus);
  if (unit === "month") {
    const day = date.getDate();
    date.setDate(1);
    date.setMonth(date.getMonth() + delta);
    date.setDate(Math.min(day, new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()));
  } else {
    date.setDate(date.getDate() + delta * (unit === "week" ? 7 : 1));
  }
  timelineCal.focus = timelineBucketKey(date, "day");
  paintTimelineCalendar();
}

function timelineCalendarToday() {
  timelineCal.focus = timelineBucketKey(new Date(), "day");
  $("timeline-calendar").dataset.refocus = "1";
  paintTimelineCalendar();
}

//: A note offer's "Show on calendar" (INBOX 904 B72): this view on that day,
//: every kind shown, the span the reader last chose kept. The read is dropped:
//: the reminder was made after it, and the month's cached rows lack it.
function timelineCalendarOn(key) {
  timelineCal.url = "";
  timelineCal.only = null;
  timelineCal.focus = key;
  $("timeline-calendar").dataset.refocus = "1";
  prefs.set("timeline-view", "calendar");
  syncTimelineViewSeg();
  paintTimeline();
}

//: The reminders tab's Calendar button (decision 19): this view, reminders
//: only, on today.
function timelineCalendarReminders() {
  timelineCal.only = "reminder";
  timelineCal.focus = timelineBucketKey(new Date(), "day");
  prefs.set("timeline-view", "calendar");
  syncTimelineViewSeg();
  paintTimeline();
}

//: The keys (decision 18): T today, the arrows a day or a week, Page Up and
//: Page Down a month, Home and End the week's ends, Enter the day in the
//: feed, N the add sheet on the day. Only on a day, not inside a row.
function timelineCalKeys(event) {
  if (event.altKey && timelineCalKeyMove(event)) return;
  const cell = event.target.closest?.(".timeline-cal-stop");
  if (!cell || event.target !== cell || event.ctrlKey || event.metaKey || event.altKey) return;
  const key = cell.dataset.calDay;
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
  const date = timelineCalDate(key);
  let next = null;
  if (step) next = timelineDayShift(key, step);
  else if (event.key === "Home") next = timelineDayShift(key, -((date.getDay() + 6) % 7));
  else if (event.key === "End") next = timelineDayShift(key, 6 - ((date.getDay() + 6) % 7));
  else if (event.key === "PageUp" || event.key === "PageDown") {
    timelineCal.focus = key;
    $("timeline-calendar").dataset.refocus = "1";
    timelineCalMove(event.key === "PageUp" ? -1 : 1, "month");
  } else if (event.key === "t" || event.key === "T") timelineCalendarToday();
  else if (event.key === "Enter" || event.key === " ") timelineCalPick(key);
  else if (event.key === "n" || event.key === "N") timelineCalAdd(key);
  else return;
  event.preventDefault();
  if (next) timelineCalFocus(next);
}

//: The drag's keyboard twin (WCAG 2.2, 2.5.7): Alt and an arrow on a
//: reminder moves it a day left or right, and up or down a week in the
//: month or an hour in the week and the day, through the same move and undo.
function timelineCalKeyMove(event) {
  const item = event.target.closest?.(".timeline-cal-item.is-reminder");
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -1, ArrowDown: 1 }[event.key];
  if (!item || !step) return false;
  const row = timelineCal.rows.find((r) => r.key === item.dataset.calKey);
  if (!row) return false;
  event.preventDefault();
  $("timeline-calendar").dataset.refocusKey = row.key;
  const day = timelineBucketKey(row.when, "day");
  const across = event.key === "ArrowLeft" || event.key === "ArrowRight";
  if (across) timelineCalMoveReminder(row, timelineDayShift(day, step), null);
  else if (timelineCalSpan() === "month") timelineCalMoveReminder(row, timelineDayShift(day, 7 * step), null);
  else timelineCalMoveReminder(row, day, Math.min(23, Math.max(0, row.when.getHours() + step)));
  return true;
}

function timelineCalFocus(key) {
  timelineCal.focus = key;
  const box = $("timeline-calendar");
  const target = box.querySelector(`.timeline-cal-stop[data-cal-day="${key}"]`);
  if (!target) {
    box.dataset.refocus = "1";
    paintTimelineCalendar();
    return;
  }
  for (const stop of box.querySelectorAll(".timeline-cal-stop")) {
    const on = stop === target;
    stop.tabIndex = on ? 0 : -1;
    for (const inner of stop.querySelectorAll("button")) inner.tabIndex = on ? 0 : -1;
  }
  target.focus();
}

//: N, a double click and the head's Add: the add sheet, its own lazy file
//: (timeline-cal-add.js), since most visits to the calendar add nothing.
function timelineCalAdd(key, hour = null) {
  return lazyScript("/js/timeline-cal-add.js").then((ok) => ok && timelineCalAddOpen(key, hour));
}

// --- Drag to reschedule (decision 16) ---------------------------------------
//
// A reminder dropped on a day keeps its time of day; dropped on an hour, it
// takes the hour and keeps its minutes. A day page dropped on a day without
// one takes that day as its title. Anything else, and a time already past,
// is refused with the reason. Every move is on the undo bar.

function timelineCalDropTarget(event) {
  return event.target.closest?.("#timeline-calendar [data-cal-day]") || null;
}

function timelineCalDragStart(event) {
  const source = event.target.closest?.("[data-cal-key]");
  if (!source) return;
  timelineCal.drag = source.dataset.calKey;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(TIMELINE_CAL_DRAG, timelineCal.drag);
  event.dataTransfer.setData("text/plain", source.textContent.trim());
}

function timelineCalDragOver(event) {
  const target = timelineCalDropTarget(event);
  if (!target || !timelineCal.drag) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  const box = $("timeline-calendar");
  if (box.dataset.over === `${target.dataset.calDay}:${target.dataset.calHour || ""}`) return;
  box.querySelector(".is-drop")?.classList.remove("is-drop");
  target.classList.add("is-drop");
  box.dataset.over = `${target.dataset.calDay}:${target.dataset.calHour || ""}`;
}

function timelineCalDragEnd() {
  const box = $("timeline-calendar");
  box.querySelector(".is-drop")?.classList.remove("is-drop");
  delete box.dataset.over;
  timelineCal.drag = null;
}

async function timelineCalDrop(event) {
  const target = timelineCalDropTarget(event);
  const key = timelineCal.drag || event.dataTransfer.getData(TIMELINE_CAL_DRAG);
  timelineCalDragEnd();
  if (!target || !key) return;
  event.preventDefault();
  const row = timelineCal.rows.find((r) => r.key === key);
  if (!row) return;
  const day = target.dataset.calDay;
  const hour = target.dataset.calHour === undefined ? null : Number(target.dataset.calHour);
  if (row.kind === "reminder") return timelineCalMoveReminder(row, day, hour);
  if (timelineIsDailyNote(row) && row.kind === "note") return timelineCalMovePage(row, day);
  toast("Only a reminder or a day page moves by dragging; a meeting's date is in its note.", "info");
}

async function timelineCalMoveReminder(row, day, hour) {
  const before = new Date(row.whenIso);
  const after = timelineCalDate(day);
  after.setHours(hour === null ? row.when.getHours() : hour, row.when.getMinutes(), 0, 0);
  if (after.getTime() === row.when.getTime()) return;
  if (after < new Date()) {
    toast("A reminder moves only to a time still ahead: drop it on today or later.", "info");
    return;
  }
  const put = (due, restore) => async () => {
    await apiJson(`/reminders/${row.id}`, { method: "PUT", body: JSON.stringify({ due_at: due, restore }) });
    timelineCal.url = "";
    paintTimeline();
    loadReminders();
  };
  try {
    await put(after.toISOString(), false)();
  } catch {
    return;
  }
  const when = `${TIMELINE_CAL_SHORT.format(after)}, ${TIMELINE_CAL_TIME.format(after)}`;
  pushUndo(`Moved "${row.title}" to ${when}`, put(before.toISOString(), true), put(after.toISOString(), true));
  toast(`Moved "${row.title}" to ${when}.`);
}

//: A day page is a note titled with its day (`dailyNoteTitle`), so moving it
//: is a new first line, refused where the day already has a page.
async function timelineCalMovePage(row, day) {
  const from = timelineBucketKey(row.when, "day");
  if (from === day) return;
  if (timelineCalDays(timelineCal.rows).get(day)?.page) {
    toast("That day already has a page; open it to write there.", "info");
    return;
  }
  const retitle = (fromKey, toKey) => async () => {
    const entry = await apiJson(`/entries/${row.id}`);
    const content = String(entry.content || "").replace(fromKey, dailyNoteTitle(toKey));
    await apiJson(`/entries/${row.id}`, { method: "PUT", body: JSON.stringify({ content, base_hash: entry.content_hash }) });
    timelineCal.url = "";
    paintTimeline();
  };
  try {
    await retitle(from, day)();
  } catch {
    return;
  }
  pushUndo(`Moved the page for ${from} to ${day}`, retitle(day, from), retitle(from, day));
  toast(`The page for ${from} is now the page for ${day}.`);
}

//: Wired once, on the view's box: the cells are rebuilt on every paint and a
//: listener per cell would pile up with them.
(() => {
  const box = $("timeline-calendar");
  box.addEventListener("keydown", timelineCalKeys);
  box.addEventListener("dragstart", timelineCalDragStart);
  box.addEventListener("dragover", timelineCalDragOver);
  box.addEventListener("dragend", timelineCalDragEnd);
  box.addEventListener("drop", timelineCalDrop);
  box.addEventListener("click", (event) => {
    const span = event.target.closest?.("[data-cal-span]");
    if (span) return timelineCalSetSpan(span.dataset.calSpan);
    const cell = event.target.closest?.(".timeline-cal-stop, .timeline-cal-hourcell");
    if (!cell || event.target.closest("button")) return undefined;
    clearTimeout(timelineCal.pickTimer);
    //: A double click adds on the day, or at the hour (INBOX 904 B72).
    if (event.detail >= 2) return timelineCalAdd(cell.dataset.calDay, cell.dataset.calHour === undefined ? null : Number(cell.dataset.calHour));
    //: A press on a day's own ground opens the day (the owner, 2026-10-11:
    //: "I cant click on or interact with calender dates"), held for a double
    //: click's length so the second press adds rather than landing in the
    //: Day view the first one drew.
    if (cell.classList.contains("timeline-cal-stop") && event.detail === 1) {
      timelineCal.pickTimer = setTimeout(() => timelineCalPick(cell.dataset.calDay), TIMELINE_CAL_DOUBLE_MS);
    }
    return undefined;
  });
  //: Crossing 768 or 1024 changes the span drawn.
  for (const query of ["(min-width: 768px)", "(min-width: 1024px)"]) {
    window.matchMedia(query).addEventListener("change", () => {
      if (timelineViewMode() === "calendar") paintTimeline();
    });
  }
})();
