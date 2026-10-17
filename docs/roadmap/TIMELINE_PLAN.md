# The Timeline: a full redesign of the line view and the table view

**Status: written by direct instruction ("apply the same design and plan
process to the timeline line view and see if you can redesign the timeline
table view as well"), by Fable, after the measured audit in
`scratchpad/ui-sweeps/timeline-audit*.js`. Executed after GRAPH_PLAN.md
in ROADMAP.md order; SESSION_BRIEFS.md Brief 5 is its hand-off.**

Back to [../ROADMAP.md](../ROADMAP.md).

## 1. What exists (checked in the code)

`GET /timeline?days=&scale=day|week|month|year&group=category|tag|thread|none`
(`routes_timeline.py`) returns up to `MAX_NOTES` entries newest first with a
bucket label per entry and a band per group. The tab (`#tab-timeline`,
`renderTimelineBranch` in `app.js` ~22005) draws one of two views chosen by
the hidden `#timeline-view` select behind an icon segment: a **line** view
(a d3 SVG: bands as horizontal lanes, one dot per note, axis ticks, a
hover popup with Close and Open in editor) and a **grid** view (one column
per bucket, one card per note, called "table" in the dock). The dock holds
search, the options menu (scale, group, range, custom dates), Jump to
today and help. The Phase 9 pass gave the dock one height at four widths.

## 2. Why it disappoints (measured, 48 notes across six months, 1358px)

| Measure | Line view | Grid view |
| --- | --- | --- |
| Readable text without hover | 14 text nodes for 48 notes (6 band labels, 8 ticks); no titles | titles, but 122px cards regardless of content |
| Keyboard stops on notes | 0 (SVG circles carry no tabindex) | 67, but no arrow-key order |
| Width | forced 480px minimum, overflows at 390 | 8,800px against a 1,358px viewport, 40 columns, unchanged at 1024 and 390 |
| Empty area | dot collisions 0 / 2 / 6 at 1440 / 1024 / 390 | 186 of 234 cells empty (79% of cells and of area) |
| Colour | d3 `schemeTableau10` literals, not tokens | category tokens |
| Actions from a row | Close, Open in editor | open |
| Search | dims dots, reads `d.preview` | dims cards, reads `dot.textContent` |
| Recipes in the tab | 5 font sizes, 2 card recipes, 1 popup recipe not shared with the app | |

Reading the two views against the app's own reference points: the line
view is a chart, not a timeline (a chart of when notes were written, with
no way to read one); the grid view is a spreadsheet with the axis on the
wrong side (buckets as columns push time off-screen). Neither answers the
question a timeline exists to answer: *what was I doing then, and what
came before and after it.*

## 3. The target, in one paragraph

A timeline that reads top to bottom like a journal: a vertical spine with
sticky day, week, month or year headers; each note a compact row with its
kind icon, title, one-line snippet, time, tags and space, dense when the
bucket is a month and spacious when it is a day; the same rows in a real
table when a table is what is wanted (sortable columns, sticky header, row
focus, multi-select with the Notes list's own selection bar); one search
and one filter (the dock's) that *filter* rather than dim; a scrubber
along the edge that shows the density of writing over the whole range and
jumps on click; every row reachable by keyboard and openable in place; and
on a phone, one column with the scrubber folded into the dock. Nothing in
the tab draws a colour, a font or a card that the rest of the app does not.

## 4. Decisions made (do not re-decide)

1. **The grid view is removed, not tuned.** Its shape (time as columns)
   cannot be made to read; the table view replaces it.
2. **One row model, two renderers.** `timelineRow(entry)` returns
   `{id, kind, title, snippet, when, tags, category, space, words, links,
   pinned}`; the line view and the table render from it and from nothing
   else. Search, filter, sort and selection operate on the array, so the
   two views can never disagree.
3. **The line view is DOM, not SVG.** Rows are `<li>`s inside `<section>`s
   per bucket; the spine and the sticky headers are CSS. SVG is kept only
   for the density scrubber (one path). This is what gives keyboard stops,
   text selection, ellipsis and the app's chip recipe for free.
4. **Density follows the bucket.** Day: full row (title, snippet, tags,
   time). Week: title, time, tags. Month and year: title and date only,
   two columns above 1024. The scale select stays; "auto" is added and is
   the default: the finest of day, week and month with at most 120 headers
   and, past one screen of them, a median of two items per header and at most
   60% of its calendar span empty (measured; HISTORY, "the auto scale").
5. **Bands become a filter, not lanes.** Grouping by category, tag or
   thread produced lanes that were mostly empty; the same choice now
   colours the row's kind marker and offers itself as a chip filter in the
   dock ("Show: Courses & Study"). Threads keep one affordance: a row that
   continues another shows a small link to it.
6. **The table is a `<table>`.** Sticky `<thead>`, columns date, title,
   kind, category, space, tags, words, links; click a header to sort;
   arrow keys move row focus, Enter opens, Space selects; the Notes
   selection bar (`#select-btn`'s code path) drives bulk actions. Below
   600px the table shows date and title only.
7. **The scrubber.** A 40px strip at the right edge (bottom, on a phone,
   inside the dock's "more" menu) with a density path for the whole
   loaded range and a window marker; click or drag jumps the list.
8. **Open in place.** A row's click opens the entry in the app's split
   panel (the same one Notes uses) rather than a bespoke popup; the
   bespoke popup and its media renderer are deleted.
9. **Backend.** `/timeline` gains `cursor`/`limit` (SESSION_BRIEFS Brief 6
   helper), `kind=note|document|board|reminder`, and returns `density`
   (counts per bucket for the whole range) so the scrubber needs no second
   call. `MAX_NOTES` goes; pagination replaces it.
10. **Tokens only.** Kind colours come from the category tokens the
    Library chips use; no `schemeTableau10`.
11. **Zoom is the bucket, never the page** (2026-10-05, from section 8's
    Photos note; recommendation taken). Ctrl and the wheel, or a pinch,
    steps day, week, month, year, one step per gesture; + and - on a row do
    the same for the keyboard; the focused or topmost row keeps its place.
    The step lands in the Bucket by select, so it is remembered like a
    choice made there.
12. **On this day is a time range, not a dock control** (2026-10-05, from
    section 8's Day One note; recommendation taken). The dock is at its
    seven-control ceiling and the strip under it walks days; a range is what
    the choice is. The server filters (`/timeline?on=MM-DD&tz=`), in the
    reader's own day, today left out: the Dashboard widget's rule.
13. **Date ranges as spans are not built** (EntryDate ranges in the feed):
    a feed row is one moment by decision 3, and no measured notebook here
    holds ranged notes; left until one does.

## 5. Phases

### Phase 1: the row model and the feed: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Gate green at
1440, 1024 and 390 (`scratchpad/ui-sweeps/timeline.js`).

### Phase 2: the table view: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Gate green
(`scratchpad/ui-sweeps/timelinetable.js`).

### Phase 3: the scrubber and pagination: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Gate green
against a 2,048-note seed (`scratchpad/ui-sweeps/timelinepaging.js`).

### Phase 4: kinds and the journal: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Gate green
(`scratchpad/ui-sweeps/timelinekinds.js`), with the daily note defined as a
convention rather than a store; D6's calendar strip and `Ctrl+D` are built
too (WORLD_CLASS_PLAN D6).

### Section 8's two cheap additions: **built 2026-10-05**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-10-05 (TIMELINE_PLAN,
zoom and On this day)". Decisions 11 to 13. Every phase of this plan is built.

## 6. Consistency rules

The dock stays on the Phase 8 grammar (no markup restructuring); rows use
the Notes list row tokens (`--row-h`, `--row-gap`); tags are
`.library-chip`; the row menu is the `.action-menu` recipe; the split
panel is the Notes one; keys are the app's (`/` search, arrows, Enter,
Space, Escape, `T` today). Copy: sentence case, no em-dashes, one line of
help behind the '?' popover.

## 7. Not verified until built

**Both measurements were taken on 2026-09-20** over a 2,000-note seed
(`seed-timeline-bulk.py`), and both changed what the app does. The account is
in [HISTORY.md](HISTORY.md), "Moved from the plans, 2026-09-20"; the numbers
in one line each:

- **The density strip's threshold was the wrong variable.** It hid under 200
  notes; measured with `scratchpad/ui-sweeps/timelinedensity.js`, a count
  admits a notebook the strip cannot draw (200 notes over 18 days fills 18 of
  its 120 slots: a comb, 86% of it empty or at the peak) and hides one it can
  (150 notes over 300 days fills 103 slots with a peak of 5, and reads as a
  profile). The test is now on the shape it would draw: a fifth of the slots
  carrying something, and a peak of at least four.
- **The table at 820 had no title column at all.** Measured with
  `scratchpad/ui-sweeps/timelinetable820.js`: `table-layout: fixed` plus seven
  columns in rems wanted 816px of a 704px box, so the one flexible column,
  the title, came out 0px wide and the table scrolled sideways by 112px (222px
  at 700, and at 1024 the title was 87px with all 300 titles cut off). Three
  columns now give way between 600 and 1024 (space, words, links) and the tags
  as well below 820; the title measures 375px at 1024, 176px at 820 and 242px
  at 700, with no horizontal scroll at any width.

The "auto" scale thresholds: tuned 2026-10-04 on a copy of a 2,077-note
notebook plus four synthetic shapes; the account is in
[HISTORY.md](HISTORY.md), "Moved from the plans, 2026-10-04 (the auto scale)".

## 8. Research: what the reference products do, and what it changes here

Written from working knowledge of the products, not a live teardown.

- **Apple Photos** and **Google Photos** solve "a lot of items over time"
  with a zoomable scale (years, months, days, all) and a scrubber at the
  edge showing months; density changes the tile size, not the layout.
  Implication: decisions 4 and 7 come from here; the "auto" scale should
  also respond to pinch or Ctrl+wheel.
- **Notion's timeline view** is a Gantt chart of date ranges, not a feed;
  the table view beside it is what people actually use for dated
  records. Implication: the table (decision 6) matters more than a Gantt;
  notes with date ranges (EntryDate) could later render as spans in the
  line view but that is not Phase 1 to 4.
- **Linear's activity feed, GitHub's timeline**: a vertical spine with
  sticky date headers, compact rows, kind icons on the spine. Implication:
  decision 3's shape.
- **Obsidian daily notes and the Calendar plugin**: the day is the unit;
  a heatmap of writing density per day is the overview. Implication: the
  density scrubber (decision 7) and the daily-note row (Phase 4).
- **Day One** (the journaling app closest to "what was I doing then"):
  a feed with a calendar and a "On this day" surface. Implication: an
  "On this day" chip in the dock is a cheap Phase 4 addition.

## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation.

### Bugs

- "The circle on the vertical line on the left isnt in line with the text line"
  Recommendation: align the rail circle to the first line's centre in timeline.js and the timeline CSS, measured with getBoundingClientRect against the line box. Earlier notes on this fix were not verified; measure it again. Also carried by Brief 41 (timeline.js in its file list).

### Placed from INBOX 561 (2026-10-17)

The day strip rework (543) is merged and waits on the owner's look; INBOX 904 B72 widened it into the calendar view: built 2026-10-17, HISTORY.md, "Moved from the plans, 2026-10-17 (TIMELINE B72)".

Item 561, **The owner, 2026-10-05, verbatim.** "I dont like this section in th
     timeline, it needs redesigning, restructuring, moving ro smth"
     (screenshot: the "Sep to Oct 2026" month button over a row of seven
     boxed day cells, Tue 29 to Mon 5, each its own bordered tile).
     Placed: the design agent, whose 543 rework of this strip is not merged
     yet; it is told this is still not right.
     Merged 2026-10-05 (543): the month sits between its arrows and the days
     are one well to the dock's edge, one Tab stop, arrows walk them
     (daystrip.js 44/44). Waits on the owner's look before closing.
     Owner: TIMELINE_PLAN, UI_MODERNISATION_PLAN 12 (the day strip becomes the week row); built in 543 and waiting on the owner's look, so it stays here until then.

## 9. Phase 5: the calendar as the third view (Fable, 2026-10-10; WORLD_CLASS_PLAN 25, decision 47; Brief 55)

The owner's 2026-10-10 list asks for a calendar; UI Phase 12 names a
"calendar mode". It is this plan's third view, beside the feed and the
table, from the same row model (decision 2), so the three can never
disagree.

### Decisions made (do not re-decide)

14. **Month and week grids, agenda on the phone.** Month at 1024 and up,
    week at 768 and up, the feed (already an agenda) below that. The grid
    is CSS grid, DOM cells, no SVG; a cell holds up to three rows and a
    "+n" that opens the day in the feed.
15. **What sits on the grid:** reminders (at their time), day notes (as
    the cell's head), notes by their written date (dots, not rows, so the
    grid stays readable at 5,000 notes), meetings from `routes_meetings`.
    A kind filter is the feed's own, shared.
16. **Drag reschedules a reminder;** dropping a note on a day sets its
    daily-note date only when it is a day note; anything else is refused
    with the hint. Every drop is on the undo bar (WORLD_CLASS 1.8).
17. **ICS both ways for reminders only:** export the reminders as one
    `.ics` (`routes_reminders`), import an `.ics` as reminders with a
    report; no account sync before 1.0.
18. **Keys:** `T` today, arrows move the day, `PageUp`/`PageDown` the
    month, Enter opens the day's feed, `N` a new reminder on the day.
19. **One calendar** (INBOX 768, 2026-10-10): section 9's view is the one
    grid; the reminders tab's toggle opens it filtered to reminders, and
    `renderReminderCalendar` goes.
20. **A day cell opens the day** (the owner, 2026-10-11: "I cant click on or
    interact with calender dates"): a press on a cell's own ground, Enter or
    Space opens it as the Day view, and from the Day view Enter opens the
    day in the feed (decision 18 now applies there); "+n" and the dots still
    open the feed. A cell shows its written notes as chips with titles up to
    the room its height measures (`timelineCalFit`), the last slot "+n more";
    dots are the fallback for a cell too short for a chip beside its "+n"
    (this supersedes the "dots, not rows" of decision 15 for tall cells).
21. **Dates written out are read** (the owner, 2026-10-11: "things written
    on specific dates dont show"): `timewords` reads `2026-10-25`, `16
    October 2026`, `Friday 16 October` and `Oct 3rd` as the day a note is
    about (a date without a year is the occurrence nearest the day it was
    written); a note naming a clock sits on its hour in the week and the
    day. Numeric `3/4/2026` is not read: its order is the reader's locale.
    A document has no date of its own and stays on the day it was started.
22. **No streak count, and no backfill of `done_at`** (tline-1011): the dock
    is at its grammar and `.dock-chip-row` is held at zero uses, so a streak
    has no surface; a reminder ticked before `done_at` existed has no known
    moment, so it stays in no week rather than in an invented one.
23. **A note naming two dates sits on the first and is "also on" the rest**
    (decision 2 holds: one row per note, so the feed, the table and the
    calendar cannot disagree about what a row is). `/timeline` rows carry
    `also_on` (the other days, in text order); the calendar asks with `also=true`
    and draws a quiet chip with an arrow on each of those days, which opens the
    same note and does not drag. Chosen over a row per date because a second row
    would double the note in every count and every export.
24. **The feed's range is placement, like the calendar's.** "Last N days" and an
    explicit window both keep a note by where it sits (a meeting's date, else the
    first date it mentions, else when it was written); "On this day" stays about
    when things were written. A note written today about a day long ago now sits
    in that day, not in the recent feed. Existing notes are read once by a
    background job (`entry/redate.py`, kind `redate`, resumable by cursor, done
    when `dates_read_version` reaches 2).
25. **One shape for a date with its time**: `whenText` (status.js), the reader's
    locale to the minute; the bare `toLocaleString()` (seconds on version lists,
    hovers and run logs) is gone and a test keeps it gone. 12 or 24 hours follows
    the locale; an app-level override would cost boot code for a setting every
    operating system already has.
26. **No d3 time scale for the Timeline** (VC2): the labels are
    `Intl.DateTimeFormat`, and loading the 280 KB d3 bundle to draw them would
    undo the boot diet; the row stays a vendor-use lead, not a build.
27. **No `events` table** (BACKLOG "Events as bands"): what an events table
    would hold is already on the grid as meetings (a note typed Meeting with a
    `date:`), reminders (at their time) and notes by the dates they name
    (decision 21), each filterable by kind. A fourth kind that the person
    must create separately, with a second place to record the same
    appointment, is the duplication decision 2 exists to prevent.

### Gates

| Step | Builds | Gate |
| --- | --- | --- |
| 1 to 4 | the month grid, the week and day grids and the phone agenda, reminders and day pages on the grid with drag and undo, ICS export and import | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" |

Not verified (Brief 55): the dot density at 5,000 notes in one month (the
sweep's fixture is 48 over six months; a 1,000-note month is the stress
case, read as at most ten pages of 1,000), touch drag (HTML drag and drop
has none on a phone, where the calendar is the agenda), a week grid at
1024 under a coarse pointer with hour rows full.

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC2, D3's time scale and axis for the timeline and the calendar** (M, rank 2). `timeline.js` builds its date ticks by hand (51 lines with `Date(` in 2,441); D3's time module is 75 exports with 0 called (`scaleTime`, `timeMonth`, `timeWeek`, `timeDay`, `axisBottom`, `timeFormat`). Measure: tick labels at year, month, week and day zoom match `d3.timeFormat` output for 12 fixed dates (a node test); the hand-rolled tick lines deleted; no label overlap at 390 px (`scratchpad/ui-sweeps` measure).

## 10. Deepened 2026-10-10: the timeline (Brief 72b, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72b.js` on a fresh data dir, no
model, Chromium, 96 notes back-dated over fourteen months
(`seed-timeline.py`) and 12 reminders; two runs at 1440 and one at 390 on a
shared four-core machine (ranges are across runs). Today: 1 click from the
dashboard at 1440 (the tab bar); at 390 the phone bar holds Notes, Chat,
Graph and Library, so 2 taps (More, then Timeline); click to painted rows
479 to 767 ms at 1440, 446 ms at 390; 23 controls at 1440, 26 at 390; two
views, Feed and Table (no calendar, section 9). At 1440: 0 controls past the
edge, 1 overlap (a day head's button over its date), 5 targets under 24 px.
At 390 (the table view, which the phone kept): 6 controls past the right
edge (`timeline-view-table` among them) and 3 overlaps (`timeline-search`
over `timeline-view-feed`, `timeline-view-feed` over `timeline-month-btn`,
`timeline-view-table` over `timeline-days-later`). The rail dot's centre sits
on the first line's centre (0 px at 1440; the owner's bug in "Placed from
the owner's list" did not reproduce on this fixture, 390 not measured).
Undo: `timeline.js` makes no writes of its own; its acts are the shared
selection bar's (`batchDelete` and `batchEach` in `skills.js`, both through
`pushUndo`). No model: 0 AI controls; the timeline is whole without one.
**The bar:** Apple Journal and Day One (on this day, media rows, a heat
strip), Things' Logbook, Google Photos' scrubber (year and month labels that
never collide).

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | The dock at 390 and 320: the view segment, search and month controls wrap into one row or move into the dock's menu | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 2 | fix | The day head's button beside its date, not over it; the five small targets at 24 px, 44 px on a coarse pointer | overlap 1 to 0 at 1440; small targets 5 to 0 | 7, 9, 11 |
| 3 | fix | `undo.js` drives the selection bar from the timeline (move, tag, favourite, archive, delete) | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 4 | expansion | The calendar as the third view (section 9) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 5 | expansion | Typed entries land on the day they name ("yesterday lunch with Sam") through the one quick-add grammar (CHAT_PLAN decision 50) | the parsed day equals the row's day on a 20-phrase set | 12, 10 |
| 6 | redesign | Scrubber and month ticks from D3's time scale (VC2 above) | no label overlap at 390; the hand-rolled tick lines deleted | 7, 11 |
| 7 | expansion | "On this day" and a year strip on the timeline, not only the dashboard | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 8 | optimisation | Click to rows 479 to 767 ms with 96 notes: under 300 ms, and under 800 ms on the 5,000-note scale fixture (`scale_test.py`) | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |

**Briefs.** 41 (row 2), 66 (row 5), 75 (row 6); 55's row 4 and 85's rows 1,
3, 7 and 8 are built.

## 11. Deepened 2026-10-10: reminders and notifications (Brief 72b, decisions 69 and 71)

Same sweep and fixture. Today: 1 click at 1440, 2 taps at 390 (More); click
to list 218 to 551 ms at 1440, 1,194 ms at 390; 88 to 93 controls at 1440, 79
at 390. Quick add: "dentist friday at 9am" saved in 235 to 496 ms with
"Added "Dentist": in 6 days" (the right Friday); 0 chips while typing
(decision 50 unbuilt); at 390 the quick-add row was not visible and the
phone's compose was not driven. Overflow: 0 past the edge at both widths; 7
overlaps at 1440, the closed presets menu ("Tonight 7pm", "Tomorrow 9am")
laid out over the Open, All and Done chips (the closed-menu shape Brief 72a
found in the documents dock); 5 at 390 (the view toggle over the chips, a
ghost button over `reminders-new`). Undo: 3 of 6 acts (delete, snooze, clear
completed; not create, complete, edit; static read of `shell-reminders.js`).
Notifications: the page polls `/reminders` every 60 s (`REMINDER_POLL_MS`,
`status.js`), plays a chime, records an in-app notification and posts a
`Notification` only while a tab is open and permission is granted (asked
when a reminder is set); `sw.js` has no reminder code, so a closed tab
fires nothing, and the desktop launcher (`__main__.py`) has no notification
path. A due time is up to 60 s late. ICS export exists (all, and per
reminder); no import. Recurrence: none, daily, weekly, monthly. No model:
the parser (`/reminders/parse`) is deterministic; 1 AI control ("Ask Atlas
about this") stays enabled. **The bar:** Apple Reminders (the OS notifies
with the app closed, early alerts, chips as you type), Things (quick entry
from a global key, This Evening), Todoist's recurrence grammar ("every
other Tuesday", "last Friday of the month").

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | Undo for create, complete and edit through `pushUndo` (create's inverse is the bin) | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 2 | fix | The closed presets menu does not lay out (`hidden` until opened) | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 3 | expansion | Decision 69, desktop: the launcher posts the OS notification for a due reminder | Built 2026-10-11 (Brief 86): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 86)" | |
| 4 | expansion | Decision 69, browser and PWA: the service worker shows the notification, Done and Snooze 10 minutes as its actions | Built 2026-10-11 (Brief 86): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 86)" | |
| 5 | fix | Fire on time: a timer set to the next due time, the 60 s poll kept as the backstop | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 6 | fix | A blocked permission says so once, in the reminders head and in Settings, with how to allow it per browser; the chime and the bell stay | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 7 | expansion | Live chips in the quick-add row (CHAT_PLAN decision 50) and the same row at 390 | chips within 150 ms; the saved value equals the chips; the row present at 390 | 12, 8 |
| 8 | expansion | Recurrence beyond four (every weekday, every 2 weeks, last Friday) and early alerts ("1 day before") | Built 2026-10-10 (Brief 85): HISTORY.md, "Moved from the plans, 2026-10-10 (TIMELINE Brief 85)" | |
| 9 | expansion | ICS import (section 9 decision 17) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |

**Briefs.** 66 (row 7); 55's row 9, 85's rows 1, 2, 5, 6 and 8 and 86's
rows 3 and 4 are built.

## 12. Deepened 2026-10-10: the calendar (Brief 72b, decision 71)

Same sweep and fixture. Today a calendar exists in the reminders tab, not in
the timeline: `renderReminderCalendar` (`shell-reminders.js`) draws a month
of 35 cells, 11 with dots, no titles in any cell; cells 190 by 60 px at
1440 and 42 by 60 at 390; 0 cells overflow; open 258 to 282 ms; no week
view; 0 drag handlers (no reschedule by drag); notes, day notes and meetings
are not on it. At 390, 7 overlaps (the view toggle's icon buttons over the
chips and "Jump to this month"). Section 9 (decisions 14 to 18) puts the
calendar in the timeline from the row model; the reminders grid is a second
calendar that section 9 does not mention. **The bar:** Fantastical (titles
in month cells, a week of hour rows, typed events), Apple Calendar (drag to
reschedule, week view), Google Calendar's agenda on the phone.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | redesign | One calendar (decision 19, INBOX 768) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 2 | fix | Titles in month cells, three rows and "+n" (decision 14) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 3 | expansion | Drag to reschedule with the undo bar (decision 16) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 4 | expansion | Week grid with hour rows; agenda below 768 | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 5 | expansion | Notes as dots, day notes as heads, meetings on the grid (decision 15) | Built 2026-10-11 (Brief 55): HISTORY.md, "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" | |
| 6 | expansion | `N` on a day opens quick add with the day filled (decision 18, CHAT_PLAN decision 50) | Built 2026-10-17 (INBOX 904 B72): HISTORY.md, "Moved from the plans, 2026-10-17 (TIMELINE B72)" | |

**Briefs.** Rows 1 to 6 are built.
